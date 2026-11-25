"""Testes de app/rag/roteador.py — roteamento do thinking_level (docs/RAG_SPEC.md §4).

O default é `high`: `low` só sai com certeza de consulta posológica de um
único fármaco do dicionário.
"""

from pathlib import Path

import pytest
import yaml

from app.rag.roteador import CAMINHO_VOCABULARIO_PADRAO, carregar_vocabulario, rotear

CAMINHO_CENARIOS = Path(__file__).parent.parent / "eval" / "scenarios.yaml"
CAMINHO_SEM_RESPOSTA = Path(__file__).parent.parent / "eval" / "qrels_sem_resposta.yaml"


@pytest.fixture(scope="module")
def vocabulario():
    return carregar_vocabulario(CAMINHO_VOCABULARIO_PADRAO)


def _cenarios() -> dict[str, str]:
    dados = yaml.safe_load(CAMINHO_CENARIOS.read_text(encoding="utf-8"))["cenarios"]
    return {c["id"]: c["pergunta_clinica"] for c in dados}


# --- Os seis cenários do Quadro 2 (scenarios.yaml) --------------------------


@pytest.mark.parametrize(
    "cenario_id",
    [
        "paracetamol-felino",
        "ivermectina-mdr1",
        "fenobarbital-carprofeno",
        "tramadol-felino-vs-cao-renal",
        "insulina-nph-extra-label",
        "meloxicam-irc",
    ],
)
def test_cenarios_do_quadro_2_sao_high(vocabulario, cenario_id):
    assert rotear(_cenarios()[cenario_id], vocabulario).nivel == "high"


def test_fenobarbital_carprofeno_por_dois_farmacos(vocabulario):
    r = rotear(_cenarios()["fenobarbital-carprofeno"], vocabulario)
    assert r.farmacos == ["carprofeno", "fenobarbital"]
    assert "2 fármacos" in r.motivos[0]


def test_tramadol_renal_por_qualificador_clinico(vocabulario):
    r = rotear(_cenarios()["tramadol-felino-vs-cao-renal"], vocabulario)
    assert any("qualificador clínico" in m for m in r.motivos)


def test_insulina_nph_reconhecida_como_um_farmaco(vocabulario):
    r = rotear(_cenarios()["insulina-nph-extra-label"], vocabulario)
    assert r.farmacos == ["insulina NPH"]


# --- Interações: segundo fármaco fora do dicionário original -----------------


def test_meloxicam_com_furosemida_e_high_por_dois_farmacos(vocabulario):
    r = rotear("meloxicam posso dar com furosemida", vocabulario)
    assert r.nivel == "high"
    assert r.farmacos == ["furosemida", "meloxicam"]


def test_aine_com_corticoide_e_high(vocabulario):
    # "AINE" e "corticoide" são classes, não fármacos do dicionário: o
    # `high` vem da falta de certeza de posologia.
    r = rotear("posso dar AINE com corticoide", vocabulario)
    assert r.nivel == "high"
    assert r.farmacos == []


@pytest.mark.parametrize(
    "farmaco",
    [
        "furosemida",
        "digoxina",
        "prednisolona",
        "prednisona",
        "dexametasona",
        "metilprednisolona",
        "hidrocortisona",
        "betametasona",
        "triancinolona",
    ],
)
def test_farmacos_acrescentados_ao_dicionario_sao_detectados(vocabulario, farmaco):
    assert rotear(f"dose de {farmaco}", vocabulario).farmacos == [farmaco]


def test_dois_farmacos_acrescentados_sao_high(vocabulario):
    assert rotear("prednisolona e digoxina", vocabulario).nivel == "high"


# --- Posologia direta de um fármaco: único caminho para `low` ----------------


@pytest.mark.parametrize(
    "pergunta",
    [
        "tramadol dose gato",
        "qual a dose de carprofeno em cão de 20 kg",
        "dose de dipirona para cão",
        "quanto de ivermectina para sarna sarcóptica",
        "dose de prednisolona",
        "dose de meloxicam para gato",
    ],
)
def test_posologia_direta_de_um_farmaco_e_low(vocabulario, pergunta):
    r = rotear(pergunta, vocabulario)
    assert r.nivel == "low"
    assert len(r.farmacos) == 1


# --- Default high: qualquer dúvida ------------------------------------------


def test_sem_termo_posologico_e_high(vocabulario):
    r = rotear("Posso dar paracetamol para gato com dor?", vocabulario)
    assert r.nivel == "high"


def test_um_farmaco_so_no_contexto_de_interacao_e_high(vocabulario):
    assert rotear("carprofeno junto com fenobarbital", vocabulario).nivel == "high"


@pytest.mark.parametrize(
    "pergunta",
    [
        "canabidiol para dor crônica em cão",
        "dose de grapiprant para cão",
        "dose de maropitant para gato",
        "gabapentina para dor neuropática em felino",
    ],
)
def test_fora_do_dicionario_e_high(vocabulario, pergunta):
    r = rotear(pergunta, vocabulario)
    assert r.nivel == "high"
    assert r.farmacos == []


def test_qualificador_clinico_derruba_dose_simples(vocabulario):
    assert rotear("dose de tramadol em gato com doença renal", vocabulario).nivel == "high"


def test_comorbidade_marcada_forca_high(vocabulario):
    assert rotear("dose de tramadol", vocabulario).nivel == "low"
    assert rotear("dose de tramadol", vocabulario, comorbidade_marcada=True).nivel == "high"


def test_dica_de_complexidade_alta_forca_high(vocabulario):
    assert rotear("dose de tramadol", vocabulario, complexidade_dica="alta").nivel == "high"


def test_dica_de_complexidade_baixa_nao_rebaixa_nada(vocabulario):
    assert (
        rotear("Posso usar ivermectina em Collie?", vocabulario, complexidade_dica="baixa").nivel
        == "high"
    )


def test_queries_sem_resposta_so_tramadol_dose_gato_e_low(vocabulario):
    queries = yaml.safe_load(CAMINHO_SEM_RESPOSTA.read_text(encoding="utf-8"))["queries"]
    niveis = {qid: rotear(q["texto"], vocabulario).nivel for qid, q in queries.items()}
    assert niveis.pop("tramadol-dose-gato") == "low"
    assert set(niveis.values()) == {"high"}


def test_nivel_e_sempre_explicito(vocabulario):
    for pergunta in ("", "dose de tramadol", "qualquer coisa", "posso dar AINE com corticoide"):
        assert rotear(pergunta, vocabulario).nivel in ("low", "high")
