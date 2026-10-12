"""OpenAI AI provider implementation."""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from ai.base import AIProvider
from core.config import get_settings

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """AI provider using OpenAI-compatible APIs (including OpenAI, Azure, etc.)."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.openai_api_key
        self._base_url = base_url or settings.openai_base_url
        self._model = model or settings.ai_model

        if not self._api_key:
            raise ValueError("OpenAI API key is required")

        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a structured JSON response using OpenAI's structured output."""
        try:
            response_format: dict[str, Any] | None = None
            if schema:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "extracted_data",
                        "schema": schema,
                        "strict": True,
                    },
                }
            else:
                response_format = {"type": "json_object"}

            retry_prompt = (
                "\n\nReturn a compact, complete JSON object only. Do not use markdown. "
                "Use empty arrays for collections with no supported evidence."
            )
            for attempt in range(2):
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": user_prompt + (retry_prompt if attempt else ""),
                        },
                    ],
                    response_format=response_format,
                    temperature=0.3,
                    max_tokens=3000,
                )

                content = response.choices[0].message.content
                if content is None:
                    return {}

                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as exc:
                    finish_reason = response.choices[0].finish_reason
                    if attempt == 0:
                        logger.warning(
                            "AI returned invalid structured JSON; retrying once",
                            extra={"finish_reason": finish_reason, "error": str(exc)},
                        )
                        continue
                    logger.warning(
                        "AI returned invalid structured JSON after retry; ignoring response",
                        extra={"finish_reason": finish_reason, "error": str(exc)},
                    )
                    return {}

                if isinstance(parsed, (dict, list)):
                    return parsed
                logger.warning("AI structured response must be a JSON object or array")
                return {}

            return {}
        except Exception as exc:
            logger.error("AI generation failed: %s", exc)
            return {}

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> str:
        """Generate a free-text response."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("AI text generation failed: %s", exc)
            return ""

    async def close(self) -> None:
        if self._client:
            await self._client.close()
