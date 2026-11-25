from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.consulta import router as consulta_router
from app.api.vocabulario import router as vocabulario_router
from app.config import get_settings
from app.rag.recuperacao import fechar_pool
from app.rag.retriever_lexical import carregar_indice
from app.rag.roteador import CAMINHO_VOCABULARIO_PADRAO, carregar_vocabulario
from app.telemetry.logging import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Índice BM25 (docs/RAG_SPEC.md §3.2): carregado uma vez na
    # inicialização do serviço, não a cada consulta.
    app.state.bm25_index = carregar_indice()
    app.state.vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO_PADRAO)
    yield
    fechar_pool()


app = FastAPI(title="VetFarmaco RAG API", lifespan=lifespan)
app.include_router(consulta_router)
app.include_router(vocabulario_router)


@app.get("/health")
async def health() -> dict[str, str | None]:
    # `modelo_id` deixa o app gravar a versão do modelo na telemetria no envio,
    # mesmo quando a consulta falha antes do evento `fim` (TCC §4.7).
    return {"status": "ok", "modelo_id": get_settings().modelo_id}
