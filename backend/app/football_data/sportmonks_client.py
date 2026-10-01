"""Dedicated Sportmonks HTTP client.

This client is responsible only for communication with the Sportmonks v3
football REST API.  It extends the shared ``FootballHTTPClient`` with
Sportmonks-specific concerns:

    * Authentication via ``api_token`` query parameter
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
from urllib.parse import parse_qs, urlparse

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

    # Side-loaded relations requested on league lookups.
    DEFAULT_LEAGUE_INCLUDES: tuple[str, ...] = (
        "sport",
        "country",
        "currentSeason",
        "seasons",
    )
    DETAILED_LEAGUE_INCLUDES: tuple[str, ...] = (
        "sport",
        "country",
        "stages",
        "currentSeason",
        "seasons",
    )

    # "latest",
    # "upcoming",
    # "stages"
    # "inplay",
    # "today",

    # Side-loaded relations requested on team lookups.  ``players.player`` is a
    # nested include and must be requested on its own: sending bare ``players``
    # alongside it returns the squad without the nested player objects.
    DEFAULT_TEAM_INCLUDES: tuple[str, ...] = (
        "sport",
        "country",
        "venue",
        "coaches",
        "rivals",
        "players.player",
        "latest",
        "upcoming",
        "seasons",
        "activeSeasons",
        "sidelined",
        "sidelinedHistory",
        "statistics",
        "trophies",
        "socials",
        "rankings",
    )

    @classmethod
    def _normalize_includes(cls, includes: Any) -> list[str]:
        """Normalize an include selection into a list of include names.

        Sportmonks treats ``include=a,b`` as a single include literally named
        ``"a,b"`` and rejects it with response code 5001.  Multiple relations
        must therefore be sent as repeated ``include`` query parameters, which
        this list is built for.

        ``None`` means "no include relations", so only endpoints that opt in
        (see :meth:`get_leagues`) request side-loads.
        """
        if includes is None:
            return []
        if isinstance(includes, str):
            candidates: list[Any] = includes.split(",")
        else:
            candidates = list(includes)
        names: list[str] = []
        for candidate in candidates:
            name = str(candidate).strip()
            if name and name not in names:
                names.append(name)
        return names

    def _build_params(
        self,
        params: dict[str, Any] | None = None,
        includes: Any = None,
    ) -> list[tuple[str, str]]:
        """Build a query-param list, repeating ``include`` for each relation."""
        pairs: list[tuple[str, str]] = [("api_token", self.api_token)]
        explicit_include = (params or {}).get("include")
        for key, value in (params or {}).items():
            if key == "include" or value is None:
                continue
            pairs.append((str(key), str(value)))
        if explicit_include is not None:
            for name in self._normalize_includes(explicit_include):
                pairs.append(("include", name))
        elif includes is not None:
            for name in self._normalize_includes(includes):
                pairs.append(("include", name))
        return pairs

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
        includes: Any = None,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> Any:
        """Make a single (non-paginated) API request.

        Returns the ``data`` payload from the Sportmonks envelope.
        """
        data = await self._http.request(
            method,
            endpoint,
            params=self._build_params(params, includes),
            max_retries=max_retries,
            **kwargs,
        )
        return self._unwrap_response(data)

    async def get_paginated(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        includes: Any = None,
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

        merged_params: dict[str, Any] = dict(params or {})
        merged_params.setdefault("page", 1)
        merged_params.setdefault("per_page", page_size)

        current_page = 1
        pages_yielded = 0

        while pages_yielded < max_pages:
            merged_params["page"] = current_page
            data = await self._http.request(
                "GET", endpoint, params=self._build_params(merged_params, includes)
            )
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
            if isinstance(next_page, int):
                current_page = next_page
            else:
                parsed = urlparse(next_page)
                qs = parse_qs(parsed.query)
                page_values = qs.get("page")
                if not page_values:
                    break
                try:
                    current_page = int(page_values[0])
                except (TypeError, ValueError):
                    break

    async def request_all_pages(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        includes: Any = None,
        max_pages: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[Any]:
        """Fetch all pages and return a single combined list."""
        results: list[Any] = []
        async for page in self.get_paginated(
            endpoint,
            params=params,
            includes=includes,
            max_pages=max_pages,
            page_size=page_size,
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
            await self._http.get("/leagues", params={"api_token": self.api_token, "per_page": 1})
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
    async def get_leagues(
        self,
        params: dict[str, Any] | None = None,
        includes: Any = None,
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/leagues",
            params=params,
            includes=self.DEFAULT_LEAGUE_INCLUDES if includes is None else includes,
        )

    async def get_league(self, league_id: str, includes: Any = None) -> Any:
        return await self.request(
            "GET",
            f"/leagues/{league_id}",
            includes=self.DETAILED_LEAGUE_INCLUDES if includes is None else includes,
        )

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
        includes: Any = None,
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        if league_id:
            merged["league_id"] = league_id
        if season_id:
            merged["season_id"] = season_id
        return await self.request_all_pages(
            "/teams",
            params=merged,
            includes=self.DEFAULT_TEAM_INCLUDES if includes is None else includes,
        )

    async def get_team(self, team_id: str, includes: Any = None) -> Any:
        return await self.request(
            "GET",
            f"/teams/{team_id}",
            includes=self.DEFAULT_TEAM_INCLUDES if includes is None else includes,
        )

    # ── Team squads ───────────────────────────────────────────────────── #
    async def get_team_squad(self, team_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/teams/{team_id}/squad")

    async def get_extended_team_squad(self, team_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/teams/{team_id}/squad/extended")

    async def get_team_squad_by_team_and_season(
        self, team_id: str, season_id: str
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            f"/teams/{team_id}/squad", params={"season_id": season_id}
        )

    async def get_fixtures(
        self,
        params: dict[str, Any] | None = None,
        includes: Any = None,
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/fixtures", params=params or {}, includes=includes)

    async def get_fixture(self, fixture_id: str, includes: Any = None) -> Any:
        return await self.request(
            "GET",
            f"/fixtures/{fixture_id}",
            includes=includes,
        )

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

    async def get_standings_by_season_id(self, season_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/standings/seasons/{season_id}")

    async def get_standings_by_round_id(self, round_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/standings/rounds/{round_id}")

    async def get_standing_corrections_by_season_id(self, season_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/standings/seasons/{season_id}/corrections")

    async def get_live_standings_by_league_id(self, league_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/standings/live", params={"league_id": league_id})

    async def get_grouped_standings_by_round_id(self, round_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/standings/grouped/rounds/{round_id}")

    # ── Topscorers ───────────────────────────────────────────────────── #
    async def get_topscorers_by_season_id(self, season_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/topscorers/seasons/{season_id}")

    async def get_topscorers_by_stage_id(self, stage_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/topscorers/stages/{stage_id}")

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

    async def get_players_by_country_id(self, country_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages("/players", params={"country_id": country_id})

    async def search_players(self, query: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/players/search/{query}")

    async def get_last_updated_players(self) -> list[dict[str, Any]]:
        return await self.request_all_pages("/players/last-updated")

    # ── Match facts ───────────────────────────────────────────────────── #
    async def get_match_facts(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/match-facts", params=params or {})

    async def get_match_facts_by_fixture_id(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/match-facts/fixtures/{fixture_id}")

    async def get_match_facts_by_date_range(
        self, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/match-facts", params={"from": from_date, "to": to_date}
        )

    async def get_match_facts_by_league_id(
        self, league_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        return await self.request_all_pages(
            "/match-facts", params={"league_id": league_id, **merged}
        )

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

    async def get_odds_by_fixture_and_bookmaker(
        self, fixture_id: str, bookmaker_id: str
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/odds/pre-match",
            params={"fixture_id": fixture_id, "bookmaker_id": bookmaker_id},
        )

    async def get_odds_by_fixture_and_market(
        self, fixture_id: str, market_id: str
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/odds/pre-match",
            params={"fixture_id": fixture_id, "market_id": market_id},
        )

    async def get_last_updated_pre_match_odds(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/odds/pre-match/last-updated", params=params or {})

    async def get_live_odds_by_fixture_id(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages("/odds/live", params={"fixture_id": fixture_id})

    async def get_live_odds_by_fixture_and_market(
        self, fixture_id: str, market_id: str
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/odds/live", params={"fixture_id": fixture_id, "market_id": market_id}
        )

    async def get_last_updated_live_odds(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/odds/live/last-updated", params=params or {})

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

    # ── League endpoints ──────────────────────────────────────────────── #
    async def get_leagues_by_live(self) -> list[dict[str, Any]]:
        return await self.request_all_pages("/leagues/live")

    async def get_leagues_by_fixture_date(self, date: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/leagues/date/{date}")

    async def get_leagues_by_country_id(self, country_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/leagues/countries/{country_id}")

    async def search_leagues(self, query: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/leagues/search/{query}")

    async def get_all_leagues_by_team_id(self, team_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/leagues/team/{team_id}")

    async def get_current_leagues_by_team_id(self, team_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/leagues/team/{team_id}/current")

    # ── Season endpoints ──────────────────────────────────────────────── #
    async def get_season(self, season_id: str) -> Any:
        return await self.request("GET", f"/seasons/{season_id}")

    async def get_seasons_by_team_id(
        self, team_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/seasons/team/{team_id}", params=params or {})

    async def search_seasons(self, query: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/seasons/search/{query}")

    async def get_brackets_by_season_id(self, season_id: str) -> Any:
        return await self.request("GET", f"/seasons/{season_id}/brackets")

    async def get_season_statistics_by_participant(
        self, season_id: str, participant_id: str
    ) -> Any:
        return await self.request(
            "GET", f"/seasons/{season_id}/participants/{participant_id}/statistics"
        )

    # ── Stage endpoints ───────────────────────────────────────────────── #
    async def get_stages(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/stages", params=params or {})

    async def get_stage(self, stage_id: str) -> Any:
        return await self.request("GET", f"/stages/{stage_id}")

    async def get_stages_by_season_id(
        self, season_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/stages/seasons/{season_id}", params=params or {})

    async def search_stages(self, query: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/stages/search/{query}")

    async def get_stage_statistics(self, stage_id: str) -> Any:
        return await self.request("GET", f"/stages/{stage_id}/statistics")

    # ── Round endpoints ───────────────────────────────────────────────── #
    async def get_rounds(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/rounds", params=params or {})

    async def get_round(self, round_id: str) -> Any:
        return await self.request("GET", f"/rounds/{round_id}")

    async def get_rounds_by_season_id(
        self, season_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/rounds/seasons/{season_id}", params=params or {})

    async def search_rounds(self, query: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/rounds/search/{query}")

    async def get_round_statistics(self, round_id: str) -> Any:
        return await self.request("GET", f"/rounds/{round_id}/statistics")

    # ── Schedule endpoints ─────────────────────────────────────────────── #
    async def get_schedules_by_season_id(
        self, season_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/schedules/season/{season_id}", params=params or {})

    async def get_schedules_by_team_id(
        self, team_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/schedules/team/{team_id}", params=params or {})

    async def get_schedules_by_season_and_team(
        self, season_id: str, team_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        return await self.request_all_pages(
            f"/schedules/season/{season_id}/team/{team_id}", params=merged
        )

    # ── Team rankings (beta) ───────────────────────────────────────────── #
    async def get_team_rankings(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/team-rankings", params=params or {})

    async def get_team_rankings_by_team_id(self, team_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages("/team-rankings", params={"team_id": team_id})

    async def get_team_rankings_by_date(
        self, date: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        return await self.request_all_pages("/team-rankings", params={"date": date, **merged})

    # ── Expected (xG) ────────────────────────────────────────────────── #
    async def get_expected_by_team_id(
        self, team_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        return await self.request_all_pages("/expected", params={"team_id": team_id, **merged})

    async def get_expected_by_player_id(
        self, player_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        return await self.request_all_pages("/expected", params={"player_id": player_id, **merged})

    # ── Predictions ───────────────────────────────────────────────────── #
    async def get_probabilities(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/predictions/probabilities", params=params or {})

    async def get_probabilities_by_fixture_id(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/predictions/probabilities", params={"fixture_id": fixture_id}
        )

    async def get_predictability_by_league_id(
        self, league_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        return await self.request_all_pages(
            "/predictions/predictability", params={"league_id": league_id, **merged}
        )

    async def get_value_bets(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/predictions/value-bets", params=params or {})

    async def get_value_bets_by_fixture_id(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/predictions/value-bets", params={"fixture_id": fixture_id}
        )

    async def get_live_probabilities(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/predictions/live-probabilities", params=params or {})

    async def get_live_probabilities_by_fixture_id(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(
            "/predictions/live-probabilities", params={"fixture_id": fixture_id}
        )

    # ── Bookmakers ─────────────────────────────────────────────────────── #
    async def get_bookmakers(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/bookmakers", params=params or {})

    async def get_premium_bookmakers(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/bookmakers/premium", params=params or {})

    async def get_bookmaker(self, bookmaker_id: str) -> Any:
        return await self.request("GET", f"/bookmakers/{bookmaker_id}")

    async def search_bookmakers(self, query: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/bookmakers/search/{query}")

    async def get_bookmakers_by_fixture_id(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages("/bookmakers", params={"fixture_id": fixture_id})

    async def get_bookmaker_mappings_by_fixture_id(self, fixture_id: str) -> list[dict[str, Any]]:
        return await self.request_all_pages(f"/bookmakers/mappings/fixtures/{fixture_id}")

    # ── Livescores ─────────────────────────────────────────────────────── #
    async def get_inplay_livescores(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/livescores/inplay", params=params or {})

    async def get_all_livescores(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/livescores", params=params or {})

    async def get_latest_updated_livescores(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/livescores/latest-updated", params=params or {})

    async def get_fixtures_live(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/fixtures/live", params=params or {})

    # ── News ───────────────────────────────────────────────────────────── #
    async def get_pre_match_news(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/news/pre-match", params=params or {})

    async def get_pre_match_news_by_season_id(
        self, season_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        return await self.request_all_pages(
            "/news/pre-match", params={"season_id": season_id, **merged}
        )

    async def get_pre_match_news_for_upcoming_fixtures(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/news/pre-match/upcoming", params=params or {})

    async def get_post_match_news(
        self, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.request_all_pages("/news/post-match", params=params or {})

    async def get_post_match_news_by_season_id(
        self, season_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        return await self.request_all_pages(
            "/news/post-match", params={"season_id": season_id, **merged}
        )

    # ── Types ──────────────────────────────────────────────────────────── #
    async def get_types(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/types", params=params or {})

    async def get_type(self, type_id: str) -> Any:
        return await self.request("GET", f"/types/{type_id}")

    async def get_type_by_entity(
        self, entity_id: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        merged: dict[str, Any] = params or {}
        return await self.request_all_pages(f"/types/entity/{entity_id}", params=merged)

    # ── States ─────────────────────────────────────────────────────────── #
    async def get_states(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.request_all_pages("/states", params=params or {})

    async def get_state(self, state_id: str) -> Any:
        return await self.request("GET", f"/states/{state_id}")
