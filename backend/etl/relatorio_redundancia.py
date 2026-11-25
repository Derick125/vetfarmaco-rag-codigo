"""Relatório de redundância textual entre chunks de bula (leitura pura —
não altera `backend/data/preview/*.json` nem toca no banco).

Motivação: um PDF de bula RCM/SPC da UE (ex. `meloxicam.pdf`) descreve mais
de um "ciclo de produto" — a mesma substância em apresentações comerciais
diferentes, cada uma para uma espécie-alvo (ver `_atribuir_ciclo_de_produto`
em `etl/extract_bula.py`) — e cada ciclo gera sua PRÓPRIA seção/chunk, ainda
que o conteúdo clínico seja, em boa parte, o mesmo texto repetido com a
espécie/dose trocada. Antes de carregar isso no banco (onde cada chunk vira
um vetor buscável independente), é preciso saber QUANTO desse conteúdo é
repetição de fato — para decidir deduplicar, mesclar ou manter como está —
sem que o script decida isso sozinho.

Produz um único Markdown com três partes:

1. Meloxicam, seção por seção: os chunks agrupados por ciclo de produto
   (chunk_id, ciclo, tokens) e a similaridade par a par ENTRE CICLOS
   DIFERENTES (pares do mesmo ciclo — janelas adjacentes da mesma seção
   contínua — não entram: elas se sobrepõem por design, `SOBREPOSICAO_TOKENS`
   em `etl/chunk_bula.py`, e essa não é a redundância em questão).
2. Os chunks de `interacoes` do meloxicam, texto completo de cada um lado a
   lado, mais um diff em nível de palavra (`~~removido~~`/`**inserido**`)
   de cada ciclo contra o primeiro, para leitura direta.
3. Corpus inteiro (as seis bulas): todo par de chunks — mesma bula ou não —
   com similaridade acima de `--limiar` (default 0,90).

Métrica: `difflib.SequenceMatcher.ratio()` sobre a lista de palavras
(minúsculas) de cada chunk — mede o quanto de uma sequência de tokens "cabe"
na outra preservando ordem, o que serve tanto de nota de similaridade quanto
de base para o diff da parte 2 (mesma ferramenta para as duas coisas, para
não ter dois números que significam coisas ligeiramente diferentes).

Nada aqui deduplica, mescla ou descarta — é só o levantamento para decisão
humana.

Uso:
    python -m etl.relatorio_redundancia --previews data/preview \\
        --saida data/audit/redundancia.md --limiar 0.90
"""

from __future__ import annotations

import argparse
import difflib
import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import structlog

logger = structlog.get_logger()

DIRETORIO_PREVIEW_PADRAO = Path(__file__).resolve().parent.parent / "data" / "preview"
CAMINHO_SAIDA_PADRAO = Path(__file__).resolve().parent.parent / "data" / "audit" / "redundancia.md"
LIMIAR_PADRAO = 0.90


@dataclass
class ChunkLido:
    bula: str
    chunk_id: str
    secao: str
    produto: str
    especies: list[str]
    tokens: int
    texto: str
    palavras: list[str]  # minúsculas — só para a métrica, nunca exibido


def carregar_chunks(diretorio: Path) -> list[ChunkLido]:
    chunks: list[ChunkLido] = []
    for caminho in sorted(diretorio.glob("*.json")):
        bula = caminho.stem
        for registro in json.loads(caminho.read_text(encoding="utf-8")):
            chunks.append(
                ChunkLido(
                    bula=bula,
                    chunk_id=registro["chunk_id"],
                    secao=registro["secao"],
                    produto=registro["produto"],
                    especies=registro["especies"],
                    tokens=registro["tokens"],
                    texto=registro["texto"],
                    palavras=registro["texto"].lower().split(),
                )
            )
    return chunks


# --------------------------------------------------------------------------
# Métrica de similaridade
# --------------------------------------------------------------------------


def _cota_superior(len_a: int, len_b: int) -> float:
    """Maior valor que `SequenceMatcher.ratio()` PODE assumir dado só o
    tamanho das duas sequências (2*min/soma) — permite pular o cálculo real
    (caro) para pares que não têm a MENOR chance de atingir o limiar, sem
    arriscar descartar um par que passaria.
    """
    total = len_a + len_b
    return 0.0 if total == 0 else 2 * min(len_a, len_b) / total


def similaridade(a: ChunkLido, b: ChunkLido) -> float:
    return difflib.SequenceMatcher(None, a.palavras, b.palavras, autojunk=False).ratio()


def _diff_palavras(a: str, b: str) -> str:
    """Diff em nível de palavra entre dois textos, formatado em Markdown —
    `~~removido de a~~` / `**inserido em b**` — trechos iguais aparecem sem
    marcação. Usa a mesma ferramenta (`SequenceMatcher`) da métrica acima.
    """
    palavras_a, palavras_b = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, palavras_a, palavras_b, autojunk=False)
    partes: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            partes.append(" ".join(palavras_a[i1:i2]))
        elif tag == "delete":
            partes.append(f"~~{' '.join(palavras_a[i1:i2])}~~")
        elif tag == "insert":
            partes.append(f"**{' '.join(palavras_b[j1:j2])}**")
        elif tag == "replace":
            partes.append(f"~~{' '.join(palavras_a[i1:i2])}~~ **{' '.join(palavras_b[j1:j2])}**")
    return " ".join(partes)


# --------------------------------------------------------------------------
# Parte 1 — meloxicam, seção por seção
# --------------------------------------------------------------------------


def _rotulo_ciclo(chunk: ChunkLido) -> str:
    especies = "/".join(chunk.especies) if chunk.especies else "sem espécie"
    return f"{especies} — {chunk.produto}"


def _pares_entre_ciclos_diferentes(
    chunks: list[ChunkLido], limiar: float = 0.0
) -> list[tuple[ChunkLido, ChunkLido, float]]:
    pares = []
    for a, b in combinations(chunks, 2):
        if a.produto == b.produto:
            continue  # mesmo ciclo: janelas adjacentes, sobreposição esperada
        if _cota_superior(len(a.palavras), len(b.palavras)) < limiar:
            continue
        pares.append((a, b, similaridade(a, b)))
    pares.sort(key=lambda item: item[2], reverse=True)
    return pares


def relatorio_meloxicam(todos_chunks: list[ChunkLido]) -> str:
    chunks = [c for c in todos_chunks if c.bula == "meloxicam"]
    if not chunks:
        return "*(nenhum chunk encontrado para `meloxicam` em `data/preview/`)*\n"

    produtos = sorted({c.produto for c in chunks})
    linhas = [
        "## 1. Meloxicam — chunks por ciclo de produto, seção por seção\n",
        f"{len(chunks)} chunks, {len(produtos)} ciclos de produto:\n",
    ]
    for p in produtos:
        linhas.append(f"- {p}")
    linhas.append("")

    por_secao: dict[str, list[ChunkLido]] = {}
    for c in chunks:
        por_secao.setdefault(c.secao, []).append(c)

    for secao in sorted(por_secao):
        grupo = por_secao[secao]
        ciclos_presentes = {c.produto for c in grupo}
        linhas.append(f"### {secao} ({len(grupo)} chunks)\n")
        faltando = [p for p in produtos if p not in ciclos_presentes]
        if faltando:
            linhas.append(
                "> **Ciclo(s) sem chunk nesta seção:** "
                + "; ".join(faltando)
                + " — não necessariamente um erro (pode não haver texto "
                "próprio dessa apresentação para esta seção no PDF), mas "
                "vale conferir na fonte.\n"
            )
        linhas.append("| chunk_id | ciclo | tokens |")
        linhas.append("|---|---|---|")
        for c in sorted(grupo, key=lambda c: c.chunk_id):
            linhas.append(f"| {c.chunk_id} | {_rotulo_ciclo(c)} | {c.tokens} |")
        linhas.append("")

        pares = _pares_entre_ciclos_diferentes(grupo)
        if not pares:
            linhas.append(
                "*(só um ciclo tem chunk nesta seção — sem par entre ciclos diferentes "
                "para comparar)*\n"
            )
            continue
        linhas.append(
            f"**{len(pares)} pares entre ciclos diferentes** "
            "(pares do mesmo ciclo — janelas adjacentes — omitidos de propósito):\n"
        )
        linhas.append("| chunk_id A | chunk_id B | similaridade |")
        linhas.append("|---|---|---|")
        for a, b, sim in pares:
            linhas.append(f"| {a.chunk_id} | {b.chunk_id} | {sim:.3f} |")
        linhas.append("")

    return "\n".join(linhas)


# --------------------------------------------------------------------------
# Parte 2 — interacoes do meloxicam, lado a lado com diff
# --------------------------------------------------------------------------


def relatorio_interacoes_meloxicam(todos_chunks: list[ChunkLido]) -> str:
    chunks = sorted(
        (c for c in todos_chunks if c.bula == "meloxicam" and c.secao == "interacoes"),
        key=lambda c: c.chunk_id,
    )
    if not chunks:
        return "*(sem chunks de `interacoes` para meloxicam)*\n"

    linhas = [
        "## 2. Meloxicam — `interacoes`, texto completo por ciclo\n",
        f"{len(chunks)} chunks (nem todos os ciclos têm exatamente um — ver "
        "contagem abaixo; um ciclo pode ter mais de um cabeçalho mapeado para "
        '`interacoes`, ex. "Interações medicamentosas" e "Incompatibilidades" '
        "separados).\n",
    ]

    for c in chunks:
        linhas.append(f"### `{c.chunk_id}` — {_rotulo_ciclo(c)} ({c.tokens} tokens)\n")
        linhas.append("```")
        linhas.append(c.texto)
        linhas.append("```\n")

    referencia = chunks[0]
    linhas.append(
        f"### Diff de cada chunk contra `{referencia.chunk_id}` ({_rotulo_ciclo(referencia)})\n"
    )
    linhas.append(
        "`~~riscado~~` = só está na referência; `**negrito**` = só está no outro "
        "chunk; texto sem marcação = igual nos dois.\n"
    )
    for c in chunks[1:]:
        sim = similaridade(referencia, c)
        linhas.append(f"**`{c.chunk_id}`** ({_rotulo_ciclo(c)}) — similaridade: {sim:.3f}\n")
        linhas.append(_diff_palavras(referencia.texto, c.texto))
        linhas.append("")

    return "\n".join(linhas)


# --------------------------------------------------------------------------
# Parte 3 — corpus inteiro
# --------------------------------------------------------------------------


def relatorio_corpus(todos_chunks: list[ChunkLido], limiar: float) -> str:
    linhas = [
        "## 3. Corpus inteiro — pares acima do limiar\n",
        f"{len(todos_chunks)} chunks em {len({c.bula for c in todos_chunks})} bulas. "
        f"Todo par (mesma bula ou não) com similaridade > {limiar:.2f}:\n",
    ]

    pares: list[tuple[ChunkLido, ChunkLido, float]] = []
    for a, b in combinations(todos_chunks, 2):
        if _cota_superior(len(a.palavras), len(b.palavras)) <= limiar:
            continue
        sim = similaridade(a, b)
        if sim > limiar:
            pares.append((a, b, sim))
    pares.sort(key=lambda item: item[2], reverse=True)

    if not pares:
        linhas.append(f"*(nenhum par acima de {limiar:.2f})*\n")
        return "\n".join(linhas)

    linhas.append(f"**{len(pares)} pares encontrados:**\n")
    linhas.append("| chunk_id A | chunk_id B | mesma bula? | similaridade |")
    linhas.append("|---|---|---|---|")
    for a, b, sim in pares:
        mesma_bula = "sim" if a.bula == b.bula else "não"
        linhas.append(f"| {a.chunk_id} | {b.chunk_id} | {mesma_bula} | {sim:.3f} |")
    linhas.append("")

    return "\n".join(linhas)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def gerar_relatorio(diretorio_previews: Path, limiar: float) -> str:
    chunks = carregar_chunks(diretorio_previews)
    partes = [
        "# Relatório de redundância entre chunks de bula\n",
        "Leitura pura — não altera `data/preview/*.json` nem carrega no banco. "
        "Nada aqui foi deduplicado ou descartado.\n",
        relatorio_meloxicam(chunks),
        relatorio_interacoes_meloxicam(chunks),
        relatorio_corpus(chunks, limiar),
    ]
    return "\n".join(partes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previews", type=Path, default=DIRETORIO_PREVIEW_PADRAO)
    parser.add_argument("--saida", type=Path, default=CAMINHO_SAIDA_PADRAO)
    parser.add_argument("--limiar", type=float, default=LIMIAR_PADRAO)
    args = parser.parse_args(argv)

    relatorio = gerar_relatorio(args.previews, args.limiar)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(relatorio, encoding="utf-8")

    logger.info("relatorio_redundancia_gravado", saida=str(args.saida))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
