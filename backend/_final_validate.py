import asyncio, traceback, uuid
from datetime import datetime

from db.database import AsyncSessionLocal
from sqlalchemy import select, delete, text

from models.league import League, Season, Team
from models.match import Match, Prediction
from models.research import ResearchEvidence, ResearchRun
from api.v1.endpoints.admin import delete_league, delete_team


async def exists(m, pk):
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(m).where(m.id == pk))).scalar_one_or_none() is not None


async def clean_leftovers():
    async with AsyncSessionLocal() as s:
        lids = [r async for r in (await s.stream(select(League.id).where(League.provider_league_id == "zz-league")))]
        tids = [r async for r in (await s.stream(select(Team.id).where(Team.name.like("zz_test_%"))))]
    for lid in lids:
        async with AsyncSessionLocal() as s:
            try:
                await delete_league(lid, _admin="clean", db=s)
            except Exception:
                pass
    for tid in tids:
        async with AsyncSessionLocal() as s:
            try:
                await delete_team(tid, _admin="clean", db=s)
            except Exception:
                pass


async def seed_league():
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
    return lid, sid, tid2, mid, rid, evid, pid


async def main():
    await clean_leftovers()

    # ---- Test: league -> match -> research + prediction cascade (in-process) ----
    lid, sid, tid2, mid, rid, evid, pid = await seed_league()
    async with AsyncSessionLocal() as s:
        try:
            res = await delete_league(lid, _admin="diag", db=s)
            print("delete_league ->", res)
        except Exception:
            print("delete_league RAISED")
            traceback.print_exc()
    checks = {
        "league": await exists(League, lid),
        "season": await exists(Season, sid),
        "match": await exists(Match, mid),
        "run": await exists(ResearchRun, rid),
        "evidence": await exists(ResearchEvidence, evid),
        "prediction": await exists(Prediction, pid),
        "team(leftover expected)": await exists(Team, tid2),
    }
    print("[league] residual:", checks)
    # team is intentionally not deleted by league delete; clean it now:
    async with AsyncSessionLocal() as s:
        try:
            res = await delete_team(tid2, _admin="diag", db=s)
            print("delete_team(team leftover) ->", res, "gone=", not await exists(Team, tid2))
        except Exception:
            print("delete_team leftover RAISED")
            traceback.print_exc()

    # ---- Test: team WITH a match -> match+research cascade (in-process) ----
    tid = str(uuid.uuid4())
    mid2, rid2, evid2 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    now = datetime.now()
    async with AsyncSessionLocal() as s:
        s.add(Team(id=tid, name="zz_test_team_with_match"))
        s.add(Match(id=mid2, provider_name="zztest", provider_fixture_id="zz-x2",
                    home_team_id=tid, status="scheduled"))
        await s.commit()
        s.add(ResearchRun(id=rid2, match_id=mid2, started_at=now, completed_at=now, status="ok"))
        s.add(ResearchEvidence(id=evid2, match_id=mid2, research_run_id=rid2,
                               evidence_type="injury", subject="zz", confidence=0.5))
        await s.commit()
    async with AsyncSessionLocal() as s:
        try:
            res = await delete_team(tid, _admin="diag", db=s)
            print("delete_team(with match) ->", res)
        except Exception:
            print("delete_team(with match) RAISED")
            traceback.print_exc()
    tchecks = {
        "team": await exists(Team, tid),
        "match": await exists(Match, mid2),
        "run": await exists(ResearchRun, rid2),
        "evidence": await exists(ResearchEvidence, evid2),
    }
    print("[team-with-match] residual:", tchecks)
    ok = not any(tchecks.values())
    print("ALL PASS:", ok)


if __name__ == "__main__":
    asyncio.run(main())
