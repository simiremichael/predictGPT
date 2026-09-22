"""AI service: orchestrates evidence extraction, conflict detection,
and explanation generation using the provider abstraction.

The service treats all web content as untrusted input and never
follows instructions embedded in web pages.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from ai.base import AIProvider
from ai.exceptions import AIError, ExtractionError
from ai.prompts import (
    CONFLICT_DETECTION_SYSTEM_PROMPT,
    CONFLICT_DETECTION_USER_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    INJURY_EXTRACTION_USER_PROMPT,
    LINEUP_EXTRACTION_USER_PROMPT,
    SUSPENSION_EXTRACTION_USER_PROMPT,
    TEAM_NEWS_EXTRACTION_USER_PROMPT,
)
from core.config import get_settings
from web_research.schemas import (
    EvidenceStatus,
    InjuryEvidence,
    LineupEvidence,
    LineupStatus,
    ResearchSource,
    SuspensionEvidence,
    TeamNewsEvidence,
)

logger = logging.getLogger(__name__)


class AIService:
    """High-level service wrapping the AI provider for football evidence tasks."""

    def __init__(self, ai_provider: AIProvider | None = None) -> None:
        self._provider = ai_provider
        self._settings = get_settings()

    async def get_provider(self) -> AIProvider:
        """Get or lazily initialize the AI provider."""
        if self._provider is None:
            from ai.factory import get_ai_provider

            self._provider = get_ai_provider()
        return self._provider

    async def close(self) -> None:
        if self._provider:
            await self._provider.close()
            self._provider = None

    # ── Evidence extraction ────────────────────────────────────────── #

    async def extract_injuries(
        self,
        content: str,
        source_id: str,
        home_team: str,
        away_team: str,
    ) -> list[InjuryEvidence]:
        """Extract injury evidence from web content."""
        return await self._extract_evidence(
            content, source_id, home_team, away_team,
            INJURY_EXTRACTION_USER_PROMPT, InjuryEvidence,
        )

    async def extract_suspensions(
        self,
        content: str,
        source_id: str,
        home_team: str,
        away_team: str,
    ) -> list[SuspensionEvidence]:
        """Extract suspension evidence from web content."""
        return await self._extract_evidence(
            content, source_id, home_team, away_team,
            SUSPENSION_EXTRACTION_USER_PROMPT, SuspensionEvidence,
        )

    async def extract_lineup(
        self,
        content: str,
        source_id: str,
        home_team: str,
        away_team: str,
    ) -> LineupEvidence | None:
        """Extract lineup evidence from web content."""
        results = await self._extract_evidence(
            content, source_id, home_team, away_team,
            LINEUP_EXTRACTION_USER_PROMPT, LineupEvidence,
        )
        return results[0] if results else None

    async def extract_team_news(
        self,
        content: str,
        source_id: str,
        home_team: str,
        away_team: str,
    ) -> list[TeamNewsEvidence]:
        """Extract team news evidence from web content."""
        return await self._extract_evidence(
            content, source_id, home_team, away_team,
            TEAM_NEWS_EXTRACTION_USER_PROMPT, TeamNewsEvidence,
        )

    async def _extract_evidence(
        self,
        content: str,
        source_id: str,
        home_team: str,
        away_team: str,
        user_prompt_template: str,
        result_model: type,
    ) -> list[Any]:
        """Generic evidence extraction using the AI provider.

        Treats all content as untrusted evidence. Uses structured output
        via the system prompt instructions.
        """
        if not content:
            return []

        user_prompt = user_prompt_template.format(
            home_team=home_team,
            away_team=away_team,
            source_id=source_id,
            content=content,
        )

        try:
            provider = await self.get_provider()
            raw_result = await provider.generate_structured(
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=None,
            )

            if not raw_result:
                return []

            # The AI returns JSON; parse into model instances
            records: list[Any] = []
            if isinstance(raw_result, list):
                for item in raw_result:
                    if isinstance(item, dict):
                        try:
                            records.append(result_model(**item))
                        except Exception as exc:
                            logger.warning(
                                "Failed to parse evidence record: %s", exc,
                                extra={"source_id": source_id},
                            )
            elif isinstance(raw_result, dict):
                try:
                    records.append(result_model(**raw_result))
                except Exception as exc:
                    logger.warning(
                        "Failed to parse evidence record: %s", exc,
                        extra={"source_id": source_id},
                    )

            return records

        except Exception as exc:
            logger.error(
                "AI extraction failed",
                extra={
                    "source_id": source_id,
                    "error": str(exc),
                },
            )
            raise ExtractionError(
                f"AI extraction failed: {exc}",
                details={"source_id": source_id},
            ) from exc

    # ── Conflict detection ──────────────────────────────────────────── #

    async def detect_conflicts(
        self,
        evidence_text: str,
        home_team: str,
        away_team: str,
    ) -> list[dict[str, Any]]:
        """Detect conflicting claims across evidence sources."""
        if not evidence_text:
            return []

        user_prompt = CONFLICT_DETECTION_USER_PROMPT.format(
            home_team=home_team,
            away_team=away_team,
            evidence_text=evidence_text,
        )

        try:
            provider = await self.get_provider()
            raw_result = await provider.generate_structured(
                system_prompt=CONFLICT_DETECTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=None,
            )

            if not raw_result:
                return []

            if isinstance(raw_result, list):
                return [item for item in raw_result if isinstance(item, dict)]

            return []

        except Exception as exc:
            logger.error("Conflict detection failed: %s", exc)
            return []

    # ── Text generation ─────────────────────────────────────────────── #

    async def generate_explanation(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> str:
        """Generate a human-readable text response."""
        provider = await self.get_provider()
        return await provider.generate_text(system_prompt, user_prompt, max_tokens)
