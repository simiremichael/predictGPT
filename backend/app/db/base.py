"""SQLAlchemy declarative base and async engine helpers."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

from core.config import get_settings

settings = get_settings()


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base with UUID primary keys by default."""

    pass


def _uuid_pk():
    """Generate a UUID4 string for primary keys."""
    import uuid as _uuid

    return str(_uuid.uuid4())
