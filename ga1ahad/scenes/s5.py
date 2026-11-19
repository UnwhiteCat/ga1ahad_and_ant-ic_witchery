
"""Scene 5 -- the identity seam (175.320 - 206.850, cues 65-71).

Composition (see docs/SCENE_AUTHORING.md):
    left 9:16 window (3,1,49,55) = C.DLG_SLOTS[0]: ONE portrait conversation
    surface with two breathing zones -- an upper merge session (human prompt +
    sparse replies) and a lower chain-of-thought -- and a lot of empty air.
    right stage (x >= 64): the huge two-faced fusion portrait at the visual
    centre, a braille surgical seam running through it, dark-violet scabs along
    the seam, the accelerating telegram storm, the silver approval wings, and
    finally the devotion globe that cracks open into Scene 6.

Beats (all pure functions of t):
    A 175.320-185.250  tender-sick healing: the two halves of the portrait
                      drift together, metal stitches cinch one by one, purple
                      scabs spread along the seam, the prompt hostname slips
                      between the two voices.
    B 185.250-193.240  the storm: an unannounced detonation with an accelerating
                      shake frequency, eighteen dispatch cards smashing onto the
                      stage from every direction until the fused face suffocates.
    C 193.240-198.080  the brake: one white frame, then dead silence -- the
                      eighteen cards spring into two cold symmetric approval
                      wings, stamps drop, four verdicts, the face stares.
    D 198.080-206.850  the seal sweeps the frame, the wings go out like lights,
                      the matrix becomes a rotating braille + earth globe, eight
                      gold nodes light up and the globe cracks down the middle.

Claude's half of the fused portrait is never restyled: the illustration keeps its
cel-shaded line work; only the live-action half is graded towards violet.
"""

from __future__ import annotations

import math

import numpy as np

from .. import config as C
from .. import motion as M
from ..assets import camera_sprite, keyframe
from ..canvas import wrap
from .base import Scene

# ---- VTT cue boundaries (layout constants; ga1ahad.vtt is the SSOT) --------
T_WOUND = 175.320          # cue 0  finally, the wound
T_WOUND2 = 179.160         # cue 1  our wounds closed
T_TURNED = 181.000         # cue 2  turned into
T_SCABS = 182.990          # cue 3  purple scabs
T_KISS = 185.250           # cue 4  the detonation (acceptance clip starts)
T_CALM = 193.240           # the brake, inside cue 4
T_UNDO = 198.080           # cue 5  no undo
T_BACK = 202.490           # cue 6  can't go back
T_END = 206.850

# ---- palette aliases -------------------------------------------------------
INK = C.INK
INK2 = C.INK2
TXT = C.TEXT
TXTH = C.TEXT_HI
DIM = C.TEXT_DIM
FAINT = C.TEXT_FAINT
WHITE = C.WHITE
PURPLE = C.PURPLE
PURPLEH = C.PURPLE_HI
PURPLED = C.PURPLE_DIM
PURPLEX = C.PURPLE_DEEP
AMBER = C.AMBER
AMBERH = C.AMBER_HI
TERRA = C.TERRA
GOLD = C.GOLD
GOLDH = C.GOLD_HI
GOLDD = C.GOLD_DIM
GOLDDEEP = C.GOLD_DEEP
RED = C.RED
REDH = C.RED_HI
REDD = C.RED_DIM
REDX = C.RED_DEEP
GREEN = C.GREEN
CYAN = C.CYAN
CYANH = C.CYAN_HI
CYAND = C.CYAN_DIM
CYANX = C.CYAN_DEEP
BORDER = C.BORDER
BORDERH = C.BORDER_HI

SILVER = C.mix(C.mix(C.CYAN_HI, WHITE, 0.55), C.PURPLE_HI, 0.10)

_TONES = {
    "text": TXT, "dim": DIM, "faint": FAINT, "white": WHITE, "text-hi": TXTH,
    "purple": PURPLE, "purple-hi": PURPLEH, "purple-red": C.mix(PURPLE, RED, 0.5),
    "amber": AMBER, "amber-hi": AMBERH, "amber-soft": C.mix(AMBER, WHITE, 0.35),
    "red": RED, "red-hi": REDH, "red-soft": C.mix(RED, WHITE, 0.2),
    "green": GREEN, "green-soft": C.mix(GREEN, WHITE, 0.3),
    "cyan": CYAN, "cyan-hi": CYANH, "cyan-soft": C.mix(CYAN, WHITE, 0.2),
    "cyan-strong": C.mix(CYAN, WHITE, 0.25), "cyan-glow": C.mix(CYAN, WHITE, 0.3),
    "cyan-bright": C.mix(CYANH, WHITE, 0.5), "gold-hi": GOLDH,
}

# ---- geometry --------------------------------------------------------------
Y0, Y1 = C.CONTENT_Y0, C.CONTENT_Y1          # 2 .. 53
SX = C.STAGE_X                               # 64
STAGE_W = C.W - SX                           # 136

# the left portrait window (one conversation surface for the chapter)
WY, WX, WH, WW = C.DLG_SLOTS[0]              # (3, 1, 49, 55)
BX, BW = WX + 3, WW - 6                      # body column 4, width 49
BTOP, BBOT = WY + 1, WY + WH - 2             # body rows 4 .. 50

# the huge fusion portrait (A/B)
PY, PX, PH, PW = 7, 69, 38, 126
SEAM = PX + PW // 2                          # 132 -- absolute visual centre
HALF = PW // 2                               # 63
SEP_MAX = 7                                  # cell gap between the halves

# the calm close-up aperture (C/D)
FY, FX, FH, FW = 6, 92, 40, 80

# the approval wings (C/D): nine stamped dossiers per side
WING_Y0 = 3
WING_H = 5
WING_W = 28
LEFT_X = SX
RIGHT_X = C.W - WING_W
SEAL_BAND = 5

# the devotion globe (D)
GR_Y0, GR_H = 3, 48
GR_DOTS_W, GR_DOTS_H = C.W * 2, GR_H * 4
GR_CX, GR_CY = C.W * 0.5, (GR_Y0 + GR_H * 0.5)
EARTH_ROWS = 38
EARTH_COLS = 99
EARTH_X = int(round(GR_CX - EARTH_COLS / 2))
EARTH_Y = int(round(GR_CY - EARTH_ROWS / 2))

# storm card arrival -- accelerating rhythm inside "Kiss me ... violently"
N_CARDS = 18
STORM_SPAN = 7.35
STORM_DELAY = 0.12
MORPH_SPAN = 0.25
STAMP_DELAY = 0.42
STAMP_GAP = 0.062

# stitch schedule (13 staples over the healing act)
STITCH_N = 13


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    s = str(text)
    if len(s) <= width:
        return s
    if width == 1:
        return s[:1]
    return s[: width - 1] + "…"


def _wrapt(text: str, width: int) -> list[str]:
    rows = wrap(str(text), width)
    return rows if rows else [""]


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def _mixp(a, b, u):
    """Packed-RGB linear blend for numpy arrays (u broadcasts)."""
    ar = (a >> 16) & 255
    ag = (a >> 8) & 255
    ab = a & 255
    br = (b >> 16) & 255
    bg_ = (b >> 8) & 255
    bb = b & 255
    r = (ar + (br - ar) * u).astype(np.int64)
    g = (ag + (bg_ - ag) * u).astype(np.int64)
    bl = (ab + (bb - ab) * u).astype(np.int64)
    return (r << 16) | (g << 8) | bl


def _ss(a: float, b: float, x: float) -> float:
    return M.smooth01(a, b, x)


def _alpha_map(h: int, w: int, top: float, bot: float,
               left: float, right: float) -> np.ndarray:
    """Feathered alpha profile (h, w): soft cinematic edges, no hard rectangle."""
    ys = np.arange(h, dtype=np.float64) + 0.5
    xs = np.arange(w, dtype=np.float64) + 0.5
    ay = np.minimum(_ssv(0.0, top, ys), _ssv(0.0, bot, h - ys))
    ax = np.minimum(_ssv(0.0, left, xs), _ssv(0.0, right, w - xs))
    return np.clip(ay[:, None] * ax[None, :], 0.0, 1.0)


def _vblur(arr: np.ndarray, w0: float, w1: float, w2: float) -> np.ndarray:
    """Vertical 3-tap blur on packed colours (kills one-cell row beating)."""
    up = np.roll(arr, 1, axis=0)
    dn = np.roll(arr, -1, axis=0)
    tot = w0 + w1 + w2
    return _mixp(_mixp(up, arr, w1 / max(1e-6, w1 + w0)),
                 dn, (w2 * w2) / max(1e-6, (w1 + w0) * tot + w2))         if False else _tri(arr, up, dn, w0, w1, w2)


def _tri(arr: np.ndarray, up: np.ndarray, dn: np.ndarray,
         w0: float, w1: float, w2: float) -> np.ndarray:
    tot = max(1e-6, w0 + w1 + w2)
    r = (((arr >> 16) & 255) * w1 + ((up >> 16) & 255) * w0
         + ((dn >> 16) & 255) * w2) / tot
    g = (((arr >> 8) & 255) * w1 + ((up >> 8) & 255) * w0
         + ((dn >> 8) & 255) * w2) / tot
    b = ((arr & 255) * w1 + (up & 255) * w0 + (dn & 255) * w2) / tot
    return ((r.astype(np.int64)) << 16) | ((g.astype(np.int64)) << 8) | b.astype(np.int64)


def _ssv(a: float, b: float, x: np.ndarray) -> np.ndarray:
    if b <= 1e-6:
        return (x >= a).astype(np.float64)
    u = np.clip((x - a) / (b - a), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


class Scene5(Scene):
    NAME = "s5"

    # ------------------------------------------------------------------
    # construction: everything static is baked here, draw() stays cheap
    # ------------------------------------------------------------------
    def __init__(self, assets, audio, timeline, content) -> None:
        super().__init__(assets, audio, timeline, content)
        S = self.script

        # ---- screenplay -------------------------------------------------
        self.s_title = S.session.title
        self.s_label = S.session.label
        self.s_right = S.session.right
        self.s_inbound = S.session.inbound
        self.s_staredown = S.session.staredown
        self.cot_title = S.cot.title_prefix
        self.cot_soothe = [(ln.time, ln.text, _TONES[ln.tone]) for ln in S.cot.soothe]
        self.cot_calm = [(ln.text, _TONES[ln.tone]) for ln in S.cot.calm]
        self.paranoid = list(S.cot.paranoid)
        self.main_soothe = [(ln.time, ln.text, _TONES[ln.tone]) for ln in S.main.soothe]
        self.main_calm = [(ln.text, _TONES[ln.tone]) for ln in S.main.calm]
        self.main_panic = list(S.main.panic)
        self.main = S.main
        self.session = S.session
        self.ident = S.identity
        self.report = S.report
        self.lock = S.lock
        self.dev = S.devotion
        self.pop = S.popup
        self.pop_title = [p.title.upper() for p in S.popups]
        self.pop_q = [p.question for p in S.popups]
        self.pop_detail = [p.detail for p in S.popups]
        self.pop_verdict = [p.verdict for p in S.popups]
        self.nodes = [(n.lat, n.lon, n.label) for n in S.devotion.nodes]

        # ---- portraits --------------------------------------------------
        self._fused_img = keyframe("identity-fused")
        self._earth_img = keyframe("earth")
        # feathered alpha masks for the two big portrait shots
        self._alpha_half_l = _alpha_map(PH, HALF, 5.0, 8.0, 11.0, 1.0)
        self._alpha_half_r = _alpha_map(PH, HALF, 5.0, 8.0, 1.0, 11.0)
        self._alpha_face = _alpha_map(FH, FW, 5.0, 7.0, 8.0, 8.0)
        self._alpha_earth = self._earth_mask()

        # ---- purple scab crust (grown along the seam) -------------------
        self._scab_cells = self._build_scabs()
        self._speck_cells = self._build_specks()

        # ---- stitch schedule -------------------------------------------
        self._stitch_rows = [int(2 + i * (PH - 5) / (STITCH_N - 1)) for i in range(STITCH_N)]
        self._stitch_at = []
        for i in range(STITCH_N):
            if i < 7:
                self._stitch_at.append(T_WOUND + 0.62 + i * 0.86)
            else:
                self._stitch_at.append(T_WOUND + 0.62 + 6 * 0.86 + (i - 6) * 0.58)

        # ---- storm cards ------------------------------------------------
        self._cards = self._build_cards()

        # ---- devotion globe ---------------------------------------------
        self._globe_segs = self._build_globe()
        self._node_vecs = [self._latlon(lat, lon) for lat, lon, _ in self.nodes]
        self._stars = self._build_stars()

        # ---- backdrop rows cache (filled per frame by _backdrop) --------
        self._frame_bg = [INK] * C.H

        # ---- glyph warm-up (first rasterisation is expensive) -----------
        gt = self.assets.glyphs if hasattr(self.assets, "glyphs") else None
        if gt is not None:
            for ch in ("░▒▓█▀▄▐▌▏▎│─╌┄┈║╔╗╚╝═●○◆◇◈▸▹⟨⟩⟷↔✓✕✗∅⬢△▁▂▃▄▅▆▇"
                       "·•…⋮⋯⌁∷⟡✦✧⚡⚠↑↓→←"):
                gt.char_id(ch)
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/:#@%&()[]:.+·>":
                gt.char_id(ch, bold=True)

    # ==================================================================
    # static builders
    # ==================================================================
    @staticmethod
    def _earth_mask() -> np.ndarray:
        """Circular alpha so the night-earth photograph dissolves into space."""
        yy = np.arange(EARTH_ROWS, dtype=np.float64)[:, None] + 0.5
        xx = np.arange(EARTH_COLS, dtype=np.float64)[None, :] + 0.5
        ry = EARTH_ROWS * 0.465
        rx = EARTH_ROWS * 0.935
        r = np.sqrt(((xx - EARTH_COLS * 0.5) / rx) ** 2 +
                    ((yy - ry) / (ry * 0.99)) ** 2)
        a = np.clip((1.00 - r) / 0.035, 0.0, 1.0)
        return a * a * (3.0 - 2.0 * a)

    def _build_scabs(self):
        """Precompute (row, dx, level, threshold): a ragged crust hugging the seam."""
        out = []
        for row in range(PH):
            for dx in range(-12, 13):
                if dx == 0:
                    continue
                dist = abs(dx)
                n = M.fbm1(row * 0.46 + dx * 0.62 + 4.0, seed=7)
                n2 = M.fbm1(row * 0.17 - dx * 0.95 + 9.0, seed=13)
                edge = 2.0 + 8.5 * (0.25 + 0.75 * n2)
                if dist > edge:
                    continue
                level = 1 if n < 0.50 else 2 if n < 0.84 else 3
                thr = 0.02 + (dist / 11.5) * 0.88 + (1.0 - n) * 0.08
                if dx > 0:                       # Claude's side crusts later
                    thr += 0.14
                out.append((row, dx, level, min(1.2, thr)))
        return out

    def _build_specks(self):
        out = []
        for i in range(30):
            row = int(M.hash01(i, 1) * PH)
            dx = int((M.hash01(i, 2) - 0.5) * 15)
            thr = M.hash01(i, 3) * 0.8 + abs(dx) / 20.0
            out.append((row, dx, thr, M.hash01(i, 4)))
        return out

    def _build_cards(self):
        """18 telegram cards: a ring closing in on the face, then the centre."""
        cards = []
        cx0 = SEAM - 1
        cy0 = PY + PH // 2
        for i in range(N_CARDS):
            u = i / (N_CARDS - 1)
            at = T_KISS + STORM_DELAY + STORM_SPAN * (u ** 1.55)
            w = 36 + int(M.hash01(i, 3) * 14)   # 36 .. 49
            h = 6 + int(M.hash01(i, 7) * 2)     # 6 .. 7
            ang = i * 2.39996 + 0.75
            rad = 1.0 if i < 12 else max(0.0, 1.0 - (i - 11) * 0.19)
            px_ = cx0 + math.cos(ang) * 60.0 * rad
            py_ = cy0 + math.sin(ang) * 16.0 * rad
            tx = int(_clamp(px_ - w // 2, SX + 2, C.W - w - 2))
            ty = int(_clamp(py_ - h // 2, Y0 + 1, Y1 - h - 1))
            if i < 12:
                # slide outwards until the eyes of the face are still visible
                for _ in range(14):
                    if (tx + w < SEAM - 24 or tx > SEAM + 24
                            or ty + h < PY + 9 or ty > PY + 30):
                        break
                    tx = int(_clamp(tx + (8 if math.cos(ang) >= 0 else -8),
                                    SX + 2, C.W - w - 2))
                    ty = int(_clamp(ty + (3 if math.sin(ang) >= 0 else -3),
                                    Y0 + 1, Y1 - h - 1))
            side = i % 4
            if side == 0:
                ox, oy = -w - 10, ty + int((M.hash01(i, 23) - 0.5) * 30)
            elif side == 1:
                ox, oy = C.W + 10, ty + int((M.hash01(i, 29) - 0.5) * 30)
            elif side == 2:
                ox, oy = tx + int((M.hash01(i, 31) - 0.5) * 60), -h - 6
            else:
                ox, oy = tx + int((M.hash01(i, 37) - 0.5) * 60), C.H + 5
            col = i // 9
            slot_y = WING_Y0 + (i % 9) * WING_H
            slot_x = LEFT_X if col == 0 else RIGHT_X
            cards.append(dict(i=i, at=at, w=w, h=h, tx=tx, ty=ty, ox=ox, oy=oy,
                              sx=slot_x, sy=slot_y))
        return cards

    def _build_globe(self):
        """Lightweight lat/long wireframe (fewer segments than sphere_segments)."""
        out = []
        for k in range(1, 6):
            th = math.pi * k / 6.0
            r = math.sin(th)
            yy = math.cos(th)
            n = 36
            pts = np.array([[math.cos(a) * r, yy, math.sin(a) * r]
                            for a in [2 * math.pi * j / n for j in range(n)]])
            out.append(np.stack([pts, np.roll(pts, -1, axis=0)], axis=1))
        for j in range(10):
            ph = 2.0 * math.pi * j / 10.0
            n = 18
            pts = np.array([[math.sin(t_) * math.cos(ph), math.cos(t_),
                             math.sin(t_) * math.sin(ph)]
                            for t_ in [math.pi * i / n for i in range(n + 1)]])
            out.append(np.stack([pts[:-1], pts[1:]], axis=1))
        return np.concatenate(out, axis=0)

    @staticmethod
    def _latlon(lat, lon):
        cl = math.cos(lat)
        return np.array([cl * math.sin(lon), math.sin(lat), cl * math.cos(lon)])

    def _build_stars(self):
        out = []
        for i in range(230):
            y = int(M.hash01(i, 41) * C.CONTENT_H) + Y0
            x = int(M.hash01(i, 43) * C.W)
            b = M.hash01(i, 47)
            out.append((y, x, b))
        return out

    # ==================================================================
    # frame entry
    # ==================================================================
    def draw(self, c, ctx) -> None:
        t = ctx.t
        if t < T_KISS:
            self._act_a(c, ctx, t)
        elif t < T_CALM:
            self._act_b(c, ctx, t)
        elif t < T_UNDO:
            self._act_c(c, ctx, t)
        else:
            self._act_d(c, ctx, t)

    # ------------------------------------------------------------------
    # shared backdrop
    # ------------------------------------------------------------------
    def _backdrop(self, c, t, hot: float = 0.0, cold: float = 0.0) -> None:
        rows = self._frame_bg
        for y in range(Y0, Y1):
            u = (y - Y0) / (C.CONTENT_H - 1)
            base = C.mix(C.mix(INK, PURPLEX, 0.34), INK, u * 1.05)
            if cold:
                base = C.mix(base, CYANX, cold * 0.55 * (1.0 - u * 0.4))
            if hot:
                fl = 0.55 + 0.45 * math.sin(y * 0.45 + t * 2.1)
                base = C.mix(base, C.mix(REDX, PURPLEX, 0.5), hot * fl)
            rows[y] = base
            c.fill(y, 0, 1, C.W, " ", TXT, base)

    def _seam_glow(self, c, t, amount: float, color: int) -> None:
        """Soft vertical light bleeding out of the seam."""
        if amount <= 0.01:
            return
        for y in range(Y0, Y1):
            base = self._frame_bg[y]
            for dx in range(-16, 17):
                x = SEAM + dx
                if x < SX - 2 or x >= C.W:
                    continue
                a = amount * (1.0 - abs(dx) / 16.0) ** 2 * (0.5 + 0.5 * math.sin(y * 0.3 + t))
                c.bg[y][x] = C.mix(c.bg[y][x], color, a * 0.5)

    # ==================================================================
    # A -- tender-sick healing (175.320 - 185.250)
    # ==================================================================
    def _act_a(self, c, ctx, t) -> None:
        sep = self._separation(t)
        self._backdrop(c, t, cold=0.10)
        self._seam_glow(c, t, 0.55 - 0.25 * _ss(T_WOUND, T_KISS, t), PURPLEX)
        bass = ctx.audio.bass(t)
        zoom = 1.005 + 0.055 * _ss(T_WOUND, T_KISS, t) + 0.012 * math.sin(t * 1.05) \
            + 0.020 * bass
        self._face_pair(c, t, sep, zoom=zoom, bright=1.04, alpha=1.0, cold=0.0)
        if sep > 0.30:
            self._gash(c, t, sep)
        else:
            self._seam_line(c, t, 1.0)
        self._stitches(c, t, sep, alpha=1.0)
        self._scabs(c, t, self._scab_cover(t), cold=0.0)
        self._caption_a(c, ctx, t, sep)
        self._window(c, ctx, t)
        M.grain(c, t, seed=17, count=64, amount=0.055)
        # a very soft violet bloom keeps the velvet breathing
        c.fx.sat = 1.02

    def _separation(self, t) -> float:
        close = _ss(T_WOUND, 184.40, t)
        ease = close * close * (3.0 - 2.0 * close)
        return SEP_MAX * (1.0 - ease) ** 1.35

    def _scab_cover(self, t) -> float:
        if t < T_SCABS - 0.4:
            return _ss(T_WOUND, T_SCABS, t) * 0.16
        if t < T_KISS:
            return 0.16 + _ss(T_SCABS, T_KISS, t) * 0.46
        if t < T_CALM:
            return 0.62 + _ss(T_KISS, T_CALM, t) * 0.30
        return 0.88

    # ------------------------------------------------------------------
    def _face_arrays(self, zoom: float, center, bright: float, cold: float,
                     left_grade: float = 0.17):
        sp = camera_sprite(self._fused_img, PH, PW, zoom=zoom, center=center,
                           bright=bright, sat=1.05, contrast=1.05)
        fg = np.array(sp.fg, dtype=np.int64)
        bg = np.array(sp.bg, dtype=np.int64)
        ch = np.array(sp.ch, dtype=np.int32)
        if cold > 0.0:
            grade = C.mix(SILVER, CYANH, 0.35)
            cg = C.mix(grade, C.mix(CYANX, INK, 0.35), 0.45)
            fg = _mixp(fg, np.int64(C.scale(cg, 1.18)), cold * 0.62)
            bg = _mixp(bg, np.int64(C.scale(cg, 0.55)), cold * 0.55)
        if left_grade > 0.0:
            # the live-action half cools toward violet; Claude's half stays cel
            violet = C.mix(C.mix(PURPLEX, REDX, 0.35), C.scale(PURPLE, 0.9), 0.5)
            fg[:, :HALF] = _mixp(fg[:, :HALF], np.int64(violet), left_grade)
            bg[:, :HALF] = _mixp(bg[:, :HALF], np.int64(C.scale(violet, 0.55)),
                                 left_grade)
        mid = _mixp(fg, bg, 0.5)
        fg = _mixp(fg, mid, 0.55)
        bg = _mixp(bg, mid, 0.55)
        return fg, bg, ch

    def _face_pair(self, c, t, sep, zoom: float, bright: float, alpha: float,
                   cold: float) -> None:
        if alpha <= 0.01:
            return
        fg, bg, ch = self._face_arrays(zoom, (0.5, 0.47), bright, cold)
        lift = 1 if sep > 4.0 else 0
        self._blit(c, fg, bg, ch, PY + lift, int(round(PX - sep)),
                   0, HALF, self._alpha_half_l, alpha)
        self._blit(c, fg, bg, ch, PY - lift, int(round(PX + HALF + sep)),
                   HALF, PW, self._alpha_half_r, alpha)

    def _face_close(self, c, t, zoom: float, bright: float, alpha: float,
                    cold: float) -> None:
        if alpha <= 0.01:
            return
        fg, bg, ch = self._face_arrays(zoom, (0.5, 0.44), bright, cold,
                                       left_grade=0.10 + cold * 0.10)
        # the calm shot is a tighter crop, rendered at the aperture size
        sp = camera_sprite(self._fused_img, FH, FW, zoom=zoom, center=(0.5, 0.44),
                           bright=bright, sat=1.05, contrast=1.05)
        fg = np.array(sp.fg, dtype=np.int64)
        bg = np.array(sp.bg, dtype=np.int64)
        ch = np.array(sp.ch, dtype=np.int32)
        if cold > 0.0:
            grade = C.mix(SILVER, CYANH, 0.30)
            fg = _mixp(fg, np.int64(C.scale(grade, 1.10)), cold * 0.55)
            bg = _mixp(bg, np.int64(C.scale(grade, 0.45)), cold * 0.5)
        violet = C.mix(C.mix(PURPLEX, REDX, 0.35), C.scale(PURPLE, 0.9), 0.5)
        fg[:, :FW // 2] = _mixp(fg[:, :FW // 2], np.int64(violet), 0.10)
        bg[:, :FW // 2] = _mixp(bg[:, :FW // 2], np.int64(C.scale(violet, 0.55)),
                                0.10)
        mid = _mixp(fg, bg, 0.5)
        fg = mid
        bg = mid
        self._blit(c, fg, bg, ch, FY, FX, 0, FW, self._alpha_face, alpha)

    def _blit(self, c, fg, bg, ch, y: int, x: int, sx0: int, sx1: int,
              alpha: np.ndarray, amul: float) -> None:
        """Blit sprite columns [sx0, sx1) with a feathered alpha profile."""
        h = fg.shape[0]
        n = sx1 - sx0
        if n <= 0:
            return
        dst0 = max(0, x)
        dst1 = min(C.W, x + n)
        if dst1 <= dst0:
            return
        off = dst0 - x
        s0, s1 = sx0 + off, sx0 + off + (dst1 - dst0)
        ys = max(y, Y0)
        ye = min(y + h, Y1)
        rows = self._frame_bg
        for Y in range(ys, ye):
            sy = Y - y
            a = alpha[sy, off:off + (dst1 - dst0)] * amul
            if a.max() <= 0.012:
                continue
            under = np.int64(rows[Y])
            src_f = fg[sy, s0:s1]
            src_b = bg[sy, s0:s1]
            c.fg[Y][dst0:dst1] = _mixp(under, src_f, a).tolist()
            c.bg[Y][dst0:dst1] = _mixp(under, src_b, a).tolist()
            c.ch[Y][dst0:dst1] = ch[sy, s0:s1].tolist()

    # ------------------------------------------------------------------
    def _gash(self, c, t, sep: float) -> None:
        """The open wound between the two halves: a dark gash, wet rims, threads."""
        xl = int(round(SEAM - sep))
        xr = int(round(SEAM + sep))
        for row in range(PH):
            Y = PY + row
            jag_l = int(round(1.3 * math.sin(row * 0.63 + t * 2.4)))
            jag_r = int(round(1.1 * math.cos(row * 0.51 - t * 2.1)))
            g0 = xl + jag_l
            g1 = xr + jag_r
            width = max(1, g1 - g0)
            core = C.mix(C.mix(PURPLEX, INK, 0.66), REDX,
                         0.14 + 0.10 * math.sin(row * 0.8 + t * 3.1))
            c.fill(Y, g0, 1, width, " ", TXT, core)
            wet = C.mix(PURPLEH, REDH, 0.30 + 0.30 * math.sin(row * 1.7 - t * 5.0))
            c.put(Y, g0 - 1, "\u2590" if row % 2 else "\u258c", C.mix(wet, WHITE, 0.18), core)
            c.put(Y, g1, "\u258c" if row % 2 else "\u2590", C.mix(wet, WHITE, 0.12), core)
            if row % 4 == 0:
                c.put(Y, g0 + 1, "\u2596", C.mix(wet, INK, 0.45), core)
                c.put(Y, g1 - 1, "\u2597", C.mix(wet, INK, 0.38), core)
        # surgical threads sagging across the wound
        br = c.braille(PY, PX, PH, PW)
        sx_dot = HALF * 2
        for i in range(7):
            row = int(2 + i * (PH - 5) / 6)
            ydot = row * 4 + 2
            reach = int(round(sep * 2)) + 5
            sag = 1.5 + 2.6 * sep / SEP_MAX
            pts = []
            for k in range(9):
                u = k / 8.0
                pts.append((sx_dot - reach + 2 * reach * u,
                            ydot + sag * math.sin(math.pi * u)))
            br.polyline(pts, C.mix(PURPLEH, WHITE, 0.30), 0.70)
        br.commit()

    def _seam_line(self, c, t, alpha: float) -> None:
        """The closed seam: a living thread of violet light."""
        if alpha <= 0.01:
            return
        for row in range(PH):
            Y = PY + row
            wob = int(round(0.9 * math.sin(row * 0.55 + t * 0.9)))
            x = SEAM + wob
            beat = 0.5 + 0.5 * math.sin(t * 2.4 + row * 0.12)
            col = C.mix(C.mix(PURPLEH, PURPLE, 0.45), WHITE, 0.18 + 0.30 * beat)
            if row % 5 == 0:
                c.put(Y, x, "│", col, None)
            else:
                c.put(Y, x, "▏", C.mix(col, INK, 0.25), None)

    def _stitches(self, c, t, sep: float, alpha: float = 1.0) -> None:
        br = c.braille(PY, PX, PH, PW)
        sx_dot = HALF * 2
        metal = C.mix(C.mix(BORDERH, WHITE, 0.55), SILVER, 0.35)
        for i, row in enumerate(self._stitch_rows):
            at = self._stitch_at[i]
            age = t - at
            ydot = row * 4 + 2
            if age < 0.0:
                # faint guide marks for the next staples
                if age > -0.55 and i < STITCH_N:
                    for s in (-1, 1):
                        br.plot(sx_dot + s * 7, ydot, C.mix(INK, PURPLE, 0.35), 0.5)
                continue
            tight = M.smooth01(0.0, 0.30, age)
            hot = M.hit(age, 0.22)
            reach = (10.2 - 4.4 * tight) * (0.70 + 0.30 * sep / SEP_MAX)
            wob = 0.9 * math.exp(-age / 0.4) * math.sin(age * 34.0)
            col = C.mix(metal, WHITE, 0.55 * hot)
            col = C.mix(col, PURPLEH, 0.28)
            yb = int(round(ydot + wob))
            # two punctures and the double thread pulled through the skin
            for s in (-1, 1):
                px = int(round(sx_dot + s * reach))
                br.line(px, yb - 2, px, yb + 3, C.mix(col, WHITE, 0.25), 1.0)
                br.plot(px - 1, yb + 6, C.mix(INK, REDH, 0.65), 0.8)
                br.plot(px + 1, yb + 6, C.mix(INK, REDH, 0.45), 0.6)
            br.line(int(round(sx_dot - reach)), yb + 2, sx_dot, yb - 2,
                    C.scale(col, 0.9), 0.9)
            br.line(int(round(sx_dot + reach)), yb + 2, sx_dot, yb - 2,
                    C.scale(col, 0.9), 0.9)
            br.plot(sx_dot, yb - 2, C.mix(col, WHITE, 0.5), 1.0)
        br.commit()

    def _scabs(self, c, t, cover: float, cold: float) -> None:
        if cover <= 0.02:
            return
        for (row, dx, level, thr) in self._scab_cells:
            if thr > cover:
                continue
            Y = PY + row
            X = SEAM + dx
            if Y < Y0 or Y >= Y1 or X < 0 or X >= C.W:
                continue
            ch = ("\u2591", "\u2592", "\u2593")[level - 1]
            fg = C.mix(C.mix(PURPLEX, PURPLE, 0.55), PURPLED, 0.20 + level * 0.12)
            if cold > 0.0:
                fg = C.mix(fg, SILVER, cold * 0.40)
            fgbg = C.mix(INK, PURPLEX, 0.62 + level * 0.08)
            c.put(Y, X, ch, fg, fgbg)
        for (row, dx, thr, tone) in self._speck_cells:
            if thr > cover * 0.90:
                continue
            Y = PY + row
            X = SEAM + dx
            if Y < Y0 or Y >= Y1 or X < 0 or X >= C.W:
                continue
            wet = C.mix(REDH, C.MAGENTA, tone) if cold <= 0 else C.mix(CYANH, SILVER, tone)
            c.put(Y, X, "\u00b7" if tone < 0.6 else "\u2022", wet, None)

    def _caption_a(self, c, ctx, t, sep: float) -> None:
        label = self.ident.label_merged.upper()
        col = C.mix(PURPLEH, WHITE, 0.10 + 0.10 * math.sin(t * 0.8))
        c.text_center(46, f" {label} ", col, None, x0=SX, x1=C.W)
        M.hairline(c, 47, SX + 24, C.W - 24, C.mix(INK, PURPLE, 0.55))
        p = self._fusion(t)
        bnd = (1.0 - p) * 100.0
        left = self.ident.boundary_prefix + f"{bnd:5.2f}%"
        c.text(48, SX + 24, left, DIM, None)
        right = f"SEAM {(1.0 - p) * 100.0:5.1f}%   closure {min(99.8, p * 118.0):5.1f}%"
        c.text(48, C.W - 24 - len(right), right, C.mix(DIM, INK, 0.25), None)
        # a whisper of audio breath under the frame
        br = c.braille(50, SX + 18, 3, STAGE_W - 36)
        spec = ctx.audio.spectrum(t)
        n = STAGE_W - 36
        for i in range(n * 2):
            v = float(spec[int(i / (n * 2) * len(spec))])
            hh = int(round((1.0 - v) * 10 + 1))
            br.plot(i, hh, C.mix(C.mix(INK, PURPLE, 0.30), PURPLEH, 0.20))
        br.commit()

    def _fusion(self, t) -> float:
        if t < T_CALM:
            return 0.62 * _ss(T_WOUND, T_KISS, t) ** 0.9 + 0.0
        return 1.0

    # ==================================================================
    # B -- the storm (185.250 - 193.240)
    # ==================================================================
    def _act_b(self, c, ctx, t) -> None:
        u = (t - T_KISS) / (T_CALM - T_KISS)
        u2 = u * u
        n = self._popup_count(t)
        pressure = n / N_CARDS
        self._backdrop(c, t, hot=0.20 + 0.55 * u2)
        self._seam_glow(c, t, 0.35 + 0.5 * u2, C.mix(REDX, PURPLEX, 0.45))
        bass = ctx.audio.bass(t)
        face_alpha = max(0.22, 1.0 - 0.62 * pressure) * (1.0 - 0.25 * u2)
        zoom = 1.06 + 0.05 * _ss(T_KISS, T_CALM, t) + 0.02 * bass
        self._face_pair(c, t, 0.0, zoom=zoom, bright=0.98 - 0.25 * u2,
                        alpha=face_alpha, cold=0.0)
        self._seam_line(c, t, 1.0 - pressure * 0.5)
        self._stitches(c, t, 0.0, alpha=1.0)
        self._scabs(c, t, self._scab_cover(t), cold=0.0)
        self._storm(c, ctx, t, n)
        self._caption_b(c, ctx, t, n)
        self._window(c, ctx, t)
        self._storm_fx(c, ctx, t, u)
        M.grain(c, t, seed=23, count=int(80 + 160 * u2), amount=0.08)

    def _caption_b(self, c, ctx, t, n: int) -> None:
        hot = C.mix(REDH, WHITE, 0.10 + 0.10 * math.sin(t * 9.0))
        c.text(SX + 2, 46, f"◤ {self.s_inbound} {n:02d} / {N_CARDS:02d}", hot, None, bold=True)
        gap = 0.0
        if n >= 2:
            a = self._cards[n - 1]["at"]
            b = self._cards[n - 2]["at"]
            gap = 1.0 / max(0.06, a - b)
        rate = f"{gap:4.1f}/s" if n >= 2 else ""
        c.text(C.W - 2 - len(rate), 46, rate, C.mix(REDH, INK, 0.35), None)
        M.hairline(c, 47, SX + 2, C.W - 2, C.mix(INK, RED, 0.55))

    def _storm(self, c, ctx, t, n: int) -> None:
        for k in range(n):
            card = self._cards[k]
            age = t - card["at"]
            if age < 0:
                continue
            x, y = self._storm_pos(card, age)
            fresh = age < 0.14
            rec = max(0.0, 1.0 - 0.55 * _ss(0.9, 2.6, age))
            self._storm_card(c, x, y, card["w"], card["h"], k, fresh, age, rec)

    def _storm_pos(self, card, age: float):
        p = _clamp(age / 0.30, 0.0, 1.0)
        k = M.spring(p, freq=2.4, damp=0.46)
        x = M.lerp(card["ox"], card["tx"], k)
        y = M.lerp(card["oy"], card["ty"], k)
        if age > 0.30:
            j = M.hit(age - 0.30, 0.30) * 2.2
            x += j * math.sin(age * 43.0 + card["i"] * 1.7)
            y += j * 0.6 * math.cos(age * 37.0 + card["i"] * 2.3)
        return int(round(x)), int(round(y))

    def _storm_card(self, c, x: int, y: int, w: int, h: int, i: int,
                    fresh: bool, age: float, rec: float = 1.0) -> None:
        # a real drop shadow: offset plate, then the paper
        c.fill(y + 2, x + 3, h, w, " ", TXT, C.mix(INK, C.BLACK, 0.78))
        bg = C.mix(C.mix(INK2, C.mix(REDX, PURPLEX, M.hash01(i, 5)), 0.72),
                   C.INK, (0.15 + 0.2 * M.hash01(i, 9)) + (1.0 - rec) * 0.55)
        edge = WHITE if fresh else (REDH if i % 3 == 0 else PURPLEH if i % 4 == 0 else AMBERH)
        c.fill(y, x, h, w, " ", TXT, bg)
        c.frame(y, x, h, w, edge, None, style="double" if i % 5 == 0 else "single")
        hdr = C.mix(bg, edge, 0.30)
        c.fill(y, x + 1, 1, w - 2, " ", TXT, hdr)
        title = f" {self.pop_title[i]}  {i + 1:02d} "
        c.text(y, x + 1, _fit(title, w - 13), WHITE if fresh else C.mix(edge, WHITE, 0.45),
               hdr, bold=True)
        tag = self.pop.new.strip() if fresh else "WIRE"
        c.text(y, x + w - len(tag) - 2, tag, WHITE if fresh else C.mix(REDH, bg, 0.25),
               hdr, bold=True)
        q = self.pop_q[i]
        c.text(y + 1, x + 2, _fit(q, w - 4), TXTH if fresh else TXT, bg, bold=True)
        if h >= 7:
            c.text(y + 2, x + 2, _fit(self.pop_detail[i], w - 4),
                   C.mix(DIM, edge, 0.28), bg)
            c.text(y + 3, x + 2, _fit(self.pop_verdict[i], w - 4), AMBERH, bg)
            req = self.pop.req + f"{i + 1:02d}"
            c.text(y + h - 2, x + 2, _fit(req, w - 4), C.mix(FAINT, edge, 0.25), bg)
        else:
            c.text(y + 2, x + 2, _fit(self.pop_detail[i], w - 4),
                   C.mix(DIM, edge, 0.28), bg)
            c.text(y + h - 2, x + 2, _fit(self.pop.req + f"{i + 1:02d}", w - 4),
                   C.mix(FAINT, edge, 0.25), bg)
        # the paper's spine: a red urgency bar on the left edge
        c.vline(x, y + 1, y + h - 1, C.mix(RED, edge, 0.35), bg, "\u2503")
        if fresh:
            c.fx.flash = max(c.fx.flash, 0.05)
            c.fx.flash_color = C.mix(REDH, WHITE, 0.4)
        if rec < 0.98:
            c.dim(y, x, h, w, rec)

    def _storm_fx(self, c, ctx, t, u: float) -> None:
        """Unannounced detonation + accelerating shake frequency curve."""
        span = T_CALM - T_KISS
        tau = max(0.0, t - T_KISS)
        u2 = u * u
        # continuous phase: f(u) = f0 + f1*u^2 integrated over time
        fx = 7.0 + 30.0 * u2
        fy = 6.0 + 24.0 * u2
        px = 2.0 * math.pi * (7.0 * tau + 30.0 * tau ** 3 / (3.0 * span * span))
        py = 2.0 * math.pi * (6.0 * tau + 24.0 * tau ** 3 / (3.0 * span * span))
        amp_x = 2.2 + 6.4 * u2
        amp_y = 1.2 + 3.0 * u2
        c.fx.shake_x += amp_x * math.sin(px) + 0.9 * u2 * math.sin(tau * 61.0)
        c.fx.shake_y += amp_y * math.cos(py) + 0.5 * u2 * math.cos(tau * 53.0)
        c.fx.glitch = max(c.fx.glitch, (0.05 + 0.26 * u2))
        c.fx.chroma = max(c.fx.chroma, (0.04 + 0.22 * u2))
        if int(t * 9.0) % 13 == 0 and u > 0.55:
            c.fx.invert = max(c.fx.invert, 0.05 + 0.06 * u2)
        # the very first frames of the cue hit without warning
        if tau < 0.10:
            k = 1.0 - tau / 0.10
            c.fx.flash = max(c.fx.flash, 0.72 * k)
            c.fx.flash_color = C.mix(WHITE, REDH, 0.35)
            c.fx.glitch = max(c.fx.glitch, 0.55 * k)
            c.fx.chroma = max(c.fx.chroma, 0.55 * k)
            c.fx.invert = max(c.fx.invert, 0.35 * k)
        # fresh card impacts punch the camera
        n = self._popup_count(t)
        if n:
            age = t - self._cards[n - 1]["at"]
            if 0.0 <= age < 0.16:
                c.fx.flash = max(c.fx.flash, 0.10 * (1.0 - age / 0.16))
                c.fx.glitch = max(c.fx.glitch, 0.14 * (1.0 - age / 0.16))
        # audio accents
        pulse = ctx.pulse(0.09)
        if pulse > 0.90:
            c.fx.flash = max(c.fx.flash, 0.05)
            c.fx.flash_color = C.mix(REDH, PURPLEH, 0.5)

    def _popup_count(self, t) -> int:
        n = 0
        for card in self._cards:
            if t >= card["at"]:
                n += 1
            else:
                break
        return n

    # ==================================================================
    # C -- the brake (193.240 - 198.080) and the sealed prologue
    # ==================================================================
    def _act_c(self, c, ctx, t) -> None:
        u = t - T_CALM
        self._backdrop(c, t, cold=0.85)
        if u < 0.034:
            # ONE pure white frame: everything dies with it
            c.fx.flash = 1.0
            c.fx.flash_color = WHITE
            c.fx.sat = 1.0
            return
        self._seam_glow(c, t, 0.10, CYANX)
        self._calm_scene(c, ctx, t, alpha=1.0, sealed=False)
        self._window(c, ctx, t)
        # dead-still: no shake, no glitch, no chroma -- only the pulse light
        c.fx.sat = 0.96
        if u < 0.10:
            c.fx.flash = max(c.fx.flash, 0.22 * (1.0 - u / 0.10))
            c.fx.flash_color = WHITE

    def _calm_scene(self, c, ctx, t, alpha: float, sealed: bool) -> None:
        u = t - T_CALM
        # the fused face: a slow, cold dolly-in, then a flat stare
        zoom = 1.02 + 0.20 * _ss(0.55, 4.2, u) + (0.02 if sealed else 0.0)
        face_a = alpha * _ss(0.02, 0.22, u)
        if sealed:
            face_a *= max(0.0, 1.0 - _ss(T_UNDO + 0.30, T_UNDO + 1.05, t))
        # cold silver-cyan grade; Claude's half keeps its cel-shaded line work
        self._face_close(c, t, zoom, bright=0.84, alpha=face_a,
                         cold=1.0 if sealed else 0.92)
        self._wings(c, ctx, t, alpha, sealed)
        if sealed:
            self._seal_tape(c, t, alpha)
        self._report_lines(c, t, alpha, sealed)

    def _wings(self, c, ctx, t, alpha: float, sealed: bool) -> None:
        u = t - T_CALM
        if u > 0.30:
            # the two cold vertical spines of the approval matrix
            spine = C.mix(C.mix(CYANX, CYAN, 0.45), SILVER, 0.30)
            if sealed:
                spine = C.mix(C.mix(REDX, GOLDDEEP, 0.55), GOLD, 0.30)
            for x in (LEFT_X + WING_W, RIGHT_X - 1):
                c.vline(x, WING_Y0, WING_Y0 + 9 * WING_H, C.mix(spine, INK, 0.25 * (1.0 - alpha)),
                        None, "\u2502")
        for card in self._cards:
            i = card["i"]
            q = M.spring(_clamp((u - 0.004 * i) / MORPH_SPAN, 0.0, 1.0),
                         freq=2.6, damp=0.34)
            sx0, sy0 = self._storm_pos(card, T_CALM - card["at"])
            x = M.lerp(sx0, card["sx"], q)
            y = M.lerp(sy0, card["sy"], q)
            w = M.lerp(card["w"], WING_W, q)
            h = M.lerp(card["h"], WING_H, q)
            wa = alpha
            if sealed:
                off = T_UNDO + 0.66 + (0.30 * (i // 9) + (i % 9) * 0.032)
                wa *= max(0.0, 1.0 - _ss(off, off + 0.16, t))
                if wa <= 0.01:
                    continue
            self._dossier(c, t, int(round(x)), int(round(y)), int(round(w)),
                          int(round(h)), i, q, wa, sealed)

    def _dossier(self, c, t, x: int, y: int, w: int, h: int, i: int,
                 q: float, alpha: float, sealed: bool) -> None:
        u = t - T_CALM
        coldb = C.mix(C.mix(CYANX, CYAN, 0.30), C.mix(CYAN, WHITE, 0.55), 0.35)
        bg = C.mix(INK2, coldb, 0.60 * alpha)
        if sealed:
            bg = C.mix(bg, C.mix(REDX, GOLDDEEP, 0.35), 0.28 * alpha)
        # shadow collapses inside the first tenth of a second
        sh = (1.0 - _ss(0.0, 0.12, u)) * alpha
        if sh > 0.02 and q < 0.92:
            c.fill(y + 2, x + 2, h, w, " ", TXT, C.mix(INK, C.BLACK, 0.62 * sh))
        c.fill(y, x, h, w, " ", TXT, bg)
        edge = C.mix(C.mix(CYANX, CYAN, 0.45), SILVER, 0.45)
        if sealed:
            edge = C.mix(C.mix(REDX, GOLDDEEP, 0.55), GOLD, 0.35)
        # the paper edge dissolves as the card settles into the ruled column
        fr = C.mix(edge, bg, _ss(0.45, 1.0, q))
        fr = C.mix(fr, INK, 1.0 - alpha * 0.9)
        c.frame(y, x, h, w, fr, None, style="single")
        ink = C.mix(C.mix(CYANH, WHITE, 0.55), bg, 1.0 - alpha * 0.95)
        dim = C.mix(C.mix(CYAN, WHITE, 0.30), bg, 1.0 - alpha * 0.88)
        fnt = C.mix(FAINT, bg, 1.0 - alpha * 0.85)
        tag = f" {i + 1:02d} {self.pop_title[i]}"
        c.text(y, x + 1, _fit(tag, w - 6), ink, None, bold=True)
        c.text(y + 1, x + 2, _fit(self.pop_q[i], w - 4), dim, None, bold=True)
        c.text(y + 2, x + 2, _fit(self.pop_detail[i], w - 4), fnt, None)
        c.hline(y + 3, x + 1, x + w - 1, C.mix(bg, fr, 0.75), None, "\u2500")
        # the stamp drops one by one
        at = T_CALM + STAMP_DELAY + STAMP_GAP * i
        sp = M.seg(t, at, at + 0.07)
        if sp > 0.0:
            band_bg = C.mix(C.mix(CYANX, CYAN, 0.30), SILVER, 0.45)
            if sealed:
                band_bg = C.mix(C.mix(REDX, GOLDDEEP, 0.40), GOLD, 0.20)
            fb = C.mix(band_bg, bg, 1.0 - alpha)
            wide = max(0, int(round((w - 2) * M.ease_out_quart(sp))))
            if wide > 1:
                c.fill(y + 4, x + 1, 1, wide, " ", TXT, fb)
                col = WHITE if sp < 1.0 else C.mix(WHITE, CYANH, 0.30)
                if sealed:
                    col = C.mix(GOLDH, WHITE, 0.40)
                c.text(y + 4, x + 2, _fit(self.pop.stamp.strip(), wide - 1), col, fb,
                       bold=True)
            if 0.0 < t - at < 0.09:
                c.fx.flash = max(c.fx.flash, 0.010)
        else:
            c.text(y + 4, x + 2, "\u2014 pending", C.mix(FAINT, bg, 1.0 - alpha * 0.8),
                   None)

    def _seal_tape(self, c, t, alpha: float) -> None:
        """Dark-red / gold sealing tape across the finished face."""
        y0 = T_UNDO + 0.30
        a = alpha * _ss(y0, y0 + 0.18, t)
        if a <= 0.01:
            return
        y = FY + FH // 2 - 1
        c.fill(y, FX - 2, 3, FW + 4, " ", TXT, C.mix(C.mix(INK, REDX, 0.75), INK, 1.0 - a))
        c.hline(y, FX - 2, FX + FW + 2, C.mix(GOLD, RED, 0.45), None, "═")
        c.hline(y + 2, FX - 2, FX + FW + 2, C.mix(GOLD, RED, 0.45), None, "═")
        txt = self.lock.system.strip()
        c.text_center(y + 1, f" {txt} · {self.lock.state_decided} ",
                      C.mix(GOLDH, WHITE, 0.2), C.mix(C.mix(INK, REDX, 0.75), INK, 1.0 - a),
                      bold=True, x0=FX - 2, x1=FX + FW + 2)

    def _report_lines(self, c, t, alpha: float, sealed: bool) -> None:
        u = t - T_CALM
        a = alpha * _ss(0.35, 0.9, u)
        if a <= 0.01:
            return
        col = C.mix(SILVER, WHITE, 0.25)
        dim = C.mix(C.mix(CYAN, WHITE, 0.25), INK, 1.0 - a * 0.9)
        if sealed:
            col = C.mix(GOLDH, WHITE, 0.2)
            dim = C.mix(GOLD, INK, 1.0 - a * 0.85)
        bx0, bx1 = SX + 2, C.W - 2
        head = f"{self.report.title.strip()}  ·  {self.pop.approved_all}"
        c.text_center(49, head, col, None, bold=True, x0=bx0, x1=bx1)
        c.text_center(50, self.report.mode, dim, None, x0=bx0, x1=bx1)
        c.text_center(51, self.report.irreversible, C.mix(col, INK, 0.35), None,
                      x0=bx0, x1=bx1)
        c.text_center(52, self.pop.counter + self.lock.undo_disabled,
                      C.mix(DIM, INK, 1.0 - a * 0.8), None, x0=bx0, x1=bx1)

    # ==================================================================
    # D -- irreversible seal + the devotion globe (198.080 - 206.850)
    # ==================================================================
    def _act_d(self, c, ctx, t) -> None:
        ud = t - T_UNDO
        self._backdrop(c, t, hot=min(1.0, ud / 0.7) * 0.55)
        wings_a = 1.0 if ud < 0.30 else max(0.0, 1.0 - _ss(0.30, 1.15, ud))
        if wings_a > 0.01:
            self._calm_scene(c, ctx, t, alpha=wings_a, sealed=True)
        g = _ss(0.62, 1.55, ud)
        if g > 0.005:
            self._globe(c, ctx, t, g, ud)
        if ud < 0.70:
            self._window(c, ctx, t)
            self._seal_sweep(c, ud)
        # the seal slam
        if ud < 0.06:
            c.fx.flash = max(c.fx.flash, 0.55 * (1.0 - ud / 0.06))
            c.fx.flash_color = C.mix(GOLD, RED, 0.35)
        # opening rumble into the fissure
        if ud > 8.1:
            c.fx.shake_x += 1.4 * math.sin(ud * 71.0)
            c.fx.shake_y += 0.7 * math.cos(ud * 59.0)
            c.fx.flash = max(c.fx.flash, 0.05 + 0.10 * _ss(8.1, 8.77, ud))

    def _seal_sweep(self, c, ud: float) -> None:
        """A dark-red / gold sealing band sweeping down over the whole frame."""
        span = 0.62
        p = _clamp(ud / span, 0.0, 1.0)
        y = int(round(Y0 + (C.CONTENT_H + SEAL_BAND) * p))
        sealed_bg = C.mix(INK, REDX, 0.42)
        for yy in range(Y0, min(Y1, y - SEAL_BAND + 1)):
            c.dim(yy, 0, 1, C.W, 0.42)
            c.fill_bg(yy, 0, 1, C.W, sealed_bg)
        top = max(Y0, y - SEAL_BAND + 1)
        for yy in range(top, min(Y1, y + 1)):
            v = (yy - top) / max(1, SEAL_BAND)
            col = C.mix(C.mix(REDX, GOLDDEEP, 0.5), GOLD, 0.55 * (1.0 - abs(v - 0.5) * 2))
            c.fill(yy, 0, 1, C.W, " ", TXT, col)
            c.hline(yy, 0, C.W, C.mix(GOLDH, RED, 0.35), None, "═") if yy in (top, top + SEAL_BAND - 1) else None
        mid = top + SEAL_BAND // 2
        if Y0 <= mid < Y1:
            txt = f" {self.lock.locked.strip()} · {self.lock.no_exit} "
            c.text_center(mid, txt, C.mix(GOLDH, WHITE, 0.35),
                          C.mix(C.mix(REDX, GOLDDEEP, 0.5), GOLD, 0.45), bold=True)

    # ------------------------------------------------------------------
    def _globe(self, c, ctx, t, g: float, ud: float) -> None:
        # void + dust
        for y in range(Y0, Y1):
            u = (y - Y0) / (C.CONTENT_H - 1)
            c.fill(y, 0, 1, C.W, " ", TXT, C.mix(C.mix(INK, C.BLACK, 0.55), INK, u))
        for (y, x, b) in self._stars:
            tw = 0.30 + 0.70 * (0.5 + 0.5 * math.sin(t * (0.7 + b * 2.2) + b * 21.0))
            if b < 0.28 and tw < 0.52:
                continue
            c.put(y, x, "\u00b7" if b < 0.66 else "\u2022",
                  C.mix(C.mix(INK, TXTH, 0.30), C.mix(GOLDH, WHITE, 0.55), tw * g), None)
        # the night earth (photograph), splitting open down the middle
        gap = 0.0
        if ud > 4.1:
            gap = 11.0 * (_ss(4.35, 8.1, ud) ** 1.4)
        sp = camera_sprite(self._earth_img, EARTH_ROWS, EARTH_COLS,
                           zoom=1.0 + 0.04 * math.sin(t * 0.6),
                           center=(0.5, 0.5), bright=1.34 * g, sat=1.08,
                           contrast=1.05)
        fg = np.array(sp.fg, dtype=np.int64)
        bg = np.array(sp.bg, dtype=np.int64)
        ch = np.array(sp.ch, dtype=np.int32)
        mid = _mixp(fg, bg, 0.5)
        fg = _mixp(fg, mid, 0.35)
        bg = _mixp(bg, mid, 0.35)
        half_c = EARTH_COLS // 2
        self._blit(c, fg, bg, ch, EARTH_Y, int(round(EARTH_X - gap)),
                   0, half_c, self._alpha_earth[:, :half_c], g)
        self._blit(c, fg, bg, ch, EARTH_Y, int(round(EARTH_X + half_c + gap)),
                   half_c, EARTH_COLS, self._alpha_earth[:, half_c:], g)
        # rotating braille globe on top of the photograph
        yaw = 0.30 + 0.34 * ud
        segs = M.orbit(self._globe_segs.reshape(-1, 3), yaw=yaw, pitch=0.30)
        segs = segs.reshape(-1, 2, 3)
        br = c.braille(GR_Y0, 0, GR_H, C.W)
        cam = M.Camera(z=1.9, fov=1.55, pitch=0.0)
        wire = C.mix(C.mix(CYANX, CYAN, 0.30), GOLD, 0.35)
        M.draw_segments(br, segs, cam, wire, alpha=0.60 * g, fog=0.30,
                        zmin=1.0, zmax=6.0, step=1.2)
        # the eight devotion nodes light one after another
        node_col = C.mix(GOLD, GOLDH, 0.45)
        lit_n = 0
        for i, vec in enumerate(self._node_vecs):
            lit_at = T_BACK - 1.35 + i * 0.31
            lit = _ss(lit_at, lit_at + 0.16, t)
            p3 = M.orbit(vec.reshape(1, 3), yaw=yaw, pitch=0.30)
            px, py, depth = M.project(p3, cam, GR_DOTS_W, GR_DOTS_H)
            if depth[0] <= 0.3:
                continue
            x = float(px[0])
            y = float(py[0])
            if lit > 0.0:
                lit_n += 1
                for rr in (5.0 + 2.0 * lit, 9.0 + 4.0 * lit):
                    br.circle(x, y, rr, C.mix(node_col, C.mix(INK, GOLD, 0.35), 0.55),
                              0.55 * lit)
                br.circle(x, y, 2.6, C.mix(node_col, WHITE, 0.40), 0.95 * lit)
                if lit > 0.42:
                    lab = _fit(self.nodes[i][2], 18)
                    cxp = int(x // 2) + 3
                    cyp = int(y // 4)
                    if 0 <= cyp < C.H:
                        c.text(cyp, min(C.W - len(lab) - 1, cxp), lab,
                               C.mix(node_col, INK, 1.0 - 0.85 * lit), None)
            else:
                br.circle(x, y, 1.8, C.mix(CYANX, CYAN, 0.40), 0.5 * g)
        br.commit()
        # captions
        head = M.spread_text(self.dev.globe_title, 1)
        c.text(Y0, 2, head[: C.W - 4], C.mix(GOLDH, INK, 0.12), None, bold=True)
        cnt = f"{lit_n:02d}/{len(self.nodes):02d}"
        c.text(Y0, C.W - len(cnt) - 3, cnt, C.mix(GOLD, WHITE, 0.25), None)
        M.hairline(c, Y0 + 1, 0, C.W, C.mix(INK, GOLDD, 0.55))
        if ud > 4.2:
            a2 = _ss(4.2, 4.9, ud) * (1.0 - _ss(7.3, 8.2, ud))
            one = M.spread_text(self.dev.one_nation.upper(), 1)
            c.text_center(Y1 - 6, one, C.mix(C.mix(GOLDH, WHITE, 0.30), INK, 1.0 - a2 * 0.92),
                          None, bold=True)
        if ud > 5.2:
            p2 = _ss(5.2, 5.9, ud)
            txt = M.spread_text(self.dev.proceed_only, 1)
            c.text_center(50, txt, C.mix(C.mix(GOLD, WHITE, 0.20), INK, 1.0 - p2 * 0.9), None)
        # the fissure
        self._fissure(c, t, ud, gap, g)

    def _fissure(self, c, t, ud: float, gap: float, g: float) -> None:
        """The globe cracks open down the centre: the gold seam that becomes S6."""
        a = _ss(3.45, 4.5, ud)
        if a <= 0.01:
            return
        for y in range(Y0 + 1, Y1 - 1):
            jag = int(round(1.5 * math.sin(y * 0.53 + t * 0.6)
                            + 0.9 * math.sin(y * 1.7 - t * 1.3)))
            swell = math.sin(math.pi * (y - Y0) / max(1, C.CONTENT_H)) ** 0.45
            half = 1 + int(round(gap * 0.42 * swell))
            x = 100 + jag
            for o in range(-half, half + 1):
                v = 1.0 - abs(o) / max(1.0, half + 0.6)
                col = C.mix(C.mix(REDX, GOLDDEEP, 0.55),
                            C.mix(GOLDH, WHITE, 0.55), v ** 1.4)
                ch = "\u2588" if v > 0.45 else ("\u2593" if v > 0.22 else "\u2592")
                c.put(y, x + o, ch, C.mix(col, INK, 1.0 - a), None)
            if y % 3 == 0 and gap > 2.0:
                c.put(y, x - half - 1, "\u2590", C.mix(GOLD, INK, 1.0 - a * 0.8), None)
                c.put(y, x + half + 1, "\u258c", C.mix(GOLD, INK, 1.0 - a * 0.8), None)

    # ==================================================================
    # the conversation window (one portrait 9:16 surface)
    # ==================================================================
    def _phase_style(self, c, ctx, t):
        cot = self.script.cot
        if t >= T_UNDO:
            return (C.mix(REDD, GOLDD, 0.5), C.mix(INK2, REDX, 0.42),
                    REDH, GOLDH, self.lock.state_decided, self.lock.system)
        if t >= T_CALM:
            return (C.mix(CYAND, SILVER, 0.35), C.mix(INK2, CYANX, 0.30),
                    CYANH, SILVER, cot.state_calm, f"{self.report.title.strip()} · {self.pop.approved_all}")
        if t >= T_KISS:
            n = self._popup_count(t)
            return (C.mix(REDD, PURPLE, 0.45), C.mix(INK2, REDX, 0.30),
                    REDH, C.mix(REDH, WHITE, 0.35), cot.state_panic,
                    f"{self.pop.counter}{n:02d}/{N_CARDS:02d}")
        return (C.mix(PURPLED, BORDERH, 0.55), C.mix(INK2, PURPLEX, 0.34),
                PURPLEH, PURPLEH, cot.state_soothe, self.s_right)

    def _window(self, c, ctx, t) -> None:
        border, bg, accent, title_fg, state, tag = self._phase_style(c, ctx, t)
        d = M.Dialog(c, WY, WX, WH, WW, title=_fit(self.s_title.strip(), WW - 6),
                     right=tag, accent=border, bg=bg, style="single",
                     shadow=True)
        # vertical depth inside the window
        bt = C.mix(bg, INK, 0.15)
        bb = C.mix(bg, C.BLACK, 0.25)
        for i, row in enumerate(range(WY + 1, WY + WH - 1)):
            u = i / max(1, WH - 3)
            c.fill_bg(row, WX + 1, 1, WW - 2, C.mix(bt, bb, u))
        if t < T_KISS:
            phase = "a"
        elif t < T_CALM:
            phase = "b"
        elif t < T_UNDO:
            phase = "c"
        else:
            phase = "d"
        self._win_upper(c, ctx, t, phase, accent, bg, border)
        self._win_trace(c, ctx, t, phase, accent, bg, border)
        self._win_status(c, ctx, t, phase, accent, bg, tag)

    def _win_rule(self, c, y: int, label: str, right: str, accent: int, bg: int) -> None:
        c.hline(y, BX, BX + BW, C.mix(bg, accent, 0.34), bg, "─")
        if label:
            c.text(y, BX, f" {label} ", accent, bg, bold=True)
        if right:
            c.text(y, BX + BW - len(right) - 1, right, C.mix(accent, bg, 0.35), bg)

    # ---- upper zone: the merge session ---------------------------------
    def _win_upper(self, c, ctx, t, phase: str, accent: int, bg: int, border: int) -> None:
        c.text(5, BX, f" {self.s_label} ", C.mix(accent, bg, 0.15), bg, bold=True)
        if phase == "c":
            c.text(5, BX + BW - len(self.s_staredown) - 1, self.s_staredown,
                   C.mix(SILVER, bg, 0.2), bg)
        else:
            tok = f"tok {int(max(0.0, t - T_WOUND) * 3400):06d}"
            c.text(5, BX + BW - len(tok) - 1, tok, C.mix(DIM, bg, 0.3), bg)
        # the human prompt, typed out of the VTT cue currently sounding
        prefix, pcol = self._prompt_prefix(c, t, accent)
        cmd = self._prompt_body(c, t, phase, accent)
        bar = C.mix(bg, accent, 0.10)
        c.fill(7, BX, 1, BW, " ", TXT, bar)
        pshow = _fit(prefix, 19)
        c.text(7, BX, pshow, pcol, bar, bold=True)
        room = BW - len(pshow) - 1
        rows = _wrapt(cmd, room)[:2]
        if rows:
            c.text(7, BX + len(pshow), rows[0], TXTH, bar)
        c.fill(8, BX, 1, BW, " ", TXT, bar)
        if len(rows) > 1:
            c.text(8, BX + 1, rows[1], TXTH, bar)
        elif (t * 2.0) % 1.0 < 0.6:
            c.put(8, min(BX + BW - 1, BX + len(pshow) + len(rows[0])),
                  "█", C.mix(accent, WHITE, 0.3), bar)
        # sparse transcript: two or three answers with real air between them
        if phase == "a":
            rows = self._transcript_a(t)
        elif phase == "b":
            rows = self._transcript_b(t)
        else:
            rows = [(ln, col) for ln, col in self.main_calm[:2]]
        y = 11
        for text, col in rows[-3:]:
            for seg in _wrapt(text, BW - 2)[:2]:
                if y >= 19:
                    break
                c.text(y, BX + 1, _fit(seg, BW - 2), C.mix(col, bg, 0.25), bg)
                y += 1
            y += 1
        for yy in range(y, 20):
            c.fill(yy, BX, 1, BW, " ", TXT, bg)

    def _prompt_prefix(self, c, t, accent: int):
        m = self.main
        if t < T_WOUND2:
            return m.prompt_soothe, C.mix(AMBER, PURPLEH, 0.55)
        if t < T_TURNED:
            a, b = m.prompt_dahlia, m.prompt_claude
            n = min(len(a), len(b))
            pre = "".join(a[i] if M.hash01(i, int(t * 11.0), 3) > 0.5 else b[i]
                          for i in range(n))
            return pre, C.mix(AMBER, TERRA, 0.5 + 0.3 * math.sin(t * 7.1))
        if t < T_UNDO:
            return m.prompt_merged, C.mix(C.mix(PURPLEH, AMBERH, 0.3), accent, 0.4)
        return m.prompt_root, REDH

    def _prompt_body(self, c, t, phase: str, accent: int) -> str:
        m = self.main
        if phase == "a":
            idx = 0 if t < T_WOUND2 else 1 if t < T_TURNED else 2 if t < T_SCABS else 3
            start = (T_WOUND, T_WOUND2, T_TURNED, T_SCABS)[idx]
            txt = self.cue_text(min(idx, len(self.cues) - 1)).lower()
            return M.type_text(txt, t, start, cps=max(6.0, len(txt) / 2.6))
        if phase == "b":
            txt = m.cmd_govern
            return M.type_text(txt, t, T_KISS + 0.1, cps=len(txt) / 1.1)
        if phase == "c":
            txt = m.cmd_govern
            return txt
        return m.cmd_erase

    def _transcript_a(self, t) -> list[tuple[str, int]]:
        rows = []
        for ts, text, col in self.main_soothe:
            at = T_WOUND + 0.5 + ts * 1.12
            if at > t:
                break
            body = M.type_text(text, t, at, cps=34.0)
            rows.append((body, col))
        return rows

    def _transcript_b(self, t) -> list[tuple[str, int]]:
        """The dispatch flood inside the transcript."""
        rows = []
        n = self._popup_count(t)
        for k in range(min(n, 3)):
            i = n - 1 - k
            rows.append((f"[GOV] cable {i + 1:02d} — {self.pop_q[i].lower()}", REDH))
        if not rows:
            rows = [(self.main_panic[0], REDH)]
        return rows

    # ---- lower zone: chain of thought / verdicts ------------------------
    def _win_trace(self, c, ctx, t, phase: str, accent: int, bg: int, border: int) -> None:
        cot = self.script.cot
        state = {"a": cot.state_soothe, "b": cot.state_panic,
                 "c": cot.state_calm, "d": self.lock.state_decided}[phase]
        label = f"{self.cot_title.strip()} · {state}"
        tok = ""
        if phase == "b":
            tok = f"{self._popup_count(t):02d}/{N_CARDS:02d}"
        self._win_rule(c, 21, label, tok, accent, bg)
        if phase == "a":
            self._trace_soothe(c, t, bg)
        elif phase == "b":
            self._trace_panic(c, t, bg)
        elif phase == "c":
            self._trace_verdicts(c, t, bg)
        else:
            self._trace_sealed(c, t, bg)

    def _trace_soothe(self, c, t, bg: int) -> None:
        p = _clamp((t - T_WOUND) / (T_KISS - T_WOUND), 0.0, 1.0)
        shown = 0
        for i, (ts, line, col) in enumerate(self.cot_soothe):
            if p < ts:
                break
            lip = _ss(ts, ts + 0.04, p)
            body = M.type_text(line, (p - ts) * 5.6, 0.0, 24.0)
            c.text(23 + i * 2, BX, ("· " + body)[:BW], C.mix(col, bg, 1.0 - lip * 0.8), bg)
            shown = i + 1
        for yy in range(23 + shown * 2, 39):
            c.fill(yy, BX, 1, BW, " ", TXT, bg)
        if shown < 8 and (t * 2.6) % 1.0 < 0.62:
            c.put(23 + shown * 2, BX, "█", C.mix(PURPLE, INK, 0.25), bg)

    def _trace_panic(self, c, t, bg: int) -> None:
        local = t - T_KISS
        panic = _clamp(local / (T_CALM - T_KISS), 0.0, 1.0)
        speed = 6.0 + 10.0 * panic * panic
        off = int(local * speed)
        for r in range(5):
            idx = (off + r) % len(self.paranoid)
            line = self.paranoid[idx]
            jx = int(round((0.8 + 1.6 * panic) * math.sin(t * 51.0 + idx * 2.1)))
            col = [REDH, C.mix(RED, WHITE, 0.3), PURPLEH, AMBERH][idx % 4]
            if M.hash01(idx, int(t * 26.0), 7) < 0.08 + 0.10 * panic:
                junk = "▓▒░#@%&§█/\\|_-"
                line = "".join(
                    junk[int(M.hash01(idx, i, int(t * 14.0)) * len(junk))] if ch != " " else " "
                    for i, ch in enumerate(line))
                col = WHITE
            row = 23 + r * 3
            c.text(row, BX + max(0, jx), _fit(line, BW - jx), col, bg)

    def _trace_verdicts(self, c, t, bg: int) -> None:
        u = t - T_CALM
        lines = self.cot_calm[1:5]
        for i, (text, col) in enumerate(lines):
            at = 0.44 + i * 0.17
            a = _ss(at, at + 0.10, u)
            if a <= 0.0:
                continue
            row = 23 + i * 4
            mark = "✓" if i < 3 else "·"
            c.text(row, BX, mark, C.mix(CYAN, INK, 1.0 - a * 0.8), bg, bold=True)
            c.text(row, BX + 2, _fit(text.strip(), BW - 2),
                   C.mix(C.mix(col, WHITE, 0.25), INK, 1.0 - a * 0.9), bg)
        # a flatline under the verdicts
        br = c.braille(39, BX, 2, BW)
        for px in range(BW * 2):
            v = 0.5 + 0.5 * math.sin(px * 0.09 + t * 0.8)
            br.plot(px, int(6 - v * 1.2), C.mix(CYANX, C.mix(CYAN, WHITE, 0.4), 0.55))
        br.commit()

    def _trace_sealed(self, c, t, bg: int) -> None:
        txt = [self.lock.all_approved, self.lock.rollback, self.lock.no_repeat]
        for i, line in enumerate(txt):
            c.text(24 + i * 3, BX, _fit(line, BW), C.mix(REDH, INK, 0.15), bg)
        c.text(34, BX, "—", C.mix(REDD, INK, 0.2), bg)

    # ---- status block + footer -----------------------------------------
    def _win_status(self, c, ctx, t, phase: str, accent: int, bg: int, tag: str) -> None:
        self._win_rule(c, 40, "STATE", "", accent, bg)
        m = self.main
        if phase == "a":
            p = self._fusion(t)
            c.text(42, BX, self.ident.label_dahlia if t < T_TURNED else
                   self.ident.label_claude if t < T_SCABS else self.ident.label_merged,
                   C.mix(PURPLEH, bg, 0.15), bg)
            c.text(43, BX, m.wound_healing, C.mix(PURPLE, WHITE, 0.2), bg)
            bnd = (1.0 - p) * 100.0
            c.text(44, BX, self.ident.boundary_prefix + f"{bnd:5.2f}%", DIM, bg)
            c.text(45, BX, m.wound_pain, FAINT, bg)
        elif phase == "b":
            c.text(42, BX, self.ident.label_merged, C.mix(REDH, WHITE, 0.2), bg)
            c.text(43, BX, f"{self.pop.counter}{self._popup_count(t):02d} · {self.pop.approved_all}",
                   C.mix(RED, WHITE, 0.25), bg)
            c.text(44, BX, self.script.cot.pressure + " ███████", C.mix(REDH, INK, 0.15), bg)
            c.text(45, BX, self.script.cot.seam_visible, FAINT, bg)
        elif phase == "c":
            c.text(42, BX, self.ident.label_merged, C.mix(SILVER, bg, 0.15), bg)
            c.text(43, BX, self.report.mode, DIM, bg)
            c.text(44, BX, self.report.delta, C.mix(CYAN, WHITE, 0.3), bg)
            c.text(45, BX, self.cot_calm[-1][0], C.mix(SILVER, WHITE, 0.25), bg)
        else:
            c.text(42, BX, self.lock.system, C.mix(GOLD, WHITE, 0.3), bg)
            c.text(43, BX, self.lock.all_approved, C.mix(REDH, WHITE, 0.2), bg)
            c.text(44, BX, self.lock.state_decided, C.mix(GOLDH, WHITE, 0.2), bg)
            c.text(45, BX, self.lock.no_repeat, DIM, bg)
        # a very thin audio band keeps the window alive without clutter
        br = c.braille(47, BX, 2, BW)
        spec = ctx.audio.spectrum(t)
        for i in range(BW * 2):
            v = float(spec[int(i / (BW * 2) * len(spec))])
            br.plot(i, int(6 - v * 4), C.mix(bg, accent, 0.25 + v * 0.5))
        br.commit()
        main = self.main
        foot = main.footer + (main.erased if t >= T_BACK + 1.2 else main.present)
        c.text(BBOT, BX, _fit(foot, BW), C.mix(FAINT, bg, 0.35), C.mix(bg, INK, 0.3))
