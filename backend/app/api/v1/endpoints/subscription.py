"""Subscription management endpoints with Flutterwave integration."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.config import get_settings
from core.security import get_current_user, get_current_user_required
from db.database import DBSession, get_db
from models.user import Subscription, SubscriptionStatus, User
from schemas.auth import FlutterwaveInitResponse, FlutterwaveVerifyRequest

router = APIRouter(prefix="/subscription", tags=["subscription"])


FREE_PREDICTION_LIMIT = 2


async def _get_flutterwave_token(settings) -> str:
    """Return the Flutterwave secret key for v3 API Bearer authentication."""
    if not settings.flutterwave_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flutterwave secret key is not configured on this server.",
        )
    return settings.flutterwave_secret_key


async def _verify_flutterwave_transaction(charge_id: str, access_token: str) -> dict[str, Any]:
    """Verify a transaction via Flutterwave v3 GET /transactions/{id}/verify."""
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.get(
            f"{get_settings().flutterwave_api_base_url}/transactions/{charge_id}/verify",
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
) -> Subscription:
    """Helper to create/update a subscription record."""
    now = datetime.now(UTC)
    period_end = now + timedelta(days=30)

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

        sub = user.subscription
        now = datetime.now(UTC)
        period_start = sub.current_period_start if sub else None
        period_end = sub.current_period_end if sub else None
        if period_start is not None and period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=UTC)
        if period_end is not None and period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=UTC)
        renewal_open = bool(
            user.has_active_subscription
            and period_start is not None
            and period_end is not None
            and now >= period_start + timedelta(days=25)
        )
        if user.has_active_subscription and not renewal_open:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Renewal is available during the final five days of your subscription.",
            )

        currency, amount = _get_currency_for_user(user, settings)
        if sub is None:
            sub = _create_subscription_record(
                user=user,
                status=SubscriptionStatus.INCOMPLETE,
            )
            sub.amount = amount
            sub.currency = currency.lower()
            session.add(sub)
            await session.commit()
            await session.refresh(sub)
        else:
            # Reuse the user's single subscription row for renewals and restarts.
            sub.amount = amount
            sub.currency = currency.lower()
            await session.commit()

        # Generate a unique reference for the transaction
        tx_ref = f"sub_{sub.id}_{int(now.timestamp())}_{secrets.token_hex(4)}"
        sub.payment_reference = tx_ref
        await session.commit()

        # Initiate Flutterwave Standard API payment
        flutterwave_url = f"{settings.flutterwave_api_base_url}/payments"

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
                        "tx_ref": tx_ref,
                        "amount": amount,
                        "currency": currency,
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
                payment_link = charge_data.get("link") or charge_data.get(
                    "payment_options", {}
                ).get("link")

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
    """Handle Flutterwave webhook events."""
    settings = get_settings()

    raw_body = await request.body()

    # Verify HMAC-SHA256 signature (verif-hash for v3, flutterwave-signature for v4)
    signature = request.headers.get("verif-hash") or request.headers.get(
        "flutterwave-signature", ""
    )
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

    event_type = body.get("event") or body.get("type", "")
    data = body.get("data", {})

    if event_type == "charge.completed":
        charge_id = data.get("id")
        payment_reference = data.get("reference") or data.get("tx_ref")
        if not charge_id or not payment_reference:
            return {"status": "ignored"}

        async with DBSession() as session:
            from sqlalchemy import select, update

            result = await session.execute(
                select(Subscription).where(Subscription.payment_reference == payment_reference)
            )
            sub = result.scalar_one_or_none()

            access_token = await _get_flutterwave_token(settings)
            verified = await _verify_flutterwave_transaction(str(charge_id), access_token)

            # Load the user to determine expected currency/price
            if sub is not None:
                _user_result = await session.execute(
                    select(User).where(User.id == sub.user_id)
                )
                _user = _user_result.scalar_one()
            else:
                # Renewal charges have a new transaction reference. Match them
                # to the customer using metadata.
                customer_email = (verified.get("customer") or {}).get("email", "")
                if not customer_email:
                    return {"status": "ignored"}
                user_result = await session.execute(
                    select(User).where(User.email == str(customer_email).strip().lower())
                )
                renewal_user = user_result.scalar_one_or_none()
                if renewal_user is None:
                    return {"status": "ignored"}
                _user = renewal_user

            expected_currency, expected_amount = _get_currency_for_user(_user, settings)
            try:
                amount_matches = (
                    float(verified.get("amount") or 0) >= expected_amount
                )
            except (TypeError, ValueError):
                amount_matches = False
            if (
                verified.get("status") not in ("successful", "succeeded")
                or (verified.get("currency") or "").upper() != expected_currency.upper()
                or not amount_matches
            ):
                return {"status": "payment_not_verified"}

            if sub is not None:
                verified_ref = verified.get("tx_ref") or verified.get("reference")
                if verified_ref != sub.payment_reference:
                    return {"status": "payment_not_verified"}
            elif renewal_user is not None:
                # Find or create subscription for renewal
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
                was_active = sub.status == SubscriptionStatus.ACTIVE
                sub.status = SubscriptionStatus.ACTIVE
                current_end = sub.current_period_end
                if current_end is not None and current_end.tzinfo is None:
                    current_end = current_end.replace(tzinfo=UTC)
                current_start = sub.current_period_start
                if current_start is not None and current_start.tzinfo is None:
                    current_start = current_start.replace(tzinfo=UTC)
                allow_early_renewal = bool(
                    was_active
                    and current_start is not None
                    and now >= current_start + timedelta(days=25)
                )
                period_start = (
                    current_end
                    if current_end and current_end > now and allow_early_renewal
                    else now
                )
                sub.current_period_start = period_start
                sub.current_period_end = period_start + timedelta(days=30)
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
                    select(User).where(User.email == str(customer_email).strip().lower())
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

        verified = await _verify_flutterwave_transaction(payload.transaction_id, access_token)
        expected_currency, expected_amount = _get_currency_for_user(user, settings)
        try:
            amount_matches = float(verified.get("amount") or 0) >= expected_amount
        except (TypeError, ValueError):
            amount_matches = False
        customer_email = str((verified.get("customer") or {}).get("email") or "").strip().lower()
        metadata = verified.get("meta") or {}
        valid = (
            verified.get("status") in ("successful", "succeeded")
            and (verified.get("tx_ref") or verified.get("reference")) == sub.payment_reference
            and (verified.get("currency") or "").upper() == expected_currency.upper()
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
        # Always update the subscription when payment is verified, regardless of
        # whether the webhook already set the reference (handles race conditions)
        now = datetime.now(UTC)
        sub.status = SubscriptionStatus.ACTIVE
        current_end = sub.current_period_end
        if current_end is not None and current_end.tzinfo is None:
            current_end = current_end.replace(tzinfo=UTC)
        renewal_extension = bool(
            sub.status == SubscriptionStatus.ACTIVE
            and sub.current_period_start is not None
            and now >= (
                sub.current_period_start.replace(tzinfo=UTC)
                if sub.current_period_start.tzinfo is None
                else sub.current_period_start
            ) + timedelta(days=25)
            and current_end is not None
            and current_end > now
        )
        period_start = current_end if renewal_extension else now
        sub.current_period_start = period_start
        sub.current_period_end = period_start + timedelta(days=30)
        sub.flutterwave_subscription_id = transaction_reference
        await session.execute(update(User).where(User.id == user.id).values(is_subscribed=True))
        user.is_subscribed = True
        await session.commit()

        return {"is_subscribed": user.has_active_subscription}


def _get_currency_for_user(user: User, settings) -> tuple[str, float]:
    """Choose the Flutterwave charge currency and amount by account country."""
    if (user.country or "").upper() == settings.nigeria_country_code.upper():
        return "NGN", float(settings.subscription_price_ngn)
    return "USD", settings.subscription_price_usd


@router.get("/check")
async def check_subscription(
    email: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Quick check if the current user has an active subscription."""
    settings = get_settings()
    if email is None:
        return {
            "is_subscribed": False,
            "subscription_price_usd": settings.subscription_price_usd,
            "subscription_price": settings.subscription_price_usd,
            "subscription_currency": "USD",
            "subscription_price_ngn": settings.subscription_price_ngn,
            "free_predictions_remaining": FREE_PREDICTION_LIMIT,
            "total_free_predictions": FREE_PREDICTION_LIMIT,
        }

    from sqlalchemy import select

    async with DBSession() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        currency, price = (
            _get_currency_for_user(user, settings)
            if user
            else ("USD", settings.subscription_price_usd)
        )
        if user and user.subscription:
            sub = user.subscription
            period_end = sub.current_period_end
            if period_end is not None and period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=UTC)
            if (
                sub.status == SubscriptionStatus.ACTIVE
                and period_end is not None
                and period_end <= datetime.now(UTC)
            ):
                sub.status = SubscriptionStatus.EXPIRED
                user.is_subscribed = False
                await session.commit()

        subscription_active = bool(user and user.has_active_subscription)
        renewal_available = False
        period_start_value = user.subscription.current_period_start if user and user.subscription else None
        period_end_value = user.subscription.current_period_end if user and user.subscription else None
        if period_start_value is not None and period_start_value.tzinfo is None:
            period_start_value = period_start_value.replace(tzinfo=UTC)
        if period_end_value is not None and period_end_value.tzinfo is None:
            period_end_value = period_end_value.replace(tzinfo=UTC)
        if subscription_active and period_start_value and period_end_value:
            now = datetime.now(UTC)
            renewal_available = (
                now >= period_start_value + timedelta(days=25)
                and now < period_end_value
            )
        subscription_info = None
        if user and user.subscription:
            subscription_info = {
                "status": user.subscription.status.value,
                "current_period_start": period_start_value.isoformat() if period_start_value else None,
                "current_period_end": period_end_value.isoformat() if period_end_value else None,
            }
        if subscription_active:
            return {
                "is_subscribed": True,
                "subscription_price_usd": settings.subscription_price_usd,
                "subscription_price_ngn": settings.subscription_price_ngn,
                "subscription_price": price,
                "subscription_currency": currency,
                "subscription": subscription_info,
                "renewal_available": renewal_available,
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
                        "subscription_price": price,
                        "subscription_price_usd": settings.subscription_price_usd,
                        "subscription_price_ngn": settings.subscription_price_ngn,
                        "subscription_currency": currency,
                        "subscription": subscription_info,
                        "renewal_available": False,
                        "free_predictions_remaining": FREE_PREDICTION_LIMIT,
                        "total_free_predictions": FREE_PREDICTION_LIMIT,
                    }

        return {
            "is_subscribed": False,
            "subscription_price_usd": settings.subscription_price_usd,
            "subscription_price_ngn": settings.subscription_price_ngn,
            "subscription_price": price,
            "subscription_currency": currency,
            "subscription": subscription_info,
            "renewal_available": False,
            "free_predictions_remaining": FREE_PREDICTION_LIMIT,
            "total_free_predictions": FREE_PREDICTION_LIMIT,
        }
