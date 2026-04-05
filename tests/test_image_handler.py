import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from publisher.image_handler import _has_corner_overlay


class TestCornerOverlayDetection:

    def test_rejects_obvious_corner_overlay(self):
        img = Image.new("RGB", (1200, 630), color=(35, 120, 60))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, 240, 110), fill=(250, 250, 250))
        draw.rectangle((20, 20, 220, 42), fill=(10, 10, 10))
        draw.rectangle((20, 52, 180, 74), fill=(10, 10, 10))
        draw.rectangle((20, 84, 200, 104), fill=(10, 10, 10))
        assert _has_corner_overlay(img) is True

    def test_keeps_clean_editorial_image(self):
        img = Image.new("RGB", (1200, 630), color=(70, 95, 140))
        draw = ImageDraw.Draw(img)
        draw.ellipse((380, 120, 820, 560), fill=(210, 180, 130))
        draw.rectangle((470, 250, 730, 600), fill=(160, 45, 45))
        assert _has_corner_overlay(img) is False
