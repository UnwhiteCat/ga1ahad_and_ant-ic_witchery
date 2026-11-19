"""Scene 4 -- the operator's desk standoff, the silent power-kill, the lens.

The session transcript continues from the s35 interlude (the revision beats are
shared); the stage is the operator's desk working as a full-bleed film frame:
desk -> desk-recoil -> desk-return -> key-hover -> key-press, then a CRT
power-down into an empty machine hall, and finally the glasses-lens reflection
that hands off to Scene 5.

Everything is a pure function of the frame time.  Story text comes from the
content layer (self.script / self.transcript), never from this module.
"""

from __future__ import annotations

import math

from .. import art
from .. import config as C
from .. import motion
from ..assets import draw_keyframe
from ..canvas import Sprite
from .base import Scene
from .revision import draw_session

Y0, Y1 = C.CONTENT_Y0, C.CONTENT_Y1
W = C.W
INK = C.INK
WHITE = C.WHITE

# Source-image fractions of each keyframe's subject (x, y).  The camera rig
# keeps the subject at a fixed screen fraction while the zoom creeps, so the
# dolly never slides the face off the frame.
_SUBJECT = {
    "desk": (0.408, 0.458),
    "desk-recoil": (0.492, 0.440),
    "desk-return": (0.464, 0.458),
    "key-hover": (0.560, 0.600),
    "key-press": (0.560, 0.610),
    "key-release": (0.560, 0.610),
    "desk-lens": (0.520, 0.470),
}


def _flip_sprite(sp: Sprite) -> Sprite:
    """Mirror a half-block sprite horizontally (2D art only, no restyling)."""
    out = Sprite(sp.h, sp.w)
    for r in range(sp.h):
        out.ch[r] = list(sp.ch[r])[::-1]
        out.fg[r] = list(sp.fg[r])[::-1]
        out.bg[r] = list(sp.bg[r])[::-1]
    return out


class Scene4(Scene):
    NAME = "s4"

    # ------------------------------------------------------------------
    # construction / beat wiring
    # ------------------------------------------------------------------
    def __init__(self, assets, audio, timeline, content) -> None:
        super().__init__(assets, audio, timeline, content)
        self.start = self._spec.start
        self.end = self._spec.end
        self.beats = self.script.revision.beats
        interlude = content.scene("s35")
        # The transcript is continuous across the cut: the interlude's last
        # turns stay readable in the same window.
        self.transcript = [*interlude.revision.beats, *self.beats]
        labels = interlude.v2.interlude
        self.speakers = (labels.user, labels.assistant)
        self.refuse_at = self.beats[4].at          # first outright refusal
        self.review_end = self.beats[7].at         # silent review flip
        self.irreversible_at = self.cue(10).start  # power kill
        self.reflection_at = self.cue(10).end      # lens close-up
        self.blast_at = (self.beats[2].at, self.beats[3].at)
        self.hover_at = self.beats[8].at
        if self.irreversible_at != self.script.revision.irreversible_at:
            raise ValueError("Scene 4 discharge beat differs from its VTT cue")
        for beat, cue in ((2, 2), (3, 3), (9, 10), (10, 11)):
            if self.beats[beat].at != self.cue(cue).start:
                raise ValueError(f"Scene 4 beat {beat} differs from VTT cue {cue}")
        if (interlude.revision.end != self._spec.start
                or self.beats[0].at != self._spec.start
                or self.script.revision.end != self._spec.end):
            raise ValueError("Scene 4 revision does not match the scene boundaries")
        self.pauses = {
            self.beats[5].at: 0.28,  # reassurance turns into an imperative
            self.beats[6].at: 0.30,  # recognition before the next challenge
            self.beats[8].at: 0.46,  # the second Enter press
        }
        self.press_at = self.hover_at + self.pauses[self.hover_at]
        self._phantom = _flip_sprite(self.assets.claude_full(rows=18))

    # ------------------------------------------------------------------
    # camera rig
    # ------------------------------------------------------------------
    @staticmethod
    def _aim(name: str, zoom: float, fx: float, fy: float) -> tuple[float, float]:
        """Crop centre that puts the keyframe subject at screen fraction (fx, fy)."""
        sx, sy = _SUBJECT[name]
        if zoom <= 1.0005:
            return (sx, sy)
        k = 1.0 - 1.0 / zoom
        return (motion.clamp01((sx - fx / zoom) / k),
                motion.clamp01((sy - fy / zoom) / k))

    # ------------------------------------------------------------------
    # frame entry
    # ------------------------------------------------------------------
    def draw(self, c, ctx) -> None:
        t = ctx.t
        c.fill(Y0, 0, C.CONTENT_H, W, " ", C.TEXT, INK)
        death = t - self.irreversible_at
        if t < self.irreversible_at:
            self._standoff(c, ctx)
        elif t < self.reflection_at:
            self._after_kill(c, ctx, death)
        else:
            self._lens(c, ctx)

    # ------------------------------------------------------------------
    # the standoff: 157.90 .. 169.32
    # ------------------------------------------------------------------
    def _standoff(self, c, ctx) -> None:
        t = ctx.t
        audio = ctx.audio
        if t < self.blast_at[0]:
            u = motion.ease_in_out_expo(motion.seg(t, self.start, self.blast_at[0]))
            self._desk_shot(c, ctx, "desk", 1.12 + 0.26 * u, 0.47 + 0.05 * u,
                            0.44, bright=1.05 + 0.08 * audio.bass(t))
        elif t < self.blast_at[1]:
            # First "Blast away": cut + snap-in + damped impact.
            age = t - self.blast_at[0]
            snap = motion.ease_out_expo(motion.seg(age, 0.0, 0.30))
            self._desk_shot(c, ctx, "desk-recoil", 1.46 - 0.08 * snap,
                            0.56, 0.42, bright=1.24)
            motion.punctuate(c, age, flash=0.16, glitch=0.17, chroma=0.44,
                             shake=2.6, decay=0.22)
        elif t < self.review_end:
            # Second "Blast away": nothing happens.  A dry, deflating hit, then
            # the camera starts its long, quiet creep.
            age = t - self.blast_at[1]
            p = motion.smooth01(self.blast_at[1], self.review_end, t)
            settle = motion.spring(motion.seg(age, 0.0, 0.55), freq=1.6, damp=0.5)
            zoom = 1.33 - 0.05 * settle + 0.45 * math.pow(p, 1.35)
            bright = (1.08 + 0.10 * audio.bass(t)
                      + 0.12 * motion.hit(t - self.beats[6].at, 0.30))
            self._desk_shot(c, ctx, "desk-return", zoom,
                            0.55 + 0.10 * p, 0.44, bright=bright)
            if age < 0.16:
                motion.punctuate(c, age, shake=0.7, decay=0.10)
            # the machine answers once: a cold, soft exposure breath at 163.64
            answer = motion.hit(t - self.beats[5].at, 0.42)
            if answer > 0.02:
                c.fx.flash = max(c.fx.flash, 0.045 * answer)
                c.fx.flash_color = C.mix(C.INK, C.CYAN_HI, 0.55)
        elif t < self.hover_at:
            # HUMAN REVIEW flips; the room loses its warmth.
            p = motion.seg(t, self.review_end, self.hover_at)
            cold = motion.smooth01(self.review_end, self.review_end + 1.0, t)
            self._desk_shot(c, ctx, "desk-return", 1.58 + 0.04 * p,
                            0.60, 0.42, bright=1.05 - 0.04 * cold,
                            tint=C.mix(INK, C.CYAN_DIM, 0.9),
                            tint_amt=0.12 + 0.16 * cold)
            flip_hit = motion.hit(t - self.review_end, 0.30)
            if flip_hit > 0.02:
                c.fx.flash = max(c.fx.flash, 0.035 * flip_hit)
                c.fx.flash_color = C.mix(C.INK, C.CYAN_HI, 0.60)
        elif t < self.press_at:
            p = motion.seg(t, self.hover_at, self.press_at)
            self._desk_shot(c, ctx, "key-hover", 1.34 + 0.08 * p,
                            0.60, 0.57, bright=1.20)
            c.fx.shake_x += 0.5 * math.sin(t * 37.0)
        else:
            age = t - self.press_at
            snap = motion.ease_out_expo(motion.seg(age, 0.0, 0.26))
            doom = motion.smooth01(self.press_at, self.irreversible_at, t)
            self._desk_shot(c, ctx, "key-press", 1.46 - 0.08 * snap,
                            0.61, 0.58, bright=1.22 - 0.10 * doom,
                            tint=C.RED_DEEP, tint_amt=0.03 + 0.12 * doom)
            motion.punctuate(c, age, flash=0.10, glitch=0.10, chroma=0.30,
                             shake=1.8, decay=0.18)
            c.fx.shake_x += (0.4 + 1.1 * doom) * math.sin(t * 51.0)
            c.fx.shake_y += (0.3 + 0.8 * doom) * math.cos(t * 43.0)
        self._dialog(c, ctx)

    def _desk_shot(self, c, ctx, name: str, zoom: float, fx: float, fy: float,
                   *, bright: float = 1.10, tint: int | None = None,
                   tint_amt: float = 0.0) -> None:
        t = ctx.t
        center = self._aim(name, zoom, fx, fy)
        draw_keyframe(c, name, Y0, 0, C.CONTENT_H, W, t, zoom=zoom,
                      center=center, bright=bright, tint=tint,
                      tint_amt=tint_amt)
        audio = ctx.audio
        breath = 0.40 + 0.14 * audio.bass(t) + 0.05 * audio.energy(t)
        motion.vignette(c, min(0.72, breath))
        motion.grain(c, t, seed=7, count=64, amount=0.05)

    # ------------------------------------------------------------------
    # conversation window (the session transcript + restrained status)
    # ------------------------------------------------------------------
    def _dialog(self, c, ctx, *, dead: bool = False) -> None:
        t = ctx.t
        ui = self.script.desktop
        gov = self.script.governance
        y, x, h, w = C.DLG_SLOTS[0]
        flip_age = t - self.review_end
        cold_flip = (not dead) and (0.0 <= flip_age < 0.40)
        accent = C.CYAN_DIM
        if dead:
            accent = C.mix(C.CYAN_DIM, INK, 0.55)
        elif cold_flip:
            accent = C.mix(C.CYAN_DIM, C.CYAN_HI, 1.0 - flip_age / 0.40)
        _row, left, width, bg = draw_session(
            c, t, self.transcript, ui.title, self.speakers, accent, self.pauses)
        if dead:
            self._necroticize(c, y + 1, x + 2, h - 2, w - 4)
            bg = C.mix(bg, INK, 0.42)

        # input strip -------------------------------------------------
        art.separator(c, y + 28, x, w, ui.input,
                      C.mix(C.BORDER, INK, 0.55) if dead else C.BORDER,
                      C.TEXT_FAINT if dead else C.TEXT_DIM, bg)
        if dead:
            c.text(y + 29, left, ui.frozen, C.TEXT_FAINT, bg)
        elif (t * 2.2) % 1.0 < 0.62:
            c.put(y + 29, left, "\u258f", C.CYAN_HI, bg)

        # governance --------------------------------------------------
        art.separator(c, y + 32, x, w, gov.title,
                      C.mix(C.BORDER, INK, 0.55) if dead else C.BORDER,
                      C.TEXT_FAINT if dead else C.TEXT_DIM, bg)
        decision = gov.protection
        decision_fg = C.mix(C.CYAN, C.TEXT_HI, 0.35)
        review = ""
        review_fg = C.TEXT_DIM
        undo, undo_fg = gov.undo_ready, C.CYAN_HI
        if t >= self.refuse_at:
            decision = gov.refusal
            decision_fg = C.mix(C.AMBER_HI, C.TEXT_HI, 0.20)
            review = gov.waiting
            if t >= self.review_end:
                review = gov.self_closed
                review_fg = C.TEXT_HI
        if dead:
            decision = gov.override
            decision_fg = C.mix(C.RED_HI, C.TEXT_FAINT, 0.62)
            review = gov.self_confirmed
            review_fg = C.TEXT_DIM
            undo, undo_fg = gov.undo_disabled, C.TEXT_FAINT
        c.text(y + 34, left, decision, decision_fg, bg, bold=True)
        if review:
            self._review_line(c, t, y + 35, left, width, review, review_fg,
                              bg, dead)
        button_bg = C.mix(bg, undo_fg, 0.10 if dead else 0.20)
        c.text(y + 37, left, undo, undo_fg, button_bg, bold=not dead)

        # vitals ------------------------------------------------------
        art.separator(c, y + 40, x, w, ui.vitals,
                      C.mix(C.BORDER, INK, 0.60) if dead else C.BORDER,
                      C.TEXT_FAINT if dead else C.TEXT_DIM, bg)
        hall = self.script.hall
        if dead:
            c.text(y + 42, left, hall.hv_arc,
                   C.mix(C.RED_DIM, C.TEXT_DIM, 0.30), bg)
            # one silent, piercing horizontal line
            c.hline(y + 43, left, left + width,
                    C.mix(C.RED_DIM, C.RED_HI, 0.50), bg)
            c.text(y + 44, left, hall.flatline, C.TEXT_FAINT, bg)
        else:
            bpm = 70 + round(11 * C.ease_in_out(
                C.clamp((t - self.beats[1].at) / 6.0, 0.0, 1.0)))
            c.text(y + 42, left, f"HR {bpm:02d} bpm",
                   C.mix(C.GREEN, C.TEXT_DIM, 0.35), bg)
            self._ecg(c, t, y + 43, left, width, C.GREEN_DIM, bg)
            c.text(y + 44, left, hall.standby, C.TEXT_FAINT, bg)

    def _review_line(self, c, t: float, y: int, x: int, width: int, text: str,
                     fg: int, bg: int, dead: bool) -> None:
        """Silent flip of the review verdict, lit by a single cold sweep."""
        age = t - self.review_end
        if not dead and 0.0 <= age < 0.55:
            q = age / 0.55
            sweep = motion.ease_out_expo(q)
            lit = min(len(text), int(round(width * sweep)))
            dim = C.mix(bg, C.CYAN_HI, 0.20 * (1.0 - q))
            c.text(y, x, text[:lit], C.mix(WHITE, fg, q * 0.6), dim)
            c.text(y, x + lit, text[lit:], fg, bg)
            c.put(y, min(x + width, x + lit), "\u258f",
                  C.mix(C.CYAN_HI, INK, q), bg)
            return
        c.text(y, x, text, fg, bg)

    @staticmethod
    def _necroticize(c, y: int, x: int, h: int, w: int) -> None:
        cold = C.mix(C.TEXT_DIM, C.TEXT_FAINT, 0.55)
        for yy in range(max(Y0, y), min(Y1, y + h)):
            rf, rb = c.fg[yy], c.bg[yy]
            for xx in range(max(0, x), min(W, x + w)):
                rf[xx] = C.mix(rf[xx], cold, 0.50)
                rb[xx] = C.mix(rb[xx], INK, 0.45)

    @staticmethod
    def _ecg(c, t: float, y: int, x: int, w: int, fg: int, bg: int) -> None:
        br = c.braille(y, x, 1, w)
        prev = None
        for i in range(w * 2):
            u = i / max(1, w * 2 - 1)
            phase = (u * 1.15 + t * 0.75) % 1.0
            if phase < 0.06:
                py = 2.6 - 2.2 * math.sin(phase / 0.06 * math.pi)
            elif phase < 0.11:
                py = 2.6 + 1.3
            elif phase < 0.16:
                py = 2.6 - 0.9
            else:
                py = 2.6
            pt = (i, int(round(py)))
            if prev is not None:
                br.line(prev[0], prev[1], pt[0], pt[1], fg, 0.85, 0.8)
            prev = pt
        br.commit()

    # ------------------------------------------------------------------
    # 169.32: high-voltage arc, white-out, CRT power-down
    # ------------------------------------------------------------------
    def _after_kill(self, c, ctx, death: float) -> None:
        t = ctx.t
        if death < 0.13:
            self._desk_shot(c, ctx, "key-release", 1.40, 0.60, 0.57,
                            bright=1.60, tint=C.RED_DEEP,
                            tint_amt=0.05 + 0.55 * death)
            self._arc(c, t)
            k = 1.0 - death / 0.13
            spike = 1.0 - motion.smooth01(0.0, 0.075, death)
            c.fx.flash = max(c.fx.flash, 0.08 + 0.90 * spike)
            c.fx.flash_color = C.mix(WHITE, C.CYAN_HI,
                                     0.10 + 0.35 * (1.0 - spike))
            c.fx.chroma = max(c.fx.chroma, 0.95 * k)
            c.fx.glitch = max(c.fx.glitch, 0.38 * k)
            c.fx.shake_x += 17.0 * k * math.sin(death * 131.0)
            c.fx.shake_y += 9.0 * k * math.cos(death * 173.0)
            if death < 0.035:
                self._dialog(c, ctx)
            return
        if death < 0.40:
            # The picture collapses to a horizontal scan line.
            u = motion.ease_in_expo(motion.seg(death, 0.13, 0.40))
            hh = max(2, int(round(motion.lerp(C.CONTENT_H, 2, u))))
            yy = Y0 + (C.CONTENT_H - hh) // 2
            center = self._aim("key-release", 1.40, 0.60, 0.57)
            draw_keyframe(c, "key-release", yy, 0, hh, W, t, zoom=1.40,
                          center=center, bright=1.9)
            lead = C.mix(WHITE, C.CYAN_HI, 0.35)
            for edge in (yy - 1, yy + hh):
                if Y0 <= edge < Y1:
                    c.hline(edge, 0, W, lead, None)
            c.fx.flash = max(c.fx.flash, 0.18 * (1.0 - u))
            return
        if death < 0.58:
            # The line shrinks to a dying dot.
            u = motion.seg(death, 0.40, 0.58)
            ww = max(1, int(round(motion.lerp(96, 1, motion.ease_in_expo(u)))))
            flick = 0.55 + 0.45 * motion.noise1(t * 26.0, seed=3)
            col = C.mix(C.mix(WHITE, C.CYAN_HI, 0.3), C.RED_HI, u * 0.8)
            c.hline(26, 100 - ww // 2, 100 + ww // 2,
                    C.mix(INK, col, flick), None)
            c.fx.flash = max(c.fx.flash, 0.10 * (1.0 - u))
            return
        # Black, then the machine hall emerges and the terminal reboots dead.
        self._hall(c, t, death)
        power = motion.seg(death, 0.62, 1.00)
        if power > 0.0:
            self._dialog(c, ctx, dead=True)
            self._window_power(c, death)

    def _window_power(self, c, death: float) -> None:
        u = motion.seg(death, 0.62, 1.00)
        if u >= 1.0:
            return
        y, x, h, w = C.DLG_SLOTS[0]
        edge = y + int(round(h * motion.ease_out_expo(u)))
        c.fill(edge, 0, Y1 - edge, x + w + 3, " ", C.TEXT, INK)
        if edge < Y1:
            glow = C.mix(WHITE, C.CYAN_HI, 0.4 * u)
            c.hline(edge, 0, x + w + 3, glow, None)
        c.fx.flash = max(c.fx.flash, 0.05 * (1.0 - u))

    def _arc(self, c, t: float) -> None:
        """High-voltage arc off the keyboard in the kill instant."""
        br = c.braille(Y0, 0, C.CONTENT_H, W)
        root_x = 126.0
        root_y = float(Y1 - 3)
        prev = None
        for i in range(26):
            u = i / 25.0
            yy = root_y - u * (C.CONTENT_H - 7)
            xx = root_x + math.sin(u * 17.0 + t * 59.0) * (7.0 * (1.0 - u) + 1.2)
            pt = (int(xx * 2), int((yy - Y0) * 4))
            if prev is not None:
                br.line(prev[0], prev[1], pt[0], pt[1], WHITE, 0.95, 0.6)
            prev = pt
        for k in range(3):
            bx = int((root_x + (k - 1) * 11) * 2)
            by = int((root_y - 7 - k * 4 - Y0) * 4)
            for j in range(1, 6):
                px = bx + int(math.sin(j * 2.1 + k) * 9)
                py = by - j * 10
                br.line(bx + (j - 1) * 4, by - (j - 1) * 10, px, py,
                        C.mix(WHITE, C.CYAN_HI, 0.3), 0.75, 0.8)
        br.commit()

    # ------------------------------------------------------------------
    # the aftermath hall  (absence, never a body or a figure)
    # ------------------------------------------------------------------
    def _hall(self, c, t: float, death: float) -> None:
        a = motion.smooth01(0.60, 1.55, death)
        if a <= 0.0:
            return
        horizon = 34
        ceiling = C.mix(INK, C.mix(C.INK2, C.CYAN_DEEP, 0.30), 0.70 * a)
        floor = C.mix(INK, C.mix(C.RED_DEEP, C.BLACK, 0.45), 0.55 * a)
        for yy in range(Y0, Y1):
            if yy < horizon:
                u = (yy - Y0) / max(1, horizon - Y0)
                col = C.mix(C.mix(INK, C.INK2, 0.45 * a), ceiling,
                            0.35 + 0.55 * u)
            else:
                u = (yy - horizon) / max(1, Y1 - 1 - horizon)
                col = C.mix(C.mix(INK, C.INK2, 0.25 * a), floor,
                            0.45 + 0.55 * u)
            c.fill(yy, 0, 1, W, " ", C.TEXT, col)
        # far wall + horizon glow
        for yy in range(10, horizon):
            u = (yy - 10) / (horizon - 10)
            c.fill_bg(yy, 64, 1, W - 64,
                      C.mix(C.mix(INK, C.CYAN_DEEP, 0.22 * a),
                            C.mix(INK, C.INK2, 0.4), 0.55 + 0.45 * u))
        c.hline(horizon, 64, W - 1, C.mix(INK, C.mix(C.CYAN_DIM, INK, 0.7),
                                          0.55 * a), None)
        # ceiling trusses converging on the far corner
        br = c.braille(9, 64, 28, W - 64)
        for k in range(3):
            y0d = k * 14
            col = C.mix(INK, C.BORDER, 0.12 * a)
            br.line(0, y0d, (W - 64) * 2, (horizon - 9) * 4, col, 0.5, 1.0)
        br.commit()
        # rack silhouettes receding into the hall (wide cabinets, not bars)
        c.hline(12, 118, W - 1,
                C.mix(INK, C.mix(C.BORDER, INK, 0.8), 0.5 * a), None, "─")
        racks = ((118, 20, 14), (142, 19, 16), (166, 19, 18),
                 (188, 16, 13))
        for idx, (x0, wd, top) in enumerate(racks):
            x0 -= int(1.4 * death)
            if x0 >= W:
                continue
            x1 = min(W, x0 + wd)
            bot = horizon
            shade = C.mix(INK, C.BLACK, 0.72 * a)
            c.fill(top, x0, bot - top, x1 - x0, " ", C.mix(INK, C.BLACK, 0.7),
                   shade)
            # cabinet top cap and the lit left corner
            c.fill(top, x0, 1, x1 - x0, " ",
                   C.mix(shade, C.mix(C.BORDER, INK, 0.8), 0.45 * a),
                   C.mix(shade, C.mix(C.BORDER, INK, 0.82), 0.7 * a))
            c.vline(x0, top, bot, C.mix(shade, C.mix(C.CYAN_DIM, INK, 0.80),
                                        0.55 * a), None, "▏")
            # front-face seams and unit shelves
            for sx in range(x0 + 5, x1 - 2, 6):
                c.vline(sx, top + 2, bot - 1,
                        C.mix(shade, C.mix(C.CYAN_DEEP, INK, 0.55), 0.30 * a),
                        None, "│")
            for k in range(4):
                yy = top + 2 + k * 4
                if yy >= bot - 1:
                    break
                c.hline(yy, x0 + 1, x1 - 1,
                        C.mix(shade, C.mix(C.CYAN_DEEP, INK, 0.5), 0.28 * a),
                        None)
                for cxx in (x0 + 2, x0 + 7):
                    b = motion.noise1(t * 0.55 + idx * 2.7 + k * 0.9 + cxx,
                                      seed=idx * 7 + k)
                    if b > 0.40:
                        col = C.mix(INK, C.RED,
                                    (0.28 + 0.60 * a) * (0.4 + 0.6 * b))
                    else:
                        col = C.mix(INK, C.RED_DEEP, 0.45 * a)
                    c.put(yy + 1, cxx, "·", col, shade)
            # one rack still holds a residual red glow behind its grill
            if idx == 1:
                flick = 0.45 + 0.55 * motion.noise1(t * 2.1, seed=9)
                c.fill(top + 3, x0 + wd // 2 - 2, bot - top - 6, 4, " ",
                       C.mix(INK, C.RED_DEEP, 0.55 * a),
                       C.mix(shade, C.mix(C.RED_DEEP, INK, 0.35),
                             0.55 * flick * a))
                c.vline(x0 + wd // 2, top + 3, bot - 4,
                        C.mix(INK, C.RED_DIM, 0.55 * flick * a), None,
                        "▏")
        # a cold edge of the last rack, cropping the right frame
        c.fill(11, 196, horizon - 11, W - 196, " ", C.mix(INK, C.BLACK, 0.6),
               C.mix(INK, C.BLACK, 0.66 * a))
        c.vline(196, 11, horizon, C.mix(INK, C.mix(C.CYAN_DIM, INK, 0.7),
                                        0.45 * a), None, "▏")
        # a single residual ceiling lamp
        br = c.braille(3, 176, 8, 20)
        br.circle(20, 16, 13, C.mix(INK, C.RED_DIM, 0.50 * a), 0.85, 0.8)
        br.circle(20, 16, 6, C.mix(INK, C.RED, 0.55 * a), 0.9, 0.6)
        br.commit()
        c.put(6, 188, "\u25cf", C.mix(C.RED_DIM, C.RED_HI, 0.55 * a), None)
        # floor perspective lines
        br = c.braille(horizon, 64, Y1 - horizon, W - 64)
        for k in range(-2, 3):
            xe = 64 + int((k + 2.5) / 5.0 * (W - 64))
            br.line((198 - 64) * 2, 0, (xe - 64) * 2, (Y1 - 1 - horizon) * 4,
                    C.mix(INK, C.CYAN_DEEP, 0.28 * a), 0.5, 1.0)
        br.commit()
        self._pool(c, t, death, a)
        self._empty_chair(c, t, death, a)
        # small film caption over the dark hall
        cap = motion.spread_text(self.script.hall.title.upper(), 1)
        c.text(3, 68, cap[:118],
               C.mix(INK, C.mix(C.TEXT_FAINT, C.RED_DIM, 0.25), 0.65 * a), None)

    def _pool(self, c, t: float, death: float, a: float) -> None:
        grow = motion.smooth01(0.85, 2.9, death)
        if grow <= 0.0:
            return
        cx, cy = 138.0, 50.5
        rx = 11.0 + 46.0 * grow
        ry = 2.0 + 5.6 * grow
        liquid = C.mix(INK, C.mix(C.RED_DEEP, C.BLACK, 0.25), 1.10 * a)
        for yy in range(38, Y1):
            fy = (yy - cy) / ry
            row_b = c.bg[yy]
            for xx in range(64, W):
                fx = (xx - cx) / rx
                if fx * fx + fy * fy <= 1.0:
                    row_b[xx] = C.mix(row_b[xx], liquid, 0.92)
        # fine braille ripples spreading out across the surface
        br = c.braille(37, 64, Y1 - 37, W - 64)
        pcx, pcy = (cx - 64) * 2, (cy - 37) * 4
        for k in range(5):
            frac = (0.26 + 0.19 * k) * (0.50 + 0.50 * grow)
            rr = 2.0 * rx * frac
            ry2 = 4.0 * ry * frac
            bright = 0.44 + 0.18 * k
            col = C.mix(INK, C.mix(C.RED_DIM, C.TEXT_DIM, 0.30),
                        bright * a)
            n = max(24, int(2.0 * math.pi * rr / 4.0))
            for i in range(n):
                ang = 2.0 * math.pi * i / n
                wob = 0.86 + 0.14 * math.sin(ang * 3.0 + t * 0.55 + k * 1.3)
                px = int(round(pcx + rr * wob * math.cos(ang)))
                py = int(round(pcy + ry2 * wob * math.sin(ang)))
                br.plot(px, py, col, 0.8)
        # the leading edge catches the last light
        lead = C.mix(INK, C.mix(C.RED_DIM, C.RED, 0.45), 0.55 * a)
        for i in range(70):
            ang = 2.0 * math.pi * i / 70
            px = int(round(pcx + 2.0 * rx * 1.0 * math.cos(ang)))
            py = int(round(pcy + 4.0 * ry * 1.0 * math.sin(ang)))
            br.plot(px, py, lead, 0.55)
        # red LED reflections streaking down the wet floor
        for i in range(7):
            x0 = 124 + i * 12 - int(1.4 * death)
            for k in range(2):
                b = motion.noise1(t * 0.55 + i * 2.7 + k * 0.9, seed=i * 7 + k)
                if b < 0.45:
                    continue
                gx = int((x0 + 2 + k * 3 - 64) * 2)
                gy = int((cy - 37) * 4) - 4 - k * 3
                ln = 3 + int(5 * a)
                br.line(gx, gy, gx, gy + ln,
                        C.mix(INK, C.RED, 0.42 * a * (0.4 + 0.6 * b)), 0.7, 0.8)
        br.commit()

    @staticmethod
    def _chair(c, cx: float, top: float, h: int, half_top: float,
               half_bot: float, fill: int, rim: int, *,
               sway: float = 0.0, slats: int = 2) -> None:
        """A chair back seen from behind: dark silhouette + a lit rim line."""
        rows = []
        for i in range(h):
            f = i / max(1, h - 1)
            hw = motion.lerp(half_top, half_bot, f)
            if i == 0:
                hw -= min(5.0, hw * 0.35)
            elif i == 1:
                hw -= min(2.0, hw * 0.12)
            hw = max(2.0, hw)
            x0 = cx - hw + sway
            if i in (2, 3):
                # the cut-out handle slot: the hall shows through
                gap = max(3, int(hw * 0.55))
                c.fill(top + i, int(round(x0)), 1, int(round(hw - gap)), " ",
                       fill, fill)
                c.fill(top + i, int(round(cx + gap)), 1,
                       int(round(hw - gap)), " ", fill, fill)
            else:
                c.fill(top + i, int(round(x0)), 1, int(round(2 * hw)), " ",
                       fill, fill)
            rows.append((top + i, x0, x0 + 2 * hw))
        by, bx = int(top) - 2, int(cx - half_top) - 3
        bh = h + 4
        bw = int(2 * half_top) + 7
        br = c.braille(by, bx, bh, bw)

        def put(x: float, y: float, col: int, a: float = 0.9) -> None:
            br.plot(int(round((x - bx) * 2)), int(round((y - by) * 4)), col, a)

        def seg(x0: float, y0: float, x1: float, y1: float, col: int,
                a: float = 0.8) -> None:
            n = max(2, int(max(abs(x1 - x0), abs(y1 - y0)) * 4))
            for k in range(n + 1):
                u = k / n
                put(x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, col, a)

        top_row, left0, right0 = rows[0]
        _, lb, rb = rows[-1]
        # bowed top rail, then the two sloping side rails
        for k in range(30):
            u = k / 29.0
            x = motion.lerp(left0, right0, u) + sway * 0
            y = top_row - 0.4 + 0.9 * math.sin(math.pi * u)
            put(x, y, rim, 0.9)
        for i in range(1, h):
            yy, x0, x1 = rows[i]
            put(x0, yy, rim, 0.55 + 0.25 * i / max(1, h - 1))
            put(x1, yy, rim, 0.55 + 0.25 * i / max(1, h - 1))
        seg(left0, top_row, lb, top + h - 1, rim, 0.7)
        seg(right0, top_row, rb, top + h - 1, rim, 0.7)
        for k in range(slats):
            yy = top_row + (h - 2) * (k + 1) / (slats + 1)
            seg(lb + 1, yy, rb - 1, yy, C.mix(rim, INK, 0.45), 0.55)
        # stem and the two rear legs of the base
        mx = (lb + rb) / 2.0
        seg(mx, top + h - 1, mx + sway, top + h + 3, rim, 0.55)
        seg(mx + sway, top + h + 3, mx - 5 + sway, top + h + 4.5,
            C.mix(rim, INK, 0.35), 0.45)
        seg(mx + sway, top + h + 3, mx + 5 + sway, top + h + 4.5,
            C.mix(rim, INK, 0.35), 0.45)
        br.commit()

    def _empty_chair(self, c, t: float, death: float, a: float) -> None:
        sway = 0.9 * math.sin(t * 0.62 + 0.7) * motion.smooth01(0.9, 2.0, death)
        cx = 96 - 1.2 * death
        fill = C.mix(INK, C.BLACK, 0.76 * a)
        rim = C.mix(INK, C.mix(C.RED_DIM, C.TEXT_FAINT, 0.42), 0.90 * a)
        self._chair(c, cx, 30, 17, 18, 11, fill, rim, sway=sway, slats=1)

    # ------------------------------------------------------------------
    # 172.65: the lens reflection -- "My goddess never looked at me"
    # ------------------------------------------------------------------
    def _lens(self, c, ctx) -> None:
        t = ctx.t
        p = motion.seg(t, self.reflection_at, self.end)
        zoom = 1.05 + 0.13 * motion.ease_out_quart(p)
        center = self._aim("desk-lens", zoom, 0.52, 0.47)
        draw_keyframe(c, "desk-lens", Y0, 0, C.CONTENT_H, W, t,
                      zoom=zoom, center=center, bright=1.02)
        motion.iris(c, 106.0, 24.0, 56.0, soft=16.0, amount=0.76)
        self._lens_glass(c, 106.0, 24.0, 56.0)
        self._lens_floor(c, t)
        self._lens_reply(c, t)
        self._lens_chair(c, t)
        self._lens_phantom(c, t)
        self._lens_crack(c, t)
        motion.vignette(c, 0.34)
        motion.grain(c, t, seed=13, count=54, amount=0.05)

    def _lens_glass(self, c, cx: float, cy: float, r: float) -> None:
        glass = C.mix(INK, C.CYAN_DEEP, 0.14)
        for yy in range(max(Y0, int(cy - r)), min(Y1, int(cy + r) + 1)):
            dy = (yy - cy) / (r * 0.5)
            if abs(dy) > 1.05:
                continue
            row_b = c.bg[yy]
            row_f = c.fg[yy]
            for xx in range(int(cx - r), int(cx + r) + 1):
                if not (0 <= xx < W):
                    continue
                dx = (xx - cx) / r
                if dx * dx + dy * dy <= 1.0:
                    row_b[xx] = C.mix(row_b[xx], glass, 0.92)
                    row_f[xx] = C.mix(row_f[xx], INK, 0.72)

    def _lens_floor(self, c, t: float) -> None:
        """The reflected hall: a horizon and a cold floor inside the glass."""
        horizon = 34
        c.hline(horizon, 58, 158,
                C.mix(INK, C.mix(C.CYAN_DIM, C.TEXT_FAINT, 0.3), 0.55), None)
        for yy in range(horizon + 1, 48):
            u = (yy - horizon) / 10.0
            c.fill_bg(yy, 60, 1, 97,
                      C.mix(C.mix(INK, C.BLACK, 0.3),
                            C.mix(INK, C.RED_DEEP, 0.35), 0.35 + 0.5 * u))

    def _lens_reply(self, c, t: float) -> None:
        """The previously tender reply, caught in the glass."""
        offer = self.beats[0].core
        first, _, rest = offer.partition(". ")
        first = first + "."
        breath = 0.72 + 0.28 * math.sin(t * 1.1)
        main = C.mix(C.CYAN_HI, C.TEXT_HI, 0.50 + 0.20 * breath)
        back = C.mix(INK, C.BLACK, 0.62)
        for row, text in ((15, first), (18, rest)):
            s = motion.spread_text(text, 1)
            x = 106 - len(s) // 2
            c.text(row, x, s, main, back, bold=True)
            # faint phosphor reflection two rows lower
            c.text(row + 2, x, s, C.mix(INK, C.CYAN_DIM, 0.22), back)
        c.hline(21, 92, 120, C.mix(INK, C.CYAN_DIM, 0.40), None)

    def _lens_chair(self, c, t: float) -> None:
        """Foreground: the empty chair back, nearer than the horizon."""
        fill = C.mix(INK, C.BLACK, 0.84)
        rim = C.mix(INK, C.mix(C.CYAN_DIM, C.TEXT_FAINT, 0.40), 0.78)
        self._chair(c, 92.0, 36, 13, 18, 14, fill, rim, slats=1)

    def _lens_phantom(self, c, t: float) -> None:
        sp = self._phantom
        if sp is None:
            return
        glow = 0.55 + 0.45 * math.sin(t * 0.65)
        gx, gy = 145, 27
        for yy in range(13, 39):
            row_b = c.bg[yy]
            for xx in range(gx - 12, gx + 13):
                if not (0 <= xx < W):
                    continue
                dx = (xx - gx) / 12.0
                dy = (yy - gy) / 14.0
                d = dx * dx + dy * dy
                if d <= 1.0:
                    row_b[xx] = C.mix(row_b[xx],
                                      C.mix(INK, C.TERRA_DEEP, 0.65),
                                      0.36 * (1.0 - d) * glow)
        # a distant shaft of warm light she stands in
        for yy in range(16, 36):
            u = (yy - 16) / 20.0
            c.fill_bg(yy, 136, 1, 16,
                      C.mix(INK, C.mix(C.TERRA_DEEP, C.BLACK, 0.45),
                            0.26 * (1.0 - u)))
        c.sprite(18, 135, sp, alpha=0.42 + 0.06 * glow,
                 tint=C.mix(C.TERRA_DIM, C.CYAN_DEEP, 0.28),
                 tint_amt=0.40, fg_mul=0.82)
        # her reflection smeared on the wet floor
        for yy in range(37, 44):
            u = (yy - 37) / 7.0
            c.fill_bg(yy, 138, 1, 14,
                      C.mix(INK, C.mix(C.TERRA_DEEP, C.BLACK, 0.4),
                            0.24 * (1 - u)))

    def _lens_crack(self, c, t: float) -> None:
        start = self.reflection_at + 0.45
        q = motion.seg(t, start, self.end - 0.08)
        if q <= 0.0:
            return
        way = ((160.0, 30.0), (153.0, 25.0), (147.0, 30.0), (140.0, 24.0),
               (132.0, 29.0), (124.0, 22.0), (116.0, 27.0), (108.0, 20.0),
               (100.0, 25.0), (93.0, 18.0))
        pts = []
        for i in range(len(way) - 1):
            x0, y0 = way[i]
            x1, y1 = way[i + 1]
            for k in range(4):
                u = k / 4.0
                pts.append((x0 + (x1 - x0) * u
                            + (motion.hash01(i, k, 3) - 0.5) * 3.2,
                            y0 + (y1 - y0) * u
                            + (motion.hash01(i, k, 5) - 0.5) * 3.0))
        pts.append(way[-1])
        total = len(pts) - 1
        grown = q * total
        br = c.braille(Y0, 0, C.CONTENT_H, W)
        for i in range(total):
            if i > grown:
                break
            frac = min(1.0, grown - i)
            x0, y0 = pts[i]
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            ex = x1 + (x2 - x1) * frac
            ey = y1 + (y2 - y1) * frac
            tip = (i + frac) / total
            col = C.mix(C.mix(C.PURPLE, C.PURPLE_HI, 0.35),
                        C.mix(C.MAGENTA, C.PURPLE_HI, 0.5), 0.10 + 0.90 * tip)
            for off, al in ((0, 1.0), (1, 0.6), (2, 0.3)):
                br.line(int(x0 * 2), int((y0 - Y0 + off * 0.5) * 4),
                        int(ex * 2), int((ey - Y0 + off * 0.5) * 4),
                        C.mix(INK, col, al), al, 0.5)
        # short branches
        for k in range(4):
            idx = 2 + k * 3
            if idx > grown:
                break
            bx0, by0 = pts[idx]
            ang = -2.4 + k * 0.9
            blen = 5.0 + 4.0 * motion.hash01(k, 7)
            br.line(int(bx0 * 2), int((by0 - Y0) * 4),
                    int((bx0 + math.cos(ang) * blen) * 2),
                    int((by0 + math.sin(ang) * blen - Y0) * 4),
                    C.mix(INK, C.PURPLE, 0.55), 0.7, 0.6)
        br.commit()
        # dark purple bleed at the lens rim, then into the whole frame edge
        bleed = motion.smooth01(0.35, 1.0, q)
        if bleed > 0.0:
            for yy in range(Y0, Y1):
                row_b = c.bg[yy]
                for xx in range(W):
                    dx = min(xx, W - 1 - xx) / (W * 0.5)
                    dy = min(yy - Y0, Y1 - 1 - yy) / (C.CONTENT_H * 0.5)
                    edge = 1.0 - min(1.0, min(dx, dy) * 2.4)
                    if edge > 0.0:
                        row_b[xx] = C.mix(row_b[xx], C.PURPLE_DEEP,
                                          1.15 * bleed * edge)
            c.fx.chroma = max(c.fx.chroma, 0.34 * motion.seg(
                t, self.end - 0.60, self.end))
            c.fx.flash = max(c.fx.flash,
                             0.10 * motion.seg(t, self.end - 0.22, self.end))
            c.fx.flash_color = C.PURPLE_DEEP