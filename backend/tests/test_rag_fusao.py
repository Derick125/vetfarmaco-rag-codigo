"""Testes de app/rag/fusao.py — RRF (docs/RAG_SPEC.md §3.3).

`test_rrf_bate_com_calculo_manual` documenta a conta esperada no próprio
teste, para conferência manual:

    semântica = ["a", "b", "c", "d"]   (a=1º, b=2º, c=3º, d=4º)
    lexical   = ["b", "d", "a"]        (b=1º, d=2º, a=3º)
    k = 60

    a = 1/(60+1) + 1/(60+3) = 1/61 + 1/63 ≈ 0,03226646
    b = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 ≈ 0,03252247
    c = 1/(60+3)            = 1/63        ≈ 0,01587302
    d = 1/(60+4) + 1/(60+2) = 1/64 + 1/62 ≈ 0,03175403

    ordem final (maior → menor escore): b, a, d, c
"""

import pytest

from app.rag.fusao import K_PADRAO, fundir, rrf


def test_k_padrao_do_rag_spec_e_60():
    assert K_PADRAO == 60


def test_rrf_bate_com_calculo_manual():
    semantica = ["a", "b", "c", "d"]
    lexical = ["b", "d", "a"]

    resultado = rrf([semantica, lexical], k=60)

    esperado = {
        "a": 1 / 61 + 1 / 63,
        "b": 1 / 62 + 1 / 61,
        "c": 1 / 63,
        "d": 1 / 64 + 1 / 62,
    }
    assert resultado.keys() == esperado.keys()
    for chunk_id, escore in esperado.items():
        assert resultado[chunk_id] == pytest.approx(escore)

    assert list(resultado.keys()) == ["b", "a", "d", "c"]


def test_rrf_chunk_presente_em_um_so_ranking_ainda_entra_no_resultado():
    resultado = rrf([["x", "y"], ["z"]], k=60)
    assert set(resultado) == {"x", "y", "z"}
    assert resultado["z"] == pytest.approx(1 / 61)


def test_rrf_lista_vazia_de_rankings_devolve_vazio():
    assert rrf([], k=60) == {}


def test_rrf_k_diferente_de_60_muda_o_escore():
    resultado_k60 = rrf([["a", "b"]], k=60)
    resultado_k1 = rrf([["a", "b"]], k=1)
    assert resultado_k60["a"] != resultado_k1["a"]
    assert resultado_k1["a"] == pytest.approx(1 / 2)  # 1/(1+1)


def test_fundir_usa_so_a_posicao_ignora_o_escore_original_de_cada_estrategia():
    # "a" e "b" trocam de posição entre as duas listas — escalas de escore
    # bem diferentes (cosseno vs. BM25) não deveriam importar para o RRF.
    semantica = [("a", 0.99), ("b", 0.10)]
    lexical = [("b", 500.0), ("a", 1.0)]

    fundido = dict(fundir(semantica, lexical, k=60))

    assert fundido["a"] == pytest.approx(fundido["b"])


def test_fundir_respeita_qtd():
    semantica = [(f"c{i}", 1.0) for i in range(20)]
    fundido = fundir(semantica, qtd=10)
    assert len(fundido) == 10


def test_fundir_default_qtd_e_10():
    semantica = [(f"c{i}", 1.0) for i in range(20)]
    fundido = fundir(semantica)
    assert len(fundido) == 10
