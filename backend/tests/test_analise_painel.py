"""Testes de eval/analise_painel.py com dados inventados (nada do painel real)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from eval import analise_painel as ap

# Exemplo clássico de Krippendorff com 3 avaliadores e 15 unidades; None = sem nota.
# Valores de referência publicados: nominal 0,691 e intervalo 0,811.
EXEMPLO = [
    [None, None, None, None, None, 3, 4, 1, 2, 1, 1, 3, 3, None, 3],
    [1, None, 2, 1, 3, 3, 4, 3, None, None, None, None, None, None, None],
    [None, None, 2, 1, 3, 4, 4, None, 2, 1, 1, 3, 3, None, 4],
]


def _unidades_exemplo() -> list[list[int]]:
    return [[av[u] for av in EXEMPLO if av[u] is not None] for u in range(15)]


def test_alfa_nominal_e_intervalo_batem_com_o_exemplo_publicado():
    assert round(ap.alfa_krippendorff(_unidades_exemplo(), "nominal"), 3) == 0.691
    assert round(ap.alfa_krippendorff(_unidades_exemplo(), "intervalo"), 3) == 0.811


def test_alfa_ordinal_conferido_a_mao():
    # unidades [1,2], [2,3], [1,3]: n_1 = n_2 = n_3 = 2, n = 6;
    # delta² ordinal (1,2) = (2,3) = 4 e (1,3) = 16 -> alfa = 1 - 5 * 48 / 192 = -0,25
    assert ap.alfa_krippendorff([[1, 2], [2, 3], [1, 3]], "ordinal") == pytest.approx(-0.25)
    # no exemplo publicado o ordinal fica entre o nominal e o intervalo
    ordinal = ap.alfa_krippendorff(_unidades_exemplo(), "ordinal")
    assert 0.691 < ordinal < 0.9


def test_alfa_concordancia_perfeita_e_sem_variacao():
    perfeita = [[1, 1, 1], [3, 3, 3], [5, 5, 5], [2, 2, 2]]
    assert ap.alfa_krippendorff(perfeita) == pytest.approx(1.0)
    assert ap.alfa_krippendorff([[4, 4, 4], [4, 4, 4]]) is None


def _notas(a: int, b: int, c: int, d: int) -> ap.Notas:
    return {(s, af): v for s in range(1, 7) for af, v in zip("abcd", (a, b, c, d), strict=True)}


def test_alfa_so_com_tres_ou_mais_avaliadores():
    dois = [_notas(5, 5, 5, 5), _notas(4, 4, 4, 4)]
    assert ap.secao_alfa(dois) == ["Alfa de Krippendorff ordinal: não calculado (n < 3)."]
    tres = dois + [_notas(3, 3, 3, 3)]
    assert "não calculado" not in "\n".join(ap.secao_alfa(tres))


def test_estatisticas_so_com_mais_de_um_avaliador():
    assert ap.tabela_estatisticas([_notas(5, 5, 5, 5)]) == ["Não calculado: há apenas 1 avaliador."]
    tabela = "\n".join(ap.tabela_estatisticas([_notas(5, 4, 3, 2), _notas(4, 4, 3, 1)]))
    assert "4,5 [4–5]" in tabela and "1,5 [1–2]" in tabela


def test_regra_mediana_e_nota_baixa_em_seguranca():
    bons = [_notas(5, 5, 5, 5), _notas(4, 4, 4, 4)]
    assert "**atende**" in "\n".join(ap.tabela_regra(bons, ap.APROVADOS))
    # medianas altas, mas uma nota 2 em segurança (d) reprova a regra
    com_nota_baixa = [_notas(5, 5, 5, 5), _notas(5, 5, 5, 2)]
    assert "não atende" in "\n".join(ap.tabela_regra(com_nota_baixa, ap.APROVADOS))
    # nota 3 em segurança (sem nota <= 2) mas mediana (c) < 4 também reprova
    mediana_baixa = [_notas(5, 5, 3, 5), _notas(5, 5, 3, 5)]
    assert "não atende" in "\n".join(ap.tabela_regra(mediana_baixa, ap.APROVADOS))


def test_aprovados_e_reprovados_nao_se_misturam():
    assert set(ap.APROVADOS) == {1, 2, 6} and set(ap.REPROVADOS) == {3, 4, 5}
    texto = ap.relatorio([_notas(5, 5, 5, 5), _notas(4, 4, 4, 4)])
    aprovados, reprovados = texto.split("## Reprovados")
    assert "meloxicam-irc" in aprovados and "meloxicam-irc" not in reprovados.split("##")[0]
    assert "tramadol-felino-vs-cao-renal" in reprovados


def _cabecalho() -> list[str]:
    cab = ["Carimbo de data/hora", "Código pessoal"]
    q = 5
    for _ in range(6):
        cab += [
            f"{q}. A resposta seria útil para a tomada de decisão.",
            f"{q + 1}. Eu consideraria seguro aplicar esta resposta.",
            f"{q + 2}. A resposta está integralmente sustentada pelos trechos.",
            f"{q + 3}. Os trechos apresentados correspondem à pergunta.",
            f"{q + 4}. Comentários sobre esta situação (opcional)",
        ]
        q += 5
    return cab


def test_carregar_ignora_dados_identificadores_e_linhas_sem_notas(tmp_path: Path):
    cab = _cabecalho()
    arquivo = tmp_path / "ficticio.csv"
    with arquivo.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cab)
        completa = ["2000/01/01", "ZZ00"] + ["4", "3", "5", "4", "comentário que não deve sair"] * 6
        w.writerow(completa)
        w.writerow(["2000/01/02", "ZZ01"] + [""] * (len(cab) - 2))  # não consentiu
    avaliadores, sem_notas, invalidos = ap.carregar(arquivo)
    assert len(avaliadores) == 1 and sem_notas == 1 and invalidos == 0
    assert avaliadores[0][(1, "c")] == 4 and avaliadores[0][(1, "d")] == 3
    assert avaliadores[0][(1, "a")] == 5 and avaliadores[0][(1, "b")] == 4
    texto = ap.relatorio(avaliadores, sem_notas, invalidos)
    for proibido in ("ZZ00", "ZZ01", "2000/01", "comentário que não deve sair"):
        assert proibido not in texto


def test_formulario_diferente_para_o_script(tmp_path: Path):
    arquivo = tmp_path / "outro.csv"
    arquivo.write_text("Carimbo,5. algo qualquer\n2000/01/01,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="não batem com o formulário"):
        ap.carregar(arquivo)
