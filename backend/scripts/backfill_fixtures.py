"""Backfill fixtures for each league's current season.

The daily sync's own fixture pass only looks 30 days ahead, so it can leave a
league with no rows at all once a campaign is under way. This script fetches a
wider window (recent past + upcoming) for the current season of every
configured league, upserting into Match by provider fixture id.

Usage:
    set PYTHONPATH=app
    python scripts/backfill_fixtures.py [--days-back 60] [--days-forward 120]
"""

import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from db.database import AsyncSessionLocal
from football_data.factory import get_football_provider
from football_data.models import FixtureStatus
from models.league import League, Season
from models.match import Match

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# httpx logs the full request URL at INFO, which puts the api_token query
# parameter into the logs. Keep provider calls at WARNING for this script.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("backfill_fixtures")


async def backfill(days_back: int, days_forward: int) -> int:
    provider = get_football_provider()
    await provider.connect()
    provider_name = provider.provider_name

    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=days_back)
    to_date = now + timedelta(days=days_forward)

    total_new = 0
    total_updated = 0
    total_errors = 0

    async with AsyncSessionLocal() as db:
        # Drive off the seasons already stored locally rather than LeagueMapping:
        # the provider_leagues rows are what the teams were mapped against, so
        # using them keeps fixtures consistent with existing team rows.
        season_rows = (
            await db.execute(
                select(Season.id, Season.league_id, League.provider_league_id)
                .join(League, League.id == Season.league_id)
                .where(Season.is_current.is_(True))
            )
        ).all()

        logger.info("Backfilling %d current seasons", len(season_rows))

        for season_id, internal_league_id, provider_league_id in season_rows:
            try:
                fixtures = await provider.get_fixtures(
                    league_id=provider_league_id,
                    season_id=season_id,
                    from_date=from_date,
                    to_date=to_date,
                )
            except Exception as exc:
                logger.warning("Fixture fetch failed for %s: %s", internal_league_id, exc)
                total_errors += 1
                continue

            new_rows = 0
            for norm in fixtures:
                if not norm.provider_fixture_id:
                    continue

                status_val = (
                    norm.status.value if isinstance(norm.status, FixtureStatus) else str(norm.status)
                )
                existing = await db.get(Match, norm.provider_fixture_id)

                if existing is None:
                    db.add(
                        Match(
                            id=norm.provider_fixture_id,
                            provider_name=provider_name,
                            provider_fixture_id=norm.provider_fixture_id,
                            league_id=internal_league_id,
                            season_id=season_id,
                            home_team_id=norm.home_team_id,
                            away_team_id=norm.away_team_id,
                            home_team_name=norm.home_team_name,
                            away_team_name=norm.away_team_name,
                            kickoff_at=norm.kickoff_at,
                            status=status_val,
                            venue=norm.venue,
                            referee=norm.referee,
                            home_score=norm.home_score,
                            away_score=norm.away_score,
                            is_finished=norm.is_finished,
                            retrieved_at=norm.retrieved_at,
                            provider_metadata=norm.provider_metadata,
                        )
                    )
                    new_rows += 1
                elif (
                    existing.home_score != norm.home_score
                    or existing.away_score != norm.away_score
                    or existing.status != status_val
                    or existing.is_finished != norm.is_finished
                ):
                    existing.home_score = norm.home_score
                    existing.away_score = norm.away_score
                    existing.status = status_val
                    existing.is_finished = norm.is_finished
                    existing.kickoff_at = norm.kickoff_at
                    existing.season_id = season_id
                    existing.retrieved_at = datetime.utcnow()
                    total_updated += 1

            await db.commit()
            total_new += new_rows
            logger.info(
                "%s season=%s fetched=%d new=%d", internal_league_id, season_id, len(fixtures), new_rows
            )

    logger.info(
        "Backfill complete: %d new, %d updated, %d league errors",
        total_new,
        total_updated,
        total_errors,
    )
    return total_new


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days-back", type=int, default=60)
    parser.add_argument("--days-forward", type=int, default=120)
    args = parser.parse_args()
    asyncio.run(backfill(args.days_back, args.days_forward))


if __name__ == "__main__":
    main()