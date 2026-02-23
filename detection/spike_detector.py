"""
Spike Detector — Aggregates stories from all sources, deduplicates,
calculates spike scores, and returns trending topics worth covering.
"""
import logging
import hashlib
from collections import defaultdict
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from database.db import (
    get_connection, is_story_seen, add_story, record_keyword_mention,
    get_keyword_baseline
)

logger = logging.getLogger(__name__)


def _cluster_stories(stories):
    """
    Group related stories by topic. Stories about the same event
    (e.g., "Italy qualifies" from ESPN + BBC) get clustered together.
    """
    clusters = defaultdict(list)

    for story in stories:
        # Create a simplified topic key from title words
        title_words = set(story["title"].lower().split())
        # Remove common words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                      "to", "for", "of", "with", "and", "or", "but", "not", "this",
                      "that", "it", "as", "by", "from", "has", "have", "had", "will",
                      "be", "been", "can", "could", "would", "should", "do", "does"}
        key_words = title_words - stop_words

        # Find best matching existing cluster
        best_match = None
        best_score = 0

        for cluster_key in clusters:
            cluster_words = set(cluster_key.split("|"))
            overlap = len(key_words & cluster_words)
            score = overlap / max(len(key_words | cluster_words), 1)
            if score > best_score and score > 0.3:  # 30% word overlap threshold
                best_match = cluster_key
                best_score = score

        if best_match:
            clusters[best_match].append(story)
        else:
            cluster_key = "|".join(sorted(key_words)[:8])  # Use first 8 key words
            clusters[cluster_key].append(story)

    return clusters


def _calculate_spike_score(cluster_stories, conn):
    """
    Calculate a spike score for a cluster of stories.
    Higher score = more newsworthy / trending.
    """
    score = 0.0
    factors = []

    # Factor 1: Number of sources covering this story
    unique_sources = set(s["source"] for s in cluster_stories)
    source_count = len(unique_sources)
    score += source_count * 15  # Each source = 15 points
    factors.append(f"{source_count} sources")

    # Factor 2: Multiple source types (RSS + NewsAPI + Trends = stronger signal)
    source_types = set(s.get("source_type", "unknown") for s in cluster_stories)
    if len(source_types) > 1:
        score += len(source_types) * 10
        factors.append(f"{len(source_types)} source types")

    # Factor 3: Recency — stories from last 2 hours score higher
    now = datetime.utcnow()
    for story in cluster_stories:
        pub = story.get("published_at", now)
        if isinstance(pub, datetime):
            hours_old = (now - pub).total_seconds() / 3600
            if hours_old < 2:
                score += 20
                factors.append("< 2h old")
            elif hours_old < 6:
                score += 10

    # Factor 4: Google Trends rising indicator
    for story in cluster_stories:
        if story.get("is_rising"):
            score += 25
            factors.append("trending on Google")
            break

    # Factor 5: High-value keywords (tickets, messi, final, etc.)
    high_value_keywords = [
        "messi", "ronaldo", "ticket", "final", "draw", "qualify",
        "disqualified", "ban", "injury", "transfer", "jersey",
        "opening match", "opening ceremony",
    ]
    for story in cluster_stories:
        title_lower = story["title"].lower()
        for hvk in high_value_keywords:
            if hvk in title_lower:
                score += 15
                factors.append(f"high-value: {hvk}")
                break

    # Factor 6: Keyword baseline spike check
    for story in cluster_stories:
        kw = story.get("matched_keyword", "")
        if kw:
            baseline_avg, samples = get_keyword_baseline(conn, kw)
            if samples > 0 and baseline_avg > 0:
                current_mentions = len(cluster_stories)
                ratio = current_mentions / baseline_avg
                if ratio >= config.SPIKE_THRESHOLD:
                    score += ratio * 10
                    factors.append(f"keyword spike {ratio:.1f}x")

    return round(score, 1), factors


def _is_excluded(text):
    """Check if text contains any exclusion keywords (cricket, rugby, etc.)."""
    text_lower = text.lower()
    for kw in getattr(config, "EXCLUDE_KEYWORDS", []):
        if kw.lower() in text_lower:
            return True
    return False


def detect_spikes(all_stories, trends_data=None):
    """
    Main detection function.
    Takes all stories from RSS + NewsAPI + Trends and returns
    ranked trending topics with spike scores.

    Returns a list of dicts:
    [
        {
            "topic": "Italy qualifies for World Cup 2026",
            "score": 85.0,
            "factors": ["3 sources", "trending on Google", "< 2h old"],
            "stories": [...],
            "sources": ["ESPN", "BBC", "NewsAPI"],
            "top_url": "https://...",
            "matched_keyword": "italy",
        },
        ...
    ]
    """
    conn = get_connection()

    # Merge trends data into stories format if provided
    combined = list(all_stories)
    if trends_data:
        for trend in trends_data:
            if trend.get("is_rising"):
                combined.append({
                    "title": f"Rising search: {trend['keyword']}",
                    "summary": f"Google Trends shows '{trend['keyword']}' is rising ({trend.get('spike_ratio', 0)}x above average)",
                    "url": f"https://trends.google.com/trends/explore?q={trend['keyword'].replace(' ', '+')}",
                    "source": trend.get("source", "Google Trends"),
                    "source_type": "trends",
                    "matched_keyword": trend["keyword"],
                    "published_at": trend.get("recorded_at", datetime.utcnow()),
                    "story_hash": hashlib.sha256(trend["keyword"].encode()).hexdigest()[:16],
                    "is_rising": True,
                })

    # ── Relevance filter: remove stories with excluded keywords ───
    filtered = []
    excluded_count = 0
    for story in combined:
        title = story.get("title", "")
        keyword = story.get("matched_keyword", "")
        if _is_excluded(title) or _is_excluded(keyword):
            excluded_count += 1
            continue
        filtered.append(story)

    if excluded_count > 0:
        logger.info(f"Spike Detector: Excluded {excluded_count} irrelevant stories (cricket/rugby/etc.)")
    combined = filtered

    # Filter out already-seen stories
    new_stories = []
    for story in combined:
        if not is_story_seen(conn, story["story_hash"], config.DEDUP_WINDOW_HOURS):
            new_stories.append(story)
            add_story(conn, story["story_hash"], story["title"],
                      story["source"], story.get("url", ""),
                      story.get("matched_keyword", ""))

    if not new_stories:
        logger.info("Spike Detector: No new stories found")
        conn.close()
        return []

    logger.info(f"Spike Detector: Processing {len(new_stories)} new stories")

    # Record keyword mentions for baseline tracking
    keyword_counts = defaultdict(int)
    for story in new_stories:
        kw = story.get("matched_keyword", "")
        if kw:
            keyword_counts[kw] += 1
    for kw, count in keyword_counts.items():
        record_keyword_mention(conn, kw, "combined", count)

    # Cluster related stories
    clusters = _cluster_stories(new_stories)

    # Score each cluster
    trending_topics = []
    min_score = getattr(config, "SPIKE_MIN_SCORE", 40)
    for cluster_key, cluster_stories in clusters.items():
        score, factors = _calculate_spike_score(cluster_stories, conn)

        # Only report clusters with meaningful score
        if score >= min_score:
            # Pick the best title (longest, most descriptive)
            best_story = max(cluster_stories, key=lambda s: len(s["title"]))

            trending_topics.append({
                "topic": best_story["title"],
                "score": score,
                "factors": factors,
                "stories": cluster_stories,
                "sources": list(set(s["source"] for s in cluster_stories)),
                "top_url": best_story.get("url", ""),
                "matched_keyword": best_story.get("matched_keyword", ""),
                "story_count": len(cluster_stories),
            })

    # Sort by score (highest first)
    trending_topics.sort(key=lambda x: x["score"], reverse=True)

    conn.close()
    logger.info(f"Spike Detector: Identified {len(trending_topics)} trending topics")
    return trending_topics


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # Test with some fake stories
    test_stories = [
        {
            "title": "Italy defeats Northern Ireland 2-0 in World Cup qualifier",
            "summary": "Italy has taken a major step toward World Cup 2026 qualification",
            "url": "https://espn.com/test1",
            "source": "ESPN",
            "source_type": "rss",
            "matched_keyword": "italy",
            "published_at": datetime.utcnow(),
            "story_hash": "test_hash_1",
        },
        {
            "title": "Italy World Cup qualification: Northern Ireland beaten in playoff",
            "summary": "Italy are through to the World Cup 2026 playoff final",
            "url": "https://bbc.com/test2",
            "source": "BBC Sport",
            "source_type": "rss",
            "matched_keyword": "italy",
            "published_at": datetime.utcnow(),
            "story_hash": "test_hash_2",
        },
    ]

    topics = detect_spikes(test_stories)
    for t in topics:
        print(f"\n🔥 [{t['score']}] {t['topic']}")
        print(f"   Sources: {', '.join(t['sources'])}")
        print(f"   Factors: {', '.join(t['factors'])}")
