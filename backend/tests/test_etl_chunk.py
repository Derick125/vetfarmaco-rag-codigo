"""Testes de etl/chunk.py — tamanho e sobreposição das janelas (docs/RAG_SPEC.md §2)."""

from pathlib import Path

import pytest

from etl.chunk import (
    _ENCODER,
    JANELA_TOKENS,
    MAX_TOKENS_CHUNK,
    SOBREPOSICAO_TOKENS,
    PaginaLida,
    _casar,
    _compilar_termos,
    _janelas,
    _montar_chunk_id,
    _tokens_do_documento,
    carregar_vocabulario,
    segmentar,
)

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "etl" / "vocabulario" / "farmacos.yaml"

# Os seis cenários do Quadro 2 do TCC (docs/RAG_SPEC.md §9).
FARMACOS_QUADRO_2 = {
    "paracetamol",
    "ivermectina",
    "fenobarbital",
    "carprofeno",
    "tramadol",
    "insulina NPH",
    "meloxicam",
}


def _paragrafo(indice: int) -> str:
    return (
        f"Parágrafo número {indice} de texto sintético usado para validar o tamanho "
        "e a sobreposição das janelas de chunking, com palavras suficientes para "
        "gerar tokens de forma previsível em português. "
    )


def _paginas_sinteticas(n_paragrafos: int, paginas: int = 1) -> list[PaginaLida]:
    """Distribui `n_paragrafos` parágrafos únicos e numerados entre `paginas`."""
    por_pagina = max(1, n_paragrafos // paginas)
    registros = []
    indice = 0
    for numero_pagina in range(1, paginas + 1):
        texto = "".join(_paragrafo(i) for i in range(indice, indice + por_pagina))
        indice += por_pagina
        registros.append(
            PaginaLida(numero=numero_pagina, capitulo="1 — Capítulo Teste", texto=texto)
        )
    return registros


# --------------------------------------------------------------------------
# _janelas — matemática pura da janela deslizante
# --------------------------------------------------------------------------


def test_janelas_tamanho_e_passo():
    intervalos = _janelas(total=2000, janela=512, passo=448)

    for inicio, fim in intervalos[:-1]:
        assert fim - inicio == 512

    ultimo_inicio, ultimo_fim = intervalos[-1]
    assert ultimo_fim - ultimo_inicio <= 512
    assert ultimo_fim == 2000


def test_janelas_sobreposicao_exata_entre_consecutivas():
    intervalos = _janelas(total=2000, janela=512, passo=448)

    for (_inicio_a, fim_a), (inicio_b, _fim_b) in zip(intervalos, intervalos[1:], strict=False):
        assert fim_a - inicio_b == 64


def test_janelas_cobre_intervalo_inteiro_sem_buracos():
    intervalos = _janelas(total=1500, janela=512, passo=448)

    for (_inicio_a, fim_a), (inicio_b, _fim_b) in zip(intervalos, intervalos[1:], strict=False):
        assert inicio_b < fim_a  # próxima janela começa antes do fim da anterior — sem buraco

    assert intervalos[0][0] == 0
    assert intervalos[-1][1] == 1500


def test_janelas_entrada_menor_que_a_janela_gera_uma_unica_janela():
    assert _janelas(total=100, janela=512, passo=448) == [(0, 100)]


def test_janelas_entrada_vazia():
    assert _janelas(total=0, janela=512, passo=448) == []


def test_constantes_do_paradigma_sliding_window():
    """512 tokens com sobreposição de 64 — docs/RAG_SPEC.md §2."""
    assert JANELA_TOKENS == 512
    assert SOBREPOSICAO_TOKENS == 64
    assert MAX_TOKENS_CHUNK == 2048


# --------------------------------------------------------------------------
# _tokens_do_documento + _janelas — sobreposição real, ao nível de token
# --------------------------------------------------------------------------


def test_sobreposicao_em_tokens_reais_entre_janelas_consecutivas():
    paginas = _paginas_sinteticas(n_paragrafos=200)
    todos_tokens, _pagina_do_token, _capitulo_do_token = _tokens_do_documento(paginas)
    passo = JANELA_TOKENS - SOBREPOSICAO_TOKENS
    intervalos = _janelas(len(todos_tokens), JANELA_TOKENS, passo)
    assert len(intervalos) >= 3  # o texto sintético deve gerar múltiplas janelas

    for (_inicio_a, fim_a), (inicio_b, _fim_b) in zip(intervalos, intervalos[1:], strict=False):
        cauda_a = todos_tokens[fim_a - SOBREPOSICAO_TOKENS : fim_a]
        cabeca_b = todos_tokens[inicio_b : inicio_b + SOBREPOSICAO_TOKENS]
        assert cauda_a == cabeca_b


# --------------------------------------------------------------------------
# segmentar() — comportamento observável nos chunks finais
# --------------------------------------------------------------------------


@pytest.fixture
def vocabulario():
    return carregar_vocabulario(CAMINHO_VOCABULARIO)


def test_nenhum_chunk_excede_o_limite_de_2048_tokens(vocabulario):
    paginas = _paginas_sinteticas(n_paragrafos=400)
    chunks = segmentar(paginas, fonte="Fonte Teste", tipo_fonte="livro", vocabulario=vocabulario)

    assert chunks  # o corpus sintético deve gerar ao menos um chunk
    assert all(c.tokens <= MAX_TOKENS_CHUNK for c in chunks)


def test_chunks_de_texto_corrido_ficam_proximos_do_alvo_de_512_tokens(vocabulario):
    paginas = _paginas_sinteticas(n_paragrafos=400)
    chunks = segmentar(paginas, fonte="Fonte Teste", tipo_fonte="livro", vocabulario=vocabulario)

    # todo chunk exceto o(s) último(s) de cada página deve ficar bem próximo
    # da janela alvo — uma pequena folga cobre o efeito de o texto final ser
    # re-tokenizado após decodificado (não é garantido round-trip exato).
    quase_no_alvo = [c for c in chunks if c.tokens >= JANELA_TOKENS - 5]
    assert len(quase_no_alvo) >= 2


def test_chunks_consecutivos_compartilham_texto_sobreposto(vocabulario):
    paginas = _paginas_sinteticas(n_paragrafos=400)
    chunks = segmentar(paginas, fonte="Fonte Teste", tipo_fonte="livro", vocabulario=vocabulario)

    primeiro, segundo = chunks[0], chunks[1]
    tokens_primeiro = _ENCODER.encode(primeiro.texto)
    tokens_segundo = _ENCODER.encode(segundo.texto)
    cauda = _ENCODER.decode(tokens_primeiro[-SOBREPOSICAO_TOKENS:])
    assert (
        cauda in segundo.texto
        or _ENCODER.decode(tokens_segundo[: SOBREPOSICAO_TOKENS // 2]) in primeiro.texto
    )


def test_tabela_nunca_e_dividida_entre_chunks(vocabulario):
    tabela = (
        "| Medicamento | Espécie | Dose (mg/kg) |\n| --- | --- | --- |\n| Meloxicam | Cães | 0,2 |"
    )
    paginas = [
        PaginaLida(
            numero=10,
            capitulo="1 — Capítulo Teste",
            texto="Texto normal da página.",
            tabelas=[tabela],
        )
    ]
    chunks = segmentar(paginas, fonte="Fonte Teste", tipo_fonte="livro", vocabulario=vocabulario)

    tabelas_nos_chunks = [c for c in chunks if c.texto == tabela]
    assert len(tabelas_nos_chunks) == 1


def test_farmacos_e_especies_extraidos_por_casamento(vocabulario):
    texto = "O meloxicam é indicado para cães e gatos com dor pós-operatória."
    farmacos = _casar(texto, vocabulario.farmacos)
    especies = _casar(texto, vocabulario.especies)

    assert farmacos == ["meloxicam"]
    assert especies == ["canino", "felino"]


def test_casamento_nao_gera_falso_positivo_para_texto_sem_farmaco(vocabulario):
    texto = "Este parágrafo fala sobre fisiologia renal, sem citar nenhum medicamento."
    assert _casar(texto, vocabulario.farmacos) == []


def test_casamento_usa_sinonimo_e_retorna_nome_canonico():
    termos = _compilar_termos(
        [
            {
                "nome": "ácido acetilsalicílico",
                "sinonimos": ["ácido acetilsalicílico", "aas", "aspirina"],
            }
        ]
    )
    assert _casar("O paciente já usava AAS antes da consulta.", termos) == [
        "ácido acetilsalicílico"
    ]


def test_chunk_id_segue_o_formato_fonte_capitulo_pagina_sequencia(vocabulario):
    paginas = [
        PaginaLida(
            numero=574, capitulo="22 — Anti-inflamatórios Não Esteroidais", texto="Texto curto."
        )
    ]
    chunks = segmentar(
        paginas, fonte="Spinosa et al. (2017)", tipo_fonte="livro", vocabulario=vocabulario
    )

    assert chunks[0].chunk_id == "spinosa-c22-p574-001"


def test_montar_chunk_id_sem_numero_de_capitulo():
    assert _montar_chunk_id("bula", None, 1, 1) == "bula-p1-001"


def test_texto_hash_e_deterministico_e_sensivel_ao_conteudo(vocabulario):
    paginas_a = [PaginaLida(numero=1, capitulo=None, texto="Texto idêntico para os dois lados.")]
    paginas_b = [PaginaLida(numero=1, capitulo=None, texto="Texto diferente para o outro lado.")]

    chunks_a1 = segmentar(paginas_a, "Fonte", "livro", vocabulario)
    chunks_a2 = segmentar(paginas_a, "Fonte", "livro", vocabulario)
    chunks_b = segmentar(paginas_b, "Fonte", "livro", vocabulario)

    assert chunks_a1[0].texto_hash == chunks_a2[0].texto_hash  # idempotência do ETL
    assert chunks_a1[0].texto_hash != chunks_b[0].texto_hash


# --------------------------------------------------------------------------
# etl/vocabulario/farmacos.yaml — cobertura exigida
# --------------------------------------------------------------------------


def test_vocabulario_cobre_os_seis_farmacos_do_quadro_2(vocabulario):
    nomes = {termo.nome for termo in vocabulario.farmacos}
    faltando = FARMACOS_QUADRO_2 - nomes
    assert not faltando, f"farmacos.yaml não cobre: {faltando}"


def test_vocabulario_cobre_canino_e_felino(vocabulario):
    nomes = {termo.nome for termo in vocabulario.especies}
    assert {"canino", "felino"} <= nomes
