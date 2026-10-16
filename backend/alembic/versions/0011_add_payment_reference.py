"""Add payment_reference column to subscriptions table.

Revision ID: 0011_add_payment_reference
Revises: 0010_user_subscription
Create Date: 2026-10-16

This migration adds the payment_reference column to the subscriptions table
for databases created before the column was included in the initial schema.
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_add_payment_reference"
down_revision = "0010_user_subscription"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("payment_reference", sa.String(200), nullable=True),
    )
    op.create_index(
        "ix_subscriptions_payment_reference",
        "subscriptions",
        ["payment_reference"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_subscriptions_payment_reference", table_name="subscriptions")
    op.drop_column("subscriptions", "payment_reference")
