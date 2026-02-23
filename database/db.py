"""
SQLite database for tracking seen stories, keyword baselines, and sent notifications.
Handles deduplication and spike history.
"""
import sqlite3
import os
import time
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent.db")


def get_connection():
    """Get a database connection, creating tables if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


def _create_tables(conn):
    """Create all required tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS seen_stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_hash TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            source TEXT,
            url TEXT,
            keywords TEXT,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notified INTEGER DEFAULT 0,
            article_written INTEGER DEFAULT 0,
            article_published INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS keyword_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            source TEXT NOT NULL,
            mention_count INTEGER DEFAULT 1,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notifications_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_hash TEXT NOT NULL,
            telegram_message_id TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trend_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            interest_value INTEGER,
            is_rising INTEGER DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_seen_stories_hash ON seen_stories(story_hash);
        CREATE INDEX IF NOT EXISTS idx_keyword_mentions_keyword ON keyword_mentions(keyword);
        CREATE INDEX IF NOT EXISTS idx_notifications_hash ON notifications_sent(story_hash);
    """)
    conn.commit()


def is_story_seen(conn, story_hash, dedup_hours=12):
    """Check if a story has been seen within the deduplication window."""
    cutoff = datetime.utcnow() - timedelta(hours=dedup_hours)
    row = conn.execute(
        "SELECT id FROM seen_stories WHERE story_hash = ? AND first_seen_at > ?",
        (story_hash, cutoff.isoformat())
    ).fetchone()
    return row is not None


def add_story(conn, story_hash, title, source, url, keywords=""):
    """Record a new story in the database."""
    try:
        conn.execute(
            """INSERT OR IGNORE INTO seen_stories (story_hash, title, source, url, keywords)
               VALUES (?, ?, ?, ?, ?)""",
            (story_hash, title, source, url, keywords)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already exists


def mark_notified(conn, story_hash):
    """Mark a story as having been notified about."""
    conn.execute(
        "UPDATE seen_stories SET notified = 1 WHERE story_hash = ?",
        (story_hash,)
    )
    conn.commit()


def record_keyword_mention(conn, keyword, source, count=1):
    """Record a keyword mention for baseline tracking."""
    conn.execute(
        """INSERT INTO keyword_mentions (keyword, source, mention_count)
           VALUES (?, ?, ?)""",
        (keyword, source, count)
    )
    conn.commit()


def get_keyword_baseline(conn, keyword, hours=24):
    """Get the average mention count for a keyword over the past N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    row = conn.execute(
        """SELECT AVG(mention_count) as avg_count, COUNT(*) as samples
           FROM keyword_mentions
           WHERE keyword = ? AND recorded_at > ?""",
        (keyword, cutoff.isoformat())
    ).fetchone()
    if row and row["avg_count"]:
        return float(row["avg_count"]), int(row["samples"])
    return 0.0, 0


def record_notification(conn, story_hash, message_id=""):
    """Record that a notification was sent."""
    conn.execute(
        """INSERT INTO notifications_sent (story_hash, telegram_message_id)
           VALUES (?, ?)""",
        (story_hash, str(message_id))
    )
    conn.commit()


def record_trend_snapshot(conn, keyword, interest_value, is_rising=False):
    """Record a Google Trends snapshot."""
    conn.execute(
        """INSERT INTO trend_snapshots (keyword, interest_value, is_rising)
           VALUES (?, ?, ?)""",
        (keyword, interest_value, 1 if is_rising else 0)
    )
    conn.commit()


def cleanup_old_data(conn, days=7):
    """Remove data older than N days to keep the DB small."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    conn.execute("DELETE FROM keyword_mentions WHERE recorded_at < ?", (cutoff.isoformat(),))
    conn.execute("DELETE FROM trend_snapshots WHERE recorded_at < ?", (cutoff.isoformat(),))

    # Also clean up seen_stories and notifications older than 14 days
    # (2x the 7-day dedup window as safety margin)
    old_cutoff = datetime.utcnow() - timedelta(days=14)
    conn.execute("DELETE FROM seen_stories WHERE first_seen_at < ?", (old_cutoff.isoformat(),))
    conn.execute("DELETE FROM notifications_sent WHERE sent_at < ?", (old_cutoff.isoformat(),))
    conn.commit()
