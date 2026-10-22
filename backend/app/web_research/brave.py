"""Brave Search API provider."""
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
_brave_fallback_until: datetime | None = None


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


def _is_brave_quota_exhausted() -> bool:
    global _brave_fallback_until
    now = datetime.now(UTC)
    with _quota_state_lock:
        if _brave_fallback_until and now >= _brave_fallback_until:
            _brave_fallback_until = None
        return _brave_fallback_until is not None


def _mark_brave_quota_exhausted() -> bool:
    global _brave_fallback_until
    now = datetime.now(UTC)
    with _quota_state_lock:
        if _brave_fallback_until and now >= _brave_fallback_until:
            _brave_fallback_until = None
        newly_exhausted = _brave_fallback_until is None
        if newly_exhausted:
            _brave_fallback_until = _next_month_start(now)
        return newly_exhausted


class BraveSearchProvider(WebSearchProvider):
    """Search Brave Search API.

    This is a terminal provider — it does not fall back to another provider.
    When Brave quota or rate limits are exhausted, a SearchRateLimitError is
    raised so the caller can decide how to proceed.
    """

    provider_name = "brave"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        api_key: str,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if _is_brave_quota_exhausted():
            raise SearchRateLimitError(
                "Brave Search API quota exhausted for this month",
                details={"query": query},
            )

        try:
            response = await self._client.post(
                self.endpoint,
                json={
                    "q": query,
                    "count": max(1, min(limit, 20)),
                    "extra_snippets": True,
                },
            )
        except httpx.TimeoutException as exc:
            raise SearchProviderError(
                "Brave Search API request timed out", details={"query": query}
            ) from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError(
                f"Brave Search API request failed: {exc}", details={"query": query}
            ) from exc

        if response.status_code in {401, 403}:
            raise SearchProviderError(
                f"Brave Search API authentication failed (HTTP {response.status_code})",
                details={"query": query, "status_code": response.status_code},
            )
        if response.status_code in {402, 432, 433}:
            if _mark_brave_quota_exhausted():
                logger.warning(
                    "Brave Search API quota exhausted (HTTP %s)",
                    response.status_code,
                )
            raise SearchRateLimitError(
                f"Brave Search API quota exhausted (HTTP {response.status_code})",
                details={"query": query, "status_code": response.status_code},
            )
        if response.status_code == 429:
            logger.warning("Brave Search API request rate limit reached")
            raise SearchRateLimitError(
                "Brave Search API rate limit reached",
                details={"query": query},
            )
        if response.status_code != 200:
            raise SearchProviderError(
                f"Brave Search API returned HTTP {response.status_code}",
                details={"query": query, "status_code": response.status_code},
            )

        try:
            data: Any = response.json()
        except ValueError as exc:
            raise SearchProviderError(
                "Brave Search API returned invalid JSON", details={"query": query}
            ) from exc
        if not isinstance(data, dict):
            raise SearchProviderError(
                "Brave Search API returned an unexpected response",
                details={"query": query},
            )

        results: list[SearchResult] = []
        for item in data.get("web", {}).get("results", []):
            if not isinstance(item, dict) or not item.get("url"):
                continue
            title = item.get("title")
            snippet = item.get("snippet")
            extra_snippets = (item.get("extra_snippets") or [])
            combined_snippet = snippet
            if not combined_snippet and extra_snippets:
                combined_snippet = extra_snippets[0]
            results.append(
                SearchResult(
                    title=title,
                    url=item["url"],
                    snippet=combined_snippet,
                    source_type="search_result",
                    result_metadata={
                        "extra_snippets": extra_snippets[:5],
                    } if len(extra_snippets) > 1 else None,
                )
            )
        return results[:limit]

    async def close(self) -> None:
        await self._client.aclose()
