"""Prediction result recording and model evaluation.

After matches finish, actual results are stored and compared against
predictions to produce evaluation metrics.  Historical prediction
probabilities are never modified — new ``PredictionResult`` records link
actual outcomes to original predictions.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from prediction.schemas import PredictionOutputSchema

logger = get_logger(__name__)

settings = get_settings()


class EvaluationService:
    """Evaluates completed matches against stored predictions."""

    def __init__(self, db_session: Any = None) -> None:
        self._db = db_session

    async def record_match_result(
        self,
        match_id: str,
        home_score: int,
        away_score: int,
        match_finished_at: datetime | None = None,
    ) -> list[str]:
        """Record actual results for a finished match and evaluate predictions.

        Returns a list of prediction IDs that were evaluated.
        """
        if self._db is None:
            return []

        from sqlalchemy import select

        from models.match import Prediction, PredictionResult

        result = await self._db.execute(
            select(Prediction).where(Prediction.match_id == match_id)
        )
        predictions = result.scalars().all()

        evaluated_ids: list[str] = []

        for pred in predictions:
            existing = await self._db.execute(
                select(PredictionResult).where(PredictionResult.prediction_id == pred.id)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            scoreline = await self._find_scoreline_in_prediction(pred, home_score, away_score)
            exact_correct = scoreline is not None
            top4_hit = await self._check_top4_hit(pred, home_score, away_score)

            hda_correct = self._check_hda_correct(pred, home_score, away_score)
            over_25_correct = self._check_over_25(pred, home_score, away_score)
            btts_correct = self._check_btts(pred, home_score, away_score)

            pr = PredictionResult(
                prediction_id=pred.id,
                home_score=home_score,
                away_score=away_score,
                exact_score_correct=exact_correct,
                top4_hit=top4_hit,
                home_win_correct=hda_correct.get("home_win"),
                draw_correct=hda_correct.get("draw"),
                away_win_correct=hda_correct.get("away_win"),
                over_25_correct=over_25_correct,
                btts_correct=btts_correct,
                evaluated_at=match_finished_at or datetime.utcnow(),
            )
            self._db.add(pr)
            evaluated_ids.append(pred.id)

        await self._db.commit()
        logger.info(
            "Match results recorded and predictions evaluated",
            extra={"match_id": match_id, "evaluated": len(evaluated_ids)},
        )
        return evaluated_ids

    async def _find_scoreline_in_prediction(
        self, pred: Any, home_score: int, away_score: int
    ) -> Any | None:
        """Check if the actual scoreline exists in the prediction's top-4."""
        if self._db is None:
            return None
        from sqlalchemy import select

        from models.match import PredictionScoreline

        result = await self._db.execute(
            select(PredictionScoreline)
            .where(PredictionScoreline.prediction_id == pred.id)
            .where(
                PredictionScoreline.home_goals == home_score,
                PredictionScoreline.away_goals == away_score,
            )
        )
        return result.scalar_one_or_none()

    async def _check_top4_hit(self, pred: Any, home_score: int, away_score: int) -> bool:
        """Check if the actual scoreline is in the prediction's top-4."""
        if self._db is None:
            return False
        from sqlalchemy import select

        from models.match import PredictionScoreline

        result = await self._db.execute(
            select(PredictionScoreline)
            .where(PredictionScoreline.prediction_id == pred.id)
            .where(
                PredictionScoreline.home_goals == home_score,
                PredictionScoreline.away_goals == away_score,
            )
        )
        return result.scalar_one_or_none() is not None

    def _check_hda_correct(
        self, pred: Any, home_score: int, away_score: int
    ) -> dict[str, bool]:
        """Check Home/Draw/Away result prediction correctness."""
        if home_score > away_score:
            actual = "home"
        elif home_score < away_score:
            actual = "away"
        else:
            actual = "draw"

        hda_probs = {
            "home": pred.home_probability or 0.0,
            "draw": pred.draw_probability or 0.0,
            "away": pred.away_probability or 0.0,
        }

        max(hda_probs, key=hda_probs.get) if hda_probs else "home"

        return {
            "home_win": actual == "home",
            "draw": actual == "draw",
            "away_win": actual == "away",
        }

    def _check_over_25(self, pred: Any, home_score: int, away_score: int) -> bool:
        """Check Over/Under 2.5 correctness."""
        actual_over = (home_score + away_score) > 2.5
        predicted_over = (pred.over_2_5_probability or 0.0) > (pred.under_2_5_probability or 0.0)
        return actual_over == predicted_over

    def _check_btts(self, pred: Any, home_score: int, away_score: int) -> bool:
        """Check BTTS correctness."""
        actual_btts = home_score >= 1 and away_score >= 1
        predicted_btts = (pred.btts_probability or 0.0) > 0.5
        return actual_btts == predicted_btts

    async def evaluate_completed_matches(
        self, matches: list[dict[str, Any]], job_id: str | None = None
    ) -> dict[str, Any]:
        """Background job: evaluate predictions for completed matches.

        Args:
            matches: List of match dicts with id, home_score, away_score.
            job_id: If provided, update job progress.
        """
        from jobs.job_manager import set_job_progress, update_job_status

        total = len(matches)
        if job_id:
            await update_job_status(job_id, "running", total=total)

        evaluated = 0
        failed = 0
        errors: list[str] = []

        for match in matches:
            try:
                ids = await self.record_match_result(
                    match_id=match["id"],
                    home_score=match["home_score"],
                    away_score=match["away_score"],
                    match_finished_at=match.get("finished_at"),
                )
                evaluated += len(ids)
                if job_id:
                    await set_job_progress(job_id, succeeded=evaluated, failed=failed)
            except Exception as exc:
                failed += 1
                errors.append(f"Match {match['id']}: {str(exc)}")
                if job_id:
                    await set_job_progress(job_id, succeeded=evaluated, failed=failed)

        if job_id:
            await update_job_status(job_id, "completed", succeeded=evaluated, failed=failed)

        return {"evaluated": evaluated, "failed": failed, "errors": errors}


class MetricsCalculator:
    """Calculate model performance metrics from evaluation results."""

    @staticmethod
    def brier_score(predictions: list[tuple[float, int]]) -> float:
        """Lower is better. predictions = [(prob_of_event, actually_occurred)]."""
        if not predictions:
            return 0.0
        n = len(predictions)
        return sum((p - o) ** 2 for p, o in predictions) / n

    @staticmethod
    def log_loss(predictions: list[tuple[float, int]]) -> float:
        """Lower is better. predictions = [(prob_of_event, actually_occurred)]."""
        import math

        eps = 1e-15
        total = 0.0
        for p, o in predictions:
            p = max(eps, min(1 - eps, p))
            total += o * math.log(p) + (1 - o) * math.log(1 - p)
        return -total / len(predictions) if predictions else 0.0

    @staticmethod
    def mae(predicted: list[float], actual: list[float]) -> float:
        """Mean Absolute Error."""
        if not predicted:
            return 0.0
        return sum(abs(p - a) for p, a in zip(predicted, actual, strict=False)) / len(predicted)

    @staticmethod
    def rmse(predicted: list[float], actual: list[float]) -> float:
        """Root Mean Square Error."""
        import math

        if not predicted:
            return 0.0
        return math.sqrt(sum((p - a) ** 2 for p, a in zip(predicted, actual, strict=False)) / len(predicted))

    @staticmethod
    def calibration_error(buckets: list[tuple[float, float]]) -> float:
        """Mean absolute calibration error.

        Each bucket is (mean_predicted_probability, observed_frequency).
        """
        if not buckets:
            return 0.0
        return sum(abs(p - o) for p, o in buckets) / len(buckets)

    @staticmethod
    def top4_hit_rate(hits: int, total: int) -> float:
        return hits / total if total > 0 else 0.0

    @staticmethod
    def exact_score_hit_rate(hits: int, total: int) -> float:
        return hits / total if total > 0 else 0.0
