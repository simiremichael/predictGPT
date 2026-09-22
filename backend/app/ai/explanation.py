"""AI explanation generator.

Generates human-readable explanations from statistical predictions combined
with research evidence. Explanations are based on actual prediction data and
stored evidence -- they never invent reasoning after the fact.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ai.base import AIProvider
from ai.exceptions import AIError
from ai.prompts import (
    EXPLANATION_SYSTEM_PROMPT,
    EXPLANATION_USER_PROMPT,
)
from core.config import get_settings
from core.logging import get_logger
from prediction.base import ModelResult
from prediction.schemas import PredictionOutputSchema
from web_research.schemas import MatchResearchResult

logger = get_logger(__name__)


class AIExplanationService:
    """Generates human-readable explanations for predictions."""

    VERSION = "explanation-v1.0.0"

    def __init__(self, ai_provider: AIProvider | None = None) -> None:
        self._ai_provider = ai_provider
        self._settings = get_settings()

    async def get_provider(self) -> AIProvider:
        if self._ai_provider is None:
            from ai.factory import get_ai_provider

            self._ai_provider = get_ai_provider()
        return self._ai_provider

    async def generate_explanation(
        self,
        match_input: Any,
        prediction: PredictionOutputSchema,
        research_result: MatchResearchResult | None,
        model_result: ModelResult | None = None,
    ) -> str:
        """Generate a human-readable explanation for a prediction.

        Falls back to a deterministic template if AI is unavailable.
        """
        evidence_summary = "No web research evidence available."
        research_available = False
        research_data_quality = "N/A"

        if research_result:
            research_available = True
            research_data_quality = f"{research_result.data_quality:.2f}"
            evidence_summary = self._build_evidence_summary(research_result)

        system_prompt = EXPLANATION_SYSTEM_PROMPT
        user_prompt = EXPLANATION_USER_PROMPT.format(
            home_team=prediction.match_home_team,
            away_team=prediction.match_away_team,
            competition=getattr(match_input, "league_id", "Unknown"),
            kickoff=prediction.match_kickoff.isoformat() if prediction.match_kickoff else "TBD",
            lambda_home=prediction.expected_goals.home,
            lambda_away=prediction.expected_goals.away,
            home_prob=prediction.result_probabilities.home,
            draw_prob=prediction.result_probabilities.draw,
            away_prob=prediction.result_probabilities.away,
            over_25_prob=prediction.markets.over_under.over_2_5,
            btts_prob=prediction.markets.btts.yes,
            top_scorelines=", ".join(
                f"{s.home_goals}-{s.away_goals} ({s.probability:.1%})"
                for s in prediction.top_4_scorelines
            ),
            model_name=prediction.model,
            model_version=prediction.model_version,
            data_quality=f"{prediction.data_quality:.2f}",
            research_available=research_available,
            research_data_quality=research_data_quality,
            evidence_summary=evidence_summary,
        )

        try:
            provider = await self.get_provider()
            text = await provider.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1000,
            )
            if text and len(text) > 50:
                return text
        except Exception as exc:
            logger.warning("AI explanation generation failed, using fallback: %s", exc)

        return self._fallback_explanation(
            prediction, research_result, evidence_summary
        )

    def _build_evidence_summary(
        self, research_result: MatchResearchResult
    ) -> str:
        """Build a concise summary of research evidence."""
        parts: list[str] = []

        if research_result.injuries:
            injury_summary = ", ".join(
                f"{i.player} ({i.evidence_status})"
                for i in research_result.injuries[:5]
            )
            parts.append(f"Injuries: {injury_summary}")

        if research_result.suspensions:
            susp_summary = ", ".join(
                f"{s.player} ({s.suspension_status})"
                for s in research_result.suspensions[:5]
            )
            parts.append(f"Suspensions: {susp_summary}")

        if research_result.lineups:
            for lineup in research_result.lineups:
                parts.append(f"Lineup ({lineup.team}): status={lineup.status}")

        if research_result.team_news:
            news_summary = ", ".join(
                f"{n.news_type} ({n.team})"
                for n in research_result.team_news[:5]
            )
            parts.append(f"News: {news_summary}")

        if research_result.conflicts:
            parts.append(f"Conflicts: {len(research_result.conflicts)} detected")

        parts.append(f"{len(research_result.sources)} sources, quality {research_result.data_quality:.2f}")

        return "\n".join(parts) if parts else "No significant evidence found."

    def _fallback_explanation(
        self,
        prediction: PredictionOutputSchema,
        research_result: MatchResearchResult | None,
        evidence_summary: str,
    ) -> str:
        """Deterministic fallback explanation when AI is unavailable."""
        lines: list[str] = []
        lines.append("Statistical Prediction Explanation")
        lines.append("=" * 40)
        lines.append("")
        lines.append(
            f"The Poisson model ({prediction.model} v{prediction.model_version}) "
            f"predicts {prediction.match_home_team} vs {prediction.match_away_team}."
        )
        lines.append("")
        lines.append(f"Expected goals: {prediction.expected_goals.home:.2f} - {prediction.expected_goals.away:.2f}")
        lines.append(f"Result probabilities: H={prediction.result_probabilities.home:.1%}, "
                      f"D={prediction.result_probabilities.draw:.1%}, "
                      f"A={prediction.result_probabilities.away:.1%}")
        lines.append("")
        lines.append("Top scorelines:")
        for i, sl in enumerate(prediction.top_4_scorelines[:4], 1):
            lines.append(f"  {i}. {sl.home_goals}-{sl.away_goals} ({sl.probability:.1%})")

        if research_result:
            lines.append("")
            lines.append("Research evidence:")
            lines.append(evidence_summary)
        else:
            lines.append("")
            lines.append("No web research evidence available. Prediction based on statistical model only.")

        lines.append("")
        lines.append(f"Data quality: {prediction.data_quality:.2f}")
        lines.append(f"Model confidence: {prediction.model_confidence:.1%}")

        return "\n".join(lines)

    async def close(self) -> None:
        if self._ai_provider:
            await self._ai_provider.close()