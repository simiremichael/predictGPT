"""Ensemble model framework.

Prepares the architecture for combining multiple models via weighted
averaging.  No actual ensemble is implemented yet — the interface exists
so future models (Dixon-Coles, Elo, xG, ML) can be plugged in.

The default configuration is:
    {"poisson": 1.0}

Weights MUST NOT be tuned until validated through backtesting.
"""
from __future__ import annotations

from typing import Any

from prediction.base import ModelResult, PredictionInput
from prediction.exceptions import ModelNotImplementedError


class EnsembleModel:
    """Framework for combining multiple prediction models.

    Currently operates as a pass-through to the primary model (Poisson).
    Future versions will blend multiple models with validated weights.

    Configuration:
        model_weights: Dict mapping model_name -> weight.
            Default: {"poisson": 1.0}
        weights_must_be_validated: If True, only applies weights from a
            pre-validated configuration.  Default: True.
    """

    def __init__(
        self,
        model_weights: dict[str, float] | None = None,
        weights_validated: bool = False,
    ) -> None:
        self._default_weights = {"poisson": 1.0}
        self._weights: dict[str, float] = model_weights or self._default_weights.copy()
        self._weights_validated = weights_validated
        self._primary_model: Any = None

    def set_primary_model(self, model: Any) -> None:
        """Set the primary (or only) model to use."""
        self._primary_model = model

    def predict(self, match: PredictionInput) -> ModelResult:
        """Generate a prediction using the ensemble.

        If only one model is configured (and it's Poisson), delegates directly.
        Multi-model ensembling is not yet active.
        """
        if not self._weights_validated and len(self._weights) > 1:
            # Weights haven't been validated through backtesting
            self._weights = self._default_weights.copy()
            self._weights_validated = False

        if len(self._weights) == 1 and "poisson" in self._weights:
            if self._primary_model is None:
                from prediction.poisson import PoissonModel
                self._primary_model = PoissonModel()
            return self._primary_model.predict(match)

        if self._primary_model is not None:
            return self._primary_model.predict(match)

        raise ModelNotImplementedError(
            "No model available in ensemble. Configure at least one model."
        )

    def explain_features(self, features: dict[str, Any]) -> list[str]:
        """Return ensemble-level feature explanations."""
        if self._primary_model and hasattr(self._primary_model, "explain_features"):
            return self._primary_model.explain_features(features)
        return ["Ensemble model using primary model"]

    @property
    def model_name(self) -> str:
        if len(self._weights) == 1 and "poisson" in self._weights:
            return "ensemble_poisson"
        return "ensemble"

    @property
    def model_version(self) -> str:
        return "ensemble-v0.1.0"
