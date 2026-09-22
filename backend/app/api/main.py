"""Application entry point and factory.

`create_app()` builds the FastAPI application used by both ``uvicorn`` and
tests.  It wires up:
  * middleware (CORS, request-id, timing/response-id logging, rate limiting, idempotency)
  * database startup/shutdown
  * Redis startup/shutdown
  * API routers
  * global exception handlers
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.endpoints.admin import router as admin_router
from api.v1.endpoints.leagues import router as leagues_router
from api.v1.endpoints.matches import router as matches_router
from api.v1.endpoints.predictions import router as predictions_router
from api.v1.endpoints.providers import router as providers_router
from api.v1.endpoints.research import router as research_router
from api.v1.endpoints.search import router as search_router
from api.v1.endpoints.teams import router as teams_router
from core.api_exceptions import (
    APIError,
    IdempotencyConflictError,
    InsufficientDataError,
    InvalidPredictionError,
    LeagueNotFoundError,
    MatchNotFoundError,
    PredictionConflictError,
    PredictionNotFoundError,
    RateLimitExceededError,
    ResearchUnavailableError,
    TeamNotFoundError,
)
from core.config import get_settings
from core.exceptions import FootballDataError
from core.logging import get_logger, set_request_id
from db.database import engine, get_db
from db.redis_client import redis_client


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ANN201
        await redis_client.connect()
        yield
        await redis_client.close()
        await engine.dispose()

    app = FastAPI(
        title="Football AI",
        description="AI-powered football match prediction platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
        debug=settings.debug,
    )

    # ── CORS ──────────────────────────────────────────────────────── #
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global Exception Handlers ───────────────────────────────────── #

    @app.exception_handler(APIError)
    async def _api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        get_logger(__name__).warning(
            "API error",
            extra={
                "error_code": exc.error_code,
                "message": exc.message,
                "path": str(request.url.path),
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                },
            },
        )

    @app.exception_handler(MatchNotFoundError)
    async def _match_not_found_handler(request: Request, exc: MatchNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(PredictionNotFoundError)
    async def _prediction_not_found_handler(
        request: Request, exc: PredictionNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(TeamNotFoundError)
    async def _team_not_found_handler(request: Request, exc: TeamNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(LeagueNotFoundError)
    async def _league_not_found_handler(request: Request, exc: LeagueNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(RateLimitExceededError)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceededError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(IdempotencyConflictError)
    async def _idempotency_conflict_handler(
        request: Request, exc: IdempotencyConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(ResearchUnavailableError)
    async def _research_unavailable_handler(
        request: Request, exc: ResearchUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(PredictionConflictError)
    async def _prediction_conflict_handler(
        request: Request, exc: PredictionConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(InvalidPredictionError)
    async def _invalid_prediction_handler(
        request: Request, exc: InvalidPredictionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(InsufficientDataError)
    async def _insufficient_data_handler(
        request: Request, exc: InsufficientDataError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(FootballDataError)
    async def _football_data_error_handler(
        request: Request, exc: FootballDataError
    ) -> JSONResponse:
        from core.exceptions import (
            ProviderAuthenticationError,
            ProviderNotFoundError,
            ProviderRateLimitError,
            ProviderUnavailableError,
            ProviderValidationError,
        )

        status_code = status.HTTP_502_BAD_GATEWAY
        if isinstance(exc, ProviderNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, ProviderAuthenticationError):
            status_code = status.HTTP_502_BAD_GATEWAY
        elif isinstance(exc, ProviderRateLimitError):
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
        elif isinstance(exc, ProviderUnavailableError):
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif isinstance(exc, ProviderValidationError):
            status_code = status.HTTP_502_BAD_GATEWAY
        get_logger(__name__).warning(
            "Provider error",
            extra={"error": exc.message, "path": str(request.url.path), "details": exc.details},
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.__class__.__name__,
                    "message": exc.message or exc.__class__.__name__,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                },
            },
        )

    # ── Request ID + timing middleware ──────────────────────────────── #
    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next: Any) -> Any:
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(rid)
        start = time.monotonic()
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            get_logger(__name__).error(
                "Unhandled exception",
                extra={"error": str(exc), "path": str(request.url.path)},
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"},
                },
                headers={"X-Request-ID": rid},
            )
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response

    # ── Routers ─────────────────────────────────────────────────────── #
    app.include_router(providers_router, prefix="/api/v1", tags=["providers"])
    app.include_router(matches_router, prefix="/api/v1", tags=["matches"])
    app.include_router(teams_router, prefix="/api/v1", tags=["teams"])
    app.include_router(leagues_router, prefix="/api/v1", tags=["leagues"])
    app.include_router(predictions_router, prefix="/api/v1", tags=["predictions"])
    app.include_router(research_router, prefix="/api/v1", tags=["research"])
    app.include_router(search_router, prefix="/api/v1", tags=["search"])
    app.include_router(admin_router, prefix="/api/v1", tags=["admin"])

    # Health endpoints
    from api.v1.endpoints.health import deep_health, health

    @app.get("/api/v1/health", tags=["health"])
    async def _health(
        db: AsyncSession = Depends(get_db),
    ) -> dict[str, Any]:
        return await health(db)

    @app.get("/api/v1/health/deep", tags=["health"])
    async def _health_deep(
        db: AsyncSession = Depends(get_db),
    ) -> dict[str, Any]:
        return await deep_health(db)

    @app.get("/health", tags=["health"], include_in_schema=False)
    async def _health_simple() -> dict[str, str]:
        return {"status": "ok"}

    # Root
    @app.get("/", tags=["root"])
    async def _root() -> dict[str, Any]:
        return {
            "success": True,
            "data": {"service": "Football AI", "version": "0.1.0", "docs": "/docs"},
        }

    return app


app = create_app()
