"""Integration tests for provider status endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestProviderStatusEndpoint:
    async def test_status_returns_active_provider(self) -> None:
        from httpx import ASGITransport, AsyncClient

        from api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/providers/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_provider" in data
        assert "providers" in data
        assert data["active_provider"] == "api_football"

    async def test_status_marks_unconfigured_providers(self) -> None:
        from httpx import ASGITransport, AsyncClient

        from api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/providers/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["providers"]["api_football"]["configured"] is False

    async def test_compare_endpoint_removed(self) -> None:
        """Verify the old provider comparison endpoint is no longer registered."""
        from httpx import ASGITransport, AsyncClient

        from api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/admin/providers/compare",
                params={"league_internal_id": "premier_league"},
                headers={"X-Admin-Api-Key": "test_admin_key"},
            )
        assert resp.status_code == 404

    async def test_sync_database_endpoint_requires_admin_key(self) -> None:
        """Verify the DB sync route is registered and protected by admin auth."""
        from httpx import ASGITransport, AsyncClient

        from api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/v1/providers/sync/database")
        assert resp.status_code == 403

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/providers/sync/database",
                headers={"X-Admin-Api-Key": "test_admin_key"},
            )
        assert resp.status_code in {200, 500}

    async def test_provider_league_by_id_endpoint_accepts_provider_id(self) -> None:
        from httpx import ASGITransport, AsyncClient

        from api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/providers/leagues/39")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["success"] is True
        assert payload["data"] is not None

    async def test_provider_leagues_return_db_rows_when_provider_matches_db(self) -> None:
        from api.v1.endpoints import providers as provider_routes
        from db.database import AsyncSessionLocal
        from models.league import League

        async with AsyncSessionLocal() as db:
            db.add(
                League(
                    id="db-league-1",
                    name="Premier League",
                    country="England",
                    country_code="GB",
                    is_active=True,
                )
            )
            await db.commit()

        provider = AsyncMock()
        provider.connect = AsyncMock()
        provider.close = AsyncMock()
        provider.get_leagues = AsyncMock(
            return_value=[
                type(
                    "LeaguePayload",
                    (),
                    {
                        "provider_league_id": "db-league-1",
                        "name": "Premier League",
                        "country": "England",
                        "country_code": "GB",
                    },
                )()
            ]
        )

        with patch.object(provider_routes, "get_football_provider", return_value=provider):
            with patch.object(provider_routes, "run_daily_sync", new=AsyncMock()) as sync_mock:
                payload = await provider_routes._provider_data_response("get_leagues")

        assert payload["success"] is True
        assert payload["data"][0]["name"] == "Premier League"
        sync_mock.assert_not_called()

    async def test_provider_leagues_runs_sync_when_db_is_empty(self) -> None:
        from api.v1.endpoints import providers as provider_routes

        provider = AsyncMock()
        provider.connect = AsyncMock()
        provider.close = AsyncMock()
        provider.get_leagues = AsyncMock(
            return_value=[
                type(
                    "LeaguePayload",
                    (),
                    {
                        "provider_league_id": "new-league",
                        "name": "La Liga",
                        "country": "Spain",
                        "country_code": "ES",
                    },
                )()
            ]
        )

        with patch.object(provider_routes, "get_football_provider", return_value=provider):
            with patch.object(provider_routes, "run_daily_sync", new=AsyncMock()) as sync_mock:
                with patch.object(
                    provider_routes,
                    "_read_leagues_from_db",
                    new=AsyncMock(
                        side_effect=[
                            [],
                            [
                                {
                                    "id": "new-league",
                                    "name": "La Liga",
                                    "country": "Spain",
                                    "country_code": "ES",
                                }
                            ],
                        ]
                    ),
                ):
                    payload = await provider_routes._provider_data_response("get_leagues")

        assert payload["success"] is True
        assert payload["data"][0]["name"] == "La Liga"
        sync_mock.assert_called_once()

    async def test_sync_and_reconcile_invalidates_daily_sync_redis_on_mismatch(self) -> None:
        from api.v1.endpoints import providers as provider_routes

        provider = AsyncMock()
        provider.connect = AsyncMock()
        provider.close = AsyncMock()
        provider.get_leagues = AsyncMock(
            return_value=[
                type(
                    "LeaguePayload",
                    (),
                    {
                        "provider_league_id": "league-1",
                        "name": "La Liga",
                        "country": "Spain",
                        "country_code": "ES",
                    },
                )()
            ]
        )

        redis = AsyncMock()
        redis.client = AsyncMock()
        redis.client.get = AsyncMock(return_value="2024-01-01")
        redis.client.set = AsyncMock()
        redis.client.delete = AsyncMock()

        with patch.object(provider_routes, "get_redis", new=AsyncMock(return_value=redis)):
            with patch.object(provider_routes, "get_football_provider", return_value=provider):
                with patch.object(
                    provider_routes,
                    "_read_db_resource_payload",
                    new=AsyncMock(
                        side_effect=[
                            [
                                {
                                    "id": "league-1",
                                    "name": "Premier League",
                                    "country": "England",
                                    "country_code": "GB",
                                    "is_active": True,
                                }
                            ],
                            [
                                {
                                    "id": "league-1",
                                    "name": "La Liga",
                                    "country": "Spain",
                                    "country_code": "ES",
                                    "is_active": True,
                                }
                            ],
                        ]
                    ),
                ):
                    with patch.object(
                        provider_routes, "run_daily_sync", new=AsyncMock()
                    ) as sync_mock:
                        payload = await provider_routes._sync_and_reconcile_resource("get_leagues")

        assert payload[0]["name"] == "La Liga"
        sync_mock.assert_called_once()
        redis.client.delete.assert_any_await()
        deleted_keys = [call.args[0] for call in redis.client.delete.await_args_list]
        assert any("provider:daily-sync:" in key for key in deleted_keys)
