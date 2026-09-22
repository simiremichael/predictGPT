"""Pagination utilities for API endpoints.

Provides a standard ``paginate`` function that computes page metadata and
slices a query or list result set.
"""
from __future__ import annotations

import math
from typing import Any, TypeVar

from core.config import get_settings

T = TypeVar("T")

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def get_page_size(page_size: int | None) -> int:
    if page_size is None or page_size < 1:
        return DEFAULT_PAGE_SIZE
    settings = get_settings()
    max_ps = getattr(settings, "max_page_size", MAX_PAGE_SIZE) or MAX_PAGE_SIZE
    return min(page_size, max_ps)


def get_page(page: int | None) -> int:
    if page is None or page < 1:
        return 1
    return page


class PaginationResult:
    """Holds a paginated slice of data with metadata."""

    def __init__(
        self,
        data: list[T],
        page: int,
        page_size: int,
        total: int,
    ) -> None:
        self.data = data
        self.page = page
        self.page_size = page_size
        self.total = total
        self.total_pages = max(1, math.ceil(total / page_size)) if page_size > 0 else 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    def to_meta(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total": self.total,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_previous": self.has_previous,
        }


def paginate[T](
    items: list[T],
    page: int,
    page_size: int,
) -> PaginationResult:
    """Paginate an in-memory list of items."""
    page = get_page(page)
    page_size = get_page_size(page_size)

    start = (page - 1) * page_size
    end = start + page_size

    data = items[start:end] if items else []
    total = len(items) if hasattr(items, "__len__") else 0

    return PaginationResult(data=data, page=page, page_size=page_size, total=total)


def offset_limit(page: int, page_size: int) -> tuple[int, int]:
    """Return (offset, limit) for a SQL query from page params."""
    page = get_page(page)
    page_size = get_page_size(page_size)
    offset = (page - 1) * page_size
    return offset, page_size
