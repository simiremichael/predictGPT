"""Core prediction interfaces and data structures.

This module defines:
    * PredictionInput -- aggregated data fed to every model
    * PredictionModel (ABC) -- the abstract model interface
    * ModelResult -- the raw mathematical output of a model
    * Scoreline -- a single (home_goals, away_goals, probability) entry
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from football_data.models import (
    FixtureStatus,
    NormalizedFixture,
    NormalizedForm,
    NormalizedHeadToHead,
    NormalizedInjury,
    NormalizedLineup,
    NormalizedMatchStatistics,
    NormalizedOdds,
    NormalizedSuspension,
    NormalizedTeam,
    NormalizedTeamStatistics,
)


@dataclass
class PredictionInput:
    """Aggregated match-level input consumed by the prediction model.

    This structure is provider-agnostic: every field comes from normalized
    provider data or from the database.  Missing optional fields default to
    ``None`` and the model must degrade gracefully.
    """

    match_id: str
    home_team_id: str
    away_team_id: str
    home_team_name: str
    away_team_name: str
    league_id: str
    season_id: str | None = None
    kickoff_at: datetime | None = None

    # Normalized team data
    home_team: NormalizedTeam | None = None
    away_team: NormalizedTeam | None = None
    home_team_stats: NormalizedTeamStatistics | None = None
    away_team_stats: NormalizedTeamStatistics | None = None
    home_form: NormalizedForm | None = None
    away_form: NormalizedForm | None = None
    h2h: NormalizedHeadToHead | None = None
    injuries: list[NormalizedInjury] = field(default_factory=list)
    suspensions: list[NormalizedSuspension] = field(default_factory=list)
    predicted_lineup: NormalizedLineup | None = None
    confirmed_lineup: NormalizedLineup | None = None
    odds: NormalizedOdds | None = None
    provider: str = "api_football"

    # Recent fixtures for context (pre-kickoff only)
    home_recent_fixture: list[NormalizedFixture] = field(default_factory=list)
    away_recent_fixture: list[NormalizedFixture] = field(default_factory=list)

    # Match statistics (for finished/league matches)
    match_stats: NormalizedMatchStatistics | None = None

    # Metadata
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Scoreline:
    """A single scoreline with its probability."""

    home_goals: int
    away_goals: int
    probability: float

    def as_tuple(self) -> tuple[int, int]:
        return (self.home_goals, self.away_goals)


@dataclass
class ModelResult:
    """Raw mathematical output from a prediction model.

    Contains the lambda values, goal distributions, and the full score matrix.
    The score matrix is a 2-D structure where ``matrix[h][a]`` gives the
    probability of the home team scoring ``h`` goals and the away team scoring
    ``a`` goals.
    """

    model: str
    model_version: str
    lambda_home: float
    lambda_away: float
    home_goal_distribution: list[float]
    away_goal_distribution: list[float]
    score_matrix: list[list[float]]
    max_goals: int
    data_quality: float
    model_parameters: dict[str, Any]
    feature_snapshot: dict[str, Any]


class PredictionModel:
    """Abstract base class for all prediction models.

    Every concrete model must:
        1. Accept a PredictionInput
        2. Return a ModelResult with lambda values and score matrix
        3. Be provider-independent
    """

    model_name: str = "abstract"
    model_version: str = "0.0.0"

    def predict(self, match: PredictionInput) -> ModelResult:
        """Generate a prediction for a single match.

        Args:
            match: Aggregated prediction input.

        Returns:
            ModelResult containing lambda values and score matrix.

        Raises:
            InsufficientDataError: If required data is missing.
        """
        raise NotImplementedError

    def explain_features(self, features: dict[str, Any]) -> list[str]:
        """Return deterministic human-readable feature explanations.

        Must not use LLMs or external calls.
        """
        raise NotImplementedError
