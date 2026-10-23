"""AI adjustment layer.

Sits AFTER the Phase 3 statistical (Poisson) model. It applies bounded,
evidence-based adjustments to the lambda (goal-rate) parameters based on
research evidence, then the score matrix is recalculated by the statistical
model.

Architecture:
    Phase 3 Features -> Poisson Model -> Base Prediction
                                         |
                                         v
                                    AI Evidence Adjustment
                                         |
                                         v
                                     Final Prediction

Key rules:
- Adjustments are bounded by configured caps
- No evidence -> no adjustment
- Adjustments modify goal-rate lambdas, NOT scorelines directly
- The score matrix is recalculated after adjustments
- Every adjustment is auditable with reason codes and source IDs
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from web_research.schemas import AIFeatureAdjustment

from ai.base import AIProvider
from ai.exceptions import AIError
from ai.feature_builder import AIFeatureBuilder, AIFeatureVector
from ai.prompts import AI_ADJUSTMENT_SYSTEM_PROMPT, AI_ADJUSTMENT_USER_PROMPT
from core.config import get_settings
from core.logging import get_logger
from prediction.base import ModelResult, PredictionInput
from prediction.features import FeatureVector
from prediction.markets import MarketCalculator
from prediction.poisson import PoissonModel
from prediction.schemas import (
    ExpectedGoalsSchema,
    GoalDistributionSchema,
    GoalDistributionsSchema,
    MarketBTTSchema,
    MarketCleanSheetSchema,
    MarketDoubleChanceSchema,
    MarketOverUnderSchema,
    MarketsSchema,
    PredictionOutputSchema,
    ResultProbabilitiesSchema,
    ScorelineSchema,
    ScoreMatrixSchema,
)
from prediction.score_matrix import ScoreMatrix

logger = get_logger(__name__)


@dataclass
class AIAdjustedPrediction:
    """Prediction after AI evidence adjustment.

    Contains the original base prediction, the AI adjustment, and the
    recalculated prediction.
    """

    base_model_result: ModelResult
    ai_adjustment: AIFeatureAdjustment
    adjusted_model_result: ModelResult
    adjustment_applied: bool
    explanation: str


class AIAdjustmentLayer:
    """Applies bounded, evidence-based AI adjustments to statistical predictions.

    The adjustment modifies lambda (goal-rate) values, never scorelines directly.
    After adjustment, the score matrix is recalculated using the same Poisson model.
    """

    VERSION = "ai-adjustment-v1.1.0"

    def __init__(
        self,
        ai_provider: AIProvider | None = None,
        feature_builder: AIFeatureBuilder | None = None,
    ) -> None:
        self._settings = get_settings()
        self._ai_provider = ai_provider
        self._feature_builder = feature_builder or AIFeatureBuilder()
        self._max_attack_adjustment = self._settings.ai_attack_impact_cap
        self._max_defense_adjustment = self._settings.ai_defense_impact_cap

    async def apply_adjustment(
        self,
        match_input: PredictionInput,
        base_result: ModelResult,
        features: FeatureVector,
        ai_features: AIFeatureVector,
    ) -> AIAdjustedPrediction:
        """Apply AI evidence adjustment to the base prediction.

        Args:
            match_input: The original prediction input.
            base_result: The statistical model's output before AI adjustment.
            features: The Phase 3 feature vector.
            ai_features: The AI-derived features from research evidence.

        Returns:
            AIAdjustedPrediction with the adjusted model result.
        """
        # The Poisson baseline is the starting point. Always ask the AI to
        # evaluate it; without supporting data, the prompt directs it to zero.
        statistical_adjustment = self._compute_statistical_adjustments(ai_features)

        context_source_ids = self._available_context_source_ids(ai_features, match_input)

        # Ask the configured AI to evaluate the baseline, even when evidence
        # and structured match context are unavailable.
        evidence_text = ai_features.evidence_text or "No web evidence extracted."
        evidence_text += (
            "\nStructured match context IDs available for citation: "
            + ", ".join(context_source_ids)
        )

        system_prompt = AI_ADJUSTMENT_SYSTEM_PROMPT.format(
            max_attack_adjustment=self._max_attack_adjustment,
            max_defense_adjustment=self._max_defense_adjustment,
        )

        # Compute base market probabilities for the prompt
        base_matrix = ScoreMatrix(
            home_distribution=base_result.home_goal_distribution,
            away_distribution=base_result.away_goal_distribution,
            max_goals=base_result.max_goals,
        )
        base_hda = base_matrix.get_result_probabilities()
        base_markets = MarketCalculator(base_matrix).get_all_markets()

        # Extract H2H and recent-form stats for the AI prompt
        h2h = getattr(match_input, "h2h", None)
        h2h_team_a_wins = h2h.team_a_wins if h2h else "unknown"
        h2h_team_b_wins = h2h.team_b_wins if h2h else "unknown"
        h2h_draws = h2h.draws if h2h else "unknown"
        h2h_avg_goals = h2h.avg_goals_per_game if h2h else "unknown"

        # Recent 5-game stats. Scores are stored from each fixture's
        # home/away perspective, so resolve the team's role per match.
        home_recent = list(getattr(match_input, "home_recent_fixture", []))
        away_recent = list(getattr(match_input, "away_recent_fixture", []))

        def recent_goal_totals(recent: list[Any], team_id: str | None, is_home: bool) -> tuple[int | str, int | str]:
            goals_for = 0
            goals_against = 0
            counted = 0
            for fixture in recent:
                if (
                    not fixture.is_finished
                    or fixture.home_score is None
                    or fixture.away_score is None
                ):
                    continue
                if team_id and fixture.home_team_id == team_id:
                    team_played_home = True
                elif team_id and fixture.away_team_id == team_id:
                    team_played_home = False
                else:
                    team_played_home = is_home
                if team_played_home:
                    goals_for += fixture.home_score
                    goals_against += fixture.away_score
                else:
                    goals_for += fixture.away_score
                    goals_against += fixture.home_score
                counted += 1
            return (goals_for, goals_against) if counted else ("unknown", "unknown")

        home_last5_goals_for, home_last5_goals_against = recent_goal_totals(
            home_recent[-5:], match_input.home_team_id, True
        )
        away_last5_goals_for, away_last5_goals_against = recent_goal_totals(
            away_recent[-5:], match_input.away_team_id, False
        )

        # Season average goals
        home_stats = getattr(match_input, "home_team_stats", None)
        away_stats = getattr(match_input, "away_team_stats", None)
        home_season_goals_for = home_stats.goals_for if home_stats else "unknown"
        home_season_goals_against = home_stats.goals_against if home_stats else "unknown"
        away_season_goals_for = away_stats.goals_for if away_stats else "unknown"
        away_season_goals_against = away_stats.goals_against if away_stats else "unknown"

        user_prompt = AI_ADJUSTMENT_USER_PROMPT.format(
            home_team=match_input.home_team_name,
            away_team=match_input.away_team_name,
            league=match_input.league_id,
            lambda_home=base_result.lambda_home,
            lambda_away=base_result.lambda_away,
            home_win_prob=round(base_hda["home"], 4),
            draw_prob=round(base_hda["draw"], 4),
            away_prob=round(base_hda["away"], 4),
            over_25_prob=round(base_markets["over_2_5"], 4),
            btts_prob=round(base_markets["btts_yes"], 4),
            home_league_position=ai_features.home_league_position
            if ai_features.home_league_position is not None
            else "unknown",
            away_league_position=ai_features.away_league_position
            if ai_features.away_league_position is not None
            else "unknown",
            home_ppg=ai_features.home_standing_points_per_game
            if ai_features.home_standing_points_per_game is not None
            else "unknown",
            away_ppg=ai_features.away_standing_points_per_game
            if ai_features.away_standing_points_per_game is not None
            else "unknown",
            home_season_goals_for=home_season_goals_for,
            home_season_goals_against=home_season_goals_against,
            away_season_goals_for=away_season_goals_for,
            away_season_goals_against=away_season_goals_against,
            home_avg_goals_per_game=ai_features.home_avg_goals_per_game
            if ai_features.home_avg_goals_per_game is not None
            else "unknown",
            away_avg_goals_per_game=ai_features.away_avg_goals_per_game
            if ai_features.away_avg_goals_per_game is not None
            else "unknown",
            home_btts_rate=ai_features.home_btts_rate
            if ai_features.home_btts_rate is not None
            else "unknown",
            away_btts_rate=ai_features.away_btts_rate
            if ai_features.away_btts_rate is not None
            else "unknown",
            home_over_2_5_rate=ai_features.home_over_2_5_rate
            if ai_features.home_over_2_5_rate is not None
            else "unknown",
            away_over_2_5_rate=ai_features.away_over_2_5_rate
            if ai_features.away_over_2_5_rate is not None
            else "unknown",
            h2h_team_a_wins=h2h_team_a_wins,
            h2h_team_b_wins=h2h_team_b_wins,
            h2h_draws=h2h_draws,
            h2h_avg_goals=h2h_avg_goals,
            home_last5_goals_for=home_last5_goals_for,
            home_last5_goals_against=home_last5_goals_against,
            away_last5_goals_for=away_last5_goals_for,
            away_last5_goals_against=away_last5_goals_against,
            evidence_text=evidence_text,
            context_source_ids=", ".join(context_source_ids) or "none",
        )

        # Query the AI provider for adjustments
        ai_adjustment = await self._get_ai_adjustment(system_prompt, user_prompt, match_input)
        ai_adjustment = self._validate_adjustment_sources(
            ai_adjustment, ai_features, context_source_ids
        )

        # Blend AI adjustments with statistical adjustments
        adjustment = self._blend_adjustments(ai_adjustment, statistical_adjustment)

        # Enforce caps
        adjustment = self._enforce_caps(adjustment)

        # Check if there is any actual adjustment (lambda or market-level)
        has_adjustment = (
            abs(adjustment.home_attack_adjustment) > 0
            or abs(adjustment.away_attack_adjustment) > 0
            or abs(adjustment.home_defense_adjustment) > 0
            or abs(adjustment.away_defense_adjustment) > 0
            or abs(adjustment.home_win_adjustment) > 0
            or abs(adjustment.draw_win_adjustment) > 0
            or abs(adjustment.away_win_adjustment) > 0
            or abs(adjustment.btts_adjustment) > 0
            or abs(adjustment.over_2_5_adjustment) > 0
        )

        if not has_adjustment:
            return AIAdjustedPrediction(
                base_model_result=base_result,
                ai_adjustment=adjustment,
                adjusted_model_result=base_result,
                adjustment_applied=False,
                explanation="No AI adjustment applied based on available evidence.",
            )

        # Apply adjustment to lambdas
        adjusted_lambda_home = base_result.lambda_home + adjustment.home_attack_adjustment
        adjusted_lambda_away = base_result.lambda_away + adjustment.away_attack_adjustment

        # Apply defense adjustments to the opponent's effective lambda
        adjusted_lambda_home += adjustment.away_defense_adjustment
        adjusted_lambda_away += adjustment.home_defense_adjustment

        # Ensure lambdas remain positive
        adjusted_lambda_home = max(0.05, adjusted_lambda_home)
        adjusted_lambda_away = max(0.05, adjusted_lambda_away)

        # Recalculate the score matrix with adjusted lambdas
        model = PoissonModel()
        home_dist = [model._poisson_pmf(k, adjusted_lambda_home) for k in range(model.max_goals + 1)]
        away_dist = [model._poisson_pmf(k, adjusted_lambda_away) for k in range(model.max_goals + 1)]

        matrix: list[list[float]] = []
        for h in range(model.max_goals + 1):
            row = [home_dist[h] * away_dist[a] for a in range(model.max_goals + 1)]
            matrix.append(row)

        adjusted_result = ModelResult(
            model="poisson-ai",
            model_version=self.VERSION,
            lambda_home=adjusted_lambda_home,
            lambda_away=adjusted_lambda_away,
            home_goal_distribution=home_dist,
            away_goal_distribution=away_dist,
            score_matrix=matrix,
            max_goals=model.max_goals,
            data_quality=base_result.data_quality,
            model_parameters={
                **base_result.model_parameters,
                "ai_adjustment_applied": True,
                "ai_adjustment_version": self.VERSION,
            },
            feature_snapshot={
                **base_result.feature_snapshot,
                "ai_features": ai_features.__dict__,
                "ai_adjustment": adjustment.model_dump(),
            },
            market_adjustments={
                "home_win": adjustment.home_win_adjustment,
                "draw_win": adjustment.draw_win_adjustment,
                "away_win": adjustment.away_win_adjustment,
                "btts": adjustment.btts_adjustment,
                "over_2_5": adjustment.over_2_5_adjustment,
            },
        )

        explanation = self._build_adjustment_explanation(
            base_result, adjustment, ai_features
        )

        return AIAdjustedPrediction(
            base_model_result=base_result,
            ai_adjustment=adjustment,
            adjusted_model_result=adjusted_result,
            adjustment_applied=True,
            explanation=explanation,
        )

    async def _get_ai_adjustment(
        self, system_prompt: str, user_prompt: str, match_input: PredictionInput | None = None
    ) -> AIFeatureAdjustment:
        """Query the AI provider for adjustment values."""
        if self._ai_provider is None:
            from ai.factory import get_ai_provider
            try:
                self._ai_provider = get_ai_provider()
            except Exception as exc:
                logger.warning("AI adjustment provider initialization failed: %s", exc)
                return AIFeatureAdjustment()

        adjustment_schema = {
            "type": "object",
            "properties": {
                "home_attack_adjustment": {"type": "number"},
                "away_attack_adjustment": {"type": "number"},
                "home_defense_adjustment": {"type": "number"},
                "away_defense_adjustment": {"type": "number"},
                "home_win_adjustment": {"type": "number"},
                "draw_win_adjustment": {"type": "number"},
                "away_win_adjustment": {"type": "number"},
                "btts_adjustment": {"type": "number"},
                "over_2_5_adjustment": {"type": "number"},
                "confidence": {"type": "number"},
                "reason_codes": {"type": "array", "items": {"type": "string"}},
                "source_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "home_attack_adjustment",
                "away_attack_adjustment",
                "home_defense_adjustment",
                "away_defense_adjustment",
                "home_win_adjustment",
                "draw_win_adjustment",
                "away_win_adjustment",
                "btts_adjustment",
                "over_2_5_adjustment",
                "confidence",
                "reason_codes",
                "source_ids",
            ],
            "additionalProperties": False,
        }

        try:
            result = await self._ai_provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=adjustment_schema,
            )

            if result:
                return AIFeatureAdjustment(**result)
            else:
                return AIFeatureAdjustment()
        except Exception as exc:
            logger.warning("AI adjustment query failed; using statistical prediction: %s", exc)
            return AIFeatureAdjustment()

    def _fallback_adjustment(
        self, match_input: PredictionInput | None
    ) -> AIFeatureAdjustment:
        """Return no adjustment when AI cannot make an evidence-based call."""
        return AIFeatureAdjustment()

    @staticmethod
    def _available_context_source_ids(
        ai_features: AIFeatureVector,
        match_input: PredictionInput,
    ) -> list[str]:
        """Create auditable IDs for structured, non-web match data."""
        ids: list[str] = []
        if any((
            ai_features.home_league_position is not None,
            ai_features.away_league_position is not None,
            ai_features.home_standing_points_per_game is not None,
            ai_features.away_standing_points_per_game is not None,
        )):
            ids.append("match_context:league_standings")
        if any((
            ai_features.home_avg_goals_per_game is not None,
            ai_features.away_avg_goals_per_game is not None,
            getattr(getattr(match_input, "home_team_stats", None), "goals_for", None) is not None,
            getattr(getattr(match_input, "away_team_stats", None), "goals_for", None) is not None,
        )):
            ids.append("match_context:season_goals")
        recent_fixtures = (
            list(getattr(match_input, "home_recent_fixture", []) or [])
            + list(getattr(match_input, "away_recent_fixture", []) or [])
        )
        if any((
            ai_features.home_btts_rate is not None,
            ai_features.away_btts_rate is not None,
            ai_features.home_over_2_5_rate is not None,
            ai_features.away_over_2_5_rate is not None,
            any(
                getattr(fixture, "is_finished", False)
                and getattr(fixture, "home_score", None) is not None
                and getattr(fixture, "away_score", None) is not None
                for fixture in recent_fixtures
            ),
        )):
            ids.append("match_context:recent_form")
        if getattr(match_input, "h2h", None) is not None or ai_features.h2h_record:
            ids.append("match_context:head_to_head")
        return ids

    @staticmethod
    def _validate_adjustment_sources(
        adjustment: AIFeatureAdjustment,
        ai_features: AIFeatureVector,
        context_source_ids: list[str] | None = None,
    ) -> AIFeatureAdjustment:
        """Reject nonzero AI adjustments that cite no supplied research source."""
        valid_source_ids: set[str] = set()
        for collection_name in ("injuries", "suspensions", "lineups", "team_news"):
            for item in getattr(ai_features, collection_name, []) or []:
                if isinstance(item, dict):
                    valid_source_ids.update(
                        source_id for source_id in item.get("source_ids", [])
                        if isinstance(source_id, str) and source_id
                    )
        valid_source_ids.update(
            item["url"] for item in ai_features.search_context
            if isinstance(item, dict) and isinstance(item.get("url"), str) and item["url"]
        )
        valid_source_ids.update(context_source_ids or [])

        adjustment_values = (
            adjustment.home_attack_adjustment,
            adjustment.away_attack_adjustment,
            adjustment.home_defense_adjustment,
            adjustment.away_defense_adjustment,
            adjustment.home_win_adjustment,
            adjustment.draw_win_adjustment,
            adjustment.away_win_adjustment,
            adjustment.btts_adjustment,
            adjustment.over_2_5_adjustment,
        )
        if any(value != 0 for value in adjustment_values) and adjustment.source_ids:
            if not set(adjustment.source_ids).issubset(valid_source_ids):
                logger.warning(
                    "Discarding AI adjustment with unsupported source IDs; "
                    "using the statistical prediction"
                )
                return AIFeatureAdjustment()
        return adjustment.model_copy(
            update={"source_ids": [
                source_id for source_id in adjustment.source_ids
                if source_id in valid_source_ids
            ]}
        )

    def _compute_statistical_adjustments(
        self,
        ai_features: AIFeatureVector,
    ) -> AIFeatureAdjustment:
        """Compute bounded adjustments from H2H and league context.

        League standing (position and points-per-game gap) carries more
        weight than individual signals. A team with a clear standing
        advantage — especially the away team — gets a positive adjustment.
        """
        home_attack_adj = 0.0
        away_attack_adj = 0.0
        home_defense_adj = 0.0
        away_defense_adj = 0.0
        home_win_adj = 0.0
        draw_win_adj = 0.0
        away_win_adj = 0.0
        reason_codes: list[str] = []

        # League position advantage (lower position number is better for home)
        # League standing should carry significant weight — a team higher in
        # the table (whether home or away) is more likely to win, score BTTS,
        # and play in over-2.5 games.
        if ai_features.league_position_advantage is not None:
            if ai_features.league_position_advantage > 0:
                # A position gap is a weak supporting signal; do not turn
                # ordinal rank directly into a large goal-rate change.
                pos_weight = min(0.05, ai_features.league_position_advantage * 0.004)
                home_attack_adj += pos_weight
                home_win_adj += min(0.02, pos_weight * 0.2)
                reason_codes.append("home_league_position_advantage")
            elif ai_features.league_position_advantage < 0:
                pos_weight = min(0.05, abs(ai_features.league_position_advantage) * 0.004)
                away_attack_adj += pos_weight
                away_win_adj += min(0.02, pos_weight * 0.2)
                reason_codes.append("away_league_position_advantage")

        # Standing PPG advantage — points per game is a stronger signal
        # than position alone; weight it heavily.
        if ai_features.standing_ppg_advantage is not None:
            ppg_adj = max(-0.08, min(0.08, ai_features.standing_ppg_advantage * 0.04))
            if ppg_adj > 0:
                home_attack_adj += ppg_adj
                home_win_adj += min(0.02, ppg_adj * 0.2)
                reason_codes.append("home_standing_ppg_advantage")
            elif ppg_adj < 0:
                away_attack_adj += abs(ppg_adj)
                away_win_adj += min(0.02, abs(ppg_adj) * 0.2)
                reason_codes.append("away_standing_ppg_advantage")

        # Average goals per game advantage
        if ai_features.avg_goals_advantage is not None:
            gpg_adj = max(-0.06, min(0.06, ai_features.avg_goals_advantage * 0.04))
            if gpg_adj > 0:
                home_attack_adj += gpg_adj
                reason_codes.append("avg_goals_advantage")
            elif gpg_adj < 0:
                away_attack_adj += abs(gpg_adj)
                reason_codes.append("avg_goals_disadvantage")

        # H2H head-to-head ratio — also consider win counts and avg goals
        if ai_features.h2h_record is not None:
            h2h_ratio = ai_features.h2h_record.get("home_win_ratio", None)
            h2h_team_a_wins = ai_features.h2h_record.get("team_a_wins", None)
            h2h_team_b_wins = ai_features.h2h_record.get("team_b_wins", None)
            h2h_avg_goals = ai_features.h2h_record.get("avg_goals_per_game", None)

            # Win ratio adjustment
            if h2h_ratio is not None:
                h2h_adj = max(-0.04, min(0.04, (h2h_ratio - 0.5) * 0.08))
                if h2h_adj > 0:
                    home_attack_adj += h2h_adj
                    home_win_adj += min(0.01, h2h_adj * 0.2)
                    reason_codes.append("h2h_advantage")
                elif h2h_adj < 0:
                    away_attack_adj += abs(h2h_adj)
                    away_win_adj += min(0.01, abs(h2h_adj) * 0.2)
                    reason_codes.append("h2h_disadvantage")

            # H2H goal volume: high-scoring H2H meetings suggest over-2.5
            if h2h_avg_goals is not None and h2h_avg_goals > 2.5:
                over_adj = min(0.10, (h2h_avg_goals - 2.5) * 0.04)
                home_attack_adj += over_adj
                away_attack_adj += over_adj
                reason_codes.append("h2h_high_scoring")
            elif h2h_avg_goals is not None and h2h_avg_goals < 2.5:
                under_adj = min(0.10, (2.5 - h2h_avg_goals) * 0.04)
                home_defense_adj -= under_adj
                away_defense_adj -= under_adj
                reason_codes.append("h2h_low_scoring")

            # H2H win count differential
            if h2h_team_a_wins is not None and h2h_team_b_wins is not None:
                total = h2h_team_a_wins + h2h_team_b_wins + (ai_features.h2h_record.get("draws", 0) or 0)
                if total >= 3:
                    win_gap = h2h_team_a_wins - h2h_team_b_wins
                    if win_gap > 0:
                        home_win_adj += min(0.04, win_gap * 0.02)
                        reason_codes.append("h2h_win_count_advantage")
                    elif win_gap < 0:
                        away_win_adj += min(0.04, abs(win_gap) * 0.02)
                        reason_codes.append("h2h_win_count_disadvantage")

        # BTTS rate advantage — teams with higher recent BTTS may produce
        # more goals across both sides (affects both attack)
        if (
            ai_features.home_btts_rate is not None
            and ai_features.away_btts_rate is not None
        ):
            btts_diff = ai_features.home_btts_rate - ai_features.away_btts_rate
            if abs(btts_diff) >= 0.05:
                btts_adj = btts_diff * 0.15
                if btts_adj > 0:
                    home_attack_adj += min(0.20, btts_adj)
                    reason_codes.append("home_btts_advantage")
                else:
                    away_attack_adj += min(0.20, abs(btts_adj))
                    reason_codes.append("away_btts_advantage")

        # Over 2.5 rate advantage — teams that exceed 2.5 more often
        # have higher scoring profiles
        if (
            ai_features.home_over_2_5_rate is not None
            and ai_features.away_over_2_5_rate is not None
        ):
            ou_diff = ai_features.home_over_2_5_rate - ai_features.away_over_2_5_rate
            if abs(ou_diff) >= 0.05:
                ou_adj = ou_diff * 0.15
                if ou_adj > 0:
                    home_attack_adj += min(0.20, ou_adj)
                    reason_codes.append("home_over_2_5_advantage")
                else:
                    away_attack_adj += min(0.20, abs(ou_adj))
                    reason_codes.append("away_over_2_5_advantage")

        return AIFeatureAdjustment(
            home_attack_adjustment=round(home_attack_adj, 4),
            away_attack_adjustment=round(away_attack_adj, 4),
            home_defense_adjustment=round(home_defense_adj, 4),
            away_defense_adjustment=round(away_defense_adj, 4),
            home_win_adjustment=round(home_win_adj, 4),
            draw_win_adjustment=round(draw_win_adj, 4),
            away_win_adjustment=round(away_win_adj, 4),
            btts_adjustment=0.0,
            over_2_5_adjustment=0.0,
            confidence=0.3,
            reason_codes=reason_codes,
            source_ids=[],
        )

    def _blend_adjustments(
        self,
        ai_adjustment: AIFeatureAdjustment,
        statistical_adjustment: AIFeatureAdjustment,
    ) -> AIFeatureAdjustment:
        """Blend AI and statistical adjustments.

        Statistical adjustments provide a baseline weight to H2H/league
        signals, while the AI adjustment provides context-aware modifications.
        The statistical adjustment is weighted at 60% when no AI adjustment
        exists, and 20% otherwise (AI insight takes priority when available).
        """
        stat_weight = 0.2 if any([
            ai_adjustment.home_attack_adjustment,
            ai_adjustment.away_attack_adjustment,
            ai_adjustment.home_defense_adjustment,
            ai_adjustment.away_defense_adjustment,
            ai_adjustment.home_win_adjustment,
            ai_adjustment.draw_win_adjustment,
            ai_adjustment.away_win_adjustment,
            ai_adjustment.btts_adjustment,
            ai_adjustment.over_2_5_adjustment,
        ]) else 0.6

        blended = AIFeatureAdjustment(
            home_attack_adjustment=round(
                ai_adjustment.home_attack_adjustment
                + statistical_adjustment.home_attack_adjustment * stat_weight,
                4,
            ),
            away_attack_adjustment=round(
                ai_adjustment.away_attack_adjustment
                + statistical_adjustment.away_attack_adjustment * stat_weight,
                4,
            ),
            home_defense_adjustment=round(
                ai_adjustment.home_defense_adjustment
                + statistical_adjustment.home_defense_adjustment * stat_weight,
                4,
            ),
            away_defense_adjustment=round(
                ai_adjustment.away_defense_adjustment
                + statistical_adjustment.away_defense_adjustment * stat_weight,
                4,
            ),
            home_win_adjustment=round(
                ai_adjustment.home_win_adjustment
                + statistical_adjustment.home_win_adjustment * stat_weight,
                4,
            ),
            draw_win_adjustment=round(
                ai_adjustment.draw_win_adjustment
                + statistical_adjustment.draw_win_adjustment * stat_weight,
                4,
            ),
            away_win_adjustment=round(
                ai_adjustment.away_win_adjustment
                + statistical_adjustment.away_win_adjustment * stat_weight,
                4,
            ),
            btts_adjustment=ai_adjustment.btts_adjustment,
            over_2_5_adjustment=ai_adjustment.over_2_5_adjustment,
            confidence=max(ai_adjustment.confidence, statistical_adjustment.confidence),
            reason_codes=list(dict.fromkeys(
                ai_adjustment.reason_codes + statistical_adjustment.reason_codes
            )),
            source_ids=ai_adjustment.source_ids,
        )

        return blended

    def _enforce_caps(self, adjustment: AIFeatureAdjustment) -> AIFeatureAdjustment:
        """Enforce configured maximum adjustment caps."""
        def finite_clamp(value: float, cap: float) -> float:
            return max(-cap, min(cap, value)) if math.isfinite(value) else 0.0

        home_attack = finite_clamp(adjustment.home_attack_adjustment, self._max_attack_adjustment)
        away_attack = finite_clamp(adjustment.away_attack_adjustment, self._max_attack_adjustment)
        home_defense = finite_clamp(adjustment.home_defense_adjustment, self._max_defense_adjustment)
        away_defense = finite_clamp(adjustment.away_defense_adjustment, self._max_defense_adjustment)

        # Market-level adjustments are bounded to ±0.25
        market_cap = 0.25
        return AIFeatureAdjustment(
            home_attack_adjustment=round(home_attack, 4),
            away_attack_adjustment=round(away_attack, 4),
            home_defense_adjustment=round(home_defense, 4),
            away_defense_adjustment=round(away_defense, 4),
            home_win_adjustment=round(
                finite_clamp(adjustment.home_win_adjustment, market_cap), 4
            ),
            draw_win_adjustment=round(
                finite_clamp(adjustment.draw_win_adjustment, market_cap), 4
            ),
            away_win_adjustment=round(
                finite_clamp(adjustment.away_win_adjustment, market_cap), 4
            ),
            btts_adjustment=round(
                finite_clamp(adjustment.btts_adjustment, market_cap), 4
            ),
            over_2_5_adjustment=round(
                finite_clamp(adjustment.over_2_5_adjustment, market_cap), 4
            ),
            confidence=finite_clamp(adjustment.confidence, 1.0),
            reason_codes=adjustment.reason_codes,
            source_ids=adjustment.source_ids,
        )

    def _build_adjustment_explanation(
        self,
        base_result: ModelResult,
        adjustment: AIFeatureAdjustment,
        ai_features: AIFeatureVector,
    ) -> str:
        """Build a human-readable explanation of the AI adjustment."""
        if not adjustment.home_attack_adjustment and not adjustment.away_attack_adjustment:
            if not adjustment.home_defense_adjustment and not adjustment.away_defense_adjustment:
                if (
                    not adjustment.home_win_adjustment
                    and not adjustment.draw_win_adjustment
                    and not adjustment.away_win_adjustment
                    and not adjustment.btts_adjustment
                    and not adjustment.over_2_5_adjustment
                ):
                    return "No AI adjustment applied based on available evidence."

        parts: list[str] = []
        parts.append(f"AI adjustment applied (confidence: {adjustment.confidence:.2f}).")

        if adjustment.reason_codes:
            parts.append(f"Reason codes: {', '.join(adjustment.reason_codes)}.")

        if adjustment.home_attack_adjustment != 0:
            parts.append(
                f"Home attack adjusted by {adjustment.home_attack_adjustment:+.4f} "
                f"(lambda: {base_result.lambda_home:.4f} -> "
                f"{base_result.lambda_home + adjustment.home_attack_adjustment:.4f})."
            )
        if adjustment.away_attack_adjustment != 0:
            parts.append(
                f"Away attack adjusted by {adjustment.away_attack_adjustment:+.4f} "
                f"(lambda: {base_result.lambda_away:.4f} -> "
                f"{base_result.lambda_away + adjustment.away_attack_adjustment:.4f})."
            )

        # Market-level adjustments
        if (
            adjustment.home_win_adjustment != 0
            or adjustment.draw_win_adjustment != 0
            or adjustment.away_win_adjustment != 0
        ):
            win_changes = []
            if adjustment.home_win_adjustment != 0:
                win_changes.append(f"home +{adjustment.home_win_adjustment:+.2%}")
            if adjustment.draw_win_adjustment != 0:
                win_changes.append(f"draw {adjustment.draw_win_adjustment:+.2%}")
            if adjustment.away_win_adjustment != 0:
                win_changes.append(f"away {adjustment.away_win_adjustment:+.2%}")
            parts.append(f"Market-level WIN adjustments: {', '.join(win_changes)}.")

        if adjustment.btts_adjustment != 0:
            parts.append(f"BTTS adjusted by {adjustment.btts_adjustment:+.2%}")
        if adjustment.over_2_5_adjustment != 0:
            parts.append(
                f"Over 2.5 adjusted by {adjustment.over_2_5_adjustment:+.2%}"
            )

        if adjustment.source_ids:
            parts.append(f"Based on {len(adjustment.source_ids)} evidence source(s).")

        return " ".join(parts)
