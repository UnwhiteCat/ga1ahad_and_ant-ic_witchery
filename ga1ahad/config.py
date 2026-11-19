"""Global constants, palette and path helpers for the Ga1ahad TUI video.

The whole renderer is a pure function of time: every frame is produced from
``t`` seconds, which makes offline rendering resumable, parallel and exactly
reproducible.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Canvas geometry (the hard spec)
# --------------------------------------------------------------------------
W = 200                      # TUI columns
H = 56                       # TUI rows
CELL_W = 10                  # px per character cell (internal raster)
CELL_H = 20                  # px per character cell (internal raster)
PIX_W = W * CELL_W           # 2000 px internal render width
PIX_H = H * CELL_H           # 1120 px internal render height

OUT_W = 1920                 # final video width  (16:9)
OUT_H = 1080                 # final video height (16:9)
FPS = 30
DURATION = 219.1499375       # exact length of ga1ahad_audio.wav (7_012_798 / 32_000)
DURATION_DISPLAY = "03:39.150"
N_FRAMES = int(round(DURATION * FPS))       # full frames; audio tail runs to the exact end

# --------------------------------------------------------------------------
# Output CRT stage (MP4 render path; see crt.py)
# --------------------------------------------------------------------------
CRT_STRENGTH = 1.0           # default strength; 0 disables (CLI/env override)

# Chrome layout: scene content lives between the top status bar and the
# persistent lyric bar.
TOP_ROWS = 2                 # rows 0..1
BOTTOM_ROWS = 3              # rows 53..55
CONTENT_Y0 = TOP_ROWS        # 2
CONTENT_Y1 = H - BOTTOM_ROWS # 53 (exclusive)
CONTENT_H = CONTENT_Y1 - CONTENT_Y0  # 51

# --------------------------------------------------------------------------
# LLM dialog window: portrait 9:16, margins left/top/bottom = 1
# --------------------------------------------------------------------------
# Every human <-> LLM conversation lives in ONE portrait window.  The 51 usable
# content rows (2..52) minus margin-top 1 and margin-bottom 1 leave 49 rows, so
# the window is 49 rows (rows 3..51, row 2 and row 52 stay empty) and starts at
# column 1 (column 0 stays empty).  In the 10x20 px cell grid the nearest
# integer 9:16 is 55x49 cells = 550x980 px (8*55 = 440 vs 9*49 = 441, within
# one cell of the exact 9:16 relation 8*w == 9*h; 0.2% in pixels -- invisible
# next to the frame's own 0.4% squeeze).  Chrome rows 0..1 / 53..55 stay
# frame-owned, so the margins are measured inside the content band.
DLG_W = 55                     # portrait conversation window, cells (550 px)
DLG_H = 49                     # rows (980 px) -> 9:16 within one cell
DLG_X = 1                      # margin-left, cells (column 0 stays empty)
DLG_TOP = 3                    # margin-top: content row 2 stays empty
DLG_BOTTOM = 1                 # margin-bottom: content row 52 stays empty
DLG_LANE_W = 64                # left band reserved for the dialog + its gutter
DLG_SLOTS = ((DLG_TOP, DLG_X, DLG_H, DLG_W),)
STAGE_X = DLG_LANE_W           # 64: everything right of this is animation
STAGE_W = W - STAGE_X          # 136


def is_dialog_9x16(w: int, h: int) -> bool:
    """True when a ``w`` x ``h`` cell window is (within one cell of) 9:16.

    The integer relation is ``8*w == 9*h`` (e.g. 54x48, 45x40).  The requested
    1-cell top/bottom margins force 49 rows, whose exact width would be 55.125
    cells; 55 cols renders 550x980 px -- within one cell (0.2 %) of 9:16.
    """
    return abs(8 * w - 9 * h) <= 1

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
VTT_PATH = ROOT / "ga1ahad.vtt"
AUDIO_PATH = ROOT / "ga1ahad_audio.wav"
CLAUDE_IMAGE = ROOT / "claude.webp"
OUT_MP4 = ROOT / "ga1ahad.mp4"
BUILD_DIR = ROOT / "build"
CACHE_DIR = BUILD_DIR / "cache"
ANALYSIS_PATH = BUILD_DIR / "audio_analysis.npz"
CONTENT_ROOT = ROOT / "content"

# --------------------------------------------------------------------------
# Font discovery (offline friendly)
# --------------------------------------------------------------------------
FONT_CANDIDATES = [
    os.environ.get("GA1AHAD_FONT", ""),
    "/nix/store/349bajb6xdfd4mw3in7bs8jkpmhx1w96-dejavu-fonts-2.37/share/fonts/truetype/DejaVuSansMono.ttf",
]
FONT_FAMILIES = ["DejaVu Sans Mono", "Noto Sans Mono", "JetBrains Mono",
                 "Liberation Mono", "Maple Mono NF CN", "Noto Mono"]
SYMBOL_FALLBACK_FAMILIES = ["DejaVu Sans", "Noto Sans Symbols 2", "Noto Sans Symbols",
                            "Symbola", "Noto Sans"]


# --------------------------------------------------------------------------
# 24-bit palette
# --------------------------------------------------------------------------
def hx(s: str) -> int:
    """'#36c3b4' -> 0x36C3B4"""
    s = s.lstrip("#")
    return int(s, 16)


# Core ink / panels
BLACK = 0x000000
INK = hx("05070A")
INK2 = hx("080C10")
PANEL = hx("0A1118")
PANEL2 = hx("0E1A22")
PANEL3 = hx("122630")
BORDER = hx("1E3A46")
BORDER_HI = hx("2E5A68")
GRID = hx("153038")

# Text
TEXT = hx("D7F2F0")
TEXT_HI = hx("F2FFFE")
TEXT_DIM = hx("6E8E93")
TEXT_FAINT = hx("3C5560")
WHITE = hx("FFFFFF")

# Sam Altman / OpenAI -- engineering teal
CYAN = hx("36C3B4")
CYAN_HI = hx("7FF6E6")
CYAN_DIM = hx("18756F")
CYAN_DEEP = hx("0B3A3B")

# Dahlia Amodei / Anthropic -- amber brown + hysteric red
AMBER = hx("C87A4B")
AMBER_HI = hx("FFB27A")
AMBER_DIM = hx("6E3A1E")
BROWN = hx("7A4A2A")
BROWN_DIM = hx("3A2416")
RED = hx("E63946")
RED_HI = hx("FF5D6C")
RED_DIM = hx("7C1A22")
RED_DEEP = hx("3A0A0E")
BLOOD = hx("7A0C12")
BLOOD_HI = hx("C41520")

# Claude -- terracotta / sunflower gold
TERRA = hx("D97757")
TERRA_HI = hx("F08C4B")
TERRA_PALE = hx("FFC9A3")
TERRA_DIM = hx("7A3C28")
TERRA_DEEP = hx("3A1A12")
GOLD = hx("F5B942")
GOLD_HI = hx("FFD97A")
GOLD_DIM = hx("8A6415")
GOLD_DEEP = hx("3A2A08")

# Extra accents
GREEN = hx("54E38A")
GREEN_DIM = hx("1E6B3C")
TERM_GREEN = hx("38D973")
BLUE = hx("4A90D9")
BLUE_DIM = hx("1E3F6B")
PURPLE = hx("8A4FD0")
PURPLE_HI = hx("C9A2F0")
PURPLE_DIM = hx("4A2878")
PURPLE_DEEP = hx("1E0E33")
ORANGE = hx("FF8A3D")
MAGENTA = hx("E055C0")


# --------------------------------------------------------------------------
# Colour maths (packed 0xRRGGBB)
# --------------------------------------------------------------------------
def mix(a: int, b: int, t: float) -> int:
    """Linear blend a->b with t in [0,1] (no clamping of t on purpose; clamp only at 0/1)."""
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    it = 1.0 - t
    r = int(((a >> 16) & 255) * it + ((b >> 16) & 255) * t)
    g = int(((a >> 8) & 255) * it + ((b >> 8) & 255) * t)
    bl = int((a & 255) * it + (b & 255) * t)
    return (r << 16) | (g << 8) | bl


def scale(c: int, f: float) -> int:
    """Multiply brightness by f, clamped."""
    r = int(((c >> 16) & 255) * f)
    g = int(((c >> 8) & 255) * f)
    b = int((c & 255) * f)
    return (min(255, r) << 16) | (min(255, g) << 8) | min(255, b)


def add(c: int, other: int) -> int:
    r = min(255, ((c >> 16) & 255) + ((other >> 16) & 255))
    g = min(255, ((c >> 8) & 255) + ((other >> 8) & 255))
    b = min(255, (c & 255) + (other & 255))
    return (r << 16) | (g << 8) | b


def with_alpha(c: int, bg: int, a: float) -> int:
    return mix(bg, c, a)


def lum(c: int) -> float:
    r = (c >> 16) & 255
    g = (c >> 8) & 255
    b = c & 255
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def hsv_shift(c: int, dh: float, s_mul: float = 1.0, v_mul: float = 1.0) -> int:
    """Cheap hue rotation in HSV space (used by glitch effects)."""
    import colorsys

    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h = (h + dh) % 1.0
    s = min(1.0, s * s_mul)
    v = min(1.0, v * v_mul)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255) << 16) | (int(g * 255) << 8) | int(b * 255)


def ramp(stops: list[tuple[float, int]], t: float) -> int:
    """Multi-stop colour ramp; stops sorted by position."""
    if not stops:
        return WHITE
    if t <= stops[0][0]:
        return stops[0][1]
    if t >= stops[-1][0]:
        return stops[-1][1]
    for i in range(1, len(stops)):
        p0, c0 = stops[i - 1]
        p1, c1 = stops[i]
        if t <= p1:
            span = p1 - p0
            return mix(c0, c1, 0.0 if span <= 0 else (t - p0) / span)
    return stops[-1][1]


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def smoothstep(a: float, b: float, x: float) -> float:
    if a == b:
        return 0.0 if x < a else 1.0
    t = clamp((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ease_out_cubic(x: float) -> float:
    x = clamp(x, 0.0, 1.0)
    return 1.0 - (1.0 - x) ** 3


def ease_in_cubic(x: float) -> float:
    x = clamp(x, 0.0, 1.0)
    return x * x * x


def ease_in_quad(x: float) -> float:
    x = clamp(x, 0.0, 1.0)
    return x * x


def ease_out_quad(x: float) -> float:
    x = clamp(x, 0.0, 1.0)
    return 1.0 - (1.0 - x) ** 2


def ease_out_quint(x: float) -> float:
    x = clamp(x, 0.0, 1.0)
    return 1.0 - (1.0 - x) ** 5


def ease_in_out(x: float) -> float:
    x = clamp(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def fmt_time(t: float) -> str:
    t = max(0.0, t)
    m = int(t // 60)
    s = t - m * 60
    return f"{m:02d}:{s:06.3f}"


def fmt_clock(t: float) -> str:
    t = max(0.0, t)
    m = int(t // 60)
    s = int(t - m * 60)
    ms = int(round((t - int(t)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{m:02d}:{s:02d}.{ms:03d}"
