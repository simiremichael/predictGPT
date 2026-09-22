import asyncio
import json
from unittest.mock import AsyncMock, patch

from services.frontend_cache import FrontendCacheService


class FakeRedis:
    def __init__(self):
        self.store = {
            "db:version": "2",
        }

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)

    async def get_json(self, key):
        raw = self.store.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key, value, ttl=None):
        self.store[key] = json.dumps(value)


def test_frontend_cache_revalidates_on_db_version_change() -> None:
    async def run_test() -> None:
        service = FrontendCacheService()
        service._db_version = 1

        cache_key = service._cache_key("leagues:list", "active", "all", 1, 10)
        fake_redis = FakeRedis()
        fake_redis.store[cache_key] = json.dumps(
            {"data": {"stale": True}, "_db_version": 1, "_cached_at": 1}
        )
        fake_redis.store["db:version"] = "2"

        async def fake_get_redis():
            return fake_redis

        service._get_redis = fake_get_redis

        async def fetcher():
            return {"fresh": True}

        result = await service.get(
            "leagues:list",
            "active",
            "all",
            1,
            10,
            fetcher=fetcher,
            ttl=300,
            stale_ttl=3600,
        )

        assert result == {"fresh": True}
        assert service._db_version == 2

    asyncio.run(run_test())


def test_frontend_cache_ignores_stale_payload_when_db_version_mismatch() -> None:
    async def run_test() -> None:
        service = FrontendCacheService()
        service._db_version = 2

        cache_key = service._cache_key("leagues:list", "active", "all", 1, 10)
        fake_redis = FakeRedis()
        fake_redis.store[cache_key] = json.dumps(
            {"data": {"stale": True}, "_db_version": 1, "_cached_at": 1}
        )
        fake_redis.store["db:version"] = "2"

        async def fake_get_redis():
            return fake_redis

        service._get_redis = fake_get_redis

        async def fetcher():
            return {"fresh": True}

        result = await service.get(
            "leagues:list",
            "active",
            "all",
            1,
            10,
            fetcher=fetcher,
            ttl=300,
            stale_ttl=3600,
        )

        assert result == {"fresh": True}

    asyncio.run(run_test())


def test_provider_league_resolution_maps_internal_ids_to_provider_ids() -> None:
    from api.v1.endpoints.providers import _resolve_provider_league_id

    assert _resolve_provider_league_id("premier_league", "api_football") == "39"
    assert _resolve_provider_league_id("39", "api_football") == "39"
