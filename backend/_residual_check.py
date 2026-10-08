import asyncio, traceback, uuid
from datetime import datetime
from sqlalchemy import select, text, delete
from db.database import AsyncSessionLocal, engine
from models.league import League, Season, Team
from models.match import Match, Prediction
from models.research import ResearchEvidence, ResearchRun
from api.v1.endpoints.admin import delete_league


async def exists(m, pk):
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(m).where(m.id == pk))).scalar_one_or_none() is not None


async def main():
    # connectivity probe with hard timeout
    from sqlalchemy import select as sel
    async with AsyncSessionLocal() as s:
        await s.execute(text("SET statement_timeout = '10s'"))
        r = (await s.execute(sel(text("1")))).scalar()
        print("connectivity probe:", r)

    lid, sid, tid2, mid, rid, evid, pid = [str(uuid.uuid4()) for _ in range(7)]
    now = datetime.now()
    async with AsyncSessionLocal() as s:
        await s.execute(text("SET statement_timeout = '15s'"))
        s.add(League(id=lid, name="zz_test_league", provider_league_id="zz-league"))
        await s.flush()
        s.add(Season(id=sid, league_id=lid, name="zz-season", is_current=True))
        s.add(Team(id=tid2, name="zz_test_team_league"))
        s.add(Match(id=mid, provider_name="zztest", provider_fixture_id="zz-fx",
                    league_id=lid, season_id=sid, home_team_id=tid2))
        await s.commit()
        s.add(ResearchRun(id=rid, match_id=mid, started_at=now, completed_at=now, status="ok"))
        await s.commit()
        s.add(ResearchEvidence(id=evid, match_id=mid, research_run_id=rid,
                               evidence_type="injury", subject="zz", confidence=0.5))
        s.add(Prediction(id=pid, match_id=mid, model_version="test", provider_used="zztest"))
        await s.commit()

    async with AsyncSessionLocal() as s:
        await s.execute(text("SET statement_timeout = '20s'"))
        try:
            res = await delete_league(lid, _admin="diag", db=s)
            print("delete_league ->", res)
        except Exception:
            print("delete_league RAISED:")
            traceback.print_exc()

    checks = {
        "league": await exists(League, lid),
        "season": await exists(Season, sid),
        "match": await exists(Match, mid),
        "run": await exists(ResearchRun, rid),
        "evidence": await exists(ResearchEvidence, evid),
        "prediction": await exists(Prediction, pid),
    }
    print("[league-cascade] residual (all should be False):", checks)
    print("RESULT:", "PASS" if not any(checks.values()) else "FAIL")

    # cleanup any leftovers (FK-safe order)
    async with AsyncSessionLocal() as s:
        await s.execute(text("SET statement_timeout = '10s'"))
        await s.execute(delete(ResearchEvidence).where(ResearchEvidence.id == evid))
        await s.execute(delete(ResearchRun).where(ResearchRun.id == rid))
        await s.execute(delete(Prediction).where(Prediction.id == pid))
        await s.execute(delete(Match).where(Match.id == mid))
        await s.execute(delete(Season).where(Season.id == sid))
        await s.execute(delete(Team).where(Team.id == tid2))
        await s.execute(delete(League).where(League.id == lid))
        await s.commit()


if __name__ == "__main__":
    asyncio.run(main())
