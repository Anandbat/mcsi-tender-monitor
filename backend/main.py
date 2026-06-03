import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).parent.parent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

from backend.database import init_db, get_tenders, upsert_tender, log_sync, get_sync_log, get_stats
from backend.scrapers import ALL_SCRAPERS

# ── State ──────────────────────────────────────────────────────────
sync_status: dict = {}   # source → {"running": bool, "last": str, "count": int, "error": str}
for name, _ in ALL_SCRAPERS:
    sync_status[name] = {"running": False, "last": None, "count": 0, "error": ""}

# ── Sync logic ─────────────────────────────────────────────────────
async def run_scraper(source_name: str, fn):
    if sync_status[source_name]["running"]:
        return
    sync_status[source_name]["running"] = True
    sync_status[source_name]["error"] = ""
    try:
        items = await fn()
        count = 0
        for item in items:
            eid = item.pop("external_id", None) or item.get("name", "")[:40]
            ok = await upsert_tender(source_name, eid, item)
            if ok:
                count += 1
        sync_status[source_name]["count"] = count
        sync_status[source_name]["last"] = datetime.now().strftime("%H:%M:%S")
        await log_sync(source_name, "ok", count)
        print(f"[{source_name}] synced {count} tenders")
    except Exception as e:
        err = str(e)[:200]
        sync_status[source_name]["error"] = err
        await log_sync(source_name, "error", 0, err)
        print(f"[{source_name}] ERROR: {err}")
    finally:
        sync_status[source_name]["running"] = False

async def sync_all():
    print(f"[Sync] Starting full sync at {datetime.now():%H:%M:%S}")
    tasks = [run_scraper(name, fn) for name, fn in ALL_SCRAPERS]
    await asyncio.gather(*tasks, return_exceptions=True)
    print("[Sync] Complete")

# ── Scheduler ──────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="Asia/Ulaanbaatar")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Initial sync on startup
    asyncio.create_task(sync_all())
    # Schedule every 2 hours
    scheduler.add_job(sync_all, "interval", hours=2, id="auto_sync")
    scheduler.start()
    yield
    scheduler.shutdown()

# ── App ────────────────────────────────────────────────────────────
app = FastAPI(title="MCSI Tender Monitor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────

@app.get("/api/tenders")
async def api_tenders(
    source: str = Query(None),
    search: str = Query(None),
    limit: int = Query(100),
):
    items = await get_tenders(source=source, search=search, limit=limit)
    return {"tenders": items, "count": len(items)}

@app.get("/api/stats")
async def api_stats():
    stats = await get_stats()
    sources = []
    for name, _ in ALL_SCRAPERS:
        s = sync_status.get(name, {})
        sources.append({
            "name": name,
            "live": not bool(s.get("error")),
            "running": s.get("running", False),
            "count": s.get("count", 0),
            "last": s.get("last") or "Never",
            "error": s.get("error", ""),
        })
    stats["sources"] = sources
    return stats

@app.post("/api/sync")
async def api_sync(background_tasks: BackgroundTasks, source: str = Query(None)):
    """Trigger sync — all sources or a specific one."""
    if source:
        fn_map = {name: fn for name, fn in ALL_SCRAPERS}
        if source not in fn_map:
            return JSONResponse({"error": f"Unknown source: {source}"}, status_code=404)
        background_tasks.add_task(run_scraper, source, fn_map[source])
        return {"started": [source]}
    else:
        background_tasks.add_task(sync_all)
        return {"started": [name for name, _ in ALL_SCRAPERS]}

@app.get("/api/sync/log")
async def api_sync_log():
    return {"log": await get_sync_log()}

@app.get("/api/sync/status")
async def api_sync_status():
    return {"sources": [
        {"name": k, **v} for k, v in sync_status.items()
    ]}

@app.get("/")
async def root():
    return FileResponse(ROOT / "mcsi-tender-monitor.html")

@app.get("/app")
async def app_page():
    return FileResponse(ROOT / "mcsi-tender-monitor.html")

# Serve any file from root directory (logo, images, etc.)
@app.get("/{filename:path}")
async def serve_static(filename: str):
    filepath = ROOT / filename
    if filepath.exists() and filepath.is_file():
        return FileResponse(filepath)
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": "Not found"}, status_code=404)

