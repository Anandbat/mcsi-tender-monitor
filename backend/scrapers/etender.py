"""
e-tender.mn — Mongolia official e-procurement portal.
Tries multiple URL patterns to find active tenders.
"""
import hashlib
from bs4 import BeautifulSoup
from .base import make_client, parse_date_mn, clean

SOURCE = "e-tender.mn"
BASE_URL = "https://www.e-tender.mn"

CANDIDATE_URLS = [
    f"{BASE_URL}/mn/tender",
    f"{BASE_URL}/tender",
    f"{BASE_URL}/mn/tenders",
    f"{BASE_URL}/mn",
    BASE_URL,
]

async def scrape() -> list[dict]:
    results = []
    async with make_client() as client:
        html = None
        for url in CANDIDATE_URLS:
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.text) > 1000:
                    html = resp.text
                    print(f"[e-tender.mn] loaded: {url}")
                    break
            except Exception as e:
                print(f"[e-tender.mn] {url}: {e}")

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")

        rows = (
            soup.select("table.tender-list tbody tr") or
            soup.select("table tbody tr") or
            soup.select(".tender-item, .tender-row, .list-group-item") or
            soup.select("tr[data-id]") or
            [r for r in soup.select("table tr") if len(r.select("td")) >= 3]
        )

        for row in rows:
            cells = row.select("td")
            link = row.select_one("a")
            name = clean(link.get_text() if link else (cells[1].get_text() if len(cells) > 1 else ""))
            if not name or len(name) < 5:
                continue

            href = ""
            if link:
                href = link.get("href", "")
                if href.startswith("/"):
                    href = BASE_URL + href

            date_text = ""
            for cell in cells:
                txt = cell.get_text(strip=True)
                if any(c in txt for c in [".", "/"]) and any(c.isdigit() for c in txt) and len(txt) < 20:
                    date_text = txt
                    break

            label, iso = parse_date_mn(date_text)

            value = ""
            for cell in cells:
                txt = cell.get_text(strip=True)
                if "₮" in txt or "MNT" in txt or "сая" in txt:
                    value = txt
                    break

            uid = hashlib.md5((href or name).encode()).hexdigest()[:16]
            results.append({
                "external_id": uid,
                "name": name,
                "category": "General",
                "value": value,
                "currency": "MNT",
                "deadline": label,
                "deadline_ts": iso,
                "url": href or BASE_URL,
                "description": "",
                "status": "open",
                    "posted_at": "",
                })

    return results
