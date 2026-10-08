import asyncio
import traceback
import uuid

from db.database import AsyncSessionLocal
from sqlalchemy import select, delete

from models.league import League, Season, Team
from models.match import Match, Prediction
from models.research import ResearchEvidence, ResearchRun
from api.v1.endpoints.admin import delete_league


async def main():
    async with AsyncSessionLocal() as s:
        lid = (await s.execute(select(League.id).where(League.name == "zz_test_league"))).scalar_one_or_none()
    print("lingering league id:", lid)
    if not lid:
        print("no lingering league; nothing to test")
        return
    async with AsyncSessionLocal() as s:
        try:
            res = await delete_league(lid, _admin="diag", db=s)
            print("delete_league returned:", res)
        except Exception:
            print("delete_league RAISED:")
            traceback.print_exc()
    # residuals
    async with AsyncSessionLocal() as s:
        for label, m, pk in [
            ("league", League, lid),
        ]:
            row = (await s.execute(select(m).where(m.id == pk))).scalar_one_or_none()
            print(f"residual {label}: {row is not None}")
        # count zztest matches left
        n = (await s.execute(select(Match.id).where(Match.provider_name == "zztest"))).scalars().all()
        print("residual zztest matches:", len(n))
    # final cleanup of any leftovers
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Team).where(Team.name == "zz_test_team_league"))
        await s.execute(delete(Match).where(Match.provider_name == "zztest"))
        await s.execute(delete(League).where(League.name == "zz_test_league"))
        await s.commit()


if __name__ == "__main__":
    asyncio.run(main())
