"""Subscription management endpoints with Flutterwave integration."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.config import get_settings
from core.security import get_current_user, get_current_user_required
from db.database import get_db
from models.user import Subscription, SubscriptionStatus, User
from schemas.auth import FlutterwaveInitResponse

router = APIRouter(prefix="/subscription", tags=["subscription"])


FREE_PREDICTION_LIMIT = 2


def _create_subscription_record(
    user: User,
    flutterwave_customer_id: str | None = None,
    flutterwave_subscription_id: str | None = None,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    period_days: int = 30,
) -> Subscription:
    """Helper to create/update a subscription record."""
    now = datetime.now(UTC)
    period_end = now + timedelta(days=period_days)

    sub = Subscription(
        user_id=user.id,
        flutterwave_customer_id=flutterwave_customer_id,
        flutterwave_subscription_id=flutterwave_subscription_id,
        status=status,
        current_period_start=now,
        current_period_end=period_end,
        amount=5.0,
        currency="usd",
    )
    return sub


@router.post("/initiate", response_model=FlutterwaveInitResponse)
async def initiate_subscription(
    email: str = Depends(get_current_user_required),
    db=Depends(get_db),
) -> FlutterwaveInitResponse:
    """Initiate a Flutterwave payment for subscription."""
    settings = get_settings()

    if not settings.flutterwave_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flutterwave is not configured on this server.",
        )

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

        # Check if already subscribed
        if user.is_subscribed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an active subscription",
            )

        # Create a pending subscription record
        sub = _create_subscription_record(
            user=user,
            status=SubscriptionStatus.INCOMPLETE,
        )
        session.add(sub)
        await session.commit()
        await session.refresh(sub)

        user.subscription_id = sub.id
        await session.commit()
        await session.refresh(user)

        # Initiate Flutterwave checkout
        tx_ref = f"sub_{user.id}_{int(datetime.now(UTC).timestamp())}"
        flutterwave_url = "https://api.flutterwave.com/v3/payments"

        try:
            async with httpx.AsyncClient(timeout=30) as http:
                response = await http.post(
                    flutterwave_url,
                    headers={
                        "Authorization": f"Bearer {settings.flutterwave_secret_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "tx_ref": tx_ref,
                        "amount": settings.subscription_price_usd,
                        "currency": "USD",
                        "customer": {
                            "email": user.email,
                            "user_id": user.id,
                            "subscription_id": sub.id,
                        },
                        "redirect_url": "https://predictgpt.onrender.com/subscription/complete",
                        "meta": {
                            "subscription_id": sub.id,
                            "user_id": user.id,
                            "transaction_type": "subscription_payment",
                        },
                        "customizations": {
                            "title": "Football AI Subscription",
                            "description": f"Monthly subscription (${settings.subscription_price_usd}/month)",
                            "logo": "https://predictgpt.onrender.com/favicon.ico",
                        },
                    },
                )
                data = response.json()
                payment_link = data.get("data", {}).get("link")

            return FlutterwaveInitResponse(
                link=payment_link,
                subscription_id=sub.id,
                reference=tx_ref,
                message="Payment initiated. Complete your payment to subscribe.",
            )
        except Exception as exc:
            # Rollback: delete the pending subscription
            await session.delete(sub)
            user.subscription_id = None
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to initialize payment: {str(exc)}",
            ) from exc


@router.post("/webhook")
async def flutterwave_webhook(
    request: Request,
) -> dict[str, Any]:
    """Handle Flutterwave webhook events."""
    settings = get_settings()

    if settings.flutterwave_webhook_secret:
        signature = request.headers.get("verif-hash", "")
        if signature != settings.flutterwave_webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        ) from None

    event_type = body.get("event", "")
    data = body.get("data", {})

    if event_type in ("charge.succeeded", "payment.completed"):
        meta = data.get("meta", {})
        sub_id = meta.get("subscription_id")
        if not sub_id:
            sub_id = data.get("customer", {}).get("user_id") if data else None

        if sub_id:
            async with get_db() as session:
                from sqlalchemy import select, update

                result = await session.execute(
                    select(Subscription).where(Subscription.id == sub_id)
                )
                sub = result.scalar_one_or_none()
                if sub:
                    sub.status = SubscriptionStatus.ACTIVE
                    sub.current_period_start = datetime.now(UTC)
                    sub.current_period_end = datetime.now(UTC) + timedelta(days=30)
                    sub.flutterwave_subscription_id = data.get("id", "") or data.get("flw_ref", "")

                    # Mark user as subscribed
                    await session.execute(
                        update(User)
                        .where(User.id == sub.user_id)
                        .values(is_subscribed=True)
                    )
                    await session.commit()

    elif event_type in ("subscription.cancelled", "payment.failed"):
        meta = data.get("meta", {})
        sub_id = meta.get("subscription_id")
        if not sub_id:
            sub_id = data.get("customer", {}).get("user_id") if data else None

        if sub_id:
            async with get_db() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Subscription).where(Subscription.id == sub_id)
                )
                sub = result.scalar_one_or_none()
                if sub:
                    sub.status = SubscriptionStatus.CANCELLED
                    await session.commit()

    return {"status": "ok"}


@router.get("/check")
async def check_subscription(
    email: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Quick check if the current user has an active subscription."""
    if email is None:
        return {
            "is_subscribed": False,
            "free_predictions_remaining": FREE_PREDICTION_LIMIT,
            "total_free_predictions": FREE_PREDICTION_LIMIT,
        }

    from sqlalchemy import select

    async with get_db() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        if user and user.is_subscribed:
            return {
                "is_subscribed": True,
                "free_predictions_remaining": None,
                "total_free_predictions": FREE_PREDICTION_LIMIT,
            }

        # Check if subscription has expired
        if user and user.subscription:
            if user.subscription.status == SubscriptionStatus.ACTIVE:
                if user.subscription.current_period_end and user.subscription.current_period_end < datetime.now(UTC):
                    return {
                        "is_subscribed": False,
                        "free_predictions_remaining": FREE_PREDICTION_LIMIT,
                        "total_free_predictions": FREE_PREDICTION_LIMIT,
                    }

        return {
            "is_subscribed": False,
            "free_predictions_remaining": FREE_PREDICTION_LIMIT,
            "total_free_predictions": FREE_PREDICTION_LIMIT,
        }
