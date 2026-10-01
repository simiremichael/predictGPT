"""Normalized internal football data models.

These Pydantic models are the contract between the provider abstraction layer
and the rest of the application.  Neither the prediction engine, the API
routes, nor the database layer may import or depend on provider-specific
response objects.

Every model carries:
    provider          -- e.g. "api_football" or "sportmonks"
    provider_id       -- the ID as it appears in the provider's API
    internal_id       -- a UUID stable across providers (resolved at runtime)

Optional / provider-specific fields are typed as Optional and default to None,
so models from either provider -- or even a provider missing some data -- remain
valid.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Provider(StrEnum):
    API_FOOTBALL = "api_football"
    SPORTMONKS = "sportmonks"


# ── League & Season -------------------------------------------------------- #
class NormalizedLeague(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_league_id: str
    name: str
    country: str | None = None
    country_code: str | None = None
    season_count: int | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedSeason(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_season_id: str
    league_id: str
    name: str
    year: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_current: bool = False
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


# ── Team ------------------------------------------------------------------- #
class NormalizedTeam(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_team_id: str
    league_id: str | None = None
    season_id: str | None = None
    name: str
    short_name: str | None = None
    slug: str | None = None
    logo_url: str | None = None
    venue_name: str | None = None
    venue_city: str | None = None
    founded: int | None = None
    country: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


# ── Player ----------------------------------------------------------------- #
class NormalizedPlayer(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_player_id: str
    team_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str
    position: str | None = None
    position_detail: str | None = None
    date_of_birth: datetime | None = None
    nationality: str | None = None
    height: int | None = None
    weight: int | None = None
    footed: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


# ── Fixture ---------------------------------------------------------------- #
class FixtureStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    PAUSED = "paused"
    FINISHED = "finished"
    POSTPONED = "postponed"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    AWARDED = "awarded"
    ABANDONED = "abandoned"


class NormalizedFixture(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_fixture_id: str
    league_id: str | None = None
    provider_league_id: str | None = None
    season_id: str | None = None
    provider_season_id: str | None = None
    home_team_id: str | None = None
    provider_home_team_id: str | None = None
    away_team_id: str | None = None
    provider_away_team_id: str | None = None
    home_team_name: str | None = None
    away_team_name: str | None = None
    kickoff_at: datetime | None = None
    timezone: str | None = None
    status: FixtureStatus = FixtureStatus.SCHEDULED
    venue: str | None = None
    referee: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    halftime_home_score: int | None = None
    halftime_away_score: int | None = None
    fulltime_home_score: int | None = None
    fulltime_away_score: int | None = None
    is_finished: bool = False
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def date(self) -> datetime | None:
        """Alias for kickoff_at (some providers call it `date`)."""
        return self.kickoff_at


class NormalizedFixtureList(BaseModel):
    fixtures: list[NormalizedFixture]
    provider: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


# ── Team Statistics -------------------------------------------------------- #
class NormalizedTeamStatistics(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_team_id: str
    league_id: str | None = None
    season_id: str | None = None
    fixture_id: str | None = None
    match_id: str | None = None
    is_home: bool = False
    games_played: int | None = None
    wins: int | None = None
    draws: int | None = None
    losses: int | None = None
    goals_for: int | None = None
    goals_against: int | None = None
    home_goals_for: int | None = None
    away_goals_for: int | None = None
    home_goals_against: int | None = None
    away_goals_against: int | None = None
    clean_sheets: int | None = None
    failed_to_score: int | None = None
    points: int | None = None
    position: int | None = None
    form_rating: float | None = None
    average_possession: float | None = None
    average_shots: float | None = None
    average_shots_on_target: float | None = None
    average_xg: float | None = None
    average_xga: float | None = None
    goals_per_game: float | None = None
    goals_conceded_per_game: float | None = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedForm(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_team_id: str
    fixture_id: str | None = None
    recent_matches: list[NormalizedFixture] = Field(default_factory=list)
    form_score: float | None = None
    form_description: str | None = None
    wins: int | None = None
    draws: int | None = None
    losses: int | None = None
    goals_scored: int | None = None
    goals_conceded: int | None = None
    points_per_match: float | None = None
    average_goals_scored: float | None = None
    average_goals_conceded: float | None = None
    clean_sheet_rate: float | None = None
    failed_to_score_rate: float | None = None
    average_xg: float | None = None
    average_xga: float | None = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedHeadToHead(BaseModel):
    internal_id: str | None = None
    provider: str
    team_a_id: str | None = None
    team_b_id: str | None = None
    league_id: str | None = None
    fixtures: list[NormalizedFixture] = Field(default_factory=list)
    team_a_wins: int | None = None
    team_b_wins: int | None = None
    draws: int | None = None
    avg_goals_per_game: float | None = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
class InjurySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNAVAILABLE = "unavailable"


class NormalizedInjury(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_player_id: str | None = None
    provider_team_id: str | None = None
    team_id: str | None = None
    player_name: str | None = None
    position: str | None = None
    injury_type: str | None = None
    severity: InjurySeverity | None = None
    description: str | None = None
    start_date: datetime | None = None
    return_date: datetime | None = None
    is_startingXI_impact: bool = False
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedSuspension(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_player_id: str | None = None
    provider_team_id: str | None = None
    team_id: str | None = None
    player_name: str | None = None
    position: str | None = None
    reason: str | None = None
    suspension_type: str | None = None
    suspended_from: datetime | None = None
    suspended_until: datetime | None = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class LineupStatus(StrEnum):
    PROJECTED = "projected"
    CONFIRMED = "confirmed"


class NormalizedLineupPlayer(BaseModel):
    player_name: str
    position: str | None = None
    jersey_number: int | None = None
    is_starter: bool = True
    is_substitute: bool = False
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedLineup(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_fixture_id: str
    team_id: str | None = None
    team_name: str | None = None
    status: LineupStatus = LineupStatus.CONFIRMED
    formation: str | None = None
    players: list[NormalizedLineupPlayer] = Field(default_factory=list)
    starting_xi: list[NormalizedLineupPlayer] = Field(default_factory=list)
    substitutes: list[NormalizedLineupPlayer] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedMatchStatistics(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_fixture_id: str
    match_id: str | None = None
    home_team_id: str | None = None
    away_team_id: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    possession: dict[str, float] | None = None
    shots: dict[str, int] | None = None
    shots_on_target: dict[str, int] | None = None
    xg: dict[str, float] | None = None
    xga: dict[str, float] | None = None
    corners: dict[str, int] | None = None
    fouls: dict[str, int] | None = None
    is_finished: bool = False
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedOddsMarket(BaseModel):
    market: str
    selection: str
    odds: float
    is_main: bool = False
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedOdds(BaseModel):
    internal_id: str | None = None
    provider: str
    provider_fixture_id: str
    fixture_id: str | None = None
    markets: list[NormalizedOddsMarket] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedStanding(BaseModel):
    team_id: str | None = None
    team_name: str
    position: int
    points: int
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    form: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedStandings(BaseModel):
    internal_id: str | None = None
    provider: str
    league_id: str | None = None
    season_id: str | None = None
    standings: list[NormalizedStanding] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedPredictionInput(BaseModel):
    """Aggregated input consumed by the prediction engine.

    Built by the orchestrator from fixtures, statistics, form, H2H,
    injuries, lineups and odds across both (or one) providers.
    """

    match_id: str
    home_team_id: str
    away_team_id: str
    home_team_name: str
    away_team_name: str
    league_id: str
    season_id: str | None = None
    kickoff_at: datetime | None = None
    home_goals_scored_season: float | None = None
    home_goals_conceded_season: float | None = None
    away_goals_scored_season: float | None = None
    away_goals_conceded_season: float | None = None
    league_avg_goals: float | None = None
    home_form: list[NormalizedFixture] | None = None
    away_form: list[NormalizedFixture] | None = None
    home_attack_strength: float | None = None
    home_defense_strength: float | None = None
    away_attack_strength: float | None = None
    away_defense_strength: float | None = None
    h2h: NormalizedHeadToHead | None = None
    injuries: list[NormalizedInjury] = Field(default_factory=list)
    suspensions: list[NormalizedSuspension] = Field(default_factory=list)
    predicted_lineup: NormalizedLineup | None = None
    confirmed_lineup: NormalizedLineup | None = None
    odds: NormalizedOdds | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedProviderStatus(BaseModel):
    """Provider availability/health status for the status endpoint."""

    name: str
    configured: bool
    healthy: bool
    error: str | None = None
    last_checked: datetime | None = None
    last_request_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    rate_limit: dict[str, Any] | None = None
    requests_made: int = 0
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderHealthInfo(BaseModel):
    """Detailed health information for a provider, used by admin/test endpoints."""

    provider: str
    configured: bool
    healthy: bool
    response_time_ms: float | None = None
    last_request_at: datetime | None = None
    last_response_status: int | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset: str | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
