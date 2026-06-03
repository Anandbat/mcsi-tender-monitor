"""
World Bank — procurement notices for Mongolia.
API: https://search.worldbank.org/api/v2/procnotices
Correct filter: project_ctry_name=Mongolia
Correct fields: bid_description, submission_deadline_date, notice_type, id
"""
import hashlib
from .base import make_client, parse_date_mn, clean

SOURCE = "World Bank"

API_URL = "https://search.worldbank.org/api/v2/procnotices"

async def scrape() -> list[dict]:
    results = []
    async with make_client() as client:
        page = 1
        seen = set()
        while len(results) < 200:
            params = {
                "project_ctry_name": "Mongolia",
                "format": "json",
                "rows": 50,
                "os": (page - 1) * 50,
            }
            try:
                resp = await client.get(API_URL, params=params)
                print(f"[World Bank] page={page} → {resp.status_code}")
                if resp.status_code != 200:
                    break
                data = resp.json()
            except Exception as e:
                print(f"[World Bank] error: {e}")
                break

            notices = data.get("procnotices", [])
            if not isinstance(notices, list) or not notices:
                break

            print(f"[World Bank] {len(notices)} notices (total={data.get('total')})")

            for item in notices:
                if not isinstance(item, dict):
                    continue
                name = clean(
                    item.get("bid_description") or
                    item.get("project_name") or
                    item.get("noticeTitle") or ""
                )
                if not name:
                    continue

                dl = (
                    item.get("submission_deadline_date") or
                    item.get("deadlineDate") or
                    item.get("closingDate") or
                    item.get("noticedate") or ""
                )
                label, iso = parse_date_mn(str(dl))

                notice_id = str(item.get("id") or "")
                if notice_id in seen:
                    continue
                seen.add(notice_id)

                uid = hashlib.md5(notice_id.encode() if notice_id else name.encode()).hexdigest()[:16]
                url_link = (
                    f"https://projects.worldbank.org/en/projects-operations/procurement/noticedetail/{notice_id}"
                    if notice_id else
                    "https://projects.worldbank.org/en/projects-operations/procurement-notices"
                )

                posted_raw = item.get("noticedate") or item.get("submission_date") or ""
                _, posted_iso = parse_date_mn(str(posted_raw))

                results.append({
                    "external_id": uid,
                    "name": name,
                    "category": clean(item.get("notice_type") or item.get("procurement_method_name") or "Development"),
                    "value": str(item.get("totalContractAmount") or ""),
                    "currency": "USD",
                    "deadline": label,
                    "deadline_ts": iso,
                    "url": url_link,
                    "description": clean(item.get("project_name") or ""),
                    "status": "open",
                    "posted_at": posted_iso,
                })

            total = int(data.get("total", 0))
            if page * 50 >= total or page * 50 >= 200:
                break
            page += 1

    print(f"[World Bank] {len(results)} Mongolia tenders")
    return results
