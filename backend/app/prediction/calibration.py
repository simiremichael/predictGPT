"""Leakage-safe multiclass calibration for historical 1X2 predictions."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

RAW_PREDICTION_VERSION = "v1.0.0"
CALIBRATED_PREDICTION_VERSION = "v1.1.0"
MIN_TRAINING_SAMPLES = 100
MIN_VALIDATION_SAMPLES = 30


@dataclass
class CalibrationAssessment:
    """Training result plus a later chronological validation comparison."""

    applied: bool
    temperature: float
    training_samples: int
    validation_samples: int
    raw_log_loss: float | None
    calibrated_log_loss: float | None
    raw_brier_score: float | None
    calibrated_brier_score: float | None
    note: str


def normalize_probabilities(probabilities: list[float]) -> list[float]:
    if len(probabilities) != 3:
        raise ValueError("1X2 probabilities must contain home, draw, and away")
    clean = [
        max(0.0, float(value)) if math.isfinite(float(value)) else 0.0
        for value in probabilities
    ]
    total = sum(clean)
    if total <= 0:
        return [1 / 3, 1 / 3, 1 / 3]
    return [value / total for value in clean]


def apply_temperature(probabilities: list[float], temperature: float) -> list[float]:
    """Apply multiclass temperature scaling while preserving outcome order."""
    if not math.isfinite(temperature) or temperature <= 0:
        return normalize_probabilities(probabilities)
    normalized = normalize_probabilities(probabilities)
    logits = [math.log(max(value, 1e-12)) / temperature for value in normalized]
    peak = max(logits)
    weights = [math.exp(value - peak) for value in logits]
    total = sum(weights)
    return [value / total for value in weights]


def _log_loss(samples: list[tuple[list[float], int]], temperature: float = 1.0) -> float:
    if not samples:
        return 0.0
    return sum(
        -math.log(max(1e-12, apply_temperature(probabilities, temperature)[outcome]))
        for probabilities, outcome in samples
    ) / len(samples)


def _brier_score(samples: list[tuple[list[float], int]], temperature: float = 1.0) -> float:
    if not samples:
        return 0.0
    total = 0.0
    for probabilities, outcome in samples:
        calibrated = apply_temperature(probabilities, temperature)
        total += sum(
            (probability - (1.0 if index == outcome else 0.0)) ** 2
            for index, probability in enumerate(calibrated)
        )
    return total / len(samples)


def fit_and_assess(
    records: list[dict[str, Any]],
    min_training_samples: int = MIN_TRAINING_SAMPLES,
    min_validation_samples: int = MIN_VALIDATION_SAMPLES,
) -> CalibrationAssessment:
    """Fit on the earlier 80% and only accept a gain on the later 20%.

    Each record contains a three-value ``probabilities`` list and integer
    ``outcome`` (home=0, draw=1, away=2). Callers must supply chronological,
    pre-kickoff predictions for one model version.
    """
    samples: list[tuple[list[float], int]] = []
    for record in records:
        try:
            probabilities = normalize_probabilities(record["probabilities"])
            outcome = int(record["outcome"])
            if outcome in (0, 1, 2):
                samples.append((probabilities, outcome))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue

    validation_count = max(min_validation_samples, int(len(samples) * 0.2))
    training_count = len(samples) - validation_count
    if training_count < min_training_samples or validation_count < min_validation_samples:
        return CalibrationAssessment(
            applied=False,
            temperature=1.0,
            training_samples=max(0, training_count),
            validation_samples=min(len(samples), validation_count),
            raw_log_loss=None,
            calibrated_log_loss=None,
            raw_brier_score=None,
            calibrated_brier_score=None,
            note=(f"Insufficient historical outcomes: need at least {min_training_samples} "
                  f"training and {min_validation_samples} later validation matches; "
                  f"have {max(0, training_count)} and {min(len(samples), validation_count)}."),
        )

    training = samples[:training_count]
    validation = samples[training_count:]

    # Deterministic bounded grid search avoids a scipy dependency and limits
    # over-confident temperatures on noisy football outcomes.
    candidates = [math.exp(-1.5 + step * 0.025) for step in range(121)]
    temperature = min(
        candidates,
        key=lambda value: (_log_loss(training, value), abs(math.log(value))),
    )
    raw_log_loss = _log_loss(validation)
    calibrated_log_loss = _log_loss(validation, temperature)
    raw_brier = _brier_score(validation)
    calibrated_brier = _brier_score(validation, temperature)
    # Require out-of-sample improvement in both proper scoring rules. Accuracy
    # is unchanged by temperature scaling because it preserves the argmax.
    applied = (
        calibrated_log_loss + 1e-9 < raw_log_loss
        and calibrated_brier + 1e-9 < raw_brier
    )
    return CalibrationAssessment(
        applied=applied,
        temperature=temperature if applied else 1.0,
        training_samples=len(training),
        validation_samples=len(validation),
        raw_log_loss=raw_log_loss,
        calibrated_log_loss=calibrated_log_loss,
        raw_brier_score=raw_brier,
        calibrated_brier_score=calibrated_brier,
        note=(
            "Calibration improves both later-period log loss and Brier score."
            if applied
            else "No calibration applied: later-period scoring did not improve on both metrics."
        ),
    )
