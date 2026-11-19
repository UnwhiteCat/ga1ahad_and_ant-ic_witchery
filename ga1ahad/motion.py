"""Shared cinematic motion primitives for the Ga1ahad TUI film.

This module is the common vocabulary of the whole film: physics-style easing,
a 3D Braille camera rig, kinetic typography, film-language transitions and a
minimal conversation-window layout helper.  Everything is a pure function of
time (plus explicit seeds) so frames stay reproducible under parallel
rendering, and every helper is cheap enough to be called per frame.

Dependency direction: this module may import config / canvas / the standard
library / numpy only (no frame / cli / encode / verify imports).  The
conversation-window helper needs the project's official art.llm_dialog
contract, so it imports art lazily inside Dialog.__init__ (deferred, no
module-level cycle).

Conventions
-----------
- Cell coordinates are (row, col); a Braille viewport of rows x cols cells
  exposes 2*cols x 4*rows square dots.
- 3D camera space: +x right, +y up, +z into the screen.  Camera is the pose
  used to build a world->view transform (position + Euler yaw/pitch/roll).
- Colours are packed 0xRRGGBB ints (see config).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

from . import config as C

__all__ = [
    "clamp01", "lerp", "smooth01", "seg", "env",
    "ease_out_back", "ease_in_back", "ease_in_expo", "ease_out_expo",
    "ease_in_out_expo", "ease_out_quart", "spring", "impulse", "hit",
    "hit_env", "stagger", "hash01", "noise1", "fbm1", "loop_phase",
    "fade", "grad", "Camera", "project", "orbit", "draw_points",
    "draw_segments", "ring_segments", "sphere_segments", "grid_segments",
    "contour_segments", "mesh_segments", "star_points",
    "BIG_FONT", "big_text", "big_text_size", "spread_text", "stretch_text",
    "split_flap", "scramble_text", "type_text",
    "iris", "letterbox", "bg_gradient", "vignette", "grain", "feather_sprite",
    "punctuate", "shutter", "hairline", "corner_marks", "rule_row", "Dialog",
]

# --------------------------------------------------------------------------
# scalar helpers
# --------------------------------------------------------------------------
def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def smooth01(a: float, b: float, x: float) -> float:
    """Smoothstep on the [a, b] interval."""
    if a == b:
        return 0.0 if x < a else 1.0
    t = clamp01((x - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


def seg(t: float, start: float, end: float) -> float:
    """Clamped 0..1 progress through [start, end] (linear)."""
    if end <= start:
        return 1.0 if t >= start else 0.0
    return clamp01((t - start) / (end - start))


def env(t: float, start: float, end: float) -> float:
    """Smooth 0 -> 1 -> 0 envelope over [start, end]."""
    if end <= start:
        return 0.0
    x = (t - start) / (end - start)
    if x <= 0.0 or x >= 1.0:
        return 0.0
    return math.sin(math.pi * x) ** 1.5


def loop_phase(t: float, period: float) -> float:
    if period <= 0.0:
        return 0.0
    return (t / period) % 1.0


# --------------------------------------------------------------------------
# easing / spring physics
# --------------------------------------------------------------------------
def ease_out_back(u: float, k: float = 1.70158) -> float:
    u = clamp01(u) - 1.0
    return 1.0 + (k + 1.0) * u * u * u + k * u * u


def ease_in_back(u: float, k: float = 1.70158) -> float:
    u = clamp01(u)
    return (k + 1.0) * u * u * u - k * u * u


def ease_in_expo(u: float) -> float:
    u = clamp01(u)
    return 0.0 if u <= 0.0 else 2.0 ** (10.0 * u - 10.0)


def ease_out_expo(u: float) -> float:
    u = clamp01(u)
    return 1.0 if u >= 1.0 else 1.0 - 2.0 ** (-10.0 * u)


def ease_in_out_expo(u: float) -> float:
    u = clamp01(u)
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    if u < 0.5:
        return 0.5 * 2.0 ** (20.0 * u - 10.0)
    return 1.0 - 0.5 * 2.0 ** (-20.0 * u + 10.0)


def ease_out_quart(u: float) -> float:
    u = clamp01(u)
    return 1.0 - (1.0 - u) ** 4


def spring(u: float, freq: float = 3.2, damp: float = 0.30) -> float:
    """Damped spring settling 0 -> 1 with overshoot, normalized to hit 1 at u=1.

    u in [0, 1] is normalized time; freq is oscillation count and damp the
    decay rate.  Returns values that may slightly exceed 1.
    """
    u = clamp01(u)
    if u >= 1.0:
        return 1.0
    if u <= 0.0:
        return 0.0
    z = max(1e-4, damp)
    w = 2.0 * math.pi * freq
    osc = math.cos(w * u)
    amp = math.exp(-z * 6.0 * u)
    raw = 1.0 - amp * osc
    end = 1.0 - math.exp(-z * 6.0) * math.cos(w)
    return raw / end if abs(end) > 1e-4 else raw


def impulse(age: float, freq: float = 3.0, decay: float = 0.18) -> float:
    """Oscillating camera-hit response: 1 at age 0, decaying to 0 by ~6*decay."""
    if age < 0.0:
        return 0.0
    k = math.exp(-age / max(1e-4, decay))
    return k * math.cos(2.0 * math.pi * freq * age)


def hit(age: float, decay: float = 0.16) -> float:
    """Monotonic 1 -> 0 hit response (0 before the hit)."""
    if age < 0.0:
        return 0.0
    return math.exp(-age / max(1e-4, decay))


def hit_env(t: float, at: float, decay: float = 0.16) -> float:
    return hit(t - at, decay)


def stagger(i: int, n: int, u: float, spread: float = 0.5) -> float:
    """Item i of n starts later: per-item 0..1 progress."""
    if n <= 1:
        return clamp01(u)
    delay = (i / (n - 1)) * clamp01(spread)
    span = max(1e-4, 1.0 - clamp01(spread))
    return clamp01((u - delay) / span)


# --------------------------------------------------------------------------
# deterministic hash / noise
# --------------------------------------------------------------------------
def hash01(*parts: float) -> float:
    """Deterministic float in [0, 1) from any tuple of numbers."""
    h = 2166136261
    for v in parts:
        iv = (int(float(v) * 1009.0) ^ 0x9E3779B9) & 0xFFFFFFFF
        h = ((h ^ iv) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    h ^= h >> 15
    return (h & 0xFFFFFF) / 16777216.0


def noise1(x: float, seed: int = 0) -> float:
    """Smooth 1D value noise in [0, 1] (cubic interpolation)."""
    i = math.floor(x)
    f = x - i
    a = hash01(i, seed)
    b = hash01(i + 1, seed)
    s = f * f * (3.0 - 2.0 * f)
    return a + (b - a) * s


def fbm1(x: float, seed: int = 0, octaves: int = 3) -> float:
    """Fractal 1D noise in [0, 1]."""
    total = 0.0
    amp = 0.5
    norm = 0.0
    for o in range(max(1, octaves)):
        total += noise1(x * (2.0 ** o), seed + o * 17) * amp
        norm += amp
        amp *= 0.5
    return total / max(1e-9, norm)


# --------------------------------------------------------------------------
# colour helpers
# --------------------------------------------------------------------------
def fade(color: int, alpha: float, bg: int = C.INK) -> int:
    return C.mix(bg, color, clamp01(alpha))


def grad(top: int, bottom: int, u: float) -> int:
    return C.mix(top, bottom, clamp01(u))


# --------------------------------------------------------------------------
# 3D Braille camera rig
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Camera:
    """Camera pose; world -> view is R^T * (p - position)."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0      # radians, turn around +y
    pitch: float = 0.0    # radians, look up positive
    roll: float = 0.0     # radians, screen roll
    fov: float = 1.0      # 0.5 * fov = half-height in world units at z=1


def _camera_matrix(cam: Camera) -> np.ndarray:
    cy, sy = math.cos(cam.yaw), math.sin(cam.yaw)
    cp, sp = math.cos(cam.pitch), math.sin(cam.pitch)
    cr, sr = math.cos(cam.roll), math.sin(cam.roll)
    ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]])
    rz = np.array([[cr, -sr, 0.0], [sr, cr, 0.0], [0.0, 0.0, 1.0]])
    return ry @ rx @ rz


def _as_pts(pts) -> np.ndarray:
    arr = np.asarray(pts, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(1, 3)
    return arr.reshape(-1, 3)


def project(pts, cam: Camera, pw: int, ph: int):
    """Project world points to Braille viewport dots.

    Returns (px, py, depth) float arrays: px in dot units [0, pw), py in
    [0, ph) (y down, screen space), depth the camera-space z (positive in
    front of the camera).
    """
    p = _as_pts(pts)
    rel = p - np.array([cam.x, cam.y, cam.z])
    view = rel @ _camera_matrix(cam)
    z = view[:, 2]
    zz = np.where(z > 1e-4, z, 1e-4)
    focal = 0.5 * float(ph) * cam.fov
    px = pw * 0.5 + focal * view[:, 0] / zz
    py = ph * 0.5 - focal * view[:, 1] / zz
    return px, py, z


def orbit(pts, *, yaw: float = 0.0, pitch: float = 0.0, roll: float = 0.0,
          center=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Rotate world points around center (returns a new array)."""
    p = _as_pts(pts) - np.asarray(center, dtype=np.float64)
    R = _camera_matrix(Camera(yaw=yaw, pitch=pitch, roll=roll))
    return p @ R.T + np.asarray(center, dtype=np.float64)


def _colors(colors, n: int) -> np.ndarray:
    if isinstance(colors, (int, np.integer)):
        return np.full(n, int(colors), dtype=np.int64)
    arr = np.asarray(colors, dtype=np.int64).reshape(-1)
    if arr.size == n:
        return arr
    if arr.size == 1:
        return np.full(n, int(arr[0]), dtype=np.int64)
    return np.resize(arr, n)


def _depth_alpha(depth: np.ndarray, fog: float, zmin: float, zmax: float,
                 alpha: float) -> np.ndarray:
    u = np.clip((depth - zmin) / max(1e-6, (zmax - zmin)), 0.0, 1.0)
    a = fog + (1.0 - fog) * (1.0 - u)
    return np.clip(a * alpha, 0.0, 1.0)


def draw_points(br, pts, cam: Camera, colors, *, size: int = 1,
                fog: float = 0.6, alpha: float = 0.95,
                zmin: float = 0.4, zmax: float = 14.0) -> int:
    """Plot 3D points with depth fading.  Returns the number of plotted dots."""
    p = _as_pts(pts)
    n = len(p)
    if not n:
        return 0
    px, py, z = project(p, cam, br.cols * 2, br.rows * 4)
    alphas = _depth_alpha(z, fog, zmin, zmax, alpha)
    cols = _colors(colors, n)
    pw, ph = br.cols * 2, br.rows * 4
    dots = br.dots
    plotted = 0
    size = max(1, int(size))
    for i in range(n):
        a = alphas[i]
        if a <= 0.03 or z[i] <= 0.05:
            continue
        x = int(px[i])
        y = int(py[i])
        if not (0 <= x < pw and 0 <= y < ph):
            continue
        col = C.mix(C.INK, int(cols[i]), float(a))
        if size <= 1:
            dots[(x, y)] = col
            plotted += 1
        else:
            for oy in range(size):
                for ox in range(size):
                    xx, yy = x + ox, y + oy
                    if 0 <= xx < pw and 0 <= yy < ph:
                        dots[(xx, yy)] = col
                        plotted += 1
    return plotted


def draw_segments(br, segs, cam: Camera, color: int, *, alpha: float = 0.85,
                  fog: float = 0.6, zmin: float = 0.4, zmax: float = 14.0,
                  step: float = 0.6) -> int:
    """Draw 3D line segments (shape (M, 2, 3)) with depth fading."""
    arr = np.asarray(segs, dtype=np.float64)
    if arr.size == 0:
        return 0
    arr = arr.reshape(-1, 2, 3)
    px0, py0, z0 = project(arr[:, 0, :], cam, br.cols * 2, br.rows * 4)
    px1, py1, z1 = project(arr[:, 1, :], cam, br.cols * 2, br.rows * 4)
    mid = 0.5 * (z0 + z1)
    alphas = _depth_alpha(mid, fog, zmin, zmax, alpha)
    plotted = 0
    for i in range(len(arr)):
        if z0[i] <= 0.05 or z1[i] <= 0.05:
            continue
        a_i = float(alphas[i])
        if a_i <= 0.03:
            continue
        col = C.mix(C.INK, color, a_i)
        br.line(float(px0[i]), float(py0[i]), float(px1[i]), float(py1[i]),
                col, 0.92, step)
        plotted += 1
    return plotted


# -- procedural geometry ---------------------------------------------------
def ring_segments(radius: float, n: int = 64, *,
                  axes=(0, 1), center=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Closed 3D circle in the plane spanned by two axes (0=x, 1=y, 2=z)."""
    a, b = axes
    pts = np.zeros((n, 3), dtype=np.float64)
    ang = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    pts[:, a] = np.cos(ang) * radius
    pts[:, b] = np.sin(ang) * radius
    pts += np.asarray(center, dtype=np.float64)
    return np.stack([pts, np.roll(pts, -1, axis=0)], axis=1)


def sphere_segments(radius: float = 1.0, lat: int = 9, lon: int = 18) -> np.ndarray:
    """Wireframe sphere: latitude circles + longitude half-circles (y up)."""
    out = []
    for i in range(1, lat):
        th = math.pi * i / lat
        rr = math.sin(th) * radius
        yy = math.cos(th) * radius
        ang = np.linspace(0.0, 2.0 * math.pi, 48, endpoint=False)
        ring = np.stack([np.cos(ang) * rr, np.full_like(ang, yy),
                         np.sin(ang) * rr], axis=1)
        out.append(np.stack([ring, np.roll(ring, -1, axis=0)], axis=1))
    for j in range(lon):
        ph = 2.0 * math.pi * j / lon
        th = np.linspace(0.0, math.pi, 32)
        ring = np.stack([np.sin(th) * math.cos(ph) * radius,
                         np.cos(th) * radius,
                         np.sin(th) * math.sin(ph) * radius], axis=1)
        out.append(np.stack([ring[:-1], ring[1:]], axis=1))
    return np.concatenate(out, axis=0)


def grid_segments(nx: int, nz: int, *, dx: float = 1.0, dz: float = 1.0,
                  y_fn=None, center=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Planar/patch grid wireframe; y_fn(x, z) lifts it into a terrain."""
    cx, cy, cz = center
    xs = (np.arange(nx) - (nx - 1) / 2.0) * dx
    zs = (np.arange(nz) - (nz - 1) / 2.0) * dz
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    Y = np.zeros_like(X) if y_fn is None else np.vectorize(y_fn)(X, Z)
    P = np.stack([X + cx, Y + cy, Z + cz], axis=-1)
    segs = []
    if nx > 1:
        segs.append(np.stack([P[:-1, :, :], P[1:, :, :]], axis=2).reshape(-1, 2, 3))
    if nz > 1:
        segs.append(np.stack([P[:, :-1, :], P[:, 1:, :]], axis=2).reshape(-1, 2, 3))
    return np.concatenate(segs, axis=0) if segs else np.zeros((0, 2, 3))


def contour_segments(field, level: float, x0: float = -1.0, x1: float = 1.0,
                     z0: float = -1.0, z1: float = 1.0) -> np.ndarray:
    """Marching-squares contour of field (rows along z, cols along x).

    The resulting segments are 3D with height y = level, so a stack of levels
    renders as a contour terrain (use Camera/orbit for depth).
    """
    f = np.asarray(field, dtype=np.float64)
    if f.ndim != 2 or f.shape[0] < 2 or f.shape[1] < 2:
        return np.zeros((0, 2, 3))
    nz, nx = f.shape
    gx = np.linspace(x0, x1, nx)
    gz = np.linspace(z0, z1, nz)
    segs = []

    def interp(pa, pb, va, vb):
        denom = vb - va
        u = 0.5 if abs(denom) < 1e-12 else (level - va) / denom
        u = min(1.0, max(0.0, u))
        return pa + (pb - pa) * u

    for j in range(nz - 1):
        for i in range(nx - 1):
            v00 = f[j, i]
            v10 = f[j, i + 1]
            v01 = f[j + 1, i]
            v11 = f[j + 1, i + 1]
            idx = ((v00 > level) << 0) | ((v10 > level) << 1) \
                | ((v11 > level) << 2) | ((v01 > level) << 3)
            if idx in (0, 15):
                continue
            p00 = np.array([gx[i], level, gz[j]])
            p10 = np.array([gx[i + 1], level, gz[j]])
            p01 = np.array([gx[i], level, gz[j + 1]])
            p11 = np.array([gx[i + 1], level, gz[j + 1]])
            pts = []
            if ((idx ^ (idx >> 1)) & 1) != 0:
                pts.append(interp(p00, p10, v00, v10))
            if (((idx >> 1) ^ (idx >> 2)) & 1) != 0:
                pts.append(interp(p10, p11, v10, v11))
            if (((idx >> 2) ^ (idx >> 3)) & 1) != 0:
                pts.append(interp(p11, p01, v11, v01))
            if (((idx >> 3) ^ idx) & 1) != 0:
                pts.append(interp(p01, p00, v01, v00))
            for k in range(0, len(pts) - 1, 2):
                segs.append(np.stack([pts[k], pts[k + 1]], axis=0))
    return np.array(segs) if segs else np.zeros((0, 2, 3))


def mesh_segments(xs, zs, y_fn) -> np.ndarray:
    """Wireframe surface: y_fn(x, z) sampled on the given coordinates."""
    gx = np.asarray(xs, dtype=np.float64)
    gz = np.asarray(zs, dtype=np.float64)
    X, Z = np.meshgrid(gx, gz, indexing="ij")
    Y = np.vectorize(y_fn)(X, Z)
    P = np.stack([X, Y, Z], axis=-1)
    segs = []
    if P.shape[0] > 1:
        segs.append(np.stack([P[:-1, :, :], P[1:, :, :]], axis=2).reshape(-1, 2, 3))
    if P.shape[1] > 1:
        segs.append(np.stack([P[:, :-1, :], P[:, 1:, :]], axis=2).reshape(-1, 2, 3))
    return np.concatenate(segs, axis=0) if segs else np.zeros((0, 2, 3))


def star_points(n: int, seed: int = 0, *, radius: float = 1.0,
                depth: float = 6.0) -> np.ndarray:
    """Deterministic star/dust point cloud in a shell around the origin."""
    rng = random.Random(seed * 7919 + 11)
    pts = np.zeros((n, 3), dtype=np.float64)
    for i in range(n):
        z = rng.uniform(-1.0, 1.0)
        th = rng.uniform(0.0, 2.0 * math.pi)
        r = math.sqrt(max(0.0, 1.0 - z * z))
        pts[i] = (math.cos(th) * r * radius, z * radius,
                  math.sin(th) * r * radius * depth)
    return pts


# --------------------------------------------------------------------------
# kinetic typography: 5x7 block font
# --------------------------------------------------------------------------
_GLYPHS_SRC = {
    "A": (" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "),
    "C": (" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "),
    "D": ("#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"),
    "F": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "),
    "G": (" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ### "),
    "H": ("#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "I": (" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    "J": ("  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "),
    "K": ("#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "Q": (" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"),
    "R": ("#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    "S": (" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "V": ("#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "),
    "W": ("#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"),
    "X": ("#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"),
    "Y": ("#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    "0": (" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "),
    "1": ("  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    "2": (" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"),
    "3": ("#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "),
    "4": ("   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "),
    "5": ("#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "),
    "6": ("  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "),
    "7": ("#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "),
    "8": (" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "),
    "9": (" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "),
    ".": ("     ", "     ", "     ", "     ", "     ", "  ## ", "  ## "),
    ",": ("     ", "     ", "     ", "     ", "  ## ", "  ## ", " #   "),
    ":": ("     ", "  ## ", "  ## ", "     ", "  ## ", "  ## ", "     "),
    ";": ("     ", "  ## ", "  ## ", "     ", "  ## ", "  ## ", " #   "),
    "!": ("  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "),
    "?": (" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "),
    "'": ("  #  ", "  #  ", "     ", "     ", "     ", "     ", "     "),
    '"': (" # # ", " # # ", "     ", "     ", "     ", "     ", "     "),
    "-": ("     ", "     ", "     ", "#####", "     ", "     ", "     "),
    "+": ("     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "),
    "/": ("    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "),
    "%": ("#   #", "#  # ", "   # ", "  #  ", " #   ", "#  # ", "#   #"),
    "(": ("   # ", "  #  ", " #   ", " #   ", " #   ", "  #  ", "   # "),
    ")": (" #   ", "  #  ", "   # ", "   # ", "   # ", "  #  ", " #   "),
    "[": (" ### ", " #   ", " #   ", " #   ", " #   ", " #   ", " ### "),
    "]": (" ### ", "   # ", "   # ", "   # ", "   # ", "   # ", " ### "),
    "<": ("   # ", "  #  ", " #   ", "#    ", " #   ", "  #  ", "   # "),
    ">": (" #   ", "  #  ", "   # ", "    #", "   # ", "  #  ", " #   "),
    "_": ("     ", "     ", "     ", "     ", "     ", "     ", "#####"),
    "=": ("     ", "     ", "#####", "     ", "#####", "     ", "     "),
    "#": (" # # ", " # # ", "#####", " # # ", "#####", " # # ", " # # "),
    "*": ("     ", "#   #", " # # ", "  #  ", " # # ", "#   #", "     "),
    "&": (" ##  ", "#  # ", "#  # ", " ##  ", "#  # ", "#   #", " ## #"),
    "·": ("     ", "     ", "     ", "  #  ", "     ", "     ", "     "),
    "•": ("     ", "     ", " ##  ", " ##  ", "     ", "     ", "     "),
    "▲": ("  #  ", " ### ", "#####", "     ", "     ", "     ", "     "),
}
BIG_FONT = {k: tuple(rows) for k, rows in _GLYPHS_SRC.items()}
_FALLBACK_GLYPH = ("     ", " ### ", "  #  ", "  #  ", "  #  ", " ### ", "     ")


def big_text_size(text: str, scale: int = 1, spacing: int = 1) -> tuple[int, int]:
    """Output size of big_text: (width, height) in cells."""
    scale = max(1, int(scale))
    spacing = max(0, int(spacing))
    s = str(text).upper()
    if not s:
        return (0, 7 * scale)
    w = len(s) * 5 * scale + max(0, len(s) - 1) * spacing * scale
    return (w, 7 * scale)


def big_text(c, y: int, x: int, text: str, fg: int, *, scale: int = 1,
             spacing: int = 1, x1: int | None = None, align: str = "left",
             top: int | None = None, bottom: int | None = None,
             bg: int | None = None, block: str = "\u2588",
             banding: bool = False) -> tuple[int, int]:
    """Draw monumental 5x7 block typography.

    scale multiplies every font pixel into scale x scale cells (1 is a 7-row
    headline, 2 a 14-row monument).  top/bottom give a vertical colour ramp;
    align may be left / center / right relative to x1 (default canvas width).
    Returns (width, height).
    """
    scale = max(1, int(scale))
    spacing = max(0, int(spacing))
    wid, hei = big_text_size(text, scale, spacing)
    if not text:
        return wid, hei
    if x1 is None:
        x1 = c.w
    if align == "center":
        x = max(0, x + (x1 - x - wid) // 2)
    elif align == "right":
        x = max(0, x1 - wid)
    s = str(text).upper()
    cursor = x
    for ch in s:
        glyph = BIG_FONT.get(ch)
        if glyph is None:
            glyph = _FALLBACK_GLYPH if ch != " " else ("     ",) * 7
        for py, row in enumerate(glyph):
            col = fg
            if top is not None and bottom is not None:
                col = C.mix(top, bottom, py / 6.0)
            if banding and py % 2 == 1:
                col = C.scale(col, 0.82)
            for px, bit in enumerate(row):
                if bit != " ":
                    for sy in range(scale):
                        for sx in range(scale):
                            c.put(y + py * scale + sy, cursor + px * scale + sx,
                                  block, col, bg)
        cursor += 5 * scale + spacing * scale
    return wid, hei


def spread_text(s: str, gap: int = 1) -> str:
    """Wide-tracked text: 'ABC' -> 'A B C' (gap spaces)."""
    return (" " * max(0, int(gap))).join(str(s))


def stretch_text(s: str, width: int) -> str:
    """Justify s to exactly width cells by stretching spaces."""
    s = str(s)
    width = max(0, int(width))
    if len(s) >= width:
        return s[:width]
    words = s.split(" ")
    if len(words) <= 1:
        return s + " " * (width - len(s))
    gaps = len(words) - 1
    extra = width - len(s)
    base, rem = divmod(extra, gaps)
    parts = [words[0]]
    for i, w in enumerate(words[1:]):
        parts.append(" " * (1 + base + (1 if i < rem else 0)))
        parts.append(w)
    return "".join(parts)


_JUNK = "▪▫◼◻▰▱░▒▓█◆◇◈#@%&$*+=-_/|<>[]{}()0123456789ABCDEF"


def split_flap(s: str, progress: float, seed: float = 0.0) -> str:
    """Split-flap scramble that settles left to right as progress -> 1."""
    s = str(s)
    p = clamp01(progress)
    n = max(1, len(s))
    out = []
    for i, ch in enumerate(s):
        if ch == " ":
            out.append(" ")
            continue
        threshold = 0.82 * (i / n) + 0.18 * hash01(seed, i)
        if p >= threshold:
            out.append(ch)
        else:
            k = int(hash01(seed, i, p * 60.0) * len(_JUNK))
            out.append(_JUNK[k])
    return "".join(out)


def scramble_text(s: str, t: float, start: float = 0.0, settle: float = 0.35,
                  cps: float = 45.0, seed: float = 0.0) -> str:
    """Scramble that decodes over len(s)/cps + settle seconds."""
    dur = len(str(s)) / max(1e-3, cps) + max(0.0, settle)
    return split_flap(s, (t - start) / max(1e-3, dur), seed)


def type_text(s: str, t: float, start: float = 0.0, cps: float = 40.0) -> str:
    n = int(max(0.0, (t - start)) * max(1e-3, cps))
    return str(s)[:n]


# --------------------------------------------------------------------------
# film-language transitions
# --------------------------------------------------------------------------
def iris(c, cx: float, cy: float, radius: float, *, soft: float = 8.0,
         amount: float = 0.94) -> None:
    """Iris/spotlight mask: dim everything outside a circle in cell space."""
    W = c.w
    amount = clamp01(amount)
    r = max(0.0, float(radius))
    for yy in range(c.h):
        dy = (yy + 0.5 - cy) * 2.0
        if abs(dy) > r + soft:
            _dim_row(c, yy, 0, W, amount)
            continue
        rem = r * r - dy * dy
        if rem >= 0.0:
            half = math.sqrt(rem)
            x_lo = cx - half
            x_hi = cx + half
            if x_lo > soft + 1:
                _dim_row(c, yy, 0, int(x_lo - soft), amount)
            if x_hi < W - soft - 1:
                _dim_row(c, yy, int(x_hi + soft), W, amount)
            inner0, inner1 = int(x_lo), int(x_hi) + 1
            for xx in range(max(0, inner0 - 1), min(W, inner1 + 1)):
                d = math.hypot(xx + 0.5 - cx, dy)
                t = smooth01(r - soft, r + soft, d)
                if t > 0.0:
                    _dim_cell(c, yy, xx, amount * (1.0 - t))
        else:
            for xx in range(W):
                d = math.hypot(xx + 0.5 - cx, dy)
                t = smooth01(r - soft, r + soft, d)
                if t > 0.0:
                    _dim_cell(c, yy, xx, amount * (1.0 - t))


def _dim_cell(c, y: int, x: int, amount: float) -> None:
    if amount <= 0.0:
        return
    if not (0 <= y < c.h and 0 <= x < c.w):
        return
    if c.clip_enabled and not (c.clip_y0 <= y < c.clip_y1):
        return
    f = 1.0 - amount
    c.fg[y][x] = _mul(c.fg[y][x], f)
    c.bg[y][x] = _mul(c.bg[y][x], f)


def _dim_row(c, y: int, x0: int, x1: int, amount: float) -> None:
    if amount <= 0.0 or not (0 <= y < c.h):
        return
    if c.clip_enabled and not (c.clip_y0 <= y < c.clip_y1):
        return
    x0 = max(0, int(x0))
    x1 = min(c.w, int(x1))
    if x1 <= x0:
        return
    f = 1.0 - amount
    row_f = c.fg[y]
    row_b = c.bg[y]
    if f <= 0.02:
        row_f[x0:x1] = [0] * (x1 - x0)
        row_b[x0:x1] = [0] * (x1 - x0)
        return
    cache: dict[int, int] = {}
    for x in range(x0, x1):
        v = row_f[x]
        nv = cache.get(v)
        if nv is None:
            nv = cache[v] = _mul(v, f)
        row_f[x] = nv
        v = row_b[x]
        nv = cache.get(v)
        if nv is None:
            nv = cache[v] = _mul(v, f)
        row_b[x] = nv


def _mul(color: int, f: float) -> int:
    r = int(((color >> 16) & 255) * f)
    g = int(((color >> 8) & 255) * f)
    b = int((color & 255) * f)
    return (r << 16) | (g << 8) | b


def letterbox(c, ratio: float = 2.35, color: int = C.INK) -> tuple[int, int]:
    """Cinematic bars inside the content band; returns (top_rows, bottom_rows)."""
    top, bot = C.CONTENT_Y0, C.CONTENT_Y1
    height = bot - top
    width_px = c.w * C.CELL_W
    want_rows = int(round((width_px / max(0.5, ratio)) / C.CELL_H))
    bar = max(0, (height - want_rows) // 2)
    if bar > 0:
        c.fill(top, 0, bar, c.w, " ", C.TEXT, color)
        c.fill(bot - bar, 0, bar, c.w, " ", C.TEXT, color)
    return bar, bar


def bg_gradient(c, top_color: int, bottom_color: int,
                y0: int | None = None, y1: int | None = None) -> None:
    """Fill the content band with a vertical background gradient."""
    y0 = C.CONTENT_Y0 if y0 is None else y0
    y1 = C.CONTENT_Y1 if y1 is None else y1
    rows = max(1, y1 - y0 - 1)
    for yy in range(y0, y1):
        col = C.mix(top_color, bottom_color, (yy - y0) / rows)
        c.fill(yy, 0, 1, c.w, " ", C.TEXT, col)


_VIGNETTE_CACHE: dict[tuple[int, int], list[list[float]]] = {}


def vignette(c, amount: float = 0.5, power: float = 2.2) -> None:
    """Subtle optical corner falloff over the content band."""
    amount = clamp01(amount)
    if amount <= 0.0:
        return
    key = (c.w, c.h)
    prof = _VIGNETTE_CACHE.get(key)
    if prof is None:
        prof = []
        for yy in range(c.h):
            u = (yy + 0.5) / c.h * 2.0 - 1.0
            row = []
            for xx in range(c.w):
                v = (xx + 0.5) / c.w * 2.0 - 1.0
                d = min(1.0, math.hypot(u * 0.92, v * 0.86) / 1.4142)
                row.append(d ** power)
            prof.append(row)
        _VIGNETTE_CACHE[key] = prof
    y0, y1 = C.CONTENT_Y0, C.CONTENT_Y1
    for yy in range(y0, y1):
        row_f = c.fg[yy]
        row_b = c.bg[yy]
        p = prof[yy]
        for xx in range(c.w):
            f = 1.0 - amount * p[xx]
            if f > 0.995:
                continue
            row_f[xx] = _mul(row_f[xx], f)
            row_b[xx] = _mul(row_b[xx], f)


def grain(c, t: float, seed: int = 0, count: int = 160,
          color: int = C.TEXT_FAINT, amount: float = 0.10) -> None:
    """Sparse deterministic film grain dots over the content band."""
    rng = random.Random(int(t * 1000.0) ^ (seed * 2654435761))
    y0, y1 = C.CONTENT_Y0, C.CONTENT_Y1
    for _ in range(max(0, int(count))):
        yy = rng.randrange(y0, y1)
        xx = rng.randrange(c.w)
        if rng.random() < 0.55:
            c.bg[yy][xx] = C.mix(c.bg[yy][xx], color, amount * rng.random())
        else:
            c.fg[yy][xx] = C.mix(c.fg[yy][xx], color, amount * rng.random())


def feather_sprite(c, y: int, x: int, sp, *, feather: int = 5,
                   bg: int | None = None, tint: int | None = None,
                   tint_amt: float = 0.0, vertical: bool = False,
                   alpha: float = 1.0) -> None:
    """Blit a sprite with soft edges (no ugly rectangle around keyframes).

    Cells near the sprite border cross-fade their colours into the underlying
    background, and empty sprite cells inside the faded border also dissolve
    the existing canvas content; the centre of the image stays untouched.
    """
    feather = max(0, int(feather))
    h, w = sp.h, sp.w
    y0, y1 = max(0, y), min(c.h, y + h)
    x0, x1 = max(0, x), min(c.w, x + w)
    if y1 <= y0 or x1 <= x0:
        return
    tint_amt = clamp01(tint_amt)
    for yy in range(y0, y1):
        sy = yy - y
        for xx in range(x0, x1):
            sx = xx - x
            dy = min(sy, h - 1 - sy) if not vertical else 0
            dx = min(sx, w - 1 - sx)
            edge = dy if vertical else min(dy, dx)
            a = 1.0 if feather <= 0 else smooth01(0.0, float(feather), edge)
            a *= clamp01(alpha)
            gid = sp.ch[sy][sx]
            fg = sp.fg[sy][sx]
            bgs = sp.bg[sy][sx]
            if tint is not None and tint_amt > 0.0:
                fg = C.mix(fg, tint, tint_amt)
                bgs = C.mix(bgs, tint, tint_amt)
            under_fg = c.fg[yy][xx]
            under_bg = c.bg[yy][xx]
            if gid == 0:
                blend = a * 0.85
                c.bg[yy][xx] = C.mix(bgs if bg is None else bg, under_bg, blend)
                c.fg[yy][xx] = C.mix(under_fg, under_bg, blend * 0.5)
                continue
            c.ch[yy][xx] = gid
            c.fg[yy][xx] = C.mix(under_bg, fg, a)
            c.bg[yy][xx] = C.mix(under_bg, bgs, a)


def punctuate(c, age: float, *, flash: float = 0.0, glitch: float = 0.0,
              chroma: float = 0.0, shake: float = 0.0,
              decay: float = 0.16, flash_color: int = C.WHITE) -> None:
    """Short, decaying camera-hit punctuation (never a permanent filter)."""
    if age < 0.0:
        return
    k = math.exp(-age / max(1e-3, decay))
    if flash > 0.0:
        c.fx.flash = max(c.fx.flash, flash * k)
        c.fx.flash_color = flash_color
    if glitch > 0.0:
        c.fx.glitch = max(c.fx.glitch, glitch * k)
    if chroma > 0.0:
        c.fx.chroma = max(c.fx.chroma, chroma * k)
    if shake > 0.0:
        amp = shake * k
        c.fx.shake_x += amp * math.sin(age * 97.0)
        c.fx.shake_y += amp * 0.55 * math.cos(age * 71.0)


def shutter(c, t: float, start: float, dur: float, *, bands: int = 9,
            color: int = C.INK, hi: int = C.BORDER_HI) -> float:
    """Mechanical shutter/venetian wipe; returns 0..1 progress."""
    u = seg(t, start, start + max(1e-3, dur))
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        c.fill(C.CONTENT_Y0, 0, C.CONTENT_H, c.w, " ", C.TEXT, color)
        return 1.0
    top, height = C.CONTENT_Y0, C.CONTENT_H
    bands = max(1, int(bands))
    band_h = height / bands
    for i in range(bands):
        local = clamp01((u - i * (0.5 / bands)) / 0.65)
        if local <= 0.0:
            continue
        hh = max(1, int(band_h * local))
        if i % 2 == 0:
            yy = top + int(i * band_h)
        else:
            yy = top + int((i + 1) * band_h) - hh
        c.fill(max(top, yy), 0, min(height, hh), c.w, " ", C.TEXT, color)
        lead = yy if i % 2 == 0 else yy + hh - 1
        if top <= lead < top + height:
            c.hline(lead, 0, c.w, hi, None, "\u2500")
    return u


# --------------------------------------------------------------------------
# small layout language
# --------------------------------------------------------------------------
def hairline(c, y: int, x0: int, x1: int, color: int,
             ch: str = "\u2500") -> None:
    c.hline(y, max(0, x0), min(c.w, x1), color, None, ch)


def corner_marks(c, y0: int, x0: int, y1: int, x1: int, color: int,
                 size: int = 3) -> None:
    """Viewfinder brackets at the four corners of a rect."""
    for (yy, xx, dy, dx) in ((y0, x0, 1, 1), (y0, x1 - 1, 1, -1),
                             (y1 - 1, x0, -1, 1), (y1 - 1, x1 - 1, -1, -1)):
        c.hline(yy, xx, xx + dx * size, color, None, "\u2500")
        c.vline(xx, yy, yy + dy * size, color, None, "\u2502")


def rule_row(c, y: int, label: str, color: int, *, fg: int | None = None,
             x0: int = 0, x1: int | None = None,
             rule_color: int | None = None) -> None:
    """Centred small-caps label flanked by hairlines."""
    x1 = c.w if x1 is None else x1
    lab = f" {label} " if label else ""
    lx = x0 + max(0, (x1 - x0 - len(lab)) // 2)
    rc = rule_color if rule_color is not None else color
    c.hline(y, x0, max(x0, lx - 1), rc, None, "\u2500")
    c.hline(y, min(x1, lx + len(lab) + 1), x1, rc, None, "\u2500")
    if lab:
        c.text(y, lx, lab, fg if fg is not None else color, None)


# --------------------------------------------------------------------------
# conversation window layout (the official art.llm_dialog contract)
# --------------------------------------------------------------------------
class Dialog:
    """Sparse editorial layout inside the ONE left portrait conversation window.

    Internally calls the project's official art.llm_dialog helper (lazily
    imported so this module keeps its low-level dependency direction), which
    enforces the 9:16 portrait aspect, the 1/1/1 margins and the dialog mask,
    and guarantees nothing leaks onto the right animation stage.

    Rows passed to the helpers are relative to the window: row 0 is the title
    bar; the body is rows 1..h-2.  Available for layout: self.left (first body
    column), self.width (usable body width).
    """

    def __init__(self, c, y: int, x: int, h: int, w: int, title: str = "",
                 *, right: str = "", accent: int = C.CYAN_DIM,
                 bg: int | None = None, fg: int = C.TEXT,
                 style: str = "rounded", shadow: bool = True) -> None:
        from . import art
        self.c = c
        self.bg = bg if bg is not None else C.mix(C.PANEL, C.INK, 0.45)
        self.accent = accent
        self.fg = fg
        self.rect = art.llm_dialog(c, y, x, h, w, title, bg=self.bg,
                                   border=accent, style=style, shadow=shadow,
                                   right=right, title_fg=C.TEXT_HI,
                                   fg=fg)
        self.y, self.x, self.h, self.w = self.rect
        self.left = self.x + 3
        self.width = self.w - 6

    def text(self, row: int, s: str, color: int, *, bold: bool = False,
             x: int | None = None, bg: int | None = None) -> int:
        return self.c.text(self.y + row, self.x + 3 if x is None else self.x + x,
                           str(s)[: self.width], color,
                           self.bg if bg is None else bg, bold=bold)

    def label(self, row: int, s: str, color: int | None = None) -> None:
        """Dim small-caps label at the left body edge."""
        self.text(row, str(s).upper(), color if color is not None else C.TEXT_DIM,
                  bold=True)

    def rule(self, row: int, label: str = "", color: int | None = None) -> None:
        rc = color if color is not None else C.mix(self.bg, self.accent, 0.55)
        lab = f" {label} " if label else ""
        yy = self.y + row
        if lab:
            lx = self.x + max(2, (self.w - len(lab)) // 2)
            self.c.hline(yy, self.x + 1, max(self.x + 1, lx - 1), rc, self.bg, "\u2500")
            self.c.hline(yy, min(self.x + self.w - 1, lx + len(lab)),
                         self.x + self.w - 1, rc, self.bg, "\u2500")
            self.c.text(yy, lx, lab, C.mix(rc, C.WHITE, 0.25), self.bg)
        else:
            self.c.hline(yy, self.x + 2, self.x + self.w - 2, rc, self.bg, "\u2500")

    def message(self, row: int, text: str, color: int, *, tag: str = "",
                tag_color: int | None = None, max_rows: int = 6) -> int:
        """Speaker-tag + wrapped body; returns the row after the block."""
        from .canvas import wrap
        yy = row
        if tag:
            self.c.text(self.y + yy, self.x + 3, tag[-self.width:],
                        tag_color if tag_color is not None else color,
                        self.bg, bold=True)
            yy += 1
        for line in wrap(str(text), self.width)[:max_rows]:
            if yy >= self.h - 2:
                break
            self.c.text(self.y + yy, self.x + 3, line, color, self.bg)
            yy += 1
        return yy + 1

    def footer(self, row: int, s: str, *, color: int = C.TEXT_FAINT) -> None:
        yy = min(self.y + self.h - 2, self.y + row)
        self.c.text(yy, self.x + 3, str(s)[: self.width], color, self.bg)

    def cursor(self, row: int, col: int, t: float, color: int,
               rate: float = 2.4) -> None:
        phase = (t * rate) % 1.0
        self.c.put(self.y + row, self.x + 3 + col,
                   "\u2588" if phase < 0.55 else " ", color, self.bg)
