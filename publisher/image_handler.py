"""
Image Handler — Generates AI featured images via Gemini Imagen
and compresses them to WebP under 100KB for SEO + hosting efficiency.
"""
import logging
import io
import os
import re
import random
from datetime import datetime

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat
from google import genai

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from writer.seo_prompt import build_image_prompt
from gemini_client import generate_content_with_fallback, generate_image_with_fallback, generate_image_with_gemini_flash

logger = logging.getLogger(__name__)

# Max file size in bytes (100KB)
MAX_FILE_SIZE = 100 * 1024
# Target dimensions (1200x630 is standard OG/featured image)
TARGET_WIDTH = 1200
TARGET_HEIGHT = 630
_SILICONFLOW_AUTH_CHECKED = False
_SILICONFLOW_AUTH_OK = None


def _trim_edges(img, percent=0.035):
    """Trim a small margin from all sides to reduce corner logos/watermarks."""
    try:
        if percent <= 0:
            return img
        margin_x = int(img.width * percent)
        margin_y = int(img.height * percent)
        if margin_x * 2 >= img.width or margin_y * 2 >= img.height:
            return img
        return img.crop((margin_x, margin_y, img.width - margin_x, img.height - margin_y))
    except Exception:
        return img


def _corner_regions(img, width_ratio=0.22, height_ratio=0.18):
    width = max(1, int(img.width * width_ratio))
    height = max(1, int(img.height * height_ratio))
    return {
        "top_left": (0, 0, width, height),
        "top_right": (img.width - width, 0, img.width, height),
        "bottom_left": (0, img.height - height, width, img.height),
        "bottom_right": (img.width - width, img.height - height, img.width, img.height),
    }


def _inner_region_for_corner(img, corner_name, width_ratio=0.22, height_ratio=0.18, inset_ratio=0.08):
    width = max(1, int(img.width * width_ratio))
    height = max(1, int(img.height * height_ratio))
    inset_x = max(1, int(img.width * inset_ratio))
    inset_y = max(1, int(img.height * inset_ratio))

    if corner_name == "top_left":
        return (inset_x, inset_y, inset_x + width, inset_y + height)
    if corner_name == "top_right":
        return (img.width - inset_x - width, inset_y, img.width - inset_x, inset_y + height)
    if corner_name == "bottom_left":
        return (inset_x, img.height - inset_y - height, inset_x + width, img.height - inset_y)
    return (
        img.width - inset_x - width,
        img.height - inset_y - height,
        img.width - inset_x,
        img.height - inset_y,
    )


def _has_corner_overlay(img):
    """Detect likely broadcaster/logo overlays near corners in source images."""
    try:
        if img.mode != "RGB":
            img = img.convert("RGB")

        gray = ImageOps.grayscale(img)
        for corner_name, box in _corner_regions(img).items():
            patch = gray.crop(box)
            inner_patch = gray.crop(_inner_region_for_corner(img, corner_name))
            patch_stat = ImageStat.Stat(patch)
            inner_stat = ImageStat.Stat(inner_patch)

            mean_diff = abs(patch_stat.mean[0] - inner_stat.mean[0])
            stddev = patch_stat.stddev[0]

            # Find strong edge/detail concentration that often comes from text/logo overlays.
            edges = patch.filter(ImageFilter.FIND_EDGES)
            edge_mean = ImageStat.Stat(edges).mean[0]

            # Count very bright and very dark pixels; overlays often cluster near extremes.
            hist = patch.histogram()
            total_pixels = max(1, patch.width * patch.height)
            bright_ratio = sum(hist[230:256]) / total_pixels
            dark_ratio = sum(hist[0:30]) / total_pixels

            # Compare the corner to a blurred version to surface hard-edged overlays.
            diff = ImageChops.difference(patch, patch.filter(ImageFilter.GaussianBlur(radius=3)))
            diff_mean = ImageStat.Stat(diff).mean[0]

            if (
                mean_diff >= 10
                and edge_mean >= 14
                and diff_mean >= 6
                and stddev >= 15
                and (bright_ratio >= 0.08 or dark_ratio >= 0.12)
            ):
                logger.info(
                    "    Rejected source image due to likely corner overlay in %s "
                    "(mean_diff=%.1f edge_mean=%.1f diff_mean=%.1f bright=%.2f dark=%.2f)",
                    corner_name,
                    mean_diff,
                    edge_mean,
                    diff_mean,
                    bright_ratio,
                    dark_ratio,
                )
                return True
    except Exception as e:
        logger.warning(f"    Corner overlay scan failed: {e}")

    return False


def _check_siliconflow_auth(api_key):
    """Check SiliconFlow auth once per process so logs are more actionable."""
    global _SILICONFLOW_AUTH_CHECKED, _SILICONFLOW_AUTH_OK

    if _SILICONFLOW_AUTH_CHECKED:
        return bool(_SILICONFLOW_AUTH_OK)

    _SILICONFLOW_AUTH_CHECKED = True
    _SILICONFLOW_AUTH_OK = False

    if not api_key:
        logger.info("    SiliconFlow skipped: API key missing")
        return False

    try:
        import requests

        response = requests.get(
            getattr(config, "SILICONFLOW_USER_INFO_URL", "https://api.siliconflow.cn/v1/user/info"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
        if response.status_code == 200:
            _SILICONFLOW_AUTH_OK = True
            logger.info("    SiliconFlow auth OK")
            return True
        if response.status_code == 401:
            logger.warning("    SiliconFlow skipped: API key invalid (401)")
            return False
        logger.warning(f"    SiliconFlow auth check returned HTTP {response.status_code}")
        return False
    except Exception as e:
        logger.warning(f"    SiliconFlow auth check failed: {e}")
        return False


def _compress_to_webp(image_path_or_bytes, output_path, max_size=MAX_FILE_SIZE, trim_edges=False):
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

        if trim_edges:
            img = _trim_edges(img)

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

def _compress_to_jpg(image_path_or_bytes, output_path, max_size=MAX_FILE_SIZE, trim_edges=False):
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

        if trim_edges:
            img = _trim_edges(img)
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


def _try_gemini_flash_image(article_title, output_path_webp, output_path_jpg):
    """Try Gemini 2.x Flash Image (free tier). Returns (webp, jpg) or (None, None)."""
    try:
        prompt = build_image_prompt(article_title)
        response = generate_image_with_gemini_flash(prompt)
        if not response or not getattr(response, "candidates", None):
            return None, None
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                image_bytes = part.inline_data.data
                if isinstance(image_bytes, bytes) and len(image_bytes) > 100:
                    result_webp = _compress_to_webp(image_bytes, output_path_webp)
                    result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
                    if result_webp and result_jpg:
                        logger.info(f"    Images ready from Gemini Flash Image: {result_webp}, {result_jpg}")
                        return result_webp, result_jpg
                break
    except Exception as e:
        logger.warning(f"    Gemini Flash Image failed: {e}")
    return None, None


def _try_huggingface_image(article_title, output_path_webp, output_path_jpg):
    """Try Hugging Face Inference API (Serverless). Returns (webp, jpg) or (None, None)."""
    if not getattr(config, "USE_HUGGING_FACE_IMAGE", True):
        return None, None

    token = getattr(config, "HUGGING_FACE_TOKEN", "")
    if not token:
        return None, None

    import requests
    try:
        model_id = getattr(config, "HUGGING_FACE_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
        # Use the router endpoint which is more reliable for serverless providers
        url = f"{getattr(config, 'HUGGING_FACE_API_URL', 'https://router.huggingface.co/hf-inference/models')}/{model_id}"
        
        prompt = build_image_prompt(article_title)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"inputs": prompt}

        logger.info(f"    Trying Hugging Face ({model_id}): {article_title[:40]}...")
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        
        if response.status_code == 503:
            logger.info("    HF Model loading (503), retrying in 10s...")
            import time
            time.sleep(10)
            response = requests.post(url, headers=headers, json=payload, timeout=90)

        response.raise_for_status()
        image_bytes = response.content
        
        if "image" not in response.headers.get("Content-Type", "").lower() or len(image_bytes) < 3000:
            logger.warning(f"    HF response not an image: {response.status_code} {response.headers.get('Content-Type')}")
            return None, None

        result_webp = _compress_to_webp(image_bytes, output_path_webp)
        result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
        if result_webp and result_jpg:
            logger.info(f"    Images ready from Hugging Face: {result_webp}, {result_jpg}")
            return result_webp, result_jpg
    except Exception as e:
        logger.warning(f"    Hugging Face failed: {e}")
    return None, None


def _try_together_image(article_title, output_path_webp, output_path_jpg):
    """Try Together AI image generation. Returns (webp, jpg) or (None, None)."""
    if not getattr(config, "USE_TOGETHER_IMAGE", True):
        return None, None

    api_key = getattr(config, "TOGETHER_API_KEY", "")
    if not api_key:
        return None, None

    import requests
    try:
        url = getattr(config, "TOGETHER_API_URL", "https://api.together.xyz/v1/images/generations")
        model = getattr(config, "TOGETHER_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
        
        prompt = build_image_prompt(article_title)
        payload = {
            "model": model,
            "prompt": prompt,
            "width": 1024,
            "height": 768,
            "steps": 4,
            "n": 1,
            "response_format": "b64_json"
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        logger.info(f"    Trying Together AI ({model}): {article_title[:40]}...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        import base64
        data = response.json()
        b64_data = data.get("data", [{}])[0].get("b64_json")
        if not b64_data:
            return None, None
            
        image_bytes = base64.b64decode(b64_data)
        result_webp = _compress_to_webp(image_bytes, output_path_webp)
        result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
        if result_webp and result_jpg:
            logger.info(f"    Images ready from Together AI: {result_webp}, {result_jpg}")
            return result_webp, result_jpg
    except Exception as e:
        logger.warning(f"    Together AI failed: {e}")
    return None, None


def _try_source_image(source_url, output_path_webp, output_path_jpg):
    """Try to use the featured image from the source article (og:image or first large img). Returns (webp, jpg) or (None, None)."""
    if not source_url or not source_url.startswith("http") or "trends.google" in source_url:
        return None, None
    try:
        import requests
        from urllib.parse import urljoin
        headers = {"User-Agent": "Mozilla/5.0 (compatible; FIFANewsAgent/1.0; +https://github.com/DrShahidIslam/Fifa-Alerts-App)"}
        r = requests.get(source_url, headers=headers, timeout=12)
        r.raise_for_status()
        html = r.text
        image_url = None
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            image_url = m.group(1).strip()
        if not image_url:
            m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
            if m:
                image_url = m.group(1).strip()
        if not image_url:
            for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', html, re.I):
                src = m.group(1).strip()
                if "logo" in src.lower() or "avatar" in src.lower() or "icon" in src.lower():
                    continue
                image_url = src
                break
        if not image_url:
            return None, None
        image_url = urljoin(source_url, image_url)
        lowered_image_url = image_url.lower()
        lowered_source_url = source_url.lower()
        blocked_tokens = (
            "logo", "logos", "branding", "brand", "watermark", "bbc", "guardian", "icon", "avatar", "sky", "espn"
        )
        if any(token in lowered_image_url or token in lowered_source_url for token in blocked_tokens):
            logger.info(f"    Skipping likely branded source image: {image_url}")
            return None, None
        img_r = requests.get(image_url, headers=headers, timeout=12)
        img_r.raise_for_status()
        image_bytes = img_r.content
        if len(image_bytes) < 3000:
            return None, None
        img = Image.open(io.BytesIO(image_bytes))
        if _has_corner_overlay(img):
            return None, None
        result_webp = _compress_to_webp(image_bytes, output_path_webp, trim_edges=True)
        result_jpg = _compress_to_jpg(image_bytes, output_path_jpg, trim_edges=True)
        if result_webp and result_jpg:
            logger.info(f"    Image from source article: {result_webp}, {result_jpg}")
            return result_webp, result_jpg
    except Exception as e:
        logger.warning(f"    Source image failed: {e}")
    return None, None


def _try_siliconflow_image(article_title, output_path_webp, output_path_jpg):
    """Try SiliconFlow image generation using the same API shape as the working Pinterest app."""
    if not getattr(config, "USE_SILICONFLOW_IMAGE", True):
        logger.info("    SiliconFlow skipped: disabled by config")
        return None, None

    api_key = getattr(config, "SILICONFLOW_API_KEY", "")
    if not _check_siliconflow_auth(api_key):
        return None, None

    try:
        import requests

        prompt = build_image_prompt(article_title)
        payload = {
            "model": getattr(config, "SILICONFLOW_IMAGE_MODEL", "Kwai-Kolors/Kolors"),
            "prompt": (
                f"{prompt}, highly detailed, masterpiece, best quality, "
                "professional sports journalism, photorealistic"
            ),
            "negative_prompt": getattr(config, "SILICONFLOW_NEGATIVE_PROMPT", ""),
            "image_size": "1024x576",
            "batch_size": 1,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            getattr(config, "SILICONFLOW_API_URL", "https://api.siliconflow.cn/v1/images/generations"),
            headers=headers,
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json() or {}
        images = data.get("images") or []
        image_url = (images[0] or {}).get("url") if images else ""
        if not image_url:
            return None, None

        image_response = requests.get(
            image_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FIFANewsAgent/1.0)"},
            timeout=60,
        )
        image_response.raise_for_status()
        image_bytes = image_response.content
        if len(image_bytes) < 3000:
            return None, None
        result_webp = _compress_to_webp(image_bytes, output_path_webp)
        result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
        if result_webp and result_jpg:
            logger.info(f"    Images ready from SiliconFlow: {result_webp}, {result_jpg}")
            return result_webp, result_jpg
    except Exception as e:
        logger.warning(f"    SiliconFlow image generation failed: {e}")
    return None, None


def _try_pollinations_image(article_title, output_path_webp, output_path_jpg):
    """Try to generate image via free Pollinations.ai. Returns (webp, jpg) or (None, None)."""
    import urllib.request
    import urllib.parse
    import time
    try:
        logger.info(f"    Trying Pollinations FLUX (free): {article_title[:40]}...")
        # Use more descriptive seasoning for Pollinations FLUX
        prompt = (
            f"A professional sports photograph of {article_title}. "
            f"Cinematic lighting, high quality, highly detailed editorial photo, "
            f"realistic, dramatic atmosphere, 8k resolution, photorealistic"
        )
        safe_prompt = urllib.parse.quote(prompt)
        seed = int(time.time() * 1000) % 1000000
        # Explicitly use flux model which is current best on pollinations
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={TARGET_WIDTH}&height={TARGET_HEIGHT}&seed={seed}&nologo=true&model=flux"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FIFANewsAgent/1.0)"})
        with urllib.request.urlopen(req, timeout=60) as response:
            image_bytes = response.read()
            
        if not image_bytes or len(image_bytes) < 3000:
            return None, None

        result_webp = _compress_to_webp(image_bytes, output_path_webp)
        result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
        if result_webp and result_jpg:
            logger.info(f"    Images ready from Pollinations: {result_webp}, {result_jpg}")
            return result_webp, result_jpg
    except Exception as e:
        logger.warning(f"    Pollinations failed: {e}")
    return None, None


def _generate_placeholder_image(article_title, output_path_webp, output_path_jpg):
    """Generate a simple placeholder image (solid color + title text)."""
    from PIL import ImageDraw, ImageFont
    try:
        width, height = TARGET_WIDTH, TARGET_HEIGHT
        img = Image.new("RGB", (width, height), color=(20, 50, 30))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", 42)
            except OSError:
                font = ImageFont.load_default()
        words = article_title.split()
        lines, current_line = [], ""
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
        y_pos = height // 2 - len(lines) * 30
        for line in lines[:4]:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, y_pos), line, fill=(255, 255, 255), font=font)
            y_pos += 55
        result_webp = _compress_to_webp(img, output_path_webp)
        result_jpg = _compress_to_jpg(img, output_path_jpg)
        return result_webp, result_jpg
    except Exception as e:
        logger.error(f"    Placeholder image error: {e}")
        return None, None


def generate_inline_image(article_title, save_dir=None):
    """
    Generate a secondary inline image using multiple possible sources.
    Returns the WebP and JPG paths.
    """
    if save_dir is None:
        save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images")
    os.makedirs(save_dir, exist_ok=True)

    slug = re.sub(r"[^a-z0-9]+", "-", article_title.lower())[:30].strip("-")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path_webp = os.path.join(save_dir, f"inline_{slug}_{timestamp}.webp")
    output_path_jpg = os.path.join(save_dir, f"inline_{slug}_{timestamp}.jpg")

    logger.info(f"  Generating inline image for: {article_title[:60]}")
    
    # 1. Hugging Face
    webp, jpg = _try_huggingface_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg: return webp, jpg
    
    # 2. Together AI
    webp, jpg = _try_together_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg: return webp, jpg
    
    # 3. SiliconFlow (Legacy/Credits)
    webp, jpg = _try_siliconflow_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg: return webp, jpg
    
    # 4. Pollinations (Reliable fallback)
    return _try_pollinations_image(article_title, output_path_webp, output_path_jpg)


def generate_featured_image(article_title, save_dir=None, source_url=None):
    """
    Generate a featured image using a hierarchy of AI sources and source imagery.
    Optimized for cost/free-tier reliability with high aesthetic standards.
    """
    if save_dir is None:
        save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images")
    os.makedirs(save_dir, exist_ok=True)

    slug = re.sub(r"[^a-z0-9]+", "-", article_title.lower())[:50].strip("-")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path_webp = os.path.join(save_dir, f"{slug}_{timestamp}.webp")
    output_path_jpg = os.path.join(save_dir, f"{slug}_{timestamp}.jpg")

    logger.info(f"  Generating featured image hierarchy for: {article_title[:60]}")

    # 1. Gemini 2.x Flash Image (If configured/working)
    webp, jpg = _try_gemini_flash_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg: return webp, jpg

    # 2. Hugging Face Router (FLUX.1-schnell) - High Quality Primary
    webp, jpg = _try_huggingface_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg: return webp, jpg

    # 3. Together AI (FLUX.1-schnell) - Secondary High Quality
    webp, jpg = _try_together_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg: return webp, jpg

    # 4. SiliconFlow (Kwai-Kolors/FLUX) - Legacy/Conditional
    webp, jpg = _try_siliconflow_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg: return webp, jpg

    # 5. Source Article Photography (Filtered for branding/logos)
    allow_source_images = getattr(config, "ALLOW_SOURCE_ARTICLE_IMAGES", False)
    fallback_to_source = getattr(config, "SOURCE_IMAGE_FALLBACK_ON_AI_FAILURE", False)
    if source_url and (allow_source_images or fallback_to_source):
        webp, jpg = _try_source_image(source_url, output_path_webp, output_path_jpg)
        if webp and jpg: return webp, jpg

    # 6. Pollinations FLUX (Reliable, unlimited free fallback)
    webp, jpg = _try_pollinations_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg: return webp, jpg

    # 7. Paid tier only: Gemini Imagen
    if getattr(config, "USE_GEMINI_IMAGEN", False):
        try:
            prompt = build_image_prompt(article_title)
            generation_config = genai.types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="16:9",
            )
            response = generate_image_with_fallback(
                model="imagen-4.0-fast-generate-001",
                prompt=prompt,
                generation_config=generation_config,
            )
            if response.generated_images:
                for generated_image in response.generated_images:
                    result_webp = _compress_to_webp(generated_image.image.image_bytes, output_path_webp)
                    result_jpg = _compress_to_jpg(generated_image.image.image_bytes, output_path_jpg)
                    if result_webp and result_jpg:
                        logger.info(f"    Images ready from Imagen: {result_webp}, {result_jpg}")
                        return result_webp, result_jpg
        except Exception as e:
            logger.warning(f"    Imagen failed: {e}")

    # 8. Placeholder (Title card)
    logger.info("    Falling back to placeholder title card")
    return _generate_placeholder_image(article_title, output_path_webp, output_path_jpg)


def _generate_fallback_image(article_title, output_path_webp, output_path_jpg):
    """Legacy fallback: try Pollinations then placeholder. Prefer generate_featured_image() which tries Pollinations first."""
    webp, jpg = _try_pollinations_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg:
        return webp, jpg
    return _generate_placeholder_image(article_title, output_path_webp, output_path_jpg)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_title = "Italy Qualifies for World Cup 2026 After Northern Ireland Victory"
    webp_path, jpg_path = generate_featured_image(test_title)
    if webp_path and jpg_path:
        size_kb = os.path.getsize(webp_path) / 1024
        print(f"Image: {webp_path} ({size_kb:.1f}KB)")
    else:
        print("Image generation failed")
