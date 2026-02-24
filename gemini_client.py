"""
Gemini Client Helper — Handles API key rotation and retries when rate limits are exhausted.
"""
import logging
import time
import re
from google import genai
import config

logger = logging.getLogger(__name__)

def generate_content_with_fallback(
    model, 
    contents, 
    generation_config=None,
    max_retries_per_key=3, 
    base_delay=20
):
    """
    Call Gemini API with exponential backoff on 429/RESOURCE_EXHAUSTED errors.
    It cycles through available API keys in config.GEMINI_API_KEYS.
    """
    keys = config.GEMINI_API_KEYS
    if not keys:
        raise ValueError("No Gemini API keys configured.")
        
    for key_idx, current_key in enumerate(keys):
        client = genai.Client(api_key=current_key)
        
        for attempt in range(max_retries_per_key + 1):
            try:
                if generation_config:
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=generation_config
                    )
                else:
                    response = client.models.generate_content(
                        model=model,
                        contents=contents
                    )
                return response
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
    
                if not is_rate_limit:
                    if key_idx == len(keys) - 1:
                        # Non-retryable error, and it's the last key, so raise
                        raise
                    logger.warning(f"  ⚠️ Error from key {key_idx + 1}: {e}. Trying next key...")
                    break # Try next key
                
                # Check if this is a DAILY quota exhaustion
                if "limit: 0" in error_str or "PerDay" in error_str:
                    logger.warning(f"  ⚠️ Gemini daily quota exhausted for key {key_idx + 1}/{len(keys)}.")
                    break # Go to next key
                
                # It's a per-minute rate limit. If we have more keys, just jump to the next one.
                if key_idx < len(keys) - 1:
                    logger.warning(f"  ⚠️ Gemini rate limited on key {key_idx + 1}, trying next key immediately...")
                    break # Go to next key
                
                # If we are on the LAST key, do exponential backoff
                if attempt >= max_retries_per_key:
                    logger.error(f"  ❌ Gemini API exhausted all {max_retries_per_key} retries on the last key.")
                    raise
                
                # Try to parse retry delay from error message (e.g., "Please retry in 18.5s")
                delay = base_delay * (2 ** attempt)
                retry_match = re.search(r'retry in ([\d.]+)s', error_str)
                if retry_match:
                    parsed_delay = float(retry_match.group(1))
                    delay = max(delay, parsed_delay + 2)
                    
                logger.warning(f"  ⏳ Gemini rate limited on final key (attempt {attempt + 1}/{max_retries_per_key}). "
                               f"Waiting {delay:.0f}s before retry...")
                time.sleep(delay)
                
    raise Exception("All Gemini API keys failed or exhausted quota.")
