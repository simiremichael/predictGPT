"""Redis cache client wrapper."""
from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis

from core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class RedisClient:
    """Thin async wrapper around redis with JSON value support."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        self._client = redis.from_url(self._url, decode_responses=True)
        try:
            await self._client.ping()
            logger.info("Redis connection established", extra={"provider": "redis"})
        except Exception as exc:  # pragma: no cover - connectivity is environment dependent
            logger.warning("Redis ping failed", extra={"error": str(exc)})

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client is not connected. Call connect() first.")
        return self._client

    # -- basic key/value ------------------------------------------------ #
    async def get(self, key: str) -> str | None:
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self.client.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def expire(self, key: str, ttl: int) -> None:
        await self.client.expire(key, ttl)

    # -- JSON helpers --------------------------------------------------- #
    async def get_json(self, key: str) -> Any:
        raw = await self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self.set(key, json.dumps(value), ttl=ttl)

    async def exists(self, key: str) -> bool:
        return await self.client.exists(key) > 0


redis_client = RedisClient(settings.redis_url)


async def get_redis() -> RedisClient:
    """FastAPI dependency for the Redis client."""
    return redis_client
