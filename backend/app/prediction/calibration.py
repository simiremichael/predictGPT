"""Calibration support for prediction models.

Prepares infrastructure for probability calibration, reliability diagrams,
and calibration assessment.  Actual calibration requires sufficient
historical prediction data to fit calibration curves.

This module does NOT claim calibration quality until sufficient data exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CalibrationPoint:
    """A single point on a reliability curve."""

    predicted_probability: float
    observed_frequency: float
    sample_count: int


@dataclass
class CalibrationResult:
    """Result of a calibration assessment."""

    expected_calibration_error: float
    reliability_points: list[CalibrationPoint]
    is_well_calibrated: bool
    note: str


class CalibrationManager:
    """Manages calibration of prediction probabilities.

    Calibration adjusts raw model probabilities to better match observed
    frequencies.  This class is prepared for future use but does not
    apply any adjustments until sufficient historical data is available.
    """

    def __init__(self, n_bins: int = 10) -> None:
        self.n_bins = n_bins
        self._min_samples = 100

    def assess(
        self,
        predictions: list[dict[str, Any]],
        min_samples: int | None = None,
    ) -> CalibrationResult:
        """Assess calibration given historical predictions with outcomes.

        Each prediction dict should contain:
            - predicted_prob: float (the predicted probability)
            - outcome: int (1 = event occurred, 0 = did not)

        Returns a CalibrationResult.  If insufficient data exists, returns
        an uncalibrated result with a note.
        """
        if min_samples is None:
            min_samples = self._min_samples

        if len(predictions) < min_samples:
            return CalibrationResult(
                expected_calibration_error=0.0,
                reliability_points=[],
                is_well_calibrated=False,
                note=(
                    f"Insufficient data for calibration (need {min_samples} samples, "
                    f"have {len(predictions)}). No calibration applied."
                ),
            )

        # Build reliability bins
        bin_size = 1.0 / self.n_bins
        bins: list[list[dict[str, Any]]] = [[] for _ in range(self.n_bins)]

        for pred in predictions:
            prob = pred.get("predicted_prob", 0.0)
            bin_idx = min(int(prob / bin_size), self.n_bins - 1)
            bins[bin_idx].append(pred)

        points: list[CalibrationPoint] = []
        ece = 0.0
        total = len(predictions)

        for _i, bin_preds in enumerate(bins):
            if not bin_preds:
                continue

            avg_prob = sum(p["predicted_prob"] for p in bin_preds) / len(bin_preds)
            observed = sum(p["outcome"] for p in bin_preds) / len(bin_preds)
            points.append(CalibrationPoint(
                predicted_probability=avg_prob,
                observed_frequency=observed,
                sample_count=len(bin_preds),
            ))

            ece += (len(bin_preds) / total) * abs(avg_prob - observed)

        # Well-calibrated if ECE < 0.05 (5%)
        is_well_calibrated = ece < 0.05

        return CalibrationResult(
            expected_calibration_error=ece,
            reliability_points=points,
            is_well_calibrated=is_well_calibrated,
            note="Calibration assessed based on historical data." if is_well_calibrated
            else "Model may need calibration adjustment.",
        )

    def apply_calibration(
        self,
        probability: float,
        calibration_result: CalibrationResult,
    ) -> float:
        """Apply calibration adjustment to a probability.

        Currently a no-op until sufficient calibration data is available.
        """
        if not calibration_result.is_well_calibrated:
            return probability
        return probability
