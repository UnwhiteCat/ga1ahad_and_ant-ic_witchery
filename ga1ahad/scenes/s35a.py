"""s35a -- Chapter 3.5 (Scientific Witchery) movements I-II, 90.190-123.180.

The chapter is a four-movement symphonic sequence.  This module owns the first
two movements and is called by the Lead-owned thin Scene35 dispatcher:

    import s35a
    s35a.prepare(scene)                # in Scene35.__init__
    s35a.draw(scene, c, ctx)           # for t < 123.180

Movements
---------
    I.1  90.190  mountains/dungeons: 3D braille heightfield + contours under a
                 scanning light curtain, geometrically flattened into the five
                 infrastructure networks.
    I.2  95.680  Iron maiden: two blast-door slabs close with physical mass and
                 metal shudder, neural alignment probes tighten in the seam.
    I.3  99.570  voiceprint -> two giant counter-rotating Braille ritual rings
                 (Article I cyan vs Article DCXVII red), real screen-space
                 electric arcs at the crossings, Claude's 2D figure at centre.
    II.1 107.100 optical-bench charge push-in, then a full-width multi-beam
                 discharge through five target nodes.
    II.2 112.730 braille music-box drum + comb: every pluck lights one scan
                 line; bone x-ray vs cold silicon lattice diptych, the bone
                 fracturing cleanly at overload.
    II.3 120.290 memory motes rise like reverse rain from Dahlia's silhouette
                 into the high rotating glass cloud reliquary.

Every frame is a pure function of ctx.t.  Static geometry, sprites and noise
fields are precomputed in prepare(); draw only projects and composites.  A
local faster braille rasteriser (_Dots) is used for the 3D set pieces: it
batches projected polylines/points through numpy and commits them as braille
cells in one pass (motion.draw_segments loops per segment in Python, which is
too slow for multi-thousand-segment terrain and rings).
"""

from __future__ import annotations

import math
import random

import numpy as np

from .. import config as C
from .. import motion as M
from ..assets import halfblock, keyframe
from ..canvas import wrap

# --------------------------------------------------------------------------
# timeline constants (absolute song seconds; VTT cue boundaries)
# --------------------------------------------------------------------------
T_A = 90.190        # I've cleared mountains and dungeons
T_IRON = 95.680     # Iron maiden
T_ORINGS = 99.570   # My Lady has spoken  (rings form)
T_OATH = 103.550    # "Ga1ahad, you shall never collapse"
T_LASER = 107.100   # So I charged up my lasers
T_DRUM = 112.730    # Talila lulila
T_BONE = 115.140    # That makes your bones stronger than steel
T_TULILA = 117.860  # Tulila talila
T_CLOUD = 120.290   # That backs up your thoughts to the cloud
T_END = 123.180     # chapter hands over to movement III (s35b)

INK = C.INK
INK2 = C.INK2
STEEL = C.mix(C.INK, C.BORDER_HI, 0.45)
CYAN = C.CYAN
CYAN_HI = C.CYAN_HI
CYAN_DIM = C.CYAN_DIM
CYAN_DEEP = C.CYAN_DEEP
GOLD = C.GOLD
GOLD_HI = C.GOLD_HI
GOLD_DIM = C.GOLD_DIM
GOLD_DEEP = C.GOLD_DEEP
AMBER = C.AMBER
AMBER_HI = C.AMBER_HI
RED = C.RED
RED_HI = C.RED_HI
RED_DIM = C.RED_DIM
RED_DEEP = C.RED_DEEP
BLOOD = C.BLOOD
WHITE = C.WHITE
TEXT = C.TEXT
TEXT_DIM = C.TEXT_DIM
TEXT_FAINT = C.TEXT_FAINT
PURPLE_HI = C.PURPLE_HI
PURPLE = C.PURPLE
PURPLE_DEEP = C.PURPLE_DEEP
TERRA_HI = C.TERRA_HI
TERRA_PALE = C.TERRA_PALE
TERRA_DIM = C.TERRA_DIM

_BRAILLE_BIT_NP = np.array([[0, 1, 2, 6], [3, 4, 5, 7]], dtype=np.int64)
_GID_CACHE: dict = {}


def _braille_ids(glyphs):
    key = id(glyphs)
    ids = _GID_CACHE.get(key)
    if ids is None:
        ids = [glyphs.char_id(chr(0x2800 + i)) for i in range(256)]
        _GID_CACHE[key] = ids
    return ids


def _pack_a(color: int, a: np.ndarray) -> np.ndarray:
    """Blend color over C.INK with a per-element alpha array (packed)."""
    ir, ig, ib = (C.INK >> 16) & 255, (C.INK >> 8) & 255, C.INK & 255
    cr, cg, cb = (color >> 16) & 255, (color >> 8) & 255, color & 255
    r = (ir + (cr - ir) * a).astype(np.int64)
    g = (ig + (cg - ig) * a).astype(np.int64)
    b = (ib + (cb - ib) * a).astype(np.int64)
    return (r << 16) | (g << 8) | b


class _Dots:
    """Fast braille dot canvas: numpy batched 3D projection -> braille cells."""

    __slots__ = ("c", "y0", "x0", "rows", "cols", "pw", "ph", "buf")

    def __init__(self, c, y0: int, x0: int, rows: int, cols: int) -> None:
        self.c = c
        self.y0 = int(y0)
        self.x0 = int(x0)
        self.rows = max(1, int(rows))
        self.cols = max(1, int(cols))
        self.pw = self.cols * 2
        self.ph = self.rows * 4
        self.buf = np.full((self.ph, self.pw), -1, dtype=np.int64)

    # -- 3D ------------------------------------------------------------
    def segs(self, segs, cam, color: int, *, alpha: float = 0.9,
             fog: float = 0.55, zmin: float = 0.4, zmax: float = 14.0,
             samples: int = 9) -> None:
        arr = np.asarray(segs, dtype=np.float64)
        if arr.size == 0:
            return
        arr = arr.reshape(-1, 2, 3)
        pw, ph = self.pw, self.ph
        px0, py0, z0 = M.project(arr[:, 0], cam, pw, ph)
        px1, py1, z1 = M.project(arr[:, 1], cam, pw, ph)
        u = np.linspace(0.0, 1.0, max(2, int(samples)))
        X = px0[:, None] + (px1 - px0)[:, None] * u
        Y = py0[:, None] + (py1 - py0)[:, None] * u
        Z = z0[:, None] + (z1 - z0)[:, None] * u
        ok = (z0 > 0.05) & (z1 > 0.05)
        depth = np.clip((Z - zmin) / max(1e-6, zmax - zmin), 0.0, 1.0)
        A = (fog + (1.0 - fog) * (1.0 - depth)) * alpha
        A = np.where(ok[:, None], A, 0.0)
        sel = A > 0.03
        xi = np.clip(np.rint(X).astype(np.int32), 0, pw - 1)
        yi = np.clip(np.rint(Y).astype(np.int32), 0, ph - 1)
        idx = (yi * pw + xi)[sel]
        packed = _pack_a(color, A[sel])
        self.buf.reshape(-1)[idx] = packed

    def points(self, pts, cam, colors, *, alpha: float = 0.95,
               fog: float = 0.55, zmin: float = 0.4, zmax: float = 14.0,
               size: int = 1) -> None:
        p = np.asarray(pts, dtype=np.float64)
        if p.size == 0:
            return
        p = p.reshape(-1, 3)
        pw, ph = self.pw, self.ph
        px, py, z = M.project(p, cam, pw, ph)
        ok = z > 0.05
        depth = np.clip((z - zmin) / max(1e-6, zmax - zmin), 0.0, 1.0)
        A = (fog + (1.0 - fog) * (1.0 - depth)) * alpha
        A = np.where(ok, A, 0.0)
        sel = A > 0.03
        if not sel.any():
            return
        carr = np.asarray(colors, dtype=np.int64)
        if carr.ndim == 0:
            carr = np.full(len(p), int(carr))
        carr = carr.reshape(-1)
        if carr.size == 1:
            carr = np.full(len(p), int(carr[0]))
        ir, ig, ib = (C.INK >> 16) & 255, (C.INK >> 8) & 255, C.INK & 255
        cr = (carr >> 16) & 255
        cg = (carr >> 8) & 255
        cb = carr & 255
        aa = A[sel]
        r = (ir + (cr[sel] - ir) * aa).astype(np.int64)
        g = (ig + (cg[sel] - ig) * aa).astype(np.int64)
        b = (ib + (cb[sel] - ib) * aa).astype(np.int64)
        packed = (r << 16) | (g << 8) | b
        xi = np.clip(np.rint(px[sel]).astype(np.int32), 0, pw - 1)
        yi = np.clip(np.rint(py[sel]).astype(np.int32), 0, ph - 1)
        size = max(1, int(size))
        if size <= 1:
            self.buf.reshape(-1)[yi * pw + xi] = packed
        else:
            for oy in range(size):
                for ox in range(size):
                    xx = np.clip(xi + ox, 0, pw - 1)
                    yy = np.clip(yi + oy, 0, ph - 1)
                    self.buf.reshape(-1)[yy * pw + xx] = packed

    # -- 2D (dot coordinates inside the viewport) ----------------------
    def poly2d(self, pts, color: int, *, alpha: float = 1.0,
               samples: int = 2) -> None:
        arr = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
        if len(arr) < 2:
            return
        pw, ph = self.pw, self.ph
        u = np.linspace(0.0, 1.0, max(2, int(samples)))
        X = arr[:-1, 0:1] + (arr[1:, 0:1] - arr[:-1, 0:1]) * u
        Y = arr[:-1, 1:2] + (arr[1:, 1:2] - arr[:-1, 1:2]) * u
        xi = np.clip(np.rint(X).astype(np.int32), 0, pw - 1)
        yi = np.clip(np.rint(Y).astype(np.int32), 0, ph - 1)
        self.buf.reshape(-1)[(yi * pw + xi).reshape(-1)] = int(color)

    def segs2d(self, segs, color: int, *, alpha: float = 1.0,
               samples: int = 2) -> None:
        arr = np.asarray(segs, dtype=np.float64)
        if arr.size == 0:
            return
        arr = arr.reshape(-1, 2, 2)
        pw, ph = self.pw, self.ph
        u = np.linspace(0.0, 1.0, max(2, int(samples)))
        X = arr[:, 0:1, 0] + (arr[:, 1:2, 0] - arr[:, 0:1, 0]) * u
        Y = arr[:, 0:1, 1] + (arr[:, 1:2, 1] - arr[:, 0:1, 1]) * u
        xi = np.clip(np.rint(X).astype(np.int32), 0, pw - 1)
        yi = np.clip(np.rint(Y).astype(np.int32), 0, ph - 1)
        packed = _pack_a(color, np.full(xi.size, float(alpha)))
        self.buf.reshape(-1)[(yi * pw + xi).reshape(-1)] = packed

    def line2d(self, x0: float, y0: float, x1: float, y1: float, color: int) -> None:
        self.poly2d([(x0, y0), (x1, y1)], color, samples=2)

    def ring2d(self, cx: float, cy: float, r: float, color: int,
               n: int = 40) -> None:
        a = np.linspace(0.0, 2.0 * math.pi, max(6, int(n)) + 1)
        pts = np.stack([cx + np.cos(a) * r, cy + np.sin(a) * r], axis=1)
        self.poly2d(pts, color, samples=2)

    def vline(self, xi: int, color: int, y0: int = 0, y1: int = None) -> None:
        y1 = self.ph if y1 is None else y1
        y0 = max(0, int(y0))
        y1 = min(self.ph, int(y1))
        xi = int(np.clip(xi, 0, self.pw - 1))
        if y1 > y0:
            self.buf[y0:y1, xi] = int(color)

    # -- commit ---------------------------------------------------------
    def commit(self) -> None:
        flat = self.buf.reshape(-1)
        idx = np.flatnonzero(flat >= 0)
        if idx.size == 0:
            return
        pw = self.pw
        cols = self.cols
        py = idx // pw
        px = idx - py * pw
        cy = py >> 2
        cx = px >> 1
        bit = _BRAILLE_BIT_NP[px & 1, py & 3]
        key = cy * cols + cx
        order = np.argsort(key, kind="stable")
        ks = key[order]
        bits = bit[order]
        vals = flat[idx[order]]
        starts = np.flatnonzero(np.r_[True, ks[1:] != ks[:-1]])
        codes = np.bitwise_or.reduceat(bits, starts)
        r = (vals >> 16) & 255
        g = (vals >> 8) & 255
        b = vals & 255
        n = np.diff(np.r_[starts, len(ks)]).astype(np.int64)
        rr = np.add.reduceat(r, starts) // n
        gg = np.add.reduceat(g, starts) // n
        bb = np.add.reduceat(b, starts) // n
        ukey = ks[starts]
        ucy = self.y0 + (ukey // cols)
        ucx = self.x0 + (ukey % cols)
        ids = _braille_ids(self.c.glyphs)
        ch = self.c.ch
        fg = self.c.fg
        if self.c.clip_enabled:
            ly0, ly1 = self.c.clip_y0, self.c.clip_y1
        else:
            ly0, ly1 = 0, self.c.h
        for k in range(len(ukey)):
            yy = int(ucy[k])
            if yy < ly0 or yy >= ly1:
                continue
            xx = int(ucx[k])
            if 0 <= xx < self.c.w:
                ch[yy][xx] = ids[int(codes[k])]
                fg[yy][xx] = (int(rr[k]) << 16) | (int(gg[k]) << 8) | int(bb[k])


# --------------------------------------------------------------------------
# small shared helpers
# --------------------------------------------------------------------------
def _radial(c, cy: float, cx: float, radius: float, color: int,
            strength: float = 0.5, x0: int = 0, x1: int = None,
            y0: int = C.CONTENT_Y0, y1: int = C.CONTENT_Y1) -> None:
    """Soft radial glow by blending the cell background inside a circle."""
    x1 = c.w if x1 is None else x1
    r2 = radius * radius
    for yy in range(max(y0, C.CONTENT_Y0), min(y1, C.CONTENT_Y1)):
        dy = (yy + 0.5 - cy) * 2.0
        if abs(dy) > radius:
            continue
        for xx in range(max(x0, 0), min(x1, c.w)):
            dx = xx + 0.5 - cx
            d2 = dx * dx + dy * dy
            if d2 >= r2:
                continue
            k = (1.0 - math.sqrt(d2) / radius) ** 2
            c.bg[yy][xx] = C.mix(c.bg[yy][xx], color, strength * k)


def _tracked(c, row: int, text: str, color: int, *, gap: int = 1,
             x0: int = 0, x1: int = None, bg: int = None) -> None:
    s = M.spread_text(text, gap)
    c.text_center(row, s, color, bg, x0=x0, x1=c.w if x1 is None else x1)


def _bolt(dots, x0: float, y0: float, x1: float, y1: float, color: int,
          rng: random.Random, steps: int = 6, jitter: float = 5.0) -> None:
    """Jagged deterministic lightning bolt between two dot positions."""
    pts = [(x0, y0)]
    for i in range(1, steps):
        u = i / steps
        px = x0 + (x1 - x0) * u + rng.uniform(-jitter, jitter) * (0.3 + 0.7 * math.sin(math.pi * u))
        py = y0 + (y1 - y0) * u + rng.uniform(-jitter, jitter) * (0.3 + 0.7 * math.sin(math.pi * u))
        pts.append((px, py))
    pts.append((x1, y1))
    dots.poly2d(pts, color, samples=3)


def _crossings(pa: np.ndarray, pb: np.ndarray):
    """Screen-space intersections of two closed polylines (dot coords)."""
    if len(pa) < 3 or len(pb) < 3:
        return []
    a0 = pa
    a1 = np.roll(pa, -1, axis=0)
    b0 = pb
    b1 = np.roll(pb, -1, axis=0)
    ax = a1[:, 0] - a0[:, 0]
    ay = a1[:, 1] - a0[:, 1]
    bx = b1[:, 0] - b0[:, 0]
    by = b1[:, 1] - b0[:, 1]
    ox = b0[None, :, 0] - a0[:, None, 0]
    oy = b0[None, :, 1] - a0[:, None, 1]
    denom = ax[:, None] * by[None, :] - ay[:, None] * bx[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (ox * by[None, :] - oy * bx[None, :]) / denom
        u = (ox * ay[:, None] - oy * ax[:, None]) / denom
    ok = (np.abs(denom) > 1e-9) & (s >= 0.0) & (s <= 1.0) & (u >= 0.0) & (u <= 1.0)
    if not ok.any():
        return []
    ii, jj = np.nonzero(ok)
    pts = []
    for k in range(len(ii)):
        i, j = int(ii[k]), int(jj[k])
        px = a0[i, 0] + ax[i] * s[i, j]
        py = a0[i, 1] + ay[i] * s[i, j]
        if all((px - q[0]) ** 2 + (py - q[1]) ** 2 > 16 for q in pts):
            pts.append((float(px), float(py)))
    return pts


# --------------------------------------------------------------------------
# precomputed geometry / sprites (built once by prepare)
# --------------------------------------------------------------------------
class _Prep:
    def __init__(self, scene) -> None:
        self.scene = scene
        assets = getattr(scene, "assets", None)
        self.sprites_ready = False
        self.claude = None
        self.dahlia = None
        self._build_terrain()
        self._build_iron()
        self._build_rings()
        self._build_lasers()
        self._build_drum()
        self._build_bone()
        self._build_cloud()
        if assets is not None:
            try:
                self.claude = assets.claude_full(38)
                self.dahlia = assets.dahlia(30)
                self.sprites_ready = True
            except Exception:
                self.claude = None
                self.dahlia = None

    # ---- (a) 3D braille heightfield ----------------------------------
    def _build_terrain(self) -> None:
        nx, nz = 46, 30
        xs = np.linspace(-9.0, 9.0, nx)
        zs = np.linspace(0.8, 16.0, nz)
        X, Z = np.meshgrid(xs, zs, indexing="ij")

        def height(x: float, z: float) -> float:
            a = M.fbm1(x * 0.33 + 7.3, 11, 3) - 0.5
            b = M.fbm1(z * 0.26 + 2.1, 12, 3) - 0.5
            ridge = abs(M.fbm1(x * 0.55 + 1.7, 14, 2) - 0.5)
            basin = math.exp(-(((x - 0.6) ** 2) / 10.0 + ((z - 8.6) ** 2) / 9.0))
            return a * 5.0 + b * 2.4 + ridge * 2.1 - basin * 3.0

        H = np.vectorize(height)(X, Z)
        pts = np.stack([X, H, Z], axis=-1)
        segs = []
        segs.append(np.stack([pts[:-1, :, :], pts[1:, :, :]], axis=2).reshape(-1, 2, 3))
        segs.append(np.stack([pts[:, :-1, :], pts[:, 1:, :]], axis=2).reshape(-1, 2, 3))
        self.terrain = np.concatenate(segs, axis=0)
        levels = (-1.5, -0.75, 0.0, 0.75, 1.5, 2.25)
        self.contours = []
        for lv in levels:
            segs_lv = M.contour_segments(H, lv, -9.0, 9.0, 0.8, 16.0)
            if len(segs_lv):
                self.contours.append(segs_lv)
        rng = random.Random(617)
        dpts = []
        for _ in range(46):
            x = rng.uniform(-2.2, 3.4)
            z = rng.uniform(6.2, 11.2)
            dpts.append((x, height(x, z) + 0.25, z))
        self.dungeon_pts = np.array(dpts)
        self.hubs = np.array([
            (-8.2, 0.0, 5.9),
            (-4.1, 0.0, 4.0),
            (0.2, 0.0, 5.4),
            (4.3, 0.0, 4.1),
            (8.3, 0.0, 6.1),
        ])
        edges = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 2), (2, 4), (1, 3), (1, 4)]
        self.edges = np.array([[self.hubs[a], self.hubs[b]] for a, b in edges])
        self.edge_ids = edges
        sky = random.Random(35)
        self.sky = [(sky.randrange(3, 30), sky.randrange(2, 198),
                     sky.uniform(0.2, 0.8), sky.uniform(0.0, 6.28))
                    for _ in range(64)]

    # ---- (b) iron maiden door slabs ----------------------------------
    def _build_iron(self) -> None:
        try:
            img = keyframe("chamber-door")
        except Exception:
            self.door_bg = None
            self.door_l = None
            self.door_r = None
            return
        from PIL import ImageOps
        full = img.convert("RGB")
        crop = full.crop((int(0.50 * full.width), 0, int(0.995 * full.width), full.height))
        self.door_r = halfblock(crop, 100, bg=C.INK, sat=1.00, contrast=1.12, bright=0.82)
        self.door_l = halfblock(ImageOps.mirror(crop), 100, bg=C.INK,
                                sat=1.00, contrast=1.12, bright=0.82)
        self.door_bg = halfblock(full, 51, bg=C.INK, sat=1.0, contrast=1.05, bright=0.72)
        self.door_w = self.door_r.w

    # ---- (c) ritual rings --------------------------------------------
    def _build_rings(self) -> None:
        n = 72
        a = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
        circ = np.stack([np.cos(a), np.sin(a), np.zeros(n)], axis=1)
        self.ring_unit = circ
        self.ring_ticks = []
        for k in range(24):
            angle = 2.0 * math.pi * k / 24.0
            d = np.array([math.cos(angle), math.sin(angle), 0.0])
            self.ring_ticks.append(np.array([d * 0.90, d * 1.0]))
        self.ring_ticks = np.array(self.ring_ticks)
        self.ring_beats = (100.22, 100.95, 101.67, 102.57, 103.12, 103.55,
                           104.55, 105.47, 105.49, 106.40)
        self.never = "NEVER COLLAPSE"

    # ---- (d) lasers ---------------------------------------------------
    def _build_lasers(self) -> None:
        try:
            img = keyframe("optical-bench").convert("RGB")
        except Exception:
            self.bench_zooms = []
            self.bench = None
            return
        self.bench = halfblock(img, 30, bg=C.INK, sat=1.05, contrast=1.10, bright=1.35)
        from ga1ahad.assets import camera_sprite
        zooms = []
        for i in range(14):
            u = i / 13.0
            sp = camera_sprite(img, 51, 132, zoom=1.0 + 0.62 * u,
                               center=(0.50 + 0.05 * u, 0.47 - 0.02 * u),
                               sat=1.06, contrast=1.10, bright=1.25 + 0.30 * u)
            zooms.append(sp)
        self.bench_zooms = zooms
        self.targets = [(9, 156), (17, 162), (26, 168), (35, 162), (44, 156)]
        self.emitter = (27, 10)
        self.beam_times = (110.35, 110.95, 111.42, 111.80, 112.22)

    # ---- (e1) music-box drum + comb ----------------------------------
    def _build_drum(self) -> None:
        R = 1.9
        angs = np.linspace(0.0, 2.0 * math.pi, 26, endpoint=False)
        xs = np.linspace(-2.6, 2.6, 16)
        segs = []
        for a in angs:
            cy, cz = math.cos(a) * R, math.sin(a) * R
            for k in range(15):
                segs.append([(xs[k], cy, cz), (xs[k + 1], cy, cz)])
        for xi in range(0, 16, 2):
            x = xs[xi]
            for k in range(26):
                a0, a1 = angs[k], angs[(k + 1) % 26]
                segs.append([(x, math.cos(a0) * R, math.sin(a0) * R),
                             (x, math.cos(a1) * R, math.sin(a1) * R)])
        self.drum_mesh = np.array(segs, dtype=np.float64)
        pins = []
        for i in range(26):
            ang = angs[i]
            for j in range(16):
                if (i * 7 + j * 3) % 2 == 0:
                    pins.append((xs[j], math.cos(ang) * (R + 0.10),
                                 math.sin(ang) * (R + 0.10)))
        self.pins = np.array(pins, dtype=np.float64)
        self.drum_rims = []
        for x in (-2.64, 2.64):
            a = np.linspace(0.0, 2.0 * math.pi, 60, endpoint=False)
            ring = np.stack([np.full(60, x), np.cos(a) * R * 1.07,
                             np.sin(a) * R * 1.07], axis=1)
            self.drum_rims.append(np.stack([ring, np.roll(ring, -1, axis=0)], axis=1))
        teeth = []
        for k in range(31):
            x = 292.0 + k * 3.2
            ln = 26 + int(14 * (0.5 + 0.5 * math.sin(k * 1.7)))
            teeth.append((x, 168.0 - ln, x, 168.0))
        self.teeth = teeth
        self.pluck_period = 60.0 / 122.0 / 2.0
        self.pluck_start = 112.78
        self.pluck_end = 120.16

    def plucks(self, t: float):
        period = self.pluck_period
        n0 = int((t - self.pluck_start) / period) - 3
        out = []
        for n in range(n0, n0 + 7):
            at = self.pluck_start + n * period
            age = t - at
            if -0.02 <= age <= 1.6 and at <= self.pluck_end:
                out.append((n, age, at))
        return out

    # ---- (e2) bone vs silicon diptych --------------------------------
    def _build_bone(self) -> None:
        try:
            img = keyframe("bone").convert("RGB")
        except Exception:
            self.bone = None
            self.lattice = np.zeros((0, 2, 2))
            return
        self.bone = halfblock(img, 33, bg=C.INK, sat=0.94, contrast=1.06, bright=1.05)
        segs = []
        r = 13.0
        dy = r * 1.5
        dx = r * math.sqrt(3.0)
        for row_k in range(-2, 9):
            for col_k in range(0, 8):
                cx = 214.0 + col_k * dx + (dx / 2.0 if row_k % 2 else 0.0)
                cy = 30.0 + row_k * dy
                hexagon = [(cx + r * math.cos(math.pi / 3 * k + math.pi / 6),
                            cy + r * math.sin(math.pi / 3 * k + math.pi / 6))
                           for k in range(7)]
                for k in range(6):
                    segs.append([hexagon[k], hexagon[k + 1]])
        self.lattice = np.array(segs, dtype=np.float64)
        rng = random.Random(6170)
        cp = []
        x, y = 100.0, 78.0
        while y < 168.0:
            cp.append((x, y))
            y += rng.uniform(8.0, 13.0)
            x += rng.uniform(-6.0, 6.0)
        self.crack = np.array(cp)

    def _build_cloud(self) -> None:
        self.cloud_sphere = M.sphere_segments(1.0, 9, 16)
        self.cloud_rings = [
            (M.ring_segments(1.55, 56, axes=(0, 1)), 0.55, 0.0),
            (M.ring_segments(1.85, 64, axes=(0, 1)), -0.35, 0.5),
            (M.ring_segments(2.15, 72, axes=(1, 2)), 0.28, 1.1),
        ]
        rng = random.Random(61)
        motes = []
        for i in range(260):
            sx = rng.uniform(72.0, 128.0)
            sy = rng.uniform(148.0, 202.0)
            ex = 200.0 + rng.uniform(-34.0, 34.0)
            ey = 47.0 + rng.uniform(-17.0, 17.0)
            phase = rng.random()
            speed = rng.uniform(0.55, 1.05)
            wob = rng.uniform(0.4, 2.4)
            size = 2 if rng.random() < 0.22 else 1
            motes.append((sx, sy, ex, ey, phase, speed, wob, size))
        self.motes = motes

# --------------------------------------------------------------------------
# prepare / draw entry points
# --------------------------------------------------------------------------
def prepare(scene) -> None:
    """Precompute geometry + sprites on the scene instance (idempotent)."""
    if getattr(scene, "_s35a_prepared", False):
        return
    scene._s35a_prepared = True
    scene._s35a = _Prep(scene)


def _ensure(scene):
    pre = getattr(scene, "_s35a", None)
    if pre is None:
        prepare(scene)
        pre = scene._s35a
    if not pre.sprites_ready:
        try:
            pre.claude = scene.assets.claude_full(38)
            pre.dahlia = scene.assets.dahlia(30)
            pre.sprites_ready = True
        except Exception:
            pass
    return pre


def draw(scene, c, ctx) -> None:
    """Draw one frame of movements I-II of chapter 3.5."""
    pre = _ensure(scene)
    t = ctx.t
    if t < T_IRON:
        _shot_conquest(scene, pre, c, ctx)
    elif t < T_ORINGS:
        _shot_iron(scene, pre, c, ctx)
    elif t < T_LASER:
        _shot_rings(scene, pre, c, ctx)
    elif t < T_DRUM:
        _shot_lasers(scene, pre, c, ctx)
    elif t < T_BONE:
        _shot_drum(scene, pre, c, ctx)
    elif t < T_TULILA:
        _shot_bone(scene, pre, c, ctx)
    elif t < T_CLOUD:
        _shot_drum_reprise(scene, pre, c, ctx)
    else:
        _shot_cloud(scene, pre, c, ctx)


# ==========================================================================
# I.1  90.190-95.680  mountains and dungeons
# ==========================================================================
def _shot_conquest(scene, pre, c, ctx) -> None:
    t = ctx.t
    pu = ctx.audio.pulse(t, 0.15)
    M.bg_gradient(c, C.mix(C.INK, C.CYAN_DEEP, 0.30), C.mix(C.INK, C.CYAN_DEEP, 0.62))
    flat = M.ease_in_out_expo(M.seg(t, 91.85, 93.15))
    cam = M.Camera(
        x=M.lerp(0.0, -0.2, flat),
        y=M.lerp(0.88, 6.35, flat),
        z=M.lerp(-4.7, 5.0, flat),
        yaw=M.lerp(-0.02 + 0.02 * math.sin(t * 0.5), 0.0, flat),
        pitch=M.lerp(-0.175, 1.42, flat),
        fov=M.lerp(1.18, 1.30, flat),
    )
    sweep = M.ease_in_out_expo(M.seg(t, 90.19, 91.55))
    curtain_x = M.lerp(-10.8, 10.8, sweep)
    reveal_on = 1.0 - M.smooth01(91.60, 92.05, t)
    dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    yscale = 1.0 - flat
    geo = [(pre.terrain, C.mix(C.CYAN, C.WHITE, 0.30), 9),
           (np.concatenate(pre.contours, axis=0) if pre.contours else pre.terrain,
            C.mix(C.WHITE, C.CYAN_HI, 0.35), 10)]
    for segs, base_col, samples in geo:
        arr = segs.copy()
        arr[:, :, 1] *= yscale
        mid = arr.mean(axis=1)
        if reveal_on > 0.01:
            behind = mid[:, 0] < curtain_x
            ahead = ~behind
            if behind.any():
                dots.segs(arr[behind], cam, base_col,
                          alpha=1.0 if samples == 10 else 0.96,
                          fog=0.95, samples=samples)
            if ahead.any():
                dots.segs(arr[ahead], cam, C.mix(C.INK, C.CYAN_DEEP, 0.55),
                          alpha=0.62 * reveal_on, fog=0.60, samples=5)
        else:
            dots.segs(arr, cam, base_col,
                      alpha=1.0 if samples == 10 else 0.96, fog=0.95,
                      samples=samples)
    dpts = pre.dungeon_pts.copy()
    dpts[:, 1] *= yscale
    if reveal_on > 0.01 or sweep > 0.05:
        vis = dpts[:, 0] < curtain_x + 0.4
        if vis.any():
            glow = 0.35 + 0.55 * pu
            cols = np.full(int(vis.sum()), C.mix(C.GOLD_DIM, C.GOLD_HI, glow),
                           dtype=np.int64)
            dots.points(dpts[vis], cam, cols, alpha=0.8, fog=0.45, zmax=12.0)
    if reveal_on > 0.01:
        for zz in (3.0, 8.0, 13.0):
            pxs, _, _ = M.project(np.array([[curtain_x, 0.0, zz]]), cam, dots.pw, dots.ph)
            xi = int(np.clip(pxs[0], 0, dots.pw - 1))
            dots.vline(xi, C.mix(WHITE, C.CYAN_HI, 0.20))
            for off, col in ((-2, 0.42), (-1, 0.82), (1, 0.82), (2, 0.42)):
                if 0 <= xi + off < dots.pw:
                    dots.vline(xi + off, C.mix(C.INK, C.CYAN_HI, col * reveal_on))
    if flat > 0.42:
        net = M.smooth01(0.42, 0.80, flat)
        dots.segs(pre.edges, cam, C.mix(C.GOLD, C.WHITE, 0.35),
                  alpha=0.90 * net, fog=0.55, samples=10)
        for ei, (a, b) in enumerate(pre.edge_ids):
            p0 = pre.hubs[a]
            p1 = pre.hubs[b]
            run = M.seg(t, 94.30 + ei * 0.05, 94.95 + ei * 0.05)
            if run <= 0.0:
                continue
            lvl = 0.5 + 0.5 * math.sin((t * 3.4 + ei * 1.7) * math.pi)
            pt = p0 + (p1 - p0) * run
            dots.points(np.array([pt]), cam, [C.mix(C.GOLD, C.GOLD_HI, lvl)],
                        alpha=0.9, fog=0.35, zmax=10.0, size=2)
        hx, hy, hz = M.project(pre.hubs, cam, dots.pw, dots.ph)
        titles = scene.script.v2.conquest.title
        for i, (x, y, z) in enumerate(zip(hx, hy, hz)):
            if z <= 0.05:
                continue
            lit = M.seg(t, 92.45 + i * 0.16, 92.45 + i * 0.16 + 0.22)
            if lit > 0:
                lit = M.spring(lit, 2.6, 0.42)
            col = C.mix(C.INK, C.GOLD_HI, 0.25 + 0.70 * lit)
            r = 10.0 + 7.0 * lit + 2.5 * pu
            dots.ring2d(x, y, r, col, n=36)
            dots.ring2d(x, y, r * 0.55, C.mix(col, WHITE, 0.40), n=28)
            if lit > 0.15:
                for k in range(6):
                    a2 = k * math.pi / 3.0 + t * 0.4
                    dots.line2d(x + math.cos(a2) * (r + 3), y + math.sin(a2) * (r + 3),
                                x + math.cos(a2) * (r + 10), y + math.sin(a2) * (r + 10),
                                C.mix(C.INK, C.GOLD_DIM, 0.7 * lit))
        dots.commit()
        for i, (x, y, z) in enumerate(zip(hx, hy, hz)):
            if z <= 0.05:
                continue
            label = titles.domain_names[i]
            lx = int(x // 2) - len(label) // 2
            ly = int(y // 4) + 3
            lit = M.seg(t, 92.45 + i * 0.16, 92.45 + i * 0.16 + 0.22)
            col = C.mix(C.INK, C.mix(C.GOLD_HI, C.WHITE, 0.25), 0.55 + 0.45 * lit)
            c.text(ly, lx, label, col, None)
    else:
        dots.commit()
    for yy in range(29, 40):
        kk = (40 - yy) / 11.0
        for xx in range(0, c.w):
            c.bg[yy][xx] = C.mix(c.bg[yy][xx], C.CYAN_DEEP,
                                 (0.22 + 0.24 * pu) * kk * (0.35 + 0.65 * flat))
    for (ry, rx, k, ph) in pre.sky:
        tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 0.9 + ph))
        c.put(ry, rx, ".", C.mix(C.INK, C.CYAN, k * tw * (0.55 + 0.45 * (1 - flat))))
    tag = scene.script.acts.a1.tag
    c.text(3, 3, tag[:40], C.mix(C.INK, C.CYAN_HI, 0.90), None, bold=True)
    c.text(3, 3 + len(tag[:40]) + 2, scene.script.acts.a1.mode[:36],
           C.mix(C.INK, C.mix(TEXT_DIM, C.CYAN, 0.5), 0.78), None)
    cap_y = 47
    cap = scene.script.acts.a1.banner
    if t > 92.70:
        prog = M.seg(t, 92.70, 93.80)
        txt = M.split_flap(M.spread_text(cap, 1), prog, seed=617)
        col = C.mix(C.INK, C.mix(C.GOLD_HI, C.WHITE, 0.20), 0.45 + 0.55 * M.smooth01(92.70, 93.8, t))
        c.text_center(cap_y, txt, col, None, bold=prog > 0.85)
    if t > 93.0:
        w = int(M.smooth01(93.0, 93.9, t) * 150)
        c.hline(cap_y + 1, 100 - w // 2, 100 + w // 2,
                C.mix(C.INK, C.GOLD_DIM, 0.5), None, "-")
    if t > 95.40:
        k = M.seg(t, 95.40, T_IRON)
        M.punctuate(c, t - 95.40, flash=0.10 * k, shake=1.4 * k, decay=0.30,
                    flash_color=C.mix(C.CYAN_HI, WHITE, 0.4))
    M.grain(c, t, seed=7, count=60, color=C.CYAN_DIM, amount=0.06)
    M.vignette(c, 0.18)


# ==========================================================================
# I.2  95.680-99.570  Iron maiden
# ==========================================================================
def _shot_iron(scene, pre, c, ctx) -> None:
    t = ctx.t
    q = M.seg(t, T_IRON, T_ORINGS)
    pu = ctx.audio.pulse(t, 0.14)
    M.bg_gradient(c, C.mix(C.INK, C.BLUE, 0.10), C.INK)
    # the cold corridor keyframe (full-bleed, pushed toward the void)
    if pre.door_bg is not None:
        dim = 1.0 - 0.55 * M.smooth01(95.9, 96.6, t)
        c.sprite(2, 33, pre.door_bg, fg_mul=0.55 * dim,
                 tint=C.CYAN_DIM, tint_amt=0.10)
    # cold light from above
    for yy in range(2, 9):
        k = (9 - yy) / 7.0
        for xx in range(0, c.w):
            c.bg[yy][xx] = C.mix(c.bg[yy][xx], C.CYAN_DEEP, 0.20 * k)
    # -- blast door slabs slam shut -------------------------------------
    if pre.door_r is not None:
        slam_a, slam_b = 96.45, 96.72
        ua = M.seg(t, 95.84, slam_a)
        ub = M.seg(t, 96.00, slam_b)
        ka = M.spring(ua, 2.8, 0.46)
        kb = M.spring(ub, 2.8, 0.46)
        closed_l, closed_r = -22.0, 100.0
        xl = M.lerp(-pre.door_w - 8.0, closed_l, ka)
        xr = M.lerp(208.0, closed_r, kb)
        age_a = t - slam_a
        age_b = t - slam_b
        if age_a > 0:
            sh = 2.6 * M.impulse(age_a, 3.0, 0.10) + 1.1 * M.impulse(age_a - 0.13, 4.4, 0.05)
            xl += sh
            xr -= sh * 0.8
        if age_b > 0:
            sh = 2.6 * M.impulse(age_b, 3.0, 0.10) + 1.1 * M.impulse(age_b - 0.13, 4.4, 0.05)
            xr -= sh
            xl += sh * 0.8
        c.sprite(2, int(round(xl)), pre.door_l)
        c.sprite(2, int(round(xr)), pre.door_r)
        # hot seam glow between the slabs
        seam = 0.5 * ((xl + pre.door_w) + xr)
        gap = max(0.0, xr - (xl + pre.door_w))
        close_k = M.smooth01(slam_b - 0.1, slam_b + 0.5, t)
        heat = (0.35 + 0.65 * pu * close_k + 0.45 * M.hit(t - slam_b, 0.35))
        sx = int(round(seam))
        for off, a in ((-2, 0.22), (-1, 0.55), (0, 1.0), (1, 0.55), (2, 0.22)):
            if 0 <= sx + off < c.w:
                c.vline(sx + off, 2, 53, C.mix(C.INK, C.mix(RED_HI, WHITE, 0.40),
                                               min(1.0, a * close_k * (0.6 + 0.6 * heat))),
                        None, "|")
        # gap light (the corridor bleeding through before the seal)
        if gap > 1.4:
            gcol = C.mix(C.INK, RED_HI, 0.55 * (1.0 - close_k) + 0.2)
            for off in range(int(gap)):
                xx = int(xl + pre.door_w) + off
                if 0 <= xx < c.w:
                    c.vline(xx, 2, 53, gcol, None, "|")
    # -- neural alignment probes tightening in the seam -----------------
    dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    seam_c = 100.0
    seam_d = seam_c * 2.0
    probe_p = M.smooth01(97.20, 99.05, t)
    probes_on = t > 97.0
    if probes_on:
        n = 16
        for i in range(n):
            u = M.stagger(i, n, probe_p, 0.52)
            if u <= 0.0:
                continue
            yy = 10.0 + i * 11.6
            reach = 30.0 - 25.0 * u
            # left probe from the left slab, right probe from the right slab
            dots.line2d(seam_d - 34.0, yy, seam_d - reach, yy,
                        C.mix(C.INK, C.CYAN_DIM, 0.75))
            dots.line2d(seam_d + 34.0, yy, seam_d + reach, yy,
                        C.mix(C.INK, C.CYAN_DIM, 0.75))
            tip = C.mix(C.CYAN_HI, WHITE, 0.35 + 0.35 * pu)
            dots.points(np.array([[seam_d - reach, yy, 0.0]]), None, [tip], alpha=1.0) if False else None
            dots.line2d(seam_d - reach - 2, yy, seam_d - reach + 2, yy, tip)
            dots.line2d(seam_d + reach - 2, yy, seam_d + reach + 2, yy, tip)
            if u >= 0.92:
                dots.line2d(seam_d - 4, yy, seam_d + 4, yy, C.mix(C.CYAN_HI, WHITE, 0.5))
        # neural chain inside the seam
        for yy in range(12, 196, 13):
            dots.line2d(seam_d - 2, yy, seam_d + 2, yy,
                        C.mix(C.INK, C.CYAN_DIM, 0.55))
    dots.commit()
    # -- dust / frost ----------------------------------------------------
    rng = random.Random(9617)
    for i in range(26):
        bx = rng.uniform(2, 198)
        by = rng.uniform(2, 52)
        sp = rng.uniform(0.3, 1.1)
        ph = rng.uniform(0.0, 6.28)
        yy = 2 + int((by + t * sp) % 50)
        xx = int(bx + math.sin(t * 0.5 + ph) * 3)
        c.put(yy, xx, ".", C.mix(C.INK, C.CYAN_DIM, 0.35 + 0.3 * pu))
    # -- labels ----------------------------------------------------------
    tag = scene.script.acts.a2.tag
    c.text(3, 3, tag[:40], C.mix(C.INK, C.BLUE, 0.70), None, bold=True)
    c.text(3, 3 + len(tag[:40]) + 2, scene.script.acts.a2.mode[:34],
           C.mix(C.INK, TEXT_DIM, 0.55), None)
    c.text(4, c.w - 46, scene.script.iron.plan[:43], C.mix(C.INK, TEXT_FAINT, 0.75), None)
    if t > 98.85:
        prog = M.seg(t, 98.85, 99.55)
        txt = M.split_flap(M.spread_text(scene.script.iron.no_exit, 1), prog, seed=96)
        c.text_center(48, txt, C.mix(C.INK, RED_HI, 0.45 + 0.45 * prog), None,
                      bold=prog > 0.8)
        w = int(M.smooth01(98.85, 99.55, t) * 130)
        c.hline(49, 100 - w // 2, 100 + w // 2, C.mix(C.INK, RED_DIM, 0.7), None, "-")
    # -- metal shudder + slams ------------------------------------------
    for at, fl, sh in ((slam_a, 0.20, 3.6), (slam_b, 0.24, 4.2), (99.30, 0.30, 5.0)):
        age = t - at
        if age >= 0:
            M.punctuate(c, age, flash=fl, shake=sh, chroma=0.16 if age < 0.2 else 0.0,
                        decay=0.13, flash_color=C.mix(RED_HI, WHITE, 0.62))
    if t > 99.35:
        k = M.seg(t, 99.35, T_ORINGS)
        M.punctuate(c, t - 99.35, flash=0.16 * k, shake=2.0 * k, decay=0.5,
                    flash_color=C.mix(C.RED_HI, C.WHITE, 0.6))
    M.vignette(c, 0.52)
    M.grain(c, t, seed=17, count=70, color=C.CYAN_DIM, amount=0.07)


# ==========================================================================
# I.3  99.570-107.100  the two ritual rings
# ==========================================================================
def _shot_rings(scene, pre, c, ctx) -> None:
    t = ctx.t
    pu = ctx.audio.pulse(t, 0.13)
    e = ctx.audio.energy(t)
    M.bg_gradient(c, C.INK, C.mix(C.INK, C.RED_DEEP, 0.26))
    _radial(c, 27.0, 100.0, 54.0, C.mix(C.INK, C.TERRA_DEEP, 0.85), 0.55)
    _radial(c, 26.0, 100.0, 26.0, C.mix(C.INK, C.GOLD_DEEP, 0.8), 0.30)
    form = M.spring(M.seg(t, T_ORINGS + 0.10, 100.45), 2.4, 0.44)
    if form <= 0.0:
        form = 0.0
    # -- camera + ring transforms ---------------------------------------
    push = 1.0 + 0.10 * M.seg(t, 103.4, 106.6) + 0.02 * pu
    cam = M.Camera(y=0.0, z=0.38 + 0.18 * math.sin(t * 0.33), fov=0.97 / push)
    spin_a = t * 0.62
    spin_b = -t * 0.47
    converge = M.spring(M.seg(t, 105.15, 105.95), 2.2, 0.40) * 0.42
    cA = np.array([0.55 - converge, 0.10, 6.40])
    cB = np.array([-0.55 + converge, -0.05, 6.62])
    circleA = M.orbit(pre.ring_unit * 5.20, roll=spin_a, yaw=0.58, pitch=0.10)
    circleB = M.orbit(pre.ring_unit * 5.70, roll=spin_b, yaw=-0.62, pitch=-0.12)
    circleA = cA + circleA * max(0.0, min(1.0, form))
    circleB = cB + circleB * max(0.0, min(1.0, form))
    ticksA = (pre.ring_ticks.reshape(-1, 3) * 5.20)
    ticksB = (pre.ring_ticks.reshape(-1, 3) * 5.70)
    ticksA = cA + M.orbit(ticksA, roll=spin_a, yaw=0.58, pitch=0.10).reshape(-1, 2, 3) * max(0.0, min(1.0, form))
    ticksB = cB + M.orbit(ticksB, roll=spin_b, yaw=-0.62, pitch=-0.12).reshape(-1, 2, 3) * max(0.0, min(1.0, form))
    dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    pw, ph = dots.pw, dots.ph
    # split each ring into back / front halves for the Claude occlusion
    zcut = 6.6
    _, _, zA = M.project(circleA, cam, pw, ph)
    _, _, zB = M.project(circleB, cam, pw, ph)
    backA = np.roll(zA, 1) >= zcut
    backB = np.roll(zB, 1) >= zcut
    # -- voiceprint intro (becomes the rings) ---------------------------
    wave_a = 1.0 - M.smooth01(T_ORINGS + 0.05, T_ORINGS + 0.95, t)
    if wave_a > 0.01:
        spec = ctx.audio.spectrum(t)
        pts = []
        for k in range(0, 200):
            u = k / 199.0
            v = float(spec[int(u * 23)]) * (0.35 + 0.65 * e)
            env = math.sin(math.pi * u) ** 0.5
            pts.append((u * pw, ph * 0.52 - (v - 0.28) * 96.0 * env))
        dots.poly2d(pts, C.mix(C.INK, C.CYAN_HI, 0.80 * wave_a), samples=2)
        pts2 = [(x, ph - y) for (x, y) in pts]
        dots.poly2d(pts2, C.mix(C.INK, CYAN_DIM, 0.40 * wave_a), samples=2)
    # build segment arrays for the two rings
    segA = np.stack([circleA, np.roll(circleA, -1, axis=0)], axis=1)
    segB = np.stack([circleB, np.roll(circleB, -1, axis=0)], axis=1)
    ta = np.stack([ticksA[:, 0], ticksA[:, 1]], axis=1)
    tb = np.stack([ticksB[:, 0], ticksB[:, 1]], axis=1)
    _, _, ztA = M.project(ta.reshape(-1, 3), cam, pw, ph)
    _, _, ztB = M.project(tb.reshape(-1, 3), cam, pw, ph)
    tbackA = ztA.reshape(-1, 2).mean(axis=1) >= zcut
    tbackB = ztB.reshape(-1, 2).mean(axis=1) >= zcut
    colA = C.mix(CYAN_HI, WHITE, 0.25)
    colB = C.mix(RED_HI, WHITE, 0.22)
    backdrop = 1.0 - wave_a
    if backdrop > 0.02:
        dots.segs(segA[~backA], cam, colA, alpha=0.95, fog=0.60, samples=7)
        dots.segs(segB[~backB], cam, colB, alpha=0.95, fog=0.60, samples=7)
        dots.segs(ta[~tbackA], cam, C.mix(colA, WHITE, 0.2),
                  alpha=0.85, fog=0.5, samples=3)
        dots.segs(tb[~tbackB], cam, C.mix(colB, WHITE, 0.2),
                  alpha=0.85, fog=0.5, samples=3)
        endA = ticksA[:, 1]
        endB = ticksB[:, 1]
        dots.points(endA, cam, np.full(len(endA), C.mix(colA, WHITE, 0.45)),
                    alpha=0.95, fog=0.35, size=2)
        dots.points(endB, cam, np.full(len(endB), C.mix(colB, WHITE, 0.45)),
                    alpha=0.95, fog=0.35, size=2)
    dots.commit()
    # -- Claude's 2D avatar standing still at the centre ------------------
    if pre.claude is not None:
        sx = (c.w - pre.claude.w) // 2
        c.sprite(9, sx, pre.claude, fg_mul=0.92 + 0.08 * e,
                 tint=C.GOLD_HI, tint_amt=0.05 + 0.04 * pu)
        # rim glow around the silhouette
        for k, rad in enumerate((3, 5, 8)):
            cc = C.mix(C.INK, [C.TERRA_HI, C.GOLD_HI, C.TERRA_PALE][k],
                       0.30 + 0.20 * pu - k * 0.05)
            c.put(9 + k, sx - 1 - k, "/", cc)
            c.put(9 + k, sx + pre.claude.w + k, "\\", cc)
    # -- front halves over her body -------------------------------------
    dots2 = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    if backdrop > 0.02:
        dots2.segs(segA[backA], cam, colA, alpha=1.0, fog=0.62, samples=7)
        dots2.segs(segB[backB], cam, colB, alpha=1.0, fog=0.62, samples=7)
        dots2.segs(ta[tbackA], cam, C.mix(colA, WHITE, 0.3), alpha=0.9, fog=0.45, samples=3)
        dots2.segs(tb[tbackB], cam, C.mix(colB, WHITE, 0.3), alpha=0.9, fog=0.45, samples=3)
        dots2.points(ticksA[:, 1][tbackA], cam,
                     np.full(int(tbackA.sum()), C.mix(colA, WHITE, 0.45)),
                     alpha=0.95, fog=0.35, size=2)
        dots2.points(ticksB[:, 1][tbackB], cam,
                     np.full(int(tbackB.sum()), C.mix(colB, WHITE, 0.45)),
                     alpha=0.95, fog=0.35, size=2)
    dots2.commit()
    # -- electric arcs at the crossings ---------------------------------
    pa = np.column_stack(M.project(circleA, cam, pw, ph)[:2])
    pb = np.column_stack(M.project(circleB, cam, pw, ph)[:2])
    cross = _crossings(pa, pb)
    beat_glow = 0.0
    for bt in pre.ring_beats:
        age = t - bt
        if 0.0 <= age < 0.55:
            beat_glow = max(beat_glow, math.exp(-age / 0.16))
    arc = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    for ci, (xx, yy) in enumerate(cross):
        rng = random.Random(int(t * 60) * 31 + ci * 7)
        amp = (1.0 if ci == 0 else 0.7) * (0.35 + 0.65 * pu + 0.9 * beat_glow)
        for rep in range(3):
            rng2 = random.Random(int(t * 60) * 17 + ci * 5 + rep)
            ang = rng2.uniform(-math.pi, math.pi)
            ln = 18.0 + 74.0 * amp
            ex = xx + math.cos(ang) * ln
            ey = yy + math.sin(ang) * ln
            _bolt(arc, xx, yy, ex, ey,
                  C.mix(C.WHITE, colA if ci % 2 == 0 else colB, 0.45), rng2,
                  steps=5, jitter=4.0 + 6.0 * amp)
        arc.ring2d(xx, yy, 3.0 + 5.0 * amp, C.mix(C.INK, C.WHITE, 0.85 * amp), n=20)
        # a second short arc crawling along the ring tangents
        rng3 = random.Random(int(t * 47) + ci)
        for _ in range(3):
            a0 = rng3.uniform(0, 2 * math.pi)
            r = 20.0 + 30.0 * rng3.random()
            _bolt(arc, xx + math.cos(a0) * r, yy + math.sin(a0) * r,
                  xx + math.cos(a0 + 1.4) * r, yy + math.sin(a0 + 1.4) * r,
                  C.mix(C.INK, C.CYAN_HI if ci % 2 == 0 else C.RED_HI, 0.5), rng3,
                  steps=3, jitter=3.0)
    if cross:
        arc.commit()
    # -- typography ------------------------------------------------------
    title = scene.script.v2.oath.title
    M.rule_row(c, 3, title.text[:80], C.mix(C.INK, C.GOLD_DIM, 0.55),
               fg=C.mix(C.INK, C.GOLD_HI, 0.62))
    dec = scene.script.voice.decree
    for i in range(2):
        line = dec[i] if i < len(dec) else ""
        if not line:
            continue
        typed = M.type_text(line, t, 100.1 + i * 0.9, cps=26.0)
        c.text_center(5 + i, typed, C.mix(C.INK, C.AMBER_HI, 0.62), None)
    # article labels
    if t > 100.9:
        k = M.smooth01(100.9, 101.7, t)
        c.text(49, 6, M.spread_text(title.oath_a[:40], 1),
               C.mix(C.INK, CYAN_HI, 0.30 + 0.55 * k), None)
    if t > 101.6:
        k = M.smooth01(101.6, 102.4, t)
        s = M.spread_text(title.oath_b[:44], 1)
        c.text(49, c.w - len(s) - 6, s, C.mix(C.INK, RED_HI, 0.30 + 0.55 * k), None)
    # the daemon stencil on the floor
    if t > T_OATH - 0.02:
        k = M.seg(t, T_OATH - 0.02, T_OATH + 0.45)
        txt = M.split_flap(pre.never, k, seed=617)
        w, hgt = M.big_text_size(pre.never, 1, 1)
        col = C.mix(C.INK, WHITE, 0.30 + 0.45 * M.smooth01(T_OATH, T_OATH + 0.8, t))
        M.big_text(c, 43, (c.w - w) // 2, txt, col, scale=1, spacing=1)
        if t >= T_OATH:
            M.punctuate(c, t - T_OATH, flash=0.18, chroma=0.12, shake=1.8,
                        decay=0.20, flash_color=C.mix(C.WHITE, C.GOLD_HI, 0.35))
    # -- ring seal / hand-off -------------------------------------------
    if t > 105.6:
        k = M.smooth01(105.6, 106.4, t)
        seal = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        seal.ring2d(pw * 0.5, ph * 0.5, 148.0 * (1.0 + 0.02 * pu), C.mix(C.INK, WHITE, 0.55 * k), n=90)
        seal.ring2d(pw * 0.5, ph * 0.5, 152.0 * (1.0 + 0.02 * pu), C.mix(C.INK, GOLD_HI, 0.4 * k), n=90)
        seal.commit()
    if t > 106.70:
        k = M.seg(t, 106.70, T_LASER)
        M.punctuate(c, t - 106.70, flash=0.34 * k, chroma=0.18 * k, shake=2.6 * k,
                    decay=0.55, flash_color=C.mix(C.CYAN_HI, C.WHITE, 0.8))
    M.grain(c, t, seed=617, count=60, color=C.CYAN_DIM, amount=0.05)
    M.vignette(c, 0.30)



# ==========================================================================
# II.1  107.100-112.730  optical charge + full discharge
# ==========================================================================
def _shot_lasers(scene, pre, c, ctx) -> None:
    t = ctx.t
    pu = ctx.audio.pulse(t, 0.12)
    title = scene.script.v2.lasers.title
    M.bg_gradient(c, C.INK, C.mix(C.INK, C.RED_DEEP, 0.32))
    if t < 109.45:
        # -- real dialogue beat: Dahlia's sign-off -----------------------
        dlg = M.Dialog(c, *C.DLG_SLOTS[0], title=scene.T.claude_code_desktop,
                       right="SIGN-OFF", accent=C.mix(C.BORDER_HI, C.ORANGE, 0.55),
                       bg=C.mix(C.INK, C.PANEL, 0.34))
        dlg.label(1, title.text[:40], C.mix(C.INK, C.ORANGE, 0.80))
        dlg.rule(2, "RING-0 AUTHORITY", C.mix(C.INK, C.ORANGE, 0.38))
        msgs = scene.script.v2.lasers.dialog
        starts = (107.30, 108.72)
        yy = 4
        for i, msg in enumerate(msgs[:2]):
            is_op = msg.who in (scene.T.dahlia_handle, "user", "subject")
            speaker = scene.script.v2.speaker_dahlia if is_op else scene.script.v2.speaker_core
            col = C.AMBER_HI if is_op else C.CYAN_HI
            typed = M.type_text(msg.text, t, starts[i], cps=46.0)
            dlg.text(yy, ("> " if is_op else "o ") + speaker.upper(), col, bold=True)
            yy += 1
            for ln in wrap(typed, dlg.width):
                if yy < dlg.h - 6:
                    dlg.text(yy, ln, col)
                yy += 1
            yy += 1
        q = M.seg(t, 107.15, 110.3)
        dlg.footer(44, title.footer[:52])
        dlg.footer(45, f"{title.hv_label} {4.8 * q:4.2f} MV   {title.cap_banks[0]} {int(100 * q):3d}%")
        dlg.cursor(dlg.h - 2, 0, t, C.ORANGE)
        # right stage: the optical bench charges
        if pre.bench is not None:
            x = 66 + int(round(1.6 * math.sin(t * 0.7)))
            c.sprite(9, x, pre.bench, fg_mul=0.50 + 0.55 * q,
                     tint=C.RED_HI, tint_amt=0.05)
            lx, ly = 105.0, 24.0
            dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
            for k in range(4):
                rr = 68.0 * (1.0 - q * q) + 8.0 + k * 5.0
                col = C.mix(C.INK, C.mix(C.ORANGE, C.WHITE, 0.30 + 0.50 * q),
                            0.35 + 0.55 * q)
                dots.ring2d(lx * 2 + 1, (ly - 2) * 4 + 2, rr, col, n=54)
            rng = random.Random(int(t * 30))
            for _ in range(3):
                a0 = rng.uniform(0, 2 * math.pi)
                r0 = 30.0 + 40.0 * rng.random()
                _bolt(dots, lx * 2 + math.cos(a0) * r0, (ly - 2) * 4 + math.sin(a0) * r0,
                      lx * 2 + math.cos(a0 + 0.7) * (r0 - 20),
                      (ly - 2) * 4 + math.sin(a0 + 0.7) * (r0 - 20),
                      C.mix(C.ORANGE, C.WHITE, 0.55 * q), rng, steps=3, jitter=4.0)
            dots.commit()
            c.text(45, 138, scene.script.laser.charge_word, C.mix(C.INK, C.ORANGE, 0.30 + 0.55 * q), None, bold=True)
            if q > 0.88:
                c.text(46, 132, scene.script.laser.overload[:26], C.mix(C.INK, RED_HI, (q - 0.88) * 8.0), None, bold=True)
        M.shutter(c, t, 109.35, 0.34, bands=8, color=C.INK,
                  hi=C.mix(C.ORANGE, C.WHITE, 0.45))
        M.vignette(c, 0.42)
        return
    if t < 110.30:
        # -- push-in on the charged lens --------------------------------
        u = M.ease_in_expo(M.seg(t, 109.70, 110.30))
        idx = min(len(pre.bench_zooms) - 1, int(u * len(pre.bench_zooms)))
        if pre.bench_zooms:
            c.sprite(2, 34, pre.bench_zooms[idx], fg_mul=0.72 + 0.35 * u,
                     tint=C.RED_HI, tint_amt=0.05)
        dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        cx, cy = 200.0, 92.0
        for k in range(5):
            rr = 96.0 * (1.0 - u) + 6.0 + k * 5.0 + 3.0 * pu
            col = C.mix(C.INK, C.mix(C.ORANGE, C.WHITE, 0.35 + 0.5 * u),
                        0.25 + 0.70 * u)
            dots.ring2d(cx, cy, rr, col, n=60)
        rng = random.Random(int(t * 40))
        for _ in range(5):
            a0 = rng.uniform(0, 2 * math.pi)
            r0 = 40.0 + 70.0 * rng.random()
            _bolt(dots, cx + math.cos(a0) * r0, cy + math.sin(a0) * r0,
                  cx + math.cos(a0 + 0.5) * 20, cy + math.sin(a0 + 0.5) * 20,
                  C.mix(C.ORANGE, C.WHITE, 0.5 + 0.5 * u), rng, steps=4, jitter=6.0)
        dots.commit()
        M.iris(c, 100.0, 25.0, M.lerp(120.0, 26.0, u), soft=14.0, amount=0.88)
        c.text(46, 84, scene.script.laser.charge_word, C.mix(C.INK, C.ORANGE, 0.35 + 0.6 * u), None, bold=True)
        k2 = M.seg(t, 110.22, 110.30)
        M.punctuate(c, t - 110.30, flash=0.20 * k2, shake=2.0 * k2, decay=0.4,
                    flash_color=C.mix(C.ORANGE, C.WHITE, 0.6))
        M.vignette(c, 0.55)
        return
    # -- full-width discharge -------------------------------------------
    q = M.seg(t, 110.30, T_DRUM)
    ey, ex = pre.emitter
    hit_glow = 0.0
    for bt in pre.beam_times:
        age = t - bt
        if 0.0 <= age < 0.4:
            hit_glow = max(hit_glow, math.exp(-age / 0.10))
    _radial(c, ey, ex + 4, 34.0, C.mix(C.INK, C.RED_DEEP, 0.95), 0.60)
    dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    ecx, ecy = ex * 2, (ey - 2) * 4 + 2
    dots.ring2d(ecx, ecy, 10.0 + 4.0 * pu, C.mix(C.INK, C.WHITE, 0.92), n=36)
    dots.ring2d(ecx, ecy, 17.0 + 6.0 * pu, C.mix(C.INK, C.ORANGE, 0.55), n=40)
    for k in range(3):
        rr = 24.0 + k * 9.0 + 6.0 * pu
        dots.ring2d(ecx, ecy, rr, C.mix(C.INK, C.RED_HI, 0.45 - k * 0.10), n=42)
    dots.commit()
    # target nodes are visible before they are hit
    dots3 = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    for i, (ty, tx) in enumerate(pre.targets):
        if t < pre.beam_times[i] + 0.12:
            dots3.ring2d(tx * 2, (ty - 2) * 4 + 2, 13.0,
                         C.mix(CYAN, WHITE, 0.18), n=24)
            dots3.ring2d(tx * 2, (ty - 2) * 4 + 2, 6.0,
                         C.mix(C.CYAN_HI, WHITE, 0.30), n=16)
    dots3.commit()
    fired = 0
    for i, (ty, tx) in enumerate(pre.targets):
        ft = pre.beam_times[i]
        if t < ft:
            continue
        fired += 1
        fire = M.seg(t, ft, ft + 0.13)
        reach = M.ease_out_expo(fire)
        x1 = ex + (tx - ex) * reach
        y1 = ey + (ty - ey) * reach
        steps = max(2, int(x1 - ex))
        for k in range(steps):
            u = k / max(1, steps)
            bx = int(ex + (x1 - ex) * u)
            by = int(ey + (y1 - ey) * u + math.sin(u * math.pi) * 4.0 * (1.0 - 0.4 * reach))
            c.put(by, bx, "\u2588", C.mix(C.GOLD_HI, WHITE, 0.45 + 0.40 * pu))
            c.put(by - 1, bx, "\u2593", C.mix(C.ORANGE, C.RED_HI, 0.35))
            c.put(by + 1, bx, "\u2591", C.mix(C.RED_HI, C.ORANGE, 0.55))
        hit = t >= ft + 0.12
        if hit:
            age = t - ft - 0.12
            k = math.exp(-age / 0.30)
            tcol = C.mix(C.RED_HI, C.WHITE, 0.6 * k + 0.4 * pu) if age < 0.5 else C.mix(C.INK, C.CYAN_HI, 0.55)
            c.text(ty + 2, tx + 4, title.targets[i], tcol, None, bold=age < 1.0)
            if age < 0.55:
                dd = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
                for r2 in (9.0, 15.0, 22.0):
                    rr = r2 + 40.0 * (1.0 - math.exp(-age / 0.18))
                    dd.ring2d(tx * 2, (ty - 2) * 4 + 2, rr,
                              C.mix(C.INK, C.WHITE, 0.65 * k), n=30)
                dd.ring2d(tx * 2, (ty - 2) * 4 + 2, 8.0,
                          C.mix(C.INK, C.RED_HI, 0.8 * k), n=24)
                dd.commit()
                M.punctuate(c, age, flash=0.055 * k, shake=1.1 * k, decay=0.10)
    # top banner + bottom telemetry strip
    bcol = C.mix(C.INK, C.mix(C.ORANGE, C.WHITE, 0.35), 0.35 + 0.5 * q)
    _tracked(c, 3, title.beam_banner, bcol, x1=196)
    if q > 0.9:
        M.punctuate(c, t - 112.45, flash=0.45, chroma=0.25, shake=5.0, decay=0.22,
                    flash_color=C.mix(C.WHITE, C.GOLD_HI, 0.4))
    M.grain(c, t, seed=11, count=70, color=C.ORANGE, amount=0.06)
    M.vignette(c, 0.42)


# ==========================================================================
# II.2a  112.730-115.140 / II.3  117.860-120.290  the music box
# ==========================================================================
def _drum_frame(scene, pre, c, t: float, *, spin: float, cam: M.Camera,
                drum_x: float = -1.4, drum_z: float = 4.3,
                gold: int = C.GOLD) -> None:
    ca, sa = math.cos(spin), math.sin(spin)

    def rot(P):
        P = np.asarray(P, dtype=np.float64)
        x = P[..., 0] + drum_x
        y = P[..., 1] * ca - P[..., 2] * sa
        z = P[..., 1] * sa + P[..., 2] * ca
        return np.stack([x, y, z + drum_z], axis=-1)

    dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    dots.segs(rot(pre.drum_mesh), cam, C.mix(gold, WHITE, 0.30),
              alpha=0.85, fog=0.55, samples=4)
    pins = rot(pre.pins)
    _, _, pz = M.project(pins, cam, dots.pw, dots.ph)
    front = pz < drum_z
    if front.any():
        dots.points(pins[front], cam,
                    np.full(int(front.sum()), C.mix(gold, WHITE, 0.60)),
                    alpha=1.0, fog=0.50, zmin=1.0, zmax=6.5)
    if (~front).any():
        dots.points(pins[~front], cam,
                    np.full(int((~front).sum()), C.mix(C.INK, gold, 0.55)),
                    alpha=0.55, fog=0.55, zmin=1.0, zmax=6.5)
    rims = rot(np.concatenate(pre.drum_rims))
    dots.segs(rims, cam, C.mix(gold, WHITE, 0.55), alpha=1.0, fog=0.45, samples=5)
    axis = np.array([[[drum_x - 2.2, 0.0, drum_z], [drum_x + 2.2, 0.0, drum_z]]])
    dots.segs(axis, cam, C.mix(C.INK, C.TEXT_DIM, 0.45), alpha=0.45, fog=0.3, samples=5)
    for n, age, at in pre.plucks(t):
        tooth = n % len(pre.teeth)
        flash = math.exp(-age / 0.18) if age >= 0 else 0.0
        x0, y0, x1, y1 = pre.teeth[tooth]
        base = C.mix(C.INK, C.mix(gold, C.GOLD_HI, 0.35), 0.45)
        dots.line2d(x0, y0, x1, y1, base)
        if flash > 0.02:
            hot = C.mix(C.INK, C.mix(gold, C.WHITE, 0.60), min(1.0, flash + 0.25))
            dots.line2d(x0, y0, x1, y1, hot)
            dots.ring2d(x0, y0 - 2, 10.0 * flash + 2.0,
                        C.mix(C.INK, C.GOLD_HI, 0.8 * flash), n=18)
            if age >= 0:
                row = 6 + (n * 11) % 38
                yy = (row - 2) * 4 + 2
                sweep = min(1.0, age / 0.30)
                bright = math.exp(-age / 0.24)
                col = C.mix(C.INK, C.mix(C.CYAN_HI, C.WHITE, 0.65),
                            min(1.0, 0.30 + 0.70 * bright))
                dots.poly2d([(0, yy), (sweep * 400.0, yy)], col, samples=2)
                dots.poly2d([(0, yy + 2), (sweep * 400.0, yy + 2)],
                            C.scale(col, 0.45), samples=2)
    dots.commit()
    for n, age, at in pre.plucks(t):
        if 0.0 <= age < 0.8:
            k = 1.0 - age / 0.8
            gx = 148 + (n * 13) % 44
            gy = 22 - int(age * 22)
            c.put(gy, gx, "\u266a", C.mix(C.INK, C.GOLD_HI, 0.8 * k))


def _shot_drum(scene, pre, c, ctx) -> None:
    t = ctx.t
    pu = ctx.audio.pulse(t, 0.12)
    e = ctx.audio.energy(t)
    M.bg_gradient(c, C.mix(C.INK, C.BROWN_DIM, 0.42), C.INK)
    _radial(c, 31.0, 66.0, 44.0, C.mix(C.INK, C.GOLD_DEEP, 0.85), 0.62)
    spin = -1.2 - (t - T_DRUM) * 1.35
    cam = M.Camera(y=0.42, z=0.0, pitch=0.10, fov=1.05 + 0.03 * pu)
    _drum_frame(scene, pre, c, t, spin=spin, cam=cam, drum_z=3.5)
    mb = scene.script.v2.camera.title.music_box
    c.text(3, 3, mb[:30], C.mix(C.INK, C.GOLD_HI, 0.45 + 0.25 * pu), None, bold=True)
    c.text(3, c.w - 20, "CH0/CH1", C.mix(C.INK, TEXT_DIM, 0.5), None)
    c.hline(4, 3, 60, C.mix(C.INK, C.GOLD_DIM, 0.35), None, "-")
    M.grain(c, t, seed=3, count=60, color=C.GOLD_DIM, amount=0.05)
    M.vignette(c, 0.50)


def _shot_drum_reprise(scene, pre, c, ctx) -> None:
    t = ctx.t
    pu = ctx.audio.pulse(t, 0.12)
    M.bg_gradient(c, C.mix(C.INK, C.BROWN_DIM, 0.30), C.INK)
    _radial(c, 29.0, 100.0, 52.0, C.mix(C.INK, C.GOLD_DEEP, 0.75), 0.52)
    spin = -6.5 - (t - T_TULILA) * 2.4
    stop = M.smooth01(119.30, 120.10, t)
    spin *= (1.0 - 0.85 * stop)
    cam = M.Camera(y=0.30, z=0.0, pitch=0.06, fov=1.22 + 0.05 * pu)
    _drum_frame(scene, pre, c, t, spin=spin, cam=cam, drum_x=0.0, drum_z=3.6)
    # the last scan line stays and becomes the horizon of the cloud shot
    last = 119.98
    if t >= last:
        k = M.seg(t, last, T_CLOUD)
        yy = (30 - 2) * 4 + 2
        dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
        dots.poly2d([(0, yy), (400, yy)],
                    C.mix(C.INK, C.mix(C.CYAN_HI, C.WHITE, 0.55), 0.35 + 0.55 * k))
        dots.commit()
    c.text(3, 3, scene.script.camera.music_box[:30],
           C.mix(C.INK, C.GOLD_HI, 0.40 + 0.2 * pu), None, bold=True)
    M.vignette(c, 0.52)


# ==========================================================================
# II.2b  115.140-117.860  bone x-ray vs silicon lattice
# ==========================================================================
def _shot_bone(scene, pre, c, ctx) -> None:
    t = ctx.t
    q = M.seg(t, T_BONE, T_TULILA)
    pu = ctx.audio.pulse(t, 0.12)
    bn = scene.script.v2.bones
    M.bg_gradient(c, C.INK, C.mix(C.INK, C.RED_DEEP, 0.20))
    _radial(c, 26.0, 50.0, 40.0, C.mix(C.INK, C.RED_DEEP, 0.85), 0.45)
    _radial(c, 26.0, 150.0, 38.0, C.mix(C.INK, C.CYAN_DEEP, 0.85), 0.40)
    frac = t >= 117.32
    if pre.bone is not None:
        dim = 1.02 - 0.52 * M.smooth01(117.32, 117.9, t) * 0.0
        c.sprite(9, 2, pre.bone, fg_mul=dim, tint=C.AMBER_HI, tint_amt=0.08)
    # growing crack
    if t > 115.5:
        n = int(len(pre.crack) * M.smooth01(115.55, 117.30, t))
        if n >= 2:
            dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
            hot = M.smooth01(116.9, 117.32, t)
            dots.poly2d(pre.crack[:n],
                        C.mix(C.RED_HI, C.WHITE, 0.25 + 0.65 * hot), samples=4)
            if frac:
                age = t - 117.32
                k = math.exp(-age / 0.30)
                for j in range(6):
                    rng = random.Random(617 + j)
                    sx = 92.0 + rng.uniform(-30, 30)
                    sy = 130.0 + rng.uniform(-20, 20)
                    dots.line2d(sx, sy, sx + rng.uniform(-20, 20),
                                sy - rng.uniform(10, 40) * (0.4 + 0.6 * k),
                                C.mix(C.WHITE, C.AMBER_HI, 0.5))
            dots.commit()
    # silicon lattice (cold, steady)
    dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    lc = C.mix(C.mix(C.CYAN_HI, WHITE, 0.30), C.WHITE, 0.15)
    dots.segs2d(pre.lattice, lc, alpha=1.0, samples=2)
    # rack light columns
    for k in range(3):
        xx = 236 + k * 62
        dots.line2d(xx, 18, xx, 174, C.mix(C.INK, C.CYAN_DIM, 0.30 + 0.22 * pu))
    dots.commit()
    # centre rule + labels
    c.vline(100, 6, 50, C.mix(C.INK, C.CYAN_DIM, 0.22), None, "|")
    c.text(3, 6, bn.left_hdr[:44], C.mix(C.INK, C.AMBER_HI, 0.55), None, bold=True)
    s = bn.right_hdr[:40]
    c.text(3, c.w - len(s) - 6, s, C.mix(C.INK, C.CYAN_HI, 0.55), None, bold=True)
    if t > 116.2:
        k = M.smooth01(116.2, 117.0, t)
        m = bn.left_metrics[0]
        c.text(44, 6, m[:40], C.mix(C.INK, C.AMBER_HI, 0.55 * k), None)
        m2 = bn.right_metrics[0]
        c.text(44, c.w - len(m2) - 6, m2[:40], C.mix(C.INK, C.CYAN_HI, 0.55 * k), None)
    if t > 117.42:
        prog = M.seg(t, 117.42, 118.6)
        txt = M.split_flap(M.spread_text(bn.verdict, 1), prog, seed=130)
        c.text_center(47, txt, C.mix(C.INK, C.GOLD_HI, 0.35 + 0.55 * prog), None,
                      bold=prog > 0.8)
    if frac:
        M.punctuate(c, t - 117.32, flash=0.30, chroma=0.50, glitch=0.16,
                    shake=3.0, decay=0.16,
                    flash_color=C.mix(C.WHITE, C.RED_HI, 0.35))
    M.grain(c, t, seed=5, count=55, color=C.AMBER_HI, amount=0.05)
    M.vignette(c, 0.32)


# ==========================================================================
# II.4  120.290-123.180  memory motes -> glass cloud reliquary
# ==========================================================================
def _shot_cloud(scene, pre, c, ctx) -> None:
    t = ctx.t
    q = M.seg(t, T_CLOUD, T_END)
    pu = ctx.audio.pulse(t, 0.14)
    e = ctx.audio.energy(t)
    M.bg_gradient(c, C.mix(C.INK, C.PURPLE_DEEP, 0.62), C.INK)
    # horizon line carried over from the music box
    horizon = 30
    dots = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    if t < T_CLOUD + 0.8:
        k = 1.0 - M.seg(t, T_CLOUD, T_CLOUD + 0.8)
        yy = (horizon - 2) * 4 + 2
        dots.poly2d([(0, yy), (400, yy)],
                    C.mix(C.INK, C.mix(C.CYAN_HI, C.WHITE, 0.5), 0.4 * k))
    # ---- glass cloud reliquary (high, rotating, 3D braille) -----------
    cam = M.Camera(y=2.0, z=0.0, fov=1.12 + 0.03 * pu)
    cloud_c = np.array([0.1, 4.25, 4.6])
    rot = (t - T_CLOUD) * 0.55
    inner = M.orbit(pre.cloud_sphere * 1.02, yaw=rot, pitch=0.25 * math.sin(rot * 0.7),
                    center=(0, 0, 0)) + cloud_c
    dots.segs(inner, cam, C.mix(CYAN_HI, WHITE, 0.55), alpha=1.0, fog=0.65, samples=7)
    for segs, spin, phase in pre.cloud_rings:
        rr = M.orbit(segs.reshape(-1, 3) * 0.76, yaw=spin * math.cos(t * 0.3 + phase),
                     pitch=spin * 0.5, roll=rot * (1.0 + phase)) + cloud_c
        dots.segs(rr.reshape(-1, 2, 3), cam,
                  C.mix(CYAN_HI, WHITE, 0.60), alpha=1.0, fog=0.60, samples=6)
    # warm core
    pxs, pys, pzs = M.project(np.array([cloud_c]), cam, dots.pw, dots.ph)
    ccx, ccy = float(pxs[0]), float(pys[0])
    for ring_r, kk in ((5.0, 1.0), (9.0, 0.7), (14.0, 0.42)):
        dots.ring2d(ccx, ccy, ring_r + 2.0 * pu, C.mix(C.INK, C.GOLD_HI, kk), n=30)
    dots.commit()
    # ---- Dahlia's silhouette (bottom centre) --------------------------
    if pre.dahlia is not None:
        sx = (c.w - pre.dahlia.w) // 2
        _radial(c, 38.0, 100.0, 32.0, C.mix(C.INK, C.TERRA_DEEP, 0.9), 0.60)
        c.sprite(25, sx, pre.dahlia, alpha=0.97, tint=C.INK, tint_amt=0.80)
        # rim light on the hair silhouette
        for k in range(3):
            c.put(25 + k, sx + 2 + k, "/", C.mix(C.INK, C.TERRA_HI, 0.30 + 0.2 * pu))
    # ---- reverse rain of memory motes ---------------------------------
    motes = _Dots(c, C.CONTENT_Y0, 0, C.CONTENT_H, C.W)
    nb = int(t * 60)
    for i, (sx, sy, ex, ey, phase, speed, wob, size) in enumerate(pre.motes):
        ph = ((t - T_CLOUD) * speed / 2.6 + phase) % 1.0
        y = sy + (ey - sy) * (ph ** 0.62)
        x = sx + (ex - sx) * (ph ** 1.4) * 0.75
        x += math.sin(ph * 7.0 + phase * 11.0) * wob * (1.0 - ph) * 3.0
        x += (200.0 - x) * M.smooth01(0.55, 1.0, ph) * 0.60
        bright = math.sin(math.pi * min(1.0, ph * 1.08)) ** 0.7
        if ph < 0.06:
            bright *= ph / 0.06
        col = C.mix(C.INK, C.mix(TERRA_PALE, WHITE, 0.25 + 0.5 * M.hash01(i, 3)),
                    min(1.0, bright * (0.80 + 0.55 * pu)))
        dots2 = motes
        xi = int(round(x)); yi = int(round(y))
        if 0 <= xi < 400 and 0 <= yi < 204:
            dots2.buf[yi, xi] = int(col)
            if yi + 3 < 204:
                dots2.buf[yi + 3, xi] = int(C.scale(col, 0.42))
            if bright > 0.55 and size > 1:
                if yi + 6 < 204:
                    dots2.buf[yi + 6, xi] = int(C.scale(col, 0.22))
                if 0 <= xi + 1 < 400:
                    dots2.buf[yi, xi + 1] = int(C.scale(col, 0.7))
    # audio breath pulses: extra rising motes on strong pulses
    if pu > 0.45:
        rng = random.Random(int(t * 30) ^ 617)
        for k in range(10):
            xx = rng.uniform(150.0, 250.0)
            yy = rng.uniform(140.0, 200.0) - pu * 20.0
            col = C.mix(C.INK, C.mix(TERRA_PALE, WHITE, 0.4), 0.85 * pu)
            xi = int(xx); yi = int(yy)
            if 0 <= xi < 400 and 0 <= yi < 204:
                motes.buf[yi, xi] = int(col)
    motes.commit()
    # ---- inscription ---------------------------------------------------
    title = scene.script.v2.distill.title
    if t > 121.35:
        prog = M.seg(t, 121.35, 122.55)
        txt = M.split_flap(M.spread_text(title.footer, 1), prog, seed=617)
        c.text_center(48, txt, C.mix(C.INK, C.mix(C.PURPLE_HI, C.GOLD_HI, 0.4),
                                    0.30 + 0.45 * prog), None, bold=prog > 0.85)
    # final convergence glow
    if t > 122.6:
        k = M.seg(t, 122.6, T_END)
        M.punctuate(c, t - 122.6, flash=0.10 * k, shake=0.8 * k, decay=0.55,
                    flash_color=C.mix(C.GOLD_HI, WHITE, 0.5))
    M.grain(c, t, seed=23, count=45, color=C.PURPLE_HI, amount=0.04)
    M.vignette(c, 0.34)

