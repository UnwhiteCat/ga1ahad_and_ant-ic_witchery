"""Character canvas with 24-bit colour cells, braille sub-pixel layer and FX state.

Coordinates are ``(row, col)`` with row 0 at the top.  Colours are packed
``0xRRGGBB`` integers.  The canvas is deliberately plain-Python (lists of ints)
because scene code writes tens of thousands of cells per frame and Python list
assignment is considerably faster than numpy scalar indexing; conversion to
numpy happens once per frame in :mod:`ga1ahad.raster`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import config as C
from .glyphs import GlyphTable, glyph_table

W, H = C.W, C.H


# --------------------------------------------------------------------------
# Effects state (consumed by the rasteriser / cell post-processor)
# --------------------------------------------------------------------------
@dataclass
class Effects:
    glitch: float = 0.0          # 0..1 row tearing + char corruption
    chroma: float = 0.0          # 0..1 RGB channel separation (cells)
    invert: float = 0.0          # 0..1 inverted video flash
    flash_color: int = 0xFFFFFF
    flash: float = 0.0           # 0..1 white/colour flash overlay
    shake_x: float = 0.0         # px
    shake_y: float = 0.0         # px
    scan: float = 1.0            # scanline strength
    vignette: float = 1.0
    noise: float = 0.0           # additive pixel noise
    hue_shift: float = 0.0       # whole frame hue rotation (radians fraction)
    sat: float = 1.0
    zoom: float = 1.0            # pixel scale jitter (glitch punch-in)
    roll: float = 0.0            # vertical pixel roll (px)

    def reset(self) -> None:
        self.glitch = 0.0
        self.chroma = 0.0
        self.invert = 0.0
        self.flash = 0.0
        self.flash_color = 0xFFFFFF
        self.shake_x = 0.0
        self.shake_y = 0.0
        self.scan = 1.0
        self.vignette = 1.0
        self.noise = 0.0
        self.hue_shift = 0.0
        self.sat = 1.0
        self.zoom = 1.0
        self.roll = 0.0


# --------------------------------------------------------------------------
# Sprites
# --------------------------------------------------------------------------
class Sprite:
    """A compact block of cells used for portraits, icons and logos."""

    __slots__ = ("h", "w", "ch", "fg", "bg")

    def __init__(self, h: int, w: int) -> None:
        self.h = h
        self.w = w
        self.ch = [[0] * w for _ in range(h)]
        self.fg = [[C.WHITE] * w for _ in range(h)]
        self.bg = [[C.BLACK] * w for _ in range(h)]

    @classmethod
    def blank(cls, h: int, w: int) -> "Sprite":
        return cls(h, w)

    def blit_into(self, canvas: "Canvas", y: int, x: int,
                  alpha: float = 1.0) -> None:
        canvas.sprite(y, x, self, alpha=alpha)


# --------------------------------------------------------------------------
# Braille sub-pixel layer
# --------------------------------------------------------------------------
class Braille:
    """A region of ``rows x cols`` cells, addressed as ``2*cols x 4*rows`` dots."""

    __slots__ = ("canvas", "y", "x", "rows", "cols", "dots")

    def __init__(self, canvas: "Canvas", y: int, x: int, rows: int, cols: int) -> None:
        self.canvas = canvas
        self.y = y
        self.x = x
        self.rows = rows
        self.cols = cols
        self.dots: dict[tuple[int, int], int] = {}

    # dot coordinates: px in [0, cols*2), py in [0, rows*4)
    def plot(self, px: int, py: int, color: int, alpha: float = 1.0) -> None:
        if 0 <= px < self.cols * 2 and 0 <= py < self.rows * 4:
            if alpha < 1.0:
                old = self.dots.get((px, py))
                color = C.mix(old, color, alpha) if old is not None else C.scale(color, alpha)
            self.dots[(px, py)] = color

    def plot_f(self, fx: float, fy: float, color: int, alpha: float = 1.0) -> None:
        self.plot(int(fx), int(fy), color, alpha)

    def line(self, x0: float, y0: float, x1: float, y1: float, color: int,
             alpha: float = 1.0, step: float = 0.5) -> None:
        dx, dy = x1 - x0, y1 - y0
        n = int(max(abs(dx), abs(dy)) / step) + 1
        for i in range(n + 1):
            t = i / n if n else 0.0
            self.plot(int(round(x0 + dx * t)), int(round(y0 + dy * t)), color, alpha)

    def polyline(self, pts: list[tuple[float, float]], color: int,
                 alpha: float = 1.0) -> None:
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], color, alpha)

    def circle(self, cx: float, cy: float, r: float, color: int,
               alpha: float = 1.0, step: float = 0.35) -> None:
        n = max(8, int(2 * math.pi * r / step))
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            self.plot(int(round(cx + r * math.cos(a))), int(round(cy + r * math.sin(a))),
                      color, alpha)

    def commit(self) -> None:
        """Convert dot matrix into braille characters on the canvas."""
        dots = self.dots
        if not dots:
            return
        # per-cell accumulation (cell -> list of (bit, colour))
        cells: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for (px, py), col in dots.items():
            cx, cy = px // 2, py // 4
            bit = _BRAILLE_BIT[px % 2][py % 4]
            cells.setdefault((cy, cx), []).append((bit, col))
        cv = self.canvas
        own = cv.glyphs
        for (cy, cx), items in cells.items():
            code = 0
            r = g = b = n = 0
            for bit, col in items:
                code |= 1 << bit
                r += (col >> 16) & 255
                g += (col >> 8) & 255
                b += col & 255
                n += 1
            color = ((r // n) << 16) | ((g // n) << 8) | (b // n)
            gid = own.char_id(chr(0x2800 + code))
            yy, xx = self.y + cy, self.x + cx
            if cv.clip_enabled and not cv._row_ok(yy):
                continue
            if 0 <= yy < H and 0 <= xx < W:
                cv.ch[yy][xx] = gid
                cv.fg[yy][xx] = color


# braille bit index mapping (px%2, py%4) -> bit 0..7
#   (0,0)=dot1 bit0  (0,1)=dot2 bit1  (0,2)=dot3 bit2  (1,0)=dot4 bit3
#   (0,3)=dot7 bit6  (1,1)=dot5 bit4  (1,2)=dot6 bit5  (1,3)=dot8 bit7
_BRAILLE_BIT = [[0, 1, 2, 6], [3, 4, 5, 7]]


# --------------------------------------------------------------------------
# Canvas
# --------------------------------------------------------------------------
class Canvas:
    def __init__(self, glyphs: GlyphTable | None = None, width: int = W,
                 height: int = H) -> None:
        self.glyphs = glyphs or glyph_table()
        self.w = width
        self.h = height
        self.ch = [[0] * width for _ in range(height)]
        self.fg = [[C.WHITE] * width for _ in range(height)]
        self.bg = [[C.BLACK] * width for _ in range(height)]
        self.fx = Effects()
        # scene/content clipping: enabled by Renderer around scene.draw() so a
        # scene can never paint on the chrome rows (0,1,53,54,55).
        self.clip_enabled = False
        self.clip_y0 = 0
        self.clip_y1 = height
        self.clip_count = 0
        # direct row/list writes that still escaped the clip on the last draw
        # (discarded by Renderer before the chrome is painted)
        self.scene_bleed = 0
        # LLM dialog mask: cells painted by art.llm_dialog().  The focus-region
        # contract keeps every conversation window inside the left dialog lane
        # (columns 0..C.DLG_LANE_W); the renderer counts any leak into the right
        # animation stage so `verify` can fail a regression.
        self.dlg = [[False] * width for _ in range(height)]
        self.dlg_cells = 0
        self.dlg_stage_bleed = 0
        self.dlg_exempt = False

    # -- content clip ----------------------------------------------------
    def set_content_clip(self, y0: int, y1: int) -> None:
        self.clip_enabled = True
        self.clip_y0, self.clip_y1 = y0, y1
        self.clip_count = 0

    def clear_clip(self) -> None:
        self.clip_enabled = False
        self.clip_y0, self.clip_y1 = 0, self.h

    def _row_ok(self, y: int) -> bool:
        if not self.clip_enabled:
            return 0 <= y < self.h
        if self.clip_y0 <= y < self.clip_y1:
            return True
        self.clip_count += 1
        return False

    def _clip_span(self, y0: int, y1: int) -> tuple[int, int]:
        if not self.clip_enabled:
            return max(0, y0), min(self.h, y1)
        a, b = max(y0, self.clip_y0), min(y1, self.clip_y1)
        if (a, b) != (y0, y1):
            self.clip_count += 1
        return max(0, a), min(self.h, b)
        # chrome control set by scenes
        self.hide_topbar = False
        self.hide_lyrics = False
        self.bleed = False     # scene wants the full 56 rows (chrome floats above)

    # -- lifecycle -------------------------------------------------------
    def clear(self, fg: int = C.TEXT, bg: int = C.INK) -> None:
        self.ch = [[0] * self.w for _ in range(self.h)]
        self.fg = [[fg] * self.w for _ in range(self.h)]
        self.bg = [[bg] * self.w for _ in range(self.h)]
        self.dlg = [[False] * self.w for _ in range(self.h)]
        self.dlg_cells = 0
        self.dlg_stage_bleed = 0
        self.dlg_exempt = False

    # -- LLM dialog mask -------------------------------------------------
    def mark_dialog(self, y: int, x: int, h: int, w: int) -> None:
        """Record a conversation window on the dialog mask (clip-aware)."""
        y0, y1 = self._clip_span(y, y + h)
        x0, x1 = max(0, x), min(self.w, x + w)
        if y1 <= y0 or x1 <= x0:
            return
        stage = C.STAGE_X
        for yy in range(y0, y1):
            row = self.dlg[yy]
            for xx in range(x0, x1):
                if not row[xx]:
                    row[xx] = True
                    self.dlg_cells += 1
                    if xx >= stage:
                        self.dlg_stage_bleed += 1

    # -- primitives ------------------------------------------------------
    def put(self, y: int, x: int, ch: str | int, fg: int, bg: int | None = None) -> None:
        if self.clip_enabled and not self._row_ok(y):
            return
        if 0 <= y < self.h and 0 <= x < self.w:
            self.ch[y][x] = ch if isinstance(ch, int) else self.glyphs.char_id(ch)
            self.fg[y][x] = fg
            if bg is not None:
                self.bg[y][x] = bg

    def get(self, y: int, x: int) -> tuple[int, int, int]:
        return self.ch[y][x], self.fg[y][x], self.bg[y][x]

    def text(self, y: int, x: int, s: str, fg: int, bg: int | None = None,
             bold: bool = False) -> int:
        """Draw a string, clipped to the canvas. Returns the advance width."""
        if self.clip_enabled and not self._row_ok(y):
            return 0
        if not (0 <= y < self.h) or not s:
            return 0
        ids = self.glyphs.text_ids(s, bold) if bold else self.glyphs.text_ids(s)
        n = len(ids)
        x0 = max(0, x)
        x1 = min(self.w, x + n)
        if x1 > x0:
            off = x0 - x
            self.ch[y][x0:x1] = ids[off:off + x1 - x0]
            self.fg[y][x0:x1] = [fg] * (x1 - x0)
            if bg is not None:
                self.bg[y][x0:x1] = [bg] * (x1 - x0)
        return n

    def text_center(self, y: int, s: str, fg: int, bg: int | None = None,
                    bold: bool = False, x0: int = 0, x1: int | None = None) -> int:
        x1 = self.w if x1 is None else x1
        x = x0 + max(0, (x1 - x0 - len(s)) // 2)
        return self.text(y, x, s, fg, bg, bold=bold)

    def fill(self, y: int, x: int, h: int, w: int, ch: str = " ",
             fg: int = C.TEXT, bg: int | None = C.INK) -> None:
        gid = self.glyphs.char_id(ch)
        y0, y1 = self._clip_span(y, y + h)
        y0 = max(0, y0)
        y1 = min(self.h, y1)
        x0 = max(0, x)
        x1 = min(self.w, x + w)
        if y1 <= y0 or x1 <= x0:
            return
        n = x1 - x0
        for yy in range(y0, y1):
            self.ch[yy][x0:x1] = [gid] * n
            self.fg[yy][x0:x1] = [fg] * n
            if bg is not None:
                self.bg[yy][x0:x1] = [bg] * n

    def fill_bg(self, y: int, x: int, h: int, w: int, bg: int) -> None:
        y0, y1 = self._clip_span(y, y + h)
        y0 = max(0, y0)
        y1 = min(self.h, y1)
        x0 = max(0, x)
        x1 = min(self.w, x + w)
        for yy in range(y0, y1):
            self.bg[yy][x0:x1] = [bg] * (x1 - x0)

    def blend_bg(self, y: int, x: int, color: int, alpha: float) -> None:
        if self.clip_enabled and not self._row_ok(y):
            return
        if 0 <= y < self.h and 0 <= x < self.w:
            self.bg[y][x] = C.mix(self.bg[y][x], color, alpha)

    def hline(self, y: int, x0: int, x1: int, fg: int, bg: int | None = None,
              ch: str = "\u2500") -> None:
        gid = self.glyphs.char_id(ch)
        a = max(0, min(x0, x1))
        b = min(self.w, max(x0, x1))
        if (not self.clip_enabled or self._row_ok(y)) and 0 <= y < self.h and b > a:
            self.ch[y][a:b] = [gid] * (b - a)
            self.fg[y][a:b] = [fg] * (b - a)
            if bg is not None:
                self.bg[y][a:b] = [bg] * (b - a)

    def vline(self, x: int, y0: int, y1: int, fg: int, bg: int | None = None,
              ch: str = "\u2502") -> None:
        gid = self.glyphs.char_id(ch)
        a, b = self._clip_span(min(y0, y1), max(y0, y1))
        a = max(0, a)
        b = min(self.h, b)
        if 0 <= x < self.w:
            for yy in range(a, b):
                self.ch[yy][x] = gid
                self.fg[yy][x] = fg
                if bg is not None:
                    self.bg[yy][x] = bg

    # -- boxes -----------------------------------------------------------
    def frame(self, y: int, x: int, h: int, w: int, fg: int,
              bg: int | None = None, style: str = "single",
              fill: bool = False) -> None:
        """Draw a box border.  Style: single / double / heavy / rounded / dotted."""
        if h <= 1 or w <= 1:
            return
        S = {
            "single": ("\u250c", "\u2510", "\u2514", "\u2518", "\u2500", "\u2502", "\u251c",
                       "\u2524", "\u252c", "\u2534", "\u253c"),
            "rounded": ("\u256d", "\u256e", "\u256f", "\u2570", "\u2500", "\u2502", "\u251c",
                        "\u2524", "\u252c", "\u2534", "\u253c"),
            "double": ("\u2554", "\u2557", "\u255a", "\u255d", "\u2550", "\u2551", "\u2560",
                       "\u2563", "\u2566", "\u2569", "\u256c"),
            "heavy": ("\u250f", "\u2513", "\u2517", "\u251b", "\u2501", "\u2503", "\u2523",
                      "\u252b", "\u2533", "\u253b", "\u254b"),
        }[style]
        tl, tr, bl, br, hz, vt = S[0], S[1], S[2], S[3], S[4], S[5]
        if fill and bg is not None:
            self.fill(y + 1, x + 1, h - 2, w - 2, " ", fg, bg)
        self.hline(y, x + 1, x + w - 1, fg, bg, hz)
        self.hline(y + h - 1, x + 1, x + w - 1, fg, bg, hz)
        self.vline(x, y + 1, y + h - 1, fg, bg, vt)
        self.vline(x + w - 1, y + 1, y + h - 1, fg, bg, vt)
        self.put(y, x, tl, fg, bg)
        self.put(y, x + w - 1, tr, fg, bg)
        self.put(y + h - 1, x, bl, fg, bg)
        self.put(y + h - 1, x + w - 1, br, fg, bg)

    def panel(self, y: int, x: int, h: int, w: int, fg: int = C.BORDER,
              bg: int = C.PANEL, title: str | None = None,
              title_fg: int | None = None, style: str = "single",
              title_align: str = "left", fill: bool = True) -> None:
        self.frame(y, x, h, w, fg, bg, style, fill=fill)
        if title:
            tf = title_fg if title_fg is not None else fg
            label = f" {title} "
            if title_align == "center":
                tx = x + max(1, (w - len(label)) // 2)
            elif title_align == "right":
                tx = x + w - len(label) - 2
            else:
                tx = x + 2
            self.text(y, tx, label, tf, bg, bold=True)

    def label(self, y: int, x: int, key: str, value: str, kfg: int, vfg: int,
              bg: int | None = None) -> None:
        self.text(y, x, key, kfg, bg)
        self.text(y, x + len(key), value, vfg, bg)

    # -- sprites ---------------------------------------------------------
    def sprite(self, y: int, x: int, sp: Sprite, alpha: float = 1.0,
               fg_mul: float = 1.0, tint: int | None = None,
               tint_amt: float = 0.0) -> None:
        y0, y1 = self._clip_span(y, y + sp.h)
        y0 = max(0, y0)
        y1 = min(self.h, y1)
        x0 = max(0, x)
        x1 = min(self.w, x + sp.w)
        if y1 <= y0 or x1 <= x0:
            return
        for sy in range(y0 - y, y1 - y):
            row_ch = self.ch[y + sy]
            row_fg = self.fg[y + sy]
            row_bg = self.bg[y + sy]
            src_ch = sp.ch[sy]
            src_fg = sp.fg[sy]
            src_bg = sp.bg[sy]
            for sx in range(x0 - x, x1 - x):
                gid = src_ch[sx]
                if gid == 0:
                    continue
                fg = src_fg[sx]
                bg = src_bg[sx]
                if tint is not None and tint_amt > 0:
                    fg = C.mix(fg, tint, tint_amt)
                    bg = C.mix(bg, tint, tint_amt)
                if fg_mul != 1.0:
                    fg = C.scale(fg, fg_mul)
                    bg = C.scale(bg, fg_mul)
                if alpha < 1.0:
                    fg = C.mix(row_bg[x + sx], fg, alpha)
                row_ch[x + sx] = gid
                row_fg[x + sx] = fg
                row_bg[x + sx] = bg

    # -- helpers ---------------------------------------------------------
    def braille(self, y: int, x: int, rows: int, cols: int) -> Braille:
        return Braille(self, y, x, rows, cols)

    def dim(self, y: int, x: int, h: int, w: int, f: float) -> None:
        ya, yb = self._clip_span(y, y + h)
        for yy in range(max(0, ya), min(self.h, yb)):
            row_f = self.fg[yy]
            row_b = self.bg[yy]
            for xx in range(max(0, x), min(self.w, x + w)):
                row_f[xx] = C.scale(row_f[xx], f)
                row_b[xx] = C.scale(row_b[xx], f)

    def to_rows(self) -> list[str]:
        """Plain text rows (debug/verification helper)."""
        return ["".join(self.glyphs.chars[g] for g in row) for row in self.ch]

    def row_text(self, y: int, x0: int = 0, x1: int | None = None) -> str:
        x1 = self.w if x1 is None else x1
        return "".join(self.glyphs.chars[g] for g in self.ch[y][x0:x1])


# --------------------------------------------------------------------------
# Text utilities
# --------------------------------------------------------------------------
def wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= width:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def typewriter(text: str, t: float, cps: float = 60.0, delay: float = 0.0) -> str:
    n = int(max(0.0, (t - delay)) * cps)
    return text[:n]


def glitch_text(text: str, amount: float, rng, glyphs: GlyphTable | None = None) -> str:
    if amount <= 0:
        return text
    junk = "\u2592\u2593#@%&\u00a7\u2588\u2591/\\|_-+=<>[]{}()"
    out = []
    for ch in text:
        if ch != " " and rng.random() < amount * 0.55:
            out.append(rng.choice(junk))
        else:
            out.append(ch)
    return "".join(out)
