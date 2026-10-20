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

    VERSION = "ai-adjustment-v1.0.0"

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
        if not ai_features.research_available:
            return AIAdjustedPrediction(
                base_model_result=base_result,
                ai_adjustment=AIFeatureAdjustment(),
                adjusted_model_result=base_result,
                adjustment_applied=False,
                explanation="No web research evidence available; using statistical model only.",
            )

        # Research can complete successfully without finding actionable match
        # evidence. In that case, keep the statistical prediction unchanged.
        if not any((
            ai_features.injuries,
            ai_features.suspensions,
            ai_features.lineups,
            ai_features.team_news,
            ai_features.search_context,
        )):
            return AIAdjustedPrediction(
                base_model_result=base_result,
                ai_adjustment=AIFeatureAdjustment(),
                adjusted_model_result=base_result,
                adjustment_applied=False,
                explanation="No actionable research evidence available; using statistical model only.",
            )

        # Always query AI when research is available so each match gets
        # context-aware adjustments (team names, league, base lambdas, evidence).
        evidence_text = ai_features.evidence_text or "No specific research evidence extracted."

        system_prompt = AI_ADJUSTMENT_SYSTEM_PROMPT.format(
            max_attack_adjustment=self._max_attack_adjustment,
            max_defense_adjustment=self._max_defense_adjustment,
        )

        user_prompt = AI_ADJUSTMENT_USER_PROMPT.format(
            home_team=match_input.home_team_name,
            away_team=match_input.away_team_name,
            league=match_input.league_id,
            lambda_home=base_result.lambda_home,
            lambda_away=base_result.lambda_away,
            evidence_text=evidence_text,
        )

        # Compute statistical adjustments from H2H and league context
        # These are blended with the AI's adjustments to ensure statistical
        # signals (league position, avg goals, H2H) have a consistent baseline
        statistical_adjustment = self._compute_statistical_adjustments(ai_features)

        # Query the AI provider for adjustments
        adjustment = await self._get_ai_adjustment(system_prompt, user_prompt, match_input)

        # Blend AI adjustments with statistical adjustments
        adjustment = self._blend_adjustments(adjustment, statistical_adjustment)

        # Enforce caps
        adjustment = self._enforce_caps(adjustment)

        # Check if there is any actual adjustment
        has_adjustment = (
            abs(adjustment.home_attack_adjustment) > 0
            or abs(adjustment.away_attack_adjustment) > 0
            or abs(adjustment.home_defense_adjustment) > 0
            or abs(adjustment.away_defense_adjustment) > 0
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
            except Exception:
                return AIFeatureAdjustment()

        adjustment_schema = {
            "type": "object",
            "properties": {
                "home_attack_adjustment": {"type": "number"},
                "away_attack_adjustment": {"type": "number"},
                "home_defense_adjustment": {"type": "number"},
                "away_defense_adjustment": {"type": "number"},
                "confidence": {"type": "number"},
                "reason_codes": {"type": "array", "items": {"type": "string"}},
                "source_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "home_attack_adjustment",
                "away_attack_adjustment",
                "home_defense_adjustment",
                "away_defense_adjustment",
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

    def _compute_statistical_adjustments(
        self,
        ai_features: AIFeatureVector,
    ) -> AIFeatureAdjustment:
        """Compute bounded adjustments from H2H and league context.

        These adjustments are blended with the AI's response to ensure
        statistical signals contribute consistently to the final prediction.
        """
        home_attack_adj = 0.0
        away_attack_adj = 0.0
        home_defense_adj = 0.0
        away_defense_adj = 0.0
        reason_codes: list[str] = []

        # League position advantage (lower position number is better for home)
        if ai_features.league_position_advantage is not None:
            if ai_features.league_position_advantage > 0:
                # Home team is higher in table (better position)
                home_attack_adj += min(0.3, ai_features.league_position_advantage * 0.02)
                away_defense_adj += min(0.3, ai_features.league_position_advantage * 0.02)
                reason_codes.append("league_position_advantage")
            elif ai_features.league_position_advantage < 0:
                # Away team is higher in table
                away_attack_adj += min(0.3, abs(ai_features.league_position_advantage) * 0.02)
                home_defense_adj += min(0.3, abs(ai_features.league_position_advantage) * 0.02)
                reason_codes.append("league_position_disadvantage")

        # Standing PPG advantage
        if ai_features.standing_ppg_advantage is not None:
            ppg_adj = ai_features.standing_ppg_advantage * 0.08
            if ppg_adj > 0:
                home_attack_adj += min(0.35, ppg_adj)
                away_defense_adj += min(0.35, ppg_adj)
                reason_codes.append("standing_ppg_advantage")
            elif ppg_adj < 0:
                away_attack_adj += min(0.35, abs(ppg_adj))
                home_defense_adj += min(0.35, abs(ppg_adj))
                reason_codes.append("standing_ppg_disadvantage")

        # Average goals per game advantage
        if ai_features.avg_goals_advantage is not None:
            gpg_adj = ai_features.avg_goals_advantage * 0.08
            if gpg_adj > 0:
                home_attack_adj += min(0.25, gpg_adj)
                away_defense_adj += min(0.25, gpg_adj)
                reason_codes.append("avg_goals_advantage")
            elif gpg_adj < 0:
                away_attack_adj += min(0.25, abs(gpg_adj))
                home_defense_adj += min(0.25, abs(gpg_adj))
                reason_codes.append("avg_goals_disadvantage")

        # H2H head-to-head ratio
        if ai_features.h2h_record is not None:
            h2h_ratio = ai_features.h2h_record.get("home_win_ratio", None)
            if h2h_ratio is not None:
                h2h_adj = (h2h_ratio - 0.5) * 0.5  # -0.25 to +0.25 range
                if h2h_adj > 0:
                    home_attack_adj += min(0.25, h2h_adj)
                    reason_codes.append("h2h_advantage")
                elif h2h_adj < 0:
                    away_attack_adj += min(0.25, abs(h2h_adj))
                    reason_codes.append("h2h_disadvantage")

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
            confidence=max(ai_adjustment.confidence, statistical_adjustment.confidence),
            reason_codes=list(dict.fromkeys(
                ai_adjustment.reason_codes + statistical_adjustment.reason_codes
            )),
            source_ids=ai_adjustment.source_ids,
        )

        return blended

    def _enforce_caps(self, adjustment: AIFeatureAdjustment) -> AIFeatureAdjustment:
        """Enforce configured maximum adjustment caps."""
        home_attack = max(-self._max_attack_adjustment, min(self._max_attack_adjustment, adjustment.home_attack_adjustment))
        away_attack = max(-self._max_attack_adjustment, min(self._max_attack_adjustment, adjustment.away_attack_adjustment))
        home_defense = max(-self._max_defense_adjustment, min(self._max_defense_adjustment, adjustment.home_defense_adjustment))
        away_defense = max(-self._max_defense_adjustment, min(self._max_defense_adjustment, adjustment.away_defense_adjustment))

        return AIFeatureAdjustment(
            home_attack_adjustment=round(home_attack, 4),
            away_attack_adjustment=round(away_attack, 4),
            home_defense_adjustment=round(home_defense, 4),
            away_defense_adjustment=round(away_defense, 4),
            confidence=adjustment.confidence,
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

        if adjustment.source_ids:
            parts.append(f"Based on {len(adjustment.source_ids)} evidence source(s).")

        return " ".join(parts)
