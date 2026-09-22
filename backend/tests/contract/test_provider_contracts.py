"""Contract tests: both providers must produce compatible normalized data.

These tests verify that each provider implementation correctly maps its
provider-specific response format into the normalized internal models,
ensuring that the prediction engine receives consistent data regardless
of which provider is active.

Mocked HTTP responses are used so no network access is required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from football_data.api_football import APIFootballProvider
from football_data.base import FootballDataProvider
from football_data.models import (
    FixtureStatus,
    InjurySeverity,
    LineupStatus,
    NormalizedFixture,
    NormalizedInjury,
    NormalizedLeague,
    NormalizedLineup,
    NormalizedTeam,
)
from football_data.sportmonks import SportmonksProvider
from tests.conftest import (
    MOCK_API_FOOTBALL_FIXTURE,
    MOCK_API_FOOTBALL_INJURY,
    MOCK_API_FOOTBALL_LEAGUE,
    MOCK_API_FOOTBALL_LINEUP,
    MOCK_API_FOOTBALL_TEAM,
    MOCK_SPORTMONKS_FIXTURE,
    MOCK_SPORTMONKS_INJURY,
    MOCK_SPORTMONKS_LEAGUE,
    MOCK_SPORTMONKS_TEAM,
)


def _make_provider(provider_cls: type, **kwargs: str) -> FootballDataProvider:
    if provider_cls.__name__ == "APIFootballProvider":
        return provider_cls(api_key=kwargs.get("api_key", "test"), base_url=kwargs.get("base_url", "http://test"))
    return provider_cls(api_token=kwargs.get("api_token", "test"), base_url=kwargs.get("base_url", "http://test"))


def _patch_http_get(provider: FootballDataProvider, return_value: dict) -> patch:
    mock = _AsyncGetMock(return_value)
    if hasattr(provider, "_client"):
        # APIFootballProvider stores client in self._client
        return patch.object(provider, "_client", mock)
    # SportmonksProvider stores client in self.http
    return patch.object(provider, "http", mock)


class _AsyncGetMock:
    """Minimal mock for APIFootballClient / SportmonksClient that returns a fixed dict."""

    def __init__(self, return_value: dict) -> None:
        self._return_value = return_value
        self._client = MagicMock()
        self.http = self  # expose underlying http client for connect() callers

    async def request(self, method: str, endpoint: str, **kwargs) -> dict:
        return self._return_value

    async def get(self, path: str, *, params: dict | None = None, **kwargs) -> dict:
        return self._return_value

    async def get_raw(self, path: str, *, params: dict | None = None, **kwargs) -> list:
        return self._return_value

    async def request_all_pages(self, endpoint: str, **kwargs) -> list:
        # Return the "response" or "data" list from the mock envelope
        data = self._return_value
        if isinstance(data, dict):
            return data.get("response", data.get("data", []))
        return data if isinstance(data, list) else [data]

    async def _ensure_client(self):
        return self._client

    async def aclose(self) -> None:
        pass

    def _build_default_headers(self) -> dict:
        return {}

    def _auth_header(self) -> dict:
        return {}

    def get_metrics(self) -> dict:
        return {}

    # API-Football typed helpers
    async def get_leagues(self, params: dict | None = None) -> list:
        return self._unwrap_list()

    async def get_league(self, league_id: str) -> list:
        return self._unwrap_list()

    async def get_teams(self, league_id: str | None = None, season_id: str | None = None) -> list:
        return self._unwrap_list()

    async def get_team(self, team_id: str) -> list:
        return self._unwrap_list()

    async def get_fixtures(self, params: dict | None = None) -> list:
        return self._unwrap_list()

    async def get_fixture(self, fixture_id: str) -> list:
        return self._unwrap_list()

    async def get_standings(self, params: dict | None = None) -> list:
        return self._unwrap_list()

    async def get_injuries(self, params: dict | None = None) -> list:
        return self._unwrap_list()

    async def get_lineups(self, fixture_id: str) -> list:
        return self._unwrap_list()

    async def get_match_statistics(self, fixture_id: str) -> list:
        return self._unwrap_list()

    async def get_head_to_hhead(self, team_a: str, team_b: str) -> list:
        return self._unwrap_list()

    async def get_odds(self, fixture_id: str, params: dict | None = None) -> list:
        return self._unwrap_list()

    async def get_players(self, params: dict | None = None) -> list:
        return self._unwrap_list()

    async def get_sidelined(self, params: dict | None = None) -> list:
        return self._unwrap_list()

    async def get_seasons(self, league_id: str | None = None) -> list:
        return self._unwrap_list()

    # Sportmonks typed helpers

    def _unwrap_list(self) -> list:
        data = self._return_value
        if isinstance(data, dict):
            return data.get("response", data.get("data", []))
        return data if isinstance(data, list) else [data]

    def _unwrap_single(self):
        data = self._return_value
        if isinstance(data, dict):
            inner = data.get("response", data.get("data"))
            if isinstance(inner, list):
                return inner[0] if inner else None
            return inner
        return data


# ── Shared contract: get_league ───────────────────────────────────────────
class TestContractLeague:
    @pytest.mark.asyncio
    async def test_api_football_get_league(self) -> None:
        provider = APIFootballProvider(api_key="k", base_url="http://t")
        provider._client = _AsyncGetMock({"response": [MOCK_API_FOOTBALL_LEAGUE]})
        league = await provider.get_league("39")
        assert league is not None
        assert league.provider == "api_football"
        assert league.provider_league_id == "39"
        assert league.name == "Premier League"
        assert league.country == "England"

    @pytest.mark.asyncio
    async def test_sportmonks_get_league(self) -> None:
        provider = SportmonksProvider(api_token="t", base_url="http://t")
        provider.http = _AsyncGetMock({"data": MOCK_SPORTMONKS_LEAGUE})
        league = await provider.get_league("39")
        assert league is not None
        assert league.provider == "sportmonks"
        assert league.provider_league_id == "39"
        assert league.name == "Premier League"
        assert league.country == "England"


# ── Shared contract: get_team ─────────────────────────────────────────────
class TestContractTeam:
    @pytest.mark.asyncio
    async def test_api_football_get_team(self) -> None:
        provider = APIFootballProvider(api_key="k", base_url="http://t")
        provider._client = _AsyncGetMock({"response": [MOCK_API_FOOTBALL_TEAM]})
        team = await provider.get_team("42")
        assert team is not None
        assert team.provider == "api_football"
        assert team.provider_team_id == "42"
        assert team.name == "Arsenal"

    @pytest.mark.asyncio
    async def test_sportmonks_get_team(self) -> None:
        provider = SportmonksProvider(api_token="t", base_url="http://t")
        provider.http = _AsyncGetMock({"data": MOCK_SPORTMONKS_TEAM})
        team = await provider.get_team("42")
        assert team is not None
        assert team.provider == "sportmonks"
        assert team.provider_team_id == "42"
        assert team.name == "Arsenal"


# ── Shared contract: get_fixture ──────────────────────────────────────────
class TestContractFixture:
    @pytest.mark.asyncio
    async def test_api_football_get_fixture(self) -> None:
        provider = APIFootballProvider(api_key="k", base_url="http://t")
        provider._client = _AsyncGetMock({"response": [MOCK_API_FOOTBALL_FIXTURE]})
        fixture = await provider.get_fixture("12345")
        assert fixture is not None
        assert fixture.provider == "api_football"
        assert fixture.provider_fixture_id == "12345"
        assert fixture.home_team_name == "Arsenal"
        assert fixture.away_team_name == "Manchester City"
        assert fixture.status == FixtureStatus.SUSPENDED
        assert fixture.home_score is None
        assert fixture.away_score is None

    @pytest.mark.asyncio
    async def test_sportmonks_get_fixture(self) -> None:
        provider = SportmonksProvider(api_token="t", base_url="http://t")
        provider.http = _AsyncGetMock({"data": MOCK_SPORTMONKS_FIXTURE})
        fixture = await provider.get_fixture("12345")
        assert fixture is not None
        assert fixture.provider == "sportmonks"
        assert fixture.provider_fixture_id == "12345"
        assert fixture.home_team_name == "Arsenal"
        assert fixture.away_team_name == "Manchester City"
        assert fixture.status == FixtureStatus.SCHEDULED
        assert fixture.home_score is None
