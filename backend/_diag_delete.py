import asyncio
import traceback
import uuid

from db.database import AsyncSessionLocal
from models.league import Team

from api.v1.endpoints.admin import delete_league, delete_team


async def main():
    from sqlalchemy import select, delete

    tid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(Team(id=tid, name="zz_diag_team"))
        await s.commit()
    print("seeded team:", tid, "exists=", end="")
    async with AsyncSessionLocal() as s2:
        print((await s2.execute(select(Team).where(Team.id == tid))).scalar_one_or_none() is not None)

    # call the route function directly (bypass transport)
    async with AsyncSessionLocal() as s3:
        try:
            res = await delete_team(tid, _admin="diag", db=s3)
            print("delete_team returned:", res)
        except Exception as e:
            print("delete_team RAISED:", repr(e))
            traceback.print_exc()
    # verify gone
    async with AsyncSessionLocal() as s4:
        row = (await s4.execute(select(Team).where(Team.id == tid))).scalar_one_or_none()
        print("still exists after delete:", row is not None)
    # cleanup if survived
    async with AsyncSessionLocal() as s5:
        await s5.execute(delete(Team).where(Team.name == "zz_diag_team"))
        await s5.commit()


if __name__ == "__main__":
    asyncio.run(main())
