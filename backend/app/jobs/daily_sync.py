"""Daily sync job that compares database data with provider data at 12pm Nigeria time (WAT, UTC+1)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.endpoints.providers import (
    _save_fixtures,
    _save_leagues,
    _save_seasons,
    _save_standings,
    _save_teams,
)
from core.logging import get_logger
from db.database import AsyncSessionLocal
from db.redis_client import redis_client
from football_data.factory import get_football_provider
from models.league import Season

logger = get_logger(__name__)

WAT = timezone(timedelta(hours=1))
SYNC_HOUR = 12
SYNC_DAYS_KEY = "daily_sync:last_run_date"
PREDICTION_REFRESH_SECONDS = 6 * 60 * 60


async def _mark_sync_complete() -> None:
    today = datetime.now(WAT).strftime("%Y-%m-%d")
    await redis_client.set_json(
        f"{SYNC_DAYS_KEY}:{today}",
        {"synced_at": datetime.now(WAT).isoformat(), "status": "completed"},
        ttl=86400 * 8,
    )


async def _was_synced_today() -> bool:
    today = datetime.now(WAT).strftime("%Y-%m-%d")
    result = await redis_client.get_json(f"{SYNC_DAYS_KEY}:{today}")
    return result is not None


async def _get_current_season_id_by_league(db: AsyncSession, provider_league_id: str) -> str | None:
    stmt = (
        select(Season.id)
        .where(Season.league_id == provider_league_id, Season.is_current.is_(True))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def daily_sync_once() -> dict[str, Any]:
    """Run one full sync cycle: fetch provider data and persist to DB."""
    provider = get_football_provider()
    counts: dict[str, int] = {}
    try:
        async with provider:
            leagues = await provider.get_leagues()
            counts["leagues"] = len(leagues) if leagues else 0

            if leagues:
                async with AsyncSessionLocal() as db:
                    await _save_leagues(db, leagues)
                    await db.commit()

                    for league in leagues or []:
                        league_id = getattr(league, "provider_league_id", None) or getattr(
                            league, "id", None
                        )
                        if not league_id:
                            continue
                        league_id = str(league_id)

                        current_season_id = await _get_current_season_id_by_league(db, league_id)

                        if current_season_id is None:
                            seasons = await provider.get_seasons(league_id=league_id)
                            counts["seasons"] = counts.get("seasons", 0) + (
                                len(seasons) if seasons else 0
                            )
                            current_seasons = [
                                s for s in (seasons or []) if getattr(s, "is_current", False)
                            ]
                            if current_seasons:
                                await _save_seasons(db, current_seasons)
                            await db.commit()
                            current_season_id = await _get_current_season_id_by_league(
                                db, league_id
                            )
                        else:
                            logger.info(
                                "League %s already has a current season in DB.",
                                league_id,
                            )

                        teams = await provider.get_teams(
                            league_id=league_id, season_id=current_season_id
                        )
                        counts["teams"] = counts.get("teams", 0) + (len(teams) if teams else 0)
                        if teams:
                            await _save_teams(db, teams)

                        fixtures = await provider.get_fixtures(
                            league_id=league_id, season_id=current_season_id
                        )
                        counts["fixtures"] = counts.get("fixtures", 0) + (
                            len(fixtures) if fixtures else 0
                        )
                        if fixtures:
                            await _save_fixtures(db, fixtures)

                        standings = await provider.get_standings(
                            league_id=league_id, season_id=current_season_id
                        )
                        counts["standings"] = counts.get("standings", 0) + (
                            len(standings.standings)
                            if standings and hasattr(standings, "standings")
                            else 0
                        )
                        if standings:
                            await _save_standings(db, [standings])

                        await db.commit()
    except Exception:
        logger.exception("Daily sync failed")
        return {"success": False, "counts": counts}

    await _mark_sync_complete()
    logger.info("Daily sync completed", extra={"counts": counts})
    return {"success": True, "counts": counts}


async def generate_upcoming_predictions_once() -> dict[str, Any]:
    """Generate persisted predictions for upcoming current-season fixtures."""
    from services.prediction_orchestrator import PredictionOrchestrator

    if not await _was_synced_today():
        sync_result = await daily_sync_once()
        if not sync_result.get("success"):
            logger.warning(
                "Prediction generation is using existing fixtures after sync failure",
                extra={"sync_counts": sync_result.get("counts", {})},
            )

    async with AsyncSessionLocal() as db:
        return await PredictionOrchestrator().generate_upcoming_predictions(db_session=db)


async def prediction_generation_loop() -> None:
    """Generate predictions at startup and refresh them every six hours."""
    first_cycle = True
    while True:
        try:
            if first_cycle or not await _was_synced_today():
                await daily_sync_once()
            result = await generate_upcoming_predictions_once()
            logger.info("Prediction generation cycle completed", extra=result)
        except Exception:
            logger.exception("Prediction generation cycle failed")
        first_cycle = False
        await asyncio.sleep(PREDICTION_REFRESH_SECONDS)


async def daily_sync_loop() -> None:
    """Background loop that triggers daily_sync_once at 12:00 WAT daily."""
    while True:
        now = datetime.now(WAT)
        target = now.replace(hour=SYNC_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        delay = (target - now).total_seconds()
        await asyncio.sleep(delay)

        try:
            if not await _was_synced_today():
                logger.info("Starting daily sync at %s", now.isoformat())
                await daily_sync_once()
        except Exception:
            logger.exception("Daily sync loop encountered an error")

        await asyncio.sleep(60)
