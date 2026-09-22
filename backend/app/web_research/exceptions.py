"""Exceptions for the web research module."""
from __future__ import annotations

from typing import Any


class WebResearchError(Exception):
    """Base exception for all web research errors."""

    def __init__(self, message: str = "", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class SearchProviderError(WebResearchError):
    """Raised when the search provider is unavailable or returns an error."""


class SearchRateLimitError(WebResearchError):
    """Raised when the search provider rate-limit has been exceeded."""

    def __init__(
        self,
        message: str = "Search rate limit exceeded",
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.retry_after = retry_after


class SourceRetrievalError(WebResearchError):
    """Raised when a source URL cannot be fetched or parsed."""


class ExtractionError(WebResearchError):
    """Raised when AI extraction of evidence fails."""
