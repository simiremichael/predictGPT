"""Pydantic response schemas for API endpoints.

All schemas inherit from the standard ``SuccessResponse`` / ``PaginatedResponse``
envelope so clients receive a consistent shape across endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from prediction.schemas import (
    AIAdjustmentSchema,
    ExpectedGoalsSchema,
    MarketBTTSchema,
    MarketCleanSheetSchema,
    MarketDoubleChanceSchema,
    MarketOverUnderSchema,
    MarketsSchema,
    PredictionOutputSchema,
    ResearchSummarySchema,
    ResultProbabilitiesSchema,
    ScorelineSchema,
)


class TeamResponse(BaseModel):
    id: str
    name: str
    short_name: str | None = None
    slug: str | None = None
    logo_url: str | None = None
    venue_name: str | None = None
    venue_city: str | None = None
    country: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


class LeagueResponse(BaseModel):
    id: str
    name: str
    country: str | None = None
    country_code: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


class SeasonResponse(BaseModel):
    id: str
    league_id: str
    name: str
    year: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_current: bool = False


class StandingResponse(BaseModel):
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


class MatchBrief(BaseModel):
    id: str
    league_id: str | None = None
    league_name: str | None = None
    season_id: str | None = None
    home_team_id: str | None = None
    home_team_name: str | None = None
    away_team_id: str | None = None
    away_team_name: str | None = None
    kickoff_at: datetime | None = None
    status: str = "scheduled"
    venue: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    is_finished: bool = False
    retrieved_at: datetime | None = None


class MatchDetailResponse(BaseModel):
    match: MatchBrief
    league: LeagueResponse | None = None
    season: SeasonResponse | None = None
    home_team: TeamResponse | None = None
    away_team: TeamResponse | None = None
    venue: str | None = None
    referee: str | None = None
    statistics: dict[str, Any] | None = None
    form: dict[str, Any] | None = None
    h2h: dict[str, Any] | None = None
    injuries: list[dict[str, Any]] = Field(default_factory=list)
    suspensions: list[dict[str, Any]] = Field(default_factory=list)
    lineups: list[dict[str, Any]] = Field(default_factory=list)
    odds: dict[str, Any] | None = None
    retrieved_at: datetime | None = None


class MatchSummaryResponse(BaseModel):
    match: MatchBrief
    prediction: dict[str, Any] | None = None
    data_quality: dict[str, Any] | None = None


class PredictionSummaryResponse(BaseModel):
    prediction_id: str
    match_id: str
    match_home_team: str
    match_away_team: str
    model: str
    model_version: str
    prediction_version: str
    generated_at: datetime
    lambda_home: float
    lambda_away: float
    result_probabilities: ResultProbabilitiesSchema
    top_scoreline: ScorelineSchema | None = None
    top_4_scorelines: list[ScorelineSchema] = Field(default_factory=list)
    markets: MarketsSchema
    data_quality: float
    model_confidence: float
    research_available: bool = False
    ai_adjustment_applied: bool = False
    ai_explanation: str | None = None


class PredictionHistoryItem(BaseModel):
    prediction_id: str
    match_id: str
    match_home_team: str
    match_away_team: str
    model_version: str
    prediction_version: str
    generated_at: datetime
    data_quality: float
    model_confidence: float
    home_probability: float | None = None
    draw_probability: float | None = None
    away_probability: float | None = None
    ai_adjustment_applied: bool = False
    context_hash: str | None = None


class PredictionComparisonItem(BaseModel):
    prediction_id: str
    model_version: str
    prediction_version: str
    generated_at: datetime
    lambda_home: float
    lambda_away: float
    home_probability: float | None = None
    draw_probability: float | None = None
    away_probability: float | None = None
    research_available: bool = False
    ai_adjustment_applied: bool = False
    context_hash: str | None = None


class PredictionChangeResponse(BaseModel):
    previous: PredictionComparisonItem
    current: PredictionComparisonItem
    changes: dict[str, Any] = Field(default_factory=dict)


class ResearchEvidenceItemResponse(BaseModel):
    subject: str
    claim: str | None = None
    evidence_status: str
    confidence: float
    source_ids: list[str]


class ResearchSourceItemResponse(BaseModel):
    url: str
    title: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    source_type: str | None = None
    credibility_score: float = 0.0
    freshness_score: float = 0.0


class ResearchResponse(BaseModel):
    match_id: str
    researched_at: datetime | None = None
    sources: list[ResearchSourceItemResponse] = Field(default_factory=list)
    injuries: list[ResearchEvidenceItemResponse] = Field(default_factory=list)
    suspensions: list[ResearchEvidenceItemResponse] = Field(default_factory=list)
    lineups: list[dict[str, Any]] = Field(default_factory=list)
    team_news: list[ResearchEvidenceItemResponse] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    data_quality: float = 0.0


class SearchResultItem(BaseModel):
    id: str
    type: str
    name: str
    subtitle: str | None = None


class SearchResponse(BaseModel):
    teams: list[SearchResultItem] = Field(default_factory=list)
    players: list[SearchResultItem] = Field(default_factory=list)
    leagues: list[SearchResultItem] = Field(default_factory=list)
    matches: list[SearchResultItem] = Field(default_factory=list)


class PerformanceResponse(BaseModel):
    model_version: str | None = None
    league_id: str | None = None
    season_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    total_predictions: int = 0
    evaluated_predictions: int = 0
    metrics: dict[str, float] = Field(default_factory=dict)
    top_4_hit_rate: float | None = None
    exact_score_hit_rate: float | None = None
    brier_score: float | None = None
    log_loss: float | None = None


class ProviderStatusResponse(BaseModel):
    active_provider: str
    providers: dict[str, Any] = Field(default_factory=dict)


class PredictionJobStatus(str):
    """Enum-like class for prediction job statuses."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
