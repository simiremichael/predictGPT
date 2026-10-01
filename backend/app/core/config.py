"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices as _AliasChoices
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AliasChoices = _AliasChoices


class ProviderSettings(BaseSettings):
    """Settings for a single football data provider."""

    model_config = SettingsConfigDict(extra="ignore")

    key: str | None = None
    base_url: str | None = None
    enabled: bool = False
    rate_limit_per_minute: int = Field(default=0)
    timeout_seconds: int = Field(default=30)


class Settings(BaseSettings):
    """Top-level application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    app_env: Literal["development", "staging", "production", "testing"] = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "app_env"),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL", "log_level"),
    )
    project_name: str = Field(
        default="Football AI",
        validation_alias=AliasChoices("PROJECT_NAME", "project_name"),
    )
    api_version: str = Field(
        default="v1",
        validation_alias=AliasChoices("API_VERSION", "api_version"),
    )
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("APP_DEBUG", "app_debug"),
    )

    # ------------------------------------------------------------------ #
    # Active data provider
    # ------------------------------------------------------------------ #
    football_data_provider: Literal["api_football", "sportmonks"] = "sportmonks"

    # Optional failover provider. Empty string means no failover.
    primary_football_provider: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PRIMARY_FOOTBALL_PROVIDER", "primary_football_provider"),
    )
    fallback_football_provider: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FALLBACK_FOOTBALL_PROVIDER", "fallback_football_provider"),
    )

    # ------------------------------------------------------------------ #
    # API-Football
    # ------------------------------------------------------------------ #
    api_football_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_FOOTBALL_KEY", "api_football_key"),
    )
    api_football_base_url: str = Field(
        default="https://api.sportmonks.com/v3/football",
        validation_alias=AliasChoices("API_FOOTBALL_BASE_URL", "api_football_base_url"),
    )
    api_football_rate_limit: int = Field(
        default=10,
        validation_alias=AliasChoices("API_FOOTBALL_RATE_LIMIT", "api_football_rate_limit"),
    )

    # ------------------------------------------------------------------ #
    # Timeouts (seconds)
    # ------------------------------------------------------------------ #
    football_api_connect_timeout: float = Field(
        default=10.0,
        validation_alias=AliasChoices(
            "FOOTBALL_API_CONNECT_TIMEOUT", "football_api_connect_timeout"
        ),
    )
    football_api_read_timeout: float = Field(
        default=30.0,
        validation_alias=AliasChoices("FOOTBALL_API_READ_TIMEOUT", "football_api_read_timeout"),
    )
    football_api_total_timeout: float = Field(
        default=60.0,
        validation_alias=AliasChoices("FOOTBALL_API_TOTAL_TIMEOUT", "football_api_total_timeout"),
    )

    # ------------------------------------------------------------------ #
    # Pagination / sync
    # ------------------------------------------------------------------ #
    sync_form_match_count: int = Field(
        default=10,
        validation_alias=AliasChoices("FORM_MATCH_COUNT", "sync_form_match_count"),
    )
    max_pagination_pages: int = Field(
        default=50,
        validation_alias=AliasChoices("MAX_PAGINATION_PAGES", "max_pagination_pages"),
        description="Safety cap to prevent runaway pagination.",
    )
    max_retries: int = Field(
        default=3,
        validation_alias=AliasChoices("MAX_RETRIES", "max_retries"),
    )

    # ------------------------------------------------------------------ #
    # Sportmonks
    # ------------------------------------------------------------------ #
    sportmonks_api_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SPORTMONKS_API_TOKEN", "sportmonks_api_token"),
    )
    sportmonks_base_url: str = Field(
        default="https://api.sportmonks.com/v3/football",
        validation_alias=AliasChoices("SPORTMONKS_BASE_URL", "sportmonks_base_url"),
    )
    sportmonks_rate_limit: int = Field(
        default=29,
        validation_alias=AliasChoices("SPORTMONKS_RATE_LIMIT", "sportmonks_rate_limit"),
    )

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    database_url: str = Field(
        default="postgresql+asyncpg://neondb_owner:npg_UlzWti9uqGm0@ep-square-grass-za4glnjc-pooler.c-2.eu-west-2.aws.neon.tech/neondb?ssl=require",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # ------------------------------------------------------------------ #
    # Redis
    # ------------------------------------------------------------------ #
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "redis_url"),
    )
    redis_cache_ttl_default: int = 3600

    # ------------------------------------------------------------------ #
    # AI / LLM
    # ------------------------------------------------------------------ #
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    openai_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_BASE_URL", "openai_base_url"),
    )
    ai_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("AI_MODEL", "ai_model"),
    )

    # ------------------------------------------------------------------ #
    # Web Search / Research
    # ------------------------------------------------------------------ #
    web_search_provider: str = Field(
        default="duckduckgo",
        validation_alias=AliasChoices("WEB_SEARCH_PROVIDER", "web_search_provider"),
    )
    web_search_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("WEB_SEARCH_API_KEY", "web_search_api_key"),
    )
    web_search_base_url: str = Field(
        default="https://api.duckduckgo.com",
        validation_alias=AliasChoices("WEB_SEARCH_BASE_URL", "web_search_base_url"),
    )

    # ------------------------------------------------------------------ #
    # Research freshness
    # ------------------------------------------------------------------ #
    research_max_age_hours: int = Field(
        default=24,
        validation_alias=AliasChoices("RESEARCH_MAX_AGE_HOURS", "research_max_age_hours"),
    )

    # ------------------------------------------------------------------ #
    # Source credibility
    # ------------------------------------------------------------------ #
    source_credibility_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("SOURCE_CREDIBILITY_ENABLED", "source_credibility_enabled"),
    )

    # ------------------------------------------------------------------ #
    # Admin / API security
    # ------------------------------------------------------------------ #
    admin_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ADMIN_API_KEY", "admin_api_key"),
    )
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:19006"]
    )

    # ------------------------------------------------------------------ #
    # Caching TTLs (seconds)
    # ------------------------------------------------------------------ #
    cache_ttl_leagues: int = 86400
    cache_ttl_teams: int = 43200
    cache_ttl_fixtures: int = 1800
    cache_ttl_statistics: int = 3600
    cache_ttl_form: int = 3600
    cache_ttl_injuries: int = 600
    cache_ttl_lineups: int = 300
    cache_ttl_odds: int = 120
    cache_ttl_news: int = 600
    cache_ttl_predictions: int = 300

    # ------------------------------------------------------------------ #
    # AI adjustment caps (max absolute shift in goal-rate lambda)
    # ------------------------------------------------------------------ #
    ai_attack_impact_cap: float = 0.15
    ai_defense_impact_cap: float = 0.15

    # ------------------------------------------------------------------ #
    # API pagination & caching
    # ------------------------------------------------------------------ #
    max_page_size: int = 100
    prediction_cache_ttl: int = 300

    @field_validator("football_data_provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        allowed = {"api_football", "sportmonks"}
        if v not in allowed:
            raise ValueError(f"Invalid FOOTBALL_DATA_PROVIDER '{v}'. Must be one of: {allowed}")
        return v

    @property
    def api_football_settings(self) -> ProviderSettings:
        return ProviderSettings(
            key=self.api_football_key,
            base_url=self.api_football_base_url,
            enabled=bool(self.api_football_key),
            rate_limit_per_minute=self.api_football_rate_limit,
            timeout_seconds=30,
        )

    @property
    def sportmonks_settings(self) -> ProviderSettings:
        return ProviderSettings(
            key=self.sportmonks_api_token,
            base_url=self.sportmonks_base_url,
            enabled=bool(self.sportmonks_api_token),
            rate_limit_per_minute=self.sportmonks_rate_limit,
            timeout_seconds=30,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
