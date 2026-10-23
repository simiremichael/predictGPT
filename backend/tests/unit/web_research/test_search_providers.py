"""Tests for the You.com and Brave search providers."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from web_research.base import SearchResult
from web_research.brave import BraveSearchProvider
from web_research.exceptions import SearchProviderError, SearchRateLimitError
from web_research.tavily import TavilySearchProvider
from web_research.youcom import YouComSearchProvider


@pytest.fixture
def brave_provider() -> BraveSearchProvider:
    return BraveSearchProvider(api_key="brave-key")


@pytest.fixture
def youcom_provider(brave_provider: BraveSearchProvider) -> YouComSearchProvider:
    return YouComSearchProvider(
        api_key="you-key",
        fallback_provider=brave_provider,
    )


class TestYouComSearchProvider:
    @pytest.mark.asyncio
    async def test_returns_results_from_youcom(
        self, youcom_provider: YouComSearchProvider
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "results": {
                    "web": [
                        {
                            "title": "Arsenal Injury News",
                            "url": "https://example.com/arsenal-injury",
                            "snippets": ["Bukayo Saka is doubtful for the match"],
                            "publisher": "Football News",
                            "published_at": "2024-01-15T10:00:00Z",
                        },
                        {
                            "title": "Chelsea Team News",
                            "url": "https://example.com/chelsea-news",
                            "snippets": ["Cole Palmer starts training"],
                        },
                    ]
                }
            }
        )
        youcom_provider._client = MagicMock()
        youcom_provider._client.post = AsyncMock(return_value=mock_response)
        youcom_provider._fallback_provider = None

        results = await youcom_provider.search("Arsenal vs Chelsea injuries", limit=3)

        assert len(results) == 2
        assert results[0].title == "Arsenal Injury News"
        assert results[0].url == "https://example.com/arsenal-injury"
        assert results[0].snippet == "Bukayo Saka is doubtful for the match"
        assert results[0].publisher == "Football News"
        assert results[0].published_at == "2024-01-15T10:00:00Z"
        assert results[1].title == "Chelsea Team News"

    @pytest.mark.asyncio
    async def test_falls_back_to_brave_on_quota_exhaustion(
        self, youcom_provider: YouComSearchProvider, brave_provider: BraveSearchProvider
    ) -> None:
        from datetime import UTC, datetime, timedelta

        import web_research.youcom as youcom_module

        original = youcom_module._youcom_fallback_until
        try:
            # Force quota exhaustion
            youcom_module._youcom_fallback_until = datetime.now(UTC) + timedelta(hours=1)

            # Mock Brave to return results
            brave_provider._client = MagicMock()
            brave_response = MagicMock()
            brave_response.status_code = 200
            brave_response.json = MagicMock(
                return_value={
                    "web": {
                        "results": [
                            {"title": "Brave Result", "url": "https://brave.example/result"},
                        ]
                    }
                }
            )
            brave_provider._client.post = AsyncMock(return_value=brave_response)

            results = await youcom_provider.search("test query", limit=3)

            assert len(results) == 1
            assert results[0].title == "Brave Result"
            assert results[0].url == "https://brave.example/result"
        finally:
            youcom_module._youcom_fallback_until = original

    @pytest.mark.asyncio
    async def test_handles_empty_results(
        self, youcom_provider: YouComSearchProvider
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"results": {"web": []}})

        youcom_provider._client = MagicMock()
        youcom_provider._client.post = AsyncMock(return_value=mock_response)
        youcom_provider._fallback_provider = None

        results = await youcom_provider.search("empty query", limit=3)
        assert results == []

    @pytest.mark.asyncio
    async def test_raises_on_non_200(
        self, youcom_provider: YouComSearchProvider
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500

        youcom_provider._client = MagicMock()
        youcom_provider._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(SearchProviderError):
            await youcom_provider.search("bad request", limit=3)

    @pytest.mark.asyncio
    async def test_raises_on_timeout(
        self, youcom_provider: YouComSearchProvider
    ) -> None:
        import httpx

        youcom_provider._client = MagicMock()
        youcom_provider._client.post = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )
        youcom_provider._fallback_provider = None

        with pytest.raises(SearchProviderError, match="timed out"):
            await youcom_provider.search("timeout query", limit=3)

    @pytest.mark.asyncio
    async def test_empty_results_fall_back_to_configured_provider(
        self, youcom_provider: YouComSearchProvider
    ) -> None:
        fallback = MagicMock()
        fallback.search = AsyncMock(return_value=[
            SearchResult(title="Fallback", url="https://example.com", snippet="news")
        ])
        youcom_provider._fallback_provider = fallback
        response = MagicMock(status_code=200)
        response.json = MagicMock(return_value={"results": {"web": []}})
        youcom_provider._client = MagicMock()
        youcom_provider._client.post = AsyncMock(return_value=response)

        results = await youcom_provider.search("empty query", limit=1)

        assert results[0].title == "Fallback"
        fallback.search.assert_awaited_once_with("empty query", limit=1)

    @pytest.mark.asyncio
    async def test_transient_error_falls_back_to_configured_provider(
        self, youcom_provider: YouComSearchProvider
    ) -> None:
        fallback = MagicMock()
        fallback.search = AsyncMock(return_value=[
            SearchResult(title="Fallback", url="https://example.com", snippet="news")
        ])
        youcom_provider._fallback_provider = fallback
        youcom_provider._client = MagicMock()
        youcom_provider._client.post = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )

        results = await youcom_provider.search("timeout query", limit=1)

        assert results[0].title == "Fallback"
        fallback.search.assert_awaited_once_with("timeout query", limit=1)


class TestBraveSearchProvider:
    @pytest.fixture(autouse=True)
    def reset_brave_circuit(self):
        import web_research.brave as brave_module

        original = brave_module._brave_fallback_until
        brave_module._brave_fallback_until = None
        yield
        brave_module._brave_fallback_until = original

    @pytest.mark.asyncio
    async def test_empty_results_fall_back_to_youcom(self) -> None:
        fallback = MagicMock()
        fallback.search = AsyncMock(return_value=[
            SearchResult(title="Fallback", url="https://example.com", snippet="news")
        ])
        provider = BraveSearchProvider(api_key="brave-key", fallback_provider=fallback)
        provider._client = MagicMock()
        response = MagicMock(status_code=200)
        response.json = MagicMock(return_value={"web": {"results": []}})
        provider._client.post = AsyncMock(return_value=response)

        results = await provider.search("empty query", limit=1)

        assert results[0].title == "Fallback"
        fallback.search.assert_awaited_once_with("empty query", limit=1)

    @pytest.mark.asyncio
    async def test_returns_results_from_brave(self) -> None:
        provider = BraveSearchProvider(api_key="brave-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "web": {
                    "results": [
                        {
                            "title": "Brave Result 1",
                            "url": "https://example.com/1",
                            "snippet": "First result snippet",
                            "extra_snippets": ["Extra 1", "Extra 2"],
                        },
                        {
                            "title": "Brave Result 2",
                            "url": "https://example.com/2",
                            "snippet": "Second result",
                        },
                    ]
                }
            }
        )
        provider._client = MagicMock()
        provider._client.post = AsyncMock(return_value=mock_response)

        results = await provider.search("football news", limit=5)

        assert len(results) == 2
        assert results[0].title == "Brave Result 1"
        assert results[0].url == "https://example.com/1"
        assert results[0].snippet == "First result snippet"
        assert results[0].result_metadata is not None
        assert results[0].result_metadata["extra_snippets"] == ["Extra 1", "Extra 2"]
        assert results[1].title == "Brave Result 2"

    @pytest.mark.asyncio
    async def test_uses_extra_snippet_when_no_regular_snippet(self) -> None:
        provider = BraveSearchProvider(api_key="brave-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "web": {
                    "results": [
                        {
                            "title": "No Snippet Result",
                            "url": "https://example.com/3",
                            "snippet": None,
                            "extra_snippets": ["Extra-only snippet"],
                        },
                    ]
                }
            }
        )
        provider._client = MagicMock()
        provider._client.post = AsyncMock(return_value=mock_response)

        results = await provider.search("test query", limit=5)

        assert len(results) == 1
        assert results[0].snippet == "Extra-only snippet"

    @pytest.mark.asyncio
    async def test_raises_on_unauthorized(self) -> None:
        provider = BraveSearchProvider(api_key="brave-key")
        mock_response = MagicMock()
        mock_response.status_code = 401

        provider._client = MagicMock()
        provider._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(SearchProviderError, match="authentication failed"):
            await provider.search("unauthorized query", limit=5)

    @pytest.mark.asyncio
    async def test_raises_on_quota_exhausted(self) -> None:
        provider = BraveSearchProvider(api_key="brave-key")
        mock_response = MagicMock()
        mock_response.status_code = 402

        provider._client = MagicMock()
        provider._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(SearchRateLimitError, match="quota exhausted"):
            await provider.search("exhausted query", limit=5)


class TestTavilySearchProvider:
    @pytest.mark.asyncio
    async def test_first_failure_uses_brave_and_routes_next_query_to_fallback(self) -> None:
        import web_research.tavily as tavily_module

        fallback = MagicMock()
        fallback.provider_name = "brave"
        fallback.search = AsyncMock(
            return_value=[SearchResult(title="Fallback", url="https://example.com", snippet="news")]
        )
        provider = TavilySearchProvider(api_key="tavily-key", fallback_provider=fallback)
        original_client = provider._client
        provider._client = MagicMock()
        provider._client.post = AsyncMock(return_value=MagicMock(status_code=503))
        provider._client.aclose = AsyncMock()
        previous_circuit = tavily_module._tavily_fallback_until
        tavily_module._tavily_fallback_until = None

        try:
            first = await provider.search("first query", limit=1)
            second = await provider.search("second query", limit=1)

            assert first[0].title == "Fallback"
            assert second[0].title == "Fallback"
            assert provider._client.post.await_count == 1
            assert fallback.search.await_count == 2
        finally:
            tavily_module._tavily_fallback_until = previous_circuit
            await provider._client.aclose()
            await original_client.aclose()

    @pytest.mark.asyncio
    async def test_empty_tavily_results_fall_back_immediately(self) -> None:
        import web_research.tavily as tavily_module

        fallback = MagicMock()
        fallback.provider_name = "brave"
        fallback.search = AsyncMock(
            return_value=[SearchResult(title="Fallback", url="https://example.com", snippet="news")]
        )
        provider = TavilySearchProvider(api_key="tavily-key", fallback_provider=fallback)
        original_client = provider._client
        provider._client = MagicMock()
        provider._client.post = AsyncMock(
            return_value=MagicMock(status_code=200, json=MagicMock(return_value={"results": []}))
        )
        provider._client.aclose = AsyncMock()
        previous_circuit = tavily_module._tavily_fallback_until
        tavily_module._tavily_fallback_until = None

        try:
            results = await provider.search("empty query", limit=1)
            assert results[0].title == "Fallback"
            assert fallback.search.await_count == 1
        finally:
            tavily_module._tavily_fallback_until = previous_circuit
            await provider._client.aclose()
            await original_client.aclose()
