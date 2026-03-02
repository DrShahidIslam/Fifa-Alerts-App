"""
WordPress Client — Handles all WordPress REST API interactions:
creating posts, uploading media, setting categories/tags,
and injecting RankMath SEO fields.
"""
import base64
import logging
import os
import re
import json
import time
import requests
from requests.auth import HTTPBasicAuth

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)

API_BASE = f"{config.WP_URL}/wp-json/wp/v2"
AUTH = HTTPBasicAuth(config.WP_USERNAME, config.WP_APP_PASSWORD)
TIMEOUT = 30
RETRY_DELAY = 5   # seconds between retries on 502/503
RETRY_403_DELAY = 4  # seconds before retry on 403 (some firewalls allow on retry)
# Browser-like headers reduce "bot" detection by Wordfence/Cloudflare
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FIFANewsAgent/1.0; +https://github.com/DrShahidIslam/Fifa-Alerts-App)",
    "Referer": f"{config.WP_URL}/",
    "Accept": "application/json, */*; q=0.1",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": config.WP_URL.rstrip("/"),
}


def create_post(article, featured_image_path=None, status=None):
    """
    Create a WordPress post from an article dict.
    If WP_PUBLISH_WEBHOOK_URL and WP_PUBLISH_SECRET are set, publishes via webhook (foolproof, no firewall).
    Otherwise uses REST API (may be blocked by Wordfence/Cloudflare from GitHub Actions).
    """
    if status is None:
        status = config.WP_DEFAULT_STATUS

    if getattr(config, "WP_PUBLISH_WEBHOOK_URL", None) and getattr(config, "WP_PUBLISH_SECRET", None):
        return _publish_via_webhook(article, featured_image_path, status)

    logger.info(f"Publishing to WordPress: '{article.get('title', 'Untitled')}'")

    # ── Step 1: Upload featured image (if provided) ───────────────
    media_id = None
    if featured_image_path and os.path.exists(featured_image_path):
        media_id = upload_media(featured_image_path, article.get("title", ""))

    # ── Step 2: Get or create category ────────────────────────────
    category_id = get_or_create_category(article.get("category", config.WP_DEFAULT_CATEGORY))

    # ── Step 3: Get or create tags ────────────────────────────────
    tag_ids = []
    for tag_name in article.get("tags", []):
        tag_id = get_or_create_tag(tag_name)
        if tag_id:
            tag_ids.append(tag_id)

    # ── Step 4: Create the post (with retry on 502/503) ───────────
    post_data = {
        "title": article.get("title", "Untitled"),
        "content": article.get("full_content", article.get("content", "")),
        "excerpt": article.get("meta_description", ""),
        "slug": article.get("slug", ""),
        "status": status,
        "categories": [category_id] if category_id else [],
        "tags": tag_ids,
        "comment_status": "open",
    }

    if media_id:
        post_data["featured_media"] = media_id

    try:
        for attempt in range(3):
            response = requests.post(
                f"{API_BASE}/posts",
                json=post_data,
                auth=AUTH,
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            if response.status_code in (200, 201):
                result = response.json()
                post_id = result.get("id")
                post_url = result.get("link", "")

                logger.info(f"  Post created (ID: {post_id}, Status: {status})")
                logger.info(f"  URL: {post_url}")

                # ── Step 5: Set RankMath SEO fields ─────────────────────
                _set_rankmath_meta(post_id, article)

                return {
                    "post_id": post_id,
                    "post_url": post_url,
                    "status": status,
                }
            if response.status_code in (502, 503) and attempt < 2:
                logger.warning(f"  WordPress {response.status_code}, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            if response.status_code == 403 and attempt < 2:
                logger.warning(f"  403 Forbidden, retrying in {RETRY_403_DELAY}s (attempt {attempt + 1}/3)...")
                time.sleep(RETRY_403_DELAY)
                continue
            break

        logger.error(f"  Post creation failed: HTTP {response.status_code}")
        logger.error(f"     Response: {response.text[:500]}")
        if response.status_code == 403:
            logger.error("     Tip: 403 from GitHub Actions = firewall blocking runner IPs. See deploy/WP_FIREWALL_GUIDE.md Step 1b.")
        return None

    except Exception as e:
        logger.error(f"  Post creation error: {e}")
        return None


def _publish_via_webhook(article, featured_image_path=None, status=None):
    """
    Publish via webhook on the user's server. No REST API from agent = no firewall block.
    Requires deploy/fifa-agent-webhook.php on the server and WP_PUBLISH_WEBHOOK_URL + WP_PUBLISH_SECRET in env.
    """
    url = config.WP_PUBLISH_WEBHOOK_URL
    secret = config.WP_PUBLISH_SECRET
    if not url or not secret:
        return None

    payload = {
        "title": article.get("title", "Untitled"),
        "content": article.get("full_content", article.get("content", "")),
        "excerpt": article.get("meta_description", ""),
        "slug": article.get("slug", ""),
        "status": status or config.WP_DEFAULT_STATUS,
        "tags": article.get("tags", []),
        "category": article.get("category", config.WP_DEFAULT_CATEGORY),
        "rank_math_title": article.get("title", ""),
        "rank_math_description": article.get("meta_description", ""),
        "rank_math_focus_keyword": article.get("matched_keyword", "") or (article.get("tags") or [""])[0],
    }
    if featured_image_path and os.path.exists(featured_image_path):
        with open(featured_image_path, "rb") as f:
            payload["featured_image_base64"] = base64.b64encode(f.read()).decode("ascii")
        payload["featured_image_filename"] = os.path.basename(featured_image_path)

    for attempt in range(3):
        try:
            r = requests.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-FIFA-Agent-Token": secret,
                    "User-Agent": "FIFANewsAgent/1.0",
                },
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    logger.info(f"  Post created via webhook (ID: {data.get('post_id')}, URL: {data.get('post_url', '')})")
                    return {
                        "post_id": data.get("post_id"),
                        "post_url": data.get("post_url", ""),
                        "status": data.get("status", status),
                    }
                logger.error(f"  Webhook returned success=false: {data.get('message', '')}")
                return None
            if r.status_code in (502, 503, 403) and attempt < 2:
                logger.warning(f"  Webhook {r.status_code}, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            logger.error(f"  Webhook failed: HTTP {r.status_code} - {r.text[:300]}")
            return None
        except Exception as e:
            logger.warning(f"  Webhook request error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(RETRY_DELAY)
    return None


def upload_media(file_path, title=""):
    """
    Upload an image file to WordPress media library. Retries once on 502/503.

    Returns:
        int: media ID, or None if failed
    """
    filename = os.path.basename(file_path)
    mime_type = _get_mime_type(filename)

    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        headers = HEADERS.copy()
        headers.update({
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": mime_type,
        })

        for attempt in range(3):
            response = requests.post(
                f"{API_BASE}/media",
                data=file_data,
                headers=headers,
                auth=AUTH,
                timeout=60,
            )
            if response.status_code in (200, 201):
                media_id = response.json().get("id")
                logger.info(f"  Image uploaded (Media ID: {media_id})")

                if title:
                    requests.post(
                        f"{API_BASE}/media/{media_id}",
                        json={"alt_text": title[:125]},
                        auth=AUTH,
                        headers=HEADERS,
                        timeout=15,
                    )
                return media_id
            if response.status_code in (502, 503) and attempt < 2:
                logger.warning(f"  Media upload {response.status_code}, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            if response.status_code == 403 and attempt < 2:
                logger.warning(f"  403 on media upload, retrying in {RETRY_403_DELAY}s (attempt {attempt + 1}/3)...")
                time.sleep(RETRY_403_DELAY)
                continue
            break

        logger.error(f"  Media upload failed: HTTP {response.status_code}")
        logger.error(f"     {response.text[:300]}")
        if response.status_code == 403:
            logger.error("     Tip: See deploy/WP_FIREWALL_GUIDE.md Step 1b (allowlist GitHub Actions IPs).")
        return None

    except Exception as e:
        logger.error(f"  ❌ Media upload error: {e}")
        return None


def get_or_create_category(name):
    """Get category ID by name, creating it if it doesn't exist."""
    try:
        response = requests.get(
            f"{API_BASE}/categories",
            params={"search": name, "per_page": 5},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code == 200:
            categories = response.json()
            for cat in categories:
                if cat["name"].lower() == name.lower():
                    return cat["id"]

        response = requests.post(
            f"{API_BASE}/categories",
            json={"name": name},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code in (200, 201):
            cat_id = response.json().get("id")
            logger.info(f"  📁 Created category '{name}' (ID: {cat_id})")
            return cat_id

    except Exception as e:
        logger.error(f"  ❌ Category error for '{name}': {e}")

    return None


def get_or_create_tag(name):
    """Get tag ID by name, creating it if it doesn't exist."""
    try:
        response = requests.get(
            f"{API_BASE}/tags",
            params={"search": name, "per_page": 5},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code == 200:
            tags = response.json()
            for tag in tags:
                if tag["name"].lower() == name.lower():
                    return tag["id"]

        response = requests.post(
            f"{API_BASE}/tags",
            json={"name": name},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code in (200, 201):
            return response.json().get("id")

    except Exception as e:
        logger.error(f"  ❌ Tag error for '{name}': {e}")

    return None


def _set_rankmath_meta(post_id, article):
    """
    Set RankMath SEO metadata on a post.
    Uses the WordPress REST API custom fields that RankMath often looks for.
    """
    focus_kw = article.get("matched_keyword", "")
    if not focus_kw and article.get("tags"):
        focus_kw = article["tags"][0]

    # RankMath natively reads these meta keys if the WP REST API exposes them.
    # We will try both the nested 'meta' approach and the flat 'meta' approach.
    rankmath_meta = {
        "meta": {
            "rank_math_title": article.get("title", ""),
            "rank_math_description": article.get("meta_description", ""),
            "rank_math_focus_keyword": focus_kw,
            "rank_math_robots": ["index", "follow"],
        }
    }

    try:
        # PATCH is the correct method for partial post update (meta only).
        # Meta keys must be registered in WP (see deploy/rankmath-rest-snippet.php).
        response = requests.request(
            "PATCH",
            f"{API_BASE}/posts/{post_id}",
            json=rankmath_meta,
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code == 200:
            logger.info(f"  RankMath SEO metadata set (focus: '{focus_kw}')")
        else:
            logger.warning(
                f"  RankMath meta update returned HTTP {response.status_code}. "
                "Add deploy/rankmath-rest-snippet.php to your theme's functions.php so meta is writable via REST."
            )

    except Exception as e:
        logger.warning(f"  RankMath meta update failed: {e}")

def update_post_status(post_id, status="publish"):
    """Update a post's status (e.g., from draft to publish). Uses webhook if configured, else REST API."""
    if getattr(config, "WP_PUBLISH_WEBHOOK_URL", None) and getattr(config, "WP_PUBLISH_SECRET", None):
        return _update_status_via_webhook(post_id, status)
    try:
        response = requests.post(
            f"{API_BASE}/posts/{post_id}",
            json={"status": status},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            try:
                return response.json().get("link")
            except (ValueError, KeyError):
                logger.error("Update post status: response was not valid JSON (REST may be blocked)")
                return None
        logger.error(f"Failed to update post status: HTTP {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error updating post status: {e}")
        return None


def _update_status_via_webhook(post_id, status="publish"):
    """Update post status via webhook (same endpoint as create; avoids REST 403 from GitHub Actions)."""
    url = config.WP_PUBLISH_WEBHOOK_URL
    secret = config.WP_PUBLISH_SECRET
    if not url or not secret:
        return None
    try:
        r = requests.post(
            url,
            json={"action": "publish_draft", "post_id": int(post_id), "status": status},
            headers={"Content-Type": "application/json", "X-FIFA-Agent-Token": secret},
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                return data.get("post_url")
        return None
    except Exception as e:
        logger.warning(f"Webhook status update failed: {e}")
        return None


def _get_mime_type(filename):
    """Determine MIME type from filename."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return mime_map.get(ext, "image/jpeg")


def test_wordpress_connection():
    """Test the WordPress REST API connection."""
    try:
        response = requests.get(
            f"{API_BASE}/posts",
            params={"per_page": 1},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code == 200:
            posts = response.json()
            logger.info(f"WordPress: Connected. Latest post: '{posts[0]['title']['rendered'][:50]}'" if posts else "WordPress: Connected. No posts found.")
            return True
        else:
            logger.error(f"WordPress: HTTP {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"WordPress connection failed: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Test connection
    if test_wordpress_connection():
        print("✅ WordPress connection successful!")
    else:
        print("❌ WordPress connection failed!")
