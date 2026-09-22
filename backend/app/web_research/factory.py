"""Search provider factory."""
from __future__ import annotations

import logging

from web_research.base import WebSearchProvider

logger = logging.getLogger(__name__)

SUPPORTED_SEARCH_PROVIDERS = ("duckduckgo", "brave")


def get_search_provider() -> WebSearchProvider:
    """Instantiate and return the active search provider from configuration."""
    from core.config import get_settings

    settings = get_settings()
    provider_name: str = settings.web_search_provider

    if provider_name not in SUPPORTED_SEARCH_PROVIDERS:
        raise ValueError(
            f"Unsupported WEB_SEARCH_PROVIDER '{provider_name}'. "
            f"Supported: {SUPPORTED_SEARCH_PROVIDERS}"
        )

    if provider_name == "duckduckgo":
        from web_research.search import DuckDuckGoSearchProvider

        provider = DuckDuckGoSearchProvider(
            base_url=settings.web_search_base_url,
        )
    else:
        raise ValueError(f"Unknown search provider '{provider_name}'")

    logger.info(
        "Web search provider selected",
        extra={"provider": provider.provider_name},
    )
    return provider
