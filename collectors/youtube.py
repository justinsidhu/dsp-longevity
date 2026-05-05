"""
YouTube collector — two modes:
1. Official API: view counts, like counts, channel stats (requires API key)
2. Free heatmap scrape: intensityScoreNormalized array from ytInitialData
   No API key needed for heatmap — direct HTTP parse of page response.

Heatmap is pulled WEEKLY not daily (data doesn't change minute-to-minute).
"""

import re, json, time, requests
from datetime import date

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Artist name -> their official YouTube channel ID
# Get channel ID from: youtube.com/@artistname/about -> view source -> "channelId"
ARTIST_CHANNELS = {
    "Kendrick Lamar":   "UCCgGCBGzBmMnFtjPFOONHSg",
    "Drake":            "UCByOQJjeasppilrpv_5swBA",
    "Taylor Swift":     "UCqECaJ8Gagnn7YCbPEzWH6g",
    "Bad Bunny":        "UCsR3_GeAIcCXfDPGGQQirlQ",
    "The Weeknd":       "UCF9IOB2TExg3QIBupFtBDxg",
    "Billie Eilish":    "UCiGm_E4ZwYSHV3bcW1pnmVg",
    "Doja Cat":         "UCkTDp1bHSw5o9TRKp-NBzEw",
    "SZA":              "UCNO2rFMtFuYHzXRPGkbOvXA",
    "Sabrina Carpenter":"UCPUfdcQ1LxKqhIkdp0S1KAQ",
    "Olivia Rodrigo":   "UCRyjjRnNFjWbgeFbfJVHhJg",
}

# Track name -> YouTube video ID for official music videos
# These are the videos we pull heatmaps for
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


# ── OFFICIAL API ──────────────────────────────────────────────────────────────

def collect_youtube_stats(api_key):
    """Pull view/like counts for tracked music videos via official API."""
    if not api_key:
        print("  YouTube stats: no API key, skipping")
        return []

    today = date.today().isoformat()
    video_ids = list(TRACK_VIDEOS.values())
    records = []

    # videos.list costs 1 unit per call — very quota-friendly
    chunk_size = 50
    for i in range(0, len(video_ids), chunk_size):
        chunk = video_ids[i:i+chunk_size]
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "statistics,snippet",
                "id": ",".join(chunk),
                "key": api_key,
            },
            timeout=15,
        )
        if r.status_code != 200:
            print(f"  YouTube API error: {r.status_code}")
            continue

        for item in r.json().get("items", []):
            vid_id = item["id"]
            stats = item.get("statistics", {})
            track_name = next(
                (k for k, v in TRACK_VIDEOS.items() if v == vid_id), vid_id
            )
            records.append({
                "snapshot_date": today,
                "video_id": vid_id,
                "track_name": track_name,
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
                "published_at": item["snippet"].get("publishedAt"),
            })

    print(f"  YouTube stats: {len(records)} videos tracked")
    return records


# ── FREE HEATMAP SCRAPE ───────────────────────────────────────────────────────

def scrape_heatmap(video_id):
    """
    Extract most-replayed heatmap from YouTube page response.
    Parses ytInitialData JSON blob embedded in the HTML.
    Returns list of {start_ms, end_ms, intensity} dicts, or None on failure.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return None

        html = r.text

        # Extract ytInitialData JSON blob
        match = re.search(r"var ytInitialData = ({.*?});</script>", html, re.DOTALL)
        if not match:
            # Try alternate pattern
            match = re.search(r"ytInitialData\s*=\s*({.*?});\s*(?:var|</script>)", html, re.DOTALL)
        if not match:
            return None

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

        # Navigate to heatmap data — path varies by YouTube version
        # Try primary path
        heatmap_data = None
        try:
            framework = data.get("frameworkUpdates", {})
            entity_batch = framework.get("entityBatchUpdate", {})
            mutations = entity_batch.get("mutations", [])
            for mutation in mutations:
                payload = mutation.get("payload", {})
                mc = payload.get("macroMarkersListEntity", {})
                contents = mc.get("markersList", {}).get("markerInfos", [])
                if contents:
                    heatmap_data = contents
                    break
        except Exception:
            pass

        # Try alternate path via playerOverlays
        if not heatmap_data:
            try:
                overlays = (
                    data.get("playerOverlays", {})
                    .get("playerOverlayRenderer", {})
                    .get("decoratedPlayerBarRenderer", {})
                    .get("decoratedPlayerBarRenderer", {})
                    .get("playerBar", {})
                    .get("multiMarkersPlayerBarRenderer", {})
                    .get("markersMap", [])
                )
                for marker in overlays:
                    if marker.get("key") == "HEATSEEK":
                        heatmap_data = (
                            marker.get("value", {})
                            .get("heatmap", {})
                            .get("heatmapRenderer", {})
                            .get("heatMarkers", [])
                        )
                        break
            except Exception:
                pass

        if not heatmap_data:
            return None

        # Parse into clean format
        segments = []
        for marker in heatmap_data:
            # Handle both marker formats
            m = marker.get("heatMarkerRenderer", marker)
            start = m.get("timeRangeStartMillis", m.get("visibleTimeRangeStartMillis", 0))
            duration = m.get("markerDurationMillis", m.get("timeRangeDurationMillis", 2500))
            intensity = m.get("heatMarkerIntensityScoreNormalized",
                              m.get("intensityScoreNormalized", 0))
            segments.append({
                "start_ms": start,
                "end_ms": start + duration,
                "intensity": round(float(intensity), 4),
            })

        return segments if segments else None

    except Exception as e:
        print(f"    Heatmap scrape error for {video_id}: {e}")
        return None


def collect_heatmaps(force=False):
    """
    Pull heatmaps for all tracked videos. Only runs on Mondays unless forced,
    since heatmap data accumulates slowly.
    """
    from datetime import datetime
    today = date.today()
    is_monday = today.weekday() == 0

    if not is_monday and not force:
        print("  YouTube heatmaps: skipping (only runs Mondays)")
        return []

    records = []
    for track_name, video_id in TRACK_VIDEOS.items():
        print(f"    Heatmap: {track_name}")
        segments = scrape_heatmap(video_id)

        if segments:
            # Store summary stats + top 3 peak moments
            intensities = [s["intensity"] for s in segments]
            peak_segments = sorted(segments, key=lambda x: x["intensity"], reverse=True)[:3]

            records.append({
                "snapshot_date": today.isoformat(),
                "track_name": track_name,
                "video_id": video_id,
                "segment_count": len(segments),
                "avg_intensity": round(sum(intensities) / len(intensities), 4),
                "max_intensity": round(max(intensities), 4),
                "peak_moments": peak_segments,  # top 3 most-replayed timestamps
                "full_heatmap": segments,
            })
            print(f"      {len(segments)} segments, peak at {peak_segments[0]['start_ms']/1000:.0f}s")
        else:
            print(f"      No heatmap data (video may be too new or under 50K views)")

        time.sleep(3)  # be respectful between page fetches

    print(f"  YouTube heatmaps: {len(records)} videos scraped")
    return records
