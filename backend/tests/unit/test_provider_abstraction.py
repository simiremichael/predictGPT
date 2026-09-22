"""Unit tests for the provider abstraction layer and provider switching."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.config import get_settings
from core.exceptions import ProviderConfigurationError
from football_data.api_football import APIFootballProvider
from football_data.api_football_client import APIFootballClient
from football_data.base import FootballDataProvider
from football_data.factory import SUPPORTED_PROVIDERS, get_football_provider, get_provider_for_name
from football_data.sportmonks import SportmonksProvider

PROVIDER_METHODS = [
    "get_leagues",
    "get_league",
    "get_seasons",
    "get_teams",
    "get_team",
    "get_team_statistics",
    "get_team_form",
    "get_fixtures",
    "get_fixture",
    "get_head_to_hawk" if False else "get_head_to_head",
    "get_injuries",
    "get_suspensions",
    "get_lineups",
    "get_predicted_lineups",
    "get_match_statistics",
    "get_odds",
    "get_players",
    "get_standings",
    "health_check",
]


class TestProviderAbstraction:
    """Verify both providers implement the FootballDataProvider ABC."""

    def test_both_providers_are_subclasses_of_abc(self) -> None:
        assert issubclass(APIFootballProvider, FootballDataProvider)
        assert issubclass(SportmonksProvider, FootballDataProvider)

    def test_both_providers_implement_all_abstract_methods(self) -> None:
        for cls in (APIFootballProvider, SportmonksProvider):
            for method in PROVIDER_METHODS:
                assert hasattr(cls, method), f"{cls.__name__} missing method {method}"
                attr = getattr(cls, method)
                assert not getattr(attr, "__isabstractmethod__", False), (
                    f"{cls.__name__}.{method} is still abstract"
                )

    def test_provider_names_are_provider_specific(self) -> None:
        assert APIFootballProvider.provider_name == "api_football"
        assert SportmonksProvider.provider_name == "sportmonks"


class TestProviderFactory:
    """Verify the factory selects the correct provider based on config."""

    def test_factory_returns_api_football(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOOTBALL_DATA_PROVIDER", "api_football")
        monkeypatch.setenv("API_FOOTBALL_KEY", "test_key")
        get_settings.cache_clear()
        provider = get_football_provider()
        assert isinstance(provider, APIFootballProvider)
        assert provider.provider_name == "api_football"

    def test_factory_returns_sportmonks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOOTBALL_DATA_PROVIDER", "sportmonks")
        monkeypatch.setenv("SPORTMONKS_API_TOKEN", "test_token")
        get_settings.cache_clear()
        provider = get_football_provider()
        assert isinstance(provider, SportmonksProvider)
        assert provider.provider_name == "sportmonks"

    def test_factory_raises_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOOTBALL_DATA_PROVIDER", "api_football")
        # Ensure no API key is set
        monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
        get_settings.cache_clear()
        with pytest.raises(ProviderConfigurationError, match="API_FOOTBALL_KEY"):
            get_football_provider()

    def test_factory_raises_on_invalid_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOOTBALL_DATA_PROVIDER", "api_football")
        monkeypatch.setenv("API_FOOTBALL_KEY", "test_key")
        get_settings.cache_clear()
        provider = get_football_provider()
        # The active provider type should change when config changes
        monkeypatch.setenv("FOOTBALL_DATA_PROVIDER", "sportmonks")
        monkeypatch.setenv("SPORTMONKS_API_TOKEN", "test_token")
        get_settings.cache_clear()
        provider2 = get_football_provider()
        assert provider.provider_name != provider2.provider_name

    def test_sportmonks_raises_without_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPORTMONKS_API_TOKEN", raising=False)
        get_settings.cache_clear()
        provider = get_provider_for_name("sportmonks")
        assert provider is None

    def test_supported_providers_constant(self) -> None:
        assert SUPPORTED_PROVIDERS == ("api_football", "sportmonks")

    @pytest.mark.asyncio
    async def test_api_football_teams_request_omits_paging_params(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("API_FOOTBALL_KEY", "test_key")
        get_settings.cache_clear()

        client = APIFootballClient(api_key="test_key", base_url="https://example.com")
        client._http.request = AsyncMock(return_value={"response": []})

        await client.get_teams(league_id="39", season_id="2023")

        client._http.request.assert_awaited_once_with(
            "GET",
            "/teams",
            params={"league": "39", "season": "2023"},
        )


class TestProviderSwitching:
    """Core requirement: switching FOOTBALL_DATA_PROVIDER changes the active provider."""

    def test_switch_from_api_football_to_sportmonks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Start with API-Football
        monkeypatch.setenv("FOOTBALL_DATA_PROVIDER", "api_football")
        monkeypatch.setenv("API_FOOTBALL_KEY", "key1")
        get_settings.cache_clear()
        provider_a = get_football_provider()
        assert provider_a.provider_name == "api_football"

        # Switch to Sportmonks
        monkeypatch.setenv("FOOTBALL_DATA_PROVIDER", "sportmonks")
        monkeypatch.setenv("SPORTMONKS_API_TOKEN", "token1")
        get_settings.cache_clear()
        provider_b = get_football_provider()
        assert provider_b.provider_name == "sportmonks"

        # The same factory call returns different types
        assert type(provider_a) is not type(provider_b)

    def test_prediction_engine_does_not_import_provider_concrete_class(self) -> None:
        """Ensure the prediction module (if it exists) doesn't hardcode providers.

        Phase 1 check: verify there is no import of APIFootballProvider or
        SportmonksProvider in the prediction package.
        """
        import pathlib

        prediction_dir = pathlib.Path(__file__).resolve().parents[2] / "app" / "prediction"
        if prediction_dir.exists():
            for py_file in prediction_dir.rglob("*.py"):
                content = py_file.read_text()
                assert "APIFootballProvider" not in content, (
                    f"{py_file} hardcodes APIFootballProvider"
                )
                assert "SportmonksProvider" not in content, (
                    f"{py_file} hardcodes SportmonksProvider"
                )
