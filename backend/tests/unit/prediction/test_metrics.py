"""Unit tests for prediction metrics.

Tests cover:
    - Brier score
    - Log loss
    - Mean absolute goal error
    - Over/Under accuracy
    - BTTS accuracy
    - Calibration error
    - Exact score accuracy
    - Top 4 hit rate
"""
from __future__ import annotations

import math

import pytest

from prediction import metrics


class TestBrierScore:
    """Tests for Brier score calculation."""

    def test_perfect_predictions(self) -> None:
        """Brier score = 0 for perfect predictions."""
        assert metrics.brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0, abs=1e-6)

    def test_worst_predictions(self) -> None:
        """Brier score = 1 for maximally wrong predictions."""
        assert metrics.brier_score([0.0, 1.0], [1, 0]) == pytest.approx(1.0, abs=1e-6)

    def test_partial_error(self) -> None:
        """Brier score = 0.25 for moderate error."""
        # (1-0.5)^2 = 0.25, (0-0.5)^2 = 0.25 → avg = 0.25
        assert metrics.brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25, abs=1e-6)

    def test_empty_list(self) -> None:
        """Empty list returns 0."""
        assert metrics.brier_score([], []) == 0.0


class TestLogLoss:
    """Tests for log loss calculation."""

    def test_perfect_predictions(self) -> None:
        """Log loss approaches 0 for perfect predictions."""
        loss = metrics.log_loss([0.9, 0.1], [1, 0])
        assert loss < 0.5  # Should be small but not zero

    def test_confident_wrong_predictions(self) -> None:
        """Confident wrong predictions should have high log loss."""
        loss = metrics.log_loss([0.99, 0.01], [0, 1])
        assert loss > 2.0  # Should be high

    def test_empty_list(self) -> None:
        """Empty list returns 0."""
        assert metrics.log_loss([], []) == 0.0

    def test_clipping_prevents_zero(self) -> None:
        """Probabilities of 0 or 1 are clipped to avoid log(0)."""
        loss = metrics.log_loss([0.0, 1.0], [1, 0])
        assert math.isfinite(loss)  # Should not be inf


class TestMeanAbsoluteGoalError:
    """Tests for mean absolute goal error."""

    def test_zero_error(self) -> None:
        """No error when prediction matches actual exactly."""
        assert metrics.mean_absolute_goal_error(2.0, 1.0, 2, 1) == pytest.approx(0.0)

    def test_known_error(self) -> None:
        """Known error calculation."""
        # |2 - 1.5| + |1 - 1.0| = 0.5 + 0 = 0.5
        assert metrics.mean_absolute_goal_error(1.5, 1.0, 2, 1) == pytest.approx(0.5)

    def test_large_error(self) -> None:
        """Large error when predictions are off."""
        # |0 - 3| + |0 - 2| = 3 + 2 = 5
        assert metrics.mean_absolute_goal_error(0.1, 0.1, 3, 2) == pytest.approx(4.8, abs=0.1)


class TestExactScoreAccuracy:
    """Tests for exact score accuracy."""

    def test_exact_match(self) -> None:
        """Exact score match returns True."""
        from prediction.base import Scoreline

        sl = Scoreline(home_goals=2, away_goals=1, probability=0.15)
        assert metrics.exact_score_accuracy(sl, 2, 1)

    def test_mismatch_home(self) -> None:
        """Wrong home score returns False."""
        from prediction.base import Scoreline

        sl = Scoreline(home_goals=1, away_goals=1, probability=0.15)
        assert not metrics.exact_score_accuracy(sl, 2, 1)

    def test_mismatch_away(self) -> None:
        """Wrong away score returns False."""
        from prediction.base import Scoreline

        sl = Scoreline(home_goals=2, away_goals=0, probability=0.15)
        assert not metrics.exact_score_accuracy(sl, 2, 1)


class TestTop4HitRate:
    """Tests for top 4 hit rate."""

    def test_hit_in_top_4(self) -> None:
        """Scoreline in top 4 returns True."""
        from prediction.base import Scoreline

        top_4 = [
            Scoreline(1, 0, 0.15),
            Scoreline(1, 1, 0.13),
            Scoreline(2, 0, 0.12),
            Scoreline(2, 1, 0.11),
        ]
        assert metrics.top_4_hit_rate(top_4, 2, 1)

    def test_miss_not_in_top_4(self) -> None:
        """Scoreline not in top 4 returns False."""
        from prediction.base import Scoreline

        top_4 = [
            Scoreline(1, 0, 0.15),
            Scoreline(1, 1, 0.13),
            Scoreline(2, 0, 0.12),
            Scoreline(2, 1, 0.11),
        ]
        assert not metrics.top_4_hit_rate(top_4, 3, 2)

    def test_empty_top_4(self) -> None:
        """Empty top 4 returns False."""
        assert not metrics.top_4_hit_rate([], 1, 0)


class TestOverUnderAccuracy:
    """Tests for Over/Under accuracy."""

    def test_correct_over(self) -> None:
        """Over prediction correct when actual exceeds threshold."""
        assert metrics.over_under_accuracy(0.7, 2.5, 4)

    def test_correct_under(self) -> None:
        """Under prediction correct when actual is below threshold."""
        assert metrics.over_under_accuracy(0.3, 2.5, 1)

    def test_wrong_over(self) -> None:
        """Over prediction wrong when actual is under."""
        assert not metrics.over_under_accuracy(0.7, 2.5, 1)


class TestBTTSAcuuracy:
    """Tests for BTTS accuracy."""

    def test_correct_yes(self) -> None:
        """BTTS yes correct when both teams score."""
        assert metrics.btts_accuracy(0.7, 2, 1)

    def test_correct_no(self) -> None:
        """BTTS no correct when one team doesn't score."""
        assert metrics.btts_accuracy(0.3, 0, 1)

    def test_wrong_yes(self) -> None:
        """BTTS yes wrong when one team doesn't score."""
        assert not metrics.btts_accuracy(0.7, 0, 1)


class TestCalibrationError:
    """Tests for Expected Calibration Error."""

    def test_perfect_calibration(self) -> None:
        """ECE = 0 when predictions match outcomes perfectly."""
        probs = [1.0] * 100
        outcomes = [1] * 100
        assert metrics.calibration_error(probs, outcomes) == pytest.approx(0.0, abs=1e-6)

    def test_poor_calibration(self) -> None:
        """ECE > 0 when predictions are poorly calibrated."""
        probs = [0.9] * 100
        outcomes = [0] * 100
        assert metrics.calibration_error(probs, outcomes) > 0.5

    def test_empty_predictions(self) -> None:
        """ECE = 0 for empty input."""
        assert metrics.calibration_error([], []) == 0.0
