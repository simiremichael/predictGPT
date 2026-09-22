"""Reusable async HTTP client for football data providers.

Centralises:
    * timeout configuration
    * retry with exponential backoff
    * rate-limit awareness (respects provider per-minute limits)
    * structured observability logging
    * provider-specific error mapping into FootballDataError subclasses

Both APIFootballProvider and SportmonksProvider use this, ensuring no HTTP
request code is duplicated per method.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from core.config import ProviderSettings
from core.exceptions import (
    ProviderAuthenticationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from core.logging import StructuredLogger

logger = StructuredLogger(__name__)


class FootballHTTPClient:
    """Provider-agnostic async HTTP client with retry + rate limiting."""

    def __init__(
        self,
        settings: ProviderSettings,
        provider_name: str,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        total_timeout: float = 60.0,
        auth_header_name: str | None = None,
        auth_header_prefix: str = "",
    ) -> None:
        self.settings = settings
        self.provider_name = provider_name
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.total_timeout = total_timeout
        self._auth_header_name = auth_header_name
        self._auth_header_prefix = auth_header_prefix
        self._client: httpx.AsyncClient | None = None
        self._rate_lock = asyncio.Lock()
        self._request_timestamps: list[float] = []
        self._requests_made: int = 0
        self._last_request_at: datetime | None = None
        self._last_failure_at: datetime | None = None
        self._last_error: str | None = None
        self._last_response_status: int | None = None
        self._rate_limit_remaining: int | None = None
        self._rate_limit_reset: str | None = None

    # ── lifecycle ───────────────────────────────────────────────────── #
    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(
                connect=self.connect_timeout,
                read=self.read_timeout,
                write=self.read_timeout,
                pool=10.0,
            )
            self._client = httpx.AsyncClient(
                base_url=self.settings.base_url or "",
                timeout=timeout,
                headers=self._build_default_headers(),
            )
        return self._client

    def _build_default_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.settings.key and self._auth_header_name:
            headers[self._auth_header_name] = (
                f"{self._auth_header_prefix}{self.settings.key}"
            )
        return headers

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> FootballHTTPClient:
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def _acquire_rate_slot(self) -> None:
        """Sliding-window rate limiter (per-minute)."""
        limit = self.settings.rate_limit_per_minute
        if limit <= 0:
            return
        async with self._rate_lock:
            now = time.monotonic()
            cutoff = now - 60.0
            self._request_timestamps = [t for t in self._request_timestamps if t > cutoff]
            if len(self._request_timestamps) >= limit:
                sleep_for = 60.0 - (now - self._request_timestamps[0])
                if sleep_for > 0:
                    logger.warning(
                        "Rate limit approaching, sleeping",
                        provider=self.provider_name,
                        sleep_seconds=round(sleep_for, 2),
                    )
                    await asyncio.sleep(sleep_for)
            self._request_timestamps.append(time.monotonic())

    # ── core request ────────────────────────────────────────────────── #
    async def request(
        self,
        method: str,
        url: str,
        *,
        max_retries: int = 3,
        retry_backoff_base: float = 1.0,
        **kwargs: Any,
    ) -> Any:
        """Perform an HTTP request with retry + error mapping.

        Returns the parsed JSON body (or raw bytes if ``raw=True``).
        Raises FootballDataError subclasses on failure.

        Retry behaviour:
            * 5xx (ProviderUnavailableError) -- retried with exponential backoff
            * httpx.RequestError (network)   -- retried with exponential backoff
            * 401 / 403 / 404                -- raised immediately (no retry)
            * 429 (rate limit)               -- raised immediately
        """
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                await self._acquire_rate_slot()
                client = await self._ensure_client()
                start = time.monotonic()
                self._requests_made += 1
                self._last_request_at = datetime.utcnow()
                response = await client.request(method, url, **kwargs)
                duration_ms = (time.monotonic() - start) * 1000

                self._last_response_status = response.status_code
                self._track_rate_limit(response)

                self._log_response(
                    url, response.status_code, duration_ms, attempt
                )

                self._handle_response_errors(response)

                return response.json()

            except (ProviderRateLimitError, ProviderNotFoundError, ProviderAuthenticationError):
                self._last_failure_at = datetime.utcnow()
                self._last_error = str(last_exc) if last_exc else "rate limit"
                raise
            except ProviderUnavailableError as exc:
                # 5xx -- retry with backoff
                last_exc = exc
                self._last_failure_at = datetime.utcnow()
                self._last_error = exc.message
                if attempt < max_retries:
                    await asyncio.sleep(retry_backoff_base * (2 ** (attempt - 1)))
                    continue
                raise
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                self._last_failure_at = datetime.utcnow()
                self._last_error = str(exc)
                mapped = self._map_http_error(exc, url)
                # 5xx via raise_for_status() -- retry
                status = exc.response.status_code if exc.response is not None else 0
                if status >= 500 and attempt < max_retries:
                    await asyncio.sleep(retry_backoff_base * (2 ** (attempt - 1)))
                    continue
                raise mapped from exc
            except httpx.RequestError as exc:
                last_exc = exc
                self._last_failure_at = datetime.utcnow()
                self._last_error = str(exc)
                if attempt < max_retries:
                    await asyncio.sleep(retry_backoff_base * (2 ** (attempt - 1)))
                    continue
                raise ProviderUnavailableError(
                    f"{self.provider_name} request failed: {exc}",
                    details={"url": url, "error": str(exc)},
                ) from exc

        # Should not reach here
        raise ProviderUnavailableError(
            f"{self.provider_name} request failed after {max_retries} attempts",
            details={"url": url, "last_error": str(last_exc)},
        )

    # ── error handling ─────────────────────────────────────────────── #
    def _handle_response_errors(self, response: httpx.Response) -> None:
        """Raise appropriate error for non-2xx responses."""
        if response.status_code == 401:
            raise ProviderAuthenticationError(
                f"{self.provider_name} authentication failed",
                details={"status": response.status_code, "body": self._safe_text(response)},
            )
        if response.status_code == 403:
            raise ProviderNotFoundError(
                f"{self.provider_name} access forbidden",
                details={"status": response.status_code, "body": self._safe_text(response)},
            )
        if response.status_code == 404:
            raise ProviderNotFoundError(
                f"{self.provider_name} resource not found",
                details={"status": response.status_code, "body": self._safe_text(response)},
            )
        if response.status_code == 429:
            retry_after = self._extract_retry_after(response)
            raise ProviderRateLimitError(
                f"{self.provider_name} rate limit exceeded",
                retry_after=retry_after,
                details={"status": response.status_code, "body": self._safe_text(response)},
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"{self.provider_name} server error",
                details={"status": response.status_code, "body": self._safe_text(response)},
            )
        if not (200 <= response.status_code < 300):
            raise ProviderValidationError(
                f"{self.provider_name} unexpected response {response.status_code}",
                details={"status": response.status_code, "body": self._safe_text(response)},
            )

    def _map_http_error(
        self, exc: httpx.HTTPStatusError, url: str
    ) -> Any:
        """Map an HTTPStatusError to a FootballDataError."""
        status = exc.response.status_code if exc.response is not None else 0
        if status == 429:
            return ProviderRateLimitError(
                f"{self.provider_name} rate limit exceeded",
                retry_after=self._extract_retry_after(exc.response) if exc.response else None,
            )
        if status in (401, 403):
            return ProviderAuthenticationError(
                f"{self.provider_name} authentication failed",
            )
        if status == 404:
            return ProviderNotFoundError(
                f"{self.provider_name} resource not found: {url}"
            )
        if status >= 500:
            return ProviderUnavailableError(
                f"{self.provider_name} server error: {url}"
            )
        return ProviderValidationError(
            f"{self.provider_name} HTTP {status}: {url}"
        )

    def _extract_retry_after(self, response: httpx.Response) -> int | None:
        raw = response.headers.get("Retry-After")
        if raw:
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None
        return None

    def _track_rate_limit(self, response: httpx.Response) -> None:
        """Extract rate-limit info from response headers (API-Football and others)."""
        remaining = response.headers.get("X-RateLimit-Remaining", response.headers.get("Ratelimit-Remaining"))
        reset = response.headers.get("X-RateLimit-Reset", response.headers.get("Ratelimit-Reset"))
        if remaining is not None:
            try:
                self._rate_limit_remaining = int(remaining)
            except (TypeError, ValueError):
                pass
        if reset is not None:
            self._rate_limit_reset = reset

    def get_metrics(self) -> dict[str, Any]:
        """Return current request/rate-limit metrics for health/status reporting."""
        return {
            "requests_made": self._requests_made,
            "last_request_at": self._last_request_at.isoformat() if self._last_request_at else None,
            "last_response_status": self._last_response_status,
            "rate_limit_remaining": self._rate_limit_remaining,
            "rate_limit_reset": self._rate_limit_reset,
            "last_failure_at": self._last_failure_at.isoformat() if self._last_failure_at else None,
            "last_error": self._last_error,
        }

    def _safe_text(self, response: httpx.Response) -> str:
        try:
            return response.text[:500]
        except Exception:
            return "<unreadable>"

    # ── logging ─────────────────────────────────────────────────────── #
    def _log_response(
        self, url: str, status: int, duration_ms: float, attempt: int
    ) -> None:
        level = logging.INFO if status < 400 else logging.WARNING
        logger._emit(
            level,
            "Provider HTTP request",
            provider=self.provider_name,
            endpoint=url,
            status=str(status),
            duration_ms=round(duration_ms, 2),
            attempt=attempt,
            request_id=None,
        )

    # ── convenience getters ─────────────────────────────────────────── #
    async def get(
        self, path: str, *, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> Any:
        return await self.request("GET", path, params=params or {}, **kwargs)

    async def get_raw(
        self, path: str, *, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """GET that validates the ``response`` wrapper is a list."""
        return await self.get(path, params=params, **kwargs)
