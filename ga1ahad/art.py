"""Reusable TUI art widgets shared by all scenes.

Everything here is a deterministic function of ``t`` (plus a seed) so the
offline renderer can split frames across workers and render in parallel.
"""

from __future__ import annotations

import math
import random

import numpy as np

from . import config as C
from .canvas import Canvas, Braille, Sprite, wrap
from .timeline import Timeline


# --------------------------------------------------------------------------
# Panels / frames
# --------------------------------------------------------------------------
def title_bar(c: Canvas, y: int, x: int, w: int, title: str, fg: int,
              bg: int | None = None, fill_bg: int | None = None) -> None:
    if bg is None:
        bg = fill_bg if fill_bg is not None else C.PANEL2
    label = f" {title} "
    c.fill(y, x, 1, w, " ", fg, bg)
    tw = min(len(label), w - 2)
    c.text(y, x + 1, label[:tw], fg, bg, bold=True)


def panel(c: Canvas, y: int, x: int, h: int, w: int, fg: int = C.BORDER,
          bg: int = C.PANEL, title: str | None = None,
          title_fg: int | None = None, style: str = "single",
          title_align: str = "left", fill: bool = True) -> None:
    c.panel(y, x, h, w, fg, bg, title=title, title_fg=title_fg, style=style,
            title_align=title_align, fill=fill)


def banner(c: Canvas, y: int, x: int, w: int, text: str, fg: int,
           fill: int | None = None, border: int | None = None,
           side: str = "\u258c", sides: bool = True) -> None:
    big_banner(c, y, x, w, text, fg, fill=fill, border=border, side=side, sides=sides)


def box_shadow(c: Canvas, y: int, x: int, h: int, w: int, amount: float = 0.55) -> None:
    """Darken cells to the right/below a window to fake depth."""
    ya, yb = y, y + h + 1
    if getattr(c, "clip_enabled", False):
        ya, yb = max(ya, c.clip_y0), min(yb, c.clip_y1)
    for yy in range(max(0, ya), min(c.h, yb)):
        for xx in range(max(0, x), min(c.w, x + w + 1)):
            edge = (xx == x + w) or (yy == y + h)
            if edge:
                c.bg[yy][xx] = C.mix(c.bg[yy][xx], C.BLACK, amount)
                c.fg[yy][xx] = C.mix(c.fg[yy][xx], C.BLACK, amount * 0.7)


def dialog(c: Canvas, y: int, x: int, h: int, w: int, title: str = "",
           lines: list[str] | None = None, fg: int = C.TEXT, bg: int = C.PANEL,
           border: int = C.BORDER_HI, style: str = "single", shadow: bool = True,
           title_bg: int | None = None, line_fg: list[int] | None = None,
           align: str = "left", image: Sprite | None = None) -> None:
    """A TUI window with optional shadow, title and text body."""
    if shadow:
        box_shadow(c, y, x, h, w, 0.6)
    c.panel(y, x, h, w, border, bg, style=style, fill=True)
    if title:
        tbg = title_bg if title_bg is not None else C.mix(bg, border, 0.25)
        c.fill(y, x + 1, 1, w - 2, " ", border, tbg)
        c.text(y, x + 2, f" {title} "[: w - 3], border if title_bg is None else fg, tbg, bold=True)
    if lines:
        yy = y + 1
        inner_w = w - 4
        for i, line in enumerate(lines):
            if yy >= y + h - 1:
                break
            for seg in wrap(line, inner_w) if align != "raw" else [line]:
                if yy >= y + h - 1:
                    break
                col = line_fg[i] if line_fg and i < len(line_fg) else fg
                if align == "center":
                    c.text_center(yy, seg, col, bg, x0=x + 2, x1=x + w - 2)
                else:
                    c.text(yy, x + 2, seg[:inner_w], col, bg)
                yy += 1
    if image is not None:
        ix = x + max(1, (w - image.w) // 2)
        iy = y + max(1, h - image.h - 1)
        c.sprite(iy, ix, image)


def llm_dialog(c: Canvas, y: int, x: int, h: int, w: int, title: str = "",
               *, fg: int = C.TEXT, bg: int = C.PANEL,
               border: int = C.BORDER_HI, style: str = "single",
               shadow: bool = True, title_bg: int | None = None,
               title_fg: int | None = None, right: str = "",
               right_fg: int | None = None) -> tuple[int, int, int, int]:
    """The human <-> LLM conversation window (portrait 9:16, left margins).

    Enforces the focus-region contract used throughout the film:

    * the window is a *portrait* 9:16 rectangle in pixels (``|8*w - 9*h| <= 1``
      on the 10x20 cell grid -- 55x49 cells = 550x980 px is the standard size,
      54x48 is the exact relation),
    * it is placed with the requested margins inside the content band:
      ``x >= C.DLG_X`` (margin-left 1), ``y >= C.DLG_TOP`` (margin-top 1) and
      ``y + h <= C.CONTENT_Y1 - C.DLG_BOTTOM`` (margin-bottom 1), left lane,
    * it is recorded on the canvas dialog mask so the renderer / verifier can
      prove that no conversation window leaks into the right animation stage.

    Returns the window rect ``(y, x, h, w)``; scenes draw their live content into
    the inner body (``y + 1 .. y + h - 2``, ``x + 2 .. x + w - 3``).  Special
    transitions may break the rule only through ``Scene.DIALOG_EXEMPT``.
    """
    if not C.is_dialog_9x16(w, h):
        raise ValueError(
            f"LLM dialog must be portrait 9:16 in pixels (|8*w - 9*h| <= 1), "
            f"got {w}x{h} cells")
    if x < C.DLG_X or x + w > C.DLG_LANE_W:
        raise ValueError(
            f"LLM dialog must honour the left lane/margin (x >= {C.DLG_X}, "
            f"x+w <= {C.DLG_LANE_W}), got x={x} w={w}")
    if y < C.DLG_TOP or y + h > C.CONTENT_Y1 - C.DLG_BOTTOM:
        raise ValueError(
            f"LLM dialog must sit between margins {C.DLG_TOP} and "
            f"{C.CONTENT_Y1 - C.DLG_BOTTOM - 1}, got y={y} h={h}")
    if shadow:
        box_shadow(c, y, x, h, w, 0.55)
    c.panel(y, x, h, w, border, bg, style=style, fill=True)
    tbg = title_bg if title_bg is not None else C.mix(bg, border, 0.24)
    if title or right:
        c.fill(y, x + 1, 1, w - 2, " ", border, tbg)
    if title:
        c.text(y, x + 2, f" {title} "[: w - 3],
               title_fg if title_fg is not None else border, tbg, bold=True)
    if right:
        rx = x + w - len(right) - 2
        c.text(y, max(x + 2, rx), right,
               right_fg if right_fg is not None else C.mix(border, C.WHITE, 0.3), tbg)
    c.mark_dialog(y, x, h, w)
    return (y, x, h, w)


def llm_body(y: int, h: int) -> tuple[int, int]:
    """Inner body rows of a dialog rect: ``(first_row, last_row_exclusive)``."""
    return (y + 1, y + h - 1)


def separator(c: Canvas, y: int, x: int, w: int, label: str = "",
              fg: int = C.GRID, label_fg: int | None = None,
              bg: int | None = None) -> None:
    c.hline(y, x, x + w, fg, bg, "\u2500")
    if label:
        lf = label_fg if label_fg is not None else C.TEXT_DIM
        lab = f" {label} "
        lx = x + max(0, (w - len(lab)) // 2)
        c.fill(y, lx, 1, len(lab), " ", lf, bg if bg is not None else C.INK)
        c.text(y, lx, lab, lf, bg, bold=False)


# --------------------------------------------------------------------------
# Bars and gauges
# --------------------------------------------------------------------------
def bar(c: Canvas, y: int, x: int, w: int, frac: float, fg: int,
        track_fg: int = C.BORDER, bg: int | None = C.INK,
        ch: str = "\u2588", track: str = "\u2591") -> None:
    frac = 0.0 if frac != frac else min(1.0, max(0.0, frac))
    n = int(round(frac * w))
    c.fill(y, x, 1, w, track, track_fg, bg)
    c.fill(y, x, 1, n, ch, fg, bg)


def gradient_bar(c: Canvas, y: int, x: int, w: int, frac: float,
                 colors: list[int], bg: int | None = None,
                 ch_full: str = "\u2588", ch_empty: str = "\u2591") -> None:
    frac = min(1.0, max(0.0, frac))
    n = int(round(frac * w))
    for i in range(w):
        if i < n:
            t = i / max(1, w - 1)
            col = C.ramp([(k / max(1, len(colors) - 1), v) for k, v in enumerate(colors)], t)
            c.put(y, x + i, ch_full, col, bg)
        else:
            c.put(y, x + i, ch_empty, C.BORDER, bg)


def gauge(c: Canvas, y: int, x: int, w: int, frac: float, fg: int,
          label: str = "", bg: int | None = C.INK) -> None:
    if label:
        c.text(y, x, label[:w], C.TEXT_DIM, bg)
        x += len(label)
        w = max(2, w - len(label))
    bar(c, y, x, w, frac, fg, bg=bg)


def value_display(c: Canvas, y: int, x: int, label: str, value: str,
                  fg: int = C.TEXT_HI, bg: int | None = None,
                  label_fg: int = C.TEXT_FAINT) -> None:
    c.text(y, x, label, label_fg, bg)
    c.text(y, x + len(label), value, fg, bg, bold=True)


# --------------------------------------------------------------------------
# Braille charts
# --------------------------------------------------------------------------
def line_chart(c: Canvas, y: int, x: int, h: int, w: int, data: list[float],
               color: int, bg: int | None = None, grid: int | None = None,
               lo: float | None = None, hi: float | None = None,
               axis: bool = False, fill: bool = False,
               fill_ch: str = "\u2591") -> None:
    """Braille line chart.  ``grid`` optionally draws a faint dotted lattice."""
    if not data:
        if grid is not None:
            c.fill(y, x, h, w, " ", C.TEXT, bg)
        return
    n = len(data)
    lo = min(data) if lo is None else lo
    hi = max(data) if hi is None else hi
    span = (hi - lo) or 1.0
    # background + lattice
    c.fill(y, x, h, w, " ", C.TEXT, bg)
    if grid is not None:
        for gy in range(2, h, max(2, h // 4)):
            for gx in range(0, w, 3):
                c.put(y + gy, x + gx, "\u00b7", grid, bg)
        for gx in range(3, w, max(3, w // 8)):
            for gy in range(1, h, 3):
                c.put(y + gy, x + gx, "\u00b7", grid, bg)
    # area fill under the curve (cell resolution)
    if fill:
        shade = C.scale(color, 0.30)
        for cx in range(w):
            di = min(n - 1, int(cx / max(1, w - 1) * (n - 1)))
            v = data[di]
            cy = int(round((1.0 - (v - lo) / span) * (h - 1)))
            cy = min(h - 1, max(0, cy))
            for yy in range(cy + 1, h):
                c.put(y + yy, x + cx, fill_ch, shade, bg)
    br = c.braille(y, x, h, w)
    pw, ph = w * 2, h * 4
    prev = None
    pts = []
    for i, v in enumerate(data):
        px = int(round(i / max(1, n - 1) * (pw - 1)))
        py = int(round((1.0 - (v - lo) / span) * (ph - 3) + 1))
        pts.append((px, py))
    for i in range(1, len(pts)):
        px0, py0 = pts[i - 1]
        px1, py1 = pts[i]
        br.line(px0, py0, px1, py1, color, 0.95)
    # head marker
    hx, hy = pts[-1]
    br.plot(hx, hy - 1, C.mix(color, C.WHITE, 0.6))
    br.plot(hx, hy + 1, C.mix(color, C.WHITE, 0.6))
    br.commit()
    if axis:
        c.text(y + h - 1, x, f"{lo:.2f}", grid or C.TEXT_FAINT, bg)
        c.text(y + h - 1, x + w - len(f"{hi:.2f}"), f"{hi:.2f}", grid or C.TEXT_FAINT, bg)


def wave(c: Canvas, y: int, x: int, h: int, w: int, t: float, color: int,
         freq: float = 3.0, amp: float = 0.8, phase: float = 0.0,
         speed: float = 2.0, bg: int | None = None, second: int | None = None,
         bg_fill: bool = True) -> None:
    if bg_fill:
        c.fill(y, x, h, w, " ", C.TEXT, bg if bg is not None else C.INK)
    br = c.braille(y, x, h, w)
    pw, ph = w * 2, h * 4
    mid = (ph - 1) / 2.0
    pts = []
    for px in range(pw):
        u = px / max(1, pw - 1)
        env = math.sin(math.pi * u) ** 0.5
        val = (math.sin(u * math.pi * 2 * freq + t * speed + phase) * 0.6
               + math.sin(u * math.pi * 5 * freq + t * speed * 1.7 + phase * 2) * 0.25)
        pts.append((px, mid - val * amp * mid * env))
    for i in range(1, len(pts)):
        br.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], color, 0.9)
    if second is not None:
        for px in range(pw):
            u = px / max(1, pw - 1)
            val = math.sin(u * math.pi * 2 * (freq * 0.5) + t * speed * 0.6 + phase)
            yy = mid - val * mid * 0.45
            br.plot(px, int(yy), second, 0.55)
    br.commit()


def spectrum(c: Canvas, y: int, x: int, h: int, w: int, t: float,
             audio, fg: int = C.CYAN, bg: int | None = None,
             style: str = "bars", peak_fg: int | None = None) -> None:
    spec = audio.spectrum(t)
    n = min(len(spec), w)
    floor_y = y + h - 1
    for i in range(n):
        v = float(spec[int(i / max(1, n) * len(spec))])
        bh = max(0, min(h, int(round(v * h))))
        for j in range(bh):
            yy = floor_y - j
            if style == "bars":
                col = C.mix(fg, C.GOLD_HI, j / max(1, h))
                c.put(yy, x + i, "\u2588", col, bg)
            else:
                c.put(yy, x + i, "\u2591" if j < bh else " ", C.mix(fg, C.BLACK, 0.3), bg)
        if bh > 0:
            c.put(floor_y - min(h - 1, bh), x + i,
                  "\u2580", peak_fg if peak_fg is not None else C.GOLD_HI, bg)


def heatmap(c: Canvas, y: int, x: int, h: int, w: int, t: float, seed: int = 0,
            palette: list[int] | None = None, ch: str = "\u2588",
            bg: int | None = C.INK, focus: tuple[float, float] | None = None) -> None:
    palette = palette or [C.BLACK, C.CYAN_DEEP, C.CYAN_DIM, C.CYAN, C.CYAN_HI, C.WHITE]
    rng = random.Random(seed)
    off = rng.random() * 6.28
    for yy in range(h):
        for xx in range(w):
            v = (math.sin(xx * 0.31 + yy * 0.17 + t * 0.9 + off) * 0.35
                 + math.sin(xx * 0.11 - yy * 0.53 + t * 1.7) * 0.3
                 + math.sin((xx + yy) * 0.07 + t * 0.4) * 0.2 + 0.7)
            if focus:
                d = math.hypot((xx / w - focus[0]), (yy / h - focus[1]) * 2.0)
                v += max(0.0, 0.8 - d * 1.6)
            v = min(1.2, max(0.0, v))
            idx = min(len(palette) - 1, int(v * len(palette)))
            c.put(y + yy, x + xx, ch, palette[idx], bg)


# --------------------------------------------------------------------------
# Particles (stateless, deterministic)
# --------------------------------------------------------------------------
def particles(c: Canvas, y: int, x: int, h: int, w: int, t: float, seed: int = 1,
              count: int = 80, colors: list[int] | None = None,
              speed: float = 1.0, spread: float = 1.0, grav: float = 0.0,
              life: float = 3.0, mode: str = "braille", fade: bool = True,
              origin: tuple[float, float] = (0.5, 1.0), burst: bool = True,
              drift: float = 0.0) -> None:
    colors = colors or [C.GOLD, C.GOLD_HI, C.TERRA_HI, C.WHITE]
    rng = random.Random(seed)
    br = c.braille(y, x, h, w) if mode == "braille" else None
    pw, ph = w * 2, h * 4
    for i in range(count):
        r = random.Random(seed * 7919 + i * 104729)
        ang = r.uniform(-math.pi, 0.0) if burst else r.uniform(0, math.pi * 2)
        spd = r.uniform(0.3, 1.0) * speed
        vx = math.cos(ang) * spd * spread * (pw / 2)
        vy = math.sin(ang) * spd * spread * (ph / 2)
        delay = r.uniform(0.0, 0.35) if burst else 0.0
        age = (t - delay) % life
        ox = origin[0] * pw + r.uniform(-0.04, 0.04) * pw
        oy = origin[1] * ph
        px = ox + vx * age + drift * age * 3
        py = oy + vy * age + 0.5 * grav * age * age * ph
        if life > 0 and fade:
            a = max(0.0, 1.0 - age / life)
        else:
            a = 1.0
        if a <= 0.01:
            continue
        col = colors[i % len(colors)]
        col = C.mix(C.INK, col, min(1.0, a * 1.3))
        if br is not None:
            br.plot(int(px) % pw if False else int(px), int(py), col)
        else:
            c.put(y + int(py // 4) % h, x + int(px // 2) % w,
                  "\u00b7" if a < 0.5 else "\u2022", col)


def confetti(c: Canvas, y: int, x: int, h: int, w: int, t: float, seed: int = 3,
             count: int = 90, colors: list[int] | None = None,
             speed: float = 1.0) -> None:
    colors = colors or [C.GOLD, C.GOLD_HI, C.TERRA_HI, C.WHITE, C.CYAN_HI]
    glyphs = ["\u2580", "\u2584", "\u2592", "\u2502", "\u2500", "\u25c6", "\u2588"]
    for i in range(count):
        r = random.Random(seed * 131 + i * 977)
        fall = r.uniform(2.0, 7.0) * speed
        sway = r.uniform(0.4, 1.6)
        phase = r.uniform(0, 6.28)
        xx = (r.uniform(0, 1) * w + math.sin(t * sway + phase) * 2.0) % w
        yy = (r.uniform(0, 1) * h + t * fall) % h
        col = colors[i % len(colors)]
        c.put(y + int(yy), x + int(xx), glyphs[i % len(glyphs)], col, C.INK)


def starfield(c: Canvas, y: int, x: int, h: int, w: int, t: float,
              speed: float = 1.0, density: int = 70, color: int = C.TEXT_FAINT,
              bright: int = C.TEXT_HI) -> None:
    for i in range(density):
        r = random.Random(9001 + i * 37)
        sx = r.uniform(0, w)
        sy = r.uniform(0, h)
        sp = r.uniform(0.2, 1.6) * speed
        yy = int((sy + t * sp) % h)
        xx = int(sx)
        ch = " " if r.random() < 0.5 else ("\u00b7" if r.random() < 0.7 else "\u2022")
        col = color if r.random() < 0.8 else bright
        c.put(y + yy, x + xx, ch, col)


# --------------------------------------------------------------------------
# Terminal style helpers
# --------------------------------------------------------------------------
def scroll_lines(c: Canvas, y: int, x: int, h: int, w: int, lines: list[str],
                 t: float, speed: float = 8.0, fg: int = C.TEXT_DIM,
                 bg: int | None = C.INK, start: float = 0.0, cols: list[int] | None = None,
                 header: str | None = None) -> None:
    off = int(max(0.0, t - start) * speed)
    c.fill(y, x, h, w, " ", C.TEXT, bg)
    for row in range(h):
        idx = off + row
        if idx >= len(lines):
            break
        line = lines[idx]
        col = cols[idx] if cols else fg
        # older lines fade
        k = 1.0 - row / max(1, h) * 0.35
        col = C.mix(C.INK, col, k)
        c.text(y + row, x, line[:w], col, bg)
    if header:
        c.text(y, x, header[:w], C.TEXT_HI, bg, bold=True)


def typewriter(text: str, t: float, start: float = 0.0, cps: float = 60.0,
               cursor: bool = True, blink: float = 8.0) -> str:
    n = int(max(0.0, t - start) * cps)
    out = text[:n]
    if cursor and n <= len(text):
        on = (math.sin(t * blink * 3.14) > -0.2)
        if on:
            out += "\u2588"
    return out


def prompt_line(c: Canvas, y: int, x: int, user: str, host: str, cmd: str,
                t: float, start: float = 0.0, cps: float = 90.0,
                user_fg: int = C.CYAN_HI, cmd_fg: int = C.TEXT, bg: int | None = None,
                max_w: int | None = None) -> None:
    pre = f"{user}@{host}:~$ "
    c.text(y, x, pre, user_fg, bg, bold=False)
    body = typewriter(cmd, t, start, cps)
    if max_w:
        body = body[: max_w - len(pre)]
    c.text(y, x + len(pre), body, cmd_fg, bg)


def ticker(c: Canvas, y: int, x: int, w: int, text: str, t: float,
           speed: float = 12.0, fg: int = C.TEXT_DIM, bg: int | None = C.INK,
           bullet: str = " \u00b7 ") -> None:
    full = (text + bullet) * (w // max(1, len(text) + len(bullet)) + 2)
    off = int(t * speed) % max(1, len(text) + len(bullet))
    c.fill(y, x, 1, w, " ", fg, bg)
    c.text(y, x, full[off:off + w], fg, bg)


def big_banner(c: Canvas, y: int, x: int, w: int, text: str, fg: int,
               bg: int = C.INK, fill: int | None = None, border: int | None = None,
               side: str = "\u258c", sides: bool = True) -> None:
    bar_bg = fill if fill is not None else C.mix(bg, fg, 0.12)
    c.fill(y, x, 1, w, " ", fg, bar_bg)
    txt = f" {text} "[:w]
    # centre inside the banner box, not on the whole canvas (callers place
    # banners on the right stage or inside the portrait dialog window)
    c.text_center(y, txt, fg, bar_bg, bold=True, x0=x, x1=x + w)
    if sides:
        c.put(y, x, side, border if border is not None else fg, bar_bg)
        c.put(y, x + w - 1, side, border if border is not None else fg, bar_bg)


def dot_matrix_text(c: Canvas, y: int, x: int, text: str, fg: int,
                    bg: int | None = None, step: int = 2) -> int:
    """Fake 2x high text by drawing a shadow row under the text."""
    c.fill(y + 1, x, 1, len(text), "\u2584", C.scale(fg, 0.35), bg)
    c.text(y, x, text, fg, bg, bold=True)
    return len(text)


def wave_band(c: Canvas, y: int, w: int, t: float, audio, color: int,
              bg: int = C.INK, height: int = 1) -> None:
    """Thin audio-reactive band (used as a decorative separator)."""
    spec = audio.spectrum(t)
    for i in range(w):
        v = float(spec[int(i / w * len(spec))])
        if height <= 1:
            ch = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"[min(7, int(v * 7))]
        else:
            ch = "\u2588" if v > 0.4 else "\u2591"
        c.put(y, i, ch, color if v > 0.15 else C.BORDER, bg)


# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------
def progress_dots(c: Canvas, y: int, x: int, n: int, frac: float, fg: int,
                  bg: int | None = None) -> None:
    k = int(frac * n)
    for i in range(n):
        c.put(y, x + i * 2, "\u25cf" if i < k else "\u25cb", fg if i < k else C.BORDER, bg)


def clock_ring(c: Canvas, cx: int, cy: int, r: int, frac: float, fg: int,
               bg: int | None = None) -> None:
    br = c.braille(cy - r // 2, cx - r, r, max(1, (2 * r) // 2))
    # not used heavily; simple approximation
    br.commit()


def scanline_overlay(c: Canvas, t: float, strength: float = 0.06) -> None:
    pass


def subtitle_note(c: Canvas, y: int, x: int, text: str, fg: int, bg: int | None = None) -> None:
    c.text(y, x, f"\u2039 {text} \u203a", fg, bg)
