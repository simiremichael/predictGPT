"""Pytest configuration.

Inserts ``backend/app`` at the front of ``sys.path`` so that the top-level
packages (``core``, ``db``, ``football_data``, ``api`` ...) are importable
without an installed package.  When the test suite is run from the
``backend`` directory (the default for ``pytest``), this conftest is picked
up automatically.
"""

import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# Ensure test settings don't depend on a real .env being present.
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("FOOTBALL_DATA_PROVIDER", "sportmonks")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://neondb_owner:npg_UlzWti9uqGm0@ep-square-grass-za4glnjc-pooler.c-2.eu-west-2.aws.neon.tech/neondb?ssl=require",
)
os.environ.setdefault(
    "REDIS_URL",
    "rediss://default:gQAAAAAABFumAAIgcDE4Y2JhMTVhMDFlYzE0ZDIzOTViNzYxMjA1ZjVlNWU2Nw@singular-gazelle-285606.upstash.io:6379",
)
os.environ.setdefault("ADMIN_API_KEY", "test_admin_key")
os.environ.setdefault("APP_DEBUG", "false")

import pytest
from pydantic_settings import SettingsConfigDict

from core.config import Settings


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test independent from credentials in the developer .env file."""
    import core.config as _cfg_mod

    monkeypatch.setattr(
        Settings,
        "model_config",
        SettingsConfigDict(
            env_file=None,
            env_nested_delimiter="__",
            extra="ignore",
            case_sensitive=False,
        ),
    )
    _cfg_mod.get_settings.cache_clear()
    yield
    _cfg_mod.get_settings.cache_clear()


@pytest.fixture()
def settings() -> Settings:
    """Return a fresh Settings instance for the test environment."""
    return Settings()
