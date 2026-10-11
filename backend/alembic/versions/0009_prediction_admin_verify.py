"""Add admin verification columns to predictions.

Adds ``admin_verify_gg``, ``admin_verify_win`` and ``admin_verify_over_2_5``
columns so the admin can mark market predictions as correct / incorrect
from the admin UI.

Revision ID: 0009_prediction_admin_verify
Revises: 0008_provider_team_unique
Create Date: 2026-10-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_prediction_admin_verify"
down_revision = "0008_provider_team_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("admin_verify_gg", sa.Boolean(), nullable=True))
    op.add_column("predictions", sa.Column("admin_verify_win", sa.Boolean(), nullable=True))
    op.add_column("predictions", sa.Column("admin_verify_over_2_5", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("predictions", "admin_verify_over_2_5")
    op.drop_column("predictions", "admin_verify_win")
    op.drop_column("predictions", "admin_verify_gg")
