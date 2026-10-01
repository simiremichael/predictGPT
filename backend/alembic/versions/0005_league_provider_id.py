"""Add provider_league_id column to leagues table.

Revision ID: 0005_league_provider_id
Revises: 0004_prediction_context_hash
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0005_league_provider_id"
down_revision = "0004_prediction_context_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("leagues")]
    if "provider_league_id" not in columns:
        op.add_column(
            "leagues",
            sa.Column("provider_league_id", sa.String(100), nullable=True),
        )
        op.execute(
            "UPDATE leagues SET provider_league_id = '0' WHERE provider_league_id IS NULL"
        )
        op.alter_column(
            "leagues",
            "provider_league_id",
            nullable=False,
        )
        op.create_index("ix_leagues_provider_league_id", "leagues", ["provider_league_id"])


def downgrade() -> None:
    op.drop_index("ix_leagues_provider_league_id", table_name="leagues")
    op.drop_column("leagues", "provider_league_id")
