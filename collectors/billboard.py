"""
Billboard collector — pulls Hot 100 from mhollingshead's GitHub mirror.
Updated daily, no API key needed, completely free.
https://github.com/mhollingshead/billboard-hot-100
"""

import requests
from datetime import date, timedelta


BASE = "https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main/date"


def get_latest_chart():
    """
    Billboard publishes on Saturdays. Try today and walk back
    up to 7 days to find the most recent chart.
    """
    today = date.today()
    for i in range(8):
        d = today - timedelta(days=i)
        url = f"{BASE}/{d.isoformat()}.json"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return d.isoformat(), r.json()
    return None, None


def collect_billboard():
    today = date.today().isoformat()
    chart_date, chart = get_latest_chart()
    if not chart:
        print("  Billboard: no chart found")
        return []

    records = []
    for entry in chart.get("data", []):
        records.append({
            "snapshot_date": today,
            "chart_date": chart_date,
            "song": entry.get("song"),
            "artist": entry.get("artist"),
            "position": entry.get("this_week"),
            "last_week": entry.get("last_week"),
            "peak_position": entry.get("peak_position"),
            "weeks_on_chart": entry.get("weeks_on_chart"),
            # Derived longevity signals
            "is_new_entry": entry.get("last_week") is None,
            "position_change": (
                (entry.get("last_week") or entry.get("this_week")) - entry.get("this_week")
                if entry.get("last_week") else 0
            ),
        })
    print(f"  Billboard: {len(records)} entries from chart dated {chart_date}")
    return records
