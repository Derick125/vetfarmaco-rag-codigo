"""Testes de POST /consulta: autenticação por X-API-Key e contrato SSE."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

import app.api.consulta as modulo
import app.api.deps as deps
from app.config import Settings
from app.main import app
from app.rag.recuperacao import Recuperacao
from tests.test_rag_validador import CHUNK_TRAMADOL

ID = CHUNK_TRAMADOL.chunk_id
CHAVE = "chave-de-teste"
CORPO = {"pergunta": "Qual a classe do tramadol?"}

RESPOSTA = {
    "paragrafos": [{"texto": "O tramadol é um opioide.", "chunk_ids": [ID]}],
    "citacoes": [{"chunk_id": ID, "trecho": "Tramadol (mg/kg) 3 a 6"}],
    "nivel_confianca": "alta",
}


def _settings(**kw) -> Settings:
    base = dict(
        app_api_key=CHAVE,
        gemini_api_key="g",
        database_url="postgresql://x/y",
        modelo_id="modelo-teste",
        preco_in_usd=1.0,
        preco_out_usd=2.0,
    )
    return Settings(_env_file=None, **(base | kw))


@pytest.fixture
def capturado() -> dict:
    return {}


@pytest.fixture
def servico(monkeypatch, capturado):
    s = _settings()
    monkeypatch.setattr(deps, "get_settings", lambda: s)
    monkeypatch.setattr(modulo, "get_settings", lambda: s)

    async def recuperar_falso(settings, indice, pergunta):
        capturado["pergunta_da_recuperacao"] = pergunta
        return Recuperacao([CHUNK_TRAMADOL], ms_busca_vetorial=1.0, ms_busca_lexical=2.0)

    monkeypatch.setattr(modulo, "_recuperar", recuperar_falso)

    async def gerar_falso(client, modelo, pergunta, trechos, nivel):
        capturado["texto_ao_modelo"] = pergunta
        capturado["nivel"] = nivel
        texto = json.dumps(RESPOSTA, ensure_ascii=False)
        uso = SimpleNamespace(
            prompt_token_count=10, candidates_token_count=20, thoughts_token_count=30
        )
        yield SimpleNamespace(text=texto[:40], usage_metadata=None)
        yield SimpleNamespace(text=texto[40:], usage_metadata=uso)

    monkeypatch.setattr(modulo, "gerar_stream", gerar_falso)
    with TestClient(app) as client:
        yield client


def _eventos(resposta) -> list[tuple[str, dict]]:
    saida, nome = [], None
    for linha in resposta.iter_lines():
        if linha.startswith("event:"):
            nome = linha.split(":", 1)[1].strip()
        elif linha.startswith("data:") and nome:
            saida.append((nome, json.loads(linha.split(":", 1)[1])))
            nome = None
    return saida


def test_sem_api_key_401(servico):
    assert servico.post("/consulta", json=CORPO).status_code == 401


def test_api_key_errada_401(servico):
    r = servico.post("/consulta", json=CORPO, headers={"X-API-Key": "outra"})
    assert r.status_code == 401


def test_api_key_nao_configurada_503_nunca_aberto(servico, monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(app_api_key=None))
    r = servico.post("/consulta", json=CORPO, headers={"X-API-Key": ""})
    assert r.status_code == 503


def test_corpo_invalido_422(servico):
    r = servico.post("/consulta", json={"pergunta": ""}, headers={"X-API-Key": CHAVE})
    assert r.status_code == 422


def test_servico_sem_configuracao_do_modelo_503(servico, monkeypatch):
    monkeypatch.setattr(modulo, "get_settings", lambda: _settings(modelo_id=None))
    r = servico.post("/consulta", json=CORPO, headers={"X-API-Key": CHAVE})
    assert r.status_code == 503


def test_stream_sse_na_ordem_do_contrato(servico):
    with servico.stream("POST", "/consulta", json=CORPO, headers={"X-API-Key": CHAVE}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        eventos = _eventos(r)
    assert [n for n, _ in eventos] == ["recuperacao", "paragrafo", "citacoes", "fim"]
    assert eventos[0][1]["chunks"] == 1
    assert eventos[1][1]["texto"] == "O tramadol é um opioide."
    fim = eventos[3][1]
    assert fim["modelo"] == "modelo-teste"
    assert fim["usage"]["thoughtTokens"] == 30
    # (10 × 1 + (20 + 30) × 2) / 1e6: o raciocínio entra no custo como saída.
    assert fim["custoUsd"] == pytest.approx((10 * 1.0 + 50 * 2.0) / 1e6)


def test_telemetria_registra_os_tres_tempos_e_thought_tokens(servico):
    with capture_logs() as logs:
        with servico.stream("POST", "/consulta", json=CORPO, headers={"X-API-Key": CHAVE}) as r:
            _eventos(r)
    registro = next(x for x in logs if x["event"] == "consulta_concluida")
    for campo in (
        "ms_ate_primeiro_token",
        "ms_ate_primeiro_paragrafo_validado",
        "ms_total",
    ):
        assert registro[campo] is not None, campo
    assert registro["thought_tokens"] == 30
    assert registro["custo_usd"] == pytest.approx((10 * 1.0 + 50 * 2.0) / 1e6)
    assert registro["modelo"] == "modelo-teste"
    assert registro["desfecho"] == "ok"


def test_falha_na_recuperacao_vira_evento_erro(servico, monkeypatch):
    async def quebra(*a):
        raise RuntimeError("senha=segredo")

    monkeypatch.setattr(modulo, "_recuperar", quebra)
    with servico.stream("POST", "/consulta", json=CORPO, headers={"X-API-Key": CHAVE}) as r:
        eventos = _eventos(r)
    assert [n for n, _ in eventos] == ["erro"]
    assert "segredo" not in json.dumps(eventos[0][1])


# --- Campos estruturados -------------------------------------------------------------

COMPLETO = {
    "pergunta": "É seguro repetir meloxicam neste paciente?",
    "especie": "felino",
    "peso_kg": 4.2,
    "farmacos": ["Meloxicam", "furosemida"],
    "comorbidades": ["insuficiencia_renal_cronica"],
}


def _consulta(servico, corpo):
    with servico.stream("POST", "/consulta", json=corpo, headers={"X-API-Key": CHAVE}) as r:
        return r.status_code, _eventos(r) if r.status_code == 200 else None


def test_campos_estruturados_compoem_o_texto_do_modelo(servico, capturado):
    status, eventos = _consulta(servico, COMPLETO)
    assert status == 200 and eventos[-1][0] == "fim"
    assert capturado["texto_ao_modelo"] == (
        "Espécie: felino.\n"
        "Peso: 4,2 kg.\n"
        "Fármacos em questão: meloxicam, furosemida.\n"
        "Condições relevantes: insuficiência renal crônica.\n"
        "\n"
        "Pergunta: É seguro repetir meloxicam neste paciente?"
    )


def test_recuperacao_recebe_so_a_pergunta_sem_espécie_nem_campos(servico, capturado):
    _consulta(servico, COMPLETO)
    assert capturado["pergunta_da_recuperacao"] == COMPLETO["pergunta"]


def test_so_a_pergunta_mantem_o_comportamento_anterior(servico, capturado):
    _consulta(servico, CORPO)
    assert capturado["texto_ao_modelo"] == CORPO["pergunta"]
    assert capturado["pergunta_da_recuperacao"] == CORPO["pergunta"]


def test_comorbidade_vai_ao_roteador_e_sobe_o_raciocinio(servico, capturado):
    corpo = {"pergunta": "Qual a dose de meloxicam?", "farmacos": ["meloxicam"]}
    _consulta(servico, corpo)
    assert capturado["nivel"] == "low"
    _consulta(servico, corpo | {"comorbidades": ["hepatopatia"]})
    assert capturado["nivel"] == "high"


def test_thinking_level_vai_na_recuperacao_e_no_fim(servico, capturado):
    corpo = {"pergunta": "Qual a dose de meloxicam?", "farmacos": ["meloxicam"]}
    for extra, nivel in (({}, "low"), ({"comorbidades": ["hepatopatia"]}, "high")):
        with servico.stream(
            "POST", "/consulta", json=corpo | extra, headers={"X-API-Key": CHAVE}
        ) as r:
            eventos = dict(_eventos(r))
        assert eventos["recuperacao"]["thinkingLevel"] == nivel
        assert eventos["fim"]["thinkingLevel"] == nivel
        assert capturado["nivel"] == nivel


@pytest.mark.parametrize(
    "extra",
    [
        {"especie": "equino"},
        {"peso_kg": 0},
        {"peso_kg": -1},
        {"peso_kg": 5000},
        {"comorbidades": ["cliente chato"]},
        {"farmacos": ["x"] * 11},
    ],
)
def test_campo_invalido_422(servico, extra):
    status, _ = _consulta(servico, CORPO | extra)
    assert status == 422


def test_farmaco_fora_do_dicionario_422(servico):
    status, _ = _consulta(servico, CORPO | {"farmacos": ["Rex da Silva"]})
    assert status == 422


def test_farmaco_repetido_aparece_uma_vez_com_nome_canonico(servico, capturado):
    _consulta(servico, CORPO | {"farmacos": ["meloxicam", "MELOXICAM"]})
    assert "Fármacos em questão: meloxicam.\n" in capturado["texto_ao_modelo"]
