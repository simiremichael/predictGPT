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

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, not_, or_, select
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
from core.security import get_current_user, verify_admin_api_key
from db.database import DBSession, get_db
from jobs.job_manager import create_job, get_job
from models.match import (
    Match,
    Prediction,
    PredictionResult,
    PredictionRun,
    PredictionScoreline,
)
from schemas.api import PredictionHistoryItem
from services.prediction_data import PredictionDataService
from services.prediction_orchestrator import PredictionOrchestrator

router = APIRouter(tags=["predictions"])


async def _is_subscribed(user_email: str | None) -> bool:
    """Check if the user has an active subscription (or is a superuser)."""
    if not user_email:
        return False
    from models.user import User

    async with DBSession() as session:
        result = await session.execute(select(User).where(User.email == user_email))
        user = result.scalar_one_or_none()
        return bool(user and (user.has_active_subscription or user.is_superuser))


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
    user_email: str | None = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve the latest valid prediction for a match.

    Free users can see basic match info but full prediction probabilities
    and AI-adjusted scorelines require an active subscription.
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

    is_subscribed = await _is_subscribed(user_email)

    if is_subscribed:
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
                "subscription_required": False,
            },
        }
    else:
        pred_dict = prediction.model_dump()
        limited_data = {
            "prediction_id": pred_dict.get("prediction_id"),
            "match_id": pred_dict.get("match_id"),
            "model_version": pred_dict.get("model_version"),
            "prediction_version": pred_dict.get("prediction_version"),
            "generated_at": pred_dict.get("generated_at"),
            "provider_used": pred_dict.get("provider_used"),
            "data_quality": pred_dict.get("data_quality"),
            "confidence": pred_dict.get("confidence"),
            "prediction_status": pred_dict.get("prediction_status"),
            "lambda_home": pred_dict.get("lambda_home"),
            "lambda_away": pred_dict.get("lambda_away"),
            "home_probability": pred_dict.get("home_probability"),
            "draw_probability": pred_dict.get("draw_probability"),
            "away_probability": pred_dict.get("away_probability"),
            "over_2_5_probability": pred_dict.get("over_2_5_probability"),
            "under_2_5_probability": pred_dict.get("under_2_5_probability"),
            "btts_probability": pred_dict.get("btts_probability"),
        }
        response = {
            "success": True,
            "data": limited_data,
            "meta": {
                "context_hash": prediction.context_hash,
                "current_context_hash": current_context_hash,
                "context_changed": bool(
                    prediction.context_hash
                    and current_context_hash
                    and prediction.context_hash != current_context_hash
                ),
                "subscription_required": True,
                "message": "Full prediction details require an active subscription.",
            },
        }

    try:
        await set_cached(cache_key, response, ttl=get_settings().cache_ttl_predictions)
    except Exception:
        pass

    return response


class PredictionVerifyRequest(BaseModel):
    gg: bool | None = None
    win: bool | None = None
    over_2_5: bool | None = None


@router.put(
    "/predictions/{prediction_id}/verify",
    summary="Verify a prediction (admin)",
    response_model=dict[str, Any],
    dependencies=[Depends(verify_admin_api_key)],
)
async def verify_prediction(
    prediction_id: str,
    body: PredictionVerifyRequest = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Set admin verification flags for a prediction.

    - gg: whether the admin checked BTTS (both teams scored)
    - win: whether the admin confirmed the team with highest probability won
    - over_2_5: whether the admin confirmed over 2.5 goals
    """
    from models.match import Prediction

    stmt = select(Prediction).where(Prediction.id == prediction_id)
    result = await db.execute(stmt)
    prediction = result.scalar_one_or_none()
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction {prediction_id} not found",
        )

    if body.gg is not None:
        prediction.admin_verify_gg = body.gg
    if body.win is not None:
        prediction.admin_verify_win = body.win
    if body.over_2_5 is not None:
        prediction.admin_verify_over_2_5 = body.over_2_5

    await db.commit()
    await db.refresh(prediction)

    invalidate_cache_keys(
        cache_match_prediction_key(prediction.match_id),
        cache_predictions_list_key(),
    )

    return {
        "success": True,
        "data": {
            "prediction_id": prediction.id,
            "admin_verify_gg": prediction.admin_verify_gg,
            "admin_verify_win": prediction.admin_verify_win,
            "admin_verify_over_2_5": prediction.admin_verify_over_2_5,
        },
    }


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

    try:
        cancelled = await cancel_job(job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job store unavailable",
        ) from exc
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
    upcoming_only: bool = Query(
        False,
        description="Only show predictions for matches that haven't been played yet (status='scheduled' and kickoff_at >= now)",
    ),
    played: bool | None = Query(
        None,
        description="Filter by match played status. True for played, False for not played.",
    ),
    min_elapsed_minutes: int | None = Query(
        None,
        ge=0,
        le=10080,
        description="Only include matches whose kickoff was at least this many minutes ago.",
    ),
    max_elapsed_minutes: int | None = Query(
        None,
        ge=0,
        le=10080,
        description="Only include matches whose kickoff was no more than this many minutes ago.",
    ),
    kickoff_date: date | None = Query(
        None,
        description="Filter by match kickoff date (YYYY-MM-DD).",
    ),
    newest_first: bool = Query(
        False,
        description="Sort matches by kickoff time, newest first.",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_email: str | None = Depends(get_current_user),
) -> dict[str, Any]:
    """List prediction history with filters and pagination.

    Free (non-subscribed) users are limited to the first 2 predictions.
    """
    is_subscribed = await _is_subscribed(user_email)

    page_num = get_page(page)
    ps = get_page_size(page_size)
    offset = (page_num - 1) * ps
    now = datetime.now(UTC)

    cache_key = cache_predictions_list_key(
        match_id=match_id,
        league_id=league_id,
        team_id=team_id,
        model_version=model_version,
        date_from=date_from,
        date_to=date_to,
        upcoming_only=upcoming_only,
        played=played,
        min_elapsed_minutes=min_elapsed_minutes,
        max_elapsed_minutes=max_elapsed_minutes,
        kickoff_date=str(kickoff_date) if kickoff_date else None,
        newest_first=newest_first,
        elapsed_minute_bucket=(
            int(now.timestamp() // 60)
            if min_elapsed_minutes is not None or max_elapsed_minutes is not None
            else None
        ),
        is_subscribed=is_subscribed,
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
            Match.kickoff_at,
            Match.status,
            func.coalesce(PredictionResult.home_score, Match.home_score),
            func.coalesce(PredictionResult.away_score, Match.away_score),
        )
        .join(Match, Match.id == Prediction.match_id)
        .outerjoin(PredictionResult, PredictionResult.prediction_id == Prediction.id)
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
    if upcoming_only:
        stmt = stmt.where(Match.kickoff_at >= now).where(Match.is_finished.is_(False))
    completed_match = or_(
        Match.is_finished.is_(True),
        func.lower(Match.status) == "finished",
    )
    if played is True:
        # The results page classifies fixtures by elapsed time. Providers can
        # leave a finished match marked as live/scheduled, so once an elapsed
        # threshold is requested, use that threshold instead of trusting the
        # provider's completion flag.
        if min_elapsed_minutes is None:
            stmt = stmt.where(completed_match)
    elif played is False:
        stmt = stmt.where(not_(completed_match))
    if min_elapsed_minutes is not None:
        stmt = stmt.where(
            Match.kickoff_at <= now - timedelta(minutes=min_elapsed_minutes)
        )
    if max_elapsed_minutes is not None:
        stmt = stmt.where(
            Match.kickoff_at >= now - timedelta(minutes=max_elapsed_minutes)
        )
    if kickoff_date:
        start = datetime.combine(kickoff_date, datetime.min.time())
        end = start + timedelta(days=1)
        stmt = stmt.where(Match.kickoff_at >= start).where(Match.kickoff_at < end)

    # Free (non-subscribed) users see at most 2 predictions
    free_limit = 2 if not is_subscribed else None

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0
    if free_limit is not None:
        total = min(total, free_limit)

    kickoff_order = (
        Match.kickoff_at.desc().nullslast()
        if newest_first
        else Match.kickoff_at.asc().nullslast()
    )
    stmt = stmt.order_by(kickoff_order, Prediction.generated_at.desc()).offset(offset).limit(ps)
    if free_limit is not None:
        stmt = stmt.limit(free_limit)
    result = await db.execute(stmt)
    predictions = result.all()

    items = [
        PredictionHistoryItem(
            prediction_id=p.id,
            match_id=p.match_id,
            match_home_team=home_name,
            match_away_team=away_name,
            match_kickoff=match_kickoff,
            match_status=match_status,
            home_score=home_score,
            away_score=away_score,
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
            over_2_5_probability=p.over_2_5_probability,
            under_2_5_probability=p.under_2_5_probability,
            btts_probability=p.btts_probability,
            ai_adjustment_applied=bool(p.ai_adjustment_json),
            context_hash=p.context_hash,
            admin_verify_gg=p.admin_verify_gg,
            admin_verify_win=p.admin_verify_win,
            admin_verify_over_2_5=p.admin_verify_over_2_5,
        )
        for (
            p,
            home_name,
            away_name,
            match_kickoff,
            match_status,
            home_score,
            away_score,
        ) in predictions
    ]

    response = {
        "success": True,
        "data": [item.model_dump() for item in items],
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
            "upcoming_only": upcoming_only,
            "is_subscribed": is_subscribed,
            "free_predictions_remaining": max(0, 2 - len(items)) if not is_subscribed else None,
        },
    }

    try:
        # Prediction lists change during batch generation. Keep their cache
        # brief so active pages pick up newly saved records promptly, even if
        # an invalidation event is missed.
        await set_cached(
            cache_key,
            response,
            ttl=min(get_settings().cache_ttl_predictions, 5),
        )
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
    user_email: str | None = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve a specific prediction by its ID.

    Free users can see basic prediction metadata but full details
    (scorelines, AI evidence, adjustments) require an active subscription.
    """
    cache_key = cache_prediction_key(prediction_id)

    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    stmt = (
        select(Prediction, PredictionScoreline, Match.kickoff_at)
        .join(Match, Match.id == Prediction.match_id)
        .outerjoin(PredictionScoreline, PredictionScoreline.prediction_id == Prediction.id)
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
    match_kickoff = rows[0][2]
    scorelines = [row[1] for row in rows]

    is_subscribed = await _is_subscribed(user_email)

    if is_subscribed:
        response = {
            "success": True,
            "data": {
                "prediction_id": pred.id,
                "match_id": pred.match_id,
                "match_kickoff": match_kickoff.isoformat() if match_kickoff else None,
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
                "admin_verify_gg": pred.admin_verify_gg,
                "admin_verify_win": pred.admin_verify_win,
                "admin_verify_over_2_5": pred.admin_verify_over_2_5,
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
            "meta": {"subscription_required": False},
        }
    else:
        response = {
            "success": True,
            "data": {
                "prediction_id": pred.id,
                "match_id": pred.match_id,
                "match_kickoff": match_kickoff.isoformat() if match_kickoff else None,
                "model_version": pred.model_version,
                "prediction_version": pred.prediction_version,
                "generated_at": pred.generated_at.isoformat() if pred.generated_at else None,
                "provider_used": pred.provider_used,
                "home_probability": pred.home_probability,
                "draw_probability": pred.draw_probability,
                "away_probability": pred.away_probability,
                "confidence": pred.confidence,
                "prediction_status": pred.prediction_status,
                "data_quality": pred.feature_snapshot.get("data_quality", 0.0)
                if isinstance(pred.feature_snapshot, dict)
                else 0.0,
            },
            "meta": {
                "subscription_required": True,
                "message": "Full prediction details including scorelines and AI evidence require an active subscription.",
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
    user_email: str | None = Depends(get_current_user),
) -> dict[str, Any]:
    """Return all historical predictions for a match, showing evolution.

    Free users see limited prediction metadata; full scorelines and AI details
    require an active subscription.
    """
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

    is_subscribed = await _is_subscribed(user_email)

    if not is_subscribed:
        for pred in paginated:
            pred.pop("lambda_home", None)
            pred.pop("lambda_away", None)
            pred.pop("over_2_5_probability", None)
            pred.pop("btts_probability", None)
            pred.pop("research_available", None)
            pred.pop("ai_adjustment_applied", None)
            pred.pop("top_scorelines", None)

    return {
        "success": True,
        "data": paginated,
        "meta": {
            "page": page_num,
            "page_size": ps,
            "total": total,
            "total_pages": max(1, -(-total // ps)) if ps > 0 else 1,
            "subscription_required": not is_subscribed,
            "message": "Full prediction details require an active subscription."
            if not is_subscribed
            else None,
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
    user_email: str | None = Depends(get_current_user),
) -> dict[str, Any]:
    """Compare the latest prediction against the previous one.

    Full comparison including lambdas and detailed metrics requires an
    active subscription. Free users see basic metadata only.
    """
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
        is_subscribed = await _is_subscribed(user_email)
        if not is_subscribed:
            for pred in all_preds:
                pred.pop("lambda_home", None)
                pred.pop("lambda_away", None)
                pred.pop("over_2_5_probability", None)
                pred.pop("under_2_5_probability", None)
                pred.pop("btts_probability", None)
        return {
            "success": True,
            "data": {
                "current": all_preds[0],
                "changes": {},
            },
            "meta": {
                "subscription_required": not is_subscribed,
                "message": "Full prediction comparison requires an active subscription."
                if not is_subscribed
                else None,
            },
        }

    is_subscribed = await _is_subscribed(user_email)
    if not is_subscribed:
        for pred in all_preds:
            pred.pop("lambda_home", None)
            pred.pop("lambda_away", None)
            pred.pop("over_2_5_probability", None)
            pred.pop("under_2_5_probability", None)
            pred.pop("btts_probability", None)

    comparer = PredictionComparisonService()
    comparison = comparer.compare(all_preds[1], all_preds[0])

    return {"success": True, "data": comparison, "meta": {
        "subscription_required": not is_subscribed,
        "message": "Full prediction comparison requires an active subscription."
        if not is_subscribed
        else None,
    }}


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
