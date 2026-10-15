"""Authentication endpoints: register, login, me."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from core.config import get_settings
from core.security import (
    create_access_token,
    get_current_user,
    get_current_user_required,
    hash_password,
    verify_password,
)
from db.database import get_db
from models.user import User
from schemas.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    SubscriptionStatusResponse,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(
    payload: AuthRegisterRequest,
    db=Depends(get_db),
) -> TokenResponse:
    """Register a new user account and return a JWT token."""
    settings = get_settings()
    from sqlalchemy import select

    async with db as session:
        existing = await session.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        user = User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        access_token = create_access_token(
            payload.email,
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )
        return TokenResponse(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: AuthLoginRequest,
    db=Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return a JWT token."""
    settings = get_settings()
    from sqlalchemy import select

    async with db as session:
        result = await session.execute(
            select(User).where(User.email == payload.email)
        )
        user = result.scalar_one_or_none()

        if user is None or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )

        access_token = create_access_token(
            user.email,
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )
        return TokenResponse(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    email: str | None = Depends(get_current_user),
) -> UserResponse:
    """Get the current authenticated user's info."""
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with get_db() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return UserResponse.model_validate(user)


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    email: str = Depends(get_current_user_required),
    db=Depends(get_db),
) -> SubscriptionStatusResponse:
    """Get the current user's subscription status."""
    from sqlalchemy import select

    async with db as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        user_resp = UserResponse.model_validate(user)

        sub_resp = None
        if user.subscription:
            sub_resp = {
                "id": user.subscription.id,
                "status": user.subscription.status.value,
                "current_period_end": (
                    user.subscription.current_period_end.isoformat()
                    if user.subscription.current_period_end
                    else None
                ),
                "amount": user.subscription.amount,
                "currency": user.subscription.currency,
            }

        return SubscriptionStatusResponse(
            is_subscribed=user.is_subscribed,
            subscription=sub_resp,
            user=user_resp,
        )
