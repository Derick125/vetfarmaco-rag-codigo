"""GET /vocabulario: autenticação, formato e contrato com POST /consulta."""

from fastapi.testclient import TestClient

import app.api.deps as deps
from app.api.consulta import ConsultaRequest, _farmacos_canonicos
from app.api.vocabulario import montar_vocabulario
from app.main import app
from app.rag.composicao import COMORBIDADES, ESPECIES

# Reaproveita o serviço com recuperação e modelo simulados do teste de /consulta.
from tests.test_api_consulta import CHAVE, CORPO, _settings, capturado, servico  # noqa: F401

CABECALHO = {"X-API-Key": CHAVE}


def test_sem_api_key_401(servico):  # noqa: F811
    assert servico.get("/vocabulario").status_code == 401


def test_api_key_errada_401(servico):  # noqa: F811
    assert servico.get("/vocabulario", headers={"X-API-Key": "outra"}).status_code == 401


def test_api_key_nao_configurada_503(servico, monkeypatch):  # noqa: F811
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(app_api_key=None))
    assert servico.get("/vocabulario", headers={"X-API-Key": ""}).status_code == 503


def test_formato_e_conteudo(servico):  # noqa: F811
    r = servico.get("/vocabulario", headers=CABECALHO)
    assert r.status_code == 200
    corpo = r.json()
    assert set(corpo) == {"versao", "especies", "farmacos", "comorbidades"}
    assert corpo["especies"] == list(ESPECIES)
    assert corpo["comorbidades"] == [{"chave": k, "rotulo": v} for k, v in COMORBIDADES.items()]
    nomes = [f["nome"] for f in corpo["farmacos"]]
    assert "meloxicam" in nomes
    assert nomes == sorted(nomes, key=str.casefold)
    assert len(nomes) == len(set(nomes))


def test_sinonimos_sem_repetir_o_nome(servico):  # noqa: F811
    corpo = servico.get("/vocabulario", headers=CABECALHO).json()
    aas = next(f for f in corpo["farmacos"] if f["nome"] == "ácido acetilsalicílico")
    assert "aspirina" in aas["sinonimos"]
    assert "ácido acetilsalicílico" not in aas["sinonimos"]
    for f in corpo["farmacos"]:
        assert f["nome"].casefold() not in [s.casefold() for s in f["sinonimos"]]


def test_versao_estavel_e_sensivel_ao_conteudo():
    with TestClient(app):
        voc = app.state.vocabulario
        a = montar_vocabulario(voc)
        assert a["versao"] == montar_vocabulario(voc)["versao"]
        voc.farmacos[0].sinonimos.append("sinonimo-novo-de-teste")
        try:
            assert montar_vocabulario(voc)["versao"] != a["versao"]
        finally:
            voc.farmacos[0].sinonimos.remove("sinonimo-novo-de-teste")


def test_contrato_tudo_que_o_endpoint_serve_e_aceito_por_consulta(servico):  # noqa: F811
    corpo = servico.get("/vocabulario", headers=CABECALHO).json()
    nomes = [f["nome"] for f in corpo["farmacos"]]
    voc = servico.app.state.vocabulario
    # validador de fármacos do /consulta: devolve cada nome inalterado
    assert _farmacos_canonicos(nomes, voc) == nomes
    # corpo validado pelo modelo pydantic: todas as espécies e comorbidades
    for especie in corpo["especies"]:
        ConsultaRequest(pergunta="pergunta de teste", especie=especie)
    ConsultaRequest(
        pergunta="pergunta de teste", comorbidades=[c["chave"] for c in corpo["comorbidades"]]
    )


def test_contrato_via_post_em_lotes_de_10(servico):  # noqa: F811
    nomes = [f["nome"] for f in servico.get("/vocabulario", headers=CABECALHO).json()["farmacos"]]
    for i in range(0, len(nomes), 10):
        corpo = CORPO | {"farmacos": nomes[i : i + 10]}
        r = servico.post("/consulta", json=corpo, headers=CABECALHO)
        assert r.status_code == 200, nomes[i : i + 10]
