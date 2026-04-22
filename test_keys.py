"""Test each Gemini API key individually to diagnose quota issues."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from google import genai
import config

for i, key in enumerate(config.GEMINI_API_KEYS):
    print(f"\n--- Key {i+1}/{len(config.GEMINI_API_KEYS)}: ...{key[-8:]} ---")
    model_name = config.GEMINI_MODEL
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model_name,
            contents="Say hello in one word"
        )
        print(f"  SUCCESS [{model_name}]: {response.text.strip()}")
    except Exception as e:
        err = str(e)
        if "NOT_FOUND" in err or "404" in err:
            print(f"  FAIL [{model_name}]: Not found")
        elif "limit: 0" in err:
            print(f"  FAIL [{model_name}]: Quota 0")
        elif "PerDay" in err:
            print(f"  FAIL [{model_name}]: Daily exhausted")
        elif "403" in err:
            print(f"  FAIL [{model_name}]: Permission denied (403)")
        else:
            print(f"  FAIL [{model_name}]: {err[:50]}")
