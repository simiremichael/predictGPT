"""Backtesting framework for prediction models.

Provides infrastructure to evaluate prediction models against historical
match results.  Enforces data leakage protection by using cutoff_datetime
to ensure only pre-kickoff data is used.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from prediction.base import ModelResult, PredictionInput
from prediction.exceptions import InsufficientDataError
from prediction.metrics import (
    brier_score,
    exact_score_accuracy,
    log_loss,
    mean_absolute_goal_error,
    top_4_hit_rate,
)

logger = logging.getLogger(__name__)


class MatchRepository(Protocol):
    """Protocol for historical match data access.

    Implementations must support cutoff_datetime for data leakage protection.
    """

    async def get_historical_matches(
        self,
        league_id: str | None = None,
        before: datetime | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        """Return historical matches before the cutoff datetime."""

    async def get_match(self, match_id: str) -> Any | None:
        """Return a single match by ID."""

    async def get_league_baseline(
        self,
        league_id: str,
        season_id: str | None = None,
        before: datetime | None = None,
    ) -> Any:
        """Return league-level baseline statistics."""


@dataclass
class BacktestConfig:
    """Configuration for a backtesting run."""

    model: Any
    league_id: str | None = None
    season_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    history_window: int = 100
    form_window: int = 5
    min_goals_for_inclusion: int = 1
    metrics_to_compute: list[str] = field(
        default_factory=lambda: [
            "home_draw_away_accuracy",
            "top_4_hit_rate",
            "brier_score",
            "log_loss",
            "maege",
        ]
    )


@dataclass
class BacktestResult:
    """Aggregated results from a backtesting run."""

    total_matches: int = 0
    successful_predictions: int = 0
    failed_predictions: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    per_match_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BacktestingEngine:
    """Runs backtesting simulations for prediction models.

    Data leakage protection:
        Every feature query uses cutoff_datetime to ensure only data
        available before match kickoff is used.
    """

    def __init__(self, repository: MatchRepository) -> None:
        self.repository = repository

    async def run_backtest(
        self,
        config: BacktestConfig,
        cutoff_datetime_provider: Any = None,
    ) -> BacktestResult:
        """Run a backtesting simulation.

        Args:
            config: Backtesting configuration.
            cutoff_datetime_provider: Optional callable that returns the
                cutoff datetime for a given match.  Defaults to match's
                kickoff_at.

        Returns:
            BacktestResult with aggregated metrics.
        """
        result = BacktestResult()
        all_hda_probs: list[float] = []
        all_hda_outcomes: list[int] = []

        if cutoff_datetime_provider is None:
            cutoff_datetime_provider = lambda m: m.kickoff_at  # noqa: E731

        # Fetch historical matches
        matches = await self.repository.get_historical_matches(
            league_id=config.league_id,
            before=config.end_date,
            limit=None,
        )

        # Filter by date range
        filtered = []
        for match in matches:
            kickoff = getattr(match, "kickoff_at", None)
            if kickoff is None:
                continue
            if config.start_date and kickoff < config.start_date:
                continue
            if config.end_date and kickoff >= config.end_date:
                continue
            # Only evaluate finished matches
            if not getattr(match, "is_finished", False):
                continue
            filtered.append(match)

        for match in filtered:
            cutoff = cutoff_datetime_provider(match)

            try:
                prediction_input = await self._build_prediction_input(
                    match, cutoff, config
                )

                model_result = config.model.predict(prediction_input)

                match_result = self._evaluate_single(
                    match, model_result, match.home_score, match.away_score
                )

                result.per_match_results.append(match_result)
                result.successful_predictions += 1

                # Collect for aggregate metrics
                hda_probs = match_result.get("hda_probs", {})
                hda_actual = match_result.get("hda_actual", {})
                for outcome in ["home", "draw", "away"]:
                    all_hda_probs.append(hda_probs.get(outcome, 0.0))
                    all_hda_outcomes.append(hda_actual.get(outcome, 0))

            except InsufficientDataError as e:
                result.failed_predictions += 1
                result.errors.append(f"Match {match.id}: {str(e)}")
                logger.debug("Insufficient data for match %s: %s", match.id, str(e))
            except Exception as e:
                result.failed_predictions += 1
                result.errors.append(f"Match {match.id}: {str(e)}")
                logger.exception("Error backtesting match %s", match.id)

        result.total_matches = result.successful_predictions + result.failed_predictions

        # Compute aggregate metrics
        if all_hda_probs:
            result.metrics["brier_score"] = brier_score(
                all_hda_probs, all_hda_outcomes
            )
            result.metrics["log_loss"] = log_loss(
                all_hda_probs, all_hda_outcomes
            )

        # Compute per-metric averages
        for metric_name in config.metrics_to_compute:
            if metric_name == "brier_score" or metric_name == "log_loss":
                continue

            values = [
                r.get(metric_name, 0) / 1.0
                for r in result.per_match_results
                if metric_name in r
            ]
            if values:
                result.metrics[metric_name] = sum(values) / len(values)

        return result

    async def _build_prediction_input(
        self,
        match: Any,
        cutoff: datetime,
        config: BacktestConfig,
    ) -> PredictionInput:
        """Build a PredictionInput using only pre-kickoff data.

        This is where data leakage protection is enforced.
        """
        # Load team stats, form, etc. using cutoff datetime
        # The repository methods must respect cutoff
        raise NotImplementedError(
            "Use a concrete BacktestingEngine subclass or override this method"
        )

    def _evaluate_single(
        self,
        match: Any,
        model_result: ModelResult,
        actual_home: int,
        actual_away: int,
    ) -> dict[str, Any]:
        """Evaluate a single prediction against actual results."""
        from prediction.score_matrix import ScoreMatrix

        matrix = ScoreMatrix.from_model_result(model_result)
        top_4 = matrix.get_top_scorelines(n=4)
        top_scoreline = matrix.get_top_scoreline()
        hda = matrix.get_result_probabilities()

        # Determine actual result
        actual_result = "draw"
        if actual_home > actual_away:
            actual_result = "home"
        elif actual_home < actual_away:
            actual_result = "away"

        # Predicted result
        predicted_result = max(hda, key=hda.get)

        return {
            "match_id": match.id,
            "lambda_home": model_result.lambda_home,
            "lambda_away": model_result.lambda_away,
            "actual_home": actual_home,
            "actual_away": actual_away,
            "exact_score_hit": exact_score_accuracy(
                top_scoreline or type("S", (), {"home_goals": 0, "away_goals": 0})(),
                actual_home,
                actual_away,
            ) if top_scoreline else False,
            "top4_hit": top_4_hit_rate(top_4, actual_home, actual_away),
            "hda_probs": hda,
            "hda_actual": {
                "home": 1 if actual_result == "home" else 0,
                "draw": 1 if actual_result == "draw" else 0,
                "away": 1 if actual_result == "away" else 0,
            },
            "predicted_result": predicted_result,
            "actual_result": actual_result,
            "result_prediction_correct": predicted_result == actual_result,
            "maege": mean_absolute_goal_error(
                model_result.lambda_home,
                model_result.lambda_away,
                actual_home,
                actual_away,
            ),
        }
