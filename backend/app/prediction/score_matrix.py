"""Score probability matrix operations.

Builds the 2D score matrix from goal distributions, normalizes it,
extracts top-N scorelines, and computes result probabilities (Home/Draw/Away).
"""
from __future__ import annotations

import math
from typing import Any

from prediction.base import ModelResult, Scoreline


class ScoreMatrix:
    """Operations on a Poisson score probability matrix.

    The matrix is indexed as ``matrix[home_goals][away_goals]`` giving the
    probability of that exact scoreline.
    """

    def __init__(
        self,
        home_distribution: list[float],
        away_distribution: list[float],
        max_goals: int = 8,
    ) -> None:
        self.home_distribution = home_distribution
        self.away_distribution = away_distribution
        self.max_goals = max_goals
        self.matrix = self._build_matrix()

    def _build_matrix(self) -> list[list[float]]:
        """Build the joint probability matrix via the outer product.

        Assumes independence between home and away goal counts (standard
        independent Poisson model).
        """
        matrix: list[list[float]] = []
        for h in range(self.max_goals + 1):
            row = []
            for a in range(self.max_goals + 1):
                prob = self.home_distribution[h] * self.away_distribution[a]
                row.append(prob)
            matrix.append(row)
        return matrix

    def normalize(self) -> list[list[float]]:
        """Normalize the matrix so all probabilities sum to 1.0.

        This is needed when the goal range is truncated (e.g., max_goals=8)
        and the remaining probability mass is lost.
        """
        total = self._sum_matrix(self.matrix)
        if total <= 0:
            return self.matrix

        if abs(total - 1.0) > 0.0001:
            normalized: list[list[float]] = []
            for h in range(self.max_goals + 1):
                row = []
                for a in range(self.max_goals + 1):
                    row.append(self.matrix[h][a] / total)
                normalized.append(row)
            return normalized

        return self.matrix

    def get_top_scorelines(self, n: int = 4) -> list[Scoreline]:
        """Return the top-N most probable scorelines.

        Scorelines are sorted by probability descending.  Ties are broken
        by lower total goals (more conservative scorelines first).
        """
        all_scorelines: list[Scoreline] = []
        for h in range(self.max_goals + 1):
            for a in range(self.max_goals + 1):
                prob = self.matrix[h][a]
                if prob > 0:
                    all_scorelines.append(Scoreline(h, a, prob))

        # Sort by probability descending, then by total goals ascending for ties
        all_scorelines.sort(key=lambda s: (-s.probability, s.home_goals + s.away_goals))

        return all_scorelines[:n]

    def get_top_scoreline(self) -> Scoreline | None:
        """Return the single most probable scoreline."""
        top = self.get_top_scorelines(n=1)
        return top[0] if top else None

    def get_result_probabilities(self) -> dict[str, float]:
        """Calculate Home / Draw / Away probabilities from the matrix.

        Returns:
            Dict with keys 'home', 'draw', 'away' and values summing to ~1.0.
        """
        home_prob = 0.0
        draw_prob = 0.0
        away_prob = 0.0

        for h in range(self.max_goals + 1):
            for a in range(self.max_goals + 1):
                prob = self.matrix[h][a]
                if h > a:
                    home_prob += prob
                elif h == a:
                    draw_prob += prob
                else:
                    away_prob += prob

        return {"home": home_prob, "draw": draw_prob, "away": away_prob}

    def get_total_probability(self) -> float:
        """Sum all probabilities in the matrix."""
        return self._sum_matrix(self.matrix)

    def get_tail_mass(self) -> float:
        """Compute the probability mass in the truncated tail (> max_goals).

        This represents goals beyond the matrix which are "lost" when
        truncating the distribution.
        """
        home_tail = 1.0 - sum(self.home_distribution[: self.max_goals + 1])
        away_tail = 1.0 - sum(self.away_distribution[: self.max_goals + 1])
        # Conservative: at least one team exceeds max_goals
        return home_tail + away_tail - home_tail * away_tail

    def _sum_matrix(self, matrix: list[list[float]]) -> float:
        """Sum all entries in a 2D matrix."""
        total = 0.0
        for row in matrix:
            total += sum(row)
        return total

    def to_serializable(self) -> list[list[float]]:
        """Return a JSON-serializable copy of the normalized matrix."""
        return [row[:] for row in self.matrix]

    @classmethod
    def from_model_result(cls, result: ModelResult) -> ScoreMatrix:
        """Create a ScoreMatrix from an existing ModelResult."""
        return cls(
            home_distribution=result.home_goal_distribution,
            away_distribution=result.away_goal_distribution,
            max_goals=result.max_goals,
        )
