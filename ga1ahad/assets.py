"""Image keyframes and emblems rendered as half-block character tiles."""

from __future__ import annotations

import functools
import math

import numpy as np

from . import config as C
from .canvas import Sprite
from .glyphs import glyph_table


# --------------------------------------------------------------------------
# Image helpers
# --------------------------------------------------------------------------
def _crop_frac(img, x0: float, y0: float, x1: float, y1: float):
    w, h = img.size
    return img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))


def halfblock(img, rows: int, bg: int = C.INK, alpha_thresh: float = 0.30,
              sat: float = 1.0, contrast: float = 1.0, bright: float = 1.0) -> Sprite:
    """Convert an RGBA PIL image into a half-block character sprite.

    Each cell stores the top pixel as foreground and the bottom pixel as
    background of a ``▀`` character, doubling the effective vertical resolution.
    """
    from PIL import Image, ImageEnhance

    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    rows = max(1, rows)
    cols = max(1, int(round(2 * rows * w / h)))
    px = img.resize((cols, rows * 2), Image.LANCZOS)
    if sat != 1.0:
        px = ImageEnhance.Color(px).enhance(sat)
    if contrast != 1.0:
        px = ImageEnhance.Contrast(px).enhance(contrast)
    if bright != 1.0:
        px = ImageEnhance.Brightness(px).enhance(bright)
    arr = np.asarray(px).astype(np.float32)
    alpha = arr[..., 3:4] / 255.0
    bgc = np.array([(bg >> 16) & 255, (bg >> 8) & 255, bg & 255], dtype=np.float32)
    rgb = arr[..., :3] * alpha + bgc * (1.0 - alpha)
    channels = rgb.astype(np.uint32)
    packed = (channels[..., 0] << 16) | (channels[..., 1] << 8) | channels[..., 2]
    opaque = (alpha[0::2, :, 0] >= alpha_thresh) | (alpha[1::2, :, 0] >= alpha_thresh)
    upper = glyph_table().char_id("▀")
    sp = Sprite(rows, cols)
    sp.ch = np.where(opaque, upper, 0).tolist()
    sp.fg = np.where(opaque, packed[0::2], C.WHITE).tolist()
    sp.bg = np.where(opaque, packed[1::2], bg).tolist()
    return sp


def tint_sprite(sp: Sprite, tint: int, amount: float) -> Sprite:
    out = Sprite(sp.h, sp.w)
    for r in range(sp.h):
        for c in range(sp.w):
            out.ch[r][c] = sp.ch[r][c]
            out.fg[r][c] = C.mix(sp.fg[r][c], tint, amount)
            out.bg[r][c] = C.mix(sp.bg[r][c], tint, amount)
    return out


def recolor_sprite(sp: Sprite, func) -> Sprite:
    out = Sprite(sp.h, sp.w)
    for r in range(sp.h):
        for c in range(sp.w):
            out.ch[r][c] = sp.ch[r][c]
            out.fg[r][c] = func(sp.fg[r][c])
            out.bg[r][c] = func(sp.bg[r][c])
    return out


@functools.lru_cache(maxsize=None)
def keyframe(name: str):
    from PIL import Image

    with Image.open(C.ROOT / "assets" / "keyframes" / f"{name}.webp") as source:
        return source.copy()


def camera_sprite(img, rows: int, cols: int, *, zoom: float = 1.0,
                  center: tuple[float, float] = (0.5, 0.5), **grade) -> Sprite:
    """Sample a moving camera crop directly onto the half-block grid."""
    from PIL import Image

    width, height = img.size
    aspect = cols / (2 * rows)
    crop_w = min(width, height * aspect) / zoom
    crop_h = crop_w / aspect
    x = max(0.0, width - crop_w) * C.clamp(center[0], 0.0, 1.0)
    y = max(0.0, height - crop_h) * C.clamp(center[1], 0.0, 1.0)
    box = (x, y, min(width, x + crop_w), min(height, y + crop_h))
    return halfblock(img.resize((cols, 2 * rows), Image.Resampling.LANCZOS, box),
                     rows, **grade)


def draw_keyframe(c, name: str, y: int, x: int, h: int, w: int, t: float,
                  *, zoom: float = 1.04, center=(0.5, 0.5),
                  bright: float = 1.0, tint: int | None = None,
                  tint_amt: float = 0.0) -> None:
    """Pan within the source image at sub-cell precision, even in an ANSI frame."""
    cx = center[0] + 0.09 * math.sin(t * 1.37)
    cy = center[1] + 0.06 * math.sin(t * 1.72)
    shot = camera_sprite(keyframe(name), h, w, zoom=zoom, center=(cx, cy), bright=bright)
    c.sprite(y, x, shot, tint=tint, tint_amt=tint_amt)


# --------------------------------------------------------------------------
# Emblems / icons
# --------------------------------------------------------------------------
def sunflower_image(size: int = 96, petals: int = 12, petal_color=(240, 140, 75),
                    core_color=(245, 185, 66), dark=False) -> "object":
    from PIL import Image, ImageDraw

    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    pr = S * 0.42
    for i in range(petals):
        a = i * 2 * math.pi / petals
        px, py = cx + math.cos(a) * pr * 0.62, cy + math.sin(a) * pr * 0.62
        rw = S * 0.20
        rh = S * 0.10
        box = [px - rw, py - rh, px + rw, py + rh]
        # rotated ellipse approximated via polygon
        pts = []
        for k in range(16):
            t = 2 * math.pi * k / 16
            ex, ey = rw * math.cos(t), rh * math.sin(t)
            pts.append((px + ex * math.cos(a) - ey * math.sin(a),
                        py + ex * math.sin(a) + ey * math.cos(a)))
        if dark:
            col = (120, 32, 24, 255)
        else:
            col = petal_color + (255,)
        d.polygon(pts, fill=col)
    d.ellipse([cx - S * 0.19, cy - S * 0.19, cx + S * 0.19, cy + S * 0.19],
              fill=(90, 50, 20, 255) if dark else core_color + (255,))
    d.ellipse([cx - S * 0.12, cy - S * 0.12, cx + S * 0.12, cy + S * 0.12],
              fill=(140, 70, 25, 255) if dark else (140, 78, 20, 255))
    return img.resize((size, size), Image.LANCZOS)


def sunburst_image(size: int = 96, rays: int = 24, color=(245, 185, 66)) -> "object":
    from PIL import Image, ImageDraw

    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    for i in range(rays):
        a = i * 2 * math.pi / rays
        length = S * (0.50 if i % 2 == 0 else 0.36)
        width = S * 0.012
        x0, y0 = cx + math.cos(a) * S * 0.12, cy + math.sin(a) * S * 0.12
        x1, y1 = cx + math.cos(a) * length, cy + math.sin(a) * length
        d.line([x0, y0, x1, y1], fill=color + (255,), width=max(1, int(width)))
    return img.resize((size, size), Image.LANCZOS)


# --------------------------------------------------------------------------
# Claude crops
# --------------------------------------------------------------------------
class Assets:
    """Lazily built sprites; all sizes in character rows."""

    def __init__(self) -> None:
        self._cache: dict = {}
        self.glyphs = glyph_table()

    # -- claude -----------------------------------------------------------
    def claude_full(self, rows: int = 48, bg: int = C.INK, dark: bool = False,
                   sat: float = 1.12, contrast: float = 1.04) -> Sprite:
        key = ("claude_full", rows, bg, dark, sat, contrast)
        if key not in self._cache:
            sp = halfblock(keyframe("claude"), rows, bg=bg, sat=sat, contrast=contrast)
            if dark:
                sp = tint_sprite(sp, C.TERRA_DIM, 0.30)
            self._cache[key] = sp
        return self._cache[key]

    def claude_bust(self, rows: int = 24, bg: int = C.INK, dark: bool = False) -> Sprite:
        key = ("claude_bust", rows, bg, dark)
        if key not in self._cache:
            img = _crop_frac(keyframe("claude"), 0.16, 0.0, 0.86, 0.29)
            sp = halfblock(img, rows, bg=bg, sat=1.14, contrast=1.06)
            if dark:
                sp = tint_sprite(sp, C.TERRA_DIM, 0.28)
            self._cache[key] = sp
        return self._cache[key]

    def claude_face(self, rows: int = 12, bg: int = C.INK, dark: bool = False) -> Sprite:
        key = ("claude_face", rows, bg, dark)
        if key not in self._cache:
            img = _crop_frac(keyframe("claude"), 0.20, 0.01, 0.80, 0.175)
            sp = halfblock(img, rows, bg=bg, sat=1.14, contrast=1.08)
            if dark:
                sp = tint_sprite(sp, C.TERRA_DIM, 0.25)
            self._cache[key] = sp
        return self._cache[key]

    def claude_eyes(self, rows: int = 14, bg: int = C.INK) -> Sprite:
        """The illustrated avatar's ocular keyframe for the final verdict."""
        key = ("claude_eyes", rows, bg)
        if key not in self._cache:
            img = _crop_frac(keyframe("claude-eyes"), 0, 0.30, 1, 0.70)
            self._cache[key] = halfblock(img, rows, bg=bg, sat=1.16,
                                         contrast=1.12, bright=0.96)
        return self._cache[key]

    def claude_book(self, rows: int = 14, bg: int = C.INK) -> Sprite:
        key = ("claude_book", rows, bg)
        if key not in self._cache:
            img = _crop_frac(keyframe("claude"), 0.16, 0.10, 0.48, 0.36)
            self._cache[key] = halfblock(img, rows, bg=bg, sat=1.2, contrast=1.05)
        return self._cache[key]

    # -- other characters ------------------------------------------------
    def sam(self, rows: int = 26, bg: int = C.INK) -> Sprite:
        from .portraits import sam_bust
        return sam_bust(rows, bg)

    def dahlia(self, rows: int = 26, bg: int = C.INK, manic: bool = False) -> Sprite:
        from .portraits import dahlia_bust
        return dahlia_bust(rows, bg, manic)

    def dahlia_face(self, rows: int = 10, bg: int = C.INK,
                    manic: bool = False) -> Sprite:
        from .portraits import dahlia_face
        return dahlia_face(rows, bg, manic)

    def gpt4(self, rows: int = 18, bg: int = C.INK) -> Sprite:
        from .portraits import gpt4_entity
        return gpt4_entity(rows, bg)

    # -- icons -----------------------------------------------------------
    def sun(self, rows: int = 6, dark: bool = False) -> Sprite:
        key = ("sun", rows, dark)
        if key not in self._cache:
            size = rows * 20
            img = sunflower_image(size, petals=12, dark=dark)
            self._cache[key] = halfblock(img, rows, bg=C.INK)
        return self._cache[key]

    def sunburst(self, rows: int = 10) -> Sprite:
        key = ("sunburst", rows)
        if key not in self._cache:
            img = sunburst_image(rows * 20, rays=32)
            self._cache[key] = halfblock(img, rows, bg=C.INK)
        return self._cache[key]


@functools.lru_cache(maxsize=1)
def assets() -> Assets:
    return Assets()
