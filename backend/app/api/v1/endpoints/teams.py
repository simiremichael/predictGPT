"""Team API endpoints.

GET  /api/v1/teams                           -- list all teams
GET  /api/v1/teams/{team_id}                 -- team detail
GET  /api/v1/teams/{team_id}/matches         -- matches for a team
GET  /api/v1/teams/{team_id}/statistics      -- team statistics
GET  /api/v1/teams/{team_id}/seasons         -- team seasons
GET  /api/v1/teams/{team_id}/countries       -- team countries
GET  /api/v1/leagues/{league_id}/teams       -- teams in a league
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import (
    cache_team_key,
    cache_team_matches_key,
    cache_team_statistics_key,
    get_cached,
    set_cached,
)
from core.pagination import get_page, get_page_size
from db.database import get_db
from models.league import League, ProviderLeague, ProviderTeam, Season, Team
from models.match import Match, TeamStatistics as TeamStatsModel

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=dict[str, Any])
async def list_teams(
    request: Request,
    db: AsyncSession = Depends(get_db),
    league_id: str | None = Query(None, description="Filter by league"),
    is_active: bool = Query(default=True),
    search: str | None = Query(None, description="Search by name or short_name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """List all teams with optional filtering and pagination."""
    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps

    stmt = select(Team)
    if is_active:
        stmt = stmt.where(Team.is_active)
    if league_id:
        stmt = stmt.join(
            __import__("models.league", fromlist=["ProviderTeam"]).ProviderTeam
        ).where(
            __import__("models.league", fromlist=["ProviderTeam"]).ProviderTeam.internal_team_id == Team.id
        )
    if search:
        stmt = stmt.where(
            (Team.name.ilike(f"%{search}%")) | (Team.short_name.ilike(f"%{search}%"))
        )

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar() or 0

    stmt = stmt.order_by(Team.name).offset(offset).limit(ps)
    result = await db.execute(stmt)
    teams = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": t.id,
                "name": t.name,
                "short_name": t.short_name,
                "slug": t.slug,
                "logo_url": t.logo_url,
                "venue_name": t.venue_name,
                "venue_city": t.venue_city,
                "country": t.country,
                "is_active": t.is_active,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in teams
        ],
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
        },
    }


@router.get("/{team_id}", response_model=dict[str, Any])
async def get_team(
    team_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed information about a specific team."""
    cache_key = cache_team_key(team_id)

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = select(Team).where(Team.id == team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} not found",
        )

    response = {
        "success": True,
        "data": {
            "id": team.id,
            "name": team.name,
            "short_name": team.short_name,
            "slug": team.slug,
            "logo_url": team.logo_url,
            "venue_name": team.venue_name,
            "venue_city": team.venue_city,
            "country": team.country,
            "is_active": team.is_active,
            "created_at": team.created_at.isoformat() if team.created_at else None,
        },
    }

    try:
        await set_cached(cache_key, response, ttl=86400)
    except Exception:
        pass

    return response


@router.get("/{team_id}/matches", response_model=dict[str, Any])
async def get_team_matches(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    league_id: str | None = Query(None),
    status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get matches for a team."""
    cache_key = cache_team_matches_key(
        team_id, league_id=league_id, status=status, date_from=date_from, date_to=date_to,
        page=page, page_size=page_size,
    )

    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = select(Match).where(
        (Match.home_team_id == team_id) | (Match.away_team_id == team_id)
    )

    if league_id:
        stmt = stmt.where(Match.league_id == league_id)
    if status:
        stmt = stmt.where(Match.status == status)
    if date_from:
        stmt = stmt.where(Match.kickoff_at >= date_from)
    if date_to:
        stmt = stmt.where(Match.kickoff_at <= date_to)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar() or 0

    stmt = stmt.order_by(Match.kickoff_at.desc()).offset(offset).limit(ps)
    result = await db.execute(stmt)
    matches = result.scalars().all()

    response = {
        "success": True,
        "data": [
            {
                "id": m.id,
                "league_id": m.league_id,
                "home_team_id": m.home_team_id,
                "home_team_name": m.home_team_name,
                "away_team_id": m.away_team_id,
                "away_team_name": m.away_team_name,
                "kickoff_at": m.kickoff_at.isoformat() if m.kickoff_at else None,
                "status": m.status,
                "venue": m.venue,
                "home_score": m.home_score,
                "away_score": m.away_score,
                "is_finished": m.is_finished,
            }
            for m in matches
        ],
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
        },
    }

    try:
        await set_cached(cache_key, response, ttl=1800)
    except Exception:
        pass

    return response


@router.get("/{team_id}/statistics", response_model=dict[str, Any])
async def get_team_statistics(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    league_id: str | None = Query(None),
    season_id: str | None = Query(None),
) -> dict[str, Any]:
    """Get statistics for a team."""
    cache_key = cache_team_statistics_key(team_id)

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = select(TeamStatsModel).where(TeamStatsModel.internal_team_id == team_id)

    if league_id:
        stmt = stmt.where(TeamStatsModel.league_id == league_id)
    if season_id:
        stmt = stmt.where(TeamStatsModel.season_id == season_id)

    result = await db.execute(stmt)
    stats = result.scalars().all()

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No statistics found for team {team_id}",
        )

    response = {
        "success": True,
        "data": {
            "team_id": team_id,
            "statistics": [
                {
                    "league_id": s.league_id,
                    "season_id": s.season_id,
                    "is_home": s.is_home,
                    "games_played": s.games_played,
                    "wins": s.wins,
                    "draws": s.draws,
                    "losses": s.losses,
                    "goals_for": s.goals_for,
                    "goals_against": s.goals_against,
                    "clean_sheets": s.clean_sheets,
                    "points": s.points,
                    "position": s.position,
                    "form_rating": s.form_rating,
                    "average_possession": s.average_possession,
                    "average_shots": s.average_shots,
                    "average_xg": s.average_xg,
                    "average_xga": s.average_xga,
                    "goals_per_game": s.goals_per_game,
                    "goals_conceded_per_game": s.goals_conceded_per_game,
                }
                for s in stats
            ],
        },
    }

    try:
        await set_cached(cache_key, response, ttl=3600)
    except Exception:
        pass

    return response


@router.get("/{team_id}/seasons", response_model=dict[str, Any])
async def get_team_seasons(
    team_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get seasons a team has participated in."""
    stmt = (
        select(Season, League)
        .join(ProviderLeague, ProviderLeague.internal_league_id == Season.league_id)
        .join(League, League.id == Season.league_id)
        .join(ProviderTeam, ProviderTeam.provider_league_id == ProviderLeague.provider_league_id)
        .where(ProviderTeam.internal_team_id == team_id)
        .distinct(Season.id)
        .order_by(Season.year.desc().nullslast(), Season.name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    seasons_data = []
    for season, league in rows:
        seasons_data.append({
            "id": season.id,
            "league_id": league.id,
            "league_name": league.name,
            "name": season.name,
            "year": season.year,
            "start_date": season.start_date.isoformat() if season.start_date else None,
            "end_date": season.end_date.isoformat() if season.end_date else None,
            "is_current": season.is_current,
        })

    return {
        "success": True,
        "data": seasons_data,
        "meta": {"total": len(seasons_data)},
    }


@router.get("/{team_id}/countries", response_model=dict[str, Any])
async def get_team_countries(
    team_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get countries a team has played in (via leagues)."""
    stmt = (
        select(League.country, func.count(League.id).label("league_count"))
        .join(Season, Season.league_id == League.id)
        .join(ProviderLeague, ProviderLeague.internal_league_id == League.id)
        .join(ProviderTeam, ProviderTeam.provider_league_id == ProviderLeague.provider_league_id)
        .where(ProviderTeam.internal_team_id == team_id)
        .where(League.country.isnot(None))
        .group_by(League.country)
        .order_by(func.count(League.id).desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    countries_data = [
        {"country": row.country, "league_count": row.league_count}
        for row in rows
    ]

    return {
        "success": True,
        "data": countries_data,
        "meta": {"total": len(countries_data)},
    }


@router.get("/leagues/{league_id}/teams", response_model=dict[str, Any])
async def get_league_teams(
    league_id: str,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """Get all teams in a league."""
    from core.config import get_settings

    settings = get_settings()
    provider_name = settings.football_data_provider
    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps

    current_season_stmt = (
        select(Season.id)
        .where(Season.league_id == league_id, Season.is_current.is_(True))
        .limit(1)
    )
    current_season_id = (await db.execute(current_season_stmt)).scalar_one_or_none()

    base_stmt = (
        select(Team)
        .join(ProviderTeam, ProviderTeam.internal_team_id == Team.id)
        .where(ProviderTeam.provider_league_id == league_id)
        .where(ProviderTeam.provider_name == provider_name)
    )
    if current_season_id:
        base_stmt = base_stmt.where(ProviderTeam.season_id == current_season_id)

    stmt = base_stmt.distinct(Team.id).order_by(Team.id, Team.name)

    count_stmt = select(func.count()).select_from(
        base_stmt.with_only_columns(Team.id).distinct(Team.id).subquery()
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    if total == 0:
        try:
            from football_data.factory import get_football_provider
            from api.v1.endpoints.providers import _save_provider_data_to_db

            provider = get_football_provider()
            await provider.connect()
            try:
                provider_data = await provider.get_teams(
                    league_id=league_id, season_id=current_season_id
                )
            finally:
                await provider.close()

            if provider_data:
                if not isinstance(provider_data, list):
                    provider_data = [provider_data]
                await _save_provider_data_to_db("get_teams", provider_data)
                await db.commit()
            count_result = await db.execute(count_stmt)
            total = count_result.scalar() or 0
        except Exception:
            pass

    stmt = stmt.offset(offset).limit(ps)
    result = await db.execute(stmt)
    teams = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": t.id,
                "name": t.name,
                "short_name": t.short_name,
                "slug": t.slug,
                "logo_url": t.logo_url,
                "venue_name": t.venue_name,
                "venue_city": t.venue_city,
                "country": t.country,
                "is_active": t.is_active,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in teams
        ],
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
        },
    }
