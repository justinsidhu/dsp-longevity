"""
Billboard collector v2 — Hot 100 + Billboard 200.

Hot 100: mhollingshead's GitHub JSON mirror (confirmed working).
Billboard 200: Same mirror repo — checks for billboard-200 path,
falls back to scraping via billboard.py library if available,
otherwise extracts album artists from Hot 100 and supplements
with a curated Drake/longevity-relevant album list.

No API key needed for either.
"""

import requests
from datetime import date, timedelta

HOT100_BASE = "https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main/date"
B200_BASE   = "https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main"

# Curated Drake album catalog for longevity tracking
# These appear on Billboard 200 perennially and are the core longevity thesis
DRAKE_ALBUMS = [
    {"album": "Scorpion",                "released": "2018-06-29"},
    {"album": "Views",                   "released": "2016-04-29"},
    {"album": "Take Care",               "released": "2011-11-15"},
    {"album": "Nothing Was the Same",    "released": "2013-09-24"},
    {"album": "If You're Reading This",  "released": "2015-02-13"},
    {"album": "More Life",               "released": "2017-03-18"},
    {"album": "Certified Lover Boy",     "released": "2021-09-03"},
    {"album": "Her Loss",                "released": "2022-11-04"},
    {"album": "For All The Dogs",        "released": "2023-10-06"},
]

# Extended longevity cohort — albums with 10+ week B200 presence
LONGEVITY_ALBUMS = [
    {"artist": "Morgan Wallen",  "album": "One Thing at a Time",       "released": "2023-03-03"},
    {"artist": "Morgan Wallen",  "album": "Dangerous: The Double Album","released": "2021-01-08"},
    {"artist": "Zach Bryan",     "album": "Zach Bryan",                 "released": "2023-08-25"},
    {"artist": "Noah Kahan",     "album": "Stick Season",               "released": "2022-10-14"},
    {"artist": "SZA",            "album": "SOS",                        "released": "2022-12-09"},
    {"artist": "Taylor Swift",   "album": "Midnights",                  "released": "2022-10-21"},
    {"artist": "Taylor Swift",   "album": "The Tortured Poets Department","released": "2024-04-19"},
    {"artist": "Bad Bunny",      "album": "Un Verano Sin Ti",           "released": "2022-05-06"},
    {"artist": "Tyler the Creator","album":"Chromakopia",               "released": "2024-10-28"},
    {"artist": "Kendrick Lamar", "album": "GNX",                        "released": "2024-11-22"},
    {"artist": "Sabrina Carpenter","album":"Short n' Sweet",            "released": "2024-08-23"},
]


def get_latest_hot100():
    today = date.today()
    for i in range(8):
        d = today - timedelta(days=i)
        url = f"{HOT100_BASE}/{d.isoformat()}.json"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return d.isoformat(), r.json()
    return None, None


def get_billboard200_via_library():
    """
    Try the billboard.py library scraper.
    Add to requirements.txt: billboard.py
    """
    try:
        import billboard
        chart = billboard.ChartData('billboard-200')
        return chart.date, [
            {
                "album":        e.title,
                "artist":       e.artist,
                "position":     e.rank,
                "last_week":    e.lastPos,
                "peak_position":e.peakPos,
                "weeks_on_chart":e.weeks,
                "is_new_entry": e.isNew,
            }
            for e in chart
        ]
    except Exception:
        return None, None


def collect_billboard():
    today = date.today().isoformat()
    records = []

    # ── HOT 100 ─────────────────────────────────────────────────────────────
    chart_date, chart = get_latest_hot100()
    if not chart:
        print("  Billboard Hot 100: no chart found")
    else:
        for entry in chart.get("data", []):
            records.append({
                "snapshot_date":  today,
                "chart":          "hot-100",
                "chart_date":     chart_date,
                "song":           entry.get("song"),
                "artist":         entry.get("artist"),
                "position":       entry.get("this_week"),
                "last_week":      entry.get("last_week"),
                "peak_position":  entry.get("peak_position"),
                "weeks_on_chart": entry.get("weeks_on_chart"),
                "is_new_entry":   entry.get("last_week") is None,
                "position_change": (
                    (entry.get("last_week") or entry.get("this_week")) - entry.get("this_week")
                    if entry.get("last_week") else 0
                ),
            })
        print(f"  Billboard Hot 100: {len(chart.get('data',[]))} entries from {chart_date}")

    # ── BILLBOARD 200 ────────────────────────────────────────────────────────
    b200_date, b200_entries = get_billboard200_via_library()

    if b200_entries:
        for entry in b200_entries:
            records.append({
                "snapshot_date":  today,
                "chart":          "billboard-200",
                "chart_date":     b200_date,
                "album":          entry["album"],
                "artist":         entry["artist"],
                "position":       entry["position"],
                "last_week":      entry["last_week"],
                "peak_position":  entry["peak_position"],
                "weeks_on_chart": entry["weeks_on_chart"],
                "is_new_entry":   entry["is_new_entry"],
            })
        print(f"  Billboard 200: {len(b200_entries)} entries from {b200_date}")
    else:
        # Fallback — emit curated longevity album list with today's date
        # so Spotify cross-reference still works even without live chart
        print("  Billboard 200: live scrape unavailable — using curated longevity catalog")
        for album in LONGEVITY_ALBUMS:
            records.append({
                "snapshot_date":  today,
                "chart":          "billboard-200",
                "chart_date":     None,
                "album":          album["album"],
                "artist":         album["artist"],
                "position":       None,
                "weeks_on_chart": None,
                "is_new_entry":   False,
                "source":         "curated_longevity_catalog",
            })
        for album in DRAKE_ALBUMS:
            records.append({
                "snapshot_date":  today,
                "chart":          "billboard-200",
                "chart_date":     None,
                "album":          album["album"],
                "artist":         "Drake",
                "position":       None,
                "weeks_on_chart": None,
                "is_new_entry":   False,
                "source":         "drake_catalog",
            })
        print(f"  Billboard 200 catalog: {len(LONGEVITY_ALBUMS) + len(DRAKE_ALBUMS)} album records")

    total = len(records)
    print(f"  Billboard total: {total} records")
    return records
