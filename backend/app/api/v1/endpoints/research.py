"""Research API endpoints.

GET  /api/v1/matches/{match_id}/research     -- retrieve latest research
POST /api/v1/matches/{match_id}/research     -- trigger fresh research (admin)
GET  /api/v1/matches/{match_id}/analysis     -- get prediction with AI analysis
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web_research.service import MatchResearchService

from core.cache import (
    cache_match_key,
    cache_match_prediction_key,
    cache_match_research_key,
    cache_match_summary_key,
    get_cached,
    invalidate_cache_keys,
    set_cached,
)
from core.security import verify_admin_api_key
from db.database import get_db
from models.match import Match
from models.research import ResearchEvidence, ResearchRun
from services.ai_prediction_service import AIPredictionService

router = APIRouter(tags=["research"])

_research_service: MatchResearchService | None = None


def get_research_service() -> MatchResearchService:
    """Get or create the MatchResearchService singleton."""
    global _research_service
    if _research_service is None:
        _research_service = MatchResearchService()
    return _research_service


class ResearchSourceSchema(BaseModel):
    url: str
    title: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    source_type: str | None = None
    credibility_score: float = 0.0
    freshness_score: float = 0.0


class EvidenceSchema(BaseModel):
    subject: str
    claim: str | None = None
    evidence_status: str
    confidence: float
    source_ids: list[str]


class ConflictSchema(BaseModel):
    subject: str
    claim_a: str
    claim_b: str
    source_a_id: str
    source_b_id: str
    detected_at: datetime


class ResearchResponse(BaseModel):
    match_id: str
    researched_at: datetime | None = None
    sources: list[ResearchSourceSchema] = Field(default_factory=list)
    injuries: list[EvidenceSchema] = Field(default_factory=list)
    suspensions: list[EvidenceSchema] = Field(default_factory=list)
    lineups: list[dict[str, Any]] = Field(default_factory=list)
    team_news: list[EvidenceSchema] = Field(default_factory=list)
    conflicts: list[ConflictSchema] = Field(default_factory=list)
    data_quality: float = 0.0


@router.get(
    "/matches/{match_id}/research",
    response_model=dict[str, Any],
    summary="Get latest web research for a match",
)
async def get_research(
    request: Request,
    match_id: str,
    force_refresh: bool = Query(False, description="Force a fresh research run"),
    db: AsyncSession = Depends(get_db),
    service: MatchResearchService = Depends(get_research_service),
) -> dict[str, Any]:
    """Retrieve the latest web research for a match.

    Returns sources, injuries, suspensions, lineups, and team news
    extracted from web research.
    """
    cache_key = cache_match_research_key(match_id)

    try:
        cached = await get_cached(cache_key)
        if cached and not force_refresh:
            return cached
    except Exception:
        pass

    match_stmt = select(Match).where(Match.id == match_id)
    match_result = await db.execute(match_stmt)
    match = match_result.scalar_one_or_none()

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found",
        )

    try:
        result = await service.research_match(
            match_id=match_id,
            home_team=match.home_team_name or "Unknown",
            away_team=match.away_team_name or "Unknown",
            competition=match.league_id,
            kickoff_at=match.kickoff_at,
            force_refresh=force_refresh,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Research failed: {str(exc)}",
        ) from exc

    response = _research_to_response(match_id, result)

    try:
        await set_cached(cache_key, response, ttl=600)
    except Exception:
        pass

    return response


@router.post(
    "/matches/{match_id}/research",
    response_model=dict[str, Any],
    summary="Trigger fresh web research for a match",
    dependencies=[Depends(verify_admin_api_key)],
)
async def trigger_research(
    request: Request,
    match_id: str,
    db: AsyncSession = Depends(get_db),
    service: MatchResearchService = Depends(get_research_service),
) -> dict[str, Any]:
    """Trigger a fresh research run for a match.

    Requires admin authentication.
    """
    match_stmt = select(Match).where(Match.id == match_id)
    match_result = await db.execute(match_stmt)
    match = match_result.scalar_one_or_none()

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found",
        )

    try:
        result = await service.research_match(
            match_id=match_id,
            home_team=match.home_team_name or "Unknown",
            away_team=match.away_team_name or "Unknown",
            competition=match.league_id,
            kickoff_at=match.kickoff_at,
            force_refresh=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Research failed: {str(exc)}",
        ) from exc

    response = _research_to_response(match_id, result)

    try:
        await invalidate_cache_keys(
            cache_match_research_key(match_id),
            cache_match_key(match_id),
            cache_match_prediction_key(match_id),
            cache_match_summary_key(match_id),
        )
        await set_cached(cache_match_research_key(match_id), response, ttl=600)
    except Exception:
        pass

    return response


@router.get(
    "/matches/{match_id}/analysis",
    response_model=dict[str, Any],
    summary="Get prediction with AI research analysis",
)
async def get_analysis(
    request: Request,
    match_id: str,
    db: AsyncSession = Depends(get_db),
    orchestrator: Any = Depends(lambda: __import__("services.prediction_orchestrator", fromlist=["PredictionOrchestrator"]).PredictionOrchestrator()),
) -> dict[str, Any]:
    """Get a full prediction including AI research analysis and explanation.

    This endpoint combines:
    - Statistical model (Phase 3 Poisson)
    - Web research (Phase 4)
    - AI evidence adjustment (Phase 4)
    - AI explanation generation (Phase 4)
    """
    # Try to get existing prediction first
    try:
        prediction = await orchestrator.get_latest_prediction(match_id, db)
    except Exception:
        prediction = None

    if prediction is None:
        # Generate a new prediction (includes research if available)
        try:
            prediction = await orchestrator.generate_prediction(
                match_id=match_id,
                db_session=db,
                force_refresh=False,
                include_research=True,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not generate prediction for match {match_id}: {str(exc)}",
            ) from exc

    return {
        "success": True,
        "data": prediction.model_dump() if hasattr(prediction, "model_dump") else prediction,
    }


class AIPredictionRequest(BaseModel):
    include_research: bool = Field(default=True, description="Perform DuckDuckGo research before generating the prediction")
    force_refresh: bool = Field(default=False, description="Force a fresh research run even if cached")


class AIBatchPredictionRequest(BaseModel):
    league_id: str | None = Field(default=None, description="Limit to a specific league")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of fixtures to predict")
    include_research: bool = Field(default=True, description="Perform DuckDuckGo research for each match")


@router.post(
    "/matches/{match_id}/predictions/ai",
    response_model=dict[str, Any],
    summary="Generate an AI research-backed prediction for a match",
    dependencies=[Depends(verify_admin_api_key)],
)
async def generate_ai_prediction(
    request: Request,
    match_id: str,
    body: AIPredictionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Generate a prediction using DuckDuckGo research + AI analysis.

    Fetches the match from the database, searches DuckDuckGo for team news,
    injuries, suspensions, and lineups, then uses the AI provider to produce
    a research-adjusted prediction with an explanation. The prediction and
    research run are saved to the database.

    Requires admin authentication.
    """
    match_stmt = select(Match).where(Match.id == match_id)
    match_result = await db.execute(match_stmt)
    match = match_result.scalar_one_or_none()

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found",
        )

    service = AIPredictionService(db_session=db)

    try:
        result = await service.generate_prediction(
            match_id=match_id,
            include_research=body.include_research,
            force_refresh=body.force_refresh,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI prediction generation failed: {str(exc)}",
        ) from exc

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("error", "Prediction generation failed"),
        )

    return result


@router.post(
    "/predictions/ai/batch",
    response_model=dict[str, Any],
    summary="Generate AI predictions for upcoming fixtures",
    dependencies=[Depends(verify_admin_api_key)],
)
async def generate_ai_predictions_batch(
    request: Request,
    body: AIBatchPredictionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fetch fixtures from the DB and generate AI predictions for each.

    Retrieves upcoming scheduled matches from the database, runs DuckDuckGo
    research + AI prediction for each, and saves results to the database.

    Requires admin authentication.
    """
    service = AIPredictionService(db_session=db)

    try:
        result = await service.generate_predictions_for_league(
            league_id=body.league_id,
            limit=body.limit,
            include_research=body.include_research,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Batch AI prediction generation failed: {str(exc)}",
        ) from exc

    return result


def _research_to_response(
    match_id: str, result: Any
) -> dict[str, Any]:
    """Convert a MatchResearchResult to the standardized API response format."""
    from pydantic import Field

    sources: list[dict[str, Any]] = []
    for s in result.sources:
        sources.append({
            "url": s.url,
            "title": s.title,
            "publisher": s.publisher,
            "published_at": s.published_at.isoformat() if s.published_at else None,
            "source_type": s.source_type.value if hasattr(s.source_type, "value") else str(s.source_type),
            "credibility_score": s.credibility_score,
            "freshness_score": s.freshness_score,
        })

    def _to_evidence(e: Any) -> dict[str, Any]:
        return {
            "subject": getattr(e, "subject", getattr(e, "player", "unknown")),
            "claim": getattr(e, "claim", None),
            "evidence_status": str(e.evidence_status) if hasattr(e, "evidence_status") else "unknown",
            "confidence": getattr(e, "confidence", 0.0),
            "source_ids": getattr(e, "source_ids", []),
        }

    research_data = {
        "match_id": match_id,
        "researched_at": result.researched_at.isoformat() if hasattr(result, "researched_at") and result.researched_at else None,
        "sources": sources,
        "injuries": [_to_evidence(i) for i in result.injuries],
        "suspensions": [_to_evidence(s) for s in result.suspensions],
        "lineups": [ln.model_dump() for ln in result.lineups] if hasattr(result, "lineups") else [],
        "team_news": [_to_evidence(t) for t in result.team_news],
        "conflicts": [
            {
                "subject": c.subject,
                "claim_a": c.claim_a,
                "claim_b": c.claim_b,
                "source_a_id": c.source_a_id,
                "source_b_id": c.source_b_id,
                "detected_at": c.detected_at.isoformat() if hasattr(c, "detected_at") and c.detected_at else None,
            }
            for c in result.conflicts
        ] if hasattr(result, "conflicts") else [],
        "data_quality": result.data_quality if hasattr(result, "data_quality") else 0.0,
    }

    return {
        "success": True,
        "data": research_data,
        "meta": {
            "match_id": match_id,
            "source_count": len(sources),
            "injuries_count": len(research_data["injuries"]),
            "suspensions_count": len(research_data["suspensions"]),
            "team_news_count": len(research_data["team_news"]),
            "conflicts_count": len(research_data["conflicts"]),
        },
    }
