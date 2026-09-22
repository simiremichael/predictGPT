"""Prediction comparison and change analysis.

Calculates the differences between two predictions for the same match,
showing how probabilities, lambdas, and research inputs changed.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PredictionComparisonService:
    """Compares two predictions and reports what changed."""

    NUMERIC_FIELDS: list[str] = [
        "lambda_home",
        "lambda_away",
        "home_probability",
        "draw_probability",
        "away_probability",
        "over_2_5_probability",
        "under_2_5_probability",
        "btts_probability",
        "confidence",
        "data_quality",
    ]

    def compare(
        self, previous: dict[str, Any], current: dict[str, Any]
    ) -> dict[str, Any]:
        """Compare two prediction dicts and return a changes report.

        Args:
            previous: The older prediction as a dict.
            current: The newer prediction as a dict.

        Returns:
            A dict with 'previous', 'current', and 'changes' sections.
        """
        changes: dict[str, Any] = {}

        for field in self.NUMERIC_FIELDS:
            prev_val = self._extract_numeric(previous, field)
            curr_val = self._extract_numeric(current, field)

            if prev_val is not None or curr_val is not None:
                delta = (curr_val or 0.0) - (prev_val or 0.0)
                if abs(delta) > 0.0001:
                    changes[field] = {
                        "previous": prev_val,
                        "current": curr_val,
                        "change": round(delta, 6),
                    }

        prev_research = self._extract_nested(previous, "research", "available")
        curr_research = self._extract_nested(current, "research", "available")
        if prev_research != curr_research:
            changes["research_available"] = {
                "previous": prev_research,
                "current": curr_research,
            }

        prev_ai = self._extract_nested(previous, "ai_adjustment", "applied")
        curr_ai = self._extract_nested(current, "ai_adjustment", "applied")
        if prev_ai != curr_ai:
            changes["ai_adjustment_applied"] = {
                "previous": prev_ai,
                "current": curr_ai,
            }

        prev_top = self._extract_nested(previous, "top_scoreline")
        curr_top = self._extract_nested(current, "top_scoreline")
        if prev_top != curr_top:
            changes["top_scoreline"] = {
                "previous": prev_top,
                "current": curr_top,
            }

        prev_sources = self._count_sources(previous)
        curr_sources = self._count_sources(current)
        if prev_sources != curr_sources:
            changes["source_count"] = {
                "previous": prev_sources,
                "current": curr_sources,
            }

        prev_model = self._extract_str(previous, "model_version")
        curr_model = self._extract_str(current, "model_version")
        if prev_model != curr_model:
            changes["model_version"] = {
                "previous": prev_model,
                "current": curr_model,
            }

        return {
            "previous": {
                "prediction_id": self._extract_str(previous, "prediction_id"),
                "model_version": prev_model,
                "generated_at": self._extract_str(previous, "generated_at"),
                "lambda_home": self._extract_numeric(previous, "lambda_home"),
                "lambda_away": self._extract_numeric(previous, "lambda_away"),
                "home_probability": self._extract_numeric(previous, "home_probability"),
                "draw_probability": self._extract_numeric(previous, "draw_probability"),
                "away_probability": self._extract_numeric(previous, "away_probability"),
                "research_available": prev_research,
                "ai_adjustment_applied": prev_ai,
            },
            "current": {
                "prediction_id": self._extract_str(current, "prediction_id"),
                "model_version": curr_model,
                "generated_at": self._extract_str(current, "generated_at"),
                "lambda_home": self._extract_numeric(current, "lambda_home"),
                "lambda_away": self._extract_numeric(current, "lambda_away"),
                "home_probability": self._extract_numeric(current, "home_probability"),
                "draw_probability": self._extract_numeric(current, "draw_probability"),
                "away_probability": self._extract_numeric(current, "away_probability"),
                "research_available": curr_research,
                "ai_adjustment_applied": curr_ai,
            },
            "changes": changes,
        }

    def _extract_numeric(self, d: dict[str, Any], field: str) -> float | None:
        val = d.get(field)
        if val is None:
            nested = d.get("result_probabilities") or d.get("expected_goals")
            if nested and isinstance(nested, dict):
                val = nested.get(field)
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    def _extract_nested(self, d: dict[str, Any], *path: str) -> Any:
        obj: Any = d
        for key in path:
            if isinstance(obj, dict):
                obj = obj.get(key)
            else:
                return None
            if obj is None:
                return None
        return obj

    def _extract_str(self, d: dict[str, Any], field: str) -> str | None:
        val = d.get(field)
        return str(val) if val is not None else None

    def _count_sources(self, d: dict[str, Any]) -> int:
        research = d.get("research_summary") or d.get("research")
        if isinstance(research, dict):
            return research.get("sources_count", 0)
        return 0
