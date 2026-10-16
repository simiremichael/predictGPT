"""Security helpers: JWT authentication, password hashing, API-key auth."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.config import get_settings

api_key_header = APIKeyHeader(name="X-Admin-Api-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except (ValueError, TypeError):
        return False


def create_access_token(email: str, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token for the given email."""
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(UTC) + expires_delta
    payload = {
        "sub": email,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)] = None,
) -> str | None:
    """Extract and validate the JWT token, returning the user's email.

    Returns None when no token is present (anonymous user).
    Raises HTTPException on invalid/expired tokens.
    """
    if credentials is None:
        return None
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except JWTError:
        return None


async def get_current_user_required(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)] = None,
) -> str:
    """Require a valid JWT token. Raises 401 if missing or invalid."""
    email = await get_current_user(credentials)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return email


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
