"""
tender.gov.mn local scraper - pushes directly to Supabase.
Run: python sync_tendergov.py
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from backend.database import init_db, upsert_tender, log_sync
from backend.scrapers.tendergov import scrape

async def main():
    print("=" * 50)
    print("  tender.gov.mn -> Supabase sync")
    print("=" * 50)

    await init_db()
    print("\nScraping tender.gov.mn...")

    try:
        items = await scrape()
        print(f"Found: {len(items)} tenders")

        count = 0
        for item in items:
            eid = item.pop("external_id", None) or item.get("name", "")[:40]
            ok = await upsert_tender("tender.gov.mn", eid, item)
            if ok:
                count += 1

        await log_sync("tender.gov.mn", "ok", count)
        print(f"Saved to Supabase: {count} tenders")

    except Exception as e:
        await log_sync("tender.gov.mn", "error", 0, str(e))
        print(f"Error: {e}")

    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())
