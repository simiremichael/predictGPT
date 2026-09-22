"""Pydantic schemas for AI provider responses."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AICompletionRequest(BaseModel):
    """Request model for AI completion."""

    system_prompt: str
    user_prompt: str
    max_tokens: int = 1000
    temperature: float = 0.7


class AICompletionResponse(BaseModel):
    """Response model for AI completion."""

    text: str
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)
    finish_reason: str | None = None


class StructuredAIResponse(BaseModel):
    """Response model for structured AI output."""

    data: dict[str, Any]
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)
