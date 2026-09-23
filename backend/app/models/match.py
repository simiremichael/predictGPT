"""SQLAlchemy models for match data, statistics, injuries, lineups, odds, etc."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from models.league import _uuid


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_fixture_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    league_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("leagues.id"), nullable=True, index=True
    )
    season_id: Mapped[str | None] = mapped_column(String, ForeignKey("seasons.id"), nullable=True)
    home_team_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id"), nullable=True, index=True
    )
    away_team_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id"), nullable=True, index=True
    )
    home_team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    away_team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="scheduled")
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    referee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    league: Mapped["League"] = relationship("League", back_populates="matches")


class MatchStatistics(Base):
    __tablename__ = "match_statistics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    possession: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    shots: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    shots_on_target: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    xg: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    xga: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    corners: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    fouls: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class TeamStatistics(Base):
    __tablename__ = "team_statistics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_team_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    internal_team_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id"), nullable=True, index=True
    )
    league_id: Mapped[str | None] = mapped_column(String, ForeignKey("leagues.id"), nullable=True)
    season_id: Mapped[str | None] = mapped_column(String, ForeignKey("seasons.id"), nullable=True)
    is_home: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    games_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    draws: Mapped[int | None] = mapped_column(Integer, nullable=True)
    losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals_for: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals_against: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clean_sheets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    form_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_possession: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_shots: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_xg: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_xga: Mapped[float | None] = mapped_column(Float, nullable=True)
    goals_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    goals_conceded_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    league: Mapped["League"] = relationship("League", back_populates="team_statistics")


class TeamForm(Base):
    __tablename__ = "team_form"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_team_id: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    internal_team_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id"), nullable=True, index=True
    )
    fixture_id: Mapped[str | None] = mapped_column(String, ForeignKey("matches.id"), nullable=True)
    form_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    form_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    recent_match_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class HeadToHead(Base):
    __tablename__ = "head_to_head"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    league_id: Mapped[str | None] = mapped_column(String, ForeignKey("leagues.id"), nullable=True)
    team_a_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    team_b_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    team_a_internal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id"), nullable=True
    )
    team_b_internal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id"), nullable=True
    )
    team_a_wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_b_wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    draws: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_goals_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    fixture_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    league: Mapped["League"] = relationship("League", back_populates="head_to_heads")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_player_id: Mapped[str] = mapped_column(String(100), nullable=False)
    team_id: Mapped[str | None] = mapped_column(String, ForeignKey("teams.id"), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    footed: Mapped[str | None] = mapped_column(String(10), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ProviderPlayer(Base):
    """Maps an internal player UUID to provider-specific IDs."""

    __tablename__ = "provider_players"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    internal_player_id: Mapped[str] = mapped_column(
        String, ForeignKey("players.id"), nullable=False, index=True
    )
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_player_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_team_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Injury(Base):
    __tablename__ = "injuries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_player_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_team_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    internal_team_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id"), nullable=True
    )
    player_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    injury_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    return_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_startingXI_impact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Suspension(Base):
    __tablename__ = "suspensions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_player_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_team_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    internal_team_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id"), nullable=True
    )
    player_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    suspension_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suspended_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PredictedLineup(Base):
    __tablename__ = "predicted_lineups"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_fixture_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    internal_fixture_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("matches.id"), nullable=True
    )
    team_id: Mapped[str | None] = mapped_column(String, ForeignKey("teams.id"), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    formation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    players_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class ConfirmedLineup(Base):
    __tablename__ = "confirmed_lineups"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_fixture_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    internal_fixture_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("matches.id"), nullable=True
    )
    team_id: Mapped[str | None] = mapped_column(String, ForeignKey("teams.id"), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    formation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    players_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class Odds(Base):
    __tablename__ = "odds"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_fixture_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    internal_fixture_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("matches.id"), nullable=True
    )
    markets_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class WebSource(Base):
    __tablename__ = "web_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relevance: Mapped[float | None] = mapped_column(Float, nullable=True)


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    match_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("matches.id"), nullable=True, index=True
    )
    source_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("web_sources.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    claims_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    version: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    match_id: Mapped[str] = mapped_column(
        String, ForeignKey("matches.id"), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prediction_version: Mapped[str] = mapped_column(String(100), nullable=False, default="v1.0.0", index=True)
    research_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("research_runs.id"), nullable=True, index=True
    )
    provider_used: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    lambda_home: Mapped[float | None] = mapped_column(Float, nullable=True)
    lambda_away: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    draw_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    over_2_5_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    under_2_5_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    btts_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    feature_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    news_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    odds_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    ai_adjustment_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # A match+model_version should produce at most one active prediction
    )


class PredictionScoreline(Base):
    __tablename__ = "prediction_scorelines"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    prediction_id: Mapped[str] = mapped_column(
        String, ForeignKey("predictions.id"), nullable=False, index=True
    )
    home_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    away_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    prediction_id: Mapped[str] = mapped_column(
        String, ForeignKey("predictions.id"), nullable=False, index=True
    )
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exact_score_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    top4_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    home_win_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    draw_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    away_win_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    over_25_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    btts_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    league_id: Mapped[str | None] = mapped_column(String, nullable=True)
    season_id: Mapped[str | None] = mapped_column(String, nullable=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ProviderSyncLog(Base):
    __tablename__ = "provider_sync_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    records_fetched: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_stored: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider_used: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    matches_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matches_succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matches_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
