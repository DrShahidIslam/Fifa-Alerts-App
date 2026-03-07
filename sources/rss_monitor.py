"""
RSS Feed Monitor — Fetches and filters World Cup 2026 stories from major sports RSS feeds.
"""
import feedparser
import hashlib
import logging
import re
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def _normalize(text):
    """Lowercase and strip special chars for keyword matching."""
    return re.sub(r'[^a-z0-9\s]', '', text.lower())


def _matches_keywords(text, keywords=None):
    """Check if text matches any World Cup related keywords."""
    if keywords is None:
        keywords = config.ALL_KEYWORDS
    normalized = _normalize(text)
    for kw in keywords:
        if kw.lower() in normalized:
            return True, kw
    return False, None


def _hash_story(title, url):
    """Create a unique hash for a story based on title + URL."""
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _derive_feed_keyword(title, summary=""):
    """Create a human keyword for football-only feeds instead of using an internal label."""
    combined_text = f"{title} {summary}".strip()
    is_match, matched_keyword = _matches_keywords(combined_text)
    if is_match and matched_keyword:
        return matched_keyword

    cleaned = re.sub(r"<[^>]+>", " ", title or summary or "")
    cleaned = re.sub(r"^[^:]{1,30}:\s*", "", cleaned).strip()
    words = re.findall(r"[A-Za-z0-9']+", cleaned)
    stop_words = {"the", "a", "an", "and", "or", "with", "from", "after", "before", "today", "live", "report"}
    parts = [w for w in words if len(w) > 2 and w.lower() not in stop_words]
    if len(parts) >= 4:
        return " ".join(parts[:4])
    if parts:
        return " ".join(parts[:3])
    return "football news"


def fetch_rss_stories():
    """
    Fetch stories from all configured RSS feeds.
    In GENERAL_FOOTBALL_MODE, football-only feeds pass all stories.
    Other feeds still use keyword filtering.
    """
    stories = []
    general_mode = getattr(config, "GENERAL_FOOTBALL_MODE", False)
    football_feeds = getattr(config, "FOOTBALL_ONLY_FEEDS", [])

    for feed_name, feed_url in config.RSS_FEEDS.items():
        try:
            logger.info(f"Fetching RSS: {feed_name}")
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"RSS feed error for {feed_name}: {feed.bozo_exception}")
                continue

            # In general mode, football-only feeds accept all stories
            is_football_feed = general_mode and feed_name in football_feeds

            for entry in feed.entries[:30]:  # Check latest 30 entries
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")

                if is_football_feed:
                    # Accept all stories from football-only feeds
                    is_match = True
                    matched_keyword = _derive_feed_keyword(title, summary)
                else:
                    # Check if this story matches keywords
                    combined_text = f"{title} {summary}"
                    is_match, matched_keyword = _matches_keywords(combined_text)

                if is_match:
                    # Parse published date
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            published = datetime(*entry.published_parsed[:6])
                        except Exception:
                            published = datetime.utcnow()
                    else:
                        published = datetime.utcnow()

                    story = {
                        "title": title.strip(),
                        "summary": summary.strip()[:500],
                        "url": link.strip(),
                        "source": feed_name,
                        "source_type": "rss",
                        "matched_keyword": matched_keyword,
                        "published_at": published,
                        "story_hash": _hash_story(title, link),
                    }
                    stories.append(story)
                    logger.debug(f"  ✓ Matched: {title[:80]} [{matched_keyword}]")

        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_name}: {e}")
            continue

    # Exclusion filter — remove cricket, rugby, etc. at source level
    exclude_kws = getattr(config, "EXCLUDE_KEYWORDS", [])
    filtered = []
    excluded_count = 0
    for story in stories:
        text = f"{story.get('title', '')} {story.get('summary', '')}".lower()
        if any(kw.lower() in text for kw in exclude_kws):
            excluded_count += 1
            continue
        filtered.append(story)

    if excluded_count > 0:
        logger.info(f"RSS Monitor: Excluded {excluded_count} irrelevant stories (cricket/rugby/etc.)")

    logger.info(f"RSS Monitor: Found {len(filtered)} football stories across {len(config.RSS_FEEDS)} feeds")
    return filtered


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    stories = fetch_rss_stories()
    for s in stories[:10]:
        print(f"[{s['source']}] {s['title']}")
        print(f"  Keyword: {s['matched_keyword']} | URL: {s['url'][:80]}")
        print()
