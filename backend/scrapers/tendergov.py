"""
tender.gov.mn — uses curl_cffi to mimic Chrome browser fingerprint,
bypassing Cloudflare protection.
"""
import hashlib
import json
import asyncio
from pathlib import Path
from bs4 import BeautifulSoup
from .base import parse_date_mn, clean

SOURCE = "tender.gov.mn"
COOKIES_FILE = Path(__file__).parent.parent.parent / "cookies.json"
BASE     = "https://user.tender.gov.mn"
LIST_URL = f"{BASE}/kr/invitation"

def load_cookie() -> str:
    try:
        data = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
        return data.get("tender.gov.mn", "")
    except Exception:
        return ""

def parse_cookies(cookie_str: str) -> dict:
    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies

async def scrape() -> list[dict]:
    cookie_str = load_cookie()
    if not cookie_str:
        print("[tender.gov.mn] No cookie in cookies.json")
        return []

    # Run sync curl_cffi in thread pool
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _scrape_sync, cookie_str)

def _get_deadline(session, href: str, cookies: dict) -> str:
    """Fetch tender detail page and extract 'Хүлээн авах огноо' (submission deadline)."""
    if not href:
        return ""
    try:
        r = session.get(href, cookies=cookies, timeout=15)
        if r.status_code != 200:
            return ""
        lines = BeautifulSoup(r.text, "html.parser").get_text(separator="\n", strip=True).split("\n")
        for i, line in enumerate(lines):
            if "хүлээн авах огноо" in line.lower() or "submission deadline" in line.lower():
                # Next non-empty line should be the date
                for j in range(i+1, min(i+4, len(lines))):
                    _, iso = parse_date_mn(lines[j])
                    if iso:
                        return iso
    except Exception:
        pass
    return ""


def _scrape_sync(cookie_str: str) -> list[dict]:
    try:
        from curl_cffi import requests as cf_requests
    except ImportError:
        print("[tender.gov.mn] curl_cffi not installed")
        return []

    cookies = parse_cookies(cookie_str)
    session = cf_requests.Session(impersonate="chrome")
    results = []

    for page in range(1, 6):
        try:
            resp = session.get(
                LIST_URL,
                params={"year": "2026", "page": page, "perpage": 20, "get": 1},
                cookies=cookies,
                headers={
                    "Referer": LIST_URL,
                    "Accept-Language": "mn-MN,mn;q=0.9,en;q=0.8",
                },
                timeout=30,
            )
            print(f"[tender.gov.mn] page {page} → {resp.status_code}")

            if resp.status_code == 403:
                print("[tender.gov.mn] 403 — cookie хуучирсан байж магадгүй. cookies.json шинэчилнэ.")
                break
            if resp.status_code != 200:
                break

        except Exception as e:
            print(f"[tender.gov.mn] page {page} error: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        rows = (
            soup.select("table tbody tr") or
            soup.select(".invitation-list tr") or
            soup.select("tr[class]") or
            [r for r in soup.select("tr") if len(r.select("td")) >= 3]
        )

        if not rows:
            print(f"[tender.gov.mn] page {page}: no rows found")
            print(f"[tender.gov.mn] HTML: {resp.text[:800]}")
            break

        found = 0
        for row in rows:
            cells = row.select("td")
            if len(cells) < 2:
                continue
            link = row.select_one("a")
            name = clean(link.get_text() if link else cells[0].get_text())
            if not name or len(name) < 5:
                continue

            href = ""
            if link:
                href = link.get("href", "")
                if href.startswith("/"):
                    href = BASE + href

            # Announcement date from list
            posted_iso = ""
            for cell in cells:
                txt = cell.get_text(strip=True)
                _, d_iso = parse_date_mn(txt)
                if d_iso:
                    posted_iso = d_iso
                    break

            # Fetch deadline from detail page
            deadline_iso = _get_deadline(session, href, cookies)
            label = deadline_iso
            iso = deadline_iso

            value = ""
            for cell in cells:
                txt = cell.get_text(strip=True)
                if "₮" in txt:
                    value = txt
                    break

            uid = hashlib.md5((href or name).encode()).hexdigest()[:16]
            results.append({
                "external_id": uid,
                "name": name,
                "category": "Government",
                "value": value,
                "currency": "MNT",
                "deadline": label,
                "deadline_ts": iso,
                "url": href or LIST_URL,
                "description": "",
                "status": "open",
                    "posted_at": posted_iso,
                })
            found += 1

        print(f"[tender.gov.mn] page {page}: {found} tenders")
        if found == 0:
            break

    session.close()
    return results
