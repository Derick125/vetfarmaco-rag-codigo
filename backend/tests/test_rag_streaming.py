"""Testes de app/rag/streaming.py — eventos só depois da validação (RAG_SPEC.md §7.1)."""

import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from app.rag.roteador import CAMINHO_VOCABULARIO_PADRAO, carregar_vocabulario
from app.rag.streaming import ExtratorParagrafos, Telemetria, Uso, custo_usd, emitir_resposta
from tests.test_rag_validador import CHUNK_TRAMADOL

ID = CHUNK_TRAMADOL.chunk_id
pytestmark = pytest.mark.anyio

EVENTOS_PERMITIDOS = {"paragrafo", "citacoes", "alerta", "fim", "erro"}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def vocabulario():
    return carregar_vocabulario(CAMINHO_VOCABULARIO_PADRAO)


def _resposta(paragrafos, *, citacoes=None, alerta=None, nivel="alta"):
    r = {
        "paragrafos": paragrafos,
        "citacoes": citacoes
        if citacoes is not None
        else [{"chunk_id": ID, "trecho": "Tramadol (mg/kg) 3 a 6"}],
        "nivel_confianca": nivel,
    }
    if alerta is not None:
        r["alerta_seguranca"] = alerta
    return r


P_OK = {"texto": "O tramadol é um opioide.", "chunk_ids": [ID]}
P_OK2 = {"texto": "Há apresentação para equinos.", "chunk_ids": [ID]}
P_DOSE_GATO = {"texto": "Para gatos, use 2 mg/kg por via oral.", "chunk_ids": [ID]}


def _pedacos(resposta, tamanho=7):
    texto = json.dumps(resposta, ensure_ascii=False)
    return [texto[i : i + tamanho] for i in range(0, len(texto), tamanho)]


class FonteFalsa:
    """Stream falso que conta quantos chunks foram consumidos."""

    def __init__(self, pedacos, uso=None, atraso=0.0):
        self.pedacos = pedacos
        self.uso = uso
        self.atraso = atraso
        self.consumidos = 0

    async def __aiter__(self):
        for i, texto in enumerate(self.pedacos):
            if self.atraso:
                await asyncio.sleep(self.atraso)
            self.consumidos += 1
            ultimo = i == len(self.pedacos) - 1
            yield SimpleNamespace(text=texto, usage_metadata=self.uso if ultimo else None)


async def _coletar(fonte, vocabulario, **kw):
    tel = Telemetria()
    eventos = [
        e
        async for e in emitir_resposta(
            fonte,
            [CHUNK_TRAMADOL],
            vocabulario,
            inicio=time.perf_counter(),
            modelo="modelo-teste",
            telemetria=tel,
            **kw,
        )
    ]
    return eventos, tel


# --- Extrator incremental ------------------------------------------------------


def test_extrator_emite_cada_paragrafo_uma_vez_e_em_ordem():
    resposta = _resposta([P_OK, P_OK2])
    ex = ExtratorParagrafos()
    achados = []
    for pedaco in _pedacos(resposta, 3):
        achados += ex.alimentar(pedaco)
    assert achados == [P_OK, P_OK2]


def test_extrator_ignora_chaves_e_aspas_dentro_de_strings():
    p = {"texto": 'Veja {"a": [1]} e \\"aspas\\" } ]', "chunk_ids": [ID]}
    ex = ExtratorParagrafos()
    achados = []
    for pedaco in _pedacos(_resposta([p]), 1):
        achados += ex.alimentar(pedaco)
    assert achados == [p]


def test_extrator_nao_confunde_objetos_de_outras_chaves_com_paragrafos():
    alerta = {"severidade": "cautela", "texto": "x", "chunk_ids": [ID]}
    texto = json.dumps(
        {
            "alerta_seguranca": alerta,
            "citacoes": [{"chunk_id": ID, "trecho": "t"}],
            "paragrafos": [P_OK],
        }
    )
    assert ExtratorParagrafos().alimentar(texto) == [P_OK]


def test_extrator_nao_emite_paragrafo_incompleto():
    texto = json.dumps(_resposta([P_OK]))
    corte = texto.index('"chunk_ids"')
    assert ExtratorParagrafos().alimentar(texto[:corte]) == []


# --- Ordem e conteúdo dos eventos ----------------------------------------------


async def test_ordem_paragrafos_citacoes_fim(vocabulario):
    fonte = FonteFalsa(_pedacos(_resposta([P_OK, P_OK2])))
    eventos, tel = await _coletar(fonte, vocabulario)
    assert [e.nome for e in eventos] == ["paragrafo", "paragrafo", "citacoes", "fim"]
    assert eventos[0].dados == {"indice": 1, "texto": P_OK["texto"], "chunkIds": [ID]}
    assert eventos[2].dados["citacoes"][0]["fonte"] == CHUNK_TRAMADOL.referencia
    assert tel.paragrafos_emitidos == 2


async def test_nunca_emite_token_bruto(vocabulario):
    fonte = FonteFalsa(_pedacos(_resposta([P_OK]), 5))
    eventos, _ = await _coletar(fonte, vocabulario)
    assert {e.nome for e in eventos} <= EVENTOS_PERMITIDOS
    assert "token" not in {e.nome for e in eventos}
    # Nenhum evento carrega um fragmento do JSON do modelo.
    for e in eventos:
        assert '"paragrafos"' not in json.dumps(e.dados)


async def test_paragrafo_sai_antes_do_fim_do_stream(vocabulario):
    pedacos = _pedacos(_resposta([P_OK, P_OK2]), 4)
    fonte = FonteFalsa(pedacos)
    gerador = emitir_resposta(
        fonte,
        [CHUNK_TRAMADOL],
        vocabulario,
        inicio=time.perf_counter(),
        modelo="m",
    )
    primeiro = await anext(gerador)
    assert primeiro.nome == "paragrafo"
    assert fonte.consumidos < len(pedacos)
    await gerador.aclose()


# --- Paragrafo reprovado nunca sai ---------------------------------------------


async def test_paragrafo_com_dose_sem_lastro_de_especie_nao_e_emitido(vocabulario):
    fonte = FonteFalsa(_pedacos(_resposta([P_OK, P_DOSE_GATO])))
    eventos, tel = await _coletar(fonte, vocabulario)
    textos = [e.dados["texto"] for e in eventos if e.nome == "paragrafo"]
    assert textos == [P_OK["texto"]]
    assert eventos[-1].nome == "fim"
    assert eventos[-1].dados["nivelConfianca"] == "media"  # rebaixada pelo validador
    assert any("especie_sem_lastro" in m for m in tel.eventos_validador)


async def test_todos_removidos_vira_sem_evidencia_sem_paragrafos(vocabulario):
    fonte = FonteFalsa(_pedacos(_resposta([P_DOSE_GATO])))
    eventos, _ = await _coletar(fonte, vocabulario)
    assert [e.nome for e in eventos] == ["citacoes", "fim"]
    assert eventos[-1].dados["nivelConfianca"] == "sem_evidencia"


async def test_citacao_fantasma_em_paragrafo_aborta_sem_emitir_e_para_o_stream(vocabulario):
    fantasma = {"texto": "Texto.", "chunk_ids": ["inventado-001"]}
    pedacos = _pedacos(_resposta([fantasma, P_OK]), 4)
    fonte = FonteFalsa(pedacos)
    eventos, tel = await _coletar(fonte, vocabulario)
    assert [e.nome for e in eventos] == ["erro"]
    assert eventos[0].dados["codigo"] == "citacao_fantasma"
    assert fonte.consumidos < len(pedacos)
    assert tel.citacoes_fantasma == 1


async def test_citacao_fantasma_so_nas_citacoes_vira_erro_sem_fim(vocabulario):
    resposta = _resposta([P_OK], citacoes=[{"chunk_id": "inventado-001", "trecho": "x"}])
    eventos, _ = await _coletar(FonteFalsa(_pedacos(resposta)), vocabulario)
    nomes = [e.nome for e in eventos]
    assert nomes[-1] == "erro" and "fim" not in nomes and "citacoes" not in nomes


async def test_json_invalido_vira_erro_sem_vazar_o_texto(vocabulario):
    eventos, _ = await _coletar(FonteFalsa(['{"paragrafos": [ {"texto": "SEGREDO']), vocabulario)
    assert [e.nome for e in eventos] == ["erro"]
    assert "SEGREDO" not in json.dumps(eventos[0].dados)


async def test_falha_do_stream_vira_erro_generico(vocabulario):
    async def quebrado():
        yield SimpleNamespace(text='{"paragrafos": [', usage_metadata=None)
        raise RuntimeError("detalhe interno")

    eventos, _ = await _coletar(quebrado(), vocabulario)
    assert [e.nome for e in eventos] == ["erro"]
    assert "detalhe interno" not in json.dumps(eventos[0].dados)


# --- Alerta só depois da validação completa ------------------------------------


async def test_alerta_sai_depois_dos_paragrafos_e_das_citacoes(vocabulario):
    alerta = {"severidade": "cautela", "texto": "Cautela com opioides.", "chunk_ids": [ID]}
    # O alerta vem ANTES dos parágrafos no JSON: ainda assim só sai ao final.
    resposta = {"alerta_seguranca": alerta, **_resposta([P_OK, P_OK2])}
    eventos, _ = await _coletar(FonteFalsa(_pedacos(resposta)), vocabulario)
    assert [e.nome for e in eventos] == ["paragrafo", "paragrafo", "citacoes", "alerta", "fim"]
    assert eventos[3].dados["texto"] == alerta["texto"]


async def test_alerta_sem_chunk_ids_nao_sai(vocabulario):
    alerta = {"severidade": "cautela", "texto": "Cuidado.", "chunk_ids": []}
    eventos, _ = await _coletar(FonteFalsa(_pedacos(_resposta([P_OK], alerta=alerta))), vocabulario)
    assert "alerta" not in [e.nome for e in eventos]


async def test_alerta_com_interacao_sem_lastro_vira_paragrafo_inferencia(vocabulario):
    alerta = {
        "severidade": "cautela",
        "texto": "Fenobarbital e carprofeno competem por proteínas.",
        "chunk_ids": [ID],
    }
    eventos, _ = await _coletar(FonteFalsa(_pedacos(_resposta([P_OK], alerta=alerta))), vocabulario)
    assert "alerta" not in [e.nome for e in eventos]
    ultimo = [e for e in eventos if e.nome == "paragrafo"][-1]
    assert ultimo.dados["texto"].startswith("Inferência não documentada:")


# --- Os três tempos e o custo ---------------------------------------------------


async def test_tres_tempos_medidos_separadamente(vocabulario):
    fonte = FonteFalsa(_pedacos(_resposta([P_OK, P_OK2]), 9), atraso=0.005)
    eventos, tel = await _coletar(fonte, vocabulario)
    t = tel.tempos
    assert t.ms_ate_primeiro_token is not None
    assert t.ms_ate_primeiro_paragrafo_validado is not None
    assert t.ms_total is not None
    # O primeiro parágrafo só fecha depois de vários tokens: os tempos não coincidem.
    assert t.ms_ate_primeiro_token < t.ms_ate_primeiro_paragrafo_validado < t.ms_total
    tempos_fim = eventos[-1].dados["tempos"]
    assert tempos_fim["msPrimeiroToken"] == t.ms_ate_primeiro_token
    assert tempos_fim["msPrimeiroParagrafoValidado"] == t.ms_ate_primeiro_paragrafo_validado


async def test_sem_paragrafo_validado_o_tempo_fica_nulo(vocabulario):
    fonte = FonteFalsa(_pedacos(_resposta([])))
    _, tel = await _coletar(fonte, vocabulario)
    assert tel.tempos.ms_ate_primeiro_token is not None
    assert tel.tempos.ms_ate_primeiro_paragrafo_validado is None


def test_custo_inclui_thought_tokens_como_saida():
    uso = Uso(input_tokens=1_000_000, output_tokens=1_000_000, thought_tokens=1_000_000)
    assert custo_usd(uso, 0.75, 3.75) == pytest.approx(0.75 + 2 * 3.75)


def test_custo_desconhecido_e_none_nao_zero():
    assert custo_usd(Uso(1000, 10, 5), None, 3.75) is None
    assert custo_usd(Uso(None, 10, 5), 0.75, 3.75) is None


async def test_fim_traz_uso_e_custo(vocabulario):
    uso = SimpleNamespace(
        prompt_token_count=1_000_000, candidates_token_count=0, thoughts_token_count=1_000_000
    )
    fonte = FonteFalsa(_pedacos(_resposta([P_OK])), uso=uso)
    eventos, _ = await _coletar(fonte, vocabulario, preco_in_usd=1.0, preco_out_usd=2.0)
    fim = eventos[-1].dados
    assert fim["usage"] == {"inputTokens": 1_000_000, "outputTokens": 0, "thoughtTokens": 1_000_000}
    assert fim["custoUsd"] == pytest.approx(1.0 + 2.0)
    assert fim["modelo"] == "modelo-teste"
