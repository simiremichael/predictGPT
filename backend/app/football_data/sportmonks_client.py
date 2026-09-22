"""Dedicated Sportmonks HTTP client.

This client is responsible only for communication with the Sportmonks v3
football REST API.  It extends the shared ``FootballHTTPClient`` with
Sportmonks-specific concerns:

    * Authentication via Bearer token header
    * Pagination handling (Sportmonks returns ``data`` plus meta pagination info)
    * Response wrapper validation (``data``, ``meta``, ``pagination``)
    * Rate-limit header tracking (``X-RateLimit-Remaining`` etc.)

No prediction or normalization logic lives here; that belongs in the
provider and prediction layers respectively.
"""

from __future__ import annotations

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


class SportmonksClient:
    """Dedicated client for Sportmonks v3 football API communication."""

    provider_name = "sportmonks"

    # Sportmonks default pagination is 30, max is 200 for most endpoints.
    DEFAULT_PAGE_SIZE = 30
    MAX_PAGES = 50

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
        *,
        enabled: bool = True,
    ) -> None:
        settings = get_settings()
        self.api_token = api_token or settings.sportmonks_api_token
        if not self.api_token:
            raise ProviderConfigurationError(
                "SPORTMONKS_API_TOKEN is required for SportmonksClient."
            )
        self.base_url = base_url or settings.sportmonks_base_url

        provider_settings = ProviderSettings(
            key=self.api_token,
            base_url=self.base_url,
            enabled=enabled,
            rate_limit_per_minute=settings.sportmonks_rate_limit,
            timeout_seconds=settings.football_api_total_timeout,
        )
        self._http = FootballHTTPClient(
            provider_settings,
            self.provider_name,
            connect_timeout=settings.football_api_connect_timeout,
            read_timeout=settings.football_api_read_timeout,
            total_timeout=settings.football_api_total_timeout,
            auth_header_name="Authorization",
            auth_header_prefix="Bearer ",
        )

    # ── lifecycle ───────────────────────────────────────────────────── #
    @property
    def http(self) -> FootballHTTPClient:
        return self._http

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> SportmonksClient:
        await self._http._ensure_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # ── response parsing ────────────────────────────────────────────── #
    def _unwrap_response(self, data: Any) -> Any:
        """Extract the ``data`` payload from the Sportmonks envelope.

        Sportmonks responses look like:
            {"data": [...], "meta": {...}, "pagination": {...}}

        For single-resource responses, ``data`` is a dict.  Returns the raw
        data payload.  Raises ProviderValidationError if the structure is malformed.
        """
        if not isinstance(data, dict):
            raise ProviderValidationError(
                f"Unexpected response type from {self.provider_name}: {type(data).__name__}"
            )
        if data.get("errors") or (
            data.get("meta", {}).get("error_code") if isinstance(data.get("meta"), dict) else None
        ):
            errors = data.get("errors", data.get("meta", {}))
            message = (
                str(errors) if not isinstance(errors, list) else "; ".join(str(e) for e in errors)
            )
            if (
                "token" in message.lower()
                or "authorization" in message.lower()
                or "unauthorized" in message.lower()
            ):
                raise ProviderAuthenticationError(
                    f"{self.provider_name} API error: {message}",
                    details={"errors": errors},
                )
            raise ProviderUnavailableError(
                f"{self.provider_name} API error: {message}",
                details={"errors": errors},
            )
        return data.get("data")

    def _extract_pagination(self, data: Any) -> dict[str, Any] | None:
        """Extract pagination info from Sportmonks response."""
        if not isinstance(data, dict):
            return None
        pagination = data.get("pagination")
        if isinstance(pagination, dict):
            return pagination
        meta = data.get("meta")
        if isinstance(meta, dict) and "pagination" in meta:
            return meta.get("pagination")
        return None

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

        Returns the ``data`` payload from the Sportmonks envelope.
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
    ) -> AsyncIterator[Any]:
        """Yield each page's ``data`` payload, following Sportmonks pagination.

        Sportmonks responses include a ``pagination`` object:
            {
                "data": [...],
                "pagination": {
                    "current_page": 1,
                    "next_page": 2,
                    "prev_page": 1,
                    "from": 1,
                    "to": 30,
                    "per_page": 30,
                    "path": "...",
                    "total": 352
                }
            }

        Yields the ``data`` payload for each page.  Stops when:
            * No more pages (pagination.next_page is empty)
            * ``max_pages`` reached
            * Response is empty
        """
        if max_pages is None:
            max_pages = self.MAX_PAGES
        elif max_pages > self.MAX_PAGES:
            max_pages = self.MAX_PAGES

        merged_params: dict[str, Any] = {**(params or {})}
        merged_params.setdefault("page", 1)
        merged_params.setdefault("per_page", page_size)

        current_page = 1
        pages_yielded = 0

        while pages_yielded < max_pages:
            merged_params["page"] = current_page
            data = await self._http.request("GET", endpoint, params=merged_params)
            result = self._unwrap_response(data)

            if not result:
                break

            yield result

            pages_yielded += 1

            # Check if there are more pages
            pagination = self._extract_pagination(data)
            if pagination is None:
                break
            next_page = pagination.get("next_page")
            if not next_page:
                break
            current_page = next_page

    async def request_all_pages(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        max_pages: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[Any]:
        """Fetch all pages and return a single combined list."""
        results: list[Any] = []
        async for page in self.get_paginated(
            endpoint, params=params, max_pages=max_pages, page_size=page_size
        ):
            if isinstance(page, list):
                results.extend(page)
            else:
                results.append(page)
        return results

    # ── health check ────────────────────────────────────────────────── #
    async def health_check(self) -> dict[str, Any]:
        """Make a minimal request to verify credentials and connectivity.

        Returns a dict with health metrics.
        """
        try:
            start = datetime.utcnow()
            await self._http.get("/leagues")
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
    async def get_leagues(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/leagues", params=params or {})

    async def get_league(self, league_id: str) -> Any:
        return await self.request("GET", f"/leagues/{league_id}")

    async def get_seasons(
        self, league_id: str | None = None, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        if league_id:
            merged["league_id"] = league_id
        return await self.request_all_pages("/seasons", params=merged)

    async def get_teams(
        self,
        league_id: str | None = None,
        season_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        if league_id:
            merged["league_id"] = league_id
        if season_id:
            merged["season_id"] = season_id
        return await self.request_all_pages("/teams", params=merged)

    async def get_team(self, team_id: str) -> Any:
        return await self.request("GET", f"/teams/{team_id}")

    async def get_fixtures(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/fixtures", params=params or {})

    async def get_fixture(self, fixture_id: str) -> Any:
        return await self.request("GET", f"/fixtures/{fixture_id}")

    async def get_standings(
        self,
        league_id: str | None = None,
        season_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        if league_id:
            merged["league_id"] = league_id
        if season_id:
            merged["season_id"] = season_id
        return await self.request_all_pages("/standings", params=merged)

    async def get_predictions(self, fixture_id: str) -> Any:
        return await self.request("GET", f"/fixtures/{fixture_id}/predictions")

    async def get_timezones(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/timezones", params=params or {})

    async def get_countries(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/countries", params=params or {})

    async def get_venues(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/venues", params=params or {})

    async def get_coaches(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/coaches", params=params or {})

    async def get_transfers(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/transfers", params=params or {})

    async def get_trophies(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/trophies", params=params or {})

    async def get_players(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/players", params=params or {})

    async def get_player(self, player_id: str) -> Any:
        return await self.request("GET", f"/players/{player_id}")

    async def get_lineups(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/fixtures/{fixture_id}/lineups")

    async def get_match_statistics(self, fixture_id: str) -> Any:
        return await self.request("GET", f"/fixtures/{fixture_id}/statistics")

    async def get_injuries(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/injuries", params=params or {})

    async def get_sidelined(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/sidelined", params=params or {})

    async def get_odds(
        self, fixture_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = {"fixture_id": fixture_id, **(params or {})}
        return await self.request_all_pages("/odds/pre-match", params=merged)

    async def get_odds_live(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/odds/live", params=params or {})

    async def get_odds_pre_match(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/odds/pre-match", params=params or {})

    async def get_head_to_head(self, team_id: str, vs_team_id: str) -> list[dict[str, Any]]:
        params = {"team_id": team_id, "vs_team_id": vs_team_id}
        return await self.request_all_pages("/head-to-head", params=params)

    async def get_team_statistics(
        self, team_id: str, season_id: str | None = None, params: dict[str, Any] | None = None
    ) -> Any:
        merged: dict[str, Any] = params or {}
        if season_id:
            merged["season_id"] = season_id
        return await self.request("GET", f"/teams/{team_id}/stats", params=merged)
