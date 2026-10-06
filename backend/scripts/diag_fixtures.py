"""Diagnose the date range of the fixtures the provider returns."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from football_data.factory import get_football_provider

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main() -> None:
    provider = get_football_provider()
    async with provider:
        fixtures = await provider.get_fixtures(
            from_date=datetime.now(timezone.utc) - timedelta(days=1),
            to_date=datetime.now(timezone.utc) + timedelta(days=365),
        )
    fx = fixtures or []
    kicks = [getattr(f, "kickoff_at", None) for f in fx]
    kicks = [k for k in kicks if k is not None]
    sids = sorted({getattr(f, "season_id", None) for f in fx if getattr(f, "season_id", None)})
    in_2026 = sum(1 for k in kicks if k.year == 2026)
    print("DIAG total=%d seasons=%s" % (len(fx), sids), flush=True)
    if kicks:
        print("DIAG kickoff min=%s max=%s" % (min(kicks), max(kicks)), flush=True)
    print("DIAG kickoffs_in_2026=%d 2024=%d 2025=%d 2027=%d" % (
        in_2026,
        sum(1 for k in kicks if k.year == 2024),
        sum(1 for k in kicks if k.year == 2025),
        sum(1 for k in kicks if k.year == 2027),
    ), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
