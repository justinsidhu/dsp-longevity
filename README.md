# DSP Music Economy & Artist Longevity
### An open research tool for studying platform power, algorithmic convergence, and what actually builds durable streaming value.

---

## The core question

Streaming platforms have replaced radio as the primary music discovery mechanism — but the mechanisms of that replacement are largely opaque. Do editorial playlists like RapCaviar build genuine artist longevity, or manufacture temporary popularity? Does algorithmic personalization broaden or narrow the discovery surface over time? And can cross-signal divergence between platform behavior and cultural interest tell us something real about which artists are building durable careers vs. being propped up by editorial placement?

This project runs those questions through empirical data, updated daily.

---

## Novel metrics (not available in Chartmetric or similar tools)

### 1. Divergence Score
The normalized gap between Spotify popularity and the average of cross-platform cultural signals (Google Trends, Wikipedia pageviews, Billboard chart position).

- **Positive divergence** (Spotify > culture signals): Platform streaming outpacing cultural interest. Possible explanations: passive playlist streams inflating popularity, international streaming masking domestic fade, catalog mode.
- **Negative divergence** (Culture > Spotify): Cultural buzz ahead of streaming. Possible explanations: rising artist, controversy moment, fanbase more active off-platform.
- **Aligned**: Platform and cultural behavior moving together — the strongest signal of genuine, durable relevance.

### 2. Playlist Survival Rate
For each track on each editorial playlist, the percentage of collection days it has appeared since first observed. A track that survives on RapCaviar for 30+ days is a fundamentally different phenomenon than one that rotates out in 5.

Tracks with high survival rates + positive divergence scores are the most interesting case study: the platform is betting on them, and it's paying off culturally.

### 3. Echo Chamber Index
Daily pairwise overlap between all tracked editorial playlists. If Today's Top Hits and RapCaviar share 60% of their tracks, listeners on both are hearing the same thing — the algorithmic discovery surface is narrowing. We track this over time as a measure of platform homogenization.

### 4. YouTube Engagement Depth
Most-replayed heatmap intensity pulled directly from YouTube's page data (no API key needed). A viral drop-off pattern (high early intensity, rapid decay) vs. a sustained engagement pattern tells you something about how people actually interact with a track beyond passive streaming.

---

## Data sources

| Signal | Source | Cost | Refresh |
|--------|--------|------|---------|
| Playlist presence / track popularity | Spotify Web API | Free | Daily |
| Chart position, weeks on chart, peak | Billboard Hot 100 (GitHub mirror) | Free | Weekly |
| Search interest by region | Google Trends (pytrends) | Free | Daily |
| Cultural weight / information-seeking | Wikipedia Pageviews API | Free | Daily |
| View counts, like counts | YouTube Data API v3 | Free (quota) | Daily |
| Most-replayed heatmap | YouTube page scrape | Free | Weekly |

**Note on Spotify API restrictions:** In November 2024, Spotify deprecated audio features endpoints (danceability, energy, valence) for new developer apps, coinciding with their rollout of AI playlist and AI DJ features. This project treats that restriction itself as a data point — the platform is actively limiting independent research into the signals that power its recommendation engine.

---

## Scientific method

This project participates in the scientific method explicitly. Each day's Telegram digest includes a research prompt based on anomalies in the data. Responses are logged in `data/journal/research_log.jsonl` — building a running interpretive record alongside the quantitative data.

**Starting hypotheses:**

1. Tracks that enter via TikTok virality will show faster playlist rotation (lower survival rate) than tracks that enter via editorial placement on non-viral playlists.
2. Artists with sustained positive divergence (Spotify >> culture) are more likely to drop in Billboard position within 30 days.
3. The Echo Chamber Index has been increasing over time — editorial playlists are converging, narrowing the active discovery surface.
4. YouTube most-replayed peak intensity at the track's hook (typically 45-90s) correlates with Spotify popularity growth in the following week.

---

## Setup

### 1. Spotify credentials
Create an app at [developer.spotify.com](https://developer.spotify.com). Copy Client ID and Secret.

### 2. YouTube API key (optional but recommended)
Google Cloud Console → Enable YouTube Data API v3 → Create API key. Free tier: 10,000 units/day. We use ~50 units/day.

### 3. Telegram bot
Message `@BotFather` → `/newbot` → copy token. Get your chat ID from `@userinfobot`.

### 4. GitHub Secrets
Settings → Secrets → Actions:
```
SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET
YOUTUBE_API_KEY
TELEGRAM_TOKEN
TELEGRAM_CHAT_ID
```

### 5. First run
```bash
pip install -r requirements.txt
export SPOTIFY_CLIENT_ID=...
export SPOTIFY_CLIENT_SECRET=...
python3 collect.py
git add data/
git commit -m "data: initial snapshot"
git push
```

### 6. GitHub Pages
Settings → Pages → Source: main → /dashboard

Dashboard live at: `https://YOUR_USERNAME.github.io/dsp-longevity/`

---

## Research journal

Daily research prompts and responses are logged in `data/journal/`. The running log is at `data/journal/research_log.jsonl`. This file is the interpretive layer of the project — the human reasoning alongside the data.

---

*Independent research project. Not affiliated with Spotify, Billboard, YouTube, or Chartmetric. Methodology is fully open and auditable.*
