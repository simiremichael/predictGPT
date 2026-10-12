from __future__ import annotations

import pytest

from prediction.calibration import apply_temperature, fit_and_assess
from prediction.score_matrix import ScoreMatrix


def test_calibration_requires_enough_historical_results() -> None:
    result = fit_and_assess([
        {"probabilities": [0.5, 0.3, 0.2], "outcome": 0}
        for _ in range(20)
    ])

    assert not result.applied
    assert result.temperature == 1.0
    assert result.raw_log_loss is None


def test_calibration_is_accepted_only_when_later_period_improves() -> None:
    outcomes = [0, 0, 0, 1, 2] * 60
    records = [
        {"probabilities": [0.8, 0.1, 0.1], "outcome": outcome}
        for outcome in outcomes
    ]

    result = fit_and_assess(records)

    assert result.applied
    assert result.temperature > 1.0
    assert result.calibrated_log_loss < result.raw_log_loss
    assert result.calibrated_brier_score < result.raw_brier_score


def test_temperature_preserves_outcome_order_and_sums_to_one() -> None:
    probabilities = apply_temperature([0.65, 0.25, 0.1], temperature=1.4)

    assert probabilities[0] > probabilities[1] > probabilities[2]
    assert sum(probabilities) == pytest.approx(1.0)


def test_score_matrix_rescales_all_outcomes_to_calibrated_probabilities() -> None:
    matrix = ScoreMatrix([0.5, 0.5], [0.5, 0.5], max_goals=1)

    matrix.apply_result_probabilities({"home": 0.5, "draw": 0.3, "away": 0.2})

    result = matrix.get_result_probabilities()
    assert result["home"] == pytest.approx(0.5)
    assert result["draw"] == pytest.approx(0.3)
    assert result["away"] == pytest.approx(0.2)
    assert matrix.get_total_probability() == pytest.approx(1.0)
