"""
tender.mn — private Mongolian tender aggregator.
"""
import hashlib
from bs4 import BeautifulSoup
from .base import make_client, parse_date_mn, clean

SOURCE = "tender.mn"

CANDIDATE_URLS = [
    "https://tender.mn",
    "https://www.tender.mn",
    "https://tender.mn/tenders",
    "https://tender.mn/list",
]

async def scrape() -> list[dict]:
    results = []
    async with make_client() as client:
        html = None
        base = "https://tender.mn"
        for url in CANDIDATE_URLS:
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.text) > 500:
                    html = resp.text
                    base = "/".join(url.split("/")[:3])
                    break
            except Exception as e:
                print(f"[tender.mn] {url}: {e}")

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        rows = (
            soup.select(".tender-card, .tender-item, .card") or
            soup.select("article") or
            soup.select("table tbody tr") or
            [r for r in soup.select("li") if r.select_one("a")]
        )

        for row in rows:
            link = row.select_one("a")
            name = clean(link.get_text() if link else row.get_text())
            if not name or len(name) < 5:
                continue

            href = ""
            if link:
                href = link.get("href", "")
                if href.startswith("/"):
                    href = base + href

            date_el = row.select_one(".deadline, .date, .expires, time, .end-date")
            date_text = date_el.get_text(strip=True) if date_el else ""
            label, iso = parse_date_mn(date_text)

            uid = hashlib.md5((href or name).encode()).hexdigest()[:16]
            results.append({
                "external_id": uid,
                "name": name,
                "category": "General",
                "value": "",
                "currency": "MNT",
                "deadline": label,
                "deadline_ts": iso,
                "url": href or base,
                "description": "",
                "status": "open",
                    "posted_at": "",
                })

    return results
