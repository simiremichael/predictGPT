from __future__ import annotations

from core.config import get_settings
from web_research import factory


def _set_provider_env(monkeypatch, **overrides) -> None:
    values = {
        "WEB_SEARCH_PROVIDER": "tavily",
        "TAVILY_API_KEY": "tavily-key",
        "BRAVE_API_KEY": "brave-key",
        "YOU_API_KEY": "you-key",
    }
    values.update(overrides)
    for key, value in values.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def test_default_chain_is_tavily_brave_then_youcom(monkeypatch) -> None:
    _set_provider_env(monkeypatch)

    provider = factory.get_search_provider()

    assert provider.provider_name == "tavily"
    assert provider._fallback_provider.provider_name == "brave"
    assert provider._fallback_provider._fallback_provider.provider_name == "youcom"


def test_missing_tavily_key_starts_with_brave(monkeypatch) -> None:
    _set_provider_env(monkeypatch, TAVILY_API_KEY=None)

    provider = factory.get_search_provider()

    assert provider.provider_name == "brave"
    assert provider._fallback_provider.provider_name == "youcom"


def test_missing_brave_key_falls_directly_to_youcom(monkeypatch) -> None:
    _set_provider_env(monkeypatch, BRAVE_API_KEY=None)

    provider = factory.get_search_provider()

    assert provider.provider_name == "tavily"
    assert provider._fallback_provider.provider_name == "youcom"
