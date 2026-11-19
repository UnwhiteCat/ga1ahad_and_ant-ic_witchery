
"""Scene 3 -- 01:03.860 - 01:30.190 (VTT cues 17..29).

Shot list (one idea per shot, cut on the lyric):

63.860  the opening bell: a full-bleed wall of gold, a huge braille tape curve,
        gold dust, then a large chiaroscuro still-life insert (the poisoned
        tea) -- the party upstairs.
66.360  the camera falls: the golden world is compressed into one glaring
        ticker strip along the top, a thick steel plate sweeps through the
        frame, and Hall B-07 opens below in freezing black.
69.450  bipolar light cuts on the five "Eat up" hits: golden over-exposed
        altarpiece (the 2D illustrated bust in a rotating halo glare) cuts
        against deep red fear (the desk / the smile, trembling in a pool of
        red) while the one left portrait window carries the voice: the human
        types late and shaking, the model always answers clean and complete.
84.630  silence: every tremor drops to zero.  A slow push into the illustrated
        eyes; far in the dark a door lock turns from green to red and the
        bolts fall -- straight into S3.5's blast door.

All layout, glyphs and telemetry live here; every name and every story string
comes from the content layer (content/<locale>/scenes/s3.toml + glossary).
"""

from __future__ import annotations

import math

from .. import config as C
from .. import motion as M
from ..assets import camera_sprite, keyframe
from ..canvas import wrap
from .base import Scene

W, H = C.W, C.H
Y0, Y1 = C.CONTENT_Y0, C.CONTENT_Y1
SX, SW = C.STAGE_X, C.STAGE_W

# --------------------------------------------------------------------------
# scene window and VTT cue range (text/timing only ever comes from the VTT)
# --------------------------------------------------------------------------
FIRST, LAST = 17, 29
T0, T1 = 63.860, 90.190

# shot boundaries (absolute track time)
BEL = 63.860
TEA_IN = 64.50
TEA_OUT = 65.75
FALL = 66.360
PLATE_END = 67.790
BIPOLAR = 69.450
SILENCE = 84.630

# the five "Eat up" hits -- golden prayer; the gaps between are red fear
GOLD_HITS = (69.45, 72.52, 75.52, 78.30, 81.21)
GOLD_CUES = {18: 0, 20: 1, 23: 2, 25: 3, 27: 4}
RED_CUES = {19: 0, 21: 1, 24: 2, 26: 3, 28: 4}

# --------------------------------------------------------------------------
# red close-up coverage: cue -> (keyframe, rows, zoom0, zoom1, tint, y, cx, cy)
# --------------------------------------------------------------------------
RED_SHOTS = (
    ("desk", 34, 1.02, 1.14, 0.24, 8, 0.47, 0.44),
    ("smile", 34, 1.14, 1.30, 0.20, 7, 0.50, 0.40),
    ("desk-tap", 32, 1.04, 1.18, 0.26, 9, 0.52, 0.45),
    ("smile", 38, 1.20, 1.38, 0.18, 5, 0.50, 0.37),
    ("desk", 40, 1.08, 1.30, 0.26, 4, 0.48, 0.40),
)

# golden altarpiece per beat: bust rows and over-exposure amount
GOLD_SHOTS = ((24, 0.10), (25, 0.16), (26, 0.22), (27, 0.30), (28, 0.42))

# camera hits (absolute time -> fx).  Short punctuation, never a long filter.
HITS = (
    (BEL, 0.55, C.WHITE, 1.4, 0.00, 0.00),
    (69.45, 0.34, C.GOLD_HI, 0.9, 0.00, 0.00),
    (70.86, 0.22, C.RED_HI, 1.2, 0.05, 0.10),
    (72.52, 0.34, C.GOLD_HI, 0.9, 0.00, 0.00),
    (73.55, 0.22, C.RED_HI, 1.2, 0.05, 0.10),
    (75.52, 0.34, C.GOLD_HI, 0.9, 0.00, 0.00),
    (76.54, 0.22, C.RED_HI, 1.2, 0.05, 0.10),
    (78.30, 0.34, C.GOLD_HI, 0.9, 0.00, 0.00),
    (79.40, 0.22, C.RED_HI, 1.2, 0.05, 0.10),
    (81.21, 0.40, C.GOLD_HI, 1.0, 0.00, 0.00),
    (82.22, 0.26, C.RED_HI, 1.4, 0.05, 0.12),
    (67.20, 0.30, C.WHITE, 2.4, 0.10, 0.00),
)

LOCK_AT = 87.40                     # green -> red, in silence
BOLT_AT = (88.35, 88.80, 89.25, 89.70)


def _seg(t: float, a: float, b: float) -> float:
    return M.seg(t, a, b)


def _held(t: float, a: float, b: float, fade_in: float = 0.0,
          fade_out: float = 0.0) -> float:
    """1 inside [a,b] with optional ramps at both ends."""
    if t < a or t > b:
        return 0.0
    v = 1.0
    if fade_in > 0:
        v = min(v, _seg(t, a, a + fade_in))
    if fade_out > 0:
        v = min(v, 1.0 - _seg(t, b - fade_out, b))
    return v


class Scene3(Scene):
    NAME = "s3"

    def __init__(self, assets, audio, timeline, content) -> None:
        super().__init__(assets, audio, timeline, content)
        S = self.script
        # dialogue + content tables (all on-screen wording lives in the TOML)
        self._dahlia = {c: tuple(getattr(S.dahlia, "c%d" % c)) for c in range(FIRST, LAST + 1)}
        self._replies = {r.cue: tuple(r.lines) for r in S.claude.reply}
        self._rites = list(S.eat.rites)
        self._prayers = list(S.eat.prayers)
        self._full = list(S.eat.full)
        # static art
        self._tea = keyframe("tea")
        self._eyes = keyframe(S.assets.eyes)
        self._faces = {"desk": keyframe("desk"), "desk-tap": keyframe("desk-tap"),
                       "smile": keyframe(S.assets.smile)}
        self._space = self.assets.glyphs.char_id(" ")
        # precomputed colour fields (full canvas row tables, rows 2..52)
        self._gold_field = self._radial_field(
            W, focus=(132.0, 13.0), sx=0.95, sy=2.35, radius=132.0,
            stops=((0.00, C.WHITE), (0.16, C.mix(C.GOLD_HI, C.WHITE, 0.55)),
                   (0.44, C.GOLD), (0.72, C.mix(C.GOLD_DIM, C.GOLD, 0.45)),
                   (1.02, C.mix(C.INK, C.GOLD_DEEP, 0.42)), (1.45, C.INK)))
        self._red_field = self._radial_field(
            W, focus=(136.0, 26.0), sx=0.72, sy=2.45, radius=142.0,
            stops=((0.00, C.mix(C.RED_DEEP, C.RED, 0.30)), (0.32, C.RED_DEEP),
                   (0.66, C.mix(C.INK, C.RED_DEEP, 0.45)), (1.05, C.INK)))
        self._hall_field = None
        self._cer_field = self._ceremony_field()
        # film grain / stipple positions for the gold dust (precomputed)
        self._dust = tuple((M.hash01(i, 3.1), M.hash01(i, 7.7), M.hash01(i, 11.3),
                            M.hash01(i, 19.1)) for i in range(150))
        # storm markers for the falling sequence
        self._streaks = tuple((M.hash01(i, 1.7), M.hash01(i, 2.9),
                               M.hash01(i, 5.3), 6 + 16 * M.hash01(i, 8.1))
                              for i in range(46))
        # a cache for brightness-scaled packed colours
        self._scale_cache: dict[tuple[int, int], int] = {}

    # ------------------------------------------------------------------
    # precomputed fields
    # ------------------------------------------------------------------
    @staticmethod
    def _radial_field(width, focus, sx, sy, radius, stops):
        fx, fy = focus
        rows = []
        for y in range(Y0, Y1):
            dy = (y + 0.5 - fy) * sy
            row = []
            for x in range(width):
                dx = (x + 0.5 - fx) * sx
                u = math.hypot(dx, dy) / radius
                row.append(C.ramp(list(stops), u))
            rows.append(row)
        return rows

    def _ceremony_field(self):
        """Trade-floor wall of light: dark above, molten gold at the horizon."""
        stops = ((2, C.INK), (18, C.mix(C.INK, C.GOLD_DEEP, 0.22)),
                 (32, C.GOLD_DEEP), (39, C.mix(C.GOLD_DEEP, C.GOLD, 0.60)),
                 (44, C.mix(C.GOLD, C.GOLD_HI, 0.55)),
                 (48, C.mix(C.GOLD_HI, C.WHITE, 0.25)),
                 (52, C.mix(C.GOLD_DEEP, C.INK, 0.40)))
        rows = []
        for y in range(Y0, Y1):
            base = C.ramp(list(stops), y)
            near = max(0.0, 1.0 - abs(y - 44) / 10.0)
            row = []
            for x in range(W):
                k = 0.5 + 0.5 * math.sin(x * 0.045 + y * 0.9)
                row.append(C.mix(base, C.GOLD_HI, 0.14 * near * k))
            rows.append(row)
        return rows

    # ------------------------------------------------------------------
    # colour helpers (brightness caches keep the per-frame budget tight)
    # ------------------------------------------------------------------
    def _scaled(self, color: int, f: float) -> int:
        key = (color, int(f * 64.0))
        hit = self._scale_cache.get(key)
        if hit is None:
            hit = C.scale(color, key[1] / 64.0)
            self._scale_cache[key] = hit
        return hit

    def _fill_field(self, c, field, bright: float = 1.0, to_white: float = 0.0) -> None:
        space = self._space
        for i, y in enumerate(range(Y0, Y1)):
            src = field[i]
            if to_white > 0.0:
                row = [C.mix(self._scaled(v, bright), C.WHITE, to_white) for v in src]
            else:
                row = [self._scaled(v, bright) for v in src]
            c.ch[y] = [space] * W
            c.fg[y] = row
            c.bg[y] = list(row)   # never alias fg/bg: c.text/c.fill write both

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------
    def draw(self, c, ctx) -> None:
        t = ctx.t
        self._hits(c, t)
        if t < FALL:
            if TEA_IN <= t < TEA_OUT:
                self._tea_shot(c, ctx)
            else:
                self._ceremony(c, ctx, peak=1 if t >= TEA_OUT else 0)
        elif t < BIPOLAR:
            self._fall(c, ctx)
            if t >= 68.45:
                self._window(c, ctx, fade=_seg(t, 68.45, 68.95))
        elif t < SILENCE:
            self._bipolar(c, ctx)
            self._window(c, ctx, fade=1.0)
        else:
            self._silence(c, ctx)

    # ------------------------------------------------------------------
    # camera hits
    # ------------------------------------------------------------------
    def _hits(self, c, t: float) -> None:
        for at, flash, color, shake, glitch, chroma in HITS:
            age = t - at
            if 0.0 <= age < 0.42:
                M.punctuate(c, age, flash=flash, flash_color=color, shake=shake,
                            glitch=glitch, chroma=chroma, decay=0.12)

    # ==================================================================
    # SHOT A -- the opening bell (full-bleed gold)
    # ==================================================================
    def _ceremony(self, c, ctx, peak: int) -> None:
        t = ctx.t
        S = self.script.exchange
        tt = t - BEL
        pulse = ctx.audio.pulse(t, 0.14)
        # 1. the wall of light -------------------------------------------
        gain = (0.92 + 0.10 * peak) + 0.10 * pulse
        self._fill_field(c, self._cer_field, bright=gain)
        # horizon shimmer: brief horizontal highlights
        for yy in range(29, 38):
            a = 0.10 + 0.10 * math.sin(yy * 0.8 + t * 2.4)
            for x in range(0, W, 3):
                c.blend_bg(yy, x, C.GOLD_HI, a)
        # 2. the tape curve (braille, white-hot against the dark sky) ----
        grow = M.ease_out_expo(_seg(tt, 0.0, 0.62))
        br = c.braille(4, 0, 36, W)
        pw, ph = W * 2, 36 * 4
        amp = 1.0 + 0.30 * peak
        # the previous session, a dim ghost curve for depth
        prev = None
        for x in range(0, pw, 2):
            u = x / (pw - 1.0)
            y2 = ph - 6 - 58.0 * (u ** 1.9) + 4.0 * math.sin(u * 31.0 - t * 2.2)
            if prev is not None:
                br.line(prev[0], prev[1], x, y2, C.mix(C.INK, C.GOLD_DIM, 0.75), 0.55, 0.8)
            prev = (x, y2)
        # today's tape: a huge dynamic rising curve, drawn in as the bell rings
        prev = None
        for x in range(0, pw):
            u = x / (pw - 1.0)
            if u > grow + 0.02:
                break
            rise = 96.0 * (u ** 1.75) * amp
            wig = (7.0 * math.sin(u * 21.0 + t * 1.9)
                   + 3.2 * math.sin(u * 57.0 - t * 3.7)
                   + 1.6 * math.sin(u * 143.0 + t * 6.1))
            yy = ph - 18 - rise + wig
            if prev is not None:
                br.line(prev[0], prev[1], x, yy, C.WHITE, 0.97, 0.55)
                br.line(prev[0], prev[1] + 1.0, x, yy + 1.0, C.WHITE, 0.80, 0.55)
                br.line(prev[0], prev[1] + 2.5, x, yy + 2.5, C.mix(C.GOLD_HI, C.WHITE, 0.4), 0.50, 0.55)
                br.line(prev[0], prev[1] - 1.5, x, yy - 1.5, C.WHITE, 0.70, 0.55)
                br.line(prev[0], prev[1] - 3.0, x, yy - 3.0, C.GOLD_HI, 0.38, 0.55)
                br.line(prev[0], prev[1] - 5.0, x, yy - 5.0, C.GOLD, 0.18, 0.55)
            prev = (x, yy)
        # sky gridlines and the last-price marker
        for g in (1, 2, 3, 4):
            gy = int(ph * (0.20 + 0.16 * g))
            br.line(0, gy, pw - 1, gy, C.mix(C.INK, C.GOLD_DIM, 0.50), 0.20, 2.0)
        if prev is not None:
            mx, my = prev
            br.line(mx, 0, mx, ph - 1, C.mix(C.GOLD_HI, C.WHITE, 0.5), 0.35, 2.0)
            for d in range(-3, 4):
                br.plot(mx + d, int(my), C.WHITE, 0.9)
                br.plot(mx, int(my) + d, C.WHITE, 0.9)
        # 3. gold dust ---------------------------------------------------
        for i, (a, b, cc, dd) in enumerate(self._dust):
            x = int((a * W + t * (5.0 + 9.0 * cc)) % W) * 2
            y = int((b * ph - t * (16.0 + 38.0 * dd)) % ph)
            if x < pw - 1 and y >= 0:
                br.plot(x, y, C.mix(C.GOLD, C.WHITE, 0.35 + 0.5 * cc),
                        0.35 + 0.5 * dd)
        br.commit()
        # 4. monumental type --------------------------------------------
        wal = min(1.0, tt / 0.42)
        xl = M.lerp(-30.0, 9.0, M.ease_out_expo(wal))
        M.big_text(c, 4, int(xl), S.exchange, C.GOLD_HI, scale=2, spacing=2,
                   top=C.WHITE, bottom=C.GOLD)
        ev = M.spread_text(S.event, 1)
        c.text(21, int(M.lerp(-40, 11, M.ease_out_expo(min(1.0, tt / 0.6)))),
               ev, C.mix(C.GOLD_HI, C.WHITE, 0.35), bold=True)
        # last price / gain at the right, small and precise
        rx = W - 30
        c.text(4, rx, S.last, C.mix(C.WHITE, C.GOLD_HI, 0.25), bold=True)
        c.text(5, rx, S.gain, C.GOLD_HI, bold=True)
        c.text(21, W - 26, S.place, C.GOLD, bold=True)
        c.text(22, W - 26, S.day, C.mix(C.GOLD, C.GOLD_DIM, 0.4))
        # 5. bottom tape ------------------------------------------------
        tape = S.tape
        off = int(t * 26.0)
        bgrd = C.mix(C.INK, C.GOLD_DEEP, 0.65)
        c.fill(51, 0, 1, W, " ", C.GOLD_HI, bgrd)
        for x in range(W):
            ch = tape[(off + x) % len(tape)]
            c.put(51, x, ch, C.mix(C.INK, C.GOLD_DEEP, 0.5), None)
        c.text(49, 2, S.caption, C.mix(C.INK, C.GOLD_DEEP, 0.35))
        c.put(49, 0, "▌", C.mix(C.INK, C.GOLD_DEEP, 0.45))
        # 6. bell flare at the very start
        if peak:
            M.vignette(c, 0.30)

    # ------------------------------------------------------------------
    # SHOT A2 -- the large still-life insert (the poisoned tea)
    # ------------------------------------------------------------------
    def _tea_shot(self, c, ctx) -> None:
        t = ctx.t
        u = _seg(t, TEA_IN, TEA_OUT)
        c.fill(Y0, 0, Y1 - Y0, W, " ", C.TEXT, C.BLACK)
        rows = 44
        cols = max(8, int(round(2 * rows * self._tea.width / self._tea.height)))
        sp = camera_sprite(self._tea, rows, cols, zoom=1.02 + 0.13 * u,
                           center=(0.495 + 0.02 * u, 0.515), bright=1.04,
                           sat=1.08, contrast=1.05)
        x = (W - cols) // 2
        M.feather_sprite(c, 3, x, sp, feather=11, bg=C.BLACK,
                         tint=C.GOLD, tint_amt=0.04)
        # a faint warm key light from upper left + gold dust across the table
        for i, (a, b, cc, dd) in enumerate(self._dust[:80]):
            yy = 4 + int((b * 42 + t * (2.0 + 4.0 * dd)) % 40)
            xx = int((a * W + t * (2.0 + 5.0 * cc)) % W)
            c.put(yy, xx, "·", C.mix(C.GOLD_DIM, C.GOLD_HI, 0.25 + 0.5 * cc))
        M.vignette(c, 0.78)
        # a thin hairline of light along the table edge, lower frame
        c.hline(49, 6, W - 7, C.mix(C.INK, C.GOLD_DIM, 0.55))
        c.put(49, W - 6, "◢", C.GOLD_DIM)

    # ==================================================================
    # SHOT B -- the fall: gold world compressed, steel plate, Hall B-07
    # ==================================================================
    def _fall(self, c, ctx) -> None:
        t = ctx.t
        tp = t - FALL
        if tp < 0.44:
            self._fall_sink(c, ctx, tp / 0.44)
            return
        if tp < 1.39:
            self._plate(c, ctx, (tp - 0.44) / 0.95)
            return
        self._hall(c, ctx, _seg(t, PLATE_END, PLATE_END + 0.7))

    def _fall_sink(self, c, ctx, u: float) -> None:
        """The golden ceiling tears away upward; the dark shaft swallows us."""
        t = ctx.t
        c.fill(Y0, 0, Y1 - Y0, W, " ", C.TEXT, C.INK)
        band = int(round(M.lerp(50, 2, M.ease_in_expo(u))))
        y1 = Y0 + band
        # the party seen from below: squeezed into the top of the frame
        for i, y in enumerate(range(Y0, min(Y1, y1))):
            src = self._cer_field[min(len(self._cer_field) - 1,
                                      int((0.60 + 0.40 * i / max(1, band))
                                          * len(self._cer_field)))]
            f = 1.0 + 0.7 * u
            row = [self._scaled(v, f) for v in src]
            c.ch[y] = [self._space] * W
            c.fg[y] = row
            c.bg[y] = list(row)
        if band > 2:
            tape = self.script.exchange.tape
            off = int(t * 48.0)
            for x in range(W):
                ch = tape[(off + x) % len(tape)]
                c.put(y1 - 2, x, ch, C.mix(C.INK, C.GOLD_DEEP, 0.5), None)
        c.hline(y1 - 1, 0, W, C.mix(C.GOLD_HI, C.WHITE, 0.55))
        c.hline(y1, 0, W, C.WHITE)
        # the shaft: long gold speed streaks rushing upward
        br = c.braille(y1 + 1, 0, max(1, Y1 - y1 - 1), W)
        ph = max(1, Y1 - y1 - 1) * 4
        for a, b, cc, ln in self._streaks:
            x = int(a * W) * 2
            speed = 90.0 + 420.0 * u
            yy = int((b * ph + t * speed) % (ph + ln)) - ln
            br.line(x, yy, x, yy + int(ln * (1.0 + 1.5 * u)),
                    C.mix(C.INK, C.GOLD_DIM, 0.30 + 0.6 * cc), 0.65, 1.0)
        br.commit()
        # a few hard vertical light bars in the shaft
        for i in range(7):
            x = int((M.hash01(i, 2.2) * 0.9 + 0.05) * W)
            c.vline(x, y1 + 1, Y1, C.mix(C.INK, C.GOLD_DIM, 0.30 + 0.2 * M.hash01(i, 4)))
        M.grain(c, t, seed=7, count=50, color=C.GOLD_DIM, amount=0.10)

    def _plate(self, c, ctx, p: float) -> None:
        """A thick steel plate sweeps through the falling camera."""
        t = ctx.t
        y_top = 56.0 - 112.0 * (p ** 0.80)
        thick = 56
        if p < 0.36:
            # 1. the gold shaft above the rising plate
            c.fill(Y0, 0, Y1 - Y0, W, " ", C.TEXT, C.INK)
            br = c.braille(Y0, 0, Y1 - Y0, W)
            ph = (Y1 - Y0) * 4
            top = int(max(Y0, y_top))
            for yy in range(Y0, top):
                a = 0.10 + M.smooth01(Y0, max(Y0 + 1, top), yy) * 0.62
                c.fill_bg(yy, 0, 1, W, C.mix(C.INK, C.GOLD, a * 0.55))
            for a, b, cc, ln in self._streaks[:30]:
                x = int(a * W) * 2
                yy = int((b * ph + t * (150.0 + 80.0 * cc)) % (ph + ln)) - ln
                if yy + ln < top * 4:
                    br.line(x, yy, x, yy + ln,
                            C.mix(C.INK, C.GOLD_DIM, 0.4 + 0.4 * cc), 0.65, 1.0)
            br.commit()
        else:
            # 2. Hall B-07 below; the plate's underside flees upward
            self._hall(c, ctx, 1.0)
        # plate body: a monumental slab of gunmetal
        a0 = max(Y0, int(y_top))
        a1 = min(Y1, int(y_top) + thick)
        if a1 > a0:
            for yy in range(a0, a1):
                r = yy - y_top
                u_r = r / float(thick)
                base = C.mix(C.mix(C.INK2, C.BORDER, 0.52),
                             C.mix(C.INK, C.INK2, 0.5), u_r * 0.85)
                if r < 8:
                    base = C.mix(base, C.mix(C.BORDER_HI, C.GOLD_DIM, 0.45),
                                 0.30 * (1.0 - r / 8.0))
                if int(r) % 13 == 0:
                    base = C.mix(base, C.INK, 0.55)
                c.fill(yy, 0, 1, W, " ", C.TEXT, base)
            # vertical panel seams and rivet columns
            for x in range(4, W, 23):
                c.vline(x, a0, a1, C.mix(C.INK, C.BORDER, 0.45))
            for yy in range(a0, a1):
                r = int(yy - y_top)
                if r % 13 == 5:
                    for x in range(8, W, 23):
                        c.put(yy, x, "◉", C.mix(C.INK, C.BORDER_HI, 0.52))
                        c.put(yy, x + 1, "◉", C.mix(C.INK, C.BORDER_HI, 0.38))
                if 25 <= r <= 29 and (r % 2 == 0):
                    for x in range(W):
                        if ((x // 2) + r) % 2 == 0:
                            c.put(yy, x, "▚", C.mix(C.INK, C.AMBER_DIM, 0.55),
                                  C.mix(C.INK2, C.INK, 0.55))
            # a giant stencilled hall code, moving with the slab
            M.big_text(c, a0 + 6, 56, self.script.hall.id, C.mix(C.INK, C.BORDER_HI, 0.55),
                       scale=2, spacing=2)
            # hot leading edge
            edge_row = a0 if y_top > 2 else a1 - 1
            c.hline(edge_row, 0, W, C.mix(C.GOLD_HI, C.WHITE, 0.7))
            for x in range(0, W, 5):
                c.put(edge_row, x, "▬", C.WHITE)
        # friction sparks at the leading edge
        if a1 > a0:
            spr = c.braille(Y0, 0, Y1 - Y0, W)
            edge = (a0 if y_top > 2 else a1 - 1) - Y0
            for i in range(30):
                h = M.hash01(i, math.floor(t * 30))
                x = int((h * 197)) * 2
                ln = 2 + int(10 * M.hash01(i, 3))
                yy = int(edge * 4) - int(M.hash01(i, 5) * 18)
                spr.line(x, yy, x, yy - ln, C.mix(C.GOLD_HI, C.WHITE, 0.4), 0.8)
            spr.commit()

    def _hall(self, c, ctx, settle: float = 1.0) -> None:
        """Hall B-07: black, cold, waiting under the far gold strip."""
        t = ctx.t
        S = self.script.hall
        c.fill(Y0, 0, Y1 - Y0, W, " ", C.TEXT, C.INK)
        # the last wedge of the party, crushed into one strip along the top
        self._strip(c, ctx, heat=0.95)
        # a faint cold ambient wash so the black reads as a room, not a void
        for yy in range(6, 52):
            for x in range(SX, W, 2):
                c.blend_bg(yy, x, C.CYAN_DEEP, 0.075)
        # ceiling: a long cold structural line and hanging work lamps
        c.hline(6, SX, W, C.mix(C.INK, C.CYAN_DIM, 0.95))
        for k in range(6):
            x = SX + 9 + k * 24
            c.put(6, x, "┬", C.mix(C.INK, C.CYAN_HI, 0.60))
            on = M.hash01(k, math.floor(t * 2.4)) > 0.22
            c.put(7, x, "◉" if on else "○",
                  C.mix(C.INK, C.CYAN_HI, 0.95 if on else 0.28))
            c.vline(x, 8, 10, C.mix(C.INK, C.CYAN_DIM, 0.60))
        # rack silhouettes receding into the cold
        for i in range(9):
            x = SX + 6 + i * 15
            depth = 0.95 - 0.48 * (i / 8.0)
            c.vline(x, 8, 48, C.mix(C.INK, C.CYAN_DIM, depth))
            c.vline(x + 1, 8, 48, C.mix(C.INK, C.CYAN_DEEP, depth * 0.8))
            for y in range(11, 47, 3):
                on = M.hash01(i, y, math.floor(t * 2.0)) > 0.46
                accent = C.CYAN if i % 2 == 0 else C.GOLD
                c.put(y, x + 2, "▪",
                      C.mix(C.INK, accent, 0.95 if on else 0.18))
        # floor: perspective paving rushing beneath the fall
        br = c.braille(36, SX, 16, SW)
        vx = (132 - SX) * 2.0
        pw, ph = SW * 2, 16 * 4
        for k in range(-8, 9):
            br.line(vx, 0, vx + k * 27.0, ph, C.mix(C.INK, C.CYAN_DIM, 0.85), 0.65, 1.2)
        for yy in range(2, ph, 6):
            br.line(0, yy, pw - 1, yy, C.mix(C.INK, C.CYAN_DIM, 0.55), 0.6, 1.4)
        br.commit()
        # a cold shaft of light from the vents, centre of the hall
        for yy in range(7, 46):
            half = 5.0 + (yy - 7) * 0.58
            a = 0.17 * (1.0 - abs(yy - 24) / 30.0)
            for x in range(int(132 - half), int(132 + half)):
                c.blend_bg(yy, x, C.mix(C.CYAN_DEEP, C.TEXT_FAINT, 0.45), a)
        # freezing fog gathering along the floor
        for yy in range(40, 52):
            a = 0.08 + 0.24 * ((yy - 40) / 12.0)
            for x in range(SX, W, 2):
                c.blend_bg(yy, x, C.mix(C.INK, C.CYAN_DIM, 0.55), a)
        # far door, a red pulse in the dark
        c.vline(186, 22, 47, C.mix(C.INK, C.RED_DEEP, 0.65))
        c.vline(190, 22, 47, C.mix(C.INK, C.RED_DEEP, 0.45))
        c.put(30, 188, "●", C.mix(C.INK, C.RED, 0.65))
        c.hline(22, 186, 191, C.mix(C.INK, C.BORDER, 0.45))
        # location card, small and cold
        c.hline(44, SX + 2, SX + 58, C.mix(C.INK, C.CYAN_DIM, 0.75))
        c.text(45, SX + 3, S.id, C.mix(C.CYAN_HI, C.WHITE, 0.30), bold=True)
        c.text(45, SX + 3 + len(S.id) + 2, S.sub, C.mix(C.TEXT_FAINT, C.TEXT_DIM, 0.6))
        c.text(45, W - len(S.ceiling) - 3, S.ceiling, C.mix(C.RED_DIM, C.RED, 0.5))
        # residual falling motion at the start of the settle
        if settle < 1.0:
            k = 1.0 - settle
            br2 = c.braille(Y0, 0, Y1 - Y0, W)
            for a, b, cc, ln in self._streaks[:30]:
                x = int(a * W) * 2
                yy = int((b * 204 + t * 340.0) % (204 + ln)) - ln
                br2.line(x, yy, x, yy + ln, C.mix(C.INK, C.GOLD_DIM, 0.55 * k),
                         0.55, 1.2)
            br2.commit()
            M.vignette(c, 0.55 * k)

    def _strip(self, c, ctx, heat: float) -> None:
        """The upstairs revelry as one distant glaring gold ticker strip."""
        t = ctx.t
        tape = self.script.exchange.tape
        y = Y0
        off = int(t * 34.0)
        for x in range(SX, W):
            sh = 0.5 + 0.5 * math.sin(x * 0.21 + t * 3.3)
            col = C.mix(C.mix(C.INK, C.GOLD_DIM, 0.45),
                        C.mix(C.GOLD_HI, C.WHITE, 0.45),
                        M.clamp01(0.42 + 0.68 * heat * sh))
            c.put(y, x, " ", C.TEXT, col)
            ch = tape[(off + x) % len(tape)]
            c.put(y, x, ch, C.mix(C.INK, C.GOLD_DEEP, 0.45), None)
        glow = C.mix(C.INK, C.GOLD_DEEP, 0.55 * heat)
        c.fill(y + 1, SX, 1, SW, " ", C.GOLD_DIM, glow)
        for x in range(SX, W, 2):
            c.put(y + 2, x, "▁", C.mix(C.INK, C.GOLD_DIM, 0.55 * heat))

    # ==================================================================
    # SHOT C -- bipolar light cuts
    # ==================================================================
    def _bipolar(self, c, ctx) -> None:
        cue = ctx.lyric.index
        if cue in GOLD_CUES:
            span = self._cue_span(cue)
            u = _seg(ctx.t, span[0], span[1])
            self._gold(c, ctx, GOLD_CUES[cue], u)
        else:
            span = self._cue_span(cue)
            u = _seg(ctx.t, span[0], span[1])
            self._red(c, ctx, RED_CUES.get(cue, 0), u)

    def _cue_span(self, cue: int) -> tuple[float, float]:
        ly = self.cues[cue - FIRST]
        return (ly.start, ly.start + max(1e-3, ly.duration))

    # -- golden altarpiece ----------------------------------------------
    def _gold(self, c, ctx, bi: int, u: float) -> None:
        t = ctx.t
        pulse = ctx.audio.pulse(t, 0.13)
        rows, tint = GOLD_SHOTS[bi]
        # over-exposure builds over the five rites
        white = 0.0
        if bi == 3:
            white = 0.16 + 0.16 * u
        elif bi == 4:
            white = 0.30 + 0.42 * u
        bright = 0.96 + 0.06 * bi + 0.10 * pulse
        self._fill_field(c, self._gold_field, bright=bright, to_white=white)
        br = c.braille(Y0, SX, Y1 - Y0, SW)
        pw, ph = SW * 2, (Y1 - Y0) * 4
        cx, cy = (132 - SX) * 2.0, (13 - Y0) * 4.0
        # 1. god rays, turning slowly behind the head
        n = 30
        phase = t * 0.22 + bi * 0.4
        ray = C.mix(C.GOLD_HI, C.WHITE, 0.35 + 0.4 * white)
        for i in range(n):
            a = phase + 2.0 * math.pi * i / n
            r0 = 26.0 + 6.0 * math.sin(t * 0.7 + i)
            r1 = 130.0 + 46.0 * M.hash01(i, 7)
            ca, sa = math.cos(a), math.sin(a)
            steps = 16
            for k in range(steps):
                q = k / (steps - 1.0)
                rr = r0 + (r1 - r0) * q
                alpha = (1.0 - q) * 0.55
                if alpha < 0.05:
                    continue
                br.plot(int(cx + ca * rr), int(cy + sa * rr * 0.92),
                        C.mix(C.GOLD, ray, alpha), 0.9)
        # 2. rotating halos: three tilted braille rings encircling the head
        cam = M.Camera(x=0.0, y=0.0, z=-9.0, fov=1.0)
        for i, (rad, zoff, tilt, spin, lift) in enumerate((
                (5.9, 2.6, 1.30, 0.55, 0.6), (4.9, 1.6, 1.46, -0.72, -0.4),
                (6.9, 3.4, 1.14, 0.34, 0.2))):
            seg = M.ring_segments(rad, 64, axes=(0, 1),
                                  center=(0.0, lift, zoff))
            seg = M.orbit(seg, pitch=tilt + 0.10 * math.sin(t * 0.9 + i),
                          roll=spin * t + i)
            M.draw_segments(br, seg, cam, C.mix(C.GOLD_HI, C.WHITE, 0.55),
                            alpha=0.26 + 0.10 * i, fog=0.28, zmin=2.0,
                            zmax=14.0, step=1.2)
        # anamorphic glare: long thin horizontal flares either side of the head
        for k, off in enumerate((-3, -2, 2, 3)):
            yy = int(cy + off * 2.2)
            alpha = 0.20 - 0.03 * abs(off)
            br.line(4, yy, pw - 4, yy, C.mix(C.GOLD_HI, C.WHITE, 0.5), alpha, 2.0)
        # 3. dust motes rising through the glare
        for i, (a, b, cc, dd) in enumerate(self._dust):
            if i % 2 and bi < 4:
                continue
            x = int((a * SW + t * (2.0 + 6.0 * cc)) % SW) * 2
            y = int((b * ph - t * (10.0 + 26.0 * dd)) % ph)
            br.plot(x, y, C.mix(C.GOLD, C.WHITE, 0.35 + 0.55 * dd),
                    0.30 + 0.45 * cc)
        br.commit()
        # 3b. a vertical shaft of light behind the head
        for yy in range(Y0, Y1):
            dyy = abs(yy + 0.5 - 14.0)
            half = 9.0 + dyy * 1.2
            a = 0.16 * max(0.0, 1.0 - dyy / 30.0)
            for x in range(int(132 - half), int(132 + half) + 1):
                c.blend_bg(yy, x, C.mix(C.GOLD_HI, C.WHITE, 0.55), a)
        # 4. the illustrated bust in the glare ---------------------------
        bust = self.assets.claude_bust(rows)
        bx = 132 - bust.w // 2
        by = 4 - (rows - 24) // 2
        M.feather_sprite(c, by, bx, bust, feather=8,
                         bg=C.mix(C.GOLD, C.GOLD_HI, 0.55),
                         tint=C.mix(C.GOLD_HI, C.WHITE, 0.2),
                         tint_amt=tint + 0.10 * white, alpha=0.98)
        # 5. the prayer, monumental -------------------------------------
        word = self._prayers[bi].upper()
        ww, _ = M.big_text_size(word, 2, 2)
        px = SX + (SW - ww) // 2
        M.big_text(c, 34, px + 1, word, C.mix(C.GOLD_DEEP, C.INK, 0.40), scale=2,
                   spacing=2)
        M.big_text(c, 33, px, word, C.mix(C.GOLD_HI, C.WHITE, 0.55), scale=2,
                   spacing=2, top=C.mix(C.GOLD, C.WHITE, 0.45), bottom=C.WHITE)
        rite = M.spread_text(self._rites[bi], 1)
        c.text(30, SX + (SW - len(rite)) // 2, rite,
               C.mix(C.GOLD_DEEP, C.INK, 0.30))
        full = M.spread_text(self._full[bi], 1)
        if len(full) < SW:
            c.text(50, SX + (SW - len(full)) // 2, full,
                   C.mix(C.GOLD_HI, C.WHITE, 0.35))
        M.vignette(c, 0.34 + 0.10 * white)

    # -- deep red fear --------------------------------------------------
    def _red(self, c, ctx, bi: int, u: float) -> None:
        t = ctx.t
        pulse = ctx.audio.pulse(t, 0.15)
        name, rows, z0, z1, tint, py, ccx, ccy = RED_SHOTS[bi]
        tremor = 0.45 + 0.14 * bi + 0.35 * pulse
        self._fill_field(c, self._red_field, bright=1.00 + 0.20 * pulse)
        # the party still glares along the top, a world away
        self._strip(c, ctx, heat=0.72)
        # cold reminders of the hall at the far right edge
        for i in range(3):
            x = W - 5 - i * 4
            c.vline(x, 8, 46, C.mix(C.INK, C.CYAN_DEEP, 0.26 - i * 0.05))
        # heat: slow red wash rising from the bottom
        for yy in range(40, Y1):
            a = 0.06 + 0.06 * math.sin(t * 1.7 + yy * 0.5)
            c.blend_bg(yy, SX, C.RED_DEEP, a)
        # the close-up, trembling in its pool of red
        img = self._faces[name]
        cols = max(8, int(round(2 * rows * img.width / img.height)))
        jx = 0.008 * tremor * math.sin(t * 24.0 + bi * 1.7)
        jy = 0.007 * tremor * math.sin(t * 33.0 + bi)
        zoom = z0 + (z1 - z0) * M.ease_in_out_expo(u)
        sp = camera_sprite(img, rows, cols, zoom=zoom,
                           center=(ccx + jx, ccy + jy),
                           bright=1.12 + 0.20 * u + 0.10 * pulse,
                           sat=1.10, contrast=1.16)
        x = 132 - cols // 2
        y = py + int(round(1.8 * tremor * math.sin(t * 19.0 + 0.8)))
        M.feather_sprite(c, y, x, sp, feather=13, bg=C.INK,
                         tint=C.RED_DEEP, tint_amt=tint, alpha=0.96)
        # red light raking down the steel behind the picture
        br = c.braille(Y0, SX, Y1 - Y0, SW)
        ph = (Y1 - Y0) * 4
        for i in range(9):
            xx = int((M.hash01(i, 4.4) * 0.96 + 0.02) * SW) * 2
            br.line(xx, 0, xx, ph, C.mix(C.INK, C.RED, 0.28 + 0.18 * M.hash01(i, 7)),
                    0.55, 2.0)
        for i, (a, b, cc, dd) in enumerate(self._dust[:56]):
            xx = int((a * SW + t * (1.5 + 3.0 * cc)) % SW) * 2
            yy = int((b * ph - t * (8.0 + 20.0 * dd)) % ph)
            br.plot(xx, yy, C.mix(C.RED_DEEP, C.RED_HI, 0.25 + 0.5 * cc),
                    0.25 + 0.35 * dd)
        br.commit()
        # pressure: the iris closes as the terror builds
        rad = M.lerp(132.0, 100.0, bi / 4.0 + 0.14 * u)
        M.iris(c, 134.0, 26.0, rad, soft=36.0, amount=0.44 + 0.06 * bi)
        M.vignette(c, 0.46 + 0.05 * bi)

    # ==================================================================
    # the one conversation window (voices distinguished by colour, no boxes)
    # ==================================================================
    def _window(self, c, ctx, fade: float) -> None:
        if fade <= 0.0:
            return
        t = ctx.t
        S = self.script
        cue = ctx.lyric.index
        span = self._cue_span(cue if cue <= LAST else LAST)
        gold = cue in GOLD_CUES
        if gold:
            lines = self._replies.get(cue, (S.dialog.listening,))
            accent = C.mix(C.GOLD_DIM, C.GOLD, 0.35)
            right = self.T.claude_handle
            prompt = S.dialog.claude_prompt
            body = C.mix(C.TEXT_HI, C.GOLD_HI, 0.22)
            t0 = span[0] + 0.10
            cps = 46.0
            tremor = 0.0
        else:
            lines = self._dahlia.get(cue, ())
            accent = C.mix(C.AMBER_DIM, C.RED_DIM, 0.55)
            right = self.T.dahlia_handle
            prompt = S.dialog.dahlia_prompt
            body = C.mix(C.AMBER_HI, C.WHITE, 0.18)
            t0 = span[0] + 0.06
            cps = max(30.0, sum(len(x) for x in lines) / max(0.6, (span[1] - span[0]) * 0.80))
            tremor = 1.0
        d = M.Dialog(c, *C.DLG_SLOTS[0], title=S.dialog.title, right=right,
                     accent=accent, bg=C.mix(C.INK2, C.PANEL, 0.55), style="rounded")
        d.text(15, prompt, C.mix(accent, C.TEXT_DIM, 0.45))
        d.rule(17, color=C.mix(accent, C.INK, 0.35))
        shown = self._typed_lines(lines, t, t0, cps, tremor)
        row = 19
        for ln in shown:
            if row >= 27:
                break
            d.text(row, ln, body, bold=gold)
            row += 1
        # tremble / stall is drawn into the characters; the caret keeps the
        # rhythm visible (Claude's caret is clean, the human's stutters)
        last = shown[-1] if shown else ""
        if last:
            if gold:
                d.cursor(row - 1, len(last), t, C.GOLD_HI, rate=1.6)
            else:
                if (t * 2.1) % 1.0 < 0.62:
                    d.cursor(row - 1, len(last), t, C.AMBER_HI, rate=3.4)
        hr = 138 + int(26 * _seg(t, T0, T1)) + (8 if not gold else 0)
        temp = 31.2 + 7.4 * _seg(t, T0, T1)
        foot = "%s %3d %s   ·   %s %.1f°C   ·   %s" % (
            S.dialog.voice, hr, "BPM", S.hall.id, temp, S.dialog.mic)
        d.footer(46, foot, color=C.mix(C.INK, C.TEXT_FAINT, 0.95))
        if fade < 1.0:
            c.dim(3, 1, 49, 55, max(0.0, fade))

    def _typed_lines(self, lines, t: float, t0: float, cps: float,
                     tremor: float) -> list[str]:
        """Typewriter with real hesitations; the human's letters tremble."""
        out: list[str] = []
        start = t0
        for li, line in enumerate(lines):
            n = len(line)
            age = t - start
            if age <= 0.0:
                out.append("")
                continue
            # hesitation: the human's line catches twice per sentence
            hes = 0.0
            if tremor > 0:
                stall = 0.16 * M.noise1(age * 5.3 + li * 7.1, seed=3)
                hes = stall * (1.2 if (age % 1.1) < 0.10 else 0.0)
            cnt = int((age - hes) * cps)
            cnt = max(0, min(n, cnt))
            if tremor > 0 and cnt > 0:
                chars = list(line[:cnt])
                for k in range(len(chars)):
                    if chars[k] == " ":
                        continue
                    if k >= cnt - 9 and M.hash01(k, math.floor(t * 14.0), li) < 0.16 * tremor:
                        chars[k] = "▒" if M.hash01(k, 2.0) < 0.5 else "▏"
                out.append("".join(chars))
            else:
                out.append(line[:cnt])
            start += n / cps + 0.05
        return out

    # ==================================================================
    # SHOT D -- silence: the eyes, the lock, the bolts
    # ==================================================================
    def _silence(self, c, ctx) -> None:
        t = ctx.t
        ts = t - SILENCE
        c.fill(Y0, 0, Y1 - Y0, W, " ", C.TEXT, C.BLACK)
        if ts < 0.30:
            # the world holds its breath: one cold rule, nothing else
            c.hline(38, 8, 46, C.mix(C.BLACK, C.CYAN_DEEP, 0.40))
            return
        u = _seg(ts, 0.34, 4.35)
        z = M.lerp(1.28, 2.20, M.ease_in_out_expo(u))
        cx = M.lerp(0.505, 0.492, M.ease_in_out_expo(u))
        cy = M.lerp(0.470, 0.452, M.ease_in_out_expo(u))
        bright = 0.58 + 0.14 * u
        sp = camera_sprite(self._eyes, Y1 - Y0, W, zoom=z, center=(cx, cy),
                           bright=bright, sat=1.06, contrast=1.06)
        c.sprite(Y0, 0, sp)
        # chiaroscuro: the left of the frame falls into the dark machine hall
        self._left_dark(c, 0.93)
        M.vignette(c, 0.52)
        # micro-focus pulls: the iris settles twice, in dead silence
        for at in (86.05, 87.10):
            age = t - at
            if 0.0 <= age < 0.30:
                k = 1.0 - age / 0.30
                c.fx.flash = max(c.fx.flash, 0.03 * k)
                c.fx.flash_color = C.TEXT_HI
        self._lock(c, ctx)
        self._bolts(c, ctx)
        # the last red breath before the blast door
        if ts > 5.2:
            c.dim(Y0, 0, Y1 - Y0, W, max(0.7, 1.0 - (ts - 5.2) * 0.5))

    def _left_dark(self, c, amount: float) -> None:
        """Fade the left of the frame into the machine hall (no border)."""
        cut = 90
        for x in range(cut):
            f = 1.0 - amount * (1.0 - M.smooth01(2.0, 66.0, x))
            if f >= 0.999:
                continue
            cache = {}
            for y in range(Y0, Y1):
                row_f = c.fg[y]
                row_b = c.bg[y]
                v = row_f[x]
                nv = cache.get(v)
                if nv is None:
                    nv = cache[v] = C.scale(v, f)
                row_f[x] = nv
                v = row_b[x]
                nv = cache.get(v)
                if nv is None:
                    nv = cache[v] = C.scale(v, f)
                row_b[x] = nv

    def _lock(self, c, ctx) -> None:
        """Far in the dark: the door lock turns green -> red, in silence."""
        t = ctx.t
        S = self.script.final
        red = t >= LOCK_AT
        col = C.RED if red else C.GREEN
        hot = C.RED_HI if red else C.GREEN
        if red:
            age = t - LOCK_AT
            if age < 0.20:
                col = C.mix(C.GREEN, C.RED, age / 0.20)
        x, y = 7, 22
        # the door face, deep in the dark
        c.vline(37, 18, 52, C.mix(C.BLACK, C.BORDER, 0.50))
        c.vline(38, 18, 52, C.mix(C.BLACK, C.BORDER, 0.32))
        c.hline(18, 4, 37, C.mix(C.BLACK, C.BORDER, 0.42))
        c.frame(y, x, 12, 28, C.mix(C.BLACK, C.BORDER_HI, 0.55), None, "single")
        c.text(y + 1, x + 2, S.access, C.mix(C.BLACK, C.TEXT_FAINT, 0.95), bold=True)
        c.text(y + 1, x + 20, S.bolts, C.mix(C.BLACK, C.TEXT_FAINT, 0.70))
        # the indicator lamp: a hard square of green that goes red
        for dy in range(3):
            for dx in range(3):
                c.put(y + 4 + dy, x + 3 + dx, "█", col)
        for dy in range(-1, 4):
            for dx in range(-1, 4):
                if 0 <= dy <= 2 and 0 <= dx <= 2:
                    continue
                c.blend_bg(y + 4 + dy, x + 3 + dx, col, 0.30)
        c.put(y + 9, x + 3, "●", hot)
        lab = S.locked if red else S.open
        c.text(y + 9, x + 6, lab, hot, bold=True)
        # a faint red key light spilling along the steel once it locks
        if red:
            k = min(1.0, (t - LOCK_AT))
            for i in range(40):
                h = M.hash01(i, 1.0)
                yy = y + 2 + int(h * 26)
                xx = x + 30 + int(12 * M.hash01(i, 2.0) * k)
                c.put(yy, xx, "·", C.mix(C.BLACK, C.RED_DEEP, 0.7))
        # a thin cold rail under the door
        c.hline(50, 0, 54, C.mix(C.BLACK, C.CYAN_DEEP, 0.45))

    def _bolts(self, c, ctx) -> None:
        """Four heavy bolts slide home across the door, one after another."""
        t = ctx.t
        if t < BOLT_AT[0]:
            return
        for i, at in enumerate(BOLT_AT):
            age = t - at
            if age < 0.0:
                continue
            u = M.ease_out_expo(min(1.0, age / 0.26))
            y = 39 + i * 3
            x0 = int(M.lerp(-30, 5, u))
            live = u < 0.999
            col = C.mix(C.BLACK, C.BORDER_HI, 0.55 if live else 0.85)
            edge = C.mix(C.BORDER_HI, C.WHITE, 0.30 if live else 0.06)
            for xx in range(max(0, x0), min(37, x0 + 31)):
                c.put(y, xx, "▄", col)
                c.put(y + 1, xx, "█", C.scale(col, 0.82))
                c.put(y + 2, xx, "▀", C.scale(col, 0.55))
            c.put(y, min(36, x0 + 30), "▐", edge)
            c.put(y + 1, min(36, x0 + 30), "▌", edge)
            if live:
                c.fx.shake_x += 0.5 * math.sin(age * 90.0)
            else:
                c.put(y + 1, x0 + 6, "▪", C.mix(C.BLACK, C.RED_DEEP, 0.8))
