"""Admin endpoints.

GET  /api/v1/admin/stats              -- platform-wide statistics
GET  /api/v1/admin/prediction-runs     -- list prediction runs
GET  /api/v1/admin/models              -- list model versions
POST /api/v1/admin/predictions/generate -- trigger batch prediction generation
DELETE /api/v1/admin/leagues/all        -- delete all leagues
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import verify_admin_api_key
from db.database import get_db
from models.match import Match, Prediction, PredictionRun

router = APIRouter(prefix="/admin", tags=["admin"])


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

    from models.league import League, Team
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
    db: AsyncSession = Depends(get_db),
    league_ids: list[str] | None = Query(
        None, alias="league_ids", description="League IDs to generate predictions for"
    ),
    force_refresh: bool = Query(False, description="Force regeneration of existing predictions"),
) -> dict[str, Any]:
    """Trigger batch prediction generation.

    Queues a background prediction job for upcoming matches.
    """
    from jobs.job_manager import create_job, update_job_status
    from services.prediction_orchestrator import PredictionOrchestrator

    job_id = await create_job(
        job_type="batch_prediction",
        extra={
            "league_ids": league_ids or [],
            "force_refresh": force_refresh,
            "trigger": "admin_api",
        },
    )

    orchestrator = PredictionOrchestrator()

    async def _run_batch():
        try:
            await update_job_status(job_id, "running")
            result = await orchestrator.generate_upcoming_predictions(
                league_ids=league_ids,
                db_session=db,
                job_id=job_id,
            )
            await update_job_status(
                job_id,
                "completed",
                succeeded=result.get("generated", 0),
                failed=result.get("failed", 0),
                extra={"total_matches": result.get("total_matches", 0)},
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
