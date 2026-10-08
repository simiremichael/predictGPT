import asyncio
import traceback
import uuid
from datetime import datetime, timedelta

from db.database import AsyncSessionLocal, engine
from sqlalchemy import select, text, delete

from models.league import League, Season, Team
from models.match import Match, Prediction
from models.research import ResearchEvidence, ResearchRun
from api.v1.endpoints.admin import delete_league


async def blocked_sessions():
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "SELECT pid, usename, state, wait_event_type, query, state_change "
            "FROM pg_stat_activity WHERE datname = current_database() "
            "ORDER BY state_change LIMIT 25"
        ))).fetchall()
    for r in rows:
        print("  pid=%s state=%s wait=%s q=(%s) since=%s" % (
            r[0], r[2], r[3], (r[4] or "")[:80], r[5]))


async def main():
    print("=== DB sessions before ===")
    await blocked_sessions()

    lid, sid, tid2, mid, rid, evid, pid = [str(uuid.uuid4()) for _ in range(7)]
    now = datetime.now()
    async with AsyncSessionLocal() as s:
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
    print("seeded:", lid)

    async with AsyncSessionLocal() as s:
        try:
            await asyncio.wait_for(delete_league(lid, _admin="diag", db=s), timeout=20)
            print("delete_league OK")
        except asyncio.TimeoutError:
            print("delete_league HUNG >20s; traceback:")
            # the running coroutine is now abandoned; print stack of the task
            try:
                await asyncio.wait_for(delete_league(lid, _admin="diag", db=s), timeout=5)
            except asyncio.TimeoutError:
                pass
        except Exception:
            print("delete_league RAISED:")
            traceback.print_exc()

    print("=== DB sessions after ===")
    await blocked_sessions()

    # cleanup
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Team).where(Team.name == "zz_test_team_league"))
        await s.execute(delete(Match).where(Match.provider_name == "zztest"))
        await s.execute(delete(League).where(League.id == lid))
        await s.commit()


if __name__ == "__main__":
    asyncio.run(main())
