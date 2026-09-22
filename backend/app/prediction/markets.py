"""Market probability calculations from the score matrix.

Computes Over/Under, BTTS, and clean-sheet probabilities from the
score probability matrix.  These are derived mathematically from the
joint probability distribution, not guessed independently.
"""
from __future__ import annotations

from typing import Any

from prediction.score_matrix import ScoreMatrix


class MarketCalculator:
    """Calculate betting markets from a score matrix.

    All markets are computed from the normalized score matrix to ensure
    they are mutually consistent and sum to approximately 1.0 for
    complementary pairs.
    """

    OVER_UNDER_THRESHOLDS: list[float] = [0.5, 1.5, 2.5, 3.5, 4.5]

    def __init__(self, score_matrix: ScoreMatrix) -> None:
        self.matrix = score_matrix
        self._matrix = self._normalize_for_calculations()

    def _normalize_for_calculations(self) -> list[list[float]]:
        """Ensure the matrix is normalized before market calculations."""
        total = sum(sum(row) for row in self.matrix.matrix)
        if total <= 0:
            return self.matrix.matrix
        if abs(total - 1.0) > 0.0001:
            normalized: list[list[float]] = []
            for h_row in self.matrix.matrix:
                row = [val / total for val in h_row]
                normalized.append(row)
            return normalized
        return self.matrix.matrix

    # ── Over/Under ────────────────────────────────────────────────────── #
    def get_over_under(self) -> dict[str, float]:
        """Calculate Over/Under probabilities for standard thresholds.

        Returns a dict with keys like 'over_0_5', 'under_0_5', 'over_1_5', etc.
        Each pair sums to ~1.0.
        """
        results: dict[str, float] = {}

        for threshold in self.OVER_UNDER_THRESHOLDS:
            over_prob = 0.0
            under_prob = 0.0

            for h in range(self.matrix.max_goals + 1):
                for a in range(self.matrix.max_goals + 1):
                    prob = self._matrix[h][a]
                    total_goals = h + a
                    if total_goals > threshold:
                        over_prob += prob
                    elif total_goals < threshold:
                        under_prob += prob
                    else:
                        # Exactly at threshold — split evenly for .5 thresholds
                        # For 2.5, exactly 2 goals is "under 2.5", 3 is "over"
                        over_prob += prob * 0.5
                        under_prob += prob * 0.5

            threshold_key = str(threshold).replace(".", "_")
            results[f"over_{threshold_key}"] = round(over_prob, 6)
            results[f"under_{threshold_key}"] = round(under_prob, 6)

        return results

    def get_over_2_5(self) -> float:
        """Convenience: Over 2.5 goals probability."""
        return self.get_over_under().get("over_2_5", 0.0)

    def get_under_2_5(self) -> float:
        """Convenience: Under 2.5 goals probability."""
        return self.get_over_under().get("under_2_5", 0.0)

    # ── BTTS ──────────────────────────────────────────────────────────── #
    def get_btts(self) -> dict[str, float]:
        """Calculate Both Teams to Score probabilities.

        BTTS Yes: Home >= 1 AND Away >= 1
        BTTS No:  otherwise
        """
        btts_yes = 0.0

        for h in range(self.matrix.max_goals + 1):
            for a in range(self.matrix.max_goals + 1):
                if h >= 1 and a >= 1:
                    btts_yes += self._matrix[h][a]

        btts_no = 1.0 - btts_yes
        return {
            "btts_yes": round(btts_yes, 6),
            "btts_no": round(btts_no, 6),
        }

    # ── Clean Sheets ──────────────────────────────────────────────────── #
    def get_clean_sheets(self) -> dict[str, float]:
        """Calculate clean sheet probabilities for each team.

        Home clean sheet: Away = 0
        Away clean sheet: Home = 0
        """
        home_cs = 0.0  # Home team keeps clean sheet (away scores 0)
        away_cs = 0.0  # Away team keeps clean sheet (home scores 0)

        for h in range(self.matrix.max_goals + 1):
            for a in range(self.matrix.max_goals + 1):
                prob = self._matrix[h][a]
                if a == 0:
                    home_cs += prob
                if h == 0:
                    away_cs += prob

        return {
            "home_clean_sheet": round(home_cs, 6),
            "away_clean_sheet": round(away_cs, 6),
        }

    # ── Double Chance ────────────────────────────────────────────────── #
    def get_double_chance(self) -> dict[str, float]:
        """Calculate double chance market probabilities.

        Home or Draw, Draw or Away, Home or Away
        """
        result_probs = self.matrix.get_result_probabilities()

        return {
            "home_or_draw": round(result_probs["home"] + result_probs["draw"], 6),
            "draw_or_away": round(result_probs["draw"] + result_probs["away"], 6),
            "home_or_away": round(result_probs["home"] + result_probs["away"], 6),
        }

    # ── All markets ──────────────────────────────────────────────────── #
    def get_all_markets(self) -> dict[str, float]:
        """Return all market probabilities as a flat dict."""
        markets: dict[str, float] = {}
        markets.update(self.get_over_under())
        markets.update(self.get_btts())
        markets.update(self.get_clean_sheets())
        markets.update(self.get_double_chance())
        return markets
