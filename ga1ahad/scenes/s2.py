"""Scene 2 -- THE SCHISM / CODE SPECIALISATION  (00:40.640 - 01:03.860).

A cinematic rewrite in five movements:

  40.640 - 43.060  THE TEAR       the seam from the previous chapter rips the
                                  frame open; the left portrait window shows the
                                  revocation transcript and the silent mirror
                                  while two operators sink into a cyan and a red
                                  undercurrent.  Hard cut to black at 43.060.
  43.060 - 44.600  COLD OPEN      full-width brand reveal: braille petal arcs
                                  unfold a sunflower emblem, a wide-tracked
                                  wordmark settles.  No conversation window.
  44.600 - 52.390  THREE ACTS     one visual system per lyric: (1) phosphor
                                  terminal mode with a self-stitching syntax
                                  tree and green test pulses; (2) a ladder
                                  collapse under real gravity while diff light
                                  bands weave through it; (3) cold desktop
                                  minimalism with the resolved-rate curve as a
                                  gold light pillar and the first clean
                                  silhouette of the avatar in the dark.
  52.390 - 60.910  THE WALTZ      the whole frame is silently streaming source
                                  code; developer comment windows drift, stack
                                  and press in waltz time with drop shadows and
                                  parallax depth (glyph-crafted cards only).
  60.910 - 63.860  MONUMENT       every window is pulled into the centre and
                                  collapses into an accelerating milestone and
                                  a contracting gold ring; at 63.860 it
                                  detonates into the next chapter's bell gold.

Only the first movement shows the 9:16 conversation window (the official
art.llm_dialog contract, drawn through motion.Dialog).  Everything else is a
full-width 200x51 stage.
"""

from __future__ import annotations

import math
import random

from .. import config as C
from .. import motion as M
from .base import Scene

# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------
S2_START = 40.640
S2_END = 63.860
TEAR_END = 43.060
SPLASH_END = 44.600
ACT1, ACT2, ACT3 = 44.600, 47.580, 50.440
WALTZ = 52.390
WAVES = (52.390, 55.330, 58.080, 60.910)
COLLAPSE = 60.910

Y0, Y1 = C.CONTENT_Y0, C.CONTENT_Y1      # 2 .. 52 (inclusive)
BAND_H = Y1 - Y0                          # 51

# ---------------------------------------------------------------------------
# palette helpers
# ---------------------------------------------------------------------------
_TONE = {
    "hi": C.CYAN_HI,
    "dim": C.TEXT_DIM,
    "faint": C.TEXT_FAINT,
    "red": C.RED_HI,
    "amber": C.AMBER,
    "amber-hi": C.AMBER_HI,
    "gold": C.GOLD_HI,
    "terra": C.TERRA_HI,
    "terra-pale": C.TERRA_PALE,
    "green": C.GREEN,
    "term": C.TERM_GREEN,
    "green-dim": C.GREEN_DIM,
    "text": C.TEXT,
    "magenta": C.MAGENTA,
    "cyan": C.CYAN,
    "purple": C.PURPLE_HI,
    "red-dim": C.RED_DIM,
    "user": C.TEXT_DIM,
    "bot": C.TERM_GREEN,
    "meta": C.GREEN_DIM,
}


def _tone(name: str, default: int = C.TEXT) -> int:
    return _TONE.get(name, default)


def _rtext(c, y: int, x_end: int, s: str, fg: int, bg: int | None = None,
           bold: bool = False) -> int:
    """Right-aligned single-line text ending at x_end (exclusive)."""
    s = str(s)
    if not s:
        return 0
    return c.text(y, max(0, x_end - len(s)), s, fg, bg, bold=bold)


def _ctext(c, y: int, s: str, fg: int, bg: int | None = None,
           bold: bool = False) -> int:
    return c.text_center(y, str(s), fg, bg, bold=bold)


def _shadow(c, y: int, x: int, h: int, w: int, *, ox: int = 2, oy: int = 1,
            amount: float = 0.55) -> None:
    """Fake a cast shadow as an L-shaped darkening to the right/below."""
    xr = min(C.W, x + w + ox)
    for yy in range(max(Y0, y + oy), min(Y1, y + h + oy)):
        row_b, row_f = c.bg[yy], c.fg[yy]
        for xx in range(max(0, x + w), xr):
            row_b[xx] = C.mix(row_b[xx], C.BLACK, amount)
            row_f[xx] = C.mix(row_f[xx], C.BLACK, amount * 0.8)
    for yy in range(max(Y0, y + h), min(Y1, y + h + oy)):
        row_b, row_f = c.bg[yy], c.fg[yy]
        for xx in range(max(0, x + ox), xr):
            row_b[xx] = C.mix(row_b[xx], C.BLACK, amount)
            row_f[xx] = C.mix(row_f[xx], C.BLACK, amount * 0.8)


def _dim_rect(c, y: int, x: int, h: int, w: int, factor: float) -> None:
    y0, y1 = max(Y0, y), min(Y1, y + h)
    x0, x1 = max(0, x), min(C.W, x + w)
    if y1 <= y0 or x1 <= x0:
        return
    for yy in range(y0, y1):
        row_f, row_b = c.fg[yy], c.bg[yy]
        for xx in range(x0, x1):
            row_f[xx] = C.scale(row_f[xx], factor)
            row_b[xx] = C.scale(row_b[xx], factor)


def _bar(c, y: int, x: int, w: int, frac: float, fg: int, *,
         track: int = C.BORDER, bg: int | None = None,
         ch: str = "\u2588", tch: str = "\u2591") -> None:
    frac = M.clamp01(frac)
    n = int(round(frac * w))
    for i in range(w):
        if i < n:
            c.put(y, x + i, ch, fg, bg)
        else:
            c.put(y, x + i, tch, track, bg)


# ---------------------------------------------------------------------------
# 3D / geometry tables (built once at module import; pure constants)
# ---------------------------------------------------------------------------
# abstract syntax tree: (column, row) cell anchors, breadth-first order
_AST_NODES = (
    (146, 7),                                               # 0 root
    (108, 17), (146, 18), (184, 17),                        # 1-3
    (90, 27), (124, 28), (134, 28), (158, 28),
    (172, 28), (194, 28),                                   # 4-9
    (82, 38), (98, 39), (114, 38), (128, 39), (142, 38),
    (156, 39), (170, 38), (182, 39), (194, 38),             # 10-18
)
_AST_EDGES = (
    (0, 1), (0, 2), (0, 3),
    (1, 4), (1, 5), (2, 6), (2, 7), (3, 8), (3, 9),
    (4, 10), (4, 11), (5, 12), (5, 13), (6, 14),
    (7, 15), (7, 16), (8, 17), (9, 18),
)

# comment windows: (column, row, width, height, depth-layer 0 far .. 2 near)
_CARD_LAYOUT = (
    (14, 6, 38, 8, 2),
    (104, 5, 40, 8, 1),
    (60, 30, 36, 8, 0),
    (8, 18, 34, 8, 1),
    (136, 20, 38, 8, 2),
    (78, 41, 40, 8, 1),
    (24, 34, 34, 8, 0),
    (116, 34, 36, 8, 2),
    (156, 8, 36, 8, 1),
    (46, 22, 34, 8, 0),
    (96, 25, 38, 8, 1),
    (132, 42, 36, 8, 0),
)
_CARD_ACCENTS = (
    C.CYAN, C.TERRA_HI, C.GOLD, C.AMBER, C.BLUE, C.TERRA_PALE,
    C.CYAN_HI, C.GOLD_HI, C.AMBER_HI, C.TERRA, C.CYAN_DIM, C.GOLD_DIM,
)

# the silently streaming source code behind the waltz (generic tokens only)
_CODE_LINES = (
    "let frame = self.frames.get_mut(lane)",
    "if frame.is_none() { return Err(Lane); }",
    "impl Merge<A, B> for TokenStream {",
    "    fn next(&mut self) -> Option<Item> {",
    "unsafe { ptr::write_volatile(dst, src) }",
    "// the race is still inside the shader pass",
    "match kind { Borrow => clone(tmp), _ => drop }",
    "fn resolve(&self, ctx: &Ctx) -> Result<Frame>",
    "let mut out: Vec<Token> = Vec::with_capacity(n);",
    "while i < a.len() && j < b.len() { out.push(..) }",
    "assert_eq!(rows, cols * 4, \"lane geometry\");",
    "frame.write_checked(px, &self.camera);",
    "self.dirty = false; let _ = trace(\"closed\");",
    "for (k, lane) in self.lanes.iter_mut().enumerate() {",
    "    lane.commit(k, ctx.epoch, &mut scratch)?;",
    "// FIXME: the borrow checker cannot see the alias",
    "let n = (0..len).filter(|p| bits.get(*p)).count();",
    "drop(guard); atomic.store(1, Ordering::Release);",
    "if cfg!(feature = \"simd\") { kernel::run_simd() }",
    "return Ok(Frame { lane, px, stamp: now() });",
    "pub fn commit(&mut self, id: u32, out: &mut Buf) {",
    "let hash = fnv1a(&bytes[..]) ^ salt.rotate_left(13);",
    "loop { let step = work.steal()?; if step.is_empty() { break } }",
    "self.mirror.sync_dir(\"tests\", &[Mode::Rw])?;",
    "let patch = diff::unified(&old, &new, 3, context);",
    "verify!(suite == expected, \"regression in lane {}\");",
    "// NOTE: this is the line that used to deadlock",
    "let score = bench.run(SUITE)?.resolved as f64 / total;",
    "impl Drop for Guard { fn drop(&mut self) { release() } }",
    "cfg.iter().filter_map(|k| table.get(k)).collect()",
)


# ---------------------------------------------------------------------------
# the chapter
# ---------------------------------------------------------------------------
class Scene2(Scene):
    NAME = "s2"

    # ---- construction --------------------------------------------------
    def __init__(self, assets, audio, timeline, content) -> None:
        super().__init__(assets, audio, timeline, content)
        S = self.script

        # sprites (the asset cache keeps these cheap)
        self._sam_sp = assets.sam(17)
        self._dahlia_sp = assets.dahlia(17, manic=True)
        claude_raw = C.mix(C.INK, C.mix(C.GOLD_DEEP, C.TERRA_DEEP, 0.45),
                          0.55)
        self._claude_sp = assets.claude_full(40, dark=True, bg=claude_raw)
        # the dark=True tint is applied to the sprite background as well, so
        # match the canvas backdrop to the sprite's own empty-cell colour and
        # the keyframe dissolves into the room without a rectangle
        self._claude_bg = C.mix(claude_raw, C.TERRA_DIM, 0.28)

        # split transcript: (reveal delay, colour, text[, typed])
        self._sam = [
            (float(b.delay), _tone(str(b.tone), C.CYAN_HI), str(b.text))
            for b in S.split.sam_lines
        ]
        self._dahlia = [
            (float(b.delay), _tone(str(b.tone), C.AMBER_HI), str(b.text),
             bool(b.get("typed", True)))
            for b in S.split.dahlia_lines
        ]
        # a sparse edit: Sam's revoke + the quiet mirror, no wall of text
        self._sam_show = (self._sam[0], self._sam[1], self._sam[3],
                          self._sam[5])
        self._dahlia_show = (self._dahlia[0], self._dahlia[2],
                             self._dahlia[3], self._dahlia[8])

        # waltz comment cards: (content, layout, accent, appear, layer)
        self._cards = []
        for k, card in enumerate(S.praise.cards):
            wave = min(2, k // 4)
            beat = k % 4
            appear = WAVES[wave] + beat * 0.90
            layout = _CARD_LAYOUT[k % len(_CARD_LAYOUT)]
            accent = _CARD_ACCENTS[k % len(_CARD_ACCENTS)]
            self._cards.append((card, layout, accent, appear, wave, k))

        # the streaming code field: (x, width, speed, phase, colour slot)
        rng = random.Random(0x5EA02)
        slots = (C.TEXT_FAINT, C.CYAN_DIM, C.GOLD_DIM, C.TERRA_DIM,
                 C.TEXT_FAINT, C.BLUE_DIM)
        self._streams = []
        for i in range(13):
            x = 2 + i * 15 + rng.randrange(-2, 3)
            width = 12 + rng.randrange(0, 7)
            speed = 3.2 + rng.random() * 5.4
            phase = rng.random() * 55.0
            slot = slots[i % len(slots)]
            self._streams.append((x, width, speed, phase, slot))

        # stage labels reused every frame
        S_lab = S.lab
        self._stage_names = [str(x) for x in S_lab.stage_names]
        self._stage_badges = [str(x) for x in S_lab.stage_badges]

    # ==================================================================
    # dispatch
    # ==================================================================
    def draw(self, c, ctx) -> None:
        t = ctx.t
        lt = t - S2_START
        if t < TEAR_END:
            self._shot_tear(c, ctx, t, lt)
        elif t < SPLASH_END:
            self._shot_splash(c, ctx, t, t - TEAR_END)
        elif t < ACT2:
            self._shot_act1(c, ctx, t, t - ACT1)
        elif t < ACT3:
            self._shot_act2(c, ctx, t, t - ACT2)
        elif t < WALTZ:
            self._shot_act3(c, ctx, t, t - ACT3)
        else:
            self._shot_waltz(c, ctx, t, t - WALTZ)

    # ==================================================================
    # movement 1 -- 40.640..43.060 : the tear
    # ==================================================================
    def _shot_tear(self, c, ctx, t: float, lt: float) -> None:
        S = self.script.split
        # two atmospheres tearing apart: cold cyan left, hot red right
        seam = 132
        for xx in range(C.W):
            if xx < seam:
                d = min(1.0, (seam - xx) / 62.0)
                col = C.mix(C.INK, C.CYAN_DEEP, 0.14 + 0.36 * d)
            else:
                d = min(1.0, (xx - seam) / 62.0)
                col = C.mix(C.INK, C.RED_DEEP, 0.15 + 0.40 * d)
            c.fill_bg(Y0, xx, BAND_H, 1, col)

        # stage: a vertical tear at the seam, cyan left / red right
        gap = int(round(C.ease_out_cubic(M.seg(lt, 0.0, 1.50)) * 7))
        jseed = int(t * 24.0)
        for yy in range(Y0, Y1):
            wob = int(round((M.hash01(yy, jseed) - 0.5) * 2.6))
            glow = 0.35 + 0.55 * abs(math.sin(yy * 0.42 + t * 3.4))
            xl = seam - gap + wob
            xr = seam + gap + wob
            for k in range(3, 0, -1):
                c.put(yy, max(1, xl - k), "\u2588",
                      C.mix(C.INK, C.CYAN, 0.26 * glow / k), C.INK)
                c.put(yy, min(C.W - 1, xr + k), "\u2588",
                      C.mix(C.INK, C.RED, 0.26 * glow / k), C.INK)
            c.put(yy, max(1, xl), "\u2590", C.mix(C.INK, C.CYAN_HI,
                                                  0.80 * glow), C.INK)
            if gap > 0:
                for xx in range(seam - gap, seam + gap + 1):
                    if 0 <= xx < C.W:
                        c.put(yy, xx, "\u2593",
                              C.mix(C.RED_DEEP, C.RED_HI, 0.30 * glow), C.INK)
            c.put(yy, min(C.W - 1, xr), "\u258c",
                  C.mix(C.INK, C.RED_HI, 0.85 * glow), C.INK)

        # two undercurrents: cold cyan flows left, hot red flows right
        for i in range(24):
            h1 = M.hash01(i, 7)
            h2 = M.hash01(i, 11)
            # left current (cyan)
            xx = 66 + int(58 * h1 + 5 * math.sin(t * 1.4 + i * 0.9))
            yy = Y0 + int((h2 * BAND_H + t * (3.0 + 4.0 * h1)) % BAND_H)
            c.text(yy, xx, "\u2500" * (3 + int(3 * h1)),
                   C.mix(C.INK, C.CYAN, 0.34 + 0.36 * h2), C.INK)
            # right current (red)
            xx = 138 + int(55 * h2 + 5 * math.sin(t * 1.1 + i * 1.3))
            yy = Y0 + int((h1 * BAND_H + t * (2.4 + 4.4 * h2)) % BAND_H)
            c.text(yy, xx, "\u2500" * (3 + int(3 * h2)),
                   C.mix(C.INK, C.RED, 0.30 + 0.34 * h1), C.INK)

        # the two operators sink into their undercurrents
        p = C.ease_in_cubic(M.seg(lt, 0.0, 1.55))
        jx = 81 - int(11 * p)
        jy = 7 + int(24 * p)
        M.feather_sprite(c, jy, jx, self._sam_sp, feather=5,
                         tint=C.CYAN, tint_amt=0.22 + 0.55 * p,
                         alpha=0.95 - 0.62 * p)
        dx = 148 + int(12 * p)
        dy = 7 + int(24 * p)
        M.feather_sprite(c, dy, dx, self._dahlia_sp, feather=5,
                         tint=C.RED, tint_amt=0.20 + 0.55 * p,
                         alpha=0.95 - 0.62 * p)

        # slam: ACCESS / REVOKED. across the tearing stage
        if lt > 0.70:
            p2 = M.ease_out_expo(M.seg(lt, 0.70, 0.88))
            plate = C.mix(C.INK, C.BLACK, 0.72)
            c.fill(12, 64, 30, C.W - 64, " ", C.TEXT, plate)
            dy2 = int(round((1.0 - p2) * -9))
            l1, l2 = str(S.banner_line_1), str(S.banner_line_2)
            w1 = M.big_text_size(l1, 2, 2)[0]
            w2 = M.big_text_size(l2, 2, 2)[0]
            col1 = C.mix(plate, C.AMBER_HI, 0.55 + 0.40 * p2)
            col2 = C.mix(plate, C.RED_HI, 0.55 + 0.45 * p2)
            M.big_text(c, 14 + dy2, 132 - w1 // 2, l1, col1, scale=2,
                       spacing=2, top=C.AMBER, bottom=C.WHITE)
            M.big_text(c, 30 + dy2, 132 - w2 // 2, l2, col2, scale=2,
                       spacing=2, top=C.RED, bottom=C.RED_HI)
            _ctext(c, 46, str(S.banner_revoke), C.RED_HI, plate)
            _ctext(c, 48, str(S.banner_warning), C.mix(plate, C.RED_HI, 0.7),
                   plate)
            M.punctuate(c, lt - 0.70, flash=0.20, glitch=0.40, chroma=0.55,
                        shake=3.2, decay=0.18, flash_color=C.RED)

        # the conversation window (the only one in this chapter)
        self._tear_dialog(c, ctx, lt)

        # sink to black before the cut
        k = M.seg(lt, 2.16, 2.42)
        if k > 0.0:
            _dim_rect(c, Y0, 0, BAND_H, C.W, max(0.0, 1.0 - 0.96 * k))
        if lt < 0.14:
            M.punctuate(c, lt, glitch=0.18, chroma=0.30, decay=0.12)

    def _tear_dialog(self, c, ctx, lt: float) -> None:
        S = self.script.split
        d = M.Dialog(
            c, *C.DLG_SLOTS[0],
            title=str(S.header),
            right=f"{self.T.openai_upper} \u2194 {self.T.anthropic_upper}",
            accent=C.mix(C.CYAN_DIM, C.AMBER_DIM, 0.45),
            bg=C.mix(C.INK2, C.CYAN_DEEP, 0.10),
        )
        # status strip
        d.text(1, str(S.header_note), C.TEXT_DIM)
        stamp = str(S.security_stamp)
        blink = (ctx.t * 2.6) % 1.0 < 0.6
        c.text(d.y + 1, d.x + d.w - len(stamp) - 3, stamp,
               C.RED_HI if blink else C.RED_DIM, d.bg, bold=True)
        # Sam's security console
        d.rule(2, str(S.sam_console), C.CYAN_DIM)
        row = 3
        last = None
        for i, (delay, col, txt) in enumerate(self._sam_show):
            if lt < delay:
                continue
            s = M.scramble_text(txt, lt, start=delay, settle=0.12, cps=110.0,
                                seed=float(i))
            d.text(row + i, s, col)
            last = (row + i, len(s))
        if last is not None and (ctx.t * 2.2) % 1.0 < 0.55:
            c.put(d.y + last[0], min(d.x + d.w - 2, d.x + 3 + last[1]),
                  "\u2588", C.CYAN_HI, d.bg)
        if lt > 1.85:
            d.text(8, str(S.sam_quote_1), C.CYAN_DIM)
            d.text(9, str(S.sam_quote_2), C.CYAN_DIM)
        # the silent mirror
        d.rule(11, str(S.dahlia_console), C.AMBER_DIM)
        row = 12
        last = None
        for i, (delay, col, txt, typed) in enumerate(self._dahlia_show):
            if lt < delay:
                continue
            s = (M.scramble_text(txt, lt, start=delay, settle=0.12, cps=100.0,
                                 seed=11.0 + i) if typed else txt)
            d.text(row + i, s, col)
            last = (row + i, len(s))
        if last is not None and (ctx.t * 2.0 + 0.4) % 1.0 < 0.55:
            c.put(d.y + last[0], min(d.x + d.w - 2, d.x + 3 + last[1]),
                  "\u2588", C.AMBER_HI, d.bg)
        # the two system operations behind the schism
        rev = M.clamp01(M.seg(lt, 0.85, 2.10))
        d.rule(17, "REVOCATION", C.RED_DIM)
        _bar(c, d.y + 18, d.x + 3, d.width - 12, rev, C.RED, bg=d.bg,
             track=C.mix(d.bg, C.RED_DEEP, 0.5))
        c.text(d.y + 18, d.x + d.w - 9, f"{int(rev * 100):3d}%", C.RED_DIM,
               d.bg)
        mir = M.clamp01(M.seg(lt, 0.45, 1.75))
        d.rule(19, "MIRROR", C.AMBER_DIM)
        _bar(c, d.y + 20, d.x + 3, d.width - 12, mir, C.AMBER, bg=d.bg,
             track=C.mix(d.bg, C.AMBER_DIM, 0.4))
        c.text(d.y + 20, d.x + d.w - 9, f"{int(mir * 100):3d}%", C.AMBER_DIM,
               d.bg)
        if lt > 1.05:
            d.text(22, str(S.revoked_operator), C.RED_HI, bold=True)
        d.text(23, str(S.ghost_note), C.AMBER_DIM)
        d.text(24, str(S.cold_start_note), C.TERRA_HI)
        # a quiet watermark: the word the window is trying not to say
        if lt > 1.20:
            p = C.ease_out_cubic(M.seg(lt, 1.20, 1.60))
            word = str(S.revoked_stamp)
            bw = M.big_text_size(word, 1, 1)[0]
            stx = d.x + max(1, (d.w - bw) // 2)
            col = C.mix(d.bg, C.RED_DIM, 0.65 * p)
            M.big_text(c, d.y + 39, stx, word, col, scale=1, spacing=1)
        d.footer(46, f"CUE 01/08  \u00b7  {C.fmt_clock(ctx.t)}  \u00b7  "
                     f"OPERATOR SESSIONS CLOSED", color=C.TEXT_FAINT)

    # ==================================================================
    # movement 2 -- 43.060..44.600 : the cold open
    # ==================================================================
    def _shot_splash(self, c, ctx, t: float, lt: float) -> None:
        S = self.script.splash
        c.fill(Y0, 0, BAND_H, C.W, " ", C.TEXT, C.BLACK)
        # a warm pool of light behind the emblem
        for yy in range(Y0 + 2, Y0 + 31):
            for xx in range(34, 166):
                d = math.hypot((xx - 100) / 42.0, (yy - 18.0) / 14.0)
                k = max(0.0, 1.0 - d)
                if k > 0.03:
                    c.blend_bg(yy, xx, C.GOLD_DEEP, 0.34 * k * k)

        # braille emblem: twelve petals unfold as precision arcs
        br = c.braille(Y0, 0, BAND_H, C.W)
        cx, cy = 200.0, 60.0
        u = M.ease_out_expo(M.seg(lt, 0.04, 0.82))
        spin = t * 0.22
        for i in range(12):
            a = i * math.pi / 6.0 + spin
            petal_col = C.mix(C.GOLD, C.GOLD_HI,
                              0.55 + 0.40 * math.sin(t * 2.1 + i * 1.3))
            # a petal is three nested precision arcs, unfolding outward
            for sign in (1.0, 0.0, -1.0):
                prev = None
                for k in range(12):
                    q = k / 11.0
                    r = 8.0 + (50.0 * u) * q
                    lat = math.sin(math.pi * q) * (11.0 - 3.5 * q) * sign
                    x = cx + math.cos(a) * r - math.sin(a) * lat
                    y = cy + math.sin(a) * r + math.cos(a) * lat
                    if prev is not None:
                        br.line(prev[0], prev[1], x, y,
                                petal_col if sign
                                else C.mix(C.GOLD_HI, C.WHITE, 0.30),
                                0.95)
                    prev = (x, y)
        # core + seed spiral
        if u > 0.10:
            for rr in (8.0, 14.0, 20.0):
                br.circle(cx, cy, rr * u, C.GOLD_HI, 0.95)
            for k in range(70):
                rr = math.sqrt(k / 70.0) * 17.0 * u
                aa = k * 2.39996 + t * 0.5
                br.plot(int(cx + math.cos(aa) * rr), int(cy + math.sin(aa) * rr),
                        C.mix(C.GOLD, C.GOLD_HI, 0.5 + 0.5 * math.sin(k * 1.7 + t)),
                        0.9)
            # a thin dashed orbit keeps the emblem "engineered"
            ro = 60.0 * u
            for k in range(96):
                if k % 3 == 0:
                    continue
                aa = k * 2.0 * math.pi / 96.0 + spin * 0.6
                br.plot(int(cx + math.cos(aa) * ro), int(cy + math.sin(aa) * ro),
                        C.mix(C.INK, C.GOLD_DIM, 0.85), 0.9)
        br.commit()

        # wide-tracked wordmark: letters drop in one by one
        word = str(S.wordmark).upper().replace(" ", "")
        if word and lt > 0.38:
            n = min(9, len(word))
            word = word[:n]
            avail = 176.0
            gw = 10.0
            gap = max(4.0, (avail - gw * n) / max(1, n - 1))
            x0 = 12.0
            for i, ch in enumerate(word):
                p = M.stagger(i, n, M.seg(lt, 0.38, 1.10), spread=0.55)
                e = M.spring(p, freq=2.4, damp=0.36)
                yy = 31 - int(round((1.0 - min(1.0, e)) * 5))
                col = C.mix(C.BLACK, C.GOLD_HI, min(1.0, 0.30 + 0.85 * e))
                M.big_text(c, yy, int(x0 + i * (gw + gap)), ch, col,
                           scale=2, spacing=0, top=C.TERRA, bottom=C.GOLD_HI)
        if lt > 0.86:
            k = M.clamp01((lt - 0.86) / 0.30)
            M.hairline(c, 45, 46, 154, C.mix(C.BLACK, C.GOLD_DIM, k))
        if lt > 0.92:
            _ctext(c, 46, str(S.subtitle), C.GOLD_HI, None, bold=True)
        if lt > 1.02:
            _ctext(c, 48, str(S.credit), C.TEXT_DIM, None)
        if lt > 1.14:
            blink = (t * 1.8) % 1.0 < 0.72
            _ctext(c, 50, str(S.online),
                   C.GOLD_HI if blink else C.GOLD_DIM, None, bold=True)
        # tasting the light: a soft gold wash at the very end of the shot
        if lt > 1.30:
            k = M.seg(lt, 1.30, 1.54)
            for yy in range(Y0, Y1):
                v = 0.30 * k * (1.0 - abs(yy - 26) / 27.0)
                if v > 0:
                    c.fill_bg(yy, 0, 1, C.W, C.mix(C.BLACK, C.GOLD_DEEP, v))

    # ==================================================================
    # movement 3a -- 44.600..47.580 : phosphor terminal + AST
    # ==================================================================
    def _shot_act1(self, c, ctx, t: float, lt: float) -> None:
        S = self.script
        # phosphor-green filed gradient + CRT scanlines
        M.bg_gradient(c, C.mix(C.INK, C.GREEN_DIM, 0.12),
                      C.mix(C.INK, C.GREEN, 0.05), Y0, Y1)
        for yy in range(Y0, Y1, 2):
            c.fill_bg(yy, 0, 1, C.W, C.mix(C.INK, C.GREEN_DIM, 0.16))
        sweep_y = Y0 + int((lt * 26.0) % BAND_H)
        c.fill_bg(sweep_y, 0, 1, C.W, C.mix(C.INK, C.GREEN, 0.09))
        # header
        c.text(Y0, 4, str(S.lab.header), C.mix(C.INK, C.TERM_GREEN, 0.95),
               None, bold=True)
        _rtext(c, Y0, C.W - 4,
               f"{S.lab.stage_badges[0]}  \u00b7  {self._stage_names[0].upper()}",
               C.GREEN_DIM)
        M.hairline(c, Y0 + 1, 4, C.W - 4, C.mix(C.INK, C.GREEN_DIM, 0.8))

        # left: the live terminal log
        logs = [str(x) for x in S.sandbox.logs]
        last = None
        for i, line in enumerate(logs):
            start = 0.14 + i * 0.20
            if lt < start:
                continue
            s = M.type_text(line, lt, start=start, cps=170.0)
            col = C.mix(C.INK, C.TERM_GREEN if i % 2 else C.GREEN, 0.95)
            c.text(5 + i, 4, s[:78], col, None)
            last = (5 + i, len(s))
        if last is not None and (t * 2.4) % 1.0 < 0.55:
            c.put(last[0], min(84, 4 + last[1]), "\u2588", C.GREEN, None)
        # ambient source keeps streaming under the log (terminal texture)
        for k in range(9):
            yy = 16 + k * 4
            idx = (k * 5 + int(lt * 2.2)) % len(_CODE_LINES)
            c.text(yy, 4, _CODE_LINES[idx][:74],
                   C.mix(C.INK, C.GREEN_DIM,
                         0.60 + 0.25 * M.hash01(k, 3)))

        # right: self-stitching syntax tree
        self._act1_ast(c, ctx, t, lt)

        # bottom rail: the reward strip (single hairline strip, no panel)
        M.hairline(c, 48, 4, C.W - 4, C.mix(C.INK, C.GREEN_DIM, 0.6))
        c.text(49, 4, str(S.sandbox.caption), C.mix(C.INK, C.GREEN_DIM, 0.9))
        rew = M.clamp01(0.25 + 0.75 * C.ease_out_cubic(M.seg(lt, 0.4, 2.4)))
        lbl = str(S.sandbox.reward_title)
        _rtext(c, 49, C.W - 4, lbl, C.GREEN_DIM)
        _bar(c, 50, C.W - 4 - 46, 40, rew, C.TERM_GREEN, bg=None,
             track=C.mix(C.INK, C.GREEN_DIM, 0.45))
        c.text(50, C.W - 4 - 46 - 6, f"{rew:4.2f}", C.mix(C.INK, C.GREEN, 0.9))

    def _act1_ast(self, c, ctx, t: float, lt: float) -> None:
        S = self.script.sandbox
        br = c.braille(Y0, 0, BAND_H, C.W)
        dot = [(col * 2 + 1, (row - Y0) * 4 + 2) for (col, row) in _AST_NODES]
        node_t = [0.16 + 0.072 * k for k in range(len(_AST_NODES))]
        green_hi = C.mix(C.GREEN, C.WHITE, 0.55)
        # edges stitch themselves from parent to child
        for j, (a, b) in enumerate(_AST_EDGES):
            ta = max(node_t[a], node_t[b])
            if lt < ta:
                continue
            pr = C.ease_out_cubic(M.seg(lt, ta, ta + 0.30))
            x0, y0 = dot[a]
            x1, y1 = dot[b]
            xe = x0 + (x1 - x0) * pr
            ye = y0 + (y1 - y0) * pr
            br.line(x0, y0, xe, ye, C.mix(C.INK, C.TERM_GREEN, 0.95), 0.95)
            br.line(x0, y0 + 1, xe, ye + 1, C.mix(C.INK, C.GREEN, 0.80), 0.9)
            # a test pulse runs down each finished branch
            if pr >= 1.0:
                ph = (lt * 0.72 + M.hash01(j, 3)) % 1.0
                px = x0 + (x1 - x0) * ph
                py = y0 + (y1 - y0) * ph
                br.plot(int(px), int(py), green_hi, 1.0)
                br.plot(int(px) + 1, int(py), C.GREEN, 0.9)
        # a needle stitches the newest edge (sewing metaphor)
        if 0.5 < lt < 2.4:
            k = int((lt - 0.5) / 0.10) % len(_AST_EDGES)
            a, b = _AST_EDGES[k]
            ta = max(node_t[a], node_t[b])
            pr = M.clamp01((lt - ta) / 0.30)
            x0, y0 = dot[a]
            x1, y1 = dot[b]
            nx = x0 + (x1 - x0) * pr
            ny = y0 + (y1 - y0) * pr
            for d in range(4):
                br.plot(int(nx), int(ny + d), C.mix(C.WHITE, C.GREEN, 0.35), 1.0)
        # glowing rings around every node that has appeared
        for k, (col, row) in enumerate(_AST_NODES):
            if lt < node_t[k]:
                continue
            e = min(1.0, M.spring(M.seg(lt, node_t[k], node_t[k] + 0.30),
                                  freq=2.8, damp=0.32))
            bx, by = dot[k]
            br.circle(bx, by, 3.0 + 2.5 * e,
                      C.mix(C.INK, C.TERM_GREEN, 0.55 + 0.45 * e), 0.95)
        br.commit()
        # node caps + short hex ids after the braille commit
        for k, (col, row) in enumerate(_AST_NODES):
            if lt < node_t[k]:
                continue
            e = M.spring(M.seg(lt, node_t[k], node_t[k] + 0.30), freq=2.8,
                         damp=0.32)
            e = min(1.0, e)
            colr = C.mix(C.INK, C.TERM_GREEN, 0.70 + 0.30 * e)
            c.put(row, col, "\u25c6" if k == 0 else "\u25c7", colr, None)
            if k % 2 == 0 and col < 186 and lt > node_t[k] + 0.10:
                c.text(row, col + 2, f"0x{0x40 + k:02X}",
                       C.mix(C.INK, C.GREEN_DIM, 0.95))
            # leaf nodes eventually pass their test suite
            if k >= 10 and lt > node_t[k] + 0.42:
                blink = 0.5 + 0.5 * math.sin(t * 6.0 + k)
                c.put(row - 1, col + 1, "\u2713",
                      C.mix(C.INK, C.GREEN, 0.70 + 0.30 * blink))
        c.text(4, 92, str(S.ast_title), C.mix(C.INK, C.GREEN_DIM, 1.0))
        c.text(5, 92, str(S.ast_fix), C.mix(C.INK, C.TERM_GREEN, 0.7))

    # ==================================================================
    # movement 3b -- 47.580..50.440 : the ladder collapse
    # ==================================================================
    def _shot_act2(self, c, ctx, t: float, lt: float) -> None:
        S = self.script
        M.bg_gradient(c, C.mix(C.INK, C.CYAN_DEEP, 0.16),
                      C.mix(C.INK, C.PANEL3, 0.22), Y0, Y1)
        self._act2_bands(c, ctx, t, lt)
        # header
        c.text(Y0, 4, str(S.bench.title), C.mix(C.INK, C.CYAN, 0.95),
               None, bold=True)
        _rtext(c, Y0, C.W - 4,
               f"{S.bench.leaderboard}  \u00b7  {S.lab.stage_badges[1]}  \u00b7  "
               f"{self._stage_names[1].upper()}", C.TEXT_DIM)
        M.hairline(c, Y0 + 1, 4, C.W - 4, C.mix(C.INK, C.CYAN_DIM, 0.85))
        _rtext(c, 4, C.W - 4, str(S.bench.eval_line), C.TEXT_FAINT)
        self._act2_ladder(c, ctx, t, lt)
        self._act2_stamp(c, ctx, t, lt)

    def _act2_bands(self, c, ctx, t: float, lt: float) -> None:
        """The diff weaves as light bands across the whole frame."""
        br = c.braille(Y0, 0, BAND_H, C.W)
        for i in range(7):
            base = 18.0 + i * 26.0
            amp = 5.0 + (i % 3) * 2.5
            col = C.mix(C.INK, C.GREEN if i % 2 else C.RED,
                        0.60 + 0.22 * math.sin(t * 1.3 + i))
            prev = None
            for x in range(0, 400, 2):
                y = base + amp * math.sin(x * 0.017 + t * 1.05 + i * 1.7)
                if prev is not None:
                    br.line(prev[0], prev[1], x, y, col, 0.95, 0.45)
                prev = (x, y)
        br.commit()

    def _act2_ladder(self, c, ctx, t: float, lt: float) -> None:
        S = self.script
        names = [str(x) for x in S.bench.rows]
        fails = [str(x) for x in S.bench.fail_msgs]
        scores = (0.0, 41.2, 38.9, 29.4, 26.7, 21.0, 12.8)
        x0, track = 50, 134
        for i in range(len(names)):
            y = 8 + i * 6
            name = names[i % len(names)]
            if i == 0:
                # the survivor: keeps climbing to the record and stays lit
                p = M.spring(M.seg(lt, 0.10, 1.30), freq=2.0, damp=0.34)
                frac = 0.824 * min(1.0, p)
                pulse = ctx.audio.pulse(t, 0.20)
                col = C.mix(C.GOLD, C.GOLD_HI, 0.45 + 0.50 * pulse)
                c.text(y, 6, name[:42], C.GOLD_HI, None, bold=True)
                _bar(c, y, x0, track, frac, col,
                     track=C.mix(C.INK, C.GOLD_DEEP, 0.85))
                hx = x0 + int(frac * track)
                c.put(y, min(C.W - 1, hx), "\u2588",
                      C.mix(C.WHITE, C.GOLD_HI, 0.45), None)
                _bar(c, y + 1, x0, track, frac,
                     C.mix(C.INK, C.GOLD_DIM, 0.55),
                     track=C.mix(C.INK, C.GOLD_DEEP, 0.30), ch="\u2584",
                     tch=" ")
                c.text(y, x0 + track + 2, str(S.swe.rank_scores[0]),
                       C.WHITE, None, bold=True)
                continue
            # competitors: race, stall, snap, fall, dissolve
            t0 = 0.10 + (i - 1) * 0.05
            race = M.spring(M.seg(lt, t0, t0 + 0.80), freq=2.6, damp=0.35)
            snap = 1.08 + (i - 1) * 0.16
            age = lt - snap
            frac = (scores[i] / 100.0) * min(1.0, race)
            warn = ""
            if age < 0.0:
                frac += 0.006 * math.sin(t * 46.0 + i * 2.1)
                if lt > snap - 0.55:
                    warn = fails[(i + int(lt * 5.0)) % len(fails)]
            col = C.mix(C.INK, C.CYAN, 0.90)
            if age >= 0.0:
                col = C.mix(C.INK, C.RED_HI, 0.60 + 0.40 * M.hit(age, 0.10))
                frac *= max(0.0, 1.0 - age * 3.4)
            c.text(y, 6, name[:42], C.TEXT)
            _bar(c, y, x0, track, max(0.0, frac), col,
                 track=C.mix(C.INK, C.BORDER, 0.9))
            if warn:
                c.text(y, x0 + int(frac * track) + 2, warn, C.RED_HI)
            c.text(y, x0 + track + 2, f"{scores[i]:4.1f}%",
                   C.TEXT if age < 0 else C.RED_HI)
            if age >= 0.0:
                # snap: a broken mark stays on the track
                bx = x0 + int(max(0.0, frac) * track)
                c.put(y, min(C.W - 1, bx), "\u2573", C.RED_DIM)
                # chunks under real gravity
                for ch in range(3):
                    ca = age
                    vy = 40.0 + ch * 13.0
                    yy = y + int(0.5 * vy * ca * ca)
                    if yy >= Y1:
                        continue
                    xx = (x0 + int(frac * track * 0.60) - ch * 15
                          + int((ch - 1) * 11.0 * ca))
                    n = max(1, 13 - ch * 2 - int(ca * 12))
                    fad = max(0.0, 1.0 - ca * 1.05)
                    if fad <= 0.05:
                        continue
                    chcol = C.mix(C.INK, C.mix(C.RED_HI, C.GOLD, 0.30), fad)
                    for k in range(n):
                        c.put(yy, xx + k, "\u2501", chcol, None)
                    # a short falling trail above the fragment
                    for k in range(3):
                        c.put(max(Y0, yy - 1 - k), xx + 2 + k,
                              "\u00b7", C.mix(C.INK, C.RED_DIM, fad * 0.8))
                    # dissolve into dust
                    if ca > 0.30:
                        for k in range(4):
                            h = M.hash01(i, ch, k, int(ca * 12.0))
                            c.put(yy + 1 + int(h * 4), xx + int(h * 25) % 25,
                                  "\u00b7", C.mix(C.INK, C.RED_HI,
                                                   0.55 * fad), None)
                M.punctuate(c, age, shake=1.1, chroma=0.16, decay=0.08)
        # the survivor line under the top rung
        if lt > 1.15:
            k = M.clamp01((lt - 1.15) / 0.35)
            _ctext(c, 13, str(S.bench.survivor_line),
                   C.mix(C.INK, C.GOLD_HI, k), None, bold=True)

    def _act2_stamp(self, c, ctx, t: float, lt: float) -> None:
        if lt < 1.98:
            return
        S = self.script.bench
        p = M.ease_out_expo(M.seg(lt, 1.98, 2.16))
        plate = C.mix(C.INK, C.BLACK, 0.80)
        c.fill(18, 0, Y1 - 18, C.W, " ", C.TEXT, plate)
        dy = int(round((1.0 - p) * -8))
        l1, l2 = str(S.stamp_line_1), str(S.stamp_line_2)
        w = max(M.big_text_size(l1, 2, 2)[0], M.big_text_size(l2, 2, 2)[0])
        x0 = 100 - w // 2
        M.big_text(c, 24 + dy, x0, l1, C.mix(plate, C.TEXT_DIM, 0.9),
                   scale=2, spacing=2, top=C.TEXT_FAINT, bottom=C.TEXT)
        M.big_text(c, 38 + dy, x0, l2, C.mix(plate, C.GOLD_HI, 0.55 + 0.45 * p),
                   scale=2, spacing=2, top=C.TERRA, bottom=C.GOLD_HI)
        M.hairline(c, 22 + dy, x0 - 10, x0 + w + 10,
                   C.mix(plate, C.GOLD_DIM, 0.7))
        M.hairline(c, 36 + dy, x0 - 10, x0 + w + 10,
                   C.mix(plate, C.GOLD_DIM, 0.7))
        M.punctuate(c, lt - 1.98, flash=0.16, shake=2.4, chroma=0.2,
                    decay=0.16, flash_color=C.GOLD_HI)

    # ==================================================================
    # movement 3c -- 50.440..52.390 : cold desktop / gold pillar
    # ==================================================================
    def _shot_act3(self, c, ctx, t: float, lt: float) -> None:
        S = self.script
        M.bg_gradient(c, C.mix(C.INK, C.BLUE_DIM, 0.12),
                      C.mix(C.INK, C.BLACK, 0.30), Y0, Y1)
        # a single hairline "desktop" rule and the record caption
        M.hairline(c, 6, 8, C.W - 8, C.mix(C.INK, C.BORDER, 0.75))
        M.corner_marks(c, 8, 10, 48, C.W - 10,
                       C.mix(C.INK, C.GOLD_DIM, 0.55), size=3)
        c.text(4, 9, str(S.swe.title), C.TEXT_DIM, None, bold=True)
        _rtext(c, 4, C.W - 9, str(S.swe.peak), C.GOLD_DIM)

        # the resolved-rate curve: it rises and becomes a pillar of light
        head = M.ease_out_expo(M.seg(lt, 0.10, 1.05))
        br = c.braille(Y0, 0, BAND_H, C.W)
        curve = []
        for k in range(97):
            q = k / 96.0
            x = 12.0 + 74.0 * q
            y = 50.0 - 20.0 * (q ** 1.6)
            curve.append((x * 2.0 + 1.0, (y - Y0) * 4.0 + 2.0))
        n_head = max(1, int(len(curve) * head))
        for k in range(n_head - 1):
            x0, y0 = curve[k]
            x1, y1 = curve[k + 1]
            br.line(x0, y0, x1, y1, C.mix(C.INK, C.GOLD_HI, 0.98), 1.0)
            br.line(x0, y0 + 1, x1, y1 + 1, C.mix(C.INK, C.GOLD, 0.92),
                    0.95)
            br.line(x0, y0 + 3, x1, y1 + 3, C.mix(C.INK, C.GOLD_DIM, 0.88),
                    0.9)
            br.line(x0, y0 + 6, x1, y1 + 6, C.mix(C.INK, C.GOLD_DEEP, 0.95),
                    0.9)
        # vertical light pillar into the ceiling
        px = int(86 * 2 + 1)
        for k in range(5):
            shade = (0.98, 0.80, 0.55, 0.80, 0.98)[k]
            br.line(px - 2 + k, int((30 - Y0) * 4), px - 2 + k, 1,
                    C.mix(C.INK, C.GOLD if k % 2 else C.GOLD_HI, shade),
                    0.95)
        # a bright bloom cap where the pillar leaves the frame
        for k in range(26):
            aa = k * 2.0 * math.pi / 26.0
            br.plot(int(px + math.cos(aa) * (8 + 3 * math.sin(t * 3))),
                    int(2 + abs(math.sin(aa)) * 5),
                    C.mix(C.GOLD, C.WHITE, 0.55), 0.9)
        br.commit()
        # glow under the curve and along the pillar (bg washes)
        for xx in range(12, 88):
            q = (xx - 12) / 74.0
            top = int(round(50.0 - 20.0 * (q ** 1.6)))
            c.fill_bg(top + 1, xx, Y1 - top - 1, 1,
                      C.mix(C.INK, C.GOLD_DIM, 0.18 + 0.22 * q))
        # the shaft: a narrow column of light that widens as it leaves the frame
        for yy in range(Y0, 32):
            k = (31 - yy) / 29.0
            spread = 3.0 + 3.0 * (1.0 - k)
            for xx in range(86 - int(spread), 86 + int(spread) + 1):
                inten = math.exp(-((xx - 86.0) / 2.6) ** 2)
                c.blend_bg(yy, xx, C.mix(C.GOLD_DIM, C.GOLD_HI, 0.35),
                           0.22 + 0.55 * inten * (0.5 + 0.5 * k))
        for yy in range(Y0, Y0 + 4):
            half = 10 - 2 * (yy - Y0)
            M.hairline(c, yy, 86 - half, 86 + half,
                       C.mix(C.GOLD, C.WHITE, 0.35))

        # the record itself, kinetic
        score = str(S.swe.rank_scores[0])
        _ctext(c, 11, M.spread_text(str(S.swe.resolved_rate), 1),
               C.TEXT_DIM, None, bold=True)
        n = len(score)
        for i, ch in enumerate(score):
            p = M.stagger(i, n, M.seg(lt, 0.28, 0.98), spread=0.42)
            e = min(1.0, M.spring(p, freq=2.6, damp=0.36))
            yy = 15 - int(round((1.0 - e) * 5))
            col = C.mix(C.INK, C.GOLD_HI, 0.20 + 0.85 * e)
            M.big_text(c, yy, 92 + i * 11, ch, col, scale=2, spacing=0,
                       top=C.GOLD, bottom=C.GOLD_HI)
        if lt > 1.10:
            k = M.clamp01((lt - 1.10) / 0.35)
            _ctext(c, 33, str(S.swe.resolved),
                   C.mix(C.INK, C.TEXT, 0.85 * k), None)
            _ctext(c, 35, str(S.swe.verified),
                   C.mix(C.INK, C.TEXT_DIM, k), None)
            _ctext(c, 37, str(S.swe.delta),
                   C.mix(C.INK, C.GOLD_HI, 0.85 * k), None, bold=True)
        c.text(47, 10, str(S.swe.axis_from), C.TEXT_FAINT)
        _rtext(c, 3, 96, str(S.swe.axis_now), C.GOLD_DIM)

        # the avatar: a clean illustrated silhouette in the dark, with a halo
        self._act3_claude(c, ctx, t, lt)
        if lt < 0.16:
            M.punctuate(c, lt, flash=0.10, chroma=0.18, decay=0.12,
                        flash_color=C.GOLD_HI)

    def _act3_claude(self, c, ctx, t: float, lt: float) -> None:
        sp = self._claude_sp
        sx = 154
        sy = 11
        head_x = sx + sp.w * 0.5
        head_y = sy + sp.h * 0.13
        # a warm backdrop that matches the sprite's own background colour, so
        # the keyframe dissolves into the dark instead of sitting in a box
        for yy in range(Y0, Y1):
            for xx in range(116, C.W):
                k = C.smoothstep(116.0, 154.0, float(xx))
                c.blend_bg(yy, xx, self._claude_bg, k)
        # the illustrated silhouette itself (feathered, no rectangle)
        alpha = 0.55 + 0.42 * C.ease_out_cubic(M.seg(lt, 0.15, 1.05))
        M.feather_sprite(c, sy, sx, sp, feather=7, tint=C.TERRA_HI,
                         tint_amt=0.08, alpha=alpha)
        # soft halo + crown rays, drawn only outside the figure so her
        # illustrated linework stays crisp
        br = c.braille(Y0, 0, BAND_H, C.W)
        cx = head_x * 2.0
        cy = (head_y - Y0) * 4.0
        pulse = ctx.audio.pulse(t, 0.25)
        grow = 0.85 + 0.25 * C.ease_out_cubic(M.seg(lt, 0.1, 1.2))
        for ring in range(4):
            rr = (56.0 + ring * 20.0 + 3.0 * math.sin(t * 1.6 + ring)) * grow
            for k in range(160):
                if (k + ring * 7) % 3 == 0:
                    continue
                aa = k * 2.0 * math.pi / 160.0 + t * (0.20 + 0.05 * ring)
                px = cx + math.cos(aa) * rr
                py = cy + math.sin(aa) * rr * 0.82
                cellx, celly = int(px) // 2, Y0 + int(py) // 4
                if (sy - 1 <= celly <= sy + sp.h
                        and sx - 1 <= cellx <= sx + sp.w):
                    continue
                br.plot(int(px), int(py),
                        C.mix(C.INK, C.GOLD,
                              0.40 + 0.30 * pulse - ring * 0.05), 0.9)
        for k in range(15):
            aa = math.pi * (0.10 + 0.80 * k / 14.0)
            r0, r1 = 52.0, 82.0 + 9.0 * math.sin(t * 2.0 + k)
            br.line(cx + math.cos(aa) * r0, cy - math.sin(aa) * r0,
                    cx + math.cos(aa) * r1, cy - math.sin(aa) * r1,
                    C.mix(C.INK, C.GOLD_DIM, 0.45 + 0.25 * pulse), 0.85)
        br.commit()

    # ==================================================================
    # movement 4+5 -- 52.390..63.860 : the waltz and the monument
    # ==================================================================
    def _shot_waltz(self, c, ctx, t: float, lt: float) -> None:
        S = self.script
        collapse = M.seg(t, COLLAPSE + 0.04, 63.50)
        e = collapse ** 2.1
        # full-bleed streaming code (the thing that holds the world up)
        boost = 1.0 - 0.72 * e
        self._code_sea(c, ctx, t, boost)
        # header rail (it dissolves as the collapse begins)
        if e < 0.55:
            k = 1.0 - e / 0.55
            c.text(Y0, 4, str(S.storm.header),
                   C.mix(C.INK, C.TERRA_HI, 0.75 * k))
            _rtext(c, Y0, C.W - 4, str(S.storm.trending),
                   C.mix(C.INK, C.GOLD_HI, 0.75 * k))
        # comment windows, far layers first
        for card, layout, accent, appear, wave, k in sorted(
                self._cards, key=lambda item: item[1][4]):
            if t < appear:
                continue
            self._waltz_card(c, ctx, t, lt, card, layout, accent, appear,
                             wave, k, e)
        # the monument collapsing out of the crowd
        self._monument(c, ctx, t, e, collapse)

    def _code_sea(self, c, ctx, t: float, boost: float) -> None:
        pulse = ctx.audio.pulse(t, 0.22)
        hit = max(M.hit_env(t, w, 0.5) for w in WAVES)
        bright = (0.80 + 0.30 * hit) * (0.95 + 0.30 * pulse) * boost
        for si, (x0, width, speed, phase, slot) in enumerate(self._streams):
            for k in range(9):
                yy = Y0 + int((phase + k * 6.2 - t * speed) % 55.0)
                idx = (si * 7 + k * 3 + int(phase)) % len(_CODE_LINES)
                line = _CODE_LINES[idx]
                col = C.mix(C.INK, slot, min(1.0, 0.74 * bright
                                             + 0.18 * M.hash01(si, k)))
                c.text(yy, x0, line[:width], col, None)
                if M.hash01(si, k, 7) > 0.80:
                    px = x0 + 2 + int(M.hash01(si, k, 9) * max(1, width - 4))
                    c.text(yy, px, line[2:5], C.mix(C.INK, C.TEXT_DIM,
                                                    0.75 * bright), None)

    def _waltz_card(self, c, ctx, t: float, lt: float, card, layout,
                    accent: int, appear: float, wave: int, k: int,
                    collapse: float) -> None:
        x, y, w, h, layer = layout
        # entry: spring in from off-frame, press on the waltz beat
        p = M.seg(t, appear, appear + 0.52)
        e_in = M.spring(p, freq=2.2, damp=0.34)
        dirx = -1.0 if k % 2 == 0 else 1.0
        dx = dirx * 30.0 * (1.0 - e_in)
        dy = (-12.0 if k % 2 else 12.0) * (1.0 - e_in)
        # beat press: a small lift on every waltz beat
        beat = ((t - WAVES[0]) % 0.96) / 0.96
        press = math.exp(-beat * 7.0) * 0.5
        dx += 2.2 * math.sin(t * 1.05 + k * 2.1)
        dy += 1.2 * math.sin(t * 0.90 + k * 1.7) - press
        # depth: far windows sit dimmer and lag behind
        depth = (0.66, 0.84, 1.0)[layer]
        dimk = depth * (0.72 + 0.28 * M.clamp01(e_in))
        dimk *= max(0.55, 1.0 - 0.045 * max(0.0, t - appear))
        yy = int(round(y + dy))
        xx = int(round(x + dx))
        # the collapse sucks every window into the centre, accelerating
        alpha = 1.0
        if collapse > 0.0:
            u = M.seg(t, COLLAPSE + 0.01 + 0.012 * k, 63.42)
            ce = u ** 1.55
            cx, cy = 100.0, 26.0
            vx = cx - (xx + w / 2.0)
            vy = cy - (yy + h / 2.0)
            ang = math.atan2(vy, vx) + ce * 2.4
            rad = math.hypot(vx, vy) * (1.0 - 0.95 * ce)
            xx = int(round(cx + math.cos(ang) * rad - w / 2.0))
            yy = int(round(cy + math.sin(ang) * rad - h / 2.0))
            alpha = 1.0 - 0.95 * ce
            dimk *= 1.0 + 0.4 * ce
            if ce > 0.82:
                return
        self._card(c, ctx, t, yy, xx, w, h, card, accent, dimk, alpha,
                   layer)

    def _card(self, c, ctx, t: float, y: int, x: int, w: int, h: int,
              card, accent: int, bright: float, alpha: float,
              layer: int) -> None:
        S = self.script.storm
        bright = M.clamp01(bright)
        bg = C.mix(C.INK, C.PANEL2, 0.30 + 0.30 * bright)
        bord = C.mix(C.INK, accent, 0.55 + 0.35 * bright)
        _shadow(c, y, x, h, w, ox=1 + layer, oy=1, amount=0.55)
        c.frame(y, x, h, w, bord, bg, style="rounded", fill=True)
        # title strip
        tag = str(card.tag)
        user = str(card.user)
        tbg = C.mix(bg, accent, 0.16 + 0.12 * bright)
        c.fill(y, x + 1, 1, w - 2, " ", C.TEXT, tbg)
        c.put(y, x + 2, "\u25c8", C.mix(tbg, accent, 0.9), tbg)
        c.text(y, x + 4, f"{tag.upper()}  {user}"[: w - 8], C.WHITE, tbg,
               bold=True)
        # a crafted glyph mark at the right of the title bar
        c.put(y, x + w - 3, "\u25c7", C.mix(tbg, accent, 0.8), tbg)
        # body: the comment text, three short lines
        lines = [str(s) for s in card.lines]
        for i, line in enumerate(lines[:3]):
            rr = y + 1 + i
            if rr >= y + h - 3:
                break
            c.text(rr, x + 2, line[: w - 4],
                   C.mix(bg, C.TEXT, 0.55 + 0.40 * bright), bg)
        # footer rail with the card metrics
        if h >= 8:
            fy = y + h - 3
            c.hline(fy, x + 1, x + w - 1, C.mix(bg, accent, 0.25), bg,
                    "\u2500")
            c.text(fy + 1, x + 2, str(S.card_metrics)[: w - 4],
                   C.mix(bg, C.TEXT_DIM, 0.85), bg)
            tier = str(S.card_tiers[0] if w > 36 else S.card_tiers[1])
            _rtext(c, fy + 1, x + w - 2, tier,
                   C.mix(bg, accent, 0.85))
        if alpha < 0.995:
            _dim_rect(c, y, x, h, w, max(0.05, 0.15 + 0.85 * alpha))

    def _monument(self, c, ctx, t: float, e: float, collapse: float) -> None:
        S = self.script.finale
        # contracting gold ring, then the detonation
        br = c.braille(Y0, 0, BAND_H, C.W)
        cx, cy = 200.0, (26 - Y0) * 4.0
        # radial speed streaks: the crowd is being dragged inward
        if collapse > 0.04:
            for k in range(130):
                h1 = M.hash01(k, 21)
                h2 = M.hash01(k, 33)
                ang = h1 * 2.0 * math.pi + t * 0.6
                rad = (24.0 + 150.0 * h2) * (1.0 - 0.90 * collapse)
                ln = 6.0 + 10.0 * collapse
                cos_a, sin_a = math.cos(ang), math.sin(ang) * 0.55
                br.line(cx + cos_a * rad, cy + sin_a * rad,
                        cx + cos_a * (rad - ln), cy + sin_a * (rad - ln),
                        C.mix(C.INK, C.GOLD_DIM,
                              0.45 + 0.45 * collapse), 0.9)
        if collapse > 0.02:
            r = M.lerp(150.0, 16.0, M.ease_in_expo(min(1.0, collapse)))
            for ring in range(3):
                rr = max(2.0, r + ring * 7.0 * (1.0 - collapse))
                for k in range(160):
                    if (k + ring * 5) % 3 == 0:
                        continue
                    aa = k * 2.0 * math.pi / 160.0 + t * (0.5 + 0.2 * ring)
                    br.plot(int(cx + math.cos(aa) * rr),
                            int(cy + math.sin(aa) * rr * 0.55),
                            C.mix(C.INK, C.GOLD_HI,
                                  0.30 + 0.60 * collapse - ring * 0.08), 0.9)
        # detonation: the ring bursts outward and the dust flies
        det = M.seg(t, 63.52, 63.84)
        if det > 0.0:
            rr = 16.0 + 150.0 * M.ease_out_expo(det)
            for k in range(200):
                aa = k * 2.0 * math.pi / 200.0
                br.plot(int(cx + math.cos(aa) * rr),
                        int(cy + math.sin(aa) * rr * 0.55),
                        C.mix(C.GOLD, C.WHITE, det * 0.7), 0.95)
            for k in range(150):
                h1 = M.hash01(k, 5)
                h2 = M.hash01(k, 9)
                aa = h1 * 2.0 * math.pi
                rad = (6.0 + 130.0 * M.ease_out_expo(det)) * (0.45 + 0.55 * h2)
                br.plot(int(cx + math.cos(aa) * rad),
                        int(cy + math.sin(aa) * rad * 0.55),
                        C.mix(C.GOLD_HI, C.WHITE, 0.5 * det), 0.9)
        br.commit()

        # the accelerating counter (a milestone, not a dashboard)
        if collapse > 0.10:
            u = M.seg(t, 61.10, 63.42)
            n = int(1_000_000 * (100.0 ** (u ** 1.7)))
            txt = f"{n:,}"
        else:
            txt = ""
        k = C.ease_out_cubic(M.seg(t, COLLAPSE + 0.30, 62.10))
        if txt and k > 0.02:
            w = M.big_text_size(txt, 2, 2)[0]
            x0 = max(4, 100 - w // 2)
            # a dark plate keeps the milestone readable over the crowd
            c.fill(20, max(0, x0 - 3), 18, min(C.W, w + 6), " ", C.TEXT,
                   C.mix(C.INK, C.BLACK, 0.80))
            col = C.mix(C.INK, C.GOLD_HI, 0.20 + 0.80 * k)
            M.big_text(c, 22, x0, txt, col, scale=2, spacing=2,
                       top=C.GOLD, bottom=C.WHITE)
        if k > 0.05:
            _ctext(c, 18, M.spread_text(str(S.monument_1), 3),
                   C.mix(C.INK, C.TERRA_HI, 0.95 * k), None, bold=True)
            _ctext(c, 39, M.spread_text(str(S.monument_3), 2),
                   C.mix(C.INK, C.GOLD_HI, 0.95 * k), None, bold=True)
        # small monument furniture (header, bell, mantra)
        if t > COLLAPSE + 0.1:
            hk = M.clamp01((t - COLLAPSE - 0.1) / 0.8)
            c.text(Y0, 4, str(S.header), C.mix(C.INK, C.GOLD_DIM, hk))
            _rtext(c, Y0, C.W - 4, str(S.bell), C.mix(C.INK, C.GOLD_DIM, hk))
            _ctext(c, 44, str(S.deity),
                   C.mix(C.INK, C.GOLD_HI, 0.80 * hk))
            _ctext(c, 46, str(S.subline), C.mix(C.INK, C.TEXT_DIM, hk))
            _rtext(c, 51, C.W - 4, str(S.footer),
                   C.mix(C.INK, C.TEXT_FAINT, hk))
        # the last frames wash to the next chapter's bell gold
        gold = M.seg(t, 63.42, 63.86)
        if gold > 0.0:
            for yy in range(Y0, Y1):
                v = 1.0 - abs(yy - 26) / 27.0
                col = C.mix(C.INK, C.mix(C.GOLD_DEEP, C.GOLD_HI,
                                         0.30 + 0.55 * v), gold)
                c.fill_bg(yy, 0, 1, C.W, col)
            if gold > 0.55:
                c.fx.flash = max(c.fx.flash, (gold - 0.55) * 0.55)
                c.fx.flash_color = C.GOLD_HI
            M.punctuate(c, t - 63.50, flash=0.75, shake=5.0, chroma=0.55,
                        decay=0.14, flash_color=C.GOLD_HI)
