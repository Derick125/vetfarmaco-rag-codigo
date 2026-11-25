"""Auditoria do Recall@10: híbrido vs. isolados, query a query, com IC bootstrap.

Reusa a recuperação de `eval.recall_at_k` (mesmo gold set, mesmas três
estratégias) e grava `data/audit/recall_final.md` com:
  - vitórias / empates / derrotas do híbrido por query;
  - IC 95% por bootstrap pareado (reamostra queries) da diferença de médias;
  - curva de estabilização: Recall@10 médio acumulado por bloco de queries.

Uso:
    uv run python -m eval.auditoria_recall
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import psycopg
from google import genai
from pgvector.psycopg import register_vector
from ranx import Qrels, Run, evaluate

from app.config import get_settings
from app.rag.retriever_lexical import carregar_indice
from eval.recall_at_k import (
    CAMINHO_QRELS_PADRAO,
    _carregar_qrels,
    _executar_estrategias,
)

CAMINHO_SAIDA_PADRAO = Path(__file__).resolve().parent.parent / "data" / "audit" / "recall_final.md"
N_REAMOSTRAGENS = 10_000
SEMENTE = 42
TAMANHO_BLOCO = 4


def _recall10_por_query(qrels: Qrels, run_dict: dict, ids: list[str]) -> np.ndarray:
    run = Run.from_dict(run_dict)
    por_query = evaluate(qrels, run, "recall@10", return_mean=False)
    # ranx devolve na ordem de qrels.qrels; mapeia explicitamente por id.
    ordem = list(qrels.qrels.keys())
    mapa = dict(zip(ordem, por_query, strict=True))
    return np.array([mapa[i] for i in ids], dtype=float)


def _vde(hibrido: np.ndarray, outro: np.ndarray) -> tuple[int, int, int]:
    iguais = np.isclose(hibrido, outro)
    vitorias = int(np.sum((hibrido > outro) & ~iguais))
    derrotas = int(np.sum((hibrido < outro) & ~iguais))
    return vitorias, int(iguais.sum()), derrotas


def _bootstrap(diferencas: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    n = len(diferencas)
    indices = rng.integers(0, n, size=(N_REAMOSTRAGENS, n))
    medias = diferencas[indices].mean(axis=1)
    baixo, alto = np.percentile(medias, [2.5, 97.5])
    return float(diferencas.mean()), float(baixo), float(alto)


def _curva(ids: list[str], series: dict[str, np.ndarray]) -> list[str]:
    n = len(ids)
    linhas = [
        "| bloco | queries acumuladas | "
        + " | ".join(series)
        + " | Δ híbrido−semântico | Δ híbrido−lexical |",
        "|---|---|" + "---|" * (len(series) + 2),
    ]
    for bloco in range(math.ceil(n / TAMANHO_BLOCO)):
        fim = min((bloco + 1) * TAMANHO_BLOCO, n)
        medias = {nome: float(v[:fim].mean()) for nome, v in series.items()}
        d_sem = medias["híbrido"] - medias["semântico"]
        d_lex = medias["híbrido"] - medias["lexical"]
        linhas.append(
            f"| {bloco + 1} | {fim} | "
            + " | ".join(f"{m:.4f}" for m in medias.values())
            + f" | {d_sem:+.4f} | {d_lex:+.4f} |"
        )
    return linhas


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qrels", type=Path, default=CAMINHO_QRELS_PADRAO)
    parser.add_argument("--saida", type=Path, default=CAMINHO_SAIDA_PADRAO)
    args = parser.parse_args(argv)

    settings = get_settings()
    queries = _carregar_qrels(args.qrels)
    ids = list(queries)
    qrels = Qrels.from_dict(
        {i: dict.fromkeys(e["chunk_ids_relevantes"], 1) for i, e in queries.items()}
    )

    indice_bm25 = carregar_indice()
    client = genai.Client(api_key=settings.gemini_api_key)
    with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
        register_vector(conn)
        run_h, run_s, run_l = _executar_estrategias(conn, client, indice_bm25, queries)

    series = {
        "híbrido": _recall10_por_query(qrels, run_h, ids),
        "semântico": _recall10_por_query(qrels, run_s, ids),
        "lexical": _recall10_por_query(qrels, run_l, ids),
    }

    rng = np.random.default_rng(SEMENTE)
    comparacoes = {}
    for nome in ("semântico", "lexical"):
        v, e, d = _vde(series["híbrido"], series[nome])
        media, baixo, alto = _bootstrap(series["híbrido"] - series[nome], rng)
        comparacoes[nome] = (v, e, d, media, baixo, alto)

    md = [
        "# Recall@10 final — híbrido vs. isolados",
        "",
        f"Gold set: `{args.qrels.name}` — {len(ids)} queries. Métrica: Recall@10 por query "
        "(`ranx`). Empate = recall idêntico da query nas duas estratégias.",
        "",
        "## Médias",
        "",
        "| estratégia | Recall@10 médio |",
        "|---|---|",
        *(f"| {n} | {v.mean():.4f} |" for n, v in series.items()),
        "",
        "## Híbrido por query: vitórias / empates / derrotas",
        "",
        "| contra | vence | empata | perde | Δ média (híbrido − outro) | IC 95% bootstrap |",
        "|---|---|---|---|---|---|",
    ]
    for nome, (v, e, d, media, baixo, alto) in comparacoes.items():
        md.append(f"| {nome} | {v} | {e} | {d} | {media:+.4f} | [{baixo:+.4f}, {alto:+.4f}] |")
    md += [
        "",
        f"Bootstrap pareado: {N_REAMOSTRAGENS:,} reamostragens das {len(ids)} queries com "
        f"reposição, percentis 2,5 e 97,5 da diferença de médias (semente {SEMENTE}).",
        "",
        "## Recall@10 por query",
        "",
        "| query | híbrido | semântico | lexical |",
        "|---|---|---|---|",
        *(
            f"| {q} | {series['híbrido'][i]:.3f} | {series['semântico'][i]:.3f} | "
            f"{series['lexical'][i]:.3f} |"
            for i, q in enumerate(ids)
        ),
        "",
        "## Curva de estabilização por bloco",
        "",
        f"Média acumulada do Recall@10 a cada bloco de {TAMANHO_BLOCO} queries, na ordem de "
        "`qrels.yaml` (alfabética por id — não há ordem temporal de rotulação).",
        "",
        *_curva(ids, series),
        "",
    ]
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\nGravado em {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
