"""You.com search provider."""
from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

import httpx
from web_research.base import SearchResult, WebSearchProvider
from web_research.exceptions import SearchProviderError, SearchRateLimitError

logger = logging.getLogger(__name__)
_quota_state_lock = threading.Lock()
_youcom_fallback_until: datetime | None = None


def _next_month_start(now: datetime) -> datetime:
    if now.month == 12:
        return now.replace(
            year=now.year + 1,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    return now.replace(
        month=now.month + 1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _is_youcom_quota_exhausted() -> bool:
    global _youcom_fallback_until
    now = datetime.now(UTC)
    with _quota_state_lock:
        if _youcom_fallback_until and now >= _youcom_fallback_until:
            _youcom_fallback_until = None
        return _youcom_fallback_until is not None


def _mark_youcom_quota_exhausted() -> bool:
    global _youcom_fallback_until
    now = datetime.now(UTC)
    with _quota_state_lock:
        if _youcom_fallback_until and now >= _youcom_fallback_until:
            _youcom_fallback_until = None
        newly_exhausted = _youcom_fallback_until is None
        if newly_exhausted:
            _youcom_fallback_until = _next_month_start(now)
        return newly_exhausted


class YouComSearchProvider(WebSearchProvider):
    """Search You.com and fall back to a secondary provider after quota exhaustion."""

    provider_name = "youcom"

    def __init__(
        self,
        api_key: str,
        fallback_provider: WebSearchProvider | None = None,
        base_url: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._fallback_provider = fallback_provider
        self._endpoint = base_url or "https://ydc-index.io/v1/search"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if _is_youcom_quota_exhausted():
            return await self._search_with_fallback(query, limit)

        try:
            response = await self._client.post(
                self._endpoint,
                json={
                    "query": query,
                    "count": max(0, min(limit, 20)),
                    "include_published_date": True,
                },
            )
        except httpx.TimeoutException as exc:
            raise SearchProviderError(
                "You.com search request timed out", details={"query": query}
            ) from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError(
                f"You.com search request failed: {exc}", details={"query": query}
            ) from exc

        if response.status_code in {402, 432, 433}:
            if _mark_youcom_quota_exhausted():
                logger.warning(
                    "You.com quota exhausted (HTTP %s); switching to fallback",
                    response.status_code,
                )
            return await self._search_with_fallback(query, limit)
        if response.status_code == 429:
            logger.warning("You.com request rate limit reached; using fallback for this query")
            return await self._search_with_fallback(query, limit)
        if response.status_code != 200:
            raise SearchProviderError(
                f"You.com search returned HTTP {response.status_code}",
                details={"query": query, "status_code": response.status_code},
            )

        try:
            data: Any = response.json()
        except ValueError as exc:
            raise SearchProviderError(
                "You.com search returned invalid JSON", details={"query": query}
            ) from exc
        if not isinstance(data, dict):
            raise SearchProviderError(
                "You.com search returned an unexpected response",
                details={"query": query},
            )

        results: list[SearchResult] = []
        for item in data.get("results", {}).get("web", []):
            if not isinstance(item, dict) or not item.get("url"):
                continue
            snippets = item.get("snippets", [])
            results.append(
                SearchResult(
                    title=item.get("title"),
                    url=item["url"],
                    snippet=snippets[0] if snippets else None,
                    source_type="search_result",
                    publisher=item.get("publisher"),
                    published_at=item.get("published_at"),
                    result_metadata={
                        "snippets": snippets,
                    } if len(snippets) > 1 else None,
                )
            )
        return results[:limit]

    async def _search_with_fallback(
        self, query: str, limit: int
    ) -> list[SearchResult]:
        if self._fallback_provider is None:
            raise SearchRateLimitError(
                "You.com is unavailable and no fallback provider is configured",
                details={"query": query},
            )
        return await self._fallback_provider.search(query, limit=limit)

    async def close(self) -> None:
        await self._client.aclose()
        if self._fallback_provider is not None:
            await self._fallback_provider.close()
