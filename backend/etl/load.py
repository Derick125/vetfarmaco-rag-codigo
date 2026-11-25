"""Carga idempotente no Postgres (docs/DATABASE.md §2, docs/RAG_SPEC.md §2).

Carrega os chunks com embedding (saída de `etl/embed.py`) nas tabelas
`documento` e `chunk`. Idempotente por `texto_hash`: como `texto_hash` não
tem restrição `unique` no schema (só `chunk_id` tem), a checagem é feita
em Python — cada chunk é conferido por hash antes de inserir, e
reprocessar o mesmo PDF não duplica linhas.

Antes disso, dentro do PRÓPRIO lote recebido, funde chunks com texto
CLINICAMENTE idêntico — mesmo hash sobre o texto normalizado (minúsculo,
espaços colapsados, pontuação preservada) — num só
(`_deduplicar_por_texto_normalizado`). Comum em bula RCM/SPC com mais de
um ciclo de produto (`etl/extract_bula.py`,
`_atribuir_ciclo_de_produto`): dois ciclos podem repetir o mesmo parágrafo
clínico palavra por palavra. Mantém a ocorrência do ciclo com mais
espécies documentadas (o "mais completo"); as demais são só registradas em
log (`chunks_fundidos_por_texto_identico`), nunca inseridas. NUNCA funde
por similaridade/limiar — só igualdade exata após normalização, para que
uma diferença clínica real entre ciclos (uma frase a mais, uma dose
diferente) jamais seja apagada por engano.

Registra `indice_versao` (data + hash do corpus) na linha de `documento`
— é o que a tela de ajustes do app expõe para rastreabilidade científica
(TCC §4.7).

Uso:
    python -m etl.load --entrada chunks_com_embedding.jsonl \\
        --titulo "Farmacologia Aplicada à Medicina Veterinária"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import psycopg
import structlog
from pgvector.psycopg import register_vector

from app.config import get_settings

logger = structlog.get_logger()

_PADRAO_ESPACOS = re.compile(r"\s+")


@dataclass
class RegistroCarga:
    """Um chunk pronto para carga — chunk.py + embed.py já preencheram tudo.

    `secao`, `origem` e `produto` são metadados de BULA (seção canônica,
    humana|veterinaria, produto/ciclo — vindos do manifesto e do preview
    de `etl/extract_bula.py`, nunca de casamento de texto) — `None` para
    chunk de livro, que não tem nenhum desses conceitos.
    """

    chunk_id: str
    fonte: str
    tipo_fonte: str
    capitulo: str | None
    pagina: int
    farmacos: list[str]
    especies: list[str]
    tokens: int
    texto_hash: str
    texto: str
    embedding: list[float]
    secao: str | None = None
    origem: str | None = None
    produto: str | None = None


def calcular_indice_versao(hashes_dos_chunks: list[str]) -> str:
    """`indice_versao` = data + hash do corpus (docs/DATABASE.md §2).

    O hash é sobre o conjunto (ordenado, para ser determinístico) de
    `texto_hash` do lote — muda se, e só se, o conteúdo do corpus mudar.
    """
    hash_corpus = hashlib.sha256("".join(sorted(hashes_dos_chunks)).encode("utf-8")).hexdigest()
    return f"{date.today():%Y%m%d}-{hash_corpus[:12]}"


def _normalizar_para_dedup(texto: str) -> str:
    """Minúsculo, espaços colapsados, pontuação preservada.

    Cobre variação incidental de formatação entre ciclos (espaço duplo,
    quebra de linha a mais, caixa inconsistente) que o `texto_hash` bruto
    — igualdade byte a byte — não pega. Pontuação fica porque diferença de
    pontuação pode ser diferença clínica real (ex. uma vírgula que muda a
    condição a que uma dose se aplica); só grafia/espaçamento são ruído
    aqui.
    """
    return _PADRAO_ESPACOS.sub(" ", texto.lower()).strip()


def _hash_normalizado(texto: str) -> str:
    return hashlib.sha256(_normalizar_para_dedup(texto).encode("utf-8")).hexdigest()


def _chave_completude(registro: RegistroCarga) -> tuple[int, int, int]:
    """Quanto maior, mais "completo" o ciclo que este chunk representa —
    usado só para desempate entre chunks cujo texto é idêntico por
    definição (é assim que caíram no mesmo grupo de fusão): mais espécies
    documentadas, depois mais fármacos citados, depois mais tokens. Se
    tudo empatar, `max` mantém o primeiro da ordem original de entrada —
    determinístico, mas arbitrário nesse caso extremo.
    """
    return (len(registro.especies), len(registro.farmacos), registro.tokens)


def _deduplicar_por_texto_normalizado(registros: list[RegistroCarga]) -> list[RegistroCarga]:
    """Funde, DENTRO do lote recebido, chunks cujo texto normalizado
    (`_normalizar_para_dedup`) é idêntico — nunca compara contra o que já
    está no banco (isso é o `texto_hash` bruto, já idempotente, ver
    `carregar`) e nunca funde por similaridade/limiar, só por igualdade
    exata. Para cada grupo fundido, mantém a ocorrência mais completa
    (`_chave_completude`) e registra em log quais `chunk_id` foram
    descartados a favor de qual.
    """
    grupos: dict[str, list[RegistroCarga]] = {}
    ordem: list[str] = []
    for registro in registros:
        chave = _hash_normalizado(registro.texto)
        if chave not in grupos:
            ordem.append(chave)
        grupos.setdefault(chave, []).append(registro)

    resultado: list[RegistroCarga] = []
    for chave in ordem:
        grupo = grupos[chave]
        if len(grupo) == 1:
            resultado.append(grupo[0])
            continue
        mantido = max(grupo, key=_chave_completude)
        fundidos = [r.chunk_id for r in grupo if r.chunk_id != mantido.chunk_id]
        logger.info(
            "chunks_fundidos_por_texto_identico",
            chunk_id_mantido=mantido.chunk_id,
            chunk_ids_fundidos=fundidos,
            especies_mantidas=mantido.especies,
        )
        resultado.append(mantido)
    return resultado


def _obter_ou_criar_documento(
    conn: psycopg.Connection,
    titulo: str,
    tipo_fonte: str,
    referencia: str,
    indice_versao: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "select id from documento where titulo = %s and tipo_fonte = %s and referencia = %s",
            (titulo, tipo_fonte, referencia),
        )
        linha = cur.fetchone()
        if linha is not None:
            documento_id = linha[0]
            cur.execute(
                "update documento set indice_versao = %s where id = %s",
                (indice_versao, documento_id),
            )
            logger.info(
                "documento_reutilizado", documento_id=documento_id, indice_versao=indice_versao
            )
            return documento_id

        cur.execute(
            """
            insert into documento (titulo, tipo_fonte, referencia, indice_versao)
            values (%s, %s, %s, %s)
            returning id
            """,
            (titulo, tipo_fonte, referencia, indice_versao),
        )
        documento_id = cur.fetchone()[0]
        logger.info("documento_criado", documento_id=documento_id, indice_versao=indice_versao)
        return documento_id


def carregar(
    conn: psycopg.Connection, registros: list[RegistroCarga], titulo: str
) -> dict[str, int]:
    """Carrega os chunks de forma idempotente por `texto_hash`.

    Primeiro funde, dentro do lote, chunks com texto normalizado idêntico
    (`_deduplicar_por_texto_normalizado`) — comum entre ciclos de produto
    de uma mesma bula RCM/SPC. Só depois disso calcula `indice_versao` e
    checa idempotência contra o banco, então o hash do corpus e a
    contagem de "já existentes" refletem o conteúdo já deduplicado, não a
    repetição bruta.

    A checagem de idempotência é uma única consulta em lote (não uma por
    chunk — em corpora de milhares de chunks isso é a diferença entre
    minutos e dezenas de minutos). Os `insert`s novos rodam dentro de
    `conn.pipeline()`, que manda os comandos sem esperar a resposta de
    cada um antes de enviar o próximo.

    Retorna `{"inseridos": N, "ja_existentes": M, "fundidos": F}` — `F` é
    quantos chunks do lote original foram descartados por serem
    texto-idênticos a outro (nunca chegam a ser conferidos contra o banco
    nem inseridos).
    """
    if not registros:
        return {"inseridos": 0, "ja_existentes": 0, "fundidos": 0}

    total_recebido = len(registros)
    registros = _deduplicar_por_texto_normalizado(registros)
    fundidos = total_recebido - len(registros)

    fonte = registros[0].fonte
    tipo_fonte = registros[0].tipo_fonte
    indice_versao = calcular_indice_versao([r.texto_hash for r in registros])

    documento_id = _obter_ou_criar_documento(conn, titulo, tipo_fonte, fonte, indice_versao)

    todos_hashes = [r.texto_hash for r in registros]
    with conn.cursor() as cur:
        cur.execute("select texto_hash from chunk where texto_hash = any(%s)", (todos_hashes,))
        hashes_existentes = {linha[0] for linha in cur.fetchall()}

    novos = [r for r in registros if r.texto_hash not in hashes_existentes]

    with conn.pipeline(), conn.cursor() as cur:
        for registro in novos:
            cur.execute(
                """
                insert into chunk (
                    chunk_id, documento_id, texto, texto_hash, capitulo,
                    pagina, farmacos, especies, tokens, embedding,
                    secao, origem, produto
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    registro.chunk_id,
                    documento_id,
                    registro.texto,
                    registro.texto_hash,
                    registro.capitulo,
                    registro.pagina,
                    registro.farmacos,
                    registro.especies,
                    registro.tokens,
                    registro.embedding,
                    registro.secao,
                    registro.origem,
                    registro.produto,
                ),
            )

    resultado = {
        "inseridos": len(novos),
        "ja_existentes": len(registros) - len(novos),
        "fundidos": fundidos,
    }
    logger.info(
        "carga_concluida", documento_id=documento_id, indice_versao=indice_versao, **resultado
    )
    return resultado


def _ler_registros(caminho: Path) -> list[RegistroCarga]:
    registros = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        dados = json.loads(linha)
        registros.append(
            RegistroCarga(
                chunk_id=dados["chunk_id"],
                fonte=dados["fonte"],
                tipo_fonte=dados["tipo_fonte"],
                capitulo=dados.get("capitulo"),
                pagina=dados["pagina"],
                farmacos=dados.get("farmacos", []),
                especies=dados.get("especies", []),
                tokens=dados["tokens"],
                texto_hash=dados["texto_hash"],
                texto=dados["texto"],
                embedding=dados["embedding"],
                secao=dados.get("secao"),
                origem=dados.get("origem"),
                produto=dados.get("produto"),
            )
        )
    return registros


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entrada",
        required=True,
        type=Path,
        help="JSONL de chunks+embedding produzido por etl/embed.py",
    )
    parser.add_argument(
        "--titulo",
        required=True,
        help='Título do documento, ex.: "Farmacologia Aplicada à Medicina Veterinária"',
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if not settings.database_url:
        logger.error("database_url_ausente", mensagem="Defina DATABASE_URL em backend/.env.")
        return 1

    registros = _ler_registros(args.entrada)
    if not registros:
        logger.warning("nenhum_registro_na_entrada", caminho=str(args.entrada))
        return 0

    try:
        with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
            register_vector(conn)
            resultado = carregar(conn, registros, args.titulo)
    except psycopg.OperationalError as erro:
        logger.error("falha_de_conexao", erro=str(erro))
        return 1

    logger.info("fim", **resultado)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
