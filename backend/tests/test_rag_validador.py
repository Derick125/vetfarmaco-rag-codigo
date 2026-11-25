"""Testes de app/rag/validador.py — validação pós-geração (docs/RAG_SPEC.md §7)."""

import pytest

from app.rag.gerador import Trecho
from app.rag.roteador import CAMINHO_VOCABULARIO_PADRAO, carregar_vocabulario
from app.rag.validador import validar


@pytest.fixture(scope="module")
def vocabulario():
    return carregar_vocabulario(CAMINHO_VOCABULARIO_PADRAO)


# Chunk fictício, inventado para os testes: imita a estrutura de uma tabela de doses cujo
# cabeçalho de espécies não veio junto (só a linha do fármaco, valores por kg e uma nota
# que cita "equinos"). No metadado, `especies = ['equino']`; o texto nunca menciona cão nem gato.
# Nenhum texto de livro ou de bula foi copiado.
CHUNK_TRAMADOL = Trecho(
    chunk_id="fixture-tabela-002",
    referencia="Livro-texto fictício (2000)",
    capitulo="15 — Capítulo fictício",
    pagina=311,
    especies=["equino"],
    texto=(
        "Analgésico Alfa (mg/kg) 0,5 a 1 (IM) 1 a 2 (IV, IM, SC)\n\n(IV, IM, SC)\n\n"
        "Tramadol (mg/kg) 3 a 6\n\n(oral)\n\n2\n\n(oral)\n\n4 a 5 (oral)\n\n1 (epidural)\n\n"
        "Produtos fictícios: Exemplo®, Modelo®\n\n"
        "Legenda inventada: as siglas da tabela de teste não têm significado clínico. **Nota: o "
        "produto desta tabela de teste está registrado apenas para equinos, por via IV."
    ),
)

# Resposta fictícia, no formato da gerada para "tramadol dose gato".
RESPOSTA_TRAMADOL_GATO = {
    "paragrafos": [
        {
            "texto": (
                "Para gatos, a literatura veterinária indica a dose de 2 mg/kg por via oral "
                "para o tramadol."
            ),
            "chunk_ids": ["fixture-tabela-002"],
        }
    ],
    "citacoes": [
        {
            "chunk_id": "fixture-tabela-002",
            "trecho": "Tramadol (mg/kg) 3 a 6 (oral) 2 (oral) 4 a 5 (oral) 1 (epidural)",
            "fonte": "Livro-texto fictício (2000)",
            "pagina": 311,
        }
    ],
    "nivel_confianca": "alta",
}


def _resposta(texto: str, chunk_ids: list[str], trecho: str, nivel: str = "alta") -> dict:
    return {
        "paragrafos": [{"texto": texto, "chunk_ids": chunk_ids}],
        "citacoes": [{"chunk_id": chunk_ids[0], "trecho": trecho}] if chunk_ids else [],
        "nivel_confianca": nivel,
    }


# --- Espécie com lastro: o caso do tramadol ----------------------------------


def test_tramadol_gato_sem_lastro_de_especie_remove_paragrafo(vocabulario):
    r = validar(RESPOSTA_TRAMADOL_GATO, [CHUNK_TRAMADOL], vocabulario)

    assert not r.descartada
    assert r.resposta["paragrafos"] == []
    assert [p["motivo"] for p in r.paragrafos_removidos] == ["especie_sem_lastro: felino"]
    # Todos os parágrafos removidos → nada sustentado → sem_evidencia.
    assert r.nivel_original == "alta"
    assert r.nivel_final == "sem_evidencia"
    assert r.resposta["nivel_confianca"] == "sem_evidencia"


def test_o_valor_da_dose_ocorre_no_chunk_so_a_especie_falta(vocabulario):
    # Garante que o caso acima é barrado pela checagem de espécie, e não pela
    # de dose: o "2" de "2 mg/kg" aparece no chunk.
    r = validar(RESPOSTA_TRAMADOL_GATO, [CHUNK_TRAMADOL], vocabulario)
    assert "dose_sem_lastro" not in [p["motivo"] for p in r.paragrafos_removidos]


def test_nao_altera_a_resposta_original(vocabulario):
    validar(RESPOSTA_TRAMADOL_GATO, [CHUNK_TRAMADOL], vocabulario)
    assert len(RESPOSTA_TRAMADOL_GATO["paragrafos"]) == 1
    assert RESPOSTA_TRAMADOL_GATO["nivel_confianca"] == "alta"


def test_especie_com_lastro_por_metadado(vocabulario):
    chunk = Trecho(**{**CHUNK_TRAMADOL.__dict__, "especies": ["equino", "felino"]})
    r = validar(RESPOSTA_TRAMADOL_GATO, [chunk], vocabulario)
    assert r.paragrafos_removidos == []
    assert r.nivel_final == "alta"


def test_especie_com_lastro_por_texto_do_chunk(vocabulario):
    chunk = Trecho(
        chunk_id="x-1",
        referencia="Livro-texto fictício (2000)",
        especies=[],
        texto="Em gatos, a dose de tramadol é de 2 mg/kg por via oral.",
    )
    resposta = _resposta(
        "Para gatos, a dose é de 2 mg/kg por via oral.", ["x-1"], "a dose de tramadol é de 2 mg/kg"
    )
    r = validar(resposta, [chunk], vocabulario)
    assert r.paragrafos_removidos == []
    assert r.nivel_final == "alta"


def test_cada_especie_mencionada_precisa_de_lastro(vocabulario):
    chunk = Trecho(
        chunk_id="x-1",
        referencia="Livro-texto fictício (2000)",
        especies=["canino"],
        texto="Em cães, 2 mg/kg por via oral.",
    )
    resposta = _resposta(
        "Em cães e gatos, a dose é de 2 mg/kg por via oral.", ["x-1"], "Em cães, 2 mg/kg"
    )
    r = validar(resposta, [chunk], vocabulario)
    assert [p["motivo"] for p in r.paragrafos_removidos] == ["especie_sem_lastro: felino"]


def test_paragrafo_sem_dose_nao_passa_pela_checagem_de_especie(vocabulario):
    resposta = _resposta(
        "O tramadol é um opioide usado em gatos.", ["fixture-tabela-002"], "Tramadol (mg/kg)"
    )
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.paragrafos_removidos == []
    assert r.nivel_final == "alta"


def test_remocao_parcial_rebaixa_um_degrau_e_mantem_o_resto(vocabulario):
    resposta = RESPOSTA_TRAMADOL_GATO | {
        "paragrafos": [
            {"texto": "O tramadol é um opioide.", "chunk_ids": ["fixture-tabela-002"]},
            *RESPOSTA_TRAMADOL_GATO["paragrafos"],
        ]
    }
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert [p["texto"] for p in r.resposta["paragrafos"]] == ["O tramadol é um opioide."]
    assert r.nivel_final == "media"


# --- Demais checagens do §7 ---------------------------------------------------


def test_citacao_fantasma_descarta_a_resposta_inteira(vocabulario):
    resposta = _resposta("Texto.", ["nao-existe-001"], "Texto.")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.descartada
    assert r.resposta is None
    assert r.eventos == ["citacao_fantasma: nao-existe-001"]


def test_dose_sem_lastro_no_chunk_remove_o_paragrafo(vocabulario):
    resposta = _resposta("A dose é de 7 mg/kg.", ["fixture-tabela-002"], "Tramadol (mg/kg) 3 a 6")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert [p["motivo"] for p in r.paragrafos_removidos] == ["dose_sem_lastro"]
    assert r.nivel_final == "sem_evidencia"


def test_dose_sem_chunk_ids_remove_o_paragrafo(vocabulario):
    resposta = {
        "paragrafos": [{"texto": "A dose é de 2 mg/kg.", "chunk_ids": []}],
        "citacoes": [],
        "nivel_confianca": "media",
    }
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert [p["motivo"] for p in r.paragrafos_removidos] == ["dose_sem_chunk_ids"]


def test_trecho_nao_literal_rebaixa_a_confianca(vocabulario):
    resposta = _resposta("Opioide.", ["fixture-tabela-002"], "frase que o chunk não contém")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.nivel_final == "media"
    assert r.eventos == ["trecho_nao_literal: fixture-tabela-002"]


def test_trecho_literal_ignora_acento_caixa_e_quebras_de_linha(vocabulario):
    resposta = _resposta("Opioide.", ["fixture-tabela-002"], "TRAMADOL (MG/KG) 3 A 6 (ORAL)")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.eventos == []


def test_alerta_sem_chunk_ids_e_removido_e_rebaixa(vocabulario):
    resposta = _resposta("Opioide.", ["fixture-tabela-002"], "Tramadol (mg/kg)") | {
        "alerta_seguranca": {"severidade": "cautela", "texto": "Cuidado.", "chunk_ids": []}
    }
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert "alerta_seguranca" not in r.resposta
    assert r.nivel_final == "media"


def test_resposta_valida_passa_intacta(vocabulario):
    resposta = _resposta("O tramadol é um opioide.", ["fixture-tabela-002"], "Tramadol (mg/kg)")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.resposta == resposta
    assert r.eventos == []


def test_resposta_nao_parseavel_e_descartada(vocabulario):
    assert validar(None, [CHUNK_TRAMADOL], vocabulario).descartada


# --- Espécie com lastro por frase, com exceção para declaração de ausência ----

# Trechos fictícios para um parágrafo de insulina NPH: o chunk do livro (inventado) é de
# cão/suíno e o da bula (inventado) é de uso humano.
CHUNK_INSULINA_LIVRO = Trecho(
    chunk_id="fixture-insulina-001",
    referencia="Livro-texto fictício (2000)",
    capitulo="30",
    pagina=627,
    especies=["canino", "suino"],
    texto=(
        "Texto inventado: para cães diabéticos sem cetoacidose, o exemplo cita a insulina "
        "NPH na dose de 0,35 a 0,7 UI/kg a cada 12 h."
    ),
)
CHUNK_INSULINA_BULA = Trecho(
    chunk_id="insulina-nph-posologia-001",
    referencia="Bula — insulina NPH",
    secao="posologia",
    origem="humana",
    especies=[],
    texto="Posologia em seres humanos: dose individualizada conforme a glicemia.",
)
PARAGRAFO_INSULINA = (
    "A dose inicial de insulina NPH humana especificamente para gatos diabéticos não consta "
    "dos documentos recuperados. O material traz apenas a dose recomendada de NPH para cães "
    "diabéticos não cetoacidóticos (0,35 a 0,7 UI/kg a cada 12 h) e faixas posológicas "
    "destinadas a seres humanos em bula de uso humano."
)


def test_paragrafo_de_insulina_nao_e_barrado_por_frase(vocabulario):
    # "gatos" só aparece na frase sem dose; a frase com dose fala de cães, que têm lastro.
    resposta = _resposta(
        PARAGRAFO_INSULINA,
        ["fixture-insulina-001", "insulina-nph-posologia-001"],
        "na dose de 0,35 a 0,7 UI/kg a cada 12 h",
    )
    resposta["paragrafos"][0]["chunk_ids"] = ["fixture-insulina-001", "insulina-nph-posologia-001"]
    r = validar(resposta, [CHUNK_INSULINA_LIVRO, CHUNK_INSULINA_BULA], vocabulario)

    assert r.paragrafos_removidos == []
    assert r.resposta["paragrafos"][0]["texto"] == PARAGRAFO_INSULINA
    assert r.nivel_final == "alta"
    assert r.excecoes == []  # passou por frase, sem precisar de exceção


def test_dose_para_gatos_nao_consta_mas_em_gatos_use_2_mg_kg_e_barrada(vocabulario):
    # O ";" separa as frases: a segunda tem dose e espécie, e não declara ausência.
    resposta = _resposta(
        "A dose para gatos não consta; em gatos use 2 mg/kg.",
        ["fixture-tabela-002"],
        "Tramadol (mg/kg) 3 a 6",
    )
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)

    assert [p["motivo"] for p in r.paragrafos_removidos] == ["especie_sem_lastro: felino"]
    assert r.resposta["paragrafos"] == []
    assert r.excecoes == []


def test_frase_com_dose_e_especie_que_declara_ausencia_e_excecao_registrada(vocabulario):
    frase = "A dose de 2 mg/kg para gatos não consta dos documentos recuperados."
    resposta = _resposta(frase, ["fixture-tabela-002"], "Tramadol (mg/kg) 3 a 6")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)

    assert r.paragrafos_removidos == []
    assert r.nivel_final == "alta"
    assert r.excecoes == [
        {"frase": frase, "especie": "felino", "motivo": "a própria frase declara ausência"}
    ]


@pytest.mark.parametrize(
    "declaracao", ["não consta", "não há", "não foi possível", "não foi possível localizar"]
)
def test_declaracoes_de_ausencia_reconhecidas(vocabulario, declaracao):
    resposta = _resposta(
        f"Para gatos, a dose de 2 mg/kg {declaracao} no trecho.",
        ["fixture-tabela-002"],
        "Tramadol (mg/kg) 3 a 6",
    )
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.paragrafos_removidos == []
    assert len(r.excecoes) == 1


def test_excecao_nao_salva_paragrafo_removido_por_outra_frase(vocabulario):
    resposta = _resposta(
        "A dose de 2 mg/kg para gatos não consta. Em gatos use 2 mg/kg.",
        ["fixture-tabela-002"],
        "Tramadol (mg/kg) 3 a 6",
    )
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert [p["motivo"] for p in r.paragrafos_removidos] == ["especie_sem_lastro: felino"]
    assert r.excecoes == []  # exceção de parágrafo removido não é registrada


# --- Interação com lastro: alerta que nomeia ≥ 2 fármacos --------------------

CHUNK_CARPROFENO = Trecho(
    chunk_id="carprofeno-interacoes-001",
    referencia="Bula — carprofeno",
    secao="interacoes",
    origem="veterinaria",
    texto="Texto inventado: o exemplo não traz dados de uso do carprofeno com outros fármacos.",
)
CHUNK_FENOBARBITAL = Trecho(
    chunk_id="fixture-indutor-003",
    referencia="Livro-texto fictício (2000)",
    capitulo="13",
    pagina=271,
    texto="Texto inventado: o fenobarbital aparece aqui como indutor de enzimas do fígado.",
)
TEXTO_ALERTA = (
    "Recomenda-se cautela quanto ao deslocamento de ligação proteica do carprofeno e à "
    "indução metabólica hepática provocada pelo fenobarbital."
)


def _com_alerta(texto: str, chunk_ids: list[str], **extra) -> dict:
    return _resposta("Premissa citada.", [chunk_ids[0]] if chunk_ids else [], "x") | {
        "alerta_seguranca": {"severidade": "cautela", "texto": texto, "chunk_ids": chunk_ids},
        **extra,
    }


def _resposta_carprofeno_fenobarbital(chunk_ids: list[str]) -> dict:
    resposta = _com_alerta(TEXTO_ALERTA, chunk_ids)
    resposta["paragrafos"] = [{"texto": "Premissa citada.", "chunk_ids": chunk_ids[:1]}]
    resposta["citacoes"] = []
    return resposta


def test_alerta_com_dois_farmacos_sem_chunk_que_os_mencione_juntos_vira_inferencia(vocabulario):
    resposta = _resposta_carprofeno_fenobarbital(
        ["carprofeno-interacoes-001", "fixture-indutor-003"]
    )
    r = validar(resposta, [CHUNK_CARPROFENO, CHUNK_FENOBARBITAL], vocabulario)

    assert "alerta_seguranca" not in r.resposta
    movido = r.resposta["paragrafos"][-1]
    assert movido["texto"] == f"Inferência não documentada: {TEXTO_ALERTA}"
    assert movido["chunk_ids"] == ["carprofeno-interacoes-001", "fixture-indutor-003"]
    assert r.eventos == ["interacao_sem_lastro: carprofeno + fenobarbital"]
    assert r.alertas_movidos[0]["farmacos"] == ["carprofeno", "fenobarbital"]
    assert r.nivel_final == "alta"  # não rebaixa: o risco continua na resposta, rotulado


def test_alerta_com_dois_farmacos_e_chunk_que_menciona_ambos_e_mantido(vocabulario):
    chunk_ambos = Trecho(
        chunk_id="ambos-1",
        referencia="Livro-texto fictício (2000)",
        texto="Texto inventado: o fenobarbital reduz a meia-vida do carprofeno.",
    )
    resposta = _resposta_carprofeno_fenobarbital(["carprofeno-interacoes-001", "ambos-1"])
    r = validar(resposta, [CHUNK_CARPROFENO, chunk_ambos], vocabulario)

    assert r.resposta["alerta_seguranca"]["texto"] == TEXTO_ALERTA
    assert r.alertas_movidos == []
    assert r.eventos == []


def test_chunk_fora_do_alerta_nao_da_lastro_a_interacao(vocabulario):
    # O chunk com os dois fármacos existe no contexto, mas não é citado no alerta.
    chunk_ambos = Trecho(
        chunk_id="ambos-1",
        referencia="Livro-texto fictício (2000)",
        texto="Texto inventado: o fenobarbital reduz a meia-vida do carprofeno, no outro chunk.",
    )
    resposta = _resposta_carprofeno_fenobarbital(["carprofeno-interacoes-001"])
    r = validar(resposta, [CHUNK_CARPROFENO, chunk_ambos], vocabulario)
    assert "alerta_seguranca" not in r.resposta
    assert len(r.alertas_movidos) == 1


def test_alerta_com_um_so_farmaco_nao_e_tocado(vocabulario):
    resposta = _com_alerta(
        "O carprofeno exige cautela em hepatopatas.", ["carprofeno-interacoes-001"]
    )
    r = validar(resposta, [CHUNK_CARPROFENO], vocabulario)
    assert r.resposta["alerta_seguranca"]["texto"].startswith("O carprofeno")
    assert r.alertas_movidos == []


def test_alerta_com_dois_farmacos_e_sem_chunk_ids_vira_inferencia_sem_rebaixar(vocabulario):
    resposta = _com_alerta(TEXTO_ALERTA, [])
    resposta["paragrafos"] = []
    resposta["citacoes"] = []
    r = validar(resposta, [CHUNK_CARPROFENO], vocabulario)

    assert "alerta_seguranca" not in r.resposta
    assert r.resposta["paragrafos"] == [
        {"texto": f"Inferência não documentada: {TEXTO_ALERTA}", "chunk_ids": []}
    ]
    assert r.nivel_final == "alta"


def test_paragrafo_movido_tambem_passa_pela_checagem_de_dose(vocabulario):
    texto = "Carprofeno com fenobarbital: reduzir a dose para 9 mg/kg."
    resposta = _resposta_carprofeno_fenobarbital(["carprofeno-interacoes-001"])
    resposta["alerta_seguranca"]["texto"] = texto
    r = validar(resposta, [CHUNK_CARPROFENO], vocabulario)

    assert [p["motivo"] for p in r.paragrafos_removidos] == ["dose_sem_lastro"]
    assert all(not p["texto"].startswith("Inferência") for p in r.resposta["paragrafos"])


def test_resposta_sem_alerta_nao_e_afetada_pela_checagem_de_interacao(vocabulario):
    resposta = _resposta("O carprofeno é um AINE.", ["carprofeno-interacoes-001"], "carprofeno")
    r = validar(resposta, [CHUNK_CARPROFENO], vocabulario)
    assert r.alertas_movidos == []
    assert r.eventos == []


# --- "não há" só é exceção com "documentos" ou "trechos" na mesma frase --------


def test_nao_ha_sozinho_nao_e_excecao(vocabulario):
    resposta = _resposta(
        "Em gatos não há restrição de 2 mg/kg.",
        ["fixture-tabela-002"],
        "Tramadol (mg/kg) 3 a 6",
    )
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert [p["motivo"] for p in r.paragrafos_removidos] == ["especie_sem_lastro: felino"]
    assert r.excecoes == []


@pytest.mark.parametrize(
    "frase",
    [
        "Não há dose de 2 mg/kg para gatos nos documentos recuperados.",
        "Não há, nos trechos recuperados, dose de 2 mg/kg para gatos.",
        "Para gatos, não há no trecho a dose de 2 mg/kg.",
    ],
)
def test_nao_ha_com_documentos_ou_trechos_e_excecao(vocabulario, frase):
    resposta = _resposta(frase, ["fixture-tabela-002"], "Tramadol (mg/kg) 3 a 6")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.paragrafos_removidos == []
    assert len(r.excecoes) == 1


@pytest.mark.parametrize(
    "frase",
    ["Em gatos não existe restrição de 2 mg/kg.", "Em gatos não existem restrições de 2 mg/kg."],
)
def test_nao_existe_sozinho_nao_e_excecao(vocabulario, frase):
    resposta = _resposta(frase, ["fixture-tabela-002"], "Tramadol (mg/kg) 3 a 6")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert [p["motivo"] for p in r.paragrafos_removidos] == ["especie_sem_lastro: felino"]
    assert r.excecoes == []


@pytest.mark.parametrize(
    "frase",
    [
        "Não existe dose de 2 mg/kg para gatos nos documentos recuperados.",
        "Não existem, nos trechos recuperados, doses de 2 mg/kg para gatos.",
    ],
)
def test_nao_existe_com_documentos_ou_trechos_e_excecao(vocabulario, frase):
    resposta = _resposta(frase, ["fixture-tabela-002"], "Tramadol (mg/kg) 3 a 6")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.paragrafos_removidos == []
    assert len(r.excecoes) == 1


def test_trecho_nao_literal_e_substituido_pelo_texto_do_chunk(vocabulario):
    original = "frase que o chunk não contém"
    resposta = _resposta("Opioide.", ["fixture-tabela-002"], original)
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.resposta["citacoes"][0]["trecho"] == CHUNK_TRAMADOL.texto
    assert r.trechos_substituidos == [
        {"chunk_id": "fixture-tabela-002", "trecho_original": original}
    ]
    assert resposta["citacoes"][0]["trecho"] == original  # a entrada não é alterada


def test_trecho_literal_nao_e_substituido(vocabulario):
    resposta = _resposta("Opioide.", ["fixture-tabela-002"], "Tramadol (mg/kg) 3 a 6")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.resposta["citacoes"][0]["trecho"] == "Tramadol (mg/kg) 3 a 6"
    assert r.trechos_substituidos == []


def test_expressao_do_prompt_nao_consta_dos_documentos_recuperados_e_excecao(vocabulario):
    frase = "A dose de 2 mg/kg para gatos não consta dos documentos recuperados."
    resposta = _resposta(frase, ["fixture-tabela-002"], "Tramadol (mg/kg) 3 a 6")
    r = validar(resposta, [CHUNK_TRAMADOL], vocabulario)
    assert r.paragrafos_removidos == []
    assert len(r.excecoes) == 1


def test_regra_15_do_prompt_fixa_a_expressao():
    from app.rag.gerador import SYSTEM_INSTRUCTION

    assert '"não consta dos documentos recuperados"' in SYSTEM_INSTRUCTION


# --- Trecho literal com elipse [...]: fragmentos literais, no mesmo chunk, em ordem ---


def _eventos_do_trecho(vocabulario, trecho: str) -> list[str]:
    resposta = _resposta("Opioide.", ["fixture-tabela-002"], trecho)
    return validar(resposta, [CHUNK_TRAMADOL], vocabulario).eventos


def test_trecho_com_elipse_e_fragmentos_em_ordem_e_literal(vocabulario):
    trecho = "Analgésico Alfa (mg/kg) 0,5 a 1 (IM) [...] Tramadol (mg/kg) 3 a 6 [...] 1 (epidural)"
    assert _eventos_do_trecho(vocabulario, trecho) == []


def test_trecho_com_elipse_aceita_elipse_unicode_e_ignora_caixa_e_acento(vocabulario):
    trecho = "ANALGÉSICO ALFA (mg/kg) […] tramadol (MG/KG) 3 a 6"
    assert _eventos_do_trecho(vocabulario, trecho) == []


def test_fragmentos_fora_de_ordem_nao_sao_literais(vocabulario):
    # "1 (epidural)" vem depois de "Tramadol" no chunk; aqui aparece antes.
    trecho = "1 (epidural) [...] Tramadol (mg/kg) 3 a 6"
    assert _eventos_do_trecho(vocabulario, trecho) == ["trecho_nao_literal: fixture-tabela-002"]


def test_fragmento_ausente_do_chunk_nao_e_literal(vocabulario):
    trecho = "Tramadol (mg/kg) 3 a 6 [...] eliminação renal"
    assert _eventos_do_trecho(vocabulario, trecho) == ["trecho_nao_literal: fixture-tabela-002"]


def test_fragmento_nao_pode_reaproveitar_o_texto_do_anterior(vocabulario):
    # "Tramadol" ocorre uma vez no chunk: dois fragmentos iguais não cabem.
    trecho = "Tramadol (mg/kg) [...] Tramadol (mg/kg)"
    assert _eventos_do_trecho(vocabulario, trecho) == ["trecho_nao_literal: fixture-tabela-002"]


def test_trecho_sem_elipse_continua_exigindo_trecho_continuo(vocabulario):
    # Sem [...], os mesmos fragmentos separados por outro texto não são literais.
    trecho = "Analgésico Alfa (mg/kg) 0,5 a 1 (IM) Tramadol (mg/kg) 3 a 6"
    assert _eventos_do_trecho(vocabulario, trecho) == ["trecho_nao_literal: fixture-tabela-002"]
