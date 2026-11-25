"""Auditoria consolidada dos previews de bula (extensão de `etl/chunk_bula.py`
e `scripts/preview_bula.py` para conferência do corpus, sem tocar no banco).

Lê todos os `*.json` de um diretório de previews (o array de chunks por bula
gravado por `scripts/preview_bula.py`) e produz dois CSVs:

- `resumo_bulas.csv`: uma linha por bula — total de chunks, distribuição de
  chunks por seção canônica (célula única, "secao=contagem" separado por
  "; ", ordenado por nome de seção) e o chunk de maior/menor contagem de
  tokens (id + valor cada).
- `chunks_com_dose.csv`: uma linha por chunk cujo texto contém pelo menos um
  padrão de dose por peso (`etl.dose.PADRAO_DOSE_POR_KG` — compartilhado com
  a validação "dose com lastro" da Fase 3, ver `etl/dose.py`) — os trechos
  encontrados, e se o PRÓPRIO TEXTO do chunk nomeia um fármaco e/ou uma
  espécie do
  vocabulário controlado (`etl/vocabulario/farmacos.yaml`, casado com
  `etl.chunk._casar` — o mesmo mecanismo do corpus de livro).

  Isto é DIFERENTE dos campos de metadado `farmacos`/`especies` do chunk:
  esses vêm do manifesto (`data/bulas/manifesto.yaml`), nunca de casamento
  de texto (ver `etl/chunk_bula.py`) — por isso `farmacos_metadado` é quase
  sempre nomeado (um PDF só tem um fármaco) mas `especies_metadado` fica
  vazio em toda bula humana do corpus, ainda que o cenário de uso do TCC
  seja veterinário. O casamento de texto aqui existe para tornar visível
  exatamente esse ponto: um chunk de posologia com dose por kg cujo texto
  não nomeia espécie nenhuma é dose extra-label sem documentação própria —
  o gap que os cenários do Quadro 2 do TCC exploram.

Uso:
    python -m etl.auditar_previews \\
        --previews data/preview --saida-dir data/audit
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import structlog

from etl.chunk import Vocabulario, _casar, carregar_vocabulario
from etl.dose import extrair_doses
from etl.extract_bula import CAMINHO_VOCABULARIO_FARMACOS_PADRAO

logger = structlog.get_logger()

DIRETORIO_PREVIEW_PADRAO = Path(__file__).resolve().parent.parent / "data" / "preview"
DIRETORIO_AUDITORIA_PADRAO = Path(__file__).resolve().parent.parent / "data" / "audit"


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------


@dataclass
class ResumoBula:
    bula: str
    fonte: str
    total_chunks: int
    distribuicao_secoes: dict[str, int]
    chunk_maior_id: str
    chunk_maior_tokens: int
    chunk_menor_id: str
    chunk_menor_tokens: int


@dataclass
class ChunkComDose:
    bula: str
    chunk_id: str
    secao: str
    pagina: int
    tokens: int
    doses_encontradas: list[str]
    farmacos_metadado: list[str]
    especies_metadado: list[str]
    farmacos_no_texto: list[str]
    especies_no_texto: list[str]


# --------------------------------------------------------------------------
# Leitura e agregação
# --------------------------------------------------------------------------


def _ler_preview(caminho: Path) -> list[dict]:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _resumir_bula(bula: str, chunks: list[dict]) -> ResumoBula:
    distribuicao: dict[str, int] = {}
    for chunk in chunks:
        distribuicao[chunk["secao"]] = distribuicao.get(chunk["secao"], 0) + 1
    maior = max(chunks, key=lambda c: c["tokens"])
    menor = min(chunks, key=lambda c: c["tokens"])
    return ResumoBula(
        bula=bula,
        fonte=chunks[0]["fonte"],
        total_chunks=len(chunks),
        distribuicao_secoes=distribuicao,
        chunk_maior_id=maior["chunk_id"],
        chunk_maior_tokens=maior["tokens"],
        chunk_menor_id=menor["chunk_id"],
        chunk_menor_tokens=menor["tokens"],
    )


def _chunks_com_dose(bula: str, chunks: list[dict], vocabulario: Vocabulario) -> list[ChunkComDose]:
    encontrados: list[ChunkComDose] = []
    for chunk in chunks:
        doses = extrair_doses(chunk["texto"])
        if not doses:
            continue
        encontrados.append(
            ChunkComDose(
                bula=bula,
                chunk_id=chunk["chunk_id"],
                secao=chunk["secao"],
                pagina=chunk["pagina"],
                tokens=chunk["tokens"],
                doses_encontradas=doses,
                farmacos_metadado=chunk["farmacos"],
                especies_metadado=chunk["especies"],
                farmacos_no_texto=_casar(chunk["texto"], vocabulario.farmacos),
                especies_no_texto=_casar(chunk["texto"], vocabulario.especies),
            )
        )
    return encontrados


def auditar(
    diretorio_previews: Path, caminho_vocabulario_farmacos: Path
) -> tuple[list[ResumoBula], list[ChunkComDose]]:
    vocabulario = carregar_vocabulario(caminho_vocabulario_farmacos)
    resumos: list[ResumoBula] = []
    chunks_com_dose: list[ChunkComDose] = []
    for caminho in sorted(diretorio_previews.glob("*.json")):
        bula = caminho.stem
        chunks = _ler_preview(caminho)
        if not chunks:
            logger.warning("preview_vazio", bula=bula, origem=str(caminho))
            continue
        resumos.append(_resumir_bula(bula, chunks))
        chunks_com_dose.extend(_chunks_com_dose(bula, chunks, vocabulario))
    return resumos, chunks_com_dose


# --------------------------------------------------------------------------
# Saída CSV
# --------------------------------------------------------------------------


def _formatar_distribuicao(distribuicao: dict[str, int]) -> str:
    return "; ".join(f"{secao}={contagem}" for secao, contagem in sorted(distribuicao.items()))


def _escrever_resumo(caminho: Path, resumos: list[ResumoBula]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(
            [
                "bula",
                "fonte",
                "total_chunks",
                "distribuicao_secoes",
                "chunk_maior_id",
                "chunk_maior_tokens",
                "chunk_menor_id",
                "chunk_menor_tokens",
            ]
        )
        for resumo in resumos:
            escritor.writerow(
                [
                    resumo.bula,
                    resumo.fonte,
                    resumo.total_chunks,
                    _formatar_distribuicao(resumo.distribuicao_secoes),
                    resumo.chunk_maior_id,
                    resumo.chunk_maior_tokens,
                    resumo.chunk_menor_id,
                    resumo.chunk_menor_tokens,
                ]
            )


def _escrever_chunks_com_dose(caminho: Path, linhas: list[ChunkComDose]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(
            [
                "bula",
                "chunk_id",
                "secao",
                "pagina",
                "tokens",
                "doses_encontradas",
                "nomeia_farmaco_no_texto",
                "farmacos_no_texto",
                "farmacos_metadado",
                "nomeia_especie_no_texto",
                "especies_no_texto",
                "especies_metadado",
            ]
        )
        for linha in linhas:
            escritor.writerow(
                [
                    linha.bula,
                    linha.chunk_id,
                    linha.secao,
                    linha.pagina,
                    linha.tokens,
                    "; ".join(linha.doses_encontradas),
                    "sim" if linha.farmacos_no_texto else "não",
                    "; ".join(linha.farmacos_no_texto),
                    "; ".join(linha.farmacos_metadado),
                    "sim" if linha.especies_no_texto else "não",
                    "; ".join(linha.especies_no_texto),
                    "; ".join(linha.especies_metadado),
                ]
            )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--previews",
        type=Path,
        default=DIRETORIO_PREVIEW_PADRAO,
        help="Diretório com os *.json de preview (default: backend/data/preview)",
    )
    parser.add_argument(
        "--saida-dir",
        type=Path,
        default=DIRETORIO_AUDITORIA_PADRAO,
        help="Diretório de saída dos CSVs (default: backend/data/audit)",
    )
    parser.add_argument(
        "--vocabulario-farmacos", type=Path, default=CAMINHO_VOCABULARIO_FARMACOS_PADRAO
    )
    args = parser.parse_args(argv)

    resumos, chunks_com_dose = auditar(args.previews, args.vocabulario_farmacos)

    caminho_resumo = args.saida_dir / "resumo_bulas.csv"
    caminho_doses = args.saida_dir / "chunks_com_dose.csv"
    _escrever_resumo(caminho_resumo, resumos)
    _escrever_chunks_com_dose(caminho_doses, chunks_com_dose)

    logger.info(
        "auditoria_concluida",
        bulas=len(resumos),
        chunks_com_dose=len(chunks_com_dose),
        resumo=str(caminho_resumo),
        chunks_com_dose_csv=str(caminho_doses),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
