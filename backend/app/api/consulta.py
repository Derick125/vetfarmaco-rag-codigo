"""POST /consulta — resposta por SSE (docs/RAG_SPEC.md §7.1, FRONTEND_SPEC.md §6).

Eventos, nesta ordem: `recuperacao`, `paragrafo`*, `citacoes`, `alerta`?, `fim` — ou
`erro` em qualquer ponto. Nunca há evento com token bruto do modelo.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.api.deps import exigir_api_key
from app.config import Settings, get_settings
from app.rag.composicao import COMORBIDADES, Especie, compor_consulta
from app.rag.gerador import gerar_stream
from app.rag.recuperacao import Recuperacao, obter_cliente, obter_pool, recuperar_paralelo
from app.rag.roteador import rotear
from app.rag.streaming import Evento, Telemetria, custo_usd, emitir_resposta

logger = structlog.get_logger()
router = APIRouter()

Comorbidade = Literal[tuple(COMORBIDADES)]  # type: ignore[valid-type]


class ConsultaRequest(BaseModel):
    # Campos estruturados (FRONTEND_SPEC.md §9): é neles que PII nunca entra
    # (CLAUDE.md regra 3). `pergunta` é texto livre, já sanitizado no cliente.
    pergunta: str = Field(min_length=3, max_length=4000)
    especie: Especie | None = None
    peso_kg: float | None = Field(default=None, gt=0, le=200)
    farmacos: list[str] = Field(default_factory=list, max_length=10)
    comorbidades: list[Comorbidade] = Field(default_factory=list, max_length=len(COMORBIDADES))
    complexidade_dica: Literal["alta", "baixa"] | None = None


def _sse(evento: Evento) -> dict[str, str]:
    return {"event": evento.nome, "data": json.dumps(evento.dados, ensure_ascii=False)}


def _farmacos_canonicos(informados: list[str], vocabulario: Any) -> list[str]:
    """Nomes canônicos do dicionário, sem repetição e na ordem enviada. Fármaco fora do
    dicionário é 422: o campo é estruturado para não carregar texto livre (PII)."""
    por_nome = {t.nome.casefold(): t.nome for t in vocabulario.farmacos}
    saida: list[str] = []
    for nome in informados:
        canonico = por_nome.get(nome.strip().casefold())
        if canonico is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Fármaco fora do dicionário controlado."
            )
        if canonico not in saida:
            saida.append(canonico)
    return saida


async def _recuperar(settings: Settings, indice_bm25: Any, pergunta: str) -> Recuperacao:
    pool = await asyncio.to_thread(obter_pool, settings.database_url or "")
    return await recuperar_paralelo(
        pool, obter_cliente(settings.gemini_api_key or ""), indice_bm25, pergunta
    )


@router.post("/consulta", dependencies=[Depends(exigir_api_key)])
async def consulta(corpo: ConsultaRequest, request: Request) -> EventSourceResponse:
    settings = get_settings()
    faltando = [
        nome
        for nome, valor in (
            ("GEMINI_API_KEY", settings.gemini_api_key),
            ("DATABASE_URL", settings.database_url),
            ("MODELO_ID", settings.modelo_id),
        )
        if not valor
    ]
    if faltando:
        logger.error("configuracao_ausente", variaveis=faltando)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Serviço não configurado.")

    inicio = time.perf_counter()
    consulta_id = uuid.uuid4().hex
    modelo_id = settings.modelo_id or ""
    vocabulario = request.app.state.vocabulario
    indice_bm25 = request.app.state.bm25_index
    farmacos = _farmacos_canonicos(corpo.farmacos, vocabulario)
    texto = compor_consulta(
        corpo.pergunta,
        especie=corpo.especie,
        peso_kg=corpo.peso_kg,
        farmacos=farmacos,
        comorbidades=list(dict.fromkeys(corpo.comorbidades)),
    )
    client = obter_cliente(settings.gemini_api_key or "")

    async def eventos() -> AsyncIterator[dict[str, str]]:
        tel = Telemetria()
        rec: Recuperacao | None = None
        nivel: str | None = None
        try:
            try:
                # recuperação: só a pergunta, sem filtro (RAG_SPEC.md §7.1)
                rec = await _recuperar(settings, indice_bm25, corpo.pergunta)
            except Exception:
                logger.exception("falha_recuperacao", consulta_id=consulta_id)
                tel.desfecho = "falha_recuperacao"
                yield _sse(
                    Evento("erro", {"codigo": "falha_recuperacao", "mensagem": "Falha na busca."})
                )
                return
            roteamento = rotear(
                texto,
                vocabulario,
                comorbidade_marcada=bool(corpo.comorbidades),
                complexidade_dica=corpo.complexidade_dica,
            )
            nivel = roteamento.nivel
            yield _sse(
                Evento(
                    "recuperacao",
                    {
                        "chunks": len(rec.trechos),
                        "ms": (time.perf_counter() - inicio) * 1000,
                        "thinkingLevel": nivel,
                    },
                )
            )

            stream = gerar_stream(client, modelo_id, texto, rec.trechos, roteamento.nivel)
            async for evento in emitir_resposta(
                stream,
                rec.trechos,
                vocabulario,
                inicio=inicio,
                modelo=modelo_id,
                thinking_level=nivel,
                preco_in_usd=settings.preco_in_usd,
                preco_out_usd=settings.preco_out_usd,
                telemetria=tel,
            ):
                yield _sse(evento)
        finally:
            if tel.tempos.ms_total is None:
                tel.tempos.ms_total = (time.perf_counter() - inicio) * 1000
            _registrar(consulta_id, modelo_id, nivel, rec, tel, settings)

    return EventSourceResponse(eventos())


def _registrar(
    consulta_id: str,
    modelo_id: str,
    nivel: str | None,
    rec: Recuperacao | None,
    tel: Telemetria,
    settings: Settings,
) -> None:
    logger.info(
        "consulta_concluida",
        consulta_id=consulta_id,
        modelo=modelo_id,  # TCC §4.7
        thinking_level=nivel,
        desfecho=tel.desfecho,
        ms_conexao=rec.ms_conexao if rec else None,
        ms_embedding=rec.ms_embedding if rec else None,
        ms_busca_vetorial=rec.ms_busca_vetorial if rec else None,
        ms_busca_lexical=rec.ms_busca_lexical if rec else None,
        ms_fusao=rec.ms_fusao if rec else None,
        ms_carga_trechos=rec.ms_carga_trechos if rec else None,
        ms_recuperacao=rec.ms_total if rec else None,
        ms_ate_primeiro_evento=tel.tempos.ms_ate_primeiro_evento,
        ms_ate_primeiro_token=tel.tempos.ms_ate_primeiro_token,
        ms_ate_primeiro_paragrafo_validado=tel.tempos.ms_ate_primeiro_paragrafo_validado,
        ms_total=tel.tempos.ms_total,
        input_tokens=tel.uso.input_tokens,
        output_tokens=tel.uso.output_tokens,
        thought_tokens=tel.uso.thought_tokens,
        custo_usd=custo_usd(tel.uso, settings.preco_in_usd, settings.preco_out_usd),
        chunks_recuperados=len(rec.trechos) if rec else 0,
        paragrafos_emitidos=tel.paragrafos_emitidos,
        citacoes_validadas=tel.citacoes_validadas,
        citacoes_fantasma=tel.citacoes_fantasma,
        eventos_validador=tel.eventos_validador,
    )
