"""
Kalshi collector — pulls music prediction market data.
Tracks implied probability, volume, and price history for music markets.
Requires a Kalshi account and API key (free, read-only).
KALSHI_API_KEY env var.
"""

import os, time, requests
from datetime import date

BASE = "https://trading-api.kalshi.com/trade-api/v2"

# Music-related keywords to match against market titles
MUSIC_KEYWORDS = [
    "drake", "iceman", "spotify", "billboard", "grammy", "streams",
    "album", "song", "artist", "music", "rap", "pop", "hip hop",
    "taylor swift", "bad bunny", "kendrick", "beyonce", "weekend",
    "featured", "chart", "number one", "#1"
]


def get_headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def is_music_market(market):
    """Check if a market is music-related by scanning title and category."""
    title = (market.get("title") or "").lower()
    subtitle = (market.get("subtitle") or "").lower()
    category = (market.get("category") or "").lower()

    if "music" in category or "entertainment" in category:
        return True
    combined = f"{title} {subtitle}"
    return any(kw in combined for kw in MUSIC_KEYWORDS)


def collect_kalshi():
    api_key = os.environ.get("KALSHI_API_KEY")
    if not api_key:
        print("  Kalshi: no API key (set KALSHI_API_KEY), skipping")
        return []

    today = date.today().isoformat()
    records = []

    try:
        # Pull all active markets, paginate through
        cursor = None
        all_markets = []

        while True:
            params = {"limit": 200, "status": "open"}
            if cursor:
                params["cursor"] = cursor

            r = requests.get(
                f"{BASE}/markets",
                headers=get_headers(api_key),
                params=params,
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            markets = data.get("markets", [])
            all_markets.extend(markets)

            cursor = data.get("cursor")
            if not cursor or not markets:
                break
            time.sleep(0.3)

        # Filter to music markets
        music_markets = [m for m in all_markets if is_music_market(m)]
        print(f"  Kalshi: {len(music_markets)} music markets found (of {len(all_markets)} total)")

        for market in music_markets:
            ticker = market.get("ticker", "")

            # Pull order book for current yes price
            yes_price = market.get("yes_ask") or market.get("last_price") or 0
            no_price = market.get("no_ask") or 0

            record = {
                "snapshot_date": today,
                "platform": "kalshi",
                "market_id": ticker,
                "title": market.get("title"),
                "subtitle": market.get("subtitle"),
                "category": market.get("category"),
                "status": market.get("status"),
                "yes_price": yes_price,          # implied probability (0-100)
                "no_price": no_price,
                "volume": market.get("volume", 0),
                "volume_24h": market.get("volume_24h", 0),
                "open_interest": market.get("open_interest", 0),
                "close_time": market.get("close_time"),
                "result": market.get("result"),  # null if unresolved
            }
            records.append(record)
            time.sleep(0.1)

    except Exception as e:
        print(f"  Kalshi error: {e}")

    print(f"  Kalshi: {len(records)} market snapshots collected")
    return records
