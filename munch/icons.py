"""Loads bundled SVG icons (Tabler Icons, MIT licensed — see
assets/icons/NOTICE.md) and rasterizes them to the exact color/size
needed.

Tkinter can't render SVG natively. resvg_py is used instead of the more
common cairosvg because cairosvg needs a system Cairo install that isn't
present on a bare Windows machine; resvg_py ships its rasterizer as a
self-contained compiled wheel, no native library setup required.
"""

import io
import os

import resvg_py
from PIL import Image

_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons")

_cache = {}


def load_icon(name, color, size):
    """Returns a PIL Image (RGBA). Results are cached per (name, color,
    size) — icons are redrawn at a handful of fixed sizes/colors, not
    arbitrary ones, so this avoids re-rasterizing on every call."""
    key = (name, color, size)
    if key in _cache:
        return _cache[key]

    path = os.path.join(_ICONS_DIR, f"{name}.svg")
    with open(path, "r", encoding="utf-8") as f:
        svg = f.read().replace("currentColor", color)

    png_bytes = resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size)
    image = Image.open(io.BytesIO(bytes(png_bytes))).convert("RGBA")
    _cache[key] = image
    return image
