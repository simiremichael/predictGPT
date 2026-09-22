"""Exceptions for the AI module."""
from __future__ import annotations

from typing import Any


class AIError(Exception):
    """Base exception for all AI-related errors."""

    def __init__(self, message: str = "", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class AIAuthenticationError(AIError):
    """Raised when AI provider credentials are missing or invalid."""


class AIRateLimitError(AIError):
    """Raised when the AI provider rate-limit has been exceeded."""

    def __init__(
        self,
        message: str = "AI rate limit exceeded",
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.retry_after = retry_after


class AIProviderError(AIError):
    """Raised when the AI provider is unavailable or returns an error."""


class ExtractionError(AIError):
    """Raised when AI extraction of structured data fails."""
