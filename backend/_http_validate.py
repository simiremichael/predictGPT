"""End-to-end validation of admin deletes against the live server (HTTP)."""
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
BASE = "http://localhost:8001/api/v1"


def _call(method, path, payload=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    req.add_header("X-Admin-Api-Key", ADMIN_KEY)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(payload).encode()
    else:
        data = None
    try:
        with urllib.request.urlopen(req, data=data, timeout=45) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode() or "{}")
        except Exception:
            body = {}
        return e.code, body


async def exists(model, pk):
    async with AsyncSessionLocal() as s:
        row = await s.execute(select(model).where(model.id == pk))
        return row.scalar_one_or_none() is not None


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
    return dict(lid=lid, sid=sid, tid=tid2, mid=mid, rid=rid, evid=evid, pid=pid)


async def seed_team_with_match():
    tid, mid, rid, evid = [str(uuid.uuid4()) for _ in range(4)]
    now = datetime.now()
    async with AsyncSessionLocal() as s:
        s.add(Team(id=tid, name="zz_test_team_with_match"))
        s.add(Match(id=mid, provider_name="zztest", provider_fixture_id="zz-x2",
                    home_team_id=tid, status="scheduled"))
        await s.commit()
        s.add(ResearchRun(id=rid, match_id=mid, started_at=now, completed_at=now, status="ok"))
        s.add(ResearchEvidence(id=evid, match_id=mid, research_run_id=rid,
                               evidence_type="injury", subject="zz", confidence=0.5))
        await s.commit()
    return dict(tid=tid, mid=mid, rid=rid, evid=evid)


async def main():
    # 0) sanity: missing league -> 404
    st, body = _call("DELETE", "/admin/leagues/does-not-exist")
    print(f"[sanity 404] status={st} body={body}")
    assert st == 404, "expected 404 for missing league"

    # 1) league -> match -> research + prediction cascade
    d = await seed_league()
    st, body = _call("DELETE", f"/admin/leagues/{d['lid']}")
    checks = {k: await exists(m, d[k]) for k, m in [
        ("lid", League), ("sid", Season), ("mid", Match),
        ("rid", ResearchRun), ("evid", ResearchEvidence), ("pid", Prediction)]}
    print(f"[league] status={st} gone={ {k: not v for k, v in checks.items()} } body={body}")

    # 2) team with match -> match + research cascade
    d2 = await seed_team_with_match()
    st2, body2 = _call("DELETE", f"/admin/teams/{d2['tid']}")
    checks2 = {k: await exists(m, d2[k]) for k, m in [
        ("tid", Team), ("mid", Match), ("rid", ResearchRun), ("evid", ResearchEvidence)]}
    print(f"[team-match] status={st2} gone={ {k: not v for k, v in checks2.items()} } body={body2}")

    # 3) bare team
    tid3 = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(Team(id=tid3, name="zz_test_bare_team"))
        await s.commit()
    st3, body3 = _call("DELETE", f"/admin/teams/{tid3}")
    gone3 = not await exists(Team, tid3)
    print(f"[team-bare] status={st3} gone={gone3} body={body3}")

    ok = (st == 200 and not any(checks.values())
          and st2 == 200 and not any(checks2.values())
          and st3 == 200 and gone3)
    print("ALL PASS:", ok)


if __name__ == "__main__":
    asyncio.run(main())
