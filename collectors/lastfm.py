"""
Last.fm collector — global cross-DSP listener and play counts.
Free API key at last.fm/api/account/create — takes 5 minutes.
Aggregates listening data from Spotify, Apple Music, YouTube, and all
connected platforms — the closest thing to a true cross-platform stream count.
"""

import os, time, requests
from datetime import date

BASE = "https://ws.audioscrobbler.com/2.0/"


def lastfm_get(method, params, api_key):
    params.update({"method": method, "api_key": api_key, "format": "json"})
    r = requests.get(BASE, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


TRACKED_ARTISTS = [
    "Drake", "Kendrick Lamar", "Taylor Swift", "Bad Bunny",
    "The Weeknd", "Sabrina Carpenter", "Olivia Rodrigo", "SZA",
    "Morgan Wallen", "Zach Bryan", "Post Malone", "Travis Scott",
    "Billie Eilish", "Doja Cat", "Tyler the Creator", "Lil Baby",
    "Noah Kahan", "Luke Combs", "Tyla", "Peso Pluma",
]


def collect_lastfm():
    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key:
        print("  Last.fm: no API key (set LASTFM_API_KEY), skipping")
        return []

    today = date.today().isoformat()
    records = []

    for artist_name in TRACKED_ARTISTS:
        try:
            data = lastfm_get("artist.getinfo", {"artist": artist_name}, api_key)
            artist = data.get("artist", {})
            stats = artist.get("stats", {})

            listeners = int(stats.get("listeners", 0))
            playcount = int(stats.get("playcount", 0))

            # Top tracks for this artist
            top_data = lastfm_get("artist.gettoptracks", {
                "artist": artist_name, "limit": 5
            }, api_key)
            top_tracks = [
                {
                    "name": t.get("name"),
                    "playcount": int(t.get("playcount", 0)),
                    "listeners": int(t.get("listeners", 0)),
                }
                for t in top_data.get("toptracks", {}).get("track", [])
            ]

            records.append({
                "snapshot_date": today,
                "artist_name": artist_name,
                "lastfm_listeners": listeners,
                "lastfm_playcount": playcount,
                "top_tracks": top_tracks,
            })
            time.sleep(0.3)

        except Exception as e:
            print(f"    Last.fm error for {artist_name}: {e}")

    print(f"  Last.fm: {len(records)} artist records collected")
    return records
