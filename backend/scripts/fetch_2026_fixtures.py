"""Persist fixtures for the now -> month-end 2026 window.

Per the request, fixtures are fetched from today (2026-10-04) through the end of
the month via Sportmonks' date-scoped ``/fixtures/between/{from}/{to}`` route
(not the flat ``/fixtures`` endpoint, which ignores date params and returns a
stale 2024 corpus).  Only fixtures that belong to a DB current season are kept,
so the ``/providers/matches`` page (which defaults to current seasons) can serve
them from the database without a slow live fetch.

    set PYTHONPATH=app
    python scripts/fetch_2026_fixtures.py
"""

import asyncio
import logging
from datetime import date

from dotenv import load_dotenv
from sqlalchemy import delete, func, select

from api.v1.endpoints.providers import (
    _current_season_ids,
    _map_fixture_teams,
    _save_fixtures,
)
from db.database import AsyncSessionLocal
from football_data.factory import get_football_provider
from models.match import Match

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("fetch_2026_fixtures")


async def main() -> None:
    today = date(2026, 10, 4)
    month_end = date(2026, 10, 31)

    provider = get_football_provider()
    async with provider:
        fixtures = await provider.get_fixtures(from_date=today, to_date=month_end)
    fixtures = fixtures or []

    kicks = [getattr(f, "kickoff_at", None) for f in fixtures]
    kicks = [k for k in kicks if k is not None]
    sids = sorted({getattr(f, "season_id", None) for f in fixtures if getattr(f, "season_id", None)})
    logger.info(
        "Fetched %d fixtures (seasons=%s, kickoff years=%s) for %s..%s",
        len(fixtures),
        sids,
        sorted({k.year for k in kicks}) if kicks else [],
        today,
        month_end,
    )

    async with AsyncSessionLocal() as db:
        cur = set(str(x) for x in (await db.execute(_current_season_ids())).scalars().all())
        current = [f for f in fixtures if f.season_id in cur]
        logger.info("Keeping %d fixtures in current seasons (of %d)", len(current), len(fixtures))

        try:
            # Drop stale non-current-season fixtures (e.g. the 2024 /fixtures corpus)
            # so they do not shadow the 2026 set on all_seasons=true queries.
            if cur:
                await db.execute(delete(Match).where(Match.season_id.notin_(cur)))
            await _save_fixtures(db, current)
            await _map_fixture_teams(db, current)
            await db.commit()
            logger.info("Persisted %d fixtures to DB", len(current))
        except Exception:
            await db.rollback()
            logger.exception("Save failed, rolled back")
            raise

        total = (await db.execute(select(func.count()).select_from(Match))).scalar()
        cur_matches = (
            (await db.execute(select(func.count()).select_from(Match).where(Match.season_id.in_(list(cur)))))
            if cur
            else 0
        )
        logger.info("DB state: total matches=%d, current-season matches=%d", total, cur_matches)


if __name__ == "__main__":
    asyncio.run(main())
