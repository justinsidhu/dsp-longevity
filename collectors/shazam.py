"""
Shazam collector — uses shazamio (free, reverse-engineered Shazam API).
Pulls:
- Top 200 US chart (daily rankings with position, track, artist)
- Listening counter for tracked tracks (total Shazam count)
- Shazam Discovery Top 50 (emerging artists before they break)

Shazam is the purest human discovery signal in the pipeline:
someone hears something they don't recognize, takes active
steps to identify it. Unlike streaming (passive) or search
(intent-driven), Shazam = genuine ambient discovery moment.

Install: pip install shazamio
"""

import asyncio
import time
from datetime import date

try:
    from shazamio import Shazam
    from shazamio.schemas.enums import GenreMusic
    SHAZAMIO_AVAILABLE = True
except ImportError:
    SHAZAMIO_AVAILABLE = False


# Shazam track IDs for our tracked songs
# Find by searching shazam.com/track/<id>/<slug>
TRACKED_TRACKS = {
    "Not Like Us":          552406075,
    "Espresso":             727553491,
    "APT.":                 736663695,
    "Please Please Please": 728060695,
    "Die With A Smile":     730616610,
    "Beautiful Things":     718783825,
    "Too Sweet":            722198726,
    "Lose Control":         714855703,
    "Good Luck Babe":       724405253,
    "i had some help":      727044384,
}


async def _fetch_top_chart():
    """Pull US Top 200 Shazam chart."""
    shazam = Shazam()
    # top_world_tracks returns global chart; country code 'US' for US chart
    chart = await shazam.top_country_tracks(country_code="US", limit=200)
    return chart


async def _fetch_discovery_chart():
    """Pull Shazam Discovery Top 50 — emerging artists."""
    shazam = Shazam()
    chart = await shazam.top_world_tracks(limit=50)
    return chart


async def _fetch_listening_counts(track_ids: dict):
    """Pull listening counter (total Shazams) for tracked tracks."""
    shazam = Shazam()
    results = {}
    for name, track_id in track_ids.items():
        try:
            count = await shazam.listening_counter(track_id=track_id)
            results[name] = count
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"    Shazam count error for {name}: {e}")
            results[name] = None
    return results


def collect_shazam():
    """
    Main entry point — synchronous wrapper around async shazamio calls.
    Returns three record sets:
    - chart_records: US Top 200 daily rankings
    - count_records: listening counter per tracked track
    - discovery_records: Discovery Top 50 emerging artists
    """
    if not SHAZAMIO_AVAILABLE:
        print("  Shazam: shazamio not installed — run: pip install shazamio")
        return [], [], []

    today = date.today().isoformat()

    async def _run():
        chart_data, discovery_data, count_data = None, None, {}

        # US Top 200
        try:
            chart_data = await _fetch_top_chart()
        except Exception as e:
            print(f"  Shazam chart error: {e}")

        # Discovery Top 50
        try:
            discovery_data = await _fetch_discovery_chart()
        except Exception as e:
            print(f"  Shazam discovery error: {e}")

        # Listening counts for tracked tracks
        try:
            count_data = await _fetch_listening_counts(TRACKED_TRACKS)
        except Exception as e:
            print(f"  Shazam count error: {e}")

        return chart_data, discovery_data, count_data

    chart_data, discovery_data, count_data = asyncio.run(_run())

    # ── Parse US Top 200 chart ─────────────────────────────────────────────
    chart_records = []
    if chart_data:
        tracks = chart_data.get("tracks", []) if isinstance(chart_data, dict) else []
        for i, track in enumerate(tracks):
            try:
                heading = track.get("heading", {})
                chart_records.append({
                    "snapshot_date": today,
                    "chart": "us_top_200",
                    "position": i + 1,
                    "track_id": track.get("key"),
                    "track_name": heading.get("title", ""),
                    "artist_name": heading.get("subtitle", ""),
                    "shazam_url": track.get("url", ""),
                })
            except Exception:
                continue

    # ── Parse Discovery Top 50 ────────────────────────────────────────────
    discovery_records = []
    if discovery_data:
        tracks = discovery_data.get("tracks", []) if isinstance(discovery_data, dict) else []
        for i, track in enumerate(tracks):
            try:
                heading = track.get("heading", {})
                discovery_records.append({
                    "snapshot_date": today,
                    "chart": "discovery_top_50",
                    "position": i + 1,
                    "track_id": track.get("key"),
                    "track_name": heading.get("title", ""),
                    "artist_name": heading.get("subtitle", ""),
                })
            except Exception:
                continue

    # ── Parse listening counts ────────────────────────────────────────────
    count_records = []
    for track_name, count in count_data.items():
        count_records.append({
            "snapshot_date": today,
            "track_name": track_name,
            "shazam_track_id": TRACKED_TRACKS.get(track_name),
            "listening_count": count,
        })

    print(f"  Shazam: {len(chart_records)} chart entries, "
          f"{len(discovery_records)} discovery entries, "
          f"{len(count_records)} listening counts")

    return chart_records, discovery_records, count_records
