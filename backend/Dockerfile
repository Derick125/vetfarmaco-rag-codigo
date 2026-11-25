FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    NLTK_DATA=/usr/share/nltk_data \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app

# Dependências primeiro (camada em cache); só as de produção, travadas no uv.lock.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Dados do NLTK embarcados na imagem: o lifespan não depende de rede no cold start.
RUN python -m nltk.downloader -d /usr/share/nltk_data stopwords rslp

# Código e tudo o que o lifespan carrega:
#   app/                       API e pipeline RAG
#   etl/                       importado por retriever_lexical (stemmer/stopwords)
#   etl/vocabulario/*.yaml     vocabulário do roteador
#   data/bm25_index/           índice lexical
#   data/mapa_capitulos.json   mapa de capítulos
COPY app ./app
COPY etl ./etl
COPY data/bm25_index ./data/bm25_index
COPY data/mapa_capitulos.json ./data/mapa_capitulos.json

# Falha o build (não o runtime) se o índice não estiver na imagem.
RUN test -f data/bm25_index/params.index.json && test -f data/mapa_capitulos.json

RUN useradd --system --uid 1001 appuser
USER appuser

# Cloud Run injeta $PORT; 8080 é só o padrão para rodar localmente.
ENV PORT=8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
