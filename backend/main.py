"""Entry point for FastAPI Cloud and local development.

FastAPI Cloud auto-detects this file and runs `uvicorn main:app`.
The sys.path manipulation makes the ``app/`` package importable
without requiring a `pip install -e .` step.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

_APP = Path(__file__).resolve().parent / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

import asyncio  # noqa: E402

from core.config import get_settings  # noqa: E402
from db.database import engine  # noqa: E402


async def _ensure_schema() -> None:
    """Ensure required database columns exist (for databases created before migrations)."""
    settings = get_settings()
    if not settings.database_url:
        return

    try:
        from sqlalchemy import text

        async with engine.begin() as conn:
            # Check if payment_reference column exists in subscriptions table
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'subscriptions' AND column_name = 'payment_reference'"
            ))
            exists = result.fetchone()
            if exists is None:
                await conn.execute(text(
                    "ALTER TABLE subscriptions ADD COLUMN payment_reference VARCHAR(200) UNIQUE"
                ))
                print("[startup] Added payment_reference column to subscriptions table")

            # Convert timezone-naive datetime columns to timezone-aware
            # (needed for databases created before the DateTime(timezone=True) fix)
            tz_aware_columns = {
                "subscriptions": ["current_period_end", "current_period_start", "created_at", "updated_at"],
                "users": ["created_at", "updated_at"],
            }
            for table_name, columns in tz_aware_columns.items():
                for col_name in columns:
                    result_col = await conn.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :table_name AND column_name = :col_name "
                        "AND udt_name = 'timestamp'"
                    ), {"table_name": table_name, "col_name": col_name})
                    if result_col.fetchone() is not None:
                        await conn.execute(text(
                            f"ALTER TABLE {table_name} "
                            f"ALTER COLUMN {col_name} TYPE TIMESTAMP WITH TIME ZONE"
                        ))
                        print(f"[startup] Converted {table_name}.{col_name} to TIMESTAMPTZ")

            # Check if is_superuser column exists in users table
            result2 = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'is_superuser'"
            ))
            exists2 = result2.fetchone()
            if exists2 is None:
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN is_superuser BOOLEAN NOT NULL DEFAULT FALSE"
                ))
                print("[startup] Added is_superuser column to users table")

    except Exception as exc:
        print(f"[startup] Schema check warning: {exc}")


from api.main import app  # noqa: E402


@app.on_event("startup")
async def _startup() -> None:
    await asyncio.create_task(_ensure_schema())


__all__ = ["app"]
