"""DuckDuckGo Instant Answer API provider.

DuckDuckGo documents its Instant Answer API, but does not provide a general
web-results API for third-party applications. This provider uses only the
documented Instant Answer endpoint; it does not scrape DuckDuckGo's HTML
search pages.
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import httpx

from core.config import get_settings
from web_research.base import SearchResult, WebSearchProvider
from web_research.exceptions import SearchProviderError, SearchRateLimitError

_MIN_REQUEST_INTERVAL_SECONDS = 5.0
_rate_limit_lock = threading.Lock()
_next_request_at = 0.0


async def _wait_for_duckduckgo_slot() -> None:
    """Reserve a process-wide request slot for DuckDuckGo."""
    global _next_request_at

    with _rate_limit_lock:
        now = time.monotonic()
        request_at = max(now, _next_request_at)
        _next_request_at = request_at + _MIN_REQUEST_INTERVAL_SECONDS

    delay = request_at - now
    if delay > 0:
        await asyncio.sleep(delay)


class DuckDuckGoSearchProvider(WebSearchProvider):
    """Query DuckDuckGo's documented Instant Answer API at a paced rate."""

    provider_name = "duckduckgo"

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self._settings = get_settings()
        self._base_url = base_url or self._settings.web_search_base_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={
                    "User-Agent": "predictGPT/1.0 (football match research)",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Return Instant Answer API matches, or an empty list for no answer."""
        await _wait_for_duckduckgo_slot()
        try:
            client = await self._get_client()
            response = await client.get(
                self._base_url,
                params={
                    "q": query,
                    "format": "json",
                    "no_redirect": "1",
                    "no_html": "1",
                    "skip_disambig": "1",
                    # DuckDuckGo asks API clients to identify their application.
                    "t": "predictgpt",
                },
            )
        except httpx.TimeoutException as exc:
            raise SearchProviderError(
                "DuckDuckGo Instant Answer API request timed out",
                details={"query": query},
            ) from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError(
                f"DuckDuckGo Instant Answer API request failed: {exc}",
                details={"query": query},
            ) from exc

        if response.status_code in {202, 429}:
            raise SearchRateLimitError(
                f"DuckDuckGo Instant Answer API deferred or limited the query "
                f"(HTTP {response.status_code})",
                details={"query": query, "status_code": response.status_code},
            )
        if response.status_code != 200:
            raise SearchProviderError(
                f"DuckDuckGo Instant Answer API returned {response.status_code}",
                details={"query": query, "status_code": response.status_code},
            )

        try:
            data: Any = response.json()
        except ValueError as exc:
            raise SearchProviderError(
                "DuckDuckGo Instant Answer API returned invalid JSON",
                details={"query": query},
            ) from exc
        if not isinstance(data, dict):
            raise SearchProviderError(
                "DuckDuckGo Instant Answer API returned an unexpected response",
                details={"query": query},
            )

        results: list[SearchResult] = []
        abstract_text = data.get("AbstractText")
        abstract_url = data.get("AbstractURL")
        if abstract_text and abstract_url:
            results.append(
                SearchResult(
                    title=data.get("Heading") or data.get("AbstractSource") or None,
                    url=abstract_url,
                    snippet=abstract_text,
                    source_type="search_result",
                    publisher=data.get("AbstractSource"),
                )
            )

        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text") and topic.get("FirstURL"):
                results.append(
                    SearchResult(
                        title=topic["Text"][:200],
                        url=topic["FirstURL"],
                        snippet=topic["Text"],
                        source_type="search_result",
                    )
                )
                if len(results) >= limit:
                    break

        return results[:limit]

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
