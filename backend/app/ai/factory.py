"""AI provider factory.

Selects and instantiates the active AI provider based on configuration.
"""
from __future__ import annotations

import logging

from ai.base import AIProvider
from core.config import get_settings

logger = logging.getLogger(__name__)

SUPPORTED_AI_PROVIDERS = ("openai",)


def get_ai_provider() -> AIProvider:
    """Instantiate and return the active AI provider from configuration.

    Raises:
        ValueError: if the provider is unsupported or credentials are missing.
    """
    settings = get_settings()
    provider_name: str = "openai"

    if provider_name not in SUPPORTED_AI_PROVIDERS:
        raise ValueError(
            f"Unsupported AI_PROVIDER '{provider_name}'. "
            f"Supported: {SUPPORTED_AI_PROVIDERS}"
        )

    if provider_name == "openai":
        from ai.providers.openai import OpenAIProvider

        if not settings.openai_api_key:
            raise ValueError(
                "OpenAI selected as active provider but OPENAI_API_KEY "
                "is not configured."
            )
        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.ai_model,
        )
    else:
        raise ValueError(f"Unknown AI provider '{provider_name}'")

    logger.info(
        "AI provider selected",
        extra={"provider": provider.provider_name},
    )
    return provider
