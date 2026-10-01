"""Add unique constraint to provider_teams to stop duplicate mapping rows.

``_save_teams`` used ``on_conflict_do_nothing()`` against a table whose only
unique column was the surrogate UUID primary key, so the conflict clause could
never fire and every sync appended a fresh ``provider_teams`` row per team.

The index is declared ``NULLS NOT DISTINCT`` because an unfiltered
``GET /teams`` stores NULL for both ``provider_league_id`` and ``season_id``;
under the default distinct-NULLs semantics those rows would still duplicate.

Revision ID: 0008_provider_team_unique
Revises: 0007_provider_team_season_id
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_provider_team_unique"
down_revision = "0007_provider_team_season_id"
branch_labels = None
depends_on = None

_COLUMNS = (
    "internal_team_id",
    "provider_name",
    "provider_league_id",
    "season_id",
)


def upgrade() -> None:
    conn = op.get_bind()

    # Drop any duplicate mappings that earlier syncs created, keeping the
    # oldest row of each group so a re-sync does not change the mapping.
    conn.execute(
        sa.text(
            """
            DELETE FROM provider_teams a
            USING provider_teams b
            WHERE a.ctid < b.ctid
              AND a.internal_team_id IS NOT DISTINCT FROM b.internal_team_id
              AND a.provider_name IS NOT DISTINCT FROM b.provider_name
              AND a.provider_league_id IS NOT DISTINCT FROM b.provider_league_id
              AND a.season_id IS NOT DISTINCT FROM b.season_id
            """
        )
    )

    op.create_index(
        "uq_provider_teams_identity",
        "provider_teams",
        list(_COLUMNS),
        unique=True,
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_index("uq_provider_teams_identity", table_name="provider_teams")
