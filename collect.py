"""
collect.py — daily runner
Collects all signals, computes novel metrics, sends Telegram research dialogue.
"""

import os, sys, json, time, requests
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
JOURNAL = ROOT / "data" / "journal"
JOURNAL.mkdir(parents=True, exist_ok=True)

from collectors.spotify import SpotifyCollector
from collectors.billboard import collect_billboard
from collectors.wikipedia import collect_wikipedia
from collectors.trends import collect_trends
from collectors.youtube import collect_youtube_stats, collect_heatmaps, discover_topic_channels
from collectors.shazam import collect_shazam
from collectors.kalshi import collect_kalshi
from collectors.polymarket import collect_polymarket
from collectors.scoring import (
    compute_divergence_scores,
    compute_playlist_survival,
    compute_echo_chamber_trend,
    generate_research_prompt,
)


def append_jsonl(path, records):
    if not records:
        return
    with open(path, "a") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def send_telegram(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })
    return r.status_code == 200


def build_daily_report(today, divergence_scores, survival_records, echo_trend, stats):
    """Build the data report section of the Telegram message."""
    lines = [
        f"📡 *DSP Longevity — {today}*",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"*Signals collected*",
        f"🎵 Spotify tracks: {stats.get('spotify_tracks', 0)}",
        f"📊 Billboard entries: {stats.get('billboard', 0)}",
        f"🔍 Google Trends: {stats.get('trends', 0)} artists",
        f"📖 Wikipedia: {stats.get('wikipedia', 0)} artists",
        f"▶️ YouTube stats: {stats.get('youtube_stats', 0)} videos",
        f"🎲 Kalshi markets: {stats.get('kalshi', 0)}",
        f"🎲 Polymarket markets: {stats.get('polymarket', 0)}",
        "",
    ]

    # Top divergences
    if divergence_scores:
        lines.append("*Top signal divergences today*")
        for s in divergence_scores[:3]:
            icon = "🔴" if s["interpretation"] == "streaming_ahead" else \
                   "🟢" if s["interpretation"] == "culture_ahead" else "🟡"
            direction = (
                "Spotify > culture" if s["interpretation"] == "streaming_ahead" else
                "Culture > Spotify" if s["interpretation"] == "culture_ahead" else
                "Aligned"
            )
            lines.append(
                f"{icon} *{s['artist_name']}*: {s['divergence_score']:+.1f} ({direction})"
            )
        lines.append("")

    # Playlist survivors (tracks on same playlist 14+ days)
    long_survivors = [r for r in survival_records
                      if r["survival_rate"] > 0.85 and r["days_eligible"] >= 14 and r["still_present"]]
    if long_survivors:
        lines.append("*Playlist survivors (14+ days)*")
        for s in long_survivors[:3]:
            lines.append(
                f"🏆 {s['track_name']} — {s['playlist_name']} "
                f"({s['survival_rate']*100:.0f}%)"
            )
        lines.append("")

    # Echo chamber
    if echo_trend:
        latest_echo = echo_trend[-1]
        lines.append(
            f"*Echo Chamber Index*: {latest_echo['avg_overlap']:.3f} "
            f"(avg playlist overlap across {latest_echo['playlist_pairs']} pairs)"
        )
        lines.append("")

    return "\n".join(lines)


def log_research_entry(prompt):
    """Log the daily research prompt to the journal."""
    today = date.today().isoformat()
    entry = {
        "date": today,
        "type": "daily_prompt",
        "prompt": prompt,
        "response": None,  # filled when you reply via Telegram
    }
    path = JOURNAL / f"{today}.json"
    with open(path, "w") as f:
        json.dump(entry, f, indent=2)
    # Also append to running log
    append_jsonl(JOURNAL / "research_log.jsonl", [entry])


def main():
    today = date.today().isoformat()
    print(f"\n[{today}] Starting collection run...\n")

    stats = {}

    # ── SPOTIFY ───────────────────────────────────────────────────────────────
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    if client_id and client_secret:
        print("Spotify: tracking Billboard artists...")
        sp = SpotifyCollector(client_id, client_secret)
        artist_records, echo_records, release_records = sp.collect_playlists()

        append_jsonl(RAW / "spotify_new_releases.jsonl", release_records)
        append_jsonl(RAW / "echo_chamber.jsonl", echo_records)
        append_jsonl(RAW / "spotify_artists.jsonl", artist_records)

        stats["spotify_releases"] = len(release_records)
        stats["spotify_artists"] = len(artist_records)
        print(f"  Spotify: {len(artist_records)} artists tracked, {len(release_records)} new releases\n")
    else:
        print("Spotify: no credentials, skipping\n")

    # ── BILLBOARD ─────────────────────────────────────────────────────────────
    print("Billboard: collecting Hot 100...")
    bb_records = collect_billboard()
    append_jsonl(RAW / "billboard.jsonl", bb_records)
    stats["billboard"] = len(bb_records)
    print()

    # ── WIKIPEDIA ─────────────────────────────────────────────────────────────
    print("Wikipedia: collecting pageviews...")
    wiki_records = collect_wikipedia()
    append_jsonl(RAW / "wikipedia.jsonl", wiki_records)
    stats["wikipedia"] = len(wiki_records)
    print()

    # ── GOOGLE TRENDS ─────────────────────────────────────────────────────────
    print("Google Trends: collecting interest scores...")
    trend_records = collect_trends()
    append_jsonl(RAW / "google_trends.jsonl", trend_records)
    stats["trends"] = len(trend_records)
    print()

    # ── SHAZAM ────────────────────────────────────────────────────────────────
    print("Shazam: collecting charts and listening counts...")
    shazam_chart, shazam_discovery, shazam_counts = collect_shazam()
    append_jsonl(RAW / "shazam_chart.jsonl", shazam_chart)
    append_jsonl(RAW / "shazam_discovery.jsonl", shazam_discovery)
    append_jsonl(RAW / "shazam_counts.jsonl", shazam_counts)
    stats["shazam_chart"] = len(shazam_chart)
    stats["shazam_discovery"] = len(shazam_discovery)
    print()

    # ── PREDICTION MARKETS ───────────────────────────────────────────────────────
    print("Kalshi: collecting music markets...")
    kalshi_records = collect_kalshi()
    append_jsonl(RAW / "kalshi.jsonl", kalshi_records)
    stats["kalshi"] = len(kalshi_records)
    print()

    print("Polymarket: collecting music markets...")
    poly_records = collect_polymarket()
    append_jsonl(RAW / "polymarket.jsonl", poly_records)
    stats["polymarket"] = len(poly_records)
    print()

    # ── YOUTUBE ───────────────────────────────────────────────────────────────
    yt_api_key = os.environ.get("YOUTUBE_API_KEY")
    print("YouTube: collecting stats...")
    yt_stats = collect_youtube_stats(yt_api_key)
    append_jsonl(RAW / "youtube_stats.jsonl", yt_stats)
    stats["youtube_stats"] = len(yt_stats)

    print("YouTube: discovering topic channels (Mondays only)...")
    discover_topic_channels(yt_api_key)

    print("YouTube: collecting heatmaps (Mondays only)...")
    yt_heatmaps = collect_heatmaps()
    append_jsonl(RAW / "youtube_heatmaps.jsonl", yt_heatmaps)
    stats["youtube_heatmaps"] = len(yt_heatmaps)
    print()

    # ── SCORING ───────────────────────────────────────────────────────────────
    print("Computing novel metrics...")
    divergence_scores = compute_divergence_scores()
    append_jsonl(RAW / "divergence_scores.jsonl", divergence_scores)

    survival_records = compute_playlist_survival()
    append_jsonl(RAW / "playlist_survival.jsonl", survival_records)

    echo_trend = compute_echo_chamber_trend()
    print()

    # ── TELEGRAM ──────────────────────────────────────────────────────────────
    tg_token = os.environ.get("TELEGRAM_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID")

    if tg_token and tg_chat:
        print("Sending Telegram digest...")

        # Part 1: data report
        report = build_daily_report(today, divergence_scores, survival_records, echo_trend, stats)
        send_telegram(tg_token, tg_chat, report)
        time.sleep(2)

        # Part 2: research prompt (separate message so it feels like a dialogue)
        prompt = generate_research_prompt(divergence_scores, survival_records, echo_trend)
        research_msg = (
            f"🔬 *Today's research question*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{prompt}\n\n"
            f"_Reply to this to log your hypothesis in the research journal._"
        )
        send_telegram(tg_token, tg_chat, research_msg)

        # Log the prompt
        log_research_entry(prompt)
        print("  Telegram: sent ✓")
    else:
        print("Telegram: no credentials, skipping")

    print(f"\n[{today}] Collection complete.")
    print(f"Total records: {sum(v for v in stats.values())}")


if __name__ == "__main__":
    main()
