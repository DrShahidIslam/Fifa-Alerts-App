"""
FIFA World Cup 2026 — Pinterest Automation Bot

Automated pipeline that generates and publishes FIFA/football-themed
Pinterest pins using AI content generation and image creation.

This version supports "Site-Linker" mode, which creates pins for real
WordPress articles and pages from fifa-worldcup26.com.
"""

import os
import sys
import json
import time
import re
import base64
import textwrap
import tempfile
import argparse

import requests
from google import genai
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from dotenv import load_dotenv

# Import our custom site linker
import wordpress_linker

# Force UTF-8 encoding for terminal output to handle emojis on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()  # Load .env file if present (local development)

# API Keys
raw_gemini_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS = [k.strip() for k in raw_gemini_keys.split(",") if k.strip()]
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")
PINTEREST_REFRESH_TOKEN = os.getenv("PINTEREST_REFRESH_TOKEN")
PINTEREST_APP_ID = os.getenv("PINTEREST_APP_ID")
PINTEREST_APP_SECRET = os.getenv("PINTEREST_APP_SECRET")

# Board routing: maps each content category to its Pinterest board ID and blog link.
BOARD_MAP = {
    "ultimate_guide": {
        "board_id": os.getenv("PINTEREST_BOARD_ULTIMATE_GUIDE", ""),
        "name": "FIFA World Cup 2026: Ultimate Fan Guide",
        "link": "https://fifa-worldcup26.com/",
    },
    "host_cities": {
        "board_id": os.getenv("PINTEREST_BOARD_HOST_CITIES", ""),
        "name": "WC 2026 Host Cities & Massive Stadiums",
        "link": "https://fifa-worldcup26.com/",
    },
    "qualifiers": {
        "board_id": os.getenv("PINTEREST_BOARD_QUALIFIERS", ""),
        "name": "Qualifiers & National Team Spotlights",
        "link": "https://fifa-worldcup26.com/",
    },
    "history": {
        "board_id": os.getenv("PINTEREST_BOARD_HISTORY", ""),
        "name": "World Cup History, Records & Legends",
        "link": "https://fifa-worldcup26.com/",
    },
    "tactics": {
        "board_id": os.getenv("PINTEREST_BOARD_TACTICS", ""),
        "name": "Football Tactics & Transfer Analysis",
        "link": "https://fifa-worldcup26.com/",
    },
}

# Fallback board
DEFAULT_BOARD_CATEGORY = "ultimate_guide"

# SiliconFlow API config
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/images/generations"
SILICONFLOW_MODEL = "Kwai-Kolors/Kolors"

# Pinterest API base (Sandbox mode for Trial access)
PINTEREST_API_BASE = "https://api-sandbox.pinterest.com/v5"


def validate_env_vars():
    """Ensure all required environment variables are set."""
    required = {
        "GEMINI_API_KEYS": True if GEMINI_API_KEYS else False,
        "SILICONFLOW_API_KEY": SILICONFLOW_API_KEY,
        "PINTEREST_ACCESS_TOKEN": PINTEREST_ACCESS_TOKEN,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"FAILED: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Check that at least one board ID is configured
    boards_configured = [cat for cat, info in BOARD_MAP.items() if info["board_id"]]
    if not boards_configured:
        print("FAILED: No Pinterest board IDs configured! Set at least one PINTEREST_BOARD_* variable.")
        sys.exit(1)

    print("SUCCESS: All required environment variables are set.")


# ============================================================================
# PHASE 1: THE BRAIN — Gemini AI
# ============================================================================

def generate_content_with_gemini(article_context=None) -> dict:
    """
    Use Google Gemini to generate a JSON payload.
    If article_context is provided, generates content tailored to that specific WordPress page.
    """
    print("\nPhase 1: Generating content with Gemini...")

    # Build list of available board categories
    available_categories = [cat for cat, info in BOARD_MAP.items() if info["board_id"]]
    if not available_categories:
        available_categories = list(BOARD_MAP.keys())

    category_descriptions = {
        "ultimate_guide": "Match previews, predictions, tournament guides, beginners guide to WC 2026",
        "host_cities": "Stadium tours, host cities guide, travel info, flights, visas",
        "qualifiers": "Player profiles, qualifiers, and national team spotlights",
        "history": "World Cup history, records, and legends",
        "tactics": "Tactical analysis, coaching, and transfer news",
    }

    categories_prompt = "\n".join(
        f'  - "{cat}": {category_descriptions.get(cat, cat)}'
        for cat in available_categories
    )

    if article_context:
        # ARTICLE MODE PROMPT
        prompt_instruction = f"""Your task is to create a Pinterest pin for this specific page on my website:
Topic: {article_context['topic']}
Summary: {article_context['summary']}
URL: {article_context['url']}

Instructions:
- The title must capture the essence of this specific topic.
- The description should summarize the article and entice users to click the link.
- DO NOT USE EMOJIS.
- Use 10 trending hashtags at the end of the description."""
    else:
        # TRENDING MODE PROMPT
        prompt_instruction = """Your task is to come up with a UNIQUE, engaging viral football/soccer concept for a Pinterest pin.
Reference host cities (NYC, LA, Miami, etc.) or the expanded 48-team format."""

    system_prompt = f"""You are a creative sports social media strategist for FIFA World Cup 2026.
{prompt_instruction}

Return ONLY valid JSON with these exact keys:
{{
  "board_category": "One of the keys below that BEST fits this topic.",
  "title": "Short catchy title (max 100 chars, NO EMOJIS).",
  "description": "SEO description (150-300 chars, NO EMOJIS).",
  "image_prompt": "Highly detailed SiliconFlow prompt (300-400 chars). Cinematic sports photography style."
}}

Available Categories:
{categories_prompt}
"""

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    raw_text = ""
    success = False

    for api_key in GEMINI_API_KEYS:
        client = genai.Client(api_key=api_key)
        for model in models_to_try:
            try:
                response = client.models.generate_content(model=model, contents=system_prompt)
                raw_text = response.text.strip()
                success = True
                break
            except Exception:
                continue
        if success: break

    if not success:
        print("FAILED: Gemini API failed.")
        sys.exit(1)

    # Clean JSON
    raw_text = re.sub(r"```json|```", "", raw_text).strip()
    content = json.loads(raw_text)

    # Validate category
    if content.get("board_category") not in BOARD_MAP:
        content["board_category"] = DEFAULT_BOARD_CATEGORY

    print(f"   Mode: {'Article Linker' if article_context else 'Trending Concept'}")
    print(f"   Topic: {content['title']}")
    return content


# ============================================================================
# PHASE 2 & 3: IMAGE & DESIGN (Unchanged logic)
# ============================================================================

def generate_image_with_siliconflow(image_prompt: str, output_dir: str):
    print("\nPhase 2: Generating image with SiliconFlow...")
    headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": SILICONFLOW_MODEL,
        "prompt": image_prompt + ", masterpiece, cinematic lighting, 8k",
        "image_size": "768x1024",
        "batch_size": 1
    }
    response = requests.post(SILICONFLOW_API_URL, headers=headers, json=payload, timeout=60)
    result = response.json()
    image_url = result["images"][0]["url"]
    
    img_response = requests.get(image_url)
    raw_path = os.path.join(output_dir, "raw_image.png")
    with open(raw_path, "wb") as f:
        f.write(img_response.content)
    return raw_path, image_url

def design_pin_image(raw_image_path: str, title: str, output_dir: str) -> str:
    print("\nPhase 3: Designing final pin image...")
    img = Image.open(raw_image_path).convert("RGBA")
    width, height = img.size
    draw = ImageDraw.Draw(img)
    
    # Simple dark overlay at bottom
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    o_draw = ImageDraw.Draw(overlay)
    o_draw.rectangle([0, height-200, width, height], fill=(0,0,0,180))
    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Use basic font if custom not found (simplified for portability)
    try:
        font = ImageFont.truetype("arial.ttf", 45)
    except:
        font = ImageFont.load_default()

    # Wrap and draw text
    wrapped = textwrap.wrap(title, width=25)
    y = height - 160
    for line in wrapped:
        draw.text((40, y), line, font=font, fill=(255,255,255))
        y += 50
    
    final_path = os.path.join(output_dir, "final_pin.jpg")
    img.save(final_path, "JPEG", quality=90)
    return final_path


# ============================================================================
# PHASE 4: PUBLISHING
# ============================================================================

def publish_to_pinterest(image_path, title, description, board_id, link):
    print("\nPhase 4: Publishing to Pinterest...")
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": description[:500],
        "link": link,
        "media_source": {"source_type": "image_base64", "content_type": "image/jpeg", "data": image_data}
    }
    headers = {"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}", "Content-Type": "application/json"}
    
    # Use API Base defined at top
    r = requests.post(f"{PINTEREST_API_BASE}/pins", headers=headers, json=payload)
    if r.status_code in (200, 201):
        print(f"   SUCCESS: Published Pin ID {r.json().get('id')}")
        return r.json()
    else:
        print(f"   FAILED: {r.status_code} - {r.text}")
        return None

def main():
    parser = argparse.ArgumentParser(description="FIFA 2026 Pinterest Bot")
    parser.add_argument("--mode", choices=["trends", "site"], default="site", help="Bot mode: trends or site")
    args = parser.parse_args()

    print("=" * 60)
    print(f"FIFA World Cup 2026 Pinterest Bot — MODE: {args.mode.upper()}")
    print("=" * 60)

    validate_env_vars()

    article_context = None
    if args.mode == "site":
        article_context = wordpress_linker.get_random_site_article()
        if not article_context:
            print("   Warning: Could not fetch site article. Falling back to Trends mode.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        content = generate_content_with_gemini(article_context)
        
        category = content["board_category"]
        board_info = BOARD_MAP[category]
        
        # Determine the destination URL
        # If in site mode, we link to the specific page. Otherwise, the homepage.
        dest_link = article_context["url"] if article_context else board_info["link"]
        
        raw_img, _ = generate_image_with_siliconflow(content["image_prompt"], tmp_dir)
        final_img = design_pin_image(raw_img, content["title"], tmp_dir)
        
        publish_to_pinterest(
            final_img, 
            content["title"], 
            content["description"], 
            board_info["board_id"], 
            dest_link
        )

    print("\nPipeline Complete!")

if __name__ == "__main__":
    main()
