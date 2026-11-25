"""Chunking de bulas, seção por seção (docs/RAG_SPEC.md §2, extensão de
`etl/chunk.py` para o corpus complementar de bulas).

Consome as seções produzidas por `etl/extract_bula.py` e produz chunks:

- Texto corrido: janela deslizante de **512 tokens com sobreposição de
  64**, igual ao corpus de livro — mas aqui a janela **reinicia a cada
  seção**: nunca mistura o fim de POSOLOGIA com o início de
  CONTRAINDICAÇÕES. Uma seção mais curta que 512 tokens vira um único
  chunk. Seções em `SECOES_SEM_JANELA` (`interacoes`, `posologia`) nunca
  são divididas por janela — a seção inteira vira um chunk só, mesmo acima
  de 512 tokens: hierarquias de interação medicamentosa (níveis e
  subgrupos, ver `etl.extract_bula`) sempre listam fármacos, e bulas com
  faixa de dose por condição (tipo de diabetes, fase da vida) listam cada
  faixa em sequência — cortar por contagem de tokens arriscaria partir uma
  lista ou separar um valor de dose da condição a que pertence.
- Tabelas: cada tabela de `etl/extract_bula.py` vira um chunk próprio,
  nunca dividido nem misturado com texto corrido, ainda que ultrapasse 512
  tokens — prefixado por uma linha de contexto
  "<fármaco> — <cabeçalho da seção> — <legenda>".
- Todo chunk, texto ou tabela, é prefixado com essa linha de contexto
  (`_contexto`) — sem a legenda no caso de texto corrido — para que
  qualquer chunk recuperado isoladamente, fora de ordem, sem o resto do
  documento, ainda diga de que fármaco e seção se trata.

Metadados por chunk: além dos já existentes no corpus de livro
(`chunk_id`, `fonte`, `tipo_fonte`, `tokens`, `texto_hash`, `texto`), soma
`secao` (vocabulário fixo de `etl/vocabulario/secoes_bula.yaml`), `origem`
e `especies` — vindos do manifesto (`data/bulas/manifesto.yaml`), nunca do
texto — e `farmacos`, derivado do nome do arquivo através do manifesto,
nunca por casamento de texto contra a bula (evita falso positivo com
fármacos citados de passagem, ex. numa seção de interação medicamentosa).

Uso:
    python -m etl.chunk_bula --entrada secoes.jsonl --source ivermectina.pdf \\
        --manifesto data/bulas/manifesto.yaml
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

_ENCODER = tiktoken.get_encoding("cl100k_base")

CAMINHO_MANIFESTO_PADRAO = Path(__file__).parent.parent.parent / "data" / "bulas" / "manifesto.yaml"

# Seções canônicas cuja janela nunca divide o texto, mesmo acima de 512
# tokens — a seção inteira vira um único chunk, como uma tabela. Interações
# medicamentosas sempre listam fármacos (por nível/subgrupo hierárquico em
# bulas antigas — ver `etl.extract_bula`); cortar por contagem de tokens é
# exatamente o risco de partir uma lista de medicamentos ao meio.
# Posologia entra pelo mesmo motivo: bulas com faixas de dose por
# condição (ex. tipo de diabetes, fase da vida) listam cada faixa em
# sequência no mesmo parágrafo — cortar por token separaria um valor de
# dose da condição a que pertence.
SECOES_SEM_JANELA = frozenset({"interacoes", "posologia"})


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------


@dataclass
class TabelaLida:
    markdown: str
    legenda: str


@dataclass
class SecaoLida:
    """Uma linha do JSONL produzido por `etl/extract_bula.py`."""

    secao: str
    cabecalho_original: str | None
    pagina_inicial: int
    texto: str
    tabelas: list[TabelaLida]
    # Preenchidos só quando o PDF descreve mais de um produto/espécie-alvo
    # (ver `etl.extract_bula._atribuir_ciclo_de_produto`) — mais
    # específicos que `EntradaManifesto.produto`/`especies`, que descrevem
    # o arquivo inteiro.
    produto_ciclo: str | None = None
    especies_ciclo: list[str] = field(default_factory=list)


@dataclass
class EntradaManifesto:
    farmaco: str
    origem: str
    especies: list[str]
    produto: str
    fabricante: str


@dataclass
class ChunkBula:
    """Metadados obrigatórios por chunk de bula."""

    chunk_id: str
    fonte: str
    tipo_fonte: str
    secao: str
    cabecalho_original: str | None
    pagina: int
    origem: str
    especies: list[str]
    farmacos: list[str]
    produto: str
    fabricante: str
    tipo_chunk: str  # "texto" | "tabela"
    tokens: int
    texto_hash: str
    texto: str


# --------------------------------------------------------------------------
# Manifesto
# --------------------------------------------------------------------------


def carregar_manifesto(caminho: Path) -> dict[str, EntradaManifesto | None]:
    """Carrega `data/bulas/manifesto.yaml`, chaveado por nome de arquivo em
    minúsculas. Uma entrada com campo `null` vira `None` no dicionário —
    sinal de que o manifesto ainda não foi preenchido para esse arquivo.
    """
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    resultado: dict[str, EntradaManifesto | None] = {}
    for nome_arquivo, entrada in (dados.get("bulas") or {}).items():
        campos_obrigatorios = ("farmaco", "origem", "especies", "produto", "fabricante")
        if any(entrada.get(campo) is None for campo in campos_obrigatorios):
            resultado[nome_arquivo.lower()] = None
            continue
        resultado[nome_arquivo.lower()] = EntradaManifesto(
            farmaco=entrada["farmaco"],
            origem=entrada["origem"],
            especies=list(entrada["especies"]),
            produto=entrada["produto"],
            fabricante=entrada["fabricante"],
        )
    return resultado


def buscar_entrada_manifesto(
    manifesto: dict[str, EntradaManifesto | None], origem_pdf: Path
) -> EntradaManifesto:
    chave = origem_pdf.name.lower()
    if chave not in manifesto:
        raise ValueError(
            f"'{origem_pdf.name}' não está declarado em data/bulas/manifesto.yaml "
            "(farmacos/origem/especies vêm exclusivamente do manifesto, nunca de "
            "casamento de texto — adicione a entrada antes de processar este PDF)"
        )
    entrada = manifesto[chave]
    if entrada is None:
        raise ValueError(
            f"a entrada de '{origem_pdf.name}' em data/bulas/manifesto.yaml ainda tem "
            "campos TODO (null) — preencha a partir do PDF antes de processar"
        )
    return entrada


# --------------------------------------------------------------------------
# Identificador do chunk
# --------------------------------------------------------------------------


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento.strip()).strip("-").lower()
    return slug or "bula"


def _montar_chunk_id(slug_farmaco: str, secao: str, sequencia: int) -> str:
    return f"{slug_farmaco}-{secao}-{sequencia:03d}"


# --------------------------------------------------------------------------
# Janela deslizante (reinicia a cada seção)
# --------------------------------------------------------------------------


def _janelas(total: int, janela: int, passo: int) -> list[tuple[int, int]]:
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


_NOME_ESPECIE_LEGIVEL = {
    "canino": "cães",
    "felino": "gatos",
    "bovino": "bovinos",
    "suino": "suínos",
    "equino": "equinos",
    "caprino": "caprinos",
    "coelho": "coelhos",
}


def _especies_legivel(especies: list[str]) -> str | None:
    """Nomes de espécie canônicos, em português natural, para a linha de
    contexto — "cães e gatos" em vez de "canino, felino". `None` se não
    houver nenhuma (chunk sem espécie conhecida por ciclo nem por
    manifesto).
    """
    nomes = [_NOME_ESPECIE_LEGIVEL.get(e, e) for e in especies]
    if not nomes:
        return None
    if len(nomes) == 1:
        return nomes[0]
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


# Dose por kg citada no texto (vírgula decimal, como no português) —
# "0,2 mg de meloxicam/kg", "4,4 mg/kg", "2,2 mg de carprofeno por kg"
# (separador "/" OU "por", ambos usados em bulas reais), "0,3 a 0,6
# UI/kg/dia" (faixa, unidade UI — a única do corpus que não é mg; nunca
# convertida nem normalizada, só reconhecida). O número pode ser inteiro
# ("2 a 3 mg/kg/dia", fenobarbital) ou decimal — a parte decimal é
# OPCIONAL, não obrigatória. Usada só para deixar a dose explícita na
# linha de contexto de um chunk de POSOLOGIA (ver `_contexto`) — bulas com
# mais de um esquema posológico ou mais de uma faixa por condição (ex.:
# diabetes tipo 1 vs. tipo 2, adulto vs. pré-adolescente) tendem a citar
# várias doses/faixas em sequência; até `_LIMITE_DOSES_CONTEXTO` delas
# entram na linha de contexto, na ordem em que aparecem, sem repetir.
_NUM = r"\d+(?:[,.]\d+)?"
_UNIDADE_POR_KG = r"(?:mg|UI)(?:\s+de\s+\S+)?\s*(?:/|por)\s*kg(?:\s*/\s*dia|/dia)?"
_PADRAO_DOSE_POR_KG = re.compile(
    rf"{_NUM}\s*(?:a|e|-)\s*{_NUM}\s*{_UNIDADE_POR_KG}|{_NUM}\s*{_UNIDADE_POR_KG}",
    re.IGNORECASE,
)
_LIMITE_DOSES_CONTEXTO = 3


def _extrair_doses(texto: str) -> list[str]:
    doses: list[str] = []
    for casamento in _PADRAO_DOSE_POR_KG.finditer(texto):
        dose = " ".join(casamento.group().split())
        if dose not in doses:
            doses.append(dose)
        if len(doses) >= _LIMITE_DOSES_CONTEXTO:
            break
    return doses


def _contexto(
    farmaco: str,
    cabecalho: str | None,
    secao: str,
    especies: list[str],
    legenda: str | None = None,
    doses: list[str] | None = None,
) -> str:
    """Linha de contexto prefixada em todo chunk — texto ou tabela — para
    que ele nomeie o fármaco, a seção e (quando conhecida) a espécie-alvo
    mesmo recuperado isoladamente, fora de ordem, sem o resto do chunk
    vizinho (ex.: um chunk de CONTRAINDICAÇÕES citado sozinho ainda diz de
    que fármaco e espécie se trata — importante quando o mesmo PDF
    descreve produtos para espécies diferentes, ver
    `etl.extract_bula._atribuir_ciclo_de_produto`). Chunks de POSOLOGIA
    também levam a dose em mg/kg, quando extraível (`doses`).
    """
    partes = [farmaco, cabecalho or secao]
    especies_texto = _especies_legivel(especies)
    if especies_texto:
        partes.append(especies_texto)
    if doses:
        partes.append("; ".join(doses))
    if legenda is not None:
        partes.append(legenda)
    return " — ".join(partes)


def segmentar(secoes: list[SecaoLida], fonte: str, entrada: EntradaManifesto) -> list[ChunkBula]:
    slug_farmaco = _slug(entrada.farmaco)
    chunks: list[ChunkBula] = []
    # Contagem por nome canônico de seção, não por objeto de seção: mais de
    # uma seção física do PDF pode cair no mesmo nome canônico (ex.: duas
    # seções sem cabeçalho reconhecido caem ambas em "outros") — um
    # contador por objeto reiniciaria em 1 nos dois casos e colidiria
    # `chunk_id`.
    contadores: dict[str, int] = {}

    for secao in secoes:
        # Mais específico que `entrada.especies`/`entrada.produto` (que
        # descrevem o arquivo inteiro) quando o PDF descreve mais de um
        # produto/espécie-alvo — ver `SecaoLida.especies_ciclo`.
        especies_secao = secao.especies_ciclo or entrada.especies
        produto_secao = secao.produto_ciclo or entrada.produto

        for tabela in secao.tabelas:
            contadores[secao.secao] = contadores.get(secao.secao, 0) + 1
            sequencia = contadores[secao.secao]
            contexto = _contexto(
                entrada.farmaco,
                secao.cabecalho_original,
                secao.secao,
                especies_secao,
                legenda=tabela.legenda,
            )
            texto_chunk = f"{contexto}\n\n{tabela.markdown}"
            n_tokens = len(_ENCODER.encode(texto_chunk))
            chunks.append(
                ChunkBula(
                    chunk_id=_montar_chunk_id(slug_farmaco, secao.secao, sequencia),
                    fonte=fonte,
                    tipo_fonte="bula",
                    secao=secao.secao,
                    cabecalho_original=secao.cabecalho_original,
                    pagina=secao.pagina_inicial,
                    origem=entrada.origem,
                    especies=especies_secao,
                    farmacos=[entrada.farmaco],
                    produto=produto_secao,
                    fabricante=entrada.fabricante,
                    tipo_chunk="tabela",
                    tokens=n_tokens,
                    texto_hash=hashlib.sha256(texto_chunk.encode("utf-8")).hexdigest(),
                    texto=texto_chunk,
                )
            )
            # Uma tabela nunca é dividida entre chunks, mesmo acima de 512
            # tokens — só é registrada em log se isso acontecer, para
            # conferência manual (ver docstring do módulo).
            if n_tokens > JANELA_TOKENS:
                logger.warning(
                    "tabela_acima_da_janela",
                    chunk_id=chunks[-1].chunk_id,
                    tokens=n_tokens,
                    janela=JANELA_TOKENS,
                )

        doses_secao = _extrair_doses(secao.texto) if secao.secao == "posologia" else None
        contexto_secao = _contexto(
            entrada.farmaco,
            secao.cabecalho_original,
            secao.secao,
            especies_secao,
            doses=doses_secao,
        )
        tokens_secao = _ENCODER.encode(secao.texto) if secao.texto.strip() else []
        # Interações medicamentosas nunca são divididas por janela, mesmo
        # acima de 512 tokens — hierarquias de nível/subgrupo (ver
        # `etl.extract_bula`) sempre listam medicamentos, e cortar no meio
        # da lista é exatamente o que a janela deslizante faria por
        # padrão. Mesma regra de indivisibilidade das tabelas.
        if secao.secao in SECOES_SEM_JANELA:
            janelas_secao = [(0, len(tokens_secao))] if tokens_secao else []
        else:
            janelas_secao = _janelas(len(tokens_secao), JANELA_TOKENS, PASSO_TOKENS)

        for inicio, fim in janelas_secao:
            texto_janela = _ENCODER.decode(tokens_secao[inicio:fim]).strip()
            if not texto_janela:
                continue
            texto_chunk = f"{contexto_secao}\n\n{texto_janela}"
            n_tokens = len(_ENCODER.encode(texto_chunk))
            contadores[secao.secao] = contadores.get(secao.secao, 0) + 1
            sequencia = contadores[secao.secao]
            chunks.append(
                ChunkBula(
                    chunk_id=_montar_chunk_id(slug_farmaco, secao.secao, sequencia),
                    fonte=fonte,
                    tipo_fonte="bula",
                    secao=secao.secao,
                    cabecalho_original=secao.cabecalho_original,
                    pagina=secao.pagina_inicial,
                    origem=entrada.origem,
                    especies=especies_secao,
                    farmacos=[entrada.farmaco],
                    produto=produto_secao,
                    fabricante=entrada.fabricante,
                    tipo_chunk="texto",
                    tokens=n_tokens,
                    texto_hash=hashlib.sha256(texto_chunk.encode("utf-8")).hexdigest(),
                    texto=texto_chunk,
                )
            )
            if secao.secao in SECOES_SEM_JANELA and n_tokens > JANELA_TOKENS:
                logger.warning(
                    "secao_indivisivel_acima_da_janela",
                    chunk_id=chunks[-1].chunk_id,
                    tokens=n_tokens,
                    janela=JANELA_TOKENS,
                )

    logger.info("chunking_bula_concluido", fonte=fonte, secoes=len(secoes), chunks=len(chunks))
    return chunks


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _ler_secoes(caminho: Path) -> list[SecaoLida]:
    secoes = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        registro = json.loads(linha)
        secoes.append(
            SecaoLida(
                secao=registro["secao"],
                cabecalho_original=registro.get("cabecalho_original"),
                pagina_inicial=registro["pagina_inicial"],
                texto=registro.get("texto", ""),
                tabelas=[TabelaLida(**t) for t in registro.get("tabelas", [])],
                produto_ciclo=registro.get("produto_ciclo"),
                especies_ciclo=list(registro.get("especies_ciclo") or []),
            )
        )
    return secoes


def _serializar_chunk(chunk: ChunkBula) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "fonte": chunk.fonte,
        "tipo_fonte": chunk.tipo_fonte,
        "secao": chunk.secao,
        "cabecalho_original": chunk.cabecalho_original,
        "pagina": chunk.pagina,
        "origem": chunk.origem,
        "especies": chunk.especies,
        "farmacos": chunk.farmacos,
        "produto": chunk.produto,
        "fabricante": chunk.fabricante,
        "tipo_chunk": chunk.tipo_chunk,
        "tokens": chunk.tokens,
        "texto_hash": chunk.texto_hash,
        "texto": chunk.texto,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entrada", required=True, type=Path, help="JSONL produzido por etl/extract_bula.py"
    )
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Caminho do PDF de origem (identifica a entrada no manifesto)",
    )
    parser.add_argument("--manifesto", type=Path, default=CAMINHO_MANIFESTO_PADRAO)
    parser.add_argument(
        "--saida", type=Path, default=None, help="Arquivo JSONL de saída; default: stdout"
    )
    args = parser.parse_args(argv)

    manifesto = carregar_manifesto(args.manifesto)
    entrada = buscar_entrada_manifesto(manifesto, args.source)
    secoes = _ler_secoes(args.entrada)
    chunks = segmentar(secoes, entrada.produto, entrada)

    linhas = [json.dumps(_serializar_chunk(c), ensure_ascii=False) for c in chunks]

    if args.saida:
        args.saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        logger.info("saida_gravada", caminho=str(args.saida), linhas=len(linhas))
    else:
        for linha in linhas:
            print(linha)  # noqa: T201 — saída de dados do CLI, não log de depuração

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
