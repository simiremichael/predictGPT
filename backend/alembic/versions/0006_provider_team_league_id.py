"""Add provider_league_id column to provider_teams table.

Revision ID: 0006_provider_team_league_id
Revises: 0005_league_provider_id
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_provider_team_league_id"
down_revision = "0005_league_provider_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("provider_teams")]
    if "provider_league_id" not in columns:
        op.add_column(
            "provider_teams",
            sa.Column("provider_league_id", sa.String(100), nullable=True),
        )
        op.create_index(
            "ix_provider_teams_provider_league_id", "provider_teams", ["provider_league_id"]
        )


def downgrade() -> None:
    op.drop_index("ix_provider_teams_provider_league_id", table_name="provider_teams")
    op.drop_column("provider_teams", "provider_league_id")
