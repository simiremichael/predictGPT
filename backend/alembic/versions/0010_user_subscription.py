"""Add subscriptions table and user subscription fields.

Revision ID: 0010_user_subscription
Revises: 0009_prediction_admin_verify
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_user_subscription"
down_revision = "0009_prediction_admin_verify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("flutterwave_customer_id", sa.String(100), nullable=True),
        sa.Column("flutterwave_subscription_id", sa.String(200), unique=True, nullable=True),
        sa.Column("payment_reference", sa.String(200), unique=True, nullable=True),
        sa.Column("status", sa.String(20), default="incomplete", nullable=False),
        sa.Column("current_period_end", sa.DateTime, nullable=True),
        sa.Column("current_period_start", sa.DateTime, nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, default=False, nullable=False),
        sa.Column("amount", sa.Float, default=5.0, nullable=False),
        sa.Column("currency", sa.String(3), default="usd", nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.add_column("users", sa.Column("is_subscribed", sa.Boolean, default=False, nullable=False, server_default="false"))
    op.add_column("users", sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()))


def downgrade() -> None:
    op.drop_column("users", "updated_at")
    op.drop_column("users", "is_subscribed")
    op.drop_table("subscriptions")
