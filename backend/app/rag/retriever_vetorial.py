"""Retriever vetorial (docs/RAG_SPEC.md §3.1).

Top-30 por similaridade de cosseno via a função SQL `buscar_semantico`
(docs/DATABASE.md §4), com filtros opcionais por espécie e fármaco.
`SET LOCAL hnsw.ef_search = 100` favorece recall (a métrica do Quadro 1 do
TCC) às custas de latência — só na sessão da consulta, nunca no índice.

O chamador é responsável por abrir a conexão e chamar
`pgvector.psycopg.register_vector(conn)` antes (mesmo padrão de
`etl/load.py` e `scripts/testar_busca.py`) — este módulo não gerencia o
ciclo de vida da conexão. O embedding da consulta precisa ir como
`pgvector.Vector`, não como `list[float]`: o dumper de `vector` só é
registrado para `Vector`/`numpy.ndarray` (`pgvector/psycopg/vector.py`),
então uma lista comum vira `double precision[]` e a resolução de overload
da função SQL falha (só ocorre nas chamadas de função — um `INSERT` numa
coluna `vector` aceitaria a lista via *assignment cast*).
"""

from __future__ import annotations

import psycopg
from pgvector import Vector

EF_SEARCH = 100
QTD_PADRAO = 30


def buscar(
    conn: psycopg.Connection,
    embedding: list[float],
    qtd: int = QTD_PADRAO,
    filtro_especies: list[str] | None = None,
    filtro_farmacos: list[str] | None = None,
) -> list[tuple[str, float]]:
    """Retorna até `qtd` pares `(chunk_id, similaridade)`, do mais para o
    menos relevante — mesmo formato de `rag.retriever_lexical.buscar`, para
    as duas listas serem intercambiáveis em `rag.fusao.fundir`.

    `filtro_especies`/`filtro_farmacos` casam com qualquer sobreposição
    (`&&`) contra as colunas `chunk.especies`/`chunk.farmacos` — ver
    `buscar_semantico` em `docs/DATABASE.md` §4. `None` (default) não
    filtra.
    """
    with conn.transaction():
        # EF_SEARCH é uma constante do módulo, não entrada do usuário — SET
        # não aceita parâmetro via protocolo estendido (%s), só literal.
        conn.execute(f"set local hnsw.ef_search = {EF_SEARCH}")
        cur = conn.execute(
            "select chunk_id, similaridade "
            "from buscar_semantico("
            "  consulta_embedding => %s,"
            "  filtro_especies => %s,"
            "  filtro_farmacos => %s,"
            "  qtd => %s::int"
            ")",
            (Vector(embedding), filtro_especies, filtro_farmacos, qtd),
        )
        return [(chunk_id, float(similaridade)) for chunk_id, similaridade in cur.fetchall()]
