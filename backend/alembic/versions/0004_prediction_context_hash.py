"""Add context_hash column to predictions table.

Revision ID: 0004_prediction_context_hash
Revises: 0003_prediction_research
Create Date: 2026-09-22 00:00:00.000000

Adds context_hash column to the predictions table for tracking
prediction context freshness and enabling context-based comparison.
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_prediction_context_hash"
down_revision: str | None = "0003_prediction_research"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("context_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "idx_predictions_context_hash",
        "predictions",
        ["context_hash"],
    )


def downgrade() -> None:
    op.drop_index("idx_predictions_context_hash", table_name="predictions")
    op.drop_column("predictions", "context_hash")
