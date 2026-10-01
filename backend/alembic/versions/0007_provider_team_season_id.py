"""Add season_id column to provider_teams table.

Revision ID: 0007_provider_team_season_id
Revises: 0006_provider_team_league_id
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_provider_team_season_id"
down_revision = "0006_provider_team_league_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("provider_teams")]
    if "season_id" not in columns:
        op.add_column(
            "provider_teams",
            sa.Column("season_id", sa.String(100), nullable=True),
        )
        op.create_index(
            "ix_provider_teams_season_id", "provider_teams", ["season_id"]
        )


def downgrade() -> None:
    op.drop_index("ix_provider_teams_season_id", table_name="provider_teams")
    op.drop_column("provider_teams", "season_id")
