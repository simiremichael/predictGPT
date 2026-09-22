"""Poisson model for football match prediction.

Implements a mathematically transparent Poisson goal-scoring model:

    expected_home_goals =
        league_home_goal_average
        × home_attack_strength
        × away_defense_factor
        × home_form_adjustment
        × home_advantage_multiplier

    expected_away_goals =
        league_away_goal_average
        × away_attack_strength
        × home_defense_factor
        × away_form_adjustment

Goals are modelled as independent Poisson random variables, producing a
score probability matrix via the outer product of the two marginal
distributions.
"""
from __future__ import annotations

import math
from typing import Any

from prediction.base import ModelResult, PredictionInput
from prediction.exceptions import InsufficientDataError


class PoissonModel:
    """Poisson goal-scoring model for football match prediction.

    Uses the classic Dixon-Coles-inspired attack/defense formulation
    without the correlation adjustment (that comes in a future model).

    Configuration:
        MODEL_VERSION: Version string for reproducibility.
        MAX_GOALS: Maximum goals per team in the score matrix.
        HOME_ADVANTAGE_MULTIPLIER: Multiplier applied to home expected goals
            as a baseline home advantage.  Default 1.10 based on empirical
            football data showing home teams score ~10% more.
        HOME_FORM_WEIGHT: Weight of form adjustment in lambda calculation.
        MIN_HOME_FORM: Minimum form multiplier (prevents extreme values).
        FORM_WEIGHT: Blend factor for form vs. season stats (0 = season only, 1 = form only).
    """

    model_name = "poisson"
    model_version = "poisson-v1.0.0"
    MAX_GOALS = 8

    HOME_ADVANTAGE_MULTIPLIER = 1.10
    HOME_FORM_WEIGHT = 0.15
    MIN_HOME_ADVANTAGE = 1.00

    # Shrinkage toward baseline for teams with insufficient data
    SHRINKAGE_FACTOR = 0.3

    def __init__(self, max_goals: int = 8) -> None:
        self.max_goals = max_goals

    def predict(self, match: PredictionInput) -> ModelResult:
        """Generate a Poisson prediction for the given match input.

        Requires at least basic league baseline and team attack/defense data.
        Falls back to league-average baselines when team-specific data is
        missing, applying sample-size shrinkage.
        """
        from prediction.features import FeatureBuilder

        builder = FeatureBuilder()
        features = builder.build(match)

        league = features.league

        # Compute lambda values using attack/defense strengths
        home_attack = features.home_attack_strength
        home_defense = features.home_defense_strength
        away_attack = features.away_attack_strength
        away_defense = features.away_defense_strength

        home_form_adj = features.home_form_strength
        away_form_adj = features.away_form_strength

        # Optional xG adjustment
        xg_factor = 1.0
        if features.home_xg is not None and features.home_xga is not None:
            # Blend xG into the lambda estimate
            xg_factor = self._compute_xg_factor(
                features.home_xg, features.home_xga,
                league.avg_home_goals
            )
        elif features.away_xg is not None and features.away_xga is not None:
            xg_factor = self._compute_xg_factor(
                features.away_xg, features.away_xga,
                league.avg_away_goals
            )

        # Core Poisson lambda calculation
        # λ_home = league_avg_home_goals × home_attack × away_defense × home_advantage × form
        lambda_home = (
            league.avg_home_goals
            * home_attack
            * away_defense
            * self.HOME_ADVANTAGE_MULTIPLIER
            * home_form_adj
            * xg_factor
        )

        # λ_away = league_avg_away_goals × away_attack × home_defense × form
        lambda_away = (
            league.avg_away_goals
            * away_attack
            * home_defense
            * away_form_adj
        )

        # Apply sample-size protection (shrink toward league average)
        if features.home_sample < 5 or features.away_sample < 5:
            shrinkage = self.SHRINKAGE_FACTOR
            lambda_home = (
                shrinkage * league.avg_home_goals * self.HOME_ADVANTAGE_MULTIPLIER
                + (1 - shrinkage) * lambda_home
            )
            lambda_away = (
                shrinkage * league.avg_away_goals
                + (1 - shrinkage) * lambda_away
            )

        # Clamp to reasonable range
        lambda_home = max(0.1, min(8.0, lambda_home))
        lambda_away = max(0.1, min(8.0, lambda_away))

        # Compute goal distributions
        home_dist = [self._poisson_pmf(k, lambda_home) for k in range(self.max_goals + 1)]
        away_dist = [self._poisson_pmf(k, lambda_away) for k in range(self.max_goals + 1)]

        # Build score matrix (independent Poisson)
        score_matrix: list[list[float]] = []
        for h in range(self.max_goals + 1):
            row = []
            for a in range(self.max_goals + 1):
                row.append(home_dist[h] * away_dist[a])
            score_matrix.append(row)

        # Store model parameters for reproducibility
        model_parameters = {
            "max_goals": self.max_goals,
            "home_advantage_multiplier": self.HOME_ADVANTAGE_MULTIPLIER,
            "home_form_weight": self.HOME_FORM_WEIGHT,
            "shrinkage_factor": self.SHRINKAGE_FACTOR,
            "league_avg_home_goals": league.avg_home_goals,
            "league_avg_away_goals": league.avg_away_goals,
        }

        feature_snapshot = {
            "home_attack_strength": features.home_attack_strength,
            "home_defense_strength": features.home_defense_strength,
            "away_attack_strength": features.away_attack_strength,
            "away_defense_strength": features.away_defense_strength,
            "home_form_strength": features.home_form_strength,
            "away_form_strength": features.away_form_strength,
            "home_expected_goals_baseline": features.home_expected_goals_baseline,
            "away_expected_goals_baseline": features.away_expected_goals_baseline,
            "h2h_signal": features.h2h_signal,
            "data_quality": features.data_quality,
            "missing_features": features.missing_features,
            "home_sample": features.home_sample,
            "away_sample": features.away_sample,
        }

        return ModelResult(
            model=self.model_name,
            model_version=self.model_version,
            lambda_home=lambda_home,
            lambda_away=lambda_away,
            home_goal_distribution=home_dist,
            away_goal_distribution=away_dist,
            score_matrix=score_matrix,
            max_goals=self.max_goals,
            data_quality=features.data_quality,
            model_parameters=model_parameters,
            feature_snapshot=feature_snapshot,
        )

    def _poisson_pmf(self, k: int, lam: float) -> float:
        """Compute Poisson probability mass function P(X=k).

        Uses log-space calculation for numerical stability with large k.
        Handles edge cases: lam <= 0, very large lambda.
        """
        if lam <= 0:
            return 1.0 if k == 0 else 0.0

        # Use log-gamma for numerical stability
        # P(X=k) = e^(-lam) * lam^k / k!
        # log P(X=k) = -lam + k*log(lam) - log(k!)
        log_pmf = -lam + k * math.log(lam) - math.lgamma(k + 1)

        # Clamp to avoid overflow
        try:
            return math.exp(log_pmf)
        except (OverflowError, ValueError):
            return 0.0

    def _compute_xg_factor(
        self, xg: float, xga: float, league_avg: float
    ) -> float:
        """Compute a multiplier that adjusts lambda based on xG vs average.

        When a team's xG is significantly above league average, we slightly
        boost the expected goals.  This is a conservative adjustment.
        """
        if league_avg <= 0:
            return 1.0

        # Blend xG into the model: 50% weight
        xg_ratio = xg / league_avg if league_avg > 0 else 1.0
        return 0.5 * xg_ratio + 0.5 * 1.0

    def explain_features(self, features: dict[str, Any]) -> list[str]:
        """Return deterministic feature explanations (no LLM)."""
        explanations: list[str] = []

        home_attack = features.get("home_attack_strength", 1.0)
        home_defense = features.get("home_defense_strength", 1.0)  # noqa: F841
        away_attack = features.get("away_attack_strength", 1.0)
        home_form = features.get("home_form_strength", 1.0)
        away_form = features.get("away_form_strength", 1.0)
        home_sample = features.get("home_sample", 0)
        away_sample = features.get("away_sample", 0)

        if home_attack > 1.05:
            explanations.append(
                f"Home team attack strength is above league average ({home_attack:.2f})"
            )
        elif home_attack < 0.95:
            explanations.append(
                f"Home team attack strength is below league average ({home_attack:.2f})"
            )

        if away_attack > 1.05:
            explanations.append(
                f"Away team attack strength is above league average ({away_attack:.2f})"
            )
        elif away_attack < 0.95:
            explanations.append(
                f"Away team attack strength is below league average ({away_attack:.2f})"
            )

        if home_form > 1.05:
            explanations.append(
                f"Home team shows positive recent form (factor {home_form:.2f})"
            )
        elif home_form < 0.95:
            explanations.append(
                f"Home team shows negative recent form (factor {home_form:.2f})"
            )

        if away_form > 1.05:
            explanations.append(
                f"Away team shows positive recent form (factor {away_form:.2f})"
            )
        elif away_form < 0.95:
            explanations.append(
                f"Away team shows negative recent form (factor {away_form:.2f})"
            )

        if home_sample < 5:
            explanations.append(
                f"Home team sample size is small ({home_sample} games), "
                "prediction blends toward league average"
            )

        if away_sample < 5:
            explanations.append(
                f"Away team sample size is small ({away_sample} games), "
                "prediction blends toward league average"
            )

        if features.get("h2h_signal") is not None:
            h2h = features["h2h_signal"]
            if h2h > 1.1:
                explanations.append(
                    f"Head-to-head favours home team (ratio {h2h:.2f})"
                )
            elif h2h < 0.9:
                explanations.append(
                    f"Head-to-head favours away team (ratio {h2h:.2f})"
                )

        if not explanations:
            explanations.append("Both teams show league-average characteristics")

        return explanations
