"""Prediction evaluation metrics.

Implements functions used by the backtesting system to evaluate prediction
accuracy.  All metrics compare a generated prediction against the actual
match result.
"""
from __future__ import annotations

import math
from typing import Any

from prediction.base import Scoreline


def exact_score_accuracy(
    top_scoreline: Scoreline, actual_home: int, actual_away: int
) -> bool:
    """Return True if the top predicted scoreline matches exactly."""
    return top_scoreline.home_goals == actual_home and top_scoreline.away_goals == actual_away


def top_4_hit_rate(
    top_4: list[Scoreline], actual_home: int, actual_away: int
) -> bool:
    """Return True if the actual scoreline is within the top 4 predictions."""
    for sl in top_4:
        if sl.home_goals == actual_home and sl.away_goals == actual_away:
            return True
    return False


def home_draw_away_accuracy(
    predicted: dict[str, float], actual_home: int, actual_away: int
) -> dict[str, bool]:
    """Compare predicted result probabilities against actual result."""
    actual = _determine_result(actual_home, actual_away)

    predicted_result = _determine_predicted_result(predicted)

    return {
        "predicted_correct": predicted_result == actual,
        "actual_result": actual,
        "predicted_result": predicted_result,
    }


def brier_score(predicted_probs: list[float], actual_outcomes: list[int]) -> float:
    """Calculate the Brier score for probability calibration.

    Args:
        predicted_probs: List of predicted probabilities for each outcome.
        actual_outcomes: List of 0/1 indicators (1 = event occurred).

    Returns:
        Brier score (lower is better, 0 = perfect).
    """
    if len(predicted_probs) != len(actual_outcomes):
        raise ValueError("Length mismatch between predictions and outcomes")

    if not predicted_probs:
        return 0.0

    total = 0.0
    for p, a in zip(predicted_probs, actual_outcomes, strict=True):
        total += (p - a) ** 2
    return total / len(predicted_probs)


def log_loss(predicted_probs: list[float], actual_outcomes: list[int]) -> float:
    """Calculate the log loss (negative log-likelihood).

    Lower is better.  Clips probabilities to avoid log(0).
    """
    epsilon = 1e-15
    total = 0.0
    count = 0
    for p, a in zip(predicted_probs, actual_outcomes, strict=True):
        p = max(epsilon, min(1 - epsilon, p))
        if a == 1:
            total -= math.log(p)
        else:
            total -= math.log(1 - p)
        count += 1

    return total / count if count > 0 else 0.0


def mean_absolute_goal_error(
    lambda_home: float,
    lambda_away: float,
    actual_home: int,
    actual_away: int,
) -> float:
    """Calculate the absolute error in expected goals estimate."""
    return abs(actual_home - lambda_home) + abs(actual_away - lambda_away)


def over_under_accuracy(
    predicted_over_prob: float,
    threshold: float,
    actual_total: float,
) -> bool:
    """Check if over/under prediction is correct.

    If over_prob > 0.5, we predict 'over'; otherwise 'under'.
    """
    predicted_over = predicted_over_prob > 0.5
    actual_over = actual_total > threshold
    return predicted_over == actual_over


def btts_accuracy(predicted_btts_yes: float, actual_home: int, actual_away: int) -> bool:
    """Check if BTTS prediction is correct."""
    predicted_yes = predicted_btts_yes > 0.5
    actual_yes = actual_home >= 1 and actual_away >= 1
    return predicted_yes == actual_yes


def calibration_error(
    predicted_probs: list[float],
    actual_outcomes: list[int],
    n_bins: int = 10,
) -> float:
    """Calculate Expected Calibration Error (ECE).

    Divides predictions into bins and measures the difference between
    predicted probability and observed frequency.
    """
    if not predicted_probs or len(predicted_probs) != len(actual_outcomes):
        return 0.0

    bin_size = 1.0 / n_bins
    bin_total: list[list[float]] = [[] for _ in range(n_bins)]
    bin_correct: list[float] = [0.0] * n_bins

    for p, a in zip(predicted_probs, actual_outcomes, strict=True):
        bin_idx = min(int(p / bin_size), n_bins - 1)
        bin_total[bin_idx].append(p)
        if a == 1:
            bin_correct[bin_idx] += 1.0

    total_samples = len(predicted_probs)
    ece = 0.0

    for i in range(n_bins):
        if len(bin_total[i]) == 0:
            continue
        bin_accuracy = bin_correct[i] / len(bin_total[i])
        bin_avg_confidence = sum(bin_total[i]) / len(bin_total[i])
        ece += (len(bin_total[i]) / total_samples) * abs(bin_accuracy - bin_avg_confidence)

    return ece


def _determine_result(home_goals: int, away_goals: int) -> str:
    """Determine the match result: 'home', 'draw', or 'away'."""
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def _determine_predicted_result(probs: dict[str, float]) -> str:
    """Determine the predicted result from probability dict."""
    return max(probs, key=probs.get)
