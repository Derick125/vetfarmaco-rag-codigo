"""Geração de embeddings (docs/RAG_SPEC.md §2, etapa "Embeddings").

`gemini-embedding-001`, `task_type="RETRIEVAL_DOCUMENT"`,
`output_dimensionality=1536`, em lote. O modelo trunca o vetor nativo de
3072 dimensões para as primeiras 1536 — o que não preserva norma unitária
— por isso a normalização L2 é feita manualmente aqui, sempre (a
normalização automática do provedor só cobre a dimensão nativa de 3072).
Consultas em tempo real devem usar `task_type="RETRIEVAL_QUERY"` (ver
`gerar_embeddings`).

O identificador do modelo de embeddings é fixado neste módulo, e não em
`MODELO_ID`/config (que é o modelo de geração, TCC §4.7) — trocar de
embedding exige reprocessar o corpus inteiro, então é uma decisão de
pipeline, não uma variável de ambiente trocável em produção.

Uso:
    python -m etl.embed --entrada chunks.jsonl --saida chunks_com_embedding.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import structlog
from google import genai
from google.genai import errors, types

from app.config import get_settings

logger = structlog.get_logger()

MODELO_EMBEDDING = "gemini-embedding-001"
DIMENSOES = 1536
TAMANHO_LOTE_PADRAO = 100

# Limite de taxa da API (429): o SDK já tenta de novo internamente, mas com
# esperas curtas demais para uma cota por minuto. Espera exponencial própria,
# começando em 20 s (cotas do Gemini são por minuto).
MAX_TENTATIVAS_LIMITE_TAXA = 6
ESPERA_INICIAL_LIMITE_TAXA_S = 20.0


def _normalizar_l2(vetor: list[float]) -> list[float]:
    norma = math.sqrt(sum(v * v for v in vetor))
    if norma == 0:
        return vetor
    return [v / norma for v in vetor]


def _lotes(sequencia: list[str], tamanho: int) -> list[list[str]]:
    return [sequencia[i : i + tamanho] for i in range(0, len(sequencia), tamanho)]


def _embed_com_retentativa(
    client: genai.Client, lote: list[str], task_type: str
) -> types.EmbedContentResponse:
    """Chama `embed_content`, esperando e tentando de novo se a cota por
    minuto estourar (429) — sem isso, um lote no meio de um corpus grande
    derruba o processamento inteiro por um limite que se resolve sozinho
    em segundos."""
    espera = ESPERA_INICIAL_LIMITE_TAXA_S
    for tentativa in range(1, MAX_TENTATIVAS_LIMITE_TAXA + 1):
        try:
            return client.models.embed_content(
                model=MODELO_EMBEDDING,
                contents=lote,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=DIMENSOES,
                ),
            )
        except errors.ClientError as erro:
            if erro.code != 429 or tentativa == MAX_TENTATIVAS_LIMITE_TAXA:
                raise
            logger.warning(
                "limite_de_taxa_atingido", tentativa=tentativa, espera_s=espera, erro=str(erro)
            )
            time.sleep(espera)
            espera *= 2
    raise AssertionError("inalcançável")  # pragma: no cover


def gerar_embeddings(
    client: genai.Client,
    textos: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
    tamanho_lote: int = TAMANHO_LOTE_PADRAO,
) -> list[list[float]]:
    """Gera um embedding L2-normalizado por texto, em lotes de `tamanho_lote`.

    A ordem do retorno corresponde exatamente à ordem de `textos`.
    """
    resultado: list[list[float]] = []
    for lote in _lotes(textos, tamanho_lote):
        resposta = _embed_com_retentativa(client, lote, task_type)
        resultado.extend(_normalizar_l2(list(e.values)) for e in resposta.embeddings)
        logger.info("lote_embebido", tamanho=len(lote), task_type=task_type)
    return resultado


def _ler_chunks(caminho: Path) -> list[dict]:
    return [
        json.loads(linha)
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entrada", required=True, type=Path, help="JSONL de chunks produzido por etl/chunk.py"
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        help="JSONL de saída (chunks + embedding); default: stdout",
    )
    parser.add_argument("--tamanho-lote", type=int, default=TAMANHO_LOTE_PADRAO)
    args = parser.parse_args(argv)

    settings = get_settings()
    if not settings.gemini_api_key:
        logger.error("gemini_api_key_ausente", mensagem="Defina GEMINI_API_KEY em backend/.env.")
        return 1

    chunks = _ler_chunks(args.entrada)
    if not chunks:
        logger.warning("nenhum_chunk_na_entrada", caminho=str(args.entrada))
        return 0

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        embeddings = gerar_embeddings(
            client, [c["texto"] for c in chunks], tamanho_lote=args.tamanho_lote
        )
    except errors.ClientError as erro:
        logger.error("falha_ao_gerar_embeddings", erro=str(erro))
        return 1

    for chunk, embedding in zip(chunks, embeddings, strict=True):
        chunk["embedding"] = embedding

    linhas = [json.dumps(chunk, ensure_ascii=False) for chunk in chunks]
    if args.saida:
        args.saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        logger.info("saida_gravada", caminho=str(args.saida), linhas=len(linhas))
    else:
        for linha in linhas:
            print(linha)  # noqa: T201 — saída de dados do CLI, não log de depuração

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
