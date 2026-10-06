"""Smoke-test: generate one prediction end-to-end (no research/AI)."""
import asyncio
import logging
import traceback

from dotenv import load_dotenv
from sqlalchemy import select

from db.database import AsyncSessionLocal
from models.match import Match
from services.prediction_orchestrator import PredictionOrchestrator

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        mid = (await db.execute(select(Match.id).limit(1))).scalar()
        print("match_id:", mid)
        orch = PredictionOrchestrator()
        try:
            out = await orch.generate_prediction(
                mid, db_session=db, force_refresh=True, include_research=False
            )
            print(
                "OK prediction_id=%s model=%s confidence=%s data_quality=%s"
                % (out.prediction_id, out.model, out.confidence, out.data_quality),
                flush=True,
            )
        except Exception as e:
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
