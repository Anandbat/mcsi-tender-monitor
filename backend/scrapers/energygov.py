"""
Energy.gov.mn — Ministry of Energy procurement notices.
"""
import hashlib
import re
from bs4 import BeautifulSoup
from .base import make_client, parse_date_mn, clean

SOURCE = "Energy.gov.mn"
BASE = "https://energy.gov.mn"

async def scrape() -> list[dict]:
    results = []
    seen = set()

    async with make_client() as client:
        for url in [f"{BASE}/contents?type=3", f"{BASE}/posts"]:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
            except Exception as e:
                print(f"[Energy.gov.mn] error: {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Get all unique tender links
            links = soup.select('a[href*="/contents/view/iid/"]')

            for link in links:
                href = link.get("href", "")
                if not href:
                    continue
                if href.startswith("/"):
                    href = BASE + href
                if href in seen:
                    continue

                name = clean(link.get_text())
                # Skip "Дэлгэрэнгүй" (Read more) links — grab name from sibling
                if not name or len(name) < 8 or name.lower() in ["дэлгэрэнгүй", "read more", "more"]:
                    # Try to find the real title in the parent container
                    container = link.parent
                    for _ in range(4):
                        if container is None:
                            break
                        title_el = container.select_one("h2,h3,h4,h5,.title,.name,strong")
                        if title_el:
                            candidate = clean(title_el.get_text())
                            if len(candidate) > 8:
                                name = candidate
                                break
                        container = container.parent
                if not name or len(name) < 8:
                    continue

                seen.add(href)

                # Find date by walking up the DOM
                posted_text = ""
                el = link
                for _ in range(6):
                    el = el.parent
                    if not el:
                        break
                    txt = el.get_text(separator=" ", strip=True)
                    dates = re.findall(
                        r"\d{4}[./]\d{1,2}[./]\d{1,2}|"
                        r"\d{1,2}[./]\d{1,2}[./]\d{4}",
                        txt
                    )
                    if dates:
                        posted_text = dates[0]
                        break

                label, iso = parse_date_mn(posted_text)

                uid = hashlib.md5(href.encode()).hexdigest()[:16]
                results.append({
                    "external_id": uid,
                    "name": name,
                    "category": "Energy",
                    "value": "",
                    "currency": "MNT",
                    "deadline": "",
                    "deadline_ts": "",
                    "url": href,
                    "description": "",
                    "status": "open",
                    "posted_at": iso,
                })

            print(f"[Energy.gov.mn] {url}: {len(results)} items")
            if results:
                break

    return results
