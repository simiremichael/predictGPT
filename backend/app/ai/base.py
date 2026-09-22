"""Abstract base class for AI providers.

The AI layer does not depend on any specific LLM vendor.  Each concrete
provider implements ``AIProvider`` and is selected via configuration
(``AI_PROVIDER``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Abstract interface for AI/LLM providers."""

    provider_name: str

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a structured (JSON) response from the AI.

        Args:
            system_prompt: System instructions for the AI.
            user_prompt: User query / evidence to process.
            schema: Optional JSON schema for output validation.

        Returns:
            A dict parsed from the AI's JSON response.
        """
        ...

    @abstractmethod
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> str:
        """Generate a free-text response from the AI.

        Args:
            system_prompt: System instructions for the AI.
            user_prompt: User query.
            max_tokens: Maximum output tokens.

        Returns:
            The generated text.
        """
        ...

    async def close(self) -> None:
        """Close any open connections/resources. Override if needed."""
        pass
