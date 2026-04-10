"""
Gemini Client Helper - Handles API key rotation and retries when rate limits are exhausted.
"""
import logging
import time
import re

from google import genai

import config

logger = logging.getLogger(__name__)


def _classify_gemini_error(error):
    """Return a simple retry classification for Gemini API exceptions."""
    error_str = str(error or "")
    upper = error_str.upper()
    return {
        "error_str": error_str,
        "is_rate_limit": "429" in error_str or "RESOURCE_EXHAUSTED" in upper,
        "is_daily_quota": "limit: 0" in error_str or "PERDAY" in upper,
        "is_temporary_unavailable": (
            "503" in error_str
            or "500" in error_str
            or "UNAVAILABLE" in upper
            or "INTERNAL" in upper
            or "DEADLINE_EXCEEDED" in upper
            or "TIMEOUT" in upper
        ),
    }


def _compute_retry_delay(error_str, base_delay, attempt):
    delay = base_delay * (2 ** attempt)
    retry_match = re.search(r"retry in ([\d.]+)s", error_str)
    if retry_match:
        parsed_delay = float(retry_match.group(1))
        delay = max(delay, parsed_delay + 2)
    return delay


def generate_content_with_fallback(
    model,
    contents,
    generation_config=None,
    max_retries_per_key=3,
    base_delay=20,
):
    """
    Call Gemini API with exponential backoff on retryable errors.
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
                        config=generation_config,
                    )
                else:
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                    )
                return response
            except Exception as e:
                error_meta = _classify_gemini_error(e)
                error_str = error_meta["error_str"]
                is_retryable = error_meta["is_rate_limit"] or error_meta["is_temporary_unavailable"]

                if not is_retryable:
                    if key_idx == len(keys) - 1:
                        raise
                    logger.warning(f"  Error from key {key_idx + 1}: {e}. Trying next key...")
                    break

                if error_meta["is_daily_quota"]:
                    logger.warning(f"  Gemini daily quota exhausted for key {key_idx + 1}/{len(keys)}.")
                    break

                if key_idx < len(keys) - 1:
                    reason = "rate limited" if error_meta["is_rate_limit"] else "temporarily unavailable"
                    logger.warning(f"  Gemini {reason} on key {key_idx + 1}, trying next key immediately...")
                    break

                if attempt >= max_retries_per_key:
                    logger.error(f"  Gemini API exhausted all {max_retries_per_key} retries on the last key.")
                    raise

                delay = _compute_retry_delay(error_str, base_delay, attempt)
                reason = "rate limited" if error_meta["is_rate_limit"] else "temporarily unavailable"
                logger.warning(
                    f"  Gemini {reason} on final key (attempt {attempt + 1}/{max_retries_per_key}). "
                    f"Waiting {delay:.0f}s before retry..."
                )
                time.sleep(delay)

    raise Exception("All Gemini API keys failed or exhausted quota.")


def generate_image_with_gemini_flash(prompt, max_retries_per_key=2, base_delay=10):
    """
    Generate an image using Gemini 2.5 Flash Image (free tier). Uses generate_content with
    response_modalities including IMAGE. Returns response or None; caller extracts image from
    response.candidates[0].content.parts (part.inline_data.data).
    """
    try:
        from google.genai.types import GenerateContentConfig, Modality
    except ImportError:
        from google.genai import types

        GenerateContentConfig = getattr(types, "GenerateContentConfig", None)
        Modality = getattr(types, "Modality", None)
        if GenerateContentConfig is None or Modality is None:
            logger.warning("  Could not import GenerateContentConfig/Modality for Gemini Flash Image")
            return None

    keys = config.GEMINI_API_KEYS
    if not keys:
        return None

    contents = (
        "Generate a single photorealistic editorial image for a sports news article. "
        f"No text or captions in the image. Topic: {prompt}"
    )
    config_obj = GenerateContentConfig(
        response_modalities=[Modality.TEXT, Modality.IMAGE],
    )

    for key_idx, current_key in enumerate(keys):
        client = genai.Client(api_key=current_key)
        for attempt in range(max_retries_per_key + 1):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash-image",
                    contents=contents,
                    config=config_obj,
                )
                return response
            except Exception as e:
                error_meta = _classify_gemini_error(e)
                error_str = error_meta["error_str"]
                if "404" in error_str or "NOT FOUND" in error_str.upper():
                    logger.warning(f"  Gemini image model not available: {e}")
                    return None
                if error_meta["is_rate_limit"] or error_meta["is_temporary_unavailable"]:
                    if attempt >= max_retries_per_key:
                        return None
                    time.sleep(_compute_retry_delay(error_str, base_delay, attempt))
                    continue
                if key_idx < len(keys) - 1:
                    break
                logger.warning(f"  Gemini Flash Image failed: {e}")
                return None
    return None


def generate_image_with_fallback(
    model,
    prompt,
    generation_config=None,
    max_retries_per_key=3,
    base_delay=20,
):
    """
    Call Gemini API generate_images with exponential backoff on retryable errors.
    """
    keys = config.GEMINI_API_KEYS
    if not keys:
        raise ValueError("No Gemini API keys configured.")

    for key_idx, current_key in enumerate(keys):
        client = genai.Client(api_key=current_key)

        for attempt in range(max_retries_per_key + 1):
            try:
                response = client.models.generate_images(
                    model=model,
                    prompt=prompt,
                    config=generation_config,
                )
                return response
            except Exception as e:
                error_meta = _classify_gemini_error(e)
                error_str = error_meta["error_str"]
                is_retryable = error_meta["is_rate_limit"] or error_meta["is_temporary_unavailable"]

                if not is_retryable:
                    if "404" in error_str or key_idx == len(keys) - 1:
                        raise
                    logger.warning(f"  Error from key {key_idx + 1}: {e}. Trying next key...")
                    break

                if error_meta["is_daily_quota"]:
                    logger.warning(f"  Gemini daily quota exhausted for key {key_idx + 1}/{len(keys)}.")
                    break

                if key_idx < len(keys) - 1:
                    reason = "rate limited" if error_meta["is_rate_limit"] else "temporarily unavailable"
                    logger.warning(f"  Gemini {reason} on key {key_idx + 1}, trying next key immediately...")
                    break

                if attempt >= max_retries_per_key:
                    logger.error(f"  Gemini API exhausted all {max_retries_per_key} retries on the last key.")
                    raise

                delay = _compute_retry_delay(error_str, base_delay, attempt)
                reason = "rate limited" if error_meta["is_rate_limit"] else "temporarily unavailable"
                logger.warning(
                    f"  Gemini {reason} on final key (attempt {attempt + 1}/{max_retries_per_key}). "
                    f"Waiting {delay:.0f}s before retry..."
                )
                time.sleep(delay)

    raise Exception("All Gemini API keys failed or exhausted quota.")
