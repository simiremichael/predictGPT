"""Abstract base class for web search providers.

The web research module does not depend on any specific search API.
Each concrete provider implements ``WebSearchProvider`` and is selected via
configuration (``WEB_SEARCH_PROVIDER``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SearchResult:
    """A single search result entry."""

    title: str | None
    url: str
    snippet: str | None
    source_type: str = "search_result"
    publisher: str | None = None
    published_at: str | None = None
    result_metadata: dict[str, Any] = None


class WebSearchProvider(ABC):
    """Abstract interface for web search providers."""

    provider_name: str

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Execute a web search and return normalized results.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            A list of SearchResult objects.
        """
        ...

    async def close(self) -> None:
        """Close any open connections/resources. Override if needed."""
        pass
