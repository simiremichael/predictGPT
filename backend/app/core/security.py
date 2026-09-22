"""Security helpers: API-key auth for admin routes, CORS setup."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from core.config import get_settings

api_key_header = APIKeyHeader(name="X-Admin-Api-Key", auto_error=False)


async def verify_admin_api_key(
    api_key: Annotated[str | None, Security(api_key_header)] = None,
) -> str:
    """Validate the admin API key for protected admin endpoints.

    Returns the valid key, or raises an appropriate HTTP error:
      * 503 if no admin key is configured (server misconfiguration)
      * 403 if the provided key is wrong or missing
    """
    settings = get_settings()
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key is not configured on this server.",
        )
    if not api_key or api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key.",
        )
    return api_key
