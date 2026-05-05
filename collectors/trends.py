"""
Google Trends collector.
Currently disabled — Google aggressively rate-limits pytrends (429 errors).
Kept as a stub so the pipeline doesn't break when it's re-enabled later.
Placeholder returns empty records gracefully.
"""

from datetime import date


def collect_trends():
    print("  Google Trends: skipped (rate limited by Google — revisit later)")
    return []
