"""Provider status endpoints.

GET  /api/v1/providers/status  -- health of all configured providers
GET  /api/v1/providers/timezones -- API-Football timezone metadata
GET  /api/v1/providers/countries -- API-Football country list
GET  /api/v1/providers/leagues -- direct provider league list
GET  /api/v1/providers/seasons -- direct provider season list
GET  /api/v1/providers/teams -- direct provider team list
GET  /api/v1/providers/venues -- direct provider venue list
GET  /api/v1/providers/standings -- direct provider standings list
GET  /api/v1/providers/fixtures -- direct provider fixtures list
GET  /api/v1/providers/injuries -- direct provider injuries list
GET  /api/v1/providers/predictions -- direct provider predictions list
GET  /api/v1/providers/coaches -- direct provider coaches list
GET  /api/v1/providers/players -- direct provider players list
GET  /api/v1/providers/transfers -- direct provider transfers list
GET  /api/v1/providers/trophies -- direct provider trophies list
GET  /api/v1/providers/sidelined -- direct provider sidelined list
GET  /api/v1/providers/odds/pre-match -- direct provider pre-match odds list
GET  /api/v1/providers/odds/in-play -- direct provider in-play odds list
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from core.config import get_settings
from core.logging import get_logger
from core.security import verify_admin_api_key
from db.database import AsyncSessionLocal
from football_data.factory import SUPPORTED_PROVIDERS, get_football_provider, get_provider_for_name
from football_data.league_mappings import LeagueMapping
from football_data.models import NormalizedProviderStatus
from models.league import League, ProviderLeague, Season, Team
from models.match import Injury, Match, Player, Suspension, TeamStatistics

logger = get_logger(__name__)

router = APIRouter()


def _serialize_league_items(items: Any) -> set[tuple[str | None, str | None, str | None]]:
    if items is None:
        return set()

    normalized: set[tuple[str | None, str | None, str | None]] = set()

    for item in items:
        if isinstance(item, dict):
            normalized.add(
                (
                    item.get("name"),
                    item.get("country"),
                    item.get("country_code"),
                )
            )
            continue

        if hasattr(item, "name"):
            normalized.add(
                (
                    getattr(item, "name", None),
                    getattr(item, "country", None),
                    getattr(item, "country_code", None),
                )
            )

    return normalized


def _sanitize_payload_for_compare(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {
                "id",
                "internal_id",
                "created_at",
                "updated_at",
                "retrieved_at",
                "provider_metadata",
                "metadata",
                "valid_until",
            }:
                continue
            cleaned[key] = _sanitize_payload_for_compare(value)
        return {k: v for k, v in sorted(cleaned.items())}
    if isinstance(payload, (list, tuple, set)):
        return [_sanitize_payload_for_compare(item) for item in payload]
    return payload


def _payload_signature(payload: Any) -> str:
    payload = _sanitize_payload_for_compare(payload)
    return json.dumps(payload, sort_keys=True, default=str)


def _resolve_provider_league_id(
    league_id: str | None, provider_name: str | None = None
) -> str | None:
    """Map an internal league identifier (e.g. 'premier_league') to the API provider ID."""
    if league_id is None:
        return None

    league_id = str(league_id)
    if not league_id:
        return None
    if league_id.isdigit():
        return league_id

    provider_name = provider_name or get_settings().football_data_provider
    cfg = LeagueMapping.get(league_id)
    if cfg is not None:
        provider_ids = cfg.provider_ids.get(provider_name) or cfg.provider_ids.get("api_football")
        if provider_ids and provider_ids.get("league_id"):
            return str(provider_ids["league_id"])

    return league_id


async def _read_db_resource_payload(provider_method: str, **kwargs: Any) -> list[dict[str, Any]]:
    page = kwargs.pop("page", 1)
    page_size = kwargs.pop("page_size", 50)
    offset = (page - 1) * page_size

    async with AsyncSessionLocal() as db:
        if provider_method == "get_leagues":
            stmt = select(League)
            if kwargs.get("country"):
                stmt = stmt.where(League.country == kwargs["country"])
            stmt = stmt.order_by(League.name)
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()
            return {
                "data": [
                    {
                        "id": row.id,
                        "name": row.name,
                        "country": row.country,
                        "country_code": row.country_code,
                        "is_active": row.is_active,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                    for row in rows
                ],
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
                },
            }

        if provider_method == "get_seasons":
            stmt = select(Season)
            if kwargs.get("league_id"):
                stmt = stmt.where(Season.league_id == kwargs["league_id"])
            stmt = stmt.order_by(Season.year.desc(), Season.name)
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()
            return {
                "data": [
                    {
                        "id": row.id,
                        "league_id": row.league_id,
                        "name": row.name,
                        "year": row.year,
                        "is_current": row.is_current,
                    }
                    for row in rows
                ],
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
                },
            }

        if provider_method == "get_teams":
            stmt = select(Team)
            if kwargs.get("league_id"):
                stmt = stmt.where(Team.country == kwargs.get("country") or Team.country.isnot(None))
            stmt = stmt.order_by(Team.name)
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()
            return {
                "data": [
                    {
                        "id": row.id,
                        "name": row.name,
                        "short_name": row.short_name,
                        "slug": row.slug,
                        "logo_url": row.logo_url,
                        "country": row.country,
                    }
                    for row in rows
                ],
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
                },
            }

        if provider_method == "get_standings":
            stmt = select(TeamStatistics)
            if kwargs.get("league_id"):
                stmt = stmt.where(TeamStatistics.league_id == kwargs["league_id"])
            if kwargs.get("season_id"):
                stmt = stmt.where(TeamStatistics.season_id == kwargs["season_id"])
            stmt = stmt.order_by(TeamStatistics.position)
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()
            return {
                "data": [
                    {
                        "provider_team_id": row.provider_team_id,
                        "league_id": row.league_id,
                        "season_id": row.season_id,
                        "position": row.position,
                        "points": row.points,
                        "wins": row.wins,
                        "draws": row.draws,
                        "losses": row.losses,
                        "goals_for": row.goals_for,
                        "goals_against": row.goals_against,
                    }
                    for row in rows
                ],
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
                },
            }

        if provider_method == "get_fixtures":
            stmt = select(Match)
            if kwargs.get("league_id"):
                stmt = stmt.where(Match.league_id == kwargs["league_id"])
            if kwargs.get("season_id"):
                stmt = stmt.where(Match.season_id == kwargs["season_id"])
            if kwargs.get("team_id"):
                stmt = stmt.where(
                    (Match.home_team_id == kwargs["team_id"])
                    | (Match.away_team_id == kwargs["team_id"])
                )
            stmt = stmt.order_by(Match.kickoff_at)
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()
            return {
                "data": [
                    {
                        "id": row.id,
                        "league_id": row.league_id,
                        "season_id": row.season_id,
                        "home_team_id": row.home_team_id,
                        "away_team_id": row.away_team_id,
                        "home_team_name": row.home_team_name,
                        "away_team_name": row.away_team_name,
                        "kickoff_at": row.kickoff_at.isoformat() if row.kickoff_at else None,
                        "status": row.status,
                        "home_score": row.home_score,
                        "away_score": row.away_score,
                        "is_finished": row.is_finished,
                    }
                    for row in rows
                ],
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
                },
            }

        if provider_method == "get_players":
            stmt = select(Player)
            if kwargs.get("team_id"):
                stmt = stmt.where(Player.team_id == kwargs["team_id"])
            stmt = stmt.order_by(Player.full_name)
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()
            return {
                "data": [
                    {
                        "id": row.id,
                        "provider_player_id": row.provider_player_id,
                        "team_id": row.team_id,
                        "full_name": row.full_name,
                        "position": row.position,
                        "nationality": row.nationality,
                    }
                    for row in rows
                ],
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
                },
            }

        if provider_method == "get_injuries":
            stmt = select(Injury)
            if kwargs.get("team_id"):
                stmt = stmt.where(Injury.internal_team_id == kwargs["team_id"])
            if kwargs.get("fixture_id"):
                stmt = stmt.where(Injury.provider_metadata.isnot(None))
            stmt = stmt.order_by(Injury.player_name)
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()
            return {
                "data": [
                    {
                        "id": row.id,
                        "player_name": row.player_name,
                        "position": row.position,
                        "injury_type": row.injury_type,
                        "severity": row.severity,
                        "description": row.description,
                    }
                    for row in rows
                ],
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
                },
            }

        if provider_method == "get_sidelined":
            stmt = select(Suspension)
            if kwargs.get("team_id"):
                stmt = stmt.where(Suspension.internal_team_id == kwargs["team_id"])
            if kwargs.get("fixture_id"):
                stmt = stmt.where(Suspension.provider_metadata.isnot(None))
            stmt = stmt.order_by(Suspension.player_name)
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()
            return {
                "data": [
                    {
                        "id": row.id,
                        "player_name": row.player_name,
                        "position": row.position,
                        "reason": row.reason,
                        "suspension_type": row.suspension_type,
                    }
                    for row in rows
                ],
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
                },
            }

        return {"data": [], "meta": {"page": 1, "page_size": page_size, "total": 0, "total_pages": 1}}


async def _fetch_and_save_provider_data(provider_method: str, **kwargs: Any) -> dict[str, Any]:
    """Fetch data from provider, save to database, return paginated response."""
    page = kwargs.get("page", 1)
    page_size = kwargs.get("page_size", 50)
    
    provider = get_football_provider()
    await provider.connect()
    try:
        provider_payload = await getattr(provider, provider_method)(**kwargs)
    finally:
        await provider.close()

    if provider_payload is None:
        provider_payload = []
    if not isinstance(provider_payload, list):
        provider_payload = [provider_payload]

    # Save to database
    await _save_provider_data_to_db(provider_method, provider_payload)

    # Return paginated response
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "data": provider_payload[start:end],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": len(provider_payload),
            "total_pages": max(1, -(-len(provider_payload) // page_size)) if page_size > 0 else 1,
        },
    }


async def _save_provider_data_to_db(provider_method: str, provider_payload: list[Any]) -> None:
    """Save provider data to database using upsert logic."""
    if not provider_payload:
        return

    async with AsyncSessionLocal() as db:
        try:
            if provider_method == "get_leagues":
                await _save_leagues(db, provider_payload)
            elif provider_method == "get_seasons":
                await _save_seasons(db, provider_payload)
            elif provider_method == "get_teams":
                await _save_teams(db, provider_payload)
            elif provider_method == "get_standings":
                await _save_standings(db, provider_payload)
            elif provider_method == "get_fixtures":
                await _save_fixtures(db, provider_payload)
            elif provider_method == "get_players":
                await _save_players(db, provider_payload)
            elif provider_method == "get_injuries":
                await _save_injuries(db, provider_payload)
            elif provider_method == "get_sidelined":
                await _save_suspensions(db, provider_payload)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error(f"Error saving {provider_method} to DB: {exc}")


async def _save_leagues(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert leagues from provider data."""
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()
        
        provider_league_id = item.get("provider_league_id") or item.get("id")
        if not provider_league_id:
            continue
            
        existing = await db.get(League, provider_league_id)
        if existing is None:
            league = League(
                id=provider_league_id,
                name=item.get("name"),
                country=item.get("country"),
                country_code=item.get("country_code"),
                is_active=True,
            )
            db.add(league)
        else:
            existing.name = item.get("name", existing.name)
            existing.country = item.get("country", existing.country)
            existing.country_code = item.get("country_code", existing.country_code)
        
        # Update provider mapping
        provider_name = item.get("provider", "api_football")
        provider_mapping = await db.execute(
            select(ProviderLeague).where(
                ProviderLeague.provider_league_id == provider_league_id,
                ProviderLeague.provider_name == provider_name,
            )
        )
        existing_mapping = provider_mapping.scalar_one_or_none()
        if existing_mapping is None:
            db.add(ProviderLeague(
                internal_league_id=provider_league_id,
                provider_name=provider_name,
                provider_league_id=provider_league_id,
                is_active=True,
            ))


async def _save_seasons(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert seasons from provider data."""
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()
        
        provider_season_id = item.get("provider_season_id") or item.get("id")
        league_id = item.get("league_id")
        if not provider_season_id or not league_id:
            continue
            
        existing = await db.get(Season, provider_season_id)
        if existing is None:
            if item.get("is_current"):
                await db.execute(
                    update(Season)
                    .where(Season.league_id == league_id)
                    .values(is_current=False)
                )
            db.add(Season(
                id=provider_season_id,
                league_id=league_id,
                name=item.get("name") or str(item.get("year")),
                year=item.get("year"),
                start_date=item.get("start_date"),
                end_date=item.get("end_date"),
                is_current=item.get("is_current", False),
            ))
        else:
            existing.is_current = item.get("is_current", existing.is_current)
            existing.year = item.get("year", existing.year)
            if item.get("start_date"):
                existing.start_date = item.get("start_date")
            if item.get("end_date"):
                existing.end_date = item.get("end_date")


async def _save_teams(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert teams from provider data."""
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()
        
        provider_team_id = item.get("provider_team_id") or item.get("id")
        if not provider_team_id:
            continue
            
        existing = await db.get(Team, provider_team_id)
        if existing is None:
            db.add(Team(
                id=provider_team_id,
                name=item.get("name"),
                short_name=item.get("short_name"),
                slug=item.get("slug"),
                logo_url=item.get("logo_url"),
                venue_name=item.get("venue_name"),
                venue_city=item.get("venue_city"),
                country=item.get("country"),
                is_active=True,
            ))
        else:
            if item.get("name"):
                existing.name = item.get("name")
            if item.get("short_name"):
                existing.short_name = item.get("short_name")
            if item.get("logo_url"):
                existing.logo_url = item.get("logo_url")
        
        provider_name = item.get("provider", "api_football")
        stmt = (
            insert(ProviderTeam.__table__)
            .values(
                internal_team_id=provider_team_id,
                provider_name=provider_name,
                provider_team_id=provider_team_id,
                is_active=True,
            )
            .on_conflict_do_nothing()
        )
        await db.execute(stmt)


async def _save_standings(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert standings/team statistics from provider data."""
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()
        
        provider_name = item.get("provider", "api_football")
        provider_team_id = item.get("provider_team_id") or item.get("team_id")
        league_id = item.get("league_id")
        season_id = item.get("season_id")
        
        if not provider_team_id or not league_id or not season_id:
            continue
        
        existing_stmt = select(TeamStatistics).where(
            TeamStatistics.provider_name == provider_name,
            TeamStatistics.provider_team_id == provider_team_id,
            TeamStatistics.league_id == league_id,
            TeamStatistics.season_id == season_id,
        )
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()
        
        if existing is None:
            db.execute(
                insert(TeamStatistics.__table__).values(
                    provider_name=provider_name,
                    provider_team_id=provider_team_id,
                    internal_team_id=item.get("team_id"),
                    league_id=league_id,
                    season_id=season_id,
                    is_home=False,
                    games_played=item.get("played"),
                    wins=item.get("wins"),
                    draws=item.get("draws"),
                    losses=item.get("losses"),
                    goals_for=item.get("goals_for"),
                    goals_against=item.get("goals_against"),
                    points=item.get("points"),
                    position=item.get("position"),
                    form_rating=item.get("form_rating") or item.get("form"),
                    retrieved_at=datetime.utcnow(),
                    provider_metadata=item.get("provider_metadata", {}),
                )
            )
        else:
            existing.points = item.get("points", existing.points)
            existing.position = item.get("position", existing.position)
            existing.wins = item.get("wins", existing.wins)
            existing.draws = item.get("draws", existing.draws)
            existing.losses = item.get("losses", existing.losses)
            existing.goals_for = item.get("goals_for", existing.goals_for)
            existing.goals_against = item.get("goals_against", existing.goals_against)
            existing.retrieved_at = datetime.utcnow()
            existing.provider_metadata = item.get("provider_metadata", {})


async def _save_fixtures(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert fixtures from provider data."""
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()
        
        provider_fixture_id = item.get("provider_fixture_id") or item.get("id")
        if not provider_fixture_id:
            continue
        
        provider_name = item.get("provider", "api_football")
        status_val = item.get("status")
        if hasattr(status_val, "value"):
            status_val = status_val.value
        
        existing = await db.get(Match, provider_fixture_id)
        if existing is None:
            db.add(Match(
                id=provider_fixture_id,
                provider_name=provider_name,
                provider_fixture_id=provider_fixture_id,
                league_id=item.get("league_id"),
                season_id=item.get("season_id"),
                home_team_id=item.get("home_team_id"),
                away_team_id=item.get("away_team_id"),
                home_team_name=item.get("home_team_name"),
                away_team_name=item.get("away_team_name"),
                kickoff_at=item.get("kickoff_at"),
                status=status_val or "scheduled",
                venue=item.get("venue"),
                referee=item.get("referee"),
                home_score=item.get("home_score"),
                away_score=item.get("away_score"),
                is_finished=item.get("is_finished", False),
                retrieved_at=item.get("retrieved_at", datetime.utcnow()),
                provider_metadata=item.get("provider_metadata", {}),
            ))
        else:
            existing.home_score = item.get("home_score", existing.home_score)
            existing.away_score = item.get("away_score", existing.away_score)
            existing.status = status_val or existing.status
            existing.is_finished = item.get("is_finished", existing.is_finished)
            existing.retrieved_at = datetime.utcnow()
            existing.kickoff_at = item.get("kickoff_at", existing.kickoff_at)


async def _save_players(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert players from provider data."""
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()
        
        provider_player_id = item.get("provider_player_id") or item.get("id")
        if not provider_player_id:
            continue
        
        provider_name = item.get("provider", "api_football")
        existing = await db.get(Player, provider_player_id)
        if existing is None:
            db.add(Player(
                id=provider_player_id,
                provider_name=provider_name,
                provider_player_id=provider_player_id,
                team_id=item.get("team_id"),
                first_name=item.get("first_name"),
                last_name=item.get("last_name"),
                full_name=item.get("full_name"),
                position=item.get("position"),
                date_of_birth=item.get("date_of_birth"),
                nationality=item.get("nationality"),
                height=item.get("height"),
                weight=item.get("weight"),
                footed=item.get("footed"),
                retrieved_at=datetime.utcnow(),
                provider_metadata=item.get("provider_metadata", {}),
            ))


async def _save_injuries(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert injuries from provider data."""
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()
        
        provider_player_id = item.get("provider_player_id")
        provider_team_id = item.get("provider_team_id")
        if not provider_player_id and not provider_team_id:
            continue
        
        provider_name = item.get("provider", "api_football")
        injury = Injury(
            provider_name=provider_name,
            provider_player_id=provider_player_id,
            provider_team_id=provider_team_id,
            internal_team_id=item.get("team_id"),
            player_name=item.get("player_name"),
            position=item.get("position"),
            injury_type=item.get("injury_type"),
            severity=item.get("severity"),
            description=item.get("description"),
            start_date=item.get("start_date"),
            return_date=item.get("return_date"),
            is_startingXI_impact=item.get("is_startingXI_impact", False),
            retrieved_at=datetime.utcnow(),
            provider_metadata=item.get("provider_metadata", {}),
        )
        db.add(injury)


async def _save_suspensions(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert suspensions from provider data."""
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()
        
        provider_player_id = item.get("provider_player_id")
        provider_team_id = item.get("provider_team_id")
        if not provider_player_id and not provider_team_id:
            continue
        
        provider_name = item.get("provider", "api_football")
        suspension = Suspension(
            provider_name=provider_name,
            provider_player_id=provider_player_id,
            provider_team_id=provider_team_id,
            internal_team_id=item.get("team_id"),
            player_name=item.get("player_name"),
            position=item.get("position"),
            reason=item.get("reason"),
            suspension_type=item.get("suspension_type"),
            suspended_from=item.get("suspended_from"),
            suspended_until=item.get("suspended_until"),
            retrieved_at=datetime.utcnow(),
            provider_metadata=item.get("provider_metadata", {}),
        )
        db.add(suspension)


async def _provider_data_response(
    provider_method: str,
    **kwargs: Any,
) -> dict[str, Any]:
    kwargs = dict(kwargs)
    if "league_id" in kwargs:
        kwargs["league_id"] = _resolve_provider_league_id(kwargs["league_id"])

    resource_methods = {
        "get_leagues",
        "get_seasons",
        "get_teams",
        "get_standings",
        "get_fixtures",
        "get_players",
        "get_injuries",
        "get_sidelined",
    }

    if provider_method in resource_methods:
        # Try to read from database first
        db_payload = await _read_db_resource_payload(provider_method, **kwargs)
        if db_payload and db_payload.get("data"):
            # Data exists in DB, return it
            return {
                "success": True,
                "data": db_payload["data"],
                "meta": {**db_payload.get("meta", {}), "source": "database"},
            }
        
        # DB is empty, fetch from provider and save
        provider_data = await _fetch_and_save_provider_data(provider_method, **kwargs)
        if provider_data:
            return {
                "success": True,
                "data": provider_data["data"],
                "meta": {**provider_data.get("meta", {}), "source": "provider"},
            }

    # For other methods, just fetch from provider
    provider = get_football_provider()
    await provider.connect()
    try:
        data = await getattr(provider, provider_method)(**kwargs)
        if data is None:
            payload: list[dict[str, Any]] = []
        elif isinstance(data, list):
            payload = [_transform_provider_data(provider_method, item) for item in data]
        else:
            payload = [_transform_provider_data(provider_method, data)]

        page = kwargs.get("page", 1)
        page_size = kwargs.get("page_size", 50)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_data = payload[start:end]

        return {
            "success": True,
            "data": paginated_data,
            "meta": {
                "page": page,
                "page_size": page_size,
                "total": len(payload),
                "total_pages": max(1, -(-len(payload) // page_size)) if page_size > 0 else 1,
            },
        }
    finally:
        await provider.close()


def _transform_provider_data(provider_method: str, item: Any) -> dict[str, Any]:
    """Transform provider data to match web API types."""
    if hasattr(item, "model_dump"):
        item = item.model_dump()
    elif hasattr(item, "dict"):
        item = item.dict()

    if provider_method == "get_leagues":
        return {
            "id": item.get("provider_league_id") or item.get("id") or item.get("internal_id"),
            "name": item.get("name"),
            "country": item.get("country"),
            "country_code": item.get("country_code"),
            "is_active": True,
            "created_at": None,
        }
    elif provider_method == "get_seasons":
        return {
            "id": item.get("provider_season_id") or item.get("id") or item.get("internal_id"),
            "league_id": item.get("league_id"),
            "name": item.get("name"),
            "year": item.get("year"),
            "start_date": item.get("start_date"),
            "end_date": item.get("end_date"),
            "is_current": item.get("is_current", False),
        }
    elif provider_method == "get_teams":
        return {
            "id": item.get("provider_team_id") or item.get("id") or item.get("internal_id"),
            "name": item.get("name"),
            "short_name": item.get("short_name"),
            "slug": item.get("slug"),
            "logo_url": item.get("logo_url"),
            "country": item.get("country"),
            "is_active": True,
            "created_at": None,
        }
    elif provider_method == "get_fixtures":
        return {
            "id": item.get("provider_fixture_id") or item.get("id") or item.get("internal_id"),
            "league_id": item.get("league_id"),
            "season_id": item.get("season_id"),
            "home_team_id": item.get("home_team_id"),
            "away_team_id": item.get("away_team_id"),
            "home_team_name": item.get("home_team_name"),
            "away_team_name": item.get("away_team_name"),
            "kickoff_at": item.get("kickoff_at"),
            "status": item.get("status"),
            "venue": item.get("venue"),
            "home_score": item.get("home_score"),
            "away_score": item.get("away_score"),
            "is_finished": item.get("is_finished", False),
        }
    elif provider_method == "get_players":
        return {
            "id": item.get("provider_player_id") or item.get("id") or item.get("internal_id"),
            "provider_player_id": item.get("provider_player_id"),
            "team_id": item.get("team_id"),
            "full_name": item.get("full_name"),
            "position": item.get("position"),
            "nationality": item.get("nationality"),
        }
    elif provider_method == "get_injuries":
        return {
            "id": item.get("id") or item.get("internal_id"),
            "player_name": item.get("player_name"),
            "position": item.get("position"),
            "injury_type": item.get("injury_type"),
            "severity": item.get("severity"),
            "description": item.get("description"),
        }
    elif provider_method == "get_sidelined":
        return {
            "id": item.get("id") or item.get("internal_id"),
            "player_name": item.get("player_name"),
            "position": item.get("position"),
            "reason": item.get("reason"),
            "suspension_type": item.get("suspension_type"),
        }
    elif provider_method == "get_standings":
        return item

    return item


class ProviderStatusResponse(BaseModel):
    active_provider: str
    providers: dict[str, NormalizedProviderStatus] = Field(default_factory=dict)


@router.get("/providers/status", response_model=ProviderStatusResponse, tags=["providers"])
async def providers_status() -> ProviderStatusResponse:
    """Return the configuration and health of every football data provider."""
    settings = get_settings()
    result: dict[str, NormalizedProviderStatus] = {}

    for name in SUPPORTED_PROVIDERS:
        provider_name = name
        if provider_name == "api_football":
            configured = bool(settings.api_football_key)
        else:
            configured = bool(
                getattr(
                    settings,
                    {
                        "sportmonks": "sportmonks_api_token",
                    }[provider_name],
                )
            )

        status = NormalizedProviderStatus(
            name=provider_name,
            configured=configured,
            healthy=False,
            last_checked=datetime.utcnow(),
        )

        if configured:
            provider = get_provider_for_name(provider_name)
            if provider is not None:
                try:
                    is_healthy = await provider.health_check()
                    status.healthy = is_healthy
                except Exception as exc:
                    status.healthy = False
                    status.error = str(exc)
                finally:
                    try:
                        await provider.close()
                    except Exception:
                        pass
            else:
                status.error = "Could not instantiate provider."
        else:
            status.healthy = False
            status.error = "Credentials not configured."

        result[provider_name] = status

    return ProviderStatusResponse(
        active_provider=settings.football_data_provider,
        providers=result,
    )


@router.get("/providers/timezones", tags=["providers"])
async def provider_timezones() -> dict[str, Any]:
    return await _provider_data_response("get_timezones")


@router.get("/providers/countries", tags=["providers"])
async def provider_countries() -> dict[str, Any]:
    return await _provider_data_response("get_countries")


@router.get("/providers/leagues", tags=["providers"])
async def provider_leagues(
    country: str | None = Query(None),
    season: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if country:
        params["country"] = country
    if season:
        params["season"] = season
    return await _provider_data_response("get_leagues", **params)


@router.get("/providers/leagues/{league_id}", tags=["providers"])
async def provider_league_by_id(league_id: str) -> dict[str, Any]:
    """Return a single league by provider league id, e.g. 39 for Premier League."""
    return await _provider_data_response("get_league", league_id=league_id)


@router.post("/providers/sync/database", tags=["providers"])
async def sync_provider_database(
    _admin: str = Depends(verify_admin_api_key),
) -> dict[str, Any]:
    """Fetch provider data and persist it to the local database.

    This is the Swagger-triggered equivalent of the scheduled daily sync job.
    """
    try:
        await run_daily_sync()
        return {
            "success": True,
            "data": {"synced": True},
            "meta": {"message": "Provider data synced to database successfully."},
        }
    except Exception as exc:
        logger.exception("Provider database sync failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Provider sync failed: {exc}",
        ) from exc


@router.get("/providers/leagues/seasons", tags=["providers"])
async def provider_league_seasons(league_id: str) -> dict[str, Any]:
    resolved_league_id = _resolve_provider_league_id(league_id)
    return await _provider_data_response("get_seasons", league_id=resolved_league_id)


@router.get("/providers/teams", tags=["providers"])
async def provider_teams(
    league_id: str | None = Query(None),
    season_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_teams", league_id=league_id, season_id=season_id)


@router.get("/providers/venues", tags=["providers"])
async def provider_venues(
    venue_id: str | None = Query(None),
    team_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_venues", venue_id=venue_id, team_id=team_id)


@router.get("/providers/standings", tags=["providers"])
async def provider_standings(
    league_id: str | None = Query(None),
    season_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_standings", league_id=league_id, season_id=season_id)


@router.get("/providers/fixtures", tags=["providers"])
async def provider_fixtures(
    league_id: str | None = Query(None),
    season_id: str | None = Query(None),
    team_id: str | None = Query(None),
    fixture_id: str | None = Query(None),
) -> dict[str, Any]:
    params: dict[str, Any] = {"league_id": league_id, "season_id": season_id, "team_id": team_id}
    if fixture_id:
        return await _provider_data_response("get_fixture", fixture_id=fixture_id)
    return await _provider_data_response(
        "get_fixtures", **{k: v for k, v in params.items() if v is not None}
    )


@router.get("/providers/injuries", tags=["providers"])
async def provider_injuries(
    team_id: str | None = Query(None),
    fixture_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_injuries", team_id=team_id, fixture_id=fixture_id)


@router.get("/providers/predictions", tags=["providers"])
async def provider_predictions(fixture_id: str = Query(...)) -> dict[str, Any]:
    return await _provider_data_response("get_predictions", fixture_id=fixture_id)


@router.get("/providers/coaches", tags=["providers"])
async def provider_coaches(
    team_id: str | None = Query(None),
    coach_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_coaches", team_id=team_id, coach_id=coach_id)


@router.get("/providers/players", tags=["providers"])
async def provider_players(
    team_id: str | None = Query(None),
    player_id: str | None = Query(None),
) -> dict[str, Any]:
    params: dict[str, Any] = {"team_id": team_id} if team_id else {}
    if player_id:
        return await _provider_data_response("get_team", team_id=player_id)
    return await _provider_data_response("get_players", **params)


@router.get("/providers/transfers", tags=["providers"])
async def provider_transfers(
    player_id: str | None = Query(None),
    team_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_transfers", player_id=player_id, team_id=team_id)


@router.get("/providers/trophies", tags=["providers"])
async def provider_trophies(
    player_id: str | None = Query(None),
    team_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_trophies", player_id=player_id, team_id=team_id)


@router.get("/providers/sidelined", tags=["providers"])
async def provider_sidelined(
    team_id: str | None = Query(None),
    fixture_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_sidelined", team_id=team_id, fixture_id=fixture_id)


@router.get("/providers/odds/pre-match", tags=["providers"])
async def provider_odds_pre_match(
    fixture_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_pre_match_odds", fixture_id=fixture_id)


@router.get("/providers/odds/in-play", tags=["providers"])
async def provider_odds_in_play(
    fixture_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_in_play_odds", fixture_id=fixture_id)


@router.get("/providers/odds/preplay", tags=["providers"])
async def provider_odds_preplay(
    fixture_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_pre_match_odds", fixture_id=fixture_id)


@router.get("/providers/odds/inplay", tags=["providers"])
async def provider_odds_inplay(
    fixture_id: str | None = Query(None),
) -> dict[str, Any]:
    return await _provider_data_response("get_in_play_odds", fixture_id=fixture_id)
