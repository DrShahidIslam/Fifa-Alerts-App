"""
Spike Detector - Aggregates stories from all sources, deduplicates,
calculates spike scores, and returns trending topics worth covering.
"""
import hashlib
import logging
import re
from collections import defaultdict
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from database.db import (
    add_story,
    get_connection,
    get_keyword_baseline,
    is_story_seen,
    record_keyword_mention,
)

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "with",
    "and", "or", "but", "not", "this", "that", "it", "as", "by", "from", "has", "have", "had",
    "will", "be", "been", "can", "could", "would", "should", "do", "does", "did", "after", "before",
}

FOOTBALL_HINTS = [
    "football", "soccer", "fifa", "world cup", "qualifier", "qualifying", "uefa", "conmebol", "afc",
    "concacaf", "caf", "ofc", "goal", "manager", "transfer", "striker", "midfielder", "defender",
    "keeper", "hat trick", "red card", "offside", "penalty", "league", "club world cup",
]

SOURCE_WEIGHTS = {
    "fifa": 18,
    "reuters": 16,
    "bbc": 14,
    "espn": 13,
    "the guardian": 12,
    "fox": 10,
    "sky": 10,
    "newsapi": 8,
    "google trends": 6,
}

HIGH_VALUE_TERMS = [
    "messi", "ronaldo", "mbappe", "haaland", "ticket", "draw", "final", "injury", "transfer", "ban",
    "qualification", "qualified", "opening match", "opening ceremony", "standings", "fixtures", "bracket",
]


def _tokenize(text):
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in STOP_WORDS}


def _build_entity_terms():
    terms = set()
    for bucket in (
        getattr(config, "PRIMARY_KEYWORDS", []),
        getattr(config, "TEAM_KEYWORDS", []),
        getattr(config, "PLAYER_KEYWORDS", []),
        getattr(config, "VENUE_KEYWORDS", []),
        getattr(config, "LOGISTICS_KEYWORDS", []),
        getattr(config, "GENERAL_FOOTBALL_KEYWORDS", []),
    ):
        for term in bucket:
            if term and len(term) >= 4:
                terms.add(term.lower())
    return sorted(terms, key=len, reverse=True)


ENTITY_TERMS = _build_entity_terms()


def _extract_entities(text):
    t = (text or "").lower()
    entities = set()
    for term in ENTITY_TERMS:
        if term in t:
            entities.add(term)
    return entities


def _story_vectors(story):
    combined = f"{story.get('title', '')} {story.get('summary', '')}"
    return _tokenize(combined), _extract_entities(combined)


def _similarity(a_tokens, a_entities, b_tokens, b_entities, a_kw="", b_kw=""):
    token_overlap = len(a_tokens & b_tokens) / max(len(a_tokens | b_tokens), 1)
    entity_overlap = len(a_entities & b_entities) / max(len(a_entities | b_entities), 1)
    keyword_bonus = 0.08 if a_kw and b_kw and a_kw.lower() == b_kw.lower() else 0.0
    return (token_overlap * 0.6) + (entity_overlap * 0.4) + keyword_bonus


def _cluster_stories(stories):
    """Cluster stories using token + entity similarity."""
    clusters = []

    for story in stories:
        tokens, entities = _story_vectors(story)
        story["_tokens"] = tokens
        story["_entities"] = entities

        best_idx = -1
        best_score = 0.0
        for i, cluster in enumerate(clusters):
            score = _similarity(
                tokens,
                entities,
                cluster["tokens"],
                cluster["entities"],
                story.get("matched_keyword", ""),
                cluster.get("matched_keyword", ""),
            )
            if score > best_score and score >= 0.28:
                best_idx = i
                best_score = score

        if best_idx >= 0:
            clusters[best_idx]["stories"].append(story)
            clusters[best_idx]["tokens"].update(tokens)
            clusters[best_idx]["entities"].update(entities)
        else:
            clusters.append(
                {
                    "stories": [story],
                    "tokens": set(tokens),
                    "entities": set(entities),
                    "matched_keyword": story.get("matched_keyword", ""),
                }
            )

    return [c["stories"] for c in clusters]


def _source_authority_bonus(unique_sources):
    bonus = 0
    for src in unique_sources:
        s = src.lower()
        for name, weight in SOURCE_WEIGHTS.items():
            if name in s:
                bonus += weight
                break
    return bonus


def _contains_world_cup_signal(text):
    t = (text or "").lower()
    return any(x in t for x in ("world cup", "fifa", "2026", "qualifier", "qualifying"))


def _is_football_relevant(story):
    """Allow broad football coverage while filtering unrelated sports noise."""
    combined = f"{story.get('title', '')} {story.get('summary', '')} {story.get('matched_keyword', '')}".lower()
    if any(k in combined for k in getattr(config, "EXCLUDE_KEYWORDS", [])):
        return False
    if _contains_world_cup_signal(combined):
        return True
    if getattr(config, "GENERAL_FOOTBALL_MODE", False):
        return any(h in combined for h in FOOTBALL_HINTS)
    return False


def _calculate_spike_score(cluster_stories, conn):
    """Calculate a spike score for a cluster of stories."""
    score = 0.0
    factors = []

    unique_sources = set(s.get("source", "unknown") for s in cluster_stories)
    source_count = len(unique_sources)
    score += source_count * 10
    factors.append(f"{source_count} sources")

    authority = _source_authority_bonus(unique_sources)
    if authority:
        score += authority
        factors.append("high-authority coverage")

    source_types = set(s.get("source_type", "unknown") for s in cluster_stories)
    if len(source_types) > 1:
        score += len(source_types) * 9
        factors.append(f"{len(source_types)} source types")

    now = datetime.utcnow()
    fresh = 0
    for story in cluster_stories:
        pub = story.get("published_at", now)
        if isinstance(pub, datetime):
            hours_old = (now - pub).total_seconds() / 3600
            if hours_old < 2:
                score += 16
                fresh += 1
            elif hours_old < 6:
                score += 8
    if fresh:
        factors.append("very recent coverage")

    if any(s.get("is_rising") for s in cluster_stories):
        score += 22
        factors.append("trending on Google")

    title_blob = " ".join((s.get("title") or "").lower() for s in cluster_stories)
    for term in HIGH_VALUE_TERMS:
        if term in title_blob:
            score += 12
            factors.append(f"high-value term: {term}")
            break

    all_entities = set()
    for s in cluster_stories:
        all_entities.update(s.get("_entities", set()))
    if len(all_entities) >= 2:
        score += min(20, len(all_entities) * 3)
        factors.append("strong entity overlap")

    if _contains_world_cup_signal(title_blob):
        score += 12
        factors.append("World Cup relevance")
    elif getattr(config, "GENERAL_FOOTBALL_MODE", False):
        score += 5
        factors.append("general football relevance")

    for story in cluster_stories:
        kw = story.get("matched_keyword", "")
        if kw:
            baseline_avg, samples = get_keyword_baseline(conn, kw)
            if samples > 0 and baseline_avg > 0:
                ratio = len(cluster_stories) / baseline_avg
                if ratio >= config.SPIKE_THRESHOLD:
                    score += ratio * 8
                    factors.append(f"keyword spike {ratio:.1f}x")
                    break

    return round(score, 1), factors


def detect_spikes(all_stories, trends_data=None):
    """
    Main detection function.
    Takes all stories from RSS + NewsAPI + Trends and returns ranked topics.
    """
    conn = get_connection()

    combined = list(all_stories)
    if trends_data:
        for trend in trends_data:
            if trend.get("is_rising"):
                combined.append(
                    {
                        "title": f"Rising search: {trend['keyword']}",
                        "summary": f"Google Trends shows '{trend['keyword']}' is rising ({trend.get('spike_ratio', 0)}x above average)",
                        "url": f"https://trends.google.com/trends/explore?q={trend['keyword'].replace(' ', '+')}",
                        "source": trend.get("source", "Google Trends"),
                        "source_type": "trends",
                        "matched_keyword": trend["keyword"],
                        "published_at": trend.get("recorded_at", datetime.utcnow()),
                        "story_hash": hashlib.sha256(trend["keyword"].encode()).hexdigest()[:16],
                        "is_rising": True,
                    }
                )

    filtered = [s for s in combined if _is_football_relevant(s)]
    excluded = len(combined) - len(filtered)
    if excluded:
        logger.info(f"Spike Detector: Excluded {excluded} non-football stories")

    new_stories = []
    for story in filtered:
        if not is_story_seen(conn, story["story_hash"], config.DEDUP_WINDOW_HOURS):
            new_stories.append(story)
            add_story(
                conn,
                story["story_hash"],
                story.get("title", ""),
                story.get("source", ""),
                story.get("url", ""),
                story.get("matched_keyword", ""),
            )

    if not new_stories:
        logger.info("Spike Detector: No new stories found")
        conn.close()
        return []

    logger.info(f"Spike Detector: Processing {len(new_stories)} new stories")

    keyword_counts = defaultdict(int)
    for story in new_stories:
        kw = story.get("matched_keyword", "")
        if kw:
            keyword_counts[kw] += 1
    for kw, count in keyword_counts.items():
        record_keyword_mention(conn, kw, "combined", count)

    clusters = _cluster_stories(new_stories)

    trending_topics = []
    min_score = getattr(config, "SPIKE_MIN_SCORE", 35)
    for cluster_stories in clusters:
        score, factors = _calculate_spike_score(cluster_stories, conn)
        if score < min_score:
            continue

        best_story = max(cluster_stories, key=lambda s: len(s.get("title", "")))
        trending_topics.append(
            {
                "topic": best_story.get("title", "Untitled"),
                "score": score,
                "factors": factors,
                "stories": cluster_stories,
                "sources": list(set(s.get("source", "Unknown") for s in cluster_stories)),
                "top_url": best_story.get("url", ""),
                "matched_keyword": best_story.get("matched_keyword", ""),
                "story_count": len(cluster_stories),
            }
        )

    trending_topics.sort(key=lambda x: x["score"], reverse=True)
    conn.close()
    logger.info(f"Spike Detector: Identified {len(trending_topics)} trending topics")
    return trending_topics


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)