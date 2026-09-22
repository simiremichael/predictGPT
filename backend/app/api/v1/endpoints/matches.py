"""Match API endpoints.

GET  /api/v1/matches                        -- list matches with filters
GET  /api/v1/matches/upcoming               -- upcoming matches
GET  /api/v1/matches/today                  -- today's matches
GET  /api/v1/matches/{match_id}             -- match detail
GET  /api/v1/matches/{match_id}/summary   -- match summary for frontend

All data is read from the synchronized database.  No direct provider calls.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from web_research.service import MatchResearchService

from core.cache import (
    cache_match_key,
    cache_match_summary_key,
    cache_matches_list_key,
    get_cached,
    set_cached,
)
from core.exceptions import ProviderNotFoundError
from core.pagination import get_page, get_page_size
from db.database import get_db
from football_data.league_mappings import LeagueMapping
from models.league import League, Team
from models.match import Match, MatchStatistics, TeamStatistics
from schemas.api import MatchBrief, MatchDetailResponse, MatchSummaryResponse

router = APIRouter(prefix="/matches", tags=["matches"])

_app_timezone = UTC


@router.get("", response_model=dict[str, Any])
async def list_matches(
    request: Request,
    db: AsyncSession = Depends(get_db),
    date: str | None = Query(None, description="Filter by specific date (YYYY-MM-DD)"),
    date_from: str | None = Query(None, description="Start date range"),
    date_to: str | None = Query(None, description="End date range"),
    league_id: str | None = Query(None, description="Filter by league internal ID (e.g. 'premier_league')"),
    season_id: str | None = Query(None),
    team_id: str | None = Query(None, description="Filter by team ID"),
    status: str | None = Query(None, description="Filter by status"),
    country: str | None = Query(None),
    provider: str | None = Query(None, description="Filter by provider"),
    upcoming: bool = Query(False),
    today: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """List matches with filtering and pagination."""
    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps

    cache_key = cache_matches_list_key(
        date=date, date_from=date_from, date_to=date_to,
        league_id=league_id, season_id=season_id, team_id=team_id,
        status=status, country=country, provider=provider,
        upcoming=upcoming, today=today,
    )

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = select(Match)

    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        stmt = stmt.where(func.date(Match.kickoff_at) == target_date)
    elif today:
        today_date = datetime.now(_app_timezone).date()
        stmt = stmt.where(func.date(Match.kickoff_at) == today_date)
    elif upcoming:
        now = datetime.now(_app_timezone)
        stmt = stmt.where(Match.kickoff_at >= now)
    else:
        if date_from:
            d = datetime.strptime(date_from, "%Y-%m-%d")
            stmt = stmt.where(Match.kickoff_at >= d)
        if date_to:
            d = datetime.strptime(date_to, "%Y-%m-%d")
            stmt = stmt.where(Match.kickoff_at <= d)

    stmt = _resolve_league_filter(league_id, stmt)
    if season_id:
        stmt = stmt.where(Match.season_id == season_id)
    if team_id:
        stmt = stmt.where(
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id)
        )
    if status:
        stmt = stmt.where(Match.status == status)
    if country:
        stmt = stmt.join(League).where(League.country == country)
    if provider:
        stmt = stmt.where(Match.provider_name == provider)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Match.kickoff_at).offset(offset).limit(ps)
    result = await db.execute(stmt)
    matches = result.scalars().all()

    match_list = [_match_to_brief(m) for m in matches]

    response = {
        "success": True,
        "data": match_list,
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
        },
    }

    try:
        from core.config import get_settings

        ttl = get_settings().cache_ttl_fixtures
        await set_cached(cache_key, response, ttl=ttl)
    except Exception:
        pass

    return response


@router.get("/upcoming", response_model=dict[str, Any])
async def get_upcoming_matches(
    request: Request,
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=30),
    league_id: str | None = Query(None),
    team_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get upcoming matches within the next N days."""
    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps

    now = datetime.now(_app_timezone)
    cutoff = now + timedelta(days=days) if days else None

    cache_key = cache_matches_list_key(
        upcoming=True, days=days, league_id=league_id, team_id=team_id,
        page=page_num, page_size=ps,
    )

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = select(Match).where(
        Match.kickoff_at >= now,
        Match.status.in_(["scheduled", "live"]),
        not Match.is_finished,
    )

    if cutoff:
        stmt = stmt.where(Match.kickoff_at <= cutoff)
    stmt = _resolve_league_filter(league_id, stmt)
    if team_id:
        stmt = stmt.where(
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id)
        )

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Match.kickoff_at).offset(offset).limit(ps)
    result = await db.execute(stmt)
    matches = result.scalars().all()

    match_list = [_match_to_brief(m) for m in matches]

    response = {
        "success": True,
        "data": match_list,
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
        },
    }

    try:
        from core.config import get_settings

        await set_cached(cache_key, response, ttl=get_settings().cache_ttl_fixtures)
    except Exception:
        pass

    return response


@router.get("/today", response_model=dict[str, Any])
async def get_todays_matches(
    request: Request,
    db: AsyncSession = Depends(get_db),
    league_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get today's matches from the local database."""
    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps

    today_date = datetime.now(_app_timezone).date()

    cache_key = cache_matches_list_key(today=True, league_id=league_id, page=page_num, page_size=ps)

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = select(Match).where(func.date(Match.kickoff_at) == today_date)
    stmt = _resolve_league_filter(league_id, stmt)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Match.kickoff_at).offset(offset).limit(ps)
    result = await db.execute(stmt)
    matches = result.scalars().all()

    match_list = [_match_to_brief(m) for m in matches]

    response = {
        "success": True,
        "data": match_list,
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
        },
    }

    try:
        from core.config import get_settings

        await set_cached(cache_key, response, ttl=get_settings().cache_ttl_fixtures)
    except Exception:
        pass

    return response


@router.get("/{match_id}", response_model=dict[str, Any])
async def get_match(
    request: Request,
    match_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed match information."""
    cache_key = cache_match_key(match_id)

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = select(Match).where(Match.id == match_id)
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found",
        )

    match_detail = _build_match_detail(match, db)

    response = {"success": True, "data": match_detail}

    try:
        from core.config import get_settings

        await set_cached(cache_key, response, ttl=get_settings().cache_ttl_fixtures)
    except Exception:
        pass

    return response


@router.get("/{match_id}/summary", response_model=dict[str, Any])
async def get_match_summary(
    request: Request,
    match_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get optimized match summary for frontend display."""
    cache_key = cache_match_summary_key(match_id)

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = select(Match).where(Match.id == match_id)
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found",
        )

    match_brief = _match_to_brief(match)

    prediction = None
    try:
        from core.cache import cache_match_prediction_key
        from services.prediction_orchestrator import PredictionOrchestrator

        pred_key = cache_match_prediction_key(match_id)
        cached_pred = await get_cached(pred_key)
        if cached_pred:
            prediction = cached_pred.get("data")
        else:
            orchestrator = PredictionOrchestrator()
            pred = await orchestrator.get_latest_prediction(match_id, db)
            if pred:
                prediction = pred.model_dump()
        if prediction:
            await set_cached(pred_key, {"success": True, "data": prediction}, ttl=300)
    except Exception:
        pass

    response = {
        "success": True,
        "data": {
            "match": match_brief,
            "prediction": prediction,
            "data_quality": {
                "football": 1.0 if match.retrieved_at else 0.0,
            },
        },
    }

    try:
        from core.config import get_settings

        await set_cached(cache_key, response, ttl=get_settings().cache_ttl_match_summary)
    except Exception:
        pass

    return response


# ── Helpers ────────────────────────────────────────────────────────────── #


def _resolve_league_filter(league_id: str | None, stmt: Any) -> Any:
    """Resolve an internal league ID (e.g. 'premier_league') to DB league IDs.

    If the input matches a known LeagueMapping entry, resolve it via
    ProviderLeague.provider_league_id. Otherwise use it as-is (assumes it
    is already a DB league ID).
    """
    if not league_id:
        return stmt
    from models.league import ProviderLeague

    cfg = LeagueMapping.get(league_id)
    if cfg:
        provider_league_id = cfg.provider_ids.get("api_football", {}).get("league_id")
        if provider_league_id:
            subq = (
                select(ProviderLeague.internal_league_id)
                .where(ProviderLeague.provider_league_id == provider_league_id)
                .where(ProviderLeague.is_active)
            )
            return stmt.where(Match.league_id.in_(subq))
    return stmt.where(Match.league_id == league_id)


def _match_to_brief(m: Match) -> dict[str, Any]:
    """Convert a Match model to a brief dict for API response."""
    league_name = None
    if m.league:
        league_name = m.league.name

    return {
        "id": m.id,
        "league_id": m.league_id,
        "league_name": league_name,
        "season_id": m.season_id,
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
        "retrieved_at": m.retrieved_at.isoformat() if m.retrieved_at else None,
    }


async def _build_match_detail(match: Match, db: AsyncSession) -> dict[str, Any]:
    """Build full match detail including statistics, form, H2H, etc."""
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.league),
            selectinload(Match.season),
        )
        .where(Match.id == match.id)
    )
    result = await db.execute(stmt)
    match_with_rel = result.scalar_one()

    detail: dict[str, Any] = {
        "id": match.id,
        "league_id": match.league_id,
        "league_name": match_with_rel.league.name if match_with_rel.league else None,
        "season_id": match.season_id,
        "home_team": {
            "id": match.home_team_id,
            "name": match.home_team_name or (match_with_rel.home_team.name if match_with_rel.home_team else None),
        } if match.home_team_id else None,
        "away_team": {
            "id": match.away_team_id,
            "name": match.away_team_name or (match_with_rel.away_team.name if match_with_rel.away_team else None),
        } if match.away_team_id else None,
        "kickoff_at": match.kickoff_at.isoformat() if match.kickoff_at else None,
        "status": match.status,
        "venue": match.venue,
        "referee": match.referee,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "is_finished": match.is_finished,
        "statistics": None,
        "form": None,
        "h2h": None,
        "injuries": [],
        "suspensions": [],
        "lineups": [],
        "odds": None,
        "retrieved_at": match.retrieved_at.isoformat() if match.retrieved_at else None,
    }

    # Load statistics
    stats_stmt = select(MatchStatistics).where(MatchStatistics.match_id == match.id)
    stats_result = await db.execute(stats_stmt)
    stats = stats_result.scalar_one_or_none()
    if stats:
        detail["statistics"] = {
            "possession": stats.possession,
            "shots": stats.shots,
            "shots_on_target": stats.shots_on_target,
            "xg": stats.xg,
        }

    # Load team statistics
    home_stats_stmt = select(TeamStatistics).where(
        TeamStatistics.internal_team_id == match.home_team_id,
        TeamStatistics.is_home.is_(True),
    ).order_by(TeamStatistics.retrieved_at.desc()).limit(1)
    home_stats_result = await db.execute(home_stats_stmt)
    home_stats = home_stats_result.scalar_one_or_none()

    away_stats_stmt = select(TeamStatistics).where(
        TeamStatistics.internal_team_id == match.away_team_id,
        TeamStatistics.is_home.is_(False),
    ).order_by(TeamStatistics.retrieved_at.desc()).limit(1)
    away_stats_result = await db.execute(away_stats_stmt)
    away_stats = away_stats_result.scalar_one_or_none()

    if home_stats or away_stats:
        detail["form"] = {
            "home_strength": home_stats.goals_per_game if home_stats else None,
            "away_strength": away_stats.goals_per_game if away_stats else None,
        }

    # Load injuries
    from models.match import ConfirmedLineup, Injury, Odds, Suspension

    injuries_stmt = select(Injury).where(
        (Injury.internal_team_id == match.home_team_id)
        | (Injury.internal_team_id == match.away_team_id)
    ).limit(50)
    injuries_result = await db.execute(injuries_stmt)
    detail["injuries"] = [
        {
            "player_name": i.player_name,
            "position": i.position,
            "injury_type": i.injury_type,
            "severity": i.severity,
            "return_date": i.return_date.isoformat() if i.return_date else None,
        }
        for i in injuries_result.scalars().all()
    ]

    susp_stmt = select(Suspension).where(
        (Suspension.internal_team_id == match.home_team_id)
        | (Suspension.internal_team_id == match.away_team_id)
    ).limit(50)
    susp_result = await db.execute(susp_stmt)
    detail["suspensions"] = [
        {
            "player_name": s.player_name,
            "position": s.position,
            "reason": s.reason,
            "suspension_type": s.suspension_type,
            "suspended_until": s.suspended_until.isoformat() if s.suspended_until else None,
        }
        for s in susp_result.scalars().all()
    ]

    lineups_stmt = select(ConfirmedLineup).where(
        ConfirmedLineup.internal_fixture_id == match.id
    )
    lineups_result = await db.execute(lineups_stmt)
    detail["lineups"] = [ln.model_dump() for ln in lineups_result.scalars().all()]

    odds_stmt = select(Odds).where(
        Odds.internal_fixture_id == match.id
    ).order_by(Odds.retrieved_at.desc()).limit(1)
    odds_result = await db.execute(odds_stmt)
    odds = odds_result.scalar_one_or_none()
    if odds:
        detail["odds"] = {"markets": odds.markets_json}

    return detail
