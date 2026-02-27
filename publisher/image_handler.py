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
from gemini_client import generate_content_with_fallback, generate_image_with_fallback

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
        if isinstance(image_path_or_bytes, Image.Image):
            img = image_path_or_bytes
        elif isinstance(image_path_or_bytes, bytes):
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

def _compress_to_jpg(image_path_or_bytes, output_path, max_size=MAX_FILE_SIZE):
    """
    Compress an image to JPEG format under the target file size.
    Applies resizing to 1200x630 and iteratively reduces quality until under limit.
    """
    try:
        if isinstance(image_path_or_bytes, Image.Image):
            img = image_path_or_bytes
        elif isinstance(image_path_or_bytes, bytes):
            img = Image.open(io.BytesIO(image_path_or_bytes))
        else:
            img = Image.open(image_path_or_bytes)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img = _resize_and_crop(img, TARGET_WIDTH, TARGET_HEIGHT)

        if not output_path.lower().endswith((".jpg", ".jpeg")):
            output_path = os.path.splitext(output_path)[0] + ".jpg"

        quality = 85
        while quality >= 10:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            size = buffer.tell()

            if size <= max_size:
                with open(output_path, "wb") as f:
                    f.write(buffer.getvalue())
                return output_path
            quality -= 5

        img = img.resize((800, 420), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=15, optimize=True)
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())
        return output_path

    except Exception as e:
        logger.error(f"    JPEG compression error: {e}")
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
    Automatically compresses to WebP and JPEG under 100KB.

    Args:
        article_title: The article title for context
        save_dir: Directory to save the image (defaults to project root/images/)

    Returns:
        tuple: (webp_path, jpg_path) or (None, None) if failed
    """
    if save_dir is None:
        save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images")
    os.makedirs(save_dir, exist_ok=True)

    prompt = build_image_prompt(article_title)

    # Build output filenames
    slug = re.sub(r'[^a-z0-9]+', '-', article_title.lower())[:50].strip('-')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path_webp = os.path.join(save_dir, f"{slug}_{timestamp}.webp")
    output_path_jpg = os.path.join(save_dir, f"{slug}_{timestamp}.jpg")

    try:
        logger.info(f"  Generating featured image for: {article_title[:60]}")

        # Use Imagen 4 for image generation
        generation_config = genai.types.GenerateImagesConfig(
            number_of_images=1,
            output_mime_type="image/jpeg",
            aspect_ratio="16:9",
        )

        response = generate_image_with_fallback(
            model="imagen-4.0-fast-generate-001",
            prompt=prompt,
            generation_config=generation_config
        )

        # Extract image from response
        if response.generated_images:
            for generated_image in response.generated_images:
                # Compress to both WebP and JPEG
                result_webp = _compress_to_webp(generated_image.image.image_bytes, output_path_webp)
                result_jpg = _compress_to_jpg(generated_image.image.image_bytes, output_path_jpg)
                
                if result_webp and result_jpg:
                    logger.info(f"    Images ready: {result_webp}, {result_jpg}")
                    return result_webp, result_jpg

        logger.warning("    No image in Gemini response, using fallback")
        return _generate_fallback_image(article_title, output_path_webp, output_path_jpg)

    except Exception as e:
        logger.error(f"    Imagen generation error: {e}")
        return _generate_fallback_image(article_title, output_path_webp, output_path_jpg)


def _generate_fallback_image(article_title, output_path_webp, output_path_jpg):
    """
    Create a beautiful AI fallback image using pollinations.ai when Gemini fails.
    Outputs as compressed WebP and JPEG under 100KB.
    """
    import urllib.request
    import urllib.parse
    import time
    from PIL import Image
    import io

    try:
        logger.info(f"    Fetching fallback from Pollinations: {article_title[:40]}...")
        
        # Build prompt: cinematic football scene related to the article
        prompt = f"Cinematic photography, professional sports journalism, high quality, highly detailed editorial photo for news article about: {article_title}. Realistic, dramatic lighting, 8k resolution, photorealistic"
        safe_prompt = urllib.parse.quote(prompt)
        
        # We append a random seed so it generates different images each time
        seed = int(time.time() * 1000) % 1000000
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={TARGET_WIDTH}&height={TARGET_HEIGHT}&seed={seed}&nologo=true&model=flux"
        
        # Download the image
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            image_bytes = response.read()
            
        result_webp = _compress_to_webp(image_bytes, output_path_webp)
        result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
        return result_webp, result_jpg

    except Exception as e:
        logger.error(f"    Fallback generation error (Pollinations): {e}")
        
        # Absolute final resort: basic solid color with text if EVERYTHING fails
        try:
            from PIL import ImageDraw, ImageFont

            width, height = TARGET_WIDTH, TARGET_HEIGHT
            img = Image.new('RGB', (width, height), color=(20, 50, 30))
            draw = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype("arial.ttf", 42)
            except OSError:
                font = ImageFont.load_default()

            words = article_title.split()
            lines, current_line = [], ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                if len(test_line) > 35:
                    if current_line: lines.append(current_line)
                    current_line = word
                else:
                    current_line = test_line
            if current_line: lines.append(current_line)

            y_pos = height // 2 - len(lines) * 30
            for line in lines[:4]:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                draw.text(((width - text_width) // 2, y_pos), line, fill=(255, 255, 255), font=font)
                y_pos += 55

            result_webp = _compress_to_webp(img, output_path_webp)
            result_jpg = _compress_to_jpg(img, output_path_jpg)
            return result_webp, result_jpg

        except Exception as fallback_e:
            logger.error(f"    Hard fallback error: {fallback_e}")
            return None, None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_title = "Italy Qualifies for World Cup 2026 After Northern Ireland Victory"
    path = generate_featured_image(test_title)
    if path:
        size_kb = os.path.getsize(path) / 1024
        print(f"Image: {path} ({size_kb:.1f}KB)")
    else:
        print("Image generation failed")
