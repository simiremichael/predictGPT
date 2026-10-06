"""Generate predictions for every current-season 2026 fixture on the matches
page (kickoff now -> month end).

Per the request: take the 2026 matches and analyse/generate predictions so the
prediction page is populated.

Why this is fast (unlike calling Orchestrator.generate_upcoming_predictions,
which is capped to a 7-day window and runs a per-match provider sync):

  * PredictionService.predict_match accepts a pre-built ``prediction_context``.
    When supplied, the service builds the PredictionInput straight from it
    (services/prediction_data.py:426) instead of running the availability
    check + provider sync.  These 2026 fixtures have no stored team history
    in the DB yet, so the sync would only 404 and degrade to league baselines
    anyway -- identical to what we produce here.
  * include_research=False skips the web-research / LLM adjustment layer.
  * Each match is predicted in its own session with a bounded concurrency
    semaphore, so DB I/O overlaps.  PoissonModel compute is light.

    set PYTHONPATH=app
    python scripts/generate_2026_predictions.py
"""

import asyncio
import logging
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import func, select

from core.config import get_settings
from db.database import AsyncSessionLocal
from football_data.models import FixtureStatus
from models.league import Season
from models.match import Match, Prediction
from prediction.service import PredictionService
from services.data_availability import DataAvailabilityResult
from services.prediction_data import PredictionContext, PredictionDataService

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("gen_2026_predictions")

# A pooled engine (NOT NullPool) so the 1037-match run reuses a handful of
# physical DB connections instead of opening one per match. The sandbox DB
# host's DNS resolver cannot tolerate 8 concurrent ``asyncpg.connect`` calls
# (getaddrinfo failures / CancelledError storms), so we keep concurrency low
# and size the pool to match.
_settings = get_settings()
engine = create_async_engine(
    _settings.database_url,
    pool_size=4,
    max_overflow=2,
    pool_pre_ping=True,
    future=True,
)
PooledSession = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

CONCURRENCY = 2
WINDOW_DAYS = 30


async def _has_existing_prediction(db, match_id: str) -> bool:
    result = await db.execute(select(Prediction).where(Prediction.match_id == match_id).limit(1))
    return result.scalar_one_or_none() is not None


async def _load_match(db, match_id: str) -> Match | None:
    # A bare select is enough: _build_context only reads scalar columns
    # (home_team_name / away_team_name are populated on the fixtures), and
    # passing prediction_context to predict_match short-circuits
    # _load_match_input before any relationship is touched.
    result = await db.execute(select(Match).where(Match.id == match_id))
    return result.scalar_one_or_none()


def _build_context(data_service: PredictionDataService, match: Match) -> PredictionContext:
    return PredictionContext(
        match_id=str(match.id),
        fixture=data_service._serialize_match(match),
        home_team=data_service._serialize_team(match, is_home=True),
        away_team=data_service._serialize_team(match, is_home=False),
        availability=DataAvailabilityResult(
            available=True, fresh=True, missing=[], stale=[], last_updated=None
        ),
        match=match,
    )


async def _predict_one(match_id: str, semaphore: asyncio.Semaphore) -> str:
    async with semaphore:
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                async with PooledSession() as db:
                    if await _has_existing_prediction(db, match_id):
                        return "skipped"
                    match = await _load_match(db, match_id)
                    if match is None:
                        return "missing"
                    data_service = PredictionDataService()
                    ctx = _build_context(data_service, match)
                    service = PredictionService()
                    await service.predict_match(
                        str(match_id),
                        db_session=db,
                        force_new=True,
                        include_research=False,
                        prediction_context=ctx,
                    )
                    return "generated"
            except Exception as exc:
                last_exc = exc
                logger.warning("retry %d/%d match %s: %r", attempt, 3, match_id, exc)
                await asyncio.sleep(2 * attempt)
        logger.exception("Failed match %s after retries: %s", match_id, last_exc)
        return "failed"


async def main() -> None:
    data_service = PredictionDataService()
    now = datetime.utcnow()
    month_end = now + timedelta(days=WINDOW_DAYS)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Match.id)
            .join(Season, Season.id == Match.season_id)
            .where(
                Season.is_current.is_(True),
                Match.status == FixtureStatus.SCHEDULED.value,
                Match.is_finished.is_(False),
                Match.kickoff_at >= now,
                Match.kickoff_at <= month_end,
            )
            .order_by(Match.kickoff_at)
        )
        match_ids = [str(r) for r in result.scalars().all()]

    logger.info("Found %d current-season scheduled fixtures (now -> +%dd)", len(match_ids), WINDOW_DAYS)
    total = len(match_ids)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    done = {"generated": 0, "skipped": 0, "missing": 0, "failed": 0}
    count = 0
    for match_id in match_ids:
        count += 1
        try:
            outcome = await _predict_one(match_id, semaphore)
            done[outcome] = done.get(outcome, 0) + 1
        except Exception as exc:
            done["failed"] += 1
            logger.exception("Failed match %s: %s", match_id, exc)
        if count % 25 == 0:
            logger.info("Progress %d/%d: %s", count, total, done)

    logger.info("Done. total=%d results=%s", total, done)


if __name__ == "__main__":
    asyncio.run(main())
