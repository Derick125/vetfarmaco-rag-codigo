"""Extração do corpus PDF (docs/RAG_SPEC.md §2, etapa "Extração").

PyMuPDF extrai o texto corrido, preservando o número de página e o
cabeçalho de capítulo; pdfplumber extrai tabelas de dose e as serializa em
Markdown, para que uma tabela de posologia nunca seja quebrada entre
chunks. A limpeza remove cabeçalho/rodapé por posição, junta palavras
hifenizadas em fim de linha e normaliza unidades de dose.

Uma tabela só é aceita se sua serialização Markdown realmente contém o
texto bruto do PyMuPDF na mesma região — não basta o `pdfplumber` ter
reconhecido a bbox (`_tabela_perde_conteudo`). Achado real na auditoria do
Spinosa (`etl/auditar_perda_quadros.py`): o `pdfplumber` pode reconhecer a
área de uma tabela mas `.extract()` falhar em puxar o texto de algumas
células (comum sem borda visível) — como o texto corrido exclui todo
bloco que se sobrepõe à bbox de uma tabela "capturada", esse conteúdo
sumia dos dois lados: não virava tabela, não sobrava texto corrido. Uma
tabela rejeitada por esse critério é descartada por inteiro (perder a
estrutura de colunas é aceitável) e seus blocos fluem como texto corrido
comum — cada rejeição é registrada em log
(`tabela_rejeitada_conteudo_incompleto`).

Este módulo só extrai e limpa — não segmenta em chunks (isso é
`etl/chunk.py`) nem casa fármacos/espécies contra o vocabulário controlado
(isso acontece na etapa de metadados do chunking).

Uso:
    python -m etl.extract --source data/spinosa.pdf
    python -m etl.extract --source data/spinosa.pdf --paginas 410-438 \\
        --capitulo "20 — Anti-inflamatórios Não Esteroidais"
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import pymupdf
import structlog

logger = structlog.get_logger()

# Faixa de margem (em pontos PDF) onde um cabeçalho/rodapé pode aparecer.
# A remoção real depende de repetição (ver `_detectar_cabecalho_rodape`) —
# um PDF sem cabeçalho/rodapé impresso, em que o corpo do texto flui até a
# borda da página, não perde conteúdo só por cair nesta faixa.
MARGEM_TOPO_PT = 30.0
MARGEM_RODAPE_PT = 30.0

# Um texto marginal que se repete em pelo menos N páginas do lote é tratado
# como cabeçalho/rodapé (nome do livro, do capítulo etc.).
MIN_REPETICOES_CABECALHO = 3

# Um bloco marginal formado só por dígitos é sempre tratado como número de
# página, mesmo sem repetição exata (o valor muda a cada página).
PADRAO_NUMERO_PAGINA = re.compile(r"^\d{1,5}$")

# "mg/kg" já é a forma canônica; "mg kg-1", "mg.kg-1", "mg·kg-1" etc. viram
# "mg/kg". Vírgula decimal nunca é tocada por esta normalização.
PADRAO_UNIDADE_DOSE = re.compile(r"(?i)\b(mg|mcg|ml|UI)\s*[.\s]?\s*kg\s*-?\s*1\b")

# Fração mínima de palavras de um bloco bruto do PyMuPDF que precisa
# aparecer na serialização Markdown de uma tabela para a tabela ser aceita
# (ver `_tabela_perde_conteudo`) — mesmo limiar validado empiricamente em
# `etl/auditar_perda_quadros.py` sobre o corpus real: alto o bastante para
# não rejeitar tabela só por reformatação incidental (célula com quebra de
# linha, espaço duplo), baixo o bastante para pegar uma célula cujo
# conteúdo o `pdfplumber` simplesmente não extraiu.
LIMIAR_PRESENCA_TABELA = 0.90


@dataclass
class _Bloco:
    """Um bloco de texto do PyMuPDF com a posição original na página."""

    x0: float
    y0: float
    x1: float
    y1: float
    texto: str


@dataclass
class PaginaExtraida:
    """Resultado da extração de uma página — a unidade que `etl/chunk.py` consome."""

    numero: int
    capitulo: str | None
    texto: str
    tabelas: list[str] = field(default_factory=list)


def _normalizar_espacos(texto: str) -> str:
    """Espaço-duro (comum neste tipo de PDF justificado) vira espaço comum."""
    return texto.replace("\xa0", " ")


def _juntar_hifenizacao(texto_bloco: str) -> str:
    """Junta palavras quebradas por hífen no fim de uma linha visual.

    Um bloco do PyMuPDF contém uma linha por quebra visual, separadas por
    `\\n`. Se uma linha termina em hífen (`-` ou o hífen "leve" `\\xad`, que
    este PDF usa também para hífens comuns) e a próxima começa com
    minúscula, é quebra de palavra — as duas se juntam sem hífen e sem
    espaço. Hífens no meio da linha (palavras compostas como
    "anti-inflamatório") nunca são tocados aqui.
    """
    linhas = texto_bloco.split("\n")
    resultado: list[str] = []
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        proxima = linhas[i + 1] if i + 1 < len(linhas) else ""
        quebra_de_palavra = (
            len(linha) > 1
            and linha[-1] in "-\xad"
            and linha[-2].isalpha()
            and proxima[:1].islower()
        )
        if quebra_de_palavra:
            linhas[i + 1] = linha[:-1] + proxima
            i += 1
            continue
        resultado.append(linha)
        i += 1
    return " ".join(linha.strip() for linha in resultado if linha.strip())


def _normalizar_hifen_restante(texto: str) -> str:
    """Hífens "leves" que sobraram (não eram quebra de linha) viram hífen comum."""
    return texto.replace("\xad", "-")


def _normalizar_unidades(texto: str) -> str:
    return PADRAO_UNIDADE_DOSE.sub(lambda m: f"{m.group(1)}/kg", texto)


_PADRAO_ESPACOS_REPETIDOS = re.compile(r" {2,}")


def _limpar_bloco(texto_bloco: str) -> str:
    texto = _normalizar_espacos(texto_bloco)
    texto = _juntar_hifenizacao(texto)
    texto = _normalizar_hifen_restante(texto)
    texto = _normalizar_unidades(texto)
    # O PDF de origem justifica linhas com espaços-duros repetidos; um
    # espaço simples entre palavras não muda o sentido do texto.
    return _PADRAO_ESPACOS_REPETIDOS.sub(" ", texto).strip()


def _blocos_da_pagina(pagina: pymupdf.Page) -> list[_Bloco]:
    blocos = []
    for x0, y0, x1, y1, texto, *_resto in pagina.get_text("blocks"):
        if texto.strip():
            blocos.append(_Bloco(x0, y0, x1, y1, texto))
    return blocos


def _sobrepoe(bloco: _Bloco, bbox: tuple[float, float, float, float]) -> bool:
    bx0, by0, bx1, by1 = bbox
    return not (bloco.x1 < bx0 or bloco.x0 > bx1 or bloco.y1 < by0 or bloco.y0 > by1)


def _eh_marginal(bloco: _Bloco, altura_pagina: float) -> bool:
    return bloco.y0 <= MARGEM_TOPO_PT or bloco.y1 >= altura_pagina - MARGEM_RODAPE_PT


def _detectar_cabecalho_rodape(
    blocos_por_pagina: dict[int, list[_Bloco]], altura_pagina: float
) -> set[str]:
    """Identifica textos marginais que são cabeçalho/rodapé, por repetição.

    Um texto marginal (dentro de `MARGEM_TOPO_PT`/`MARGEM_RODAPE_PT`) só é
    tratado como boilerplate se repetir em várias páginas do lote, ou se for
    puramente numérico (número de página). Isso evita cortar corpo de texto
    que, em PDFs sem cabeçalho/rodapé impresso, flui até perto da borda.
    """
    contagem: dict[str, set[int]] = {}
    for numero_pagina, blocos in blocos_por_pagina.items():
        for bloco in blocos:
            if not _eh_marginal(bloco, altura_pagina):
                continue
            normalizado = " ".join(bloco.texto.split())
            if not normalizado:
                continue
            contagem.setdefault(normalizado, set()).add(numero_pagina)
    return {
        texto
        for texto, paginas in contagem.items()
        if len(paginas) >= MIN_REPETICOES_CABECALHO or PADRAO_NUMERO_PAGINA.match(texto)
    }


def _serializar_markdown(linhas: list[list[str]]) -> str:
    largura = max(len(linha) for linha in linhas)
    linhas = [linha + [""] * (largura - len(linha)) for linha in linhas]
    partes = [
        "| " + " | ".join(linhas[0]) + " |",
        "| " + " | ".join(["---"] * largura) + " |",
    ]
    partes.extend("| " + " | ".join(linha) + " |" for linha in linhas[1:])
    return "\n".join(partes)


_PADRAO_ESPACOS_QUAISQUER = re.compile(r"\s+")


def _normalizar_para_comparacao(texto: str) -> str:
    # O hífen "leve" (`\xad`) vira "-" na limpeza de célula de tabela
    # (`_extrair_tabelas`, abaixo) antes de serializar — sem a mesma troca
    # aqui, uma palavra que atravessa quebra de linha no bloco bruto do
    # PyMuPDF (que preserva o `\xad` cru) nunca bateria contra a mesma
    # palavra já normalizada do lado da tabela, mesmo sendo texto idêntico
    # — falso positivo de "conteúdo perdido" por diferença de formatação,
    # não por conteúdo faltando de verdade.
    texto = texto.replace("\xad", "-")
    return _PADRAO_ESPACOS_QUAISQUER.sub(" ", texto.lower()).strip()


def _fracao_presente(bloco_norm: str, alvo_norm: str, contagem_alvo: Counter) -> float:
    """Fração das palavras de `bloco_norm` que aparecem em `alvo_norm`.

    Primeiro tenta substring exata (rápido, cobre o caso comum). Se
    falhar, cai para contagem de palavras (multiset — uma palavra que
    aparece duas vezes no bloco precisa aparecer duas vezes no alvo),
    tolerando reordenação/reformatação sem exigir a frase exata.
    """
    if bloco_norm and bloco_norm in alvo_norm:
        return 1.0
    palavras_bloco = bloco_norm.split()
    if not palavras_bloco:
        return 1.0
    contagem_bloco = Counter(palavras_bloco)
    encontradas = sum(
        min(n, contagem_alvo.get(palavra, 0)) for palavra, n in contagem_bloco.items()
    )
    return encontradas / len(palavras_bloco)


def _tabela_perde_conteudo(
    bbox: tuple[float, float, float, float], markdown: str, blocos: list[_Bloco]
) -> str | None:
    """Primeiro trecho bruto do PyMuPDF dentro de `bbox` que NÃO está
    coberto (por `LIMIAR_PRESENCA_TABELA`) pela serialização Markdown da
    tabela — `None` se a tabela cobre tudo. Só verifica blocos que se
    sobrepõem à bbox (`_sobrepoe`) — o mesmo critério usado para excluir
    esses blocos do texto corrido, então a checagem é sobre exatamente o
    que seria perdido se a tabela for aceita.
    """
    alvo_norm = _normalizar_para_comparacao(markdown)
    contagem_alvo = Counter(alvo_norm.split())
    for bloco in blocos:
        if not _sobrepoe(bloco, bbox):
            continue
        bloco_norm = _normalizar_para_comparacao(bloco.texto)
        if _fracao_presente(bloco_norm, alvo_norm, contagem_alvo) < LIMIAR_PRESENCA_TABELA:
            return bloco.texto.strip()
    return None


def _extrair_tabelas(
    pagina_plumber: pdfplumber.page.Page,
    blocos: list[_Bloco],
    numero_pagina: int,
) -> tuple[list[str], list[tuple[float, float, float, float]]]:
    """Extrai tabelas de dose com pdfplumber e as serializa em Markdown.

    Retorna também as caixas delimitadoras (bbox), para excluir esse
    conteúdo do texto corrido da página e não duplicá-lo — MAS só das
    tabelas aceitas: uma tabela cuja serialização não contém todo o texto
    bruto do PyMuPDF na sua própria bbox (`_tabela_perde_conteudo`) é
    descartada por inteiro, e seus blocos passam a fluir como texto
    corrido comum (perder a estrutura de colunas é aceitável; perder
    conteúdo não é). Cada rejeição é registrada em log.
    """
    tabelas_md: list[str] = []
    bboxes: list[tuple[float, float, float, float]] = []
    for tabela in pagina_plumber.find_tables():
        linhas_brutas = tabela.extract()
        linhas = [
            [(celula or "").replace("\xa0", " ").replace("\xad", "-").strip() for celula in linha]
            for linha in linhas_brutas
        ]
        linhas = [linha for linha in linhas if any(celula for celula in linha)]
        if not linhas:
            continue
        markdown = _serializar_markdown(linhas)
        trecho_ausente = _tabela_perde_conteudo(tabela.bbox, markdown, blocos)
        if trecho_ausente is not None:
            logger.warning(
                "tabela_rejeitada_conteudo_incompleto",
                pagina=numero_pagina,
                bbox=tabela.bbox,
                motivo="trecho do texto bruto do PyMuPDF ausente na serialização da tabela",
                trecho_ausente=trecho_ausente[:200],
            )
            continue
        tabelas_md.append(markdown)
        bboxes.append(tabela.bbox)
    return tabelas_md, bboxes


def _montar_pagina(
    numero: int,
    blocos: list[_Bloco],
    bboxes_tabelas: list[tuple[float, float, float, float]],
    boilerplate: set[str],
    altura_pagina: float,
    capitulo: str | None,
) -> str:
    partes: list[str] = []
    for bloco in blocos:
        normalizado = " ".join(bloco.texto.split())
        if _eh_marginal(bloco, altura_pagina) and normalizado in boilerplate:
            continue
        if any(_sobrepoe(bloco, bbox) for bbox in bboxes_tabelas):
            continue
        texto_limpo = _limpar_bloco(bloco.texto)
        if texto_limpo:
            partes.append(texto_limpo)
    return "\n\n".join(partes)


def extrair(
    caminho_pdf: Path,
    pagina_inicial: int | None = None,
    pagina_final: int | None = None,
    capitulo: str | None = None,
) -> list[PaginaExtraida]:
    """Extrai e limpa um intervalo de páginas (1-indexado, inclusive)."""
    documento = pymupdf.open(caminho_pdf)
    total_paginas = documento.page_count
    inicio = pagina_inicial or 1
    fim = pagina_final or total_paginas
    if not (1 <= inicio <= fim <= total_paginas):
        raise ValueError(
            f"intervalo de páginas inválido: {inicio}-{fim} (documento tem {total_paginas})"
        )

    blocos_por_pagina = {
        numero: _blocos_da_pagina(documento[numero - 1]) for numero in range(inicio, fim + 1)
    }
    altura_pagina = documento[inicio - 1].rect.height
    boilerplate = _detectar_cabecalho_rodape(blocos_por_pagina, altura_pagina)

    resultado: list[PaginaExtraida] = []
    with pdfplumber.open(caminho_pdf) as documento_plumber:
        for numero in range(inicio, fim + 1):
            tabelas_md, bboxes = _extrair_tabelas(
                documento_plumber.pages[numero - 1], blocos_por_pagina[numero], numero
            )
            texto = _montar_pagina(
                numero,
                blocos_por_pagina[numero],
                bboxes,
                boilerplate,
                altura_pagina,
                capitulo,
            )
            resultado.append(
                PaginaExtraida(numero=numero, capitulo=capitulo, texto=texto, tabelas=tabelas_md)
            )

    logger.info(
        "extracao_concluida",
        origem=str(caminho_pdf),
        paginas=len(resultado),
        pagina_inicial=inicio,
        pagina_final=fim,
        tabelas_encontradas=sum(len(p.tabelas) for p in resultado),
        cabecalhos_rodapes_removidos=len(boilerplate),
    )
    return resultado


def _tipo_intervalo_paginas(valor: str) -> tuple[int, int]:
    if "-" not in valor:
        raise argparse.ArgumentTypeError("use o formato INICIO-FIM, ex.: 410-438")
    inicio_str, fim_str = valor.split("-", 1)
    try:
        inicio, fim = int(inicio_str), int(fim_str)
    except ValueError as erro:
        raise argparse.ArgumentTypeError("INICIO e FIM devem ser inteiros") from erro
    if inicio < 1 or fim < inicio:
        raise argparse.ArgumentTypeError("intervalo de páginas inválido")
    return inicio, fim


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Caminho do PDF de origem")
    parser.add_argument(
        "--paginas",
        type=_tipo_intervalo_paginas,
        default=None,
        metavar="INICIO-FIM",
        help="Intervalo de páginas, 1-indexado e inclusive (default: o PDF inteiro)",
    )
    parser.add_argument(
        "--capitulo",
        default=None,
        help=(
            "Rótulo de capítulo aplicado a todas as páginas do lote "
            '(ex.: "20 — Anti-inflamatórios Não Esteroidais"). Necessário porque '
            "PDFs sem cabeçalho de capítulo impresso não permitem detecção automática."
        ),
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        help="Arquivo JSONL de saída (uma página por linha); default: stdout",
    )
    args = parser.parse_args(argv)

    inicio, fim = args.paginas if args.paginas else (None, None)
    paginas = extrair(args.source, inicio, fim, args.capitulo)

    linhas = [
        json.dumps(
            {
                "pagina": pagina.numero,
                "capitulo": pagina.capitulo,
                "texto": pagina.texto,
                "tabelas": pagina.tabelas,
            },
            ensure_ascii=False,
        )
        for pagina in paginas
    ]

    if args.saida:
        args.saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        logger.info("saida_gravada", caminho=str(args.saida), linhas=len(linhas))
    else:
        for linha in linhas:
            print(linha)  # noqa: T201 — saída de dados do CLI, não log de depuração

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
