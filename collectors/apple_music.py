"""
Apple Music collector — daily top charts from Apple Music JSON endpoint.
No API key needed — Apple serves chart data as public JSON.
Endpoint: music.apple.com/us/charts (JSON available via internal API)
Adds Apple Music chart signal to complement Spotify popularity + Billboard.
"""

import time, requests
from datetime import date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://music.apple.com",
    "Referer": "https://music.apple.com/",
}

# Apple Music storefront codes
STOREFRONTS = ["us"]  # expand to "gb", "ca", "au" later if needed

# Apple Music chart types
CHART_TYPES = {
    "top-songs": "songs",
    "top-albums": "albums",
}


def fetch_apple_charts(chart_type, storefront="us", limit=50):
    """
    Fetch Apple Music top charts via their internal chart API.
    Falls back to scraping the page if the JSON endpoint changes.
    """
    url = f"https://amp-api.music.apple.com/v1/catalog/{storefront}/charts"
    params = {
        "types": chart_type,
        "limit": limit,
        "with": "serverSideLogging",
    }

    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    # Alternate endpoint
    alt_url = f"https://music.apple.com/us/charts"
    try:
        r = requests.get(alt_url, headers={**HEADERS, "Accept": "text/html"}, timeout=15)
        if r.status_code == 200:
            # Extract JSON from page
            import re, json
            match = re.search(r'<script[^>]+type="fastboot/shoebox"[^>]*>(.*?)</script>',
                            r.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                return data
    except Exception:
        pass

    return None


def collect_apple_music():
    today = date.today().isoformat()
    records = []

    for storefront in STOREFRONTS:
        for chart_key, chart_label in CHART_TYPES.items():
            try:
                data = fetch_apple_charts(chart_key, storefront)
                if not data:
                    print(f"  Apple Music: no data for {chart_key}/{storefront}")
                    continue

                # Parse chart results — structure varies by endpoint version
                chart_data = None

                # Try standard amp-api structure
                if "results" in data:
                    charts = data["results"]
                    chart_data = charts.get(chart_key, [{}])[0].get("data", [])

                # Try alternate structure
                if not chart_data and isinstance(data, dict):
                    for key in data:
                        if isinstance(data[key], list) and len(data[key]) > 0:
                            if isinstance(data[key][0], dict) and "attributes" in data[key][0]:
                                chart_data = data[key]
                                break

                if not chart_data:
                    print(f"  Apple Music: could not parse {chart_key} chart")
                    continue

                for i, item in enumerate(chart_data[:50]):
                    attrs = item.get("attributes", {})
                    artist_name = attrs.get("artistName", "")
                    title = attrs.get("name", "")
                    if chart_label == "albums":
                        title = attrs.get("name", "")

                    records.append({
                        "snapshot_date": today,
                        "storefront": storefront,
                        "chart_type": chart_label,
                        "position": i + 1,
                        "title": title,
                        "artist_name": artist_name,
                        "apple_id": item.get("id", ""),
                        "genre": attrs.get("genreNames", [None])[0] if attrs.get("genreNames") else None,
                        "release_date": attrs.get("releaseDate"),
                    })

                print(f"  Apple Music: {len(chart_data)} {chart_label} from {storefront} chart")
                time.sleep(0.5)

            except Exception as e:
                print(f"  Apple Music error ({chart_key}/{storefront}): {e}")

    print(f"  Apple Music: {len(records)} total chart entries")
    return records
