"""Testes de app/rag/composicao.py e do uso dos campos estruturados no roteador."""

import pytest

from app.rag.composicao import COMORBIDADES, compor_consulta
from app.rag.roteador import CAMINHO_VOCABULARIO_PADRAO, carregar_vocabulario, rotear


@pytest.fixture(scope="module")
def vocabulario():
    return carregar_vocabulario(CAMINHO_VOCABULARIO_PADRAO)


def test_sem_campos_o_texto_e_a_pergunta_intacta():
    assert compor_consulta("Qual a dose de meloxicam?") == "Qual a dose de meloxicam?"
    assert compor_consulta("Pergunta.", farmacos=[], comorbidades=[]) == "Pergunta."


def test_todos_os_campos_na_ordem_do_formulario():
    texto = compor_consulta(
        "É seguro repetir meloxicam neste paciente?",
        especie="felino",
        peso_kg=4.2,
        farmacos=["meloxicam", "furosemida"],
        comorbidades=["insuficiencia_renal_cronica"],
    )
    assert texto == (
        "Espécie: felino.\n"
        "Peso: 4,2 kg.\n"
        "Fármacos em questão: meloxicam, furosemida.\n"
        "Condições relevantes: insuficiência renal crônica.\n"
        "\n"
        "Pergunta: É seguro repetir meloxicam neste paciente?"
    )


def test_so_os_campos_presentes_aparecem():
    texto = compor_consulta("Dose?", especie="canino")
    assert texto == "Espécie: canino.\n\nPergunta: Dose?"


@pytest.mark.parametrize(
    ("peso", "esperado"), [(4.0, "4"), (4.25, "4,25"), (12.5, "12,5"), (0.35, "0,35")]
)
def test_peso_com_virgula_decimal_sem_zeros_sobrando(peso, esperado):
    assert f"Peso: {esperado} kg." in compor_consulta("x?", peso_kg=peso)


def test_toda_comorbidade_tem_rotulo():
    texto = compor_consulta("x?", comorbidades=list(COMORBIDADES))
    for rotulo in COMORBIDADES.values():
        assert rotulo in texto


# --- Comorbidades no roteador -----------------------------------------------------


def test_comorbidade_marcada_sobe_para_high_mesmo_em_pergunta_posologica_simples(vocabulario):
    pergunta = "Qual a dose de meloxicam?"
    assert rotear(pergunta, vocabulario).nivel == "low"
    r = rotear(pergunta, vocabulario, comorbidade_marcada=True)
    assert r.nivel == "high"
    assert "comorbidade marcada" in r.motivos


def test_campos_compostos_nao_mudam_o_nivel_de_pergunta_simples(vocabulario):
    pergunta = "Qual a dose de meloxicam?"
    texto = compor_consulta(pergunta, especie="felino", peso_kg=4.2, farmacos=["meloxicam"])
    assert rotear(texto, vocabulario).nivel == rotear(pergunta, vocabulario).nivel == "low"


def test_dois_farmacos_nos_campos_sobem_para_high(vocabulario):
    pergunta = "Qual a dose?"
    texto = compor_consulta(pergunta, farmacos=["meloxicam", "furosemida"])
    assert rotear(pergunta, vocabulario).nivel == "high"  # sem fármaco no texto: sem certeza
    r = rotear(texto, vocabulario)
    assert r.nivel == "high"
    assert r.farmacos == ["furosemida", "meloxicam"]
