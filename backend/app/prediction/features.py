"""Feature engineering for the prediction engine.

Builds a structured FeatureVector from normalized provider data.  The feature
pipeline converts raw normalized statistics into relative strength measures
(attack strength, defense strength, form strength) that the Poisson model
consumes.

Key design decisions:
    * League baselines are computed from team statistics or fixture history.
    * Team strengths are relative to the league average (not absolute).
    * Form uses recency-weighted match results with a configurable decay.
    * Sample-size protection blends weak signals toward league averages.
    * All features include a quality weight (0-1) indicating confidence.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.config import get_settings
from football_data.models import (
    FixtureStatus,
    NormalizedFixture,
    NormalizedForm,
    NormalizedHeadToHead,
    NormalizedStanding,
    NormalizedStandings,
    NormalizedTeam,
    NormalizedTeamStatistics,
)
from prediction.base import PredictionInput
from prediction.exceptions import InsufficientDataError


@dataclass
class LeagueBaseline:
    """League-level averages computed from historical or seasonal data."""

    league_id: str
    avg_home_goals: float
    avg_away_goals: float
    avg_total_goals: float
    home_win_rate: float
    draw_rate: float
    away_win_rate: float
    btts_rate: float
    over_2_5_rate: float
    games_played: int


@dataclass
class TeamAttDefStrength:
    """Attack and defense strength for a team in a specific context."""

    attack_strength: float
    defense_strength: float
    sample_size: int
    is_home: bool
    quality: float


@dataclass
class FeatureVector:
    """Structured features consumed by the Poisson model.

    All strengths are relative to league averages (>1 means stronger than
    average, <1 means weaker).
    """

    # League baselines
    league: LeagueBaseline

    # Home team context
    home_attack_strength: float
    home_defense_strength: float
    home_form_strength: float

    # Away team context
    away_attack_strength: float
    away_defense_strength: float
    away_form_strength: float

    # Expected goal baselines (per-game averages)
    home_expected_goals_baseline: float
    away_expected_goals_baseline: float

    # xG-based features (when available)
    home_xg: float | None = None
    away_xg: float | None = None
    home_xga: float | None = None
    away_xga: float | None = None

    # H2H signal
    h2h_signal: float | None = None

    # Data quality components
    data_quality: float = 0.0

    # Diagnostic info
    home_sample: int = 0
    away_sample: int = 0
    form_matches_used: int = 0
    missing_features: list[str] = field(default_factory=list)

    # Raw input snapshot for reproducibility
    raw_snapshot: dict[str, Any] = field(default_factory=dict)


class FeatureBuilder:
    """Builds FeatureVector objects from PredictionInput.

    The builder is stateless (aside from config) and uses cutoff_datetime
    for backtesting to prevent data leakage.
    """

    def __init__(self, history_window: int | None = None) -> None:
        settings = get_settings()
        self.history_window = history_window or settings.sync_form_match_count
        self.min_form_matches = getattr(
            settings, "min_form_matches", 5
        )
        self.default_home_advantage = 1.0
        self.form_decay_rate = 0.1

    def build(
        self,
        match_input: PredictionInput,
        league_baseline: LeagueBaseline | None = None,
    ) -> FeatureVector:
        """Build features for a single match.

        Args:
            match_input: Aggregated prediction input.
            league_baseline: Pre-computed league baseline.  If None, derived
                from available team statistics.

        Returns:
            FeatureVector ready for the prediction model.

        Raises:
            InsufficientDataError: If critical data is missing and cannot
                be derived from available inputs.
        """
        missing: list[str] = []

        # Resolve league baseline
        if league_baseline is None:
            league_baseline = self._derive_league_baseline(match_input)

        # Compute team attack/defense strengths
        home_strength = self._compute_team_strength(
            match_input,
            match_input.home_team_stats,
            match_input.home_form,
            is_home=True,
            league_baseline=league_baseline,
        )
        away_strength = self._compute_team_strength(
            match_input,
            match_input.away_team_stats,
            match_input.away_form,
            is_home=False,
            league_baseline=league_baseline,
        )

        # Form strengths
        home_form_strength = self._compute_form_strength(
            match_input.home_form, match_input.home_recent_fixture, is_home=True
        )
        away_form_strength = self._compute_form_strength(
            match_input.away_form, match_input.away_recent_fixture, is_home=False
        )

        # xG
        home_xg = home_strength.get("xg") if home_strength else None
        away_xg = away_strength.get("away_xg") if away_strength else None
        home_xga = home_strength.get("xga") if home_strength else None
        away_xga = away_strength.get("away_xga") if away_strength else None

        # H2H signal
        h2h_signal = self._compute_h2h_signal(match_input.h2h)

        # Expected goal baselines (lambda priors)
        home_lambda_baseline = (
            league_baseline.avg_home_goals * self.default_home_advantage
        )
        away_lambda_baseline = league_baseline.avg_away_goals

        # Data quality
        data_quality = self._compute_data_quality(
            match_input, home_strength, away_strength, league_baseline
        )

        # Build raw snapshot
        raw_snapshot = self._build_raw_snapshot(
            match_input, league_baseline, home_strength, away_strength
        )

        # Collect missing features
        if match_input.home_team_stats is None:
            missing.append("home_team_stats")
        if match_input.away_team_stats is None:
            missing.append("away_team_stats")
        if match_input.home_form is None:
            missing.append("home_form")
        if match_input.away_form is None:
            missing.append("away_form")
        if match_input.h2h is None:
            missing.append("h2h")
        if match_input.odds is None:
            missing.append("odds")
        if match_input.injuries:
            missing.append(f"injuries:{len(match_input.injuries)}")
        if match_input.confirmed_lineup is None:
            missing.append("confirmed_lineup")

        return FeatureVector(
            league=league_baseline,
            home_attack_strength=home_strength["attack"] if home_strength else 1.0,
            home_defense_strength=home_strength["defense"] if home_strength else 1.0,
            home_form_strength=home_form_strength,
            away_attack_strength=away_strength["attack"] if away_strength else 1.0,
            away_defense_strength=away_strength["defense"] if away_strength else 1.0,
            away_form_strength=away_form_strength,
            home_expected_goals_baseline=home_lambda_baseline,
            away_expected_goals_baseline=away_lambda_baseline,
            home_xg=home_xg,
            away_xg=away_xg,
            home_xga=home_xga,
            away_xga=away_xga,
            h2h_signal=h2h_signal,
            data_quality=data_quality,
            home_sample=home_strength.get("sample", 0) if home_strength else 0,
            away_sample=away_strength.get("sample", 0) if away_strength else 0,
            form_matches_used=self.history_window,
            missing_features=missing,
            raw_snapshot=raw_snapshot,
        )

    def _derive_league_baseline(self, match_input: PredictionInput) -> LeagueBaseline:
        """Derive league baseline from available team statistics.

        Falls back to documented defaults if no data is available.
        """
        home_stats = match_input.home_team_stats
        away_stats = match_input.away_team_stats

        # Use team stats to estimate league averages
        home_gpg = home_stats.goals_per_game if home_stats and home_stats.goals_per_game else 1.5
        away_gpg = away_stats.goals_per_game if away_stats and away_stats.goals_per_game else 1.0

        # Try to get more precise league averages from form
        home_scored = 0.0
        home_conceded = 0.0
        away_scored = 0.0
        away_conceded = 0.0
        total_games = 0

        for stats in [home_stats, away_stats]:
            if stats and stats.games_played:
                total_games += stats.games_played or 0
                if stats.goals_for:
                    if stats.is_home:
                        home_scored += stats.goals_for
                    else:
                        away_scored += stats.goals_for
                if stats.goals_against:
                    if stats.is_home:
                        home_conceded += stats.goals_against
                    else:
                        away_conceded += stats.goals_against

        return LeagueBaseline(
            league_id=match_input.league_id,
            avg_home_goals=home_gpg,
            avg_away_goals=away_gpg,
            avg_total_goals=home_gpg + away_gpg,
            home_win_rate=0.45,
            draw_rate=0.27,
            away_win_rate=0.28,
            btts_rate=0.52,
            over_2_5_rate=0.48,
            games_played=total_games,
        )

    def _compute_team_strength(
        self,
        match_input: PredictionInput,
        stats: NormalizedTeamStatistics | None,
        form: NormalizedForm | None,
        is_home: bool,
        league_baseline: LeagueBaseline,
    ) -> dict[str, float] | None:
        """Compute attack and defense strength for a team.

        Returns None if no stats available.  Uses sample-size protection
        to blend toward league average for small samples.
        """
        if stats is None and form is None:
            return None

        # Gather goals data
        games = 0
        gpg: float | None = None
        gpergame: float | None = None
        xg: float | None = None
        xga: float | None = None

        if stats is not None:
            games = stats.games_played or 0
            gpg = stats.goals_per_game
            gpergame = stats.goals_conceded_per_game
            xg = stats.average_xg
            xga = stats.average_xga

            # Use context-specific splits when available
            if is_home:
                if gpg is None and stats.home_goals_for is not None:
                    games_for_stats = max(games, 1)
                    gpg = stats.home_goals_for / games_for_stats
                if gpergame is None and stats.away_goals_against is not None:
                    games_for_stats = max(games, 1)
                    gpergame = stats.away_goals_against / games_for_stats
            else:
                if gpg is None and stats.away_goals_for is not None:
                    games_for_stats = max(games, 1)
                    gpg = stats.away_goals_for / games_for_stats
                if gpergame is None and stats.home_goals_against is not None:
                    games_for_stats = max(games, 1)
                    gpergame = stats.home_goals_against / games_for_stats

        # Fall back to form data
        if form is not None:
            if games == 0:
                games = len(form.recent_matches) or 0
            if gpg is None:
                gpg = form.average_goals_scored
            if gpergame is None:
                gpergame = form.average_goals_conceded
            if xg is None:
                xg = form.average_xg
            if xga is None:
                xga = form.average_xga
            xg = form.average_xg
            xga = form.average_xga

        if games == 0 and gpg is None:
            return None

        games = max(games, 1)

        # Compute per-game rates
        if gpg is not None:
            scored_per_game = gpg
        elif games > 0 and stats is not None:
            scored_per_game = (stats.goals_for or 0) / games
        else:
            scored_per_game = 0.0
        conceded_per_game = gpergame if gpergame is not None else 0.0

        if is_home:
            league_scored = league_baseline.avg_home_goals
            league_conceded = league_baseline.avg_away_goals
        else:
            league_scored = league_baseline.avg_away_goals
            league_conceded = league_baseline.avg_home_goals

        # Sample-size protection: blend toward league average
        weight = self._sample_weight(games, self.min_form_matches)

        attack_strength = (scored_per_game / league_scored) if league_scored > 0 else 1.0
        defense_strength = (conceded_per_game / league_conceded) if league_conceded > 0 else 1.0

        # Blend toward 1.0 (league average) for small samples
        attack_strength = weight * attack_strength + (1 - weight) * 1.0
        defense_strength = weight * defense_strength + (1 - weight) * 1.0

        result: dict[str, float] = {
            "attack": attack_strength,
            "defense": defense_strength,
            "sample": float(games),
        }

        if xg is not None:
            result["xg"] = xg
        if xga is not None:
            if is_home:
                result["xga"] = xga
            else:
                result["away_xga"] = xga

        return result

    def _compute_form_strength(
        self,
        form: NormalizedForm | None,
        recent_fixture: list[NormalizedFixture] | None,
        is_home: bool,
    ) -> float:
        """Compute form strength from recent matches.

        Uses recency weighting with exponential decay.  Returns a multiplier
        where 1.0 = neutral, >1 = positive form, <1 = negative form.
        """
        matches: list[NormalizedFixture] = []
        if form is not None:
            matches = form.recent_matches
        elif recent_fixture:
            matches = list(recent_fixture)

        if not matches:
            return 1.0

        # Take last N matches
        recent = matches[-self.history_window:]
        if not recent:
            return 1.0

        # Compute weighted points per game
        total_weighted_points = 0.0
        total_weight = 0.0

        for i, fixture in enumerate(recent):
            # Most recent = highest weight
            recency_weight = math.exp(-self.form_decay_rate * (len(recent) - 1 - i))
            total_weight += recency_weight

            if fixture.is_finished and fixture.home_score is not None and fixture.away_score is not None:
                if is_home:
                    if fixture.home_score > fixture.away_score:
                        points = 3.0
                    elif fixture.home_score == fixture.away_score:
                        points = 1.0
                    else:
                        points = 0.0
                else:
                    if fixture.away_score > fixture.home_score:
                        points = 3.0
                    elif fixture.away_score == fixture.home_score:
                        points = 1.0
                    else:
                        points = 0.0

                total_weighted_points += recency_weight * points

        if total_weight == 0:
            return 1.0

        weighted_ppg = total_weighted_points / total_weight
        # Normalize: 1.36 ppg (all wins) = 1.0 multiplier, 0 ppg = 0.0
        # Average is ~1.0, so we scale: strength = weighted_ppg / 1.36 * 0.4 + 0.8
        baseline_ppg = 1.36
        normalized = (weighted_ppg / baseline_ppg) * 0.4 + 0.6

        return max(0.5, min(1.5, normalized))

    def _compute_h2h_signal(
        self, h2h: NormalizedHeadToHead | None
    ) -> float | None:
        """Compute a head-to-head advantage signal.

        Returns a multiplier where >1 means team A historically outperforms
        vs team B, <1 means team B outperforms.  None if insufficient data.
        """
        if h2h is None:
            return None

        total = (h2h.team_a_wins or 0) + (h2h.team_b_wins or 0) + (h2h.draws or 0)
        if total == 0:
            return None

        # Use sqrt shrinkage to avoid extreme H2H bias from small samples
        shrinkage = 10.0
        a_wins_scaled = (h2h.team_a_wins or 0) + (0.5 * shrinkage)
        b_wins_scaled = (h2h.team_b_wins or 0) + (0.5 * shrinkage)
        signal = a_wins_scaled / b_wins_scaled if b_wins_scaled > 0 else 1.0

        return signal

    def _compute_data_quality(
        self,
        match_input: PredictionInput,
        home_strength: dict[str, float] | None,
        away_strength: dict[str, float] | None,
        league_baseline: LeagueBaseline,
    ) -> float:
        """Compute a data quality score between 0 and 1.

        Considers:
            - sample sizes for both teams
            - xG availability
            - H2H availability
            - odds availability
            - injury/suspension info
        """
        quality = 0.0

        # Team stats quality (40%)
        if home_strength and home_strength.get("sample", 0) >= self.min_form_matches:
            quality += 0.20
        if away_strength and away_strength.get("sample", 0) >= self.min_form_matches:
            quality += 0.20

        # xG quality (20%)
        if home_strength and home_strength.get("xg") is not None:
            quality += 0.10
        if away_strength and away_strength.get("away_xga") is not None or away_strength and away_strength.get("xga") is not None:
            quality += 0.10

        # H2H quality (10%)
        if match_input.h2h is not None:
            total = (match_input.h2h.team_a_wins or 0) + (match_input.h2h.team_b_wins or 0) + (match_input.h2h.draws or 0)
            if total >= 5:
                quality += 0.10

        # Odds quality (15%)
        if match_input.odds is not None:
            quality += 0.15

        # Injuries/suspensions quality (5%)
        if match_input.injuries or match_input.suspensions:
            quality += 0.05

        # League baseline quality (10%)
        if league_baseline.games_played >= 50:
            quality += 0.10

        return min(1.0, quality)

    def _sample_weight(self, sample: int, min_matches: int) -> float:
        """Compute shrinkage weight for sample-size protection.

        Returns a weight where 0 = fully blended to league average,
        1 = fully trust sample data.  Uses sqrt shrinkage.
        """
        if sample <= 0:
            return 0.0
        return min(1.0, math.sqrt(sample / min_matches))

    def _build_raw_snapshot(
        self,
        match_input: PredictionInput,
        baseline: LeagueBaseline,
        home_strength: dict[str, float] | None,
        away_strength: dict[str, float] | None,
    ) -> dict[str, Any]:
        """Build a snapshot of raw feature values for reproducibility."""
        return {
            "league_id": match_input.league_id,
            "season_id": match_input.season_id,
            "home_team_id": match_input.home_team_id,
            "away_team_id": match_input.away_team_id,
            "league_baseline": {
                "avg_home_goals": baseline.avg_home_goals,
                "avg_away_goals": baseline.avg_away_goals,
                "avg_total_goals": baseline.avg_total_goals,
            },
            "home_strength": home_strength,
            "away_strength": away_strength,
        }
