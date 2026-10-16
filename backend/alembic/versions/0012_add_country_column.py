"""Add country column to users table and NGN pricing support.

Revision ID: 0012_add_country_column
Revises: 0011_add_payment_reference
Create Date: 2026-10-17

This migration adds the country column to the users table for
region-based subscription pricing (NGN for Nigeria, USD for others).
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_add_country_column"
down_revision = "0011_add_payment_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("country", sa.String(2), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "country")
