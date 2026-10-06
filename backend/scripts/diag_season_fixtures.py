"""Fetch fixtures for a single current (2026) season and report what returns."""
import asyncio
import logging
from datetime import datetime, date

from dotenv import load_dotenv

from football_data.factory import get_football_provider

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main() -> None:
    provider = get_football_provider()
    async with provider:
        # current season id from the DB / provider (2026)
        fx = await provider.get_fixtures(season_id="26720")
    fx = fx or []
    kicks = [getattr(f, "kickoff_at", None) for f in fx]
    kicks = [k for k in kicks if k is not None]
    sids = sorted({getattr(f, "season_id", None) for f in fx if getattr(f, "season_id", None)})
    print("DIAG season_id=26720 total=%d seasons=%s" % (len(fx), sids), flush=True)
    if kicks:
        print("DIAG kickoff min=%s max=%s years=%s" % (
            min(kicks), max(kicks),
            sorted({k.year for k in kicks}),
        ), flush=True)

    # Also try a 2026 date window to confirm whether date filtering is honored.
    async with provider:
        fx2 = await provider.get_fixtures(
            from_date=datetime(2026, 1, 1),
            to_date=datetime(2026, 12, 31, 23, 59, 59),
        )
    fx2 = fx2 or []
    kicks2 = [getattr(f, "kickoff_at", None) for f in fx2]
    kicks2 = [k for k in kicks2 if k is not None]
    print("DIAG window=2026 total=%d years=%s" % (len(fx2), sorted({k.year for k in kicks2}) if kicks2 else []), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
