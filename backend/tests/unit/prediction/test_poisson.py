"""Unit tests for the Poisson probability and goal distribution calculations.

Tests cover:
    - Poisson PMF correctness
    - Goal distribution properties (sums to 1, non-negative)
    - Mathematical test fixture with known lambda values
    - Numerical edge cases (lambda <= 0, large lambda)
"""
from __future__ import annotations

import math

import pytest

from prediction.poisson import PoissonModel


class TestPoissonPMF:
    """Tests for the Poisson probability mass function."""

    def test_poisson_pmf_known_values(self) -> None:
        """Verify PMF against known mathematical values.

        P(X=0 | λ=1) = e^-1 ≈ 0.3679
        P(X=1 | λ=1) = e^-1 ≈ 0.3679
        P(X=2 | λ=1) = e^-1/2 ≈ 0.1839
        """
        model = PoissonModel()
        e = math.exp(-1)

        assert model._poisson_pmf(0, 1.0) == pytest.approx(e, rel=1e-6)
        assert model._poisson_pmf(1, 1.0) == pytest.approx(e, rel=1e-6)
        assert model._poisson_pmf(2, 1.0) == pytest.approx(e / 2, rel=1e-6)

    def test_poisson_pmf_lambda_zero(self) -> None:
        """P(X=0 | λ=0) = 1, P(X>0 | λ=0) = 0."""
        model = PoissonModel()
        assert model._poisson_pmf(0, 0.0) == 1.0
        assert model._poisson_pmf(1, 0.0) == 0.0
        assert model._poisson_pmf(5, 0.0) == 0.0

    def test_poisson_pmf_negative_lambda(self) -> None:
        """Lambda <= 0 should return 1 for k=0, 0 otherwise."""
        model = PoissonModel()
        assert model._poisson_pmf(0, -1.0) == 1.0
        assert model._poisson_pmf(1, -0.5) == 0.0

    def test_poisson_pmf_large_lambda(self) -> None:
        """Large lambda should not cause overflow."""
        model = PoissonModel()
        prob = model._poisson_pmf(10, 100.0)
        assert 0.0 <= prob <= 1.0

    def test_poisson_pmf_all_k_sum_to_one(self) -> None:
        """Sum of PMF over all k should approach 1.

        For practical purposes, sum up to max_goals.
        """
        model = PoissonModel()
        lam = 2.5
        total = sum(model._poisson_pmf(k, lam) for k in range(20))
        assert total == pytest.approx(1.0, abs=1e-6)


class TestPoissonDistribution:
    """Tests for the full Poisson model prediction."""

    def test_distribution_sums_to_one(self) -> None:
        """Goal distribution should sum to approximately 1."""
        from prediction.base import PredictionInput
        from prediction.features import FeatureBuilder, LeagueBaseline

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

        match = PredictionInput(
            match_id="test-1",
            home_team_id="h1",
            away_team_id="a1",
            home_team_name="Home FC",
            away_team_name="Away FC",
            league_id="test",
        )

        builder = FeatureBuilder()
        builder.build(match, league_baseline=baseline)

        model = PoissonModel()
        result = model.predict(match)

        assert sum(result.home_goal_distribution) == pytest.approx(1.0, abs=0.01)
        assert sum(result.away_goal_distribution) == pytest.approx(1.0, abs=0.01)

    def test_lambda_positive(self) -> None:
        """Lambda values must always be positive."""
        from prediction.base import PredictionInput
        from prediction.features import FeatureBuilder, LeagueBaseline

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

        match = PredictionInput(
            match_id="test-1",
            home_team_id="h1",
            away_team_id="a1",
            home_team_name="Home FC",
            away_team_name="Away FC",
            league_id="test",
        )

        builder = FeatureBuilder()
        builder.build(match, league_baseline=baseline)

        model = PoissonModel()
        result = model.predict(match)

        assert result.lambda_home > 0
        assert result.lambda_away > 0
        assert result.lambda_home <= 8.0
        assert result.lambda_away <= 8.0


class TestMathematicalFixture:
    """Test with a simple known fixture to verify mathematical correctness."""

    def test_simple_fixture(self) -> None:
        """Test with simple lambda values: λ_home=1.5, λ_away=1.0.

        Verify:
        P(0) for λ=1.5: e^(-1.5) ≈ 0.2231
        P(1) for λ=1.5: e^(-1.5) * 1.5 ≈ 0.3347
        P(0) for λ=1.0: e^(-1.0) ≈ 0.3679
        P(1) for λ=1.0: e^(-1.0) * 1.0 ≈ 0.3679

        Score P(1-0) ≈ 0.3347 * 0.3679 ≈ 0.1232
        """
        model = PoissonModel()

        # For λ=1.5
        p0_15 = model._poisson_pmf(0, 1.5)
        p1_15 = model._poisson_pmf(1, 1.5)

        assert p0_15 == pytest.approx(math.exp(-1.5), rel=1e-6)
        assert p1_15 == pytest.approx(1.5 * math.exp(-1.5), rel=1e-6)

        # For λ=1.0
        p0_10 = model._poisson_pmf(0, 1.0)
        p1_10 = model._poisson_pmf(1, 1.0)

        assert p0_10 == pytest.approx(math.exp(-1.0), rel=1e-6)
        assert p1_10 == pytest.approx(math.exp(-1.0), rel=1e-6)

        # Scoreline 1-0 = P(1, λ=1.5) × P(0, λ=1.0)
        score_1_0 = p1_15 * p0_10
        assert score_1_0 == pytest.approx(0.3347 * 0.3679, rel=1e-4)

    @pytest.mark.asyncio
    async def test_score_matrix_mathematical_integrity(self) -> None:
        """Full pipeline: verify score matrix properties with simple lambdas."""
        from prediction.base import ModelResult
        from prediction.score_matrix import ScoreMatrix

        lambda_home = 1.5
        lambda_away = 1.0

        home_dist = [PoissonModel()._poisson_pmf(k, lambda_home) for k in range(9)]
        away_dist = [PoissonModel()._poisson_pmf(k, lambda_away) for k in range(9)]

        result = ModelResult(
            model="poisson",
            model_version="poisson-v1.0.0",
            lambda_home=lambda_home,
            lambda_away=lambda_away,
            home_goal_distribution=home_dist,
            away_goal_distribution=away_dist,
            score_matrix=[],
            max_goals=8,
            data_quality=0.5,
            model_parameters={},
            feature_snapshot={},
        )

        matrix = ScoreMatrix.from_model_result(result)
        normalized = matrix.normalize()

        total = sum(sum(row) for row in matrix.matrix)
        assert total == pytest.approx(1.0, abs=0.001)

        # P(score 0-0) = P(0|1.5) * P(0|1.0)
        p_0_0 = home_dist[0] * away_dist[0]
        assert matrix.matrix[0][0] == pytest.approx(p_0_0, rel=1e-6)

        # P(score 1-0) = P(1|1.5) * P(0|1.0)
        p_1_0 = home_dist[1] * away_dist[0]
        assert matrix.matrix[1][0] == pytest.approx(p_1_0, rel=1e-6)

        # Verify normalization preserves relative proportions
        assert normalized[0][0] == pytest.approx(
            matrix.matrix[0][0] / total, rel=1e-4
        )
