"""
Hits Daily Double collector — midweek streaming estimates.
Scrapes the public Hits Top 50 chart which is the resolution source
for Polymarket's Iceman first-week sales markets.
Gives us the industry's actual tracking number before Billboard publishes.
No API, public HTML scrape.
"""

import time, requests
from datetime import date, timedelta
from html.parser import HTMLParser

BASE = "https://www.hitsdailydouble.com/charts/hits-top-50"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


class HitsParser(HTMLParser):
    """Parse the Hits Top 50 table into records."""

    def __init__(self):
        super().__init__()
        self.records = []
        self.in_table = False
        self.current_row = []
        self.current_cell = ""
        self.cell_count = 0
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "tr":
            self.current_row = []
            self.cell_count = 0
        if tag in ("td", "th"):
            self.in_cell = True
            self.current_cell = ""
            self.cell_count += 1

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.current_row.append(self.current_cell.strip())
            self.in_cell = False
        if tag == "tr" and len(self.current_row) >= 5:
            # Row format varies — try to extract rank, artist, title, activity
            row = self.current_row
            try:
                rank = row[0].strip("#").strip()
                if rank.isdigit():
                    self.records.append({
                        "rank": int(rank),
                        "artist": row[2] if len(row) > 2 else "",
                        "title": row[3] if len(row) > 3 else "",
                        "activity": row[4] if len(row) > 4 else "",
                        "raw": row,
                    })
            except Exception:
                pass

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


def collect_hits_daily_double():
    today = date.today().isoformat()
    records = []

    try:
        r = requests.get(BASE, headers=HEADERS, timeout=20)
        r.raise_for_status()

        parser = HitsParser()
        parser.feed(r.text)

        # Also try to find the chart date from the page
        chart_date = today
        if "Chart:" in r.text:
            import re
            match = re.search(r"Chart:.*?(\d{4}-\d{2}-\d{2})", r.text)
            if match:
                chart_date = match.group(1)

        for entry in parser.records[:50]:
            records.append({
                "snapshot_date": today,
                "chart_date": chart_date,
                "rank": entry["rank"],
                "artist": entry["artist"],
                "title": entry["title"],
                "activity": entry["activity"],  # this is the streaming equivalent units
            })

        print(f"  Hits Daily Double: {len(records)} chart entries (chart date: {chart_date})")

    except Exception as e:
        print(f"  Hits Daily Double error: {e}")

    return records
