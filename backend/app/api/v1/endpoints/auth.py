"""Authentication endpoints: register, login, me."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.config import get_settings
from core.security import (
    create_access_token,
    get_current_user,
    get_current_user_required,
    hash_password,
    verify_password,
)
from db.database import DBSession, get_db
from models.user import PasswordResetCode, User
from schemas.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    SubscriptionStatusResponse,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _reset_code_digest(code: str) -> str:
    return hashlib.sha256(f"{get_settings().secret_key}:{code}".encode()).hexdigest()


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest) -> dict[str, str]:
    """Send a short-lived verification code without disclosing account existence."""
    settings = get_settings()
    if not settings.gmail_username or not settings.gmail_app_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email is not configured on this server. Set Gmail SMTP credentials.",
        )

    normalized_email = str(payload.email).strip().lower()
    from sqlalchemy import delete, select

    async with DBSession() as session:
        result = await session.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()
        if user is not None:
            recent_result = await session.execute(
                select(PasswordResetCode).where(
                    PasswordResetCode.user_id == user.id,
                    PasswordResetCode.created_at >= datetime.now(UTC) - timedelta(minutes=1),
                ).limit(1)
            )
            if recent_result.scalar_one_or_none() is None:
                await session.execute(
                    delete(PasswordResetCode).where(PasswordResetCode.user_id == user.id)
                )
                code = f"{secrets.randbelow(1_000_000):06d}"
                session.add(PasswordResetCode(
                    user_id=user.id,
                    code_digest=_reset_code_digest(code),
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                ))
                await session.commit()
                try:
                    from services.email import send_email

                    await send_email(
                        user.email,
                        "Your password reset code",
                        f"Your password reset code is {code}. It expires in 10 minutes. "
                        "If you did not request this, you can ignore this email.",
                    )
                except Exception as exc:
                    await session.execute(
                        delete(PasswordResetCode).where(PasswordResetCode.user_id == user.id)
                    )
                    await session.commit()
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Could not send the password reset email.",
                    ) from exc

    return {"message": "If an account exists for that email, a reset code has been sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest) -> dict[str, str]:
    """Validate a one-time email code and update the account password."""
    normalized_email = str(payload.email).strip().lower()
    from sqlalchemy import delete, select

    async with DBSession() as session:
        result = await session.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=400, detail="Invalid or expired reset code.")
        code_result = await session.execute(
            select(PasswordResetCode)
            .where(PasswordResetCode.user_id == user.id, PasswordResetCode.used_at.is_(None))
            .order_by(PasswordResetCode.created_at.desc())
            .limit(1)
        )
        reset_code = code_result.scalar_one_or_none()
        expires_at = reset_code.expires_at if reset_code else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if reset_code is None or expires_at <= datetime.now(UTC) or reset_code.attempts >= 5:
            raise HTTPException(status_code=400, detail="Invalid or expired reset code.")
        if not secrets.compare_digest(reset_code.code_digest, _reset_code_digest(payload.code)):
            reset_code.attempts += 1
            await session.commit()
            raise HTTPException(status_code=400, detail="Invalid or expired reset code.")

        user.hashed_password = hash_password(payload.new_password)
        await session.execute(delete(PasswordResetCode).where(PasswordResetCode.user_id == user.id))
        await session.commit()

    return {"message": "Password has been reset. You can now log in."}


@router.post("/register", response_model=TokenResponse)
async def register(
    payload: AuthRegisterRequest,
    request: Request,
    db=Depends(get_db),
) -> TokenResponse:
    """Register a new user account and return a JWT token."""
    settings = get_settings()
    normalized_email = str(payload.email).strip().lower()
    from sqlalchemy import select

    async with db as session:
        existing = await session.execute(
            select(User).where(User.email == normalized_email)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        country = (payload.country or "").strip().upper()
        if country == "OTHER" or len(country) != 2 or not country.isalpha():
            country = None

        user = User(
            email=normalized_email,
            hashed_password=hash_password(payload.password),
            country=country,
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
            user=UserResponse.model_validate(user).model_copy(
                update={"is_subscribed": user.has_active_subscription}
            ),
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: AuthLoginRequest,
    db=Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return a JWT token."""
    settings = get_settings()
    normalized_email = str(payload.email).strip().lower()
    from sqlalchemy import select

    async with db as session:
        result = await session.execute(
            select(User).where(User.email == normalized_email)
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
            user=UserResponse.model_validate(user).model_copy(
                update={"is_subscribed": user.has_active_subscription}
            ),
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

    async with DBSession() as session:
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

        return UserResponse.model_validate(user).model_copy(
            update={"is_subscribed": user.has_active_subscription}
        )


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

        user_resp = UserResponse.model_validate(user).model_copy(
            update={"is_subscribed": user.has_active_subscription}
        )

        sub_resp = None
        renewal_available = False
        if user.subscription:
            period_start = user.subscription.current_period_start
            period_end = user.subscription.current_period_end
            now = datetime.now(UTC)
            if period_start is not None and period_start.tzinfo is None:
                period_start = period_start.replace(tzinfo=UTC)
            if period_end is not None and period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=UTC)
            if (
                user.subscription.status.value == "active"
                and period_start is not None
                and period_end is not None
                and period_end <= now
            ):
                from models.user import SubscriptionStatus

                user.subscription.status = SubscriptionStatus.EXPIRED
                user.is_subscribed = False
                await session.commit()
            renewal_available = bool(
                user.has_active_subscription
                and period_start is not None
                and period_end is not None
                and now >= period_start + timedelta(days=25)
                and now < period_end
            )
            sub_resp = {
                "id": user.subscription.id,
                "status": user.subscription.status.value,
                "current_period_start": period_start.isoformat() if period_start else None,
                "current_period_end": (
                    period_end.isoformat()
                    if period_end
                    else None
                ),
                "amount": user.subscription.amount,
                "currency": user.subscription.currency,
            }

        return SubscriptionStatusResponse(
            is_subscribed=user.has_active_subscription,
            subscription_price_usd=get_settings().subscription_price_usd,
            subscription_price_ngn=get_settings().subscription_price_ngn,
            subscription=sub_resp,
            user=user_resp,
            renewal_available=renewal_available,
        )
