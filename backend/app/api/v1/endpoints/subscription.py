"""Subscription management endpoints with Flutterwave v4 integration."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.config import get_settings
from core.security import get_current_user, get_current_user_required
from db.database import DBSession, get_db
from models.user import Subscription, SubscriptionStatus, User
from schemas.auth import FlutterwaveInitResponse, FlutterwaveVerifyRequest

router = APIRouter(prefix="/subscription", tags=["subscription"])


FREE_PREDICTION_LIMIT = 2


async def _get_flutterwave_token(settings) -> str:
    """Retrieve an OAuth 2.0 access token from Flutterwave v4."""
    if not settings.flutterwave_client_id or not settings.flutterwave_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flutterwave OAuth credentials are not configured on this server.",
        )

    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.post(
            settings.flutterwave_oauth_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.flutterwave_client_id,
                "client_secret": settings.flutterwave_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not authenticate with Flutterwave.",
        )
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Flutterwave did not return an access token.",
        )
    return token


async def _verify_flutterwave_transaction(charge_id: str, access_token: str) -> dict[str, Any]:
    """Verify a charge via Flutterwave v4 GET /charges/{id}."""
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.get(
            f"{get_settings().flutterwave_api_base_url}/charges/{charge_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not verify the payment with Flutterwave.",
        )
    return response.json().get("data", {})


def _create_subscription_record(
    user: User,
    flutterwave_customer_id: str | None = None,
    flutterwave_subscription_id: str | None = None,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    period_days: int = 30,
) -> Subscription:
    """Helper to create/update a subscription record."""
    now = datetime.now(UTC)
    period_end = (
        now + relativedelta(months=1) if period_days == 30 else now + timedelta(days=period_days)
    )

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
    """Initiate a Flutterwave v4 payment for subscription."""
    settings = get_settings()

    if not settings.flutterwave_client_id or not settings.flutterwave_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flutterwave OAuth credentials are not configured on this server.",
        )
    if not settings.flutterwave_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flutterwave is not configured on this server.",
        )

    access_token = await _get_flutterwave_token(settings)

    from sqlalchemy import select

    async with db as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Check if already subscribed
        if user.has_active_subscription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an active subscription",
            )

        # Create a pending subscription record
        sub = _create_subscription_record(
            user=user,
            status=SubscriptionStatus.INCOMPLETE,
        )
        sub.amount = settings.subscription_price_usd
        session.add(sub)
        await session.commit()
        await session.refresh(sub)

        # Generate a unique reference for the charge
        tx_ref = f"sub_{sub.id}_{int(datetime.now(UTC).timestamp())}_{secrets.token_hex(4)}"
        sub.payment_reference = tx_ref
        await session.commit()

        # Initiate Flutterwave v4 charge
        flutterwave_url = f"{settings.flutterwave_api_base_url}/charges"

        try:
            async with httpx.AsyncClient(timeout=30) as http:
                response = await http.post(
                    flutterwave_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "X-Trace-Id": sub.id,
                    },
                    json={
                        "reference": tx_ref,
                        "amount": str(settings.subscription_price_usd),
                        "currency": "USD",
                        "customer": {
                            "email": user.email,
                        },
                        "payment_options": "card",
                        "meta": {
                            "subscription_id": sub.id,
                            "user_id": user.id,
                            "transaction_type": "subscription_payment",
                        },
                        "redirect_url": f"{settings.frontend_url.rstrip('/')}/subscription/complete",
                    },
                )
                response.raise_for_status()
                data = response.json()
                if data.get("status") != "success":
                    raise RuntimeError(
                        data.get("message") or "Flutterwave did not return a successful response"
                    )
                charge_data = data.get("data", {})
                payment_link = charge_data.get("link") or charge_data.get("payment_options", {}).get("link")

            return FlutterwaveInitResponse(
                link=payment_link,
                subscription_id=sub.id,
                reference=tx_ref,
                message="Payment initiated. Complete your payment to subscribe.",
            )
        except Exception as exc:
            # Rollback: delete the pending subscription
            await session.delete(sub)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to initialize payment: {str(exc)}",
            ) from exc


@router.post("/webhook")
async def flutterwave_webhook(request: Request) -> dict[str, Any]:
    """Handle Flutterwave v4 webhook events."""
    settings = get_settings()

    raw_body = await request.body()

    # Verify HMAC-SHA256 signature using flutterwave-signature header (v4)
    signature = request.headers.get("flutterwave-signature", "")
    if not settings.flutterwave_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flutterwave webhook secret is not configured on this server.",
        )

    expected_signature = hmac.new(
        settings.flutterwave_webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
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

    event_type = body.get("type", "")
    data = body.get("data", {})

    if event_type == "charge.completed":
        charge_id = data.get("id")
        payment_reference = data.get("reference")
        if not charge_id or not payment_reference:
            return {"status": "ignored"}

        async with DBSession() as session:
            from sqlalchemy import select, update

            result = await session.execute(
                select(Subscription).where(Subscription.payment_reference == payment_reference)
            )
            sub = result.scalar_one_or_none()

            access_token = await _get_flutterwave_token(settings)
            verified = await _verify_flutterwave_transaction(
                str(charge_id), access_token
            )
            try:
                amount_matches = (
                    float(verified.get("amount") or 0) >= settings.subscription_price_usd
                )
            except (TypeError, ValueError):
                amount_matches = False
            if (
                verified.get("status") != "succeeded"
                or (verified.get("currency") or "").upper() != "USD"
                or not amount_matches
            ):
                return {"status": "payment_not_verified"}

            if sub is not None:
                if verified.get("reference") != sub.payment_reference:
                    return {"status": "payment_not_verified"}
            else:
                # Renewal charges have a new transaction reference. Match them
                # to the customer using metadata.
                customer_email = (verified.get("customer") or {}).get("email", "")
                if not customer_email:
                    return {"status": "ignored"}
                user_result = await session.execute(
                    select(User).where(
                        User.email == str(customer_email).strip().lower()
                    )
                )
                renewal_user = user_result.scalar_one_or_none()
                if renewal_user is None:
                    return {"status": "ignored"}
                sub_result = await session.execute(
                    select(Subscription)
                    .where(Subscription.user_id == renewal_user.id)
                    .order_by(Subscription.created_at.desc())
                    .limit(1)
                )
                sub = sub_result.scalar_one_or_none()
                if sub is None:
                    return {"status": "ignored"}

            transaction_reference = str(verified.get("id") or charge_id)
            if sub.flutterwave_subscription_id != transaction_reference:
                now = datetime.now(UTC)
                sub.status = SubscriptionStatus.ACTIVE
                current_end = sub.current_period_end
                if current_end is not None and current_end.tzinfo is None:
                    current_end = current_end.replace(tzinfo=UTC)
                period_start = current_end if current_end and current_end > now else now
                sub.current_period_start = period_start
                sub.current_period_end = period_start + relativedelta(months=1)
                sub.flutterwave_subscription_id = transaction_reference
                await session.execute(
                    update(User).where(User.id == sub.user_id).values(is_subscribed=True)
                )
                await session.commit()

    elif event_type == "charge.failed":
        payment_reference = data.get("reference")
        if payment_reference:
            async with DBSession() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Subscription).where(Subscription.payment_reference == payment_reference)
                )
                sub = result.scalar_one_or_none()
                if sub and sub.status == SubscriptionStatus.INCOMPLETE:
                    await session.delete(sub)
                    await session.commit()

    elif event_type == "subscription.cancelled" or event_type == "subscription.expired":
        customer_email = (data.get("customer") or {}).get("email", "")
        if customer_email:
            async with DBSession() as session:
                from sqlalchemy import select, update

                user_result = await session.execute(
                    select(User).where(
                        User.email == str(customer_email).strip().lower()
                    )
                )
                user = user_result.scalar_one_or_none()
                if user:
                    result = await session.execute(
                        select(Subscription)
                        .where(Subscription.user_id == user.id)
                        .order_by(Subscription.created_at.desc())
                        .limit(1)
                    )
                    sub = result.scalar_one_or_none()
                    if sub:
                        sub.status = SubscriptionStatus.CANCELLED
                        await session.execute(
                            update(User).where(User.id == user.id).values(is_subscribed=False)
                        )
                        await session.commit()

    return {"status": "ok"}


@router.post("/verify")
async def verify_subscription_payment(
    payload: FlutterwaveVerifyRequest,
    email: str = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Verify a completed checkout redirect for the signed-in customer."""
    settings = get_settings()
    if not settings.flutterwave_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flutterwave is not configured on this server.",
        )

    access_token = await _get_flutterwave_token(settings)

    async with DBSession() as session:
        from sqlalchemy import select, update

        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        sub_result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.payment_reference == payload.tx_ref,
            )
        )
        sub = sub_result.scalar_one_or_none()
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment reference not found",
            )

        verified = await _verify_flutterwave_transaction(
            payload.transaction_id, access_token
        )
        try:
            amount_matches = float(verified.get("amount") or 0) >= settings.subscription_price_usd
        except (TypeError, ValueError):
            amount_matches = False
        customer_email = str((verified.get("customer") or {}).get("email") or "").strip().lower()
        metadata = verified.get("meta") or {}
        valid = (
            verified.get("status") == "succeeded"
            and verified.get("reference") == sub.payment_reference
            and (verified.get("currency") or "").upper() == "USD"
            and amount_matches
            and str(metadata.get("subscription_id")) == sub.id
            and customer_email == user.email
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flutterwave could not confirm this subscription payment.",
            )

        transaction_reference = str(verified.get("id") or payload.transaction_id)
        if sub.flutterwave_subscription_id != transaction_reference:
            now = datetime.now(UTC)
            sub.status = SubscriptionStatus.ACTIVE
            sub.current_period_start = now
            sub.current_period_end = now + relativedelta(months=1)
            sub.flutterwave_subscription_id = transaction_reference
            await session.execute(
                update(User).where(User.id == user.id).values(is_subscribed=True)
            )
            user.is_subscribed = True
            await session.commit()

        return {"is_subscribed": user.has_active_subscription}


@router.get("/check")
async def check_subscription(
    email: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Quick check if the current user has an active subscription."""
    if email is None:
        return {
            "is_subscribed": False,
            "subscription_price_usd": get_settings().subscription_price_usd,
            "free_predictions_remaining": FREE_PREDICTION_LIMIT,
            "total_free_predictions": FREE_PREDICTION_LIMIT,
        }

    from sqlalchemy import select

    async with DBSession() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        subscription_active = bool(user and user.has_active_subscription)
        if subscription_active:
            return {
                "is_subscribed": True,
                "subscription_price_usd": get_settings().subscription_price_usd,
                "free_predictions_remaining": None,
                "total_free_predictions": FREE_PREDICTION_LIMIT,
            }

        # Check if subscription has expired
        if user and user.subscription:
            if user.subscription.status == SubscriptionStatus.ACTIVE:
                if (
                    user.subscription.current_period_end
                    and user.subscription.current_period_end < datetime.now(UTC)
                ):
                    return {
                        "is_subscribed": False,
                        "free_predictions_remaining": FREE_PREDICTION_LIMIT,
                        "total_free_predictions": FREE_PREDICTION_LIMIT,
                    }

        return {
            "is_subscribed": False,
            "subscription_price_usd": get_settings().subscription_price_usd,
            "free_predictions_remaining": FREE_PREDICTION_LIMIT,
            "total_free_predictions": FREE_PREDICTION_LIMIT,
        }
