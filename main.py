"""
FIFA World Cup 2026 News Agent — Main Entry Point

Orchestrates the detection → notification → writing → publishing pipeline.
Runs on a configurable schedule (default: every 30 minutes).

Usage:
    python main.py              # Run the agent loop
    python main.py --once       # Run a single scan and exit
    python main.py --test       # Test all connections
"""
import argparse
import logging
import time
import sys
import os
from datetime import datetime

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

import config
from sources.rss_monitor import fetch_rss_stories
from sources.trends_monitor import fetch_trending_queries, get_realtime_trending
from sources.news_api_monitor import fetch_news_headlines
from detection.spike_detector import detect_spikes
from notifications.telegram_bot import (
    send_trending_alert, send_simple_message, send_status_update, test_connection
)
from database.db import get_connection, cleanup_old_data, mark_notified, record_notification

# ── Logging Setup ─────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), config.LOG_FILE),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger("FIFANewsAgent")


def run_scan():
    """
    Execute a single scan cycle:
    1. Fetch stories from all sources
    2. Detect spikes
    3. Send Telegram alerts for trending topics
    """
    logger.info("=" * 60)
    logger.info(f"🔍 Starting scan at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    all_stories = []
    trends_data = []

    # ── Step 1: Fetch from all sources ────────────────────────────
    # RSS Feeds
    try:
        logger.info("📡 Fetching RSS feeds...")
        rss_stories = fetch_rss_stories()
        all_stories.extend(rss_stories)
        logger.info(f"   RSS: {len(rss_stories)} stories")
    except Exception as e:
        logger.error(f"RSS Monitor failed: {e}")

    # NewsAPI
    try:
        logger.info("📰 Fetching NewsAPI headlines...")
        news_stories = fetch_news_headlines()
        all_stories.extend(news_stories)
        logger.info(f"   NewsAPI: {len(news_stories)} stories")
    except Exception as e:
        logger.error(f"NewsAPI Monitor failed: {e}")

    # Google Trends
    try:
        logger.info("📈 Checking Google Trends...")
        trends_data = fetch_trending_queries()
        logger.info(f"   Trends: {len(trends_data)} data points")
    except Exception as e:
        logger.error(f"Trends Monitor failed: {e}")

    # Real-time trending searches
    try:
        logger.info("⚡ Checking real-time trending searches...")
        realtime = get_realtime_trending()
        # Add real-time trends as stories
        for rt in realtime:
            all_stories.append({
                "title": f"Trending: {rt['keyword']}",
                "summary": f"'{rt['keyword']}' is currently trending on Google in the USA",
                "url": f"https://trends.google.com/trends/explore?q={rt['keyword'].replace(' ', '+')}",
                "source": "Google Trending",
                "source_type": "realtime_trends",
                "matched_keyword": rt.get("matched_keyword", rt["keyword"]),
                "published_at": datetime.utcnow(),
                "story_hash": f"rt_{rt['keyword'][:20].replace(' ', '_')}",
                "is_rising": True,
            })
        logger.info(f"   Real-time: {len(realtime)} WC-related trends")
    except Exception as e:
        logger.error(f"Real-time Trends failed: {e}")

    # ── Step 2: Detect spikes ─────────────────────────────────────
    logger.info(f"\n🔬 Analyzing {len(all_stories)} total stories...")
    trending_topics = detect_spikes(all_stories, trends_data)

    if not trending_topics:
        logger.info("✅ No new trending topics detected this cycle.")
        return 0

    logger.info(f"🔥 Found {len(trending_topics)} trending topics!")

    # ── Step 3: Send Telegram alerts ──────────────────────────────
    conn = get_connection()
    alerts_sent = 0

    for topic in trending_topics[:5]:  # Max 5 alerts per cycle to avoid spam
        try:
            logger.info(f"\n📱 Sending alert: {topic['topic'][:80]}")
            logger.info(f"   Score: {topic['score']} | Sources: {', '.join(topic['sources'][:3])}")

            message_id = send_trending_alert(topic)

            if message_id:
                alerts_sent += 1
                # Record in database
                for story in topic.get("stories", []):
                    mark_notified(conn, story.get("story_hash", ""))
                record_notification(conn, topic.get("stories", [{}])[0].get("story_hash", ""), message_id)
                logger.info(f"   ✅ Alert sent (Telegram ID: {message_id})")
            else:
                logger.warning(f"   ⚠️ Failed to send alert")

            # Small delay between messages to avoid Telegram rate limits
            time.sleep(1)

        except Exception as e:
            logger.error(f"Error sending alert for '{topic['topic'][:50]}': {e}")

    conn.close()
    logger.info(f"\n📊 Scan complete: {alerts_sent} alerts sent out of {len(trending_topics)} topics")
    return alerts_sent


def run_agent_loop():
    """
    Main agent loop — runs scans at the configured interval.
    """
    interval = config.SCAN_INTERVAL_MINUTES

    logger.info("🤖 FIFA World Cup 2026 News Agent starting up...")
    logger.info(f"   Scan interval: {interval} minutes")
    logger.info(f"   Keywords tracked: {len(config.ALL_KEYWORDS)}")
    logger.info(f"   RSS feeds: {len(config.RSS_FEEDS)}")

    # Send startup notification
    send_status_update(
        f"Agent started at {datetime.now().strftime('%H:%M %Z')}\n"
        f"Monitoring {len(config.ALL_KEYWORDS)} keywords across {len(config.RSS_FEEDS)} RSS feeds + NewsAPI + Google Trends\n"
        f"Scan interval: every {interval} minutes"
    )

    scan_count = 0

    while True:
        try:
            scan_count += 1
            logger.info(f"\n{'=' * 60}")
            logger.info(f"SCAN #{scan_count}")
            logger.info(f"{'=' * 60}")

            alerts = run_scan()

            # Periodic cleanup
            if scan_count % 48 == 0:  # Every ~24 hours (at 30-min intervals)
                logger.info("🧹 Running database cleanup...")
                conn = get_connection()
                cleanup_old_data(conn, days=7)
                conn.close()

            logger.info(f"💤 Next scan in {interval} minutes...")
            time.sleep(interval * 60)

        except KeyboardInterrupt:
            logger.info("\n⏹️ Agent stopped by user.")
            send_simple_message("⏹️ FIFA News Agent has been stopped.")
            break
        except Exception as e:
            logger.error(f"❌ Scan error: {e}", exc_info=True)
            logger.info(f"Retrying in {interval} minutes...")
            time.sleep(interval * 60)


def test_all_connections():
    """Test all API connections and report status."""
    print("🔍 Testing all connections...\n")

    # Telegram
    print("1️⃣  Telegram Bot:")
    ok, name = test_connection()
    if ok:
        print(f"   ✅ Connected as @{name}")
        mid = send_simple_message("🧪 Connection test successful! Your FIFA News Agent is ready.")
        print(f"   ✅ Test message sent (ID: {mid})")
    else:
        print("   ❌ FAILED — Check TELEGRAM_BOT_TOKEN in .env")

    # NewsAPI
    print("\n2️⃣  NewsAPI:")
    try:
        from newsapi import NewsApiClient
        newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
        result = newsapi.get_top_headlines(q="football", language="en", page_size=1)
        if result.get("status") == "ok":
            print(f"   ✅ Connected — {result.get('totalResults', 0)} results available")
        else:
            print(f"   ❌ FAILED — {result}")
    except Exception as e:
        print(f"   ❌ FAILED — {e}")

    # RSS Feeds
    print("\n3️⃣  RSS Feeds:")
    import feedparser
    for name, url in list(config.RSS_FEEDS.items())[:3]:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                print(f"   ✅ {name}: {len(feed.entries)} entries")
            else:
                print(f"   ⚠️ {name}: No entries (feed may be empty or blocked)")
        except Exception as e:
            print(f"   ❌ {name}: {e}")

    # Google Trends
    print("\n4️⃣  Google Trends:")
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 30))
        trending = pytrends.trending_searches(pn='united_states')
        if trending is not None and not trending.empty:
            print(f"   ✅ Connected — {len(trending)} trending searches found")
        else:
            print("   ⚠️ Connected but no trending data returned")
    except Exception as e:
        print(f"   ❌ FAILED — {e}")

    # WordPress
    print("\n5️⃣  WordPress REST API:")
    try:
        import requests
        resp = requests.get(
            f"{config.WP_URL}/wp-json/wp/v2/categories",
            auth=(config.WP_USERNAME, config.WP_APP_PASSWORD),
            timeout=10
        )
        if resp.status_code == 200:
            cats = [c["name"] for c in resp.json()]
            print(f"   ✅ Connected — Categories: {', '.join(cats[:5])}")
        else:
            print(f"   ❌ FAILED — HTTP {resp.status_code}")
    except Exception as e:
        print(f"   ❌ FAILED — {e}")

    # Gemini API
    print("\n6️⃣  Google Gemini API:")
    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents="Say 'API connected' in exactly two words."
        )
        print(f"   ✅ Connected — Response: {response.text.strip()}")
    except Exception as e:
        print(f"   ❌ FAILED — {e}")

    print("\n" + "=" * 40)
    print("✅ Connection test complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FIFA World Cup 2026 News Agent")
    parser.add_argument("--once", action="store_true", help="Run a single scan and exit")
    parser.add_argument("--test", action="store_true", help="Test all API connections")
    args = parser.parse_args()

    if args.test:
        test_all_connections()
    elif args.once:
        logger.info("Running single scan...")
        run_scan()
        logger.info("Done.")
    else:
        run_agent_loop()
