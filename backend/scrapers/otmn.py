"""
OT.mn — Oyu Tolgoi procurement via WordPress REST API.
Backend: https://admin.ot.mn/wp-json/wp/v2/tender  (EOI)
         https://admin.ot.mn/wp-json/wp/v2/tender-ump  (UMP)
Fetches both EN and MN language posts, deduplicates by slug.
"""
import hashlib
import html as html_mod
import re
from .base import make_client, parse_date_mn, clean

SOURCE = "OT.mn / OASIS"

WP_BASE = "https://admin.ot.mn/wp-json/wp/v2"
ENDPOINTS = [
    (f"{WP_BASE}/tender", "EOI"),
    (f"{WP_BASE}/tender-ump", "UMP"),
]


def _fix_title(raw: str) -> str:
    """Decode HTML entities and fix any encoding issues."""
    text = html_mod.unescape(raw)
    # Try to fix Latin-1 misread UTF-8 (common with some WP setups)
    try:
        fixed = text.encode("latin-1").decode("utf-8")
        return clean(fixed)
    except (UnicodeEncodeError, UnicodeDecodeError):
        return clean(text)


def _extract_deadline(content_html: str) -> tuple[str, str]:
    """Only extract deadline when content explicitly labels it as such."""
    text = re.sub(r"<[^>]+>", " ", content_html)
    # Only match when preceded by a deadline keyword — avoids picking up posted dates
    patterns = [
        r"(?:deadline|хаалтын огноо|closing date|submission deadline|дуусах хугацаа)[^\d]{0,40}(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})",
        r"(?:deadline|хаалтын огноо|closing date|submission deadline|дуусах хугацаа)[^\d]{0,40}(\d{4}[.\-/]\d{2}[.\-/]\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return parse_date_mn(m.group(1))
    return "", ""


async def scrape() -> list[dict]:
    from datetime import date, timedelta
    # Only keep posts from last 3 years (OT.mn updates ~quarterly)
    cutoff_date = (date.today() - timedelta(days=1095)).isoformat()

    results = []
    seen_slugs = set()

    async with make_client() as client:
        for endpoint, category in ENDPOINTS:
            for lang in ["en", "mn"]:
                page = 1
                while True:
                    try:
                        params = {
                            "per_page": 50,
                            "status": "publish",
                            "page": page,
                            "orderby": "date",
                            "order": "desc",
                            "lang": lang,
                        }
                        resp = await client.get(endpoint, params=params)
                        if resp.status_code != 200:
                            break
                        items = resp.json()
                        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
                    except Exception as e:
                        print(f"[OT.mn] {lang} error: {e}")
                        break

                    if not items:
                        break

                    # If oldest post on this page is before cutoff, stop after this page
                    oldest_date = items[-1].get("date", "")[:10]
                    stop_after_page = oldest_date < cutoff_date

                    for item in items:
                        wp_date_check = item.get("date", "")[:10]
                        if wp_date_check < cutoff_date:
                            continue  # skip old posts

                        slug = item.get("slug", "") or str(item.get("id", ""))
                        # English version takes priority; skip if EN slug already added
                        if lang == "mn":
                            # Use translation slug to deduplicate
                            en_slug = slug.replace("-mn", "").replace("_mn", "")
                            if en_slug in seen_slugs or slug in seen_slugs:
                                continue

                        if slug in seen_slugs:
                            continue
                        seen_slugs.add(slug)

                        raw_title = item.get("title", {}).get("rendered", "")
                        name = _fix_title(raw_title)
                        if not name or len(name) < 5:
                            continue

                        content = item.get("content", {}).get("rendered", "")
                        label, iso = _extract_deadline(content)

                        link = item.get("link", "") or "https://www.ot.mn/mn/procurement/eoi"
                        # WordPress post date as actual published date
                        wp_date = item.get("date", "")[:10]

                        uid = hashlib.md5(slug.encode()).hexdigest()[:16]
                        results.append({
                            "external_id": uid,
                            "name": name,
                            "category": f"Mining / {category}",
                            "value": "",
                            "currency": "USD",
                            "deadline": label,
                            "deadline_ts": iso,
                            "url": link,
                            "description": "",
                            "status": "open",
                            "posted_at": wp_date,
                        })

                    if stop_after_page or page >= total_pages or page >= 6:
                        break
                    page += 1

    print(f"[OT.mn] {len(results)} tenders")
    return results
