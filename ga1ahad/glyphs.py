"""Glyph atlas: procedural Unicode block/braille/box-drawing masks + TTF masks.

Each character is rasterised into a 10x20 px alpha mask (`CELL_W` x `CELL_H`).
Procedural characters (block elements, braille patterns, box drawing, common
symbols) are generated with exact pixel geometry so that boxes, bars and
braille curves tile seamlessly across the 200x56 character canvas.  Everything
else is rasterised on demand from a monospace TTF (DejaVu Sans Mono, bold
variant for emphasis).
"""

from __future__ import annotations

import functools
import math
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np

from . import config as C

SS = 4  # supersampling factor for procedural shapes


# --------------------------------------------------------------------------
# Font discovery
# --------------------------------------------------------------------------
def _fc_match(family: str) -> str | None:
    exe = shutil.which("fc-match")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-f", "%{file}", family], capture_output=True,
                             text=True, timeout=5).stdout.strip()
    except Exception:
        return None
    if out and os.path.exists(out):
        return out
    return None


@functools.lru_cache(maxsize=8)
def find_font(family: str, bold: bool = False) -> str | None:
    env = os.environ.get("GA1AHAD_FONT")
    if env and os.path.exists(env) and not bold:
        return env
    path = _fc_match(family)
    if path:
        if bold:
            cand = path.replace("-Regular", "-Bold").replace("Regular", "Bold")
            if os.path.exists(cand):
                return cand
            # nixos DejaVu ships DejaVuSansMono-Bold.ttf in the same dir
            parent = Path(path).parent
            stem = Path(path).stem
            for pat in (f"{stem}-Bold.ttf", f"{stem}Bold.ttf",
                        "DejaVuSansMono-Bold.ttf", "NotoSansMono-Bold.ttf"):
                p = parent / pat
                if p.exists():
                    return str(p)
        return path
    for fam in C.FONT_FAMILIES:
        p = _fc_match(fam)
        if p:
            return p
    return None


def primary_font(bold: bool = False) -> str | None:
    for fam in C.FONT_FAMILIES:
        p = find_font(fam, bold=bold)
        if p and (not bold or find_font(fam, bold=True)):
            return find_font(fam, bold=True if bold else False)
    return find_font("DejaVu Sans Mono", bold=bold)


# --------------------------------------------------------------------------
# Low level helpers
# --------------------------------------------------------------------------
def _blank() -> np.ndarray:
    return np.zeros((C.CELL_H, C.CELL_W), dtype=np.uint8)


def _downsample(hi: np.ndarray) -> np.ndarray:
    """(H*SS, W*SS) float/bool -> (H, W) uint8 via box filter."""
    h, w = hi.shape
    block = hi.reshape(h // SS, SS, w // SS, SS)
    if hi.dtype == bool:
        block = block.astype(np.float32)
    mean = block.mean(axis=(1, 3))
    return np.clip(mean, 0, 255).astype(np.uint8)


def _new_hi() -> np.ndarray:
    return np.zeros((C.CELL_H * SS, C.CELL_W * SS), dtype=np.uint8)


def _hi_rect(img: np.ndarray, x0: float, y0: float, x1: float, y1: float,
             value: int = 255) -> None:
    x0i = max(0, int(round(x0 * SS)))
    y0i = max(0, int(round(y0 * SS)))
    x1i = min(img.shape[1], int(round(x1 * SS)))
    y1i = min(img.shape[0], int(round(y1 * SS)))
    if x1i > x0i and y1i > y0i:
        img[y0i:y1i, x0i:x1i] = np.maximum(img[y0i:y1i, x0i:x1i], value)


def _hi_line(img: np.ndarray, x0: float, y0: float, x1: float, y1: float,
             width: float = 2.0, value: int = 255) -> None:
    """Thick line rasterised by distance to segment (supersampled)."""
    h, w = img.shape
    xs = np.arange(w, dtype=np.float32) / SS + 0.5 / SS
    ys = np.arange(h, dtype=np.float32) / SS + 0.5 / SS
    gx, gy = np.meshgrid(xs, ys)
    vx, vy = x1 - x0, y1 - y0
    ll = vx * vx + vy * vy
    if ll <= 1e-9:
        dist = np.hypot(gx - x0, gy - y0)
    else:
        tt = np.clip(((gx - x0) * vx + (gy - y0) * vy) / ll, 0.0, 1.0)
        dist = np.hypot(gx - (x0 + tt * vx), gy - (y0 + tt * vy))
    mask = dist <= (width / 2.0)
    img[mask] = np.maximum(img[mask], value)


def _hi_arc(img: np.ndarray, cx: float, cy: float, r: float,
            a0: float, a1: float, width: float = 2.0, value: int = 255) -> None:
    """Arc from angle a0 to a1 (radians, standard math orientation but y down)."""
    steps = max(6, int(abs(a1 - a0) * r * SS / 1.5))
    prev = None
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        if prev is not None:
            _hi_line(img, prev[0], prev[1], px, py, width, value)
        prev = (px, py)


def _hi_polygon(img: np.ndarray, pts: list[tuple[float, float]], value: int = 255):
    from PIL import Image, ImageDraw
    # PIL works in the supersampled integer grid
    m = Image.fromarray(img, "L")
    d = ImageDraw.Draw(m)
    d.polygon([(x * SS, y * SS) for x, y in pts], fill=value)
    img[:] = np.array(m)


def _hi_ellipse(img: np.ndarray, x0: float, y0: float, x1: float, y1: float,
                fill: bool = True, width: float = 1.0, value: int = 255):
    from PIL import Image, ImageDraw
    m = Image.fromarray(img, "L")
    d = ImageDraw.Draw(m)
    box = [x0 * SS, y0 * SS, x1 * SS, y1 * SS]
    if fill:
        d.ellipse(box, fill=value)
    else:
        d.ellipse(box, fill=0, outline=value, width=max(1, int(round(width * SS))))
    img[:] = np.array(m)


# --------------------------------------------------------------------------
# Procedural characters
# --------------------------------------------------------------------------
def _block_masks(table: dict[str, np.ndarray]) -> None:
    W, H = C.CELL_W, C.CELL_H
    # standard 1/8 partial blocks
    for k, ch in enumerate("\u2581\u2582\u2583\u2584\u2585\u2586\u2587", start=1):
        hh = int(round(H * k / 8.0))
        m = _blank()
        m[H - hh:, :] = 255
        table[ch] = m
    for k, ch in enumerate("\u258f\u258e\u258d\u258c\u258b\u258a\u2589", start=1):
        ww = int(round(W * k / 8.0))
        m = _blank()
        m[:, :ww] = 255
        table[ch] = m
    m = _blank(); m[:, W // 2:] = 255; table["\u2590"] = m            # right half
    m = _blank(); m[:max(1, int(round(H / 8))), :] = 255; table["\u2594"] = m
    m = _blank(); m[:, W - max(1, int(round(W / 8))):] = 255; table["\u2595"] = m
    m = _blank(); m[: H // 2, :] = 255; table["\u2580"] = m           # upper half
    m = _blank(); m[H // 2:, :] = 255; table["\u2584"] = m            # lower half
    m = _blank(); m[:, :] = 255; table["\u2588"] = m                  # full block

    # quadrants
    tl = (0, 0, W // 2, H // 2)
    tr = (W // 2, 0, W, H // 2)
    bl = (0, H // 2, W // 2, H)
    br = (W // 2, H // 2, W, H)
    quads = {
        "\u2596": [bl], "\u2597": [br], "\u2598": [tl], "\u2599": [tl, bl, br],
        "\u259a": [tl, br], "\u259b": [tl, tr, bl], "\u259c": [tl, tr, br],
        "\u259d": [tr], "\u259e": [tr, bl], "\u259f": [tr, br, bl],
    }
    for ch, rects in quads.items():
        m = _blank()
        for x0, y0, x1, y1 in rects:
            m[y0:y1, x0:x1] = 255
        table[ch] = m

    # shade characters: classic 2x2 dither patterns
    yy, xx = np.mgrid[0:H, 0:W]
    light = ((xx % 2 == 0) & (yy % 2 == 0))
    dark = ~((xx % 2 == 1) & (yy % 2 == 1))
    m = _blank(); m[light] = 255; table["\u2591"] = m
    m = _blank(); m[(xx + yy) % 2 == 0] = 255; table["\u2592"] = m
    m = _blank(); m[dark] = 255; table["\u2593"] = m


def _braille_masks(table: dict[str, np.ndarray]) -> None:
    """Procedural braille: 2x4 dot matrix with 4x4 supersampled round dots."""
    # dot positions inside a 10x20 cell (x, y) in cell coordinates
    xs = (2.6, 7.4)
    ys = (2.6, 7.4, 12.6, 17.4)
    r = 1.42
    blank = _blank()
    for code in range(256):
        hi = _new_hi()
        any_dot = False
        for bit in range(8):
            if not (code >> bit) & 1:
                continue
            any_dot = True
            col = bit // 4          # left / right column
            row = bit % 4            # 4 rows
            cx, cy = xs[col], ys[row]
            x0, y0 = (cx - r) * SS, (cy - r) * SS
            x1, y1 = (cx + r) * SS, (cy + r) * SS
            xi0, yi0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
            xi1 = min(hi.shape[1], int(math.ceil(x1)))
            yi1 = min(hi.shape[0], int(math.ceil(y1)))
            yy, xx = np.mgrid[yi0:yi1, xi0:xi1]
            px = (xx + 0.5) / SS
            py = (yy + 0.5) / SS
            inside = (px - cx) ** 2 + (py - cy) ** 2 <= r * r
            hi[yi0:yi1, xi0:xi1][inside] = 255
        table[chr(0x2800 + code)] = _downsample(hi) if any_dot else blank


def _box_masks(table: dict[str, np.ndarray]) -> None:
    """Box drawing glyphs at 2px weight, perfectly aligned to cell edges."""
    W, H = C.CELL_W, C.CELL_H
    cx0, cx1 = 4.0, 6.0       # vertical line spans x in [4,6)
    cy0, cy1 = 9.0, 11.0      # horizontal line spans y in [9,11)

    def single(hl: bool, hr: bool, vu: bool, vd: bool, rounded=()) -> np.ndarray:
        hi = _new_hi()
        if hl:
            _hi_rect(hi, 0, cy0, (cx0 + cx1) / 2, cy1)
        if hr:
            _hi_rect(hi, (cx0 + cx1) / 2, cy0, W, cy1)
        if vu:
            _hi_rect(hi, cx0, 0, cx1, (cy0 + cy1) / 2)
        if vd:
            _hi_rect(hi, cx0, (cy0 + cy1) / 2, cx1, H)
        # rounded corners (top-left / top-right / bottom-left / bottom-right)
        for corner in rounded:
            if corner == "tl":
                _hi_rect(hi, 0, cy0, cx0 + 2.4, cy1) if hl else None
                _hi_rect(hi, cx0, 0, cx1, cy0 + 2.4) if vu else None
                _hi_arc(hi, cx0 + 2.4, cy0 + 2.4, 2.4, math.pi, 1.5 * math.pi, 2.0)
            elif corner == "tr":
                _hi_rect(hi, cx1 - 2.4, cy0, W, cy1) if hr else None
                _hi_rect(hi, cx0, 0, cx1, cy0 + 2.4) if vu else None
                _hi_arc(hi, cx1 - 2.4, cy0 + 2.4, 2.4, 1.5 * math.pi, 2 * math.pi, 2.0)
            elif corner == "bl":
                _hi_rect(hi, 0, cy0, cx0 + 2.4, cy1) if hl else None
                _hi_rect(hi, cx0, cy1 - 2.4, cx1, H) if vd else None
                _hi_arc(hi, cx0 + 2.4, cy1 - 2.4, 2.4, math.pi, 0.5 * math.pi, 2.0)
            elif corner == "br":
                _hi_rect(hi, cx1 - 2.4, cy0, W, cy1) if hr else None
                _hi_rect(hi, cx0, cy1 - 2.4, cx1, H) if vd else None
                _hi_arc(hi, cx1 - 2.4, cy1 - 2.4, 2.4, 0.5 * math.pi, 0.0, 2.0)
        return _downsample(hi)

    chars = {
        "\u2500": single(True, True, False, False),
        "\u2502": single(False, False, True, True),
        "\u250c": single(False, True, False, True),
        "\u2510": single(True, False, False, True),
        "\u2514": single(False, True, True, False),
        "\u2518": single(True, False, True, False),
        "\u251c": single(False, True, True, True),
        "\u2524": single(True, False, True, True),
        "\u252c": single(True, True, False, True),
        "\u2534": single(True, True, True, False),
        "\u253c": single(True, True, True, True),
        "\u256d": single(False, True, False, True, rounded=("tl",)),
        "\u256e": single(True, False, False, True, rounded=("tr",)),
        "\u256f": single(True, False, True, False, rounded=("br",)),
        "\u2570": single(False, True, True, False, rounded=("bl",)),
    }
    # dashed / dotted variants: simple 50% dots on the 2px band
    hy, vy = np.mgrid[0:H, 0:W]
    base = chars["\u2500"].copy()
    dash_h = np.zeros_like(base)
    dash_h[9:11, :] = 255
    dash_h[:, 1:3] = 0
    dash_h[:, 4:6] = 0
    dash_h[:, 7:9] = 0
    chars["\u2504"] = ((dash_h > 128) * 255).astype(np.uint8)
    vdash = np.zeros_like(base)
    vdash[:, 4:6] = 255
    vdash[1:3, :] = 0
    vdash[5:7, :] = 0
    vdash[9:11, :] = 0
    vdash[13:15, :] = 0
    vdash[17:19, :] = 0
    chars["\u2506"] = ((vdash > 128) * 255).astype(np.uint8)
    # heavy 3px
    for ch, (hl, hr, vu, vd) in {
        "\u2501": (True, True, False, False), "\u2503": (False, False, True, True),
        "\u250f": (False, True, False, True), "\u2513": (True, False, False, True),
        "\u2517": (False, True, True, False), "\u251b": (True, False, True, False),
        "\u2523": (False, True, True, True), "\u252b": (True, False, True, True),
        "\u2533": (True, True, False, True), "\u253b": (True, True, True, False),
        "\u254b": (True, True, True, True),
    }.items():
        hi = _new_hi()
        if hl:
            _hi_rect(hi, 0, 8, (cx0 + cx1) / 2 + 0.5, 12)
        if hr:
            _hi_rect(hi, (cx0 + cx1) / 2 - 0.5, 8, W, 12)
        if vu:
            _hi_rect(hi, 3, 0, 7, (cy0 + cy1) / 2 + 0.5)
        if vd:
            _hi_rect(hi, 3, (cy0 + cy1) / 2 - 0.5, 7, H)
        chars[ch] = _downsample(hi)
    # double lines
    def dbl(hl, hr, vu, vd):
        hi = _new_hi()
        if hl:
            _hi_rect(hi, 0, 7.0, cx1, 9.0)
            _hi_rect(hi, 0, 12.0, cx1, 14.0)
        if hr:
            _hi_rect(hi, cx0, 7.0, W, 9.0)
            _hi_rect(hi, cx0, 12.0, W, 14.0)
        if vu:
            _hi_rect(hi, 1.5, 0, 3.5, cy1)
            _hi_rect(hi, 6.5, 0, 8.5, cy1)
        if vd:
            _hi_rect(hi, 1.5, cy0, 3.5, H)
            _hi_rect(hi, 6.5, cy0, 8.5, H)
        return _downsample(hi)
    for ch, args in {
        "\u2550": (True, True, False, False), "\u2551": (False, False, True, True),
        "\u2554": (False, True, False, True), "\u2557": (True, False, False, True),
        "\u255a": (False, True, True, False), "\u255d": (True, False, True, False),
        "\u2560": (False, True, True, True), "\u2563": (True, False, True, True),
        "\u2566": (True, True, False, True), "\u2569": (True, True, True, False),
        "\u256c": (True, True, True, True),
    }.items():
        chars[ch] = dbl(*args)
    table.update(chars)


def _symbol_masks(table: dict[str, np.ndarray]) -> None:
    W, H = C.CELL_W, C.CELL_H
    if W < 8:  # defensive
        return
    cx, cy = W / 2.0, 10.0
    # 5 point star
    hi = _new_hi()
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 5.3 if i % 2 == 0 else 2.2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    _hi_polygon(hi, pts)
    table["\u2605"] = _downsample(hi)                 # ★
    hi = _new_hi()
    _hi_line(hi, pts[0][0], pts[0][1], pts[2][0], pts[2][1], 1.4)
    _hi_line(hi, pts[2][0], pts[2][1], pts[4][0], pts[4][1], 1.4)
    _hi_line(hi, pts[4][0], pts[4][1], pts[6][0], pts[6][1], 1.4)
    _hi_line(hi, pts[6][0], pts[6][1], pts[8][0], pts[8][1], 1.4)
    _hi_line(hi, pts[8][0], pts[8][1], pts[0][0], pts[0][1], 1.4)
    table["\u2606"] = _downsample(hi)                 # ☆

    # circles
    for ch, r, fill in (("\u25cf", 4.2, True), ("\u25cb", 4.2, False),
                        ("\u25c9", 4.6, False), ("\u25ce", 4.8, False)):
        hi = _new_hi()
        _hi_ellipse(hi, cx - r, cy - r, cx + r, cy + r, fill=fill, width=1.7)
        table[ch] = _downsample(hi)
    hi = _new_hi()
    _hi_ellipse(hi, cx - 5.0, cy - 5.0, cx + 5.0, cy + 5.0, fill=False, width=1.2)
    _hi_ellipse(hi, cx - 1.6, cy - 1.6, cx + 1.6, cy + 1.6, fill=True)
    table["\u25c9"] = _downsample(hi)
    hi = _new_hi()
    _hi_ellipse(hi, cx - 4.8, cy - 4.8, cx + 4.8, cy + 4.8, fill=False, width=1.2)
    _hi_ellipse(hi, cx - 2.2, cy - 2.2, cx + 2.2, cy + 2.2, fill=False, width=1.2)
    table["\u25ce"] = _downsample(hi)

    # diamonds
    hi = _new_hi(); _hi_polygon(hi, [(cx, 4.4), (cx + 5, cy), (cx, 15.6), (cx - 5, cy)])
    table["\u25c6"] = _downsample(hi)                 # ◆
    hi = _new_hi()
    pts = [(cx, 4.4), (cx + 5, cy), (cx, 15.6), (cx - 5, cy), (cx, 4.4)]
    for i in range(4):
        _hi_line(hi, *pts[i], *pts[i + 1], 1.5)
    table["\u25c7"] = _downsample(hi)                 # ◇

    # triangles
    hi = _new_hi(); _hi_polygon(hi, [(cx, 4.2), (cx + 5, 15.8), (cx - 5, 15.8)])
    table["\u25b2"] = _downsample(hi)
    hi = _new_hi(); _hi_polygon(hi, [(cx, 15.8), (cx + 5, 4.2), (cx - 5, 4.2)])
    table["\u25bc"] = _downsample(hi)
    hi = _new_hi(); _hi_polygon(hi, [(1.2, cy), (8.8, 4.6), (8.8, 15.4)])
    table["\u25c0"] = _downsample(hi)
    hi = _new_hi(); _hi_polygon(hi, [(8.8, cy), (1.2, 4.6), (1.2, 15.4)])
    table["\u25b6"] = _downsample(hi)
    hi = _new_hi(); _hi_polygon(hi, [(cx, 5.0), (cx + 4.4, 15.0), (cx - 4.4, 15.0)], 200)
    table["\u25b3"] = _downsample(hi)
    hi = _new_hi(); _hi_polygon(hi, [(1.6, cy), (8.4, 5.4), (8.4, 14.6)], 200)
    table["\u25c1"] = _downsample(hi)
    hi = _new_hi(); _hi_polygon(hi, [(8.4, cy), (1.6, 5.4), (1.6, 14.6)], 200)
    table["\u25b7"] = _downsample(hi)
    hi = _new_hi(); _hi_polygon(hi, [(3.2, cy), (7.0, cy - 3.2), (7.0, cy + 3.2)])
    table["\u25b8"] = _downsample(hi)
    hi = _new_hi(); _hi_polygon(hi, [(6.8, cy), (3.0, cy - 3.2), (3.0, cy + 3.2)])
    table["\u25c2"] = _downsample(hi)

    # squares
    hi = _new_hi(); _hi_rect(hi, 1.6, 5.2, 8.4, 14.8); table["\u25a0"] = _downsample(hi)
    hi = _new_hi();
    for (x0, y0, x1, y1) in ((1.6, 5.2, 8.4, 14.8),):
        _hi_rect(hi, x0, y0, x1, y0 + 1.5); _hi_rect(hi, x0, y1 - 1.5, x1, y1)
        _hi_rect(hi, x0, y0, x0 + 1.5, y1); _hi_rect(hi, x1 - 1.5, y0, x1, y1)
    table["\u25a1"] = _downsample(hi)
    hi = _new_hi(); _hi_rect(hi, 2.8, 7.6, 7.2, 12.4); table["\u25aa"] = _downsample(hi)
    hi = _new_hi(); _hi_rect(hi, 2.8, 7.6, 4.3, 12.4); _hi_rect(hi, 5.7, 7.6, 7.2, 12.4)
    _hi_rect(hi, 2.8, 7.6, 7.2, 9.1); _hi_rect(hi, 2.8, 10.9, 7.2, 12.4)
    table["\u25ab"] = _downsample(hi)

    # heart
    hi = _new_hi()
    _hi_ellipse(hi, 0.9, 4.4, 5.2, 9.2, fill=True)
    _hi_ellipse(hi, 4.8, 4.4, 9.1, 9.2, fill=True)
    _hi_polygon(hi, [(0.9, 7.4), (9.1, 7.4), (5.0, 15.2)])
    table["\u2665"] = _downsample(hi)
    # spade / club / diamond card suits
    hi = _new_hi()
    _hi_polygon(hi, [(cx, 3.6), (9.4, 11.2), (0.6, 11.2)])
    _hi_ellipse(hi, 0.0, 7.4, 4.6, 12.6, fill=True)
    _hi_ellipse(hi, 5.4, 7.4, 10.0, 12.6, fill=True)
    _hi_line(hi, cx, 9.0, cx, 15.6, 1.6)
    table["\u2660"] = _downsample(hi)
    hi = _new_hi()
    _hi_ellipse(hi, 1.0, 7.6, 5.4, 12.6, fill=True)
    _hi_ellipse(hi, 4.6, 7.6, 9.0, 12.6, fill=True)
    _hi_ellipse(hi, 2.8, 3.4, 7.2, 8.4, fill=True)
    _hi_line(hi, cx, 10.8, cx, 15.6, 1.6)
    table["\u2663"] = _downsample(hi)
    hi = _new_hi(); _hi_polygon(hi, [(cx, 4.4), (8.8, 10.0), (cx, 15.6), (1.2, 10.0)])
    table["\u2666"] = _downsample(hi)
    hi = _new_hi()
    pts = [(cx, 4.4), (8.8, 10.0), (cx, 15.6), (1.2, 10.0), (cx, 4.4)]
    for i in range(4):
        _hi_line(hi, *pts[i], *pts[i + 1], 1.3)
    table["\u2662"] = _downsample(hi)

    # sunflower / sparkle emblems used by Anthropic + Claude
    hi = _new_hi()
    for i in range(8):
        a = i * math.pi / 4
        px, py = cx + 3.1 * math.cos(a), cy + 4.0 * math.sin(a)
        _hi_ellipse(hi, px - 1.5, py - 1.5, px + 1.5, py + 1.5, fill=True)
    _hi_ellipse(hi, cx - 1.9, cy - 1.9, cx + 1.9, cy + 1.9, fill=True)
    table["\u2747"] = _downsample(hi)                 # ❇
    hi = _new_hi()
    for i in range(5):
        a = -math.pi / 2 + i * 2 * math.pi / 5
        px, py = cx + 2.9 * math.cos(a), cy + 2.9 * math.sin(a)
        _hi_ellipse(hi, px - 2.4, py - 2.4, px + 2.4, py + 2.4, fill=True)
    _hi_ellipse(hi, cx - 2.5, cy - 2.5, cx + 2.5, cy + 2.5, fill=False, width=1.5)
    table["\u273f"] = _downsample(hi)                 # ✿
    hi = _new_hi()                                    # ✦ four point star
    _hi_polygon(hi, [(cx, 3.2), (cx + 1.6, cy - 1.6), (cx + 4.8, cy),
                     (cx + 1.6, cy + 1.6), (cx, 16.8), (cx - 1.6, cy + 1.6),
                     (cx - 4.8, cy), (cx - 1.6, cy - 1.6)])
    table["\u2726"] = _downsample(hi)
    table["\u2727"] = table["\u2726"].copy()

    # check / cross / warning / bolt / skull / infinity
    hi = _new_hi()
    _hi_line(hi, 1.4, 10.6, 4.0, 14.4, 2.0)
    _hi_line(hi, 4.0, 14.4, 8.8, 5.2, 2.0)
    table["\u2713"] = _downsample(hi)
    table["\u2714"] = table["\u2713"].copy()
    hi = _new_hi()
    _hi_line(hi, 2.0, 5.6, 8.0, 14.4, 2.0)
    _hi_line(hi, 8.0, 5.6, 2.0, 14.4, 2.0)
    table["\u2717"] = _downsample(hi)
    table["\u2718"] = table["\u2717"].copy()
    table["\u2715"] = table["\u2717"].copy()
    table["\u2716"] = table["\u2717"].copy()
    hi = _new_hi()
    _hi_polygon(hi, [(cx, 3.2), (9.6, 16.4), (0.4, 16.4)])
    _hi_line(hi, cx, 3.2, 9.6, 16.4, 1.3)
    _hi_line(hi, 9.6, 16.4, 0.4, 16.4, 1.3)
    _hi_line(hi, 0.4, 16.4, cx, 3.2, 1.3)
    _hi_rect(hi, cx - 0.6, 7.0, cx + 0.6, 12.6)
    _hi_rect(hi, cx - 0.6, 13.8, cx + 0.6, 15.0)
    table["\u26a0"] = _downsample(hi)                 # ⚠
    hi = _new_hi()
    _hi_polygon(hi, [(5.6, 3.0), (2.8, 10.6), (4.8, 10.6), (3.0, 17.2),
                     (8.2, 8.4), (6.0, 8.4), (7.6, 3.0)])
    table["\u26a1"] = _downsample(hi)                 # ⚡
    hi = _new_hi()
    _hi_ellipse(hi, 2.2, 3.4, 7.8, 9.0, fill=True)
    _hi_rect(hi, 3.0, 8.6, 7.0, 12.4)
    _hi_rect(hi, 3.6, 12.0, 4.6, 15.4)
    _hi_rect(hi, 5.4, 12.0, 6.4, 15.4)
    _hi_ellipse(hi, 3.4, 5.2, 4.9, 6.7, fill=False, width=1.2)
    _hi_ellipse(hi, 5.1, 5.2, 6.6, 6.7, fill=False, width=1.2)
    table["\u2620"] = _downsample(hi)                 # ☠
    hi = _new_hi()
    _hi_ellipse(hi, 0.4, 6.0, 5.2, 12.6, fill=False, width=1.5)
    _hi_ellipse(hi, 4.8, 6.0, 9.6, 12.6, fill=False, width=1.5)
    table["\u221e"] = _downsample(hi)                 # ∞
    hi = _new_hi()
    _hi_arc(hi, cx, cy, 4.2, -0.4, 1.6 * math.pi, 1.5)
    _hi_polygon(hi, [(cx + 2.2, 4.0), (cx + 5.6, 5.8), (cx + 2.4, 7.6)])
    table["\u27f3"] = _downsample(hi)                 # ⟳
    table["\u21bb"] = table["\u27f3"].copy()
    for ch, (dx, dy) in {"\u2191": (0, -1), "\u2193": (0, 1),
                         "\u2190": (-1, 0), "\u2192": (1, 0)}.items():
        hi = _new_hi()
        _hi_line(hi, cx, 5.0, cx, 15.0, 1.8) if dx == 0 else _hi_line(hi, 2.0, cy, 8.0, cy, 1.8)
        if dx == 0:
            if dy < 0:
                _hi_polygon(hi, [(cx, 3.4), (cx + 3.2, 7.6), (cx - 3.2, 7.6)])
            else:
                _hi_polygon(hi, [(cx, 16.6), (cx + 3.2, 12.4), (cx - 3.2, 12.4)])
        else:
            if dx < 0:
                _hi_polygon(hi, [(1.6, cy), (6.4, cy - 3.4), (6.4, cy + 3.4)])
            else:
                _hi_polygon(hi, [(8.4, cy), (3.6, cy - 3.4), (3.6, cy + 3.4)])
        table[ch] = _downsample(hi)
    # typographic dashes: crisp 2px rules for subtitle typography
    hi = _new_hi(); _hi_rect(hi, 0, 9.6, C.CELL_W, 11.6); table["\u2014"] = _downsample(hi)
    hi = _new_hi(); _hi_rect(hi, 0.8, 9.6, C.CELL_W - 0.8, 11.6); table["\u2013"] = _downsample(hi)
    # small bullets and geometric fillers
    hi = _new_hi(); _hi_ellipse(hi, cx - 1.8, cy - 1.8, cx + 1.8, cy + 1.8, fill=True)
    table["\u2022"] = _downsample(hi)                 # •
    table["\u00b7"] = table["\u2022"].copy()


# --------------------------------------------------------------------------
# Glyph table
# --------------------------------------------------------------------------
class GlyphTable:
    """Maps characters to glyph ids and owns the stacked alpha mask array."""

    def __init__(self) -> None:
        self.chars: list[str] = []
        self._masks: list[np.ndarray] = []
        self._char_id: dict[str, int] = {}
        self._bold_id: dict[str, int] = {}
        self._dirty = True
        self._masks_np: np.ndarray | None = None
        self._font = primary_font(False)
        self._font_bold = primary_font(True) or self._font
        self._fallbacks: list[str | None] = []
        for fam in C.SYMBOL_FALLBACK_FAMILIES:
            self._fallbacks.append(find_font(fam, bold=False))
        self._register_procedural()

    # -- registration ----------------------------------------------------
    def _add(self, ch: str, mask: np.ndarray) -> int:
        gid = len(self.chars)
        self.chars.append(ch)
        self._masks.append(mask)
        self._char_id[ch] = gid
        self._dirty = True
        return gid

    def _register_procedural(self) -> None:
        table: dict[str, np.ndarray] = {}
        _block_masks(table)
        _braille_masks(table)
        _box_masks(table)
        _symbol_masks(table)
        # space first -> gid 0
        self._add(" ", _blank())
        for ch in sorted(table):
            self._add(ch, table[ch])

    # -- lookup ----------------------------------------------------------
    def char_id(self, ch: str, bold: bool = False) -> int:
        d = self._bold_id if bold else self._char_id
        gid = d.get(ch)
        if gid is not None:
            return gid
        mask = self._raster_font(ch, bold)
        gid = self._add(ch, mask)
        d[ch] = gid
        return gid

    def text_ids(self, s: str, bold: bool = False) -> list[int]:
        cache = self._bold_id if bold else self._char_id
        if all(c in cache for c in s):
            return [cache[c] for c in s]
        return [self.char_id(c, bold) for c in s]

    # -- font rasterisation ----------------------------------------------
    def _raster_font(self, ch: str, bold: bool) -> np.ndarray:
        from PIL import Image, ImageDraw, ImageFont

        if not ch.strip() or ch in "\u00a0\u2800":
            return _blank()
        paths = [self._font_bold if bold else self._font, self._font]
        paths += [p for p in self._fallbacks if p]
        seen = set()
        for path in paths:
            if not path or path in seen:
                continue
            seen.add(path)
            try:
                font = ImageFont.truetype(path, 16)
            except Exception:
                continue
            img = Image.new("L", (C.CELL_W, C.CELL_H), 0)
            d = ImageDraw.Draw(img)
            try:
                adv = font.getlength(ch)
            except Exception:
                adv = C.CELL_W
            x = (C.CELL_W - min(adv, C.CELL_W)) / 2.0
            try:
                d.text((x, 15), ch, font=font, fill=255, anchor="ls")
            except Exception:
                try:
                    d.text((x, 4), ch, font=font, fill=255)
                except Exception:
                    continue
            arr = np.array(img)
            if arr.max() > 0:
                return arr
        # unknown glyph -> tofu dot
        m = _blank()
        m[8:12, 4:6] = 200
        return m

    # -- masks -----------------------------------------------------------
    def masks(self) -> np.ndarray:
        if self._masks_np is None or self._dirty:
            self._masks_np = np.stack(self._masks).astype(np.uint8, copy=False)
            self._dirty = False
        return self._masks_np

    @property
    def count(self) -> int:
        return len(self.chars)


@functools.lru_cache(maxsize=1)
def glyph_table() -> GlyphTable:
    return GlyphTable()
