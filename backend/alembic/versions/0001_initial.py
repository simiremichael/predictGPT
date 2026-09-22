"""Create initial tables.

Revision ID: 0001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

Creates all core tables for the Football AI platform using the SQLAlchemy
model metadata.  Generated from the declarative models in ``models/``.
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import UUID, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON

# revision identifiers
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = "football_ai"
depends_on: str | Sequence[str] | None = None


# ── helper ───────────────────────────────────────────────────────── #
def _uuid() -> sa.Column:
    return sa.Column("id", String(), primary_key=True)


def _created() -> sa.Column:
    return sa.Column("created_at", DateTime, nullable=False, default=sa.func.now())


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────── #
    op.create_table(
        "users",
        sa.Column("id", String(), primary_key=True),
        sa.Column("email", String(255), nullable=False, unique=True),
        sa.Column("hashed_password", String(255), nullable=False),
        sa.Column("is_active", Boolean, default=True, nullable=False),
        sa.Column("is_superuser", Boolean, default=False, nullable=False),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    # ── leagues ────────────────────────────────────────────────────── #
    op.create_table(
        "leagues",
        sa.Column("id", String(), primary_key=True),
        sa.Column("name", String(255), nullable=False),
        sa.Column("country", String(100), nullable=True),
        sa.Column("country_code", String(10), nullable=True),
        sa.Column("is_active", Boolean, default=True, nullable=False),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    op.create_table(
        "seasons",
        sa.Column("id", String(), primary_key=True),
        sa.Column("league_id", String(), ForeignKey("leagues.id"), nullable=False, index=True),
        sa.Column("name", String(100), nullable=False),
        sa.Column("year", Integer, nullable=True),
        sa.Column("start_date", DateTime, nullable=True),
        sa.Column("end_date", DateTime, nullable=True),
        sa.Column("is_current", Boolean, default=False, nullable=False),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    op.create_table(
        "provider_leagues",
        sa.Column("id", String(), primary_key=True),
        sa.Column("internal_league_id", String(), ForeignKey("leagues.id"), nullable=False, index=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_league_id", String(100), nullable=False),
        sa.Column("provider_season_id", String(100), nullable=True),
        sa.Column("is_active", Boolean, default=True, nullable=False),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    # ── teams ──────────────────────────────────────────────────────── #
    op.create_table(
        "teams",
        sa.Column("id", String(), primary_key=True),
        sa.Column("name", String(255), nullable=False),
        sa.Column("short_name", String(50), nullable=True),
        sa.Column("slug", String(100), nullable=True, unique=True),
        sa.Column("logo_url", Text, nullable=True),
        sa.Column("venue_name", String(255), nullable=True),
        sa.Column("venue_city", String(100), nullable=True),
        sa.Column("founded", Integer, nullable=True),
        sa.Column("country", String(100), nullable=True),
        sa.Column("is_active", Boolean, default=True, nullable=False),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    op.create_table(
        "provider_teams",
        sa.Column("id", String(), primary_key=True),
        sa.Column("internal_team_id", String(), ForeignKey("teams.id"), nullable=False, index=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_team_id", String(100), nullable=False),
        sa.Column("is_active", Boolean, default=True, nullable=False),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    # ── matches ────────────────────────────────────────────────────── #
    op.create_table(
        "matches",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_fixture_id", String(100), nullable=False, index=True),
        sa.Column("league_id", String(), ForeignKey("leagues.id"), nullable=True, index=True),
        sa.Column("season_id", String(), ForeignKey("seasons.id"), nullable=True),
        sa.Column("home_team_id", String(), ForeignKey("teams.id"), nullable=True, index=True),
        sa.Column("away_team_id", String(), ForeignKey("teams.id"), nullable=True, index=True),
        sa.Column("home_team_name", String(255), nullable=True),
        sa.Column("away_team_name", String(255), nullable=True),
        sa.Column("kickoff_at", DateTime, nullable=True, index=True),
        sa.Column("status", String(50), nullable=False, default="scheduled"),
        sa.Column("venue", String(255), nullable=True),
        sa.Column("referee", String(255), nullable=True),
        sa.Column("home_score", Integer, nullable=True),
        sa.Column("away_score", Integer, nullable=True),
        sa.Column("is_finished", Boolean, default=False, nullable=False),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("provider_metadata", JSON, default=dict),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    # ── match_statistics ───────────────────────────────────────────── #
    op.create_table(
        "match_statistics",
        sa.Column("id", String(), primary_key=True),
        sa.Column("match_id", String(), ForeignKey("matches.id"), nullable=False, index=True),
        sa.Column("provider_name", String(50), nullable=False),
        sa.Column("possession", JSON, nullable=True),
        sa.Column("shots", JSON, nullable=True),
        sa.Column("shots_on_target", JSON, nullable=True),
        sa.Column("xg", JSON, nullable=True),
        sa.Column("xga", JSON, nullable=True),
        sa.Column("corners", JSON, nullable=True),
        sa.Column("fouls", JSON, nullable=True),
        sa.Column("is_finished", Boolean, default=True, nullable=False),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
    )

    # ── team_statistics ─────────────────────────────────────────────── #
    op.create_table(
        "team_statistics",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_team_id", String(100), nullable=False, index=True),
        sa.Column("internal_team_id", String(), ForeignKey("teams.id"), nullable=True, index=True),
        sa.Column("league_id", String(), ForeignKey("leagues.id"), nullable=True),
        sa.Column("season_id", String(), ForeignKey("seasons.id"), nullable=True),
        sa.Column("is_home", Boolean, default=False, nullable=False),
        sa.Column("games_played", Integer, nullable=True),
        sa.Column("wins", Integer, nullable=True),
        sa.Column("draws", Integer, nullable=True),
        sa.Column("losses", Integer, nullable=True),
        sa.Column("goals_for", Integer, nullable=True),
        sa.Column("goals_against", Integer, nullable=True),
        sa.Column("clean_sheets", Integer, nullable=True),
        sa.Column("points", Integer, nullable=True),
        sa.Column("position", Integer, nullable=True),
        sa.Column("form_rating", Float, nullable=True),
        sa.Column("average_possession", Float, nullable=True),
        sa.Column("average_shots", Float, nullable=True),
        sa.Column("average_xg", Float, nullable=True),
        sa.Column("average_xga", Float, nullable=True),
        sa.Column("goals_per_game", Float, nullable=True),
        sa.Column("goals_conceded_per_game", Float, nullable=True),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("provider_metadata", JSON, default=dict),
    )

    # ── team_form ──────────────────────────────────────────────────── #
    op.create_table(
        "team_form",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_team_id", String(100), nullable=True, index=True),
        sa.Column("internal_team_id", String(), ForeignKey("teams.id"), nullable=True, index=True),
        sa.Column("fixture_id", String(), ForeignKey("matches.id"), nullable=True),
        sa.Column("form_score", Float, nullable=True),
        sa.Column("form_description", Text, nullable=True),
        sa.Column("recent_match_ids", JSON, nullable=True),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("provider_metadata", JSON, default=dict),
    )

    # ── head_to_head ───────────────────────────────────────────────── #
    op.create_table(
        "head_to_head",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("league_id", String(), ForeignKey("leagues.id"), nullable=True),
        sa.Column("team_a_id", String(100), nullable=True, index=True),
        sa.Column("team_b_id", String(100), nullable=True, index=True),
        sa.Column("team_a_internal_id", String(), ForeignKey("teams.id"), nullable=True),
        sa.Column("team_b_internal_id", String(), ForeignKey("teams.id"), nullable=True),
        sa.Column("team_a_wins", Integer, nullable=True),
        sa.Column("team_b_wins", Integer, nullable=True),
        sa.Column("draws", Integer, nullable=True),
        sa.Column("avg_goals_per_game", Float, nullable=True),
        sa.Column("fixture_ids", JSON, nullable=True),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
    )

    # ── players ────────────────────────────────────────────────────── #
    op.create_table(
        "players",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_player_id", String(100), nullable=False),
        sa.Column("team_id", String(), ForeignKey("teams.id"), nullable=True),
        sa.Column("first_name", String(100), nullable=True),
        sa.Column("last_name", String(100), nullable=True),
        sa.Column("full_name", String(255), nullable=False),
        sa.Column("position", String(50), nullable=True),
        sa.Column("date_of_birth", DateTime, nullable=True),
        sa.Column("nationality", String(100), nullable=True),
        sa.Column("height", Integer, nullable=True),
        sa.Column("weight", Integer, nullable=True),
        sa.Column("footed", String(10), nullable=True),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("provider_metadata", JSON, default=dict),
    )

    op.create_table(
        "provider_players",
        sa.Column("id", String(), primary_key=True),
        sa.Column("internal_player_id", String(), ForeignKey("players.id"), nullable=False, index=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_player_id", String(100), nullable=False),
        sa.Column("provider_team_id", String(100), nullable=True),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    # ── injuries & suspensions ─────────────────────────────────────── #
    op.create_table(
        "injuries",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_player_id", String(100), nullable=True),
        sa.Column("provider_team_id", String(100), nullable=True),
        sa.Column("internal_team_id", String(), ForeignKey("teams.id"), nullable=True),
        sa.Column("player_name", String(255), nullable=True),
        sa.Column("position", String(50), nullable=True),
        sa.Column("injury_type", String(100), nullable=True),
        sa.Column("severity", String(50), nullable=True),
        sa.Column("description", Text, nullable=True),
        sa.Column("start_date", DateTime, nullable=True),
        sa.Column("return_date", DateTime, nullable=True),
        sa.Column("is_startingXI_impact", Boolean, default=False, nullable=False),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("provider_metadata", JSON, default=dict),
    )

    op.create_table(
        "suspensions",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_player_id", String(100), nullable=True),
        sa.Column("provider_team_id", String(100), nullable=True),
        sa.Column("internal_team_id", String(), ForeignKey("teams.id"), nullable=True),
        sa.Column("player_name", String(255), nullable=True),
        sa.Column("position", String(50), nullable=True),
        sa.Column("reason", String(255), nullable=True),
        sa.Column("suspension_type", String(100), nullable=True),
        sa.Column("suspended_from", DateTime, nullable=True),
        sa.Column("suspended_until", DateTime, nullable=True),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("provider_metadata", JSON, default=dict),
    )

    # ── lineups ────────────────────────────────────────────────────── #
    op.create_table(
        "predicted_lineups",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_fixture_id", String(100), nullable=False, index=True),
        sa.Column("internal_fixture_id", String(), ForeignKey("matches.id"), nullable=True),
        sa.Column("team_id", String(), ForeignKey("teams.id"), nullable=True),
        sa.Column("team_name", String(255), nullable=True),
        sa.Column("formation", String(50), nullable=True),
        sa.Column("players_json", JSON, default=dict),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
    )

    op.create_table(
        "confirmed_lineups",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_fixture_id", String(100), nullable=False, index=True),
        sa.Column("internal_fixture_id", String(), ForeignKey("matches.id"), nullable=True),
        sa.Column("team_id", String(), ForeignKey("teams.id"), nullable=True),
        sa.Column("team_name", String(255), nullable=True),
        sa.Column("formation", String(50), nullable=True),
        sa.Column("players_json", JSON, default=dict),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
    )

    # ── odds ───────────────────────────────────────────────────────── #
    op.create_table(
        "odds",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("provider_fixture_id", String(100), nullable=False, index=True),
        sa.Column("internal_fixture_id", String(), ForeignKey("matches.id"), nullable=True),
        sa.Column("markets_json", JSON, default=list),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
    )

    # ── web research ───────────────────────────────────────────────── #
    op.create_table(
        "web_sources",
        sa.Column("id", String(), primary_key=True),
        sa.Column("url", Text, nullable=False, unique=True),
        sa.Column("title", String(500), nullable=True),
        sa.Column("publisher", String(255), nullable=True),
        sa.Column("published_at", DateTime, nullable=True),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("source_type", String(50), nullable=True),
        sa.Column("relevance", Float, nullable=True),
    )

    op.create_table(
        "news_items",
        sa.Column("id", String(), primary_key=True),
        sa.Column("match_id", String(), ForeignKey("matches.id"), nullable=True, index=True),
        sa.Column("source_id", String(), ForeignKey("web_sources.id"), nullable=True),
        sa.Column("title", String(500), nullable=False),
        sa.Column("content_summary", Text, nullable=True),
        sa.Column("claims_json", JSON, default=list),
        sa.Column("relevance", Float, nullable=True),
        sa.Column("retrieved_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("provider_metadata", JSON, default=dict),
    )

    # ── predictions & model ────────────────────────────────────────── #
    op.create_table(
        "model_versions",
        sa.Column("id", String(), primary_key=True),
        sa.Column("version", String(100), nullable=False, unique=True),
        sa.Column("model_type", String(100), nullable=False),
        sa.Column("description", Text, nullable=True),
        sa.Column("parameters_json", JSON, default=dict),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("is_active", Boolean, default=False, nullable=False),
    )

    op.create_table(
        "predictions",
        sa.Column("id", String(), primary_key=True),
        sa.Column("match_id", String(), ForeignKey("matches.id"), nullable=False, index=True),
        sa.Column("model_version", String(100), nullable=False, index=True),
        sa.Column("provider_used", String(50), nullable=False),
        sa.Column("generated_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("lambda_home", Float, nullable=True),
        sa.Column("lambda_away", Float, nullable=True),
        sa.Column("home_probability", Float, nullable=True),
        sa.Column("draw_probability", Float, nullable=True),
        sa.Column("away_probability", Float, nullable=True),
        sa.Column("over_2_5_probability", Float, nullable=True),
        sa.Column("under_2_5_probability", Float, nullable=True),
        sa.Column("btts_probability", Float, nullable=True),
        sa.Column("confidence", Float, nullable=True),
        sa.Column("prediction_status", String(50), nullable=False, default="pending"),
        sa.Column("feature_snapshot", JSON, default=dict),
        sa.Column("news_snapshot", JSON, default=dict),
        sa.Column("odds_snapshot", JSON, default=dict),
        sa.Column("ai_explanation", Text, nullable=True),
        sa.Column("ai_evidence_json", JSON, default=list),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    op.create_table(
        "prediction_scorelines",
        sa.Column("id", String(), primary_key=True),
        sa.Column("prediction_id", String(), ForeignKey("predictions.id"), nullable=False, index=True),
        sa.Column("home_goals", Integer, nullable=False),
        sa.Column("away_goals", Integer, nullable=False),
        sa.Column("probability", Float, nullable=False),
        sa.Column("rank", Integer, nullable=False),
        sa.Column("created_at", DateTime, nullable=False, default=sa.func.now()),
    )

    op.create_table(
        "prediction_results",
        sa.Column("id", String(), primary_key=True),
        sa.Column("prediction_id", String(), ForeignKey("predictions.id"), nullable=False, index=True),
        sa.Column("home_score", Integer, nullable=True),
        sa.Column("away_score", Integer, nullable=True),
        sa.Column("exact_score_correct", Boolean, nullable=True),
        sa.Column("top4_hit", Boolean, nullable=True),
        sa.Column("home_win_correct", Boolean, nullable=True),
        sa.Column("draw_correct", Boolean, nullable=True),
        sa.Column("away_win_correct", Boolean, nullable=True),
        sa.Column("over_25_correct", Boolean, nullable=True),
        sa.Column("btts_correct", Boolean, nullable=True),
        sa.Column("evaluated_at", DateTime, nullable=False, default=sa.func.now()),
    )

    op.create_table(
        "model_metrics",
        sa.Column("id", String(), primary_key=True),
        sa.Column("model_version", String(100), nullable=False, index=True),
        sa.Column("league_id", String(), nullable=True),
        sa.Column("season_id", String(), nullable=True),
        sa.Column("metric_name", String(100), nullable=False),
        sa.Column("metric_value", Float, nullable=False),
        sa.Column("computed_at", DateTime, nullable=False, default=sa.func.now()),
    )

    op.create_table(
        "provider_sync_logs",
        sa.Column("id", String(), primary_key=True),
        sa.Column("provider_name", String(50), nullable=False, index=True),
        sa.Column("resource", String(100), nullable=False),
        sa.Column("status", String(50), nullable=False),
        sa.Column("records_fetched", Integer, nullable=True),
        sa.Column("records_stored", Integer, nullable=True),
        sa.Column("error_message", Text, nullable=True),
        sa.Column("started_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("completed_at", DateTime, nullable=True),
    )

    op.create_table(
        "prediction_runs",
        sa.Column("id", String(), primary_key=True),
        sa.Column("model_version", String(100), nullable=False, index=True),
        sa.Column("provider_used", String(50), nullable=False),
        sa.Column("status", String(50), nullable=False),
        sa.Column("matches_processed", Integer, nullable=False, default=0),
        sa.Column("matches_succeeded", Integer, nullable=False, default=0),
        sa.Column("matches_failed", Integer, nullable=False, default=0),
        sa.Column("started_at", DateTime, nullable=False, default=sa.func.now()),
        sa.Column("completed_at", DateTime, nullable=True),
        sa.Column("error_message", Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("prediction_runs")
    op.drop_table("provider_sync_logs")
    op.drop_table("model_metrics")
    op.drop_table("prediction_results")
    op.drop_table("prediction_scorelines")
    op.drop_table("predictions")
    op.drop_table("model_versions")
    op.drop_table("news_items")
    op.drop_table("web_sources")
    op.drop_table("odds")
    op.drop_table("confirmed_lineups")
    op.drop_table("predicted_lineups")
    op.drop_table("suspensions")
    op.drop_table("injuries")
    op.drop_table("provider_players")
    op.drop_table("players")
    op.drop_table("head_to_head")
    op.drop_table("team_form")
    op.drop_table("team_statistics")
    op.drop_table("match_statistics")
    op.drop_table("matches")
    op.drop_table("provider_teams")
    op.drop_table("teams")
    op.drop_table("provider_leagues")
    op.drop_table("seasons")
    op.drop_table("leagues")
    op.drop_table("users")
