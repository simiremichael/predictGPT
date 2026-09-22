"""DuckDuckGo search provider (no API key required).

Uses the DuckDuckGo Instant Answer API for simple queries and falls back
to HTML scraping for search result snippets. This provider is used as the
default when no dedicated search API key is configured.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from core.config import get_settings
from web_research.base import SearchResult, WebSearchProvider
from web_research.exceptions import SearchProviderError, SearchRateLimitError

logger = logging.getLogger(__name__)


class DuckDuckGoSearchProvider(WebSearchProvider):
    """Search using the DuckDuckGo Instant Answer API."""

    provider_name = "duckduckgo"

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self._settings = get_settings()
        self._base_url = base_url or self._settings.web_search_base_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers={
                    "User-Agent": "FootballAI/1.0 (research; contact@example.com)"
                },
            )
        return self._client

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search using the DuckDuckGo endpoint."""
        try:
            client = await self._get_client()
            url = f"{self._base_url}?q={query}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
            resp = await client.get(url)

            if resp.status_code == 429:
                raise SearchRateLimitError("DuckDuckGo rate limit exceeded")

            if resp.status_code != 200:
                raise SearchProviderError(
                    f"Search API returned {resp.status_code}",
                    details={"query": query},
                )

            data = resp.json()
            results: list[SearchResult] = []

            if data.get("AbstractText"):
                results.append(
                    SearchResult(
                        title=data.get("AbstractURL"),
                        url=data.get("AbstractURL") or "",
                        snippet=data.get("AbstractText"),
                        source_type="search_result",
                        publisher=data.get("AbstractSource"),
                    )
                )

            for topic in data.get("RelatedTopics", [])[:limit]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(
                        SearchResult(
                            title=topic.get("Text")[:200],
                            url=topic.get("FirstURL") or "",
                            snippet=topic.get("Text"),
                            source_type="search_result",
                    )
                )

            return results[:limit]

        except (SearchProviderError, SearchRateLimitError):
            raise
        except Exception as exc:
            raise SearchProviderError(
                f"Search failed: {exc}",
                details={"query": query},
            ) from exc

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
