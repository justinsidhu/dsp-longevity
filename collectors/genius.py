"""
Genius collector — annotation count and lyric engagement signal.
Fans who annotate lyrics are the most activated core audience.
Annotation velocity post-drop is a depth-of-engagement metric.
Free API — get a token at genius.com/api-clients.
"""

import os, time, requests
from datetime import date

BASE = "https://api.genius.com"

TRACKED_ARTISTS = [
    "Drake", "Kendrick Lamar", "Taylor Swift", "Bad Bunny",
    "The Weeknd", "Sabrina Carpenter", "Olivia Rodrigo", "SZA",
    "Morgan Wallen", "Zach Bryan", "Post Malone", "Travis Scott",
    "Billie Eilish", "Doja Cat", "Noah Kahan",
]

# Iceman-specific tracks to monitor closely
ICEMAN_TRACKS = [
    "What Did I Miss Drake",
    "Which One Drake",
    "Dog House Drake",
    "Iceman Drake",
]


def genius_get(path, token, params=None):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE}{path}", headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def search_artist_songs(artist_name, token, limit=5):
    """Search for an artist's most recently annotated songs."""
    try:
        data = genius_get("/search", token, {"q": artist_name})
        hits = data.get("response", {}).get("hits", [])
        songs = []
        seen = set()
        for hit in hits:
            result = hit.get("result", {})
            primary = result.get("primary_artist", {}).get("name", "")
            if artist_name.lower() in primary.lower() and result["id"] not in seen:
                seen.add(result["id"])
                songs.append({
                    "song_id": result["id"],
                    "title": result.get("title", ""),
                    "annotation_count": result.get("annotation_count", 0),
                    "pyongs_count": result.get("pyongs_count", 0),  # reposts
                    "pageviews": result.get("stats", {}).get("pageviews", 0),
                    "hot": result.get("stats", {}).get("hot", False),
                })
            if len(songs) >= limit:
                break
        return songs
    except Exception as e:
        print(f"    Genius search error for {artist_name}: {e}")
        return []


def get_song_annotations(song_id, token):
    """Get annotation count for a specific song."""
    try:
        data = genius_get(f"/songs/{song_id}", token)
        song = data.get("response", {}).get("song", {})
        return {
            "annotation_count": song.get("annotation_count", 0),
            "pyongs_count": song.get("pyongs_count", 0),
            "pageviews": song.get("stats", {}).get("pageviews", 0),
            "hot": song.get("stats", {}).get("hot", False),
            "description_annotation_count": song.get("description_annotation_count", 0),
        }
    except Exception:
        return {}


def collect_genius():
    token = os.environ.get("GENIUS_API_TOKEN")
    if not token:
        print("  Genius: no token (set GENIUS_API_TOKEN), skipping")
        return []

    today = date.today().isoformat()
    records = []

    # Track main artists
    for artist_name in TRACKED_ARTISTS:
        songs = search_artist_songs(artist_name, token)
        if not songs:
            continue

        total_annotations = sum(s["annotation_count"] for s in songs)
        total_pageviews = sum(s["pageviews"] for s in songs)
        hot_count = sum(1 for s in songs if s["hot"])

        records.append({
            "snapshot_date": today,
            "artist_name": artist_name,
            "songs_tracked": len(songs),
            "total_annotations": total_annotations,
            "total_pageviews": total_pageviews,
            "hot_songs": hot_count,
            "top_song": max(songs, key=lambda x: x["annotation_count"]) if songs else None,
            "songs": songs,
        })
        time.sleep(0.5)

    # Track Iceman-specific tracks closely
    iceman_records = []
    for query in ICEMAN_TRACKS:
        try:
            data = genius_get("/search", token, {"q": query})
            hits = data.get("response", {}).get("hits", [])
            for hit in hits[:1]:
                result = hit.get("result", {})
                song_id = result.get("id")
                if song_id:
                    detail = get_song_annotations(song_id, token)
                    iceman_records.append({
                        "snapshot_date": today,
                        "query": query,
                        "song_id": song_id,
                        "title": result.get("title", ""),
                        **detail,
                    })
            time.sleep(0.5)
        except Exception as e:
            print(f"    Genius Iceman track error ({query}): {e}")

    print(f"  Genius: {len(records)} artists, {len(iceman_records)} Iceman track records")
    return records + iceman_records
