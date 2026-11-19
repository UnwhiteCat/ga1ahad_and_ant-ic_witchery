"""Movements 3-4 of Scene 3.5 -- boolean/clock/conduit montage, decree,
codex and the Station B7 interlude (123.180 - 157.900).

Dispatched by ga1ahad.scenes.s35.Scene35::

    import s35b; s35b.prepare(self)          # in Scene35.__init__
    s35b.draw(self, c, ctx)                 # for ctx.t >= 123.180

The 200x51 content band is treated as a full-bleed cinema screen: no
conversation window from 123.180 to 148.890, then the mandatory left 9:16
window for the [revision] transcript while Station B7 comes up on the stage.
Static geometry, resolved screenplay strings and noise fields are prepared
once in prepare(); draw() is a pure function of ctx.t.
"""

from __future__ import annotations

import math
import random

from .. import config as C
from .. import motion as M
from ..assets import camera_sprite, keyframe
from ..canvas import wrap
from ..glyphs import glyph_table
from .revision import draw_session

Y0, Y1 = C.CONTENT_Y0, C.CONTENT_Y1
BH = Y1 - Y0                     # 51 usable rows
W = C.W
INK = C.INK
TEXT = C.TEXT
DIM = C.TEXT_DIM
FAINT = C.TEXT_FAINT
TEXT_DIM = C.TEXT_DIM
TEXT_FAINT = C.TEXT_FAINT
TEXT_HI = C.TEXT_HI
WHITE = C.WHITE
CYAN = C.CYAN
CYAN_HI = C.CYAN_HI
CYAN_DIM = C.CYAN_DIM
CYAN_DEEP = C.CYAN_DEEP
RED = C.RED
RED_HI = C.RED_HI
RED_DIM = C.RED_DIM
RED_DEEP = C.RED_DEEP
BLOOD = C.BLOOD
BLOOD_HI = C.BLOOD_HI
GOLD = C.GOLD
GOLD_HI = C.GOLD_HI
GOLD_DIM = C.GOLD_DIM
GOLD_DEEP = C.GOLD_DEEP
AMBER = C.AMBER
AMBER_HI = C.AMBER_HI
AMBER_DIM = C.AMBER_DIM
BROWN_DIM = C.BROWN_DIM
PURPLE = C.PURPLE
BORDER = C.BORDER
BORDER_HI = C.BORDER_HI

# --------------------------------------------------------------------------
# beat map (absolute song seconds)
# --------------------------------------------------------------------------
T_E1 = 123.180          # truth or false / logic
T_SPLIT_END = 123.915
T_E2 = 126.190          # rising edge / flip-flop
T_WAVES_END = 127.760
T_E3 = 129.140          # generate / oscillate / blood fill the gates
T_LISS_END = 130.090
T_OVER_END = 130.790
T_E4 = 132.130          # multiplex / process registration
T_SPIN_END = 132.800
T_E5 = 134.660          # wipe off your pus / grind down your vitamins
T_F1 = 138.680          # the end justifies the means
T_G = 140.390           # open the book / turn to page 617
T_COVER_END = 141.840
T_FLIP_END = 144.650
T_CODEX_END = 148.890
T_CLOSE = 148.780       # pages start to close just before the interlude
T_STATION = 149.400
T_REV = 148.890
T_END = 157.900

_SPLIT_CUTS = (123.180, 123.367, 123.550, 123.733)


# --------------------------------------------------------------------------
# tiny local helpers
# --------------------------------------------------------------------------
def _clear(c, color=INK):
    c.fill(Y0, 0, BH, W, " ", TEXT, color)


def _grad(c, top, bottom):
    M.bg_gradient(c, top, bottom, Y0, Y1)


def _center_text(c, y, s, fg, bg=None, bold=False, x0=0, x1=W):
    return c.text_center(y, s, fg, bg, bold=bold, x0=x0, x1=x1)


def _block(c, y, s, fg, scale=1, spacing=1, x0=0, x1=W, bg=None,
           top=None, bottom=None, block="\u2588"):
    return M.big_text(c, y, x0, s, fg, scale=scale, spacing=spacing, x1=x1,
                      align="center", bg=bg, top=top, bottom=bottom,
                      block=block)


def _hair(c, y, x0, x1, color):
    c.hline(y, max(0, x0), min(W, x1), color, None, "\u2500")


def _cut(c, age, *, flash=0.0, glitch=0.0, chroma=0.0, shake=0.0,
         decay=0.14, color=WHITE):
    if 0.0 <= age < 0.5:
        M.punctuate(c, age, flash=flash, glitch=glitch, chroma=chroma,
                    shake=shake, decay=decay, flash_color=color)


def _dot_rect(br, x, y, w, h, color, alpha=0.9):
    x2, y2 = x + w, y + h
    for px in range(int(x), int(x2) + 1):
        br.plot(px, int(y), color, alpha)
        br.plot(px, int(y2), color, alpha)
    for py in range(int(y), int(y2) + 1):
        br.plot(int(x), py, color, alpha)
        br.plot(int(x2), py, color, alpha)


# --------------------------------------------------------------------------
# prepared state
# --------------------------------------------------------------------------
class _Data:
    pass


def prepare(scene):
    """Resolve the screenplay and precompute every static field/geometry."""
    if getattr(scene, "_s35b", None) is not None:
        return
    S = scene.script
    v2 = S.v2
    acts = S.acts
    d = _Data()

    # -- resolved text ---------------------------------------------------
    d.split_tag = str(acts.e1.tag)
    d.split_banner = str(acts.e1.banner)
    lg = v2.logic.title
    d.true_sym = str(lg.true_word).split("//")[0].strip() or "1"
    d.true_tag = str(lg.true_word).split("//")[-1].strip() or "TRUE"
    d.false_sym = str(lg.false_word).split("//")[0].strip() or "0"
    d.false_tag = str(lg.false_word).split("//")[-1].strip() or "FALSE"
    d.logic_gates = [str(g) for g in lg.gates]
    d.logic_truth_hdr = str(lg.truth_hdr)
    d.logic_verdict = str(lg.verdict)
    d.logic_footer = str(lg.footer)
    d.logic_tag = str(acts.e1.tag)

    d.clock_title = str(v2.clock.title)
    d.clock_channels = [str(s) for s in v2.clock.channels]
    d.clock_ff = [str(s) for s in v2.clock.ff_names]
    d.clock_armed = str(v2.clock.armed_label)
    d.clock_footer = str(v2.clock.footer)
    d.clock_tag = str(acts.e2.tag)

    d.blood_words = [str(s) for s in v2.blood.words]
    d.blood_osc = [str(s) for s in v2.blood.osc_labels]
    d.blood_fill = str(v2.blood.fill_label)
    d.blood_pressure = str(v2.blood.pressure_label)
    d.blood_leak = str(v2.blood.leak_label)
    d.blood_footer = str(v2.blood.footer)
    d.blood_banner = str(S.blood.banner)
    d.blood_tag = str(acts.e3.tag)

    mt = v2.mux.title
    d.mux_title = str(mt.text)
    d.mux_panel = str(mt.mux_panel)
    d.mux_route = str(mt.route_lock)
    d.mux_stamp = str(mt.stamp)
    d.mux_footer = str(mt.footer)
    d.mux_tag = str(acts.e4.tag)
    d.mux_banner = str(acts.e4.banner)
    d.mux_fields = [(str(f.key), str(f.value)) for f in S.mux.fields]
    d.pid = next((v for k, v in d.mux_fields if k.upper() == "PID"), "617")
    d.reg_title = str(S.mux.reg_title)

    pg = v2.purge.title
    d.purge_title = str(pg.text)
    d.purge_laser = str(pg.laser_label)
    d.purge_mill = str(pg.mill_label)
    d.purge_output = str(pg.output)
    d.purge_removed = [str(s) for s in pg.removed]
    d.purge_footer = str(pg.footer)
    d.purge_stamp = str(S.purge.stamp)
    d.purge_state = str(S.purge.state)
    d.purge_tag = str(acts.e5.tag)

    d.hammer_lines = [str(s) for s in v2.hammer.lines]
    d.hammer_preamble = str(v2.hammer.preamble)
    d.hammer_seal = str(v2.hammer.seal)
    d.hammer_tag = str(acts.f1.tag)

    d.book_open = str(v2.book.open)
    d.book_page = str(v2.book.page)
    d.book_page_label = str(v2.book.page_label)
    d.book_page_number = str(S.book.page_number)
    d.book_left_title = str(v2.book.left_title)
    d.book_article_i = str(v2.book.article_i)
    d.book_article_dcxvii = str(v2.book.article_dcxvii)
    d.book_formulas = [str(s) for s in v2.book.formulas]
    d.book_right_title = str(v2.book.right_title)
    d.book_sun = str(v2.book.sun)
    d.book_runes = str(v2.book.runes)
    d.book_cover_title = str(v2.book.cover_title)
    d.book_cover_sub = str(v2.book.cover_sub)
    d.book_left_header = str(v2.book.left_header)
    d.book_right_header = str(v2.book.right_header)
    d.book_banner = str(acts.g.banner)
    d.book_tag = str(acts.g.tag)

    inter = v2.interlude
    d.inter_title = str(inter.desktop_title)
    d.inter_session = str(inter.session)
    d.inter_user = str(inter.user)
    d.inter_assistant = str(inter.assistant)
    d.inter_input = str(inter.input_label)
    d.inter_room = str(inter.room_title)
    d.aisle = str(S.hall.aisle)
    d.rail = str(S.hall.rail)
    d.beats = S.revision.beats

    # s4 continues this transcript at the cut: mirror its stage label when the
    # content tree still exposes it (graceful fallback to the room title).
    try:
        d.s4_hall = str(scene.content.scene("s4").hall.title)
    except Exception:
        d.s4_hall = d.inter_room

    # -- static geometry -------------------------------------------------
    # E1 facade: perspective quad in cell coords (x, y)
    d.facade_quad = ((20.0, 3.0), (178.0, 4.0), (192.0, 50.0), (6.0, 47.0))
    d.facade_us = [i / 9.0 for i in range(10)]
    d.facade_vs = [i / 7.0 for i in range(8)]
    d.facade_wins = [(i, j) for j in range(7) for i in range(9)]

    # E2 square-wave bands
    d.wave_bands = [
        dict(y0=2, h=9, lam=72.0, rate=1.02, phase=0.0, color=CYAN_HI, gain=0.86),
        dict(y0=12, h=9, lam=54.0, rate=0.82, phase=1.4, color=C.CYAN, gain=0.94),
        dict(y0=22, h=9, lam=92.0, rate=1.24, phase=2.7, color=C.TEXT_HI, gain=0.8),
        dict(y0=32, h=9, lam=46.0, rate=0.66, phase=0.8, color=C.CYAN, gain=1.0),
        dict(y0=42, h=9, lam=82.0, rate=1.1, phase=3.9, color=C.TEXT_HI, gain=0.88),
    ]
    d.latch_lanes = [
        dict(y0=2, h=11, phase=0.0, color=CYAN_HI),
        dict(y0=14, h=11, phase=0.55, color=C.TEXT_HI),
        dict(y0=26, h=11, phase=1.15, color=C.CYAN),
        dict(y0=38, h=11, phase=1.75, color=CYAN_HI),
    ]

    # E3 Lissajous (normalised -1..1)
    d.liss = []
    for k in range(961):
        u = 2.0 * math.pi * k / 960.0
        d.liss.append((math.sin(3.0 * u + math.pi / 3.0), math.sin(2.0 * u)))
    d.liss2 = []
    for k in range(1201):
        u = 2.0 * math.pi * k / 1200.0
        d.liss2.append((math.sin(5.0 * u + 1.1), math.sin(4.0 * u)))

    # E3 conduit layout
    d.pipe_main = (4, 196, 42, 4)             # x0, x1, row, height
    d.pipe_risers = [(26, 26), (62, 21), (98, 28), (134, 23), (170, 26)]

    # E4 multiplex 3D channels
    d.mux_angles = [i * math.pi / 4.0 for i in range(8)]
    d.mux_rows = [5 + i * 5 for i in range(8)]  # locked horizontal bus rows

    # E5 organic field (precomputed glyph ids + colours, rows of 200)
    d.warm_gid = []
    d.warm_fg = []
    gl = glyph_table()
    gids = [gl.char_id(ch) for ch in ("\u2591", "\u2592", "\u2593", "\u2588")]
    ramp = [(0.00, C.mix(INK, C.BROWN_DIM, 0.60)),
            (0.18, C.mix(BROWN_DIM, C.BLOOD, 0.30)),
            (0.36, C.mix(BROWN_DIM, C.BLOOD, 0.85)),
            (0.52, C.mix(C.BLOOD, C.RED_DIM, 0.80)),
            (0.66, C.mix(C.RED_DIM, C.AMBER_DIM, 0.75)),
            (0.80, C.mix(C.AMBER_DIM, C.RED_HI, 0.55)),
            (0.92, C.mix(C.RED_HI, C.AMBER_HI, 0.55)),
            (1.00, C.mix(C.AMBER_HI, C.TEXT_HI, 0.35))]
    rng = random.Random(617)
    for y in range(BH):
        gid_row = []
        fg_row = []
        for x in range(W):
            v = (0.50
                 + 0.22 * math.sin(x * 0.47 + y * 0.13 + 0.6)
                 + 0.16 * math.sin(x * 0.09 - y * 0.61 + 2.1)
                 + 0.30 * (M.noise1(x * 0.55 + y * 0.23, seed=5) - 0.5) * 2.0
                 + 0.14 * (M.hash01(x, y) - 0.5) * 2.0)
            v = C.clamp(v + rng.uniform(-0.05, 0.05), 0.0, 1.0)
            gid_row.append(gids[0] if v < 0.26 else gids[1] if v < 0.50
                           else gids[2] if v < 0.78 else gids[3])
            fg_row.append(C.ramp(ramp, v))
        d.warm_gid.append(gid_row)
        d.warm_fg.append(fg_row)
    vessels = []
    vrng = random.Random(707)
    for i in range(26):
        vessels.append((vrng.uniform(2, W - 2), vrng.uniform(0.6, 3.4),
                        vrng.uniform(0, 6.28), vrng.uniform(0.4, 1.4),
                        vrng.random()))
    d.vessels = vessels

    # E5 particles
    dust = []
    prng = random.Random(1017)
    for i in range(150):
        dust.append((prng.random(), prng.uniform(-2.0, 9.0),
                     prng.uniform(-1.0, 1.0), prng.uniform(0.4, 2.6),
                     prng.random(), i))
    d.dust = dust

    # Station B7: rack LEDs
    leds = []
    lrng = random.Random(61)
    for i in range(72):
        leds.append((lrng.randint(66, 198), lrng.randint(6, 49),
                     lrng.uniform(0.4, 2.6), lrng.uniform(0, 6.28),
                     lrng.random()))
    d.leds = leds
    d.rack_x = [70, 88, 106, 124, 142, 160, 178, 196]

    # warm sprites
    d.sun8 = scene.assets.sun(8)
    d.sun12 = scene.assets.sun(12)
    d.sunburst16 = scene.assets.sunburst(16)

    # cache the keyframes once so workers fork with the images decoded
    for name in ("book-cover", "book-open", "desk-reflection", "desk-look",
                 "desk-tap", "desk"):
        keyframe(name)

    scene._s35b = d
    scene._s35b_ready = True


# --------------------------------------------------------------------------
# E1 -- truth or false: hard geometric split screens (123.180-124.100)
# --------------------------------------------------------------------------

def _overlay_telemetry(c, t, seed=3):
    """Sparse logic telemetry: many distinct glyph/colour pairs, film-thin."""
    pal = (CYAN_HI, GOLD_HI, RED_HI, TEXT, TEXT_FAINT, C.CYAN, C.AMBER, WHITE)
    rows = (2, 8, 14, 20, 26, 32, 38, 44, 50)
    syms = ("0", "1", "\u2500", "\u2504", "\u00b7", "\u2502", "+", "/")
    drift = int(t * 17.0)
    for ri, y in enumerate(rows):
        for k in range(7):
            x = (k * 29 + ri * 13 + drift) % W
            ch = syms[(ri * 3 + k) % len(syms)]
            col = pal[(ri * 2 + k * 3) % len(pal)]
            c.put(y, x, ch, col, None)
        if ri % 2 == 0:
            x0 = (ri * 37 + int(t * 60)) % (W - 8)
            run = "01"[(ri // 2) % 2:] + "0110010"
            c.text(y, x0, run, pal[(ri + 1) % len(pal)], None, bold=False)
    for k in range(11):
        x = (k * 19 + 3 + int(t * 9)) % W
        for y in range(4, 51, 7):
            c.put(y, x, "\u2502", pal[(k + 2) % len(pal)], None)


def _e1_split(c, ctx, t, d):
    idx = 0
    for i, cut in enumerate(_SPLIT_CUTS):
        if t >= cut:
            idx = i
    cut_t = _SPLIT_CUTS[idx]
    _clear(c)

    if idx == 0:
        # white / red / ink three-way geometric劈屏 with monumental binaries
        c.fill(Y0, 0, BH, 68, " ", TEXT, WHITE)
        c.fill(Y0, 68, BH, 32, " ", TEXT, C.RED_DEEP)
        c.fill(Y0, 100, BH, 100, " ", TEXT, INK)
        M.big_text(c, Y0 + 6, 0, d.true_sym, INK, scale=5, x1=68,
                   align="center")
        M.big_text(c, Y0 + 6, 100, d.false_sym, WHITE, scale=5, x1=200,
                   align="center")
        c.fill(Y0, 67, BH, 1, " ", TEXT, RED)
        c.fill(Y0, 99, BH, 1, " ", TEXT, CYAN)
        c.text(Y0 + 8, 70, "1", C.mix(WHITE, GOLD_HI, 0.25), None, bold=True)
        c.text(Y1 - 9, 70, "0", C.mix(WHITE, GOLD_HI, 0.25), None, bold=True)
        c.text(Y0 + 2, 3, d.true_tag, C.mix(INK, CYAN_DIM, 0.85), WHITE,
               bold=True)
        c.text(Y0 + 2, 103, d.false_tag, C.mix(WHITE, CYAN_HI, 0.35), INK,
               bold=True)
    elif idx == 1:
        c.fill(Y0, 0, 25, W, " ", TEXT, WHITE)
        c.fill(Y0 + 25, 0, BH - 25, W, " ", TEXT, INK)
        _block(c, Y0 + 3, d.true_tag, INK, scale=3)
        _block(c, Y0 + 30, d.false_tag, WHITE, scale=3)
        c.hline(Y0 + 24, 0, W, CYAN, None, "\u2501")
        c.hline(Y0 + 25, 0, W, RED, None, "\u2501")
        c.text(Y0 + 26, 3, d.true_sym, CYAN_HI, INK)
        c.text(Y0 + 26, W - 5, d.false_sym, RED_HI, INK)
    elif idx == 2:
        br = c.braille(Y0, 0, BH, W)
        for off in (-1, 0, 1):
            br.line(0, 2 + off, 399, 202 + off, WHITE, 0.95, step=0.5)
            br.line(399, 2 + off, 0, 202 + off, CYAN_HI, 0.95, step=0.5)
        br.commit()
        c.text(Y0 + 1, 3, M.spread_text(d.true_tag, 1), WHITE, INK, bold=True)
        c.text(Y1 - 2, W - len(M.spread_text(d.false_tag, 1)) - 3,
               M.spread_text(d.false_tag, 1), CYAN_HI, INK, bold=True)
        c.fill(Y0 + 23, 92, 5, 16, " ", TEXT, RED)
    elif idx == 3:
        slabs = ((0, 56, WHITE), (56, 32, RED_DEEP), (88, 54, CYAN),
                 (142, 58, INK))
        glyphs = (d.true_sym, d.false_sym, d.true_sym, d.false_sym)
        for k, (x0, w, col) in enumerate(slabs):
            c.fill(Y0, x0, BH, w, " ", TEXT, col)
            fg = INK if col in (WHITE, CYAN) else WHITE
            if w >= 34:
                M.big_text(c, Y0 + 6, x0, glyphs[k], fg, scale=4,
                           x1=x0 + w, align="center")
        c.fill(Y0, 141, BH, 1, " ", TEXT, GOLD_HI)
    else:
        c.fill(Y0, 0, BH, W, " ", TEXT, RED_DEEP)
        c.fill(Y0, 0, BH, 90, " ", TEXT, C.mix(RED_DEEP, INK, 0.55))
        _block(c, Y0 + 4, d.true_sym + d.false_sym,
               C.mix(WHITE, GOLD_HI, 0.35), scale=6)
        c.fill(Y0, 90, BH, 10, " ", TEXT, WHITE)
        c.text(Y0 + 2, 3, d.split_banner, C.mix(WHITE, RED_HI, 0.4), None,
               bold=True)

    _overlay_telemetry(c, t)
    _cut(c, t - cut_t, flash=0.12, chroma=0.16, glitch=0.06, shake=1.6,
         decay=0.1)

def _facade_px(quad, u, v, zoom=1.0, focus=None, roll=0.0):
    (ax, ay), (bx, by), (cx, cy), (dx, dy2) = quad
    w = 1.0 - u
    x = w * (1.0 - v) * ax + u * (1.0 - v) * bx + u * v * cx + w * v * dx
    y = w * (1.0 - v) * ay + u * (1.0 - v) * by + u * v * cy + w * v * dy2
    fx, fy = focus if focus is not None else (W * 0.5, BH * 0.5)
    x = fx + (x - fx) * zoom
    y = fy + (y - fy) * zoom
    if roll:
        cr, sr = math.cos(roll), math.sin(roll)
        ox, oy = x - W * 0.5, y - BH * 0.5
        x = W * 0.5 + ox * cr - oy * sr
        y = BH * 0.5 + ox * sr + oy * cr
    return x, y

def _e1_facade(c, ctx, t, d):
    _grad(c, C.mix(INK, C.CYAN_DEEP, 0.35), INK)
    pu = ctx.audio.pulse(t, 0.11)
    noun = t - 124.10
    deduce = M.seg(t, 123.95, 125.60)
    wave = (0.10 + 0.90 * C.ease_in_out(deduce)) * 1.18
    # three distinct camera setups: wide establishing / extreme close / dutch
    if t < 124.86:
        push, focus, roll = 1.0 + 0.10 * M.seg(t, 124.10, 124.86), None, 0.0
        _cut(c, noun, flash=0.10, chroma=0.12, decay=0.09)
    elif t < 125.34:
        push, focus, roll = 3.35, (56.0, 13.0), 0.0
        _cut(c, t - 124.86, flash=0.14, chroma=0.14, decay=0.08)
    else:
        push, focus, roll = 1.55, (100.0, 25.0), 0.13
        _cut(c, t - 125.34, flash=0.14, chroma=0.14, decay=0.08)
    quad = d.facade_quad

    br = c.braille(Y0, 0, BH, W)
    mull = C.mix(CYAN_DIM, WHITE, 0.30)
    for u in d.facade_us:
        x0, y0 = _facade_px(quad, u, 0.0, push, focus, roll)
        x1, y1 = _facade_px(quad, u, 1.0, push, focus, roll)
        br.line(x0 * 2, (y0 - Y0) * 4, x1 * 2, (y1 - Y0) * 4, mull, 0.95,
                step=0.7)
    for v in d.facade_vs:
        x0, y0 = _facade_px(quad, 0.0, v, push, focus, roll)
        x1, y1 = _facade_px(quad, 1.0, v, push, focus, roll)
        br.line(x0 * 2, (y0 - Y0) * 4, x1 * 2, (y1 - Y0) * 4, mull, 0.9,
                step=0.7)
    br.commit()

    for i, j in d.facade_wins:
        vc = (j + 0.5) / 7.0
        passed = vc < wave
        if not passed:
            col = C.mix(INK, C.PANEL3, 0.75)
        else:
            on = M.hash01(i * 3.1, j * 7.7) < 0.56
            front = C.clamp((wave - vc) / 0.16, 0.0, 1.0)
            col = (C.mix(CYAN_HI, WHITE, 0.28 + 0.45 * front * pu) if on
                   else C.mix(INK, CYAN_DIM, 0.55))
        u0, u1 = (i + 0.22) / 9.0, (i + 0.78) / 9.0
        v0, v1 = (j + 0.22) / 7.0, (j + 0.78) / 7.0
        xa, ya = _facade_px(quad, u0, v0, push, focus, roll)
        xb, yb = _facade_px(quad, u1, v1, push, focus, roll)
        if xb <= xa or yb <= ya:
            continue
        yy, xx = int(round(ya)), int(round(xa))
        hh = max(1, int(round(yb - ya)))
        ww = max(1, int(round(xb - xa)))
        c.fill(yy, xx, hh, ww, " ", TEXT, col)
        if passed and ww >= 2 and hh >= 2:
            c.put(yy, xx + ww // 2, "1" if M.hash01(i, j) < 0.5 else "0",
                  C.mix(INK, WHITE, 0.85), col)

    # extreme close: one giant gate trace etched across the frame
    if 124.86 <= t < 125.34:
        gl = d.logic_gates[0]
        _block(c, Y0 + 17, gl, C.mix(CYAN_HI, WHITE, 0.45), scale=4)
        _hair(c, Y1 - 8, 8, W - 8, C.mix(CYAN_HI, WHITE, 0.35))
        c.text(Y1 - 6, 8, M.spread_text(d.logic_truth_hdr, 1),
               C.mix(CYAN_HI, WHITE, 0.25), None, bold=True)

    if 0.02 < wave < 1.1:
        fy = BH * 0.5 + (wave * 1.05 * BH - BH * 0.5) * 0.9
        fy = max(Y0 + 1, min(Y1 - 1, fy))
        _hair(c, int(fy), 0, W, C.mix(CYAN_HI, WHITE, 0.5))
        _hair(c, int(fy) + 1, 0, W, C.mix(CYAN, INK, 0.4))

    _overlay_telemetry(c, t, seed=5)
    c.text(Y0 + 1, 2, d.logic_tag, C.mix(CYAN_HI, WHITE, 0.25), None, bold=True)
    c.text(Y0 + 1, W - len(d.logic_truth_hdr) - 2, d.logic_truth_hdr,
           C.mix(INK, CYAN_HI, 0.6), None)
    c.text(Y1 - 2, 2, d.logic_footer, C.mix(INK, TEXT_FAINT, 0.9), None)

    if t >= 125.86:
        _clear(c, INK)
        _grad(c, INK, C.mix(INK, RED_DEEP, 0.65))
        words = d.logic_verdict.split(": ", 1)
        age = t - 125.86
        drop = int(8.0 * M.hit(age, 0.10))
        fg_top = C.mix(WHITE, CYAN_HI, 0.25)
        M.big_text(c, Y0 + 3 + drop, 0, words[0], RED_HI, scale=2, x1=W,
                   align="center", top=fg_top, bottom=RED_HI)
        if len(words) > 1:
            M.big_text(c, Y0 + 21 + drop, 0, words[1], WHITE, scale=2, x1=W,
                       align="center", top=WHITE, bottom=RED)
        _hair(c, Y0 + 19, 14, W - 14, C.mix(RED_DIM, RED_HI, 0.5))
        _hair(c, Y0 + 39, 14, W - 14, C.mix(RED_DIM, RED_HI, 0.4))
        _overlay_telemetry(c, t, seed=7)
        c.text(Y1 - 3, 4, d.logic_footer, C.mix(RED_DIM, TEXT, 0.6), None)
        _cut(c, age, flash=0.28, chroma=0.34, glitch=0.18, shake=4.0,
             decay=0.10, color=WHITE)

def _square_band(br, t, y0, h, lam, rate, phase, color, gain, alpha=0.9):
    pw = br.cols * 2
    mid = (y0 - Y0) * 4 + h * 2.0
    amp = (h * 0.5 - 1.0) * 4.0 * gain
    phase_t = 2.0 * math.pi * rate * t
    under = C.mix(INK, color, 0.55)
    hot = C.mix(color, WHITE, 0.35)
    fat = alpha > 0.8
    prev = None
    for px in range(0, pw, 2):
        val = 1.0 if math.sin(2.0 * math.pi * px / lam - phase_t + phase) >= 0.0 else -1.0
        py = int(round(mid - val * amp))
        if prev is not None and py != prev[1]:
            br.line(prev[0], prev[1], px, py, hot, alpha, step=0.5)
        for dy, cc, aa in ((0, hot, alpha), (1, color, alpha * 0.9)):
            br.plot(px, py + dy, cc, aa)
            br.plot(px + 1, py + dy, cc, aa)
        if fat:
            br.plot(px, py - 1, under, alpha * 0.8)
            br.plot(px + 1, py - 1, under, alpha * 0.8)
            br.plot(px, py + 2, under, alpha * 0.6)
            br.plot(px + 1, py + 2, under, alpha * 0.6)
        prev = (px, py)
def _strike_columns(br, t, lam, rate, phase, color, cols=42, decay=0.16,
                    boost=0.0):
    pw = br.cols * 2
    ph = br.rows * 4
    speed = lam * rate
    for k in range(cols):
        x = int((k + 0.5) * pw / cols)
        age = ((speed * t - phase * lam / (2.0 * math.pi) - x) % lam) / max(1e-6, speed)
        b = math.exp(-age / decay)
        if b < 0.06:
            continue
        a = min(1.0, b * 1.25 + boost * b)
        col = C.mix(INK, color, min(1.0, a))
        hot = C.mix(INK, WHITE, min(1.0, a * 0.9))
        for py in range(0, ph, 1):
            br.plot(x, py, col, 0.95)
            br.plot(x + 1, py, col, 0.75)
        if b > 0.5:
            for py in range(0, ph, 2):
                br.plot(x + 2, py, hot, 0.55)
                br.plot(x - 1, py, C.mix(INK, color, 0.5), 0.6)


def _e2_waves(c, ctx, t, d):
    _grad(c, INK, C.mix(INK, C.CYAN_DEEP, 0.30))
    pu = ctx.audio.pulse(t, 0.10)
    br = c.braille(Y0, 0, BH, W)
    if t < 126.94:
        for band in d.wave_bands:
            _square_band(br, t, band["y0"], band["h"], band["lam"],
                         band["rate"], band["phase"], band["color"],
                         band["gain"], alpha=1.0)
            yb = (band["y0"] - Y0) * 4 + band["h"] * 2
            for px in range(0, W * 2, 2):
                br.plot(px, yb, C.mix(INK, BORDER, 0.55), 0.5)
        _strike_columns(br, t, 72.0, 1.02, 0.0, CYAN_HI, cols=30, boost=pu)
        _strike_columns(br, t, 92.0, 1.24, 2.7, WHITE, cols=20, boost=pu * 0.7)
        _cut(c, t - T_E2, flash=0.18, chroma=0.18, glitch=0.10, shake=2.0,
             decay=0.1)
    elif t < 127.42:
        # extreme close: one razor square wave fills the screen
        _square_band(br, t, Y0, BH, 150.0, 0.95, 0.0, WHITE, 0.56, alpha=1.0)
        _strike_columns(br, t, 190.0, 0.95, 0.0, CYAN_HI, cols=22,
                        decay=0.22, boost=pu)
        _cut(c, t - 126.94, flash=0.16, chroma=0.18, shake=2.6, decay=0.10)
        c.text_center(Y1 - 6, M.spread_text("RISING EDGE", 2),
                      C.mix(CYAN_HI, WHITE, 0.3), None, bold=True)
    else:
        # dutch: crooked crystal traces across the frame
        slope = 0.055 * math.sin((t - 127.42) * 2.0)
        mid = BH * 2.0
        for k, band in enumerate(d.wave_bands):
            yb = (band["y0"] - Y0) * 4 + band["h"] * 2
            col = band["color"]
            hot = C.mix(col, WHITE, 0.3)
            prev = None
            ph_t = 2.0 * math.pi * band["rate"] * t
            for px in range(0, W * 2, 2):
                val = 1.0 if math.sin(2.0 * math.pi * px / band["lam"]
                                      - ph_t + band["phase"]) >= 0.0 else -1.0
                py = int(round(yb - val * (band["h"] * 2.0) * band["gain"]
                               + (px - W) * slope * 2.0))
                if prev is not None and py != prev[1]:
                    br.line(prev[0], prev[1], px, py, hot, 1.0, step=0.5)
                br.plot(px, py, hot, 1.0)
                br.plot(px, py + 1, col, 0.9)
                prev = (px, py)
        _strike_columns(br, t, 72.0, 1.02, 0.0, CYAN_HI, cols=30, boost=pu)
        _cut(c, t - 127.42, flash=0.16, chroma=0.20, glitch=0.10, shake=3.0,
             decay=0.10)
    br.commit()
    c.text(Y0 + 1, 2, d.clock_channels[0], C.mix(CYAN_HI, WHITE, 0.2), None,
           bold=True)
    c.text(Y0 + 1, W - len(d.clock_title) - 2, d.clock_title,
           C.mix(INK, CYAN_DIM, 0.95), None)
    c.text(Y1 - 2, 2, d.clock_tag, C.mix(INK, CYAN_HI, 0.55), None)
    for i in range(0, W, 5):
        c.put(Y1 - 1, i, "│", C.mix(INK, BORDER_HI, 0.7), None)

def _e2_latch(c, ctx, t, d):
    _grad(c, C.mix(INK, C.CYAN_DEEP, 0.2), INK)
    frozen = t >= 128.80
    tt = min(t, 128.80) if frozen else t
    br = c.braille(Y0, 0, BH, W)
    for i, lane in enumerate(d.latch_lanes):
        y0, h = lane["y0"], lane["h"]
        _square_band(br, tt, y0, h, 96.0, 1.05, lane["phase"],
                     C.mix(INK, CYAN_DIM, 0.8), 0.9, alpha=0.5)
        _square_band(br, tt, y0, h, 192.0, 1.05, lane["phase"] * 0.5,
                     lane["color"], 0.62, alpha=0.95)
    _strike_columns(br, tt, 192.0, 1.05, 0.0, C.mix(CYAN_HI, WHITE, 0.4),
                    cols=14, boost=ctx.audio.pulse(t, 0.1))
    br.commit()

    for i, lane in enumerate(d.latch_lanes):
        y0 = lane["y0"]
        c.text(y0, 2, d.clock_ff[i][:14], C.mix(lane["color"], WHITE, 0.2),
               None, bold=True)
        c.put(y0, 17, "\u25b8", C.mix(lane["color"], INK, 0.35), None)
    c.text(Y0 + 1, W - len(d.clock_title) - 2, d.clock_title,
           C.mix(INK, CYAN_DIM, 0.95), None)
    c.text(Y1 - 2, 2, d.clock_tag, C.mix(INK, CYAN_HI, 0.55), None)
    c.text(Y1 - 2, W - len(d.clock_footer) - 2, d.clock_footer,
           C.mix(INK, TEXT_FAINT, 0.9), None)

    if frozen:
        age = t - 128.80
        c.fill(Y0 + 20, 0, 1, W, " ", TEXT, C.mix(INK, CYAN_DEEP, 0.4))
        _block(c, Y0 + 21, d.clock_armed, C.mix(CYAN_HI, WHITE, 0.45), scale=2)
        _cut(c, age, flash=0.30, chroma=0.24, glitch=0.16, shake=3.2,
             decay=0.13, color=CYAN_HI)


# --------------------------------------------------------------------------
# E3 -- Lissajous curve (129.140-130.090) and overload (130.090-130.790)
# --------------------------------------------------------------------------

def _lissajous(c, ctx, t, d, mode):
    br = c.braille(Y0, 0, BH, W)
    cx = W
    cy = BH * 2.0
    gain = 1.0
    jitter = 0.0
    prog = 1.0
    if mode == "draw":
        prog = M.ease_in_out_expo(M.seg(t, 129.14, 129.86))
    elif mode == "over":
        u = M.seg(t, 130.09, 130.79)
        gain = 1.0 + 2.6 * u * u
        jitter = 7.0 * u
    rx, ry = 176.0, 84.0
    base = d.liss
    n = len(base)
    count = max(2, int(n * prog))
    pts = []
    pu = ctx.audio.pulse(t, 0.1)
    for k in range(count):
        X, Y = base[k]
        jx = 0.0
        jy = 0.0
        if jitter > 0.0:
            jx = (M.noise1(k * 0.11 + t * 17.0, seed=3) - 0.5) * jitter
            jy = (M.noise1(k * 0.13 + t * 19.0, seed=8) - 0.5) * jitter
        pts.append((cx + X * rx * gain * (1.0 + 0.05 * pu) + jx,
                    cy - Y * ry * gain + jy))
    if mode == "over":
        for (off, col) in ((-5.0, C.mix(INK, CYAN, 0.75)),
                           (5.0, C.mix(INK, RED_HI, 0.8))):
            for k in range(0, count, 2):
                x, y = pts[k]
                br.plot(int(x + off), int(y), col, 0.55)
    if mode == "draw":
        probe = C.mix(INK, CYAN_HI, 0.30)
        for k in range(1, len(d.liss2), 3):
            X, Y = d.liss2[k]
            br.plot(int(cx + X * rx * gain), int(cy - Y * ry * gain),
                    probe, 0.35)
    if mode == "over":
        col = C.mix(RED_HI, WHITE, 0.30)
        glow = C.mix(BLOOD, RED_HI, 0.55)
    else:
        col = C.mix(CYAN_HI, WHITE, 0.25)
        glow = C.mix(INK, col, 0.45)
    for k in range(1, count):
        br.line(pts[k - 1][0], pts[k - 1][1] + 1, pts[k][0], pts[k][1] + 1,
                glow, 0.7, step=0.5)
    for k in range(1, count):
        br.line(pts[k - 1][0], pts[k - 1][1], pts[k][0], pts[k][1], col, 1.0,
                step=0.4)
    if mode == "draw" and prog < 1.0:
        hx, hy = pts[-1]
        for dx, dy in ((0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (-1, 0), (0, -1)):
            br.plot(int(hx) + dx, int(hy) + dy, WHITE, 1.0)
        for dx, dy in ((3, 0), (0, 3), (-2, 0), (0, -2)):
            br.plot(int(hx) + dx, int(hy) + dy, CYAN_HI, 0.55)
    br.commit()
    return prog

def _e3_liss(c, ctx, t, d):
    _clear(c)
    c.vline(W // 2, Y0, Y1, C.mix(INK, CYAN_DEEP, 0.8), None, "│")
    # GENERATE: huge, half off the left edge, the pen draws over it
    M.big_text(c, Y0 + 9, -48, d.blood_words[0],
               C.mix(INK, CYAN_DIM, 0.60), scale=3)
    prog = _lissajous(c, ctx, t, d, "draw")
    c.text(Y1 - 2, 2, d.blood_osc[0], C.mix(CYAN, INK, 0.35), None)
    c.text(Y1 - 2, W - len(d.blood_tag) - 2, d.blood_tag,
           C.mix(INK, CYAN_HI, 0.5), None)
    if prog > 0.985:
        _cut(c, t - 129.86, flash=0.10, chroma=0.10, decay=0.1)

def _e3_over(c, ctx, t, d):
    _clear(c)
    _lissajous(c, ctx, t, d, "over")
    word = d.blood_words[1]
    half = max(3, len(word) * 2 // 5)
    top, bottom = word[:half], word[half:]
    col = C.mix(RED_HI, WHITE, 0.18)
    # split word: top-left / bottom-right, the torn wave slashes between them
    M.big_text(c, Y0 + 1, -5, top, col, scale=3)
    M.big_text(c, Y1 - 22, 0, bottom, col, scale=3, x1=W - 6,
               align="right")
    c.text(Y1 - 2, 2, d.blood_osc[1], C.mix(RED, INK, 0.3), None)
    _cut(c, t - T_OVER_END, flash=0.34, chroma=0.34, glitch=0.24, shake=4.5,
         decay=0.16, color=RED_HI)
    _cut(c, t - 130.233, flash=0.20, chroma=0.20, glitch=0.14, shake=2.0,
         decay=0.1, color=RED_HI)

def _e3_flood(c, ctx, t, d):
    _grad(c, C.mix(INK, C.RED_DEEP, 0.15), C.mix(INK, C.RED_DEEP, 0.70))
    u = M.seg(t, 130.79, 132.13)
    F = C.ease_out_quad(u)
    pu = ctx.audio.pulse(t, 0.09)
    bass = ctx.audio.bass(t)

    x0, x1, row, ph = d.pipe_main
    body0, body1 = row + 1, row + ph - 1
    main_full = C.clamp(F / 0.30, 0.0, 1.0)
    shell = C.mix(CYAN_DIM, CYAN, 0.55)
    for xx in range(x0, x1 + 1, 1):
        if xx % 2 == 0:
            c.put(row, xx, "\u2550", shell, None)
            c.put(row + ph - 1, xx, "\u2550", shell, None)
    for yy in range(row + 1, row + ph - 1):
        c.put(x0, yy, "\u2551", shell, None)
        c.put(x1, yy, "\u2551", shell, None)

    lit = int(x0 + 1 + main_full * (x1 - x0 - 2))
    for yy in range(body0, body1 + 1):
        c.put(yy, x0, "\u2551", shell, None)
        c.put(yy, x1, "\u2551", shell, None)
        c.fill(yy, x0 + 1, 1, max(0, lit - x0 - 1), "\u2588",
               C.mix(BLOOD, RED_HI, 0.20), C.mix(INK, C.RED_DEEP, 0.35))
    if main_full < 1.0:
        crest = lit
        for yy in range(body0, body1 + 1):
            wob = int(round(0.5 + 0.5 * math.sin(yy * 1.7 + t * 6.0 + bass * 3)))
            c.put(yy, crest + wob, "\u2588", C.mix(RED_HI, WHITE, 0.6), None)
            c.put(yy, crest + wob + 1, "\u2592", C.mix(RED_HI, BLOOD_HI, 0.5), None)

    for i, (rx, top) in enumerate(d.pipe_risers):
        frac = C.clamp((F - (0.32 + i * 0.105)) / 0.10, 0.0, 1.0)
        for yy in range(top, row, 1):
            c.put(yy, rx - 1, "\u2551", shell, None)
            c.put(yy, rx + 1, "\u2551", shell, None)
        if frac > 0.0:
            yf = int(row - frac * (row - top))
            for yy in range(max(top, yf), row):
                col_r = C.mix(BLOOD, RED_HI, 0.16 + 0.45 * frac)
                c.put(yy, rx, "\u2588", col_r, C.mix(INK, C.RED_DEEP, 0.35))
                c.put(yy, rx + 1, "\u2588", C.mix(col_r, INK, 0.25),
                      C.mix(INK, C.RED_DEEP, 0.35))
            if frac < 1.0:
                wob = int(round(math.sin(t * 7.0 + i) * 1.2))
                c.hline(max(top, yf + wob), rx - 1, rx + 2,
                        C.mix(RED_HI, WHITE, 0.6), None, "\u2500")
        gcol = C.mix(CYAN_DIM, CYAN, 0.35 + 0.6 * frac)
        bl, br_ = rx - 7, rx + 7
        gtop = top - 8
        c.hline(gtop, bl, br_ + 1, gcol, None, "\u2550")
        c.hline(gtop + 6, bl, br_ + 1, gcol, None, "\u2550")
        for yy in range(gtop + 1, gtop + 6):
            c.put(yy, bl, "\u2551", gcol, None)
            c.put(yy, br_, "\u2551", gcol, None)
        gl = d.logic_gates[(i * 3) % len(d.logic_gates)]
        c.text(gtop + 2, rx - len(gl) // 2, gl,
               C.mix(WHITE if frac > 0.5 else CYAN_DIM, RED_HI, 0.25), None,
               bold=frac > 0.5)
        if frac > 0.4:
            c.fill(gtop + 3, rx - 5, 2, 10, " ", TEXT,
                   C.mix(C.mix(INK, BLOOD, 0.6), RED_HI, 0.35 * frac))

    c.text(Y0 + 1, 2, d.blood_tag, C.mix(RED_HI, WHITE, 0.3), None, bold=True)
    c.text(row - 2, 4, d.blood_fill + " %5.1f%%   " % (F * 100.0)
           + d.blood_pressure + " %4d kPa" % int(380 + 237 * F),
           C.mix(RED_HI, TEXT, 0.45), None)
    c.text(Y1 - 2, 2, d.blood_footer, C.mix(INK, TEXT_FAINT, 0.95), None)
    _block(c, Y1 - 15, d.blood_words[2], C.mix(RED_HI, WHITE, 0.20), scale=2, bg=INK)
    if t >= 131.86:
        age = t - 131.86
        c.fill(Y0 + 28, 0, 1, W, " ", TEXT, C.mix(INK, BLOOD, 0.85))
        c.text_center(Y0 + 28, d.blood_banner, C.mix(WHITE, RED_HI, 0.4), None,
                      bold=True)
        rng = random.Random(int(t * 60) ^ 617)
        br = c.braille(Y0, 0, BH, W)
        for k in range(26):
            a = rng.uniform(-2.5, -0.4)
            sp = rng.uniform(12, 46)
            px = 98 * 2 + math.cos(a) * sp * (0.3 + age * 2.2) * 2
            py = 42 * 4 - math.sin(-a) * sp * (0.3 + age * 2.2)
            br.plot(int(px), int(py), C.mix(RED_HI, WHITE, rng.random()), 0.8)
        br.commit()
        _cut(c, age, flash=0.22, chroma=0.2, glitch=0.12, shake=2.4,
             decay=0.1, color=RED_HI)


def _e4_spin(c, ctx, t, d):
    _grad(c, INK, C.mix(INK, C.CYAN_DEEP, 0.40))
    p = M.seg(t, T_E4, T_SPIN_END)
    pu = ctx.audio.pulse(t, 0.1)
    br = c.braille(Y0, 0, BH, W)
    pw, ph = W * 2, BH * 4
    hubx, huby = pw * 0.88, ph * 0.5
    lock = C.clamp((p - 0.78) / 0.20, 0.0, 1.0)
    wave_amp = ph * 0.075 * (1.0 - lock)
    for i in range(8):
        row = (i + 0.5) / 8.0 * ph
        on = (i == 5)
        col = C.mix(GOLD_HI, WHITE, 0.25) if on else C.mix(CYAN_HI, WHITE, 0.30)
        pts = []
        n = 24
        for k in range(n + 1):
            uu = k / float(n)
            px = 8 + (hubx - 8) * uu
            py = row * (1.0 - uu) + huby * uu
            py += math.sin(uu * math.pi * 2.4 + t * 3.4 + i * 0.7) * wave_amp
            pts.append((px, py))
        for k in range(1, len(pts)):
            br.line(pts[k - 1][0], pts[k - 1][1], pts[k][0], pts[k][1], col,
                    0.95, step=0.6)
        fr = (t * 0.75 + i * 0.125) % 1.0
        idx = int(fr * n)
        c0 = WHITE if not on else GOLD_HI
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1), (-1, 0)):
            br.plot(int(pts[idx][0]) + dx, int(pts[idx][1]) + dy, c0, 0.95)
        cy = int(row / 4) + Y0
        if 2 <= cy < Y1:
            c.text(cy, 1, "CH-%02d" % i,
                   GOLD_HI if on else C.mix(CYAN, INK, 0.25), None, bold=on)
    br.circle(hubx, huby, 14, C.mix(CYAN_HI, WHITE, 0.4), 0.85)
    br.circle(hubx, huby, 7, GOLD_HI, 0.9)
    br.commit()
    c.text(Y0 + 1, W - len(d.mux_title) - 2, d.mux_title,
           C.mix(INK, CYAN_HI, 0.6), None)
    c.text(Y0 + 1, 2, d.mux_tag, C.mix(CYAN_HI, WHITE, 0.3), None, bold=True)
    if pu > 0.4:
        c.fx.shake_x += 0.8 * pu
    _cut(c, t - T_E4, flash=0.14, chroma=0.16, decay=0.09)

def _etched(c, y, x, text, scale, reveal, cold, hot):
    cursor = x
    for ch in text.upper():
        glyph = M.BIG_FONT.get(ch)
        if glyph is None:
            glyph = ("     ",) * 7
        for py, row in enumerate(glyph):
            for px, bit in enumerate(row):
                if bit == " ":
                    continue
                gx = cursor + px * scale
                for sy in range(scale):
                    for sx in range(scale):
                        xx = gx + sx
                        if xx > reveal:
                            continue
                        col = hot if (reveal - xx) < 4 else cold
                        c.put(y + py * scale + sy, xx, "\u2588", col, None)
        cursor += 5 * scale + scale



def _e4_lock(c, ctx, t, d):
    _grad(c, C.mix(INK, C.CYAN_DEEP, 0.30), INK)
    age = t - T_SPIN_END
    # cold backlight raking across the etched plate
    for yy in range(Y0, Y1):
        u = (yy - Y0) / float(BH)
        c.fill_bg(yy, 104, 1, W - 104, C.mix(INK, C.CYAN_DEEP, 0.10 + 0.14 * u))
    for i in range(8):
        yy = d.mux_rows[i]
        on = (i == 5)
        col = GOLD_HI if on else C.mix(CYAN, WHITE, 0.30)
        c.hline(yy, 8, 100, col, None, "\u2501" if on else "\u2500")
        c.text(yy, 2, "CH-%02d" % i, C.mix(col, WHITE, 0.55), None, bold=on)
        c.put(yy, 100, "\u25cf", col, None)
        if on:
            for k in range(6):
                c.put(yy, 104 + k * 2, "\u2500", C.mix(GOLD_HI, INK, 0.25), None)
    c.vline(100, Y0 + 1, Y1 - 1, C.mix(CYAN_HI, WHITE, 0.4), None, "\u2503")
    for i in range(8):
        c.put(d.mux_rows[i], 100, "\u25c6", GOLD_HI if i == 5 else CYAN_HI, None)

    scale = 5
    pid_w, pid_h = M.big_text_size(d.pid, scale)
    px = 110
    py = Y0 + (BH - pid_h) // 2
    reveal = int(102 + (W - 102) * M.ease_out_expo(
        M.seg(t, T_SPIN_END + 0.02, T_SPIN_END + 0.62)))
    _etched(c, py, px, d.pid, scale, reveal,
            cold=C.mix(CYAN_HI, WHITE, 0.55), hot=WHITE)
    if reveal >= px + pid_w:
        c.hline(py + pid_h + 1, px, px + pid_w, C.mix(CYAN, WHITE, 0.3), None)
        c.text(py + pid_h + 3, px, "PID " + d.pid,
               C.mix(CYAN_HI, WHITE, 0.4), None, bold=True)
        # registration sweep across the plate
        sx = 104 + int(((t - T_SPIN_END) * 260.0) % (W - 104))
        c.vline(sx, Y0 + 1, Y1 - 1, C.mix(INK, CYAN_DIM, 0.55), None, "\u2502")
    c.text(Y1 - 2, 2, d.mux_footer, C.mix(INK, TEXT_FAINT, 0.9), None)
    c.text(Y0 + 1, 2, d.reg_title, C.mix(CYAN_HI, WHITE, 0.25), None, bold=True)
    c.text(Y1 - 2, W - len(d.mux_route) - 2, d.mux_route,
           C.mix(GOLD_DIM, GOLD_HI, 0.55), None, bold=True)
    if t >= T_SPIN_END + 0.55:
        _block(c, Y0 + 2, d.mux_stamp, C.mix(GOLD_HI, WHITE, 0.25), scale=1,
               x1=100)
    _cut(c, age, flash=0.40, chroma=0.36, glitch=0.26, shake=6.0, decay=0.18,
         color=WHITE)


def _e5_wipe(c, ctx, t, d):
    u = M.seg(t, T_E5, 138.10)
    pu = ctx.audio.pulse(t, 0.12)
    p = 0.86 * u + 0.14 * C.ease_in_out(u)
    p = C.clamp(p + 0.012 * pu, 0.0, 1.0)
    blade_y = Y0 + int(round(p * (BH - 1)))

    c.fill(Y0, 0, BH, W, " ", TEXT, WHITE)
    for i in range(BH):
        yy = Y0 + i
        if yy < blade_y:
            continue
        c.ch[yy][0:W] = d.warm_gid[i]
        c.fg[yy][0:W] = d.warm_fg[i]
        bgc = C.mix(INK, C.RED_DEEP, 0.30)
        c.bg[yy][0:W] = [bgc] * W
    # organic vessels still pulsing under the blade
    if blade_y < Y1:
        br = c.braille(Y0, 0, BH - 1, W)
        for k in range(len(d.vessels)):
            x0c, amp, phase, speed, hot = d.vessels[k]
            base_y = (blade_y - Y0) * 4
            for py in range(max(0, base_y), BH * 4 - 2, 3):
                px = x0c * 2 + math.sin(py * 0.07 + phase + t * speed) * amp * 2
                col = C.mix(BLOOD_HI, RED_HI, hot)
                br.plot(int(px), py, col, 0.55)
        br.commit()
    # grind zone: cold dust where the blade bites
    for k in range(1, 7):
        yy = blade_y + k
        if yy >= Y1:
            break
        weigh = 1.0 - k / 7.0
        row = d.warm_fg[yy - Y0]
        c.fg[yy][0:W] = [C.mix(col, WHITE, 0.40 + 0.55 * weigh) for col in row]
    # the blade: a cold surgical line with a heat bloom
    c.fill(blade_y, 0, 1, W, "\u2584", C.mix(CYAN, WHITE, 0.55 + 0.3 * pu), WHITE)
    if blade_y + 1 < Y1:
        c.fill(blade_y + 1, 0, 1, W, "\u2591", C.mix(WHITE, CYAN_DIM, 0.35), WHITE)
    # dust drawn up into the sterile field
    for i in range(140):
        xf, off, drift, speed, size, seed = d.dust[i]
        age = (u * 4.8 + i * 0.137) % 0.55
        yy = blade_y - int(off + age * speed * 3.2)
        xx = int(xf * W + drift * age * 30.0 + math.sin(age * 9.0 + i) * 2.0)
        if Y0 < yy < Y1 and 0 <= xx < W:
            a = max(0.0, 1.0 - age / 0.55)
            col = C.mix(WHITE, C.mix(C.CYAN_DIM, TEXT_FAINT, 0.55), 0.25 + 0.7 * a)
            c.put(yy, xx, "\u00b7" if size < 0.5 else "\u2591", col, WHITE)
    rng = random.Random(int(t * 60) ^ 0x51F)
    for i in range(50):
        xx = rng.randrange(W)
        yy = blade_y + rng.randint(0, 2)
        if Y0 < yy < Y1:
            c.put(yy, xx, "\u2592", C.mix(WHITE, CYAN_HI, rng.random() * 0.55),
                  WHITE)

    if t < 136.0:
        c.text(Y0 + 1, 2, d.purge_tag, C.mix(INK, RED_DIM, 0.75), WHITE,
               bold=True)
        c.text(Y1 - 2, 2, d.purge_laser, C.mix(CYAN_DIM, INK, 0.25), WHITE)
    else:
        c.text(Y1 - 2, 2, d.purge_mill, C.mix(CYAN_DIM, INK, 0.20), WHITE)

    if p >= 0.999:
        _clear(c, WHITE)
        c.text(Y0 + 3, 3, d.purge_tag, C.mix(WHITE, C.CYAN_DIM, 0.88), WHITE)
        _block(c, Y0 + 17, d.purge_stamp, C.mix(WHITE, C.CYAN_DIM, 0.86), scale=2,
               spacing=3)
        c.text_center(Y0 + 34, d.purge_state,
                      C.mix(WHITE, C.CYAN_DIM, 0.82), WHITE)
        c.text_center(Y1 - 3, d.purge_output,
                      C.mix(WHITE, C.CYAN_DIM, 0.75), WHITE)
        rem = C.clamp(1.0 - M.seg(t, 137.95, 138.60), 0.0, 1.0)
        if rem > 0.0:
            c.text_center(Y1 - 6, d.purge_removed[0],
                          C.mix(WHITE, C.RED_DIM, 0.6 * rem), WHITE)
    else:
        _cut(c, t - T_E5, flash=0.30, chroma=0.16, shake=2.0, decay=0.12,
             color=WHITE)


def _f1_hammer(c, ctx, t, d):
    _grad(c, INK, C.mix(INK, C.RED_DEEP, 0.92))
    hits = (T_F1, 139.465, 139.980)
    lines = d.hammer_lines
    idx = 0
    for i, h in enumerate(hits):
        if t >= h:
            idx = i
    h_t = hits[idx]
    age = t - h_t
    line = lines[idx]
    scale = 4 if len(line) <= 7 else 3
    drop = int(9.0 * M.hit(age, 0.09))
    bh = 7 * scale
    band_y = Y0 + (BH - bh) // 2 - 2
    c.fill(band_y, 0, bh + 4, W, " ", TEXT,
           C.mix(INK, C.BLOOD, 0.42 + 0.28 * M.hit(age, 0.16)))
    _hair(c, band_y - 1, 0, W, C.mix(INK, BLOOD_HI, 0.65))
    _hair(c, band_y + bh + 3, 0, W, C.mix(INK, BLOOD_HI, 0.45))
    # deep cast shadow then the struck steel
    M.big_text(c, band_y + 4 + drop, 2, line, C.mix(INK, C.BLOOD, 0.55),
               scale=scale, x1=W, align="center")
    M.big_text(c, band_y + 2 + drop, 0, line, WHITE, scale=scale, x1=W,
               align="center", top=C.mix(WHITE, GOLD_HI, 0.15),
               bottom=C.mix(RED_HI, WHITE, 0.15))
    for k in range(idx):
        c.text_center(Y0 + 2 + k * 3, M.spread_text(lines[k], 2),
                      C.mix(INK, BLOOD_HI, 0.65), None)
    c.text(Y0 + 1, 2, d.hammer_tag, C.mix(WHITE, RED_HI, 0.45), None, bold=True)
    c.text_center(Y1 - 2, d.hammer_preamble, C.mix(TEXT, BLOOD_HI, 0.35), None)
    c.text(Y1 - 1, W - len(d.hammer_seal) - 2, d.hammer_seal,
           C.mix(INK, RED_HI, 0.65), None)
    _cut(c, age, flash=0.42, glitch=0.12, chroma=0.26, shake=8.0, decay=0.13,
         color=WHITE)

def _book_sprite(rows, cols, name, zoom, center, bright=1.0, sat=1.0):
    return camera_sprite(keyframe(name), rows, cols, zoom=zoom, center=center,
                         bright=bright, sat=sat, contrast=1.04)



def _g_cover(c, ctx, t, d):
    u = M.seg(t, T_G, T_COVER_END)
    zoom = 1.02 + 0.10 * M.ease_in_out_expo(u)
    sp = _book_sprite(66, W, "book-cover", zoom, (0.47 + 0.03 * u, 0.50),
                      bright=1.08)
    c.sprite(Y0 - 8, 0, sp, fg_mul=0.94)
    M.vignette(c, 0.30)
    c.text(Y0 + 1, 3, d.book_tag, C.mix(GOLD_HI, WHITE, 0.3), None, bold=True)
    c.text(Y0 + 1, W - len(d.book_cover_sub) - 3, d.book_cover_sub,
           C.mix(GOLD_HI, TEXT, 0.4), None, bold=True)
    _block(c, Y1 - 16, d.book_open, C.mix(GOLD_HI, WHITE, 0.35), scale=2,
           spacing=2, bg=INK)
    c.text_center(Y1 - 2, M.spread_text(d.book_cover_title, 1),
                  C.mix(GOLD_HI, TEXT, 0.45), INK)
    if t >= T_COVER_END - 0.18:
        c.fx.flash = max(c.fx.flash, 0.5)
        c.fx.flash_color = GOLD_HI


def _g_flip(c, ctx, t, d):
    u = M.seg(t, T_COVER_END, T_FLIP_END)
    q = M.ease_out_expo(M.seg(t, T_COVER_END, T_FLIP_END - 0.55))
    page = int(round(1 + (int(d.book_page_number) - 1) * q))
    sp = _book_sprite(66, W, "book-open", 1.04 + 0.06 * u, (0.5, 0.52),
                      bright=1.18)
    c.sprite(Y0 - 8, 0, sp, fg_mul=0.94)
    c.dim(Y0, 0, BH, W, 0.18)
    M.vignette(c, 0.32)
    br = c.braille(Y0, 0, BH, W)
    for k in range(8):
        ph = (u * 3.6 + k * 0.121) % 1.0
        cx = W * 2 * (0.06 + 0.86 * ph)
        cy = BH * 4 * 0.52
        rr = 46 + 40 * math.sin(ph * math.pi)
        start = -1.2 + ph * 2.4
        pts = []
        for i in range(22):
            a = start + i / 21.0 * 1.7
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr * 2.0))
        col = C.mix(GOLD_HI, WHITE, 0.3 + 0.4 * (1.0 - ph))
        for i in range(1, len(pts)):
            br.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1],
                    col, 0.95, step=0.5)
    br.commit()
    # turning page: a bright paper edge sweeping across the plate
    turn = u * 8.0
    edge_u = (u * 1.9) % 1.0
    ex = int(W * (0.06 + 0.86 * edge_u))
    for k in range(3):
        c.vline(ex + k, Y0 + 2, Y1 - 2,
                C.mix(WHITE, GOLD_HI, 0.25 + 0.25 * k), None,
                "\u2593" if k == 0 else "\u2592")
    # page counter etched straight into the paper margin (no HUD plate)
    ink_gold = C.mix(GOLD_DIM, INK, 0.45)
    M.big_text(c, Y0 + 2, 0, "%03d" % page, ink_gold, scale=2, x1=196,
               align="right")
    c.text(Y0 + 2, 148, d.book_page, C.mix(GOLD_DIM, INK, 0.55), None,
           bold=True)
    c.text(Y0 + 17, 148, d.book_page + " " + d.book_page_number,
           C.mix(GOLD_DIM, INK, 0.60), None, bold=True)
    c.text_center(Y1 - 6, M.spread_text(d.book_cover_title, 1),
                  C.mix(GOLD_HI, TEXT, 0.45), INK)
    c.text(Y0 + 1, 3, d.book_banner, C.mix(GOLD_HI, WHITE, 0.4), None,
           bold=True)
    frac_t = turn - math.floor(turn)
    if frac_t < 0.16:
        c.fx.flash = max(c.fx.flash, 0.14 * (1.0 - frac_t / 0.16))
        c.fx.flash_color = C.mix(WHITE, GOLD_HI, 0.4)
    if t >= T_FLIP_END - 0.42:
        _cut(c, t - (T_FLIP_END - 0.42), flash=0.40, chroma=0.2, shake=2.0,
             decay=0.18, color=GOLD_HI)

def _codex_column(c, x0, w, title, header, article, formulas, accent, bg, row0):
    c.text(row0, x0, header[:w], C.mix(accent, WHITE, 0.3), bg, bold=True)
    c.text(row0 + 2, x0, title[:w], accent, bg, bold=True)
    yy = row0 + 4
    for line in wrap(article, w):
        c.text(yy, x0, line, C.mix(accent, WHITE, 0.35), bg, bold=True)
        yy += 1
    yy += 1
    for formula in formulas:
        for line in wrap(formula, w):
            c.text(yy, x0, line, C.mix(C.TEXT_HI, accent, 0.15), bg)
            yy += 1
        yy += 1



def _g_codex(c, ctx, t, d, closing=False):
    u = M.seg(t, T_FLIP_END, T_CODEX_END)
    emblem = 146.55 <= t < 148.05
    if emblem:
        zoom = 1.30 + 0.10 * C.ease_in_out(M.seg(t, 146.55, 148.05))
        dim = 0.62
    else:
        zoom = 1.05 + 0.05 * C.ease_in_out(u)
        dim = 0.48
    sp = _book_sprite(66, W, "book-open", zoom, (0.5, 0.505), bright=1.16)
    c.sprite(Y0 - 8, 0, sp, fg_mul=0.94)
    for yy in range(Y0, Y1):
        c.dim(yy, 0, 1, W, dim)
    ink_teal = C.mix(CYAN_DEEP, INK, 0.25)
    ink_red = C.mix(RED_DEEP, INK, 0.20)
    ink_gold = C.mix(GOLD_DEEP, INK, 0.15)
    ink_brown = C.mix(BROWN_DIM, INK, 0.35)

    if emblem:
        # closer crop: the sunflower seal of the codex
        c.sprite(Y0 + 9, W // 2 - d.sunburst16.w // 2, d.sunburst16,
                 alpha=0.55, tint=GOLD_HI, tint_amt=0.25)
        c.sprite(Y0 + 13, W // 2 - d.sun12.w // 2, d.sun12, alpha=0.96,
                 tint=GOLD_HI, tint_amt=0.14)
        br = c.braille(Y0, 0, BH, W)
        cx, cy = W, BH * 2.0
        for rr, col in ((74.0, C.mix(INK, GOLD_HI, 0.35)),
                        (58.0, C.mix(INK, CYAN_HI, 0.25)),
                        (96.0, C.mix(INK, RED_HI, 0.22))):
            br.circle(cx, cy, rr, col, 0.45)
        br.commit()
        c.text_center(Y0 + 33, M.spread_text(d.book_sun, 2), ink_gold, None,
                      bold=True)
        c.text_center(Y0 + 36, M.spread_text(d.book_runes, 1), ink_gold, None,
                      bold=True)
        c.text_center(Y0 + 39, d.book_page_label + d.book_page_number
                      + "   " + d.book_page + " " + d.book_page_number,
                      C.mix(ink_gold, RED_DEEP, 0.45), None, bold=True)
        c.text(Y0 + 1, 3, d.book_banner, C.mix(GOLD_HI, WHITE, 0.40), None,
               bold=True)
        c.text(Y0 + 1, W - len(d.book_cover_title) - 3, d.book_cover_title,
               C.mix(GOLD_HI, TEXT, 0.45), None, bold=True)
        _cut(c, t - 146.55, flash=0.14, chroma=0.14, decay=0.12, color=GOLD_HI)
    else:
        left_x, col_w = 13, 78
        right_x = 109
        c.text(Y0 + 5, left_x, d.book_left_header[:col_w], ink_gold, None, bold=True)
        c.text(Y0 + 5, right_x, d.book_right_header[:col_w], ink_gold, None, bold=True)
        c.text(Y0 + 7, left_x, d.book_left_title[:col_w], ink_brown, None, bold=True)
        c.text(Y0 + 7, right_x, d.book_right_title[:col_w], ink_red, None, bold=True)
        _hair(c, Y0 + 9, left_x, left_x + col_w, C.mix(INK, GOLD_DIM, 0.9))
        _hair(c, Y0 + 9, right_x, right_x + col_w, C.mix(INK, GOLD_DIM, 0.9))
        yy = Y0 + 11
        for line in wrap(d.book_article_i, col_w):
            c.text(yy, left_x, line, ink_teal, None, bold=True)
            yy += 1
        yy += 1
        for formula in d.book_formulas[:2]:
            for line in wrap(formula, col_w):
                c.text(yy, left_x, line, ink_brown, None)
                yy += 1
            yy += 1
        yy = Y0 + 11
        for line in wrap(d.book_article_dcxvii, col_w):
            c.text(yy, right_x, line, ink_red, None, bold=True)
            yy += 1
        yy += 1
        for formula in d.book_formulas[2:]:
            for line in wrap(formula, col_w):
                c.text(yy, right_x, line, ink_brown, None)
                yy += 1
            yy += 1
        for yy in range(Y0 + 5, Y1 - 6):
            c.put(yy, 99, "│", C.mix(INK, GOLD_DIM, 0.75), None)
            c.put(yy, 100, "│", C.mix(INK, GOLD_DIM, 0.55), None)
        c.sprite(Y0 + 27, W // 2 - d.sun8.w // 2, d.sun8, alpha=0.95,
                 tint=GOLD_HI, tint_amt=0.10)
        c.text_center(Y0 + 36, d.book_sun, ink_gold, None, bold=True)
        pu = ctx.audio.pulse(t, 0.12)
        br = c.braille(Y0, 0, BH, W)
        rng = random.Random(int(t * 45) ^ 0x617)
        for k in range(7):
            y0 = (Y0 + 12 + k * 3) * 4
            jag = rng.uniform(-1.0, 1.0) * (2.0 + 5.0 * pu)
            pts = []
            n = 8
            for i in range(n + 1):
                uu = i / n
                pts.append((W - 22 + uu * 44 + jag * math.sin(uu * math.pi * 3),
                            y0 + (i % 2) * 3 - 1))
            for i in range(1, len(pts)):
                br.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1],
                        C.mix(RED_HI if k % 2 else CYAN_HI, WHITE, 0.5), 0.45)
        br.commit()
        _hair(c, Y0 + 39, 12, W - 12, C.mix(INK, GOLD_DIM, 0.9))
        c.text_center(Y0 + 40, M.spread_text(d.book_runes, 1), ink_gold, None,
                      bold=True)
        c.text_center(Y0 + 42, d.book_page_label + d.book_page_number + "   "
                      + d.book_page + " " + d.book_page_number,
                      C.mix(ink_gold, RED_DEEP, 0.45), None, bold=True)
        c.text(Y0 + 1, 3, d.book_banner, C.mix(GOLD_HI, WHITE, 0.35), None,
               bold=True)
        c.text(Y0 + 1, W - len(d.book_cover_title) - 3, d.book_cover_title,
               C.mix(GOLD_HI, TEXT, 0.4), None, bold=True)
        c.text(Y1 - 1, 3, d.book_tag, C.mix(INK, GOLD_HI, 0.6), None)
        _cut(c, t - 144.66, flash=0.14, chroma=0.10, decay=0.14, color=GOLD_HI)

    cu = M.seg(t, T_CLOSE, T_STATION)
    if cu > 0.0:
        opening = 1.0 - C.ease_in_out(cu)
        visible = max(2, int(round(W * opening)))
        dst = (W - visible) // 2
        for yy in range(Y0, Y1):
            src_ch = c.ch[yy][:]
            src_fg = c.fg[yy][:]
            src_bg = c.bg[yy][:]
            new_ch = []
            new_fg = []
            new_bg = []
            for i in range(visible):
                sx = min(W - 1, i * W // visible)
                new_ch.append(src_ch[sx])
                new_fg.append(C.mix(GOLD_DIM, src_fg[sx], opening))
                new_bg.append(C.mix(INK, src_bg[sx], opening))
            c.fill(yy, 0, 1, W, " ", TEXT, INK)
            c.ch[yy][dst:dst + visible] = new_ch
            c.fg[yy][dst:dst + visible] = new_fg
            c.bg[yy][dst:dst + visible] = new_bg
        if cu > 0.86:
            c.fill(Y0, 0, BH, W, " ", TEXT, INK)
        if 149.15 <= t < 149.55:
            age = t - 149.15
            c.fx.flash = max(c.fx.flash, 0.30 * math.exp(-age / 0.1))
            c.fx.flash_color = GOLD_DIM
            c.fx.shake_y = 4.0 * math.exp(-age / 0.1)

def _station_bg(c, ctx, t, d):
    _grad(c, C.mix(INK, C.INK2, 0.5), INK)
    for x in d.rack_x:
        for yy in range(Y0 + 3, Y1 - 2, 2):
            if M.hash01(x, yy) > 0.55:
                c.put(yy, x, "\u2502", C.mix(INK, C.BORDER, 0.7), None)
    for x, yy, speed, phase, kind in d.leds:
        b = 0.35 + 0.65 * max(0.0, math.sin(t * speed + phase))
        if kind > 0.75:
            col = C.mix(INK, GOLD_DIM, b)
            ch = "\u00b7"
        elif kind > 0.4:
            col = C.mix(INK, C.CYAN_DIM, b * 0.9)
            ch = "\u00b7"
        else:
            col = C.mix(INK, C.GREEN_DIM, b * 0.8)
            ch = "\u2022"
        c.put(yy, x, ch, col, None)
    for x in range(150, W):
        u = (x - 150) / (W - 150)
        c.fill_bg(Y0 + 6, x, BH - 12, 1,
                  C.mix(INK, C.CYAN_DEEP, 0.20 * (1.0 - u)))


def _stage_image(c, t, name, zoom, center, bright=1.15, tint=None, tint_amt=0.0):
    sp = camera_sprite(keyframe(name), 44, C.STAGE_W - 4, zoom=zoom,
                       center=center, bright=bright, sat=1.06, contrast=1.05)
    y, x = 6, C.STAGE_X + 2
    c.sprite(y, x, sp, tint=tint, tint_amt=tint_amt)
    for k in range(4):
        f = 0.55 - 0.13 * k
        c.dim(y + k, x, 1, sp.w, min(1.0, 1.0 - f))
        c.dim(y + 43 - k, x, 1, sp.w, min(1.0, 1.0 - f))
        c.dim(y, x + k, 44, 1, min(1.0, 1.0 - f))
        c.dim(y, x + sp.w - 1 - k, 44, 1, min(1.0, 1.0 - f))


def _interlude(c, ctx, t, d):
    _station_bg(c, ctx, t, d)
    c.text(4, C.STAGE_X + 3, d.inter_room, C.mix(CYAN_HI, WHITE, 0.2), None,
           bold=True)
    _hair(c, 5, C.STAGE_X + 2, W - 2, C.mix(INK, BORDER_HI, 0.75))
    _hair(c, 50, C.STAGE_X + 2, W - 2, C.mix(INK, BORDER_HI, 0.55))
    c.text(51, C.STAGE_X + 3, d.aisle, C.mix(INK, C.TEXT_FAINT, 0.9), None)
    c.text(51, W - len(d.rail) - 3, d.rail, C.mix(INK, C.GOLD_DIM, 0.8), None)

    cuts = (151.55, 153.60, 155.55, 156.60)
    if t < 151.55:
        name = "desk-reflection"
        zoom = 1.02 + 0.07 * M.seg(t, 149.4, 151.55)
        center = (0.50, 0.46)
    elif t < 153.60:
        u = M.seg(t, 151.55, 153.60)
        name, zoom, center = "desk-look", 1.03 + 0.09 * u, (0.40, 0.46)
    elif t < 155.55:
        u = M.seg(t, 153.60, 155.55)
        name, zoom, center = "desk-tap", 1.03 + 0.10 * u, (0.45, 0.52)
    elif t < 156.60:
        u = M.seg(t, 155.55, 156.60)
        name, zoom, center = "desk", 1.04 + 0.03 * u, (0.50, 0.50)
    else:
        name = None
        zoom = center = None

    if name is None:
        from ..assets import draw_keyframe
        draw_keyframe(c, "desk", 6, C.STAGE_X + 2, 44, C.STAGE_W - 4, t,
                      zoom=1.04, center=(0.5, 0.5), bright=1.20)
        c.text(4, C.STAGE_X + 2, d.s4_hall, C.CYAN_HI, INK, bold=True)
        c.hline(5, C.STAGE_X + 2, W - 2, BORDER_HI, INK)
        c.hline(50, C.STAGE_X + 2, W - 2, BORDER_HI, INK)
    else:
        _stage_image(c, t, name, zoom, center,
                     tint=C.mix(INK, CYAN_DIM, 0.18), tint_amt=0.10)
        for cut_t in cuts:
            age = t - cut_t
            if 0.0 <= age < 0.3:
                _cut(c, age, flash=0.06, chroma=0.10, shake=0.8, decay=0.08,
                     color=CYAN_HI)
    fl = 0.04 * ctx.audio.pulse(t, 0.12)
    if fl > 0.0:
        c.fx.flash = max(c.fx.flash, fl)
        c.fx.flash_color = C.mix(INK, CYAN_DEEP, 0.5)

    row, x, w, bg = draw_session(c, t, d.beats, d.inter_title,
                                 (d.inter_user, d.inter_assistant), C.CYAN_DIM)
    from .. import art as _art
    _art.separator(c, row, x, w, d.inter_input, C.BORDER, DIM, bg)
    c.put(row + 2, x + 1, "\u258f", C.CYAN_HI, bg)
    c.put(row + 2, x + 3, "\u2588" if (t * 2.0) % 1.0 < 0.55 else " ",
          C.CYAN_HI, bg)
    c.text(row + 20, x + 1, d.inter_session, C.mix(bg, TEXT_FAINT, 0.8), bg)
    c.text(row + 21, x + 1, d.inter_room, C.mix(bg, CYAN_DIM, 0.7), bg)


# --------------------------------------------------------------------------
# dispatch
# --------------------------------------------------------------------------
def draw(scene, c, ctx):
    d = getattr(scene, "_s35b", None)
    if d is None:
        prepare(scene)
        d = scene._s35b
    t = ctx.t
    if t < T_E1:
        return
    if t < T_SPLIT_END:
        _e1_split(c, ctx, t, d)
    elif t < T_E2:
        _e1_facade(c, ctx, t, d)
    elif t < T_WAVES_END:
        _e2_waves(c, ctx, t, d)
    elif t < T_E3:
        _e2_latch(c, ctx, t, d)
    elif t < T_LISS_END:
        _e3_liss(c, ctx, t, d)
    elif t < T_OVER_END:
        _e3_over(c, ctx, t, d)
    elif t < T_E4:
        _e3_flood(c, ctx, t, d)
    elif t < T_SPIN_END:
        _e4_spin(c, ctx, t, d)
    elif t < T_E5:
        _e4_lock(c, ctx, t, d)
    elif t < T_F1:
        _e5_wipe(c, ctx, t, d)
    elif t < T_G:
        _f1_hammer(c, ctx, t, d)
    elif t < T_COVER_END:
        _g_cover(c, ctx, t, d)
    elif t < T_FLIP_END:
        _g_flip(c, ctx, t, d)
    elif t < T_CODEX_END:
        _g_codex(c, ctx, t, d)
    elif t < T_STATION:
        _g_codex(c, ctx, t, d, closing=True)
    else:
        _interlude(c, ctx, t, d)
