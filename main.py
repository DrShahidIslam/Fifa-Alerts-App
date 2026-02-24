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
import json
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
from gemini_client import generate_content_with_fallback

# ── Global state for command handler ──────────────────────────────────
_latest_topics = []       # Most recent trending topics from last scan
_pending_article = None   # Article awaiting approval
_pending_image_path = None  # Featured image awaiting approval
_update_offset = None     # Telegram getUpdates offset
_gemini_quota_exhausted = False  # Set True when Gemini daily quota is hit
_article_attempted_this_run = False  # Limit to one article generation per --once run

def save_pending_state():
    """Save pending article and image path to disk for cross-run persistence."""
    state = {
        "article": _pending_article,
        "image_path": _pending_image_path
    }
    try:
        with open("pending_state.json", "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Failed to save pending state: {e}")

def load_pending_state():
    """Load pending article and image path from disk."""
    global _pending_article, _pending_image_path
    if _pending_article:
        return True
    try:
        if os.path.exists("pending_state.json"):
            with open("pending_state.json", "r", encoding="utf-8") as f:
                state = json.load(f)
                _pending_article = state.get("article")
                _pending_image_path = state.get("image_path")
                return bool(_pending_article)
    except Exception as e:
        logger.error(f"Failed to load pending state: {e}")
    return False

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
    
    # Save topics to disk for robustness across runs (especially if Telegram times out)
    try:
        with open("latest_topics.json", "w", encoding="utf-8") as f:
            json.dump(_latest_topics, f, default=str)
    except Exception as e:
        logger.error(f"Failed to save latest topics to disk: {e}")

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
                save_pending_state()
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
                save_pending_state()
                send_simple_message("🚫 Image skipped. Article will be published without a featured image.")
            elif data.startswith("publish_draft_"):
                post_id = data.split("_")[-1]
                answer_callback_query(callback_id, "🚀 Making post live...")
                _handle_publish_draft(post_id)
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
            _pending_image_path = None
            save_pending_state()
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

    topic = None
    if _latest_topics:
        topic = _latest_topics[0]
    else:
        # Reconstruct from disk if running in isolated environment (e.g., GitHub Actions)
        # We use a local JSON file now because DB 'notifications_sent' might be empty if Telegram timed out.
        try:
            if os.path.exists("latest_topics.json"):
                with open("latest_topics.json", "r", encoding="utf-8") as f:
                    saved_topics = json.load(f)
                    if saved_topics and len(saved_topics) > 0:
                        topic = saved_topics[0]
                        _latest_topics = saved_topics  # Restore to memory
        except Exception as e:
            logger.error(f"Error reading last topics from disk: {e}")
            
        # Fallback to DB (legacy approach) if JSON is missing
        if not topic:
            try:
                conn = get_connection()
                row = conn.execute("""
                    SELECT s.title, s.source, s.url, s.keywords, s.story_hash
                    FROM notifications_sent n
                    JOIN seen_stories s ON n.story_hash = s.story_hash
                    ORDER BY n.sent_at DESC LIMIT 1
                """).fetchone()
                conn.close()
                
                if row:
                    topic = {
                        "topic": row["title"],
                        "matched_keyword": row["keywords"],
                        "top_url": row["url"],
                        "stories": [{"title": row["title"], "source": row["source"], "url": row["url"], "summary": row["title"]}]
                    }
            except Exception as e:
                logger.error(f"Error reading last topic from DB: {e}")

    if not topic:
        send_simple_message("⚠️ No trending topics found in memory or database. Wait for the next scan.")
        return

    _article_attempted_this_run = True  # Mark as attempted before trying

    logger.info(f"📝 Generating article for: {topic['topic']}")

    send_generating_status(topic["topic"])

    try:
        article = generate_article(topic)
        if article:
            _pending_article = article
            send_article_preview(article)
            logger.info(f"✅ Article preview sent: {article['title']}")
            save_pending_state()
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
            save_pending_state()
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

    if not _pending_article and not load_pending_state():
        send_simple_message("⚠️ No article pending. Nothing to generate an image for.")
        return

    _pending_image_path = None
    _generate_and_preview_image(_pending_article.get("title", ""))


def _handle_approve(status="draft"):
    """Publish the pending article to WordPress."""
    global _pending_article, _pending_image_path

    if not _pending_article and not load_pending_state():
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
            send_publish_confirmation(result["post_url"], _pending_article["title"], post_id=result["post_id"], status=status)
            logger.info(f"✅ Published{img_note}: {result['post_url']}")
            _pending_article = None
            _pending_image_path = None
            save_pending_state()
        else:
            send_simple_message("❌ WordPress publishing failed. Check your WP credentials.")
    except Exception as e:
        logger.error(f"WordPress publish error: {e}")
        send_simple_message(f"❌ Publishing error: {str(e)[:200]}")

def _handle_publish_draft(post_id):
    """Publish an existing draft on WordPress."""
    from publisher.wordpress_client import update_post_status
    
    logger.info(f"🚀 Publishing draft (ID: {post_id})")
    try:
        url = update_post_status(post_id, "publish")
        if url:
            send_simple_message(f"🚀 Draft published successfully!\n🔗 {url}")
            logger.info(f"✅ Draft {post_id} published: {url}")
        else:
            send_simple_message("❌ Failed to publish draft. Check logs.")
    except Exception as e:
        logger.error(f"Draft publish error: {e}")
        send_simple_message(f"❌ Error publishing draft: {str(e)[:200]}")


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
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents="Say 'API connected' in exactly two words.",
            max_retries_per_key=1
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
        logger.info("Running single scan and processing commands...")

        # 1. Check for pending commands from previous runs
        try:
            check_and_handle_commands()
        except Exception as e:
            logger.error(f"Command handler error before scan: {e}")

        # 2. Run the scan
        alerts = run_scan()

        if alerts > 0:
            logger.info("Alerts sent. Polling for commands for 2 minutes to provide instant feedback...")
            end_time = time.time() + 120
            while time.time() < end_time:
                try:
                    check_and_handle_commands()
                except Exception as e:
                    logger.error(f"Command handler error after scan: {e}")
                time.sleep(3)
        else:
            # Poll one last time in case of a recent click
            try:
                check_and_handle_commands()
            except Exception as e:
                logger.error(f"Command handler error after scan: {e}")

        logger.info("Done.")
    else:
        run_agent_loop()
