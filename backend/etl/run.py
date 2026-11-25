"""Orquestra o pipeline completo do ETL (docs/RAG_SPEC.md §2).

PDF → extração → limpeza → segmentação → chunking → metadados →
embeddings → carga, mais a construção do índice BM25
(docs/RAG_SPEC.md §3.2).

Processa capítulo por capítulo, a partir de um **mapa de capítulos**
(`--mapa-capitulos`) — uma lista JSON de objetos
`{numero, titulo, pagina_inicial, pagina_final}` (1-indexado, inclusive).
Isso é necessário porque este PDF não tem cabeçalho de capítulo
extraível nem bookmarks (ver `etl/extract.py`); o mapa é construído uma
vez (detecção automática por fonte/QUADRO N.x, validada por amostragem
manual) e reutilizado em cada reprocessamento.
`backend/data/mapa_capitulos.json` é o mapa já construído para a 6ª
edição de Spinosa et al.

Uso:
    python -m etl.run --source data/spinosa.pdf \\
        --mapa-capitulos data/mapa_capitulos.json \\
        --fonte "Spinosa et al. (2017)" --tipo-fonte livro \\
        --titulo "Farmacologia Aplicada à Medicina Veterinária"

    # só extração + chunking + índice BM25, sem gastar API nem tocar o banco
    python -m etl.run --source data/spinosa.pdf \\
        --mapa-capitulos data/mapa_capitulos.json \\
        --fonte "Spinosa et al. (2017)" --tipo-fonte livro \\
        --titulo "..." --pular-embeddings
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg
import structlog
from google import genai
from google.genai import errors
from pgvector.psycopg import register_vector

from app.config import get_settings
from etl.bm25_index import DIRETORIO_INDICE_PADRAO, construir_indice, salvar_indice
from etl.chunk import Chunk, PaginaLida, Vocabulario, carregar_vocabulario, segmentar
from etl.embed import gerar_embeddings
from etl.extract import extrair
from etl.load import RegistroCarga
from etl.load import carregar as carregar_no_banco

logger = structlog.get_logger()

CAMINHO_VOCABULARIO_PADRAO = Path(__file__).parent / "vocabulario" / "farmacos.yaml"


def _ler_mapa_capitulos(caminho: Path) -> list[dict]:
    return json.loads(caminho.read_text(encoding="utf-8"))


def extrair_e_segmentar_livro(
    origem: Path,
    mapa_capitulos: list[dict],
    fonte: str,
    tipo_fonte: str,
    vocabulario: Vocabulario,
) -> list[Chunk]:
    """Roda extração + limpeza + chunking capítulo por capítulo e junta tudo.

    Cada capítulo é extraído e segmentado isoladamente — a janela
    deslizante nunca mistura tokens de dois capítulos diferentes, o que
    manteria uma citação ambígua sobre a que capítulo ela pertence.
    """
    todos_chunks: list[Chunk] = []
    for entrada in mapa_capitulos:
        rotulo_capitulo = f"{entrada['numero']} — {entrada['titulo']}"
        paginas_extraidas = extrair(
            origem, entrada["pagina_inicial"], entrada["pagina_final"], rotulo_capitulo
        )
        paginas_lidas = [
            PaginaLida(numero=p.numero, capitulo=p.capitulo, texto=p.texto, tabelas=p.tabelas)
            for p in paginas_extraidas
        ]
        chunks_capitulo = segmentar(paginas_lidas, fonte, tipo_fonte, vocabulario)
        todos_chunks.extend(chunks_capitulo)
        logger.info(
            "capitulo_processado",
            numero=entrada["numero"],
            titulo=entrada["titulo"],
            paginas=f"{entrada['pagina_inicial']}-{entrada['pagina_final']}",
            chunks=len(chunks_capitulo),
        )
    return todos_chunks


def _serializar_chunk(chunk: Chunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "fonte": chunk.fonte,
        "tipo_fonte": chunk.tipo_fonte,
        "capitulo": chunk.capitulo,
        "pagina": chunk.pagina,
        "farmacos": chunk.farmacos,
        "especies": chunk.especies,
        "tokens": chunk.tokens,
        "texto_hash": chunk.texto_hash,
        "texto": chunk.texto,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Caminho do PDF de origem")
    parser.add_argument("--mapa-capitulos", required=True, type=Path)
    parser.add_argument("--fonte", required=True, help='Ex.: "Spinosa et al. (2017)"')
    parser.add_argument("--tipo-fonte", required=True, choices=["livro", "bula"])
    parser.add_argument(
        "--titulo", required=True, help='Ex.: "Farmacologia Aplicada à Medicina Veterinária"'
    )
    parser.add_argument("--vocabulario", type=Path, default=CAMINHO_VOCABULARIO_PADRAO)
    parser.add_argument(
        "--saida-chunks",
        type=Path,
        default=None,
        help="Grava o JSONL intermediário de chunks (sem embedding); opcional",
    )
    parser.add_argument(
        "--pular-embeddings",
        action="store_true",
        help="Só extrai/limpa/segmenta e constrói o índice BM25 — não chama a API "
        "do Gemini nem toca o Postgres",
    )
    args = parser.parse_args(argv)

    mapa_capitulos = _ler_mapa_capitulos(args.mapa_capitulos)
    vocabulario = carregar_vocabulario(args.vocabulario)

    chunks = extrair_e_segmentar_livro(
        args.source, mapa_capitulos, args.fonte, args.tipo_fonte, vocabulario
    )
    logger.info("extracao_e_chunking_concluidos", total_chunks=len(chunks))

    if args.saida_chunks:
        linhas = [json.dumps(_serializar_chunk(c), ensure_ascii=False) for c in chunks]
        args.saida_chunks.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        logger.info("chunks_gravados", caminho=str(args.saida_chunks), linhas=len(linhas))

    settings = get_settings()
    indice_bm25 = construir_indice(
        chunk_ids=[c.chunk_id for c in chunks],
        textos=[c.texto for c in chunks],
        k1=settings.bm25_k1,
        b=settings.bm25_b,
    )
    salvar_indice(indice_bm25, DIRETORIO_INDICE_PADRAO)
    logger.info(
        "indice_bm25_construido", chunks=len(chunks), diretorio=str(DIRETORIO_INDICE_PADRAO)
    )

    if args.pular_embeddings:
        return 0

    if not settings.gemini_api_key:
        logger.error("gemini_api_key_ausente", mensagem="Defina GEMINI_API_KEY em backend/.env.")
        return 1
    if not settings.database_url:
        logger.error("database_url_ausente", mensagem="Defina DATABASE_URL em backend/.env.")
        return 1

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        embeddings = gerar_embeddings(client, [c.texto for c in chunks])
    except errors.ClientError as erro:
        logger.error("falha_ao_gerar_embeddings", erro=str(erro))
        return 1

    registros = [
        RegistroCarga(
            chunk_id=c.chunk_id,
            fonte=c.fonte,
            tipo_fonte=c.tipo_fonte,
            capitulo=c.capitulo,
            pagina=c.pagina,
            farmacos=c.farmacos,
            especies=c.especies,
            tokens=c.tokens,
            texto_hash=c.texto_hash,
            texto=c.texto,
            embedding=embedding,
        )
        for c, embedding in zip(chunks, embeddings, strict=True)
    ]

    try:
        with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
            register_vector(conn)
            resultado = carregar_no_banco(conn, registros, args.titulo)
    except psycopg.OperationalError as erro:
        logger.error("falha_de_conexao", erro=str(erro))
        return 1

    logger.info("pipeline_concluido", chunks_totais=len(chunks), **resultado)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
