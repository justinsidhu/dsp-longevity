"""
Spotify collector — pulls live editorial playlist tracks and artist popularity.
Uses hardcoded verified playlist IDs with search fallback.
To update IDs: open playlist in Spotify, share -> copy link, ID is after /playlist/
"""

import time, requests
from datetime import date
from base64 import b64encode

# Verified official Spotify playlist IDs — update if a 404 occurs
# Format: open.spotify.com/playlist/<ID>
PLAYLISTS = {
    "today_top_hits":   "37i9dQZF1DXcBWIGoYBM5M",
    "rap_caviar":       "37i9dQZF1DX0XUsuxWHRQd",
    "hot_hits_usa":     "37i9dQZF1DX0kbJZpiYdZl",
    "new_music_friday": "37i9dQZF1DX4JAvHpjipBk",
    "viral_50_usa":   "37i9dQZEVXbKuaTI1Z1Afx",
    "fresh_finds":    "37i9dQZF1DWWjGdmeTyeJ6",
    "pop_rising":       "37i9dQZF1DWUa8ZRTfalHk",
    "most_necessary":   "37i9dQZF1DX2RxBh64BHjQ",
}

# Search fallback terms if a hardcoded ID 404s
PLAYLIST_SEARCHES = {
    "today_top_hits":   "Today's Top Hits",
    "rap_caviar":       "RapCaviar",
    "hot_hits_usa":     "Hot Hits USA",
    "new_music_friday": "New Music Friday",
    "viral_50_usa":     "Viral 50 USA",
    "fresh_finds":      "Fresh Finds",
    "pop_rising":       "Pop Rising",
    "most_necessary":   "Most Necessary",
}


def get_token(client_id, client_secret):
    creds = b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {creds}"},
        data={"grant_type": "client_credentials"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


class SpotifyCollector:
    BASE = "https://api.spotify.com/v1"

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = get_token(client_id, client_secret)
        self._ts = time.time()

    def _h(self):
        if time.time() - self._ts > 3300:
            self.token = get_token(self.client_id, self.client_secret)
            self._ts = time.time()
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path, params=None):
        r = requests.get(f"{self.BASE}{path}", headers=self._h(), params=params)
        r.raise_for_status()
        return r.json()

    def search_playlist(self, name, query):
        """Search fallback — only used if hardcoded ID 404s."""
        try:
            data = self.get("/search", {"q": query, "type": "playlist", "limit": 20, "market": "US"})
            items = [p for p in data.get("playlists", {}).get("items", []) if p]
            # Strictly filter to spotify-owned only
            for pl in items:
                if pl.get("owner", {}).get("id") == "spotify":
                    print(f"    Search fallback resolved '{name}' -> {pl['name']} ({pl['id']})")
                    return pl["id"]
            print(f"    Search fallback found no official Spotify playlist for: {query}")
            return None
        except Exception as e:
            print(f"    Search fallback error for '{name}': {e}")
            return None

    def verify_or_search(self, name, playlist_id):
        """Try hardcoded ID first, fall back to search if 404."""
        try:
            r = requests.get(
                f"{self.BASE}/playlists/{playlist_id}",
                headers=self._h(),
                params={"fields": "id,name,owner"},
            )
            if r.status_code == 200:
                data = r.json()
                print(f"    Verified '{name}' -> {data['name']} ({playlist_id})")
                return playlist_id
            elif r.status_code == 404:
                print(f"    ID stale for '{name}', searching...")
                return self.search_playlist(name, PLAYLIST_SEARCHES[name])
            else:
                r.raise_for_status()
        except Exception as e:
            print(f"    Error verifying '{name}': {e}")
            return None

    def playlist_tracks(self, playlist_id):
        tracks, url = [], f"{self.BASE}/playlists/{playlist_id}/tracks"
        params = {"limit": 100, "fields": "items(track(id,name,popularity,artists,album)),next"}
        while url:
            r = requests.get(url, headers=self._h(), params=params)
            r.raise_for_status()
            data = r.json()
            for item in data.get("items", []):
                t = item.get("track")
                if t and t.get("id"):
                    tracks.append(t)
            url = data.get("next")
            params = None
            time.sleep(0.2)
        return tracks

    def artist_snapshot(self, artist_id):
        ar = self.get(f"/artists/{artist_id}")
        return {
            "artist_id": artist_id,
            "artist_name": ar["name"],
            "popularity": ar["popularity"],
            "followers": ar["followers"]["total"],
            "genres": ar["genres"],
        }

    def collect_playlists(self):
        today = date.today().isoformat()

        print("  Verifying playlist IDs...")
        resolved = {}
        for name, pid in PLAYLISTS.items():
            verified = self.verify_or_search(name, pid)
            if verified:
                resolved[name] = verified
            time.sleep(0.2)
        print(f"  Resolved {len(resolved)}/{len(PLAYLISTS)} playlists\n")

        if not resolved:
            print("  ERROR: Could not resolve any playlists")
            return [], [], []

        track_records, artist_ids_seen = [], set()
        playlist_track_sets = {}

        for playlist_name, playlist_id in resolved.items():
            print(f"  Pulling playlist: {playlist_name}")
            try:
                tracks = self.playlist_tracks(playlist_id)
                track_ids = set()
                for t in tracks:
                    tid = t["id"]
                    track_ids.add(tid)
                    artist_id = t["artists"][0]["id"] if t.get("artists") else None
                    record = {
                        "snapshot_date": today,
                        "playlist_name": playlist_name,
                        "playlist_id": playlist_id,
                        "track_id": tid,
                        "track_name": t["name"],
                        "track_popularity": t.get("popularity"),
                        "artist_id": artist_id,
                        "artist_name": t["artists"][0]["name"] if t.get("artists") else None,
                        "album_name": t.get("album", {}).get("name"),
                        "album_release_date": t.get("album", {}).get("release_date"),
                    }
                    track_records.append(record)
                    if artist_id:
                        artist_ids_seen.add(artist_id)
                playlist_track_sets[playlist_name] = track_ids
                time.sleep(0.5)
            except Exception as e:
                print(f"    ERROR on {playlist_name}: {e}")

        # Echo chamber index
        echo_records = []
        playlist_names = list(playlist_track_sets.keys())
        for i, p1 in enumerate(playlist_names):
            for p2 in playlist_names[i+1:]:
                s1, s2 = playlist_track_sets[p1], playlist_track_sets[p2]
                if s1 and s2:
                    overlap = len(s1 & s2) / len(s1 | s2)
                    echo_records.append({
                        "snapshot_date": today,
                        "playlist_a": p1,
                        "playlist_b": p2,
                        "overlap_score": round(overlap, 4),
                        "shared_tracks": len(s1 & s2),
                        "total_unique": len(s1 | s2),
                    })

        # Artist snapshots
        artist_records = []
        for artist_id in list(artist_ids_seen)[:40]:
            try:
                snap = self.artist_snapshot(artist_id)
                snap["snapshot_date"] = today
                artist_records.append(snap)
                time.sleep(0.3)
            except Exception as e:
                print(f"    Artist error {artist_id}: {e}")

        return track_records, echo_records, artist_records
