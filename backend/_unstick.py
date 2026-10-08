import asyncio
import os
from core.config import Settings
import asyncpg


async def main():
    settings = Settings()
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = None
    last = None
    for attempt in range(6):
        try:
            conn = await asyncpg.connect(dsn=url, timeout=20)
            break
        except Exception as e:
            last = e
            print(f"connect attempt {attempt+1} failed: {e!r}")
            await asyncio.sleep(5)
    if conn is None:
        print("could not connect:", repr(last))
        return
    await conn.execute("SET statement_timeout = '5000'")
    me = await conn.fetchval("SELECT pg_backend_pid()")
    print("terminator pid:", me)

    rows = await conn.fetch("""
        SELECT pid, usename, state, wait_event_type, wait_event,
               EXTRACT(EPOCH FROM (now() - xact_start)) AS txn_age,
               left(query, 70) AS query
        FROM pg_stat_activity
        WHERE datname = current_database()
        ORDER BY txn_age DESC NULLS LAST
        LIMIT 40
    """)
    print("=== activity ===")
    for r in rows:
        print(dict(r))

    # Terminate stuck sessions: idle-in-transaction old, or blocked (waiting) backends,
    # excluding this one.
    targets = [
        r["pid"] for r in rows
        if r["pid"] != me
        and (
            r["state"] == "idle in transaction" and (r["txn_age"] or 0) > 5
            or r["wait_event"] is not None
        )
    ]
    print("terminating:", targets)
    for pid in targets:
        await conn.execute("SELECT pg_terminate_backend($1::int)", pid)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
