"""Auditoria de todas as caixas "QUADRO N.M" do corpus do Spinosa — leitura
pura, não corrige nada em `etl/extract.py` nem em `data/extracted/`.

Motivação: `etl/extract.py` exclui do texto corrido só o que
`pdfplumber.find_tables()` reconhece como tabela (bbox por bbox); um QUADRO
que o `pdfplumber` captura só parcialmente (ex. apenas a linha de
cabeçalho, como confirmado nas páginas 411 e 785 durante a checagem de
extração do Spinosa) deixa o resto do conteúdo fluir como texto corrido
comum, na ordem natural dos blocos do PyMuPDF — o que FUNCIONA na maioria
dos casos observados, mas nunca foi conferido em todas as ~300 ocorrências
do livro. Isto audita as ocorrências reais, prioriza as que citam dose (o
tipo de conteúdo mais sensível a uma leitura fora de ordem) e, para as
capturadas só parcialmente E com dose, prepara página renderizada + texto
extraído lado a lado para conferência visual humana.

Para cada "QUADRO N.M" (identificado pela linha em MAIÚSCULA que começa o
título — distingue do texto corrido, que referencia quadros em
capitalização normal, "Quadro N.M", ao longo do livro):

1. Estima a extensão vertical da caixa a partir dos objetos de desenho
   vetorial do PyMuPDF (`Page.get_drawings()`) — sombreado do cabeçalho,
   linhas de grade — que este PDF usa para desenhar toda caixa de QUADRO
   (confirmado: uma página sem QUADRO tem 0-1 desenhos; uma página com
   QUADRO tem dezenas a centenas). É uma ESTIMATIVA, não a extração real
   do `pdfplumber` — despois clampada à altura da página.
2. Classifica a captura do `pdfplumber.find_tables()` para essa página
   contra essa extensão estimada: "cheia" (tabela cobre quase toda a
   extensão), "parcial" (tabela cobre só uma fração — tipicamente só o
   cabeçalho) ou "nenhuma" (nenhuma tabela sobrepõe a extensão).
3. Roda `etl.dose.extrair_doses` sobre todo texto dentro da extensão
   estimada (blocos de texto corrido + células de tabela, juntos — para
   detecção de presença, não para reconstrução fiel).

Saída: `data/audit/quadros.md` (relatório) + `data/audit/quadros/*.png`
(recortes de página renderizada, só para as ocorrências "parcial" com
dose — o subconjunto que mais precisa de conferência humana).

Uso:
    python -m etl.auditar_quadros --source "../data/Farmacologia...pdf" \\
        --mapa-capitulos data/mapa_capitulos.json --saida-dir data/audit
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import pymupdf
import structlog

from etl.dose import extrair_doses

logger = structlog.get_logger()

CAMINHO_MAPA_CAPITULOS_PADRAO = (
    Path(__file__).resolve().parent.parent / "data" / "mapa_capitulos.json"
)
DIRETORIO_AUDITORIA_PADRAO = Path(__file__).resolve().parent.parent / "data" / "audit"

_PADRAO_TITULO_QUADRO = re.compile(r"^QUADRO\s+(\d+)\.(\d+)\b")
MARGEM_ESQUERDA_PT = 18.0
MARGEM_DIREITA_PT = 594.0


@dataclass
class TituloQuadro:
    pagina: int
    numero: str  # "20.1"
    titulo: str  # linha completa, ex. "QUADRO 20.1" seguido do título do quadro
    y0: float
    y1: float


@dataclass
class AchadoQuadro:
    pagina: int
    capitulo: str | None
    numero: str
    titulo: str
    bbox: tuple[float, float, float, float]
    status_captura: str  # "cheia" | "parcial" | "nenhuma"
    fracao_capturada: float
    continua_na_proxima_pagina: bool
    texto_bruto: str
    doses: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Localização dos títulos
# --------------------------------------------------------------------------


def _localizar_titulos(pagina: pymupdf.Page, numero_pagina: int) -> list[TituloQuadro]:
    titulos = []
    for _x0, y0, _x1, y1, texto, *_resto in pagina.get_text("blocks"):
        primeira_linha = texto.strip().split("\n")[0].strip()
        casamento = _PADRAO_TITULO_QUADRO.match(primeira_linha)
        if casamento:
            titulos.append(
                TituloQuadro(
                    pagina=numero_pagina,
                    numero=f"{casamento.group(1)}.{casamento.group(2)}",
                    titulo=" ".join(texto.split()),
                    y0=y0,
                    y1=y1,
                )
            )
    return titulos


# --------------------------------------------------------------------------
# Estimativa de extensão vertical via desenho vetorial
# --------------------------------------------------------------------------


def _estimar_fundo(pagina: pymupdf.Page, y0_titulo: float, teto_y: float) -> tuple[float, bool]:
    """Estima o y1 (fundo) da caixa a partir dos objetos de desenho vetorial
    cujo y0 cai dentro de `[y0_titulo - 5, teto_y]` — `teto_y` é o y0 do
    próximo título de QUADRO na mesma página, ou a altura da página.

    Devolve `(y1_estimado_clampado, continua_na_proxima_pagina)` — o
    segundo é `True` quando o maior y1 bruto ultrapassa a altura da
    página, sinal de que a caixa (ou pelo menos as linhas de grade
    desenhadas para ela) se estende além do que está visível nesta
    página.
    """
    altura_pagina = pagina.rect.height
    candidatos = [
        d["rect"].y1
        for d in pagina.get_drawings()
        if y0_titulo - 5 <= d["rect"].y0 < teto_y and d["rect"].y1 > y0_titulo
    ]
    if not candidatos:
        return min(y0_titulo + 100, altura_pagina), False
    bruto = max(candidatos)
    continua = bruto > altura_pagina + 1
    return min(bruto, altura_pagina), continua


# --------------------------------------------------------------------------
# Classificação da captura pelo pdfplumber
# --------------------------------------------------------------------------


def _classificar_captura(
    bbox: tuple[float, float, float, float], tabelas_da_pagina: list
) -> tuple[str, float]:
    _x0, y0, _x1, y1 = bbox
    altura_quadro = y1 - y0
    if altura_quadro <= 0:
        return "nenhuma", 0.0

    sobrepostas = [t for t in tabelas_da_pagina if not (t.bbox[3] < y0 or t.bbox[1] > y1)]
    if not sobrepostas:
        return "nenhuma", 0.0

    # Fração coberta = união dos intervalos verticais das tabelas
    # sobrepostas, dentro dos limites do quadro — não soma bruta (duas
    # tabelas adjacentes não devem contar dobrado).
    intervalos = sorted((max(t.bbox[1], y0), min(t.bbox[3], y1)) for t in sobrepostas)
    coberto = 0.0
    fim_anterior = y0
    for inicio, fim in intervalos:
        inicio = max(inicio, fim_anterior)
        if fim > inicio:
            coberto += fim - inicio
            fim_anterior = fim
    fracao = coberto / altura_quadro

    if fracao >= 0.85:
        return "cheia", fracao
    return "parcial", fracao


# --------------------------------------------------------------------------
# Texto bruto dentro da extensão estimada (para detecção de dose)
# --------------------------------------------------------------------------


def _sobrepoe(bloco_bbox: tuple[float, float, float, float], tabela_bbox: tuple) -> bool:
    bx0, by0, bx1, by1 = bloco_bbox
    tx0, ty0, tx1, ty1 = tabela_bbox
    return not (bx1 < tx0 or bx0 > tx1 or by1 < ty0 or by0 > ty1)


def _texto_bruto_na_extensao(
    pagina: pymupdf.Page, bbox: tuple[float, float, float, float], tabelas_da_pagina: list
) -> str:
    """Texto que a extração REAL produziria para esta extensão — não uma
    concatenação ingênua. Reproduz a mesma exclusão de `etl/extract.py`
    (`_montar_pagina`): um bloco de texto corrido que se sobrepõe à bbox de
    uma tabela capturada pelo `pdfplumber` é OMITIDO do texto corrido
    (vira conteúdo só da tabela) — sem isso, o trecho que o `pdfplumber`
    capturou apareceria duplicado aqui (uma vez como bloco de texto cru,
    outra como célula de tabela), o que não é o que a extração real produz
    e enganaria a conferência visual.

    As duas fontes ficam em blocos SEPARADOS e rotulados no texto
    devolvido — "texto corrido" é o que sobra fora da tabela capturada
    (o que mais importa conferir contra a imagem, no caso "parcial"),
    "tabela capturada" é o que o `pdfplumber` já pegou (mostrado à parte
    só para contexto, não é o que está em risco).
    """
    _x0, y0, _x1, y1 = bbox
    tabelas_sobrepostas = [t for t in tabelas_da_pagina if not (t.bbox[3] < y0 or t.bbox[1] > y1)]

    texto_corrido: list[str] = []
    for bx0, by0, bx1, by1, texto, *_resto in pagina.get_text("blocks"):
        if not texto.strip() or by0 < y0 - 2 or by1 > y1 + 2:
            continue
        if any(_sobrepoe((bx0, by0, bx1, by1), t.bbox) for t in tabelas_sobrepostas):
            continue
        texto_corrido.append(texto)

    texto_tabela: list[str] = []
    for tabela in tabelas_sobrepostas:
        for linha in tabela.extract() or []:
            texto_tabela.append(" ".join(c or "" for c in linha))

    partes = [f"— texto corrido —\n{chr(10).join(texto_corrido)}"] if texto_corrido else []
    if texto_tabela:
        partes.append(f"— tabela capturada pelo pdfplumber —\n{chr(10).join(texto_tabela)}")
    return "\n\n".join(partes)


# --------------------------------------------------------------------------
# Auditoria principal
# --------------------------------------------------------------------------


def _capitulo_da_pagina(mapa: list[dict], numero_pagina: int) -> str | None:
    for entrada in mapa:
        if entrada["pagina_inicial"] <= numero_pagina <= entrada["pagina_final"]:
            return f"{entrada['numero']} — {entrada['titulo']}"
    return None


def auditar(caminho_pdf: Path, mapa_capitulos: list[dict]) -> list[AchadoQuadro]:
    documento = pymupdf.open(caminho_pdf)
    achados: list[AchadoQuadro] = []

    with pdfplumber.open(caminho_pdf) as documento_plumber:
        for indice in range(documento.page_count):
            numero_pagina = indice + 1
            pagina = documento[indice]
            titulos = _localizar_titulos(pagina, numero_pagina)
            if not titulos:
                continue

            tabelas_da_pagina = documento_plumber.pages[indice].find_tables()
            titulos_ordenados = sorted(titulos, key=lambda t: t.y0)

            for posicao, titulo in enumerate(titulos_ordenados):
                teto_y = (
                    titulos_ordenados[posicao + 1].y0
                    if posicao + 1 < len(titulos_ordenados)
                    else pagina.rect.height
                )
                y1_estimado, continua = _estimar_fundo(pagina, titulo.y0, teto_y)
                bbox = (MARGEM_ESQUERDA_PT, titulo.y0, MARGEM_DIREITA_PT, y1_estimado)

                status, fracao = _classificar_captura(bbox, tabelas_da_pagina)
                texto_bruto = _texto_bruto_na_extensao(pagina, bbox, tabelas_da_pagina)
                doses = list(dict.fromkeys(extrair_doses(texto_bruto)))  # dedup, preserva ordem

                achados.append(
                    AchadoQuadro(
                        pagina=numero_pagina,
                        capitulo=_capitulo_da_pagina(mapa_capitulos, numero_pagina),
                        numero=titulo.numero,
                        titulo=titulo.titulo,
                        bbox=bbox,
                        status_captura=status,
                        fracao_capturada=fracao,
                        continua_na_proxima_pagina=continua,
                        texto_bruto=texto_bruto,
                        doses=doses,
                    )
                )

    logger.info(
        "auditoria_quadros_concluida",
        total_quadros=len(achados),
        com_dose=sum(1 for a in achados if a.doses),
        parcial_com_dose=sum(1 for a in achados if a.status_captura == "parcial" and a.doses),
        nenhuma_com_dose=sum(1 for a in achados if a.status_captura == "nenhuma" and a.doses),
    )
    return achados


# --------------------------------------------------------------------------
# Renderização para conferência visual
# --------------------------------------------------------------------------


def _renderizar_recorte(
    documento: pymupdf.Document, achado: AchadoQuadro, caminho_saida: Path, dpi: int = 150
) -> None:
    pagina = documento[achado.pagina - 1]
    x0, y0, x1, y1 = achado.bbox
    margem = 8.0
    clip = pymupdf.Rect(
        max(0, x0 - margem),
        max(0, y0 - margem),
        min(pagina.rect.width, x1 + margem),
        min(pagina.rect.height, y1 + margem),
    )
    pixmap = pagina.get_pixmap(clip=clip, dpi=dpi)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(caminho_saida)


# --------------------------------------------------------------------------
# Relatório Markdown
# --------------------------------------------------------------------------


_ORDEM_STATUS = {"parcial": 0, "nenhuma": 1, "cheia": 2}


def _doses_para_celula(doses: list[str]) -> str:
    # Uma dose casada por etl.dose pode conter quebra de linha embutida
    # (variante real do corpus, ex. número e unidade separados por uma
    # linha em branco de tabela mal extraída — ver etl/dose.py) — precisa
    # virar uma única linha para não quebrar a linha da tabela Markdown.
    return "; ".join(" ".join(dose.split()) for dose in doses)


def gerar_relatorio(achados: list[AchadoQuadro], caminho_pdf: Path, diretorio_saida: Path) -> str:
    com_dose = [a for a in achados if a.doses]
    sem_dose = [a for a in achados if not a.doses]
    com_dose.sort(key=lambda a: (_ORDEM_STATUS[a.status_captura], a.pagina))
    sem_dose.sort(key=lambda a: (_ORDEM_STATUS[a.status_captura], a.pagina))

    por_status: dict[str, int] = {}
    for a in achados:
        por_status[a.status_captura] = por_status.get(a.status_captura, 0) + 1

    linhas = [
        "# Auditoria de QUADROs — corpus do Spinosa\n",
        "Leitura pura — não altera `etl/extract.py` nem `data/extracted/`. "
        "Extensão de caixa estimada por objetos de desenho vetorial "
        "(`Page.get_drawings()`), não pela extração real — ver metodologia "
        "no docstring de `etl/auditar_quadros.py`.\n",
        "**Achado mais sério que desordem:** a seção 3 (confirmado com "
        "`etl.extract.extrair` de verdade sobre a página 166, QUADRO 6.6) "
        'mostra que "parcial" às vezes não é só ordem de leitura errada — '
        "é PERDA de conteúdo. Quando o `pdfplumber` reconhece a bbox de uma "
        "célula mas `.extract()` não consegue puxar o texto dela (comum "
        "sem borda visível na célula), `etl/extract.py` ainda exclui esse "
        "trecho do texto corrido (porque a bbox se sobrepõe a uma tabela "
        '"capturada"), mas a tabela também não tem o texto — o trecho some '
        "dos dois lados. Em QUADRO 6.6 isso apaga por completo a linha do "
        'Betanecol ("5,0 a 15 mg/kg", "1,25 a 5,0 mg/gato") e o nome+dose '
        "inicial da Atropina — nem tabela nem texto corrido têm essas "
        "doses. A % de cobertura abaixo mede só sobreposição geométrica de "
        "bbox, não se o `pdfplumber` conseguiu extrair o conteúdo da "
        'célula — por isso mesmo um "parcial" com % razoável pode estar '
        "escondendo perda, não só desordem.\n",
        f"**{len(achados)} QUADROs encontrados** "
        f"({', '.join(f'{n} {s}' for s, n in sorted(por_status.items()))}). "
        f"**{len(com_dose)} contêm padrão de dose** (`etl/dose.py`).\n",
        "## 1. Prioridade — QUADROs com dose\n",
        "| página | capítulo | quadro | status | cobertura | continua na próx. pág.? | doses |",
        "|---|---|---|---|---|---|---|",
    ]
    for a in com_dose:
        cap = (a.capitulo or "?").split(" — ")[0]
        linhas.append(
            f"| {a.pagina} | {cap} | {a.numero} | {a.status_captura} | "
            f"{a.fracao_capturada:.0%} | {'sim' if a.continua_na_proxima_pagina else 'não'} | "
            f"{_doses_para_celula(a.doses)} |"
        )
    linhas.append("")

    linhas.append("## 2. QUADROs sem padrão de dose (referência, sem prioridade)\n")
    linhas.append("| página | capítulo | quadro | status | cobertura |")
    linhas.append("|---|---|---|---|---|")
    for a in sem_dose:
        cap = (a.capitulo or "?").split(" — ")[0]
        linhas.append(
            f"| {a.pagina} | {cap} | {a.numero} | {a.status_captura} | {a.fracao_capturada:.0%} |"
        )
    linhas.append("")

    parciais_com_dose = [a for a in com_dose if a.status_captura == "parcial"]
    linhas.append(
        f"## 3. Conferência visual — capturados parcialmente E com dose "
        f"({len(parciais_com_dose)})\n"
    )
    if not parciais_com_dose:
        linhas.append(
            "*(nenhum — todo QUADRO com dose foi capturado por inteiro ou não "
            "capturado de jeito nenhum pelo pdfplumber)*\n"
        )
    else:
        documento = pymupdf.open(caminho_pdf)
        for a in parciais_com_dose:
            nome_arquivo = f"pagina{a.pagina:04d}-quadro{a.numero.replace('.', '_')}.png"
            caminho_imagem = diretorio_saida / "quadros" / nome_arquivo
            _renderizar_recorte(documento, a, caminho_imagem)
            linhas.append(f"### QUADRO {a.numero} — página {a.pagina} ({a.capitulo or '?'})\n")
            linhas.append(f"Doses encontradas: {_doses_para_celula(a.doses)}\n")
            linhas.append(
                "<table><tr><td valign='top' width='45%'>\n\n"
                f"![p{a.pagina} QUADRO {a.numero}](quadros/{nome_arquivo})\n\n"
                "</td><td valign='top' width='55%'>\n\n"
                "```\n" + a.texto_bruto.strip() + "\n```\n\n"
                "</td></tr></table>\n"
            )

    return "\n".join(linhas)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Caminho do PDF do Spinosa")
    parser.add_argument("--mapa-capitulos", type=Path, default=CAMINHO_MAPA_CAPITULOS_PADRAO)
    parser.add_argument("--saida-dir", type=Path, default=DIRETORIO_AUDITORIA_PADRAO)
    args = parser.parse_args(argv)

    import json

    mapa = json.loads(args.mapa_capitulos.read_text(encoding="utf-8"))
    achados = auditar(args.source, mapa)
    relatorio = gerar_relatorio(achados, args.source, args.saida_dir)

    caminho_saida = args.saida_dir / "quadros.md"
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    caminho_saida.write_text(relatorio, encoding="utf-8")
    logger.info("relatorio_quadros_gravado", saida=str(caminho_saida))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
