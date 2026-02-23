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


def fetch_rss_stories():
    """
    Fetch stories from all configured RSS feeds.
    Returns a list of story dicts that match World Cup keywords.
    """
    stories = []

    for feed_name, feed_url in config.RSS_FEEDS.items():
        try:
            logger.info(f"Fetching RSS: {feed_name}")
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"RSS feed error for {feed_name}: {feed.bozo_exception}")
                continue

            for entry in feed.entries[:30]:  # Check latest 30 entries
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")

                # Check if this story is World Cup related
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

    logger.info(f"RSS Monitor: Found {len(stories)} World Cup stories across {len(config.RSS_FEEDS)} feeds")
    return stories


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    stories = fetch_rss_stories()
    for s in stories[:10]:
        print(f"[{s['source']}] {s['title']}")
        print(f"  Keyword: {s['matched_keyword']} | URL: {s['url'][:80]}")
        print()
