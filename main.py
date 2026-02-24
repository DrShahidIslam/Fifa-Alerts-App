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
    send_trending_alert, send_simple_message, send_status_update,
    send_article_preview, send_publish_confirmation, send_generating_status,
    send_image_preview, get_updates, answer_callback_query, test_connection
)
from database.db import get_connection, cleanup_old_data, mark_notified, record_notification
from writer.article_generator import generate_article
from publisher.wordpress_client import create_post
from publisher.image_handler import generate_featured_image

# ── Global state for command handler ──────────────────────────────────
_latest_topics = []       # Most recent trending topics from last scan
_pending_article = None   # Article awaiting approval
_pending_image_path = None  # Featured image awaiting approval
_update_offset = None     # Telegram getUpdates offset
_gemini_quota_exhausted = False  # Set True when Gemini daily quota is hit
_article_attempted_this_run = False  # Limit to one article generation per --once run

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
        # Always send a scan summary so user knows the agent is working
        send_simple_message(
            f"📊 Scan complete ({datetime.now().strftime('%H:%M UTC')})\n"
            f"Stories found: {len(all_stories)}\n"
            f"Trending topics: 0\n"
            f"No alerts this cycle — all quiet."
        )
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

    # Store topics for command handler
    global _latest_topics
    _latest_topics = trending_topics

    return alerts_sent


def check_and_handle_commands():
    """
    Poll Telegram for incoming commands/button presses and handle them.
    Supports:
      - write_article (inline button or /write_article text)
      - approve / publish_live (inline button or /approve, /publish_live text)
      - ignore (inline button)
    """
    global _update_offset, _latest_topics, _pending_article, _pending_image_path

    updates = get_updates(offset=_update_offset)
    if not updates:
        return

    for update in updates:
        _update_offset = update["update_id"] + 1

        # Handle inline button callback
        callback = update.get("callback_query")
        if callback:
            data = callback.get("data", "")
            callback_id = callback.get("id")
            logger.info(f"📱 Received callback: {data}")

            if data == "write_article":
                answer_callback_query(callback_id, "✍️ Generating article...")
                _handle_write_article()
            elif data == "approve":
                answer_callback_query(callback_id, "✅ Publishing as draft...")
                _handle_approve(status="draft")
            elif data == "publish_live":
                answer_callback_query(callback_id, "🚀 Publishing live...")
                _handle_approve(status="publish")
            elif data == "reject":
                answer_callback_query(callback_id, "🗑️ Article discarded.")
                _pending_article = None
                _pending_image_path = None
                send_simple_message("🗑️ Article discarded.")
            elif data == "approve_image":
                answer_callback_query(callback_id, "✅ Image approved!")
                send_simple_message("✅ Image approved! It will be used as the featured image when you publish.")
            elif data == "regenerate_image":
                answer_callback_query(callback_id, "🔄 Regenerating image...")
                _handle_regenerate_image()
            elif data == "skip_image":
                answer_callback_query(callback_id, "🚫 Image skipped.")
                _pending_image_path = None
                send_simple_message("🚫 Image skipped. Article will be published without a featured image.")
            elif data == "ignore":
                answer_callback_query(callback_id, "👍 Ignored.")
            continue

        # Handle text commands
        message = update.get("message", {})
        text = message.get("text", "").strip().lower()

        if text.startswith("/write_article"):
            _handle_write_article()
        elif text.startswith("/approve"):
            _handle_approve(status="draft")
        elif text.startswith("/publish_live"):
            _handle_approve(status="publish")
        elif text.startswith("/reject"):
            _pending_article = None
            send_simple_message("🗑️ Article discarded.")


def _handle_write_article():
    """Generate an article from the most recent trending topic."""
    global _pending_article, _latest_topics, _gemini_quota_exhausted, _article_attempted_this_run

    # Only allow one article generation attempt per --once run
    # This prevents multiple stale callbacks from triggering repeated failures
    if _article_attempted_this_run:
        logger.info("⏭️ Skipping duplicate write_article — already attempted this run")
        return

    # Don't attempt generation if we already know the quota is exhausted
    if _gemini_quota_exhausted:
        logger.info("⏸️ Skipping article generation — Gemini quota exhausted this cycle")
        send_simple_message("⏸️ Gemini API quota exhausted. Article generation paused until next cycle.")
        return

    if not _latest_topics:
        send_simple_message("⚠️ No trending topics available. Wait for the next scan.")
        return

    _article_attempted_this_run = True  # Mark as attempted before trying

    topic = _latest_topics[0]  # Use the highest-scored topic
    logger.info(f"📝 Generating article for: {topic['topic']}")

    send_generating_status(topic["topic"])

    try:
        article = generate_article(topic)
        if article:
            _pending_article = article
            send_article_preview(article)
            logger.info(f"✅ Article preview sent: {article['title']}")
            # Auto-generate featured image after article is ready
            _generate_and_preview_image(article.get("title", ""))
        else:
            send_simple_message("❌ Article generation failed. Try again later.")
    except Exception as e:
        error_str = str(e)
        logger.error(f"Article generation error: {e}")
        # If quota is exhausted, set the flag to prevent further attempts
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            _gemini_quota_exhausted = True
            send_simple_message("❌ Gemini API quota exhausted. No more article attempts this cycle.")
        else:
            send_simple_message(f"❌ Error generating article: {error_str[:200]}")


def _generate_and_preview_image(article_title):
    """Generate a featured image and send it to Telegram for approval."""
    global _pending_image_path

    if not article_title:
        return

    send_simple_message("🎨 Generating featured image... This may take a moment.")

    try:
        image_path = generate_featured_image(article_title)
        if image_path:
            _pending_image_path = image_path
            send_image_preview(image_path, article_title)
            logger.info(f"🖼️ Image preview sent: {image_path}")
        else:
            send_simple_message("⚠️ Image generation failed. Article can still be published without an image.")
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        send_simple_message(f"⚠️ Image generation failed: {str(e)[:200]}. Article can still be published without an image.")


def _handle_regenerate_image():
    """Regenerate the featured image for the pending article."""
    global _pending_image_path

    if not _pending_article:
        send_simple_message("⚠️ No article pending. Nothing to generate an image for.")
        return

    _pending_image_path = None
    _generate_and_preview_image(_pending_article.get("title", ""))


def _handle_approve(status="draft"):
    """Publish the pending article to WordPress."""
    global _pending_article, _pending_image_path

    if not _pending_article:
        send_simple_message("⚠️ No article pending approval. Generate one first with ✍️ Write Article.")
        return

    logger.info(f"📤 Publishing article: {_pending_article['title']} (status: {status})")

    try:
        result = create_post(
            _pending_article,
            featured_image_path=_pending_image_path,
            status=status,
        )
        if result:
            img_note = " (with featured image)" if _pending_image_path else ""
            send_publish_confirmation(result["post_url"], _pending_article["title"])
            logger.info(f"✅ Published{img_note}: {result['post_url']}")
            _pending_article = None
            _pending_image_path = None
        else:
            send_simple_message("❌ WordPress publishing failed. Check your WP credentials.")
    except Exception as e:
        logger.error(f"WordPress publish error: {e}")
        send_simple_message(f"❌ Publishing error: {str(e)[:200]}")


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

            # Check for commands after each scan
            try:
                check_and_handle_commands()
            except Exception as e:
                logger.error(f"Command handler error: {e}")

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


def run_listen_loop():
    """
    Listen-only mode — polls for Telegram commands without running scans.
    Useful for handling /write_article, /approve etc. between scan cycles.
    """
    logger.info("👂 Listening for Telegram commands...")
    send_simple_message("👂 Agent is listening for commands. Tap ✍️ Write Article on any alert.")

    while True:
        try:
            check_and_handle_commands()
            time.sleep(2)  # Poll every 2 seconds
        except KeyboardInterrupt:
            logger.info("\n⏹️ Listener stopped.")
            break
        except Exception as e:
            logger.error(f"Listen loop error: {e}")
            time.sleep(5)


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
    parser.add_argument("--listen", action="store_true", help="Listen for Telegram commands only")
    args = parser.parse_args()

    if args.test:
        test_all_connections()
    elif args.listen:
        run_listen_loop()
    elif args.once:
        logger.info("Running single scan...")

        # First, handle any pending commands from PREVIOUS runs
        # (e.g., user tapped Approve/Reject after last --once exited)
        try:
            check_and_handle_commands()
        except Exception as e:
            logger.error(f"Command handler error: {e}")

        # Run the scan
        alerts = run_scan()

        # Auto-generate article for top trending topic (if any found)
        if _latest_topics and not _gemini_quota_exhausted:
            logger.info("📝 Auto-generating article for top trending topic...")
            _handle_write_article()

        logger.info("Done.")
    else:
        run_agent_loop()
