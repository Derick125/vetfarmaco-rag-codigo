"""Roteamento do `thinking_level` (docs/RAG_SPEC.md §4, TCC §3.2d).

| Condição                                                          | Nível  |
|-------------------------------------------------------------------|--------|
| Pergunta posológica direta, 1 fármaco, sem comorbidade — **só se  | `low`  |
| todos os sinais positivos estiverem presentes**                   |        |
| Qualquer outro caso (≥ 2 fármacos, comorbidade, interação, dica   | `high` |
| "alta", qualificador clínico, sem termo posológico, ou dúvida)    |        |

O default é `high`: `low` exige certeza (exatamente 1 fármaco do dicionário,
termo posológico explícito e nenhum qualificador clínico na pergunta). O
nível é sempre devolvido de forma explícito — o default do modelo é `medium`
e `minimal` não é suportado (RAG_SPEC.md §4).

Fármacos são detectados com o mesmo dicionário controlado do ETL
(`etl/vocabulario/farmacos.yaml`), para a pergunta e o corpus nunca
divergirem no que conta como "um fármaco".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from etl.chunk import Vocabulario, carregar_vocabulario

NivelRaciocinio = Literal["low", "high"]

CAMINHO_VOCABULARIO_PADRAO = (
    Path(__file__).resolve().parent.parent.parent / "etl" / "vocabulario" / "farmacos.yaml"
)

# Pergunta sobre interação (sem acento, minúsculas — ver `_normalizar`).
_PADRAO_INTERACAO = re.compile(
    r"\b(?:interacao|interacoes|interage|interagem|interagir|"
    r"junto com|junto a|associad[oa]s?|associar|associacao|"
    r"combinad[oa]s?|combinar|combinacao|concomitante|concomitantemente|"
    r"ao mesmo tempo|simultaneo|simultaneamente)\b"
)

# Termo posológico explícito: sem ele não há certeza de consulta de dose.
_PADRAO_POSOLOGIA = re.compile(
    r"\b(?:dose|doses|dosagem|dosagens|posologia|quanto|quantos|mg|ml|mcg|ui|"
    r"intervalo|frequencia)\b|\bmg/kg\b"
)

# Qualificador clínico (condição, estado fisiológico, condicionante): a
# pergunta deixa de ser "dose simples" mesmo sem comorbidade marcada.
_PADRAO_QUALIFICADOR = re.compile(
    r"\b(?:com|sem|mas|porem|se|caso|apesar|quando|durante|"
    r"insuficiencia|renal|renais|rins?|hepatic\w*|figado|cardiac\w*|coracao|"
    r"gestante|prenhe|gravida|lactante|filhotes?|idos[oa]s?|geriatric\w*|"
    r"desidratad\w*|diabetic\w*|epilep\w*|convuls\w*|doenca|doencas|"
    r"cronic\w*|agud\w*|paciente|pacientes|extra-?label|crise)\b"
)


@dataclass(frozen=True)
class Roteamento:
    nivel: NivelRaciocinio
    farmacos: list[str] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).lower()


def detectar_farmacos(pergunta: str, vocabulario: Vocabulario) -> list[str]:
    """Nomes canônicos dos fármacos do dicionário citados na pergunta."""
    return sorted({t.nome for t in vocabulario.farmacos if t.padrao.search(pergunta)})


def rotear(
    pergunta: str,
    vocabulario: Vocabulario,
    *,
    comorbidade_marcada: bool = False,
    complexidade_dica: Literal["alta", "baixa"] | None = None,
) -> Roteamento:
    """Decide o `thinking_level` da consulta.

    `comorbidade_marcada` vem do cliente (campo estruturado — a comorbidade
    não é inferida do texto livre, como a sanitização de PII, CLAUDE.md
    regra 3). `complexidade_dica` é a dica do app (FRONTEND_SPEC.md §9); a
    decisão final é sempre daqui, mas uma dica `"alta"` nunca é rebaixada.
    """
    farmacos = detectar_farmacos(pergunta, vocabulario)
    motivos: list[str] = []

    if len(farmacos) >= 2:
        motivos.append(f"{len(farmacos)} fármacos: {', '.join(farmacos)}")
    if comorbidade_marcada:
        motivos.append("comorbidade marcada")
    if _PADRAO_INTERACAO.search(_normalizar(pergunta)):
        motivos.append("pergunta sobre interação")
    if complexidade_dica == "alta":
        motivos.append("dica de complexidade alta do cliente")

    if motivos:
        return Roteamento(nivel="high", farmacos=farmacos, motivos=motivos)

    # Nenhum sinal de complexidade: `low` só com certeza positiva.
    normalizada = _normalizar(pergunta)
    if len(farmacos) != 1:
        motivos.append("nenhum fármaco do dicionário identificado — não há certeza de posologia")
    if not _PADRAO_POSOLOGIA.search(normalizada):
        motivos.append("sem termo posológico explícito")
    qualificador = _PADRAO_QUALIFICADOR.search(normalizada)
    if qualificador:
        motivos.append(f"qualificador clínico na pergunta: {qualificador.group(0)!r}")

    if motivos:
        return Roteamento(nivel="high", farmacos=farmacos, motivos=motivos)
    return Roteamento(
        nivel="low", farmacos=farmacos, motivos=["posologia direta, 1 fármaco, sem comorbidade"]
    )


__all__ = [
    "CAMINHO_VOCABULARIO_PADRAO",
    "NivelRaciocinio",
    "Roteamento",
    "carregar_vocabulario",
    "detectar_farmacos",
    "rotear",
]
