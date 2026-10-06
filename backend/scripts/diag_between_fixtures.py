"""Diagnose /fixtures/between for the now -> month-end 2026 window."""
import asyncio
import logging
from datetime import date, datetime

from dotenv import load_dotenv

from api.v1.endpoints.providers import _current_season_ids
from db.database import AsyncSessionLocal
from football_data.factory import get_football_provider
from models.league import Season

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main() -> None:
    today = date(2026, 10, 4)
    month_end = date(2026, 10, 31)
    provider = get_football_provider()
    async with provider:
        fx = await provider.get_fixtures(from_date=today, to_date=month_end)
    fx = fx or []
    kicks = [getattr(f, "kickoff_at", None) for f in fx]
    kicks = [k for k in kicks if k is not None]
    sids = sorted({getattr(f, "season_id", None) for f in fx if getattr(f, "season_id", None)})
    print("BETWEEN total=%d seasons=%s" % (len(fx), sids), flush=True)
    if kicks:
        print("BETWEEN kickoff min=%s max=%s years=%s" % (
            min(kicks), max(kicks), sorted({k.year for k in kicks}),
        ), flush=True)
    if fx:
        sample = fx[0]
        print("SAMPLE keys:", sorted(vars(sample).keys()), flush=True)
        print("SAMPLE:", vars(sample), flush=True)

    async with AsyncSessionLocal() as db:
        cur = (await db.execute(_current_season_ids())).scalars().all()
        print("DB current season ids:", sorted(cur), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
