"""
Kalshi collector — RSA-PSS signed requests (required as of 2026).
Kalshi no longer accepts simple Bearer token auth — every request
must be cryptographically signed with an RSA-4096 private key.

SETUP (one-time):
1. Generate key pair:
   openssl genrsa -out kalshi_private_key.pem 4096
   openssl rsa -in kalshi_private_key.pem -pubout -out kalshi_public_key.pem

2. Upload kalshi_public_key.pem at kalshi.com → Settings → API Keys
   Kalshi gives you back a Key ID (UUID) — that's KALSHI_KEY_ID

3. Add to environment:
   export KALSHI_KEY_ID="your-uuid-key-id"
   export KALSHI_PRIVATE_KEY_PATH="/path/to/kalshi_private_key.pem"
   (or set KALSHI_PRIVATE_KEY with the PEM content directly)

GitHub Actions: Add KALSHI_KEY_ID and KALSHI_PRIVATE_KEY as secrets.
"""

import os, time, base64, requests
from datetime import date
from pathlib import Path

BASE = "https://api.elections.kalshi.com/trade-api/v2"

MUSIC_KEYWORDS = [
    "drake", "iceman", "spotify", "billboard", "grammy", "streams",
    "album", "song", "artist", "music", "rap", "pop", "hip hop",
    "taylor swift", "bad bunny", "kendrick", "beyonce", "weeknd",
    "featured", "chart", "number one", "#1", "debut", "week",
]


def is_music_market(market):
    title    = (market.get("title") or "").lower()
    subtitle = (market.get("subtitle") or "").lower()
    category = (market.get("category") or "").lower()
    if "music" in category or "entertainment" in category:
        return True
    return any(kw in f"{title} {subtitle}" for kw in MUSIC_KEYWORDS)


def make_headers(method, path, key_id, private_key_pem):
    """Generate RSA-PSS signed headers for Kalshi API."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend

        ts = str(int(time.time() * 1000))
        msg = ts + method.upper() + path
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem,
            password=None,
            backend=default_backend(),
        )
        signature = private_key.sign(
            msg.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        sig_b64 = base64.b64encode(signature).decode("utf-8")
        return {
            "KALSHI-ACCESS-KEY": key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": sig_b64,
            "Content-Type": "application/json",
        }
    except ImportError:
        print("  Kalshi: cryptography package not installed — run: pip install cryptography")
        return None
    except Exception as e:
        print(f"  Kalshi: signing error — {e}")
        return None


def load_credentials():
    """Load Kalshi key ID and private key from environment."""
    key_id = os.environ.get("KALSHI_KEY_ID")

    # Try PEM content directly (for GitHub Actions secret)
    private_key = os.environ.get("KALSHI_PRIVATE_KEY")

    # Try file path
    if not private_key:
        key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH")
        if key_path and Path(key_path).exists():
            private_key = Path(key_path).read_text()

    return key_id, private_key


def collect_kalshi():
    key_id, private_key = load_credentials()

    if not key_id or not private_key:
        print("  Kalshi: missing KALSHI_KEY_ID or KALSHI_PRIVATE_KEY — see collector docstring for setup")
        return []

    today = date.today().isoformat()
    records = []

    try:
        # Search directly for music-related markets by keyword
        # Much faster than scanning all markets
        all_markets = []
        seen_tickers = set()

        SEARCH_TERMS = ["drake", "iceman", "music", "album", "streams", "billboard", "grammy", "spotify"]

        for term in SEARCH_TERMS:
            try:
                path = "/trade-api/v2/markets"
                params = {"limit": 100, "status": "open", "series_ticker": term}
                qs = "&".join(f"{k}={v}" for k, v in params.items())
                headers = make_headers("GET", f"{path}?{qs}", key_id, private_key)
                if not headers:
                    break
                r = requests.get(f"{BASE}/markets", headers=headers, params=params, timeout=15)
                if r.status_code == 200:
                    for m in r.json().get("markets", []):
                        if m.get("ticker") not in seen_tickers:
                            seen_tickers.add(m.get("ticker"))
                            all_markets.append(m)
                time.sleep(0.3)
            except Exception:
                continue

        # Also try the events endpoint filtered by category
        try:
            path = "/trade-api/v2/events"
            params = {"limit": 100, "status": "open", "category": "entertainment"}
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            headers = make_headers("GET", f"{path}?{qs}", key_id, private_key)
            if headers:
                r = requests.get(f"{BASE}/events", headers=headers, params=params, timeout=15)
                if r.status_code == 200:
                    for event in r.json().get("events", []):
                        for m in event.get("markets", []):
                            if m.get("ticker") not in seen_tickers and is_music_market(m):
                                seen_tickers.add(m.get("ticker"))
                                all_markets.append(m)
        except Exception:
            pass

        music_markets = [m for m in all_markets if is_music_market(m)]
        print(f"  Kalshi: {len(music_markets)} music markets found")

        for market in music_markets:
            # Prices now returned as dollar strings e.g. "0.6500" since March 2026
            yes_price = market.get("yes_ask") or market.get("last_price") or 0
            if isinstance(yes_price, str):
                try:
                    yes_price = float(yes_price) * 100  # convert to cents for consistency
                except ValueError:
                    yes_price = 0

            records.append({
                "snapshot_date":  today,
                "platform":       "kalshi",
                "market_id":      market.get("ticker"),
                "title":          market.get("title"),
                "subtitle":       market.get("subtitle"),
                "category":       market.get("category"),
                "status":         market.get("status"),
                "yes_price":      yes_price,
                "volume":         market.get("volume", 0),
                "volume_24h":     market.get("volume_24h", 0),
                "open_interest":  market.get("open_interest", 0),
                "close_time":     market.get("close_time"),
                "result":         market.get("result"),
            })
            time.sleep(0.1)

    except Exception as e:
        print(f"  Kalshi error: {e}")

    print(f"  Kalshi: {len(records)} market snapshots collected")
    return records
