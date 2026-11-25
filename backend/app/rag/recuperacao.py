"""Recuperação híbrida (docs/RAG_SPEC.md §3): vetorial + BM25, fundidos por RRF.

Duas formas, com o **mesmo resultado** (verificado por
`scripts.verificar_equivalencia_recuperacao` sobre as 30 queries do gold set):

- `recuperar`: sequencial, conexão dada. É a referência (e o que os scripts usam).
- `recuperar_paralelo`: o caminho do endpoint. Conexão tirada de um pool reutilizado
  entre requisições, cliente Gemini reutilizado, e embedding, BM25 e retirada da
  conexão rodando ao mesmo tempo. A busca vetorial depende do embedding e a carga dos
  trechos depende da fusão, então essas etapas continuam em sequência.

Nada aqui muda o que é recuperado: mesmos retrievers, mesmos parâmetros (`QTD_*`,
`K_PADRAO`), mesma fusão. Em particular, **não há filtro de espécie nem de fármaco**.
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import bm25s
import psycopg
import structlog
from google import genai
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from app.rag.fusao import K_PADRAO, fundir
from app.rag.gerador import Trecho, carregar_trechos
from app.rag.retriever_lexical import buscar as buscar_lexical
from app.rag.retriever_vetorial import buscar as buscar_vetorial
from etl.embed import gerar_embeddings

logger = structlog.get_logger()

QTD_RETRIEVER = 30
QTD_CONTEXTO = 10  # RAG_SPEC.md §3.3: top-10 do fundido compõe o contexto
TAMANHO_POOL = 4


@dataclass
class Recuperacao:
    trechos: list[Trecho]
    # Tempos de parede de cada etapa (ms). Em `recuperar_paralelo` as três primeiras
    # se sobrepõem, então a soma passa de `ms_total`.
    ms_embedding: float = 0.0
    ms_busca_vetorial: float = 0.0
    ms_busca_lexical: float = 0.0
    ms_fusao: float = 0.0
    ms_carga_trechos: float = 0.0
    ms_conexao: float = 0.0
    ms_total: float = 0.0
    # Rankings intermediários, para a verificação de equivalência.
    semanticos: list[tuple[str, float]] = field(default_factory=list)
    lexicais: list[tuple[str, float]] = field(default_factory=list)
    fundidos: list[tuple[str, float]] = field(default_factory=list)


def _ms(inicio: float) -> float:
    return (time.perf_counter() - inicio) * 1000


EmbeddingFn = Callable[[genai.Client, str], list[float]]


def embedding_da_consulta(client: genai.Client, pergunta: str) -> list[float]:
    return gerar_embeddings(client, [pergunta], task_type="RETRIEVAL_QUERY")[0]


def recuperar(
    conn: psycopg.Connection,
    client: genai.Client,
    indice_bm25: bm25s.BM25 | None,
    pergunta: str,
    *,
    embedding_fn: EmbeddingFn = embedding_da_consulta,
) -> Recuperacao:
    """Sequencial: embedding → vetorial → BM25 → fusão → carga dos trechos."""
    inicio = time.perf_counter()
    t = time.perf_counter()
    embedding = embedding_fn(client, pergunta)
    ms_embedding = _ms(t)
    t = time.perf_counter()
    semanticos = buscar_vetorial(conn, embedding, qtd=QTD_RETRIEVER)
    ms_vetorial = _ms(t)
    t = time.perf_counter()
    lexicais = _lexical(indice_bm25, pergunta)
    ms_lexical = _ms(t)
    return _concluir(
        conn, inicio, semanticos, lexicais, ms_embedding, ms_vetorial, ms_lexical, ms_conexao=0.0
    )


def _lexical(indice_bm25: bm25s.BM25 | None, pergunta: str) -> list[tuple[str, float]]:
    return (
        buscar_lexical(indice_bm25, pergunta, qtd=QTD_RETRIEVER) if indice_bm25 is not None else []
    )


def _concluir(
    conn: psycopg.Connection,
    inicio: float,
    semanticos: list[tuple[str, float]],
    lexicais: list[tuple[str, float]],
    ms_embedding: float,
    ms_vetorial: float,
    ms_lexical: float,
    ms_conexao: float,
) -> Recuperacao:
    t = time.perf_counter()
    fundidos = fundir(semanticos, lexicais, k=K_PADRAO, qtd=QTD_CONTEXTO)
    ms_fusao = _ms(t)
    t = time.perf_counter()
    trechos = carregar_trechos(conn, [chunk_id for chunk_id, _ in fundidos])
    ms_carga = _ms(t)
    return Recuperacao(
        trechos=trechos,
        ms_embedding=ms_embedding,
        ms_busca_vetorial=ms_vetorial,
        ms_busca_lexical=ms_lexical,
        ms_fusao=ms_fusao,
        ms_carga_trechos=ms_carga,
        ms_conexao=ms_conexao,
        ms_total=_ms(inicio),
        semanticos=semanticos,
        lexicais=lexicais,
        fundidos=fundidos,
    )


# --- Reutilização de conexão e de cliente ---------------------------------------------

_pool: ConnectionPool | None = None


def obter_pool(database_url: str) -> ConnectionPool:
    """Pool único do processo, criado na primeira consulta (não na subida do serviço,
    que não pode depender do banco). `check` descarta conexão que o servidor derrubou
    por ociosidade antes de entregá-la."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            database_url,
            min_size=1,
            max_size=TAMANHO_POOL,
            kwargs={"connect_timeout": 10},
            configure=register_vector,
            check=ConnectionPool.check_connection,
            open=True,
        )
    return _pool


def fechar_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@functools.lru_cache(maxsize=2)
def obter_cliente(api_key: str) -> genai.Client:
    """Um cliente por chave, reutilizado (mantém as conexões HTTP abertas)."""
    return genai.Client(api_key=api_key)


async def recuperar_paralelo(
    pool: ConnectionPool,
    client: genai.Client,
    indice_bm25: bm25s.BM25 | None,
    pergunta: str,
    *,
    embedding_fn: EmbeddingFn = embedding_da_consulta,
) -> Recuperacao:
    """Embedding, BM25 e retirada da conexão do pool ao mesmo tempo; depois a busca
    vetorial (precisa do embedding), a fusão e a carga dos trechos, na conexão já em mãos."""
    inicio = time.perf_counter()

    def com_tempo(funcao: Callable[[], object]) -> Callable[[], tuple[object, float]]:
        def corpo() -> tuple[object, float]:
            t = time.perf_counter()
            return funcao(), _ms(t)

        return corpo

    resultados = await asyncio.gather(
        asyncio.to_thread(com_tempo(lambda: embedding_fn(client, pergunta))),
        asyncio.to_thread(com_tempo(lambda: _lexical(indice_bm25, pergunta))),
        asyncio.to_thread(com_tempo(pool.getconn)),
        return_exceptions=True,
    )
    falha = next((r for r in resultados if isinstance(r, BaseException)), None)
    if falha is not None:
        # A conexão pode ter sido retirada mesmo com outra etapa falhando: devolve.
        if not isinstance(resultados[2], BaseException):
            pool.putconn(resultados[2][0])  # type: ignore[arg-type]
        raise falha
    (embedding, ms_embedding), (lexicais, ms_lexical), (conn, ms_conexao) = resultados  # type: ignore[misc]
    try:

        def vetorial() -> tuple[list[tuple[str, float]], float]:
            t = time.perf_counter()
            return buscar_vetorial(conn, embedding, qtd=QTD_RETRIEVER), _ms(t)  # type: ignore[arg-type]

        semanticos, ms_vetorial = await asyncio.to_thread(vetorial)
        return await asyncio.to_thread(
            _concluir,
            conn,  # type: ignore[arg-type]
            inicio,
            semanticos,
            lexicais,  # type: ignore[arg-type]
            ms_embedding,
            ms_vetorial,
            ms_lexical,
            ms_conexao,
        )
    finally:
        conn.rollback()  # type: ignore[attr-defined]  # só leitura: encerra a transação aberta
        pool.putconn(conn)  # type: ignore[arg-type]
