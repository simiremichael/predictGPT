"""Populate the matches table with all fixtures the provider currently holds.

The sandbox's fixture set lags its /seasons window, so a single global fetch is
the only way to get any fixture rows in the store. Reuses the same bulk save path
as the daily sync (including FK-safe parent provisioning) so the web matches page
can be served from the DB instead of triggering a slow live fetch that exceeds the
browser's request timeout.

Usage:
    set PYTHONPATH=app
    python scripts/populate_fixtures.py
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from api.v1.endpoints.providers import _map_fixture_teams, _save_fixtures
from db.database import AsyncSessionLocal
from football_data.factory import get_football_provider
from models.match import Match

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("populate_fixtures")


async def main() -> None:
    provider = get_football_provider()
    async with provider:
        fixtures = await provider.get_fixtures(
            from_date=datetime.now(timezone.utc) - timedelta(days=1),
            to_date=datetime.now(timezone.utc) + timedelta(days=365),
        )
    logger.info("Fetched %s fixtures from provider", len(fixtures) if fixtures else 0)

    async with AsyncSessionLocal() as db:
        await _map_fixture_teams(db, fixtures or [])
        await _save_fixtures(db, fixtures or [])
        await db.commit()
        from sqlalchemy import func, select
        count = (await db.execute(select(func.count()).select_from(Match))).scalar() or 0
        logger.info("matches rows now = %s", count)


if __name__ == "__main__":
    asyncio.run(main())
