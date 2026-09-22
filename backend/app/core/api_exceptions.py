"""Application-level exceptions for the API layer.

These exceptions carry a machine-readable error code and HTTP status, so the
global error handler can produce standardized ``ErrorResponse`` payloads
without leaking internal stack traces.
"""
from __future__ import annotations

from typing import Any


class APIError(Exception):
    """Base API exception with error code and HTTP status."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str = "",
        *,
        error_code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message or self.__class__.__name__
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class MatchNotFoundError(APIError):
    status_code = 404
    error_code = "MATCH_NOT_FOUND"


class PredictionNotFoundError(APIError):
    status_code = 404
    error_code = "PREDICTION_NOT_FOUND"


class TeamNotFoundError(APIError):
    status_code = 404
    error_code = "TEAM_NOT_FOUND"


class LeagueNotFoundError(APIError):
    status_code = 404
    error_code = "LEAGUE_NOT_FOUND"


class ResearchUnavailableError(APIError):
    status_code = 503
    error_code = "RESEARCH_UNAVAILABLE"


class ProviderUnavailableError(APIError):
    status_code = 503
    error_code = "PROVIDER_UNAVAILABLE"


class PredictionConflictError(APIError):
    status_code = 409
    error_code = "PREDICTION_CONFLICT"


class RateLimitExceededError(APIError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"


class IdempotencyConflictError(APIError):
    status_code = 409
    error_code = "IDEMPOTENCY_CONFLICT"


class InvalidPredictionError(APIError):
    status_code = 422
    error_code = "INVALID_PREDICTION"


class InsufficientDataError(APIError):
    status_code = 422
    error_code = "INSUFFICIENT_DATA"
