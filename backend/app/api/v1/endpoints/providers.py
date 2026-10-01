"""Provider endpoints.

GET  /api/v1/providers/status  -- health of all configured providers
GET  /api/v1/providers/timezones -- API-Football timezone metadata
GET  /api/v1/providers/countries -- API-Football country list
GET  /api/v1/providers/leagues -- direct provider league list
GET  /api/v1/providers/leagues/{league_id} -- single league by provider id
GET  /api/v1/providers/leagues/seasons -- direct provider season list
GET  /api/v1/providers/teams -- direct provider team list
GET  /api/v1/providers/venues -- direct provider venue list
GET  /api/v1/providers/standings -- direct provider standings list
GET  /api/v1/providers/fixtures -- direct provider fixtures list
GET  /api/v1/providers/injuries -- direct provider injuries list
GET  /api/v1/providers/odds/pre-match -- direct provider pre-match odds list
GET  /api/v1/providers/odds/in-play -- direct provider in-play odds list
POST /api/v1/providers/sync/database -- sync all provider data to database
POST /api/v1/providers/sync/leagues -- sync leagues to database
POST /api/v1/providers/sync/seasons -- sync seasons to database
POST /api/v1/providers/sync/teams -- sync teams to database
POST /api/v1/providers/sync/fixtures -- sync fixtures to database
POST /api/v1/providers/sync/standings -- sync standings to database
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.logging import get_logger
from core.security import verify_admin_api_key
from db.database import AsyncSessionLocal
from football_data.factory import SUPPORTED_PROVIDERS, get_football_provider, get_provider_for_name
from football_data.league_mappings import LeagueMapping
from football_data.models import NormalizedProviderStatus
from models.league import League, ProviderLeague, ProviderTeam, Season, Team
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


def _parse_date_arg(value: Any) -> date | None:
    """Parse a ``YYYY-MM-DD`` string (or date/datetime) into a ``date``."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _resolve_fixture_window(kwargs: dict[str, Any]) -> tuple[date | None, date | None]:
    """Resolve the public date filters into an inclusive ``(from_date, to_date)`` window.

    Accepts ``date`` (single day), ``date_from`` / ``date_to`` (range) and, for
    ``today`` / ``upcoming``, an implied window (``days`` horizon from today).
    The same window is handed to the provider via ``from_date`` / ``to_date``.
    """
    start = _parse_date_arg(kwargs.get("date_from"))
    end = _parse_date_arg(kwargs.get("date_to"))

    single = _parse_date_arg(kwargs.get("date"))
    if single is not None:
        start = single
        end = single

    if kwargs.get("today"):
        today = datetime.utcnow().date()
        start, end = today, today

    if kwargs.get("upcoming"):
        today = datetime.utcnow().date()
        try:
            days = int(kwargs.get("days") or 7)
        except (TypeError, ValueError):
            days = 7
        start = start or today
        end = end or (today + timedelta(days=days))

    return start, end


def _current_season_ids() -> Any:
    """Select of every season id flagged as current, across all leagues.

    Each league carries its own current season, so a league-agnostic query
    (the fixtures list, the teams list) scopes to the set of current seasons
    rather than a single one.
    """
    return select(Season.id).where(Season.is_current.is_(True))


def _map_filters_for_provider(provider_method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Translate the public query filters into provider-native kwargs.

    Only fixture lookups are remapped: providers expect ``from_date`` /
    ``to_date`` as date objects and have no concept of the public ``date`` /
    ``date_from`` / ``date_to`` / ``days`` names.  Every other provider method
    receives ``kwargs`` unchanged, since its filters are already provider-native
    (``include``, ``country``, ``team_id``, ...).
    """
    if provider_method not in ("get_fixtures", "get_fixture"):
        return kwargs

    passthrough = {
        "league_id",
        "season_id",
        "team_id",
        "fixture_id",
        "status",
        "today",
        "upcoming",
        "days",
        "last_n",
    }
    mapped = {k: v for k, v in kwargs.items() if k in passthrough and v is not None}

    start, end = _resolve_fixture_window(kwargs)
    if start is not None:
        mapped["from_date"] = start
    if end is not None:
        mapped["to_date"] = end
    return mapped


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
        provider_ids = cfg.provider_ids.get(provider_name) or cfg.provider_ids.get("sportmonks")
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
            if kwargs.get("is_active") is not None:
                stmt = stmt.where(League.is_active.is_(kwargs["is_active"]))
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

        if provider_method == "get_league":
            league_id = kwargs.get("league_id")
            if league_id:
                stmt = select(League).where(League.id == league_id)
                row = (await db.execute(stmt)).scalar_one_or_none()
                if row:
                    cs_stmt = (
                        select(Season)
                        .where(Season.league_id == league_id, Season.is_current.is_(True))
                        .limit(1)
                    )
                    cs = (await db.execute(cs_stmt)).scalar_one_or_none()
                    current_season = None
                    if cs:
                        current_season = {
                            "id": cs.id,
                            "name": cs.name,
                            "year": cs.year,
                            "is_current": cs.is_current,
                        }
                    return {
                        "data": [
                            {
                                "id": row.id,
                                "name": row.name,
                                "country": row.country,
                                "country_code": row.country_code,
                                "is_active": row.is_active,
                                "created_at": row.created_at.isoformat()
                                if row.created_at
                                else None,
                                "current_season": current_season,
                            }
                        ],
                        "meta": {
                            "page": 1,
                            "page_size": 1,
                            "total": 1,
                            "total_pages": 1,
                        },
                    }
            return {
                "data": [],
                "meta": {"page": 1, "page_size": 1, "total": 0, "total_pages": 1},
            }

        if provider_method == "get_team":
            team_id = kwargs.get("team_id")
            if team_id:
                stmt = select(Team).where(Team.id == team_id)
                row = (await db.execute(stmt)).scalar_one_or_none()
                if row:
                    return {
                        "data": [
                            {
                                "id": row.id,
                                "name": row.name,
                                "short_name": row.short_name,
                                "slug": row.slug,
                                "logo_url": row.logo_url,
                                "venue_name": row.venue_name,
                                "venue_city": row.venue_city,
                                "country": row.country,
                                "is_active": row.is_active,
                            }
                        ],
                        "meta": {"page": 1, "page_size": 1, "total": 1, "total_pages": 1},
                    }
            return {
                "data": [],
                "meta": {"page": 1, "page_size": 1, "total": 0, "total_pages": 1},
            }

        if provider_method == "get_fixture":
            fixture_id = kwargs.get("fixture_id")
            if fixture_id:
                stmt = select(Match).where(Match.id == fixture_id)
                row = (await db.execute(stmt)).scalar_one_or_none()
                if row:
                    league_name = None
                    if row.league_id:
                        ln_result = await db.execute(
                            select(League.name).where(League.id == row.league_id)
                        )
                        league_name = ln_result.scalar_one_or_none()
                    return {
                        "data": [
                            {
                                "id": row.id,
                                "league_id": row.league_id,
                                "league_name": league_name,
                                "season_id": row.season_id,
                                "home_team_id": row.home_team_id,
                                "away_team_id": row.away_team_id,
                                "home_team_name": row.home_team_name,
                                "away_team_name": row.away_team_name,
                                "kickoff_at": row.kickoff_at.isoformat()
                                if row.kickoff_at
                                else None,
                                "status": row.status,
                                "venue": row.venue,
                                "home_score": row.home_score,
                                "away_score": row.away_score,
                                "is_finished": row.is_finished,
                                "retrieved_at": row.retrieved_at.isoformat()
                                if row.retrieved_at
                                else None,
                            }
                        ],
                        "meta": {"page": 1, "page_size": 1, "total": 1, "total_pages": 1},
                    }
            return {
                "data": [],
                "meta": {"page": 1, "page_size": 1, "total": 0, "total_pages": 1},
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
            from core.config import get_settings as _get_settings

            _provider = kwargs.get("provider") or _get_settings().football_data_provider
            stmt = select(Team)
            if kwargs.get("league_id"):
                stmt = (
                    select(Team)
                    .join(ProviderTeam, ProviderTeam.internal_team_id == Team.id)
                    .where(ProviderTeam.provider_league_id == kwargs["league_id"])
                    .where(ProviderTeam.provider_name == _provider)
                    .distinct(Team.id)
                )
            if kwargs.get("season_id"):
                # Applies with or without a league filter.
                if not kwargs.get("league_id"):
                    stmt = stmt.join(
                        ProviderTeam, ProviderTeam.internal_team_id == Team.id
                    )
                stmt = stmt.where(ProviderTeam.season_id == kwargs["season_id"])
                if not kwargs.get("league_id"):
                    stmt = stmt.distinct(Team.id)
            elif not kwargs.get("all_seasons"):
                # EXISTS avoids multiplying rows for teams mapped to several
                # seasons, so no DISTINCT is needed on this path.
                stmt = stmt.where(
                    select(ProviderTeam.internal_team_id)
                    .where(
                        ProviderTeam.internal_team_id == Team.id,
                        ProviderTeam.provider_name == _provider,
                        ProviderTeam.season_id.in_(_current_season_ids()),
                    )
                    .exists()
                )
            if kwargs.get("is_active") is not None:
                stmt = stmt.where(Team.is_active.is_(kwargs["is_active"]))
            if kwargs.get("search"):
                term = f"%{str(kwargs['search']).strip()}%"
                stmt = stmt.where(
                    or_(
                        Team.name.ilike(term),
                        Team.short_name.ilike(term),
                        Team.slug.ilike(term),
                    )
                )
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
                        "venue_name": row.venue_name,
                        "venue_city": row.venue_city,
                        "country": row.country,
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

        if provider_method in ("get_standings", "get_team_statistics"):
            stmt = select(TeamStatistics, Team.name).outerjoin(
                Team, Team.id == TeamStatistics.internal_team_id
            )
            if kwargs.get("team_id"):
                stmt = stmt.where(
                    or_(
                        TeamStatistics.internal_team_id == kwargs["team_id"],
                        TeamStatistics.provider_team_id == kwargs["team_id"],
                    )
                )
            if kwargs.get("league_id"):
                stmt = stmt.where(TeamStatistics.league_id == kwargs["league_id"])
            if kwargs.get("season_id"):
                stmt = stmt.where(TeamStatistics.season_id == kwargs["season_id"])
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.order_by(TeamStatistics.position)
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).all()
            return {
                "data": [
                    {
                        "team_id": stats.internal_team_id or stats.provider_team_id,
                        "team_name": team_name or f"Team {stats.provider_team_id}",
                        "provider_team_id": stats.provider_team_id,
                        "league_id": stats.league_id,
                        "season_id": stats.season_id,
                        "position": stats.position,
                        "points": stats.points,
                        "played": stats.games_played,
                        "games_played": stats.games_played,
                        "wins": stats.wins,
                        "draws": stats.draws,
                        "losses": stats.losses,
                        "goals_for": stats.goals_for,
                        "goals_against": stats.goals_against,
                        "goal_difference": (stats.goals_for or 0) - (stats.goals_against or 0),
                        "clean_sheets": stats.clean_sheets,
                        "is_home": stats.is_home,
                        "form": stats.form_rating,
                        "form_rating": stats.form_rating,
                        "average_possession": stats.average_possession,
                        "average_shots": stats.average_shots,
                        "average_xg": stats.average_xg,
                        "average_xga": stats.average_xga,
                        "goals_per_game": stats.goals_per_game,
                        "goals_conceded_per_game": stats.goals_conceded_per_game,
                    }
                    for stats, team_name in rows
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
            elif not kwargs.get("all_seasons"):
                # Default to the current season of whichever league the fixture
                # belongs to, so finished campaigns drop off the matches page.
                stmt = stmt.where(Match.season_id.in_(_current_season_ids()))
            if kwargs.get("team_id"):
                stmt = stmt.where(
                    (Match.home_team_id == kwargs["team_id"])
                    | (Match.away_team_id == kwargs["team_id"])
                )
            if kwargs.get("status"):
                stmt = stmt.where(Match.status == kwargs["status"])
            if kwargs.get("upcoming"):
                stmt = stmt.where(
                    Match.is_finished.is_(False),
                    Match.kickoff_at.is_not(None),
                    Match.kickoff_at >= datetime.utcnow(),
                )
            window_start, window_end = _resolve_fixture_window(kwargs)
            if window_start is not None:
                stmt = stmt.where(Match.kickoff_at >= datetime.combine(window_start, time.min))
            if window_end is not None:
                stmt = stmt.where(Match.kickoff_at <= datetime.combine(window_end, time.max))
            stmt = stmt.order_by(Match.kickoff_at)
            count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar() or 0
            stmt = stmt.offset(offset).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()

            league_names: dict[str, str] = {}
            league_ids_to_fetch = {row.league_id for row in rows if row.league_id}
            if league_ids_to_fetch:
                league_name_result = await db.execute(
                    select(League.id, League.name).where(League.id.in_(league_ids_to_fetch))
                )
                league_names = {row.id: row.name for row in league_name_result.fetchall()}

            return {
                "data": [
                    {
                        "id": row.id,
                        "league_id": row.league_id,
                        "league_name": league_names.get(row.league_id) if row.league_id else None,
                        "season_id": row.season_id,
                        "home_team_id": row.home_team_id,
                        "away_team_id": row.away_team_id,
                        "home_team_name": row.home_team_name,
                        "away_team_name": row.away_team_name,
                        "kickoff_at": row.kickoff_at.isoformat() if row.kickoff_at else None,
                        "status": row.status,
                        "venue": row.venue,
                        "home_score": row.home_score,
                        "away_score": row.away_score,
                        "is_finished": row.is_finished,
                        "retrieved_at": row.retrieved_at.isoformat() if row.retrieved_at else None,
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

        return {
            "data": [],
            "meta": {"page": 1, "page_size": page_size, "total": 0, "total_pages": 1},
        }


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
            elif provider_method == "get_league":
                await _save_leagues(db, provider_payload)
            elif provider_method == "get_seasons":
                await _save_seasons(db, provider_payload)
            elif provider_method == "get_teams":
                await _save_teams(db, provider_payload)
            elif provider_method == "get_team":
                await _save_teams(db, provider_payload)
            elif provider_method == "get_fixture":
                await _save_fixtures(db, provider_payload)
            elif provider_method == "get_standings":
                await _save_standings(db, provider_payload)
            elif provider_method == "get_team_statistics":
                await _save_standings(db, provider_payload)
            elif provider_method == "get_fixtures":
                await _save_fixtures(db, provider_payload)
            elif provider_method == "get_players":
                await _save_players(db, provider_payload)
            elif provider_method == "get_injuries":
                await _save_injuries(db, provider_payload)
            elif provider_method == "get_sidelined":
                await _save_suspensions(db, provider_payload)
            elif provider_method in ("get_timezones", "get_countries"):
                pass  # No DB persistence for metadata endpoints
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
                provider_league_id=provider_league_id,
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
            if not existing.provider_league_id:
                existing.provider_league_id = provider_league_id

        # Update provider mapping
        provider_name = item.get("provider", "sportmonks")
        provider_mapping = await db.execute(
            select(ProviderLeague).where(
                ProviderLeague.provider_league_id == provider_league_id,
                ProviderLeague.provider_name == provider_name,
            )
        )
        existing_mapping = provider_mapping.scalar_one_or_none()
        if existing_mapping is None:
            db.add(
                ProviderLeague(
                    internal_league_id=provider_league_id,
                    provider_name=provider_name,
                    provider_league_id=provider_league_id,
                    is_active=True,
                )
            )


async def _save_seasons(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert seasons from provider data."""
    processed = []
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()

        provider_season_id = item.get("provider_season_id") or item.get("id")
        league_id = item.get("league_id")
        if not provider_season_id or not league_id:
            continue
        processed.append(
            {
                "id": provider_season_id,
                "league_id": league_id,
                "name": item.get("name") or str(item.get("year")),
                "year": item.get("year"),
                "start_date": item.get("start_date"),
                "end_date": item.get("end_date"),
                "is_current": item.get("is_current", False),
                "created_at": datetime.utcnow(),
            }
        )

    if not processed:
        return

    existing_ids = set((await db.execute(select(Season.id))).scalars().all())
    existing_current = set(
        (await db.execute(select(Season.id).where(Season.is_current.is_(True)))).scalars().all()
    )

    to_update_current = [s for s in processed if s["is_current"] and s["league_id"]]
    if to_update_current:
        leagues_to_clear = {s["league_id"] for s in to_update_current}
        for lg in leagues_to_clear:
            await db.execute(update(Season).where(Season.league_id == lg).values(is_current=False))

    to_insert = [s for s in processed if s["id"] not in existing_ids]
    to_update = [s for s in processed if s["id"] in existing_ids]

    if to_insert:
        await db.execute(insert(Season).values(to_insert))

    for s in to_update:
        await db.execute(
            update(Season)
            .where(Season.id == s["id"])
            .values(
                name=s["name"],
                league_id=s["league_id"],
                year=s["year"],
                start_date=s["start_date"],
                end_date=s["end_date"],
                is_current=s["is_current"],
            )
        )


async def _save_teams(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert teams and their provider mappings from provider data."""
    items: list[dict[str, Any]] = []
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()
        if item.get("provider_team_id") or item.get("id"):
            items.append(item)

    for item in items:
        provider_team_id = item.get("provider_team_id") or item.get("id")
        existing = await db.get(Team, provider_team_id)
        if existing is None:
            db.add(
                Team(
                    id=provider_team_id,
                    name=item.get("name"),
                    short_name=item.get("short_name"),
                    slug=item.get("slug"),
                    logo_url=item.get("logo_url"),
                    venue_name=item.get("venue_name"),
                    venue_city=item.get("venue_city"),
                    country=item.get("country"),
                    is_active=True,
                )
            )
        else:
            for field in (
                "name",
                "short_name",
                "slug",
                "logo_url",
                "venue_name",
                "venue_city",
                "country",
            ):
                value = item.get(field)
                if value:
                    setattr(existing, field, value)

    # provider_teams.internal_team_id references teams.id and the session runs
    # with autoflush=False, so the pending Team inserts must be flushed before
    # the mapping rows are written or the foreign key fails.
    await db.flush()

    for item in items:
        provider_team_id = item.get("provider_team_id") or item.get("id")
        provider_name = item.get("provider", "sportmonks")
        stmt = (
            pg_insert(ProviderTeam.__table__)
            .values(
                internal_team_id=provider_team_id,
                provider_name=provider_name,
                provider_team_id=provider_team_id,
                provider_league_id=item.get("league_id"),
                season_id=item.get("season_id"),
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=[
                    "internal_team_id",
                    "provider_name",
                    "provider_league_id",
                    "season_id",
                ],
                set_={"is_active": True, "provider_team_id": provider_team_id},
            )
        )
        await db.execute(stmt)


async def _save_standings(db: AsyncSession, payload: list[Any]) -> None:
    """Upsert standings/team statistics from provider data."""
    flat_standings: list[dict[str, Any]] = []
    for item in payload:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()

        if isinstance(item, dict) and "standings" in item and isinstance(item["standings"], list):
            parent_provider = item.get("provider", "sportmonks")
            parent_league_id = item.get("league_id")
            parent_season_id = item.get("season_id")
            for standing in item["standings"]:
                if hasattr(standing, "model_dump"):
                    standing = standing.model_dump()
                elif hasattr(standing, "dict"):
                    standing = standing.dict()
                if isinstance(standing, dict):
                    standing.setdefault("provider", parent_provider)
                    standing.setdefault("league_id", parent_league_id)
                    standing.setdefault("season_id", parent_season_id)
                    flat_standings.append(standing)
        else:
            flat_standings.append(item)

    for item in flat_standings:
        provider_name = item.get("provider", "sportmonks")
        provider_team_id = item.get("provider_team_id") or item.get("team_id")
        league_id = item.get("league_id")
        season_id = item.get("season_id")

        if not provider_team_id or not league_id or not season_id:
            continue

        internal_team_id = item.get("internal_team_id") or item.get("team_id")
        if not internal_team_id:
            mapping_stmt = select(ProviderTeam.internal_team_id).where(
                ProviderTeam.provider_name == provider_name,
                ProviderTeam.provider_team_id == provider_team_id,
            )
            if league_id:
                mapping_stmt = mapping_stmt.where(ProviderTeam.provider_league_id == league_id)
            if season_id:
                mapping_stmt = mapping_stmt.where(ProviderTeam.season_id == season_id)
            internal_team_id = (await db.execute(mapping_stmt.limit(1))).scalar_one_or_none()

        existing_stmt = select(TeamStatistics).where(
            TeamStatistics.provider_name == provider_name,
            TeamStatistics.provider_team_id == provider_team_id,
            TeamStatistics.league_id == league_id,
            TeamStatistics.season_id == season_id,
        )
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing is None:
            await db.execute(
                insert(TeamStatistics.__table__).values(
                    provider_name=provider_name,
                    provider_team_id=provider_team_id,
                    internal_team_id=internal_team_id,
                    league_id=league_id,
                    season_id=season_id,
                    is_home=False,
                    games_played=item.get("games_played", item.get("played")),
                    clean_sheets=item.get("clean_sheets"),
                    wins=item.get("wins"),
                    draws=item.get("draws"),
                    losses=item.get("losses"),
                    goals_for=item.get("goals_for"),
                    goals_against=item.get("goals_against"),
                    points=item.get("points"),
                    position=item.get("position"),
                    form_rating=item.get("form_rating") or item.get("form"),
                    average_possession=item.get("average_possession"),
                    average_shots=item.get("average_shots"),
                    average_xg=item.get("average_xg"),
                    average_xga=item.get("average_xga"),
                    goals_per_game=item.get("goals_per_game"),
                    goals_conceded_per_game=item.get("goals_conceded_per_game"),
                    retrieved_at=datetime.utcnow(),
                    provider_metadata=item.get("provider_metadata", {}),
                )
            )
        else:
            if internal_team_id:
                existing.internal_team_id = internal_team_id
            existing.games_played = item.get(
                "games_played", item.get("played", existing.games_played)
            )
            existing.clean_sheets = item.get("clean_sheets", existing.clean_sheets)
            existing.points = item.get("points", existing.points)
            existing.position = item.get("position", existing.position)
            existing.wins = item.get("wins", existing.wins)
            existing.draws = item.get("draws", existing.draws)
            existing.losses = item.get("losses", existing.losses)
            existing.goals_for = item.get("goals_for", existing.goals_for)
            existing.goals_against = item.get("goals_against", existing.goals_against)
            existing.form_rating = item.get("form_rating", item.get("form", existing.form_rating))
            existing.average_possession = item.get(
                "average_possession", existing.average_possession
            )
            existing.average_shots = item.get("average_shots", existing.average_shots)
            existing.average_xg = item.get("average_xg", existing.average_xg)
            existing.average_xga = item.get("average_xga", existing.average_xga)
            existing.goals_per_game = item.get("goals_per_game", existing.goals_per_game)
            existing.goals_conceded_per_game = item.get(
                "goals_conceded_per_game", existing.goals_conceded_per_game
            )
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

        provider_name = item.get("provider", "sportmonks")
        status_val = item.get("status")
        if hasattr(status_val, "value"):
            status_val = status_val.value

        existing = await db.get(Match, provider_fixture_id)
        if existing is None:
            db.add(
                Match(
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
                )
            )
        else:
            for field in (
                "league_id",
                "season_id",
                "home_team_id",
                "away_team_id",
                "home_team_name",
                "away_team_name",
                "kickoff_at",
                "venue",
                "referee",
                "home_score",
                "away_score",
            ):
                value = item.get(field)
                if value is not None:
                    setattr(existing, field, value)
            existing.status = status_val or existing.status
            if item.get("is_finished") is not None:
                existing.is_finished = item["is_finished"]
            existing.retrieved_at = datetime.utcnow()
            provider_metadata = item.get("provider_metadata") or {}
            if provider_metadata:
                existing.provider_metadata = {
                    **(existing.provider_metadata or {}),
                    **provider_metadata,
                }


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

        provider_name = item.get("provider", "sportmonks")
        existing = await db.get(Player, provider_player_id)
        if existing is None:
            db.add(
                Player(
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
                )
            )


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

        provider_name = item.get("provider", "sportmonks")
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

        provider_name = item.get("provider", "sportmonks")
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


_ALL_RESOURCE_METHODS = {
    "get_leagues",
    "get_seasons",
    "get_league",
    "get_teams",
    "get_team",
    "get_team_statistics",
    "get_standings",
    "get_fixtures",
    "get_fixture",
    "get_players",
    "get_injuries",
    "get_sidelined",
    "get_timezones",
    "get_countries",
}


async def _attach_league_includes(
    league_id: str, includes: Any, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Side-load Sportmonks relations onto DB-sourced league rows.

    The DB-first path stores only the league record itself, so requested
    ``include`` relations have to be fetched from the provider and merged in.
    Failures are non-fatal: the DB rows are returned unchanged.
    """
    from football_data.sportmonks_client import SportmonksClient

    include_names = SportmonksClient._normalize_includes(includes)
    if not include_names or not rows:
        return rows

    provider = get_football_provider()
    await provider.connect()
    try:
        if getattr(provider, "provider_name", None) == "sportmonks":
            raw = await provider.http.get_league(league_id, includes=include_names)
        else:
            raw = await provider.get_league(league_id, includes=include_names)
            if hasattr(raw, "model_dump"):
                raw = raw.model_dump(mode="json")
    except Exception as exc:
        logger.warning(f"Include side-load failed for league {league_id}: {exc}")
        return rows
    finally:
        await provider.close()

    if not isinstance(raw, dict):
        return rows

    for row in rows:
        for name in include_names:
            key = "currentseason" if name == "currentSeason" else name
            if key in raw:
                row["country_details" if name == "country" else key] = raw[key]
                if name == "currentSeason":
                    row["current_season"] = raw[key]
    return rows


async def _attach_team_includes(
    team_id: str, includes: Any, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Side-load Sportmonks relations onto DB-sourced team rows.

    The DB-first path only stores the team record itself, so the requested
    ``include`` relations have to be fetched from the provider and merged in.

    This subscription populates a single include per request, so sending all
    sixteen together returns only the first one.  The relations are therefore
    fetched one request at a time, which is affordable for a single team but
    would be far too costly on the paginated list endpoint (that one sends them
    all together and returns whatever the plan allows).

    Failures are non-fatal: the DB rows are returned unchanged.
    """
    from football_data.sportmonks_client import SportmonksClient

    include_names = SportmonksClient._normalize_includes(includes)
    if not include_names or not rows:
        return rows

    provider = get_football_provider()
    await provider.connect()
    merged: dict[str, Any] = {}
    try:
        for name in include_names:
            try:
                raw = await provider.http.get_team(team_id, includes=[name])
            except Exception as exc:
                logger.warning(f"Include '{name}' failed for team {team_id}: {exc}")
                continue
            if not isinstance(raw, dict):
                continue
            # ``players.player`` is nested: Sportmonks returns the squad under
            # ``players`` with the player object embedded in each entry.
            key = name.split(".")[0].lower()
            if key in raw:
                merged[key] = raw[key]
    finally:
        await provider.close()

    for row in rows:
        for key, value in merged.items():
            row[key] = value
    return rows


async def _provider_data_response(
    provider_method: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """DB-first provider response.

    1. Always try to read from the database.
    2. If the DB is empty, fetch from the provider, loop through results,
       save each record to the DB, then re-read from the DB.
    3. If the provider also fails, return an empty DB-shaped response.
    """
    kwargs = dict(kwargs)
    if "league_id" in kwargs:
        kwargs["league_id"] = _resolve_provider_league_id(kwargs["league_id"])

    requested_includes = kwargs.get("include")

    if provider_method in _ALL_RESOURCE_METHODS:
        db_payload = None
        try:
            db_payload = await _read_db_resource_payload(provider_method, **kwargs)
        except Exception as exc:
            logger.error(f"DB read error for {provider_method}: {exc}")
            db_payload = None
        if db_payload and db_payload.get("data"):
            rows = db_payload["data"]
            if requested_includes is not None:
                if provider_method == "get_league":
                    rows = await _attach_league_includes(
                        kwargs.get("league_id", ""), requested_includes, rows
                    )
                elif provider_method == "get_team":
                    rows = await _attach_team_includes(
                        kwargs.get("team_id", ""), requested_includes, rows
                    )
            return {
                "success": True,
                "data": rows,
                "meta": {
                    **db_payload.get("meta", {}),
                    "source": "database",
                    **({"include": requested_includes} if requested_includes is not None else {}),
                },
            }

        provider_kwargs = _map_filters_for_provider(provider_method, kwargs)
        if provider_method == "get_team_statistics" and kwargs.get("team_id"):
            async with AsyncSessionLocal() as db:
                mapping_stmt = (
                    select(ProviderTeam)
                    .outerjoin(Season, Season.id == ProviderTeam.season_id)
                    .where(
                        ProviderTeam.internal_team_id == kwargs["team_id"],
                        ProviderTeam.provider_name == get_settings().football_data_provider,
                    )
                )
                if kwargs.get("league_id"):
                    mapping_stmt = mapping_stmt.where(
                        ProviderTeam.provider_league_id == kwargs["league_id"]
                    )
                if kwargs.get("season_id"):
                    mapping_stmt = mapping_stmt.where(ProviderTeam.season_id == kwargs["season_id"])
                mapping_stmt = mapping_stmt.order_by(
                    Season.is_current.desc(), Season.year.desc().nullslast()
                ).limit(1)
                team_mapping = (await db.execute(mapping_stmt)).scalar_one_or_none()
            if team_mapping:
                provider_kwargs["team_id"] = team_mapping.provider_team_id
                if not provider_kwargs.get("league_id"):
                    provider_kwargs["league_id"] = team_mapping.provider_league_id
                if not provider_kwargs.get("season_id"):
                    provider_kwargs["season_id"] = team_mapping.season_id

        provider = get_football_provider()
        await provider.connect()
        try:
            provider_data = await getattr(provider, provider_method)(**provider_kwargs)
        except Exception as exc:
            logger.error(f"Provider fetch error for {provider_method}: {exc}")
            provider_data = None
        finally:
            await provider.close()

        if provider_data is not None:
            if not isinstance(provider_data, list):
                provider_data = [provider_data]
            try:
                await _save_provider_data_to_db(provider_method, provider_data)
            except Exception as exc:
                logger.error(f"DB save error for {provider_method}: {exc}")

        try:
            db_payload = await _read_db_resource_payload(provider_method, **kwargs)
        except Exception as exc:
            logger.error(f"DB re-read error for {provider_method}: {exc}")
            db_payload = None
        if db_payload and db_payload.get("data"):
            rows = db_payload["data"]
            if provider_method == "get_league" and requested_includes is not None:
                rows = await _attach_league_includes(
                    kwargs.get("league_id", ""), requested_includes, rows
                )
            return {
                "success": True,
                "data": rows,
                "meta": {
                    **db_payload.get("meta", {}),
                    "source": "database",
                    **({"include": requested_includes} if requested_includes is not None else {}),
                },
            }

        return {
            "success": True,
            "data": [],
            "meta": {
                "page": kwargs.get("page", 1),
                "page_size": kwargs.get("page_size", 50),
                "total": 0,
                "total_pages": 1,
                "source": "database",
            },
        }

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
    elif provider_method == "get_league":
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
            "venue_name": item.get("venue_name"),
            "venue_city": item.get("venue_city"),
            "country": item.get("country"),
            "is_active": True,
            "created_at": None,
            "season_id": item.get("season_id"),
            "league_id": item.get("league_id"),
        }
    elif provider_method == "get_team":
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
            "retrieved_at": datetime.utcnow().isoformat(),
        }
    elif provider_method == "get_fixture":
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
            "retrieved_at": datetime.utcnow().isoformat(),
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
    is_active: bool | None = Query(None),
    include: str | None = Query(
        None,
        description=(
            "Comma-separated Sportmonks side-loads. Defaults to "
            "sport,country,stages,latest,upcoming,inplay,today,currentSeason,seasons"
        ),
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if country:
        params["country"] = country
    if season:
        params["season"] = season
    if is_active is not None:
        params["is_active"] = is_active
    if include is not None:
        params["include"] = include
    return await _provider_data_response("get_leagues", **params)


@router.post("/providers/sync/database", tags=["providers"])
async def sync_provider_database(
    _admin: str = Depends(verify_admin_api_key),
) -> dict[str, Any]:
    """Fetch provider data and persist it to the local database."""
    try:
        # Sync leagues
        provider = get_football_provider()
        await provider.connect()
        leagues = await provider.get_leagues()
        await provider.close()

        if leagues:
            await _save_leagues(AsyncSessionLocal(), leagues)

        return {
            "success": True,
            "data": {"synced": True, "leagues": len(leagues) if leagues else 0},
            "meta": {"message": "Provider data synced to database successfully."},
        }
    except Exception as exc:
        logger.exception("Provider database sync failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Provider sync failed: {exc}",
        ) from exc


@router.post("/providers/sync/leagues", tags=["providers"])
async def sync_leagues(
    _admin: str = Depends(verify_admin_api_key),
) -> dict[str, Any]:
    """Manually sync leagues from provider to database."""
    try:
        provider = get_football_provider()
        await provider.connect()
        leagues = await provider.get_leagues()
        await provider.close()

        if leagues:
            await _save_leagues(AsyncSessionLocal(), leagues)

        return {
            "success": True,
            "data": {"synced": True, "leagues": len(leagues) if leagues else 0},
            "meta": {"message": "Leagues synced successfully."},
        }
    except Exception as exc:
        logger.exception("League sync failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"League sync failed: {exc}",
        ) from exc


@router.post("/providers/sync/seasons", tags=["providers"])
async def sync_seasons(
    league_id: str = Query(..., description="League ID to sync seasons for"),
    _admin: str = Depends(verify_admin_api_key),
) -> dict[str, Any]:
    """Manually sync seasons for a league from provider to database."""
    try:
        resolved_league_id = _resolve_provider_league_id(league_id)

        provider = get_football_provider()
        await provider.connect()
        seasons = await provider.get_seasons(league_id=resolved_league_id)
        await provider.close()

        if seasons:
            await _save_seasons(AsyncSessionLocal(), seasons)

        return {
            "success": True,
            "data": {"synced": True, "seasons": len(seasons) if seasons else 0},
            "meta": {"message": "Seasons synced successfully."},
        }
    except Exception as exc:
        logger.exception("Season sync failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Season sync failed: {exc}",
        ) from exc


@router.post("/providers/sync/teams", tags=["providers"])
async def sync_teams(
    league_id: str = Query(..., description="League ID to sync teams for"),
    season_id: str = Query(..., description="Season ID to sync teams for"),
    _admin: str = Depends(verify_admin_api_key),
) -> dict[str, Any]:
    """Manually sync teams for a league/season from provider to database."""
    try:
        resolved_league_id = _resolve_provider_league_id(league_id)

        provider = get_football_provider()
        await provider.connect()
        teams = await provider.get_teams(league_id=resolved_league_id, season_id=season_id)
        await provider.close()

        if teams:
            await _save_teams(AsyncSessionLocal(), teams)

        return {
            "success": True,
            "data": {"synced": True, "teams": len(teams) if teams else 0},
            "meta": {"message": "Teams synced successfully."},
        }
    except Exception as exc:
        logger.exception("Team sync failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Team sync failed: {exc}",
        ) from exc


@router.post("/providers/sync/fixtures", tags=["providers"])
async def sync_fixtures(
    league_id: str = Query(..., description="League ID to sync fixtures for"),
    season_id: str = Query(..., description="Season ID to sync fixtures for"),
    _admin: str = Depends(verify_admin_api_key),
) -> dict[str, Any]:
    """Manually sync fixtures for a league/season from provider to database."""
    try:
        resolved_league_id = _resolve_provider_league_id(league_id)

        provider = get_football_provider()
        await provider.connect()
        fixtures = await provider.get_fixtures(league_id=resolved_league_id, season_id=season_id)
        await provider.close()

        if fixtures:
            await _save_fixtures(AsyncSessionLocal(), fixtures)

        return {
            "success": True,
            "data": {"synced": True, "fixtures": len(fixtures) if fixtures else 0},
            "meta": {"message": "Fixtures synced successfully."},
        }
    except Exception as exc:
        logger.exception("Fixture sync failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fixture sync failed: {exc}",
        ) from exc


@router.post("/providers/sync/standings", tags=["providers"])
async def sync_standings(
    league_id: str = Query(..., description="League ID to sync standings for"),
    season_id: str = Query(..., description="Season ID to sync standings for"),
    _admin: str = Depends(verify_admin_api_key),
) -> dict[str, Any]:
    """Manually sync standings for a league/season from provider to database."""
    try:
        resolved_league_id = _resolve_provider_league_id(league_id)

        provider = get_football_provider()
        await provider.connect()
        standings = await provider.get_standings(league_id=resolved_league_id, season_id=season_id)
        await provider.close()

        if standings and standings.standings:
            await _save_standings(AsyncSessionLocal(), standings.standings)

        return {
            "success": True,
            "data": {
                "synced": True,
                "standings": len(standings.standings) if standings and standings.standings else 0,
            },
            "meta": {"message": "Standings synced successfully."},
        }
    except Exception as exc:
        logger.exception("Standings sync failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Standings sync failed: {exc}",
        ) from exc


@router.get("/providers/leagues/seasons", tags=["providers"])
async def provider_league_seasons(
    league_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    resolved_league_id = _resolve_provider_league_id(league_id)
    return await _provider_data_response(
        "get_seasons",
        league_id=resolved_league_id,
        page=page,
        page_size=page_size,
    )


@router.get("/providers/teams", tags=["providers"])
async def provider_teams(
    league_id: str | None = Query(None),
    season_id: str | None = Query(None),
    search: str | None = Query(None, description="Case-insensitive name/short-name filter"),
    is_active: bool | None = Query(None),
    all_seasons: bool = Query(
        False,
        description="Include teams from past seasons. Defaults to current season only.",
    ),
    include: str | None = Query(
        None,
        description=(
            "Comma-separated Sportmonks side-loads. Defaults to "
            "sport,country,venue,coaches,rivals,players.player,latest,upcoming,"
            "seasons,activeSeasons,sidelined,sidelinedHistory,statistics,"
            "trophies,socials,rankings"
        ),
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if league_id:
        params["league_id"] = league_id
    if season_id:
        params["season_id"] = season_id
    if search:
        params["search"] = search
    if is_active is not None:
        params["is_active"] = is_active
    if all_seasons:
        params["all_seasons"] = True
    if include is not None:
        params["include"] = include
    return await _provider_data_response("get_teams", **params)


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


@router.get("/providers/leagues/{league_id}/standings", tags=["providers"])
async def provider_league_standings(
    league_id: str,
    season_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    return await _provider_data_response(
        "get_standings",
        league_id=league_id,
        season_id=season_id,
        page=page,
        page_size=page_size,
    )


@router.get("/providers/leagues/{league_id}", tags=["providers"])
async def provider_league_by_id(
    league_id: str,
    include: str | None = Query(
        None,
        description=(
            "Comma-separated Sportmonks side-loads. Defaults to "
            "sport,country,stages,latest,upcoming,inplay,today,currentSeason,seasons"
        ),
    ),
) -> dict[str, Any]:
    """Return a single league by provider league id, e.g. 39 for Premier League."""
    params: dict[str, Any] = {}
    if include is not None:
        params["include"] = include
    return await _provider_data_response("get_league", league_id=league_id, **params)


@router.get("/providers/teams/{team_id}", tags=["providers"])
async def provider_team(
    team_id: str,
    include: str | None = Query(
        None,
        description=(
            "Comma-separated Sportmonks side-loads. Defaults to "
            "sport,country,venue,coaches,rivals,players.player,latest,upcoming,"
            "seasons,activeSeasons,sidelined,sidelinedHistory,statistics,"
            "trophies,socials,rankings. Fetched one request per relation so all "
            "of them are actually populated."
        ),
    ),
) -> dict[str, Any]:
    params: dict[str, Any] = {"team_id": team_id}
    if include is not None:
        params["include"] = include
    response = await _provider_data_response("get_team", **params)
    if not response.get("data"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} not found",
        )
    return response


@router.get("/providers/teams/{team_id}/statistics", tags=["providers"])
async def provider_team_statistics(
    team_id: str,
    league_id: str | None = Query(None),
    season_id: str | None = Query(None),
) -> dict[str, Any]:
    response = await _provider_data_response(
        "get_team_statistics",
        team_id=team_id,
        league_id=league_id,
        season_id=season_id,
    )
    rows = response.get("data") or []
    if isinstance(rows, dict):
        rows = [rows]
    return {
        "success": response.get("success", True),
        "data": {"team_id": team_id, "statistics": rows},
        "meta": response.get("meta", {}),
    }


@router.get("/providers/teams/{team_id}/matches", tags=["providers"])
async def provider_team_matches(
    team_id: str,
    league_id: str | None = Query(None),
    season_id: str | None = Query(None),
    status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    return await _provider_data_response(
        "get_fixtures",
        team_id=team_id,
        league_id=league_id,
        season_id=season_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get("/providers/matches", tags=["providers"])
async def provider_matches(
    league_id: str | None = Query(None),
    season_id: str | None = Query(None),
    team_id: str | None = Query(None),
    fixture_id: str | None = Query(None),
    status: str | None = Query(None),
    date: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    upcoming: bool | None = Query(None),
    today: bool | None = Query(None),
    all_seasons: bool = Query(
        False,
        description="Include fixtures from past seasons. Defaults to current season only.",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "league_id": league_id,
        "season_id": season_id,
        "team_id": team_id,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
        "page": page,
        "page_size": page_size,
    }
    if fixture_id:
        return await _provider_data_response("get_fixture", fixture_id=fixture_id)
    if upcoming is not None and upcoming:
        params["upcoming"] = True
    if today is not None and today:
        params["today"] = True
    if all_seasons:
        params["all_seasons"] = True
    if date:
        params["date"] = date
    return await _provider_data_response(
        "get_fixtures", **{k: v for k, v in params.items() if v is not None}
    )


@router.get("/providers/matches/today", tags=["providers"])
async def provider_matches_today(
    league_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    return await _provider_data_response(
        "get_fixtures",
        league_id=league_id,
        today=True,
        page=page,
        page_size=page_size,
    )


@router.get("/providers/matches/upcoming", tags=["providers"])
async def provider_matches_upcoming(
    league_id: str | None = Query(None),
    team_id: str | None = Query(None),
    season_id: str | None = Query(None),
    days: int = Query(7, ge=1, le=30),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    return await _provider_data_response(
        "get_fixtures",
        league_id=league_id,
        team_id=team_id,
        season_id=season_id,
        upcoming=True,
        days=days,
        page=page,
        page_size=page_size,
    )


@router.get("/providers/matches/{match_id}", tags=["providers"])
async def provider_match(match_id: str) -> dict[str, Any]:
    return await _provider_data_response("get_fixture", fixture_id=match_id)


@router.get("/providers/matches/{match_id}/summary", tags=["providers"])
async def provider_match_summary(match_id: str) -> dict[str, Any]:
    data = await _provider_data_response("get_fixture", fixture_id=match_id)
    return data
