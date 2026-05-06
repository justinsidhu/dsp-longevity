"""
YouTube collector v2.
Two signals:
1. Topic channel view counts — auto-generated "Artist - Topic" channels
   contain every distributed track. View count = closest thing to stream
   count available publicly. Costs 1 quota unit per 50 videos.

2. Official channel stats — subscriber count, total views for artist channels.

Topic channel discovery:
- Search YouTube for "Artist Name - Topic" channel
- Store channel ID, then daily pull latest video stats
- This gives us a DSP-agnostic view count that covers Spotify, Apple Music,
  and every other DSP simultaneously since all distribute to YouTube.

YouTube is by far the largest music streaming platform globally.
The Topic channel is the open data layer the industry doesn't talk about.
"""

import os, time, requests, json
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
from datetime import date

API_BASE = "https://www.googleapis.com/youtube/v3"

# Tracked artists for Topic channel discovery
# These map to "Artist Name - Topic" channels on YouTube
TOPIC_ARTISTS = [
    "Olivia Rodrigo", "Ella Langley", "Bruno Mars", "Taylor Swift",
    "Justin Bieber", "Morgan Wallen", "Noah Kahan", "Luke Combs",
    "Sabrina Carpenter", "Drake", "Kendrick Lamar", "Bad Bunny",
    "The Weeknd", "SZA", "Post Malone", "Travis Scott",
    "Don Toliver", "Kehlani", "Zach Bryan", "Billie Eilish",
    "Doja Cat", "Tyla", "PinkPantheress", "Lil Baby",
]

# Official music video IDs for heatmap tracking
TRACK_VIDEOS = {
    "Not Like Us":          "T6eK-2OQtew",
    "Espresso":             "eVli-tstM5E",
    "APT.":                 "ArmDp-zijuc",
    "Please Please Please": "ImHs7VEIKB0",
    "Die With A Smile":     "kN0iD0pI3o0",
    "Beautiful Things":     "AEY1HxJBkJ4",
    "Too Sweet":            "rGKfBHgGBts",
    "Lose Control":         "oU-DNZjbQRI",
    "Good Luck Babe":       "NK5UHoYLMGI",
    "i had some help":      "R3-BIl2TQUQ",
}

# Drake rollout channels to monitor for new content
DRAKE_ROLLOUT_CHANNELS = {
    "Drake Official":   "UCByOQJjav0CUDwxCk-jVNRQ",  # main channel
    "plottttwistttttt": "UCJq_UgfAyO6W2HKCbrMcqLQ",  # OVO rollout/content channel
}

# Reaction/commentary channels to monitor for Iceman coverage
REACTION_CHANNEL_QUERIES = [
    "DJ Akademiks Iceman Drake",
    "Iceman Drake reaction 2026",
    "Drake Iceman review",
    "Drake May 14 livestream",
    "Drake Episode 4 livestream",
]


def get_channel_recent_videos(channel_id, api_key, max_results=10):
    """Get recent uploads from a channel — checks for new content daily."""
    try:
        channel_data = yt_get("channels", {
            "part": "contentDetails,statistics,snippet",
            "id": channel_id,
        }, api_key)
        items = channel_data.get("items", [])
        if not items:
            return [], {}
        uploads_playlist = (items[0].get("contentDetails", {})
                                    .get("relatedPlaylists", {})
                                    .get("uploads", ""))
        channel_stats = items[0].get("statistics", {})
        channel_name = items[0].get("snippet", {}).get("title", "")

        if not uploads_playlist:
            return [], channel_stats

        playlist_data = yt_get("playlistItems", {
            "part": "snippet",
            "playlistId": uploads_playlist,
            "maxResults": max_results,
        }, api_key)

        videos = []
        for item in playlist_data.get("items", []):
            vid_id = item["snippet"]["resourceId"].get("videoId")
            if vid_id:
                videos.append({
                    "video_id": vid_id,
                    "title": item["snippet"].get("title", ""),
                    "published_at": item["snippet"].get("publishedAt", ""),
                    "channel_name": channel_name,
                })
        return videos, channel_stats
    except Exception as e:
        print(f"    Channel recent videos error {channel_id}: {e}")
        return [], {}


def search_iceman_reaction_content(api_key):
    """Search YouTube for Iceman/Drake reaction and commentary content."""
    if not api_key:
        return []
    results = []
    seen_ids = set()
    for query in REACTION_CHANNEL_QUERIES[:2]:  # limit to 2 searches to save quota
        try:
            data = yt_get("search", {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "date",
                "maxResults": 5,
                "publishedAfter": "2026-05-01T00:00:00Z",
            }, api_key)
            for item in data.get("items", []):
                vid_id = item.get("id", {}).get("videoId")
                if vid_id and vid_id not in seen_ids:
                    seen_ids.add(vid_id)
                    results.append({
                        "video_id": vid_id,
                        "title": item["snippet"].get("title", ""),
                        "channel_title": item["snippet"].get("channelTitle", ""),
                        "published_at": item["snippet"].get("publishedAt", ""),
                    })
            time.sleep(0.5)
        except Exception as e:
            print(f"    Iceman reaction search error ({query}): {e}")
    return results

HEATMAP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def yt_get(endpoint, params, api_key):
    params["key"] = api_key
    r = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def find_topic_channel(artist_name, api_key):
    """
    Search for an artist's Topic channel on YouTube.
    Topic channels are titled "Artist Name - Topic" and say "auto-generated by YouTube".
    Costs 100 quota units (search is expensive) — only run weekly per artist.
    """
    try:
        data = yt_get("search", {
            "part": "snippet",
            "q": f"{artist_name} Topic",
            "type": "channel",
            "maxResults": 5,
        }, api_key)

        for item in data.get("items", []):
            title = item.get("snippet", {}).get("title", "")
            desc = item.get("snippet", {}).get("description", "").lower()
            # Match "Artist - Topic" exactly
            if f"{artist_name} - Topic".lower() in title.lower() or \
               ("topic" in title.lower() and "auto-generated" in desc):
                return item["snippet"]["channelId"]
        return None
    except Exception as e:
        print(f"    Topic channel search error for {artist_name}: {e}")
        return None


def get_channel_latest_videos(channel_id, api_key, max_results=10):
    """Get latest videos from a channel via its uploads playlist."""
    try:
        # Get uploads playlist ID
        channel_data = yt_get("channels", {
            "part": "contentDetails,statistics",
            "id": channel_id,
        }, api_key)

        items = channel_data.get("items", [])
        if not items:
            return [], {}

        uploads_playlist = (items[0].get("contentDetails", {})
                                    .get("relatedPlaylists", {})
                                    .get("uploads", ""))
        channel_stats = items[0].get("statistics", {})

        if not uploads_playlist:
            return [], channel_stats

        # Get latest videos from playlist
        playlist_data = yt_get("playlistItems", {
            "part": "snippet",
            "playlistId": uploads_playlist,
            "maxResults": max_results,
        }, api_key)

        video_ids = [
            item["snippet"]["resourceId"]["videoId"]
            for item in playlist_data.get("items", [])
            if item.get("snippet", {}).get("resourceId", {}).get("videoId")
        ]
        return video_ids, channel_stats

    except Exception as e:
        print(f"    Channel videos error {channel_id}: {e}")
        return [], {}


def get_video_stats(video_ids, api_key):
    """Batch pull view counts for up to 50 videos. Costs 1 quota unit."""
    if not video_ids:
        return {}
    try:
        data = yt_get("videos", {
            "part": "statistics,snippet",
            "id": ",".join(video_ids[:50]),
        }, api_key)

        return {
            item["id"]: {
                "title": item["snippet"].get("title", ""),
                "published_at": item["snippet"].get("publishedAt", ""),
                "view_count": int(item["statistics"].get("viewCount", 0)),
                "like_count": int(item["statistics"].get("likeCount", 0)),
                "comment_count": int(item["statistics"].get("commentCount", 0)),
            }
            for item in data.get("items", [])
        }
    except Exception as e:
        print(f"    Video stats error: {e}")
        return {}


def collect_youtube_stats(api_key):
    """
    Main collector:
    1. Pull stats for hardcoded music video IDs
    2. For Topic channels we have cached, pull latest video stats
    """
    if not api_key:
        print("  YouTube stats: no API key, skipping")
        return []

    today = date.today().isoformat()
    records = []

    # Hardcoded music videos
    if TRACK_VIDEOS:
        stats = get_video_stats(list(TRACK_VIDEOS.values()), api_key)
        for track_name, video_id in TRACK_VIDEOS.items():
            if video_id in stats:
                s = stats[video_id]
                records.append({
                    "snapshot_date": today,
                    "source": "official_mv",
                    "track_name": track_name,
                    "video_id": video_id,
                    **s,
                })

    # Topic channel stats (load cached channel IDs)
    topic_cache_file = RAW.parent / "processed" / "topic_channel_ids.json"
    topic_channels = {}
    if topic_cache_file.exists():
        topic_channels = json.loads(topic_cache_file.read_text())

    for artist_name, channel_id in topic_channels.items():
        try:
            video_ids, channel_stats = get_channel_latest_videos(channel_id, api_key, max_results=5)
            if not video_ids:
                continue

            video_stats = get_video_stats(video_ids, api_key)
            total_views = sum(v["view_count"] for v in video_stats.values())

            records.append({
                "snapshot_date": today,
                "source": "topic_channel",
                "artist_name": artist_name,
                "channel_id": channel_id,
                "channel_view_count": int(channel_stats.get("viewCount", 0)),
                "channel_subscriber_count": int(channel_stats.get("subscriberCount", 0)),
                "recent_videos_count": len(video_ids),
                "recent_videos_total_views": total_views,
                "top_video": max(video_stats.values(), key=lambda x: x["view_count"]) if video_stats else None,
            })
            time.sleep(0.3)
        except Exception as e:
            print(f"    Topic channel error for {artist_name}: {e}")

    # Drake rollout channel monitoring — runs daily May 5–22
    from datetime import date as _date
    window_start = _date(2026, 5, 5)
    window_end   = _date(2026, 5, 22)
    today_date   = _date.today()

    if window_start <= today_date <= window_end:
        print("  YouTube: Drake rollout window active — monitoring channels...")

        # Check Drake Official + plottttwistttttt for new uploads
        for channel_name, channel_id in DRAKE_ROLLOUT_CHANNELS.items():
            try:
                videos, ch_stats = get_channel_recent_videos(channel_id, api_key, max_results=10)
                if not videos:
                    continue
                video_ids = [v["video_id"] for v in videos]
                video_stats = get_video_stats(video_ids, api_key)
                for v in videos:
                    vid_id = v["video_id"]
                    stats_data = video_stats.get(vid_id, {})
                    records.append({
                        "snapshot_date": today,
                        "source": "drake_rollout_channel",
                        "channel_name": channel_name,
                        "channel_id": channel_id,
                        **v,
                        **stats_data,
                    })
                print(f"    {channel_name}: {len(videos)} recent videos tracked")
                time.sleep(0.5)
            except Exception as e:
                print(f"    Error monitoring {channel_name}: {e}")

        # Search for Iceman reaction/commentary content (Akademiks etc)
        reactions = search_iceman_reaction_content(api_key)
        if reactions:
            # Get stats for reaction videos
            reaction_ids = [r["video_id"] for r in reactions]
            reaction_stats = get_video_stats(reaction_ids, api_key)
            for r in reactions:
                stats_data = reaction_stats.get(r["video_id"], {})
                records.append({
                    "snapshot_date": today,
                    "source": "iceman_reaction",
                    **r,
                    **stats_data,
                })
            print(f"    Found {len(reactions)} Iceman reaction/commentary videos")

    print(f"  YouTube stats: {len(records)} records collected")
    return records


def discover_topic_channels(api_key):
    """
    Weekly job: discover and cache Topic channel IDs for tracked artists.
    Expensive (100 units/search) so only runs Mondays.
    Saves results to data/processed/topic_channel_ids.json
    """
    if date.today().weekday() != 0:  # Monday only
        print("  YouTube topic discovery: skipping (runs Mondays only)")
        return

    if not api_key:
        return

    import re as _re
    RAW.parent.joinpath("processed").mkdir(parents=True, exist_ok=True)
    cache_file = RAW.parent / "processed" / "topic_channel_ids.json"
    existing = json.loads(cache_file.read_text()) if cache_file.exists() else {}

    new_finds = 0
    for artist in TOPIC_ARTISTS:
        if artist in existing:
            continue
        channel_id = find_topic_channel(artist, api_key)
        if channel_id:
            existing[artist] = channel_id
            print(f"    Found topic channel: {artist} -> {channel_id}")
            new_finds += 1
        time.sleep(1.0)  # search is quota-expensive, be careful

    cache_file.write_text(json.dumps(existing, indent=2))
    print(f"  YouTube topic discovery: found {new_finds} new channels, {len(existing)} total cached")


def collect_heatmaps(force=False):
    """Weekly heatmap scrape — runs Mondays only."""
    import re as _re

    if date.today().weekday() != 0 and not force:
        print("  YouTube heatmaps: skipping (only runs Mondays)")
        return []

    today = date.today().isoformat()
    records = []

    for track_name, video_id in TRACK_VIDEOS.items():
        print(f"    Heatmap: {track_name}")
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            r = requests.get(url, headers=HEATMAP_HEADERS, timeout=20)
            if r.status_code != 200:
                continue

            match = _re.search(r"var ytInitialData = ({.*?});</script>", r.text, _re.DOTALL)
            if not match:
                continue

            data = json.loads(match.group(1))
            segments = []

            # Try to find heatmap data
            try:
                mutations = (data.get("frameworkUpdates", {})
                                 .get("entityBatchUpdate", {})
                                 .get("mutations", []))
                for mutation in mutations:
                    markers = (mutation.get("payload", {})
                                      .get("macroMarkersListEntity", {})
                                      .get("markersList", {})
                                      .get("markerInfos", []))
                    if markers:
                        for m in markers:
                            mr = m.get("heatMarkerRenderer", m)
                            segments.append({
                                "start_ms": mr.get("timeRangeStartMillis", 0),
                                "intensity": round(float(mr.get("heatMarkerIntensityScoreNormalized", 0)), 4),
                            })
                        break
            except Exception:
                pass

            if segments:
                intensities = [s["intensity"] for s in segments]
                peak = max(segments, key=lambda x: x["intensity"])
                records.append({
                    "snapshot_date": today,
                    "track_name": track_name,
                    "video_id": video_id,
                    "segment_count": len(segments),
                    "avg_intensity": round(sum(intensities) / len(intensities), 4),
                    "max_intensity": round(max(intensities), 4),
                    "peak_timestamp_ms": peak["start_ms"],
                    "peak_timestamp_s": peak["start_ms"] // 1000,
                })
                print(f"      {len(segments)} segments, peak at {peak['start_ms']//1000}s")
            else:
                print(f"      No heatmap data")

        except Exception as e:
            print(f"      Error: {e}")
        time.sleep(3)

    print(f"  YouTube heatmaps: {len(records)} videos scraped")
    return records
