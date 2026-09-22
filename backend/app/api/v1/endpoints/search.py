"""Search API endpoint.

GET  /api/v1/search  -- unified search across teams, leagues, matches, and predictions
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_search_key, get_cached, set_cached
from db.database import get_db
from models.league import League, Team
from models.match import Match

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=dict[str, Any])
async def search(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query"),
    type: str | None = Query(None, description="Filter by type: team, league, match, prediction"),
    league_id: str | None = Query(None, description="Restrict match search to a league"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Unified search across teams, leagues, matches, and predictions."""
    search_query = q.strip()
    if len(search_query) < 2:
        return {
            "success": True,
            "data": {"teams": [], "leagues": [], "matches": [], "predictions": []},
            "meta": {"query": search_query, "total": 0},
        }

    cache_key = cache_search_key(q=search_query, type=type, league_id=league_id, limit=limit)

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass
    teams: list[dict[str, Any]] = []
    leagues: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []

    if type in (None, "team"):
        stmt = select(Team).where(
            (Team.name.ilike(f"%{search_query}%"))
            | (Team.short_name.ilike(f"%{search_query}%"))
            | (Team.slug.ilike(f"%{search_query}%"))
        ).where(Team.is_active).order_by(Team.name).limit(limit)
        result = await db.execute(stmt)
        teams = [
            {
                "id": t.id,
                "type": "team",
                "name": t.name,
                "short_name": t.short_name,
                "slug": t.slug,
                "logo_url": t.logo_url,
                "country": t.country,
            }
            for t in result.scalars().all()
        ]

    if type in (None, "league"):
        stmt = select(League).where(
            (League.name.ilike(f"%{search_query}%"))
            | (League.country.ilike(f"%{search_query}%"))
        ).where(League.is_active).order_by(League.name).limit(limit)
        result = await db.execute(stmt)
        leagues = [
            {
                "id": lg.id,
                "type": "league",
                "name": lg.name,
                "country": lg.country,
                "country_code": lg.country_code,
            }
            for lg in result.scalars().all()
        ]

    if type in (None, "match"):
        like_pattern = f"%{search_query}%"
        stmt = select(Match).where(
            (Match.home_team_name.ilike(like_pattern))
            | (Match.away_team_name.ilike(like_pattern))
        )
        if league_id:
            stmt = stmt.where(Match.league_id == league_id)
        stmt = stmt.order_by(Match.kickoff_at.desc()).limit(limit)
        result = await db.execute(stmt)
        matches = [
            {
                "id": m.id,
                "type": "match",
                "league_id": m.league_id,
                "home_team_name": m.home_team_name,
                "away_team_name": m.away_team_name,
                "kickoff_at": m.kickoff_at.isoformat() if m.kickoff_at else None,
                "status": m.status,
                "home_score": m.home_score,
                "away_score": m.away_score,
                "is_finished": m.is_finished,
            }
            for m in result.scalars().all()
        ]

    if type in (None, "prediction"):
        from models.match import Prediction

        stmt = select(Prediction).where(
            Prediction.model_version.ilike(f"%{search_query}%")
        ).order_by(Prediction.generated_at.desc()).limit(limit)
        result = await db.execute(stmt)
        predictions = [
            {
                "id": p.id,
                "type": "prediction",
                "match_id": p.match_id,
                "model_version": p.model_version,
                "prediction_version": p.prediction_version,
                "generated_at": p.generated_at.isoformat() if p.generated_at else None,
                "home_probability": p.home_probability,
                "draw_probability": p.draw_probability,
                "away_probability": p.away_probability,
            }
            for p in result.scalars().all()
        ]

    total = len(teams) + len(leagues) + len(matches) + len(predictions)

    response = {
        "success": True,
        "data": {
            "teams": teams,
            "leagues": leagues,
            "matches": matches,
            "predictions": predictions,
        },
        "meta": {
            "query": search_query,
            "total": total,
        },
    }

    try:
        await set_cached(cache_key, response, ttl=1800)
    except Exception:
        pass

    return response
