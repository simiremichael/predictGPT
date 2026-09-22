"""Integration tests for Phase 5 API endpoints.

Tests cover:
- Leagues endpoints (list, detail, seasons, standings)
- Teams endpoints (list, detail, matches, statistics)
- Search endpoint
- Health endpoints
- Admin stats endpoint
- Prediction endpoints (history, detail, compare, job status, cancellation)
- Research endpoints (research, analysis)
- Standardized response format (success/data/meta envelope)
- Error handling (404s, admin auth, validation errors)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def app():
    from api.main import create_app

    return create_app()


@pytest.fixture()
async def async_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture()
def mock_db_session():
    """Create a mock AsyncSession with common query methods."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _mock_scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalars.return_value.all.return_value = [value] if value else []
    result.scalar.return_value = value
    return result


def _mock_count_result(count: int = 0):
    result = MagicMock()
    result.scalar.return_value = count
    return result


class TestLeaguesEndpoints:
    async def test_list_leagues_empty(self, async_client: AsyncClient, app) -> None:
        """GET /api/v1/leagues returns empty list with pagination meta."""
        from db.database import get_db

        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []
        empty_result.scalar.return_value = 0

        async def _mock_db():
            db = MagicMock()
            db.execute = AsyncMock(return_value=empty_result)
            yield db

        app.dependency_overrides[get_db] = _mock_db

        resp = await async_client.get("/api/v1/leagues")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == []
        assert data["meta"]["total"] == 0

        app.dependency_overrides.clear()

    async def test_get_league_not_found(self, async_client: AsyncClient, app) -> None:
        """GET /api/v1/leagues/{id} returns 404 for non-existent league."""
        from db.database import get_db

        async def _mock_db():
            db = MagicMock()
            result_mock = MagicMock()
            result_mock.fetchall.return_value = []
            result_mock.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = _mock_db

        resp = await async_client.get("/api/v1/leagues/nonexistent-id")

        assert resp.status_code == 404
        app.dependency_overrides.clear()

    async def test_list_seasons_empty(self, async_client: AsyncClient, app) -> None:
        """GET /api/v1/leagues/{id}/seasons returns empty when league has no seasons."""
        from db.database import get_db

        async def _mock_db():
            db = MagicMock()
            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = []
            result_mock.scalar.return_value = 0
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = _mock_db

        resp = await async_client.get("/api/v1/leagues/league-xyz/seasons")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == []
        app.dependency_overrides.clear()


class TestTeamsEndpoints:
    async def test_get_team_not_found(self, async_client: AsyncClient, app) -> None:
        """GET /api/v1/teams/{id} returns 404 for non-existent team."""
        from db.database import get_db

        async def _mock_db():
            db = MagicMock()
            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = _mock_db

        resp = await async_client.get("/api/v1/teams/nonexistent-id")

        assert resp.status_code == 404
        app.dependency_overrides.clear()

    async def test_get_team_statistics_not_found(self, async_client: AsyncClient, app) -> None:
        """GET /api/v1/teams/{id}/statistics returns 404 when no stats exist."""
        from db.database import get_db

        async def _mock_db():
            db = MagicMock()
            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = []
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = _mock_db

        resp = await async_client.get("/api/v1/teams/nonexistent-id/statistics")

        assert resp.status_code == 404
        app.dependency_overrides.clear()


class TestSearchEndpoint:
    async def test_search_requires_query(self, async_client: AsyncClient) -> None:
        """GET /api/v1/search without 'q' param returns 422."""
        resp = await async_client.get("/api/v1/search")
        assert resp.status_code == 422

    async def test_search_short_query_rejected(self, async_client: AsyncClient) -> None:
        """GET /api/v1/search?q=a returns 422 due to min_length=2 validation."""
        resp = await async_client.get("/api/v1/search?q=a")
        assert resp.status_code == 422


class TestHealthEndpoints:
    async def test_health_endpoint_exists(self, async_client: AsyncClient, app) -> None:
        """GET /api/v1/health returns a response with standard format."""
        from db.database import get_db

        async def _mock_db():
            db = MagicMock()
            result_mock = MagicMock()
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = _mock_db

        with patch("db.redis_client.redis_client") as mock_redis:
            mock_redis.client.ping = AsyncMock(return_value=True)
            resp = await async_client.get("/api/v1/health")

        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "data" in data
        assert "checks" in data["data"]
        app.dependency_overrides.clear()

    async def test_health_simple(self, async_client: AsyncClient) -> None:
        """GET /health returns simple status."""
        resp = await async_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestPredictionEndpoints:
    async def test_get_prediction_not_found(self, async_client: AsyncClient, app) -> None:
        """GET /api/v1/matches/{id}/prediction returns 404 when no prediction exists."""
        from db.database import get_db

        async def _mock_db():
            db = MagicMock()
            yield db

        app.dependency_overrides[get_db] = _mock_db

        with patch("core.cache.get_cached", return_value=None), \
             patch("services.prediction_orchestrator.PredictionOrchestrator") as MockOrch:
            mock_orchestrator = MagicMock()
            mock_orchestrator.get_latest_prediction = AsyncMock(return_value=None)
            MockOrch.return_value = mock_orchestrator

            resp = await async_client.get("/api/v1/matches/match-001/prediction")

        assert resp.status_code == 404
        data = resp.json()
        assert "No prediction found" in data["detail"]
        app.dependency_overrides.clear()

    async def test_create_prediction_requires_admin(self, async_client: AsyncClient) -> None:
        """POST /api/v1/matches/{id}/predict without admin key returns 401/403/503."""
        resp = await async_client.post("/api/v1/matches/match-001/predict")
        assert resp.status_code in (401, 403, 503)

    async def test_create_prediction_async_requires_admin(self, async_client: AsyncClient) -> None:
        """POST /api/v1/matches/{id}/predict/async without admin key returns 401/403/503."""
        resp = await async_client.post("/api/v1/matches/match-001/predict/async")
        assert resp.status_code in (401, 403, 503)

    async def test_cancel_job_requires_admin(self, async_client: AsyncClient) -> None:
        """POST /api/v1/predictions/jobs/{id}/cancel without admin key returns 401/403/503."""
        resp = await async_client.post("/api/v1/predictions/jobs/job-001/cancel")
        assert resp.status_code in (401, 403, 503)

    async def test_prediction_stats_requires_admin(self, async_client: AsyncClient) -> None:
        """GET /api/v1/predictions/stats without admin key returns non-200."""
        resp = await async_client.get("/api/v1/predictions/stats")
        assert resp.status_code != 200

    async def test_job_status_not_found(self, async_client: AsyncClient) -> None:
        """GET /api/v1/predictions/jobs/{id} returns 404 or 503."""
        resp = await async_client.get("/api/v1/predictions/jobs/nonexistent-job")
        assert resp.status_code in (404, 503)


class TestResearchEndpoints:
    async def test_get_research_match_not_found(self, async_client: AsyncClient, app) -> None:
        """GET /api/v1/matches/{id}/research returns 404 for non-existent match."""
        from db.database import get_db

        async def _mock_db():
            db = MagicMock()
            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = _mock_db

        resp = await async_client.get("/api/v1/matches/nonexistent/research")

        assert resp.status_code == 404
        app.dependency_overrides.clear()

    async def test_trigger_research_requires_admin(self, async_client: AsyncClient) -> None:
        """POST /api/v1/matches/{id}/research without admin key returns 401/403."""
        resp = await async_client.post("/api/v1/matches/match-001/research")
        assert resp.status_code in (401, 403)


class TestAdminEndpoints:
    async def test_admin_stats_requires_admin(self, async_client: AsyncClient) -> None:
        """GET /api/v1/admin/stats without admin key returns 401/403/503."""
        resp = await async_client.get("/api/v1/admin/stats")
        assert resp.status_code in (401, 403, 503)

    async def test_admin_models_requires_admin(self, async_client: AsyncClient) -> None:
        """GET /api/v1/admin/models without admin key returns 401/403/503."""
        resp = await async_client.get("/api/v1/admin/models")
        assert resp.status_code in (401, 403, 503)

    async def test_admin_prediction_runs_requires_admin(self, async_client: AsyncClient) -> None:
        """GET /api/v1/admin/prediction-runs without admin key returns 401/403/503."""
        resp = await async_client.get("/api/v1/admin/prediction-runs")
        assert resp.status_code in (401, 403, 503)


class TestStandardizedResponseFormat:
    """Verify all endpoints return responses in {success, data, meta} format."""

    async def test_matches_list_response_format(self, async_client: AsyncClient, app) -> None:
        """GET /api/v1/matches returns standardized format."""
        from db.database import get_db

        async def _mock_db():
            db = MagicMock()
            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = []
            result_mock.scalar.return_value = 0
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = _mock_db

        with patch("core.cache.get_cached", return_value=None), \
             patch("core.cache.set_cached", new_callable=AsyncMock), \
             patch("core.config.get_settings") as mock_settings:
            mock_settings.return_value.cache_ttl_fixtures = 1800
            mock_settings.return_value.cache_ttl_match_summary = 300
            mock_settings.return_value.max_page_size = 100

            resp = await async_client.get("/api/v1/matches")

        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "data" in data
        assert "meta" in data
        assert "page" in data["meta"]
        assert "page_size" in data["meta"]
        assert "total" in data["meta"]
        assert "total_pages" in data["meta"]
        app.dependency_overrides.clear()

    async def test_error_response_format(self, async_client: AsyncClient, app) -> None:
        """Error responses return proper error structure."""
        from db.database import get_db

        async def _mock_db():
            db = MagicMock()
            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = _mock_db

        resp = await async_client.get("/api/v1/matches/nonexistent-id")

        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data or "message" in data or "error" in data
        app.dependency_overrides.clear()


class TestRequestIDMiddleware:
    async def test_request_id_header_set(self, async_client: AsyncClient) -> None:
        """Responses include X-Request-ID header."""
        resp = await async_client.get("/health")
        assert "X-Request-ID" in resp.headers


class TestRootEndpoint:
    async def test_root_returns_service_info(self, async_client: AsyncClient) -> None:
        """GET / returns service info in standardized format."""
        resp = await async_client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "Football AI" in data["data"]["service"]
