"""
Spotify collector v2 — artist-centric approach.
- Pulls top artists from Billboard Hot 100 (already collected)
- Tracks artist popularity daily with velocity scoring
- Detects new releases by tracked artists
- Classifies labels using label_classifications.json
- Fuzzy matches artist names across sources
"""

import os, json, time, requests, re
from datetime import date, timedelta
from pathlib import Path
from base64 import b64encode
from difflib import SequenceMatcher

ROOT = Path(__file__).parent.parent
LABEL_DB = ROOT / "data" / "label_classifications.json"
RAW = ROOT / "data" / "raw"

MAJOR_KEYWORDS = [
    "republic", "interscope", "def jam", "motown", "island", "capitol",
    "geffen", "virgin", "mercury", "polydor", "universal", "umg",
    "columbia", "rca", "epic", "arista", "sony", "legacy",
    "atlantic", "warner", "elektra", "parlophone", "reprise",
]

SELF_RELEASED_KEYWORDS = [
    "distrokid", "tunecore", "cd baby", "amuse", "unitedmasters",
    "gamma", "vydia", "awal", "believe", "empire"
]

FALLBACK_ARTISTS = [
    "Olivia Rodrigo", "Ella Langley", "Bruno Mars", "Taylor Swift",
    "Justin Bieber", "Morgan Wallen", "Noah Kahan", "Luke Combs",
    "Sabrina Carpenter", "Drake", "Kendrick Lamar", "Bad Bunny",
    "The Weeknd", "SZA", "Post Malone", "Travis Scott",
    "Don Toliver", "Kehlani", "BTS", "Zach Bryan",
    "Billie Eilish", "Doja Cat", "Tyler the Creator", "Lil Baby",
    "Tyla", "PinkPantheress", "Dominic Fike", "Alex Warren",
    "KATSEYE", "Tame Impala", "Steve Lacy", "Peso Pluma",
]


def get_token(client_id, client_secret):
    creds = b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {creds}"},
        data={"grant_type": "client_credentials"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


def normalize_name(name):
    name = name.lower().strip()
    name = re.sub(r'\s*(feat\.?|ft\.?|featuring|with)\s+.*$', '', name)
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    replacements = [
        ('the weeknd', 'weeknd'), ('tyler the creator', 'tyler creator'),
        (r'\bj cole\b', 'j. cole'), ('lil uzi vert', 'lil uzi'),
    ]
    for pattern, repl in replacements:
        name = re.sub(pattern, repl, name)
    return name.strip()


def fuzzy_score(a, b):
    na, nb = normalize_name(a), normalize_name(b)
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return min(len(na), len(nb)) / max(len(na), len(nb), 1)
    tokens_a, tokens_b = set(na.split()), set(nb.split())
    if tokens_a and tokens_b:
        jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    else:
        jaccard = 0.0
    char_ratio = SequenceMatcher(None, na, nb).ratio()
    return max(jaccard, char_ratio * 0.85)


def find_best_match(query, candidates, threshold=0.75):
    best, best_score = None, 0.0
    for c in candidates:
        s = fuzzy_score(query, c)
        if s > best_score:
            best_score, best = s, c
    return (best, best_score) if best_score >= threshold else (None, 0.0)


def load_label_db():
    if LABEL_DB.exists():
        return json.loads(LABEL_DB.read_text())
    return {}


def classify_label(label_name, artist_name, label_db):
    overrides = label_db.get("artist_overrides", {})
    matched, score = find_best_match(artist_name, list(overrides.keys()), 0.8)
    if matched:
        o = overrides[matched]
        return {"tier": o["tier"], "label_canonical": o["label"],
                "distributor": o.get("distributor"), "master_ownership": o.get("master_ownership"),
                "match_source": "artist_override", "match_score": score, "notes": o.get("notes")}

    labels = label_db.get("labels", {})
    matched_l, lscore = find_best_match(label_name or "", list(labels.keys()), 0.75)
    if matched_l:
        d = labels[matched_l]
        return {"tier": d["tier"], "label_canonical": matched_l,
                "distributor": d.get("distributor"), "master_ownership": d.get("master_ownership"),
                "match_source": "label_db", "match_score": lscore, "notes": d.get("notes")}

    ll = (label_name or "").lower()
    for group, kws in label_db.get("major_groups", {}).items():
        for kw in kws:
            if kw.lower() in ll:
                return {"tier": "major", "label_canonical": label_name, "distributor": group,
                        "master_ownership": "label", "match_source": "keyword_major", "match_score": 0.7}

    for kw in SELF_RELEASED_KEYWORDS:
        if kw in ll:
            return {"tier": "self_released", "label_canonical": label_name, "distributor": label_name,
                    "master_ownership": "artist", "match_source": "keyword_self_released", "match_score": 0.7}

    return {"tier": "unknown", "label_canonical": label_name, "distributor": None,
            "master_ownership": "unknown", "match_source": "unmatched", "match_score": 0.0}


def compute_velocity(artist_id, current_pop):
    artist_file = RAW / "spotify_artists.jsonl"
    if not artist_file.exists():
        return {"velocity_score": 0, "velocity_tier": "new", "prev_popularity": None}

    seven_ago = (date.today() - timedelta(days=7)).isoformat()
    prev_records = []
    with open(artist_file) as f:
        for line in f:
            try:
                r = json.loads(line)
                if r.get("artist_id") == artist_id and r.get("snapshot_date") <= seven_ago:
                    prev_records.append(r)
            except Exception:
                continue

    if not prev_records:
        return {"velocity_score": 0, "velocity_tier": "new", "prev_popularity": None}

    prev = max(prev_records, key=lambda x: x["snapshot_date"])
    prev_pop = prev.get("popularity", current_pop)
    delta = current_pop - prev_pop

    tier = ("breakout" if delta >= 10 else "rising" if delta >= 5 else
            "stable" if delta >= -2 else "fading" if delta >= -8 else "declining")
    return {"velocity_score": delta, "velocity_tier": tier, "prev_popularity": prev_pop}


class SpotifyCollector:
    BASE = "https://api.spotify.com/v1"

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = get_token(client_id, client_secret)
        self._ts = time.time()
        self.label_db = load_label_db()

    def _h(self):
        if time.time() - self._ts > 3300:
            self.token = get_token(self.client_id, self.client_secret)
            self._ts = time.time()
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path, params=None):
        r = requests.get(f"{self.BASE}{path}", headers=self._h(), params=params)
        r.raise_for_status()
        return r.json()

    def search_artist(self, name):
        try:
            data = self.get("/search", {"q": name, "type": "artist", "limit": 5, "market": "US"})
            artists = [a for a in data.get("artists", {}).get("items", []) if a]
            if not artists:
                return None
            best, best_score = None, 0.0
            for a in artists:
                s = fuzzy_score(name, a["name"])
                if s > best_score:
                    best_score, best = s, a
            return best if best_score >= 0.75 else None
        except Exception as e:
            print(f"    Search error for '{name}': {e}")
            return None

    def get_new_releases(self, artist_id, artist_name):
        try:
            data = self.get(f"/artists/{artist_id}/albums",
                            {"include_groups": "album,single", "limit": 5, "market": "US"})
            cutoff = (date.today() - timedelta(days=30)).isoformat()
            new = []
            for album in data.get("items", []):
                if album.get("release_date", "") >= cutoff:
                    try:
                        full = self.get(f"/albums/{album['id']}")
                        label_name = full.get("label", "")
                        label_info = classify_label(label_name, artist_name, self.label_db)
                    except Exception:
                        label_name, label_info = "", {"tier": "unknown"}
                    new.append({
                        "album_id": album["id"], "album_name": album["name"],
                        "album_type": album["album_type"], "release_date": album.get("release_date"),
                        "label_raw": label_name, "label_tier": label_info.get("tier"),
                        "label_canonical": label_info.get("label_canonical"),
                        "master_ownership": label_info.get("master_ownership"),
                    })
            return new
        except Exception as e:
            print(f"    Releases error for {artist_name}: {e}")
            return []

    def collect_playlists(self):
        today = date.today().isoformat()

        # Get artist names from Billboard data
        billboard_file = RAW / "billboard.jsonl"
        artist_names = set()
        if billboard_file.exists():
            with open(billboard_file) as f:
                for line in f:
                    try:
                        r = json.loads(line)
                        artist = r.get("artist", "")
                        if artist:
                            primary = re.split(r'\s+feat\.?\s+|\s+ft\.?\s+|\s+&\s+', artist, flags=re.IGNORECASE)[0].strip()
                            artist_names.add(primary)
                    except Exception:
                        continue

        if not artist_names:
            artist_names = set(FALLBACK_ARTISTS)

        print(f"  Spotify: tracking {len(artist_names)} artists from Billboard")

        artist_records, release_records, seen_ids = [], [], set()

        for name in sorted(artist_names):
            try:
                artist = self.search_artist(name)
                if not artist or artist["id"] in seen_ids:
                    continue
                seen_ids.add(artist["id"])

                pop = artist.get("popularity", 0)
                label_info = classify_label("", name, self.label_db)
                velocity = compute_velocity(artist["id"], pop)

                artist_records.append({
                    "snapshot_date": today,
                    "artist_id": artist["id"],
                    "artist_name": artist["name"],
                    "query_name": name,
                    "match_score": round(fuzzy_score(name, artist["name"]), 3),
                    "popularity": pop,
                    "followers": artist.get("followers", {}).get("total", 0),
                    "genres": artist.get("genres", []),
                    "label_tier": label_info.get("tier"),
                    "label_canonical": label_info.get("label_canonical"),
                    "master_ownership": label_info.get("master_ownership"),
                    "label_match_source": label_info.get("match_source"),
                    **velocity,
                })

                releases = self.get_new_releases(artist["id"], name)
                for rel in releases:
                    release_records.append({"snapshot_date": today, "artist_id": artist["id"],
                                            "artist_name": artist["name"], **rel})
                    print(f"    NEW: {artist['name']} — {rel['album_name']} ({rel['release_date']})")

                time.sleep(0.4)

            except Exception as e:
                print(f"    Error: {name}: {e}")

        artist_records.sort(key=lambda x: abs(x.get("velocity_score", 0)), reverse=True)
        print(f"  Spotify: {len(artist_records)} artists, {len(release_records)} new releases")
        return artist_records, [], release_records
