"""Tests for the FootballHTTPClient error mapping and rate limiting."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.config import ProviderSettings
from core.exceptions import (
    ProviderAuthenticationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from football_data.http_client import FootballHTTPClient


def _make_client(rate_limit: int = 10) -> FootballHTTPClient:
    settings = ProviderSettings(
        key="test-key",
        base_url="https://api.test.com",
        enabled=True,
        rate_limit_per_minute=rate_limit,
        timeout_seconds=30,
    )
    client = FootballHTTPClient(settings, "test_provider")
    return client


def _mock_response(status_code: int, json_data: dict | None = None, headers: dict | None = None) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.headers = headers or {}
    mock.text = str(json_data) if json_data else "{}"
    mock.json.return_value = json_data if json_data else {"results": 0, "response": []}
    return mock


def _wire_mock_client(client: FootballHTTPClient, mock_response: MagicMock) -> MagicMock:
    """Replace the internal httpx client with a mock that returns mock_response."""
    mock_http = MagicMock()
    mock_http.is_closed = False
    mock_http.request = AsyncMock(return_value=mock_response)
    client._client = mock_http
    return mock_http


@pytest.mark.asyncio
class TestErrorMapping:
    async def test_401_maps_to_auth_error(self) -> None:
        client = _make_client()
        _wire_mock_client(client, _mock_response(401))
        with pytest.raises(ProviderAuthenticationError):
            await client.get("/test")

    async def test_403_maps_to_not_found(self) -> None:
        client = _make_client()
        _wire_mock_client(client, _mock_response(403))
        with pytest.raises(ProviderNotFoundError):
            await client.get("/test")

    async def test_404_maps_to_not_found(self) -> None:
        client = _make_client()
        _wire_mock_client(client, _mock_response(404))
        with pytest.raises(ProviderNotFoundError):
            await client.get("/test")

    async def test_429_maps_to_rate_limit(self) -> None:
        client = _make_client()
        _wire_mock_client(client, _mock_response(429, headers={"Retry-After": "30"}))
        with pytest.raises(ProviderRateLimitError) as exc_info:
            await client.get("/test")
        assert exc_info.value.retry_after == 30

    async def test_500_maps_to_unavailable(self) -> None:
        client = _make_client()
        _wire_mock_client(client, _mock_response(500))
        with pytest.raises(ProviderUnavailableError):
            await client.get("/test")

    async def test_503_retries_then_fails(self) -> None:
        client = _make_client()
        call_count = 0
        mock_http = MagicMock()
        mock_http.is_closed = False

        async def fake_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _mock_response(503)

        mock_http.request = fake_request
        client._client = mock_http

        with pytest.raises(ProviderUnavailableError):
            await client.request("GET", "/test", max_retries=2)
        assert call_count == 2

    async def test_503_then_success(self) -> None:
        client = _make_client()
        call_count = 0
        mock_http = MagicMock()
        mock_http.is_closed = False

        async def fake_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return _mock_response(503)
            return _mock_response(200, {"ok": True})

        mock_http.request = fake_request
        client._client = mock_http

        result = await client.request("GET", "/test", max_retries=3)
        assert result == {"ok": True}
        assert call_count == 3

    async def test_request_error_maps_to_unavailable(self) -> None:
        client = _make_client()
        mock_http = MagicMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        client._client = mock_http

        with pytest.raises(ProviderUnavailableError):
            await client.get("/test")

    async def test_400_maps_to_validation_error(self) -> None:
        from core.exceptions import ProviderValidationError

        client = _make_client()
        _wire_mock_client(client, _mock_response(400, {"error": "bad request"}))
        with pytest.raises(ProviderValidationError):
            await client.get("/test")

    async def test_rate_limiter_allows_normal_usage(self) -> None:
        client = _make_client(rate_limit=100)
        _wire_mock_client(client, _mock_response(200, {"ok": True}))
        result = await client.get("/test")
        assert result == {"ok": True}
