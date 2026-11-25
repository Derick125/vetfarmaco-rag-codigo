"""Análise da campanha de telemetria (OE5, docs/CRITERIOS_DE_ACEITE.md).

Junta os CSVs exportados do app (Ajustes → Telemetria das consultas → Exportar CSV),
descarta as linhas servidas do cache e calcula, por rede e por período do dia, a
mediana (P50) e o percentil 90 de:

  - ``primeiro_evento_ms``  tempo até o primeiro evento do stream;
  - ``ttft_ms``             TTFT do contrato: primeiro parágrafo validado;
  - ``total_cliente_ms``    tempo total até o ``fim``.

Também calcula a correlação do TTFT com os tokens de raciocínio (``thought_tokens``).

Acrescentado em 23/11/2026 (o que está acima não mudou), em seções ao fim do relatório:

  - P99 de cada medida, por rede e no total, só com n >= 50;
  - custo de latência da validação, a métrica oficial do OE5 (``CRITERIOS_DE_ACEITE.md``):
    tempo até o primeiro parágrafo validado menos tempo até o primeiro token, os dois do
    servidor (coluna ``custo_latencia_validacao_ms``): P50, P90 e P99 (P99 só com n >= 50).
    Informativo, fora da métrica: o tempo de rede e cliente (``ttft_ms`` menos o primeiro
    parágrafo validado no servidor);
  - custo médio e total em USD, com e sem os tokens de raciocínio, com os preços
    promocionais de 2026 (US$ 0,75 de entrada e US$ 3,75 de saída por milhão de tokens,
    ``DIVERGENCIAS.md``); ``--preco-in``/``--preco-out`` trocam os valores (depois de
    31/12/2026 os preços dobram). Os preços inferidos do CSV servem só de conferência;
  - cenário (1 a 6) e rodada (1 a 3) pela ordem fixa do ``PROTOCOLO_TELEMETRIA.md`` §1,
    ignorando a consulta de aquecimento (a primeira de cada sessão), e a mediana do TTFT
    por cenário;
  - rodada 1 contra rodadas 2 e 3 (medianas), por causa do cache implícito do Gemini;
  - contagem de consultas sem parágrafo validado e de consultas descartadas (cache, falha).

O CSV não traz o cenário nem a sessão. A sessão é inferida dos dados: consultas em ordem
de ``data``, uma nova sessão a cada lacuna maior que ``--lacuna-sessao`` minutos ou a cada
troca de ``condicao_campanha``. Dentro da sessão, a 1ª consulta é o aquecimento; das
demais contam na sequência as de ``desfecho`` ``concluida`` ou ``sem_evidencia`` (``falha``,
``incompleta`` e ``cache`` são repetidas pelo protocolo, então não ocupam posição). A
posição k (0, 1, ...) vira cenário k % 6 + 1 e rodada k // 6 + 1. Só a análise por cenário e
por rodada, que depende dessa ordem, exige sessões com exatamente 18 consultas válidas (a
menos que se passe ``--incluir-incompletas``); as demais tabelas (por rede, por período e
no total) usam todas as consultas válidas de todas as sessões. O relatório informa quantas
sessões ficaram incompletas.
Só biblioteca padrão (Python >= 3.12 por causa de ``statistics.correlation(method="ranked")``).

Uso::

    python -m eval.analise_telemetria data/telemetria/campanha/*.csv
    python -m eval.analise_telemetria ~/Downloads/telemetria_vetfarmaco*.csv --saida relatorio.md

O período vem da coluna ``data`` (UTC no CSV) convertida para o fuso local
(``--fuso``, padrão -3 = Brasília/Fortaleza): manhã 06–12h, tarde 12–18h, noite 18–06h.
A rede vem de ``condicao_campanha``; linhas ``nao_informada`` ficam fora da matriz.
"""

from __future__ import annotations

import argparse
import csv
import glob
import statistics
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import combinations, permutations
from pathlib import Path

REDES = ("wifi", "4g", "5g")
PERIODOS = ("manha", "tarde", "noite")
METRICAS = (
    ("primeiro_evento_ms", "1º evento"),
    ("ttft_ms", "TTFT (1º parágrafo validado)"),
    ("total_cliente_ms", "Total"),
)
LIMIAR_TTFT_MS = 2000.0

CENARIOS = (
    "paracetamol-felino",
    "ivermectina-mdr1",
    "fenobarbital-carprofeno",
    "tramadol-felino-vs-cao-renal",
    "insulina-nph-extra-label",
    "meloxicam-irc",
)
RODADAS = 3
CONSULTAS_POR_SESSAO = len(CENARIOS) * RODADAS
DESFECHOS_NA_SEQUENCIA = ("concluida", "sem_evidencia")
MIN_N_P99 = 50
LACUNA_SESSAO_MIN = 30
# Preços promocionais de 2026, US$ por milhão de tokens (docs/DIVERGENCIAS.md); dobram em
# 01/01/2027. O raciocínio é cobrado como saída.
PRECO_IN_M = 0.75
PRECO_OUT_M = 3.75


@dataclass(frozen=True)
class Resultado:
    """Linhas lidas e o que foi descartado, para o relatório de auditoria."""

    linhas: list[dict[str, str]]
    lidas: int
    duplicadas: int
    cache: int


def periodo_do_dia(hora: int) -> str:
    """manhã 06–12h, tarde 12–18h, noite 18–06h."""
    if 6 <= hora < 12:
        return "manha"
    if 12 <= hora < 18:
        return "tarde"
    return "noite"


def _num(valor: str | None) -> float | None:
    if valor is None or valor.strip() == "":
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def percentil(valores: list[float], p: float) -> float | None:
    """Percentil por interpolação linear (igual ao padrão do numpy). ``p`` em [0, 100]."""
    if not valores:
        return None
    ordenados = sorted(valores)
    pos = (len(ordenados) - 1) * p / 100
    baixo = int(pos)
    alto = min(baixo + 1, len(ordenados) - 1)
    return ordenados[baixo] + (ordenados[alto] - ordenados[baixo]) * (pos - baixo)


def correlacao(xs: list[float], ys: list[float]) -> tuple[float | None, float | None]:
    """(Pearson, Spearman). ``None`` com menos de 3 pares ou variância nula."""
    if len(xs) < 3:
        return None, None
    try:
        pearson = statistics.correlation(xs, ys)
        spearman = statistics.correlation(xs, ys, method="ranked")
    except statistics.StatisticsError:  # entrada constante
        return None, None
    return pearson, spearman


def carregar(caminhos: Iterable[Path]) -> Resultado:
    """Lê os CSVs, remove duplicatas por ``consulta_id`` e descarta o cache.

    O export do app é cumulativo: o mesmo registro aparece em vários arquivos.
    """
    vistos: set[str] = set()
    linhas: list[dict[str, str]] = []
    lidas = duplicadas = cache = 0
    for caminho in caminhos:
        with caminho.open(newline="", encoding="utf-8-sig") as f:
            for linha in csv.DictReader(f):
                lidas += 1
                cid = linha.get("consulta_id", "")
                if cid in vistos:
                    duplicadas += 1
                    continue
                vistos.add(cid)
                if linha.get("desfecho") == "cache":
                    cache += 1
                    continue
                linha["_arquivo"] = caminho.name
                linhas.append(linha)
    return Resultado(linhas, lidas, duplicadas, cache)


def classificar(linhas: list[dict[str, str]], fuso_h: int) -> list[dict[str, str]]:
    """Acrescenta ``_periodo`` (hora local) a cada linha."""
    fuso = timezone(timedelta(hours=fuso_h))
    for linha in linhas:
        try:
            quando = datetime.fromisoformat(linha["data"].replace("Z", "+00:00"))
            linha["_periodo"] = periodo_do_dia(quando.astimezone(fuso).hour)
        except (KeyError, ValueError):
            linha["_periodo"] = "?"
    return linhas


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:,.0f}".replace(",", ".")


def _fmt_r(v: float | None) -> str:
    return "—" if v is None else f"{v:+.2f}"


def _grupos(linhas: list[dict[str, str]]):
    """(rede, período) → linhas; período ``None`` = todos os períodos da rede."""
    for rede in REDES:
        da_rede = [x for x in linhas if x.get("condicao_campanha") == rede]
        for periodo in PERIODOS:
            yield rede, periodo, [x for x in da_rede if x["_periodo"] == periodo]
        yield rede, None, da_rede


def tabela_latencia(linhas: list[dict[str, str]]) -> list[str]:
    """Tabela Markdown: rede × período, com n, P50 e P90 das três medidas (ms)."""
    cab = ["Rede", "Período", "n"]
    for _, nome in METRICAS:
        cab += [f"{nome} P50", f"{nome} P90"]
    saida = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for rede, periodo, grupo in _grupos(linhas):
        concluidas = [x for x in grupo if x.get("desfecho") == "concluida"]
        cel = [
            rede.upper() if rede != "wifi" else "Wi-Fi",
            periodo or "**todos**",
            str(len(concluidas)),
        ]
        for col, _ in METRICAS:
            vals = [v for x in concluidas if (v := _num(x.get(col))) is not None]
            cel += [_fmt(percentil(vals, 50)), _fmt(percentil(vals, 90))]
        saida.append("| " + " | ".join(cel) + " |")
    return saida


def tabela_correlacao(linhas: list[dict[str, str]]) -> list[str]:
    """TTFT × thought_tokens, geral e por rede."""
    saida = ["| Escopo | n | Pearson r | Spearman ρ |", "|---|---|---|---|"]
    escopos = [("todas as redes", linhas)] + [
        (r, [x for x in linhas if x.get("condicao_campanha") == r]) for r in REDES
    ]
    for nome, grupo in escopos:
        pares = [
            (t, ttft)
            for x in grupo
            if x.get("desfecho") == "concluida"
            and (t := _num(x.get("thought_tokens"))) is not None
            and (ttft := _num(x.get("ttft_ms"))) is not None
        ]
        pearson, spearman = correlacao([p[0] for p in pares], [p[1] for p in pares])
        saida.append(f"| {nome} | {len(pares)} | {_fmt_r(pearson)} | {_fmt_r(spearman)} |")
    return saida


def auditoria(res: Resultado, linhas: list[dict[str, str]]) -> list[str]:
    """O que entrou e o que ficou de fora: a campanha precisa reportar isto (OE5)."""
    desfechos = Counter(x.get("desfecho", "?") for x in linhas)
    sem_rede = sum(1 for x in linhas if x.get("condicao_campanha") not in REDES)
    out = [
        f"- Linhas lidas: {res.lidas} (duplicadas removidas: {res.duplicadas})",
        f"- **Descartadas por vir do cache: {res.cache}**",
        f"- Linhas mantidas: {len(linhas)} — "
        + ", ".join(f"{k}: {v}" for k, v in sorted(desfechos.items())),
        f"- Fora da matriz (`condicao_campanha` não é Wi-Fi/4G/5G): {sem_rede}",
        "- Estatísticas de latência usam só `desfecho = concluida`; `sem_evidencia`, "
        "`falha` e `incompleta` não têm TTFT e aparecem acima, por contagem.",
    ]
    modelos = sorted({x.get("modelo_versao", "") for x in linhas} - {""})
    out.append(f"- Versões do modelo nos dados: {', '.join(modelos) or '—'}")
    custo = sum(c for x in linhas if (c := _num(x.get("custo_usd"))) is not None)
    out.append(f"- Custo somado (linhas mantidas): US$ {custo:.4f}")
    return out


def veredito_p50(linhas: list[dict[str, str]]) -> list[str]:
    """Critério OE5: P50 do TTFT < 2 000 ms em 4G e 5G."""
    out = []
    for rede in ("4g", "5g"):
        vals = [
            v
            for x in linhas
            if x.get("condicao_campanha") == rede
            and x.get("desfecho") == "concluida"
            and (v := _num(x.get("ttft_ms"))) is not None
        ]
        p50 = percentil(vals, 50)
        if p50 is None:
            out.append(f"- {rede.upper()}: sem dados")
        else:
            ok = "atende" if p50 < LIMIAR_TTFT_MS else "NÃO atende"
            out.append(
                f"- {rede.upper()}: P50 do TTFT = {_fmt(p50)} ms (n={len(vals)}) "
                f"— {ok} o limiar de 2.000 ms"
            )
    return out


def _fmt_p99(valores: list[float]) -> str:
    """P99 só com n >= MIN_N_P99; abaixo disso a estimativa não é confiável."""
    if len(valores) < MIN_N_P99:
        return f"n<{MIN_N_P99}"
    return _fmt(percentil(valores, 99))


def _escopos(linhas: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    """Todas as redes juntas e cada rede."""
    nomes = {"wifi": "Wi-Fi", "4g": "4G", "5g": "5G"}
    return [("**todas**", linhas)] + [
        (nomes[r], [x for x in linhas if x.get("condicao_campanha") == r]) for r in REDES
    ]


def _valores(linhas: list[dict[str, str]], coluna: str) -> list[float]:
    """Valores numéricos de ``coluna`` nas consultas concluídas."""
    return [
        v
        for x in linhas
        if x.get("desfecho") == "concluida" and (v := _num(x.get(coluna))) is not None
    ]


def tabela_p99(linhas: list[dict[str, str]]) -> list[str]:
    """P99 de cada medida (ms), por rede e no total; só com n >= 50."""
    cab = ["Escopo"]
    for _, nome in METRICAS:
        cab += [f"{nome} n", f"{nome} P99"]
    saida = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for nome_escopo, grupo in _escopos(linhas):
        cel = [nome_escopo]
        for col, _ in METRICAS:
            vals = _valores(grupo, col)
            cel += [str(len(vals)), _fmt_p99(vals)]
        saida.append("| " + " | ".join(cel) + " |")
    return saida


def _validacao_servidor_ms(x: dict[str, str]) -> float | None:
    """1º parágrafo validado menos 1º token, os dois do servidor.

    Usa a coluna ``custo_latencia_validacao_ms``; se vier vazia, calcula das duas colunas
    do servidor.
    """
    valor = _num(x.get("custo_latencia_validacao_ms"))
    if valor is not None:
        return valor
    paragrafo = _num(x.get("primeiro_paragrafo_validado_servidor_ms"))
    token = _num(x.get("primeiro_token_servidor_ms"))
    return None if paragrafo is None or token is None else paragrafo - token


def custo_latencia_validacao(linhas: list[dict[str, str]]) -> list[float]:
    """Métrica oficial (CRITERIOS_DE_ACEITE.md, OE5): tempo até o primeiro parágrafo
    validado menos tempo até o primeiro token, os dois do servidor, por consulta concluída."""
    return [
        v
        for x in linhas
        if x.get("desfecho") == "concluida" and (v := _validacao_servidor_ms(x)) is not None
    ]


def tempo_de_rede(linhas: list[dict[str, str]]) -> list[float]:
    """Informativo, não é a métrica oficial: TTFT do cliente menos o 1º parágrafo validado
    no servidor, ou seja, o que o TTFT acrescenta fora do servidor (rede e cliente)."""
    return [
        ttft - paragrafo
        for x in linhas
        if x.get("desfecho") == "concluida"
        and (ttft := _num(x.get("ttft_ms"))) is not None
        and (paragrafo := _num(x.get("primeiro_paragrafo_validado_servidor_ms"))) is not None
    ]


def conferencia_coluna(linhas: list[dict[str, str]]) -> str:
    """Confere se a coluna do CSV é exatamente 1º parágrafo − 1º token do servidor."""
    total = bate = 0
    for x in linhas:
        if x.get("desfecho") != "concluida":
            continue
        coluna = _num(x.get("custo_latencia_validacao_ms"))
        paragrafo = _num(x.get("primeiro_paragrafo_validado_servidor_ms"))
        token = _num(x.get("primeiro_token_servidor_ms"))
        if coluna is None or paragrafo is None or token is None:
            continue
        total += 1
        bate += abs(coluna - (paragrafo - token)) <= 0.01
    return (
        "Conferência: a coluna do CSV é igual a 1º parágrafo − 1º token do servidor "
        f"em {bate} de {total} consultas."
    )


def _tabela_percentis(linhas: list[dict[str, str]], extrair) -> list[str]:
    saida = ["| Escopo | n | P50 | P90 | P99 |", "|---|---|---|---|---|"]
    for nome_escopo, grupo in _escopos(linhas):
        vals = extrair(grupo)
        saida.append(
            f"| {nome_escopo} | {len(vals)} | {_fmt(percentil(vals, 50))} "
            f"| {_fmt(percentil(vals, 90))} | {_fmt_p99(vals)} |"
        )
    return saida


def tabela_custo_latencia(linhas: list[dict[str, str]]) -> list[str]:
    """P50, P90 e P99 (ms) da métrica oficial, por rede e no total."""
    return _tabela_percentis(linhas, custo_latencia_validacao)


def tabela_tempo_de_rede(linhas: list[dict[str, str]]) -> list[str]:
    """P50, P90 e P99 (ms) do tempo de rede e cliente (informativo)."""
    return _tabela_percentis(linhas, tempo_de_rede)


def inferir_precos(linhas: list[dict[str, str]]) -> tuple[float, float, float] | None:
    """(preço de entrada, preço de saída, resíduo máx.) em US$ por token, a partir do CSV.

    ``custo_usd = entrada * a + (saída + raciocínio) * b``: duas incógnitas, mínimos
    quadrados. ``None`` se houver menos de 2 consultas ou se elas forem proporcionais.
    """
    pts = []
    for x in linhas:
        ent, sai = _num(x.get("input_tokens")), _num(x.get("output_tokens"))
        rac, custo = _num(x.get("thought_tokens")) or 0.0, _num(x.get("custo_usd"))
        if ent is not None and sai is not None and custo is not None:
            pts.append((ent, sai + rac, custo))
    if len(pts) < 2:
        return None
    saa = sum(p[0] * p[0] for p in pts)
    sbb = sum(p[1] * p[1] for p in pts)
    sab = sum(p[0] * p[1] for p in pts)
    sac = sum(p[0] * p[2] for p in pts)
    sbc = sum(p[1] * p[2] for p in pts)
    det = saa * sbb - sab * sab
    if abs(det) < 1e-9 * saa * sbb:
        return None
    a = (sac * sbb - sbc * sab) / det
    b = (saa * sbc - sab * sac) / det
    return a, b, max(abs(a * p[0] + b * p[1] - p[2]) for p in pts)


def tabela_custo(
    linhas: list[dict[str, str]],
    preco_in_m: float = PRECO_IN_M,
    preco_out_m: float = PRECO_OUT_M,
) -> list[str]:
    """Custo médio e total (US$), com e sem os tokens de raciocínio.

    Preços em US$ por milhão de tokens (padrão: os promocionais de 2026). Os preços
    inferidos do CSV só entram como conferência.
    """
    usadas = [
        x
        for x in linhas
        if x.get("desfecho") == "concluida"
        and _num(x.get("custo_usd")) is not None
        and _num(x.get("input_tokens")) is not None
        and _num(x.get("output_tokens")) is not None
    ]
    if not usadas:
        return ["- Sem consultas concluídas com custo registrado."]
    n = len(usadas)
    registrado = sum(_num(x["custo_usd"]) or 0.0 for x in usadas)
    sem = sum(
        (
            (_num(x["input_tokens"]) or 0.0) * preco_in_m
            + (_num(x["output_tokens"]) or 0.0) * preco_out_m
        )
        / 1e6
        for x in usadas
    )
    rac = sum((_num(x.get("thought_tokens")) or 0.0) * preco_out_m / 1e6 for x in usadas)
    padrao = preco_in_m == PRECO_IN_M and preco_out_m == PRECO_OUT_M
    origem = "padrão: promocionais de 2026, `DIVERGENCIAS.md`" if padrao else "informados"
    saida = [
        f"- Consultas concluídas com custo: {n}",
        "",
        "| Custo (US$) | Total | Média por consulta |",
        "|---|---|---|",
        f"| Com raciocínio (`custo_usd` do CSV) | {registrado:.4f} | {registrado / n:.4f} |",
        f"| Sem raciocínio (entrada + saída) | {sem:.4f} | {sem / n:.4f} |",
        f"| Só raciocínio (diferença) | {rac:.4f} | {rac / n:.4f} |",
        "",
        f"- Preços usados (US$ por milhão de tokens): entrada {preco_in_m:.2f}, saída "
        f"{preco_out_m:.2f} — {origem}. O raciocínio é cobrado como saída. Os preços "
        "promocionais valem até 31/12/2026 e dobram em 01/01/2027.",
        f"- Conferência com os preços usados: sem + raciocínio = US$ {sem + rac:.4f}; "
        f"registrado no CSV = US$ {registrado:.4f}.",
    ]
    inferido = inferir_precos(usadas)
    if inferido is None:
        saida.append("- Conferência por inferência: não possível (menos de 2 consultas).")
    else:
        entrada, saida_m = inferido[0] * 1e6, inferido[1] * 1e6
        confere = (
            abs(entrada - preco_in_m) <= 0.01 * preco_in_m
            and abs(saida_m - preco_out_m) <= 0.01 * preco_out_m
        )
        saida.append(
            f"- Conferência por inferência: o CSV implica entrada {entrada:.2f} e saída "
            f"{saida_m:.2f} por milhão (resíduo máx. US$ {inferido[2]:.6f} por consulta) — "
            + ("coincide com os preços usados." if confere else "**DIFERE dos preços usados.**")
        )
    return saida


def _quando(linha: dict[str, str]) -> datetime | None:
    try:
        return datetime.fromisoformat(linha["data"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None


def montar_sessoes(
    linhas: list[dict[str, str]], lacuna_min: float = LACUNA_SESSAO_MIN
) -> list[list[dict[str, str]]]:
    """Agrupa as consultas em sessões: ordem de ``data``; nova sessão após uma lacuna
    maior que ``lacuna_min`` minutos ou ao trocar ``condicao_campanha``."""
    datadas = sorted(
        ((q, x) for x in linhas if (q := _quando(x)) is not None), key=lambda par: par[0]
    )
    sessoes: list[list[dict[str, str]]] = []
    anterior: datetime | None = None
    for quando, linha in datadas:
        nova = (
            not sessoes
            or anterior is None
            or (quando - anterior).total_seconds() / 60 > lacuna_min
            or linha.get("condicao_campanha") != sessoes[-1][-1].get("condicao_campanha")
        )
        if nova:
            sessoes.append([])
        sessoes[-1].append(linha)
        anterior = quando
    return sessoes


@dataclass(frozen=True)
class Atribuicao:
    """Resumo da identificação de cenário e rodada."""

    sessoes: int
    completas: int
    aquecimento: int
    fora_da_sequencia: int
    sem_data: int
    tamanhos: list[int]


def atribuir_cenarios(
    linhas: list[dict[str, str]], lacuna_min: float = LACUNA_SESSAO_MIN
) -> Atribuicao:
    """Marca em cada linha ``_aquecimento``, ``_cenario`` (1–6), ``_rodada`` e
    ``_sessao_completa`` (ver o docstring do módulo para as regras)."""
    sessoes = montar_sessoes(linhas, lacuna_min)
    aquecimento = fora = completas = 0
    tamanhos = []
    for sessao in sessoes:
        sessao[0]["_aquecimento"] = "1"
        aquecimento += 1
        resto = sessao[1:]
        sequencia = [x for x in resto if x.get("desfecho") in DESFECHOS_NA_SEQUENCIA]
        fora += len(resto) - len(sequencia)
        completa = len(sequencia) == CONSULTAS_POR_SESSAO
        completas += completa
        tamanhos.append(len(sequencia))
        for k, linha in enumerate(sequencia):
            linha["_cenario"] = str(k % len(CENARIOS) + 1)
            linha["_rodada"] = str(k // len(CENARIOS) + 1)
            linha["_sessao_completa"] = "1" if completa else ""
    sem_data = sum(1 for x in linhas if _quando(x) is None)
    return Atribuicao(len(sessoes), completas, aquecimento, fora, sem_data, tamanhos)


def _com_cenario(linhas: list[dict[str, str]], incluir_incompletas: bool) -> list[dict[str, str]]:
    return [
        x
        for x in linhas
        if x.get("_cenario") and (incluir_incompletas or x.get("_sessao_completa"))
    ]


def resumo_atribuicao(atr: Atribuicao, incluir_incompletas: bool) -> list[str]:
    modo = "todas as sessões" if incluir_incompletas else "só sessões completas"
    saida = [
        f"- Sessões inferidas: {atr.sessoes}; completas (18 consultas válidas após o "
        f"aquecimento): {atr.completas}; **incompletas: {atr.sessoes - atr.completas}**.",
        "- A exigência de 18 consultas vale só para esta análise, que depende da ordem; as "
        "tabelas por rede, período e total, acima, usam todas as consultas válidas de todas "
        f"as sessões. Aqui entram {modo}.",
        f"- Consultas de aquecimento ignoradas: {atr.aquecimento}.",
        f"- Consultas repetidas fora da sequência (falha ou incompleta): {atr.fora_da_sequencia}.",
        f"- Consultas válidas por sessão: {', '.join(map(str, atr.tamanhos)) or '—'} "
        f"(esperado: {CONSULTAS_POR_SESSAO}).",
    ]
    if atr.sem_data:
        saida.append(f"- Linhas sem `data` válida, fora das sessões: {atr.sem_data}.")
    return saida


def tabela_cenarios(linhas: list[dict[str, str]], incluir_incompletas: bool) -> list[str]:
    """Mediana do TTFT (ms) por cenário, na ordem fixa 1–6."""
    base = _com_cenario(linhas, incluir_incompletas)
    saida = ["| # | Cenário | n (com TTFT) | TTFT mediana |", "|---|---|---|---|"]
    for i, nome in enumerate(CENARIOS, start=1):
        vals = _valores([x for x in base if x["_cenario"] == str(i)], "ttft_ms")
        saida.append(f"| {i} | `{nome}` | {len(vals)} | {_fmt(percentil(vals, 50))} |")
    return saida


def tabela_rodadas(linhas: list[dict[str, str]], incluir_incompletas: bool) -> list[str]:
    """Mediana da rodada 1 contra a das rodadas 2 e 3 (cache implícito do Gemini)."""
    base = _com_cenario(linhas, incluir_incompletas)
    medidas = (
        ("ttft_ms", "TTFT"),
        ("primeiro_token_servidor_ms", "1º token (servidor)"),
        ("total_cliente_ms", "Total"),
    )
    cab = (
        "| Escopo | Medida | Rodada 1 n | Rodada 1 mediana | Rodadas 2–3 n "
        "| Rodadas 2–3 mediana | Δ (2–3 − 1) ms | Δ % |"
    )
    saida = [cab, "|" + "---|" * 8]
    for nome_escopo, grupo in _escopos(base):
        for col, nome in medidas:
            r1 = _valores([x for x in grupo if x["_rodada"] == "1"], col)
            r23 = _valores([x for x in grupo if x["_rodada"] in ("2", "3")], col)
            m1, m23 = percentil(r1, 50), percentil(r23, 50)
            if m1 is None or m23 is None:
                dif = pct = "—"
            else:
                dif = f"{m23 - m1:+,.0f}".replace(",", ".")
                pct = f"{(m23 - m1) / m1 * 100:+.1f}%" if m1 else "—"
            saida.append(
                f"| {nome_escopo} | {nome} | {len(r1)} | {_fmt(m1)} | {len(r23)} | {_fmt(m23)} "
                f"| {dif} | {pct} |"
            )
    return saida


def contagens(res: Resultado, linhas: list[dict[str, str]]) -> list[str]:
    """Consultas sem parágrafo validado e consultas descartadas por cache ou falha."""
    sem_par = [x for x in linhas if _num(x.get("ttft_ms")) is None]
    por_desfecho = Counter(x.get("desfecho", "?") for x in sem_par)
    falhas = sum(1 for x in linhas if x.get("desfecho") == "falha")
    incompletas = sum(1 for x in linhas if x.get("desfecho") == "incompleta")
    return [
        f"- **Sem parágrafo validado (sem TTFT, fora do P50): {len(sem_par)}** de "
        f"{len(linhas)} mantidas — "
        + (", ".join(f"{k}: {v}" for k, v in sorted(por_desfecho.items())) or "nenhuma"),
        f"- **Descartadas por cache: {res.cache}** (removidas na leitura, antes das estatísticas)",
        f"- **Descartadas por falha: {falhas}** (`desfecho = falha`); "
        f"incompletas (parcial, sem TTFT): {incompletas}",
    ]


def _divergente(x: dict[str, str]) -> bool:
    """Condição da campanha Wi-Fi, mas a coluna automática ``rede`` registrou ``mobile``."""
    return x.get("condicao_campanha") == "wifi" and x.get("rede") == "mobile"


def contagem_wifi_mobile_por_sessao(
    linhas: list[dict[str, str]], fuso_h: int, lacuna_min: float
) -> list[str]:
    """Por sessão, as linhas com ``condicao_campanha = wifi`` e ``rede = mobile``."""
    fuso = timezone(timedelta(hours=fuso_h))
    cab = ["Sessão", "Início (local)", "Período", "Condição", "Consultas", "wifi + rede=mobile"]
    saida = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    total = 0
    for i, sessao in enumerate(montar_sessoes(linhas, lacuna_min), start=1):
        inicio = _quando(sessao[0]).astimezone(fuso)
        n = sum(_divergente(x) for x in sessao)
        total += n
        saida.append(
            f"| {i} | {inicio:%d/%m %H:%M} | {periodo_do_dia(inicio.hour)} | "
            f"{sessao[0].get('condicao_campanha', '?')} | {len(sessao)} | {n} |"
        )
    saida.append(f"| **total** | | | | {len(linhas)} | **{total}** |")
    return saida


def sensibilidade_wifi_mobile(linhas: list[dict[str, str]]) -> list[str]:
    """Wi-Fi e total, com e sem as linhas ``wifi`` + ``rede = mobile`` (n, P50, P90 em ms)."""
    sem = [x for x in linhas if not _divergente(x)]
    cab = ["Escopo", "Linhas wifi+mobile", "n"]
    for _, nome in METRICAS:
        cab += [f"{nome} P50", f"{nome} P90"]
    saida = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    escopos = [
        ("Wi-Fi, análise principal (condicao_campanha)", "incluídas", linhas, "wifi"),
        ("Wi-Fi, sem as linhas wifi+mobile", "excluídas", sem, "wifi"),
        ("Total, análise principal", "incluídas", linhas, None),
        ("Total, sem as linhas wifi+mobile", "excluídas", sem, None),
    ]
    for nome, estado, base, rede in escopos:
        grupo = [
            x
            for x in base
            if x.get("condicao_campanha") in REDES
            and (rede is None or x.get("condicao_campanha") == rede)
        ]
        concluidas = [x for x in grupo if x.get("desfecho") == "concluida"]
        cel = [nome, estado, str(len(concluidas))]
        for col, _ in METRICAS:
            vals = [v for x in concluidas if (v := _num(x.get(col))) is not None]
            cel += [_fmt(percentil(vals, 50)), _fmt(percentil(vals, 90))]
        saida.append("| " + " | ".join(cel) + " |")
    return saida


def referencias_entrada(sessoes: list[list[dict[str, str]]]) -> list[float | None]:
    """Mediana de ``input_tokens`` de cada cenário, pela posição, nas sessões de 6 consultas."""
    por_cenario: list[list[float]] = [[] for _ in CENARIOS]
    for sessao in sessoes:
        if len(sessao) != len(CENARIOS):
            continue
        for k, x in enumerate(sessao):
            if (v := _num(x.get("input_tokens"))) is not None:
                por_cenario[k].append(v)
    return [statistics.median(v) if v else None for v in por_cenario]


def atribuir_por_ordem_e_tokens(
    linhas: list[dict[str, str]], lacuna_min: float = LACUNA_SESSAO_MIN
) -> tuple[list[float | None], list[str]]:
    """Marca ``_cen2`` (1–6) em cada linha pela ordem na sessão e pelos tokens de entrada.

    Critério: a referência de cada cenário é a mediana dos ``input_tokens`` por posição nas
    sessões de 6 consultas. Em cada sessão, atribui-se cada consulta a um cenário diferente
    (um por consulta), de modo que some o menor possível da distância entre os tokens da
    consulta e a referência do cenário; empate: menos trocas em relação à posição. Com mais
    de 6 consultas, fica de fora a que torna a soma menor (empate: a mais antiga). Com menos de 6, os
    cenários sem consulta ficam vazios. Devolve as referências e as sessões em que o
    resultado difere da ordem simples (posição k = cenário k + 1).
    """
    sessoes = montar_sessoes(linhas, lacuna_min)
    refs = referencias_entrada(sessoes)
    ref = [r if r is not None else 0.0 for r in refs]
    quebradas: list[str] = []
    for n, sessao in enumerate(sessoes, start=1):
        validas = [(k, x) for k, x in enumerate(sessao) if _num(x.get("input_tokens")) is not None]
        tam = min(len(validas), len(CENARIOS))
        melhor = None
        for sub in combinations(range(len(validas)), tam):
            for perm in permutations(range(len(CENARIOS)), tam):
                custo = sum(
                    abs(_num(validas[i][1]["input_tokens"]) - ref[c])
                    for i, c in zip(sub, perm, strict=True)
                )
                trocas = sum(validas[i][0] != c for i, c in zip(sub, perm, strict=True))
                chave = (round(custo, 6), trocas, sub)
                if melhor is None or chave < melhor[0]:
                    melhor = (chave, sub, perm)
        if melhor is None:
            continue
        _, sub, perm = melhor
        for i, c in zip(sub, perm, strict=True):
            validas[i][1]["_cen2"] = str(c + 1)
        if any(validas[i][0] != c for i, c in zip(sub, perm, strict=True)) or len(sessao) != len(
            CENARIOS
        ):
            quebradas.append(f"sessão {n} ({len(sessao)} consultas)")
    return refs, quebradas


def tabela_cenarios_por_tokens(linhas: list[dict[str, str]], lacuna_min: float) -> list[str]:
    """Mediana do TTFT e dos tokens de raciocínio por cenário (identificação por ordem e tokens)."""
    refs, quebradas = atribuir_por_ordem_e_tokens(linhas, lacuna_min)
    cab = [
        "#",
        "Cenário",
        "Entrada de referência (tokens)",
        "n",
        "TTFT mediana (ms)",
        "Raciocínio mediana (tokens)",
    ]
    saida = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for k, nome in enumerate(CENARIOS):
        grupo = [
            x for x in linhas if x.get("_cen2") == str(k + 1) and x.get("desfecho") == "concluida"
        ]
        ttft = [v for x in grupo if (v := _num(x.get("ttft_ms"))) is not None]
        rac = [v for x in grupo if (v := _num(x.get("thought_tokens"))) is not None]
        med = lambda v: _fmt(statistics.median(v)) if v else "—"  # noqa: E731
        saida.append(
            f"| {k + 1} | `{nome}` | {_fmt(refs[k])} | {len(grupo)} | {med(ttft)} | {med(rac)} |"
        )
    saida += [
        "",
        "Sessões em que a ordem simples não bastou (ordem trocada ou número de consultas "
        "diferente de 6): " + (", ".join(quebradas) or "nenhuma") + ".",
    ]
    return saida


def relatorio(
    res: Resultado,
    linhas: list[dict[str, str]],
    *,
    lacuna_min: float = LACUNA_SESSAO_MIN,
    fuso_h: int = -3,
    incluir_incompletas: bool = False,
    preco_in_m: float | None = None,
    preco_out_m: float | None = None,
) -> str:
    preco_in_m = PRECO_IN_M if preco_in_m is None else preco_in_m
    preco_out_m = PRECO_OUT_M if preco_out_m is None else preco_out_m
    atr = atribuir_cenarios(linhas, lacuna_min)
    partes = [
        "# Análise da campanha de telemetria",
        "",
        "## Auditoria dos dados",
        *auditoria(res, linhas),
        "",
        "## Latência por rede e período (ms)",
        *tabela_latencia(linhas),
        "",
        "## Critério OE5 (TTFT < 2.000 ms em 4G/5G)",
        *veredito_p50(linhas),
        "",
        "## Correlação TTFT × tokens de raciocínio",
        *tabela_correlacao(linhas),
        "",
        f"## P99 de cada medida (ms; só com n ≥ {MIN_N_P99})",
        *tabela_p99(linhas),
        "",
        "## Custo de latência da validação (ms) — métrica oficial (OE5)",
        "Tempo até o primeiro parágrafo validado menos tempo até o primeiro token, os dois "
        "medidos no servidor, por consulta concluída (coluna `custo_latencia_validacao_ms`; "
        "`CRITERIOS_DE_ACEITE.md`, OE5). Não inclui a rede.",
        "",
        *tabela_custo_latencia(linhas),
        "",
        conferencia_coluna(linhas),
        "",
        "### Tempo de rede e cliente (informativo, não é a métrica oficial) (ms)",
        "TTFT do cliente menos o primeiro parágrafo validado no servidor: o que o TTFT "
        "acrescenta fora do servidor. Por consulta, as duas medidas somam o TTFT do cliente "
        "menos o primeiro token do servidor.",
        "",
        *tabela_tempo_de_rede(linhas),
        "",
        "## Custo em USD, com e sem tokens de raciocínio",
        *tabela_custo(linhas, preco_in_m, preco_out_m),
        "",
        "## Cenário e rodada (ordem fixa 1–6, sem o aquecimento)",
        *resumo_atribuicao(atr, incluir_incompletas),
        "",
        "### Mediana do TTFT por cenário (ms)",
        *tabela_cenarios(linhas, incluir_incompletas),
        "",
        "## Cenário por ordem e tokens de entrada (sessões de 1 rodada)",
        "Critério: a referência de cada cenário é a mediana dos `input_tokens` por posição nas "
        "sessões de 6 consultas; em cada sessão, cada consulta recebe um cenário diferente, "
        "escolhido para somar a menor distância entre os tokens de entrada da consulta e a "
        "referência (empate: menos trocas em relação à ordem). Com 7 consultas, sai a que "
        "torna a soma menor (empate: a mais antiga). Todas as redes juntas; só `concluida`.",
        "",
        *tabela_cenarios_por_tokens(linhas, lacuna_min),
        "",
        "## Rodada 1 × rodadas 2–3 (cache implícito do Gemini; medianas em ms)",
        *tabela_rodadas(linhas, incluir_incompletas),
        "",
        "## Consultas sem parágrafo validado e descartadas",
        *contagens(res, linhas),
        "",
        "## Coluna `rede` × `condicao_campanha`: linhas wifi com rede = mobile, por sessão",
        "A análise principal usa `condicao_campanha` (`PROTOCOLO_TELEMETRIA.md` §4); a "
        "coluna automática `rede` entra só aqui, como conferência.",
        "",
        *contagem_wifi_mobile_por_sessao(linhas, fuso_h, lacuna_min),
        "",
        "## Sensibilidade: Wi-Fi e total sem as linhas wifi + rede = mobile",
        *sensibilidade_wifi_mobile(linhas),
        "",
    ]
    return "\n".join(partes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("csvs", nargs="+", help="CSVs (aceita curingas, expandidos aqui no Windows)")
    ap.add_argument("--fuso", type=int, default=-3, help="deslocamento UTC em horas (padrão -3)")
    ap.add_argument("--saida", type=Path, help="grava o relatório Markdown neste arquivo")
    ap.add_argument(
        "--lacuna-sessao",
        type=float,
        default=LACUNA_SESSAO_MIN,
        help=f"minutos de intervalo que separam duas sessões (padrão {LACUNA_SESSAO_MIN})",
    )
    ap.add_argument(
        "--incluir-incompletas",
        action="store_true",
        help="usa também as sessões que não têm exatamente 18 consultas válidas",
    )
    ap.add_argument(
        "--preco-in",
        type=float,
        help=f"US$ por milhão de tokens de entrada (padrão {PRECO_IN_M}, promocional de 2026)",
    )
    ap.add_argument(
        "--preco-out",
        type=float,
        help=f"US$ por milhão de tokens de saída (padrão {PRECO_OUT_M}, promocional de 2026)",
    )
    args = ap.parse_args(argv)

    caminhos = sorted({Path(p) for padrao in args.csvs for p in (glob.glob(padrao) or [padrao])})
    ausentes = [p for p in caminhos if not p.is_file()]
    if ausentes:
        print(f"Arquivo não encontrado: {', '.join(map(str, ausentes))}", file=sys.stderr)
        return 1

    res = carregar(caminhos)
    linhas = classificar(res.linhas, args.fuso)
    texto = relatorio(
        res,
        linhas,
        lacuna_min=args.lacuna_sessao,
        fuso_h=args.fuso,
        incluir_incompletas=args.incluir_incompletas,
        preco_in_m=args.preco_in,
        preco_out_m=args.preco_out,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(texto)
    if args.saida:
        args.saida.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
