"""Write test results to a file for readable output."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

log_path = os.path.join(os.path.dirname(__file__), "test_results.log")

import config

results = []
results.append("=" * 50)
results.append("FIFA NEWS AGENT - CONNECTION TEST")
results.append("=" * 50)

# 1. Telegram
results.append("\n[1] Telegram Bot:")
try:
    import requests as req
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe"
    r = req.get(url, timeout=10)
    data = r.json()
    if data.get("ok"):
        results.append(f"    OK - Connected as @{data['result']['username']}")
    else:
        results.append(f"    FAIL - {data.get('description', 'unknown')}")
except Exception as e:
    results.append(f"    FAIL - {e}")

# 2. NewsAPI
results.append("\n[2] NewsAPI:")
try:
    from newsapi import NewsApiClient
    newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
    result = newsapi.get_top_headlines(q="football", language="en", page_size=1)
    if result.get("status") == "ok":
        results.append(f"    OK - {result.get('totalResults', 0)} results available")
    else:
        results.append(f"    FAIL - {result}")
except Exception as e:
    results.append(f"    FAIL - {e}")

# 3. RSS Feeds
results.append("\n[3] RSS Feeds:")
import feedparser
for name, url in list(config.RSS_FEEDS.items())[:4]:
    try:
        feed = feedparser.parse(url)
        count = len(feed.entries) if feed.entries else 0
        if count > 0:
            results.append(f"    OK - {name}: {count} entries")
        else:
            results.append(f"    WARN - {name}: No entries (feed may be empty)")
    except Exception as e:
        results.append(f"    FAIL - {name}: {e}")

# 4. WordPress
results.append("\n[4] WordPress REST API:")
try:
    import requests as req
    from requests.auth import HTTPBasicAuth
    resp = req.get(
        f"{config.WP_URL}/wp-json/wp/v2/categories",
        auth=HTTPBasicAuth(config.WP_USERNAME, config.WP_APP_PASSWORD),
        timeout=15
    )
    if resp.status_code == 200:
        cats = [c["name"] for c in resp.json()]
        results.append(f"    OK - Categories: {', '.join(cats[:8])}")
    else:
        results.append(f"    HTTP {resp.status_code} - Response: {resp.text[:200]}")
except Exception as e:
    results.append(f"    FAIL - {e}")

# 5. Gemini API
results.append("\n[5] Google Gemini API:")
try:
    from gemini_client import generate_content_with_fallback
    response = generate_content_with_fallback(
        model=config.GEMINI_MODEL,
        contents="Respond with exactly one word: CONNECTED",
        max_retries_per_key=1
    )
    text = response.text.strip()
    results.append(f"    OK - Response: {text}")
except Exception as e:
    results.append(f"    FAIL - {e}")

results.append("\n" + "=" * 50)
results.append("TEST COMPLETE")
results.append("=" * 50)

output = "\n".join(results)
with open(log_path, "w", encoding="utf-8") as f:
    f.write(output)

print(f"Results written to {log_path}")
