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
    model_version = "poisson-v1.5.0"
    MAX_GOALS = 8

    HOME_ADVANTAGE_MULTIPLIER = 1.01
    HOME_FORM_WEIGHT = 0.15
    MIN_HOME_ADVANTAGE = 1.00

    # Shrinkage toward baseline for teams with insufficient data
    SHRINKAGE_FACTOR = 0.3

    # Weight factors for ranking signals (league position, H2H, standings)
    STANDING_SIGNAL_WEIGHT = 0.13   # Points-per-game advantage weight
    H2H_SIGNAL_WEIGHT = 0.16       # Head-to-head win ratio weight
    POSITION_SIGNAL_WEIGHT = 0.13    # League table position advantage weight
    AVG_GOALS_SIGNAL_WEIGHT = 0.09  # Average goals per game difference weight

    # BTTS / over-under differentiation weights
    BTTS_SIGNAL_WEIGHT = 0.11       # BTTS rate difference weight
    OVER_2_5_SIGNAL_WEIGHT = 0.13   # Over 2.5 rate difference weight

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

        # Use standings, head-to-head, and league position as bounded signals
        # that contribute to the prediction alongside form and attack/defense.
        standing_factor = 1.0
        if features.standing_signal is not None:
            standing_log_adjustment = max(
                -0.40, min(0.40, features.standing_signal * self.STANDING_SIGNAL_WEIGHT)
            )
            standing_factor = math.exp(standing_log_adjustment)

        h2h_home_factor = 1.0
        if features.h2h_signal is not None and features.h2h_signal > 0:
            h2h_log_adjustment = max(
                -0.30, min(0.30, math.log(features.h2h_signal) * self.H2H_SIGNAL_WEIGHT)
            )
            h2h_home_factor = math.exp(h2h_log_adjustment)

        position_factor = 1.0
        if features.league_position_signal is not None:
            position_adjustment = max(
                -0.40,
                min(0.40, features.league_position_signal * -self.POSITION_SIGNAL_WEIGHT),
            )
            position_factor = math.exp(position_adjustment)

        avg_goals_factor = 1.0
        if features.avg_goals_signal is not None:
            avg_goals_adjustment = max(
                -0.15,
                min(0.15, features.avg_goals_signal * self.AVG_GOALS_SIGNAL_WEIGHT),
            )
            avg_goals_factor = math.exp(avg_goals_adjustment)

        # BTTS signal: differentiate teams by their recent scoring consistency
        btts_factor = 1.0
        if (
            features.home_btts_rate is not None
            and features.away_btts_rate is not None
        ):
            btts_diff = features.home_btts_rate - features.away_btts_rate
            btts_adjustment = max(
                -0.20, min(0.20, btts_diff * self.BTTS_SIGNAL_WEIGHT)
            )
            btts_factor = math.exp(btts_adjustment)

        # Over-under 2.5 signal: differentiate teams by recent goal volume
        over_2_5_factor = 1.0
        if (
            features.home_over_2_5_rate is not None
            and features.away_over_2_5_rate is not None
        ):
            ou_diff = features.home_over_2_5_rate - features.away_over_2_5_rate
            ou_adjustment = max(
                -0.25, min(0.25, ou_diff * self.OVER_2_5_SIGNAL_WEIGHT)
            )
            over_2_5_factor = math.exp(ou_adjustment)

        # Pair each team's attacking xG with its opponent's xGA. Keep these
        # adjustments separate so one team's xG cannot move both goal rates.
        home_xg_factor = self._compute_xg_factor(
            features.home_xg, features.away_xga, league.avg_home_goals
        )
        away_xg_factor = self._compute_xg_factor(
            features.away_xg, features.home_xga, league.avg_away_goals
        )

        # Core Poisson lambda calculation
        # λ_home = league_avg_home_goals × home_attack × away_defense
        #          × home_advantage × form × xg × standing × h2h × position × avg_goals
        #          × btts × over_2_5
        lambda_home = (
            league.avg_home_goals
            * home_attack
            * away_defense
            * self.HOME_ADVANTAGE_MULTIPLIER
            * home_form_adj
            * home_xg_factor
            * standing_factor
            * h2h_home_factor
            * position_factor
            * avg_goals_factor
            * btts_factor
            * over_2_5_factor
        )

        # λ_away = league_avg_away_goals × away_attack × home_defense × form
        #          × xg / standing / h2h / position / avg_goals / btts / over_2_5
        lambda_away = (
            league.avg_away_goals
            * away_attack
            * home_defense
            * away_form_adj
            * away_xg_factor
            / standing_factor
            / h2h_home_factor
            / position_factor
            / avg_goals_factor
            / btts_factor
            / over_2_5_factor
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
            "standing_signal_weight": self.STANDING_SIGNAL_WEIGHT,
            "max_standing_log_adjustment": 0.40,
            "h2h_signal_weight": self.H2H_SIGNAL_WEIGHT,
            "max_h2h_log_adjustment": 0.30,
            "position_signal_weight": self.POSITION_SIGNAL_WEIGHT,
            "max_position_adjustment": 0.40,
            "avg_goals_signal_weight": self.AVG_GOALS_SIGNAL_WEIGHT,
            "max_avg_goals_adjustment": 0.15,
            "btts_signal_weight": self.BTTS_SIGNAL_WEIGHT,
            "max_btts_adjustment": 0.20,
            "over_2_5_signal_weight": self.OVER_2_5_SIGNAL_WEIGHT,
            "max_over_2_5_adjustment": 0.25,
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
            "standing_signal": features.standing_signal,
            "league_position_signal": features.league_position_signal,
            "avg_goals_signal": features.avg_goals_signal,
            "standing_factor": standing_factor,
            "h2h_home_factor": h2h_home_factor,
            "position_factor": position_factor,
            "avg_goals_factor": avg_goals_factor,
            "home_xg_factor": home_xg_factor,
            "away_xg_factor": away_xg_factor,
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
        self, xg: float | None, xga: float | None, league_avg: float
    ) -> float:
        """Apply a bounded xG/xGA multiplier relative to the league average."""
        if league_avg <= 0 or (xg is None and xga is None):
            return 1.0

        available_rates = [rate for rate in (xg, xga) if rate is not None and rate >= 0]
        if not available_rates:
            return 1.0

        xg_ratio = sum(available_rates) / (len(available_rates) * league_avg)
        # xG complements the goal-based strengths; cap its influence so noisy
        # or provider-specific estimates cannot dominate the prediction.
        return max(0.85, min(1.15, 0.5 + 0.5 * xg_ratio))

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

        standing_signal = features.get("standing_signal")
        if standing_signal is not None and abs(standing_signal) >= 0.25:
            leading_team = "home" if standing_signal > 0 else "away"
            explanations.append(
                f"League points per game currently favour the {leading_team} team "
                f"({abs(standing_signal):.2f} PPG difference)"
            )

        position_signal = features.get("league_position_signal")
        if position_signal is not None:
            if position_signal > 5:
                explanations.append(
                    f"Home team has stronger league position (position advantage {position_signal:.0f} places)"
                )
            elif position_signal < -5:
                explanations.append(
                    f"Away team has stronger league position (position advantage {abs(position_signal):.0f} places)"
                )

        avg_goals_signal = features.get("avg_goals_signal")
        if avg_goals_signal is not None and abs(avg_goals_signal) >= 0.3:
            leading_team = "home" if avg_goals_signal > 0 else "away"
            explanations.append(
                f"{leading_team.capitalize()} team has higher average goals per game "
                f"(difference {abs(avg_goals_signal):.2f})"
            )

        home_btts = features.get("home_btts_rate")
        away_btts = features.get("away_btts_rate")
        if home_btts is not None and away_btts is not None:
            btts_diff = home_btts - away_btts
            if abs(btts_diff) >= 0.10:
                leading_team = "home" if btts_diff > 0 else "away"
                explanations.append(
                    f"{leading_team.capitalize()} team shows higher BTTS rate in recent matches "
                    f"(difference {abs(btts_diff):.2f})"
                )

        home_ou = features.get("home_over_2_5_rate")
        away_ou = features.get("away_over_2_5_rate")
        if home_ou is not None and away_ou is not None:
            ou_diff = home_ou - away_ou
            if abs(ou_diff) >= 0.10:
                leading_team = "home" if ou_diff > 0 else "away"
                explanations.append(
                    f"{leading_team.capitalize()} team has higher over 2.5 goals rate recently "
                    f"(difference {abs(ou_diff):.2f})"
                )

        if not explanations:
            explanations.append("Both teams show league-average characteristics")

        return explanations
