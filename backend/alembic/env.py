"""Alembic environment configuration.

Usage:
    alembic upgrade head
    alembic revision --autogenerate -m "..."

Uses the async SQLAlchemy engine with ``conn.run_sync`` -- the recommended
pattern for SQLAlchemy 2.0 + async.
"""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any

# Make backend/app importable so `import models` works
_APP = Path(__file__).resolve().parents[1] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("FOOTBALL_DATA_PROVIDER", "api_football")

from core.config import get_settings  # noqa: E402
from db.base import Base  # noqa: E402
from db.database import engine  # noqa: E402
from alembic import context  # noqa: E402

config = context.config

# Import all models so they register on Base.metadata
import models  # noqa: E402,F401

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()


def do_run_migrations(connection: Any) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_async=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection)."""
    url = settings.database_url.replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the async engine."""
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
