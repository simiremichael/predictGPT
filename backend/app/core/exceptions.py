"""Normalized exception hierarchy for the football data provider layer.

These exceptions are the only ones that may propagate above the provider
abstraction.  Provider-specific errors are caught and re-raised as one of
the types defined here so the rest of the application never sees
``RequestError``, ``httpx.HTTPStatusError`` etc.
"""
from __future__ import annotations

from typing import Any


class FootballDataError(Exception):
    """Base exception for all football-data related errors."""

    def __init__(self, message: str = "", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class ProviderConfigurationError(FootballDataError):
    """Raised when the provider is not configured or misconfigured."""


class ProviderAuthenticationError(FootballDataError):
    """Raised when API credentials are missing or invalid."""


class ProviderNotFoundError(FootballDataError):
    """Raised when a requested resource (fixture, team, etc.) does not exist."""


class ProviderRateLimitError(FootballDataError):
    """Raised when the provider rate-limit has been exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.retry_after = retry_after


class ProviderUnavailableError(FootballDataError):
    """Raised when the provider is unreachable or returns a server error."""


class ProviderValidationError(FootballDataError):
    """Raised when the provider response cannot be parsed/validated."""

    def __init__(self, message: str = "", *, field: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.field = field
