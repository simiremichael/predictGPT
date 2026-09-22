"""Provider factory.

Reads ``FOOTBALL_DATA_PROVIDER`` from configuration and returns the active
``FootballDataProvider`` implementation.  The active provider is controlled
entirely by configuration; switching providers requires only changing the
env var and restarting -- no prediction engine or route code changes.

A failed import or misconfiguration raises ``ProviderConfigurationError``.
"""

from __future__ import annotations

import logging
from typing import Literal

from core.config import get_settings
from core.exceptions import ProviderConfigurationError
from football_data.base import FootballDataProvider

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = ("api_football", "sportmonks")

ActiveProvider = Literal["api_football", "sportmonks"]


def get_football_provider() -> FootballDataProvider:
    """Instantiate and return the active provider from configuration.

    Raises:
        ProviderConfigurationError: if provider is unsupported or credentials
            are missing/not configured.
    """
    settings = get_settings()
    provider_name: str = settings.football_data_provider

    if provider_name not in SUPPORTED_PROVIDERS:
        raise ProviderConfigurationError(
            f"Unsupported FOOTBALL_DATA_PROVIDER '{provider_name}'. "
            f"Supported: {SUPPORTED_PROVIDERS}"
        )

    if provider_name == "api_football":
        from football_data.api_football import APIFootballProvider

        if not settings.api_football_key:
            raise ProviderConfigurationError(
                "API-Football selected as active provider but API_FOOTBALL_KEY is not configured."
            )
        provider = APIFootballProvider(
            api_key=settings.api_football_key,
            base_url=settings.api_football_base_url,
        )
    elif provider_name == "sportmonks":
        from football_data.sportmonks import SportmonksProvider

        if not settings.sportmonks_api_token:
            raise ProviderConfigurationError(
                "Sportmonks selected as active provider but SPORTMONKS_API_TOKEN is not configured."
            )
        provider = SportmonksProvider(
            api_token=settings.sportmonks_api_token,
            base_url=settings.sportmonks_base_url,
        )
    else:  # pragma: no cover - guarded above
        raise ProviderConfigurationError(f"Unknown provider '{provider_name}'")

    logger.info(
        "Active football data provider selected",
        extra={"provider": provider.provider_name},
    )
    return provider


def get_provider_for_name(name: str) -> FootballDataProvider | None:
    """Instantiate a provider by name, without checking credentials.

    Returns None if the provider name is unsupported or credentials are
    missing.  Used by the health-check / comparison endpoints.
    """
    settings = get_settings()
    if name == "api_football" and settings.api_football_key:
        from football_data.api_football import APIFootballProvider

        return APIFootballProvider(
            api_key=settings.api_football_key,
            base_url=settings.api_football_base_url,
        )
    if name == "sportmonks" and settings.sportmonks_api_token:
        from football_data.sportmonks import SportmonksProvider

        return SportmonksProvider(
            api_token=settings.sportmonks_api_token,
            base_url=settings.sportmonks_base_url,
        )
    return None
