"""
collect.py — daily runner
Collects all signals, computes novel metrics, sends rich Telegram digest.
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
from collectors.shazam import collect_shazam
from collectors.lastfm import collect_lastfm
from collectors.reddit import collect_reddit
from collectors.hits_daily_double import collect_hits_daily_double
from collectors.genius import collect_genius
from collectors.apple_music import collect_apple_music
from collectors.kalshi import collect_kalshi
from collectors.polymarket import collect_polymarket
from collectors.youtube import collect_youtube_stats, collect_heatmaps, discover_topic_channels
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


def load_jsonl(path):
    if not Path(path).exists():
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def send_telegram(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })
    return r.status_code == 200


# ── MESSAGE BUILDERS ──────────────────────────────────────────────────────────

def msg_header(today, stats):
    """Message 1: System status + signal counts."""
    spotify_artists = stats.get("spotify_artists", 0)
    new_releases = stats.get("spotify_releases", 0)
    release_flag = f" · 🆕 {new_releases} new releases" if new_releases > 0 else ""

    return (
        f"📡 *DSP Longevity Intelligence — {today}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Signals collected today*\n"
        f"🎵 Spotify artists: {spotify_artists}{release_flag}\n"
        f"📊 Billboard Hot 100: {stats.get('billboard', 0)} entries\n"
        f"💿 Billboard 200: {stats.get('billboard_200', 0)} albums\n"
        f"📖 Wikipedia pageviews: {stats.get('wikipedia', 0)} artists\n"
        f"🎶 Shazam chart: {stats.get('shazam_chart', 0)} tracks\n"
        f"🌍 Last.fm listeners: {stats.get('lastfm', 0)} artists\n"
        f"💬 Reddit posts: {stats.get('reddit', 0)} artists tracked\n"
        f"📝 Genius annotations: {stats.get('genius', 0)} records\n"
        f"🍎 Apple Music chart: {stats.get('apple_music', 0)} entries\n"
        f"📈 Hits Daily Double: {stats.get('hits_daily_double', 0)} entries\n"
        f"▶️ YouTube stats: {stats.get('youtube_stats', 0)} videos\n"
        f"🎲 Kalshi markets: {stats.get('kalshi', 0)}\n"
        f"🎰 Polymarket markets: {stats.get('polymarket', 0)}\n"
    )


def msg_velocity(today):
    """Message 2: Artist velocity — breakouts and fading."""
    records = load_jsonl(RAW / "spotify_artists.jsonl")
    today_records = [r for r in records if r.get("snapshot_date") == today]

    if not today_records:
        return None

    breakouts = [r for r in today_records if r.get("velocity_tier") == "breakout"]
    rising = [r for r in today_records if r.get("velocity_tier") == "rising"]
    fading = [r for r in today_records if r.get("velocity_tier") == "fading"]
    declining = [r for r in today_records if r.get("velocity_tier") == "declining"]

    breakouts.sort(key=lambda x: x.get("velocity_score", 0), reverse=True)
    declining.sort(key=lambda x: x.get("velocity_score", 0))

    lines = ["🚀 *Artist Velocity Report*", "━━━━━━━━━━━━━━━━━━━━━━", ""]

    if breakouts or rising:
        lines.append("*📈 Gaining momentum*")
        for r in (breakouts + rising)[:5]:
            delta = r.get("velocity_score", 0)
            pop = r.get("popularity", 0)
            tier = r.get("label_tier", "unknown")
            tier_icon = {"major": "🏢", "major_indie": "🤝", "indie": "🎸",
                         "self_released": "✊", "services": "🔧"}.get(tier, "❓")
            lines.append(
                f"{tier_icon} *{r['artist_name']}*: {pop} pop ({delta:+d} pts) · {r.get('label_canonical') or tier}"
            )
        lines.append("")

    if fading or declining:
        lines.append("*📉 Losing momentum*")
        for r in (declining + fading)[:5]:
            delta = r.get("velocity_score", 0)
            pop = r.get("popularity", 0)
            tier = r.get("label_tier", "unknown")
            tier_icon = {"major": "🏢", "major_indie": "🤝", "indie": "🎸",
                         "self_released": "✊", "services": "🔧"}.get(tier, "❓")
            lines.append(
                f"{tier_icon} *{r['artist_name']}*: {pop} pop ({delta:+d} pts) · {r.get('label_canonical') or tier}"
            )
        lines.append("")

    # Label tier breakdown
    tier_counts = {}
    for r in today_records:
        t = r.get("label_tier", "unknown")
        tier_counts[t] = tier_counts.get(t, 0) + 1

    lines.append("*Label tier breakdown*")
    tier_labels = {"major": "🏢 Major", "major_indie": "🤝 Major-distrib indie",
                   "indie": "🎸 True indie", "self_released": "✊ Self-released",
                   "services": "🔧 Services", "unknown": "❓ Unknown"}
    for tier, label in tier_labels.items():
        count = tier_counts.get(tier, 0)
        if count > 0:
            lines.append(f"{label}: {count}")

    return "\n".join(lines)


def msg_new_releases(today):
    """Message 3: New releases detected (only sent if there are any)."""
    records = load_jsonl(RAW / "spotify_new_releases.jsonl")
    today_releases = [r for r in records if r.get("snapshot_date") == today]

    if not today_releases:
        return None

    lines = ["🆕 *New Releases Detected*", "━━━━━━━━━━━━━━━━━━━━━━", ""]

    for r in today_releases[:8]:
        tier = r.get("label_tier", "unknown")
        tier_icon = {"major": "🏢", "major_indie": "🤝", "indie": "🎸",
                     "self_released": "✊"}.get(tier, "❓")
        release_type = r.get("album_type", "release").upper()
        masters = r.get("master_ownership", "unknown")
        lines.append(
            f"{tier_icon} *{r['artist_name']}* — {r['album_name']}\n"
            f"   {release_type} · {r.get('release_date')} · Masters: {masters}\n"
            f"   {r.get('label_canonical') or r.get('label_raw') or 'Unknown label'}"
        )
        lines.append("")

    return "\n".join(lines)


def msg_divergence(divergence_scores, today):
    """Message 4: Signal divergence analysis."""
    if not divergence_scores:
        return None

    lines = ["🔬 *Signal Divergence Analysis*", "━━━━━━━━━━━━━━━━━━━━━━", ""]

    # Load spotify data for context
    sp_records = load_jsonl(RAW / "spotify_artists.jsonl")
    sp_today = {r["artist_name"]: r for r in sp_records if r.get("snapshot_date") == today}

    lines.append("*Biggest platform vs. culture gaps*")
    lines.append("_(+) = Spotify ahead of cultural signals_")
    lines.append("_(-) = Cultural signals ahead of Spotify_")
    lines.append("")

    for s in divergence_scores[:5]:
        artist = s["artist_name"]
        div = s["divergence_score"]
        interp = s["interpretation"]

        if interp == "streaming_ahead":
            icon = "🔴"
            analysis = "Platform manufacturing popularity? Passive streams may not reflect active fandom."
        elif interp == "culture_ahead":
            icon = "🟢"
            analysis = "Cultural momentum ahead of platform. Watch for Spotify catch-up."
        else:
            icon = "🟡"
            analysis = "Signals aligned — genuine cross-platform relevance."

        sp_pop = s.get("spotify_popularity", "—")
        wiki = s.get("wikipedia_score")
        billboard = s.get("billboard_score")
        wiki_str = f"Wiki: {wiki:.0f}" if wiki else ""
        bb_str = f"BB: {billboard:.0f}" if billboard else ""
        signals_str = " · ".join(filter(None, [wiki_str, bb_str]))

        # Get velocity context
        velocity = sp_today.get(artist, {}).get("velocity_tier", "")
        vel_str = f" · {velocity}" if velocity else ""

        lines.append(
            f"{icon} *{artist}*: {div:+.1f}{vel_str}\n"
            f"   Spotify: {sp_pop} · {signals_str}\n"
            f"   _{analysis}_"
        )
        lines.append("")

    return "\n".join(lines)


def msg_markets(today):
    """Message 5: Prediction market outlook."""
    poly_records = load_jsonl(RAW / "polymarket.jsonl")
    kalshi_records = load_jsonl(RAW / "kalshi.jsonl")

    today_poly = [r for r in poly_records if r.get("snapshot_date") == today]
    today_kalshi = [r for r in kalshi_records if r.get("snapshot_date") == today]

    if not today_poly and not today_kalshi:
        return None

    lines = ["🎲 *Prediction Market Outlook*", "━━━━━━━━━━━━━━━━━━━━━━", ""]

    # Polymarket — sort by volume, show top markets
    if today_poly:
        today_poly.sort(key=lambda x: x.get("volume", 0), reverse=True)
        lines.append("*Polymarket — top music markets by volume*")

        for r in today_poly[:6]:
            question = r.get("question") or r.get("event_title") or "Unknown"
            volume = r.get("volume", 0)
            leading = r.get("leading_outcome")
            resolved = r.get("resolved", False)

            if resolved:
                resolution = r.get("resolution", "resolved")
                lines.append(f"✅ ~~{question[:50]}~~ → *{resolution}*")
            elif leading:
                prob = leading.get("probability")
                outcome = leading.get("outcome", "")
                prob_str = f"{prob:.0f}%" if prob else "—"
                vol_str = f"${volume:,.0f}" if volume > 0 else ""
                lines.append(
                    f"📌 *{question[:55]}*\n"
                    f"   Leading: {outcome} at {prob_str} · Vol: {vol_str}"
                )
            lines.append("")

    # Kalshi — show top markets
    if today_kalshi:
        today_kalshi.sort(key=lambda x: x.get("volume", 0), reverse=True)
        lines.append("*Kalshi — top music markets*")

        for r in today_kalshi[:4]:
            title = r.get("title") or r.get("subtitle") or "Unknown"
            yes_price = r.get("yes_price", 0)
            volume = r.get("volume", 0)
            vol_str = f"${volume:,.0f}" if volume > 0 else ""
            prob_str = f"{yes_price}¢" if yes_price else "—"
            lines.append(
                f"📌 *{title[:55]}*\n"
                f"   Yes: {prob_str} · Vol: {vol_str}"
            )
            lines.append("")

    return "\n".join(lines)


def msg_shazam_billboard(today):
    """Message 6: Shazam discovery signal + Billboard movers."""
    shazam = load_jsonl(RAW / "shazam_chart.jsonl")
    billboard = load_jsonl(RAW / "billboard.jsonl")

    today_shazam = [r for r in shazam if r.get("snapshot_date") == today]
    today_bb = [r for r in billboard if r.get("snapshot_date") == today]

    if not today_shazam and not today_bb:
        return None

    lines = ["📊 *Charts & Discovery*", "━━━━━━━━━━━━━━━━━━━━━━", ""]

    # Billboard biggest movers
    if today_bb:
        new_entries = [r for r in today_bb if r.get("is_new_entry") and r.get("position", 101) <= 40]
        big_risers = [r for r in today_bb if r.get("position_change", 0) >= 10]
        long_tenured = [r for r in today_bb if r.get("weeks_on_chart", 0) >= 20 and r.get("position", 101) <= 30]

        big_risers.sort(key=lambda x: x.get("position_change", 0), reverse=True)
        long_tenured.sort(key=lambda x: x.get("weeks_on_chart", 0), reverse=True)

        if new_entries:
            lines.append("*🆕 New Hot 100 entries (top 40)*")
            for r in new_entries[:3]:
                lines.append(f"#{r['position']} {r['song']} — {r['artist']}")
            lines.append("")

        if big_risers:
            lines.append("*⬆️ Biggest risers*")
            for r in big_risers[:3]:
                lines.append(f"+{r['position_change']} → #{r['position']} {r['song']} — {r['artist']}")
            lines.append("")

        if long_tenured:
            lines.append("*🏆 Longevity leaders (20+ weeks, top 30)*")
            for r in long_tenured[:3]:
                lines.append(f"#{r['position']} {r['song']} — {r.get('weeks_on_chart')}wks")
            lines.append("")

    # Shazam top 10 with context
    if today_shazam:
        lines.append("*🎶 Shazam US Top 10*")
        lines.append("_(Real-world ambient discovery signal)_")
        for r in today_shazam[:10]:
            lines.append(f"#{r['position']} {r['track_name']} — {r['artist_name']}")

    return "\n".join(lines)


def log_research_entry(prompt):
    today = date.today().isoformat()
    entry = {"date": today, "type": "daily_prompt", "prompt": prompt, "response": None}
    path = JOURNAL / f"{today}.json"
    with open(path, "w") as f:
        json.dump(entry, f, indent=2)
    append_jsonl(JOURNAL / "research_log.jsonl", [entry])


def main():
    today = date.today().isoformat()
    print(f"\n[{today}] Starting collection run...\n")

    stats = {}

    # ── BILLBOARD (first — Spotify uses this) ────────────────────────────────
    print("Billboard: collecting Hot 100 + Billboard 200...")
    bb_records = collect_billboard()
    append_jsonl(RAW / "billboard.jsonl", bb_records)
    hot100_count = len([r for r in bb_records if r.get("chart") == "hot-100"])
    b200_count = len([r for r in bb_records if r.get("chart") == "billboard-200"])
    stats["billboard"] = hot100_count
    stats["billboard_200"] = b200_count
    print()

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
        print(f"  Spotify: {len(artist_records)} artists, {len(release_records)} new releases\n")
    else:
        print("Spotify: no credentials, skipping\n")

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
    print("Shazam: collecting charts...")
    shazam_chart, shazam_discovery, shazam_counts = collect_shazam()
    append_jsonl(RAW / "shazam_chart.jsonl", shazam_chart)
    append_jsonl(RAW / "shazam_discovery.jsonl", shazam_discovery)
    append_jsonl(RAW / "shazam_counts.jsonl", shazam_counts)
    stats["shazam_chart"] = len(shazam_chart)
    stats["shazam_discovery"] = len(shazam_discovery)
    print()

    # ── LAST.FM ───────────────────────────────────────────────────────────────
    print("Last.fm: collecting global listener counts...")
    lastfm_records = collect_lastfm()
    append_jsonl(RAW / "lastfm.jsonl", lastfm_records)
    stats["lastfm"] = len(lastfm_records)
    print()

    # ── REDDIT ────────────────────────────────────────────────────────────────
    print("Reddit: collecting community activation...")
    reddit_records = collect_reddit()
    append_jsonl(RAW / "reddit.jsonl", reddit_records)
    stats["reddit"] = len(reddit_records)
    print()

    # ── HITS DAILY DOUBLE ─────────────────────────────────────────────────────
    print("Hits Daily Double: collecting midweek estimates...")
    hdd_records = collect_hits_daily_double()
    append_jsonl(RAW / "hits_daily_double.jsonl", hdd_records)
    stats["hits_daily_double"] = len(hdd_records)
    print()

    # ── GENIUS ────────────────────────────────────────────────────────────────
    print("Genius: collecting annotation signals...")
    genius_records = collect_genius()
    append_jsonl(RAW / "genius.jsonl", genius_records)
    stats["genius"] = len(genius_records)
    print()

    # ── APPLE MUSIC ───────────────────────────────────────────────────────────
    print("Apple Music: collecting charts...")
    apple_records = collect_apple_music()
    append_jsonl(RAW / "apple_music.jsonl", apple_records)
    stats["apple_music"] = len(apple_records)
    print()

    # ── PREDICTION MARKETS ────────────────────────────────────────────────────
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

        messages = [
            ("header",       msg_header(today, stats)),
            ("velocity",     msg_velocity(today)),
            ("releases",     msg_new_releases(today)),
            ("divergence",   msg_divergence(divergence_scores, today)),
            ("markets",      msg_markets(today)),
            ("charts",       msg_shazam_billboard(today)),
        ]

        sent = 0
        for label, msg in messages:
            if msg:
                success = send_telegram(tg_token, tg_chat, msg)
                if success:
                    sent += 1
                time.sleep(1.5)  # avoid Telegram flood limits

        # Research prompt — always last
        prompt = generate_research_prompt(divergence_scores, survival_records, echo_trend)
        research_msg = (
            f"🔬 *Today's research question*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{prompt}\n\n"
            f"_Reply to log your hypothesis in the research journal._"
        )
        send_telegram(tg_token, tg_chat, research_msg)
        log_research_entry(prompt)

        print(f"  Telegram: {sent + 1} messages sent ✓")
    else:
        print("Telegram: no credentials, skipping")

    print(f"\n[{today}] Collection complete.")
    print(f"Total records: {sum(v for v in stats.values())}")


if __name__ == "__main__":
    main()
