"""Testes de etl/extract.py — rejeição de tabela por perda de conteúdo.

Achado real na auditoria do Spinosa (`etl/auditar_perda_quadros.py`): o
`pdfplumber` pode reconhecer a bbox de uma tabela sem `.extract()`
conseguir puxar o texto de todas as células — e como o texto corrido
exclui todo bloco que se sobrepõe a uma tabela "capturada", esse conteúdo
sumia dos dois lados. `_tabela_perde_conteudo` é a barreira contra isso.
"""

from collections import Counter

from etl.extract import (
    LIMIAR_PRESENCA_TABELA,
    _Bloco,
    _fracao_presente,
    _normalizar_para_comparacao,
    _tabela_perde_conteudo,
)


def _bloco(texto: str, x0=20.0, y0=100.0, x1=580.0, y1=110.0) -> _Bloco:
    return _Bloco(x0=x0, y0=y0, x1=x1, y1=y1, texto=texto)


def test_fracao_presente_substring_exata():
    assert _fracao_presente("5 mg/kg", "dose de 5 mg/kg em cães", Counter()) == 1.0


def test_fracao_presente_todas_as_palavras_faltando():
    alvo = "cão gato"
    fracao = _fracao_presente("betanecol 5 mg/kg", alvo, Counter(alvo.split()))
    assert fracao == 0.0


def test_fracao_presente_parcial():
    alvo = "betanecol cão"
    fracao = _fracao_presente("betanecol 5 mg/kg", alvo, Counter(alvo.split()))
    assert fracao == 1 / 3  # só "betanecol" das 3 palavras do bloco


def test_tabela_aceita_quando_serializacao_cobre_tudo():
    blocos = [_bloco("Betanecol"), _bloco("Cão"), _bloco("5,0 a 15 mg/kg, VO, a cada 8 h")]
    markdown = (
        "| Grupo | Espécie | Posologia |\n"
        "| --- | --- | --- |\n"
        "| Betanecol | Cão | 5,0 a 15 mg/kg, VO, a cada 8 h |"
    )
    bbox = (0.0, 90.0, 600.0, 120.0)

    assert _tabela_perde_conteudo(bbox, markdown, blocos) is None


def test_tabela_rejeitada_quando_celula_nao_foi_extraida():
    # A dose do Betanecol existe no bruto do PyMuPDF, mas a serialização só
    # capturou o rótulo de espécie — exatamente o padrão achado no QUADRO 6.6.
    blocos = [_bloco("Betanecol"), _bloco("Cão"), _bloco("5,0 a 15 mg/kg, VO, a cada 8 h")]
    markdown = "| Espécie |\n| --- |\n| Cão |"
    bbox = (0.0, 90.0, 600.0, 120.0)

    trecho_ausente = _tabela_perde_conteudo(bbox, markdown, blocos)

    # Devolve o PRIMEIRO bloco sem cobertura suficiente (ordem de entrada)
    # — aqui, "Betanecol", já que nem ele nem a dose estão na serialização.
    assert trecho_ausente == "Betanecol"


def test_tabela_ignora_bloco_fora_da_bbox():
    # Um parágrafo qualquer fora da área da tabela não deve derrubar a
    # tabela, mesmo que seu texto não apareça na serialização.
    dentro = _bloco("Betanecol Cão 5,0 a 15 mg/kg", y0=100.0, y1=110.0)
    fora = _bloco("Parágrafo qualquer sem relação com a tabela.", y0=500.0, y1=510.0)
    markdown = "| Betanecol | Cão | 5,0 a 15 mg/kg |"
    bbox = (0.0, 90.0, 600.0, 120.0)

    assert _tabela_perde_conteudo(bbox, markdown, [dentro, fora]) is None


def test_normalizacao_hifen_leve_igual_ao_hifen_da_serializacao():
    # `\xad` (hífen "leve" de quebra de linha) vira "-" na limpeza de
    # célula de tabela (`_extrair_tabelas`) — sem a mesma troca aqui, uma
    # palavra hifenizada no bloco bruto nunca bateria contra a mesma
    # palavra já normalizada do lado da tabela (falso positivo de perda).
    bruto = "hiper\xadtireoidismo"
    tabela = "hiper-tireoidismo"
    assert _normalizar_para_comparacao(bruto) == _normalizar_para_comparacao(tabela)


def test_tabela_nao_rejeitada_por_hifen_leve_no_bloco_bruto():
    blocos = [_bloco("Hiper\xadtireoidismo")]
    markdown = "| Diagnóstico |\n| --- |\n| Hiper-tireoidismo |"
    bbox = (0.0, 90.0, 600.0, 120.0)

    assert _tabela_perde_conteudo(bbox, markdown, blocos) is None


def test_limiar_presenca_tabela_e_alto():
    # Documenta a intenção: perto de 1.0, não um limiar frouxo — uma
    # tabela só passa se cobrir quase tudo.
    assert LIMIAR_PRESENCA_TABELA >= 0.85
