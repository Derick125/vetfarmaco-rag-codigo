"""Testes de etl/dose.py — padrão de dose por peso corporal, levantado
empiricamente sobre os seis previews de bula e o corpus do Spinosa
(`docs/RAG_SPEC.md` §7, item 3 — "dose com lastro").

Cada caso positivo é uma variante REAL encontrada no corpus (a origem vai no
id do teste); os negativos cobrem os dois jeitos mais prováveis de falso
positivo: uma faixa de peso do animal em kg sem unidade de dose ("Até 3
Kg", comum em tabela de posologia por peso) e uma unidade composta com
outra grandeza entre a unidade de dose e "kg" (clearance, não dose).
"""

from __future__ import annotations

import pytest

from etl.dose import extrair_doses

# (id do teste, texto de entrada, doses esperadas) — todos os textos de
# entrada positivos são trechos reais (ou o trecho mínimo que reproduz a
# forma real) de backend/data/preview/*.json ou
# backend/data/extracted/livro_completo_chunks.jsonl.
CASOS_POSITIVOS = [
    ("mg_simples", "35 mg/kg", ["35 mg/kg"]),
    ("mg_decimal_virgula", "0,2 mg/kg", ["0,2 mg/kg"]),
    ("mg_decimal_ponto", "2.5 mg/kg", ["2.5 mg/kg"]),
    ("ml_minusculo_espaco_antes_da_barra", "0,1 ml /kg", ["0,1 ml /kg"]),
    ("ui_maiusculo", "1,0 UI/kg", ["1,0 UI/kg"]),
    ("mcg_literal", "10 mcg/kg", ["10 mcg/kg"]),
    ("micro_sign", "2 µg/kg", ["2 µg/kg"]),  # µ = U+00B5 (sinal de micro)
    ("mu_grego", "0,03 μg/kg", ["0,03 μg/kg"]),  # μ = U+03BC (mu grego) — grafia distinta
    ("nanograma", "50 ng/kg", ["50 ng/kg"]),
    ("grama", "1 g/kg", ["1 g/kg"]),
    ("meq", "0,3 a 0,5 mEq/kg/dia", ["0,5 mEq/kg/dia"]),
    ("kg_dia_sufixo", "2 a 3 mg/kg/dia", ["3 mg/kg/dia"]),
    ("ui_kg_dia", "0,3 a 0,6 UI/kg/dia", ["0,6 UI/kg/dia"]),
    (
        "farmaco_nomeado_com_espaco_na_barra",
        "0,2 mg de ivermectina / kg de peso vivo",
        ["0,2 mg de ivermectina / kg"],
    ),
    ("farmaco_nomeado_sem_espaco", "0,2 mg de meloxicam/kg", ["0,2 mg de meloxicam/kg"]),
    (
        "farmaco_composto_com_simbolo",
        "500 mg de EPA + DHA/kg",
        ["500 mg de EPA + DHA/kg"],
    ),
    ("separador_por_kg", "2,2 mg de carprofeno por kg", ["2,2 mg de carprofeno por kg"]),
    (
        "numero_e_unidade_separados_por_linha_em_branco",
        "infusão entre 0,1 e 0,2\n\nmg/kg/min",
        ["0,2\n\nmg/kg"],
    ),
    ("expoente_kg_1_hifen_comum", "5 mg kg-1", ["5 mg kg-1"]),
    ("expoente_kg_1_travessao", "5 mg kg–1", ["5 mg kg–1"]),
    ("expoente_kg_1_ponto_medio", "5 mg·kg-1", ["5 mg·kg-1"]),
    (
        "multiplas_doses_no_mesmo_texto",
        "Cães: 0,5 a 1,0 UI/kg; gatos: 0,7 a 1,0 UI/kg",
        ["1,0 UI/kg", "1,0 UI/kg"],
    ),
]

CASOS_NEGATIVOS = [
    ("faixa_de_peso_do_animal_sem_unidade", "Até 3 Kg"),
    ("mencao_a_kg_sem_unidade_de_dose", "kg de peso corporal"),
    (
        "unidade_composta_de_clearance_nao_e_dose",
        "clearance de 87 a 150 mℓ/min · kg–1",
    ),
]


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [pytest.param(texto, esperado, id=id_) for id_, texto, esperado in CASOS_POSITIVOS],
)
def test_extrai_variantes_reais_do_corpus(texto: str, esperado: list[str]) -> None:
    assert extrair_doses(texto) == esperado


@pytest.mark.parametrize(
    ("texto"),
    [pytest.param(texto, id=id_) for id_, texto in CASOS_NEGATIVOS],
)
def test_nao_casa_falsos_positivos(texto: str) -> None:
    assert extrair_doses(texto) == []
