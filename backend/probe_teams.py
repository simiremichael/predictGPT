import asyncio
import sys

sys.path.insert(0, "app")

from sqlalchemy import func, select

from api.v1.endpoints.providers import _read_db_resource_payload, _save_teams
from db.database import AsyncSessionLocal
from models.league import ProviderTeam, Team

TEAMS = [
    {"id": "9001", "name": "Arsenal", "short_name": "ARS", "country": "England"},
    {"id": "9002", "name": "Chelsea", "short_name": "CHE", "country": "England"},
    {"id": "9003", "name": "Brighton", "short_name": "BHA", "country": "England"},
]


async def provider_rows() -> int:
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(func.count()).select_from(ProviderTeam))).scalar() or 0


async def main() -> None:
    # unfiltered fetch: no league_id / season_id, exactly what /providers/teams sends
    for round_no in (1, 2, 3):
        async with AsyncSessionLocal() as db:
            await _save_teams(db, [dict(t, provider="sportmonks") for t in TEAMS])
            await db.commit()
        print(f"after _save_teams round {round_no}: provider_teams rows = {await provider_rows()}")

    async with AsyncSessionLocal() as db:
        n = (await db.execute(select(func.count()).select_from(Team))).scalar() or 0
        print("teams rows:", n)
        await db.execute(ProviderTeam.__table__.delete())
        for t in TEAMS:
            await db.delete(await db.get(Team, t["id"]))
        await db.commit()
    print("cleaned up")

    for label, kw in [
        ("all teams", {}),
        ("search=ars", {"search": "ars"}),
        ("search=CHE", {"search": "CHE"}),
        ("is_active=true", {"is_active": True}),
        ("page_size=2 p1", {"page": 1, "page_size": 2}),
        ("page_size=2 p2", {"page": 2, "page_size": 2}),
    ]:
        out = await _read_db_resource_payload("get_teams", **kw)
        print(
            f"{label:18s} total={out['meta']['total']} "
            f"page={out['meta']['page']}/{out['meta']['total_pages']} "
            f"-> {[r['name'] for r in out['data']]}"
        )


asyncio.run(main())
