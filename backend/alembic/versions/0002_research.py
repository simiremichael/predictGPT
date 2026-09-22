"""Create web research and AI evidence tables.

Revision ID: 0002_research
Revises: 0001_initial
Create Date: 2024-02-01 00:00:00.000000

Creates tables for:
- research_runs: tracks when research was performed for a match
- research_evidence: structured evidence extracted from web sources
- evidence_conflicts: conflicting claims from different sources
- web_sources_extended: detailed web source metadata with content and scoring
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_research"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = "research"
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── research_runs ──────────────────────────────────────────────── #
    op.create_table(
        "research_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("match_id", sa.String(), sa.ForeignKey("matches.id"), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=False, default=0),
        sa.Column("query_count", sa.Integer(), nullable=False, default=0),
        sa.Column("status", sa.String(50), nullable=False, default="running"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cutoff_datetime", sa.DateTime(), nullable=True),
        sa.Column("data_quality", sa.Float(), nullable=True),
    )
    op.create_index(
        "idx_research_runs_match_cutoff",
        "research_runs",
        ["match_id", "cutoff_datetime"],
    )

    # ── research_evidence ───────────────────────────────────────────── #
    op.create_table(
        "research_evidence",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("match_id", sa.String(), sa.ForeignKey("matches.id"), nullable=True, index=True),
        sa.Column("team_id", sa.String(), sa.ForeignKey("teams.id"), nullable=True, index=True),
        sa.Column("research_run_id", sa.String(), sa.ForeignKey("research_runs.id"), nullable=True, index=True),
        sa.Column("evidence_type", sa.String(50), nullable=False, index=True),
        sa.Column("subject", sa.String(255), nullable=False, index=True),
        sa.Column("claim", sa.Text(), nullable=True),
        sa.Column("evidence_status", sa.String(20), nullable=False, default="unknown"),
        sa.Column("confidence", sa.Float(), nullable=False, default=0.0),
        sa.Column("source_ids", sa.JSON(), default=list),
        sa.Column("evidence_data", sa.JSON(), default=dict),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=sa.func.now()),
    )
    op.create_index(
        "idx_research_evidence_match_type",
        "research_evidence",
        ["match_id", "evidence_type"],
    )
    op.create_index(
        "idx_research_evidence_subject",
        "research_evidence",
        ["subject"],
    )

    # ── evidence_conflicts ──────────────────────────────────────────── #
    op.create_table(
        "evidence_conflicts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("match_id", sa.String(), sa.ForeignKey("matches.id"), nullable=True, index=True),
        sa.Column("research_run_id", sa.String(), sa.ForeignKey("research_runs.id"), nullable=True, index=True),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("claim_a", sa.Text(), nullable=False),
        sa.Column("claim_b", sa.Text(), nullable=False),
        sa.Column("source_a_id", sa.String(255), nullable=False),
        sa.Column("source_b_id", sa.String(255), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False, default=sa.func.now()),
    )
    op.create_index(
        "idx_evidence_conflicts_match",
        "evidence_conflicts",
        ["match_id"],
    )

    # ── web_sources_extended ───────────────────────────────────────── #
    op.create_table(
        "web_sources_extended",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True, index=True),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_source", sa.String(50), nullable=False, default="search_result_snippet"),
        sa.Column("credibility_score", sa.Float(), nullable=False, default=0.5),
        sa.Column("freshness_score", sa.Float(), nullable=False, default=0.5),
        sa.Column("match_id", sa.String(), sa.ForeignKey("matches.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=sa.func.now()),
    )
    op.create_index(
        "idx_web_sources_extended_match",
        "web_sources_extended",
        ["match_id"],
    )
    op.create_index(
        "idx_web_sources_extended_type_score",
        "web_sources_extended",
        ["source_type", "credibility_score"],
    )


def downgrade() -> None:
    op.drop_index("idx_web_sources_extended_type_score", table_name="web_sources_extended")
    op.drop_index("idx_web_sources_extended_match", table_name="web_sources_extended")
    op.drop_table("web_sources_extended")
    op.drop_index("idx_evidence_conflicts_match", table_name="evidence_conflicts")
    op.drop_table("evidence_conflicts")
    op.drop_index("idx_research_evidence_subject", table_name="research_evidence")
    op.drop_index("idx_research_evidence_match_type", table_name="research_evidence")
    op.drop_table("research_evidence")
    op.drop_index("idx_research_runs_match_cutoff", table_name="research_runs")
    op.drop_table("research_runs")
