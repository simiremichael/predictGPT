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
from sqlalchemy import select

from core.config import get_settings
from core.logging import get_logger
from core.security import verify_admin_api_key
from db.database import AsyncSessionLocal
from db.redis_client import get_redis
from football_data.factory import SUPPORTED_PROVIDERS, get_football_provider, get_provider_for_name
from football_data.league_mappings import LeagueMapping
from football_data.models import NormalizedProviderStatus
from models.league import League, Season, Team
from models.match import Injury, Match, Player, Suspension, TeamStatistics
from scripts.daily_sync import increment_db_version, run_daily_sync

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
    async with AsyncSessionLocal() as db:
        if provider_method == "get_leagues":
            stmt = select(League)
            if kwargs.get("country"):
                stmt = stmt.where(League.country == kwargs["country"])
            stmt = stmt.order_by(League.name)
            rows = (await db.execute(stmt)).scalars().all()
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "country": row.country,
                    "country_code": row.country_code,
                    "is_active": row.is_active,
                }
                for row in rows
            ]

        if provider_method == "get_seasons":
            stmt = select(Season)
            if kwargs.get("league_id"):
                stmt = stmt.where(Season.league_id == kwargs["league_id"])
            stmt = stmt.order_by(Season.year.desc(), Season.name)
            rows = (await db.execute(stmt)).scalars().all()
            return [
                {
                    "id": row.id,
                    "league_id": row.league_id,
                    "name": row.name,
                    "year": row.year,
                    "is_current": row.is_current,
                }
                for row in rows
            ]

        if provider_method == "get_teams":
            stmt = select(Team)
            if kwargs.get("league_id"):
                stmt = stmt.where(Team.country == kwargs.get("country") or Team.country.isnot(None))
            stmt = stmt.order_by(Team.name)
            rows = (await db.execute(stmt)).scalars().all()
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "short_name": row.short_name,
                    "slug": row.slug,
                    "logo_url": row.logo_url,
                    "country": row.country,
                }
                for row in rows
            ]

        if provider_method == "get_standings":
            stmt = select(TeamStatistics)
            if kwargs.get("league_id"):
                stmt = stmt.where(TeamStatistics.league_id == kwargs["league_id"])
            if kwargs.get("season_id"):
                stmt = stmt.where(TeamStatistics.season_id == kwargs["season_id"])
            stmt = stmt.order_by(TeamStatistics.position)
            rows = (await db.execute(stmt)).scalars().all()
            return [
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
            ]

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
            rows = (await db.execute(stmt)).scalars().all()
            return [
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
            ]

        if provider_method == "get_players":
            stmt = select(Player)
            if kwargs.get("team_id"):
                stmt = stmt.where(Player.team_id == kwargs["team_id"])
            stmt = stmt.order_by(Player.full_name)
            rows = (await db.execute(stmt)).scalars().all()
            return [
                {
                    "id": row.id,
                    "provider_player_id": row.provider_player_id,
                    "team_id": row.team_id,
                    "full_name": row.full_name,
                    "position": row.position,
                    "nationality": row.nationality,
                }
                for row in rows
            ]

        if provider_method == "get_injuries":
            stmt = select(Injury)
            if kwargs.get("team_id"):
                stmt = stmt.where(Injury.internal_team_id == kwargs["team_id"])
            if kwargs.get("fixture_id"):
                stmt = stmt.where(Injury.provider_metadata.isnot(None))
            stmt = stmt.order_by(Injury.player_name)
            rows = (await db.execute(stmt)).scalars().all()
            return [
                {
                    "id": row.id,
                    "player_name": row.player_name,
                    "position": row.position,
                    "injury_type": row.injury_type,
                    "severity": row.severity,
                    "description": row.description,
                }
                for row in rows
            ]

        if provider_method == "get_sidelined":
            stmt = select(Suspension)
            if kwargs.get("team_id"):
                stmt = stmt.where(Suspension.internal_team_id == kwargs["team_id"])
            if kwargs.get("fixture_id"):
                stmt = stmt.where(Suspension.provider_metadata.isnot(None))
            stmt = stmt.order_by(Suspension.player_name)
            rows = (await db.execute(stmt)).scalars().all()
            return [
                {
                    "id": row.id,
                    "player_name": row.player_name,
                    "position": row.position,
                    "reason": row.reason,
                    "suspension_type": row.suspension_type,
                }
                for row in rows
            ]

        return []


async def _should_refresh_provider_data(resource_key: str) -> bool:
    redis = await get_redis()
    if redis.client is None:
        await redis.connect()

    today = datetime.utcnow().strftime("%Y-%m-%d")
    cached = await redis.client.get(f"provider:daily-sync:{resource_key}")
    if cached == today:
        return False
    await redis.client.set(f"provider:daily-sync:{resource_key}", today, ex=86400 * 2)
    return True


async def _sync_and_reconcile_resource(
    provider_method: str, **kwargs: Any
) -> list[dict[str, Any]] | None:
    resource_key = f"provider:{provider_method}:{json.dumps(kwargs, sort_keys=True, default=str)}"
    if not await _should_refresh_provider_data(resource_key):
        db_payload = await _read_db_resource_payload(provider_method, **kwargs)
        if db_payload:
            return db_payload

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

    db_payload = await _read_db_resource_payload(provider_method, **kwargs)
    if not db_payload:
        await _invalidate_compare_cache(resource_key)
        await run_daily_sync()
        db_payload = await _read_db_resource_payload(provider_method, **kwargs)
        if db_payload:
            return db_payload
        return provider_payload

    if _payload_signature(provider_payload) == _payload_signature(db_payload):
        return db_payload

    await _invalidate_compare_cache(resource_key)
    await run_daily_sync()
    refreshed_db = await _read_db_resource_payload(provider_method, **kwargs)
    return refreshed_db or provider_payload


async def _invalidate_compare_cache(resource_key: str) -> None:
    """Clear stale provider sync and frontend cache markers after a DB/provider mismatch."""
    redis = await get_redis()
    if getattr(redis, "client", None) is None:
        await redis.connect()

    sync_key = f"provider:daily-sync:{resource_key}"
    try:
        await redis.client.delete(sync_key)
    except Exception:
        pass

    try:
        await increment_db_version()
    except Exception:
        pass


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
        reconciled = await _sync_and_reconcile_resource(provider_method, **kwargs)
        if reconciled is not None:
            source = "database" if reconciled and reconciled != [] else "provider"
            return {
                "success": True,
                "data": reconciled,
                "meta": {"count": len(reconciled), "source": source},
            }

    provider = get_football_provider()
    await provider.connect()
    try:
        data = await getattr(provider, provider_method)(**kwargs)
        if data is None:
            payload: list[dict[str, Any]] | list[str] = []
        elif isinstance(data, list):
            payload = data
        else:
            payload = [data]
        return {
            "success": True,
            "data": payload,
            "meta": {"count": len(payload)},
        }
    finally:
        await provider.close()


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
) -> dict[str, Any]:
    params: dict[str, Any] = {}
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
