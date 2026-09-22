"""Prediction orchestrator: the main coordination layer for the prediction pipeline.

This service ties together all existing Phase 1-4 components:
  1. Load match and normalized football data
  2. Build Phase 3 features
  3. Run the Poisson statistical model (Phase 3)
  4. Load web research (Phase 4)
  5. Apply bounded AI adjustment (Phase 4)
  6. Recalculate score matrix
  7. Generate markets
  8. Generate AI explanation (Phase 4)
  9. Persist immutable prediction
  10. Return result

If research or AI is unavailable, the pipeline degrades gracefully
to the Phase 3 statistical prediction.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from core.config import get_settings
from core.exceptions import ProviderNotFoundError
from core.logging import get_logger
from prediction.ai_adjustment import AIAdjustmentLayer
from prediction.exceptions import (
    PredictionConflictError,
    PredictionValidationError,
)
from prediction.features import FeatureBuilder
from prediction.markets import MarketCalculator
from prediction.poisson import PoissonModel
from prediction.schemas import (
    AIAdjustmentSchema,
    PredictionOutputSchema,
    ResearchSummarySchema,
)
from prediction.score_matrix import ScoreMatrix

logger = get_logger(__name__)

_active_predictions: set[str] = set()

# How stale a prediction can be before it's considered "needs refresh"
DEFAULT_PREDICTION_MAX_AGE = 3600  # 1 hour


class PredictionOrchestrator:
    """Coordinates the full prediction pipeline.

    The orchestrator is the single entry point for prediction generation.
    It delegates to the Phase 3 prediction service and Phase 4 research/AI
    components, ensuring clean separation of concerns.
    """

    def __init__(
        self,
        model: Any = None,
        feature_builder: FeatureBuilder | None = None,
        ai_adjustment_layer: AIAdjustmentLayer | None = None,
    ) -> None:
        self._settings = get_settings()
        self._model = model or PoissonModel()
        self._feature_builder = feature_builder or FeatureBuilder()
        self._ai_adjustment_layer = ai_adjustment_layer

    async def generate_prediction(
        self,
        match_id: str,
        db_session: Any = None,
        force_refresh: bool = False,
        include_research: bool = True,
        context_hash: str | None = None,
    ) -> PredictionOutputSchema:
        """Generate or retrieve a prediction for a match.

        Args:
            match_id: Internal match UUID.
            db_session: Optional SQLAlchemy session.
            force_refresh: If True, always generate a new prediction.
            include_research: If True, load web research and apply AI adjustment.
            context_hash: Optional context hash to check for data freshness.
                If provided and matches the stored prediction's context hash,
                the existing prediction is considered fresh and returned.

        Returns:
            PredictionOutputSchema with the prediction.
        """
        if match_id in _active_predictions and not force_refresh:
            raise PredictionConflictError(
                f"Prediction already in progress for match {match_id}"
            )

        current_context_hash = context_hash
        prediction_context = None
        if db_session:
            try:
                from services.prediction_data import PredictionDataService

                data_service = PredictionDataService()
                prediction_context = await data_service.get_context(match_id, db_session)
                current_context_hash = prediction_context.context_hash
            except Exception as exc:
                logger.warning(
                    "Could not refresh prediction context; using stored prediction data",
                    extra={"match_id": match_id, "error": str(exc)},
                )

        max_age = self._settings.prediction_cache_ttl

        if not force_refresh and db_session:
            existing = await self.get_latest_prediction(match_id, db_session)
            if existing is not None:
                # Check context hash freshness
                if current_context_hash and existing.context_hash == current_context_hash:
                    logger.info(
                        "Returning prediction with matching context hash",
                        extra={"match_id": match_id, "prediction_id": existing.match_id},
                    )
                    return existing
                if (
                    not current_context_hash
                    and existing.generated_at
                    > datetime.utcnow() - timedelta(seconds=max_age)
                ):
                    logger.info(
                        "Returning fresh cached prediction",
                        extra={"match_id": match_id, "prediction_id": existing.match_id},
                    )
                    return existing

        _active_predictions.add(match_id)
        try:
            prediction_id = await self._run_pipeline(
                match_id=match_id,
                db_session=db_session,
                include_research=include_research,
                prediction_context=prediction_context,
                context_hash=current_context_hash,
            )
            return await self.get_prediction_by_id(prediction_id, db_session)
        finally:
            _active_predictions.discard(match_id)

    async def _run_pipeline(
        self,
        match_id: str,
        db_session: Any,
        include_research: bool,
        prediction_context: Any | None = None,
        context_hash: str | None = None,
    ) -> str:
        """Execute the full prediction pipeline and return the prediction ID.

        Delegates to the existing PredictionService for the core pipeline,
        wrapping it with cache invalidation and logging.
        """
        from core.cache import (
            cache_match_key,
            cache_match_prediction_key,
            invalidate_cache_keys,
        )
        from prediction.service import PredictionService

        if prediction_context is None and db_session:
            try:
                from services.prediction_data import PredictionDataService

                prediction_context = await PredictionDataService().get_context(
                    match_id, db_session
                )
                context_hash = prediction_context.context_hash
            except Exception as exc:
                logger.warning(
                    "Prediction context refresh failed",
                    extra={"match_id": match_id, "error": str(exc)},
                )

        service = PredictionService()
        prediction = await service.predict_match(
            match_id,
            db_session,
            include_research=include_research,
            prediction_context=prediction_context,
            context_hash=context_hash,
        )

        if prediction is not None:
            await invalidate_cache_keys(
                cache_match_key(match_id),
                cache_match_prediction_key(match_id),
            )
            logger.info(
                "Prediction pipeline completed",
                extra={
                    "match_id": match_id,
                    "model": prediction.model,
                    "model_version": prediction.model_version,
                    "data_quality": prediction.data_quality,
                },
            )
            return prediction_id
        else:
            return match_id

    async def get_latest_prediction(
        self, match_id: str, db_session: Any = None
    ) -> PredictionOutputSchema | None:
        """Retrieve the latest valid prediction for a match."""
        from prediction.service import PredictionService

        service = PredictionService()
        return await service.get_latest_prediction(match_id, db_session)

    async def get_prediction_by_id(
        self, prediction_id: str, db_session: Any = None
    ) -> PredictionOutputSchema | None:
        """Retrieve a specific prediction by ID."""
        if db_session is None:
            return None
        from sqlalchemy import select

        from models.match import Prediction, PredictionScoreline
        from prediction.service import PredictionService

        result = await db_session.execute(
            select(Prediction).where(Prediction.id == prediction_id)
        )
        prediction = result.scalar_one_or_none()
        if prediction is None:
            return None

        score_result = await db_session.execute(
            select(PredictionScoreline).where(PredictionScoreline.prediction_id == prediction_id)
        )
        scorelines = score_result.scalars().all()

        service = PredictionService()
        return service._reconstruct_output(prediction, scorelines)

    async def get_prediction_history(
        self,
        db_session: Any = None,
        match_id: str | None = None,
        league_id: str | None = None,
        team_id: str | None = None,
        model_version: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PredictionOutputSchema], int]:
        """Retrieve prediction history with filters and pagination."""
        from sqlalchemy import func, select
        from sqlalchemy.orm import selectinload

        from core.pagination import get_page, get_page_size
        from models.match import Match, Prediction, PredictionScoreline

        page = get_page(page)
        page_size = get_page_size(page_size)
        offset = (page - 1) * page_size

        stmt = select(Prediction).options(selectinload(Prediction.match))

        if match_id:
            stmt = stmt.where(Prediction.match_id == match_id)
        if league_id:
            stmt = stmt.join(Match).where(Match.league_id == league_id)
        if team_id:
            stmt = stmt.join(Match).where(
                (Match.home_team_id == team_id) | (Match.away_team_id == team_id)
            )
        if model_version:
            stmt = stmt.where(Prediction.model_version == model_version)
        if date_from:
            stmt = stmt.where(Prediction.generated_at >= date_from)
        if date_to:
            stmt = stmt.where(Prediction.generated_at <= date_to)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db_session.execute(total_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(Prediction.generated_at.desc()).offset(offset).limit(page_size)
        result = await db_session.execute(stmt)
        predictions = result.scalars().all()

        from prediction.service import PredictionService

        service = PredictionService()
        outputs: list[PredictionOutputSchema] = []
        for pred in predictions:
            scorelines_stmt = (
                select(PredictionScoreline)
                .where(PredictionScoreline.prediction_id == pred.id)
                .order_by(PredictionScoreline.rank)
            )
            score_result = await db_session.execute(scorelines_stmt)
            scorelines = score_result.scalars().all()
            output = service._reconstruct_output(pred, scorelines)
            outputs.append(output)

        return outputs, total

    async def generate_upcoming_predictions(
        self,
        league_ids: list[str] | None = None,
        db_session: Any = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate predictions for upcoming matches in configured leagues."""
        from datetime import timezone

        from sqlalchemy import select

        from football_data.models import FixtureStatus
        from jobs.job_manager import set_job_progress, update_job_status
        from models.match import Match

        if db_session is None:
            return {"error": "Database session required", "generated": 0, "failed": 0}

        stmt = select(Match).where(
            Match.status.in_([FixtureStatus.SCHEDULED.value, FixtureStatus.LIVE.value]),
            not Match.is_finished,
        )
        if league_ids:
            stmt = stmt.where(Match.league_id.in_(league_ids))

        cutoff = datetime.now(UTC) + timedelta(hours=72)
        stmt = stmt.where(Match.kickoff_at <= cutoff)
        stmt = stmt.order_by(Match.kickoff_at).limit(50)

        result = await db_session.execute(stmt)
        matches = result.scalars().all()

        if job_id:
            await update_job_status(job_id, "running", total=len(matches))

        generated = 0
        failed = 0
        errors: list[str] = []

        for match in matches:
            try:
                existing = await self.get_latest_prediction(match.id, db_session)
                if existing and existing.generated_at > datetime.utcnow() - timedelta(
                    seconds=self._settings.prediction_cache_ttl
                ):
                    continue

                await self._run_pipeline(match.id, db_session, include_research=True)
                generated += 1
            except Exception as e:
                failed += 1
                errors.append(f"Match {match.id}: {str(e)}")

            if job_id:
                await set_job_progress(job_id, succeeded=generated, failed=failed)

        if job_id:
            await update_job_status(job_id, "completed", succeeded=generated, failed=failed)

        return {
            "generated": generated,
            "failed": failed,
            "total_matches": len(matches),
            "errors": errors,
        }
