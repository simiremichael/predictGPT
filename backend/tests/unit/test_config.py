"""Unit tests for configuration and provider configuration."""
from __future__ import annotations

import pytest

from core.config import Settings, get_settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.app_env == "development"
    assert settings.football_data_provider == "api_football"
    assert settings.debug is False
    assert "postgresql" in settings.database_url
    assert "redis" in settings.redis_url


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOOTBALL_DATA_PROVIDER", "sportmonks")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/5")
    monkeypatch.setenv("API_FOOTBALL_KEY", "my_api_key")
    monkeypatch.setenv("SPORTMONKS_API_TOKEN", "my_sportmonks_token")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.football_data_provider == "sportmonks"
    assert settings.api_football_key == "my_api_key"
    assert settings.sportmonks_api_token == "my_sportmonks_token"
    assert "test_db" in settings.database_url
    assert "6379/5" in settings.redis_url


def test_invalid_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOOTBALL_DATA_PROVIDER", "invalid_provider")
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        Settings()


def test_api_football_settings_property() -> None:
    settings = Settings()
    provider_settings = settings.api_football_settings
    assert provider_settings.enabled is False
    assert provider_settings.timeout_seconds == 30


def test_provider_settings_reflects_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_FOOTBALL_KEY", "test_key")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.api_football_settings.enabled is True
    assert settings.api_football_settings.key == "test_key"


def test_sportmonks_settings_reflects_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPORTMONKS_API_TOKEN", "test_token")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.sportmonks_settings.enabled is True
    assert settings.sportmonks_settings.key == "test_token"
