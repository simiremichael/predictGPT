"""Data sync script: pulls leagues, teams, fixtures, and standings from the
active football data provider and stores them in the local database.

Usage:
    set PYTHONPATH=app
    python sync_data.py
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from core.config import get_settings
from db.database import AsyncSessionLocal
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
logger = logging.getLogger("sync")


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


async def sync_leagues(db: AsyncSession, provider) -> int:
    provider_name = provider.provider_name
    count = 0
    for cfg in LeagueMapping.all():
        provider_ids = cfg.provider_ids.get(provider_name)
        if not provider_ids:
            logger.warning(
                "League %s not configured for provider %s, skipping", cfg.internal_id, provider_name
            )
            continue

        p_league_id = provider_ids.get("league_id")
        logger.info("Fetching league %s (provider_id=%s) ...", cfg.internal_id, p_league_id)
        try:
            league_data = await provider.get_league(p_league_id)
        except Exception as exc:
            logger.warning("Failed to fetch league %s: %s", cfg.internal_id, exc)
            await _log_sync(db, provider_name, "leagues", "failed", error=str(exc))
            continue

        if league_data is None:
            logger.warning("No data for league %s", cfg.internal_id)
            continue

        norm = league_data
        try:
            stmt = (
                insert(League.__table__)
                .values(
                    id=cfg.internal_id,
                    name=norm.name,
                    country=norm.country,
                    country_code=norm.country_code,
                    is_active=True,
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "name": norm.name,
                        "country": norm.country,
                        "country_code": norm.country_code,
                    },
                )
            )
            await db.execute(stmt)

            stmt = (
                insert(ProviderLeague.__table__)
                .values(
                    internal_league_id=cfg.internal_id,
                    provider_name=provider_name,
                    provider_league_id=norm.provider_league_id,
                    is_active=True,
                )
                .on_conflict_do_nothing()
            )
            await db.execute(stmt)
            count += 1
        except Exception as exc:
            logger.warning("Error storing league %s: %s", norm.name, exc)

    await db.commit()
    await _log_sync(
        db, provider_name, "leagues", "completed", fetched=len(LeagueMapping.all()), stored=count
    )
    logger.info("Synced %d league records", count)
    return count


async def sync_seasons(
    db: AsyncSession, provider, league_internal_id: str, provider_league_id: str
) -> list[NormalizedSeason]:
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

    result: list[NormalizedSeason] = []
    for norm in seasons:
        try:
            existing = await db.get(Season, norm.provider_season_id)
            if existing is None:
                if norm.is_current:
                    await db.execute(
                        update(Season)
                        .where(Season.league_id == league_internal_id)
                        .values(is_current=False)
                    )
                season = Season(
                    id=norm.provider_season_id,
                    league_id=league_internal_id,
                    name=norm.name or str(norm.year),
                    year=norm.year,
                    start_date=norm.start_date,
                    end_date=norm.end_date,
                    is_current=norm.is_current,
                )
                db.add(season)
                result.append(norm)
            else:
                existing.is_current = norm.is_current
                existing.year = norm.year or existing.year
                if norm.start_date:
                    existing.start_date = norm.start_date
                if norm.end_date:
                    existing.end_date = norm.end_date
                result.append(norm)
        except Exception as exc:
            logger.warning("Error storing season: %s", exc)

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


async def sync_teams(
    db: AsyncSession,
    provider,
    league_internal_id: str,
    provider_league_id: str,
    provider_season_id: str,
) -> dict[str, str]:
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

            stmt = (
                insert(Team.__table__)
                .values(
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
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "name": norm.name,
                        "short_name": norm.short_name or Team.__table__.c.short_name,
                        "slug": norm.slug or Team.__table__.c.slug,
                        "logo_url": norm.logo_url or Team.__table__.c.logo_url,
                        "venue_name": norm.venue_name or Team.__table__.c.venue_name,
                        "venue_city": norm.venue_city or Team.__table__.c.venue_city,
                        "country": norm.country or Team.__table__.c.country,
                    },
                )
            )
            await db.execute(stmt)

            stmt = (
                insert(ProviderTeam.__table__)
                .values(
                    internal_team_id=norm.provider_team_id,
                    provider_name=provider_name,
                    provider_team_id=norm.provider_team_id,
                    is_active=True,
                )
                .on_conflict_do_nothing()
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


async def sync_fixtures(
    db: AsyncSession,
    provider,
    league_internal_id: str,
    provider_league_id: str,
    provider_season_id: str,
    days: int = 30,
) -> int:
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

            stmt = (
                insert(Match.__table__)
                .values(
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
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "home_score": norm.home_score,
                        "away_score": norm.away_score,
                        "status": status_val,
                        "is_finished": norm.is_finished,
                        "retrieved_at": datetime.utcnow(),
                        "kickoff_at": norm.kickoff_at,
                        "home_team_name": norm.home_team_name or Match.__table__.c.home_team_name,
                        "away_team_name": norm.away_team_name or Match.__table__.c.away_team_name,
                    },
                )
            )
            await db.execute(stmt)
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


async def sync_standings(
    db: AsyncSession,
    provider,
    league_internal_id: str,
    provider_league_id: str,
    provider_season_id: str,
) -> int:
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
        except Exception as exc:
            logger.warning("Error storing standing: %s", exc)

    await db.commit()
    await _log_sync(
        db, provider_name, f"standings:{league_internal_id}", "completed", fetched=n, stored=stored
    )
    return stored


async def run_sync():
    logger.info("Starting data sync ...")
    provider = get_football_provider()
    await provider.connect()
    provider_name = provider.provider_name

    async with AsyncSessionLocal() as db:
        total = 0
        total += await sync_leagues(db, provider)

        for cfg in LeagueMapping.all():
            provider_ids = cfg.provider_ids.get(provider_name)
            if not provider_ids:
                continue

            p_league_id = provider_ids.get("league_id")
            p_season_id = provider_ids.get("season_id", "")
            if not p_league_id:
                continue

            seasons = await sync_seasons(db, provider, cfg.internal_id, p_league_id)

            if not p_season_id and seasons:
                for s in seasons:
                    if s.is_current:
                        p_season_id = s.provider_season_id
                        break
                if not p_season_id:
                    p_season_id = seasons[-1].provider_season_id

            await sync_teams(db, provider, cfg.internal_id, p_league_id, p_season_id or "")
            total += await sync_fixtures(
                db, provider, cfg.internal_id, p_league_id, p_season_id or ""
            )
            total += await sync_standings(
                db, provider, cfg.internal_id, p_league_id, p_season_id or ""
            )

        logger.info("Sync complete. Total fixture/standing records: %d", total)

    await provider.close()


if __name__ == "__main__":
    asyncio.run(run_sync())
