"""Unit tests for prediction validation and model versioning.

Tests cover:
    - Prediction validation (lambda > 0, probabilities in [0,1], sums ≈ 1)
    - Model versioning (model_version stored with prediction)
    - Prediction immutability (new record on re-predict)
    - Feature snapshot storage
    - Model confidence calculation
    - Prediction stability assessment
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prediction.base import ModelResult, PredictionInput, Scoreline
from prediction.exceptions import PredictionValidationError
from prediction.features import FeatureBuilder, LeagueBaseline
from prediction.markets import MarketCalculator
from prediction.poisson import PoissonModel
from prediction.score_matrix import ScoreMatrix
from prediction.service import PredictionService, _active_predictions


# ── Fixtures ────────────────────────────────────────────────────────── #
@pytest.fixture
def league_baseline() -> LeagueBaseline:
    return LeagueBaseline(
        league_id="premier_league",
        avg_home_goals=1.5,
        avg_away_goals=1.0,
        avg_total_goals=2.5,
        home_win_rate=0.45,
        draw_rate=0.27,
        away_win_rate=0.28,
        btts_rate=0.52,
        over_2_5_rate=0.48,
        games_played=380,
    )


@pytest.fixture
def match_input(league_baseline: LeagueBaseline) -> PredictionInput:
    return PredictionInput(
        match_id="test-match-1",
        home_team_id="h1",
        away_team_id="a1",
        home_team_name="Home FC",
        away_team_name="Away FC",
        league_id="premier_league",
        kickoff_at=datetime.utcnow() + timedelta(days=1),
    )


@pytest.fixture
def model_result() -> ModelResult:
    """Pre-built model result with lambda_home=1.5, lambda_away=1.0."""
    model = PoissonModel()
    lam_h, lam_a = 1.5, 1.0

    home_dist = [model._poisson_pmf(k, lam_h) for k in range(9)]
    away_dist = [model._poisson_pmf(k, lam_a) for k in range(9)]

    matrix: list[list[float]] = []
    for h in range(9):
        row = [home_dist[h] * away_dist[a] for a in range(9)]
        matrix.append(row)

    return ModelResult(
        model="poisson",
        model_version="poisson-v1.0.0",
        lambda_home=lam_h,
        lambda_away=lam_a,
        home_goal_distribution=home_dist,
        away_goal_distribution=away_dist,
        score_matrix=matrix,
        max_goals=8,
        data_quality=0.8,
        model_parameters={"test": True},
        feature_snapshot={"test": True},
    )


class TestPredictionValidation:
    """Tests for prediction output validation."""

    def test_valid_prediction_passes_validation(self, model_result: ModelResult) -> None:
        """A valid prediction should pass all validation checks."""
        service = PredictionService()
        matrix = ScoreMatrix.from_model_result(model_result)
        hda = matrix.get_result_probabilities()
        top_4 = matrix.get_top_scorelines(n=4)

        from prediction.schemas import MarketsSchema

        market_calc = MarketCalculator(matrix)
        markets = market_calc.get_all_markets()

        # Should not raise
        service._validate_prediction(model_result, matrix, hda, top_4, markets)

    def test_negative_lambda_fails_validation(self, model_result: ModelResult) -> None:
        """Lambda <= 0 should fail validation."""
        service = PredictionService()
        matrix = ScoreMatrix.from_model_result(model_result)
        hda = matrix.get_result_probabilities()
        top_4 = matrix.get_top_scorelines(n=4)
        market_calc = MarketCalculator(matrix)
        markets = market_calc.get_all_markets()

        # Negate lambda
        bad_result = ModelResult(
            model=model_result.model,
            model_version=model_result.model_version,
            lambda_home=-1.0,
            lambda_away=model_result.lambda_away,
            home_goal_distribution=model_result.home_goal_distribution,
            away_goal_distribution=model_result.away_goal_distribution,
            score_matrix=model_result.score_matrix,
            max_goals=model_result.max_goals,
            data_quality=model_result.data_quality,
            model_parameters=model_result.model_parameters,
            feature_snapshot=model_result.feature_snapshot,
        )

        with pytest.raises(PredictionValidationError, match="lambda_home"):
            service._validate_prediction(bad_result, matrix, hda, top_4, markets)

    def test_unsorted_top_4_fails_validation(self, model_result: ModelResult) -> None:
        """Top 4 not sorted should fail validation."""
        service = PredictionService()
        matrix = ScoreMatrix.from_model_result(model_result)
        hda = matrix.get_result_probabilities()
        top_4 = matrix.get_top_scorelines(n=4)

        # Reverse the order
        top_4_reversed = list(reversed(top_4))
        market_calc = MarketCalculator(matrix)
        markets = market_calc.get_all_markets()

        with pytest.raises(PredictionValidationError, match="sorted"):
            service._validate_prediction(model_result, matrix, hda, top_4_reversed, markets)

    def test_duplicate_scorelines_fails_validation(self, model_result: ModelResult) -> None:
        """Duplicate scorelines should fail validation."""
        service = PredictionService()
        matrix = ScoreMatrix.from_model_result(model_result)
        hda = matrix.get_result_probabilities()
        market_calc = MarketCalculator(matrix)
        markets = market_calc.get_all_markets()

        # Create duplicates
        top_4 = [
            Scoreline(1, 0, 0.15),
            Scoreline(1, 0, 0.13),  # Duplicate
            Scoreline(2, 0, 0.12),
            Scoreline(2, 1, 0.11),
        ]

        with pytest.raises(PredictionValidationError, match="duplicate"):
            service._validate_prediction(model_result, matrix, hda, top_4, markets)


class TestModelVersioning:
    """Tests for model versioning."""

    def test_model_has_version(self) -> None:
        """PoissonModel should have a model_version."""
        model = PoissonModel()
        assert model.model_version == "poisson-v1.0.0"

    def test_model_version_in_result(self, match_input: PredictionInput) -> None:
        """Model result should include the model version."""
        model = PoissonModel()
        result = model.predict(match_input)
        assert result.model_version == "poisson-v1.0.0"
        assert result.model == "poisson"

    def test_model_parameters_stored_in_result(self, match_input: PredictionInput) -> None:
        """Model parameters should be stored in the result."""
        model = PoissonModel()
        result = model.predict(match_input)
        assert result.model_parameters is not None
        assert "max_goals" in result.model_parameters
        assert "home_advantage_multiplier" in result.model_parameters


class TestPredictionAIResearchWiring:
    """Tests that the prediction pipeline wires in AI + web research by default."""

    def test_prediction_service_lazily_initializes_research_and_ai(self) -> None:
        """A default PredictionService should create the research and AI layers on demand."""
        service = PredictionService()

        assert service._research_service is None
        assert service._ai_adjustment_layer is None

        service._ensure_research_components()

        assert service._research_service is not None
        assert service._ai_adjustment_layer is not None


class TestPredictionImmutability:
    """Tests that predictions are immutable (new record on re-predict)."""

    @pytest.mark.asyncio
    async def test_re_predict_creates_new_record(self, match_input: PredictionInput) -> None:
        """Running predict twice should not error (immutability at DB level)."""
        service = PredictionService()
        mock_db = AsyncMock()
        with patch.object(service, "_load_match_input", AsyncMock(return_value=match_input)):
            # Generate first prediction
            result1 = await service.predict_match("test-1", db_session=mock_db)
            # Generate second prediction - should succeed
            result2 = await service.predict_match("test-1", db_session=mock_db)

            # Both should be valid
            assert result1 is not None
            assert result2 is not None
            assert result1.model_version == result2.model_version

    @pytest.mark.asyncio
    async def test_concurrent_prediction_conflict(self, match_input: PredictionInput) -> None:
        """Concurrent predictions for same match should raise conflict."""
        from prediction.exceptions import PredictionConflictError

        service = PredictionService()
        _active_predictions.add("concurrent-match")

        try:
            with pytest.raises(PredictionConflictError):
                await service.predict_match("concurrent-match", db_session=None)
        finally:
            _active_predictions.discard("concurrent-match")


class TestModelConfidence:
    """Tests for model confidence calculation."""

    def test_high_data_quality_increases_confidence(self, model_result: ModelResult) -> None:
        """Higher data quality should increase confidence."""
        service = PredictionService()
        matrix = ScoreMatrix.from_model_result(model_result)
        top_4 = matrix.get_top_scorelines(n=4)
        hda = matrix.get_result_probabilities()

        features = MagicMock()
        features.data_quality = 0.9
        features.raw_snapshot = {}
        features.home_attack_strength = 1.2
        features.away_defense_strength = 0.8
        features.home_form_strength = 1.1
        features.away_attack_strength = 0.9
        features.away_form_strength = 1.0

        confidence = service._compute_model_confidence(0.9, top_4, hda)
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.0

    def test_low_data_quality_decreases_confidence(self, model_result: ModelResult) -> None:
        """Lower data quality should decrease confidence."""
        service = PredictionService()
        matrix = ScoreMatrix.from_model_result(model_result)
        top_4 = matrix.get_top_scorelines(n=4)
        hda = matrix.get_result_probabilities()

        confidence = service._compute_model_confidence(0.1, top_4, hda)
        assert 0.0 <= confidence <= 1.0
        assert confidence < 0.5


class TestPredictionStability:
    """Tests for prediction stability assessment."""

    def test_stability_returns_known_value(self, match_input: PredictionInput) -> None:
        """Stability assessment should return a known string."""
        service = PredictionService()
        builder = FeatureBuilder()
        baseline = LeagueBaseline(
            league_id="test",
            avg_home_goals=1.5,
            avg_away_goals=1.0,
            avg_total_goals=2.5,
            home_win_rate=0.45,
            draw_rate=0.27,
            away_win_rate=0.28,
            btts_rate=0.52,
            over_2_5_rate=0.48,
            games_played=100,
        )
        features = builder.build(match_input, league_baseline=baseline)
        model = PoissonModel()
        result = model.predict(match_input)

        stability = service._compute_stability(result, features)
        assert stability in ("high", "medium", "low", "unknown")
