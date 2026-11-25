"""Retriever lexical BM25 (docs/RAG_SPEC.md §3.2).

Carrega, na inicialização do serviço (ver `app/main.py`), o índice
construído por `etl/bm25_index.py` e persistido em
`backend/data/bm25_index/`. A tokenização da consulta (stopwords em
português + stemmer RSLP) é a mesma usada na construção — reexportada de
`etl.bm25_index` para as duas nunca divergirem.

Top-30 por padrão (docs/RAG_SPEC.md §3.2).
"""

from __future__ import annotations

from pathlib import Path

import bm25s
import structlog

from etl.bm25_index import DIRETORIO_INDICE_PADRAO, stemmer_rslp, stopwords_pt

logger = structlog.get_logger()

QTD_PADRAO = 30


def carregar_indice(diretorio: Path | None = None) -> bm25s.BM25 | None:
    """Carrega o índice persistido.

    Retorna `None` (com um aviso, sem derrubar a inicialização) se o
    índice ainda não foi construído — o serviço deve subir mesmo antes do
    ETL rodar; a recuperação lexical simplesmente fica indisponível até lá.
    """
    diretorio = diretorio or DIRETORIO_INDICE_PADRAO
    if not diretorio.exists():
        logger.warning("indice_bm25_ausente", diretorio=str(diretorio))
        return None

    indice = bm25s.BM25.load(str(diretorio), load_corpus=True, show_progress=False)
    logger.info(
        "indice_bm25_carregado",
        diretorio=str(diretorio),
        documentos=len(indice.corpus),
        k1=indice.k1,
        b=indice.b,
    )
    return indice


def buscar(indice: bm25s.BM25, consulta: str, qtd: int = QTD_PADRAO) -> list[tuple[str, float]]:
    """Retorna até `qtd` pares `(chunk_id, escore)`, do mais para o menos relevante."""
    qtd = min(qtd, len(indice.corpus))
    if qtd <= 0:
        return []

    tokens_consulta = bm25s.tokenize(
        [consulta],
        stopwords=stopwords_pt(),
        stemmer=stemmer_rslp(),
        show_progress=False,
    )
    documentos, escores = indice.retrieve(tokens_consulta, k=qtd, show_progress=False)
    return [
        (documento["chunk_id"], float(escore))
        for documento, escore in zip(documentos[0], escores[0], strict=True)
    ]
