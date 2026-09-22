"""API response standard schemas.

Every API response follows a consistent envelope:

    Success: {"success": True, "data": {}, "meta": {}}
    Error:   {"success": False, "error": {"code": "...", "message": "..."}}
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": "INTERNAL_ERROR", "message": "An error occurred"}
    )


class SuccessResponse[T](BaseModel):
    success: bool = True
    data: T | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class PaginatedResponse[T](BaseModel):
    success: bool = True
    data: list[T] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1
