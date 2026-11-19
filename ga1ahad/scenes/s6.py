"""Scene 6 / finale -- 03:26.850 - 03:39.150 (12.30 s, 2 VTT cues).

There's no restart but only proceed: a 200 column frame torn in half -- on the
left a cold, dark-red pacification archive (surveillance plate, drone reticles,
slow radar sweep, append-only casualty ledger), on the right a gilded domestic
broadcast (amber revelry over the crowd keyframe, a faint rising star/stripe
motif, a waterfall of headlines).  A living fissure of dark red and
molten-gold electric arcs breathes between the two worlds.

At the second cue a column of holy light splits the fissure and the two worlds
fold outward like heavy bronze altar doors -- one becomes a scorched-iron wing,
the other a golden wing.  The painted icon rises solemnly out of the light
inside multi-layer counter-rotating Braille armillary rings, a sunflower ray
burst and slowly rising gold embers; the base inscriptions light up like
gold-leaf etching.

Then the whole golden temple dissolves to velvet black, leaving one cold
terminal prompt and a slowly blinking cursor to sit with the last note.

The scene is a pure function of time; every string comes from the content
layer and the two VTT cues are read through the scene helpers.
"""

from __future__ import annotations

import math
import random

import numpy as np

from .. import config as C
from .. import motion as M
from ..assets import camera_sprite, keyframe, recolor_sprite
from ..canvas import Sprite
from .base import Scene

# ---------------------------------------------------------------------------
# Timeline (absolute seconds; the VTT cue starts are the single source truth)
# ---------------------------------------------------------------------------
T_A = 206.850              # cue 1: There's no restart but only proceed
T_B = 211.040              # cue 2: Take up from where we've left off and see
T_END = 219.150

# content band
Y0 = C.CONTENT_Y0          # 2
Y1 = C.CONTENT_Y1          # 53 (exclusive)
ROWS = Y1 - Y0             # 51
W = C.W                    # 200
SEAM = 100.0               # the tear / axis of the altar

# torn-world layout
HL = 98                    # left theatre plate width
CROWD_Y = Y0 + 32          # crowd keyframe top row (row 34)

# altar layout
ICON_Y = 3                 # final top row of the painted icon
ICON_ROWS = 42             # final sprite rows


def _smooth(a: float, b: float, x: float) -> float:
    return M.smooth01(a, b, x)


class Scene6(Scene):
    NAME = "s6"

    # ------------------------------------------------------------------
    # construction -- every static table / sprite is built once here
    # ------------------------------------------------------------------
    def __init__(self, assets, audio, timeline, content) -> None:
        super().__init__(assets, audio, timeline, content)
        S = self.script
        one = S.s6_1
        left = one.left
        right = one.right
        altar = S.s6_2

        # --- left theatre: the pacification archive ---------------------
        self._tag = left.left_tag
        self._title = left.left_title.upper()
        self._live = left.left_live
        self._signal = left.left_signal
        self._zone = left.left_zone.upper()
        self._engine = left.left_engine
        self._casualty = left.left_casualty
        self._appending = left.left_appending
        self._archive = left.left_archive
        self._counters = tuple(left.casualty_counters)
        self._orders = left.orders_banner
        self._rollback_cmd = left.rollback_cmd
        self._rollback_denied = left.rollback_denied
        self._proceed_cmd = left.proceed_cmd
        self._proceed_ok = left.proceed_ok
        self._reticles = [(r.name, r.lock, r.target) for r in left.reticles]

        # --- right theatre: the gilded broadcast ------------------------
        self._badge = right.badge
        self._bow = right.bow
        self._head_a = right.headline_a.upper()
        self._head_b = right.headline_b.upper()
        self._approval_lbl = right.approval_label
        self._approval_val = right.approval_value
        self._dissent = right.dissent
        self._suppressed = right.suppressed
        self._hashtag = right.hashtag
        self._marquee = right.marquee
        self._feed = [str(x) for x in right.feed]

        # --- altar ------------------------------------------------------
        self._wing_texts = ((altar.wing_left_1, altar.wing_right_1),
                            (altar.wing_left_2, altar.wing_right_2),
                            (altar.wing_left_3, altar.wing_right_3))
        self._insc_nation = altar.inscription_nation.upper()
        self._insc_deity = altar.inscription_deity
        self._prompt = altar.prompt
        # colour segments of the prompt follow the glossary handles
        T = self.T
        u = len(T.claude_handle)
        h = len(T.usa_host)
        self._prompt_segs = ((self._prompt[:u], C.CYAN_DIM),
                             (self._prompt[u:u + 1], C.TEXT_FAINT),
                             (self._prompt[u + 1:u + 1 + h], C.TEXT_DIM),
                             (self._prompt[u + 1 + h:], C.CYAN))

        # --- cue lock: shot timings derive from the two VTT cues ---------
        ly_a = self.cues[0]
        ly_b = self.cues[1]
        self.t_a = ly_a.start                     # 206.850
        self.t_b = ly_b.start                     # 211.040
        b = self.t_b
        self.t_fold0 = b + 0.55                   # bronze doors start to swing
        self.t_fold1 = b + 2.05
        self.t_fig0 = b + 0.68                    # the icon starts to rise
        self.t_fig1 = b + 3.30
        self.t_halo0 = b + 2.35                   # armillary rings unfold
        self.t_halo1 = b + 4.65
        self.t_glory0 = b + 4.05                  # the ray burst blooms
        self.t_glory1 = b + 4.75
        self.t_ins0 = b + 3.55                    # gold-leaf etching
        self.t_ins1 = b + 4.95
        self.t_dim0 = b + 5.25                    # the temple starts to die
        self.t_fade0 = b + 6.40                   # 217.440 -> velvet black
        self.t_fade1 = b + 7.30                   # 218.340
        self.t_prompt = b + 6.75                  # 217.790

        self._build_plates()
        self._build_doors()
        self._build_backgrounds()
        self._build_particles()
        self._build_icon()
        self._warm_glyphs()

    # -- keyframe plates -------------------------------------------------
    def _build_plates(self) -> None:
        # left: a vertical surveillance crop, graded to a dark blood monochrome
        raw_l = camera_sprite(keyframe("civilians"), ROWS, HL,
                              zoom=1.06, center=(0.42, 0.60), bright=1.0)
        self._plate_l = recolor_sprite(
            raw_l, lambda col: C.scale(C.mix(col, C.BLOOD, 0.46), 0.90))
        # the same world after the fold: scorched iron, embers in the grain
        self._wing_l = recolor_sprite(
            raw_l, lambda col: C.scale(
                C.mix(col, C.mix(C.INK, C.RED_DEEP, 0.55), 0.62), 0.80))
        # right: the golden crowd, tall crop -- later the golden wing
        raw_r = camera_sprite(keyframe("crowd"), ROWS, HL,
                              zoom=1.05, center=(0.58, 0.58), bright=1.0)
        self._plate_r = recolor_sprite(
            raw_r, lambda col: C.scale(C.mix(col, C.GOLD, 0.14), 0.99))
        self._wing_r = recolor_sprite(
            raw_r, lambda col: C.scale(
                C.mix(col, C.mix(C.GOLD_DEEP, C.AMBER_DIM, 0.55), 0.58), 0.86))
        # right: wide crowd band at the foot of the broadcast half
        crowd = camera_sprite(keyframe("crowd"), Y1 - CROWD_Y, 100,
                              zoom=1.02, center=(0.56, 0.66), bright=1.0)
        self._crowd = recolor_sprite(
            crowd, lambda col: C.scale(C.mix(col, C.GOLD, 0.10), 0.94))

    # -- the two worlds fold into altar wings ----------------------------
    def _build_doors(self) -> None:
        n = 20
        frames = []
        for k in range(n):
            q = k / (n - 1)
            wv = int(round(M.lerp(HL, 27.0, q)))
            morph = _smooth(0.42, 1.0, q)
            spl, el = self._wing_frame(self._wing_l, wv, morph, False)
            spr, er = self._wing_frame(self._wing_r, wv, morph, True)
            frames.append((wv, spl, spr, el, er))
        self._door_frames = frames

    @staticmethod
    def _wing_frame(src, width: int, morph: float, mirror: bool):
        """Resample a plate into a tall door that slowly becomes a wing."""
        sp = Sprite(ROWS, width)
        edges = [width] * ROWS
        fade = _smooth(0.30, 0.92, morph)
        for i in range(ROWS):
            u = i / (ROWS - 1)
            leaf = 0.34 + 0.66 * (math.sin(math.pi * (0.12 + 0.76 * u)) ** 0.55)
            leaf *= 1.0 - 0.07 * (0.5 + 0.5 * math.sin(u * math.pi * 9.0))
            shape = 1.0 + (leaf - 1.0) * morph
            wr = max(3, min(width, int(round(width * shape))))
            edges[i] = wr
            lo = 0 if not mirror else width - wr
            for j in range(wr):
                dstj = j if not mirror else lo + j
                t = j / max(1, wr - 1)
                sx = int(round(t * (src.w - 1)))
                d = (wr - 1 - j) if not mirror else j
                a = 1.0
                if d < 4:
                    a = 1.0 - fade * (0.62 * (1.0 - (d + 1) / 5.0))
                sp.ch[i][dstj] = src.ch[i][sx]
                sp.fg[i][dstj] = C.mix(C.INK, src.fg[i][sx], a)
                sp.bg[i][dstj] = C.mix(C.INK, src.bg[i][sx], a)
        return sp, edges

    # -- precomputed backgrounds ----------------------------------------
    def _build_backgrounds(self) -> None:
        ink = np.array([5, 7, 10], dtype=np.float64)
        red_deep = np.array([58, 10, 14], dtype=np.float64)
        blood = np.array([122, 12, 18], dtype=np.float64)
        terra_deep = np.array([58, 26, 18], dtype=np.float64)
        gold_deep = np.array([58, 42, 8], dtype=np.float64)
        amber_dim = np.array([110, 58, 30], dtype=np.float64)
        gold = np.array([245, 185, 66], dtype=np.float64)
        gold_hi = np.array([255, 217, 122], dtype=np.float64)
        terra = np.array([217, 119, 87], dtype=np.float64)

        def smooth_vec(a, b, x):
            t = np.clip((x - a) / (b - a), 0.0, 1.0)
            return t * t * (3.0 - 2.0 * t)

        def mixr(base, other, w):
            return base * (1.0 - w[:, None]) + other * w[:, None]

        def mixg(base, other, w):
            return base * (1.0 - w[..., None]) + other * w[..., None]

        def pack_row(rgb):
            r = max(0, min(255, int(rgb[0])))
            g = max(0, min(255, int(rgb[1])))
            b = max(0, min(255, int(rgb[2])))
            return (r << 16) | (g << 8) | b

        ur = np.arange(ROWS, dtype=np.float64) / (ROWS - 1)
        u = ur[:, None]
        ycell = np.arange(ROWS, dtype=np.float64)[:, None] + Y0
        xcell = np.arange(W, dtype=np.float64)[None, :]

        # left half: cold charred red sky
        wl = np.clip(0.50 + 0.40 * np.sin(np.pi * ur), 0.0, 1.0)
        rowl = mixr(ink, red_deep, wl)
        rowl = mixr(rowl, blood, 0.42 * np.exp(-(((ur - 0.62) / 0.24) ** 2)))
        self._base_l = [pack_row(rowl[i]) for i in range(ROWS)]

        # right half: hot amber sky
        wr = np.clip(0.20 + 0.62 * ur, 0.0, 1.0)
        rowr = mixr(ink, (terra_deep + gold_deep) * 0.5, wr)
        rowr = mixr(rowr, amber_dim,
                    0.34 * np.exp(-(((ur - 0.58) / 0.30) ** 2)))
        rowr = mixr(rowr, gold, 0.10 * np.exp(-(((ur - 0.72) / 0.18) ** 2)))
        self._base_r = [pack_row(rowr[i]) for i in range(ROWS)]

        # --- temple: radial sacred glow, six intensity levels -----------
        dy = (ycell - 23.0) / 25.0
        dx = (xcell - SEAM) / 100.0
        d = np.sqrt((dx * 0.92) ** 2 + (dy * 0.86) ** 2)
        warm = np.clip(1.0 - d * 1.05, 0.0, 1.0) ** 1.30
        base = mixg(ink, mixg(terra_deep, gold_deep, np.full(d.shape, 0.45)),
                    np.clip(0.22 + 0.70 * warm, 0.0, 1.0))
        base = mixg(base, mixg(amber_dim, gold, np.full(d.shape, 0.40)),
                    0.52 * warm ** 1.2)
        ratio = (ycell - Y0) / (ROWS - 1)
        floor = np.broadcast_to(smooth_vec(0.66, 1.0, ratio), d.shape)
        base = mixg(base, ink, 0.70 * floor)
        ceil = np.broadcast_to(smooth_vec(0.14, 0.0, ratio), d.shape)
        base = mixg(base, ink, 0.40 * ceil)
        self._temple_lut = []
        for lv in range(6):
            q = lv / 5.0
            col = base * (0.30 + 0.92 * q)
            col = col + gold_hi * ((warm * 0.52 * q)[..., None])
            accent = mixg(terra, gold_hi, np.full(d.shape, 0.40 + 0.60 * q))
            col = mixg(col, accent, warm ** 1.6 * 0.30 * q)
            a = np.clip(col, 0, 255).astype(np.int32)
            packed = (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]
            self._temple_lut.append(packed.tolist())

    # -- seeded particles / geometry -------------------------------------
    def _build_particles(self) -> None:
        rng = random.Random(0x5EED06)
        # gold embers drifting up through the altar
        self._ember_data = [(rng.uniform(2.0, W - 2.0), rng.random(),
                         rng.uniform(0.014, 0.040), rng.randint(0, 2),
                         rng.uniform(0.0, math.tau)) for _ in range(74)]
        # faint stars in the gilded sky
        self._stars = [(rng.uniform(106.0, 198.0), rng.uniform(2.0, 29.0),
                        rng.uniform(0.0, math.tau), rng.random()) for _ in range(46)]
        # radar blips (angle, radius in braille dots)
        self._blips = [(rng.uniform(0.0, math.tau), rng.uniform(9.0, 24.0))
                       for _ in range(3)]
        # armillary rings: (radius dots, tilt, spin, centre y dots, colour, n)
        # odd tuples are drawn in front of the icon, the rest frame it from behind
        self._rings_behind = (
            (96.0, 0.55, -0.30, (25 - Y0) * 4 + 2, C.GOLD, 128),
            (108.0, -0.40, 0.20, (25 - Y0) * 4 + 2, C.GOLD_DIM, 136),
            (120.0, 1.02, -0.14, (25 - Y0) * 4 + 2, C.TERRA, 144),
        )
        self._rings_front = (
            (62.0, 0.58, 0.58, (25 - Y0) * 4 + 2, C.GOLD_HI, 104, 0.42),
            (80.0, -0.78, -0.34, (25 - Y0) * 4 + 2, C.TERRA_HI, 120, 0.30),
        )
        # broadcast waterfall columns: (x, width, speed, seed)
        self._streams = ((106, 22, 15.0, 0), (130, 21, 21.0, 7),
                         (154, 21, 17.0, 13), (177, 20, 24.0, 19))
        self._wf_y0 = Y0 + 3
        self._wf_h = 26

    def _build_icon(self) -> None:
        self._icon_sprite = camera_sprite(keyframe("pantocrator"), ICON_ROWS,
                                   ICON_ROWS * 3, zoom=1.02,
                                   center=(0.5, 0.5), bright=1.0)

    def _warm_glyphs(self) -> None:
        gt = self.assets.glyphs
        for ch in ("\u25cf\u25b2\u25b8\u2747\u2605\u2726\u2727\u2022"
                   "\u00b7\u25c9\u2590\u258c\u2588\u2593\u2592\u2591"
                   "\u2500\u2502\u2571\u2572\u25a0\u25c6\u25c7\u274e"
                   "\u273f\u2014\u2551\u256b\u25ae"):
            gt.char_id(ch)

    # ==================================================================
    # dispatch
    # ==================================================================
    def draw(self, c, ctx) -> None:
        if ctx.t < self.t_b:
            self._draw_split(c, ctx)
        else:
            self._draw_temple(c, ctx)

    # ==================================================================
    # SHOT 1 -- the torn two-face world  (206.850 - 211.040)
    # ==================================================================
    def _seam_edges(self, t: float):
        xl: list = []
        xr: list = []
        for i in range(ROWS):
            y = Y0 + i
            u = i / (ROWS - 1)
            env = math.sin(math.pi * min(1.0, u * 1.04)) ** 0.62
            wob = (1.9 * math.sin(y * 0.41 + t * 3.4)
                   + 1.2 * math.sin(y * 0.17 - t * 2.1)
                   + 0.8 * math.sin(y * 0.83 + t * 6.7)) * env
            half = 4.0 + 5.6 * env
            xl.append(max(82, min(96, int(round(SEAM - half + wob * 0.85)))))
            xr.append(max(104, min(118, int(round(SEAM + half + wob * 0.62)))))
        return xl, xr

    def _paint_split_bg(self, c, edges, bl: float, br: float,
                        hot: float) -> None:
        base_l, base_r = self._base_l, self._base_r
        ink = C.INK
        red_hi, gold_hi = C.RED_HI, C.GOLD_HI
        xl, xr = edges
        for i in range(ROWS):
            y = Y0 + i
            x0 = xl[i]
            x1 = xr[i]
            fa = 0.38 + 0.62 * bl
            c.bg[y][0:x0] = [C.mix(ink, base_l[i], fa)] * x0
            fa2 = 0.40 + 0.60 * br
            c.bg[y][x1:W] = [C.mix(ink, base_r[i], fa2)] * (W - x1)
            # the canyon itself: near-black with a coloured charge on each lip
            span = max(1, x1 - x0 - 1)
            for x in range(x0, x1):
                u = (x - x0) / span
                if u < 0.5:
                    col = C.mix(ink, C.BLOOD, 0.10 + 0.30 * (0.5 - u) * 2.0)
                    col = C.mix(col, red_hi, max(0.0, 0.42 - u) * hot * 1.3)
                else:
                    col = C.mix(ink, C.GOLD_DEEP, 0.10 + 0.30 * (u - 0.5) * 2.0)
                    col = C.mix(col, gold_hi, max(0.0, u - 0.58) * hot * 1.3)
                c.bg[y][x] = col
            # lip spill into both worlds
            for k in range(1, 10):
                a = (1.0 - k / 10.0) ** 1.5
                xx = x0 - k
                if xx >= 0:
                    c.bg[y][xx] = C.mix(c.bg[y][xx], C.BLOOD_HI, 0.62 * a * hot)
                xx = x1 + k
                if xx < W:
                    c.bg[y][xx] = C.mix(c.bg[y][xx], C.GOLD_HI, 0.62 * a * hot)

    def _draw_split(self, c, ctx) -> None:
        t = ctx.t
        lt = t - self.t_a
        appear = _smooth(self.t_a, self.t_a + 0.55, t)
        energy = ctx.audio.energy(t)
        pulse = ctx.audio.pulse(t, 0.13)
        breath = 0.5 + 0.5 * math.sin(lt * 1.55 - 0.9)
        bl = (0.74 + 0.26 * breath) * (0.55 + 0.45 * appear)
        br = (1.04 - 0.26 * breath) * (0.55 + 0.45 * appear)
        hot = min(1.0, 0.22 + 0.95 * pulse + 0.22 * energy)

        edges = self._seam_edges(t)
        self._paint_split_bg(c, edges, bl, br, hot)

        # the two world plates (dark red surveillance / golden crowd)
        slide = int(round(10.0 * (1.0 - appear)))
        M.feather_sprite(c, Y0, -slide, self._plate_l, feather=9, bg=C.INK,
                         alpha=appear, tint=C.INK,
                         tint_amt=max(0.0, 0.05 + 0.24 * (1.0 - bl)))
        M.feather_sprite(c, CROWD_Y, 99 + slide, self._crowd, feather=10,
                         bg=C.INK, alpha=appear, tint=C.INK,
                         tint_amt=max(0.0, 0.04 + 0.18 * (1.0 - br)))

        # gilded sky: faint rising stripes + stars
        self._sky(c, t, br, pulse)

        # the waterfall of headlines, then the big monument cut-in over it
        appear_h = _smooth(208.22, 208.58, t) * (1.0 - _smooth(209.66, 209.96, t))
        self._waterfall(c, t, 1.0 - 0.80 * appear_h)
        head = self._headline(c, t, pulse, appear_h)
        self._right_hud(c, t, br)

        # left theatre HUD
        self._left_hud(c, ctx, lt, appear, pulse)

        # the living fissure
        self._fissure(c, ctx, edges, hot)

        # micro camera hit on the downbeats (restrained)
        c.fx.shake_x = 1.15 * pulse * math.sin(t * 91.0)
        c.fx.shake_y = 0.55 * pulse * math.cos(t * 73.0)
        if pulse > 0.94:
            c.fx.chroma = max(c.fx.chroma, 0.08 * pulse)

    # -- right sky motif -------------------------------------------------
    def _sky(self, c, t: float, br: float, pulse: float) -> None:
        brl = c.braille(Y0, 104, 28, 96)
        base = C.mix(C.INK, C.GOLD_DIM, 0.16 + 0.30 * br)
        for i in range(11):
            base_x = 5 + i * 17
            phase = 116.0 - ((t * 26.0 + i * 31.0) % 116.0)
            col = C.mix(C.INK, base, 0.55 + 0.25 * math.sin(t * 1.3 + i))
            for j in range(17):
                yy = int(phase) + j
                if yy < 0 or yy > 112:
                    continue
                xx = base_x + int(2.0 * math.sin(t * 0.8 + i * 0.7 + yy * 0.06))
                brl.plot(xx, yy, col)
        for (sx, sy, ph, mag) in self._stars:
            tw = 0.5 + 0.5 * math.sin(t * (1.6 + mag) + ph)
            if tw < 0.35:
                continue
            x = int((sx - 104) * 2)
            y = int((sy - Y0) * 4)
            col = C.mix(C.INK, C.GOLD_HI, (0.22 + 0.55 * tw) * br)
            brl.plot(x, y, col)
            if mag > 0.82:
                brl.plot(x + 1, y, C.mix(C.INK, col, 0.6))
        brl.commit()

    # -- broadcast waterfall --------------------------------------------
    def _waterfall(self, c, t: float, dim: float) -> None:
        feed = self._feed
        n = len(feed)
        y0 = self._wf_y0
        h = self._wf_h
        for (x, wdt, speed, seed) in self._streams:
            off = int(t * speed + seed)
            for r in range(h):
                idx = (off + r) % n
                pre = "\u25b8 " if idx % 2 else "# "
                s = (pre + feed[idx])[:wdt]
                fade = min(1.0, r / 3.0, (h - 1 - r) / 4.0)
                if idx % 3 == 0:
                    base = C.GOLD_HI
                elif idx % 3 == 1:
                    base = C.TERRA_HI
                else:
                    base = C.GOLD
                a = (0.30 + 0.58 * fade) * dim
                c.text(y0 + r, x, s, C.mix(C.INK2, base, a))

    # -- the imperial headline cut-in ------------------------------------
    def _headline(self, c, t: float, pulse: float, h: float) -> float:
        if h <= 0.012:
            return 0.0
        appear = _smooth(208.22, 208.58, t)
        # a dark veil drops so the gold monument reads against the broadcast
        veil = min(0.88, 0.82 * h)
        y0v, y1v = Y0 + 2, Y0 + 30
        for y in range(y0v, y1v):
            row = c.bg[y]
            fy = min(1.0, (y - y0v + 1) / 3.0, (y1v - y) / 6.5)
            for x in range(104, 200):
                fx = min(1.0, (x - 104) / 16.0)
                a = veil * fy * fx
                if a > 0.01:
                    row[x] = C.mix(row[x], C.INK, a)
        dy = int(round((1.0 - appear) * 9.0))
        top = C.mix(C.INK, C.GOLD_HI, 0.58 + 0.42 * h)
        bot = C.mix(C.INK, C.TERRA, 0.52 + 0.48 * h)
        settle_a = M.clamp01(appear * 1.25 - 0.10)
        settle_b = M.clamp01(appear * 1.25 - 0.22)
        txt_a = self._head_a if settle_a >= 0.999 else \
            M.split_flap(self._head_a, settle_a, seed=5.0)
        txt_b = self._head_b if settle_b >= 0.999 else \
            M.split_flap(self._head_b, settle_b, seed=6.0)
        ya = Y0 + 6 + dy
        yb = ya + 9
        M.big_text(c, ya, 108, txt_a, top, x1=198, align="center",
                   top=top, bottom=bot)
        M.big_text(c, yb, 108, txt_b, top, x1=198, align="center",
                   top=bot, bottom=C.mix(C.INK, C.GOLD, 0.5 + 0.5 * h))
        ry = yb + 8
        if ry <= Y1 - 1:
            c.hline(ry, 114, 192, C.mix(C.INK, C.GOLD_DIM, 0.65))
            tag = M.spread_text(self._hashtag, 1)
            c.text(ry + 1, 198 - len(tag), tag[:92],
                   C.mix(C.INK, C.GOLD_HI, 0.40 + 0.50 * h))
        if 208.28 <= t <= 208.52:
            c.fx.flash = max(c.fx.flash, 0.06 * (1.0 - (t - 208.28) / 0.24))
            c.fx.flash_color = C.GOLD_HI
        return h

    # -- left theatre HUD -----------------------------------------------
    def _left_hud(self, c, ctx, lt: float, appear: float,
                  pulse: float) -> None:
        y = Y0
        tag = self._tag
        c.text(y, 3, tag, C.RED_HI, None, bold=True)
        c.text(y, 3 + len(tag) + 2, self._title, C.mix(C.INK, C.RED, 0.72))
        live = self._live
        c.text(y, 94 - len(live) - 2, live, C.RED_DIM)
        sig = self._signal
        c.text(y + 1, 3, sig, C.RED_DIM)
        c.hline(y + 1, 3 + len(sig) + 3, 94,
                C.mix(C.INK, C.RED_DEEP, 0.9))
        c.text(y + 2, 3, self._zone, C.mix(C.INK, C.RED, 0.72), bold=True)
        eng = self._engine
        c.text(y + 2, 94 - len(eng) - 2, eng, C.RED_DIM)
        lab = self._casualty
        c.text(y + 3, 3, lab, C.mix(C.INK, C.RED, 0.60), bold=True)
        if int(lt * 2.5) % 2 == 0 or pulse > 0.45:
            c.text(y + 3, 3 + len(lab) + 2, self._appending,
                   C.mix(C.RED, C.RED_HI, 0.55))
        arch = self._archive
        c.text(y + 3, 94 - len(arch) - 2, arch, C.RED_DIM)

        ci = int(lt / 1.55) % len(self._counters)
        num = self._counters[ci]
        if pulse > 0.86 and int(ctx.t * 9.0) % 3 == 0:
            num = M.split_flap(num, 0.5, seed=3.0)
        ctop = C.mix(C.INK, C.RED, 0.42)
        cbot = C.mix(C.RED, C.RED_HI, 0.30 + 0.55 * pulse)
        M.big_text(c, y + 4, 5, num, cbot, top=ctop, bottom=cbot,
                   banding=True)

        # drone reticles tracking through the archive plate
        hot = 0.30 + 0.55 * pulse
        phase = lt * 0.55
        if len(self._reticles) >= 1:
            nm, lk, tg = self._reticles[0]
            self._reticle(c, y + 13 + int(round(1.2 * math.sin(phase))),
                          66 + int(round(1.8 * math.sin(phase * 0.7))),
                          6, 11, nm, lk, tg, hot)
        if len(self._reticles) >= 2:
            nm, lk, tg = self._reticles[1]
            self._reticle(
                c, y + 27 + int(round(1.2 * math.sin(phase * 1.3 + 2))),
                63 + int(round(1.6 * math.sin(phase * 0.9 + 1))),
                5, 9, nm, lk, tg, hot * 0.85)

        self._radar(c, ctx.t, pulse)

        # standing orders / the rejected rollback at the foot of the plate
        by = Y1 - 3
        c.text(by, 4, self._orders, C.mix(C.INK, C.RED_DIM, 0.88))
        rc = self._rollback_cmd
        c.text(by + 1, 4, rc, C.RED_DIM)
        c.text(by + 1, 4 + len(rc) + 2, self._rollback_denied,
               C.mix(C.INK, C.RED, 0.82), bold=True)
        pc = self._proceed_cmd
        c.text(by + 2, 4, pc, C.mix(C.RED, C.RED_HI, 0.42), bold=True)
        c.text(by + 2, 4 + len(pc) + 2, self._proceed_ok,
               C.mix(C.RED_HI, C.WHITE, 0.15), bold=True)

    def _reticle(self, c, cy: int, cx: int, hh: int, hw: int,
                 name: str, lock: str, target: str, hot: float) -> None:
        col = C.mix(C.INK, C.RED_HI, 0.55 + 0.45 * hot)
        thin = C.mix(C.INK, C.RED, 0.55 + 0.35 * hot)
        for sy in (-1, 1):
            for sx in (-1, 1):
                y0 = cy + sy * hh
                x0 = cx + sx * hw
                y1 = cy + sy * (hh - 2)
                x1 = cx + sx * (hw - 4)
                c.hline(y0, min(x0, x1), max(x0, x1) + 1, col)
                c.vline(x0, min(y0, y1), max(y0, y1) + 1, col)
        c.hline(cy, cx - 3, cx + 4, thin)
        c.vline(cx, cy - 2, cy + 3, thin)
        c.put(cy, cx, "\u25c9", col)
        c.text(cy - hh - 1, max(0, cx - hw), (name + " " + lock)[:2 * hw], thin)
        c.text(cy + hh + 1, max(0, cx - hw), target[:2 * hw], thin)

    def _radar(self, c, t: float, pulse: float) -> None:
        brl = c.braille(Y0 + 30, 2, 18, 28)
        cx, cy = 28.0, 38.0
        base = C.mix(C.INK, C.RED, 0.52)
        bright = C.mix(C.RED_HI, C.WHITE, 0.25 + 0.35 * pulse)
        for rad in (9.0, 17.0, 25.0):
            n = int(2.0 * math.pi * rad / 1.5)
            for k in range(n):
                if rad > 14.0 and (k // 2) % 2:
                    continue
                a = 2.0 * math.pi * k / n
                brl.plot(int(cx + math.cos(a) * rad),
                         int(cy + math.sin(a) * rad * 0.94), base)
        sweep = (t * 1.12) % (2.0 * math.pi)
        for j in range(16):
            aa = sweep - j * 0.040
            col = C.mix(C.INK, bright, 1.0 - j / 16.0)
            for rr in range(5, 26, 2):
                brl.plot(int(cx + math.cos(aa) * rr),
                         int(cy + math.sin(aa) * rr * 0.94), col)
        for (ang, rad) in self._blips:
            da = abs((ang - sweep + math.pi) % (2.0 * math.pi) - math.pi)
            if da < 0.24:
                brl.plot(int(cx + math.cos(ang) * rad),
                         int(cy + math.sin(ang) * rad * 0.94),
                         C.mix(C.RED_HI, C.WHITE, 0.45))
        brl.commit()

    # -- right theatre HUD ----------------------------------------------
    def _right_hud(self, c, t: float, br: float) -> None:
        y = Y0
        c.text(y, 106, self._badge, C.mix(C.INK, C.GOLD_HI, 0.80), None,
               bold=True)
        bow = self._bow
        c.text(y, 197 - len(bow), bow, C.TERRA_HI)
        lab = self._approval_lbl
        c.text(y + 1, 106, lab, C.GOLD_DIM)
        c.text(y + 1, 106 + len(lab) + 1, self._approval_val, C.GOLD_HI,
               None, bold=True)
        c.text(y + 1, 150, self._dissent, C.TERRA_DIM)
        sup = self._suppressed
        c.text(y + 1, 197 - len(sup), sup, C.mix(C.INK, C.TERRA_DIM, 0.85))
        c.hline(y + 2, 106, 199, C.mix(C.INK, C.GOLD_DEEP, 0.9))
        # a slow marquee hugs the bottom edge
        mq = self._marquee
        off = int(t * 26.0) % max(1, len(mq))
        s = (mq + mq)[off:off + 92]
        c.text(Y1 - 2, 107, s, C.mix(C.INK, C.GOLD_DIM, 0.75))

    # -- the living fissure ---------------------------------------------
    def _fissure(self, c, ctx, edges, hot: float) -> None:
        t = ctx.t
        xl, xr = edges
        ink = C.INK
        rng = random.Random(int(t * 23.0) * 7919 + 13)
        brl = c.braille(Y0, 82, ROWS, 36)
        # electric arcs crackling across the canyon
        for arc in range(4):
            x = 36.0 + rng.uniform(-7.0, 7.0)
            pts = [(x, 1.0)]
            for k in range(1, 12):
                y = k * 204.0 / 11.0
                x += rng.uniform(-8.0, 8.0)
                x = min(70.0, max(2.0, x))
                pts.append((x, y))
            for k in range(len(pts) - 1):
                x0, y0 = pts[k]
                x1, y1 = pts[k + 1]
                u = 0.5 * (x0 + x1) / 72.0
                base = C.mix(C.RED_HI, C.GOLD_HI, u)
                col = C.mix(ink, base, 0.42 + 0.55 * hot)
                brl.line(x0, y0, x1, y1, col, 0.95, 1.0)
        # a white-hot spine right at the tear
        for k in range(0, 204, 4):
            xx = 36.0 + 1.3 * math.sin(k * 0.21 - t * 9.0)
            col = C.mix(C.mix(C.RED_HI, C.GOLD_HI, 0.5), C.WHITE,
                        0.25 + 0.45 * hot)
            brl.plot(int(xx), k, C.mix(ink, col, 0.55 + 0.45 * hot))
        brl.commit()
        # torn lip characters on the cell grid
        for i in range(ROWS):
            y = Y0 + i
            a = xl[i] - 1
            b = xr[i]
            if a >= 1:
                c.put(y, a, "\u2590", C.mix(C.BLOOD, C.RED_HI, 0.35 + 0.6 * hot))
                c.put(y, a - 1, "\u2593",
                      C.mix(ink, C.RED_DIM, 0.45 + 0.4 * hot))
            if b < W - 1:
                c.put(y, b, "\u258c", C.mix(C.GOLD, C.GOLD_HI, 0.4 + 0.6 * hot))
                c.put(y, b + 1, "\u2593",
                      C.mix(ink, C.GOLD_DIM, 0.45 + 0.4 * hot))
        # sparks thrown from the seam
        bucket = int(t * 15.0)
        for k in range(16):
            h1 = M.hash01(k, bucket)
            h2 = M.hash01(k + 40, bucket)
            h3 = M.hash01(k + 80, bucket)
            life = (t * (0.8 + h3) + h1) % 1.0
            y = Y0 + int(h2 * ROWS)
            x = int(SEAM + (h3 - 0.5) * 34.0 + (h1 - 0.5) * life * 16.0)
            if 0 <= x < W:
                ch = "\u00b7" if k % 3 else "\u2726"
                col = C.mix(C.RED_HI, C.GOLD_HI, h1)
                c.put(y, x, ch,
                      C.mix(ink, col, (1.0 - life) * (0.4 + 0.6 * hot)))

    # ==================================================================
    # SHOT 2 -- fold, altar, and the velvet black  (211.040 - 219.150)
    # ==================================================================
    def _draw_temple(self, c, ctx) -> None:
        t = ctx.t
        pulse = ctx.audio.pulse(t, 0.15)
        energy = ctx.audio.energy(t)
        fold = M.ease_in_out_expo(M.seg(t, self.t_fold0, self.t_fold1))
        fig = M.seg(t, self.t_fig0, self.t_fig1)
        halo = _smooth(self.t_halo0, self.t_halo1, t)
        glory = _smooth(self.t_glory0, self.t_glory1, t)
        inset = _smooth(self.t_ins0, self.t_ins1, t)
        dim = 1.0 - 0.52 * _smooth(self.t_dim0, self.t_fade0, t)
        diss = _smooth(self.t_fade0, self.t_fade1, t)

        lv = int(round(min(5.0, 0.35 + 1.25 * fold
                           + 3.3 * max(glory, 0.72 * halo) + 0.55 * pulse)))
        lut = self._temple_lut[max(0, min(5, lv))]
        for i in range(ROWS):
            c.bg[Y0 + i][:W] = lut[i]

        # the column of holy light
        self._column(c, t, 3.0 + 16.0 * fold,
                     0.24 + 0.22 * min(1.0, fold * 1.6) + 0.26 * glory,
                     pulse)

        # the two worlds, now bronze altar doors -> iron / gold wings
        self._doors(c, t, fold, glory, pulse)

        # sacred geometry behind the icon (sunburst + framing armillary)
        if halo > 0.012:
            self._rays(c, t, halo, glory)
            self._rings(c, t, halo, glory, self._rings_behind, 1.30)
        self._icon(c, t, fig, glory)
        # a second armillary layer orbits in front of the painted icon, and a
        # low sunburst continues outside its silhouette
        if halo > 0.20:
            self._rings(c, t, halo, glory, self._rings_front, 0.90)
            self._rays_front(c, t, halo, glory)
        if glory > 0.02:
            self._embers(c, t,
                         min(1.0, 0.35 + 0.65 * max(glory, 0.5 * halo)),
                         energy)

        # gold-leaf etching on the base of the altar
        if inset > 0.012:
            self._inscriptions(c, t, inset, glory)

        # the temple dies down, then dissolves into velvet black
        if dim < 0.999:
            self._mul_rows(c, dim)
        if diss > 0.0:
            self._mul_rows(c, 1.0 - diss)

        # one cold lonely prompt, typing itself out of the dark
        if t >= self.t_prompt - 0.12:
            self._prompt_line(c, t)

        # punctuation only: a single golden bloom on the last downbeat
        if 215.52 <= t <= 216.10:
            age = t - 215.56
            if age >= 0.0:
                c.fx.flash = max(c.fx.flash, 0.10 * math.exp(-age / 0.14))
                c.fx.flash_color = C.GOLD_HI
                c.fx.shake_x += (2.2 * math.exp(-age / 0.16)
                                 * math.sin(age * 92.0))
        if t < self.t_fold0 and t - self.t_b < 0.22:
            age = t - self.t_b
            c.fx.flash = max(c.fx.flash, 0.16 * math.exp(-age / 0.12))
            c.fx.flash_color = C.GOLD_HI
            c.fx.chroma = max(c.fx.chroma, 0.12 * math.exp(-age / 0.14))
            c.fx.shake_x += 2.0 * math.exp(-age / 0.15) * math.sin(age * 88.0)

    # -- the column of light --------------------------------------------
    def _column(self, c, t: float, half: float, strength: float,
                pulse: float) -> None:
        span0 = int(half) + 16
        hot = C.mix(C.GOLD_HI, C.WHITE, 0.34)
        for y in range(Y0, Y1):
            u = (y - Y0) / (ROWS - 1)
            vprof = 0.62 + 0.38 * (math.sin(math.pi * min(1.0, u * 1.02)) ** 0.35)
            vprof *= 1.0 - 0.92 * _smooth(0.80, 1.0, u)
            if vprof <= 0.02:
                continue
            span = max(4, int(span0 * (0.62 + 0.38 * vprof)))
            x0 = max(0, int(SEAM) - span)
            x1 = min(W, int(SEAM) + span)
            row = c.bg[y]
            shim = 0.92 + 0.08 * math.sin(y * 0.55 - t * 6.2)
            for x in range(x0, x1):
                d = abs(x - SEAM)
                f = max(0.0, 1.0 - d / span)
                a = strength * vprof * (f ** 1.6) * shim * (0.70 + 0.40 * pulse)
                if a < 0.015:
                    continue
                row[x] = C.mix(row[x], hot, min(0.94, a))

    # -- bronze doors -> wings ------------------------------------------
    def _doors(self, c, t: float, fold: float, glory: float,
               pulse: float) -> None:
        frames = self._door_frames
        k = int(round(M.clamp01(fold) * (len(frames) - 1)))
        wv, sp_l, sp_r, el, er = frames[k]
        lmul = 1.00 - 0.26 * fold + 0.14 * glory + 0.05 * pulse
        rmul = 1.05 - 0.10 * fold + 0.20 * glory + 0.05 * pulse
        c.sprite(Y0, 0, sp_l, fg_mul=lmul)
        c.sprite(Y0, W - wv, sp_r, fg_mul=rmul)
        q = _smooth(0.36, 0.92, fold)
        if q <= 0.01:
            return
        # rim light on the two inner edges + feather quills + wing witness text
        hot_l = C.mix(C.INK, C.RED_HI, 0.45 + 0.50 * glory)
        hot_r = C.mix(C.INK, C.GOLD_HI, 0.55 + 0.45 * glory)
        for i in range(ROWS):
            y = Y0 + i
            wr = el[i]
            x = wr - 1
            if x >= 1:
                c.put(y, x, "\u2590", hot_l)
                c.put(y, x - 1, "\u2593",
                      C.mix(C.INK, C.RED_DIM, 0.42 + 0.32 * glory))
            xr = W - wr
            if xr < W - 1:
                c.put(y, xr, "\u258c", hot_r)
                c.put(y, xr + 1, "\u2593",
                      C.mix(C.INK, C.GOLD_DIM, 0.42 + 0.32 * glory))
        # feather quills sweeping toward the tips
        for side in (0, 1):
            for rib in range(3):
                frac = 0.20 + rib * 0.27
                for i in range(3, ROWS - 2, 2):
                    wr = el[i]
                    xx = int(wr * frac + 1.6 * math.sin(i * 0.21 + rib * 1.9
                                                       + t * 0.7))
                    if side == 0:
                        x = max(1, min(wr - 2, xx))
                        col = C.mix(C.INK,
                                    C.RED_HI if rib % 2 else C.BLOOD,
                                    0.42 + 0.34 * glory)
                        c.put(Y0 + i, x,
                              "\u2572" if (i + rib) % 2 else "\u2571", col)
                    else:
                        x = min(W - 2, max(W - wr + 1, W - 1 - xx))
                        col = C.mix(C.INK,
                                    C.GOLD_HI if rib % 2 else C.GOLD,
                                    0.42 + 0.34 * glory)
                        c.put(Y0 + i, x,
                              "\u2571" if (i + rib) % 2 else "\u2572", col)
        # the two dead worlds engraved on their own wings
        eng_rows = (16, 26, 36)
        for j, (lt_txt, rt_txt) in enumerate(self._wing_texts):
            y = Y0 + eng_rows[j]
            wr = el[eng_rows[j]]
            if wr > len(lt_txt) + 6:
                c.text(y, max(2, wr - len(lt_txt) - 4), lt_txt[:wr - 5],
                       C.mix(C.INK, C.RED_DIM, 0.34 + 0.36 * glory))
            if wr > len(rt_txt) + 6:
                c.text(y, W - wr + 4, rt_txt[:wr - 5],
                       C.mix(C.INK, C.GOLD_DIM, 0.34 + 0.36 * glory))

    # -- sunflower ray burst --------------------------------------------
    def _rays(self, c, t: float, q: float, glory: float) -> None:
        brl = c.braille(Y0, 0, ROWS, W)
        cx = SEAM * 2.0
        cy = (25 - Y0) * 4.0 + 2.0
        rot = t * 0.045
        n = 44
        alpha = 0.72 + 0.28 * glory
        for i in range(n):
            a = rot + i * math.tau / n + (0.045 if i % 2 else 0.0)
            long = (196.0 if i % 2 == 0 else 148.0) * (0.70 + 0.48 * glory)
            r0 = (96.0 if i % 2 == 0 else 84.0) * q
            ca, sa = math.cos(a), math.sin(a)
            if i % 2 == 0:
                col = C.mix(C.GOLD, C.GOLD_HI, 0.35 + 0.55 * glory)
            else:
                col = C.mix(C.GOLD_DIM, C.GOLD, 0.30 + 0.45 * glory)
            col = C.mix(C.INK, col, alpha)
            r = r0
            while r < long:
                brl.plot(int(cx + ca * r), int(cy + sa * r), col)
                r += 3.0
        brl.commit()

    # -- the sunburst continues in front of the icon --------------------
    def _rays_front(self, c, t: float, q: float, glory: float) -> None:
        brl = c.braille(Y0, 0, ROWS, W)
        cx = SEAM * 2.0
        cy = (25 - Y0) * 4.0 + 2.0
        rot = -t * 0.030
        n = 28
        alpha = (0.26 + 0.26 * glory) * q
        for i in range(n):
            a = rot + i * math.tau / n + (0.06 if i % 2 else 0.0)
            ca, sa = math.cos(a), math.sin(a)
            col = C.mix(C.GOLD_DIM, C.GOLD_HI, 0.30 + 0.45 * glory)
            col = C.mix(C.INK, col, alpha)
            r = 112.0
            while r < 196.0:
                brl.plot(int(cx + ca * r), int(cy + sa * r), col)
                r += 4.0
        brl.commit()

    # -- counter-rotating braille armillary rings -----------------------
    def _rings(self, c, t: float, q: float, glory: float, specs,
               layer: float) -> None:
        brl = c.braille(Y0, 0, ROWS, W)
        for spec in specs:
            R0, tilt, spin, cyd, colbase, n = spec[:6]
            layer_a = layer if len(spec) < 7 else spec[6] * layer
            R = R0 * q * (1.0 + 0.03 * glory)
            if R < 6.0:
                continue
            ang = np.linspace(0.0, math.tau, n, endpoint=False)
            pts = np.stack([R * np.cos(ang), np.zeros(n), R * np.sin(ang)],
                           axis=1)
            pts = M.orbit(pts, yaw=spin * t, pitch=tilt)
            sx = 200.0 + pts[:, 0]
            sy = cyd + (-pts[:, 1])
            depth = pts[:, 2]
            for i in range(n):
                j = (i + 1) % n
                dep = 0.30 + 0.70 * (0.5 + 0.5 * depth[i] / max(1.0, R))
                bright = (0.52 + 0.48 * q) * layer_a * (0.65 + 0.35 * glory)
                col = C.mix(C.INK, C.mix(colbase, C.WHITE, 0.28 * glory),
                            min(1.0, dep * bright))
                brl.line(float(sx[i]), float(sy[i]), float(sx[j]),
                         float(sy[j]), col, 0.95, 1.0)
            # precision ticks around the ring
            tick = C.mix(C.INK,
                         C.mix(colbase, C.WHITE, 0.45 + 0.30 * glory),
                         min(1.0, (0.72 + 0.28 * q) * layer_a))
            step = max(4, n // 18)
            for i in range(0, n, step):
                dx = sx[i] - 200.0
                dy = sy[i] - cyd
                dd = math.hypot(dx, dy) or 1.0
                brl.line(float(sx[i]), float(sy[i]),
                         float(sx[i] + dx / dd * 4.0),
                         float(sy[i] + dy / dd * 4.0), tick, 0.95, 1.0)
        brl.commit()

    # -- the painted icon rises from the light --------------------------
    def _icon(self, c, t: float, fig: float, glory: float) -> None:
        if fig <= 0.004:
            return
        sp = self._icon_sprite
        y = int(round(M.lerp(Y1 + 1.0, ICON_Y, _smooth(0.0, 1.0, fig))))
        x = int(round(SEAM - sp.w * 0.5))
        alpha = M.clamp01(0.10 + 0.90 * _smooth(0.0, 0.30, fig))
        self._feather_blit(c, y, x, sp, feather=9, alpha=alpha)

    @staticmethod
    def _feather_blit(c, y: int, x: int, sp, *, feather: int = 9,
                      alpha: float = 1.0) -> None:
        """Content-band clipped feathered sprite blit (feather only the edges)."""
        h, w = sp.h, sp.w
        y0, y1 = max(Y0, y), min(Y1, y + h)
        x0, x1 = max(0, x), min(W, x + w)
        if y1 <= y0 or x1 <= x0:
            return
        feather = max(1, int(feather))
        for yy in range(y0, y1):
            sy = yy - y
            row_ch = c.ch[yy]
            row_fg = c.fg[yy]
            row_bg = c.bg[yy]
            src_ch = sp.ch[sy]
            src_fg = sp.fg[sy]
            src_bg = sp.bg[sy]
            for xx in range(x0, x1):
                sx = xx - x
                dy = min(sy, h - 1 - sy)
                dx = min(sx, w - 1 - sx)
                a = M.smooth01(0.0, float(feather), min(dy, dx)) * alpha
                gid = src_ch[sx]
                fg = src_fg[sx]
                bgs = src_bg[sx]
                if gid == 0:
                    blend = a * 0.85
                    row_bg[xx] = C.mix(bgs, row_bg[xx], blend)
                    row_fg[xx] = C.mix(row_fg[xx], row_bg[xx], blend * 0.5)
                    continue
                row_ch[xx] = gid
                row_fg[xx] = C.mix(row_bg[xx], fg, a)
                row_bg[xx] = C.mix(row_bg[xx], bgs, a)

    # -- gold embers rising through the light ---------------------------
    def _embers(self, c, t: float, q: float, energy: float) -> None:
        n = int(len(self._ember_data) * (0.4 + 0.6 * q))
        for (x0, phase, speed, size, ph) in self._ember_data[:n]:
            prog = (phase + t * speed) % 1.0
            y = Y1 - 1 - int(prog * ROWS)
            if y < Y0 + 2:
                continue
            tw = 0.5 + 0.5 * math.sin(t * (2.0 + size * 1.4) + ph)
            col = C.mix(C.GOLD_DIM, C.GOLD_HI, 0.20 + 0.55 * tw)
            col = C.mix(C.INK, col,
                        q * (0.30 + 0.70 * tw) * (0.7 + 0.3 * energy))
            ch = "\u00b7" if size == 0 else ("\u2022" if size == 1 else "\u2726")
            c.put(y, int(x0), ch, col)
            if size >= 2:
                c.put(min(Y1 - 1, y + 1), int(x0), "\u00b7",
                      C.mix(C.INK, C.AMBER_DIM, 0.45 * q))

    # -- gold-leaf etching on the base ----------------------------------
    def _inscriptions(self, c, t: float, q: float, glory: float) -> None:
        y = Y0 + 43
        rc = C.mix(C.INK, C.GOLD, 0.55 + 0.35 * q)
        c.hline(y, 24, 97, rc)
        c.hline(y, 103, 176, rc)
        c.put(y, 98, "\u2747", C.mix(C.INK, C.GOLD_HI, 0.65 + 0.35 * q))
        c.put(y, 101, "\u2747", C.mix(C.INK, C.GOLD_HI, 0.65 + 0.35 * q))
        self._etch(c, Y0 + 45, M.spread_text(self._insc_nation, 2), q,
                   base=C.GOLD, hi=C.GOLD_HI, gain=6.0)
        self._etch(c, Y0 + 47, M.spread_text(self._insc_deity, 1),
                   _smooth(0.36, 1.0, q), base=C.GOLD_DIM, hi=C.GOLD,
                   gain=5.0)

    def _etch(self, c, y: int, text: str, q: float, *, base: int, hi: int,
              gain: float) -> None:
        n = len(text)
        x0 = (W - n) // 2
        reveal = q * 1.16
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            p = M.clamp01((reveal - i / n) * gain)
            if p <= 0.02:
                continue
            col = C.mix(C.INK, hi if p > 0.8 else base, 0.25 + 0.75 * p)
            c.put(y, x0 + i, ch, col)
        pen = int(reveal * n)
        if 0 <= pen < n and reveal < 1.0:
            c.put(y, x0 + pen, "\u25ae", C.mix(C.WHITE, C.GOLD_HI, 0.35))

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _mul_rows(c, f: float) -> None:
        if f <= 0.015:
            for y in range(Y0, Y1):
                c.ch[y] = [0] * W
                c.fg[y] = [C.TEXT] * W
                c.bg[y] = [C.INK] * W
            return
        for y in range(Y0, Y1):
            c.fg[y] = [C.scale(v, f) for v in c.fg[y]]
            c.bg[y] = [C.scale(v, f) for v in c.bg[y]]

    def _prompt_line(self, c, t: float) -> None:
        text = self._prompt
        pm = _smooth(self.t_prompt, self.t_prompt + 0.50, t)
        n_show = int(round(len(text) * pm))
        x0 = (W - len(text)) // 2
        y = Y0 + 28
        off = 0
        for (seg, col) in self._prompt_segs:
            if off >= n_show:
                break
            take = min(len(seg), n_show - off)
            if take > 0:
                c.text(y, x0 + off, seg[:take],
                       C.mix(C.INK, col, 0.30 + 0.70 * pm))
            off += len(seg)
        # slowly blinking block cursor, sitting with the last note
        if pm >= 0.999:
            phase = (t * 0.85) % 1.0
            if phase < 0.56:
                c.put(y, x0 + len(text), "\u2588", C.TEXT_HI)
        else:
            c.put(y, x0 + n_show, "\u2588", C.mix(C.INK, C.TEXT_HI, pm))
