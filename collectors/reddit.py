"""
Reddit collector — community activation signal.
Uses Reddit's public JSON API (no auth needed for read-only).
Tracks post frequency and engagement on r/hiphopheads and r/popheads
for tracked artists. Fan community activation that's independent of
platform algorithms.

No API key needed — uses Reddit's public .json endpoints.
"""

import time, requests
from datetime import date, timedelta

HEADERS = {"User-Agent": "DSP-Longevity-Research/1.0 (research project)"}

SUBREDDITS = ["hiphopheads", "popheads", "indieheads"]

TRACKED_ARTISTS = [
    "Drake", "Kendrick Lamar", "Taylor Swift", "Bad Bunny",
    "The Weeknd", "Sabrina Carpenter", "Olivia Rodrigo", "SZA",
    "Morgan Wallen", "Zach Bryan", "Post Malone", "Travis Scott",
    "Billie Eilish", "Doja Cat", "Noah Kahan", "Tyla",
    # Iceman-specific
    "Iceman",
]


def search_subreddit(subreddit, query, limit=25):
    """Search a subreddit for posts mentioning an artist."""
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "restrict_sr": "true",
        "sort": "new",
        "limit": limit,
        "t": "week",  # last 7 days
    }
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("data", {}).get("children", [])
    except Exception as e:
        print(f"    Reddit search error ({subreddit}/{query}): {e}")
        return []


def collect_reddit():
    today = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    records = []

    for artist in TRACKED_ARTISTS:
        artist_data = {
            "snapshot_date": today,
            "artist_name": artist,
            "subreddits": {},
        }

        total_posts = 0
        total_score = 0
        total_comments = 0

        for sub in SUBREDDITS:
            posts = search_subreddit(sub, artist)
            sub_posts = []

            for post in posts:
                p = post.get("data", {})
                created = date.fromtimestamp(p.get("created_utc", 0)).isoformat()
                if created < cutoff:
                    continue
                sub_posts.append({
                    "title": p.get("title", "")[:100],
                    "score": p.get("score", 0),
                    "num_comments": p.get("num_comments", 0),
                    "created": created,
                    "url": p.get("permalink", ""),
                })

            post_count = len(sub_posts)
            avg_score = sum(p["score"] for p in sub_posts) / post_count if post_count else 0
            total_comments_sub = sum(p["num_comments"] for p in sub_posts)

            artist_data["subreddits"][sub] = {
                "post_count_7d": post_count,
                "avg_score": round(avg_score, 1),
                "total_comments": total_comments_sub,
                "top_post": max(sub_posts, key=lambda x: x["score"]) if sub_posts else None,
            }

            total_posts += post_count
            total_score += sum(p["score"] for p in sub_posts)
            total_comments += total_comments_sub
            time.sleep(1.0)  # Reddit rate limit — be respectful

        artist_data["total_posts_7d"] = total_posts
        artist_data["total_score_7d"] = total_score
        artist_data["total_comments_7d"] = total_comments
        records.append(artist_data)

    print(f"  Reddit: {len(records)} artist records collected")
    return records
