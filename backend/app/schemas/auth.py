"""Authentication and subscription request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class AuthRegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class AuthLoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Response containing the JWT access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserResponse(BaseModel):
    """User data returned in API responses."""

    id: str
    email: str
    is_active: bool
    is_subscribed: bool
    created_at: str | None = None

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    """Subscription data returned in API responses."""

    id: str
    status: str
    current_period_end: str | None = None
    amount: float
    currency: str

    model_config = {"from_attributes": True}


class FlutterwaveInitResponse(BaseModel):
    """Response for Flutterwave payment initialization."""

    link: str | None = None
    message: str | None = None
    subscription_id: str | None = None
    reference: str | None = None


class SubscriptionStatusResponse(BaseModel):
    """Response for subscription status check."""

    is_subscribed: bool
    subscription: SubscriptionResponse | None = None
    user: UserResponse


# Register forward refs
TokenResponse.model_rebuild()
