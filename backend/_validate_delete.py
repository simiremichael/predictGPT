"""Validate admin deletes end-to-end against the live server (admin API key)."""
import asyncio
import json
import urllib.request
import urllib.error
import uuid
from datetime import datetime

from db.database import AsyncSessionLocal
from sqlalchemy import select

from models.league import League, Season, Team
from models.match import Match, Prediction
from models.research import ResearchEvidence, ResearchRun

ADMIN_KEY = "set_a_strong_admin_key_here"
BASE = "http://localhost:8000/api/v1"


def _del(path: str):
    req = urllib.request.Request(f"{BASE}{path}", method="DELETE")
    req.add_header("X-Admin-Api-Key", ADMIN_KEY)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


async def exists(model, pk):
    async with AsyncSessionLocal() as s:
        row = await s.execute(select(model).where(model.id == pk))
        return row.scalar_one_or_none() is not None


async def cleanup_zz():
    async with AsyncSessionLocal() as s:
        league_ids = [r for r in (await s.execute(
            select(League.id).where(League.provider_league_id == "zz-league")))
            .scalars().all()]
        team_ids = [r for r in (await s.execute(
            select(Team.id).where(Team.name.like("zz_test_%"))))
            .scalars().all()]
    for lid in league_ids:
        _del(f"/admin/leagues/{lid}")
    for tid in team_ids:
        _del(f"/admin/teams/{tid}")


async def main():
    await cleanup_zz()

    # ---- Test 1: bare team ----
    tid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(Team(id=tid, name="zz_test_delete_team"))
        await s.commit()
    st, body = _del(f"/admin/teams/{tid}")
    gone = not await exists(Team, tid)
    print(f"[team-only] status={st} gone={gone} body={body}")
    print("[team-only] RESULT:", "PASS" if (st == 200 and gone) else "FAIL")

    # ---- Test 2: league -> match -> research + prediction ----
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

    st2, body2 = _del(f"/admin/leagues/{lid}")
    checks = {
        "league": await exists(League, lid),
        "season": await exists(Season, sid),
        "match": await exists(Match, mid),
        "research_run": await exists(ResearchRun, rid),
        "evidence": await exists(ResearchEvidence, evid),
        "prediction": await exists(Prediction, pid),
    }
    print(f"[league] status={st2} gone={ {k: not v for k, v in checks.items()} } body={body2}")
    print("[league] RESULT:", "PASS" if (st2 == 200 and not any(checks.values())) else "FAIL")

    await cleanup_zz()


if __name__ == "__main__":
    asyncio.run(main())
