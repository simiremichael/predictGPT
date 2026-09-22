"""Dedicated API-Football HTTP client.

This client is responsible only for communication with the API-Football
(api-sports) REST API.  It extends the shared ``FootballHTTPClient`` with
API-Football-specific concerns:

    * Authentication via ``x-apisports-key`` header
    * Pagination handling (API-Football returns ``paging`` in the response)
    * Response wrapper validation (``response``, ``results``, ``errors``)
    * Rate-limit header tracking (``X-RateLimit-Remaining`` etc.)

No prediction or normalization logic lives here; that belongs in the
provider and prediction layers respectively.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx

from core.config import ProviderSettings, get_settings
from core.exceptions import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from core.logging import StructuredLogger
from football_data.http_client import FootballHTTPClient

logger = StructuredLogger(__name__)


class APIFootballClient:
    """Dedicated client for API-Football (api-sports) API communication."""

    provider_name = "api_football"

    # API-Football maximum results per page is 100 for most endpoints,
    # though some endpoints support up to 500.
    DEFAULT_PAGE_SIZE = 100
    MAX_PAGES = 50

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        enabled: bool = True,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.api_football_key
        if not self.api_key:
            raise ProviderConfigurationError("API_FOOTBALL_KEY is required for APIFootballClient.")
        self.base_url = base_url or settings.api_football_base_url

        provider_settings = ProviderSettings(
            key=self.api_key,
            base_url=self.base_url,
            enabled=enabled,
            rate_limit_per_minute=settings.api_football_rate_limit,
            timeout_seconds=settings.football_api_total_timeout,
        )
        self._http = FootballHTTPClient(
            provider_settings,
            self.provider_name,
            connect_timeout=settings.football_api_connect_timeout,
            read_timeout=settings.football_api_read_timeout,
            total_timeout=settings.football_api_total_timeout,
            auth_header_name="x-apisports-key",
        )

    # ── lifecycle ───────────────────────────────────────────────────── #
    @property
    def http(self) -> FootballHTTPClient:
        return self._http

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> APIFootballClient:
        await self._http._ensure_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # ── core request ────────────────────────────────────────────────── #
    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> Any:
        """Make a single (non-paginated) API request.

        Returns the ``response`` list from the API-Football envelope.
        """
        merged_params: dict[str, Any] = params or {}
        data = await self._http.request(
            method, endpoint, params=merged_params, max_retries=max_retries, **kwargs
        )
        return self._unwrap_response(data)

    async def get_paginated(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        max_pages: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        supports_pagination: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield each page's ``response`` list, following API-Football pagination.

        Some API-Football endpoints reject the ``page`` / ``per_page`` parameters,
        even though they follow the same response envelope. For those endpoints we
        disable pagination and make a single request instead.
        """
        if not supports_pagination:
            data = await self._http.request("GET", endpoint, params=params or {})
            response_list = self._unwrap_response(data)
            if response_list:
                yield response_list
            return

        if max_pages is None:
            max_pages = self.MAX_PAGES
        elif max_pages > self.MAX_PAGES:
            max_pages = self.MAX_PAGES

        merged_params: dict[str, Any] = {**(params or {})}
        merged_params.setdefault("per_page", page_size)

        current_page = 1
        pages_yielded = 0

        while pages_yielded < max_pages:
            merged_params["page"] = str(current_page)
            data = await self._http.request("GET", endpoint, params=merged_params)
            response_list = self._unwrap_response(data)

            if not response_list:
                break

            yield response_list

            pages_yielded += 1

            paging = self._extract_paging(data)
            if paging is None or current_page >= paging.get("pages", 1):
                break
            current_page += 1

    async def request_all_pages(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        max_pages: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        supports_pagination: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch all pages and return a single combined list."""
        results: list[dict[str, Any]] = []
        async for page in self.get_paginated(
            endpoint,
            params=params,
            max_pages=max_pages,
            page_size=page_size,
            supports_pagination=supports_pagination,
        ):
            results.extend(page)
        return results

    # ── response parsing ────────────────────────────────────────────── #
    def _unwrap_response(self, data: Any) -> list[dict[str, Any]]:
        """Extract the ``response`` list from the API-Football envelope.

        Raises ProviderValidationError if the structure is malformed.
        """
        if not isinstance(data, dict):
            raise ProviderValidationError(
                f"Unexpected response type from {self.provider_name}: {type(data).__name__}"
            )
        if data.get("errors"):
            errors = data["errors"]
            message = (
                str(errors) if not isinstance(errors, list) else "; ".join(str(e) for e in errors)
            )
            if "token" in message.lower() or "authorization" in message.lower():
                raise ProviderAuthenticationError(
                    f"{self.provider_name} API error: {message}",
                    details={"errors": errors},
                )
            raise ProviderUnavailableError(
                f"{self.provider_name} API error: {message}",
                details={"errors": errors},
            )
        response = data.get("response")
        if response is None:
            return []
        if not isinstance(response, list):
            return [response]
        return response

    def _extract_paging(self, data: Any) -> dict[str, Any] | None:
        """Extract paging info from API-Football response."""
        if not isinstance(data, dict):
            return None
        # API-Football uses "paging" key
        paging = data.get("paging")
        if isinstance(paging, dict):
            return paging
        # Some responses use "pagging" as a flag
        if data.get("pagging") is True:
            return {"page": 1, "pages": 2}
        return None

    # ── health check ────────────────────────────────────────────────── #
    async def health_check(self) -> dict[str, Any]:
        """Make a minimal request to verify credentials and connectivity.

        Returns a dict with health metrics.
        """
        try:
            start = datetime.utcnow()
            await self._http.get("/leagues", params={"id": "39"})
            duration_ms = (datetime.utcnow() - start).total_seconds() * 1000
            metrics = self._http.get_metrics()
            return {
                "healthy": True,
                "response_time_ms": round(duration_ms, 2),
                "timestamp": datetime.utcnow().isoformat(),
                **metrics,
            }
        except Exception as exc:
            return {
                "healthy": False,
                "error": str(exc),
                "timestamp": datetime.utcnow().isoformat(),
                **self._http.get_metrics(),
            }

    # ── request helpers with automatic pagination ───────────────────── #
    async def get_timezones(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request("GET", "/timezone", params=params or {})

    async def get_countries(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request("GET", "/countries", params=params or {})

    async def get_leagues(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request("GET", "/leagues", params=params or {})

    async def get_league(self, league_id: str) -> list[dict[str, Any]]:
        return await self.request("GET", "/leagues", params={"id": league_id})

    async def get_seasons(self, league_id: str | None = None) -> list[dict[str, Any]]:
        params = {"id": league_id} if league_id else {}
        return await self.request("GET", "/leagues/seasons", params=params)

    async def get_teams(
        self, league_id: str | None = None, season_id: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if league_id:
            params["league"] = league_id
        if season_id:
            params["season"] = season_id
        if not params:
            return await self.request_all_pages("/teams", params={}, supports_pagination=False)
        return await self.request_all_pages("/teams", params=params, supports_pagination=False)

    async def get_team(self, team_id: str) -> list[dict[str, Any]]:
        return await self.request("GET", "/teams", params={"id": team_id})

    async def get_fixtures(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/fixtures", params=params or {}, supports_pagination=False
        )

    async def get_fixture(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request("GET", "/fixtures", params={"id": fixture_id})

    async def get_standings(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request("GET", "/standings", params=params or {})

    async def get_injuries(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/injuries", params=params or {})

    async def get_lineups(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request("GET", "/fixtures/lineups", params={"fixture": fixture_id})

    async def get_match_statistics(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request("GET", "/fixtures/statistics", params={"fixture": fixture_id})

    async def get_head_to_head(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/fixtures/headtoh2h" if False else "/fixtures/headtoh2h", params=params
        )

    async def get_odds(
        self, fixture_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged = {"fixture": fixture_id, **(params or {})}
        return await self.request_all_pages("/odds", params=merged)

    async def get_venues(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/venues", params=params or {}, supports_pagination=False
        )

    async def get_coaches(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/coaches", params=params or {}, supports_pagination=False
        )

    async def get_transfers(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/transfers", params=params or {}, supports_pagination=False
        )

    async def get_trophies(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/trophies", params=params or {}, supports_pagination=False
        )

    async def get_players(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/players", params=params or {}, supports_pagination=False
        )

    async def get_predictions(
        self, fixture_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged = {"fixture": fixture_id, **(params or {})}
        return await self.request("GET", "/predictions", params=merged)

    async def get_sidelined(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/sidelined", params=params or {}, supports_pagination=False
        )

    async def get_odds_live(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/odds/live", params=params or {})

    async def get_odds_pre_match(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/odds/pre-match", params=params or {})
