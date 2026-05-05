# TikTok Research API Application
## DSP Music Economy & Artist Longevity Project

---

### Project Title
The DSP Effect: Measuring How Streaming Platform Algorithms Shape Artist Longevity and Cultural Discovery

---

### Research Question
Do digital streaming platforms (DSPs) like Spotify create durable artist careers, or do they manufacture temporary popularity through editorial playlist placement and algorithmic promotion? And what role does TikTok play as an upstream discovery mechanism — does a song's virality on TikTok predict long-term streaming longevity, or does it accelerate a faster decay curve?

---

### Background & Motivation

The music industry has undergone a fundamental restructuring over the past decade. Radio — historically the primary mechanism for music discovery — has been replaced by streaming platforms and social media. Spotify's editorial playlists (RapCaviar, Today's Top Hits, New Music Friday) now function as the new radio: placement on these playlists can generate millions of streams and launch careers overnight.

However, the relationship between this platform-driven exposure and genuine, durable artist longevity is poorly understood. A 2025 peer-reviewed study in Marketing Science (Pachali & Datta, "What Drives Demand for Playlists on Spotify?") confirmed that platform-generated playlists now exert greater influence over listener behavior than major label content. Separately, a Y2M industry report found that emerging artists receive nearly 60% of their streams from algorithmic programming — yet for established artists, the ratio inverts, with 64% coming from active, user-driven listening.

This creates an empirical question: is the platform manufacturing popularity, or identifying it? And where does TikTok fit in this ecosystem — as a leading indicator of genuine cultural resonance, or as a separate virality mechanism with its own decay dynamics?

---

### Methodology

This project tracks a curated set of artists and tracks across six independent data signals on a daily basis:

1. **Spotify playlist presence & popularity score** — platform editorial endorsement and streaming behavior
2. **Billboard Hot 100 position** — cross-platform commercial performance
3. **Google Trends search interest** — active cultural search behavior (US, daily)
4. **Wikipedia pageviews** — information-seeking behavior, a proxy for cultural weight
5. **YouTube view velocity & engagement** — video platform performance
6. **Shazam chart position & listening count** — ambient, passive discovery signal

From these signals, we compute two novel metrics:

**Divergence Score**: The normalized gap between Spotify popularity and the average of all cross-platform cultural signals. A high positive divergence (Spotify >> culture signals) suggests platform-manufactured popularity without corresponding cultural engagement. A high negative divergence (culture >> Spotify) may indicate rising cultural relevance not yet captured by platform algorithms.

**Playlist Survival Rate**: For each tracked track on each editorial playlist, the percentage of collection days it has appeared since first observed. This operationalizes "longevity" as a measurable quantity rather than a subjective judgment.

**TikTok's role in this framework**: TikTok sound usage data would serve as a leading-indicator signal — the upstream discovery mechanism that precedes streaming. Specifically, we want to test:

- Does high TikTok sound usage (measured by video count using a given sound) predict subsequent Spotify playlist placement?
- Do tracks that enter Spotify via TikTok virality show faster Playlist Survival Rate decay than tracks that enter via editorial placement?
- Is TikTok-driven discovery correlated with divergence score over time — i.e., do TikTok-viral tracks show higher short-term Spotify popularity relative to Wikipedia/Google Trends, suggesting platform amplification of social virality without corresponding cultural depth?

**Data requested from TikTok Research API**:
- Video search by `music_id` for tracked songs: video count, view count, like count, share count, region code (US-focused)
- Time range: daily snapshots going forward from approval date
- Volume: approximately 10-15 tracked songs × daily queries = ~150 records/day, well within the 5,000 record/day test stage limit

---

### Why This Research Matters

This project operates from a critical but empirically grounded perspective: the consolidation of music discovery into a small number of platform algorithms represents a significant shift in cultural power, with implications for artist economics, musical diversity, and listener autonomy.

Research from Bain & Company ("Music Discovery: More Channels, More Problems," 2025) found that music discovery is now fragmented across nearly 20 different channels, yet streaming playlists remain a leading driver — and the data from our pipeline will help quantify how these channels interact.

The findings will be published as an open-source dashboard with transparent methodology, specifically designed as an open alternative to proprietary tools like Chartmetric ($350+/month) that put this research behind a paywall. All code, data, and methodology will be publicly available on GitHub.

---

### Data Handling & Privacy

- Only public video metadata will be collected — no user-level data, no private information
- Data will be aggregated at the track/sound level (total video counts, average engagement) — individual video or user records will not be stored or published
- All collected data will be used exclusively for the research question described above
- Data will be stored on GitHub (public repository) in aggregated, anonymized form
- Full compliance with TikTok's Research API Terms of Service

---

### Researcher Information

**Principal Researcher**: Preet [Last Name]
**Affiliation**: Independent researcher / VP Business Analytics, PNC Bank
**Research Focus**: Music industry platform economics, streaming analytics, cultural signal analysis
**Project Repository**: github.com/[username]/dsp-longevity (public)
**Contact**: [email]

**Research Background**: 6+ years of professional analytics experience including time at the Federal Reserve Board of Governors and CFPB. This project applies enterprise-grade data pipeline methodology (real-time signal tracking, time-series analysis, divergence scoring) to music industry research questions. The project has active data collection running across five signals, with a live public dashboard.

---

### Timeline

- Data collection began: [start date]
- TikTok signal integration target: Upon API approval
- Initial findings publication: 90 days post-approval
- Ongoing: Daily automated collection via GitHub Actions with weekly research journal updates

---

### Supporting Materials

- Live project dashboard: [github pages URL]
- Project README with full methodology: github.com/[username]/dsp-longevity
- Related academic work cited:
  - Pachali & Datta (2025), "What Drives Demand for Playlists on Spotify?" — Marketing Science
  - Bain & Company (2025), "Music Discovery: More Channels, More Problems"
  - Y2M (2024), "How Spotify Algorithms Affect Music Listening" — Music Ally

---

*Application submitted via TikTok for Developers Research Tools portal*
*developers.tiktok.com/application/research-api*
