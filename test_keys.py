"""Test each Gemini API key individually to diagnose quota issues."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from google import genai
import config

for i, key in enumerate(config.GEMINI_API_KEYS):
    print(f"\n--- Key {i+1}/{len(config.GEMINI_API_KEYS)}: ...{key[-8:]} ---")
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Say hello in one word"
        )
        print(f"  SUCCESS: {response.text.strip()}")
    except Exception as e:
        err = str(e)
        if "limit: 0" in err:
            print(f"  FAIL: Quota limit is 0 (no free tier allocated)")
        elif "PerDay" in err:
            print(f"  FAIL: Daily quota exhausted")
        elif "PerMinute" in err:
            print(f"  FAIL: Per-minute rate limit hit")
        elif "429" in err:
            # Extract key details
            if "FreeTier" in err:
                print(f"  FAIL: Free tier quota issue")
            else:
                print(f"  FAIL: Rate limited (paid tier)")
            # Show the quota metrics
            import re
            metrics = re.findall(r'quotaId["\s:]+(\S+?)["},]', err)
            for m in metrics:
                print(f"    Quota: {m}")
        else:
            print(f"  FAIL: {err[:200]}")
