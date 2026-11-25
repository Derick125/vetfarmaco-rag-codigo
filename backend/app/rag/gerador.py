"""Geração da resposta com Gemini (docs/RAG_SPEC.md §4 a §6).

Monta o contexto a partir dos chunks recuperados, chama o modelo em
streaming com saída JSON restrita ao schema do §6 e devolve a resposta
parseada. O nível de raciocínio é sempre explícito
(`ThinkingConfig.thinking_level`, verificado na versão instalada do
`google-genai` — ver `_thinking_config`); o identificador do modelo vem de
configuração, nunca hard-coded (CLAUDE.md regra 5).

Este módulo **não** faz a validação pós-geração do §7 (citações reais,
trecho literal, dose com lastro) — ela é uma etapa própria, obrigatória
antes de qualquer resposta chegar ao usuário.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from html import escape
from typing import Any

import psycopg
from google import genai
from google.genai import types

from app.rag.roteador import NivelRaciocinio

SYSTEM_INSTRUCTION = """\
Você é um assistente de consulta a literatura de farmacologia veterinária,
para cães e gatos.

REGRAS ABSOLUTAS
1. Responda usando EXCLUSIVAMENTE os trechos fornecidos em <contexto>.
2. Nunca use conhecimento próprio. Se os trechos não sustentarem a resposta,
   devolva nivel_confianca = "sem_evidencia" e deixe paragrafos vazio.
3. Nunca informe uma dose que não apareça literalmente nos trechos.
4. Cada parágrafo deve listar os chunk_id que o sustentam. Parágrafo sem
   chunk_id é proibido, salvo transição puramente conectiva.
5. Se houver contraindicação, toxicidade espécie-específica ou interação
   documentada nos trechos, preencha alerta_seguranca.
6. Não invente chunk_id. Use apenas os que aparecem em <contexto>.
7. Escreva em português do Brasil, para um médico veterinário. Sem saudações,
   sem hedging genérico, sem repetir a pergunta.
8. Quando o contexto trouxer evidências divergentes sobre a mesma questão,
   apresente todas com suas citações e declare a divergência; não escolha uma.
9. Quando o contexto trouxer premissas relacionadas mas não a afirmação
   pedida, apresente as premissas citadas e declare explicitamente que a
   afirmação específica não consta dos documentos recuperados.
10. Nunca transfira evidência de um fármaco para outro, mesmo da mesma classe.
11. Não use dose documentada para uma indicação como resposta a outra
    indicação.
12. Quando a evidência citada vier de trecho com origem="humana", sinalize
    que se trata de bula de uso humano.
13. Nunca atribua espécie, indicação, via ou unidade a um valor que o próprio
    trecho não associe explicitamente. Em tabelas cujo cabeçalho não esteja
    presente no trecho, trate os valores como não interpretáveis e declare
    isso.
14. O campo alerta_seguranca só pode conter riscos afirmados literalmente nos
    trechos citados. Se você inferir um risco a partir de premissas,
    apresente-o em parágrafo próprio, iniciado por "Inferência não
    documentada:", e nunca no alerta.
15. Ao declarar que uma dose não se aplica ou não consta para uma espécie, use
    a expressão "não consta dos documentos recuperados".

FORMATO DO CONTEXTO
Cada trecho chega como <trecho chunk_id="..." referencia="..." secao="..."
origem="...">. Os atributos secao e origem só existem em trechos de bula;
trechos de livro trazem apenas chunk_id e referencia (e capitulo/pagina
quando conhecidos).
"""

SCHEMA_RESPOSTA: dict[str, Any] = {
    "type": "object",
    "required": ["paragrafos", "citacoes", "nivel_confianca"],
    "properties": {
        "paragrafos": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["texto", "chunk_ids"],
                "properties": {
                    "texto": {"type": "string"},
                    "chunk_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "citacoes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["chunk_id", "trecho"],
                "properties": {
                    "chunk_id": {"type": "string"},
                    "trecho": {"type": "string"},
                    "fonte": {"type": "string"},
                    "pagina": {"type": "integer"},
                },
            },
        },
        "nivel_confianca": {
            "type": "string",
            "enum": ["alta", "media", "baixa", "sem_evidencia"],
        },
        "alerta_seguranca": {
            "type": "object",
            "properties": {
                "severidade": {"type": "string", "enum": ["contraindicacao", "cautela"]},
                "texto": {"type": "string"},
                "chunk_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

# `minimal` não é suportado (RAG_SPEC.md §4); `medium` (o default do modelo)
# nunca é escolhido por omissão — só os dois níveis do roteador existem.
_NIVEIS: dict[str, types.ThinkingLevel] = {
    "low": types.ThinkingLevel.LOW,
    "high": types.ThinkingLevel.HIGH,
}


@dataclass(frozen=True)
class Trecho:
    """Chunk recuperado, com os metadados que o modelo precisa ver."""

    chunk_id: str
    texto: str
    referencia: str
    secao: str | None = None
    origem: str | None = None
    capitulo: str | None = None
    pagina: int | None = None
    # Metadado do ETL (vocabulário controlado); não vai ao modelo, serve à
    # validação pós-geração ("espécie com lastro").
    especies: list[str] = field(default_factory=list)


@dataclass
class Geracao:
    resposta: dict[str, Any] | None
    texto_bruto: str
    modelo: str
    thinking_level: str
    ms_ate_primeiro_evento: float | None
    ms_total: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    thought_tokens: int | None = None
    erro_parse: str | None = None
    chunk_ids_contexto: list[str] = field(default_factory=list)


def carregar_trechos(conn: psycopg.Connection, chunk_ids: list[str]) -> list[Trecho]:
    """Busca os metadados completos dos chunks, preservando a ordem de `chunk_ids`
    (a ordem da fusão RRF). `chunk_id` sem linha no banco é descartado."""
    if not chunk_ids:
        return []
    cur = conn.execute(
        """
        select c.chunk_id, c.texto, d.referencia, c.secao, c.origem, c.capitulo,
               c.pagina, c.especies
        from chunk c
        join documento d on d.id = c.documento_id
        where c.chunk_id = any(%s)
        """,
        (chunk_ids,),
    )
    por_id = {
        linha[0]: Trecho(
            chunk_id=linha[0],
            texto=linha[1],
            referencia=linha[2],
            secao=linha[3],
            origem=linha[4],
            capitulo=linha[5],
            pagina=linha[6],
            especies=list(linha[7] or []),
        )
        for linha in cur.fetchall()
    }
    return [por_id[cid] for cid in chunk_ids if cid in por_id]


def _atributos(trecho: Trecho) -> str:
    # origem, secao e referencia sempre que existirem (nulo = omitido: só
    # bula tem secao/origem, só livro tem capitulo — DATABASE.md §2).
    campos = [
        ("chunk_id", trecho.chunk_id),
        ("referencia", trecho.referencia),
        ("secao", trecho.secao),
        ("origem", trecho.origem),
        ("capitulo", trecho.capitulo),
        ("pagina", trecho.pagina),
    ]
    return " ".join(f'{nome}="{escape(str(v), quote=True)}"' for nome, v in campos if v is not None)


def montar_prompt(pergunta: str, trechos: list[Trecho]) -> str:
    blocos = []
    for trecho in trechos:
        # O texto do chunk vai literal (doses, "<", ">"); só se neutralizam
        # as tags de fechamento, para o corpus não escapar do contexto.
        texto = trecho.texto.replace("</trecho>", "<\\/trecho>").replace(
            "</contexto>", "<\\/contexto>"
        )
        blocos.append(f"<trecho {_atributos(trecho)}>\n{texto}\n</trecho>")
    contexto = "\n".join(blocos)
    return f"<contexto>\n{contexto}\n</contexto>\n\n<pergunta>\n{pergunta}\n</pergunta>"


def _thinking_config(nivel: NivelRaciocinio) -> types.ThinkingConfig:
    # Atributo verificado em runtime (google-genai 2.23.0):
    # `ThinkingConfig.thinking_level: Optional[ThinkingLevel]`, com
    # `ThinkingLevel` ∈ {MINIMAL, LOW, MEDIUM, HIGH}.
    try:
        return types.ThinkingConfig(thinking_level=_NIVEIS[nivel])
    except KeyError:
        raise ValueError(f"nível de raciocínio inválido: {nivel!r} (use 'low' ou 'high')") from None


def _config(nivel: NivelRaciocinio) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        thinking_config=_thinking_config(nivel),
        response_mime_type="application/json",
        response_json_schema=SCHEMA_RESPOSTA,
    )


async def gerar_stream(
    client: genai.Client,
    modelo_id: str,
    pergunta: str,
    trechos: list[Trecho],
    nivel: NivelRaciocinio,
) -> AsyncIterator[types.GenerateContentResponse]:
    """Chunks crus do SDK, na ordem em que chegam."""
    async for chunk in await client.aio.models.generate_content_stream(
        model=modelo_id, contents=montar_prompt(pergunta, trechos), config=_config(nivel)
    ):
        yield chunk


async def gerar(
    client: genai.Client,
    modelo_id: str,
    pergunta: str,
    trechos: list[Trecho],
    nivel: NivelRaciocinio,
) -> Geracao:
    """Consome o stream inteiro e devolve a resposta parseada + telemetria do §8."""
    inicio = time.perf_counter()
    ms_primeiro: float | None = None
    partes: list[str] = []
    uso = None

    async for chunk in gerar_stream(client, modelo_id, pergunta, trechos, nivel):
        if ms_primeiro is None:
            ms_primeiro = (time.perf_counter() - inicio) * 1000
        if chunk.text:
            partes.append(chunk.text)
        if chunk.usage_metadata is not None:
            uso = chunk.usage_metadata

    bruto = "".join(partes)
    resposta: dict[str, Any] | None = None
    erro: str | None = None
    try:
        resposta = json.loads(bruto)
    except json.JSONDecodeError as e:
        erro = f"JSON inválido: {e}"

    return Geracao(
        resposta=resposta,
        texto_bruto=bruto,
        modelo=modelo_id,
        thinking_level=nivel,
        ms_ate_primeiro_evento=ms_primeiro,
        ms_total=(time.perf_counter() - inicio) * 1000,
        input_tokens=getattr(uso, "prompt_token_count", None),
        output_tokens=getattr(uso, "candidates_token_count", None),
        thought_tokens=getattr(uso, "thoughts_token_count", None),
        erro_parse=erro,
        chunk_ids_contexto=[t.chunk_id for t in trechos],
    )
