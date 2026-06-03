import httpx
import asyncio
from datetime import datetime, date
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "mn,en;q=0.9",
}

def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=HEADERS,
        timeout=30,
        follow_redirects=True,
        verify=False,  # some MN gov sites have cert issues
    )

def parse_date_mn(text: str) -> tuple[str, str]:
    """Return (human_label, ISO date string). Handles common Mongolian/English formats."""
    if not text:
        return "", ""
    text = text.strip()
    # ISO: 2026-06-15
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        iso = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return iso, iso
    # YYYY.MM.DD  e.g. "2026.05.25"
    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", text)
    if m:
        iso = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        return iso, iso
    # YYYY/MM/DD
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if m:
        iso = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        return iso, iso
    # DD.MM.YYYY
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        iso = f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}", iso
    # DD/MM/YYYY
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        iso = f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
        return text, iso
    # DD-Mon-YYYY e.g. "26-May-2026"
    MONTHS = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
               "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"}
    m = re.search(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", text)
    if m:
        mo = MONTHS.get(m.group(2).lower(), "")
        if mo:
            iso = f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
            return text, iso
    return text, ""

def days_left(iso_date: str) -> int:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
        return (d - date.today()).days
    except Exception:
        return 999

def clean(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.split())
