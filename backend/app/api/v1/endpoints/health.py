"""Health check endpoints.

GET  /api/v1/health   -- basic health (app status, DB/Redis connectivity)
GET  /api/v1/health/deep -- deep health (providers, cache, model availability)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db

router = APIRouter()


async def _check_database(db: AsyncSession) -> dict[str, Any]:
    try:
        await db.execute(select(1))
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


async def _check_redis() -> dict[str, Any]:
    try:
        from db.redis_client import redis_client

        await redis_client.client.ping()
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


@router.get("/api/v1/health", tags=["health"])
async def health(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Basic health check: application status, database, and Redis connectivity."""
    checks: dict[str, Any] = {}

    checks["database"] = await _check_database(db)
    checks["redis"] = await _check_redis()

    overall_healthy = all(c.get("status") == "healthy" for c in checks.values())

    return {
        "success": overall_healthy,
        "data": {
            "status": "healthy" if overall_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
        },
        "meta": {"checked_at": datetime.utcnow().isoformat()},
    }


@router.get("/api/v1/health/deep", tags=["health"])
async def deep_health(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Deep health check: includes provider connectivity and model availability."""
    checks: dict[str, Any] = {}

    # Database
    checks["database"] = await _check_database(db)

    # Redis
    checks["redis"] = await _check_redis()

    # Provider health
    from core.config import get_settings
    from football_data.factory import SUPPORTED_PROVIDERS, get_provider_for_name

    get_settings()
    provider_statuses: dict[str, Any] = {}

    for provider_name in SUPPORTED_PROVIDERS:
        provider = get_provider_for_name(provider_name)
        if provider is None:
            provider_statuses[provider_name] = {
                "status": "unavailable",
                "detail": {"error": "Provider not configured"},
            }
            continue
        try:
            await provider.connect()
            is_healthy = await provider.health_check()
            provider_statuses[provider_name] = {
                "status": "healthy" if is_healthy else "unhealthy",
                "detail": {},
            }
        except Exception as exc:
            provider_statuses[provider_name] = {
                "status": "unhealthy",
                "detail": {"error": str(exc)},
            }
        finally:
            try:
                await provider.close()
            except Exception:
                pass

    checks["providers"] = provider_statuses

    # Model availability
    models: dict[str, Any] = {}
    try:
        from prediction.poisson import PoissonModel

        PoissonModel()
        models["poisson_v1"] = {"status": "available"}
    except Exception as exc:
        models["poisson_v1"] = {"status": "unavailable", "error": str(exc)}

    checks["models"] = models

    overall_healthy = all(
        c.get("status") == "healthy" for k, c in checks.items() if k not in ("providers", "models")
    )

    return {
        "success": overall_healthy,
        "data": {
            "status": "healthy" if overall_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
        },
        "meta": {"checked_at": datetime.utcnow().isoformat()},
    }
