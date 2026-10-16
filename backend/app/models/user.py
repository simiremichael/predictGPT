"""SQLAlchemy models for user authentication and subscriptions."""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from models.match import _uuid


class SubscriptionStatus(StrEnum):
    """Subscription lifecycle states."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELLED = "cancelled"
    INCOMPLETE = "incomplete"
    EXPIRED = "expired"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_subscribed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
        onupdate=datetime.utcnow,
    )

    subscription: Mapped[Subscription | None] = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r}>"

    @property
    def has_active_subscription(self) -> bool:
        if not self.is_subscribed:
            return False
        try:
            subscription = self.subscription
        except Exception:
            return False
        if subscription is None:
            return False
        if subscription.status != SubscriptionStatus.ACTIVE:
            return False
        if subscription.current_period_end is None:
            return True
        period_end = subscription.current_period_end
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=UTC)
        return period_end > datetime.now(UTC)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    flutterwave_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    flutterwave_subscription_id: Mapped[str | None] = mapped_column(
        String(200), unique=True, nullable=True
    )
    payment_reference: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, native_enum=False, length=20),
        default=SubscriptionStatus.INCOMPLETE,
        nullable=False,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
        onupdate=datetime.utcnow,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="subscription",
        foreign_keys=[user_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Subscription id={self.id!r} user_id={self.user_id!r} status={self.status!r}>"
