#!/usr/bin/env python3
"""Generate LVGL v9 A8 descriptors for the six weather icons."""
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT_C = ROOT / "firmware/components/ui_app/icons.c"
OUT_H = ROOT / "firmware/components/ui_app/icons.h"


def weather_alpha(kind: str, size: int) -> Image.Image:
    scale = 4
    image = Image.new("L", (size * scale, size * scale), 0)
    draw = ImageDraw.Draw(image)
    center = size * scale / 2
    width = 2 * scale

    def ellipse(box, fill=None):
        draw.ellipse(box, outline=255, width=width, fill=fill)

    def line(points):
        draw.line(points, fill=255, width=width)

    sun = size * scale * 0.30
    if kind in ("clear", "partly"):
        sx, sy = ((center - size * scale * 0.16, center - size * scale * 0.13)
                  if kind == "partly" else (center, center))
        ellipse((sx - sun, sy - sun, sx + sun, sy + sun))
        if kind == "clear":
            for angle in range(0, 360, 45):
                dx = math.cos(math.radians(angle))
                dy = math.sin(math.radians(angle))
                line((sx + dx * (sun + 3 * scale), sy + dy * (sun + 3 * scale),
                      sx + dx * (sun + 8 * scale), sy + dy * (sun + 8 * scale)))

    if kind in ("partly", "cloud", "rain", "snow", "fog"):
        ox, oy = ((center + size * scale * 0.13, center + size * scale * 0.13)
                  if kind == "partly" else (center, center))
        radius = size * scale * 0.22
        ellipse((ox - radius * 1.6, oy - radius * 0.2, ox + radius * 0.2, oy + radius * 1.4))
        ellipse((ox - radius * 0.6, oy - radius * 1.2, ox + radius * 1.4, oy + radius * 0.9))
        ellipse((ox + radius * 0.4, oy - radius * 0.1, ox + radius * 2.0, oy + radius * 1.4))
        draw.rectangle((ox - radius * 1.6, oy + radius * 0.6,
                        ox + radius * 2.0, oy + radius * 1.4), fill=255)
        draw.rectangle((ox - radius * 1.3, oy + radius * 0.7,
                        ox + radius * 1.8, oy + radius * 1.25), fill=0)
        if kind == "rain":
            for index in range(3):
                line((ox - radius + index * radius, oy + radius * 1.6,
                      ox - radius - 3 * scale + index * radius, oy + radius * 2.5))
        elif kind == "snow":
            for index in range(3):
                sx = ox - radius + index * radius
                sy = oy + radius * 2.0
                line((sx - 2 * scale, sy, sx + 2 * scale, sy))
                line((sx, sy - 2 * scale, sx, sy + 2 * scale))
        elif kind == "fog":
            line((ox - radius * 1.4, oy + radius * 1.8,
                  ox + radius * 1.5, oy + radius * 1.8))
            line((ox - radius, oy + radius * 2.3,
                  ox + radius * 1.8, oy + radius * 2.3))
    return image.resize((size, size), Image.Resampling.LANCZOS)


def codex_alpha(size: int) -> Image.Image:
    """Extract the central knot from the official Codex-page app icon."""
    source = Image.open(ROOT / "docs/assets/codex-logo.png").convert("L")
    width, height = source.size
    pixels = Image.new("L", source.size, 0)
    source_pixels = source.load()
    out = pixels.load()
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.37
    for y in range(height):
        for x in range(width):
            if (x - cx) ** 2 + (y - cy) ** 2 > radius ** 2:
                continue
            # Preserve dark knot strokes; discard the pale tile and shadow.
            out[x, y] = max(0, min(255, (205 - source_pixels[x, y]) * 3))
    box = pixels.getbbox()
    if box:
        pixels = pixels.crop(box)
    pixels.thumbnail((size, size), Image.Resampling.LANCZOS)
    result = Image.new("L", (size, size), 0)
    result.paste(pixels, ((size - pixels.width) // 2, (size - pixels.height) // 2))
    return result


def metric_alpha(kind: str, size: int = 16) -> Image.Image:
    scale = 4
    image = Image.new("L", (size * scale, size * scale), 0)
    draw = ImageDraw.Draw(image)
    w = 2 * scale
    if kind == "feels":
        draw.rounded_rectangle((6 * scale, 1 * scale, 10 * scale, 12 * scale),
                               radius=2 * scale, outline=255, width=w)
        draw.ellipse((4 * scale, 9 * scale, 12 * scale, 16 * scale), fill=255)
        draw.line((8 * scale, 4 * scale, 8 * scale, 12 * scale), fill=255, width=w)
    elif kind == "humidity":
        draw.polygon(((8 * scale, 0), (2 * scale, 9 * scale),
                      (3 * scale, 14 * scale), (8 * scale, 16 * scale),
                      (13 * scale, 14 * scale), (14 * scale, 9 * scale)), fill=255)
        draw.ellipse((5 * scale, 8 * scale, 12 * scale, 14 * scale), fill=0)
    elif kind == "wind":
        for y, end in ((4, 12), (8, 15), (12, 11)):
            draw.line((1 * scale, y * scale, end * scale, y * scale), fill=255, width=w)
        draw.arc((9 * scale, 1 * scale, 15 * scale, 7 * scale), 260, 95, fill=255, width=w)
        draw.arc((11 * scale, 6 * scale, 17 * scale, 12 * scale), 260, 95, fill=255, width=w)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def emit(name: str, image: Image.Image) -> str:
    width, height = image.size
    values = ",".join(str(byte) for byte in image.tobytes())
    return (
        f"static const uint8_t {name}_map[] = {{{values}}};\n"
        f"const lv_image_dsc_t icon_{name} = {{\n"
        "  .header = { .magic = LV_IMAGE_HEADER_MAGIC, .cf = LV_COLOR_FORMAT_A8,\n"
        f"               .flags = 0, .w = {width}, .h = {height}, .stride = {width} }},\n"
        f"  .data_size = {width * height}, .data = {name}_map,\n}};\n"
    )


icons = {"codex": codex_alpha(32)}
icons.update({f"wx_{kind}": weather_alpha(kind, 26)
              for kind in ("clear", "partly", "cloud", "rain", "snow", "fog")})
icons.update({f"wx_large_{kind}": weather_alpha(kind, 42)
              for kind in ("clear", "partly", "cloud", "rain", "snow", "fog")})
icons.update({f"metric_{kind}": metric_alpha(kind)
              for kind in ("feels", "humidity", "wind")})
OUT_C.write_text('#include "icons.h"\n\n' +
                 "\n".join(emit(name, image) for name, image in icons.items()), encoding="utf-8")
OUT_H.write_text("#pragma once\n#include \"lvgl.h\"\n\n" +
                 "".join(f"extern const lv_image_dsc_t icon_{name};\n" for name in icons), encoding="utf-8")
print(f"generated {len(icons)} dashboard icons")
