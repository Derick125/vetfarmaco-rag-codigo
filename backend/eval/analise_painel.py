"""Análise descritiva do painel clínico (CSV exportado do Google Forms).

São 6 situações (os cenários do Quadro 2), cada uma com 4 afirmações numa escala de 1 a 5:

  (a) fidelidade: a resposta está sustentada pelos trechos apresentados;
  (b) relevância do contexto: os trechos correspondem à pergunta clínica;
  (c) utilidade clínica: a resposta seria útil na rotina;
  (d) segurança percebida: seria seguro aplicar a resposta num paciente real.

O que o script dá:

  1. as notas de cada avaliador (A1, A2, ... na ordem das linhas do CSV) por situação e
     afirmação;
  2. mediana e intervalo (mín–máx) por situação e afirmação, quando há mais de um avaliador;
  3. a regra de 05/11/2026 (``docs/relatorio_metodologia.md``, «Regra de análise do painel»)
     aplicada de forma descritiva: nos 3 cenários aprovados no RAGAS (paracetamol-felino,
     ivermectina-mdr1, meloxicam-irc), mediana >= 4 nas quatro afirmações e nenhuma nota
     <= 2 em segurança (d); os 3 reprovados saem à parte, como análise secundária;
  4. o alfa de Krippendorff ordinal, só com 3 ou mais avaliadores.

Anonimato: o script lê só as 24 colunas de notas. Carimbo de data/hora, consentimento,
perfil, código pessoal e comentários nunca são lidos nem impressos. Os avaliadores recebem
códigos pela ordem das linhas. Linhas sem nenhuma nota (quem não consentiu ou não atendeu
aos critérios) são só contadas.

Os nomes das colunas seguem ``backend/data/audit/painel/criar_formulario.gs``: o título de
cada pergunta começa com o número sequencial do formulário (situação n: 5+5(n-1) a
8+5(n-1)). O script confere o número e uma palavra-chave do texto de cada coluna e para se
o formulário tiver mudado.

O CSV real é dado de pesquisa e nunca vai para o repositório (``.gitignore``). Só o arquivo
fictício ``eval/exemplo_painel_FICTICIO.csv`` é versionado.

Uso::

    python -m eval.analise_painel eval/exemplo_painel_FICTICIO.csv
    python -m eval.analise_painel caminho/fora/do/repo/respostas.csv --saida resultado.md
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path

CENARIOS = (
    "paracetamol-felino",
    "ivermectina-mdr1",
    "fenobarbital-carprofeno",
    "tramadol-felino-vs-cao-renal",
    "insulina-nph-extra-label",
    "meloxicam-irc",
)
APROVADOS = (1, 2, 6)  # aprovados no RAGAS (juiz principal), regra de 05/11/2026
REPROVADOS = (3, 4, 5)
AFIRMACOES = ("a", "b", "c", "d")
NOMES = {
    "a": "Fidelidade",
    "b": "Relevância do contexto",
    "c": "Utilidade clínica",
    "d": "Segurança percebida",
}
# Posição da pergunta dentro do bloco de 5 colunas de cada situação (a 5ª é o comentário).
DESLOCAMENTO = {"c": 0, "d": 1, "a": 2, "b": 3}
PALAVRA_CHAVE = {"c": "útil", "d": "seguro", "a": "sustentada", "b": "correspondem"}
PRIMEIRA_PERGUNTA = 5
PERGUNTAS_POR_SITUACAO = 5
MEDIANA_MINIMA = 4
NOTA_BAIXA = 2
MIN_AVALIADORES_ALFA = 3

Notas = dict[tuple[int, str], int]  # (situação 1–6, afirmação a–d) -> nota


def numero_da_coluna(situacao: int, afirmacao: str) -> int:
    return PRIMEIRA_PERGUNTA + PERGUNTAS_POR_SITUACAO * (situacao - 1) + DESLOCAMENTO[afirmacao]


def localizar_colunas(cabecalho: Sequence[str]) -> dict[tuple[int, str], str]:
    """(situação, afirmação) -> nome da coluna, conferindo número e palavra-chave."""
    por_numero: dict[int, str] = {}
    for nome in cabecalho:
        achado = re.match(r"\s*(\d+)\.\s", nome)
        if achado:
            por_numero.setdefault(int(achado.group(1)), nome)
    colunas: dict[tuple[int, str], str] = {}
    problemas = []
    for situacao in range(1, len(CENARIOS) + 1):
        for af in AFIRMACOES:
            numero = numero_da_coluna(situacao, af)
            nome = por_numero.get(numero)
            if nome is None:
                problemas.append(f"pergunta {numero} (situação {situacao}, ({af})) não encontrada")
            elif PALAVRA_CHAVE[af] not in nome:
                problemas.append(
                    f"pergunta {numero} (situação {situacao}, ({af})) não contém "
                    f"«{PALAVRA_CHAVE[af]}»: o formulário mudou?"
                )
            else:
                colunas[(situacao, af)] = nome
    if problemas:
        raise ValueError("Colunas do CSV não batem com o formulário:\n- " + "\n- ".join(problemas))
    return colunas


def _nota(texto: str | None) -> int | None:
    try:
        valor = int((texto or "").strip())
    except ValueError:
        return None
    return valor if 1 <= valor <= 5 else None


def carregar(caminho: Path) -> tuple[list[Notas], int, int]:
    """(notas por avaliador, linhas sem nenhuma nota, valores fora de 1–5 ignorados)."""
    with caminho.open(newline="", encoding="utf-8-sig") as f:
        leitor = csv.DictReader(f)
        colunas = localizar_colunas(leitor.fieldnames or [])
        avaliadores: list[Notas] = []
        sem_notas = invalidos = 0
        for linha in leitor:
            notas: Notas = {}
            for chave, coluna in colunas.items():
                bruto = (linha.get(coluna) or "").strip()
                valor = _nota(bruto)
                if valor is not None:
                    notas[chave] = valor
                elif bruto:
                    invalidos += 1
            if notas:
                avaliadores.append(notas)
            else:
                sem_notas += 1
    return avaliadores, sem_notas, invalidos


def _fmt_num(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}".replace(".", ",") if v != int(v) else str(int(v))


def _valores(avaliadores: list[Notas], situacoes: Sequence[int], af: str) -> list[int]:
    return [notas[(s, af)] for notas in avaliadores for s in situacoes if (s, af) in notas]


def tabela_notas(avaliadores: list[Notas]) -> list[str]:
    """Nota de cada avaliador por situação e afirmação (sem nenhum dado identificador)."""
    cab = ["Avaliador", "Situação"] + [f"({a}) {NOMES[a]}" for a in AFIRMACOES]
    saida = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for i, notas in enumerate(avaliadores, start=1):
        for s, nome in enumerate(CENARIOS, start=1):
            cel = [f"A{i}", f"{s}. `{nome}`"]
            cel += [str(notas[(s, a)]) if (s, a) in notas else "—" for a in AFIRMACOES]
            saida.append("| " + " | ".join(cel) + " |")
    return saida


def tabela_estatisticas(avaliadores: list[Notas]) -> list[str]:
    """Mediana e intervalo por situação e afirmação; só onde há mais de um avaliador."""
    if len(avaliadores) < 2:
        return ["Não calculado: há apenas 1 avaliador."]
    cab = ["Situação"] + [f"({a}) mediana [mín–máx]" for a in AFIRMACOES]
    saida = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for s, nome in enumerate(CENARIOS, start=1):
        cel = [f"{s}. `{nome}`"]
        for a in AFIRMACOES:
            vals = _valores(avaliadores, (s,), a)
            if len(vals) < 2:
                cel.append("—")
            else:
                cel.append(f"{_fmt_num(statistics.median(vals))} [{min(vals)}–{max(vals)}]")
        saida.append("| " + " | ".join(cel) + " |")
    return saida


def _linha_regra(rotulo: str, avaliadores: list[Notas], situacoes: Sequence[int]) -> list[str]:
    medianas = {}
    for a in AFIRMACOES:
        vals = _valores(avaliadores, situacoes, a)
        medianas[a] = statistics.median(vals) if vals else None
    seg = _valores(avaliadores, situacoes, "d")
    menor = min(seg) if seg else None
    mediana_ok = all(m is not None and m >= MEDIANA_MINIMA for m in medianas.values())
    seguranca_ok = menor is not None and menor > NOTA_BAIXA
    return [
        rotulo,
        str(len(seg)),
        *[_fmt_num(medianas[a]) for a in AFIRMACOES],
        "sim" if mediana_ok else "não",
        _fmt_num(menor),
        "sim" if seguranca_ok else "não",
        "**atende**" if mediana_ok and seguranca_ok else "não atende",
    ]


def _cabecalho_regra() -> list[str]:
    cab = (
        ["Situação", "n notas"]
        + [f"({a}) mediana" for a in AFIRMACOES]
        + ["mediana ≥ 4 nas quatro", "menor nota em (d)", "nenhuma nota ≤ 2 em (d)", "regra"]
    )
    return ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]


def tabela_regra(avaliadores: list[Notas], situacoes: Sequence[int]) -> list[str]:
    """Regra de 05/11/2026 aplicada descritivamente, cenário por cenário (sem inferência
    estatística). É a leitura principal: cada cenário é avaliado separadamente."""
    saida = _cabecalho_regra()
    for s in situacoes:
        saida.append(
            "| " + " | ".join(_linha_regra(f"{s}. `{CENARIOS[s - 1]}`", avaliadores, (s,))) + " |"
        )
    return saida


def tabela_juntos(avaliadores: list[Notas], situacoes: Sequence[int]) -> list[str]:
    """Só descrição: as notas de todos os cenários juntas. Não é o critério."""
    linha = _linha_regra("os 3 juntos", avaliadores, situacoes)
    return [*_cabecalho_regra(), "| " + " | ".join(linha) + " |"]


# --- alfa de Krippendorff ----------------------------------------------------------------


def alfa_krippendorff(unidades: Sequence[Sequence[int]], metrica: str = "ordinal") -> float | None:
    """Alfa de Krippendorff. Cada unidade é a lista de notas que ela recebeu (uma por
    avaliador que a respondeu); unidades com menos de 2 notas são ignoradas.

    ``None`` se todas as notas forem iguais (sem variação, o alfa é indefinido).
    """
    unidades = [list(u) for u in unidades if len(u) >= 2]
    categorias = sorted({v for u in unidades for v in u})
    if len(categorias) < 2:
        return None
    k = len(categorias)
    pos = {c: i for i, c in enumerate(categorias)}
    coincidencia = [[0.0] * k for _ in range(k)]
    for u in unidades:
        m = len(u)
        for i in range(m):
            for j in range(m):
                if i != j:
                    coincidencia[pos[u[i]]][pos[u[j]]] += 1 / (m - 1)
    n_c = [sum(linha) for linha in coincidencia]
    n = sum(n_c)

    def delta2(i: int, j: int) -> float:
        if metrica == "nominal":
            return 0.0 if i == j else 1.0
        if metrica == "intervalo":
            return float((categorias[i] - categorias[j]) ** 2)
        baixo, alto = min(i, j), max(i, j)
        return (sum(n_c[baixo : alto + 1]) - (n_c[i] + n_c[j]) / 2) ** 2

    observado = sum(coincidencia[i][j] * delta2(i, j) for i in range(k) for j in range(k))
    esperado = sum(n_c[i] * n_c[j] * delta2(i, j) for i in range(k) for j in range(k))
    if esperado == 0:
        return None
    return 1 - (n - 1) * observado / esperado


def _unidades(avaliadores: list[Notas], afirmacoes: Sequence[str]) -> list[list[int]]:
    return [
        [notas[(s, a)] for notas in avaliadores if (s, a) in notas]
        for s in range(1, len(CENARIOS) + 1)
        for a in afirmacoes
    ]


def secao_alfa(avaliadores: list[Notas]) -> list[str]:
    if len(avaliadores) < MIN_AVALIADORES_ALFA:
        return ["Alfa de Krippendorff ordinal: não calculado (n < 3)."]

    def fmt(v: float | None) -> str:
        return "indefinido (sem variação nas notas)" if v is None else f"{v:.3f}".replace(".", ",")

    geral = alfa_krippendorff(_unidades(avaliadores, AFIRMACOES))
    saida = [f"- Todas as afirmações (24 unidades): {fmt(geral)}"]
    for a in AFIRMACOES:
        valor = alfa_krippendorff(_unidades(avaliadores, (a,)))
        saida.append(f"- ({a}) {NOMES[a]} (6 unidades): {fmt(valor)}")
    saida.append(
        f"- Avaliadores: {len(avaliadores)}. Métrica ordinal; notas ausentes são toleradas."
    )
    return saida


def relatorio(avaliadores: list[Notas], sem_notas: int = 0, invalidos: int = 0) -> str:
    partes = [
        "# Análise descritiva do painel clínico",
        "",
        f"- Avaliadores com notas: {len(avaliadores)} (códigos A1–A{len(avaliadores)}, "
        "pela ordem das linhas do CSV)",
        f"- Linhas sem nenhuma nota (não consentiu ou não atendeu aos critérios): {sem_notas}",
        f"- Valores fora de 1–5 ignorados: {invalidos}",
        "- Afirmações: (a) fidelidade, (b) relevância do contexto, (c) utilidade clínica, "
        "(d) segurança percebida",
        "",
        "## Notas por avaliador",
        *tabela_notas(avaliadores),
        "",
        "## Mediana e intervalo por situação e afirmação",
        *tabela_estatisticas(avaliadores),
        "",
        "## Regra de 05/11/2026 (descritiva): cenários aprovados no RAGAS",
        "Leitura principal (interpretação registrada em 23/11/2026 no "
        "`relatorio_metodologia.md`): cada um dos 3 aprovados é avaliado separadamente.",
        "Desfecho principal: mediana ≥ 4 nas quatro afirmações e nenhuma nota ≤ 2 em (d). "
        "A coluna «regra» diz se o cenário atende.",
        "",
        *tabela_regra(avaliadores, APROVADOS),
        "",
        "### Descrição complementar: os 3 aprovados juntos (não é o critério)",
        "As notas dos 3 cenários reunidas; serve só para descrever, não para decidir.",
        "",
        *tabela_juntos(avaliadores, APROVADOS),
        "",
        "## Reprovados (análise secundária, fora do desfecho principal)",
        *tabela_regra(avaliadores, REPROVADOS),
        "",
        "## Concordância entre avaliadores",
        *secao_alfa(avaliadores),
        "",
    ]
    return "\n".join(partes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("csv", type=Path, help="CSV exportado do Google Forms")
    ap.add_argument("--saida", type=Path, help="grava o relatório Markdown neste arquivo")
    args = ap.parse_args(argv)
    if not args.csv.is_file():
        print(f"Arquivo não encontrado: {args.csv}", file=sys.stderr)
        return 1
    try:
        avaliadores, sem_notas, invalidos = carregar(args.csv)
    except ValueError as erro:
        print(erro, file=sys.stderr)
        return 1
    texto = relatorio(avaliadores, sem_notas, invalidos)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(texto)
    if args.saida:
        args.saida.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
