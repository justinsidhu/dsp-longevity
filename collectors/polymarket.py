"""
Polymarket collector — pulls music prediction market data.
No API key needed — fully public CLOB API.
Tracks implied probability, volume, and outcomes for music markets.
"""

import time, requests
from datetime import date

BASE = "https://clob.polymarket.com"
GAMMA_BASE = "https://gamma-api.polymarket.com"  # metadata API

MUSIC_KEYWORDS = [
    "drake", "iceman", "spotify", "billboard", "grammy", "streams",
    "album", "song", "artist", "music", "rap", "pop", "hip hop",
    "taylor swift", "bad bunny", "kendrick", "beyonce", "weeknd",
    "featured", "chart", "number one", "#1", "concert", "tour",
    "debut", "first week", "sales"
]


def is_music_event(event):
    title = (event.get("title") or "").lower()
    slug = (event.get("slug") or "").lower()
    tags = [t.get("label", "").lower() for t in event.get("tags") or []]
    combined = f"{title} {slug} {' '.join(tags)}"
    if "music" in tags or "entertainment" in tags:
        return True
    return any(kw in combined for kw in MUSIC_KEYWORDS)


def collect_polymarket():
    today = date.today().isoformat()
    records = []

    try:
        # Gamma API has better event metadata than CLOB directly
        offset = 0
        limit = 100
        music_events = []

        while True:
            r = requests.get(
                f"{GAMMA_BASE}/events",
                params={
                    "limit": limit,
                    "offset": offset,
                    "active": "true",
                    "closed": "false",
                },
                timeout=15,
            )
            r.raise_for_status()
            events = r.json()

            if not events:
                break

            music_events.extend([e for e in events if is_music_event(e)])
            offset += limit

            # Stop after 500 events — music markets are a small slice
            if offset >= 500:
                break
            time.sleep(0.3)

        print(f"  Polymarket: {len(music_events)} music events found")

        for event in music_events:
            markets = event.get("markets") or []

            for market in markets:
                # Get current prices from outcomes
                outcomes = market.get("outcomes") or []
                outcome_prices = market.get("outcomePrices") or []

                # Parse outcome probabilities
                outcome_data = []
                for i, outcome in enumerate(outcomes):
                    price = float(outcome_prices[i]) if i < len(outcome_prices) else None
                    outcome_data.append({
                        "outcome": outcome,
                        "probability": round(price * 100, 1) if price else None,
                    })

                record = {
                    "snapshot_date": today,
                    "platform": "polymarket",
                    "event_id": event.get("id"),
                    "event_title": event.get("title"),
                    "event_slug": event.get("slug"),
                    "market_id": market.get("id"),
                    "question": market.get("question"),
                    "volume": float(market.get("volume") or 0),
                    "volume_24h": float(market.get("volume24hr") or 0),
                    "liquidity": float(market.get("liquidity") or 0),
                    "outcomes": outcome_data,
                    "end_date": market.get("endDate"),
                    "resolved": market.get("resolved", False),
                    "resolution": market.get("resolution"),
                    # Top outcome by probability for quick scanning
                    "leading_outcome": max(
                        outcome_data,
                        key=lambda x: x["probability"] or 0
                    ) if outcome_data else None,
                }
                records.append(record)

            time.sleep(0.2)

    except Exception as e:
        print(f"  Polymarket error: {e}")

    print(f"  Polymarket: {len(records)} market snapshots collected")
    return records
