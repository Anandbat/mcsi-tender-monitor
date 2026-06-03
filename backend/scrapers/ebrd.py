"""
EBRD — Mongolia procurement notices via ecepp.ebrd.com.
Table columns: [0]=name [1]=type [3]=posted [4]=deadline [5]=status [6]=posted-date
"""
import hashlib
from bs4 import BeautifulSoup
from .base import make_client, parse_date_mn, clean

SOURCE = "EBRD"
BASE = "https://ecepp.ebrd.com"

NON_MN = [
    'romania','slovakia','bosnia','macedonia','serbia','ukraine','albania',
    'armenia','georgia','kazakhstan','uzbekistan','kyrgyz','tajik','moldova',
    'belarus','latvia','estonia','lithuania','poland','hungary','czech',
    'bulgaria','croatia','kosovo','montenegro','azerbaijan','russia',
    'turkey','egypt','morocco','tunisia','jordan','lebanon','west bank',
    'iraq','pakistan','bangladesh','india','china','vietnam','indonesia',
    'nigeria','ghana','kenya','ethiopia','tanzania','zambia','mozambique',
    'senegal','cameroon','rwanda','uganda','zimbabwe','namibia','botswana',
    'philippines','myanmar','cambodia','thailand','malaysia','sri lanka',
    'nepal','tajikistan','uzbek','kyrgyz','afghanistan',
]

async def scrape() -> list[dict]:
    results = []
    async with make_client() as client:
        for params in [
            {"country": "MN", "status": "OPEN"},
            {"country": "MN"},
            {"country": "Mongolia", "status": "OPEN"},
        ]:
            try:
                url = f"{BASE}/delta/noticeSearchResults.html"
                resp = await client.get(url, params=params)
                print(f"[EBRD] {params} → {resp.status_code} ({len(resp.text)} bytes)")
                if resp.status_code != 200 or len(resp.text) < 1000:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                rows = (
                    soup.select("table tbody tr") or
                    [r for r in soup.select("tr") if len(r.select("td")) >= 2]
                )
                print(f"[EBRD] rows found: {len(rows)}")

                for row in rows:
                    cells = row.select("td")
                    if len(cells) < 5:
                        continue
                    link = row.select_one("a")
                    name = clean(link.get_text() if link else cells[0].get_text())
                    if not name or len(name) < 5:
                        continue
                    if any(c in name.lower() for c in NON_MN):
                        continue

                    # Type from cell[1]
                    notice_type = clean(cells[1].get_text()) if len(cells) > 1 else ""

                    # Deadline from cell[4] — "09/07/2026 11:00UK Time" or "N/A"
                    dl_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    if dl_text.upper() == "N/A" or not dl_text:
                        dl_text = ""
                    # Strip time part "11:00UK Time"
                    dl_date = dl_text.split(" ")[0] if dl_text else ""
                    label, iso = parse_date_mn(dl_date)

                    href = ""
                    if link:
                        href = link.get("href", "")
                        if href.startswith("http"):
                            pass  # already absolute
                        elif href.startswith("/"):
                            href = BASE + href
                        elif href:
                            # relative path like "viewNotice.html?..."
                            href = BASE + "/delta/" + href

                    posted_text = cells[6].get_text(strip=True) if len(cells) > 6 else ""
                    _, posted_iso = parse_date_mn(posted_text.split(" ")[0])

                    uid = hashlib.md5((href or name).encode()).hexdigest()[:16]
                    results.append({
                        "external_id": uid,
                        "name": name,
                        "category": notice_type or "General",
                        "value": "",
                        "currency": "EUR",
                        "deadline": label,
                        "deadline_ts": iso,
                        "url": href or url,
                        "description": "",
                        "status": "open",
                        "posted_at": posted_iso,
                    })

                if results:
                    print(f"[EBRD] {len(results)} Mongolia notices")
                    return results
            except Exception as e:
                print(f"[EBRD] error: {e}")

    print(f"[EBRD] 0 notices found")
    return results
