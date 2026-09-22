"""Frontend Redis cache service with database change revalidation.

This service provides a caching layer for the frontend that:
1. Caches API responses in Redis with TTL
2. Uses database change notifications to invalidate cache
3. Supports stale-while-revalidate pattern for better UX
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Callable, Optional

from core.config import get_settings
from db.redis_client import get_redis

logger = logging.getLogger(__name__)


class FrontendCacheService:
    """Redis cache service for frontend with DB-change revalidation."""

    def __init__(self):
        self.settings = get_settings()
        self._redis = None
        self._db_version = 0
        self._last_db_check = 0
        self._db_check_interval = 5  # seconds

    async def _get_redis(self):
        """Get or create Redis client. Returns None if Redis unavailable."""
        if self._redis is None:
            try:
                self._redis = await get_redis()
                if self._redis.client is None:
                    await self._redis.connect()
            except Exception as exc:
                logger.warning("Redis client unavailable: %s", exc)
                return None
        return self._redis

    def _cache_key(self, namespace: str, *parts: Any) -> str:
        """Generate a cache key."""
        raw = "|".join(str(p) for p in parts)
        digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return f"frontend:{namespace}:{digest}"

    async def _check_db_version(self) -> int:
        """Check database version for cache invalidation.

        Returns a version number that increments when database changes.
        Uses a Redis key that gets updated by the sync job.
        """
        redis = await self._get_redis()
        if redis is None:
            return self._db_version
        try:
            version = await redis.get("db:version")
            return int(version) if version else 0
        except Exception:
            return self._db_version

    async def _increment_db_version(self) -> int:
        """Increment database version (called by sync job)."""
        redis = await self._get_redis()
        if redis is None:
            return 0
        try:
            new_version = await redis.client.incr("db:version")
            logger.info("Database version incremented to %d", new_version)
            return new_version
        except Exception as exc:
            logger.error("Failed to increment DB version: %s", exc)
            return 0

    async def get(
        self,
        namespace: str,
        *keys: Any,
        fetcher: Optional[Callable] = None,
        ttl: int = 300,
        stale_ttl: int = 3600,
    ) -> Any:
        """Get cached value with optional fetcher and stale-while-revalidate.

        Args:
            namespace: Cache namespace (e.g., "leagues", "fixtures")
            keys: Cache key parts
            fetcher: Async function to fetch fresh data if cache miss
            ttl: Time-to-live for fresh cache (seconds)
            stale_ttl: Time-to-live for stale cache (seconds)

        Returns:
            Cached or freshly fetched data
        """
        redis = await self._get_redis()
        cache_key = self._cache_key(namespace, *keys)

        # If Redis is unavailable, just use the fetcher directly
        if redis is None:
            if fetcher:
                return await fetcher()
            return None

        # Check database version for cache invalidation
        try:
            current_db_version = await self._check_db_version()
            if current_db_version > self._db_version:
                # Database changed, invalidate this cache
                self._db_version = current_db_version
                await redis.delete(cache_key)
                logger.debug("Cache invalidated due to DB change: %s", cache_key)
        except Exception:
            current_db_version = self._db_version

        # Try to get fresh cache
        try:
            cached = await redis.get_json(cache_key)
        except Exception:
            cached = None

        stale_key = f"{cache_key}:stale"
        try:
            stale_cached = await redis.get_json(stale_key)
        except Exception:
            stale_cached = None

        if cached is not None:
            # Check if cache has metadata about DB version
            if isinstance(cached, dict) and "_db_version" in cached:
                if cached["_db_version"] == self._db_version:
                    return cached["data"]

                # DB version mismatch means the cached payload is stale.
                # Drop it and fall back to a fresh fetch or stale fallback.
                try:
                    await redis.delete(cache_key)
                except Exception:
                    pass
                cached = None

            # Return cached data (with or without version metadata)
            elif isinstance(cached, dict) and "data" in cached:
                return cached["data"]
            else:
                return cached

        # Try to get stale cache

        # If we have a fetcher, fetch fresh data in background
        if fetcher:
            # Return stale data immediately if available
            if stale_cached is not None:
                if isinstance(stale_cached, dict) and "data" in stale_cached:
                    stale_data = stale_cached["data"]
                else:
                    stale_data = stale_cached

                # Trigger background refresh
                asyncio.create_task(self._refresh_cache(namespace, keys, fetcher, ttl, stale_ttl))
                return stale_data

            # No stale data, fetch fresh
            fresh_data = await fetcher()
            try:
                await self.set(namespace, fresh_data, *keys, ttl=ttl, stale_ttl=stale_ttl)
            except Exception:
                pass
            return fresh_data

        # No fetcher, return stale if available
        if stale_cached is not None:
            if isinstance(stale_cached, dict) and "data" in stale_cached:
                return stale_cached["data"]
            return stale_cached

        return None

    async def _refresh_cache(
        self, namespace: str, keys: tuple, fetcher: Callable, ttl: int, stale_ttl: int
    ) -> None:
        """Background cache refresh."""
        try:
            fresh_data = await fetcher()
            await self.set(namespace, fresh_data, *keys, ttl=ttl, stale_ttl=stale_ttl)
        except Exception as exc:
            logger.warning("Background cache refresh failed: %s", exc)

    async def set(
        self, namespace: str, data: Any, *keys: Any, ttl: int = 300, stale_ttl: int = 3600
    ) -> None:
        """Set cache value with DB version metadata."""
        redis = await self._get_redis()
        if redis is None:
            return
        cache_key = self._cache_key(namespace, *keys)

        # Store with DB version metadata
        cache_value = {
            "data": data,
            "_db_version": self._db_version,
            "_cached_at": time.time(),
        }

        # Set fresh cache and stale cache with error handling
        try:
            await redis.set_json(cache_key, cache_value, ttl=ttl)
            await redis.set_json(f"{cache_key}:stale", cache_value, ttl=stale_ttl)
        except Exception as exc:
            logger.warning("Failed to set cache: %s", exc)

    async def invalidate(self, namespace: str, *keys: Any) -> None:
        """Invalidate cache entries."""
        redis = await self._get_redis()
        if redis is None:
            return
        if keys:
            for key in keys:
                cache_key = self._cache_key(namespace, key)
                try:
                    await redis.delete(cache_key)
                    await redis.delete(f"{cache_key}:stale")
                except Exception:
                    pass
        else:
            # Invalidate all keys in namespace (using pattern)
            pattern = f"frontend:{namespace}:*"
            # Note: This requires Redis SCAN which is not implemented in the wrapper
            # For now, we'll rely on DB version invalidation
            pass

    async def invalidate_all(self) -> None:
        """Invalidate all frontend caches by incrementing DB version."""
        await self._increment_db_version()
        self._db_version = await self._check_db_version()


# Global instance
frontend_cache = FrontendCacheService()


async def get_frontend_cache() -> FrontendCacheService:
    """FastAPI dependency for frontend cache service."""
    return frontend_cache
