"""League API endpoints.

GET  /api/v1/leagues                    -- list all leagues
GET  /api/v1/leagues/{league_id}        -- league detail with teams, fixtures, standings
GET  /api/v1/leagues/{league_id}/seasons -- list seasons for a league
GET  /api/v1/leagues/{league_id}/standings -- list standings for a season
GET  /api/v1/leagues/country/{country} -- list all league levels for a country
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.pagination import get_page, get_page_size
from db.database import get_db
from models.league import League, Season, Team
from models.match import Match, TeamStatistics
from services.frontend_cache import frontend_cache

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("", response_model=dict[str, Any])
async def list_leagues(
    request: Request,
    db: AsyncSession = Depends(get_db),
    is_active: bool = Query(default=True, description="Filter active leagues"),
    country: str | None = Query(None, description="Filter by country"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """List all leagues with optional filtering and pagination.
    
    Uses frontend Redis cache with DB-change revalidation.
    """
    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps
    
    # Use frontend cache with DB version revalidation
    cache_namespace = "leagues:list"
    cache_keys = ("active" if is_active else "all", country or "all", page_num, ps)
    
    async def fetch_leagues():
        stmt = select(League)
        if is_active:
            stmt = stmt.where(League.is_active)
        if country:
            stmt = stmt.where(League.country == country)
        
        count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
        total = count_result.scalar() or 0
        
        stmt = stmt.order_by(League.name).offset(offset).limit(ps)
        result = await db.execute(stmt)
        leagues = result.scalars().all()
        
        return {
            "success": True,
            "data": [
                {
                    "id": lg.id,
                    "name": lg.name,
                    "country": lg.country,
                    "country_code": lg.country_code,
                    "is_active": lg.is_active,
                    "created_at": lg.created_at.isoformat() if lg.created_at else None,
                }
                for lg in leagues
            ],
            "meta": {
                "page": page_num,
                "page_size": ps,
                "total": total,
                "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
            },
        }
    
    # Try to get from cache with fetcher
    cached = await frontend_cache.get(
        cache_namespace,
        *cache_keys,
        fetcher=fetch_leagues,
        ttl=300,  # 5 minutes fresh
        stale_ttl=3600,  # 1 hour stale
    )
    
    return cached


@router.get("/{league_id}", response_model=dict[str, Any])
async def get_league(
    league_id: str,
    db: AsyncSession = Depends(get_db),
    include_teams: bool = Query(default=False, description="Include teams in response"),
    include_fixtures: bool = Query(default=False, description="Include upcoming fixtures"),
    include_standings: bool = Query(default=False, description="Include standings"),
) -> dict[str, Any]:
    """Get detailed information about a specific league.
    
    Includes all levels of data: teams, fixtures, and standings when requested.
    Uses frontend Redis cache with DB-change revalidation.
    """
    cache_key_parts = (league_id, include_teams, include_fixtures, include_standings)
    cache_namespace = "leagues:detail"
    
    async def fetch_league_detail():
        stmt = (
            select(League, Season)
            .outerjoin(
                Season,
                (Season.league_id == League.id) & (Season.is_current),
            )
            .where(League.id == league_id)
        )
        result = await db.execute(stmt)
        rows = result.fetchall()
        
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"League {league_id} not found",
            )
        
        league = rows[0][0]
        current_season = rows[0][1]
        
        response: dict[str, Any] = {
            "success": True,
            "data": {
                "id": league.id,
                "name": league.name,
                "country": league.country,
                "country_code": league.country_code,
                "is_active": league.is_active,
                "created_at": league.created_at.isoformat() if league.created_at else None,
                "current_season": current_season.model_dump() if current_season else None,
            },
        }
        
        if include_teams:
            teams_stmt = select(Team).where(Team.country == league.country).limit(50)
            teams_result = await db.execute(teams_stmt)
            teams = teams_result.scalars().all()
            response["data"]["teams"] = [
                {
                    "id": t.id,
                    "name": t.name,
                    "short_name": t.short_name,
                    "logo_url": t.logo_url,
                    "country": t.country,
                }
                for t in teams
            ]
        
        if include_fixtures:
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            fixtures_stmt = (
                select(Match)
                .where(
                    Match.league_id == league_id,
                    Match.kickoff_at >= now,
                )
                .order_by(Match.kickoff_at)
                .limit(30)
            )
            fixtures_result = await db.execute(fixtures_stmt)
            fixtures = fixtures_result.scalars().all()
            response["data"]["fixtures"] = [
                {
                    "id": f.id,
                    "home_team_id": f.home_team_id,
                    "away_team_id": f.away_team_id,
                    "home_team_name": f.home_team_name,
                    "away_team_name": f.away_team_name,
                    "kickoff_at": f.kickoff_at.isoformat() if f.kickoff_at else None,
                    "status": f.status,
                    "home_score": f.home_score,
                    "away_score": f.away_score,
                    "is_finished": f.is_finished,
                }
                for f in fixtures
            ]
        
        if include_standings:
            standings_stmt = (
                select(TeamStatistics)
                .where(
                    TeamStatistics.league_id == league_id,
                    TeamStatistics.position.isnot(None),
                )
                .order_by(TeamStatistics.position)
                .limit(50)
            )
            standings_result = await db.execute(standings_stmt)
            standings = standings_result.scalars().all()
            response["data"]["standings"] = [
                {
                    "team_id": ts.internal_team_id,
                    "position": ts.position,
                    "points": ts.points,
                    "played": ts.games_played,
                    "wins": ts.wins,
                    "draws": ts.draws,
                    "losses": ts.losses,
                    "goals_for": ts.goals_for,
                    "goals_against": ts.goals_against,
                    "goal_difference": (ts.goals_for or 0) - (ts.goals_against or 0),
                    "form_rating": ts.form_rating,
                    "average_xg": ts.average_xg,
                }
                for ts in standings
            ]
        
        return response
    
    try:
        cached = await frontend_cache.get(
            cache_namespace,
            *cache_key_parts,
            fetcher=fetch_league_detail,
            ttl=600,
            stale_ttl=3600,
        )
        if isinstance(cached, dict) and cached.get("detail"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=cached["detail"],
            )
        return cached
    except HTTPException:
        raise
    except Exception:
        # Fallback to direct DB call if cache fails
        result = await fetch_league_detail()
        return result


@router.get("/{league_id}/seasons", response_model=dict[str, Any])
async def list_seasons(
    league_id: str,
    db: AsyncSession = Depends(get_db),
    is_current: bool | None = Query(None, description="Filter by current season"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
) -> dict[str, Any]:
    """List seasons for a league."""
    stmt = select(Season).where(Season.league_id == league_id)

    if is_current is not None:
        stmt = stmt.where(Season.is_current == is_current)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar() or 0

    stmt = stmt.order_by(Season.year.desc().nullslast(), Season.start_date.desc().nullslast())
    stm_with_limit = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stm_with_limit)
    seasons = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": s.id,
                "league_id": s.league_id,
                "name": s.name,
                "year": s.year,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "is_current": s.is_current,
            }
            for s in seasons
        ],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
        },
    }


@router.get("/country/{country}", response_model=dict[str, Any])
async def get_country_leagues(
    country: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get all league levels for a country.
    
    Returns all leagues (across all tiers) for the given country,
    including their current seasons, team counts, and standings summary.
    """
    cache_namespace = "leagues:country"
    cache_key_parts = (country.lower(),)
    
    async def fetch_country_leagues():
        stmt = (
            select(League, Season)
            .outerjoin(
                Season,
                (Season.league_id == League.id) & (Season.is_current),
            )
            .where(League.country == country)
            .order_by(League.name)
        )
        result = await db.execute(stmt)
        rows = result.fetchall()
        
        leagues_data: dict[str, Any] = {}
        
        for league, season in rows:
            if league.id not in leagues_data:
                leagues_data[league.id] = {
                    "id": league.id,
                    "name": league.name,
                    "country": league.country,
                    "country_code": league.country_code,
                    "is_active": league.is_active,
                    "created_at": league.created_at.isoformat() if league.created_at else None,
                    "tier": league.tier,
                    "current_season": None,
                    "team_count": 0,
                    "standings_summary": None,
                }
            
            if season:
                leagues_data[league.id]["current_season"] = season.model_dump()
        
        league_ids = list(leagues_data.keys())
        
        if league_ids:
            team_counts_stmt = (
                select(Team.country, func.count(Team.id).label("count"))
                .where(Team.country == country)
                .group_by(Team.country)
            )
            team_result = await db.execute(team_counts_stmt)
            team_counts = {row.country: row.count for row in team_result}
            leagues_data[league_ids[0]]["team_count"] = team_counts.get(country, 0)
            
            for lid in league_ids:
                standings_stmt = (
                    select(TeamStatistics)
                    .where(
                        TeamStatistics.league_id == lid,
                        TeamStatistics.position.isnot(None),
                    )
                    .order_by(TeamStatistics.position)
                    .limit(3)
                )
                standings_result = await db.execute(standings_stmt)
                top_teams = standings_result.scalars().all()
                leagues_data[lid]["standings_summary"] = [
                    {
                        "position": ts.position,
                        "points": ts.points,
                        "team_id": ts.internal_team_id,
                        "played": ts.games_played,
                        "wins": ts.wins,
                        "draws": ts.draws,
                        "losses": ts.losses,
                    }
                    for ts in top_teams
                ]
        
        leagues_list = sorted(
            leagues_data.values(),
            key=lambda x: x.get("tier") or 999,
        )
        
        return {
            "success": True,
            "data": leagues_list,
            "meta": {
                "country": country,
                "total_leagues": len(leagues_list),
            },
        }
    
    try:
        cached = await frontend_cache.get(
            cache_namespace,
            *cache_key_parts,
            fetcher=fetch_country_leagues,
            ttl=600,
            stale_ttl=3600,
        )
        return cached
    except Exception:
        result = await fetch_country_leagues()
        return result


@router.get("/{league_id}/standings", response_model=dict[str, Any])
async def get_standings(
    league_id: str,
    db: AsyncSession = Depends(get_db),
    season_id: str | None = Query(None, description="Season ID (defaults to current season)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """Get standings for a league (optionally filtered by season).
    
    Uses frontend Redis cache with DB-change revalidation.
    """
    page_num = get_page(page)
    ps = get_page_size(page_size)
    
    cache_namespace = "leagues:standings"
    cache_key_parts = (league_id, season_id or "current", page_num, ps)
    
    async def fetch_standings():
        stmt = select(TeamStatistics).where(TeamStatistics.league_id == league_id)

        if season_id:
            stmt = stmt.where(TeamStatistics.season_id == season_id)
        else:
            stmt = stmt.where(TeamStatistics.position.isnot(None))

        count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
        total = count_result.scalar() or 0

        stmt = stmt.where(TeamStatistics.position.isnot(None)).order_by(
            TeamStatistics.position
        )
        result = await db.execute(stmt.offset((page_num - 1) * ps).limit(ps))
        team_stats = result.scalars().all()

        return {
            "success": True,
            "data": [
                {
                    "team_id": ts.internal_team_id,
                    "team_name": "",
                    "position": ts.position,
                    "points": ts.points,
                    "played": ts.games_played,
                    "wins": ts.wins,
                    "draws": ts.draws,
                    "losses": ts.losses,
                    "goals_for": ts.goals_for,
                    "goals_against": ts.goals_against,
                    "goal_difference": (ts.goals_for or 0) - (ts.goals_against or 0),
                    "clean_sheets": ts.clean_sheets,
                    "form_rating": ts.form_rating,
                    "average_possession": ts.average_possession,
                    "average_xg": ts.average_xg,
                    "average_xga": ts.average_xga,
                }
                for ts in team_stats
            ],
            "meta": {
                "page": page_num,
                "page_size": ps,
                "total": total,
                "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
            },
        }
    
    try:
        cached = await frontend_cache.get(
            cache_namespace,
            *cache_key_parts,
            fetcher=fetch_standings,
            ttl=600,
            stale_ttl=3600,
        )
        return cached
    except Exception:
        result = await fetch_standings()
        return result
