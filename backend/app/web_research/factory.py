"""Search provider factory.

Fallback chain:
  1. Tavily  (primary, if TAVILY_API_KEY set)
  2. You.com (secondary, if YOU_API_KEY set)
  3. Brave   (terminal, if BRAVE_API_KEY set)
"""
from __future__ import annotations

import logging

from web_research.base import WebSearchProvider

logger = logging.getLogger(__name__)

SUPPORTED_SEARCH_PROVIDERS = ("tavily", "youcom", "brave")


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

    if provider_name == "tavily":
        from web_research.brave import BraveSearchProvider
        from web_research.tavily import TavilySearchProvider
        from web_research.youcom import YouComSearchProvider

        fallback = _build_secondary_provider(settings, YouComSearchProvider, BraveSearchProvider)
        if not settings.tavily_api_key:
            logger.warning("TAVILY_API_KEY is missing; using secondary search provider")
            return fallback
        provider = TavilySearchProvider(
            api_key=settings.tavily_api_key,
            fallback_provider=fallback,
        )
    elif provider_name == "youcom":
        from web_research.brave import BraveSearchProvider
        from web_research.youcom import YouComSearchProvider

        fallback = _build_secondary_provider(settings, None, BraveSearchProvider)
        if not settings.you_api_key:
            logger.warning("YOU_API_KEY is missing; using Brave search as fallback")
            return fallback
        provider = YouComSearchProvider(
            api_key=settings.you_api_key,
            fallback_provider=fallback,
        )
    elif provider_name == "brave":
        from web_research.brave import BraveSearchProvider

        if not settings.brave_api_key:
            raise ValueError(
                "BRAVE_API_KEY is required when WEB_SEARCH_PROVIDER='brave'"
            )
        provider = BraveSearchProvider(api_key=settings.brave_api_key)
    else:
        raise ValueError(f"Unknown search provider '{provider_name}'")

    logger.info(
        "Web search provider selected",
        extra={"provider": provider.provider_name},
    )
    return provider


def _build_secondary_provider(
    settings,
    primary_cls: type | None,
    terminal_cls: type,
) -> WebSearchProvider:
    """Build the You.com → Brave fallback chain.

    If primary_cls is provided (YouComSearchProvider) and its API key is
    available, use it with Brave as the terminal fallback. Otherwise fall
    back to Brave directly.
    """
    from web_research.brave import BraveSearchProvider
    from web_research.youcom import YouComSearchProvider

    if not settings.brave_api_key:
        raise ValueError("BRAVE_API_KEY is required for the search fallback chain")
    brave = terminal_cls(api_key=settings.brave_api_key)

    if primary_cls is not None and settings.you_api_key:
        return primary_cls(api_key=settings.you_api_key, fallback_provider=brave)

    logger.warning(
        "YOU_API_KEY is missing; using Brave as the secondary search provider"
    )
    return brave
