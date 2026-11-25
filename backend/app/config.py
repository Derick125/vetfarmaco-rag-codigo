from functools import lru_cache

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da aplicação, lida de variáveis de ambiente (TCC §4.7)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    modelo_id: str | None = None
    gemini_api_key: str | None = None
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    app_api_key: str | None = None
    preco_in_usd: float | None = None
    preco_out_usd: float | None = None

    @field_validator("preco_in_usd", "preco_out_usd", mode="before")
    @classmethod
    def _vazio_vira_none(cls, valor: object) -> object:
        """`.env` com a chave presente mas sem valor (`PRECO_IN_USD=`) deve
        equivaler a "não configurado", não a um erro de parsing de float."""
        return valor or None

    # Connection string direta do Postgres (Supabase → Project Settings →
    # Database → Connection string). Distinta de `supabase_url` (a API
    # REST/PostgREST): migrações e o retriever vetorial (docs/DATABASE.md
    # §3, `set local hnsw.ef_search`) precisam de uma conexão SQL direta.
    database_url: str | None = None

    # Hiperparâmetros do BM25 (docs/RAG_SPEC.md §3.2) — valores iniciais do
    # TCC §4.2, ajustáveis sem alterar código.
    bm25_k1: float = 1.2
    bm25_b: float = 0.75

    @field_validator("bm25_k1", "bm25_b", mode="before")
    @classmethod
    def _vazio_usa_default(cls, valor: object, info: ValidationInfo) -> object:
        """`BM25_K1=`/`BM25_B=` vazias no `.env` devem usar o default do
        campo, em vez de falhar o parsing de float (mesmo problema de
        `_vazio_vira_none` acima, mas aqui o campo não é opcional)."""
        if valor in (None, ""):
            return cls.model_fields[info.field_name].default
        return valor


@lru_cache
def get_settings() -> Settings:
    return Settings()
