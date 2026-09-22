"""Add research fields to predictions table.

Revision ID: 0003_prediction_research
Revises: 0002_research
Create Date: 2024-02-02 00:00:00.000000

Adds prediction_version, research_run_id, ai_adjustment_json, and
source_ids columns to the predictions table.
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_prediction_research"
down_revision: str | None = "0002_research"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("prediction_version", sa.String(100), nullable=False, server_default="v1.0.0"))
    op.add_column("predictions", sa.Column("research_run_id", sa.String(), sa.ForeignKey("research_runs.id"), nullable=True))
    op.add_column("predictions", sa.Column("ai_adjustment_json", sa.JSON(), nullable=True))
    op.add_column("predictions", sa.Column("source_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.create_index("idx_predictions_version", "predictions", ["prediction_version"])
    op.create_index("idx_predictions_research_run", "predictions", ["research_run_id"])


def downgrade() -> None:
    op.drop_index("idx_predictions_research_run", table_name="predictions")
    op.drop_index("idx_predictions_version", table_name="predictions")
    op.drop_column("predictions", "source_ids")
    op.drop_column("predictions", "ai_adjustment_json")
    op.drop_column("predictions", "research_run_id")
    op.drop_column("predictions", "prediction_version")
