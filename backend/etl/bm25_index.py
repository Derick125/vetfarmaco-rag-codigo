"""Construção do índice BM25 lexical (docs/RAG_SPEC.md §3.2).

`bm25s`, tokenização com remoção de stopwords em português e stemmer
RSLP (o "Removedor de Sufixos da Língua Portuguesa" do NLTK — a
alternativa Snowball citada no RAG_SPEC é o mesmo algoritmo genérico
instanciado para português; RSLP foi desenhado especificamente para a
língua). `k1` e `b` vêm de `Settings` (`docs/RAG_SPEC.md` §3.2, TCC §4.2:
hiperparâmetros ajustáveis, não fixos no código).

O índice é persistido em `backend/data/bm25_index/` e carregado depois na
inicialização do serviço por `app/rag/retriever_lexical.py` — a
tokenização (stopwords + stemmer) usada na consulta precisa ser
exatamente a mesma usada aqui na construção, ou o BM25 não casa nada.

Uso:
    python -m etl.bm25_index --entrada chunks.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import bm25s
import nltk
import structlog

from app.config import get_settings

logger = structlog.get_logger()

DIRETORIO_INDICE_PADRAO = Path(__file__).resolve().parent.parent / "data" / "bm25_index"


def _garantir_dados_nltk() -> None:
    for pacote, caminho in (("stopwords", "corpora/stopwords"), ("rslp", "stemmers/rslp")):
        try:
            nltk.data.find(caminho)
        except LookupError:
            nltk.download(pacote, quiet=True)


def stopwords_pt() -> list[str]:
    _garantir_dados_nltk()
    from nltk.corpus import stopwords

    return stopwords.words("portuguese")


def stemmer_rslp():
    """Retorna um stemmer em lote — `bm25s.tokenize` chama o stemmer com a
    lista inteira de tokens únicos de uma vez, não um token por vez."""
    _garantir_dados_nltk()
    from nltk.stem import RSLPStemmer

    rslp = RSLPStemmer()
    return lambda tokens: [rslp.stem(token) for token in tokens]


def construir_indice(chunk_ids: list[str], textos: list[str], k1: float, b: float) -> bm25s.BM25:
    """Tokeniza (stopwords PT + stemmer RSLP) e indexa. `corpus` guarda só
    o `chunk_id` — o texto completo já vive no Postgres (`etl/load.py`)."""
    tokens = bm25s.tokenize(
        textos,
        stopwords=stopwords_pt(),
        stemmer=stemmer_rslp(),
        show_progress=False,
    )
    corpus = [{"chunk_id": chunk_id} for chunk_id in chunk_ids]
    indice = bm25s.BM25(k1=k1, b=b, corpus=corpus)
    indice.index(tokens, show_progress=False)
    return indice


def salvar_indice(indice: bm25s.BM25, diretorio: Path) -> None:
    diretorio.mkdir(parents=True, exist_ok=True)
    indice.save(str(diretorio), corpus=indice.corpus, show_progress=False)


def _ler_chunks(caminho: Path) -> list[dict]:
    return [
        json.loads(linha)
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entrada", required=True, type=Path, help="JSONL de chunks (etl/chunk.py ou etl/embed.py)"
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=DIRETORIO_INDICE_PADRAO,
        help="Diretório de persistência (default: backend/data/bm25_index/)",
    )
    args = parser.parse_args(argv)

    chunks = _ler_chunks(args.entrada)
    if not chunks:
        logger.warning("nenhum_chunk_na_entrada", caminho=str(args.entrada))
        return 0

    settings = get_settings()
    indice = construir_indice(
        chunk_ids=[c["chunk_id"] for c in chunks],
        textos=[c["texto"] for c in chunks],
        k1=settings.bm25_k1,
        b=settings.bm25_b,
    )
    salvar_indice(indice, args.saida)

    logger.info(
        "indice_bm25_construido",
        chunks=len(chunks),
        k1=settings.bm25_k1,
        b=settings.bm25_b,
        diretorio=str(args.saida),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
