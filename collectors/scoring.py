"""
Divergence scoring engine.

Computes two novel metrics daily:
1. Divergence Score — gap between Spotify popularity and cross-signal average
   High = platform behavior diverging from cultural behavior
   Positive = Spotify higher than culture signals (passive streaming, losing relevance)
   Negative = Culture signals higher than Spotify (rising, or post-catalog resurgence)

2. Playlist Survival Rate — % of days a track has appeared on each playlist
   since first observed. High = editorially durable.

3. Echo Chamber Index — rolling average playlist overlap across tracked playlists.
   Higher = algorithmic convergence, narrowing discovery surface.
"""

import json
from pathlib import Path
from datetime import date
from collections import defaultdict

RAW = Path(__file__).parent.parent / "data" / "raw"
PROCESSED = Path(__file__).parent.parent / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)


def load_jsonl(path):
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def normalize(value, min_val, max_val):
    """Normalize a value to 0-100 scale."""
    if max_val == min_val:
        return 50.0
    return round(((value - min_val) / (max_val - min_val)) * 100, 2)


def compute_divergence_scores():
    """
    For each artist with data in multiple signals today,
    compute normalized divergence score.
    """
    today = date.today().isoformat()

    # Load latest data from each signal
    spotify_records = load_jsonl(RAW / "spotify_artists.jsonl")
    wiki_records = load_jsonl(RAW / "wikipedia.jsonl")
    trend_records = load_jsonl(RAW / "google_trends.jsonl")
    billboard_records = load_jsonl(RAW / "billboard.jsonl")

    # Get today's data per artist
    spotify_today = {r["artist_name"]: r for r in spotify_records if r["snapshot_date"] == today}
    wiki_today = {r["artist_name"]: r for r in wiki_records if r["snapshot_date"] == today}
    trends_today = {r["artist_name"]: r for r in trend_records if r["snapshot_date"] == today}

    # Billboard: build artist -> best chart position map for today
    billboard_today = {}
    for r in billboard_records:
        if r["snapshot_date"] == today:
            artist = r.get("artist", "")
            pos = r.get("position") or 101  # B200 catalog records have None position
            weeks = r.get("weeks_on_chart") or 0
            # Multiple entries possible (featured artists) — take best position
            existing_pos = billboard_today.get(artist, {}).get("position", 999)
            if artist not in billboard_today or pos < existing_pos:
                billboard_today[artist] = {
                    "position": pos,
                    "weeks_on_chart": weeks,
                    "peak_position": r.get("peak_position"),
                }

    # Normalize Wikipedia pageviews (log scale — pageviews vary wildly)
    import math
    wiki_values = [r["pageviews"] for r in wiki_today.values() if r.get("pageviews", 0) > 0]
    wiki_min = min(wiki_values) if wiki_values else 1
    wiki_max = max(wiki_values) if wiki_values else 1

    scores = []
    all_artists = set(spotify_today) | set(wiki_today) | set(trends_today)

    for artist in all_artists:
        signals = {}
        signal_count = 0

        # Spotify popularity (0-100, already normalized)
        if artist in spotify_today:
            signals["spotify_popularity"] = spotify_today[artist]["popularity"]
            signal_count += 1

        # Wikipedia (normalize log pageviews to 0-100)
        if artist in wiki_today and wiki_today[artist].get("pageviews", 0) > 0:
            log_views = math.log1p(wiki_today[artist]["pageviews"])
            log_min = math.log1p(wiki_min)
            log_max = math.log1p(wiki_max)
            signals["wikipedia_score"] = normalize(log_views, log_min, log_max)
            signal_count += 1

        # Google Trends (0-100, already normalized by Google)
        if artist in trends_today:
            signals["trends_score"] = trends_today[artist]["trend_score"]
            signal_count += 1

        # Billboard: convert position to score (1 = 100, 100 = 1, not charting = 0)
        if artist in billboard_today:
            pos = billboard_today[artist]["position"]
            signals["billboard_score"] = round((101 - pos) / 100 * 100, 1)
            signals["billboard_weeks"] = billboard_today[artist]["weeks_on_chart"]
            signal_count += 1

        # Need at least 2 signals to compute divergence
        if signal_count < 2 or "spotify_popularity" not in signals:
            continue

        # Divergence = Spotify vs average of all other signals
        other_signals = [v for k, v in signals.items()
                         if k != "spotify_popularity" and isinstance(v, (int, float))]
        if not other_signals:
            continue

        other_avg = sum(other_signals) / len(other_signals)
        divergence = round(signals["spotify_popularity"] - other_avg, 2)

        scores.append({
            "snapshot_date": today,
            "artist_name": artist,
            "divergence_score": divergence,
            "spotify_popularity": signals.get("spotify_popularity"),
            "wikipedia_score": signals.get("wikipedia_score"),
            "trends_score": signals.get("trends_score"),
            "billboard_score": signals.get("billboard_score"),
            "billboard_weeks": signals.get("billboard_weeks"),
            "signals_available": signal_count,
            "interpretation": (
                "streaming_ahead" if divergence > 15 else
                "culture_ahead" if divergence < -15 else
                "aligned"
            ),
        })

    # Sort by absolute divergence — most interesting first
    scores.sort(key=lambda x: abs(x["divergence_score"]), reverse=True)
    print(f"  Divergence: computed scores for {len(scores)} artists")
    return scores


def compute_playlist_survival():
    """
    For each track, compute what % of days it has appeared
    on each playlist since first observed.
    """
    today = date.today().isoformat()
    track_records = load_jsonl(RAW / "spotify_tracks.jsonl")

    # Group by track_id + playlist_name
    appearances = defaultdict(set)  # (track_id, playlist) -> set of dates
    track_meta = {}

    for r in track_records:
        key = (r["track_id"], r["playlist_name"])
        appearances[key].add(r["snapshot_date"])
        if r["track_id"] not in track_meta:
            track_meta[r["track_id"]] = {
                "track_name": r["track_name"],
                "artist_name": r["artist_name"],
            }

    # Get all dates we've collected
    all_dates = sorted({r["snapshot_date"] for r in track_records})
    if not all_dates:
        return []

    survival_records = []
    for (track_id, playlist), dates_seen in appearances.items():
        first_seen = min(dates_seen)
        # Days eligible = days from first_seen to today
        eligible = [d for d in all_dates if d >= first_seen]
        survival_rate = len(dates_seen) / len(eligible) if eligible else 0

        survival_records.append({
            "snapshot_date": today,
            "track_id": track_id,
            "track_name": track_meta.get(track_id, {}).get("track_name", ""),
            "artist_name": track_meta.get(track_id, {}).get("artist_name", ""),
            "playlist_name": playlist,
            "first_seen": first_seen,
            "days_observed": len(dates_seen),
            "days_eligible": len(eligible),
            "survival_rate": round(survival_rate, 4),
            "still_present": today in dates_seen,
        })

    # Sort by survival rate descending
    survival_records.sort(key=lambda x: x["survival_rate"], reverse=True)
    print(f"  Survival: computed rates for {len(survival_records)} track-playlist pairs")
    return survival_records


def compute_echo_chamber_trend():
    """Rolling 7-day average echo chamber index across all playlist pairs."""
    today = date.today().isoformat()
    echo_records = load_jsonl(RAW / "echo_chamber.jsonl")

    if not echo_records:
        return []

    # Get dates from last 30 days
    dates = sorted({r["snapshot_date"] for r in echo_records})[-30:]

    trend = []
    for d in dates:
        day_records = [r for r in echo_records if r["snapshot_date"] == d]
        if day_records:
            avg_overlap = sum(r["overlap_score"] for r in day_records) / len(day_records)
            trend.append({
                "snapshot_date": d,
                "avg_overlap": round(avg_overlap, 4),
                "playlist_pairs": len(day_records),
                "max_overlap": max(r["overlap_score"] for r in day_records),
            })

    return trend


def generate_research_prompt(divergence_scores, survival_records, echo_trend):
    """
    Generate a daily research question based on what's most interesting in the data.
    Returns a string to be sent via Telegram.
    """
    if not divergence_scores:
        return "No divergence data available today. Check collector logs."

    # Find most interesting divergence
    top = divergence_scores[0]
    artist = top["artist_name"]
    div = top["divergence_score"]

    if top["interpretation"] == "streaming_ahead":
        scenario = (
            f"*{artist}* has Spotify popularity {abs(div):.0f}pts above their cultural signals "
            f"(Google Trends, Wikipedia, Billboard).\n\n"
            f"This could mean:\n"
            f"A) Passive playlist streams inflating popularity without active fan engagement\n"
            f"B) International streaming strong while US cultural interest fades\n"
            f"C) Catalog mode — loyal listeners, not new discovery\n\n"
            f"*Which do you think, and why?*"
        )
    elif top["interpretation"] == "culture_ahead":
        scenario = (
            f"*{artist}* has cultural signals running {abs(div):.0f}pts above their Spotify score.\n\n"
            f"This could mean:\n"
            f"A) Rising artist — cultural buzz before streaming catches up\n"
            f"B) Controversy or news moment driving search without streaming\n"
            f"C) Fanbase more active on other platforms than Spotify\n\n"
            f"*Which do you think, and why?*"
        )
    else:
        # Find most durable playlist survivor instead
        survivors = [r for r in survival_records if r["survival_rate"] > 0.8 and r["days_eligible"] > 7]
        if survivors:
            s = survivors[0]
            scenario = (
                f"*{s['track_name']}* by {s['artist_name']} has survived on "
                f"*{s['playlist_name']}* for {s['days_observed']} of {s['days_eligible']} days "
                f"({s['survival_rate']*100:.0f}% survival rate).\n\n"
                f"Hypothesis to test: does high playlist survival correlate with "
                f"growing Wikipedia pageviews, or does it predict them?\n\n"
                f"*What's your read on what's driving this track's durability?*"
            )
        else:
            scenario = (
                f"Signals are largely aligned today — no major divergences.\n\n"
                f"*Research prompt:* As more data accumulates, what relationship "
                f"are you most curious to test? Playlist survival vs. chart longevity? "
                f"Echo chamber index vs. breakout artists?\n\n"
                f"*Reply to log your hypothesis.*"
            )

    # Add echo chamber note if we have trend data
    echo_note = ""
    if len(echo_trend) >= 2:
        latest = echo_trend[-1]["avg_overlap"]
        prev = echo_trend[-2]["avg_overlap"]
        delta = latest - prev
        direction = "↑ increasing" if delta > 0.01 else "↓ decreasing" if delta < -0.01 else "→ stable"
        echo_note = f"\n\n📊 Echo Chamber Index: {latest:.3f} ({direction})"

    return scenario + echo_note
