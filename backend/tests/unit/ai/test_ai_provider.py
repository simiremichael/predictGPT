"""Tests for AI provider abstraction and factory."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai.base import AIProvider


class MockAIProvider(AIProvider):
    """Mock AI provider for testing."""

    provider_name = "mock"

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"test": "result"}

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> str:
        return "Generated text"

    async def close(self) -> None:
        pass


class TestAIProviderInterface:
    def test_provider_has_required_methods(self) -> None:
        provider = MockAIProvider()
        assert hasattr(provider, "generate_structured")
        assert hasattr(provider, "generate_text")
        assert hasattr(provider, "provider_name")

    @pytest.mark.asyncio
    async def test_generate_structured_returns_dict(self) -> None:
        provider = MockAIProvider()
        result = await provider.generate_structured("sys", "user")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_text_returns_string(self) -> None:
        provider = MockAIProvider()
        result = await provider.generate_text("sys", "user")
        assert isinstance(result, str)


class TestAIProviderFactory:
    def test_supported_providers(self) -> None:
        from ai.factory import SUPPORTED_AI_PROVIDERS

        assert "openai" in SUPPORTED_AI_PROVIDERS

    def test_factory_raises_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from ai.factory import get_ai_provider

        monkeypatch.setenv("OPENAI_API_KEY", "")
        with pytest.raises((ValueError, Exception)):
            get_ai_provider()
