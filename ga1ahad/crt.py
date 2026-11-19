"""Deliberate CRT output stage for the MP4 render path.

raster.py already bakes a subtle scanline/vignette mask into every frame.
This module adds the *strong* CRT look that is applied only when an MP4 is
generated: the internal 2000x1120 raster is resampled through slightly
barrel-curved glass in a single bilinear pass, then bloom, RGB convergence
error, scanlines, vignette, a rounded bezel, a rolling refresh band, mains
flicker and phosphor grain are composited at the final 1920x1080 resolution.
The curvature and rounded bezel are deliberately capped so the visible screen
edge and the four corners stay within 1 % of the frame width/height.

Everything is a pure function of the frame timestamp t (the grain seed and
the flicker/band phase derive from it), so parallel segment renders stay
deterministic and seam-free.  crt.py depends only on config plus
numpy/Pillow and is consumed by frame.Renderer.output_frame_at (used by
encode._segment_worker and the still/sheet preview commands).

Enable/disable: render applies the stage by default; pass --no-crt or
--crt-strength 0 (or set GA1AHAD_CRT=0) for the flat raster look.
png --crt / sheet --crt preview the exact same filter.
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageFilter

from . import config as C

CRT_ENV = "GA1AHAD_CRT"
STRENGTH_MAX = 2.0

# Filter constants, all scaled by the requested strength (1.0 = the default
# look).  Kept together so the look can be tuned without touching the maths.
# The barrel coefficient is capped (see __init__) so the curved screen edge
# and the four corners stay inside 1 % of the frame width/height: at 1920x1080
# k=0.009 puts the worst horizontal inset at ~17 px (0.9 % of W) and the worst
# vertical inset at ~10 px (0.9 % of H).  Do not raise it past 0.01 without
# changing that contract (verify.py checks it).
CURVATURE = 0.009          # barrel coefficient of the glass
SCAN_DARK = 0.22           # extra darkening of every odd output line
SCAN_EVEN = 0.04           # slight darkening of the even lines too
VIGNETTE = 0.32            # corner falloff
BEZEL_RADIUS = 10.0        # rounded screen-corner radius, px at 1080p (<= 1 %)
GAIN = 0.20                # brightness compensation for scanlines/vignette
BLOOM_GAIN = 0.8           # additive glow from the bright pass
BLOOM_FLOOR = 42.0         # bright-pass threshold (0..255)
CHROMA_SHIFT = 2           # RGB convergence error, px at 1080p
GRAIN = 2.2                # additive luma grain sigma (0..255)
BAND_GAIN = 0.05           # rolling refresh band brightness
BAND_SPEED = 0.055         # band sweep, screen heights per second
BAND_SIGMA = 80.0          # band thickness, px
FLICKER_SLOW = 0.012       # mains-hum style brightness ripple
FLICKER_FAST = 0.005


def _clamp(value: float) -> float:
    return min(STRENGTH_MAX, max(0.0, float(value)))


_ENV_OFF = {"0", "off", "false", "no", "none"}
_ENV_ON = {"on", "true", "yes"}


def _env_strength() -> float | None:
    """GA1AHAD_CRT as a strength (0..2), accepting on/off words too."""
    raw = os.environ.get(CRT_ENV, "").strip().lower()
    if not raw:
        return None
    if raw in _ENV_OFF:
        return 0.0
    if raw in _ENV_ON:
        return _clamp(C.CRT_STRENGTH)
    try:
        return _clamp(float(raw))
    except ValueError:
        return None


def resolve_strength(enabled: bool | None, strength: float | None, *,
                     default: float, use_env: bool = True) -> float:
    """Resolve the CLI --crt/--no-crt + --crt-strength pair.

    Precedence: explicit --no-crt > explicit --crt-strength > explicit --crt >
    GA1AHAD_CRT (only when use_env) > default (1.0 for render, 0.0 for
    still/sheet previews).  Stills pass use_env=False so the env default only
    affects the MP4 render path.
    """
    if enabled is False:
        return 0.0
    if strength is not None:
        return _clamp(strength)
    if enabled is True:
        return _clamp(C.CRT_STRENGTH)
    if use_env:
        env = _env_strength()
        if env is not None:
            return env
    return _clamp(default)


class CRTFilter:
    """Curved-glass CRT compositor for 2000x1120 -> 1920x1080 frames.

    The instance precomputes the inverse curvature map, the static
    scanline/vignette/bezel mask and the per-row refresh-band falloff, so
    apply() is a handful of vectorised numpy passes per frame.
    """

    def __init__(self, strength: float = C.CRT_STRENGTH,
                 width: int = C.OUT_W, height: int = C.OUT_H) -> None:
        self.strength = _clamp(strength)
        s = self.strength
        self.w, self.h = width, height
        self.gain = 1.0 + GAIN * s
        self.bloom_gain = BLOOM_GAIN * s
        self.chroma = int(round(CHROMA_SHIFT * s))
        self.grain = GRAIN * s
        # curvature/bezel are capped at the default strength so the 1 % frame
        # contract also holds for --crt-strength > 1
        cap = min(1.0, s)
        self._build_warp(CURVATURE * cap)
        self._build_mask(VIGNETTE * s, BEZEL_RADIUS * cap)
        self._rows = np.linspace(0.0, height - 1.0, height,
                                 dtype=np.float32)[:, None]

    # -- construction ----------------------------------------------------
    def _build_warp(self, k: float) -> None:
        """Inverse barrel map: output pixel -> internal 2000x1120 sample."""
        src_w, src_h = C.PIX_W, C.PIX_H
        xs = np.linspace(-1.0, 1.0, self.w, dtype=np.float32)[None, :]
        ys = np.linspace(-1.0, 1.0, self.h, dtype=np.float32)[:, None]
        radius2 = xs * xs + ys * ys
        curve = 1.0 + k * radius2
        sx = (xs * curve + 1.0) * 0.5 * (src_w - 1)
        sy = (ys * curve + 1.0) * 0.5 * (src_h - 1)
        x0 = np.floor(sx).astype(np.int32)
        y0 = np.floor(sy).astype(np.int32)
        wx = (sx - x0).astype(np.float32)
        wy = (sy - y0).astype(np.float32)
        inside = ((x0 >= 0) & (x0 < src_w - 1)
                  & (y0 >= 0) & (y0 < src_h - 1)).astype(np.float32)
        x0 = np.clip(x0, 0, src_w - 2)
        y0 = np.clip(y0, 0, src_h - 2)
        self._base = (y0 * src_w + x0).astype(np.int32)
        self._w00 = (1.0 - wx) * (1.0 - wy) * inside
        self._w01 = wx * (1.0 - wy) * inside
        self._w10 = (1.0 - wx) * wy * inside
        self._w11 = wx * wy * inside

    def _build_mask(self, vignette: float, radius: float) -> None:
        h, w = self.h, self.w
        scan = np.ones((h, 1, 1), dtype=np.float32)
        scan[1::2] *= 1.0 - SCAN_DARK * self.strength
        scan[::2] *= 1.0 - SCAN_EVEN * self.strength
        yy = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
        xx = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
        radius2 = xx * xx + yy * yy
        vig = np.clip(1.0 - vignette * (radius2 * 0.5) ** 1.15,
                      0.0, 1.0)[..., None].astype(np.float32)
        # rounded-rectangle screen mask (anti-aliased over ~1.5 px)
        gy, gx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = (w - 1) * 0.5, (h - 1) * 0.5
        qx = np.abs(gx - cx) - (w * 0.5 - radius)
        qy = np.abs(gy - cy) - (h * 0.5 - radius)
        dist = np.sqrt(np.maximum(qx, 0.0) ** 2
                       + np.maximum(qy, 0.0) ** 2) - radius
        bezel = np.clip(1.0 - dist / 1.5, 0.0, 1.0).astype(np.float32)[..., None]
        self._static = (scan * vig * bezel).astype(np.float32)

    # -- frame transform -------------------------------------------------
    def _warp(self, source: np.ndarray) -> np.ndarray:
        out = np.empty((self.h, self.w, 3), dtype=np.float32)
        src_w = C.PIX_W
        base = self._base
        for channel in range(3):
            plane = np.ascontiguousarray(source[..., channel]).ravel()
            out[..., channel] = (
                np.take(plane, base) * self._w00
                + np.take(plane, base + 1) * self._w01
                + np.take(plane, base + src_w) * self._w10
                + np.take(plane, base + src_w + 1) * self._w11)
        return out

    def _grain(self, t: float) -> np.ndarray:
        """Half-resolution gaussian grain, bilinearly upsampled (pure in t)."""
        # millisecond seed: distinct for every frame at any render fps, still
        # a pure function of t
        frame = int(round(t * 1000.0))
        rng = np.random.default_rng((frame * 2654435761) & 0xFFFFFFFF)
        small = rng.standard_normal((self.h // 2, self.w // 2),
                                    dtype=np.float32) * self.grain
        im = Image.fromarray(small, mode="F").resize((self.w, self.h),
                                                     Image.BILINEAR)
        return np.asarray(im, dtype=np.float32)

    def apply(self, frame: np.ndarray, t: float) -> np.ndarray:
        """Internal PIX_H x PIX_W frame -> CRT-filtered OUT_H x OUT_W frame."""
        s = self.strength
        if s <= 0.0:
            return np.asarray(Image.fromarray(frame).resize((self.w, self.h),
                                                            Image.LANCZOS),
                              dtype=np.uint8)
        glow = self._glow(frame).astype(np.float32)
        np.maximum(glow, BLOOM_FLOOR, out=glow)
        glow -= BLOOM_FLOOR
        base = frame.astype(np.float32) * self.gain
        fr = self._warp(base)
        fr += glow * self.bloom_gain
        d = self.chroma
        if d:
            # RGB convergence error: red lands right of blue at the edges
            red = np.pad(fr[..., 0], ((0, 0), (d, d)), mode="edge")
            blue = np.pad(fr[..., 2], ((0, 0), (d, d)), mode="edge")
            fr[..., 0] = red[:, :self.w]
            fr[..., 2] = blue[:, 2 * d:]
        # grain before the mask so it is scanline-modulated and never leaks
        # outside the curved glass / bezel
        fr += self._grain(t)[..., None]
        fr *= self._static
        pos = ((t * BAND_SPEED) % 1.0) * self.h
        fr *= (1.0 + BAND_GAIN * s
               * np.exp(-0.5 * ((self._rows - pos) / BAND_SIGMA) ** 2))[..., None]
        fr *= 1.0 + s * (FLICKER_SLOW * np.sin(2.0 * np.pi * 0.7 * t)
                         + FLICKER_FAST * np.sin(2.0 * np.pi * 5.3 * t + 1.3))
        return np.clip(fr, 0.0, 255.0).astype(np.uint8)

    def _glow(self, frame: np.ndarray) -> np.ndarray:
        """Shared Pillow bloom: keep the CPU and GPU paths visually aligned."""
        small = Image.fromarray(frame).resize((self.w // 4, self.h // 4),
                                             Image.BOX)
        small = small.filter(ImageFilter.GaussianBlur(2.2))
        return np.asarray(small.resize((self.w, self.h), Image.BILINEAR))

    def close(self) -> None:
        """CPU filter owns no external resources."""


def create_filter(strength: float, backend: str = "cpu", **kwargs) -> CRTFilter:
    if backend == "cpu":
        return CRTFilter(strength, **kwargs)
    if backend == "gpu":
        from .crt_gpu import GPUCRTFilter
        return GPUCRTFilter(strength, **kwargs)
    raise ValueError(f"unknown CRT backend: {backend}")


def resolve_backend(backend: str, strength: float, *, verbose: bool = True) -> str:
    """Probe once before workers start. Explicit GPU requests never fall back."""
    if backend not in {"auto", "cpu", "gpu"}:
        raise ValueError(f"unknown CRT backend: {backend}")
    if strength <= 0:
        if backend == "gpu":
            raise ValueError("--backend gpu requires CRT; remove --no-crt or use --backend cpu")
        return "cpu"
    if backend == "cpu":
        return backend
    try:
        flt = create_filter(strength, "gpu")
        try:
            # Exercise shader execution/readback too, rather than trusting context creation.
            flt.apply(np.zeros((C.PIX_H, C.PIX_W, 3), dtype=np.uint8), 0.0)
            if verbose:
                import sys
                print(f"[render] GPU CRT: {flt.device}", file=sys.stderr)
        finally:
            flt.close()
        return "gpu"
    except Exception as exc:
        if backend == "gpu":
            raise RuntimeError(f"GPU CRT unavailable: {exc}") from exc
        if verbose:
            import sys
            print(f"[render] GPU CRT unavailable; using CPU: {exc}", file=sys.stderr)
        return "cpu"
