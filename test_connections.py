"""Quick connection test — no emojis for Windows compatibility."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
os.environ["PYTHONIOENCODING"] = "utf-8"

import config

print("=" * 50)
print("FIFA NEWS AGENT - CONNECTION TEST")
print("=" * 50)

# 1. Telegram
print("\n[1] Telegram Bot:")
try:
    import requests as req
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe"
    r = req.get(url, timeout=10)
    data = r.json()
    if data.get("ok"):
        print(f"    OK - Connected as @{data['result']['username']}")
        # Send test message
        send_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        msg_r = req.post(send_url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": "FIFA News Agent - Connection test successful! The agent is ready."
        }, timeout=10)
        msg_data = msg_r.json()
        if msg_data.get("ok"):
            print(f"    OK - Test message sent (ID: {msg_data['result']['message_id']})")
        else:
            print(f"    FAIL - Could not send message: {msg_data.get('description', 'unknown')}")
    else:
        print(f"    FAIL - {data}")
except Exception as e:
    print(f"    FAIL - {e}")

# 2. NewsAPI
print("\n[2] NewsAPI:")
try:
    from newsapi import NewsApiClient
    newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
    result = newsapi.get_top_headlines(q="football", language="en", page_size=1)
    if result.get("status") == "ok":
        print(f"    OK - {result.get('totalResults', 0)} results available")
    else:
        print(f"    FAIL - {result}")
except Exception as e:
    print(f"    FAIL - {e}")

# 3. RSS Feeds (quick test of 2 feeds)
print("\n[3] RSS Feeds:")
import feedparser
for name, url in list(config.RSS_FEEDS.items())[:3]:
    try:
        feed = feedparser.parse(url)
        count = len(feed.entries) if feed.entries else 0
        if count > 0:
            print(f"    OK - {name}: {count} entries")
        else:
            print(f"    WARN - {name}: No entries")
    except Exception as e:
        print(f"    FAIL - {name}: {e}")

# 4. WordPress
print("\n[4] WordPress REST API:")
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
        print(f"    OK - Categories: {', '.join(cats[:5])}")
    else:
        print(f"    WARN - HTTP {resp.status_code} (may need retry)")
except Exception as e:
    print(f"    FAIL - {e}")

# 5. Gemini API
print("\n[5] Google Gemini API:")
try:
    from gemini_client import generate_content_with_fallback
    response = generate_content_with_fallback(
        model=config.GEMINI_MODEL,
        contents="Respond with exactly: CONNECTED",
        max_retries_per_key=1
    )
    text = response.text.strip()
    print(f"    OK - Response: {text}")
except Exception as e:
    print(f"    FAIL - {e}")

# 6. Google Trends (quick check, skip if slow)
print("\n[6] Google Trends:")
try:
    from pytrends.request import TrendReq
    pytrends = TrendReq(hl='en-US', tz=0, timeout=(5, 10))
    trending = pytrends.trending_searches(pn='united_states')
    if trending is not None and not trending.empty:
        print(f"    OK - {len(trending)} trending searches found")
    else:
        print("    WARN - No trending data returned")
except Exception as e:
    print(f"    WARN - {e} (non-critical, trends still work)")

print("\n" + "=" * 50)
print("CONNECTION TEST COMPLETE")
print("=" * 50)
