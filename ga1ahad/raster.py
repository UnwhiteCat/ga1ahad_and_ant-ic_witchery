"""Cell effects + GPU-free rasteriser: 200x56 character cells -> 2000x1120 RGB."""

from __future__ import annotations

import numpy as np

from . import config as C
from .canvas import Canvas, Effects
from .glyphs import glyph_table

CH, CW = C.CELL_H, C.CELL_W
H, W = C.H, C.W
PIX_H, PIX_W = C.PIX_H, C.PIX_W


def _unpack_rgb(packed: np.ndarray) -> np.ndarray:
    """(H,W) packed 0xRRGGBB -> (H,W,3) uint8."""
    return np.stack([(packed >> 16) & 255, (packed >> 8) & 255, packed & 255],
                    axis=-1).astype(np.uint8)


JUNK_CHARS = "\u2591\u2592\u2593#@%&\u00a7\u2588/\\|_-+=<>[]{}01"


def _junk_ids() -> np.ndarray:
    gt = glyph_table()
    return np.array([gt.char_id(ch) for ch in JUNK_CHARS], dtype=np.int32)


# --------------------------------------------------------------------------
# Cell-level glitch (operates on int32/uint8 arrays before rasterisation)
# --------------------------------------------------------------------------
def apply_cell_fx(ch: np.ndarray, fg: np.ndarray, fgpack: np.ndarray, bgpack: np.ndarray,
                  fx: Effects, rng: np.random.Generator) -> None:
    glitch = fx.glitch
    if glitch > 0.001:
        # 1) horizontal row tearing
        n_rows = int(glitch * H * 0.75)
        if n_rows > 0:
            rows = rng.choice(H, size=n_rows, replace=False)
            for r in rows:
                shift = int(rng.integers(-max(1, int(glitch * 14)), max(2, int(glitch * 14)) + 1))
                if shift:
                    ch[r] = np.roll(ch[r], shift)
                    fgpack[r] = np.roll(fgpack[r], shift)
                    bgpack[r] = np.roll(bgpack[r], shift)
                    fg[r] = np.roll(fg[r], shift, axis=0)
        # 2) corrupted blocks
        n_blocks = int(glitch * 26)
        for _ in range(n_blocks):
            bh = int(rng.integers(1, max(2, int(glitch * 7) + 1)))
            bw = int(rng.integers(2, max(3, int(glitch * 34) + 2)))
            y = int(rng.integers(0, max(1, H - bh)))
            x = int(rng.integers(0, max(1, W - bw)))
            jids = _junk_ids()
            cols = rng.integers(0, len(jids), size=bw)
            ch[y:y + bh, x:x + bw] = jids[cols]
            hot = int(rng.integers(0, 4))
            pal = [C.RED, C.CYAN, C.GOLD, C.MAGENTA, C.WHITE][hot]
            fg[y:y + bh, x:x + bw] = (pal >> 16) & 255, (pal >> 8) & 255, pal & 255
            fgpack[y:y + bh, x:x + bw] = pal
            bgpack[y:y + bh, x:x + bw] = C.INK if hot else C.RED_DEEP
        # 3) block noise
        n = int(glitch * 60)
        for _ in range(n):
            y = int(rng.integers(0, H))
            x = int(rng.integers(0, W))
            ln = int(rng.integers(1, 20))
            pal = [C.RED, C.CYAN, C.GOLD, C.PURPLE, C.WHITE, C.TERM_GREEN][int(rng.integers(0, 6))]
            jids = _junk_ids()
            ch[y, x:x + ln] = jids[rng.integers(0, len(jids), size=min(ln, W - x))]
            fgpack[y, x:x + ln] = pal
    # chroma split (cell level)
    if fx.chroma > 0.001:
        d = max(1, int(round(fx.chroma * 6)))
        fg[..., 0] = np.roll(fg[..., 0], d, axis=1)
        if fx.chroma > 0.5:
            fg[..., 2] = np.roll(fg[..., 2], -d, axis=1)


# --------------------------------------------------------------------------
# Rasteriser
# --------------------------------------------------------------------------
class Rasterizer:
    def __init__(self) -> None:
        self.glyphs = glyph_table()
        # subtle CRT scanline mask (every other pixel line slightly dimmed)
        scan = np.ones((PIX_H, 1, 1), dtype=np.float32)
        scan[1::2, 0, 0] = 0.88
        scan[::4, 0, 0] *= 0.97
        # vignette
        yy = np.linspace(-1.0, 1.0, PIX_H, dtype=np.float32)[:, None]
        xx = np.linspace(-1.0, 1.0, PIX_W, dtype=np.float32)[None, :]
        r = np.sqrt((xx * 0.98) ** 2 + (yy * 0.86) ** 2)
        vig = np.clip(1.06 - 0.30 * r ** 2.4, 0.0, 1.2).astype(np.float32)[..., None]
        self._vig = vig
        self.crt = (scan * vig).astype(np.float32)
        self._crt_strength = 1.0

    # -- core ------------------------------------------------------------
    def cell_arrays(self, canvas: Canvas) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        ch = np.array(canvas.ch, dtype=np.int32)
        fgpack = np.array(canvas.fg, dtype=np.int32)
        bgpack = np.array(canvas.bg, dtype=np.int32)
        return ch, fgpack, bgpack

    def rasterize(self, canvas: Canvas, rng: np.random.Generator | None = None) -> np.ndarray:
        """Canvas -> RGB uint8 frame (PIX_H, PIX_W, 3)."""
        fx = canvas.fx
        rng = rng or np.random.default_rng(0)
        ch, fgpack, bgpack = self.cell_arrays(canvas)
        fg = _unpack_rgb(fgpack)
        if fx.glitch > 0.001 or fx.chroma > 0.001:
            # protect the persistent chrome (status bars + lyric subtitle) from
            # cell-level corruption so the synced lyric text always stays legible
            keep = [0, 1, H - 3, H - 2, H - 1]
            saved = [(ch[r].copy(), fgpack[r].copy(), bgpack[r].copy(), fg[r].copy())
                     for r in keep]
            apply_cell_fx(ch, fg, fgpack, bgpack, fx, rng)
            for r, (sc, sfp, sbp, sfg) in zip(keep, saved):
                ch[r] = sc
                fgpack[r] = sfp
                bgpack[r] = sbp
                fg[r] = sfg
        bg = _unpack_rgb(bgpack)
        # composite
        masks = self.glyphs.masks()
        m = masks[ch]  # (H,W,CH,CW) uint8
        fge = fg[:, :, None, None, :].astype(np.uint16)
        bge = bg[:, :, None, None, :].astype(np.uint16)
        mm = m[..., None].astype(np.uint16)
        out16 = (fge * mm + bge * (np.uint16(255) - mm) + np.uint16(127)) // np.uint16(255)
        frame = out16.astype(np.uint8).transpose(0, 2, 1, 3, 4).reshape(PIX_H, PIX_W, 3)
        # pixel level effects
        if fx.scan > 0 or fx.vignette > 0 or fx.flash > 0 or fx.invert > 0 or fx.hue_shift:
            fr = frame.astype(np.float32)
            if fx.scan > 0 or fx.vignette > 0:
                if fx.scan > 0.001 and fx.vignette > 0.001:
                    fr *= self.crt
                elif fx.scan > 0.001:
                    fr *= self.crt / np.clip(self._vig, 1e-3, None)
                elif fx.vignette > 0.001:
                    fr *= self._vig
            if fx.hue_shift:
                fr = _apply_hue(fr, fx.hue_shift, fx.sat)
            elif fx.sat != 1.0:
                grey = fr.mean(axis=-1, keepdims=True)
                fr = grey + (fr - grey) * fx.sat
            if fx.invert > 0:
                inv = 255.0 - fr
                a = min(1.0, fx.invert)
                fr = fr * (1.0 - a) + inv * a
            if fx.flash > 0:
                fc = np.array([(fx.flash_color >> 16) & 255,
                               (fx.flash_color >> 8) & 255,
                               fx.flash_color & 255], dtype=np.float32)
                a = min(1.0, fx.flash)
                fr = fr * (1.0 - a) + fc * a
            frame = np.clip(fr, 0, 255).astype(np.uint8)
        # screen shake: shift the frame and let the uncovered border go black
        # (np.roll would wrap the image, which looks wrong for a violent jolt)
        if abs(fx.shake_x) > 0.5 or abs(fx.shake_y) > 0.5:
            frame = _shift_frame(frame, int(round(fx.shake_x)), int(round(fx.shake_y)))
        if abs(fx.roll) > 0.5:
            frame = np.roll(frame, int(fx.roll), axis=0)
        return frame


def _shift_frame(frame: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Translate an RGB frame by (dx, dy) pixels.

    The uncovered border is filled with edge pixels (not black holes / wrapped
    content), which keeps the "camera is being violently shaken" look clean.
    """
    h, w = frame.shape[:2]
    if dx == 0 and dy == 0:
        return frame
    px, py = abs(dx), abs(dy)
    padded = np.pad(frame, ((py, py), (px, px), (0, 0)), mode="edge")
    x0 = px - dx
    y0 = py - dy
    return padded[y0:y0 + h, x0:x0 + w]


def _apply_hue(fr: np.ndarray, dh: float, sat: float = 1.0) -> np.ndarray:
    """Cheap hue rotation using a YIQ-ish matrix, applied to float frame."""
    c = np.cos(dh)
    s = np.sin(dh)
    # rotation around the grey axis
    m = np.array([
        [0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715,
         0.072 - c * 0.072 + s * 0.928],
        [0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140,
         0.072 - c * 0.072 - s * 0.283],
        [0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715,
         0.072 + c * 0.928 + s * 0.072],
    ], dtype=np.float32)
    out = fr @ m.T
    if sat != 1.0:
        grey = out.mean(axis=-1, keepdims=True)
        out = grey + (out - grey) * sat
    return out


def scale_to_output(frame: np.ndarray) -> np.ndarray:
    """2000x1120 -> 1920x1080 using PIL (Lanczos) for PNG stills."""
    from PIL import Image

    im = Image.fromarray(frame, "RGB")
    return np.array(im.resize((C.OUT_W, C.OUT_H), Image.LANCZOS))
