"""AI-powered prediction service using DuckDuckGo research.

This service fetches fixtures from the database, uses DuckDuckGo to search
for team information (injuries, suspensions, lineups, news), then uses
the existing prediction pipeline (Poisson model + AI adjustment) to produce
research-adjusted predictions with varied outcome probabilities.

The pipeline:
  1. Fetch upcoming matches from the database (fixtures endpoint sources)
  2. Run the Poisson model for a baseline prediction (Phase 3)
  3. Use DuckDuckGo to search team/player news (Phase 4)
  4. Apply bounded AI adjustment based on research evidence (Phase 4)
  5. Recalculate score matrix with adjusted lambdas
  6. Generate AI explanation (Phase 4)
  7. Save the prediction + research run + evidence to the database
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


class AIPredictionService:
    """Generates predictions using DuckDuckGo research + AI adjustment.

    Fetches fixtures from the database, searches the web for team news,
    injuries, suspensions, and lineups via DuckDuckGo, then runs the
    existing Poisson statistical model with AI evidence adjustment to
    produce research-backed predictions with varied probabilities.
    """

    VERSION = "ai-research-v1.0.0"

    def __init__(self, db_session: AsyncSession | None = None) -> None:
        self._settings = get_settings()
        self._db_session = db_session

    async def generate_prediction(
        self,
        match_id: str,
        db_session: AsyncSession | None = None,
        include_research: bool = True,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Generate a research-backed AI prediction for a single match.

        Args:
            match_id: Internal match / fixture ID from the database.
            db_session: SQLAlchemy async session. If None, uses the service's
                session or creates a new one.
            include_research: If True, perform DuckDuckGo research before
                generating the prediction.
            force_refresh: If True, bypass any caching of research results.

        Returns:
            A dict with the prediction result, research summary, and
            the prediction ID saved to the database.
        """
        db = db_session or self._db_session
        if db is None:
            from db.database import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                return await self._generate_prediction_impl(
                    match_id, session, include_research, force_refresh
                )

        return await self._generate_prediction_impl(
            match_id, db, include_research, force_refresh
        )

    async def _generate_prediction_impl(
        self,
        match_id: str,
        db: AsyncSession,
        include_research: bool,
        force_refresh: bool,
    ) -> dict[str, Any]:
        from sqlalchemy.orm import selectinload

        from models.match import Match

        result = await db.execute(
            select(Match).where(Match.id == match_id).options(selectinload(Match.league))
        )
        match = result.scalar_one_or_none()

        if match is None:
            return {
                "success": False,
                "error": f"Match {match_id} not found",
                "meta": {"message": f"Match {match_id} not found in database"},
            }

        home_team_name = match.home_team_name or (match.home_team.name if match.home_team else "Unknown")
        away_team_name = match.away_team_name or (match.away_team.name if match.away_team else "Unknown")

        from prediction.service import PredictionService

        prediction_service = PredictionService()

        try:
            prediction_output = await prediction_service.predict_match(
                match_id=match_id,
                db_session=db,
                include_research=include_research,
                force_new=True,
            )
        except Exception as exc:
            logger.error(
                "Prediction generation failed",
                extra={"match_id": match_id, "error": str(exc)},
            )
            return {
                "success": False,
                "error": f"Failed to generate prediction: {str(exc)}",
            }

        prediction_dict = prediction_output.model_dump(mode="json")

        return {
            "success": True,
            "data": {
                "prediction_id": prediction_output.prediction_id or match_id,
                "match_id": match_id,
                "model": prediction_output.model,
                "model_version": prediction_output.model_version,
                "prediction": prediction_dict,
            },
            "meta": {
                "match_id": match_id,
                "home_team": home_team_name,
                "away_team": away_team_name,
                "include_research": include_research,
                "research_available": prediction_output.research.available,
                "ai_adjustment_applied": prediction_output.ai_adjustment.applied,
                "message": "AI prediction generated successfully",
            },
        }

    async def generate_predictions_for_league(
        self,
        league_id: str | None = None,
        league_ids: list[str] | None = None,
        db_session: AsyncSession | None = None,
        limit: int = 10,
        include_research: bool = True,
    ) -> dict[str, Any]:
        """Fetch fixtures from DB and generate AI predictions for each.

        Retrieves upcoming scheduled matches from the database, runs
        DuckDuckGo research + AI prediction for each, and saves results
        to the database.
        """
        db = db_session or self._db_session
        if db is None:
            from db.database import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                return await self._generate_predictions_batch(
                    session, league_id, league_ids, limit, include_research
                )

        return await self._generate_predictions_batch(
            db, league_id, league_ids, limit, include_research
        )

    async def _generate_predictions_batch(
        self,
        db: AsyncSession,
        league_id: str | None,
        league_ids: list[str] | None,
        limit: int,
        include_research: bool,
    ) -> dict[str, Any]:
        from football_data.models import FixtureStatus
        from models.match import Match

        now = datetime.utcnow()

        stmt = (
            select(Match)
            .where(
                Match.status.in_(
                    [FixtureStatus.SCHEDULED.value, FixtureStatus.LIVE.value]
                ),
                Match.is_finished.is_(False),
                Match.kickoff_at >= now,
            )
            .order_by(Match.kickoff_at)
            .limit(limit)
        )

        if league_id:
            stmt = stmt.where(Match.league_id == league_id)
        if league_ids:
            stmt = stmt.where(Match.league_id.in_(league_ids))

        result = await db.execute(stmt)
        matches = result.scalars().all()

        generated = 0
        failed = 0
        errors: list[str] = []
        predictions: list[dict[str, Any]] = []

        for match in matches:
            try:
                pred_result = await self._generate_prediction_impl(
                    match.id, db, include_research, force_refresh=False
                )
                if pred_result.get("success"):
                    generated += 1
                    predictions.append(pred_result["data"])
                else:
                    failed += 1
                    errors.append(f"Match {match.id}: {pred_result.get('error', 'unknown')}")
            except Exception as exc:
                failed += 1
                errors.append(f"Match {match.id}: {str(exc)}")
                logger.exception(
                    "Failed to generate prediction for match",
                    extra={"match_id": match.id, "error": str(exc)},
                )

        return {
            "success": True,
            "data": {
                "generated": generated,
                "failed": failed,
                "total_matches": len(matches),
                "predictions": predictions,
                "errors": errors,
            },
            "meta": {
                "league_id": league_id,
                "limit": limit,
                "include_research": include_research,
                "message": f"Generated {generated} predictions, {failed} failed",
            },
        }
