"""
Wikipedia pageviews collector — free REST API, no auth needed.
Tracks daily pageviews for artist Wikipedia pages as a cultural weight signal.
"""

import requests, time
from datetime import date, timedelta

BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
HEADERS = {"User-Agent": "DSP-Longevity-Research/1.0 (research project)"}

# Artist name -> Wikipedia article title mapping
# Wikipedia titles are case-sensitive and use underscores
ARTIST_WIKI_MAP = {
    "Kendrick Lamar":   "Kendrick_Lamar",
    "Drake":            "Drake_(musician)",
    "Taylor Swift":     "Taylor_Swift",
    "Bad Bunny":        "Bad_Bunny",
    "The Weeknd":       "The_Weeknd",
    "Ariana Grande":    "Ariana_Grande",
    "Post Malone":      "Post_Malone",
    "Coldplay":         "Coldplay",
    "Billie Eilish":    "Billie_Eilish",
    "Doja Cat":         "Doja_Cat",
    "SZA":              "SZA_(singer)",
    "Tyler the Creator":"Tyler,_the_Creator",
    "Sabrina Carpenter":"Sabrina_Carpenter",
    "Olivia Rodrigo":   "Olivia_Rodrigo",
    "Morgan Wallen":    "Morgan_Wallen",
    "Peso Pluma":       "Peso_Pluma",
    "Zach Bryan":       "Zach_Bryan",
}


def get_pageviews(article, start_date, end_date):
    """Fetch daily pageviews for a Wikipedia article over a date range."""
    url = f"{BASE}/en.wikipedia/all-access/all-agents/{article}/daily/{start_date}/{end_date}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json().get("items", [])


def collect_wikipedia():
    today = date.today()
    yesterday = today - timedelta(days=1)
    start = yesterday.strftime("%Y%m%d")
    end = yesterday.strftime("%Y%m%d")
    snapshot_date = today.isoformat()

    records = []
    for artist_name, wiki_title in ARTIST_WIKI_MAP.items():
        try:
            items = get_pageviews(wiki_title, start, end)
            for item in items:
                records.append({
                    "snapshot_date": snapshot_date,
                    "pageview_date": yesterday.isoformat(),
                    "artist_name": artist_name,
                    "wiki_title": wiki_title,
                    "pageviews": item.get("views", 0),
                })
            time.sleep(0.3)
        except Exception as e:
            print(f"  Wiki error for {artist_name}: {e}")

    print(f"  Wikipedia: {len(records)} pageview records")
    return records
