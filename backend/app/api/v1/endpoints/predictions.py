"""Prediction API endpoints.

GET  /api/v1/matches/{match_id}/prediction     -- retrieve latest prediction
POST /api/v1/matches/{match_id}/predict        -- generate new prediction (force_refresh, include_research)
POST /api/v1/matches/{match_id}/predict/async  -- async prediction generation
GET  /api/v1/predictions                       -- prediction history list
GET  /api/v1/predictions/{prediction_id}        -- prediction detail
GET  /api/v1/matches/{match_id}/predictions     -- all historical predictions for match
GET  /api/v1/matches/{match_id}/predictions/compare
                                               -- compare latest vs previous prediction
POST /api/v1/predictions/jobs/{job_id}/cancel  -- cancel a running prediction job
GET  /api/v1/predictions/stats                -- prediction statistics (admin)

All endpoints delegate to the PredictionOrchestrator which coordinates
the Phase 3 statistical model and Phase 4 research/AI layers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from core.cache import (
    cache_match_key,
    cache_match_prediction_key,
    cache_match_summary_key,
    cache_prediction_key,
    cache_predictions_list_key,
    get_cached,
    invalidate_cache_keys,
    set_cached,
)
from core.config import get_settings
from core.pagination import get_page, get_page_size
from core.security import verify_admin_api_key
from db.database import get_db
from jobs.job_manager import create_job, get_job
from models.match import Match, Prediction, PredictionRun, PredictionScoreline
from schemas.api import PredictionHistoryItem
from services.prediction_data import PredictionDataService
from services.prediction_orchestrator import PredictionOrchestrator

router = APIRouter(tags=["predictions"])


def get_orchestrator() -> PredictionOrchestrator:
    return PredictionOrchestrator()


class PredictRequest(BaseModel):
    force_refresh: bool = False
    include_research: bool = True


class AsyncPredictResponse(BaseModel):
    job_id: str
    status: str
    message: str = "Prediction job queued"


class PredictionStatsResponse(BaseModel):
    total_predictions: int
    predictions_by_model: dict[str, int]
    average_data_quality: float | None
    last_prediction_at: str | None


@router.get(
    "/matches/{match_id}/prediction",
    summary="Get latest prediction for a match",
    description="Returns the most recent valid prediction. Uses cache; does not auto-generate. "
    "Checks whether the stored prediction context hash matches current data.",
    response_model=dict[str, Any],
)
async def get_prediction(
    request: Request,
    match_id: str,
    db: AsyncSession = Depends(get_db),
    orchestrator: PredictionOrchestrator = Depends(get_orchestrator),
) -> dict[str, Any]:
    """Retrieve the latest valid prediction for a match.

    The current context hash is checked before using the response cache. A
    changed context is reported without automatically generating a prediction.
    """
    cache_key = cache_match_prediction_key(match_id)

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    prediction = await orchestrator.get_latest_prediction(match_id, db)
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No prediction found for match {match_id}",
        )

    try:
        data_service = PredictionDataService()
        context = await data_service.get_context(match_id, db)
        current_context_hash = context.context_hash
    except Exception:
        current_context_hash = None

    response = {
        "success": True,
        "data": prediction.model_dump(),
        "meta": {
            "context_hash": prediction.context_hash,
            "current_context_hash": current_context_hash,
            "context_changed": bool(
                prediction.context_hash
                and current_context_hash
                and prediction.context_hash != current_context_hash
            ),
        },
    }

    try:
        await set_cached(cache_key, response, ttl=300)
    except Exception:
        pass

    return response


@router.post(
    "/matches/{match_id}/predict",
    summary="Generate a new prediction for a match",
    description="Generates a new prediction using the Poisson model with optional AI research adjustment. "
    "Creates a new immutable prediction record. Requires admin authentication. "
    "Uses database-first context loading with provider fallback.",
    dependencies=[Depends(verify_admin_api_key)],
    response_model=dict[str, Any],
)
async def create_prediction(
    request: Request,
    match_id: str,
    body: PredictRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    orchestrator: PredictionOrchestrator = Depends(get_orchestrator),
) -> dict[str, Any]:
    """Generate a new prediction for a match.

    Each call creates a new prediction record — existing predictions are never overwritten.
    Uses PredictionDataService for database-first context loading with provider fallback.
    """
    prediction = await orchestrator.generate_prediction(
        match_id=match_id,
        db_session=db,
        force_refresh=body.force_refresh,
        include_research=body.include_research,
    )

    await invalidate_cache_keys(
        cache_match_key(match_id),
        cache_match_prediction_key(match_id),
        cache_match_summary_key(match_id),
    )

    return {
        "success": True,
        "data": {
            "prediction": prediction.model_dump(),
            "context_hash": prediction.context_hash,
        },
        "meta": {
            "match_id": match_id,
            "prediction_version": prediction.prediction_version,
            "message": "Prediction generated successfully",
        },
    }


@router.post(
    "/matches/{match_id}/predict/async",
    summary="Queue a prediction for async generation",
    description="Queues a prediction job and returns immediately. Requires admin authentication.",
    dependencies=[Depends(verify_admin_api_key)],
    response_model=dict[str, Any],
)
async def create_prediction_async(
    request: Request,
    match_id: str,
    body: PredictRequest = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Queue a prediction job for asynchronous processing."""
    job_id = await create_job(
        job_type="prediction",
        entity_id=match_id,
        extra={
            "force_refresh": body.force_refresh,
            "include_research": body.include_research,
        },
    )

    return {
        "success": True,
        "data": {
            "job_id": job_id,
            "status": "queued",
        },
    }


@router.get(
    "/predictions/jobs/{job_id}",
    summary="Get prediction job status",
    response_model=dict[str, Any],
)
async def get_prediction_job(
    request: Request,
    job_id: str,
) -> dict[str, Any]:
    """Retrieve the status of a prediction job."""
    try:
        job = await get_job(job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job store unavailable",
        ) from exc
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return {"success": True, "data": job}


@router.post(
    "/predictions/jobs/{job_id}/cancel",
    summary="Cancel a prediction job",
    dependencies=[Depends(verify_admin_api_key)],
    response_model=dict[str, Any],
)
async def cancel_prediction_job(
    request: Request,
    job_id: str,
) -> dict[str, Any]:
    """Cancel a queued or running prediction job."""
    from jobs.job_manager import cancel_job

    cancelled = await cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job cannot be cancelled (already completed, failed, or not found)",
        )
    return {"success": True, "data": {"job_id": job_id, "status": "cancelled"}}


@router.get(
    "/predictions",
    summary="List prediction history",
    response_model=dict[str, Any],
)
async def list_predictions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    match_id: str | None = Query(None),
    league_id: str | None = Query(None),
    team_id: str | None = Query(None),
    model_version: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """List prediction history with filters and pagination."""
    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps

    cache_key = cache_predictions_list_key(
        match_id=match_id,
        league_id=league_id,
        team_id=team_id,
        model_version=model_version,
        date_from=date_from,
        date_to=date_to,
        page=page_num,
        page_size=ps,
    )

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    from models.league import Team

    home_team = aliased(Team)
    away_team = aliased(Team)
    stmt = (
        select(
            Prediction,
            func.coalesce(Match.home_team_name, home_team.name, "Home team"),
            func.coalesce(Match.away_team_name, away_team.name, "Away team"),
        )
        .join(Match, Match.id == Prediction.match_id)
        .outerjoin(home_team, Match.home_team_id == home_team.id)
        .outerjoin(away_team, Match.away_team_id == away_team.id)
    )
    if match_id:
        stmt = stmt.where(Prediction.match_id == match_id)
    if league_id:
        stmt = stmt.where(Match.league_id == league_id)
    if team_id:
        stmt = stmt.where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
    if model_version:
        stmt = stmt.where(Prediction.model_version == model_version)
    if date_from:
        stmt = stmt.where(Prediction.generated_at >= date_from)
    if date_to:
        stmt = stmt.where(Prediction.generated_at <= date_to)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Prediction.generated_at.desc()).offset(offset).limit(ps)
    result = await db.execute(stmt)
    predictions = result.all()

    items = [
        PredictionHistoryItem(
            prediction_id=p.id,
            match_id=p.match_id,
            match_home_team=home_name,
            match_away_team=away_name,
            model_version=p.model_version,
            prediction_version=p.prediction_version,
            generated_at=p.generated_at,
            data_quality=p.feature_snapshot.get("data_quality", 0.0)
            if isinstance(p.feature_snapshot, dict)
            else 0.0,
            model_confidence=p.confidence or 0.0,
            home_probability=p.home_probability,
            draw_probability=p.draw_probability,
            away_probability=p.away_probability,
            ai_adjustment_applied=bool(p.ai_adjustment_json),
            context_hash=p.context_hash,
        )
        for p, home_name, away_name in predictions
    ]

    response = {
        "success": True,
        "data": [item.model_dump() for item in items],
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
        },
    }

    try:
        await set_cached(cache_key, response, ttl=get_settings().cache_ttl_predictions)
    except Exception:
        pass

    return response


@router.get(
    "/predictions/{prediction_id}",
    summary="Get a specific prediction by ID",
    response_model=dict[str, Any],
)
async def get_prediction_by_id(
    request: Request,
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve a specific prediction by its ID."""
    cache_key = cache_prediction_key(prediction_id)

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = (
        select(Prediction, PredictionScoreline)
        .join(PredictionScoreline, PredictionScoreline.prediction_id == Prediction.id)
        .where(Prediction.id == prediction_id)
        .order_by(PredictionScoreline.rank)
    )
    result = await db.execute(stmt)
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction {prediction_id} not found",
        )

    pred = rows[0][0]
    scorelines = [row[1] for row in rows]

    response = {
        "success": True,
        "data": {
            "prediction_id": pred.id,
            "match_id": pred.match_id,
            "model_version": pred.model_version,
            "prediction_version": pred.prediction_version,
            "generated_at": pred.generated_at.isoformat() if pred.generated_at else None,
            "provider_used": pred.provider_used,
            "lambda_home": pred.lambda_home,
            "lambda_away": pred.lambda_away,
            "home_probability": pred.home_probability,
            "draw_probability": pred.draw_probability,
            "away_probability": pred.away_probability,
            "over_2_5_probability": pred.over_2_5_probability,
            "under_2_5_probability": pred.under_2_5_probability,
            "btts_probability": pred.btts_probability,
            "confidence": pred.confidence,
            "prediction_status": pred.prediction_status,
            "feature_snapshot": pred.feature_snapshot
            if isinstance(pred.feature_snapshot, dict)
            else {},
            "news_snapshot": pred.news_snapshot if isinstance(pred.news_snapshot, dict) else {},
            "odds_snapshot": pred.odds_snapshot if isinstance(pred.odds_snapshot, dict) else {},
            "ai_explanation": pred.ai_explanation,
            "ai_evidence": pred.ai_evidence_json,
            "ai_adjustment": pred.ai_adjustment_json,
            "source_ids": pred.source_ids,
            "context_hash": pred.context_hash,
            "top_scorelines": [
                {
                    "rank": sl.rank,
                    "home_goals": sl.home_goals,
                    "away_goals": sl.away_goals,
                    "probability": sl.probability,
                }
                for sl in scorelines
            ],
        },
    }

    try:
        await set_cached(cache_key, response, ttl=get_settings().cache_ttl_predictions)
    except Exception:
        pass

    return response


@router.get(
    "/matches/{match_id}/predictions",
    summary="Get all historical predictions for a match",
    response_model=dict[str, Any],
)
async def get_match_predictions(
    request: Request,
    match_id: str,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Return all historical predictions for a match, showing evolution."""
    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps

    stmt = (
        select(Prediction, PredictionScoreline)
        .join(PredictionScoreline, PredictionScoreline.prediction_id == Prediction.id)
        .where(Prediction.match_id == match_id)
        .order_by(Prediction.generated_at.desc(), PredictionScoreline.rank)
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    predictions_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        pred, sl = row[0], row[1]
        if pred.id not in predictions_map:
            predictions_map[pred.id] = {
                "prediction_id": pred.id,
                "match_id": pred.match_id,
                "model_version": pred.model_version,
                "prediction_version": pred.prediction_version,
                "generated_at": pred.generated_at.isoformat() if pred.generated_at else None,
                "context_hash": pred.context_hash,
                "lambda_home": pred.lambda_home,
                "lambda_away": pred.lambda_away,
                "home_probability": pred.home_probability,
                "draw_probability": pred.draw_probability,
                "away_probability": pred.away_probability,
                "over_2_5_probability": pred.over_2_5_probability,
                "btts_probability": pred.btts_probability,
                "research_available": bool(pred.ai_evidence_json),
                "ai_adjustment_applied": bool(pred.ai_adjustment_json),
                "data_quality": pred.feature_snapshot.get("data_quality", 0.0)
                if isinstance(pred.feature_snapshot, dict)
                else 0.0,
                "top_scorelines": [],
            }
        predictions_map[pred.id]["top_scorelines"].append(
            {
                "rank": sl.rank,
                "home_goals": sl.home_goals,
                "away_goals": sl.away_goals,
                "probability": sl.probability,
            }
        )

    all_predictions = list(predictions_map.values())
    total = len(all_predictions)
    paginated = all_predictions[offset : offset + ps]

    return {
        "success": True,
        "data": paginated,
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
        },
    }


@router.get(
    "/matches/{match_id}/predictions/compare",
    summary="Compare latest vs previous prediction for a match",
    response_model=dict[str, Any],
)
async def compare_match_predictions(
    request: Request,
    match_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Compare the latest prediction against the previous one."""
    from services.prediction_comparison import PredictionComparisonService

    stmt = (
        select(Prediction, PredictionScoreline)
        .join(PredictionScoreline, PredictionScoreline.prediction_id == Prediction.id)
        .where(Prediction.match_id == match_id)
        .order_by(Prediction.generated_at.desc(), PredictionScoreline.rank)
    )
    result = await db.execute(stmt)
    rows = result.fetchall()

    if len(rows) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No predictions found for match {match_id}",
        )

    predictions_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        pred, _sl = row[0], row[1]
        if pred.id not in predictions_map:
            predictions_map[pred.id] = {
                "prediction_id": pred.id,
                "match_id": pred.match_id,
                "model_version": pred.model_version,
                "prediction_version": pred.prediction_version,
                "generated_at": pred.generated_at.isoformat() if pred.generated_at else None,
                "context_hash": pred.context_hash,
                "lambda_home": pred.lambda_home,
                "lambda_away": pred.lambda_away,
                "home_probability": pred.home_probability,
                "draw_probability": pred.draw_probability,
                "away_probability": pred.away_probability,
                "over_2_5_probability": pred.over_2_5_probability,
                "under_2_5_probability": pred.under_2_5_probability,
                "btts_probability": pred.btts_probability,
                "confidence": pred.confidence,
                "data_quality": pred.feature_snapshot.get("data_quality", 0.0)
                if isinstance(pred.feature_snapshot, dict)
                else 0.0,
                "research": {"available": bool(pred.ai_evidence_json)},
                "ai_adjustment": {"applied": bool(pred.ai_adjustment_json)},
            }

    all_preds = list(predictions_map.values())
    if len(all_preds) < 2:
        return {
            "success": True,
            "data": {
                "current": all_preds[0],
                "changes": {},
            },
        }

    comparer = PredictionComparisonService()
    comparison = comparer.compare(all_preds[1], all_preds[0])

    return {"success": True, "data": comparison}


@router.get(
    "/predictions/stats",
    summary="Get prediction statistics",
    response_model=dict[str, Any],
)
async def prediction_stats(
    request: Request,
    _admin: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return aggregate statistics about stored predictions."""
    total_stmt = select(func.count()).select_from(Prediction)
    total_result = await db.execute(total_stmt)
    total_predictions = total_result.scalar() or 0

    model_stmt = select(Prediction.model_version, func.count()).group_by(Prediction.model_version)
    model_result = await db.execute(model_stmt)
    predictions_by_model = {str(row[0]): row[1] for row in model_result if row[0]}

    quality_result = await db.execute(select(func.avg(Prediction.confidence)))
    avg_quality = quality_result.scalar()

    last_stmt = select(func.max(Prediction.generated_at))
    last_result = await db.execute(last_stmt)
    last_prediction_at = last_result.scalar()

    return {
        "success": True,
        "data": {
            "total_predictions": total_predictions,
            "predictions_by_model": predictions_by_model,
            "average_data_quality": float(avg_quality) if avg_quality else None,
            "last_prediction_at": last_prediction_at.isoformat() if last_prediction_at else None,
        },
    }
