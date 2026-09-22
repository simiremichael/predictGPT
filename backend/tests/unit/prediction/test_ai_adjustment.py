"""Tests for the AI adjustment layer."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.feature_builder import AIFeatureBuilder, AIFeatureVector
from prediction.base import PredictionInput
from prediction.ai_adjustment import AIAdjustmentLayer
from prediction.poisson import PoissonModel
from web_research.schemas import (
    EvidenceStatus,
    InjuryEvidence,
    MatchResearchResult,
    ResearchSource,
)


@pytest.fixture
def match_input() -> PredictionInput:
    return PredictionInput(
        match_id="test-match-1",
        home_team_id="h1",
        away_team_id="a1",
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        league_id="premier_league",
        kickoff_at=datetime.utcnow() + timedelta(days=1),
    )


@pytest.fixture
def base_result() -> Any:
    model = PoissonModel()
    return model.predict(PredictionInput(
        match_id="test",
        home_team_id="h1",
        away_team_id="a1",
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        league_id="premier_league",
        kickoff_at=datetime.utcnow() + timedelta(days=1),
    ))


class TestAIAdjustmentLayer:
    @pytest.mark.asyncio
    async def test_no_research_no_adjustment(
        self, match_input: PredictionInput, base_result: Any
    ) -> None:
        """When no research is available, no adjustment is applied."""
        layer = AIAdjustmentLayer()
        ai_features = AIFeatureBuilder().build(None)

        result = await layer.apply_adjustment(
            match_input, base_result, MagicMock(), ai_features
        )

        assert result.adjustment_applied is False
        assert result.ai_adjustment.home_attack_adjustment == 0.0
        assert result.ai_adjustment.away_attack_adjustment == 0.0

    @pytest.mark.asyncio
    async def test_adjustment_caps_enforced(self, match_input: PredictionInput, base_result: Any) -> None:
        """AI adjustment never exceeds configured caps."""
        layer = AIAdjustmentLayer()

        ai_features = AIFeatureVector(
            research_available=True,
            evidence_text="Test evidence",
            injuries=[{
                "player": "Player",
                "position": "forward",
                "evidence_status": EvidenceStatus.REPORTED,
                "confidence": 0.9,
            }],
        )

        with patch.object(layer, "_ai_provider", AsyncMock()):
            layer._ai_provider.generate_structured = AsyncMock(
                return_value={
                    "home_attack_adjustment": 999.0,  # Way over cap
                    "away_attack_adjustment": 999.0,
                    "home_defense_adjustment": 999.0,
                    "away_defense_adjustment": 999.0,
                    "confidence": 0.9,
                    "reason_codes": ["test"],
                    "source_ids": ["s1"],
                }
            )

            result = await layer.apply_adjustment(
                match_input, base_result, MagicMock(), ai_features
            )

            assert result.adjustment_applied is True
            assert abs(result.ai_adjustment.home_attack_adjustment) <= 0.15
            assert abs(result.ai_adjustment.away_attack_adjustment) <= 0.15
            assert abs(result.ai_adjustment.home_defense_adjustment) <= 0.15
            assert abs(result.ai_adjustment.away_defense_adjustment) <= 0.15

    @pytest.mark.asyncio
    async def test_no_evidence_no_adjustment(
        self, match_input: PredictionInput, base_result: Any
    ) -> None:
        """When evidence text is empty, no adjustment is applied."""
        layer = AIAdjustmentLayer()

        ai_features = AIFeatureVector(
            research_available=True,
            evidence_text="No evidence found.",
            injuries=[],
            suspensions=[],
            lineups=[],
            team_news=[],
        )

        result = await layer.apply_adjustment(
            match_input, base_result, MagicMock(), ai_features
        )

        assert result.adjustment_applied is False

    @pytest.mark.asyncio
    async def test_adjusted_lambdas_recalculate_score_matrix(
        self, match_input: PredictionInput, base_result: Any
    ) -> None:
        """After adjustment, the score matrix is recalculated."""
        layer = AIAdjustmentLayer()

        ai_features = AIFeatureVector(
            research_available=True,
            evidence_text="Key attacker injured",
            injuries=[{
                "player": "Star Forward",
                "position": "forward",
                "evidence_status": EvidenceStatus.CONFIRMED,
                "confidence": 0.9,
            }],
        )

        with patch.object(layer, "_ai_provider", AsyncMock()):
            layer._ai_provider.generate_structured = AsyncMock(
                return_value={
                    "home_attack_adjustment": -0.1,
                    "away_attack_adjustment": 0.0,
                    "home_defense_adjustment": -0.05,
                    "away_defense_adjustment": 0.0,
                    "confidence": 0.85,
                    "reason_codes": ["key_attacker_absence"],
                    "source_ids": ["src1"],
                }
            )

            result = await layer.apply_adjustment(
                match_input, base_result, MagicMock(), ai_features
            )

            assert result.adjustment_applied is True
            assert result.adjusted_model_result.model == "poisson-ai"
            # Base lambda should differ from adjusted
            assert result.adjusted_model_result.lambda_home != result.base_model_result.lambda_home

    @pytest.mark.asyncio
    async def test_ai_failure_falls_back_to_base(
        self, match_input: PredictionInput, base_result: Any
    ) -> None:
        """If AI fails, fall back to the base prediction."""
        layer = AIAdjustmentLayer()

        ai_features = AIFeatureVector(
            research_available=True,
            evidence_text="Evidence: key player injured",
            injuries=[{
                "player": "Star Forward",
                "position": "forward",
                "evidence_status": EvidenceStatus.REPORTED,
                "confidence": 0.9,
            }],
        )

        with patch.object(layer, "_ai_provider", AsyncMock()):
            layer._ai_provider.generate_structured = AsyncMock(side_effect=Exception("AI error"))

            result = await layer.apply_adjustment(
                match_input, base_result, MagicMock(), ai_features
            )

            # Should fall back to base result
            assert result.adjustment_applied is False
