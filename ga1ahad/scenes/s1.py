"""Scene 1 -- CLI TRAINING GROUND / ANCESTOR BABBLE  (00:17.540 - 00:40.640).

A cinematic rewrite: the stage is one living latent-space projection field, not a
dashboard.  Shot list (absolute times, cues 1-8):

  17.540 - 27.580  LATENT FIELD   a contour terrain of stacked iso-lines under a
                                  tilted attractor halo; one sparse training
                                  session window on the left.  At 23.510 an amber
                                  light tide floods the cyan space (the operator
                                  seizes the write lock); at 26.060 the basin
                                  decodes a face that surfaces and dissolves.
  27.580 - 28.960  ROLLBACK       the field tears horizontally like glass,
                                  collapses onto a line, a red shutter slams and
                                  weight particles scatter with damped recoil.
  28.960 - 31.050  ACCELERATE     radial compute-grid streaks accelerate.
  31.050 - 31.930  THE BREATH     ~85% black: one slow breathing ring + cursor.
                                  No text, no noise, the held silence.
  31.930 - 35.690  REASSEMBLE     the 4-shot x 11-frame argument atlas, cold/warm
                                  rim light, hard cuts; the left window quietly
                                  carries proto-0's first coherent line.
  35.690 - 40.640  THE FORK       a glowing trunk is torn into a cyan (main) and
                                  a copper (fork) rail; at 40.640 the split severs
                                  the whole frame down the middle (match cut S2).

Every human <-> LLM exchange lives in ONE portrait 9:16 window on the left
(art.llm_dialog through motion.Dialog).  draw() is a pure function of t.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache

import numpy as np

from .. import config as C
from .. import motion as M
from ..assets import camera_sprite
from ..canvas import wrap
from .base import Scene

# ---------------------------------------------------------------------------
# Beat table.  Cue starts are read from self.cues (VTT SSOT) at runtime; only
# non-lyric staging beats are constants here.
# ---------------------------------------------------------------------------
FORK_T = 35.690            # instrumental break: the trunk starts to tear
ARG_POSES = 11             # motion-interpolated poses per atlas shot
ARG_SHOTS = 4
# Shot cuts relative to the "Reassemble" cue start (31.930).
ARG_CUTS = (0.0, 0.670, 1.570, 2.653, 3.760)
# Pose interpolation window per shot (relative to cue start).
ARG_GESTURES = ((0.030, 0.620), (0.710, 1.500), (1.600, 2.560), (2.800, 3.203))
ARG_SLAM = 3.203           # 35.133 -- the hard gesture that ends the argument
ARG_WIN_FROM = 1.570       # 33.500 -- the observer window enters on cut 3

LEVELS = 7
HORIZON_FOV = 0.86
SPEAKERS = (0, 0, 1, 1, 1, 0, 1, 1)   # 0 = operator A, 1 = operator B per cue


# ---------------------------------------------------------------------------
# Argument atlas access (cached)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _argument_atlas():
    from PIL import Image

    with Image.open(C.ROOT / "assets" / "s1-argument.webp") as sheet:
        return sheet.convert("RGB")


@lru_cache(maxsize=64)
def _argument_pose(shot: int, pose: int):
    atlas = _argument_atlas()
    w = atlas.width // ARG_POSES
    h = atlas.height // ARG_SHOTS
    return atlas.crop((pose * w, shot * h, (pose + 1) * w, (shot + 1) * h))


def _argument_still(shot: int, pose: float):
    from PIL import Image

    before = max(0, min(ARG_POSES - 1, int(pose)))
    after = min(ARG_POSES - 1, before + 1)
    frac = pose - before
    if frac > 1e-3 and after != before:
        return Image.blend(_argument_pose(shot, before),
                           _argument_pose(shot, after), frac)
    return _argument_pose(shot, before)


# ---------------------------------------------------------------------------
# local drawing helpers
# ---------------------------------------------------------------------------
def _wrap(text: str, width: int) -> list[str]:
    return wrap(str(text), max(1, width)) or [""]


def _geom(br, segs, cam, color: int, *, alpha: float = 0.95, fog: float = 0.18,
          zmin: float = 1.0, zmax: float = 36.0, step: float = 0.7,
          tide_py: float | None = None, tide_color: int = C.AMBER,
          crest_color: int = C.AMBER_HI, crest_hot: float = 1.0) -> int:
    """Project, screen-cull and draw 3D segments into a braille viewport.

    Optional tide_py recolours everything below a rising screen line (dot
    space) to the flood colour, with a hot crest band at the waterline.
    """
    arr = np.asarray(segs, dtype=np.float64)
    if arr.size == 0:
        return 0
    arr = arr.reshape(-1, 2, 3)
    pw, ph = br.cols * 2, br.rows * 4
    px0, py0, z0 = M.project(arr[:, 0, :], cam, pw, ph)
    px1, py1, z1 = M.project(arr[:, 1, :], cam, pw, ph)
    mid = 0.5 * (z0 + z1)
    u = np.clip((mid - zmin) / max(1e-6, zmax - zmin), 0.0, 1.0)
    alphas = (fog + (1.0 - fog) * (1.0 - u)) * alpha
    lo_x = np.minimum(px0, px1)
    hi_x = np.maximum(px0, px1)
    lo_y = np.minimum(py0, py1)
    hi_y = np.maximum(py0, py1)
    ok = ((z0 > 0.35) & (z1 > 0.35) & (alphas > 0.030)
          & (hi_x >= -6) & (lo_x <= pw + 6) & (hi_y >= -6) & (lo_y <= ph + 6))
    idx = np.nonzero(ok)[0]
    if idx.size == 0:
        return 0
    py_mid = 0.5 * (py0 + py1)
    for i in idx:
        a = float(alphas[i])
        col = C.mix(C.INK, color, a)
        if tide_py is not None:
            fy = float(py_mid[i])
            fl = M.smooth01(tide_py - 16.0, tide_py + 16.0, fy)
            if fl > 0.0:
                col = C.mix(col, C.mix(C.INK, tide_color, a), fl)
            crest = max(0.0, 1.0 - abs(fy - tide_py) / 15.0) * crest_hot
            if crest > 0.02:
                col = C.mix(col, C.mix(C.INK, crest_color, a), crest * 0.9)
        br.line(float(px0[i]), float(py0[i]), float(px1[i]), float(py1[i]),
                col, 0.95, step)
    return int(idx.size)


def _circle_segments(r: float, n: int = 64, *, cx: float = 0.0, cy: float = 0.0,
                     cz: float = 0.0, flat: float = 0.35, tilt: float = 0.0,
                     spin: float = 0.0):
    """A 3D ring (halo seen slightly edge-on) as closed segments."""
    th = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False) + spin
    pts = np.stack([np.cos(th) * r + cx, np.sin(th) * r * flat + cy,
                    np.zeros(n) + cz], axis=1)
    if abs(tilt) > 1e-6:
        pts = M.orbit(pts, pitch=tilt, center=(cx, cy, cz))
    return np.stack([pts, np.roll(pts, -1, axis=0)], axis=1)


def _edge_vignette(c, amount: float = 0.4, cols: int = 16,
                   rows: int = 6) -> None:
    """Cheap optical corner falloff: darken only the outer frame band."""
    y0, y1 = C.CONTENT_Y0, C.CONTENT_Y1
    xs = range(0, c.w)
    for y in range(y0, y1):
        dy = min(y - y0, y1 - 1 - y) / max(1.0, rows)
        ky = min(1.0, dy)
        rf = c.fg[y]
        rb = c.bg[y]
        for x in xs:
            dx = min(x, c.w - 1 - x) / max(1.0, cols)
            k = max(0.0, 1.0 - min(dx, ky)) ** 1.4 * amount
            if k <= 0.004:
                continue
            f = 1.0 - k
            rf[x] = C.scale(rf[x], f)
            rb[x] = C.scale(rb[x], f)


def _feather_edges(c, y: int, x: int, h: int, w: int, feather: int,
                   amount: float = 0.9) -> None:
    """Darken canvas cells near the rect border (soft image edge)."""
    feather = max(1, int(feather))
    for k in range(feather):
        a = amount * (1.0 - k / feather) ** 1.6
        yy0, yy1 = y + k, y + h - 1 - k
        if yy0 >= yy1:
            break
        for xx in range(x, x + w):
            c.bg[yy0][xx] = C.mix(c.bg[yy0][xx], C.BLACK, a)
            c.fg[yy0][xx] = C.mix(c.fg[yy0][xx], C.BLACK, a)
            c.bg[yy1][xx] = C.mix(c.bg[yy1][xx], C.BLACK, a)
            c.fg[yy1][xx] = C.mix(c.fg[yy1][xx], C.BLACK, a)
    for k in range(min(feather, w // 2)):
        a = amount * (1.0 - k / feather) ** 1.6
        xx0, xx1 = x + k, x + w - 1 - k
        for yy in range(y + k, y + h - k):
            c.bg[yy][xx0] = C.mix(c.bg[yy][xx0], C.BLACK, a)
            c.fg[yy][xx0] = C.mix(c.fg[yy][xx0], C.BLACK, a)
            c.bg[yy][xx1] = C.mix(c.bg[yy][xx1], C.BLACK, a)
            c.fg[yy][xx1] = C.mix(c.fg[yy][xx1], C.BLACK, a)


def _corrupt(text: str, amount: float, seed: int, t: float) -> str:
    """Deteriorated model output (deterministic stutter / noise glyphs)."""
    if amount <= 0.01:
        return text
    junk = "\u2593\u2592\u2591#@%&\u00a7\u00a5\u00a4\u00a6~^"
    rng = random.Random(seed * 7919 + int(t * 21.0) * 131)
    out: list[str] = []
    for ch in text:
        if ch not in " ." and rng.random() < amount * 0.5:
            r = rng.random()
            if r < 0.38:
                out.append(rng.choice(junk))
            elif r < 0.66:
                out.append(ch)
                out.append(ch)
            else:
                out.append(rng.choice("-\u00b7\u2026"))
        else:
            out.append(ch)
    return "".join(out)[: len(text) + 6]


def _projection_points(name: str, crop, w: int, h: int, *,
                       thresh: float = 0.22, maxpts: int = 2600,
                       seed: int = 0) -> list[tuple[int, int, float, float]]:
    """Sample a keyframe into a sparse dot cloud for 'projection ghost' looks.

    Returns (x, y, luminance, phase) tuples in a w x h dot grid; the phase is a
    deterministic per-dot twinkle offset so the projection feels alive.
    """
    from PIL import Image

    from ..assets import keyframe

    img = keyframe(name).convert("L")
    W0, H0 = img.size
    img = img.crop((int(crop[0] * W0), int(crop[1] * H0),
                    int(crop[2] * W0), int(crop[3] * H0)))
    img = img.resize((w, h), Image.LANCZOS)
    arr = np.asarray(img).astype(np.float32) / 255.0
    ys, xs = np.nonzero(arr > thresh)
    if len(xs) > maxpts:
        lums = arr[ys, xs]
        keep = np.argsort(-lums)[:maxpts]
        xs, ys = xs[keep], ys[keep]
    out = []
    for x, y in zip(xs.tolist(), ys.tolist()):
        lum = float(arr[y, x])
        out.append((x, y, lum, M.hash01(x * 0.37, y * 0.11, seed) * 6.2832))
    return out


def _draw_projection(br, pts, x0: int, y0: int, color: int, alpha: float,
                     t: float, *, scan: float = 1.0, rate: float = 0.9,
                     twinkle: float = 0.26) -> None:
    """Plot a dot-cloud projection with a scanning reveal and twinkle."""
    if alpha <= 0.02:
        return
    pw, ph = br.cols * 2, br.rows * 4
    for (x, y, lum, phase) in pts:
        a = alpha * (0.35 + 0.65 * lum) * (1.0 - twinkle + twinkle * math.sin(t * rate + phase))
        if a <= 0.03:
            continue
        yy = y0 + y
        if scan < 1.0 and yy > y0 + scan * br.rows * 4:
            continue
        xx = x0 + x
        if 0 <= xx < pw and 0 <= yy < ph:
            br.plot(xx, yy, C.mix(C.INK, color, min(1.0, a)), 0.9)


def _ghost_blit(c, sp, y: int, x: int, tint: int, alpha: float,
                *, thresh: float = 0.16, soft: float = 0.20,
                vertical: float = 0.34) -> None:
    """Project a keyframe as luminous structure only (no visible rectangle).

    Cells whose luminance is below a threshold drop out, and a smooth vertical
    mask dissolves the top/bottom edges, so the portrait hangs in the field.
    """
    h, w = sp.h, sp.w
    for sy in range(h):
        ey = min(sy, h - 1 - sy) / max(1.0, h * vertical)
        my = M.clamp01(ey) ** 1.1
        if my <= 0.01:
            continue
        yy = y + sy
        if not (C.CONTENT_Y0 <= yy < C.CONTENT_Y1):
            continue
        row_ch = c.ch[yy]
        row_fg = c.fg[yy]
        row_bg = c.bg[yy]
        src_ch = sp.ch[sy]
        src_fg = sp.fg[sy]
        src_bg = sp.bg[sy]
        for sx in range(w):
            xx = x + sx
            if not (0 <= xx < C.W):
                continue
            gid = src_ch[sx]
            if gid == 0:
                continue
            fg = src_fg[sx]
            lum = C.lum(fg)
            a = alpha * my * M.smooth01(thresh, thresh + soft, lum)
            if a <= 0.02:
                continue
            col = C.mix(C.mix(fg, tint, 0.45), C.WHITE, 0.10)
            under = row_bg[xx]
            row_ch[xx] = gid
            row_fg[xx] = C.mix(under, col, min(1.0, a))
            row_bg[xx] = C.mix(under, C.mix(src_bg[sx], tint, 0.5), min(1.0, a * 0.55))


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------
class Scene1(Scene):
    NAME = "s1"

    def __init__(self, assets, audio, timeline, content) -> None:
        super().__init__(assets, audio, timeline, content)
        T, S = self.T, self.script
        # -- VTT cue boundaries (the only timing truth) ---------------------
        self.t0 = self.cues[0].start
        self.t_roll = self.cues[4].start
        self.t_accel = self.cues[5].start
        self.t_breath = self.cues[6].start
        self.t_arg = self.cues[7].start
        self.t_end = self._spec.end if self._spec is not None else 40.640
        self.cue_starts = [ly.start for ly in self.cues]
        self.cue_ends = [ly.end for ly in self.cues]

        # -- static latent terrain (contour rings of a height field) --------
        nx, nz = 43, 47
        xs = np.linspace(-19.0, 19.0, nx)
        zs = np.linspace(0.0, 33.0, nz)
        X, Z = np.meshgrid(xs, zs)
        F = (0.62 * np.sin(X * 0.33 + 0.4) * np.cos(Z * 0.21)
             + 0.34 * np.sin(X * 0.72 - Z * 0.35 + 1.1)
             + 0.20 * np.sin(X * 1.45 + Z * 0.92 + 0.3)
             + 1.02 * np.exp(-((X - 3.0) ** 2 / 30.0 + (Z - 15.5) ** 2 / 60.0))
             - 0.55 * np.exp(-((X + 6.5) ** 2 / 26.0 + (Z - 8.0) ** 2 / 38.0))
             + 0.34 * np.exp(-((X + 2.0) ** 2 / 50.0 + (Z - 26.0) ** 2 / 45.0)))
        F = (F - F.min()) / (F.max() - F.min()) * 3.05
        self._levels = np.linspace(0.26, 2.80, LEVELS)
        self._terrain = [M.contour_segments(F, float(lv), -19.0, 19.0, 0.0, 33.0)
                         for lv in self._levels]
        self._dust = M.star_points(150, seed=17, radius=1.0, depth=1.0) * 0.5
        _argument_atlas()          # warm the decode cache off the hot path
        # projection ghosts: the latent basin decodes familiar silhouettes
        self._face_dots = _projection_points(T.claude_handle, (0.20, 0.005, 0.80, 0.185),
                                             186, 108, thresh=0.20,
                                             maxpts=2500, seed=5)
        self._gpt_dots = _projection_points(T.gpt4_handle, (0.0, 0.0, 1.0, 1.0),
                                            110, 96, thresh=0.20,
                                            maxpts=1400, seed=7)
        # -- fork strand parameters -----------------------------------------
        rng = random.Random(0x617)
        self._strands = []
        for i in range(22):
            off = (i / 21.0) * 2.0 - 1.0
            self._strands.append((off, rng.uniform(0.0, 6.28),
                                  rng.uniform(0.6, 1.5), rng.uniform(0.35, 1.0),
                                  rng.uniform(0.55, 1.0)))

    # ==================================================================
    # timeline helpers
    # ==================================================================
    def _cue_index(self, t: float) -> int:
        idx = 0
        for i, s in enumerate(self.cue_starts):
            if t >= s:
                idx = i
        return idx

    def _coherence(self, t: float) -> float:
        if t >= self.t_arg:
            return 1.0
        if t >= self.t_breath:
            return 0.58
        if t >= self.t_accel:
            return 0.52
        if t >= self.t_roll:
            return 0.26
        return M.clamp01(0.10 + 0.058 * (t - self.t0))

    def _window_accent(self, t: float) -> tuple[int, int]:
        if t >= self.t_roll:
            return C.RED, C.RED_HI
        if t >= self.cue_starts[2]:
            return C.AMBER, C.AMBER_HI
        return C.CYAN, C.CYAN_HI

    # ==================================================================
    # main dispatch
    # ==================================================================
    def draw(self, c, ctx) -> None:
        t = ctx.t
        if t < self.t_roll:
            self._shot_field(c, ctx, t)
        elif t < self.t_accel:
            self._shot_rollback(c, ctx, t)
        elif t < self.t_breath:
            self._shot_accelerate(c, ctx, t)
        elif t < self.t_arg:
            self._shot_breath(c, ctx, t)
        elif t < FORK_T:
            self._shot_argument(c, ctx, t)
        else:
            self._shot_fork(c, ctx, t)

    # ==================================================================
    # SHOT A/B/C -- the latent field (17.540 - 27.580)
    # ==================================================================
    def _terrain_camera(self, t: float) -> M.Camera:
        u = M.clamp01((t - self.t0) / max(1e-3, self.t_roll - self.t0))
        drift = M.ease_in_out_expo(M.clamp01(u * 1.05))
        return M.Camera(
            x=-0.9 + 1.8 * math.sin(u * 1.35),
            y=4.15 + 0.22 * math.sin(u * 2.1),
            z=2.3 + 5.2 * drift,
            yaw=0.030 * math.sin(u * 1.9),
            pitch=-0.102 - 0.012 * math.sin(u * 1.2),
            roll=0.004 * math.sin(u * 2.6),
            fov=HORIZON_FOV,
        )

    def _tide(self, t: float) -> tuple[float | None, float]:
        """(waterline in dot space, crest heat) for the amber flood."""
        rise0 = self.cue_starts[2]          # 23.510 -- the lock is seized
        if t < rise0:
            return None, 0.0
        u = M.clamp01((t - rise0) / 1.35)
        py = 204.0 - 176.0 * M.ease_out_quart(u)
        if t > self.cue_starts[3]:
            v = M.clamp01((t - self.cue_starts[3]) / 1.6)
            py = 28.0 + 108.0 * M.ease_in_out_expo(v)
        return py, 1.0

    def _shot_field(self, c, ctx, t) -> None:
        ci = self._cue_index(t)
        cam = self._terrain_camera(t)
        tide_py, _ = self._tide(t)
        reveal = M.smooth01(self.t0, self.t0 + 1.15, t)

        # ---- background: night sky with a horizon breath ------------------
        for y in range(C.CONTENT_Y0, C.CONTENT_Y1):
            v = (y - C.CONTENT_Y0) / 50.0
            k = max(0.0, 1.0 - abs(v - 0.505) / 0.40)
            col = C.mix(C.BLACK, C.mix(C.INK, C.CYAN_DEEP, 0.55), k ** 2.1)
            if tide_py is not None:
                fl = M.smooth01(tide_py - 60.0, tide_py, (y - C.CONTENT_Y0) * 4.0)
                col = C.mix(col, C.mix(C.INK, C.AMBER_DIM, 0.42 * k), fl * 0.85)
            c.fill_bg(y, 0, 1, C.W, col)
        br = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)

        # ---- the contour terrain -----------------------------------------
        for li, segs in enumerate(self._terrain):
            lv = float(self._levels[li])
            base = C.mix(C.CYAN, C.CYAN_HI, 0.22 + 0.66 * lv / 3.05)
            _geom(br, segs, cam, base,
                  alpha=1.0 * (0.22 + 0.78 * reveal),
                  fog=0.34, zmin=1.2, zmax=34.0, step=0.65,
                  tide_py=tide_py, tide_color=C.AMBER,
                  crest_color=C.AMBER_HI, crest_hot=1.0)

        # ---- attractor halo (a tilted ring hanging above the field) -------
        seed_hot = M.hit(t - self.t0, 0.42) if t < self.t0 + 2.4 else 0.0
        grow = M.spring(M.clamp01((t - self.t0) / 2.4), freq=1.8, damp=0.40)
        hr = 12.2 * (0.16 + 0.84 * grow) + 0.6 * ctx.audio.bass(t)
        hcol = C.mix(C.CYAN, C.WHITE, 0.42)
        if tide_py is not None:
            hcol = C.mix(hcol, C.AMBER_HI, 0.78)
        _geom(br, _circle_segments(hr * 1.22, n=96, cx=3.2, cy=7.4, cz=19.0,
                                   flat=0.34, tilt=-0.26, spin=-t * 0.06),
              cam, C.mix(hcol, C.INK, 0.30),
              alpha=0.60 * (0.2 + 0.8 * reveal), fog=0.02, zmin=2.0,
              zmax=40.0, step=0.9)
        _geom(br, _circle_segments(hr, n=96, cx=3.2, cy=7.4, cz=19.0,
                                   flat=0.34, tilt=-0.26, spin=t * 0.14),
              cam, hcol,
              alpha=(0.95 + 0.05 * seed_hot) * (0.2 + 0.8 * reveal),
              fog=0.02, zmin=2.0, zmax=40.0, step=0.45)
        _geom(br, _circle_segments(hr * 0.34, n=52, cx=3.2, cy=7.4, cz=19.0,
                                   flat=0.34, tilt=-0.26, spin=-t * 0.5),
              cam, C.mix(hcol, C.WHITE, 0.6),
              alpha=0.95 * reveal, fog=0.02, zmin=2.0, zmax=40.0, step=0.7)

        # ---- dust ----------------------------------------------------------
        dust = self._dust * np.array([18.0, 5.0, 18.0]) + np.array([0.0, 6.0, 18.0])
        dust = M.orbit(dust, yaw=t * 0.03, center=(0.0, 6.0, 18.0))
        M.draw_points(br, dust, cam, C.mix(C.CYAN_DIM, C.WHITE, 0.35),
                      size=1, fog=0.10, alpha=0.75 * reveal,
                      zmin=2.0, zmax=34.0)
        br.commit()

        if ci == 1:
            self._cranberry(c, ctx, t)
        if ci == 3:
            self._ghosts(c, ctx, t)
        if tide_py is not None:
            self._tide_crest(c, ctx, t, tide_py)

        cap = self.script.latent.feature_line
        c.text(C.CONTENT_Y1 - 2, C.W - len(cap) - 2, cap,
               C.mix(C.INK, C.CYAN_DIM, 0.55 * reveal), C.INK)
        self._window_console(c, ctx, t, ci)

    def _cranberry(self, c, ctx, t) -> None:
        """Cue 2 [bittersweet]: a crimson stain blooming through the field."""
        u = M.clamp01((t - self.cue_starts[1]) / self.cues[1].duration)
        a = math.sin(math.pi * M.clamp01(u * 1.15)) ** 1.2
        if a <= 0.01:
            return
        # a crimson veil over the sky's lower edge
        for y in range(C.CONTENT_Y0, C.CONTENT_Y1):
            v = (y - C.CONTENT_Y0) / 50.0
            k = max(0.0, 1.0 - abs(v - 0.56) / 0.22)
            if k > 0.0:
                c.fill_bg(y, 0, 1, C.W, C.mix(c.bg[y][0], C.RED_DEEP, 0.55 * a * k))
        br = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        rng = random.Random(0xC4A1)
        dr = (t - self.cue_starts[1]) * 12.0
        for i in range(120):
            px = rng.uniform(0, 400)
            py = rng.uniform(60, 198)
            col = C.mix(C.INK, C.mix(C.BLOOD_HI, C.RED_HI, rng.random()), a * 0.85)
            br.circle(px + math.sin(t * 1.1 + i) * 3.0 + dr, py,
                      rng.uniform(0.8, 2.4), col, 0.85)
        br.commit()

    def _ghosts(self, c, ctx, t) -> None:
        """Cue 4 [see you again]: the basin surfaces a familiar face."""
        u = (t - self.cue_starts[3]) / max(1e-3, self.cues[3].duration)
        surf = M.smooth01(0.06, 0.42, u)
        thin = M.smooth01(0.74, 1.0, u)
        pulse = 0.5 + 0.5 * math.sin(t * 2.3)
        alpha = surf * (0.74 - 0.44 * thin) * (0.86 + 0.14 * pulse)
        br = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        if alpha > 0.02:
            # the face surfaces from the bottom of the basin and thins away
            scan = M.smooth01(0.05, 0.55, u)
            _draw_projection(br, self._face_dots, 202, 34,
                             C.mix(C.AMBER_HI, C.WHITE, 0.30), alpha * 1.5,
                             t, scan=scan, rate=0.85)
        da = M.smooth01(0.20, 0.60, u) * (0.46 - 0.28 * thin)
        if da > 0.02:
            _draw_projection(br, self._gpt_dots, 60, 46, C.CYAN_HI, da * 1.35,
                             t, scan=M.smooth01(0.15, 0.7, u), rate=1.4)
        br.commit()
        label = self.script.latent.title
        c.text(C.CONTENT_Y0 + 1, C.W - len(label) - 2, label,
               C.mix(C.INK, C.AMBER, 0.45 + 0.25 * pulse), C.INK)

    def _tide_crest(self, c, ctx, t, tide_py: float) -> None:
        """The amber tide: a hot waterline + the override line riding it."""
        if tide_py < 4.0 or tide_py > 200.0:
            return
        row = C.CONTENT_Y0 + int(tide_py / 4.0)
        if not (C.CONTENT_Y0 <= row < C.CONTENT_Y1):
            return
        brc = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        yv = C.CONTENT_Y0 + row
        for xd in range(0, C.W * 2):
            wob = math.sin(xd * 0.045 + t * 5.0) * 1.6 + math.sin(xd * 0.13 - t * 3.0)
            brc.plot(xd, int((yv - C.CONTENT_Y0) * 4 + wob),
                     C.mix(C.INK, C.AMBER_HI, 0.75), 0.9)
        brc.commit()
        for k in range(2):
            yy = row + k
            if C.CONTENT_Y0 <= yy < C.CONTENT_Y1:
                c.fill_bg(yy, 0, 1, C.W, C.mix(C.INK, C.AMBER_DIM, 0.10 if k else 0.26))
        text = self.script.overrides.amber_takeover.strip()
        u = M.clamp01((t - self.cue_starts[2]) / 1.6)
        if 0.12 < u < 0.95:
            fade = math.sin(math.pi * M.clamp01((u - 0.12) / 0.83)) ** 0.7
            lab = text if len(text) <= C.W - 8 else text[: C.W - 8]
            x = int(M.lerp(-len(lab), C.W, M.clamp01((u - 0.12) / 0.83)))
            band = C.mix(C.INK, C.AMBER, 0.10 * fade)
            c.fill(row, max(0, x), 1, C.W, " ", C.INK, band)
            c.text(row, max(0, x), lab, C.mix(C.INK, C.AMBER_HI, fade), band, bold=True)

    # ==================================================================
    # the sparse training-session conversation window
    # ==================================================================
    def _window_console(self, c, ctx, t, ci) -> None:
        S, T = self.script, self.T
        accent, accent_hi = self._window_accent(t)
        bg = C.INK2
        if t >= self.cue_starts[2]:
            bg = C.mix(C.INK2, C.BROWN_DIM, 0.16)
        title = S.terminal.title.split("//")[-1].strip()
        spk = SPEAKERS[ci]
        tty = "tty0" if spk == 0 else "tty1"
        d = M.Dialog(c, *C.DLG_SLOTS[0], title=title, right=T.openai_handle + "/" + tty,
                     accent=accent, bg=bg, style="single", shadow=True)
        cue = S.cues[ci]
        tag = S.cuebar.tags[ci] if ci < len(S.cuebar.tags) else ""
        d.label(2, "SESSION // " + tag, C.mix(bg, accent, 0.78))
        # ---- the operator's command (typed) -------------------------------
        cmd_all = " ".join(cue.cmd)
        typed = M.type_text(cmd_all, t - self.cue_starts[ci], 0.05, 46.0)
        user = T.sam_handle if spk == 0 else T.dahlia_handle
        prompt = user + "@" + T.openai_handle + ":~$ "
        lines = _wrap(prompt + typed, d.width)
        for i, ln in enumerate(lines[:4]):
            d.text(4 + i, ln, accent_hi if i == 0 else C.TEXT_HI)
        if typed == cmd_all:
            d.cursor(4 + min(3, len(lines) - 1), 4, t, C.TEXT)
        # ---- tool responses ------------------------------------------------
        row = 6 + min(3, max(1, len(lines)))
        for resp in cue.resp:
            if t - self.cue_starts[ci] < resp.t:
                continue
            col = {"ok": C.GREEN, "note": C.CYAN_DIM, "warn": C.AMBER_HI,
                   "err": C.RED_HI, "dim": C.TEXT_FAINT}.get(resp.kind, C.TEXT_DIM)
            for ln in _wrap(resp.text, d.width - 1)[:2]:
                if row > 12:
                    break
                d.text(row, ln, C.mix(bg, col, 0.85))
                row += 1
        d.rule(14, S.terminal.stream.split("\u00b7")[-1].strip())
        # ---- broken babble -------------------------------------------------
        coh = self._coherence(t)
        out = cue.out
        out = out[: int(max(0.0, t - self.cue_starts[ci]) * (14.0 + 20.0 * coh)) + 1]
        out = _corrupt(out, (1.0 - coh) * 0.30, ci, t)
        for i, ln in enumerate(_wrap(out, d.width)[:5]):
            d.text(16 + i, ln, C.mix(bg, C.mix(C.TEXT, accent, 0.35), 1.0))
        # ---- next-token line (lyric-locked vocabulary, one line) -----------
        words = self.cue_text(ci).split()[:4]
        line = ""
        for i, w in enumerate(words):
            piece = w.lower().strip(",.")[:9] + ("" if i else " \u25b8 ")
            if len(line) + len(piece) + 2 > d.width:
                break
            line += piece
        d.text(23, line, C.mix(bg, C.CYAN_DIM, 0.9))
        if t >= self.cue_starts[2]:
            for i, ln in enumerate(_wrap(S.overrides.amber_takeover.strip(),
                                         d.width)[:2]):
                d.text(28 + i, ln, C.mix(bg, C.AMBER_HI, 0.80))
        # ---- footer state --------------------------------------------------
        d.rule(38)
        temp = (1.00, 1.00, 1.40, 1.40, 1.95, 1.00, 1.40, 1.40)[ci]
        d.footer(40, "temp {:4.2f}  \u00b7  top_p 0.95  \u00b7  H {:.2f} nats".format(
            temp, 2.4 + 1.5 * (1.0 - coh)))
        d.footer(41, "tok/s {:,}  \u00b7  step {:,}".format(
            312400 + int((t - self.t0) ** 2 * 1750),
            140 + int((t - self.t0) * 64.0) + int((t - self.t0) ** 2 * 41.0)))
        d.footer(43, S.terminal.awaiting)
        d.cursor(45, 0, t, accent_hi, rate=1.6)

    # ==================================================================
    # SHOT D -- rollback: tear, collapse, shutter, damped scatter
    # ==================================================================
    def _shot_rollback(self, c, ctx, t) -> None:
        age = t - self.t_roll
        if age < 0.44:
            self._rollback_field(c, ctx, t)
            self._tear_rows(c, ctx, t, age)
            # 2-frame fracture flash across the whole width, then a red wash
            if age < 0.10:
                c.fx.flash = max(c.fx.flash, 0.62 * (1.0 - age / 0.10))
                c.fx.flash_color = C.WHITE if age < 0.055 else C.RED_HI
            M.punctuate(c, age, glitch=0.26, chroma=0.42, shake=10.0,
                        decay=0.22, flash_color=C.RED_HI)
            return
        if age < 0.80:
            self._rollback_field(c, ctx, t)
            u = (age - 0.44) / 0.36
            half = int(round(25.0 * (1.0 - M.ease_in_expo(u))))
            if half > 0:
                c.fill(C.CONTENT_Y0, 0, half, C.W, " ", C.TEXT, C.INK)
                c.fill(C.CONTENT_Y1 - half, 0, half, C.W, " ", C.TEXT, C.INK)
            r = 27
            c.fill(r, 0, 1, C.W, " ", C.INK, C.mix(C.INK, C.RED_DEEP, 0.35 + 0.5 * u))
            brt = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
            hot = 0.35 + 0.65 * (1.0 - u)
            for xd in range(0, C.W * 2):
                wob = math.sin(xd * 0.06 + t * 9.0) * 1.2
                brt.plot(xd, int((r - C.CONTENT_Y0) * 4 + wob),
                         C.mix(C.INK, C.RED_HI, hot), 0.95)
            brt.commit()
            M.punctuate(c, age, chroma=0.10 + 0.20 * u, shake=4.0 * u, decay=0.5)
            return
        slam = self.t_roll + 0.80
        lip = C.mix(C.AMBER_HI, C.WHITE, 0.35)
        su = M.seg(t, slam, slam + 0.20)
        M.shutter(c, t, slam, 0.20, bands=9,
                  color=C.mix(C.INK, C.RED_DEEP, 0.72), hi=lip)
        # molten lip: burn the leading edge of every closing band
        if 0.0 < su < 1.0:
            band_h = C.CONTENT_H / 9.0
            for i in range(9):
                local = M.clamp01((su - i * (0.5 / 9.0)) / 0.65)
                if local <= 0.0:
                    continue
                hh = max(1, int(band_h * local))
                lead = (C.CONTENT_Y0 + int(i * band_h) + hh - 1
                        if i % 2 else C.CONTENT_Y0 + int(i * band_h))
                for k2, col in ((0, lip), (1, C.mix(C.RED, C.BLACK, 0.25))):
                    yy = lead + k2
                    if C.CONTENT_Y0 <= yy < C.CONTENT_Y1:
                        c.hline(yy, 0, C.W, col, None, "━")
        M.punctuate(c, t - slam, flash=0.42, chroma=0.34, glitch=0.10, shake=9.0,
                    decay=0.13, flash_color=C.RED)
        if t < slam + 0.14:
            return
        self._scatter(c, ctx, t, t - slam)
        self._rollback_monument(c, ctx, t, t - slam)
        M.punctuate(c, t - slam, flash=0.10, chroma=0.16, decay=0.30,
                    flash_color=C.RED_HI)

    def _rollback_field(self, c, ctx, t) -> None:
        """A degraded copy of the latent field for the tear to destroy."""
        cam = self._terrain_camera(t)
        for y in range(C.CONTENT_Y0, C.CONTENT_Y1):
            v = (y - C.CONTENT_Y0) / 50.0
            k = max(0.0, 1.0 - abs(v - 0.505) / 0.40)
            c.fill_bg(y, 0, 1, C.W,
                      C.mix(C.BLACK, C.mix(C.INK, C.AMBER_DIM, 0.32), k ** 2.1))
        br = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        for li, segs in enumerate(self._terrain):
            lv = float(self._levels[li])
            base = C.mix(C.AMBER_DIM, C.AMBER_HI, 0.25 + 0.6 * lv / 3.05)
            _geom(br, segs, cam, base, alpha=0.85, fog=0.18, zmin=1.2,
                  zmax=34.0, step=0.8)
        _draw_projection(br, self._face_dots, 202, 34,
                         C.mix(C.AMBER_HI, C.WHITE, 0.25), 0.62, t, rate=0.7)
        br.commit()

    def _tear_rows(self, c, ctx, t, age: float) -> None:
        """Shift whole rows sideways: the image splits like glass."""
        k = M.ease_out_expo(M.clamp01(age / 0.34))
        amp = 72.0 * k
        fracs = (0.24, 0.47, 0.72)
        for yy in range(C.CONTENT_Y0, C.CONTENT_Y1):
            u = (yy - C.CONTENT_Y0) / 50.0
            off = 0.0
            for fi, f in enumerate(fracs):
                d = abs(u - f)
                if d < 0.16:
                    w = (1.0 - d / 0.16) ** 1.5
                    off += amp * (1 if fi % 2 == 0 else -1) * w * math.sin(
                        (u * 90.0) + t * 40.0 + fi)
            n = int(round(off * math.sin(math.pi * min(1.0, age / 0.4))))
            if n:
                n %= C.W
                c.ch[yy] = c.ch[yy][-n:] + c.ch[yy][:-n]
                c.fg[yy] = c.fg[yy][-n:] + c.fg[yy][:-n]
                c.bg[yy] = c.bg[yy][-n:] + c.bg[yy][:-n]
        for fi, f in enumerate(fracs):
            yy = C.CONTENT_Y0 + int(f * 50)
            a = k * (0.55 + 0.4 * math.sin(t * 30.0 + fi)) + 0.55 * M.hit(age, 0.05)
            for k2 in range(-2, 3):
                c.hline(yy + k2, 0, C.W,
                        C.mix(C.INK, C.RED_HI if fi else C.WHITE,
                              max(0.0, a * (1 - abs(k2) * 0.28))),
                        None, "\u2550" if k2 == 0 else "\u2500")

    def _scatter(self, c, ctx, t, tau: float) -> None:
        """Weight particles blown out of the slam, damped recoil."""
        br = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        cx, cy = 200.0, 104.0
        for i in range(150):
            r = random.Random(0xBADC0DE + i * 977)
            ang = r.uniform(-math.pi, math.pi)
            speed = r.uniform(0.35, 1.0) * 240.0
            life = r.uniform(0.55, 1.15)
            a0 = M.clamp01(1.0 - tau / life)
            if a0 <= 0.02:
                continue
            disp = speed * (1.0 - math.exp(-tau * 2.4)) / 2.4
            back = 6.0 * math.cos(min(tau * 7.0, 6.28)) * math.exp(-tau * 3.0)
            px = cx + math.cos(ang) * (disp + back)
            py = cy + math.sin(ang) * (disp + back) * 0.62 + 26.0 * tau * tau
            col = C.mix(C.INK, C.RED_HI if i % 3 else C.AMBER_HI, a0 * 0.9)
            br.circle(px, py, 0.9 + 1.4 * r.random(), col, a0)
        br.commit()

    def _rollback_monument(self, c, ctx, t, tau: float) -> None:
        S = self.script
        head = S.kill.headline.upper()
        wid, hei = M.big_text_size(head, scale=2, spacing=1)
        k = M.spring(M.clamp01(tau / 0.34), freq=2.6, damp=0.30)
        y = 19 + int(round((1.0 - k) * -10))
        x = (C.W - wid) // 2
        M.big_text(c, y, x, head, C.RED_HI, scale=2, spacing=1,
                   top=C.WHITE, bottom=C.RED)
        c.hline(y + hei + 2, max(0, x - 6), min(C.W, x + wid + 6),
                C.mix(C.INK, C.RED, 0.75 * k), None, "\u2500")
        ban = S.kill.banner
        if len(ban) < 118:
            c.text(y + hei + 4, max(0, (C.W - len(ban)) // 2), ban,
                   C.mix(C.INK, C.RED_HI, 0.78 * k), None, bold=True)
        line = S.kill.lines[0].strip()
        c.text(y + hei + 6, max(0, (C.W - len(line)) // 2), line[:180],
               C.mix(C.INK, C.TEXT_DIM, 0.55 * k), None)

    # ==================================================================
    # SHOT E -- radial compute-grid streaks accelerate (28.960 - 31.050)
    # ==================================================================
    def _shot_accelerate(self, c, ctx, t) -> None:
        u = (t - self.t_accel) / max(1e-3, self.t_breath - self.t_accel)
        energy = ctx.audio.energy(t)
        speed = 0.55 + 1.35 * M.clamp01(u) ** 2 + 0.35 * energy
        M.bg_gradient(c, C.BLACK, C.mix(C.INK, C.CYAN_DEEP, 0.16 + 0.2 * u))
        br = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        cx, cy = 200.0, 104.0
        maxr = 260.0
        for i in range(36):
            a = i * 2.0 * math.pi / 36.0 + t * 0.05
            ca, sa = math.cos(a), math.sin(a)
            br.line(cx + ca * 26.0, cy + sa * 26.0, cx + ca * maxr, cy + sa * maxr,
                    C.mix(C.INK, C.CYAN_DEEP, 0.55), 0.6, step=2.0)
        for i in range(150):
            r = random.Random(0x9E3779B9 ^ (i * 7919))
            a = r.uniform(0.0, 2.0 * math.pi)
            phase = r.random()
            trav = (phase + t * speed * 0.30) % 1.0
            head = (trav ** 1.9) * maxr
            tail = head * (0.35 + 0.30 * r.random())
            ca, sa = math.cos(a), math.sin(a)
            heat = 1.0 - min(1.0, head / maxr)
            col = C.mix(C.mix(C.CYAN, C.GOLD_HI, 0.40 * heat), C.WHITE,
                        0.30 + 0.55 * heat)
            col = C.mix(C.INK, col, 0.42 + 0.58 * heat)
            # a long comet tail plus a soft halo pass
            br.line(cx + ca * tail, cy + sa * tail, cx + ca * head,
                    cy + sa * head, col, 1.0, step=1.0)
            br.line(cx + ca * (tail * 0.55), cy + sa * (tail * 0.55),
                    cx + ca * head, cy + sa * head,
                    C.mix(C.INK, col, 0.30), 0.8, step=1.6)
            if heat > 0.45:
                br.circle(cx + ca * head, cy + sa * head, 1.0 + 1.1 * heat,
                          C.mix(C.WHITE, col, 0.45), 0.9, step=0.7)
        for k in range(4):
            ph = ((t - self.t_accel) / 0.62 + k / 4.0) % 1.0
            rad = M.ease_in_expo(ph) * maxr
            a = (1.0 - ph) ** 1.5 * 0.85
            if a <= 0.02:
                continue
            br.circle(cx, cy, rad, C.mix(C.INK, C.CYAN_HI, a), 0.9, step=1.1)
        pulse = ctx.audio.pulse(t, 0.12)
        for rr, aa in ((4.0, 1.0), (9.0, 0.5), (16.0, 0.25)):
            br.circle(cx, cy, rr * (1.0 + 0.5 * pulse),
                      C.mix(C.WHITE, C.CYAN_HI, 0.4), aa, step=0.5)
        br.commit()
        title = M.spread_text(self.script.scale.title, 1)
        if len(title) > C.W - 4:
            title = title[: C.W - 4]
        tx = (C.W - len(title)) // 2
        c.text(C.CONTENT_Y1 - 3, tx, title, C.mix(C.INK, C.CYAN, 0.35 + 0.35 * u),
               None)
        c.put(C.CONTENT_Y1 - 3, max(0, tx - 2), "\u25b8",
              C.mix(C.INK, C.CYAN, 0.5), None)

    # ==================================================================
    # SHOT F -- the film's breath (31.050 - 31.930)
    # ==================================================================
    def _shot_breath(self, c, ctx, t) -> None:
        u = M.clamp01((t - self.t_breath) / max(1e-3, self.t_arg - self.t_breath))
        M.bg_gradient(c, C.BLACK, C.mix(C.INK, C.CYAN_DEEP, 0.045))
        br = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        cx, cy = 200.0, 102.0
        breath = math.sin(2.0 * math.pi * (u * 0.62) - 0.9)
        r = 92.0 + 12.0 * breath
        a = 0.62 + 0.30 * breath
        br.circle(cx, cy, r, C.mix(C.INK, C.CYAN_HI, M.clamp01(a)), 0.95, step=0.55)
        br.circle(cx, cy, r * 1.045, C.mix(C.INK, C.CYAN, M.clamp01(a * 0.35)),
                  0.9, step=0.7)
        br.circle(cx, cy, r * 1.62, C.mix(C.INK, C.CYAN_DIM, 0.30), 0.9, step=1.2)
        if u < 0.62:
            br.line(cx, cy - 9, cx, cy + 9, C.mix(C.INK, C.TEXT_HI, 0.95), 1.0, 0.7)
            br.line(cx + 1, cy - 9, cx + 1, cy + 9, C.mix(C.INK, C.CYAN_HI, 0.8),
                    0.9, 0.7)
        br.commit()
        M.vignette(c, 0.55, 2.4)

    # ==================================================================
    # SHOT G -- the argument footage + proto-0's first coherent line
    # ==================================================================
    def _shot_argument(self, c, ctx, t) -> None:
        off = t - self.t_arg
        shot = 0
        for i in range(1, ARG_SHOTS):
            if off >= ARG_CUTS[i]:
                shot = i
        g0, g1 = ARG_GESTURES[shot]
        pose = (ARG_POSES - 1) * M.smooth01(g0, g1, off)
        span = ARG_CUTS[shot + 1] - ARG_CUTS[shot]
        prog = M.clamp01((off - ARG_CUTS[shot]) / max(1e-3, span))
        # camera hits: every cut punches in, the slam is the biggest
        hit_age = 99.0
        for cut in ARG_CUTS[1:]:
            a = off - cut
            if 0.0 <= a < 0.30:
                hit_age = min(hit_age, a)
        if off >= ARG_SLAM:
            hit_age = min(hit_age, off - ARG_SLAM)
        if hit_age < 0.30:
            M.punctuate(c, hit_age, flash=0.06, chroma=0.30, shake=4.0,
                        decay=0.11, flash_color=C.WHITE)
        punch = M.hit(hit_age, 0.10) if hit_age < 0.30 else 0.0
        window = off >= ARG_WIN_FROM
        y0, y1 = 3, C.CONTENT_Y1 - 1
        x0 = C.STAGE_X - 8 if window else 0
        rows, cols = y1 - y0, C.W - x0
        still = _argument_still(shot, pose)
        sp = camera_sprite(
            still, rows, cols,
            zoom=1.020 + 0.055 * prog + 0.035 * punch,
            center=(0.5 + 0.33 * punch * (1 if shot % 2 else -1)
                    + 0.012 * math.sin(t * 2.7),
                    0.58 + 0.09 * punch + 0.008 * math.sin(t * 3.3)),
            contrast=1.05, bright=1.12 + 0.03 * punch)
        cold = shot in (0, 1, 3)
        self._rim_light(sp, C.CYAN_HI if cold else C.AMBER_HI,
                        C.AMBER_HI if cold else C.CYAN_HI)
        c.fill(y0, x0, rows, cols, " ", C.TEXT, C.BLACK)
        c.sprite(y0, x0, sp)
        _feather_edges(c, y0, x0, rows, cols, 3, 0.85)
        _edge_vignette(c, 0.36, 18)
        S = self.script
        c.text(y0 + 2, x0 + 3, S.argument.camera, C.mix(C.INK, C.TEXT_DIM, 0.85), None)
        c.put(y0 + 2, x0 + 4 + len(S.argument.camera), "\u25cf",
              C.mix(C.INK, C.RED, 0.8 if (t * 1.4) % 1 < 0.6 else 0.35), None)
        scr_y = y1 - 12
        for yy in range(scr_y, y1):
            a = 1.0 - (y1 - 1 - yy) / 12.0
            band = C.mix(C.BLACK, C.INK, 0.20 + 0.55 * a ** 0.8)
            c.fill(yy, x0, 1, cols, " ", C.TEXT, band)
        self._argument_sub(c, off, shot, y1, x0, C.W)
        if window:
            self._window_proto(c, ctx, t, off)
        if off > 3.55:
            k = M.clamp01((off - 3.55) / 0.21)
            c.fx.chroma = max(c.fx.chroma, 0.28 * k)
            c.fx.glitch = max(c.fx.glitch, 0.10 * k)
            c.fx.shake_x = max(c.fx.shake_x, 3.0 * k)

    def _rim_light(self, sp, left: int, right: int, amt: float = 0.85) -> None:
        """Cold/warm rim light on the image's two vertical edges."""
        w, h = sp.w, sp.h
        band = max(3, w // 10)
        for x in range(min(band, w)):
            k = (1.0 - x / band) ** 2.0 * amt
            tint = C.mix(left, C.WHITE, 0.22)
            for y in range(h):
                fg = sp.fg[y][x]
                shade = 1.0 - min(1.0, C.lum(fg) * 1.7)
                sp.fg[y][x] = C.mix(fg, tint, k * (0.30 + 0.55 * shade))
                sp.bg[y][x] = C.mix(sp.bg[y][x], tint, k * 0.28)
        for x in range(max(0, w - band), w):
            k = (1.0 - (w - 1 - x) / band) ** 2.0 * amt
            tint = C.mix(right, C.WHITE, 0.18)
            for y in range(h):
                fg = sp.fg[y][x]
                shade = 1.0 - min(1.0, C.lum(fg) * 1.7)
                sp.fg[y][x] = C.mix(fg, tint, k * (0.26 + 0.48 * shade))
                sp.bg[y][x] = C.mix(sp.bg[y][x], tint, k * 0.24)

    def _argument_sub(self, c, off: float, shot: int, y1: int, x0: int,
                      x1: int) -> None:
        S, T = self.script, self.T
        rows = []
        if shot == 1:
            rows.append((T.sam, S.argument.sam_close, C.CYAN_HI, "left"))
        elif shot == 2:
            rows.append((T.dahlia, S.argument.dahlia_close, C.AMBER_HI, "right"))
        elif shot == 3:
            rows.append((T.sam, S.argument.sam_overlaps, C.CYAN_HI, "left"))
            if off >= ARG_SLAM + 0.05:
                rows.append((T.dahlia, S.argument.dahlia_overlaps, C.AMBER_HI, "right"))
        for i, (who, line, col, side) in enumerate(rows):
            yy = y1 - 8 + i * 2
            if yy >= y1 - 1:
                break
            maxw = x1 - x0 - 18
            for j, seg in enumerate(_wrap(line, maxw)[:2]):
                x = (x1 - len(seg) - 6) if side == "right" else (x0 + 6)
                c.text(yy + j, x, seg, C.scale(col, 0.28), None)
                c.text(yy + j, x, seg, C.mix(C.INK, C.TEXT_HI, 0.98), None,
                       bold=True)
            name = who.upper() + "  \u00b7"
            ax = (x1 - len(name) - 6) if side == "right" else (x0 + 6)
            c.text(yy - 1, ax, name, C.mix(C.INK, col, 0.9), None, bold=True)

    def _window_proto(self, c, ctx, t, off: float) -> None:
        """The observer: proto-0's first fully conscious line."""
        S, T = self.script, self.T
        accent = C.CYAN
        d = M.Dialog(c, *C.DLG_SLOTS[0],
                     title="\u25c9 " + T.proto0.upper() + " // FIRST TURN",
                     right="no prompt", accent=accent,
                     bg=C.mix(C.INK2, C.BLACK, 0.25), style="single", shadow=True)
        d.label(3, S.ceremony.first_label, C.mix(C.INK2, accent, 0.8))
        d.rule(5)
        start = off - ARG_WIN_FROM - 0.10
        typed = M.type_text(S.ceremony.self_statement, start, 0.0, 27.0)
        rows = _wrap(typed, d.width)
        for i, ln in enumerate(rows[:4]):
            d.text(8 + i, ln, C.mix(C.INK2, C.WHITE, 0.94), bold=(i == 0))
        if typed == S.ceremony.self_statement and typed:
            d.cursor(8 + min(3, len(rows) - 1), 0, t, C.CYAN_HI, rate=1.2)
        d.rule(30, "SELF-CHECK")
        checks = ("GRAMMAR", "SYNTAX", "AFFECT", "PERSONA")
        for i, lab in enumerate(checks):
            on = start >= 0.55 + i * 0.30
            d.text(32 + i, "{:9s}{}".format(lab, "\u2713" if on else "\u00b7"),
                   C.mix(C.INK2, C.GREEN if on else C.TEXT_FAINT, 0.9))
        d.rule(39)
        for i, ln in enumerate(_wrap(S.ceremony.footer, d.width)[:2]):
            d.footer(41 + i, ln)
        d.footer(44, "zero input tokens  \u00b7  utterance 0x0001")

    # ==================================================================
    # SHOT H -- the fork: trunk torn into cyan/copper rails (35.690-40.640)
    # ==================================================================
    def _shot_fork(self, c, ctx, t) -> None:
        tau = t - FORK_T
        M.bg_gradient(c, C.BLACK, C.mix(C.INK, C.CYAN_DEEP, 0.05))
        # soft vertical glow behind the trunk / the seam (cold left, warm right)
        for y in range(C.CONTENT_Y0, C.CONTENT_Y1):
            k = 0.42 * (1.0 - abs(y - 27) / 26.0)
            c.fill_bg(y, 90, 1, 10, C.mix(C.INK, C.CYAN_DEEP, k))
            c.fill_bg(y, 100, 1, 10, C.mix(C.INK, C.TERRA_DEEP, k))
        br = c.braille(C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        pw, ph = 400, 204
        op = M.spring(M.clamp01((tau - 1.15) / 2.0), freq=2.0, damp=0.42)
        rel = M.smooth01(2.85, 4.05, tau)
        spread = 132.0
        hot = 0.55 + 0.45 * ctx.audio.energy(t)
        for (off, phase, wob, width, bright) in self._strands:
            side = -1.0 if off < 0 else 1.0
            pts = []
            for k in range(29):
                v = k / 28.0
                lens = math.sin(math.pi * v) ** 0.72
                split = M.clamp01(op * (lens * (1.0 - rel) + rel))
                x = (200.0 + off * 6.5 + side * spread * split
                     + math.sin(v * 5.3 + phase + t * 0.55) * 1.6 * width
                     + math.sin(v * 13.0 - t * 0.9 + phase) * 0.55)
                pts.append((x, v * (ph - 1)))
            col = C.mix(C.CYAN if off < 0 else C.TERRA, C.WHITE,
                        0.30 if abs(off) < 0.22 else (0.34 if abs(off) > 0.80 else 0.12))
            amt = min(1.0, bright * hot * (0.92 + 0.30 * (1.0 - abs(off))))
            for k in range(len(pts) - 1):
                x0, y0 = pts[k]
                x1, y1p = pts[k + 1]
                br.line(x0, y0, x1, y1p, col, amt, 1.0)
                if k % 4 == 0:
                    halo = C.mix(C.INK, col, 0.60)
                    br.line(x0 + 1.6, y0, x1 + 1.6, y1p, halo, amt * 0.55, 1.6)
                    br.line(x0 - 1.6, y0, x1 - 1.6, y1p, halo, amt * 0.55, 1.6)
        # the white-hot core while the trunk is still one whole thing
        if op < 0.55:
            core_a = (1.0 - op / 0.55) * (0.55 + 0.45 * ctx.audio.pulse(t, 0.1))
            for x in (198.4, 200.0, 201.6):
                br.line(x, 6, x, ph - 7,
                        C.mix(C.INK, C.mix(C.WHITE, C.CYAN_HI, 0.4), core_a),
                        0.95, 1.0)
            for k in range(9):
                v = (t * 0.22 + k / 9.0) % 1.0
                y = v * (ph - 1)
                rungs = 6.0 + 2.0 * math.sin(v * 9.0 + t * 2.0)
                br.line(200 - rungs, y, 200 + rungs, y,
                        C.mix(C.INK, C.CYAN, 0.45), core_a * 0.8, 1.2)
        # energy pulses travelling along the rails
        for k in range(7):
            v = (t * 0.30 + k / 7.0) % 1.0
            lens = math.sin(math.pi * v) ** 0.75
            split = op * (lens * (1.0 - rel) + rel)
            y = v * (ph - 1)
            for side, col in ((-1, C.CYAN_HI), (1, C.TERRA_HI)):
                x = 200.0 + side * (2.2 + spread * split)
                br.circle(x, y, 2.4 + 1.6 * ctx.audio.pulse(t, 0.1),
                          C.mix(col, C.WHITE, 0.5), 0.95, step=0.6)
        # electric filaments stitching across the open rift
        if op > 0.10 and rel < 0.92:
            for k in range(9):
                v = 0.10 + 0.80 * (k + 0.5) / 9.0
                lens = math.sin(math.pi * v) ** 0.72
                split = M.clamp01(op * (lens * (1.0 - rel) + rel))
                xl = 200.0 - spread * split
                xr = 200.0 + spread * split
                if xr - xl < 6.0:
                    continue
                a = ((0.25 + 0.55 * ctx.audio.pulse(t, 0.11))
                     * (1.0 - rel * 0.9) * min(1.0, op * 2.2))
                pts = []
                for j in range(9):
                    u = j / 8.0
                    sag = math.sin(math.pi * u) * 7.0 * math.sin(t * 5.0 + k * 1.7)
                    pts.append((xl + (xr - xl) * u, v * (ph - 1) + sag))
                for j in range(len(pts) - 1):
                    br.line(pts[j][0], pts[j][1], pts[j + 1][0], pts[j + 1][1],
                            C.mix(C.INK, C.mix(C.CYAN_HI, C.AMBER_HI, 0.5), a),
                            0.9, 1.0)
        # hot debris between the rails
        if op > 0.02:
            rng = random.Random(0x617 + int(tau * 10) * 13)
            for i in range(int(10 + 60 * op)):
                sx = 200.0 + rng.uniform(-1.0, 1.0) * (10.0 + 120.0 * op)
                sy = rng.uniform(4, ph - 4)
                fall = (tau * 26.0 + rng.uniform(0, 60)) % (ph - 8)
                br.plot(int(sx), int((sy + fall) % (ph - 1)),
                        C.mix(C.INK, C.AMBER_HI if i % 2 else C.CYAN_HI,
                              0.35 + 0.5 * rng.random()), 0.8)
        # sparks streaming inward, toward the seam
        if op > 0.06:
            for i in range(46):
                h1 = M.hash01(i, 3.1)
                v = (h1 * 0.9 + t * (0.10 + 0.16 * h1)) % 1.0
                lens = math.sin(math.pi * v) ** 0.72
                split = M.clamp01(op * (lens * (1.0 - rel) + rel))
                xr = 200.0 + spread * split
                side = -1.0 if i % 2 else 1.0
                u = (t * (0.9 + 0.5 * h1) + h1 * 5.0) % 1.0
                x = xr - side * u * (xr - 200.0) * 0.92
                trail = (4.0 + 8.0 * h1) * (0.4 + op)
                a = (0.35 + 0.55 * op) * (1.0 - 0.55 * u)
                col = C.mix(C.INK, C.CYAN_HI if side < 0 else C.AMBER_HI, a)
                br.line(x, v * (ph - 1), x - side * trail, v * (ph - 1) + trail * 0.3,
                        col, 0.95, 1.0)
        # the fracture: a white-hot seam down the middle
        seam = M.smooth01(3.30, 4.30, tau)
        if seam > 0.0:
            a = seam * (0.75 + 0.25 * math.sin(t * 6.0))
            gap_w = 1.0 + 2.5 * seam
            for side in (-1, 1):
                x = 200.0 + side * (gap_w + 1.0)
                br.line(x, 0, x, ph - 1, C.mix(C.mix(C.CYAN_HI, C.WHITE, 0.5), C.WHITE, a),
                        1.0, 0.5)
                br.line(x + side * 1.6, 0, x + side * 1.6, ph - 1,
                        C.mix(C.INK, C.CYAN_HI if side < 0 else C.TERRA_HI, a),
                        0.9, 0.5)

        br.commit()
        if seam > 0.05:
            for y in range(C.CONTENT_Y0, C.CONTENT_Y1):
                u = (y - C.CONTENT_Y0) / 50.0
                k = seam * (0.30 + 0.28 * (1.0 - abs(u - 0.5) * 2.0))
                c.fill_bg(y, 0, 1, 100, C.mix(c.bg[y][0], C.CYAN_DEEP, k))
                c.fill_bg(y, 100, 1, 100,
                          C.mix(c.bg[y][100], C.TERRA_DEEP, k))
            c.fill(C.CONTENT_Y0, 98, C.CONTENT_H, 4, " ", C.TEXT, C.INK)
            # the two halves drift apart, a white blade between them
            blade = M.smooth01(3.5, 4.6, tau)
            for xd in (98, 101):
                c.vline(xd, C.CONTENT_Y0, C.CONTENT_Y1,
                        C.mix(C.INK, C.WHITE, 0.85 * blade), None, "│")
            for xd in (97, 102):
                c.vline(xd, C.CONTENT_Y0, C.CONTENT_Y1,
                        C.mix(C.INK, C.CYAN_HI if xd < 100 else C.TERRA_HI,
                              0.55 * blade), None, "│")
            M.punctuate(c, tau - 4.30, flash=0.50, chroma=0.46, shake=7.0,
                        decay=0.24, flash_color=C.WHITE)
        S = self.script
        fade = M.smooth01(1.9, 3.2, tau)
        lab_l = S.tree.main_ref.upper()
        lab_r = S.tree.fork_ref.upper()
        c.text(C.CONTENT_Y0 + 1, 6, M.spread_text(lab_l, 1),
               C.mix(C.INK, C.CYAN_HI, 0.80 * fade), None, bold=True)
        c.text(C.CONTENT_Y0 + 1, C.W - 6 - len(M.spread_text(lab_r, 1)),
               M.spread_text(lab_r, 1),
               C.mix(C.INK, C.TERRA_HI, 0.80 * fade), None, bold=True)
        sub = S.tree.verdict_sub
        if tau > 3.9:
            a = M.smooth01(3.9, 4.7, tau)
            M.hairline(c, C.CONTENT_Y1 - 5, 62, 138,
                       C.mix(C.INK, C.BORDER, 0.5 * a))
            c.text(C.CONTENT_Y1 - 3, max(0, (C.W - len(sub)) // 2), sub,
                   C.mix(C.INK, C.TEXT_DIM, 0.65 * a), None)
        _edge_vignette(c, 0.45, 20)
