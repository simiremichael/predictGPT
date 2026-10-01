"""Prediction service: orchestrates the full prediction pipeline.

Flow:
    1. Load match and normalized team data from the database.
    2. Build features via FeatureBuilder.
    3. Run the Poisson model (Phase 3 statistical model).
    4. Generate score matrix via ScoreMatrix.
    5. Generate markets via MarketCalculator.
    6. Load latest web research (Phase 4).
    7. Apply bounded AI adjustment (Phase 4).
    8. Recalculate score matrix with adjusted lambdas.
    9. Validate output.
    10. Save prediction (immutable - creates new record each time).
    11. Return prediction output.

If web research or AI is unavailable, the pipeline degrades gracefully
to the Phase 3 statistical prediction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from core.config import get_settings
from core.exceptions import ProviderNotFoundError
from football_data.models import (
    FixtureStatus,
    NormalizedHeadToHead,
    NormalizedTeam,
    NormalizedTeamStatistics,
)
from prediction.ai_adjustment import AIAdjustmentLayer
from prediction.base import PredictionInput
from prediction.exceptions import (
    PredictionConflictError,
    PredictionValidationError,
)
from prediction.features import FeatureBuilder
from prediction.markets import MarketCalculator
from prediction.poisson import PoissonModel
from prediction.schemas import (
    AIAdjustmentSchema,
    ExpectedGoalsSchema,
    GoalDistributionSchema,
    GoalDistributionsSchema,
    MarketBTTSchema,
    MarketCleanSheetSchema,
    MarketDoubleChanceSchema,
    MarketOverUnderSchema,
    MarketsSchema,
    PredictionOutputSchema,
    ResearchSummarySchema,
    ResultProbabilitiesSchema,
    ScorelineSchema,
    ScoreMatrixSchema,
)
from prediction.score_matrix import ScoreMatrix

logger = logging.getLogger(__name__)

_active_predictions: set[str] = set()


class PredictionService:
    """Service for generating and retrieving football predictions.

    Each prediction is immutable: re-running for the same match creates a
    new prediction record rather than overwriting the existing one.
    """

    def __init__(
        self,
        model: Any = None,
        feature_builder: FeatureBuilder | None = None,
        ai_adjustment_layer: AIAdjustmentLayer | None = None,
        research_service: Any = None,
    ) -> None:
        self._model = model or PoissonModel()
        self._feature_builder = feature_builder or FeatureBuilder()
        self._ai_adjustment_layer = ai_adjustment_layer
        self._research_service = research_service
        self._settings = get_settings()

    def _ensure_research_components(self) -> None:
        """Lazily initialize the web-research and AI adjustment components."""
        if self._research_service is None:
            from web_research.service import MatchResearchService

            from ai.service import AIService

            self._research_service = MatchResearchService(ai_service=AIService())

        if self._ai_adjustment_layer is None:
            self._ai_adjustment_layer = AIAdjustmentLayer()

    async def predict_match(
        self,
        match_id: str,
        db_session: Any = None,
        force_new: bool = False,
        context_hash: str | None = None,
        prediction_context: Any | None = None,
        include_research: bool = True,
    ) -> PredictionOutputSchema:
        """Generate or retrieve a prediction for a match.

        Args:
            match_id: Internal match UUID.
            db_session: Optional SQLAlchemy session for database operations.
            force_new: If True, always generate a new prediction even if
                one exists.
            context_hash: Optional context hash for freshness tracking.
            prediction_context: Preloaded database-first match context.
            include_research: If False, skip web research and AI adjustment.

        Returns:
            PredictionOutputSchema with the prediction.

        Raises:
            PredictionConflictError: If a prediction is already being
                generated for this match.
            ProviderNotFoundError: If the match is not found.
        """
        if match_id in _active_predictions:
            raise PredictionConflictError(f"Prediction already in progress for match {match_id}")

        self._ensure_research_components()

        _active_predictions.add(match_id)
        try:
            match_input = await self._load_match_input(
                match_id,
                db_session,
                prediction_context=prediction_context,
            )

            self._validate_match_eligibility(match_input)

            features = self._feature_builder.build(match_input)

            base_model_result = self._model.predict(match_input)

            matrix = ScoreMatrix(
                home_distribution=base_model_result.home_goal_distribution,
                away_distribution=base_model_result.away_goal_distribution,
                max_goals=base_model_result.max_goals,
            )

            market_calc = MarketCalculator(matrix)
            markets = market_calc.get_all_markets()

            hda = matrix.get_result_probabilities()

            top_4 = matrix.get_top_scorelines(n=4)
            top_scoreline = matrix.get_top_scoreline()

            # ── Phase 4: Load research and apply AI adjustment ─────── #
            research_result = None
            ai_adjustment_applied = False
            ai_adjustment_schema = AIAdjustmentSchema(applied=False)
            research_summary = ResearchSummarySchema(available=False)
            ai_explanation_text: str | None = None

            if include_research and self._research_service and match_input.kickoff_at:
                try:
                    research_result = await self._research_service.research_match(
                        match_id=match_id,
                        home_team=match_input.home_team_name,
                        away_team=match_input.away_team_name,
                        competition=match_input.league_id,
                        kickoff_at=match_input.kickoff_at,
                    )
                    research_summary = self._build_research_summary(research_result)
                except Exception as exc:
                    logger.warning(
                        "Research failed, using statistical prediction only",
                        extra={"match_id": match_id, "error": str(exc)},
                    )

            # Apply AI adjustment if research is available
            if research_result and self._ai_adjustment_layer:
                try:
                    from ai.feature_builder import AIFeatureBuilder

                    ai_features = AIFeatureBuilder().build(research_result)
                    adjustment_result = await self._ai_adjustment_layer.apply_adjustment(
                        match_input, base_model_result, features, ai_features
                    )

                    if adjustment_result.adjustment_applied:
                        ai_adjustment_applied = True
                        adj = adjustment_result.ai_adjustment
                        ai_adjustment_schema = AIAdjustmentSchema(
                            applied=True,
                            home_attack_adjustment=adj.home_attack_adjustment,
                            away_attack_adjustment=adj.away_attack_adjustment,
                            home_defense_adjustment=adj.home_defense_adjustment,
                            away_defense_adjustment=adj.away_defense_adjustment,
                            confidence=adj.confidence,
                            reason_codes=adj.reason_codes,
                            source_ids=adj.source_ids,
                        )

                        # Recalculate with adjusted lambdas
                        adjusted = adjustment_result.adjusted_model_result
                        matrix = ScoreMatrix(
                            home_distribution=adjusted.home_goal_distribution,
                            away_distribution=adjusted.away_goal_distribution,
                            max_goals=adjusted.max_goals,
                        )
                        market_calc = MarketCalculator(matrix)
                        markets = market_calc.get_all_markets()
                        hda = matrix.get_result_probabilities()
                        top_4 = matrix.get_top_scorelines(n=4)
                        top_scoreline = matrix.get_top_scoreline()

                        # Generate explanation
                        try:
                            from ai.explanation import AIExplanationService

                            explainer = AIExplanationService()
                            ai_explanation_text = await explainer.generate_explanation(
                                match_input, None, research_result, adjusted
                            )
                            await explainer.close()
                        except Exception as exc:
                            logger.warning("Explanation generation failed: %s", exc)

                        model_result = adjusted
                    else:
                        model_result = base_model_result
                except Exception as exc:
                    logger.warning(
                        "AI adjustment failed, using base prediction",
                        extra={"match_id": match_id, "error": str(exc)},
                    )
                    model_result = base_model_result
            else:
                model_result = base_model_result

            self._validate_prediction(model_result, matrix, hda, top_4, markets)

            output = self._build_output(
                match_input,
                model_result,
                matrix,
                hda,
                top_4,
                top_scoreline,
                markets,
                features,
                research_summary=research_summary,
                ai_adjustment=ai_adjustment_schema,
                ai_explanation=ai_explanation_text,
                context_hash=context_hash,
            )

            prediction_id = await self._save_prediction(
                match_input,
                model_result,
                top_4,
                features,
                output,
                db_session,
                context_hash,
                research_result,
            )
            output.prediction_id = prediction_id

            logger.info(
                "Prediction generated",
                extra={
                    "match_id": match_id,
                    "prediction_id": prediction_id,
                    "model": self._model.model_name,
                    "model_version": self._model.model_version,
                    "lambda_home": round(model_result.lambda_home, 4),
                    "lambda_away": round(model_result.lambda_away, 4),
                    "data_quality": round(features.data_quality, 4),
                    "ai_adjustment_applied": ai_adjustment_applied,
                    "research_available": research_summary.available,
                    "success": True,
                },
            )

            return output

        except Exception:
            logger.exception("Prediction generation failed", extra={"match_id": match_id})
            raise
        finally:
            _active_predictions.discard(match_id)

    async def get_latest_prediction(
        self, match_id: str, db_session: Any = None
    ) -> PredictionOutputSchema | None:
        """Retrieve the latest valid prediction for a match.

        Returns None if no prediction exists.
        """
        if db_session is None:
            return None

        try:
            from sqlalchemy import select

            from models.match import Prediction, PredictionScoreline

            stmt = (
                select(Prediction)
                .where(
                    Prediction.match_id == match_id,
                    Prediction.prediction_status == "published",
                )
                .order_by(Prediction.generated_at.desc())
                .limit(1)
            )
            result = await db_session.execute(stmt)
            prediction = result.scalar_one_or_none()

            if prediction is None:
                return None

            score_stmt = (
                select(PredictionScoreline)
                .where(PredictionScoreline.prediction_id == prediction.id)
                .order_by(PredictionScoreline.rank)
            )
            score_result = await db_session.execute(score_stmt)
            scorelines = score_result.scalars().all()

            return self._reconstruct_output(prediction, scorelines)

        except Exception:
            logger.exception("Error retrieving prediction", extra={"match_id": match_id})
            return None

    async def predict_matches(
        self,
        match_ids: list[str],
        db_session: Any = None,
    ) -> dict[str, Any]:
        """Batch prediction for multiple matches.

        Returns a dict mapping match_id to either the PredictionOutput
        or an error string.
        """
        results: dict[str, Any] = {}

        for match_id in match_ids:
            try:
                pred = await self.predict_match(match_id, db_session)
                results[match_id] = pred
            except Exception as e:
                results[match_id] = str(e)

        return results

    async def generate_upcoming_predictions(
        self,
        league_ids: list[str] | None = None,
        db_session: Any = None,
    ) -> dict[str, Any]:
        """Background job: generate predictions for upcoming matches.

        Finds upcoming matches in supported leagues and generates
        predictions for any that don't have a current prediction.
        """
        if db_session is None:
            return {"error": "Database session required", "generated": 0, "failed": 0}

        from sqlalchemy import select

        from models.match import Match

        try:
            stmt = select(Match).where(
                Match.status.in_([FixtureStatus.SCHEDULED, FixtureStatus.LIVE]),
                not Match.is_finished,
            )
            if league_ids:
                stmt = stmt.where(Match.league_id.in_(league_ids))
            stmt = stmt.order_by(Match.kickoff_at).limit(50)

            result = await db_session.execute(stmt)
            matches = result.scalars().all()

            generated = 0
            failed = 0
            errors: list[str] = []

            for match in matches:
                try:
                    existing = await self.get_latest_prediction(match.id, db_session)
                    if existing is not None:
                        continue

                    await self.predict_match(match.id, db_session)
                    generated += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"Match {match.id}: {str(e)}")

            return {
                "generated": generated,
                "failed": failed,
                "total_matches": len(matches),
                "errors": errors,
            }

        except Exception as e:
            logger.exception("Failed to generate upcoming predictions")
            return {"error": str(e), "generated": 0, "failed": 0}

    # ── Private methods ──────────────────────────────────────────────── #
    async def _load_match_input(
        self,
        match_id: str,
        db_session: Any,
        prediction_context: Any | None = None,
    ) -> PredictionInput:
        """Load match and all related normalized data from the database."""
        if prediction_context is not None and prediction_context.match_id == match_id:
            return prediction_context.to_prediction_input()

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from models.league import Team
        from models.match import Match, TeamStatistics

        if db_session is None:
            raise ProviderNotFoundError("No database session available")

        stmt = (
            select(Match)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.league),
            )
            .where(Match.id == match_id)
        )
        result = await db_session.execute(stmt)
        match = result.scalar_one_or_none()

        if match is None:
            raise ProviderNotFoundError(f"Match {match_id} not found")

        home_stats_stmt = (
            select(TeamStatistics)
            .where(
                TeamStatistics.internal_team_id == match.home_team_id,
                TeamStatistics.is_home,
            )
            .order_by(TeamStatistics.retrieved_at.desc())
            .limit(1)
        )
        home_stats_result = await db_session.execute(home_stats_stmt)
        home_stats = home_stats_result.scalar_one_or_none()

        away_stats_stmt = (
            select(TeamStatistics)
            .where(
                TeamStatistics.internal_team_id == match.away_team_id,
                not TeamStatistics.is_home,
            )
            .order_by(TeamStatistics.retrieved_at.desc())
            .limit(1)
        )
        away_stats_result = await db_session.execute(away_stats_stmt)
        away_stats = away_stats_result.scalar_one_or_none()

        home_team = None
        away_team = None
        if match.home_team:
            home_team = NormalizedTeam(
                provider=match.provider_name,
                provider_team_id=str(match.home_team_id),
                internal_id=match.home_team_id,
                name=match.home_team_name or match.home_team.name,
            )
        if match.away_team:
            away_team = NormalizedTeam(
                provider=match.provider_name,
                provider_team_id=str(match.away_team_id),
                internal_id=match.away_team_id,
                name=match.away_team_name or match.away_team.name,
            )

        return PredictionInput(
            match_id=match.id,
            home_team_id=match.home_team_id or "",
            away_team_id=match.away_team_id or "",
            home_team_name=match.home_team_name or "",
            away_team_name=match.away_team_name or "",
            league_id=match.league_id or "",
            season_id=match.season_id,
            kickoff_at=match.kickoff_at,
            home_team=home_team,
            away_team=away_team,
            home_team_stats=home_stats,
            away_team_stats=away_stats,
            provider=match.provider_name,
        )

    def _validate_match_eligibility(self, match_input: PredictionInput) -> None:
        """Check that a match is eligible for prediction."""
        if match_input.kickoff_at is None:
            raise PredictionValidationError("Cannot predict match without kickoff time")

    def _validate_prediction(
        self,
        model_result: Any,
        matrix: ScoreMatrix,
        hda: dict[str, float],
        top_4: list[Any],
        markets: dict[str, float],
    ) -> None:
        """Validate prediction output before saving."""
        if model_result.lambda_home <= 0:
            raise PredictionValidationError("lambda_home must be > 0")
        if model_result.lambda_away <= 0:
            raise PredictionValidationError("lambda_away must be > 0")

        hda_sum = hda["home"] + hda["draw"] + hda["away"]
        if abs(hda_sum - 1.0) > 0.01:
            raise PredictionValidationError(f"H/D/A probabilities sum to {hda_sum}, expected ~1.0")

        if "btts_yes" in markets and "btts_no" in markets:
            btts_sum = markets["btts_yes"] + markets["btts_no"]
            if abs(btts_sum - 1.0) > 0.01:
                raise PredictionValidationError(f"BTTS yes+no sum to {btts_sum}, expected ~1.0")

        for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
            key = str(threshold).replace(".", "_")
            over = markets.get(f"over_{key}", 0)
            under = markets.get(f"under_{key}", 0)
            pair_sum = over + under
            if abs(pair_sum - 1.0) > 0.01:
                raise PredictionValidationError(
                    f"Over/Under {threshold} sum to {pair_sum}, expected ~1.0"
                )

        for i in range(len(top_4) - 1):
            if top_4[i].probability < top_4[i + 1].probability:
                raise PredictionValidationError(
                    "Top 4 scorelines are not sorted by probability descending"
                )

        seen: set[tuple[int, int]] = set()
        for sl in top_4:
            score_key = (sl.home_goals, sl.away_goals)
            if score_key in seen:
                raise PredictionValidationError("Top 4 contains duplicate scorelines")
            seen.add(score_key)

        total = sum(sum(row) for row in matrix.matrix)
        if abs(total - 1.0) > 0.001:
            raise PredictionValidationError(f"Score matrix sums to {total}, expected ~1.0")

    def _build_output(
        self,
        match_input: PredictionInput,
        model_result: Any,
        matrix: ScoreMatrix,
        hda: dict[str, float],
        top_4: list[Any],
        top_scoreline: Any | None,
        markets: dict[str, float],
        features: Any,
        research_summary: ResearchSummarySchema | None = None,
        ai_adjustment: AIAdjustmentSchema | None = None,
        ai_explanation: str | None = None,
        context_hash: str | None = None,
    ) -> PredictionOutputSchema:
        """Build the PredictionOutputSchema from model results."""
        over_under_raw: dict[str, float] = {}
        for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
            key = str(threshold).replace(".", "_")
            over_under_raw[f"over_{key}"] = markets.get(f"over_{key}", 0.0)
            over_under_raw[f"under_{key}"] = markets.get(f"under_{key}", 0.0)

        over_under = MarketOverUnderSchema(**over_under_raw)
        btts = MarketBTTSchema(
            yes=markets.get("btts_yes", 0.0),
            no=markets.get("btts_no", 0.0),
        )
        clean_sheets = MarketCleanSheetSchema(
            home_clean_sheet=markets.get("home_clean_sheet", 0.0),
            away_clean_sheet=markets.get("away_clean_sheet", 0.0),
        )
        double_chance = MarketDoubleChanceSchema(
            home_or_draw=markets.get("home_or_draw", 0.0),
            draw_or_away=markets.get("draw_or_away", 0.0),
            home_or_away=markets.get("home_or_away", 0.0),
        )

        home_dist = GoalDistributionSchema(
            probabilities=list(model_result.home_goal_distribution),
            mean=model_result.lambda_home,
        )
        away_dist = GoalDistributionSchema(
            probabilities=list(model_result.away_goal_distribution),
            mean=model_result.lambda_away,
        )

        matrix_serialized: list[list[float]] = []
        for row in matrix.to_serializable():
            matrix_serialized.append([round(v, 6) for v in row])

        score_matrix_schema = ScoreMatrixSchema(
            home_max_goals=model_result.max_goals,
            away_max_goals=model_result.max_goals,
            matrix=matrix_serialized,
        )

        top_4_schemas = [
            ScorelineSchema(
                home_goals=sl.home_goals,
                away_goals=sl.away_goals,
                probability=round(sl.probability, 6),
            )
            for sl in top_4
        ]

        top_scoreline_schema = None
        if top_scoreline:
            top_scoreline_schema = ScorelineSchema(
                home_goals=top_scoreline.home_goals,
                away_goals=top_scoreline.away_goals,
                probability=round(top_scoreline.probability, 6),
            )

        confidence = self._compute_model_confidence(features.data_quality, top_4, hda)

        stability = self._compute_stability(model_result, features)

        explanations = []
        if hasattr(self._model, "explain_features"):
            try:
                explanations = self._model.explain_features(
                    features.raw_snapshot if hasattr(features, "raw_snapshot") else {}
                )
            except Exception:
                pass

        markets_schema = MarketsSchema(
            over_under=over_under,
            btts=btts,
            clean_sheets=clean_sheets,
            double_chance=double_chance,
        )

        return PredictionOutputSchema(
            model=model_result.model,
            model_version=model_result.model_version,
            prediction_version="v1.0.0",
            lambda_home=round(model_result.lambda_home, 6),
            lambda_away=round(model_result.lambda_away, 6),
            expected_goals=ExpectedGoalsSchema(
                home=round(model_result.lambda_home, 6),
                away=round(model_result.lambda_away, 6),
            ),
            expected_total_goals=round(model_result.lambda_home + model_result.lambda_away, 6),
            result_probabilities=ResultProbabilitiesSchema(
                home=round(hda["home"], 6),
                draw=round(hda["draw"], 6),
                away=round(hda["away"], 6),
            ),
            top_scoreline=top_scoreline_schema,
            top_4_scorelines=top_4_schemas,
            score_matrix=score_matrix_schema,
            goal_distributions=GoalDistributionsSchema(
                home=home_dist,
                away=away_dist,
            ),
            markets=markets_schema,
            data_quality=round(features.data_quality, 6),
            model_confidence=confidence,
            prediction_stability=stability,
            feature_explanations=explanations,
            feature_snapshot=features.raw_snapshot,
            model_parameters=model_result.model_parameters,
            generated_at=datetime.utcnow(),
            match_id=match_input.match_id,
            match_home_team=match_input.home_team_name,
            match_away_team=match_input.away_team_name,
            match_kickoff=match_input.kickoff_at,
            research=research_summary or ResearchSummarySchema(available=False),
            ai_adjustment=ai_adjustment or AIAdjustmentSchema(applied=False),
            ai_explanation=ai_explanation,
            confidence=confidence,
            uncertainty=1.0 - confidence,
            source_ids=ai_adjustment.source_ids if ai_adjustment else [],
            context_hash=context_hash,
        )

    def _compute_model_confidence(
        self,
        data_quality: float,
        top_4: list[Any],
        hda: dict[str, float],
    ) -> float:
        """Compute model confidence (0-1).

        NOT the same as highest probability.  Considers:
            - data quality
            - probability concentration
            - top-1 vs top-4 spread
        """
        confidence = 0.0

        confidence += data_quality * 0.40

        if top_4:
            top_1_prob = top_4[0].probability
            concentration = min(1.0, top_1_prob / 0.25)
            confidence += concentration * 0.30

        if len(top_4) >= 2:
            spread = top_4[0].probability - top_4[-1].probability
            spread_score = min(1.0, spread / 0.15)
            confidence += spread_score * 0.30

        return round(min(1.0, confidence), 6)

    def _compute_stability(
        self,
        model_result: Any,
        features: Any,
    ) -> str:
        """Assess prediction stability via perturbation analysis."""
        try:
            league = features.league
            lambda_home = (
                league.avg_home_goals
                * (features.home_attack_strength * 1.05)
                * features.away_defense_strength
                * PoissonModel.HOME_ADVANTAGE_MULTIPLIER
                * features.home_form_strength
            )
            lambda_away = (
                league.avg_away_goals
                * (features.away_attack_strength * 0.95)
                * features.home_defense_strength
                * features.away_form_strength
            )

            home_delta = abs(lambda_home - model_result.lambda_home) / max(
                model_result.lambda_home, 0.01
            )
            away_delta = abs(lambda_away - model_result.lambda_away) / max(
                model_result.lambda_away, 0.01
            )

            max_delta = max(home_delta, away_delta)
            if max_delta < 0.05:
                return "high"
            elif max_delta < 0.15:
                return "medium"
            else:
                return "low"
        except Exception:
            return "unknown"

    async def _save_prediction(
        self,
        match_input: PredictionInput,
        model_result: Any,
        top_4: list[Any],
        features: Any,
        output: PredictionOutputSchema,
        db_session: Any,
        context_hash: str | None = None,
        research_result: Any | None = None,
    ) -> str:
        """Save prediction to database. Creates a new immutable record."""
        if db_session is None:
            return str(uuid.uuid4())

        try:
            from models.match import Prediction, PredictionScoreline

            prediction = Prediction(
                match_id=match_input.match_id,
                model_version=model_result.model_version,
                provider_used=match_input.provider,
                generated_at=datetime.utcnow(),
                lambda_home=model_result.lambda_home,
                lambda_away=model_result.lambda_away,
                home_probability=output.result_probabilities.home,
                draw_probability=output.result_probabilities.draw,
                away_probability=output.result_probabilities.away,
                over_2_5_probability=output.markets.over_under.over_2_5,
                under_2_5_probability=output.markets.over_under.under_2_5,
                btts_probability=output.markets.btts.yes,
                confidence=output.model_confidence,
                prediction_status="published",
                feature_snapshot=output.feature_snapshot,
                news_snapshot={
                    "research": output.research.model_dump(mode="json"),
                    "sources": [
                        {
                            "url": source.url,
                            "title": source.title,
                            "publisher": source.publisher,
                            "snippet": source.snippet,
                            "published_at": source.published_at.isoformat()
                            if source.published_at
                            else None,
                            "credibility_score": source.credibility_score,
                            "freshness_score": source.freshness_score,
                        }
                        for source in (research_result.sources if research_result else [])
                    ],
                },
                odds_snapshot={},
                ai_explanation=output.ai_explanation,
                ai_evidence_json=[
                    {
                        "kind": "injury",
                        **item.model_dump(mode="json"),
                    }
                    for item in (research_result.injuries if research_result else [])
                ]
                + [
                    {
                        "kind": "suspension",
                        **item.model_dump(mode="json"),
                    }
                    for item in (research_result.suspensions if research_result else [])
                ]
                + [
                    {
                        "kind": "lineup",
                        **item.model_dump(mode="json"),
                    }
                    for item in (research_result.lineups if research_result else [])
                ]
                + [
                    {
                        "kind": "team_news",
                        **item.model_dump(mode="json"),
                    }
                    for item in (research_result.team_news if research_result else [])
                ],
                ai_adjustment_json=(
                    output.ai_adjustment.model_dump(mode="json")
                    if output.ai_adjustment.applied
                    else None
                ),
                source_ids=output.source_ids,
                context_hash=context_hash,
            )

            db_session.add(prediction)
            await db_session.flush()

            for i, sl in enumerate(top_4):
                scoreline = PredictionScoreline(
                    prediction_id=prediction.id,
                    home_goals=sl.home_goals,
                    away_goals=sl.away_goals,
                    probability=sl.probability,
                    rank=i + 1,
                )
                db_session.add(scoreline)

            await db_session.commit()

            return prediction.id

        except Exception:
            if db_session:
                await db_session.rollback()
            raise

    def _build_research_summary(self, research_result: Any) -> ResearchSummarySchema:
        """Build a research summary schema from a research result."""
        return ResearchSummarySchema(
            available=True,
            data_quality=research_result.data_quality,
            sources_count=len(research_result.sources),
            injuries_count=len(research_result.injuries),
            suspensions_count=len(research_result.suspensions),
            lineups_count=len(research_result.lineups),
            team_news_count=len(research_result.team_news),
            conflicts_count=len(research_result.conflicts),
            average_credibility=sum(s.credibility_score for s in research_result.sources)
            / len(research_result.sources)
            if research_result.sources
            else 0.0,
            average_freshness=sum(s.freshness_score for s in research_result.sources)
            / len(research_result.sources)
            if research_result.sources
            else 0.0,
            researched_at=research_result.researched_at,
        )

    def _reconstruct_output(self, prediction: Any, scorelines: list[Any]) -> PredictionOutputSchema:
        """Reconstruct prediction output from stored DB models."""
        top_4 = [
            ScorelineSchema(
                home_goals=sl.home_goals,
                away_goals=sl.away_goals,
                probability=round(sl.probability, 6),
            )
            for sl in scorelines
        ]

        top_scoreline = top_4[0] if top_4 else None

        return PredictionOutputSchema(
            prediction_id=prediction.id,
            model="poisson",
            model_version=prediction.model_version,
            lambda_home=prediction.lambda_home or 0.0,
            lambda_away=prediction.lambda_away or 0.0,
            expected_goals=ExpectedGoalsSchema(
                home=prediction.lambda_home or 0.0,
                away=prediction.lambda_away or 0.0,
            ),
            expected_total_goals=(prediction.lambda_home or 0.0) + (prediction.lambda_away or 0.0),
            result_probabilities=ResultProbabilitiesSchema(
                home=prediction.home_probability or 0.0,
                draw=prediction.draw_probability or 0.0,
                away=prediction.away_probability or 0.0,
            ),
            top_scoreline=top_scoreline,
            top_4_scorelines=top_4,
            markets=MarketsSchema(
                over_under=MarketOverUnderSchema(
                    over_0_5=0.0,
                    over_1_5=0.0,
                    over_2_5=prediction.over_2_5_probability or 0.0,
                    over_3_5=0.0,
                    over_4_5=0.0,
                    under_0_5=0.0,
                    under_1_5=0.0,
                    under_2_5=prediction.under_2_5_probability or 0.0,
                    under_3_5=0.0,
                    under_4_5=0.0,
                ),
                btts=MarketBTTSchema(
                    yes=prediction.btts_probability or 0.0,
                    no=1.0 - (prediction.btts_probability or 0.0),
                ),
                clean_sheets=MarketCleanSheetSchema(
                    home_clean_sheet=0.0,
                    away_clean_sheet=0.0,
                ),
                double_chance=MarketDoubleChanceSchema(
                    home_or_draw=0.0,
                    draw_or_away=0.0,
                    home_or_away=0.0,
                ),
            ),
            data_quality=prediction.feature_snapshot.get("data_quality", 0.0)
            if isinstance(prediction.feature_snapshot, dict)
            else 0.0,
            model_confidence=prediction.confidence or 0.0,
            prediction_stability="medium",
            feature_explanations=[],
            feature_snapshot=prediction.feature_snapshot
            if isinstance(prediction.feature_snapshot, dict)
            else {},
            model_parameters={},
            generated_at=prediction.generated_at,
            match_id=prediction.match_id,
            match_home_team="",
            match_away_team="",
            research=ResearchSummarySchema(
                **(
                    prediction.news_snapshot.get("research", {})
                    if isinstance(prediction.news_snapshot, dict)
                    else {}
                )
            ),
            ai_adjustment=AIAdjustmentSchema(
                **(
                    prediction.ai_adjustment_json
                    if isinstance(prediction.ai_adjustment_json, dict)
                    else {"applied": False}
                )
            ),
            ai_explanation=prediction.ai_explanation,
            source_ids=prediction.source_ids or [],
            context_hash=prediction.context_hash,
        )
