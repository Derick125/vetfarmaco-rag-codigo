"""Recall@k do RAG híbrido vs. as estratégias isoladas (docs/RAG_SPEC.md §9).

Lê o gold set de `eval/qrels.yaml` (rotulado por veterinário — ver o
cabeçalho do próprio arquivo para o formato; este script não inventa
entradas), roda as três estratégias de recuperação sobre a mesma consulta
e reporta Recall@5, Recall@10 e Recall@20 com `ranx`, em tabela. O
critério do Quadro 1 do TCC (Fase 2 de `docs/PLANO_DE_FASES.md`) é o
híbrido superar as duas estratégias isoladas em Recall@10.

Só `eval/qrels.yaml` entra no cálculo. `eval/qrels_sem_resposta.yaml` (gold
set da Fase 3 — queries sem resposta no corpus) nunca é carregado aqui; ver
`scripts.consolidar_qrels`. Ao final, este script também relata quantas
queries de `backend/data/rotulacao/*.md` ficaram de fora do Recall@k e por
quê (sem resposta no corpus, ou ainda não rotuladas).

Cada estratégia é levada a `QTD_RETRIEVER` (30) resultados — profundidade
suficiente para o corte de Recall@20 de todas; `ranx` trunca internamente
para cada métrica, não é preciso re-executar por corte.

Uso:
    uv run python -m eval.recall_at_k
    uv run python -m eval.recall_at_k --qrels eval/outro_gold_set.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg
import structlog
import yaml
from google import genai
from google.genai import errors
from pgvector.psycopg import register_vector
from ranx import Qrels, Run, evaluate

from app.config import get_settings
from app.rag.fusao import K_PADRAO, fundir
from app.rag.retriever_lexical import buscar as buscar_lexical
from app.rag.retriever_lexical import carregar_indice
from app.rag.retriever_vetorial import buscar as buscar_vetorial
from etl.embed import gerar_embeddings
from scripts.consolidar_qrels import (
    CAMINHO_ROTULACAO_PADRAO,
    ArquivoDeRotulacaoInvalido,
    classificar_rotulacao,
)

logger = structlog.get_logger()

CAMINHO_QRELS_PADRAO = Path(__file__).resolve().parent / "qrels.yaml"
CORTES = (5, 10, 20)
QTD_RETRIEVER = 30


def _carregar_qrels(caminho: Path) -> dict[str, dict]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    queries = (dados or {}).get("queries") or {}
    if not queries:
        raise ValueError(f"{caminho} não tem nenhuma query em 'queries' — gold set vazio.")
    for query_id, entrada in queries.items():
        if not entrada.get("texto"):
            raise ValueError(f"query '{query_id}' em {caminho} não tem 'texto'.")
        if not entrada.get("chunk_ids_relevantes"):
            raise ValueError(
                f"query '{query_id}' em {caminho} não tem 'chunk_ids_relevantes' — "
                "sem gabarito, Recall@k não pode ser calculado para ela."
            )
    return queries


def _executar_estrategias(
    conn: psycopg.Connection,
    client: genai.Client,
    indice_bm25,
    queries: dict[str, dict],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    """Roda as três estratégias para cada query do gold set.

    Devolve `(run_hibrido, run_semantico, run_lexical)`, cada um no formato
    `{query_id: {chunk_id: escore}}` que `ranx.Run.from_dict` espera.
    """
    run_hibrido: dict[str, dict[str, float]] = {}
    run_semantico: dict[str, dict[str, float]] = {}
    run_lexical: dict[str, dict[str, float]] = {}

    for query_id, entrada in queries.items():
        texto = entrada["texto"]
        embedding = gerar_embeddings(client, [texto], task_type="RETRIEVAL_QUERY")[0]

        resultados_semanticos = buscar_vetorial(conn, embedding, qtd=QTD_RETRIEVER)
        resultados_lexicais = (
            buscar_lexical(indice_bm25, texto, qtd=QTD_RETRIEVER) if indice_bm25 is not None else []
        )
        resultados_fundidos = fundir(
            resultados_semanticos, resultados_lexicais, k=K_PADRAO, qtd=QTD_RETRIEVER
        )

        run_semantico[query_id] = dict(resultados_semanticos)
        run_lexical[query_id] = dict(resultados_lexicais)
        run_hibrido[query_id] = dict(resultados_fundidos)

        logger.info(
            "query_avaliada",
            query_id=query_id,
            semanticos=len(resultados_semanticos),
            lexicais=len(resultados_lexicais),
            fundidos=len(resultados_fundidos),
        )

    return run_hibrido, run_semantico, run_lexical


def _tabela(
    qrels: Qrels, runs_nomeados: dict[str, dict]
) -> tuple[str, dict[str, dict[str, float]]]:
    metricas = [f"recall@{corte}" for corte in CORTES]
    resultados_por_estrategia: dict[str, dict[str, float]] = {}

    cabecalho = ["estrategia", *metricas]
    linhas = [cabecalho]
    for nome, run_dict in runs_nomeados.items():
        run = Run.from_dict(run_dict)
        resultado = evaluate(qrels, run, metricas)
        resultados_por_estrategia[nome] = resultado
        linhas.append([nome, *(f"{resultado[m]:.4f}" for m in metricas)])

    larguras = [max(len(linha[i]) for linha in linhas) for i in range(len(cabecalho))]
    linhas_formatadas = [
        "  ".join(celula.ljust(largura) for celula, largura in zip(linha, larguras, strict=True))
        for linha in linhas
    ]
    separador = "  ".join("-" * largura for largura in larguras)
    tabela = "\n".join([linhas_formatadas[0], separador, *linhas_formatadas[1:]])
    return tabela, resultados_por_estrategia


def _relatar_cobertura(diretorio_rotulacao: Path, qtd_no_recall: int) -> None:
    """Relata quantas queries de `diretorio_rotulacao` ficaram fora do Recall@k e por quê."""
    try:
        classificacao = classificar_rotulacao(diretorio_rotulacao)
    except ArquivoDeRotulacaoInvalido as erro:
        logger.warning("cobertura_do_gold_set_indisponivel", erro=str(erro))
        return

    total = (
        len(classificacao.rotuladas)
        + len(classificacao.sem_resposta)
        + len(classificacao.pendentes)
    )
    print(f"\nCobertura do gold set — {total} query(ies) em {diretorio_rotulacao}:")
    print(f"  - {qtd_no_recall} no Recall@k (eval/qrels.yaml)")
    print(
        f"  - {len(classificacao.sem_resposta)} sem resposta no corpus, fora do Recall@k — "
        "gold set da Fase 3 (eval/qrels_sem_resposta.yaml)"
    )
    if classificacao.pendentes:
        print(
            f"  - {len(classificacao.pendentes)} ainda não rotulada(s): "
            f"{', '.join(classificacao.pendentes)}"
        )
    descartadas = len(classificacao.rotuladas) - qtd_no_recall
    if descartadas > 0:
        print(
            f"  - {descartadas} rotulada(s) com RELEVANTES preenchida mas descartada(s) por "
            "scripts.consolidar_qrels (chunk_id inexistente no banco) — rode-o de novo para ver "
            "o aviso e corrija a digitação."
        )


def main(argv: list[str] | None = None) -> int:
    # Mesmo motivo de scripts/testar_busca.py: console Windows em
    # cp1252/cp850 não cobre todo caractere do corpus.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--qrels", type=Path, default=CAMINHO_QRELS_PADRAO)
    parser.add_argument("--rotulacao", type=Path, default=CAMINHO_ROTULACAO_PADRAO)
    args = parser.parse_args(argv)

    settings = get_settings()
    if not settings.gemini_api_key:
        logger.error("gemini_api_key_ausente", mensagem="Defina GEMINI_API_KEY em backend/.env.")
        return 1
    if not settings.database_url:
        logger.error("database_url_ausente", mensagem="Defina DATABASE_URL em backend/.env.")
        return 1

    try:
        queries = _carregar_qrels(args.qrels)
    except (OSError, ValueError) as erro:
        logger.error("qrels_invalido", erro=str(erro))
        return 1

    qrels = Qrels.from_dict(
        {
            query_id: dict.fromkeys(entrada["chunk_ids_relevantes"], 1)
            for query_id, entrada in queries.items()
        }
    )

    indice_bm25 = carregar_indice()
    if indice_bm25 is None:
        logger.warning(
            "busca_lexical_indisponivel", mensagem="Rode o ETL para construir o índice BM25."
        )

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
            register_vector(conn)
            run_hibrido, run_semantico, run_lexical = _executar_estrategias(
                conn, client, indice_bm25, queries
            )
    except (psycopg.OperationalError, errors.ClientError) as erro:
        logger.error("falha_na_avaliacao", erro=str(erro))
        return 1

    tabela, resultados = _tabela(
        qrels,
        {
            "hibrido (RRF)": run_hibrido,
            "semantico puro": run_semantico,
            "lexical puro": run_lexical,
        },
    )
    sufixo = "y" if len(queries) == 1 else "ies"
    print(f"\nRecall@k — {len(queries)} quer{sufixo} de {args.qrels}\n")
    print(tabela)

    r10_hibrido = resultados["hibrido (RRF)"]["recall@10"]
    r10_semantico = resultados["semantico puro"]["recall@10"]
    r10_lexical = resultados["lexical puro"]["recall@10"]
    if r10_hibrido >= r10_semantico and r10_hibrido >= r10_lexical:
        print(
            f"\nCritério do Quadro 1: OK — híbrido ({r10_hibrido:.4f}) não fica abaixo de "
            f"nenhuma estratégia isolada em Recall@10."
        )
    else:
        print(
            f"\nCritério do Quadro 1: NÃO atendido — híbrido ({r10_hibrido:.4f}) fica abaixo de "
            f"semântico ({r10_semantico:.4f}) ou lexical ({r10_lexical:.4f}) em Recall@10."
        )

    _relatar_cobertura(args.rotulacao, qtd_no_recall=len(queries))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
