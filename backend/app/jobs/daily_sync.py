"""Daily sync job that compares database data with provider data at 12pm Nigeria time (WAT, UTC+1)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.endpoints.providers import (
    _map_fixture_teams,
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
from models.match import Match

logger = get_logger(__name__)

WAT = timezone(timedelta(hours=1))
SYNC_HOUR = 12
SYNC_DAYS_KEY = "daily_sync:last_run_date"
PREDICTION_REFRESH_SECONDS = 6 * 60 * 60

# How far ahead to fetch per run (~one quarter of a season). Combined with the
# daily cadence and upsert-based dedup, the current season fills incrementally
# across runs without a single run pulling the whole campaign at once.
FIXTURE_WINDOW_DAYS = 90
# Fixtures are purged the day after they were played to keep the store bounded.
FIXTURE_RETENTION_DAYS = 1


async def _prune_played_fixtures(db: AsyncSession, older_than_days: int) -> int:
    """Delete fixtures whose kickoff is older than ``older_than_days``.

    Mirrors the requested "auto delete fixtures a day after play" policy and
    bounds the size of the fixtures table between daily runs.
    """
    from sqlalchemy import delete, func

    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    stmt = delete(Match).where(Match.kickoff_at < cutoff)
    result = await db.execute(stmt)
    pruned = result.rowcount
    if pruned:
        logger.info("Pruned %d fixtures played before %s", pruned, cutoff)
    return pruned


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


def _league_id_set(leagues: list[Any]) -> set[str]:
    """Collect the provider league ids represented by a list of leagues."""
    ids: set[str] = set()
    for league in leagues:
        pid = getattr(league, "provider_league_id", None) or getattr(league, "id", None)
        if pid:
            ids.add(str(pid))
    return ids


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

                    # One global teams fetch: the provider /teams endpoint is not
                    # league-scoped, so fetching it per league would re-download
                    # the same global list 30 times.
                    all_teams = await provider.get_teams()
                    counts["teams"] = len(all_teams) if all_teams else 0
                    if all_teams:
                        await _save_teams(db, all_teams)

                    # One global seasons fetch, then keep only the current season
                    # per league (the provider's /seasons endpoint ignores a
                    # league_id filter, so it is scoped client-side inside
                    # get_seasons).
                    all_seasons = await provider.get_seasons()
                    counts["seasons"] = len(all_seasons) if all_seasons else 0
                    current_seasons = [
                        s for s in (all_seasons or []) if getattr(s, "is_current", False)
                    ]
                    current_season_by_league: dict[str, str] = {
                        str(s.league_id): str(s.provider_season_id or s.id)
                        for s in current_seasons
                        if getattr(s, "league_id", None)
                    }
                    if current_seasons:
                        await _save_seasons(db, current_seasons)
                    await db.commit()

                    current_league_ids = {
                        lid for lid in current_season_by_league if lid in _league_id_set(leagues)
                    }

                    # One global fixtures fetch for the rolling window. The
                    # provider returns fixtures for the whole sport regardless of
                    # the requested league, so fetch once and scope client-side
                    # to current seasons instead of re-downloading per league.
                    fixtures = await provider.get_fixtures(
                        from_date=datetime.now(timezone.utc)
                        - timedelta(days=FIXTURE_RETENTION_DAYS),
                        to_date=datetime.now(timezone.utc)
                        + timedelta(days=FIXTURE_WINDOW_DAYS),
                    )
                    counts["fixtures"] = len(fixtures) if fixtures else 0
                    current_season_ids = set(current_season_by_league.values())
                    current_fixtures = [
                        fx
                        for fx in (fixtures or [])
                        if getattr(fx, "season_id", None) in current_season_ids
                    ]
                    if current_fixtures:
                        await _save_fixtures(db, current_fixtures)
                        await _map_fixture_teams(db, current_fixtures)
                    await db.commit()

                    for league_id in current_league_ids:
                        season_id = current_season_by_league[league_id]
                        try:
                            standings = await provider.get_standings(
                                league_id=league_id, season_id=season_id
                            )
                            counts["standings"] = counts.get("standings", 0) + (
                                len(standings.standings)
                                if standings and hasattr(standings, "standings")
                                else 0
                            )
                            if standings:
                                await _save_standings(db, [standings])
                        except Exception:
                            logger.exception("Standings fetch failed for league %s", league_id)
                            await db.rollback()
                            continue

                    # Prune fixtures that were played more than a day ago, per the
                    # auto-delete policy, after this run's batch is persisted.
                    await _prune_played_fixtures(db, FIXTURE_RETENTION_DAYS)

                    await db.commit()
    except Exception:
        logger.exception("Daily sync failed")
        return {"success": False, "counts": counts}

    try:
        await _mark_sync_complete()
    except Exception:
        # Redis is only used to mark the run complete for the prediction loop;
        # its unavailability must not report a sync failure.
        logger.warning("Could not mark daily sync complete (redis unavailable)")
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
