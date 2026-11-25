"""Segmentação em chunks (docs/RAG_SPEC.md §2, etapa "Chunking").

Consome o JSONL produzido por `etl/extract.py` (uma linha por página, com
`pagina`, `capitulo`, `texto`, `tabelas`) e produz chunks:

- Texto corrido: janela deslizante de 512 tokens com sobreposição de 64
  (`etl/chunk.py`, `docs/RAG_SPEC.md` §2). A janela pode atravessar
  páginas; o chunk herda a página e o capítulo de onde começa.
- Tabelas: cada tabela extraída por página vira um chunk próprio, nunca
  misturado com texto corrido nem partido entre chunks — "uma tabela de
  posologia nunca deve ser quebrada entre chunks".
- Nenhum chunk pode exceder 2048 tokens (limite de entrada do modelo de
  embeddings). Chunks de texto corrido nunca chegam lá, por construção
  (janela de 512); uma tabela maior que isso é um caso patológico — ainda
  assim não é partida (regra acima tem prioridade), só registrada em log.

`farmacos` e `especies` são extraídos por casamento contra o dicionário
controlado em `etl/vocabulario/farmacos.yaml`.

A contagem de tokens usa `tiktoken` (`cl100k_base`) como aproximação
rápida e sem estado de servidor — não é o tokenizador exato do
`gemini-embedding-001` (que exigiria uma chamada de API por chunk), mas é
consistente o bastante para o paradigma de janela deslizante.

Uso:
    python -m etl.chunk --entrada paginas.jsonl \\
        --fonte "Spinosa et al. (2017)" --tipo-fonte livro
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import structlog
import tiktoken
import yaml

logger = structlog.get_logger()

JANELA_TOKENS = 512
SOBREPOSICAO_TOKENS = 64
PASSO_TOKENS = JANELA_TOKENS - SOBREPOSICAO_TOKENS
MAX_TOKENS_CHUNK = 2048

_SEPARADOR_PAGINAS = "\n\n"
_ENCODER = tiktoken.get_encoding("cl100k_base")
_TOKENS_SEPARADOR = _ENCODER.encode(_SEPARADOR_PAGINAS)


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------


@dataclass
class PaginaLida:
    """Uma linha do JSONL produzido por `etl/extract.py`."""

    numero: int
    capitulo: str | None
    texto: str
    tabelas: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    """Metadados obrigatórios por chunk (`docs/RAG_SPEC.md` §2)."""

    chunk_id: str
    fonte: str
    tipo_fonte: str
    capitulo: str | None
    pagina: int
    farmacos: list[str]
    especies: list[str]
    tokens: int
    texto_hash: str
    texto: str


@dataclass
class _TermoVocabulario:
    nome: str
    padrao: re.Pattern[str]
    # Sinônimos do YAML (inclui o próprio nome); `GET /vocabulario` os serve ao app.
    sinonimos: list[str] = field(default_factory=list)


@dataclass
class Vocabulario:
    farmacos: list[_TermoVocabulario]
    especies: list[_TermoVocabulario]


# --------------------------------------------------------------------------
# Vocabulário controlado
# --------------------------------------------------------------------------


def carregar_vocabulario(caminho: Path) -> Vocabulario:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    return Vocabulario(
        farmacos=_compilar_termos(dados.get("farmacos", [])),
        especies=_compilar_termos(dados.get("especies", [])),
    )


def _compilar_termos(entradas: list[dict]) -> list[_TermoVocabulario]:
    termos = []
    for entrada in entradas:
        nome = entrada["nome"]
        sinonimos = entrada.get("sinonimos") or [nome]
        # sinônimos mais longos primeiro, para que "amoxicilina + ácido
        # clavulânico" não seja ofuscado por "amoxicilina" na alternância.
        alternativas = sorted(sinonimos, key=len, reverse=True)
        padrao = re.compile(
            r"\b(?:" + "|".join(re.escape(s) for s in alternativas) + r")\b",
            re.IGNORECASE,
        )
        termos.append(_TermoVocabulario(nome=nome, padrao=padrao, sinonimos=list(sinonimos)))
    return termos


def _casar(texto: str, termos: list[_TermoVocabulario]) -> list[str]:
    encontrados = {termo.nome for termo in termos if termo.padrao.search(texto)}
    return sorted(encontrados)


# --------------------------------------------------------------------------
# Identificador do chunk
# --------------------------------------------------------------------------


def _slug_fonte(fonte: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", fonte)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    primeira_palavra = re.split(r"[\s,]+", sem_acento.strip())[0] if sem_acento.strip() else ""
    slug = re.sub(r"[^a-zA-Z0-9]", "", primeira_palavra).lower()
    return slug or "fonte"


def _numero_capitulo(capitulo: str | None) -> str | None:
    if not capitulo:
        return None
    encontrado = re.match(r"\s*(\d+)", capitulo)
    return encontrado.group(1) if encontrado else None


def _montar_chunk_id(slug_fonte: str, capitulo: str | None, pagina: int, sequencia: int) -> str:
    numero_capitulo = _numero_capitulo(capitulo)
    prefixo = f"{slug_fonte}-c{numero_capitulo}" if numero_capitulo else slug_fonte
    return f"{prefixo}-p{pagina}-{sequencia:03d}"


# --------------------------------------------------------------------------
# Janela deslizante sobre o texto corrido
# --------------------------------------------------------------------------


def _tokens_do_documento(
    paginas: list[PaginaLida],
) -> tuple[list[int], list[int], list[str | None]]:
    """Concatena o texto de todas as páginas em um único fluxo de tokens.

    Retorna, em paralelo, a que página e a que capítulo cada token
    pertence — usados para atribuir a janela deslizante à página/capítulo
    em que ela começa.
    """
    todos_tokens: list[int] = []
    pagina_do_token: list[int] = []
    capitulo_do_token: list[str | None] = []
    for pagina in paginas:
        texto = pagina.texto.strip()
        if not texto:
            continue
        if todos_tokens:
            todos_tokens.extend(_TOKENS_SEPARADOR)
            pagina_do_token.extend([pagina.numero] * len(_TOKENS_SEPARADOR))
            capitulo_do_token.extend([pagina.capitulo] * len(_TOKENS_SEPARADOR))
        tokens = _ENCODER.encode(texto)
        todos_tokens.extend(tokens)
        pagina_do_token.extend([pagina.numero] * len(tokens))
        capitulo_do_token.extend([pagina.capitulo] * len(tokens))
    return todos_tokens, pagina_do_token, capitulo_do_token


def _janelas(total: int, janela: int, passo: int) -> list[tuple[int, int]]:
    """Pares (início, fim) [fim exclusivo] cobrindo `[0, total)`.

    `passo = janela - sobreposição`, de forma que janelas consecutivas
    compartilham exatamente `sobreposição` tokens (exceto a última, que
    pode ser mais curta).
    """
    if total == 0:
        return []
    intervalos = []
    inicio = 0
    while True:
        fim = min(inicio + janela, total)
        intervalos.append((inicio, fim))
        if fim >= total:
            break
        inicio += passo
    return intervalos


# --------------------------------------------------------------------------
# Segmentação
# --------------------------------------------------------------------------


def segmentar(
    paginas: list[PaginaLida],
    fonte: str,
    tipo_fonte: str,
    vocabulario: Vocabulario,
) -> list[Chunk]:
    slug_fonte = _slug_fonte(fonte)

    # (pagina, capitulo, texto) — tabelas primeiro, depois as janelas de
    # texto corrido; a ordem entre si não importa, o chunk_id é
    # renumerado por página logo abaixo.
    brutos_por_pagina: dict[int, list[tuple[str | None, str]]] = {}

    for pagina in paginas:
        for tabela in pagina.tabelas:
            texto_tabela = tabela.strip()
            if texto_tabela:
                brutos_por_pagina.setdefault(pagina.numero, []).append(
                    (pagina.capitulo, texto_tabela)
                )

    todos_tokens, pagina_do_token, capitulo_do_token = _tokens_do_documento(paginas)
    for inicio, fim in _janelas(len(todos_tokens), JANELA_TOKENS, PASSO_TOKENS):
        texto = _ENCODER.decode(todos_tokens[inicio:fim]).strip()
        if not texto:
            continue
        pagina_origem = pagina_do_token[inicio]
        capitulo_origem = capitulo_do_token[inicio]
        brutos_por_pagina.setdefault(pagina_origem, []).append((capitulo_origem, texto))

    chunks: list[Chunk] = []
    for numero_pagina in sorted(brutos_por_pagina):
        for sequencia, (capitulo, texto) in enumerate(brutos_por_pagina[numero_pagina], start=1):
            n_tokens = len(_ENCODER.encode(texto))
            if n_tokens > MAX_TOKENS_CHUNK:
                logger.warning(
                    "chunk_acima_do_limite",
                    pagina=numero_pagina,
                    tokens=n_tokens,
                    limite=MAX_TOKENS_CHUNK,
                )
            chunks.append(
                Chunk(
                    chunk_id=_montar_chunk_id(slug_fonte, capitulo, numero_pagina, sequencia),
                    fonte=fonte,
                    tipo_fonte=tipo_fonte,
                    capitulo=capitulo,
                    pagina=numero_pagina,
                    farmacos=_casar(texto, vocabulario.farmacos),
                    especies=_casar(texto, vocabulario.especies),
                    tokens=n_tokens,
                    texto_hash=hashlib.sha256(texto.encode("utf-8")).hexdigest(),
                    texto=texto,
                )
            )

    logger.info(
        "segmentacao_concluida",
        fonte=fonte,
        paginas=len(paginas),
        chunks=len(chunks),
    )
    return chunks


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _ler_paginas(caminho: Path) -> list[PaginaLida]:
    paginas = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        registro = json.loads(linha)
        paginas.append(
            PaginaLida(
                numero=registro["pagina"],
                capitulo=registro.get("capitulo"),
                texto=registro.get("texto", ""),
                tabelas=registro.get("tabelas", []),
            )
        )
    return paginas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entrada", required=True, type=Path, help="JSONL produzido por etl/extract.py"
    )
    parser.add_argument("--fonte", required=True, help='Ex.: "Spinosa et al. (2017)"')
    parser.add_argument("--tipo-fonte", required=True, choices=["livro", "bula"])
    parser.add_argument(
        "--vocabulario",
        type=Path,
        default=Path(__file__).parent / "vocabulario" / "farmacos.yaml",
        help="Dicionário controlado (default: etl/vocabulario/farmacos.yaml)",
    )
    parser.add_argument(
        "--saida", type=Path, default=None, help="Arquivo JSONL de saída; default: stdout"
    )
    args = parser.parse_args(argv)

    paginas = _ler_paginas(args.entrada)
    vocabulario = carregar_vocabulario(args.vocabulario)
    chunks = segmentar(paginas, args.fonte, args.tipo_fonte, vocabulario)

    linhas = [
        json.dumps(
            {
                "chunk_id": c.chunk_id,
                "fonte": c.fonte,
                "tipo_fonte": c.tipo_fonte,
                "capitulo": c.capitulo,
                "pagina": c.pagina,
                "farmacos": c.farmacos,
                "especies": c.especies,
                "tokens": c.tokens,
                "texto_hash": c.texto_hash,
                "texto": c.texto,
            },
            ensure_ascii=False,
        )
        for c in chunks
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
