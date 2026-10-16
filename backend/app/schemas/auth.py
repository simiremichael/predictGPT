"""Authentication and subscription request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class AuthRegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    country: str | None = Field(default=None, max_length=2, description="ISO 3166-1 alpha-2 country code")

    @field_validator("password")
    @classmethod
    def validate_bcrypt_password_length(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        return password


class AuthLoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str = Field(..., min_length=1)

    @field_validator("password")
    @classmethod
    def validate_bcrypt_password_length(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        return password


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
    is_superuser: bool
    country: str | None = None
    created_at: datetime | None = None

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


class FlutterwaveVerifyRequest(BaseModel):
    transaction_id: str
    tx_ref: str


class SubscriptionStatusResponse(BaseModel):
    """Response for subscription status check."""

    is_subscribed: bool
    subscription_price_usd: float = 5.0
    subscription: SubscriptionResponse | None = None
    user: UserResponse


# Register forward refs
TokenResponse.model_rebuild()
