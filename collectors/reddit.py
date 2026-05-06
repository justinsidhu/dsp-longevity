"""
Reddit collector — community activation signal.
Uses Reddit OAuth API (required since 2023 — public JSON endpoints blocked
on server IPs like GitHub Actions).

Setup (one-time, free):
1. Go to reddit.com/prefs/apps → Create App → script type
2. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in env/GitHub Secrets
3. Set REDDIT_USERNAME and REDDIT_PASSWORD in env/GitHub Secrets

No API key needed for read-only if you use a script-type app.
"""

import os, time, requests
from datetime import date, timedelta

SUBREDDITS = ["hiphopheads", "popheads", "indieheads", "drizzy"]

TRACKED_ARTISTS = [
    "Drake", "Kendrick Lamar", "Taylor Swift", "Bad Bunny",
    "The Weeknd", "Sabrina Carpenter", "Olivia Rodrigo", "SZA",
    "Morgan Wallen", "Zach Bryan", "Post Malone", "Travis Scott",
    "Billie Eilish", "Doja Cat", "Noah Kahan", "Tyla",
    "Iceman",
]


def get_reddit_token():
    """Get OAuth token using script-type app credentials."""
    client_id     = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    username      = os.environ.get("REDDIT_USERNAME")
    password      = os.environ.get("REDDIT_PASSWORD")

    if not all([client_id, client_secret, username, password]):
        return None

    try:
        r = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "password", "username": username, "password": password},
            headers={"User-Agent": "DSP-Longevity/1.0 by justinsidhu"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        print(f"    Reddit OAuth error: {e}")
        return None


def search_subreddit(subreddit, query, token, limit=25):
    """Search a subreddit using OAuth token."""
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "DSP-Longevity/1.0 by justinsidhu",
    }
    url = f"https://oauth.reddit.com/r/{subreddit}/search"
    params = {"q": query, "restrict_sr": "true", "sort": "new", "limit": limit, "t": "week"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("data", {}).get("children", [])
    except Exception as e:
        print(f"    Reddit search error ({subreddit}/{query}): {e}")
        return []


def collect_reddit():
    """
    Reddit API requires OAuth app registration which is restricted for new accounts.
    Community signal replaced by YouTube reaction tracker (iceman_reaction source)
    and manual r/drizzy monitoring during the rollout window.
    """
    print("  Reddit: API access restricted — using YouTube reaction tracker instead")
    return []

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
            posts = search_subreddit(sub, artist, token)
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
