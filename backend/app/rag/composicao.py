"""Texto da consulta a partir dos campos estruturados (FRONTEND_SPEC.md §9).

O que vai ao roteador e ao modelo é este texto. Sem campos estruturados, ele é
exatamente a `pergunta`. A **recuperação não usa este texto nem a espécie**: ela
continua recebendo só a `pergunta`, como na avaliação da Fase 2 (RAG_SPEC.md §7.1).
"""

from __future__ import annotations

from typing import Literal, get_args

Especie = Literal["canino", "felino"]
ESPECIES: tuple[str, ...] = get_args(Especie)

# Vocabulário controlado de comorbidades (toggles do §9): o app só envia estas chaves,
# o que mantém texto livre — e PII — fora dos campos estruturados.
COMORBIDADES: dict[str, str] = {
    "insuficiencia_renal_cronica": "insuficiência renal crônica",
    "hepatopatia": "hepatopatia",
    "gestacao": "gestação",
    "epilepsia": "epilepsia",
    "raca_mdr1": "raça MDR1",
}


def _peso(peso_kg: float) -> str:
    return f"{peso_kg:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def compor_consulta(
    pergunta: str,
    *,
    especie: str | None = None,
    peso_kg: float | None = None,
    farmacos: list[str] | None = None,
    comorbidades: list[str] | None = None,
) -> str:
    """Linhas `Espécie`, `Peso`, `Fármacos em questão` e `Condições relevantes` (só as
    presentes, na ordem do formulário) seguidas da pergunta. Sem nenhum campo, devolve
    a pergunta intacta."""
    linhas: list[str] = []
    if especie:
        linhas.append(f"Espécie: {especie}.")
    if peso_kg is not None:
        linhas.append(f"Peso: {_peso(peso_kg)} kg.")
    if farmacos:
        linhas.append(f"Fármacos em questão: {', '.join(farmacos)}.")
    if comorbidades:
        linhas.append(f"Condições relevantes: {', '.join(COMORBIDADES[c] for c in comorbidades)}.")
    if not linhas:
        return pergunta
    return "\n".join(linhas) + f"\n\nPergunta: {pergunta}"
