"""Diagnose DB connection load and long-running queries."""
import asyncio

from sqlalchemy import text

from db.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        n = (await db.execute(text("select count(*) from pg_stat_activity"))).scalar()
        print("connections:", n)
        rows = (
            await db.execute(
                text(
                    "select pid, state, now()-query_start as age, left(query,80) as q "
                    "from pg_stat_activity "
                    "where state <> 'idle' and pid <> pg_backend_pid() "
                    "order by query_start limit 15"
                )
            )
        ).fetchall()
        for r in rows:
            print(" ", r.age, r.state, "|", r.q)


asyncio.run(main())
