import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

_pool: asyncpg.Pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS tenders (
    id          SERIAL PRIMARY KEY,
    source      TEXT NOT NULL,
    external_id TEXT,
    name        TEXT NOT NULL,
    category    TEXT DEFAULT '',
    value       TEXT DEFAULT '',
    currency    TEXT DEFAULT '',
    deadline    TEXT DEFAULT '',
    deadline_ts TEXT DEFAULT '',
    url         TEXT DEFAULT '',
    description TEXT DEFAULT '',
    client      TEXT DEFAULT '',
    status      TEXT DEFAULT 'open',
    posted_at   TEXT DEFAULT '',
    fetched_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS sync_log (
    id         SERIAL PRIMARY KEY,
    source     TEXT NOT NULL,
    status     TEXT NOT NULL,
    count      INTEGER DEFAULT 0,
    error      TEXT DEFAULT '',
    synced_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        for stmt in CREATE_SQL.strip().split(";"):
            s = stmt.strip()
            if s:
                await conn.execute(s)
        # Migration: add client column if missing
        await conn.execute("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS client TEXT DEFAULT ''");

async def get_tenders(source: str = None, search: str = None, limit: int = 200) -> list[dict]:
    pool = await get_pool()
    clauses, params = [], []
    idx = 1
    if source and source != "all":
        clauses.append(f"source ILIKE ${idx}")
        params.append(f"%{source}%")
        idx += 1
    if search:
        clauses.append(f"(name ILIKE ${idx} OR category ILIKE ${idx+1} OR source ILIKE ${idx+2})")
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        idx += 3
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM tenders {where} ORDER BY posted_at DESC NULLS LAST, fetched_at DESC LIMIT ${idx}",
            *params
        )
    return [dict(r) for r in rows]

async def upsert_tender(source: str, external_id: str, data: dict) -> bool:
    pool = await get_pool()
    posted_at = data.pop("posted_at", "")
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO tenders (source, external_id, name, category, value, currency,
                    deadline, deadline_ts, url, description, client, status, posted_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    name=EXCLUDED.name, category=EXCLUDED.category,
                    value=EXCLUDED.value, currency=EXCLUDED.currency,
                    deadline=EXCLUDED.deadline, deadline_ts=EXCLUDED.deadline_ts,
                    url=EXCLUDED.url, description=EXCLUDED.description,
                    client=EXCLUDED.client, status=EXCLUDED.status,
                    posted_at=EXCLUDED.posted_at, fetched_at=NOW()
            """,
            source, external_id,
            data.get("name",""), data.get("category",""), data.get("value",""),
            data.get("currency",""), data.get("deadline",""), data.get("deadline_ts",""),
            data.get("url",""), data.get("description",""), data.get("client",""),
            data.get("status","open"), posted_at)
        return True
    except Exception:
        return False

async def log_sync(source: str, status: str, count: int = 0, error: str = ""):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sync_log (source, status, count, error) VALUES ($1,$2,$3,$4)",
            source, status, count, error
        )

async def get_sync_log() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT source, status, count, error, synced_at FROM sync_log ORDER BY synced_at DESC LIMIT 50"
        )
    return [dict(r) for r in rows]

async def get_stats() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM tenders")
        closing_soon = await conn.fetchval(
            "SELECT COUNT(*) FROM tenders WHERE deadline_ts <= (NOW() + INTERVAL '7 days')::date::text AND deadline_ts >= NOW()::date::text"
        )
        new_this_week = await conn.fetchval(
            "SELECT COUNT(*) FROM tenders WHERE fetched_at >= NOW() - INTERVAL '7 days'"
        )
        by_source_rows = await conn.fetch(
            "SELECT source, COUNT(*) as c FROM tenders GROUP BY source"
        )
        last_sync = await conn.fetchval(
            "SELECT MAX(synced_at) FROM sync_log WHERE status='ok'"
        )
    return {
        "total": total,
        "closing_soon": closing_soon,
        "new_this_week": new_this_week,
        "by_source": {r["source"]: r["c"] for r in by_source_rows},
        "last_sync": str(last_sync) if last_sync else None,
    }
