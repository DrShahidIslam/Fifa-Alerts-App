"""
Google Trends Monitor — Tracks rising search queries related to FIFA World Cup 2026.
Uses pytrends to check interest levels and detect spikes in search volume.
"""
import logging
import time
from datetime import datetime

from pytrends.request import TrendReq

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def _build_keyword_batches(keywords, batch_size=5):
    """Split keywords into batches of 5 (pytrends limit per request)."""
    for i in range(0, len(keywords), batch_size):
        yield keywords[i:i + batch_size]


def fetch_trending_queries():
    """
    Check Google Trends for rising interest in World Cup related keywords.
    Returns a list of trend dicts with keyword, interest score, and rising status.
    """
    trends = []

    try:
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 30))
    except Exception as e:
        logger.error(f"Failed to initialize pytrends: {e}")
        return trends

    # Check core World Cup keywords for interest over time
    core_keywords = config.PRIMARY_KEYWORDS[:10]  # Top 10 primary keywords

    for batch in _build_keyword_batches(core_keywords):
        try:
            logger.info(f"Checking Google Trends for: {batch}")
            pytrends.build_payload(batch, cat=0, timeframe='now 7-d', geo=config.TRENDS_GEO)

            # Get interest over time
            interest_df = pytrends.interest_over_time()
            if interest_df is not None and not interest_df.empty:
                for keyword in batch:
                    if keyword in interest_df.columns:
                        values = interest_df[keyword].tolist()
                        if len(values) >= 2:
                            current = values[-1]
                            avg_recent = sum(values[-6:]) / len(values[-6:]) if len(values) >= 6 else values[-1]
                            avg_overall = sum(values) / len(values)

                            is_rising = current > avg_overall * 1.5  # 50% above average = rising

                            trends.append({
                                "keyword": keyword,
                                "current_interest": int(current),
                                "avg_interest": round(avg_overall, 1),
                                "is_rising": is_rising,
                                "spike_ratio": round(current / max(avg_overall, 1), 2),
                                "source": "google_trends",
                                "source_type": "trends",
                                "recorded_at": datetime.utcnow(),
                            })

                            if is_rising:
                                logger.info(f"  🔥 RISING: '{keyword}' — {current} vs avg {avg_overall:.0f} ({current/max(avg_overall,1):.1f}x)")

            # Rate limit — be polite to Google
            time.sleep(5)

        except Exception as e:
            logger.warning(f"Google Trends error for batch {batch}: {e}")
            time.sleep(10)
            continue

    # Also check related rising queries for top keywords
    try:
        pytrends.build_payload(["world cup 2026"], cat=0, timeframe='now 7-d', geo=config.TRENDS_GEO)
        related = pytrends.related_queries()

        if related and "world cup 2026" in related:
            rising_df = related["world cup 2026"].get("rising")
            if rising_df is not None and not rising_df.empty:
                for _, row in rising_df.head(10).iterrows():
                    query = row.get("query", "")
                    value = row.get("value", 0)
                    trends.append({
                        "keyword": query,
                        "current_interest": int(value) if isinstance(value, (int, float)) else 0,
                        "avg_interest": 0,
                        "is_rising": True,
                        "spike_ratio": 0,
                        "source": "google_trends_related",
                        "source_type": "trends",
                        "recorded_at": datetime.utcnow(),
                    })
                    logger.info(f"  📈 Related rising query: '{query}' (value: {value})")

    except Exception as e:
        logger.warning(f"Related queries error: {e}")

    logger.info(f"Trends Monitor: Found {len(trends)} trend data points, {sum(1 for t in trends if t['is_rising'])} rising")
    return trends


def get_realtime_trending():
    """
    Fetch real-time trending searches and filter for World Cup related topics.
    Returns a list of trending search dicts.
    """
    realtime_trends = []

    try:
        pytrends = TrendReq(hl='en-US', tz=0)
        trending = pytrends.trending_searches(pn='united_states')

        if trending is not None and not trending.empty:
            for _, row in trending.iterrows():
                query = str(row[0]).lower()
                # Check if this trending query is World Cup related
                for kw in config.ALL_KEYWORDS:
                    if kw.lower() in query or any(word in query for word in kw.lower().split()):
                        realtime_trends.append({
                            "keyword": str(row[0]),
                            "source": "google_trending",
                            "source_type": "realtime_trends",
                            "is_rising": True,
                            "matched_keyword": kw,
                            "recorded_at": datetime.utcnow(),
                        })
                        logger.info(f"  ⚡ Real-time trending: '{row[0]}' (matched: {kw})")
                        break

    except Exception as e:
        logger.warning(f"Real-time trending error: {e}")

    return realtime_trends


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("=== Interest Over Time ===")
    trends = fetch_trending_queries()
    for t in trends:
        status = "🔥 RISING" if t["is_rising"] else "  normal"
        print(f"  {status} | {t['keyword']}: {t['current_interest']} (avg: {t['avg_interest']}, ratio: {t['spike_ratio']}x)")

    print("\n=== Real-time Trending ===")
    rt = get_realtime_trending()
    for r in rt:
        print(f"  ⚡ {r['keyword']} (matched: {r.get('matched_keyword', 'N/A')})")
