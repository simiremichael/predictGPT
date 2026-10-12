"""DuckDuckGo search provider (no API key required).

Uses the DuckDuckGo Instant Answer API for simple queries and falls back
to HTML scraping for search result snippets. This provider is used as the
default when no dedicated search API key is configured.
"""
from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

import httpx

from core.config import get_settings
from web_research.base import SearchResult, WebSearchProvider
from web_research.exceptions import SearchProviderError, SearchRateLimitError

class _DuckDuckGoHTMLParser(HTMLParser):
    """Extract linked results and snippets from DuckDuckGo's HTML page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._current_result: dict[str, str] | None = None
        self._in_title = False
        self._in_snippet = False
        self._title_parts: list[str] = []
        self._snippet_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._current_result = {"url": attributes.get("href") or "", "title": ""}
            self._title_parts = []
            self._in_title = True
        elif tag in {"a", "div", "td"} and "result__snippet" in classes:
            self._snippet_parts = []
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            if self._current_result is not None:
                self._current_result["title"] = " ".join(self._title_parts).strip()
                self.results.append(self._current_result)
            self._current_result = None
            self._in_title = False
        elif tag in {"a", "div", "td"} and self._in_snippet:
            snippet = " ".join(self._snippet_parts).strip()
            if snippet and self.results:
                self.results[-1]["snippet"] = snippet
            self._in_snippet = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        if self._in_snippet:
            self._snippet_parts.append(text)


def _unwrap_duckduckgo_url(url: str) -> str:
    """Resolve DuckDuckGo's redirect links to their destination URL."""
    parsed = urlparse(url)
    target = parse_qs(parsed.query).get("uddg", [None])[0]
    return target if target else url


class DuckDuckGoSearchProvider(WebSearchProvider):
    """Search DuckDuckGo web results with Instant Answers as a fallback."""

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
                    "User-Agent": "FootballAI/1.0 (research; contact@example.com)"
                },
            )
        return self._client

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search linked DuckDuckGo web results, with Instant Answers as fallback."""
        web_search_error: Exception | None = None
        try:
            client = await self._get_client()
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            if response.status_code == 429:
                raise SearchRateLimitError("DuckDuckGo rate limit exceeded")
            if response.status_code != 200:
                raise SearchProviderError(
                    f"DuckDuckGo web search returned {response.status_code}",
                    details={"query": query},
                )

            parser = _DuckDuckGoHTMLParser()
            parser.feed(response.text)
            web_results: list[SearchResult] = []
            for item in parser.results:
                url = _unwrap_duckduckgo_url(item.get("url", ""))
                if url.startswith(("http://", "https://")):
                    web_results.append(
                        SearchResult(
                            title=item.get("title") or None,
                            url=url,
                            snippet=item.get("snippet") or None,
                            source_type="search_result",
                        )
                    )
                    if len(web_results) >= limit:
                        break
            if web_results:
                return web_results
        except SearchRateLimitError:
            raise
        except Exception as exc:
            web_search_error = exc

        # The Instant Answer API is useful for a few known topics, but it is
        # not a general web search API and is commonly empty for match queries.
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
                },
            )
            if response.status_code == 429:
                raise SearchRateLimitError("DuckDuckGo rate limit exceeded")
            if response.status_code != 200:
                raise SearchProviderError(
                    f"DuckDuckGo Instant Answer API returned {response.status_code}",
                    details={"query": query},
                )

            data = response.json()
            if not isinstance(data, dict):
                raise SearchProviderError(
                    "DuckDuckGo Instant Answer API returned an unexpected response",
                    details={"query": query},
                )
            results: list[SearchResult] = []
            if data.get("AbstractText") and data.get("AbstractURL"):
                results.append(
                    SearchResult(
                        title=data.get("AbstractText")[:200],
                        url=data["AbstractURL"],
                        snippet=data.get("AbstractText"),
                        source_type="search_result",
                        publisher=data.get("AbstractSource"),
                    )
                )
            for topic in data.get("RelatedTopics", [])[:limit]:
                if isinstance(topic, dict) and topic.get("Text") and topic.get("FirstURL"):
                    results.append(
                        SearchResult(
                            title=topic.get("Text")[:200],
                            url=topic["FirstURL"],
                            snippet=topic.get("Text"),
                            source_type="search_result",
                        )
                    )
            if results:
                return results[:limit]
            return []
        except SearchRateLimitError:
            raise
        except SearchProviderError as exc:
            api_error = exc
        except Exception as exc:
            api_error = exc
        if web_search_error:
            raise SearchProviderError(
                f"DuckDuckGo search failed: web results: {web_search_error}; "
                f"instant answers: {api_error}",
                details={"query": query},
            ) from api_error
        raise SearchProviderError(
            f"DuckDuckGo Instant Answer search failed: {api_error}",
            details={"query": query},
        ) from api_error

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
