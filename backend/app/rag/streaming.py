"""Streaming validado da resposta (docs/RAG_SPEC.md §7.1).

O modelo devolve um JSON em streaming. **Nenhum token bruto vai ao cliente**: o
texto é acumulado aqui e só viram eventos objetos já completos e já validados.

- `paragrafo`: emitido quando o objeto do parágrafo fecha no JSON **e** passa nas
  checagens que dependem só do parágrafo (citação real — checagem 1; dose e
  espécie com lastro — checagens 3 e 4). Parágrafo reprovado nunca é emitido.
- `citacoes`, `alerta` e `fim`: só depois do stream inteiro e do `validar` completo
  (trecho literal, interação com lastro, coerência do alerta, nível de confiança).
  Se a interação sem lastro move o alerta para um parágrafo "Inferência não
  documentada:", esse parágrafo sai como `paragrafo` nesse momento, antes de `fim`.
- `erro`: aborta a consulta. O cliente descarta tudo o que recebeu antes.

Três tempos, medidos separadamente a partir de `inicio` (recebimento da requisição):
primeiro token do modelo, primeiro parágrafo validado e total.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.rag.gerador import Trecho
from app.rag.validador import chunk_ids_fantasmas, validar, validar_paragrafo
from etl.chunk import Vocabulario

logger = structlog.get_logger()


@dataclass
class Evento:
    nome: str
    dados: dict[str, Any]


@dataclass
class Tempos:
    ms_ate_primeiro_evento: float | None = None
    ms_ate_primeiro_token: float | None = None
    ms_ate_primeiro_paragrafo_validado: float | None = None
    ms_total: float | None = None


@dataclass
class Uso:
    input_tokens: int | None = None
    output_tokens: int | None = None
    thought_tokens: int | None = None


@dataclass
class Telemetria:
    tempos: Tempos = field(default_factory=Tempos)
    uso: Uso = field(default_factory=Uso)
    eventos_validador: list[str] = field(default_factory=list)
    paragrafos_emitidos: int = 0
    citacoes_validadas: int = 0
    citacoes_fantasma: int = 0
    desfecho: str = "ok"


class ExtratorParagrafos:
    """Devolve cada objeto de `paragrafos` assim que ele fecha, no JSON parcial.

    Máquina de estados caractere a caractere (aspas, escapes e profundidade), então
    chaves e colchetes dentro de strings não confundem. Só o array `paragrafos` do
    objeto raiz interessa; o resto do JSON é lido apenas para manter a profundidade.
    """

    def __init__(self) -> None:
        self._texto = ""
        self._pos = 0
        self._profundidade = 0
        self._em_string = False
        self._escape = False
        self._string = ""
        self._espera_chave = False
        self._ultima_chave: str | None = None
        self._chave_do_array: str | None = None
        self._inicio_objeto: int | None = None

    def alimentar(self, trecho: str) -> list[dict[str, Any]]:
        self._texto += trecho
        prontos: list[dict[str, Any]] = []
        while self._pos < len(self._texto):
            c = self._texto[self._pos]
            if self._em_string:
                self._ler_string(c)
            else:
                pronto = self._ler_estrutura(c)
                if pronto is not None:
                    prontos.append(pronto)
            self._pos += 1
        return prontos

    def _ler_string(self, c: str) -> None:
        if self._escape:
            self._escape = False
            self._string += c
        elif c == "\\":
            self._escape = True
            self._string += c
        elif c == '"':
            self._em_string = False
            if self._profundidade == 1 and self._espera_chave:
                try:
                    self._ultima_chave = json.loads(f'"{self._string}"')
                except json.JSONDecodeError:
                    self._ultima_chave = None
                self._espera_chave = False
        else:
            self._string += c

    def _ler_estrutura(self, c: str) -> dict[str, Any] | None:
        if c == '"':
            self._em_string = True
            self._string = ""
        elif c in "{[":
            self._profundidade += 1
            if self._profundidade == 1:
                self._espera_chave = True
            elif self._profundidade == 2 and c == "[":
                self._chave_do_array = self._ultima_chave
            elif self._profundidade == 3 and c == "{" and self._chave_do_array == "paragrafos":
                self._inicio_objeto = self._pos
        elif c in "}]":
            pronto = None
            if self._profundidade == 3 and c == "}" and self._inicio_objeto is not None:
                bruto = self._texto[self._inicio_objeto : self._pos + 1]
                self._inicio_objeto = None
                try:
                    objeto = json.loads(bruto)
                except json.JSONDecodeError:
                    objeto = None
                if isinstance(objeto, dict):
                    pronto = objeto
            self._profundidade -= 1
            if self._profundidade == 1:
                self._chave_do_array = None
            return pronto
        elif c == "," and self._profundidade == 1:
            self._espera_chave = True
        elif c == ":" and self._profundidade == 1:
            self._espera_chave = False
        return None


def custo_usd(uso: Uso, preco_in_usd: float | None, preco_out_usd: float | None) -> float | None:
    """`(input/1e6 × PRECO_IN) + ((output + thought)/1e6 × PRECO_OUT)` — os tokens de
    raciocínio contam como saída (RAG_SPEC.md §8). `None` se algum preço ou contagem
    falta: custo desconhecido não é custo zero."""
    if preco_in_usd is None or preco_out_usd is None or uso.input_tokens is None:
        return None
    saida = (uso.output_tokens or 0) + (uso.thought_tokens or 0)
    return uso.input_tokens / 1e6 * preco_in_usd + saida / 1e6 * preco_out_usd


def _citacoes_do_cliente(
    resposta: dict[str, Any], por_id: dict[str, Trecho]
) -> list[dict[str, Any]]:
    saida = []
    for indice, citacao in enumerate(resposta.get("citacoes", []), start=1):
        trecho = por_id[citacao["chunk_id"]]
        saida.append(
            {
                "chunkId": trecho.chunk_id,
                "indice": indice,
                "trecho": citacao.get("trecho", ""),
                "fonte": trecho.referencia,
                "capitulo": trecho.capitulo,
                "pagina": trecho.pagina,
            }
        )
    return saida


def _paragrafo_evento(indice: int, paragrafo: dict[str, Any]) -> Evento:
    return Evento(
        "paragrafo",
        {
            "indice": indice,
            "texto": paragrafo.get("texto", ""),
            "chunkIds": list(paragrafo.get("chunk_ids", [])),
        },
    )


async def emitir_resposta(
    stream: AsyncIterator[Any],
    trechos: list[Trecho],
    vocabulario: Vocabulario,
    *,
    inicio: float,
    modelo: str,
    thinking_level: str | None = None,
    preco_in_usd: float | None = None,
    preco_out_usd: float | None = None,
    telemetria: Telemetria | None = None,
) -> AsyncIterator[Evento]:
    """Consome o stream do modelo e emite os eventos validados (ver o módulo).

    `inicio` é um `time.perf_counter()` do recebimento da requisição. `stream` é o
    iterador de `gerar_stream` (chunks do SDK com `.text` e `.usage_metadata`).
    Preenche `telemetria`, se dada, mesmo quando termina em erro.
    """
    tel = telemetria if telemetria is not None else Telemetria()
    por_id = {t.chunk_id: t for t in trechos}
    extrator = ExtratorParagrafos()
    partes: list[str] = []
    emitidos: list[dict[str, Any]] = []

    def agora() -> float:
        return (time.perf_counter() - inicio) * 1000

    def erro(codigo: str, mensagem: str) -> Evento:
        tel.desfecho = codigo
        tel.tempos.ms_total = agora()
        return Evento("erro", {"codigo": codigo, "mensagem": mensagem})

    try:
        async for chunk in stream:
            if tel.tempos.ms_ate_primeiro_evento is None:
                tel.tempos.ms_ate_primeiro_evento = agora()
            uso = getattr(chunk, "usage_metadata", None)
            if uso is not None:
                tel.uso = Uso(
                    getattr(uso, "prompt_token_count", None),
                    getattr(uso, "candidates_token_count", None),
                    getattr(uso, "thoughts_token_count", None),
                )
            texto = getattr(chunk, "text", None)
            if not texto:
                continue
            if tel.tempos.ms_ate_primeiro_token is None:
                tel.tempos.ms_ate_primeiro_token = agora()
            partes.append(texto)

            for paragrafo in extrator.alimentar(texto):
                fantasmas = chunk_ids_fantasmas(paragrafo, por_id)
                if fantasmas:
                    tel.citacoes_fantasma += len(fantasmas)
                    tel.eventos_validador.append(f"citacao_fantasma: {', '.join(fantasmas)}")
                    logger.error("citacao_fantasma", chunk_ids=fantasmas)
                    yield erro("citacao_fantasma", "A resposta citou trecho não recuperado.")
                    return
                motivo, _ = validar_paragrafo(paragrafo, por_id, vocabulario)
                if motivo is not None:
                    tel.eventos_validador.append(f"paragrafo_nao_emitido: {motivo}")
                    continue
                emitidos.append(paragrafo)
                if tel.tempos.ms_ate_primeiro_paragrafo_validado is None:
                    tel.tempos.ms_ate_primeiro_paragrafo_validado = agora()
                yield _paragrafo_evento(len(emitidos), paragrafo)
    except Exception:
        logger.exception("falha_geracao")
        yield erro("falha_geracao", "Falha ao gerar a resposta.")
        return

    try:
        resposta = json.loads("".join(partes))
    except json.JSONDecodeError:
        yield erro("resposta_invalida", "A resposta do modelo não pôde ser lida.")
        return
    if not isinstance(resposta, dict):
        yield erro("resposta_invalida", "A resposta do modelo não pôde ser lida.")
        return

    resultado = validar(resposta, trechos, vocabulario)
    tel.eventos_validador.extend(resultado.eventos)
    if resultado.descartada or resultado.resposta is None:
        tel.citacoes_fantasma += sum(
            1 for e in resultado.eventos if e.startswith("citacao_fantasma")
        )
        codigo = (
            "citacao_fantasma"
            if any(e.startswith("citacao_fantasma") for e in resultado.eventos)
            else "resposta_invalida"
        )
        yield erro(codigo, "A resposta foi descartada pela validação.")
        return

    validada = resultado.resposta
    mantidos = validada.get("paragrafos", [])
    if mantidos[: len(emitidos)] != emitidos:
        # O que já saiu tem de ser prefixo do que a validação completa mantém.
        logger.error("streaming_inconsistente_com_validacao")
        yield erro("inconsistencia_validador", "Falha interna de validação.")
        return
    for paragrafo in mantidos[len(emitidos) :]:
        emitidos.append(paragrafo)
        if tel.tempos.ms_ate_primeiro_paragrafo_validado is None:
            tel.tempos.ms_ate_primeiro_paragrafo_validado = agora()
        yield _paragrafo_evento(len(emitidos), paragrafo)
    tel.paragrafos_emitidos = len(emitidos)

    citacoes = _citacoes_do_cliente(validada, por_id)
    tel.citacoes_validadas = len(citacoes)
    yield Evento("citacoes", {"citacoes": citacoes})

    alerta = validada.get("alerta_seguranca")
    if alerta is not None:
        yield Evento(
            "alerta",
            {
                "severidade": alerta.get("severidade"),
                "texto": alerta.get("texto", ""),
                "chunkIds": list(alerta.get("chunk_ids", [])),
            },
        )

    tel.tempos.ms_total = agora()
    custo = custo_usd(tel.uso, preco_in_usd, preco_out_usd)
    yield Evento(
        "fim",
        {
            "nivelConfianca": validada.get("nivel_confianca"),
            "modelo": modelo,
            "thinkingLevel": thinking_level,
            "usage": {
                "inputTokens": tel.uso.input_tokens,
                "outputTokens": tel.uso.output_tokens,
                "thoughtTokens": tel.uso.thought_tokens,
            },
            "custoUsd": custo,
            "tempos": {
                "msPrimeiroToken": tel.tempos.ms_ate_primeiro_token,
                "msPrimeiroParagrafoValidado": tel.tempos.ms_ate_primeiro_paragrafo_validado,
                "msTotal": tel.tempos.ms_total,
            },
        },
    )
