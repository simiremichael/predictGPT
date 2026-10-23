"""Tavily search provider with ordered Brave/You.com fallbacks."""
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
_tavily_fallback_until: datetime | None = None


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


def _is_tavily_quota_exhausted() -> bool:
    global _tavily_fallback_until
    now = datetime.now(UTC)
    with _quota_state_lock:
        if _tavily_fallback_until and now >= _tavily_fallback_until:
            _tavily_fallback_until = None
        return _tavily_fallback_until is not None


def _mark_tavily_quota_exhausted() -> bool:
    global _tavily_fallback_until
    now = datetime.now(UTC)
    with _quota_state_lock:
        if _tavily_fallback_until and now >= _tavily_fallback_until:
            _tavily_fallback_until = None
        newly_exhausted = _tavily_fallback_until is None
        if newly_exhausted:
            _tavily_fallback_until = _next_month_start(now)
        return newly_exhausted


class TavilySearchProvider(WebSearchProvider):
    """Search Tavily first, switching to Brave and then You.com if unavailable."""

    provider_name = "tavily"

    def __init__(
        self,
        api_key: str,
        fallback_provider: WebSearchProvider | None = None,
        base_url: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._fallback_provider = fallback_provider
        self._endpoint = base_url or "https://api.tavily.com/search"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if _is_tavily_quota_exhausted():
            return await self._search_with_fallback(query, limit)

        try:
            response = await self._client.post(
                self._endpoint,
                json={
                    "query": query,
                    "search_depth": "basic",
                    "topic": "general",
                    "max_results": max(0, min(limit, 20)),
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
        except httpx.TimeoutException as exc:
            return await self._fallback_or_raise(SearchProviderError(
                "Tavily search request timed out", details={"query": query}
            ), query, limit)
        except httpx.HTTPError as exc:
            return await self._fallback_or_raise(SearchProviderError(
                f"Tavily search request failed: {exc}", details={"query": query}
            ), query, limit)

        if response.status_code in {432, 433}:
            if _mark_tavily_quota_exhausted():
                logger.warning(
                    "Tavily quota exhausted (HTTP %s); switching to fallback",
                    response.status_code,
                )
            return await self._search_with_fallback(query, limit)
        if response.status_code == 429:
            logger.warning("Tavily request rate limit reached; using fallback for this query")
            return await self._search_with_fallback(query, limit)
        if response.status_code != 200:
            return await self._fallback_or_raise(SearchProviderError(
                f"Tavily search returned HTTP {response.status_code}",
                details={"query": query, "status_code": response.status_code},
            ), query, limit)

        try:
            data: Any = response.json()
        except ValueError as exc:
            return await self._fallback_or_raise(SearchProviderError(
                "Tavily search returned invalid JSON", details={"query": query}
            ), query, limit)
        if not isinstance(data, dict):
            return await self._fallback_or_raise(SearchProviderError(
                "Tavily search returned an unexpected response",
                details={"query": query},
            ), query, limit)

        results: list[SearchResult] = []
        for item in data.get("results", []):
            if not isinstance(item, dict) or not item.get("url"):
                continue
            results.append(
                SearchResult(
                    title=item.get("title"),
                    url=item["url"],
                    snippet=item.get("content"),
                    source_type="search_result",
                    published_at=item.get("published_date"),
                    result_metadata={
                        key: item[key]
                        for key in ("score", "favicon")
                        if item.get(key) is not None
                    },
                )
            )
        return results[:limit]

    async def _search_with_fallback(
        self, query: str, limit: int
    ) -> list[SearchResult]:
        if self._fallback_provider is None:
            raise SearchRateLimitError(
                "Tavily is unavailable and no fallback provider is configured",
                details={"query": query},
            )
        return await self._fallback_provider.search(query, limit=limit)

    async def _fallback_or_raise(
        self, error: SearchProviderError, query: str, limit: int
    ) -> list[SearchResult]:
        if self._fallback_provider is None:
            raise error
        logger.warning("Tavily search failed; switching to configured fallback")
        return await self._fallback_provider.search(query, limit=limit)

    async def close(self) -> None:
        await self._client.aclose()
        if self._fallback_provider is not None:
            await self._fallback_provider.close()
