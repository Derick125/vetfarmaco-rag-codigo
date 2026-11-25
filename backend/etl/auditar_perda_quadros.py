"""Mede a PERDA REAL de conteúdo nos QUADROs do Spinosa — não a sobreposição
geométrica de bbox que `etl/auditar_quadros.py` media. Leitura pura, não
corrige nada em `etl/extract.py` nem em `data/extracted/`.

`etl/auditar_quadros.py` respondeu "o `pdfplumber` cobre a área da caixa?"
— uma pergunta de geometria. Descobrimos (QUADRO 6.6, `data/audit/quadros.md`
§3) que geometria não basta: o `pdfplumber` pode reconhecer a bbox de uma
célula e ainda assim `.extract()` devolver nada dela (comum sem borda
visível) — e como `etl/extract.py` exclui do texto corrido todo bloco que
se sobrepõe à bbox de uma tabela reconhecida, o conteúdo dessa célula some
dos DOIS lados: não vira tabela, não sobra texto corrido. Este módulo mede
isso diretamente, por comparação de conteúdo, não de área:

1. Para cada QUADRO (bbox já estimada por `etl.auditar_quadros.auditar`),
   pega TODO bloco de texto do PyMuPDF dentro da extensão — ignorando de
   propósito a exclusão por bbox de tabela — esse é o "bruto": o que
   existe na página, sem nenhum filtro.
2. Roda `etl.extract.extrair` de verdade (mesma função do pipeline real,
   uma página por vez) e junta texto corrido + tabelas serializadas — esse
   é o "saída": o que o corpus realmente recebe para aquela página.
3. Para cada bloco do bruto, verifica se ele está presente na saída —
   primeiro por substring exata (após normalizar caixa/espaço), depois,
   se isso falhar, pela fração de palavras do bloco que aparecem na saída
   (limiar 90%, absorve reformatação sem mascarar perda real). Abaixo do
   limiar = trecho perdido.
4. Roda `etl.dose.extrair_doses` em cada trecho perdido — o número que
   interessa é quantos desses trechos citam dose.

Por padrão audita todos os QUADROs encontrados (não só os que já tinham
dose detectada pela extração parcial) — um QUADRO cuja dose foi
COMPLETAMENTE perdida (nem tabela nem texto corrido) não aparecia na lista
de "53 com dose" de `etl/auditar_quadros.py`, porque aquela lista já media
dose só no que sobrevive à extração real. Isso é reportado à parte, de
forma explícita — ver seção 0 do relatório.

Saída: `data/audit/perda_quadros.md`.

Uso:
    python -m etl.auditar_perda_quadros --source "../data/Farmacologia...pdf" \\
        --mapa-capitulos data/mapa_capitulos.json --saida-dir data/audit
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
import structlog

from etl.auditar_quadros import (
    CAMINHO_MAPA_CAPITULOS_PADRAO,
    DIRETORIO_AUDITORIA_PADRAO,
    AchadoQuadro,
    auditar,
)
from etl.dose import extrair_doses
from etl.extract import extrair

logger = structlog.get_logger()

_ESPACOS = re.compile(r"\s+")
LIMIAR_PRESENCA = 0.90


def _normalizar(texto: str) -> str:
    return _ESPACOS.sub(" ", texto.lower()).strip()


@dataclass
class TrechoPerdido:
    texto: str
    doses: list[str]
    fracao_presente: float


@dataclass
class QuadroComPerda:
    achado: AchadoQuadro
    total_blocos: int
    trechos_perdidos: list[TrechoPerdido] = field(default_factory=list)

    @property
    def doses_perdidas(self) -> list[str]:
        return [dose for trecho in self.trechos_perdidos for dose in trecho.doses]


# --------------------------------------------------------------------------
# Blocos brutos (ignorando exclusão por bbox de tabela, de propósito)
# --------------------------------------------------------------------------


def _blocos_brutos_na_extensao(
    pagina: pymupdf.Page, bbox: tuple[float, float, float, float]
) -> list[str]:
    _x0, y0, _x1, y1 = bbox
    return [
        texto
        for _bx0, by0, _bx1, by1, texto, *_resto in pagina.get_text("blocks")
        if texto.strip() and by0 >= y0 - 2 and by1 <= y1 + 2
    ]


# --------------------------------------------------------------------------
# Presença de um trecho na saída real do pipeline
# --------------------------------------------------------------------------


def _fracao_presente(bloco_norm: str, saida_norm: str, contagem_saida: Counter) -> float:
    if bloco_norm and bloco_norm in saida_norm:
        return 1.0
    palavras_bloco = bloco_norm.split()
    if not palavras_bloco:
        return 1.0
    contagem_bloco = Counter(palavras_bloco)
    encontradas = sum(
        min(n, contagem_saida.get(palavra, 0)) for palavra, n in contagem_bloco.items()
    )
    return encontradas / len(palavras_bloco)


# --------------------------------------------------------------------------
# Auditoria principal
# --------------------------------------------------------------------------


def auditar_perda(caminho_pdf: Path, achados: list[AchadoQuadro]) -> list[QuadroComPerda]:
    documento = pymupdf.open(caminho_pdf)
    saida_por_pagina: dict[int, tuple[str, str]] = {}  # pagina -> (texto_norm, tabelas_norm)
    resultado: list[QuadroComPerda] = []

    for achado in achados:
        if achado.pagina not in saida_por_pagina:
            (pagina_extraida,) = extrair(caminho_pdf, achado.pagina, achado.pagina, "auditoria")
            texto_norm = _normalizar(pagina_extraida.texto)
            tabelas_norm = _normalizar(" \n ".join(pagina_extraida.tabelas))
            saida_por_pagina[achado.pagina] = (texto_norm, tabelas_norm)
        texto_norm, tabelas_norm = saida_por_pagina[achado.pagina]
        saida_norm = f"{texto_norm} \n {tabelas_norm}"
        contagem_saida = Counter(saida_norm.split())

        pagina = documento[achado.pagina - 1]
        blocos = _blocos_brutos_na_extensao(pagina, achado.bbox)

        item = QuadroComPerda(achado=achado, total_blocos=len(blocos))
        for bloco_texto in blocos:
            bloco_norm = _normalizar(bloco_texto)
            fracao = _fracao_presente(bloco_norm, saida_norm, contagem_saida)
            if fracao < LIMIAR_PRESENCA:
                item.trechos_perdidos.append(
                    TrechoPerdido(
                        texto=bloco_texto.strip(),
                        doses=extrair_doses(bloco_texto),
                        fracao_presente=fracao,
                    )
                )
        resultado.append(item)

    logger.info(
        "auditoria_perda_concluida",
        quadros_auditados=len(resultado),
        quadros_com_trecho_perdido=sum(1 for q in resultado if q.trechos_perdidos),
        quadros_com_dose_perdida=sum(1 for q in resultado if q.doses_perdidas),
        total_doses_perdidas=sum(len(q.doses_perdidas) for q in resultado),
    )
    return resultado


# --------------------------------------------------------------------------
# Relatório Markdown
# --------------------------------------------------------------------------


def _doses_celula(doses: list[str]) -> str:
    return "; ".join(" ".join(d.split()) for d in doses)


def gerar_relatorio(
    quadros: list[QuadroComPerda], quadros_com_dose_conhecida: set[tuple[int, str]]
) -> str:
    com_dose_perdida = [q for q in quadros if q.doses_perdidas]
    com_dose_perdida.sort(key=lambda q: len(q.doses_perdidas), reverse=True)

    total_doses_perdidas = sum(len(q.doses_perdidas) for q in com_dose_perdida)
    novos = [
        q
        for q in com_dose_perdida
        if (q.achado.pagina, q.achado.numero) not in quadros_com_dose_conhecida
    ]

    linhas = [
        "# Perda real de conteúdo nos QUADROs do Spinosa\n",
        "Leitura pura — não altera `etl/extract.py` nem `data/extracted/`. "
        "Comparação de CONTEÚDO (bruto do PyMuPDF vs. saída real de "
        "`etl.extract.extrair`), não de sobreposição de bbox — ver "
        "metodologia no docstring de `etl/auditar_perda_quadros.py`.\n",
        "## 0. O número que interessa\n",
        f"**{total_doses_perdidas} ocorrências de padrão de dose, em "
        f"{len(com_dose_perdida)} QUADROs, existem no PDF do Spinosa e NÃO "
        f"existem em lugar nenhum do corpus atualmente extraído** — nem em "
        f"texto corrido, nem em tabela.\n",
        f"Disso, {len(novos)} QUADRO(s) — "
        + (
            ", ".join(f"{q.achado.numero} (p.{q.achado.pagina})" for q in novos)
            if novos
            else "nenhum"
        )
        + " — têm TODA a dose perdida (nenhuma sobrevive à extração), o que "
        'significa que não apareciam na lista de "53 QUADROs com dose" do '
        "relatório anterior (`data/audit/quadros.md`), que só contava dose "
        "no que já sobrevivia à extração. Auditei todos os QUADROs do "
        "livro, não só os 53, por causa exatamente desse ponto cego.\n",
        "## 1. QUADROs com dose perdida, por gravidade\n",
        "| página | quadro | status geométrico | doses perdidas | "
        "trechos perdidos (total) | já estava nos 53? |",
        "|---|---|---|---|---|---|",
    ]
    for q in com_dose_perdida:
        a = q.achado
        ja_conhecido = (a.pagina, a.numero) in quadros_com_dose_conhecida
        conhecido = "sim" if ja_conhecido else "NÃO — só achado aqui"
        linhas.append(
            f"| {a.pagina} | {a.numero} | {a.status_captura} | "
            f"{len(q.doses_perdidas)} | {len(q.trechos_perdidos)} | {conhecido} |"
        )
    linhas.append("")

    linhas.append("## 2. Trechos perdidos, detalhado\n")
    for q in com_dose_perdida:
        a = q.achado
        linhas.append(
            f"### QUADRO {a.numero} — página {a.pagina} ({a.capitulo or '?'}) — "
            f"{len(q.doses_perdidas)} dose(s) perdida(s)\n"
        )
        for trecho in sorted(q.trechos_perdidos, key=lambda t: bool(t.doses), reverse=True):
            marca = "**[TEM DOSE]**" if trecho.doses else "(sem dose)"
            doses_txt = f" — doses: {_doses_celula(trecho.doses)}" if trecho.doses else ""
            texto_uma_linha = " ".join(trecho.texto.split())
            linhas.append(f"- {marca} (presença: {trecho.fracao_presente:.0%}){doses_txt}")
            linhas.append(f"  > {texto_uma_linha}")
        linhas.append("")

    return "\n".join(linhas)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--mapa-capitulos", type=Path, default=CAMINHO_MAPA_CAPITULOS_PADRAO)
    parser.add_argument("--saida-dir", type=Path, default=DIRETORIO_AUDITORIA_PADRAO)
    args = parser.parse_args(argv)

    mapa = json.loads(args.mapa_capitulos.read_text(encoding="utf-8"))
    achados = auditar(args.source, mapa)
    quadros_com_dose_conhecida = {(a.pagina, a.numero) for a in achados if a.doses}

    quadros = auditar_perda(args.source, achados)
    relatorio = gerar_relatorio(quadros, quadros_com_dose_conhecida)

    caminho_saida = args.saida_dir / "perda_quadros.md"
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    caminho_saida.write_text(relatorio, encoding="utf-8")
    logger.info("relatorio_perda_gravado", saida=str(caminho_saida))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
