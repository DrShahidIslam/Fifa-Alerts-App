"""
Google Trends Monitor - Tracks rising search queries related to FIFA World Cup 2026.
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
    """Split keywords into batches of 5 (pytrends limit)."""
    for i in range(0, len(keywords), batch_size):
        yield keywords[i:i + batch_size]


def _dedupe_keep_order(values):
    seen = set()
    result = []
    for value in values:
        normalized = (value or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value.strip())
    return result


def _build_trend_watchlist():
    """Watch more than just core phrases so radar catches active football topics earlier."""
    watchlist = []
    watchlist.extend(getattr(config, "PRIMARY_KEYWORDS", []))
    watchlist.extend(getattr(config, "LOGISTICS_KEYWORDS", [])[:8])
    watchlist.extend(getattr(config, "TEAM_KEYWORDS", [])[:10])
    watchlist.extend(getattr(config, "PLAYER_KEYWORDS", [])[:10])
    watchlist.extend(getattr(config, "VENUE_KEYWORDS", [])[:6])
    return _dedupe_keep_order(watchlist)[:getattr(config, "TREND_WATCHLIST_LIMIT", 25)]


def _related_query_seeds():
    return _dedupe_keep_order([
        "world cup 2026",
        "world cup qualifier",
        "world cup 2026 tickets",
        "world cup 2026 venues",
        "world cup 2026 draw",
    ])


def _best_keyword_match(query):
    query_lc = (query or "").lower()
    best = None
    best_score = 0
    for kw in getattr(config, "ALL_KEYWORDS", []):
        kw_lc = kw.lower()
        if kw_lc in query_lc:
            score = len(kw_lc)
        else:
            kw_tokens = [t for t in kw_lc.split() if len(t) > 2]
            score = sum(1 for token in kw_tokens if token in query_lc)
        if score > best_score:
            best_score = score
            best = kw
    return best if best_score > 0 else None


def fetch_trending_queries():
    """
    Check Google Trends for rising interest in World Cup related keywords.
    Returns a list of trend dicts with keyword, interest score, and rising status.
    """
    trends = []

    try:
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
    except Exception as e:
        logger.error(f"Failed to initialize pytrends: {e}")
        return trends

    watchlist = _build_trend_watchlist()
    for batch in _build_keyword_batches(watchlist):
        try:
            logger.info(f"Checking Google Trends for: {batch}")
            pytrends.build_payload(batch, cat=0, timeframe="now 7-d", geo=config.TRENDS_GEO)
            interest_df = pytrends.interest_over_time()
            if interest_df is not None and not interest_df.empty:
                for keyword in batch:
                    if keyword not in interest_df.columns:
                        continue
                    values = interest_df[keyword].tolist()
                    if len(values) < 2:
                        continue
                    current = values[-1]
                    avg_overall = sum(values) / len(values)
                    is_rising = current > avg_overall * 1.5
                    trends.append({
                        "keyword": keyword,
                        "current_interest": int(current),
                        "avg_interest": round(avg_overall, 1),
                        "is_rising": is_rising,
                        "spike_ratio": round(current / max(avg_overall, 1), 2),
                        "source": "google_trends",
                        "source_type": "trends",
                        "matched_keyword": keyword,
                        "recorded_at": datetime.utcnow(),
                    })
                    if is_rising:
                        logger.info(
                            f"  Rising: '{keyword}' - {current} vs avg {avg_overall:.0f} ({current / max(avg_overall, 1):.1f}x)"
                        )
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Google Trends error for batch {batch}: {e}")
            time.sleep(10)
            continue

    for seed in _related_query_seeds():
        try:
            pytrends.build_payload([seed], cat=0, timeframe="now 7-d", geo=config.TRENDS_GEO)
            related = pytrends.related_queries()
            if not related or seed not in related:
                continue
            rising_df = related[seed].get("rising")
            if rising_df is None or rising_df.empty:
                continue
            for _, row in rising_df.head(10).iterrows():
                query = row.get("query", "")
                query_lower = query.lower()
                if any(ex_kw.lower() in query_lower for ex_kw in getattr(config, "EXCLUDE_KEYWORDS", [])):
                    continue
                value = row.get("value", 0)
                trends.append({
                    "keyword": query,
                    "current_interest": int(value) if isinstance(value, (int, float)) else 0,
                    "avg_interest": 0,
                    "is_rising": True,
                    "spike_ratio": 0,
                    "source": "google_trends_related",
                    "source_type": "trends",
                    "matched_keyword": _best_keyword_match(query) or query,
                    "recorded_at": datetime.utcnow(),
                })
                logger.info(f"  Related rising query: '{query}' (seed: {seed}, value: {value})")
        except Exception as e:
            logger.warning(f"Related queries error for seed '{seed}': {e}")

    logger.info(f"Trends Monitor: Found {len(trends)} trend data points, {sum(1 for t in trends if t['is_rising'])} rising")
    return trends


def get_realtime_trending():
    """
    Fetch real-time trending searches and filter for World Cup related topics.
    Returns a list of trending search dicts.
    """
    realtime_trends = []

    try:
        pytrends = TrendReq(hl="en-US", tz=0)
        trending = pytrends.trending_searches(pn="united_states")
        if trending is not None and not trending.empty:
            for _, row in trending.iterrows():
                keyword = str(row[0])
                matched = _best_keyword_match(keyword)
                if not matched:
                    continue
                realtime_trends.append({
                    "keyword": keyword,
                    "source": "google_trending",
                    "source_type": "realtime_trends",
                    "is_rising": True,
                    "matched_keyword": matched,
                    "recorded_at": datetime.utcnow(),
                })
                logger.info(f"  Real-time trending: '{keyword}' (matched: {matched})")
    except Exception as e:
        logger.warning(f"Real-time trending error: {e}")

    return realtime_trends


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("=== Interest Over Time ===")
    trends = fetch_trending_queries()
    for t in trends:
        status = "RISING" if t["is_rising"] else "normal"
        print(f"  {status} | {t['keyword']}: {t['current_interest']} (avg: {t['avg_interest']}, ratio: {t['spike_ratio']}x)")

    print("\n=== Real-time Trending ===")
    rt = get_realtime_trending()
    for r in rt:
        print(f"  {r['keyword']} (matched: {r.get('matched_keyword', 'N/A')})")
