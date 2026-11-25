"""Autenticação por `X-API-Key` (docs/ARCHITECTURE.md §5, CLAUDE.md regra 4)."""

import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def exigir_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """401 sem chave ou com chave errada; 503 se `APP_API_KEY` não está configurada
    (o serviço nunca fica aberto por falta de configuração)."""
    esperada = get_settings().app_api_key
    if not esperada:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Autenticação não configurada.")
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode("utf-8"), esperada.encode("utf-8")
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chave de API inválida.")
