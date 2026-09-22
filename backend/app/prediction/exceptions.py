"""Exceptions specific to the prediction engine."""
from __future__ import annotations

from core.exceptions import FootballDataError


class PredictionError(FootballDataError):
    """Base exception for all prediction-related errors."""


class PredictionValidationError(PredictionError):
    """Raised when a prediction fails validation before it can be stored."""


class PredictionNotFoundError(PredictionError):
    """Raised when a prediction cannot be found for a match."""


class InsufficientDataError(PredictionError):
    """Raised when not enough data exists to generate a prediction."""


class ModelNotImplementedError(PredictionError):
    """Raised when a requested model is not implemented."""


class PredictionConflictError(PredictionError):
    """Raised when a concurrent prediction generation request conflicts."""
