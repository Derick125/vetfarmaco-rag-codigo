"""Testes das seções acrescentadas a eval/analise_telemetria.py (dados sintéticos)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eval import analise_telemetria as at

INICIO = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


def _linha(i: int, minutos: float, **extra: str) -> dict[str, str]:
    base = {
        "consulta_id": f"c{i}",
        "data": (INICIO + timedelta(minutes=minutos)).isoformat().replace("+00:00", "Z"),
        "condicao_campanha": "4g",
        "desfecho": "concluida",
        "ttft_ms": "1000",
        "primeiro_token_servidor_ms": "900",
        "primeiro_paragrafo_validado_servidor_ms": "950",
        "custo_latencia_validacao_ms": "50",
        "total_cliente_ms": "3000",
        "input_tokens": "1000",
        "output_tokens": "100",
        "thought_tokens": "400",
        "custo_usd": "0.00375",
    }
    base.update(extra)
    return base


def _sessao(n_validas: int = 18, inicio_min: float = 0, ttft=lambda k: 1000) -> list[dict]:
    """Aquecimento + n_validas consultas, uma por minuto."""
    linhas = [_linha(0, inicio_min, ttft_ms="9999")]
    for k in range(n_validas):
        linhas.append(_linha(k + 1, inicio_min + k + 1, ttft_ms=str(ttft(k))))
    return linhas


def test_p99_so_com_n_minimo():
    assert at._fmt_p99([1.0] * 49) == "n<50"
    assert at._fmt_p99([float(v) for v in range(1, 101)]) == at._fmt(99.01)


def test_custo_latencia_da_validacao_e_a_diferenca_medida_no_servidor():
    linhas = [
        _linha(1, 0, custo_latencia_validacao_ms="982"),
        # coluna vazia: calcula 1º parágrafo − 1º token do servidor
        _linha(
            2,
            1,
            custo_latencia_validacao_ms="",
            primeiro_paragrafo_validado_servidor_ms="2000",
            primeiro_token_servidor_ms="1200",
        ),
        _linha(3, 2, desfecho="sem_evidencia", ttft_ms="", custo_latencia_validacao_ms=""),
        _linha(4, 3, custo_latencia_validacao_ms="", primeiro_paragrafo_validado_servidor_ms=""),
    ]
    assert at.custo_latencia_validacao(linhas) == [982.0, 800.0]


def test_tempo_de_rede_e_ttft_menos_primeiro_paragrafo_do_servidor():
    linhas = [
        _linha(1, 0, ttft_ms="1100", primeiro_paragrafo_validado_servidor_ms="1000"),
        _linha(2, 1, ttft_ms="2050", primeiro_paragrafo_validado_servidor_ms="2000"),
        _linha(3, 2, desfecho="falha", ttft_ms=""),
    ]
    assert at.tempo_de_rede(linhas) == [100.0, 50.0]
    texto = at.conferencia_coluna([_linha(1, 0), _linha(2, 1, custo_latencia_validacao_ms="70")])
    assert "em 1 de 2 consultas" in texto


def test_precos_inferidos_do_csv_e_custo_sem_raciocinio():
    # entrada US$ 0,75/M; saída (e raciocínio) US$ 3,75/M
    def custo(ent, sai, rac):
        return str((ent * 0.75 + (sai + rac) * 3.75) / 1e6)

    linhas = [
        _linha(1, 0, input_tokens="4905", output_tokens="566", thought_tokens="2261",
               custo_usd=custo(4905, 566, 2261)),
        _linha(2, 1, input_tokens="3258", output_tokens="876", thought_tokens="4923",
               custo_usd=custo(3258, 876, 4923)),
    ]  # fmt: skip
    a, b, residuo = at.inferir_precos(linhas)
    assert round(a * 1e6, 4) == 0.75 and round(b * 1e6, 4) == 3.75 and residuo < 1e-9
    texto = "\n".join(at.tabela_custo(linhas))  # preços padrão: 0,75 e 3,75
    sem = (4905 * 0.75 + 566 * 3.75 + 3258 * 0.75 + 876 * 3.75) / 1e6
    assert f"| Sem raciocínio (entrada + saída) | {sem:.4f} " in texto
    assert "promocionais de 2026" in texto
    assert "coincide com os preços usados" in texto  # inferência só como conferência


def test_inferencia_acusa_preco_diferente_do_padrao():
    linhas = [
        _linha(1, 0, input_tokens="1000", output_tokens="100", thought_tokens="0",
               custo_usd="0.002"),
        _linha(2, 1, input_tokens="2000", output_tokens="300", thought_tokens="100",
               custo_usd="0.0071"),
    ]  # fmt: skip
    assert "DIFERE dos preços usados" in "\n".join(at.tabela_custo(linhas))


def test_precos_informados_prevalecem():
    texto = "\n".join(at.tabela_custo([_linha(1, 0)], 1.0, 2.0))
    assert "informados" in texto
    # sem raciocínio: (1000*1,0 + 100*2,0)/1e6 = 0,0012
    assert "| Sem raciocínio (entrada + saída) | 0.0012 " in texto


def test_cenario_e_rodada_pela_ordem_ignorando_aquecimento():
    linhas = _sessao()
    atr = at.atribuir_cenarios(linhas)
    assert atr.sessoes == 1 and atr.completas == 1 and atr.aquecimento == 1
    assert linhas[0].get("_cenario") is None  # aquecimento
    assert (linhas[1]["_cenario"], linhas[1]["_rodada"]) == ("1", "1")
    assert (linhas[6]["_cenario"], linhas[6]["_rodada"]) == ("6", "1")
    assert (linhas[7]["_cenario"], linhas[7]["_rodada"]) == ("1", "2")
    assert (linhas[18]["_cenario"], linhas[18]["_rodada"]) == ("6", "3")


def test_falha_repetida_nao_ocupa_posicao():
    linhas = _sessao()
    # uma falha entre a 2ª e a 3ª consultas válidas, repetida logo em seguida
    falha = _linha(99, 2.5, desfecho="falha", ttft_ms="")
    linhas.insert(3, falha)
    at.atribuir_cenarios(linhas)
    assert falha.get("_cenario") is None
    assert linhas[4]["_cenario"] == "3"


def test_sessao_incompleta_fica_fora_por_padrao():
    linhas = _sessao(n_validas=10)
    atr = at.atribuir_cenarios(linhas)
    assert atr.completas == 0
    assert "**incompletas: 1**" in "\n".join(at.resumo_atribuicao(atr, False))
    assert at._com_cenario(linhas, incluir_incompletas=False) == []
    assert len(at._com_cenario(linhas, incluir_incompletas=True)) == 10


def test_lacuna_e_troca_de_rede_abrem_nova_sessao():
    a = _sessao(inicio_min=0)
    b = _sessao(inicio_min=120)  # lacuna de 1 h
    c = [dict(x, condicao_campanha="5g") for x in _sessao(inicio_min=140)]
    for i, x in enumerate(a + b + c):
        x["consulta_id"] = f"s{i}"
    assert len(at.montar_sessoes(a + b + c)) == 3


def test_mediana_por_cenario_e_rodada_1_contra_2_e_3():
    # rodada 1 lenta (3000 ms), rodadas 2 e 3 rápidas (1000 ms)
    linhas = _sessao(ttft=lambda k: 3000 if k < 6 else 1000)
    at.atribuir_cenarios(linhas)
    por_cenario = "\n".join(at.tabela_cenarios(linhas, incluir_incompletas=False))
    assert "| 1 | `paracetamol-felino` | 3 | 1.000 |" in por_cenario
    rodadas = "\n".join(at.tabela_rodadas(linhas, incluir_incompletas=False))
    assert "| **todas** | TTFT | 6 | 3.000 | 12 | 1.000 | -2.000 | -66.7% |" in rodadas


def test_contagens_de_sem_paragrafo_e_descartadas():
    res = at.Resultado([], lidas=10, duplicadas=0, cache=2)
    linhas = [
        _linha(1, 0),
        _linha(2, 1, desfecho="sem_evidencia", ttft_ms=""),
        _linha(3, 2, desfecho="falha", ttft_ms=""),
        _linha(4, 3, desfecho="incompleta", ttft_ms=""),
    ]
    texto = "\n".join(at.contagens(res, linhas))
    assert "Sem parágrafo validado (sem TTFT, fora do P50): 3** de 4" in texto
    assert "falha: 1, incompleta: 1, sem_evidencia: 1" in texto
    assert "Descartadas por cache: 2" in texto
    assert "Descartadas por falha: 1" in texto


def test_relatorio_completo_roda_sem_dados_de_campanha():
    res = at.Resultado([], lidas=0, duplicadas=0, cache=0)
    texto = at.relatorio(res, at.classificar([], -3))
    assert "## P99 de cada medida" in texto and "## Consultas sem parágrafo validado" in texto
