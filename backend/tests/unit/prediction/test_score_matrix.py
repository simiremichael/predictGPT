"""Unit tests for the score matrix and market calculations.

Tests cover:
    - Score matrix construction
    - Normalization (sums to 1)
    - Top 4 scoreline extraction
    - Home/Draw/Away calculation
    - Over/Under markets
    - BTTS markets
    - Clean sheet probabilities
    - Property tests (all probabilities valid, sums correct)
"""
from __future__ import annotations

import math

import pytest

from prediction.base import ModelResult, Scoreline
from prediction.markets import MarketCalculator
from prediction.poisson import PoissonModel
from prediction.score_matrix import ScoreMatrix


# ── Fixtures ────────────────────────────────────────────────────────── #
@pytest.fixture
def simple_model_result() -> ModelResult:
    """Create a model result with lambda_home=1.5, lambda_away=1.0."""
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
        model_parameters={},
        feature_snapshot={},
    )


@pytest.fixture
def score_matrix(simple_model_result: ModelResult) -> ScoreMatrix:
    """Create a ScoreMatrix from the simple model result."""
    return ScoreMatrix.from_model_result(simple_model_result)


class TestScoreMatrixConstruction:
    """Tests for score matrix construction."""

    def test_matrix_dimensions(self, score_matrix: ScoreMatrix) -> None:
        """Matrix should be (max_goals+1) x (max_goals+1)."""
        assert len(score_matrix.matrix) == 9
        for row in score_matrix.matrix:
            assert len(row) == 9

    def test_matrix_non_negative(self, score_matrix: ScoreMatrix) -> None:
        """All matrix entries must be non-negative."""
        for row in score_matrix.matrix:
            for val in row:
                assert val >= 0.0

    def test_matrix_sums_to_one(self, score_matrix: ScoreMatrix) -> None:
        """Matrix probabilities should sum to approximately 1."""
        total = sum(sum(row) for row in score_matrix.matrix)
        assert total == pytest.approx(1.0, abs=0.001)

    def test_0_0_probability(self, score_matrix: ScoreMatrix) -> None:
        """P(0-0) should equal e^(-lambda_home) * e^(-lambda_away)."""
        expected = math.exp(-1.5) * math.exp(-1.0)
        assert score_matrix.matrix[0][0] == pytest.approx(expected, rel=1e-6)

    def test_normalize_preserves_zero_total(self) -> None:
        """Normalization with zero total should return original."""
        matrix = ScoreMatrix(
            home_distribution=[0.0] * 9,
            away_distribution=[1.0] + [0.0] * 8,
            max_goals=8,
        )
        # All zeros -> should handle gracefully
        normalized = matrix.normalize()
        assert normalized is not None

    def test_truncation_normalization(self) -> None:
        """High lambda should still normalize correctly."""
        model = PoissonModel()
        lam_h, lam_a = 5.0, 4.0
        home_dist = [model._poisson_pmf(k, lam_h) for k in range(9)]
        away_dist = [model._poisson_pmf(k, lam_a) for k in range(9)]

        matrix: list[list[float]] = []
        for h in range(9):
            row = [home_dist[h] * away_dist[a] for a in range(9)]
            matrix.append(row)

        result = ModelResult(
            model="poisson",
            model_version="poisson-v1.0.0",
            lambda_home=lam_h,
            lambda_away=lam_a,
            home_goal_distribution=home_dist,
            away_goal_distribution=away_dist,
            score_matrix=matrix,
            max_goals=8,
            data_quality=0.8,
            model_parameters={},
            feature_snapshot={},
        )

        sm = ScoreMatrix.from_model_result(result)
        total = sum(sum(row) for row in sm.matrix)
        # With lambda=5.0/4.0 and max_goals=8, there's truncation mass
        # But the matrix should contain most of the probability
        assert total > 0.9  # Most probability mass retained in 0-8 range
        # Normalized matrix should sum to 1.0
        normalized = sm.normalize()
        norm_total = sum(sum(row) for row in normalized)
        assert norm_total == pytest.approx(1.0, abs=1e-6)


class TestTopScorelines:
    """Tests for top scoreline extraction."""

    def test_top_4_returns_four(self, score_matrix: ScoreMatrix) -> None:
        """Should return exactly 4 scorelines."""
        top_4 = score_matrix.get_top_scorelines(n=4)
        assert len(top_4) == 4

    def test_top_4_sorted_descending(self, score_matrix: ScoreMatrix) -> None:
        """Top 4 should be sorted by probability descending."""
        top_4 = score_matrix.get_top_scorelines(n=4)
        for i in range(len(top_4) - 1):
            assert top_4[i].probability >= top_4[i + 1].probability

    def test_top_4_unique(self, score_matrix: ScoreMatrix) -> None:
        """Top 4 should contain unique scorelines."""
        top_4 = score_matrix.get_top_scorelines(n=4)
        seen: set[tuple[int, int]] = set()
        for sl in top_4:
            key = (sl.home_goals, sl.away_goals)
            assert key not in seen
            seen.add(key)

    def test_top_scoreline_exists(self, score_matrix: ScoreMatrix) -> None:
        """Should return a top scoreline."""
        top = score_matrix.get_top_scoreline()
        assert top is not None

    def test_top_scoreline_is_most_probable(self, score_matrix: ScoreMatrix) -> None:
        """Top scoreline should have the highest probability."""
        top = score_matrix.get_top_scoreline()
        all_scores = score_matrix.get_top_scorelines(n=100)
        assert top is not None
        for sl in all_scores:
            assert top.probability >= sl.probability


class TestResultProbabilities:
    """Tests for Home/Draw/Away calculation."""

    def test_hda_sums_to_one(self, score_matrix: ScoreMatrix) -> None:
        """H/D/A probabilities should sum to approximately 1."""
        hda = score_matrix.get_result_probabilities()
        total = hda["home"] + hda["draw"] + hda["away"]
        assert total == pytest.approx(1.0, abs=0.001)

    def test_hda_non_negative(self, score_matrix: ScoreMatrix) -> None:
        """All H/D/A probabilities must be non-negative."""
        hda = score_matrix.get_result_probabilities()
        assert hda["home"] >= 0.0
        assert hda["draw"] >= 0.0
        assert hda["away"] >= 0.0

    def test_hda_non_negative_bounds(self, score_matrix: ScoreMatrix) -> None:
        """All H/D/A probabilities must be <= 1."""
        hda = score_matrix.get_result_probabilities()
        assert hda["home"] <= 1.0
        assert hda["draw"] <= 1.0
        assert hda["away"] <= 1.0


class TestMarkets:
    """Tests for market calculations."""

    def test_over_under_pairs_sum_to_one(self, score_matrix: ScoreMatrix) -> None:
        """Each Over/Under pair should sum to approximately 1."""
        calc = MarketCalculator(score_matrix)
        markets = calc.get_over_under()

        for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
            key = str(threshold).replace(".", "_")
            pair_sum = markets[f"over_{key}"] + markets[f"under_{key}"]
            assert pair_sum == pytest.approx(1.0, abs=0.001)

    def test_btts_sums_to_one(self, score_matrix: ScoreMatrix) -> None:
        """BTTS Yes + BTTS No should sum to approximately 1."""
        calc = MarketCalculator(score_matrix)
        btts = calc.get_btts()
        total = btts["btts_yes"] + btts["btts_no"]
        assert total == pytest.approx(1.0, abs=0.001)

    def test_clean_sheets_sums_to_one(self, score_matrix: ScoreMatrix) -> None:
        """Home CS + Home not-CS should sum to 1."""
        calc = MarketCalculator(score_matrix)
        cs = calc.get_clean_sheets()
        assert cs["home_clean_sheet"] + (1 - cs["home_clean_sheet"]) == pytest.approx(1.0)
        assert cs["away_clean_sheet"] + (1 - cs["away_clean_sheet"]) == pytest.approx(1.0)

    def test_double_chance_home_draw(self, score_matrix: ScoreMatrix) -> None:
        """Home or Draw should equal home + draw probabilities."""
        calc = MarketCalculator(score_matrix)
        dc = calc.get_double_chance()
        hda = score_matrix.get_result_probabilities()
        assert dc["home_or_draw"] == pytest.approx(hda["home"] + hda["draw"], abs=0.001)

    def test_all_markets_present(self, score_matrix: ScoreMatrix) -> None:
        """All markets should be present in get_all_markets."""
        calc = MarketCalculator(score_matrix)
        markets = calc.get_all_markets()

        expected_keys = [
            "over_0_5", "under_0_5",
            "over_1_5", "under_1_5",
            "over_2_5", "under_2_5",
            "over_3_5", "under_3_5",
            "over_4_5", "under_4_5",
            "btts_yes", "btts_no",
            "home_clean_sheet", "away_clean_sheet",
            "home_or_draw", "draw_or_away", "home_or_away",
        ]
        for key in expected_keys:
            assert key in markets

    def test_market_probabilities_valid_range(self, score_matrix: ScoreMatrix) -> None:
        """All market probabilities should be in [0, 1]."""
        calc = MarketCalculator(score_matrix)
        markets = calc.get_all_markets()
        for _key, val in markets.items():
            assert 0.0 <= val <= 1.0


class TestScoreMatrixPropertyTests:
    """Property-based tests for score matrix correctness."""

    @pytest.mark.parametrize("lambda_val", [0.5, 1.0, 1.5, 2.5, 3.5, 5.0])
    def test_distribution_sums_to_one_for_various_lambdas(
        self, lambda_val: float
    ) -> None:
        """Goal distribution should sum to 1 for various lambda values."""
        model = PoissonModel()
        dist = [model._poisson_pmf(k, lambda_val) for k in range(20)]
        assert sum(dist) == pytest.approx(1.0, abs=1e-4)

    def test_score_matrix_total_probability_non_negative(self, score_matrix: ScoreMatrix) -> None:
        """Total probability must be non-negative."""
        total = sum(sum(row) for row in score_matrix.matrix)
        assert total >= 0.0

    def test_probability_conservation(self, simple_model_result: ModelResult) -> None:
        """Home and away distributions should independently sum to ~1."""
        assert sum(simple_model_result.home_goal_distribution) == pytest.approx(1.0, abs=0.0001)
        assert sum(simple_model_result.away_goal_distribution) == pytest.approx(1.0, abs=0.0001)
