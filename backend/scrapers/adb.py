"""
ADB — SearchStax API, Mongolia tenders with active closing dates only.
Discovered from: https://www.adb.org/projects/tenders
"""
import hashlib, os
from datetime import date
from .base import make_client, parse_date_mn, clean

SOURCE = "ADB"
BASE = "https://www.adb.org"

SOLR_URL = "https://searchcloud-2-ap-southeast-1.searchstax.com/29847/tenders-11959/emselect"
SEARCH_AUTH = os.environ.get("ADB_SEARCH_TOKEN", "")

async def scrape() -> list[dict]:
    today = date.today().isoformat()
    params = {
        "q": "*",
        "start": 0,
        "rows": 50,
        # Only Mongolia, only tenders with closing date >= today
        "fq": [
            "sm_fct_country:Mongolia",
            f"ds_date_closing:[{today}T00:00:00Z TO *]",
        ],
        "sort": "ds_date_closing asc",
        "model": "Default",
        "language": "en",
        "wt": "json",
    }
    auth_headers = {
        "Authorization": f"Token {SEARCH_AUTH}",
        "Accept": "application/json",
        "Origin": "https://www.adb.org",
        "Referer": "https://www.adb.org/projects/tenders",
    }

    results = []
    async with make_client() as client:
        start = 0
        while True:
            params["start"] = start
            try:
                resp = await client.get(SOLR_URL, params=params, headers=auth_headers)
                print(f"[ADB] start={start} → {resp.status_code}")
                if resp.status_code == 401:
                    print("[ADB] SearchStax token expired")
                    break
                if resp.status_code != 200:
                    break
                data = resp.json()
            except Exception as e:
                print(f"[ADB] error: {e}")
                break

            docs = data.get("response", {}).get("docs", [])
            print(f"[ADB] {len(docs)} docs")
            if not docs:
                break

            for doc in docs:
                # Title field varies by document version
                name = clean(
                    doc.get("tm_X3b_en_title", [""])[0] or
                    doc.get("ss_title") or
                    doc.get("title") or ""
                )
                if not name:
                    continue

                dl = doc.get("ds_date_closing") or doc.get("ds_date_posted") or ""
                label, iso = parse_date_mn(str(dl)[:10])

                path = doc.get("ss_url") or ""
                href = (BASE + path) if path.startswith("/") else path

                sector = ""
                raw = (doc.get("tm_X3b_en_sector") or
                       doc.get("sm_fct_sector") or [])
                if isinstance(raw, list) and raw:
                    sector = raw[0]

                tender_type = ""
                raw_type = doc.get("tm_X3b_en_type") or []
                if isinstance(raw_type, list) and raw_type:
                    tender_type = raw_type[0]

                posted_raw = doc.get("ds_date_posted") or ""
                _, posted_iso = parse_date_mn(str(posted_raw)[:10])

                executing_agency = ""
                raw_ea = doc.get("sm_fct_executing_agency") or doc.get("tm_X3b_en_executing_agency") or []
                if isinstance(raw_ea, list) and raw_ea:
                    executing_agency = raw_ea[0]
                elif isinstance(raw_ea, str):
                    executing_agency = raw_ea

                uid = hashlib.md5((href or name).encode()).hexdigest()[:16]
                results.append({
                    "external_id": uid,
                    "name": name,
                    "category": clean(sector) or "Infrastructure",
                    "value": "",
                    "currency": "USD",
                    "deadline": label,
                    "deadline_ts": iso,
                    "url": href or f"{BASE}/projects/tenders",
                    "description": clean(tender_type),
                    "client": clean(executing_agency),
                    "status": "open",
                    "posted_at": posted_iso,
                })

            total = data.get("response", {}).get("numFound", 0)
            start += len(docs)
            if start >= total or start >= 200:
                break

    print(f"[ADB] {len(results)} active Mongolia tenders")
    return results
