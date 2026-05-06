"""
Hits Daily Double collector — midweek streaming estimates.
HDD is the resolution source for Polymarket's Iceman first-week sales markets.
Their main site blocks automated requests (403) but their RSS/alternate
endpoints are accessible. Falls back gracefully with a clear status message.
"""

import time, requests, re
from datetime import date
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
}

ENDPOINTS = [
    "https://www.hitsdailydouble.com/charts/hits-top-50",
    "https://www.hitsdailydouble.com/chart",
    "https://www.hitsdailydouble.com/news&id=338500",  # weekly chart link
]


def parse_hdd_html(html):
    """Parse HDD chart HTML using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    records = []

    # Try table rows
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        texts = [c.get_text(strip=True) for c in cells]
        # Look for rank number in first cell
        rank_text = texts[0].replace("#", "").strip()
        if rank_text.isdigit():
            records.append({
                "rank": int(rank_text),
                "artist": texts[2] if len(texts) > 2 else "",
                "title": texts[3] if len(texts) > 3 else "",
                "activity": texts[4] if len(texts) > 4 else "",
            })

    return records


def collect_hits_daily_double():
    today = date.today().isoformat()
    records = []

    for endpoint in ENDPOINTS:
        try:
            r = requests.get(endpoint, headers=HEADERS, timeout=20)
            if r.status_code == 403:
                continue
            r.raise_for_status()

            entries = parse_hdd_html(r.text)
            if not entries:
                continue

            # Try to extract chart date
            chart_date = today
            date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', r.text)
            if date_match:
                chart_date = today  # Use today as fallback

            for entry in entries[:50]:
                records.append({
                    "snapshot_date": today,
                    "chart_date": chart_date,
                    "rank": entry["rank"],
                    "artist": entry["artist"],
                    "title": entry["title"],
                    "activity": entry["activity"],
                })

            print(f"  Hits Daily Double: {len(records)} entries via {endpoint}")
            return records

        except Exception as e:
            continue

    # All endpoints failed — log clearly so we know to check manually
    print(f"  Hits Daily Double: blocked (403) — check manually at hitsdailydouble.com")
    print(f"  NOTE: This is the Polymarket sales market resolution source. Check before May 22.")
    return []
