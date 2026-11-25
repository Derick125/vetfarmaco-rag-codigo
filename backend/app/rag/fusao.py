"""Fusão por Reciprocal Rank Fusion (docs/RAG_SPEC.md §3.3).

RRF (Cormack, Clarke & Büttcher, SIGIR 2009) usa só a *posição* de cada
`chunk_id` em cada ranking — nunca o escore original das estratégias, que
não são comparáveis na mesma escala (similaridade de cosseno em [0, 1] vs.
BM25 sem teto). `k = 60` é o valor do trabalho original e do TCC — **não**
usar 50 (o exemplo da documentação do Supabase, ver RAG_SPEC.md §3.3).
"""

from __future__ import annotations

from collections.abc import Sequence

K_PADRAO = 60
QTD_PADRAO = 10  # top-10 do fundido compõe o contexto (RAG_SPEC.md §3.3)


def rrf(rankings: list[list[str]], k: int = K_PADRAO) -> dict[str, float]:
    """Implementação de referência de RAG_SPEC.md §3.3.

    Cada `ranking` é uma lista de `chunk_id`, do mais para o menos
    relevante. Devolve `{chunk_id: escore_fundido}`, do maior para o menor.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for posicao, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + posicao)
    return dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))


def fundir(
    *resultados: Sequence[tuple[str, float]], k: int = K_PADRAO, qtd: int = QTD_PADRAO
) -> list[tuple[str, float]]:
    """Funde resultados no formato `(chunk_id, escore)` de cada retriever
    (`rag.retriever_vetorial.buscar`, `rag.retriever_lexical.buscar`) —
    extrai só a ordem de cada um (`rrf`, acima) e devolve os `qtd` primeiros
    pares `(chunk_id, escore_fundido)`.
    """
    rankings = [[chunk_id for chunk_id, _escore in resultado] for resultado in resultados]
    fundido = rrf(rankings, k=k)
    return list(fundido.items())[:qtd]
