"""Daily sync job: fetches all leagues, teams, fixtures, standings, and other
data from the provider, filters duplicates, compares with database, and only
updates differences.

Runs once a day via scheduler/cron or task runner.

Usage:
    set PYTHONPATH=app
    python scripts/daily_sync.py
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from core.config import get_settings
from db.database import AsyncSessionLocal
from db.redis_client import get_redis
from football_data.factory import get_football_provider
from football_data.league_mappings import LeagueMapping
from football_data.models import (
    FixtureStatus,
    NormalizedLeague,
    NormalizedSeason,
)
from models.league import League, ProviderLeague, ProviderTeam, Season, Team
from models.match import Match, ProviderSyncLog, TeamStatistics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("daily_sync")


async def _log_sync(
    db: AsyncSession,
    provider_name: str,
    resource: str,
    status: str,
    fetched: int | None = None,
    stored: int | None = None,
    error: str | None = None,
) -> None:
    entry = ProviderSyncLog(
        provider_name=provider_name,
        resource=resource,
        status=status,
        records_fetched=fetched,
        records_stored=stored,
        error_message=error,
    )
    db.add(entry)
    await db.commit()


async def refresh_provider_metadata(
    db: AsyncSession, provider, resource: str, method_name: str, **kwargs: Any
) -> int:
    """Refresh lightweight provider metadata that does not yet have a persisted DB table."""
    try:
        method = getattr(provider, method_name)
        payload = await method(**kwargs)
        if payload is None:
            payload = []
        elif not isinstance(payload, list):
            payload = [payload]
        await _log_sync(
            db,
            provider.provider_name,
            resource,
            "completed",
            fetched=len(payload),
            stored=len(payload),
        )
        return len(payload)
    except Exception as exc:
        logger.warning("Failed to refresh %s: %s", resource, exc)
        await _log_sync(
            db,
            provider.provider_name,
            resource,
            "failed",
            error=str(exc),
        )
        return 0


async def fetch_all_provider_leagues(provider) -> list[NormalizedLeague]:
    """Fetch all leagues from the provider and filter duplicates by provider_league_id."""
    logger.info("Fetching all leagues from provider...")
    leagues = await provider.get_leagues()
    logger.info("Fetched %d leagues from provider", len(leagues))

    # Filter duplicates by provider_league_id, keep first occurrence
    seen_ids = set()
    unique_leagues = []
    duplicates = 0

    for league in leagues:
        pid = league.provider_league_id
        if pid not in seen_ids:
            seen_ids.add(pid)
            unique_leagues.append(league)
        else:
            duplicates += 1

    logger.info("Unique leagues: %d, Duplicates removed: %d", len(unique_leagues), duplicates)
    return unique_leagues


async def sync_leagues_diff(
    db: AsyncSession, provider, provider_leagues: list[NormalizedLeague]
) -> dict[str, int]:
    """Sync leagues by comparing provider data with database, only updating differences."""
    stats = {"created": 0, "updated": 0, "unchanged": 0, "errors": 0}
    provider_name = provider.provider_name

    for norm in provider_leagues:
        try:
            provider_league_id = norm.provider_league_id

            # Check if league exists in DB
            existing = await db.get(League, provider_league_id)

            if existing is None:
                league = League(
                    id=provider_league_id,
                    name=norm.name,
                    country=norm.country,
                    country_code=norm.country_code,
                    is_active=True,
                )
                db.add(league)
                stats["created"] += 1
                logger.info("Created league: %s (%s)", norm.name, provider_league_id)
            else:
                # Check if data differs
                if (
                    existing.name != norm.name
                    or existing.country != norm.country
                    or existing.country_code != norm.country_code
                ):
                    existing.name = norm.name
                    existing.country = norm.country
                    existing.country_code = norm.country_code
                    stats["updated"] += 1
                    logger.info("Updated league: %s (%s)", norm.name, provider_league_id)
                else:
                    stats["unchanged"] += 1

            # Update provider mapping
            provider_mapping_result = await db.execute(
                select(ProviderLeague).where(
                    ProviderLeague.provider_league_id == provider_league_id,
                    ProviderLeague.provider_name == provider_name,
                )
            )
            existing_mapping = provider_mapping_result.scalar_one_or_none()

            if existing_mapping is None:
                provider_league = ProviderLeague(
                    internal_league_id=provider_league_id,
                    provider_name=provider_name,
                    provider_league_id=provider_league_id,
                    is_active=True,
                )
                db.add(provider_league)

        except Exception as exc:
            logger.error("Error syncing league %s: %s", norm.name, exc)
            stats["errors"] += 1

    await db.commit()
    await _log_sync(
        db,
        provider_name,
        "leagues",
        "completed",
        fetched=len(provider_leagues),
        stored=stats["created"] + stats["updated"],
    )
    return stats


async def sync_seasons_diff(
    db: AsyncSession, provider, league_internal_id: str, provider_league_id: str
) -> list[NormalizedSeason]:
    """Sync seasons for a league with diff comparison."""
    provider_name = provider.provider_name
    logger.info(
        "Fetching seasons for league %s (provider %s) ...", league_internal_id, provider_league_id
    )
    try:
        seasons = await provider.get_seasons(league_id=provider_league_id)
        logger.info("Fetched %d seasons", len(seasons))
    except Exception as exc:
        logger.warning("Failed to fetch seasons for %s: %s", league_internal_id, exc)
        return []

    current_season_id: str | None = None
    for norm in seasons:
        if norm.is_current:
            current_season_id = norm.provider_season_id
            break

    result: list[NormalizedSeason] = []
    for norm in seasons:
        try:
            existing = await db.get(Season, norm.provider_season_id)
            if existing is None:
                season = Season(
                    id=norm.provider_season_id,
                    league_id=league_internal_id,
                    name=norm.name or str(norm.year),
                    year=norm.year,
                    start_date=norm.start_date,
                    end_date=norm.end_date,
                    is_current=False,
                )
                db.add(season)
                result.append(norm)
            else:
                # Re-assert the owning league: earlier syncs wrote seasons
                # against a mapping slug instead of the leagues table id.
                existing.league_id = league_internal_id
                existing.is_current = False
                if norm.year:
                    existing.year = norm.year
                if norm.start_date:
                    existing.start_date = norm.start_date
                if norm.end_date:
                    existing.end_date = norm.end_date
                result.append(norm)
        except Exception as exc:
            logger.warning("Error storing season: %s", exc)

    # Exactly one current season per league. Clearing first and then flagging
    # only the provider's current season keeps the invariant even when several
    # seasons were previously flagged.
    await db.execute(
        update(Season)
        .where(Season.league_id == league_internal_id)
        .values(is_current=False)
    )
    if current_season_id:
        await db.execute(
            update(Season)
            .where(Season.id == current_season_id)
            .values(league_id=league_internal_id, is_current=True)
        )
    logger.info(
        "League %s current season: %s", league_internal_id, current_season_id or "none"
    )

    await db.commit()
    await _log_sync(
        db,
        provider_name,
        f"seasons:{league_internal_id}",
        "completed",
        fetched=len(seasons),
        stored=len(result),
    )
    return result


async def sync_teams_diff(
    db: AsyncSession,
    provider,
    league_internal_id: str,
    provider_league_id: str,
    provider_season_id: str,
) -> dict[str, str]:
    """Sync teams for a league/season with diff comparison."""
    provider_name = provider.provider_name
    logger.info(
        "Fetching teams for league %s, season %s ...", league_internal_id, provider_season_id
    )
    try:
        teams = await provider.get_teams(league_id=provider_league_id, season_id=provider_season_id)
        logger.info("Fetched %d teams", len(teams))
    except Exception as exc:
        logger.warning("Failed to fetch teams for %s: %s", league_internal_id, exc)
        return {}

    team_map: dict[str, str] = {}
    for norm in teams:
        try:
            if not norm.provider_team_id:
                continue

            # Check if team exists
            existing = await db.get(Team, norm.provider_team_id)

            if existing is None:
                team = Team(
                    id=norm.provider_team_id,
                    name=norm.name,
                    short_name=norm.short_name,
                    slug=norm.slug,
                    logo_url=norm.logo_url,
                    venue_name=norm.venue_name,
                    venue_city=norm.venue_city,
                    country=norm.country,
                    is_active=True,
                )
                db.add(team)
            else:
                # Check for differences
                if (
                    existing.name != norm.name
                    or existing.short_name != (norm.short_name or existing.short_name)
                    or existing.logo_url != (norm.logo_url or existing.logo_url)
                ):
                    existing.name = norm.name
                    existing.short_name = norm.short_name or existing.short_name
                    existing.logo_url = norm.logo_url or existing.logo_url
                    logger.info("Updated team: %s", norm.name)

            stmt = (
                insert(ProviderTeam.__table__)
                .values(
                    internal_team_id=norm.provider_team_id,
                    provider_name=provider_name,
                    provider_team_id=norm.provider_team_id,
                    provider_league_id=provider_league_id,
                    season_id=provider_season_id or None,
                    is_active=True,
                )
                .on_conflict_do_update(
                    # Backfill rows written before these columns were populated,
                    # and refresh the scope on every sync.
                    index_elements=[
                        "internal_team_id",
                        "provider_name",
                        "provider_league_id",
                        "season_id",
                    ],
                    set_={
                        "provider_team_id": norm.provider_team_id,
                        "provider_league_id": provider_league_id,
                        "season_id": provider_season_id or None,
                    },
                )
            )
            await db.execute(stmt)
            team_map[norm.provider_team_id] = norm.provider_team_id
        except Exception as exc:
            logger.warning("Error storing team %s: %s", norm.name, exc)

    await db.commit()
    await _log_sync(
        db,
        provider_name,
        f"teams:{league_internal_id}",
        "completed",
        fetched=len(teams),
        stored=len(team_map),
    )
    return team_map


async def sync_fixtures_diff(
    db: AsyncSession,
    provider,
    league_internal_id: str,
    provider_league_id: str,
    provider_season_id: str,
    days: int = 30,
) -> int:
    """Sync fixtures for a league/season with diff comparison."""
    provider_name = provider.provider_name
    now = datetime.now(timezone.utc)
    logger.info(
        "Fetching fixtures for league %s, season %s (next %d days) ...",
        league_internal_id,
        provider_season_id,
        days,
    )

    try:
        fixtures = await provider.get_fixtures(
            league_id=provider_league_id,
            season_id=provider_season_id,
            from_date=now,
            to_date=now + timedelta(days=days),
        )
        logger.info("Fetched %d fixtures", len(fixtures))
    except Exception as exc:
        logger.warning("Failed to fetch fixtures for %s: %s", league_internal_id, exc)
        return 0

    stored = 0
    for norm in fixtures:
        try:
            if not norm.provider_fixture_id:
                continue

            fixture_id = norm.provider_fixture_id
            status_val = (
                norm.status.value if isinstance(norm.status, FixtureStatus) else str(norm.status)
            )

            # Check if fixture exists and if data differs
            existing = await db.get(Match, fixture_id)

            if existing is None:
                match = Match(
                    id=fixture_id,
                    provider_name=provider_name,
                    provider_fixture_id=fixture_id,
                    league_id=league_internal_id,
                    season_id=provider_season_id,
                    home_team_id=norm.home_team_id,
                    away_team_id=norm.away_team_id,
                    home_team_name=norm.home_team_name,
                    away_team_name=norm.away_team_name,
                    kickoff_at=norm.kickoff_at,
                    status=status_val,
                    venue=norm.venue,
                    referee=norm.referee,
                    home_score=norm.home_score,
                    away_score=norm.away_score,
                    is_finished=norm.is_finished,
                    retrieved_at=norm.retrieved_at,
                    provider_metadata=norm.provider_metadata,
                )
                db.add(match)
                stored += 1
            else:
                # Only update if data differs
                if (
                    existing.home_score != norm.home_score
                    or existing.away_score != norm.away_score
                    or existing.status != status_val
                    or existing.is_finished != norm.is_finished
                ):
                    existing.home_score = norm.home_score
                    existing.away_score = norm.away_score
                    existing.status = status_val
                    existing.is_finished = norm.is_finished
                    existing.retrieved_at = datetime.utcnow()
                    existing.kickoff_at = norm.kickoff_at
                    existing.home_team_name = norm.home_team_name or existing.home_team_name
                    existing.away_team_name = norm.away_team_name or existing.away_team_name
                    stored += 1
        except Exception as exc:
            logger.warning("Error storing fixture: %s", exc)

    await db.commit()
    await _log_sync(
        db,
        provider_name,
        f"fixtures:{league_internal_id}",
        "completed",
        fetched=len(fixtures),
        stored=stored,
    )
    return stored


async def sync_standings_diff(
    db: AsyncSession,
    provider,
    league_internal_id: str,
    provider_league_id: str,
    provider_season_id: str,
) -> int:
    """Sync standings for a league/season with diff comparison."""
    provider_name = provider.provider_name
    logger.info(
        "Fetching standings for league %s, season %s ...", league_internal_id, provider_season_id
    )
    try:
        standings = await provider.get_standings(
            league_id=provider_league_id, season_id=provider_season_id
        )
        n = len(standings.standings) if standings and standings.standings else 0
        logger.info("Fetched standings with %d teams", n)
    except Exception as exc:
        logger.warning("Failed to fetch standings for %s: %s", league_internal_id, exc)
        return 0

    if not standings or not standings.standings:
        return 0

    stored = 0
    for standing in standings.standings:
        try:
            # Check for existing record
            existing_stmt = select(TeamStatistics).where(
                TeamStatistics.provider_name == provider_name,
                TeamStatistics.provider_team_id == (standing.team_id or ""),
                TeamStatistics.league_id == league_internal_id,
                TeamStatistics.season_id == provider_season_id,
            )
            existing_result = await db.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()

            if existing is None:
                stmt = insert(TeamStatistics.__table__).values(
                    provider_name=provider_name,
                    provider_team_id=standing.team_id or "",
                    internal_team_id=standing.team_id,
                    league_id=league_internal_id,
                    season_id=provider_season_id,
                    is_home=False,
                    games_played=standing.played,
                    wins=standing.wins,
                    draws=standing.draws,
                    losses=standing.losses,
                    goals_for=standing.goals_for,
                    goals_against=standing.goals_against,
                    points=standing.points,
                    position=standing.position,
                    form_rating=standing.provider_metadata.get("form_rating")
                    if standing.provider_metadata
                    else None,
                    retrieved_at=datetime.utcnow(),
                    provider_metadata=standing.provider_metadata or {},
                )
                await db.execute(stmt)
                stored += 1
            else:
                # Only update if data differs
                if (
                    existing.points != standing.points
                    or existing.position != standing.position
                    or existing.wins != standing.wins
                    or existing.draws != standing.draws
                    or existing.losses != standing.losses
                ):
                    existing.points = standing.points
                    existing.position = standing.position
                    existing.wins = standing.wins
                    existing.draws = standing.draws
                    existing.losses = standing.losses
                    existing.goals_for = standing.goals_for
                    existing.goals_against = standing.goals_against
                    existing.retrieved_at = datetime.utcnow()
                    existing.provider_metadata = standing.provider_metadata or {}
                    stored += 1
        except Exception as exc:
            logger.warning("Error storing standing: %s", exc)

    await db.commit()
    await _log_sync(
        db, provider_name, f"standings:{league_internal_id}", "completed", fetched=n, stored=stored
    )
    return stored


async def sync_injuries(db: AsyncSession, provider, team_ids: list[str]) -> int:
    """Sync injuries for specified teams."""
    provider_name = provider.provider_name
    stored = 0

    for team_id in team_ids:
        try:
            injuries = await provider.get_injuries(team_id=team_id)
            if injuries:
                logger.info("Fetched %d injuries for team %s", len(injuries), team_id)
                stored += len(injuries)
        except Exception as exc:
            logger.warning("Failed to fetch injuries for team %s: %s", team_id, exc)

    await _log_sync(db, provider_name, "injuries", "completed", fetched=stored, stored=stored)
    return stored


async def sync_suspensions(db: AsyncSession, provider, team_ids: list[str]) -> int:
    """Sync suspensions for specified teams."""
    provider_name = provider.provider_name
    stored = 0

    for team_id in team_ids:
        try:
            suspensions = await provider.get_suspensions(team_id=team_id)
            if suspensions:
                logger.info("Fetched %d suspensions for team %s", len(suspensions), team_id)
                stored += len(suspensions)
        except Exception as exc:
            logger.warning("Failed to fetch suspensions for team %s: %s", team_id, exc)

    await _log_sync(db, provider_name, "suspensions", "completed", fetched=stored, stored=stored)
    return stored


async def increment_db_version() -> int:
    """Increment database version in Redis for cache invalidation."""
    redis = await get_redis()
    if not redis.client:
        await redis.connect()
    try:
        new_version = await redis.client.incr("db:version")
        logger.info("Database version incremented to %d", new_version)
        return new_version
    except Exception as exc:
        logger.error("Failed to increment DB version: %s", exc)
        return 0


async def run_daily_sync(core_only: bool = False):
    """Main entry point for daily sync job."""
    logger.info("Starting daily sync job...")
    start_time = datetime.now(timezone.utc)

    provider = get_football_provider()
    await provider.connect()
    provider_name = provider.provider_name

    try:
        # Fetch all leagues from provider (with deduplication)
        provider_leagues = await fetch_all_provider_leagues(provider)

        # Sync leagues with database using diff
        async with AsyncSessionLocal() as db:
            league_stats = await sync_leagues_diff(db, provider, provider_leagues)

            # Sync data for all registered leagues (all levels)
            total_teams = 0
            total_fixtures = 0
            total_standings = 0
            all_team_ids: list[str] = []

            for cfg in LeagueMapping.all():
                provider_ids = cfg.provider_ids.get(provider_name)
                if not provider_ids:
                    logger.warning(
                        "League %s not configured for provider %s, skipping",
                        cfg.internal_id,
                        provider_name,
                    )
                    continue

                p_league_id = provider_ids.get("league_id")
                p_season_id = provider_ids.get("season_id", "")
                if not p_league_id:
                    continue

                # sync_leagues_diff stores leagues keyed by the provider league
                # id, so that same id is what every child table must reference.
                # The mapping slug is not a row in `leagues`.
                league_db_id = p_league_id

                # Sync seasons
                seasons = await sync_seasons_diff(db, provider, league_db_id, p_league_id)

                if not p_season_id and seasons:
                    for s in seasons:
                        if s.is_current:
                            p_season_id = s.provider_season_id
                            break
                    if not p_season_id:
                        p_season_id = seasons[-1].provider_season_id

                # Sync teams
                team_map = await sync_teams_diff(
                    db, provider, league_db_id, p_league_id, p_season_id or ""
                )
                total_teams += len(team_map)
                all_team_ids.extend(list(team_map.keys()))

                # Sync fixtures
                total_fixtures += await sync_fixtures_diff(
                    db, provider, league_db_id, p_league_id, p_season_id or ""
                )

                # Sync standings
                total_standings += await sync_standings_diff(
                    db, provider, league_db_id, p_league_id, p_season_id or ""
                )

            # Refresh provider metadata and supporting data that is not yet
            # backed by a dedicated table. These are large global pulls, so
            # --core-only skips them when only leagues/seasons/teams/fixtures
            # are needed and the provider rate limit is tight.
            if not core_only:
                await refresh_provider_metadata(db, provider, "timezones", "get_timezones")
                await refresh_provider_metadata(db, provider, "countries", "get_countries")
                await refresh_provider_metadata(db, provider, "venues", "get_venues")
                await refresh_provider_metadata(db, provider, "coaches", "get_coaches")
                await refresh_provider_metadata(db, provider, "transfers", "get_transfers")
                await refresh_provider_metadata(db, provider, "trophies", "get_trophies")
                await refresh_provider_metadata(
                    db, provider, "predictions", "get_predictions", fixture_id="latest"
                )

                # Fetch injuries and suspensions for key teams (limit to reduce API calls)
                if all_team_ids:
                    logger.info(
                        "Fetching injuries and suspensions for %d teams", len(all_team_ids)
                    )
                    await sync_injuries(db, provider, all_team_ids[:20])  # Limit to first 20 teams
                    await sync_suspensions(db, provider, all_team_ids[:20])
                    await refresh_provider_metadata(
                        db, provider, "sidelined", "get_sidelined", team_id=all_team_ids[0]
                    )

            # Increment DB version to invalidate frontend caches
            await increment_db_version()

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                "Daily sync completed in %.2fs: "
                "leagues created=%d, updated=%d, unchanged=%d | "
                "teams=%d, fixtures=%d, standings=%d",
                elapsed,
                league_stats["created"],
                league_stats["updated"],
                league_stats["unchanged"],
                total_teams,
                total_fixtures,
                total_standings,
            )

    except Exception as exc:
        logger.exception("Daily sync failed: %s", exc)
        raise
    finally:
        await provider.close()


if __name__ == "__main__":
    import argparse

    import logging as _logging

    # httpx logs the full request URL at INFO, which writes the provider
    # api_token query parameter into the logs.
    _logging.getLogger("httpx").setLevel(_logging.WARNING)

    _parser = argparse.ArgumentParser()
    _parser.add_argument(
        "--core-only",
        action="store_true",
        help="Skip large global metadata pulls (timezones, countries, venues, ...).",
    )
    _args = _parser.parse_args()
    asyncio.run(run_daily_sync(core_only=_args.core_only))
