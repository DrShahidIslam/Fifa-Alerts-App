"""
Image Handler — Generates AI featured images via Gemini Imagen
and compresses them to WebP under 100KB for SEO + hosting efficiency.
"""
import logging
import io
import os
import re
from datetime import datetime

from PIL import Image
from google import genai

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from writer.seo_prompt import build_image_prompt

logger = logging.getLogger(__name__)

# Max file size in bytes (100KB)
MAX_FILE_SIZE = 100 * 1024
# Target dimensions (1200x630 is standard OG/featured image)
TARGET_WIDTH = 1200
TARGET_HEIGHT = 630


def _compress_to_webp(image_path_or_bytes, output_path, max_size=MAX_FILE_SIZE):
    """
    Compress an image to WebP format under the target file size.
    Applies resizing to 1200x630 and iteratively reduces quality until under limit.

    Args:
        image_path_or_bytes: Path to source image or raw bytes
        output_path: Where to save the compressed WebP
        max_size: Maximum file size in bytes (default 100KB)

    Returns:
        str: Path to the compressed WebP file, or None if failed
    """
    try:
        # Open the image
        if isinstance(image_path_or_bytes, bytes):
            img = Image.open(io.BytesIO(image_path_or_bytes))
        else:
            img = Image.open(image_path_or_bytes)

        # Convert to RGB if necessary (RGBA/palette modes don't work well with WebP lossy)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize to target dimensions (1200x630) maintaining aspect ratio then cropping
        img = _resize_and_crop(img, TARGET_WIDTH, TARGET_HEIGHT)

        # Ensure output path has .webp extension
        if not output_path.lower().endswith(".webp"):
            output_path = os.path.splitext(output_path)[0] + ".webp"

        # Iteratively compress until under max_size
        quality = 85  # Start at high quality
        while quality >= 10:
            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=quality, method=6)
            size = buffer.tell()

            if size <= max_size:
                # Write to file
                with open(output_path, "wb") as f:
                    f.write(buffer.getvalue())

                final_kb = size / 1024
                logger.info(f"    Compressed to WebP: {final_kb:.1f}KB (quality={quality})")
                return output_path

            # Reduce quality and try again
            quality -= 5

        # Last resort: aggressive resize + minimum quality
        img = img.resize((800, 420), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="WEBP", quality=10, method=6)
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())

        final_kb = buffer.tell() / 1024
        logger.info(f"    Compressed to WebP (aggressive): {final_kb:.1f}KB")
        return output_path

    except Exception as e:
        logger.error(f"    WebP compression error: {e}")
        return None


def _resize_and_crop(img, target_w, target_h):
    """Resize image to fill target dimensions, then center-crop."""
    # Calculate scale to fill
    w_ratio = target_w / img.width
    h_ratio = target_h / img.height
    scale = max(w_ratio, h_ratio)

    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Center crop
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))

    return img


def generate_featured_image(article_title, save_dir=None):
    """
    Generate an AI featured image for an article using Gemini Imagen.
    Automatically compresses to WebP under 100KB.

    Args:
        article_title: The article title for context
        save_dir: Directory to save the image (defaults to project root/images/)

    Returns:
        str: Path to the saved WebP image file, or None if failed
    """
    if save_dir is None:
        save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images")
    os.makedirs(save_dir, exist_ok=True)

    prompt = build_image_prompt(article_title)

    # Build output filename
    slug = re.sub(r'[^a-z0-9]+', '-', article_title.lower())[:50].strip('-')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(save_dir, f"{slug}_{timestamp}.webp")

    try:
        logger.info(f"  Generating featured image for: {article_title[:60]}")
        client = genai.Client(api_key=config.GEMINI_API_KEY)

        # Use Gemini with image generation capability
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        # Extract image from response
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    # Compress to WebP under 100KB
                    result = _compress_to_webp(part.inline_data.data, output_path)
                    if result:
                        final_size = os.path.getsize(result) / 1024
                        logger.info(f"    Image ready: {result} ({final_size:.1f}KB)")
                        return result

        logger.warning("    No image in Gemini response, using fallback")
        return _generate_fallback_image(article_title, output_path)

    except Exception as e:
        logger.error(f"    Imagen generation error: {e}")
        return _generate_fallback_image(article_title, output_path)


def _generate_fallback_image(article_title, output_path):
    """
    Create a simple branded placeholder image when AI generation fails.
    Outputs as compressed WebP under 100KB.
    """
    try:
        from PIL import ImageDraw, ImageFont

        width, height = TARGET_WIDTH, TARGET_HEIGHT
        img = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(img)

        # Dark gradient background (green tones — football/pitch feel)
        for y in range(height):
            r = int(10 + (y / height) * 15)
            g = int(40 + (y / height) * 30)
            b = int(20 + (y / height) * 25)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Add title text
        try:
            font = ImageFont.truetype("arial.ttf", 42)
            small_font = ImageFont.truetype("arial.ttf", 24)
        except OSError:
            font = ImageFont.load_default()
            small_font = font

        # Word wrap title
        words = article_title.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) > 35:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)

        # Draw title centered
        y_pos = height // 2 - len(lines) * 30
        for line in lines[:4]:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x_pos = (width - text_width) // 2
            draw.text((x_pos, y_pos), line, fill=(255, 255, 255), font=font)
            y_pos += 55

        # Add site name
        site_text = "fifa-worldcup26.com"
        bbox = draw.textbbox((0, 0), site_text, font=small_font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, height - 60), site_text, fill=(150, 200, 150), font=small_font)

        # Compress to WebP
        return _compress_to_webp(img, output_path)

    except Exception as e:
        logger.error(f"    Fallback image error: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_title = "Italy Qualifies for World Cup 2026 After Northern Ireland Victory"
    path = generate_featured_image(test_title)
    if path:
        size_kb = os.path.getsize(path) / 1024
        print(f"Image: {path} ({size_kb:.1f}KB)")
    else:
        print("Image generation failed")
