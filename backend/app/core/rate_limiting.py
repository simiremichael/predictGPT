"""Rate limiting middleware using Redis token-bucket algorithm.

Protects expensive endpoints (prediction generation, research refresh, search)
from abuse while allowing normal read traffic.
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from core.config import get_settings
from db.redis_client import redis_client

settings = get_settings()

# Default rate limits: requests per minute per client
DEFAULT_PUBLIC_LIMIT = 60
DEFAULT_EXPENSIVE_LIMIT = 10
MAX_PAGE_SIZE = 100


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _bucket_key(prefix: str, identifier: str) -> str:
    h = hashlib.md5(identifier.encode()).hexdigest()[:16]
    return f"rate_limit:{prefix}:{h}"


class RateLimiter:
    """Token-bucket rate limiter backed by Redis."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = window_seconds

    async def check(self, identifier: str) -> bool:
        """Return True if allowed, False if rate-limited."""
        key = _bucket_key("rl", identifier)
        try:
            now = int(time.time())
            window_start = now - self.window

            pipe = redis_client.client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window)
            results = await pipe.execute()

            count = results[1]
            return count <= self.limit
        except Exception:
            return True  # Fail open

    async def get_remaining(self, identifier: str) -> tuple[int, int]:
        """Return (remaining, reset_timestamp)."""
        key = _bucket_key("rl", identifier)
        try:
            now = int(time.time())
            window_start = now - self.window
            remaining = self.limit - await redis_client.client.zcount(key, window_start, now)
            reset = now + self.window
            return max(0, remaining), reset
        except Exception:
            return self.limit, int(time.time()) + self.window


def rate_limit(
    limit: int = DEFAULT_PUBLIC_LIMIT,
    window: int = 60,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for FastAPI endpoints requiring rate limiting."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:

        async def wrapper(*args: Any, request: Request | None = None, **kwargs: Any) -> Any:
            if request is not None:
                limiter = RateLimiter(limit, window)
                identifier = _client_ip(request)
                allowed = await limiter.check(identifier)
                if not allowed:
                    remaining, reset = await limiter.get_remaining(identifier)
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"success": False, "error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded"}},
                        headers={
                            "X-RateLimit-Limit": str(limit),
                            "X-RateLimit-Remaining": str(remaining),
                            "X-RateLimit-Reset": str(reset),
                            "Retry-After": str(max(1, reset - int(time.time()))),
                        },
                    )
            return await func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


class IdempotencyMiddleware:
    """Middleware for idempotent POST requests via X-Idempotency-Key header.

    Stores the Response for a given key so duplicate submissions return the
    same result instead of creating duplicate resources.
    """

    TTL = 3600  # 1 hour

    @staticmethod
    async def process_request(request: Request) -> tuple[bool, JSONResponse | None]:
        """Check for an existing idempotent response.

        Returns (should_continue, cached_response).
        If a cached response exists, returns (False, response).
        Otherwise returns (True, None).
        """
        if request.method != "POST":
            return True, None

        key = request.headers.get("X-Idempotency-Key")
        if not key:
            return True, None

        cache_key = f"idempotency:{key}"
        cached = await redis_client.get(cache_key)
        if cached:
            import json

            data = json.loads(cached)
            return False, JSONResponse(
                status_code=data.get("status_code", 200),
                content=data.get("body", {}),
                headers={"X-Idempotent-Replay": "true"},
            )
        return True, None

    @staticmethod
    async def cache_response(request: Request, response: JSONResponse) -> None:
        """Cache a response for future idempotent requests."""
        key = request.headers.get("X-Idempotency-Key")
        if not key or request.method != "POST":
            return

        import json

        cache_key = f"idempotency:{key}"
        body = response.body.decode() if isinstance(response.body, bytes) else response.body
        payload = json.dumps({"status_code": response.status_code, "body": json.loads(body) if body else {}})
        await redis_client.set(cache_key, payload, ttl=IdempotencyMiddleware.TTL)
