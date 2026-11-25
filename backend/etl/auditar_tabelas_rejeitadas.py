"""Das tabelas rejeitadas por `etl/extract.py` (`_tabela_perde_conteudo`),
quantas tinham padrão de dose — e, para uma amostra, como a região original
compara com o texto corrido que sobrou. Leitura pura, não corrige nada.

`etl/extract.py` já rejeita (e loga) toda tabela cuja serialização não
cobre o texto bruto do PyMuPDF na mesma bbox — a métrica de "quantas
rejeitadas" já existe no log da extração. O que falta é: dessas, quantas
tinham dose (`etl/dose.py`) e, olhando a região renderizada ao lado do
texto corrido resultante, a associação fármaco → dose → espécie continua
recuperável depois de virar prosa (sem a estrutura de colunas)?

Saída: `data/audit/tabelas_rejeitadas_com_dose.md` + recortes de página em
`data/audit/tabelas_rejeitadas/*.png`, para uma amostra.

Uso:
    python -m etl.auditar_tabelas_rejeitadas --source "../data/Farmacologia...pdf" \\
        --amostra 5 --saida-dir data/audit
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import pymupdf
import structlog

from etl.dose import extrair_doses
from etl.extract import (
    _Bloco,
    _blocos_da_pagina,
    _serializar_markdown,
    _sobrepoe,
    _tabela_perde_conteudo,
    extrair,
)

logger = structlog.get_logger()

DIRETORIO_AUDITORIA_PADRAO = Path(__file__).resolve().parent.parent / "data" / "audit"


@dataclass
class TabelaRejeitada:
    pagina: int
    bbox: tuple[float, float, float, float]
    blocos: list[_Bloco] = field(default_factory=list)

    @property
    def texto_bruto(self) -> str:
        return "\n".join(b.texto for b in self.blocos)

    @property
    def doses(self) -> list[str]:
        return list(dict.fromkeys(extrair_doses(self.texto_bruto)))


# --------------------------------------------------------------------------
# Varredura do livro inteiro
# --------------------------------------------------------------------------


def varrer(caminho_pdf: Path) -> list[TabelaRejeitada]:
    documento = pymupdf.open(caminho_pdf)
    rejeitadas: list[TabelaRejeitada] = []

    with pdfplumber.open(caminho_pdf) as documento_plumber:
        for indice in range(documento.page_count):
            numero_pagina = indice + 1
            pagina_plumber = documento_plumber.pages[indice]
            tabelas = pagina_plumber.find_tables()
            if not tabelas:
                continue

            blocos = _blocos_da_pagina(documento[indice])

            for tabela in tabelas:
                linhas_brutas = tabela.extract()
                linhas = [
                    [
                        (celula or "").replace("\xa0", " ").replace("\xad", "-").strip()
                        for celula in linha
                    ]
                    for linha in linhas_brutas
                ]
                linhas = [linha for linha in linhas if any(celula for celula in linha)]
                if not linhas:
                    continue
                markdown = _serializar_markdown(linhas)
                if _tabela_perde_conteudo(tabela.bbox, markdown, blocos) is None:
                    continue  # aceita, não é o que estamos auditando aqui

                blocos_da_tabela = [b for b in blocos if _sobrepoe(b, tabela.bbox)]
                rejeitadas.append(
                    TabelaRejeitada(pagina=numero_pagina, bbox=tabela.bbox, blocos=blocos_da_tabela)
                )

    logger.info(
        "varredura_tabelas_rejeitadas_concluida",
        total_rejeitadas=len(rejeitadas),
        com_dose=sum(1 for t in rejeitadas if t.doses),
    )
    return rejeitadas


# --------------------------------------------------------------------------
# Renderização + texto corrido resultante, para a amostra
# --------------------------------------------------------------------------


def _renderizar(
    documento: pymupdf.Document, tabela: TabelaRejeitada, caminho_saida: Path, dpi: int = 150
) -> None:
    """Recorte da página com margem ASSIMÉTRICA (bem mais no topo) e
    LARGURA TOTAL da área de texto (não só a bbox estreita do objeto
    rejeitado) — o pdfplumber costuma partir uma tabela de posologia em
    vários objetos pequenos, um por COLUNA ou por bloco de espécie/dose;
    a bbox de UM objeto sozinho é estreita o bastante para cortar a
    coluna do nome do fármaco ou da posologia ao lado, e o nome do
    fármaco muitas vezes está no bloco anterior, um pouco acima. Sem essa
    folga, o recorte mostraria só uma coluna solta e enganaria a
    comparação com o texto corrido (que já é a página inteira).
    """
    pagina = documento[tabela.pagina - 1]
    _x0, y0, _x1, y1 = tabela.bbox
    clip = pymupdf.Rect(
        18.0,
        max(0, y0 - 90),
        min(pagina.rect.width, 594.0),
        min(pagina.rect.height, y1 + 20),
    )
    pixmap = pagina.get_pixmap(clip=clip, dpi=dpi)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(caminho_saida)


def _texto_corrido_resultante(caminho_pdf: Path, tabela: TabelaRejeitada) -> str:
    """Texto corrido REAL da página inteira (`etl.extract.extrair`), com a
    janela de parágrafos ao redor de onde as doses da tabela aparecem —
    não só os blocos dentro da bbox estrita da tabela rejeitada: como o
    pdfplumber costuma partir uma tabela de posologia em vários objetos
    pequenos, o nome do fármaco muitas vezes está num parágrafo vizinho
    (de OUTRO objeto, aceito ou rejeitado à parte) que a bbox estrita não
    cobre — mostrar só a bbox estrita subestimaria a associação que
    sobrevive de verdade no corpus. Cai para a página inteira se nenhuma
    dose for encontrada no texto (não deveria acontecer, mas evita
    resultado vazio).
    """
    (pagina_extraida,) = extrair(caminho_pdf, tabela.pagina, tabela.pagina, "auditoria")
    paragrafos = pagina_extraida.texto.split("\n\n")
    doses_norm = [d.lower() for d in tabela.doses]
    indices = [i for i, p in enumerate(paragrafos) if any(d in p.lower() for d in doses_norm)]
    if not indices:
        return pagina_extraida.texto
    inicio = max(0, min(indices) - 1)
    fim = min(len(paragrafos), max(indices) + 2)
    return "\n\n".join(paragrafos[inicio:fim])


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------


def gerar_relatorio(
    caminho_pdf: Path, com_dose: list[TabelaRejeitada], diretorio_saida: Path, tamanho_amostra: int
) -> str:
    linhas = [
        "# Tabelas rejeitadas com padrão de dose — Spinosa\n",
        "Leitura pura — não altera `etl/extract.py` nem `data/extracted/`.\n",
        f"**{len(com_dose)} das tabelas rejeitadas por `_tabela_perde_conteudo` contêm "
        f"padrão de dose** (`etl/dose.py`).\n",
        "| página | bbox | doses no bruto |",
        "|---|---|---|",
    ]
    for t in com_dose:
        bbox_txt = f"({t.bbox[0]:.0f}, {t.bbox[1]:.0f}, {t.bbox[2]:.0f}, {t.bbox[3]:.0f})"
        doses_txt = "; ".join(" ".join(d.split()) for d in t.doses)
        linhas.append(f"| {t.pagina} | {bbox_txt} | {doses_txt} |")
    linhas.append("")

    amostra = com_dose[:tamanho_amostra]
    linhas.append(f"## Amostra ({len(amostra)}) — região original vs. texto corrido resultante\n")

    documento = pymupdf.open(caminho_pdf)
    for i, t in enumerate(amostra, start=1):
        nome_arquivo = f"amostra{i:02d}-p{t.pagina}.png"
        _renderizar(documento, t, diretorio_saida / "tabelas_rejeitadas" / nome_arquivo)
        corrido = _texto_corrido_resultante(caminho_pdf, t)
        linhas.append(f"### Amostra {i} — página {t.pagina}\n")
        linhas.append(f"Doses no bruto: {'; '.join(' '.join(d.split()) for d in t.doses)}\n")
        linhas.append(
            "<table><tr><td valign='top' width='45%'>\n\n"
            f"![p{t.pagina}](tabelas_rejeitadas/{nome_arquivo})\n\n"
            "</td><td valign='top' width='55%'>\n\n"
            "**Texto corrido resultante:**\n\n"
            "```\n" + corrido.strip() + "\n```\n\n"
            "</td></tr></table>\n"
        )

    return "\n".join(linhas)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--saida-dir", type=Path, default=DIRETORIO_AUDITORIA_PADRAO)
    parser.add_argument("--amostra", type=int, default=5)
    args = parser.parse_args(argv)

    rejeitadas = varrer(args.source)
    com_dose = [t for t in rejeitadas if t.doses]

    relatorio = gerar_relatorio(args.source, com_dose, args.saida_dir, args.amostra)
    caminho_saida = args.saida_dir / "tabelas_rejeitadas_com_dose.md"
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    caminho_saida.write_text(relatorio, encoding="utf-8")
    logger.info("relatorio_tabelas_rejeitadas_gravado", saida=str(caminho_saida))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
