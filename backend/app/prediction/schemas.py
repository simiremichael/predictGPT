"""Prediction output schemas (Pydantic models for API responses).

These models define the JSON structure returned by the prediction API.
They are completely independent of the internal model representation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScorelineSchema(BaseModel):
    """A predicted scoreline with probability."""

    home_goals: int
    away_goals: int
    probability: float


class ExpectedGoalsSchema(BaseModel):
    """Expected goals for both teams."""

    home: float
    away: float


class GoalDistributionSchema(BaseModel):
    """Goal distribution for a single team."""

    probabilities: list[float]
    mean: float


class GoalDistributionsSchema(BaseModel):
    """Goal distributions for both teams."""

    home: GoalDistributionSchema
    away: GoalDistributionSchema


class ScoreMatrixSchema(BaseModel):
    """Full score probability matrix."""

    home_max_goals: int
    away_max_goals: int
    matrix: list[list[float]]


class ResultProbabilitiesSchema(BaseModel):
    """Home / Draw / Away probabilities."""

    home: float
    draw: float
    away: float


class MarketOverUnderSchema(BaseModel):
    """Over/Under market probabilities."""

    over_0_5: float
    over_1_5: float
    over_2_5: float
    over_3_5: float
    over_4_5: float
    under_0_5: float
    under_1_5: float
    under_2_5: float
    under_3_5: float
    under_4_5: float


class MarketBTTSchema(BaseModel):
    """Both Teams To Score probabilities."""

    yes: float
    no: float


class MarketCleanSheetSchema(BaseModel):
    """Clean sheet probabilities for each team."""

    home_clean_sheet: float
    away_clean_sheet: float


class MarketDoubleChanceSchema(BaseModel):
    """Double chance market probabilities."""

    home_or_draw: float
    draw_or_away: float
    home_or_away: float


class MarketsSchema(BaseModel):
    """All market probabilities."""

    over_under: MarketOverUnderSchema
    btts: MarketBTTSchema
    clean_sheets: MarketCleanSheetSchema
    double_chance: MarketDoubleChanceSchema


class ResearchSourceSchema(BaseModel):
    """Schema for a research source in API responses."""

    url: str
    title: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    source_type: str | None = None
    credibility_score: float
    freshness_score: float


class EvidenceItemSchema(BaseModel):
    """Schema for a single evidence item in API responses."""

    subject: str
    claim: str | None = None
    evidence_status: str
    confidence: float
    source_ids: list[str]


class ResearchSummarySchema(BaseModel):
    """Summary of research in API responses."""

    available: bool = False
    data_quality: float = 0.0
    sources_count: int = 0
    injuries_count: int = 0
    suspensions_count: int = 0
    lineups_count: int = 0
    team_news_count: int = 0
    conflicts_count: int = 0
    average_credibility: float = 0.0
    average_freshness: float = 0.0
    researched_at: datetime | None = None


class AIAdjustmentSchema(BaseModel):
    """Schema for AI adjustment in API responses."""

    applied: bool
    version: str | None = None
    home_attack_adjustment: float = 0.0
    away_attack_adjustment: float = 0.0
    home_defense_adjustment: float = 0.0
    away_defense_adjustment: float = 0.0
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class PredictionOutputSchema(BaseModel):
    """Complete prediction output for a single match.

    This is the main API response model.
    """

    model: str
    model_version: str
    prediction_version: str = "v1.0.0"
    lambda_home: float
    lambda_away: float
    expected_goals: ExpectedGoalsSchema
    expected_total_goals: float
    result_probabilities: ResultProbabilitiesSchema
    top_scoreline: ScorelineSchema | None = None
    top_4_scorelines: list[ScorelineSchema] = Field(default_factory=list)
    score_matrix: ScoreMatrixSchema | None = None
    goal_distributions: GoalDistributionsSchema | None = None
    markets: MarketsSchema
    data_quality: float
    model_confidence: float
    prediction_stability: str
    feature_explanations: list[str] = Field(default_factory=list)
    feature_snapshot: dict[str, Any]
    model_parameters: dict[str, Any]
    generated_at: datetime
    match_id: str
    match_home_team: str
    match_away_team: str
    match_kickoff: datetime | None = None
    research: ResearchSummarySchema
    ai_adjustment: AIAdjustmentSchema
    ai_explanation: str | None = None
    confidence: float = 0.0
    uncertainty: float = 0.0
    source_ids: list[str] = Field(default_factory=list)
    context_hash: str | None = None


class PredictionResponseSchema(BaseModel):
    """Wrapper around a prediction with match context."""

    match: dict[str, Any]
    prediction: dict[str, Any]
