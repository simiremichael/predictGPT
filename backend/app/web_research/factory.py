"""Build the configured web-search provider and its ordered fallbacks.

Default priority: Tavily, Brave Search, then You.com. Providers without API
keys are skipped so missing optional credentials do not disable search.
"""
from __future__ import annotations

import logging

from web_research.base import WebSearchProvider

logger = logging.getLogger(__name__)
SUPPORTED_SEARCH_PROVIDERS = ("tavily", "brave", "youcom")


def get_search_provider() -> WebSearchProvider:
    """Build a search chain with Tavily first, then Brave, then You.com."""
    from core.config import get_settings

    settings = get_settings()
    if settings.web_search_provider not in SUPPORTED_SEARCH_PROVIDERS:
        raise ValueError(
            f"Unsupported WEB_SEARCH_PROVIDER '{settings.web_search_provider}'. "
            f"Supported: {SUPPORTED_SEARCH_PROVIDERS}"
        )

    youcom: WebSearchProvider | None = None
    if settings.you_api_key:
        from web_research.youcom import YouComSearchProvider

        youcom = YouComSearchProvider(
            api_key=settings.you_api_key,
            base_url=settings.you_search_url,
        )

    brave: WebSearchProvider | None = None
    if settings.brave_api_key:
        from web_research.brave import BraveSearchProvider

        brave = BraveSearchProvider(
            api_key=settings.brave_api_key,
            base_url=settings.brave_search_url,
            fallback_provider=youcom,
        )

    tavily: WebSearchProvider | None = None
    if settings.tavily_api_key:
        from web_research.tavily import TavilySearchProvider

        tavily = TavilySearchProvider(
            api_key=settings.tavily_api_key,
            base_url=settings.tavily_search_url,
            fallback_provider=brave or youcom,
        )

    if settings.web_search_provider == "tavily":
        provider = tavily or brave or youcom
        if tavily is None:
            logger.warning("TAVILY_API_KEY is missing; falling back to Brave, then You.com")
    elif settings.web_search_provider == "brave":
        provider = brave or youcom
        if brave is None:
            logger.warning("BRAVE_API_KEY is missing; falling back to You.com")
    else:
        provider = youcom

    if provider is None:
        # For Tavily, no credentials are available for the requested chain.
        if settings.web_search_provider == "tavily":
            logger.warning("TAVILY_API_KEY is missing; falling back to Brave, then You.com")
        raise ValueError(
            "No web search provider is configured. Set at least one of "
            "TAVILY_API_KEY, BRAVE_API_KEY, or YOU_API_KEY."
        )

    logger.info(
        "Web search provider chain initialized",
        extra={"primary_provider": provider.provider_name},
    )
    return provider
