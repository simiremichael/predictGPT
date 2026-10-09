"""Admin endpoints.

GET  /api/v1/admin/stats              -- platform-wide statistics
GET  /api/v1/admin/prediction-runs     -- list prediction runs
GET  /api/v1/admin/models              -- list model versions
GET  /api/v1/admin/leagues             -- list leagues (internal + provider ids)
GET  /api/v1/admin/teams               -- list teams (internal + provider ids)
POST /api/v1/admin/predictions/generate -- trigger batch prediction generation
POST /api/v1/admin/leagues/resync      -- resync a league from the provider
POST /api/v1/admin/teams/resync       -- resync a team from the provider
POST /api/v1/admin/fixtures/resync    -- resync fixtures within a date range
DELETE /api/v1/admin/leagues/{id}      -- delete a single league (cascade)
DELETE /api/v1/admin/leagues           -- delete many leagues (ids=)
DELETE /api/v1/admin/teams/{id}       -- delete a single team (cascade)
DELETE /api/v1/admin/teams            -- delete many teams (ids=)
DELETE /api/v1/admin/predictions/{id} -- delete a single prediction
DELETE /api/v1/admin/predictions      -- delete many predictions (ids=)
DELETE /api/v1/admin/leagues/all       -- delete all leagues
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.security import verify_admin_api_key
from db.database import AsyncSessionLocal, get_db
from models.league import League, ProviderLeague, ProviderTeam, Season, Team
from models.match import (
    ConfirmedLineup,
    HeadToHead,
    Injury,
    Match,
    MatchStatistics,
    NewsItem,
    Odds,
    Player,
    PredictedLineup,
    Prediction,
    PredictionResult,
    PredictionRun,
    PredictionScoreline,
    ProviderPlayer,
    Suspension,
    TeamForm,
    TeamStatistics,
)
from models.research import (
    EvidenceConflict,
    ResearchEvidence,
    ResearchRun,
    WebSourceExtended,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


async def _delete_all_predictions(db: AsyncSession) -> list[str]:
    """Delete all predictions, scorelines, and related evidence from the database."""
    deleted_ids: list[str] = []

    result = await db.execute(select(Prediction.id))
    deleted_ids = [row[0] for row in result.all()]

    await db.execute(delete(PredictionScoreline))
    await db.execute(delete(Prediction))
    await db.execute(delete(ResearchEvidence))
    await db.execute(delete(ResearchRun))
    await db.commit()

    return deleted_ids


@router.get("/stats", response_model=dict[str, Any])
async def get_admin_stats(
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Platform-wide statistics (admin only)."""
    stats: dict[str, Any] = {}

    match_count_stmt = select(func.count()).select_from(Match)
    result = await db.execute(match_count_stmt)
    stats["total_matches"] = result.scalar() or 0

    prediction_count_stmt = select(func.count()).select_from(Prediction)
    result = await db.execute(prediction_count_stmt)
    stats["total_predictions"] = result.scalar() or 0

    finished_matches_stmt = select(func.count()).where(Match.is_finished).select_from(Match)
    result = await db.execute(finished_matches_stmt)
    stats["total_finished_matches"] = result.scalar() or 0

    upcoming_matches_stmt = (
        select(func.count())
        .where(not Match.is_finished)
        .where(Match.status == "scheduled")
        .select_from(Match)
    )
    result = await db.execute(upcoming_matches_stmt)
    stats["upcoming_matches"] = result.scalar() or 0

    from models.research import ResearchRun

    league_count_stmt = select(func.count()).select_from(League)
    result = await db.execute(league_count_stmt)
    stats["total_leagues"] = result.scalar() or 0

    team_count_stmt = select(func.count()).select_from(Team)
    result = await db.execute(team_count_stmt)
    stats["total_teams"] = result.scalar() or 0

    research_count_stmt = select(func.count()).select_from(ResearchRun)
    result = await db.execute(research_count_stmt)
    stats["total_research_runs"] = result.scalar() or 0

    completed_research_stmt = (
        select(func.count()).where(ResearchRun.status == "completed").select_from(ResearchRun)
    )
    result = await db.execute(completed_research_stmt)
    stats["completed_research_runs"] = result.scalar() or 0

    avg_data_quality_stmt = select(func.avg(Prediction.confidence))
    result = await db.execute(avg_data_quality_stmt)
    avg_quality = result.scalar()
    stats["average_prediction_confidence"] = float(avg_quality) if avg_quality else None

    recent_predictions_stmt = select(Prediction).order_by(desc(Prediction.generated_at)).limit(5)
    result = await db.execute(recent_predictions_stmt)
    recent = result.scalars().all()
    stats["recent_predictions"] = [
        {
            "id": p.id,
            "match_id": p.match_id,
            "model_version": p.model_version,
            "generated_at": p.generated_at.isoformat() if p.generated_at else None,
            "confidence": p.confidence,
            "home_probability": p.home_probability,
            "away_probability": p.away_probability,
        }
        for p in recent
    ]

    return {
        "success": True,
        "data": stats,
        "meta": {"generated_at": datetime.utcnow().isoformat()},
    }


@router.get("/prediction-runs", response_model=dict[str, Any])
async def list_prediction_runs(
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
    status_: str | None = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """List prediction runs with pagination and filtering."""
    offset = (page - 1) * page_size

    stmt = select(PredictionRun)
    if status_:
        stmt = stmt.where(PredictionRun.status == status_)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    result = await db.execute(count_stmt)
    total = result.scalar() or 0

    stmt = stmt.order_by(desc(PredictionRun.started_at)).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    runs = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "model_version": r.model_version,
                "provider_used": r.provider_used,
                "status": r.status,
                "matches_processed": r.matches_processed,
                "matches_succeeded": r.matches_succeeded,
                "matches_failed": r.matches_failed,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "error_message": r.error_message,
            }
            for r in runs
        ],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)) if page_size > 0 else 1,
        },
    }


@router.get("/models", response_model=dict[str, Any])
async def list_models(
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
    is_active: bool | None = Query(None),
) -> dict[str, Any]:
    """List model versions."""
    from models.match import ModelVersion

    stmt = select(ModelVersion)
    if is_active is not None:
        stmt = stmt.where(ModelVersion.is_active == is_active)
    stmt = stmt.order_by(desc(ModelVersion.created_at))

    result = await db.execute(stmt)
    models = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": m.id,
                "version": m.version,
                "model_type": m.model_type,
                "description": m.description,
                "parameters": m.parameters_json,
                "is_active": m.is_active,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in models
        ],
    }


@router.post("/predictions/generate", response_model=dict[str, Any])
async def trigger_batch_predictions(
    _admin: str = Depends(verify_admin_api_key),
    league_ids: list[str] | None = Query(
        None, alias="league_ids", description="League IDs to generate predictions for"
    ),
    force_refresh: bool = Query(False, description="Force regeneration of existing predictions"),
    clear_all: bool = Query(
        False,
        description="Delete ALL existing predictions from the database before generating new ones",
    ),
    include_research: bool = Query(
        True,
        description="Run DuckDuckGo research for team news before generating each prediction",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Maximum number of upcoming matches to generate predictions for",
    ),
) -> dict[str, Any]:
    """Trigger batch prediction generation.

    Queues a background prediction job for upcoming matches.
    """
    from jobs.job_manager import create_job, update_job_status

    job_id = await create_job(
        job_type="batch_prediction",
        extra={
            "league_ids": league_ids or [],
            "force_refresh": force_refresh,
            "clear_all": clear_all,
            "include_research": include_research,
            "trigger": "admin_api",
        },
    )

    async def _run_batch():
        try:
            await update_job_status(job_id, "running")
            async with AsyncSessionLocal() as db:
                if clear_all:
                    deleted_count = await _delete_all_predictions(db)
                    logger.info("Cleared all predictions", extra={"deleted": len(deleted_count)})

                from services.ai_prediction_service import AIPredictionService

                service = AIPredictionService(db_session=db)
                result = await service.generate_predictions_for_league(
                    league_ids=league_ids,
                    limit=limit,
                    include_research=include_research,
                )

                all_predictions = result.get("data", {}).get("predictions", [])
                all_errors = result.get("data", {}).get("errors", [])

                await update_job_status(
                    job_id,
                    "completed",
                    succeeded=result.get("data", {}).get("generated", 0),
                    failed=result.get("data", {}).get("failed", 0),
                    extra={
                        "total_matches": result.get("data", {}).get("total_matches", 0),
                        "predictions": all_predictions,
                        "errors": all_errors,
                        "clear_all": clear_all,
                    },
                )
        except Exception as exc:
            await update_job_status(job_id, "failed", errors=[str(exc)])

    import asyncio

    asyncio.create_task(_run_batch())

    return {
        "success": True,
        "data": {
            "job_id": job_id,
            "status": "queued",
        },
    }


@router.delete("/leagues/all", response_model=dict[str, Any])
async def delete_all_leagues(
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete all leagues from the database (admin only).

    Cascade-deletes dependent rows in related tables first to satisfy
    foreign-key constraints.
    """
    from models.league import League, ProviderLeague, Season

    count_result = await db.execute(select(func.count()).select_from(League))
    deleted_count = count_result.scalar() or 0

    for model in (ProviderLeague,):
        await db.execute(delete(model))

    await db.execute(delete(League))
    await db.commit()

    return {
        "success": True,
        "data": {"deleted": deleted_count},
        "meta": {"message": f"Deleted {deleted_count} league(s)"},
    }


# ── Admin listings (expose both internal & provider ids) ──────────────── #


@router.get("/leagues", response_model=dict[str, Any])
async def admin_list_leagues(
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None, description="Filter by league name"),
    is_active: bool | None = Query(None),
) -> dict[str, Any]:
    """List leagues with their internal id and provider league id (admin only)."""
    from models.league import League, ProviderLeague

    offset = (page - 1) * page_size
    stmt = select(League).order_by(League.name)
    if search:
        stmt = stmt.where(League.name.ilike(f"%{search}%"))
    if is_active is not None:
        stmt = stmt.where(League.is_active.is_(is_active))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0

    rows = (await db.execute(stmt.offset(offset).limit(page_size))).scalars().all()

    out = []
    for lg in rows:
        provider_id = (
            await db.execute(
                select(ProviderLeague.provider_league_id)
                .where(ProviderLeague.internal_league_id == lg.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        out.append(
            {
                "id": lg.id,
                "provider_league_id": provider_id,
                "name": lg.name,
                "country": lg.country,
                "country_code": lg.country_code,
                "is_active": lg.is_active,
                "created_at": lg.created_at.isoformat() if lg.created_at else None,
            }
        )

    return {
        "success": True,
        "data": out,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)) if page_size else 1,
        },
    }


@router.get("/teams", response_model=dict[str, Any])
async def admin_list_teams(
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    league_id: str | None = Query(None, description="Provider league id to scope"),
    search: str | None = Query(None, description="Filter by team name"),
) -> dict[str, Any]:
    """List teams with their internal id and provider team id (admin only)."""
    from models.match import Match

    offset = (page - 1) * page_size
    stmt = (
        select(
            Team.id,
            Team.name,
            Team.short_name,
            Team.country,
            Team.is_active,
            Team.created_at,
            ProviderTeam.provider_team_id.label("provider_team_id"),
            ProviderTeam.provider_league_id.label("provider_league_id"),
        )
        .outerjoin(ProviderTeam, ProviderTeam.internal_team_id == Team.id)
    )
    if league_id:
        stmt = stmt.where(ProviderTeam.provider_league_id == league_id)
    if search:
        stmt = stmt.where(Team.name.ilike(f"%{search}%"))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0

    rows = (await db.execute(stmt.offset(offset).limit(page_size))).all()

    out = []
    for r in rows:
        match_count = (
            await db.execute(
                select(func.count())
                .select_from(Match)
                .where((Match.home_team_id == r.id) | (Match.away_team_id == r.id))
            )
        ).scalar() or 0
        out.append(
            {
                "id": r.id,
                "provider_team_id": r.provider_team_id,
                "league_id": r.provider_league_id,
                "name": r.name,
                "short_name": r.short_name,
                "country": r.country,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "match_count": match_count,
            }
        )

    return {
        "success": True,
        "data": out,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)) if page_size else 1,
        },
    }


# ── Deletes ───────────────────────────────────────────────────────────── #


async def _delete_match_scoped_dependents(db: AsyncSession, match_ids: list[str]) -> None:
    """Delete every table that references a match id, then the matches themselves."""
    if not match_ids:
        return
    # research tables reference Match via FK (research_runs.match_id is NOT NULL,
    # others nullable). Clean children that reference a research_run *and* those
    # that reference the match directly, in dependency order, before dropping the
    # Match rows themselves.
    run_ids = select(ResearchRun.id).where(ResearchRun.match_id.in_(match_ids))
    await db.execute(
        delete(EvidenceConflict).where(
            or_(
                EvidenceConflict.match_id.in_(match_ids),
                EvidenceConflict.research_run_id.in_(run_ids),
            )
        )
    )
    await db.execute(
        delete(ResearchEvidence).where(
            or_(
                ResearchEvidence.match_id.in_(match_ids),
                ResearchEvidence.research_run_id.in_(run_ids),
            )
        )
    )
    await db.execute(delete(WebSourceExtended).where(WebSourceExtended.match_id.in_(match_ids)))
    await db.execute(delete(ResearchRun).where(ResearchRun.match_id.in_(match_ids)))

    preds = select(Prediction.id).where(Prediction.match_id.in_(match_ids))
    await db.execute(delete(PredictionScoreline).where(PredictionScoreline.prediction_id.in_(preds)))
    await db.execute(delete(PredictionResult).where(PredictionResult.prediction_id.in_(preds)))
    await db.execute(delete(Prediction).where(Prediction.match_id.in_(match_ids)))
    await db.execute(delete(MatchStatistics).where(MatchStatistics.match_id.in_(match_ids)))
    await db.execute(delete(PredictedLineup).where(PredictedLineup.internal_fixture_id.in_(match_ids)))
    await db.execute(delete(ConfirmedLineup).where(ConfirmedLineup.internal_fixture_id.in_(match_ids)))
    await db.execute(delete(Odds).where(Odds.internal_fixture_id.in_(match_ids)))
    await db.execute(delete(NewsItem).where(NewsItem.match_id.in_(match_ids)))
    await db.execute(delete(TeamForm).where(TeamForm.fixture_id.in_(match_ids)))
    await db.execute(delete(Match).where(Match.id.in_(match_ids)))


@router.delete("/leagues/{league_id}", response_model=dict[str, Any])
async def delete_league(
    league_id: str,
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a single league and all of its dependent data (admin only)."""
    from models.league import League, ProviderLeague, Season
    from models.match import HeadToHead, TeamStatistics

    league = (await db.execute(select(League).where(League.id == league_id))).scalar_one_or_none()
    if league is None:
        raise HTTPException(status_code=404, detail=f"League {league_id} not found")

    match_ids = [
        r
        for r in (await db.execute(select(Match.id).where(Match.league_id == league_id))).scalars().all()
    ]
    await _delete_match_scoped_dependents(db, match_ids)
    await db.execute(delete(TeamStatistics).where(TeamStatistics.league_id == league_id))
    await db.execute(delete(HeadToHead).where(HeadToHead.league_id == league_id))
    await db.execute(delete(ProviderLeague).where(ProviderLeague.internal_league_id == league_id))
    await db.execute(delete(Season).where(Season.league_id == league_id))
    await db.execute(delete(League).where(League.id == league_id))
    await db.commit()
    return {"success": True, "data": {"deleted": 1, "league_id": league_id},
            "meta": {"message": f"Deleted league {league_id}"}}


@router.delete("/leagues", response_model=dict[str, Any])
async def delete_leagues_bulk(
    ids: list[str] = Query(None, description="League internal ids"),
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not ids:
        return {"success": True, "data": {"deleted": 0}}
    deleted = 0
    for lid in ids:
        try:
            await delete_league(lid, _admin=_admin, db=db)  # type: ignore[arg-type]
            deleted += 1
        except HTTPException:
            raise
        except Exception:
            logger.exception("Failed to delete league %s", lid)
    await db.commit()
    return {"success": True, "data": {"deleted": deleted, "league_ids": ids}}


@router.delete("/teams/{team_id}", response_model=dict[str, Any])
async def delete_team(
    team_id: str,
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from models.league import ProviderTeam

    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

    match_ids = (
        await db.execute(
            select(Match.id).where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
        )
    ).scalars().all()
    await _delete_match_scoped_dependents(db, match_ids)
    await db.execute(delete(TeamStatistics).where(TeamStatistics.internal_team_id == team_id))
    await db.execute(delete(TeamForm).where(TeamForm.internal_team_id == team_id))
    await db.execute(delete(Injury).where(Injury.internal_team_id == team_id))
    await db.execute(delete(Suspension).where(Suspension.internal_team_id == team_id))
    player_ids = select(Player.id).where(Player.team_id == team_id)
    await db.execute(delete(ProviderPlayer).where(ProviderPlayer.internal_player_id.in_(player_ids)))
    await db.execute(delete(Player).where(Player.team_id == team_id))
    await db.execute(delete(ResearchEvidence).where(ResearchEvidence.team_id == team_id))
    await db.execute(
        delete(HeadToHead).where(
            (HeadToHead.team_a_internal_id == team_id)
            | (HeadToHead.team_b_internal_id == team_id)
        )
    )
    await db.execute(delete(PredictedLineup).where(PredictedLineup.team_id == team_id))
    await db.execute(delete(ConfirmedLineup).where(ConfirmedLineup.team_id == team_id))
    await db.execute(delete(ProviderTeam).where(ProviderTeam.internal_team_id == team_id))
    await db.execute(delete(Team).where(Team.id == team_id))
    await db.commit()
    return {"success": True, "data": {"deleted": 1, "team_id": team_id},
            "meta": {"message": f"Deleted team {team_id}"}}


@router.delete("/teams", response_model=dict[str, Any])
async def delete_teams_bulk(
    ids: list[str] = Query(None, description="Team internal ids"),
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not ids:
        return {"success": True, "data": {"deleted": 0}}
    deleted = 0
    for tid in ids:
        try:
            await delete_team(tid, _admin=_admin, db=db)  # type: ignore[arg-type]
            deleted += 1
        except HTTPException:
            raise
        except Exception:
            logger.exception("Failed to delete team %s", tid)
    await db.commit()
    return {"success": True, "data": {"deleted": deleted, "team_ids": ids}}


@router.delete("/predictions/{prediction_id}", response_model=dict[str, Any])
async def delete_prediction(
    prediction_id: str,
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from models.match import Prediction

    existed = (await db.execute(select(Prediction.id).where(Prediction.id == prediction_id))).scalar_one_or_none()
    if existed is None:
        raise HTTPException(status_code=404, detail=f"Prediction {prediction_id} not found")
    await db.execute(delete(PredictionResult).where(PredictionResult.prediction_id == prediction_id))
    await db.execute(delete(PredictionScoreline).where(PredictionScoreline.prediction_id == prediction_id))
    await db.execute(delete(Prediction).where(Prediction.id == prediction_id))
    await db.commit()
    return {"success": True, "data": {"deleted": 1, "prediction_id": prediction_id}}


@router.delete("/predictions", response_model=dict[str, Any])
async def delete_predictions_bulk(
    ids: list[str] = Query(None, description="Prediction ids"),
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from models.match import Prediction, PredictionResult, PredictionScoreline

    if not ids:
        return {"success": True, "data": {"deleted": 0}}
    await db.execute(delete(PredictionResult).where(PredictionResult.prediction_id.in_(ids)))
    await db.execute(delete(PredictionScoreline).where(PredictionScoreline.prediction_id.in_(ids)))
    result = await db.execute(delete(Prediction).where(Prediction.id.in_(ids)))
    await db.commit()
    return {"success": True, "data": {"deleted": result.rowcount, "prediction_ids": ids}}


# ── Manual resync endpoints ───────────────────────────────────────────── #


@router.post("/leagues/{league_id}/resync", response_model=dict[str, Any])
async def resync_league(
    league_id: str,
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Resync a single league (metadata + standings) from the provider (admin only)."""
    from api.v1.endpoints.providers import _save_leagues, _save_standings
    from football_data.factory import get_football_provider

    provider = get_football_provider()
    counts: dict[str, int] = {}
    try:
        async with provider:
            league = await provider.get_league(league_id)
            if not league:
                raise HTTPException(status_code=404, detail=f"League {league_id} not found on provider")
            await _save_leagues(db, [league])
            counts["leagues"] = 1

            # Resolve the internal league id to find the current season.
            internal_league_id = (
                await db.execute(
                    select(League.id)
                    .join(ProviderLeague, ProviderLeague.internal_league_id == League.id)
                    .where(ProviderLeague.provider_league_id == league_id)
                    .limit(1)
                )
            ).scalar_one_or_none()

            season_id = None
            if internal_league_id:
                season_id = (
                    await db.execute(
                        select(Season.id)
                        .where(Season.league_id == internal_league_id, Season.is_current.is_(True))
                        .limit(1)
                    )
                ).scalar_one_or_none()

            if season_id:
                standings = await provider.get_standings(
                    league_id=league_id, season_id=season_id
                )
                if standings:
                    await _save_standings(db, [standings])
                    counts["standings"] = len(getattr(standings, "standings", []) or [])
            await db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("League resync failed")
        return {"success": False, "data": counts, "meta": {"message": f"Resync failed: {exc}"}}
    return {"success": True, "data": counts, "meta": {"message": f"Resynced league {league_id}"}}


@router.post("/teams/{team_id}/resync", response_model=dict[str, Any])
async def resync_team(
    team_id: str,
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Resync a single team from the provider (admin only)."""
    from api.v1.endpoints.providers import _save_teams
    from football_data.factory import get_football_provider

    provider = get_football_provider()
    counts: dict[str, int] = {}
    try:
        async with provider:
            team = await provider.get_team(team_id)
            if not team:
                raise HTTPException(status_code=404, detail=f"Team {team_id} not found on provider")
            await _save_teams(db, [team])
            await db.commit()
            counts["teams"] = 1
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("Team resync failed")
        return {"success": False, "data": counts, "meta": {"message": f"Resync failed: {exc}"}}
    return {"success": True, "data": counts, "meta": {"message": f"Resynced team {team_id}"}}


@router.post("/fixtures/resync", response_model=dict[str, Any])
async def resync_fixtures(
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
    date_from: str | None = Query(None, description="ISO date e.g. 2026-10-01"),
    date_to: str = Query(..., description="ISO date e.g. 2026-10-31"),
    league_id: str | None = Query(None, description="Optional provider league id to scope"),
) -> dict[str, Any]:
    """Resync fixtures within a date range from the provider (admin only)."""
    from api.v1.endpoints.providers import _map_fixture_teams, _save_fixtures
    from football_data.factory import get_football_provider
    from jobs.daily_sync import _get_current_season_id_by_league

    provider = get_football_provider()

    def _parse(v: str | None) -> datetime | None:
        if not v:
            return None
        try:
            return datetime.fromisoformat(v)
        except Exception:
            return None

    from_dt = _parse(date_from) or (datetime.utcnow() - timedelta(days=1))
    to_dt = _parse(date_to) or datetime.utcnow()
    counts: dict[str, int] = {}
    try:
        async with provider:
            fixtures = await provider.get_fixtures(
                league_id=league_id, from_date=from_dt, to_date=to_dt
            )
            counts["fixtures"] = len(fixtures) if fixtures else 0

            if not fixtures:
                return {"success": True, "data": counts, "meta": {"message": "No fixtures returned"}}

            # Scope to current seasons (the provider returns the whole sport).
            current_season_ids: set[str] = set()
            if league_id:
                # league_id is a *provider* league id; provider.get_fixtures
                # scopes on it already, so no extra DB lookup is needed.
                sid = await _get_current_season_id_by_league(db, league_id)
                if sid:
                    current_season_ids.add(str(sid))
            else:
                all_seasons = await provider.get_seasons()
                current = [s for s in (all_seasons or []) if getattr(s, "is_current", False)]
                current_season_ids = {str(s.provider_season_id or s.id) for s in current}

            scoped = [
                fx
                for fx in fixtures
                if getattr(fx, "season_id", None) in current_season_ids
                or not current_season_ids
            ]
            if scoped:
                await _save_fixtures(db, scoped)
                await _map_fixture_teams(db, scoped)
                await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("Fixture resync failed")
        return {"success": False, "data": counts, "meta": {"message": f"Resync failed: {exc}"}}
    return {"success": True, "data": counts, "meta": {"message": f"Resynced fixtures {from_dt.date()}..{to_dt.date()}"}}
