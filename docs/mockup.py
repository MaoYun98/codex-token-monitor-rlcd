#!/usr/bin/env python3
"""Render a deterministic preview of the 400x300 one-bit dashboard."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SCALE = 2
W, H = 400, 300
BG, INK = "white", "black"


def font(size: int, bold: bool = False):
    names = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for name in names:
        if name.exists():
            return ImageFont.truetype(str(name), size * SCALE)
    return ImageFont.load_default()


image = Image.new("1", (W * SCALE, H * SCALE), 1)
draw = ImageDraw.Draw(image)


def xy(value):
    return int(value * SCALE)


def text(x, y, value, size=14, bold=False, anchor="la"):
    draw.text((xy(x), xy(y)), value, font=font(size, bold), fill=0, anchor=anchor)


def line(x0, y0, x1, y1, width=1):
    draw.line((xy(x0), xy(y0), xy(x1), xy(y1)), fill=0, width=width * SCALE)


def bar(x, y, width, percent):
    draw.rounded_rectangle((xy(x), xy(y), xy(x + width), xy(y + 14)),
                           radius=xy(6), outline=0, width=xy(2))
    fill_width = max(0, width * percent / 100)
    if fill_width:
        draw.rounded_rectangle((xy(x), xy(y), xy(x + fill_width), xy(y + 14)),
                               radius=xy(5), fill=0)


def codex_icon(x, y, size=32):
    source = Image.open(ROOT / "assets/codex-logo.png").convert("L")
    mask = Image.new("L", source.size, 0)
    src, dst = source.load(), mask.load()
    cx, cy = source.width / 2, source.height / 2
    radius = min(source.size) * 0.37
    for py in range(source.height):
        for px in range(source.width):
            if (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2:
                dst[px, py] = max(0, min(255, (205 - src[px, py]) * 3))
    mask = mask.crop(mask.getbbox()).resize((xy(size), xy(size)), Image.Resampling.LANCZOS)
    black = Image.new("1", mask.size, 0)
    image.paste(black, (xy(x), xy(y)), mask)


def partly_cloudy(x, y):
    draw.ellipse((xy(x + 2), xy(y), xy(x + 24), xy(y + 22)), outline=0, width=xy(2))
    for angle in range(0, 360, 45):
        import math
        dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        line(x + 13 + dx * 14, y + 11 + dy * 14, x + 13 + dx * 18, y + 11 + dy * 18, 2)
    draw.rounded_rectangle((xy(x + 10), xy(y + 17), xy(x + 42), xy(y + 36)),
                           radius=xy(9), fill=1, outline=0, width=xy(2))


def metric_icon(x, y, kind):
    if kind == "air":
        line(x + 1, y + 5, x + 12, y + 5, 2)
        line(x + 4, y + 10, x + 15, y + 10, 2)
    elif kind == "particles":
        for px, py, radius in ((4, 5, 2), (11, 3, 1), (10, 11, 3), (3, 13, 1)):
            draw.ellipse((xy(x + px - radius), xy(y + py - radius),
                          xy(x + px + radius), xy(y + py + radius)), fill=0)
    elif kind == "rain":
        draw.arc((xy(x + 1), xy(y + 1), xy(x + 15), xy(y + 12)), 180, 360,
                 fill=0, width=xy(2))
        line(x + 8, y + 6, x + 8, y + 14, 2)
    else:
        line(x + 1, y + 4, x + 13, y + 4, 2)
        line(x + 1, y + 8, x + 15, y + 8, 2)
        line(x + 1, y + 12, x + 11, y + 12, 2)


text(10, 2, "16:42", 28, True)
text(108, 5, "THU 07/16", 14)
text(108, 33, "IN 25.4 C  52%RH", 14)
text(390, 10, "BEIJING", 14, False, "ra")
line(10, 63, 390, 63, 2)
line(253, 72, 253, 288, 2)

codex_icon(12, 72)
text(52, 77, "CODEX", 20, True)
text(240, 79, "REMAINING", 14, False, "ra")
text(12, 110, "7d", 14, True)
bar(48, 113, 128, 87)
text(240, 110, "87%", 14, True, "ra")
text(12, 140, "5h", 14, True)
bar(48, 143, 128, 72)
text(240, 140, "72%", 14, True, "ra")
text(12, 169, "5h resets in 2h 14m", 14)
line(12, 195, 240, 195)
text(12, 204, "today", 14)
text(238, 204, "2.8M tok", 14, True, "ra")
text(12, 232, "focus", 14)
text(238, 232, "3h 16m", 14, True, "ra")
text(12, 260, "github", 14)
text(238, 260, "PR 3  CI 1", 14, True, "ra")

text(264, 74, "BEIJING", 20, True)
partly_cloudy(264, 105)
text(348, 104, "32 C", 28, True, "ma")
text(325, 143, "Partly", 14, False, "ma")
line(264, 171, 386, 171)
metric_icon(264, 180, "air")
metric_icon(264, 210, "particles")
metric_icon(264, 240, "rain")
text(288, 181, "AQI 82", 14)
text(288, 211, "PM2.5 28", 14)
text(288, 241, "rain3h 65%", 14)
text(390, 271, "16:42  -58dBm", 12, False, "ra")

image.convert("RGB").save(ROOT / "mockup.png")
print(ROOT / "mockup.png")
