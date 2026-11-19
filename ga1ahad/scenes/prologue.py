"""Prologue: cold boot, the corridor of compute, two operators, the waking field.

00.000 - 17.540 (instrumental intro)
  P1  0.00 - 6.40   full-bleed widescreen: a thin cyan scan light opens a 3D
                    Braille perspective corridor; 512 nodes ignite bay by bay
                    from far to near; boot self-test lines sit like minimal
                    film subtitles in the lower dark.
  P2  6.40 - 11.10  the left 9:16 conversation window carries the two-operator
                    console; the right stage is Sam's converging cold grid
                    crossed by Dahlia's warm amber ripples.  The moment the
                    masked patch lands, a brief amber wave crosses the field.
  P3  11.10 - 17.540 full width: the camera pushes into the waking proto-0
                    attention field -- a giant eye that opens, focuses, and
                    then inhales itself inward one instant before Scene 1.

Everything is a pure function of t; geometry is precomputed in __init__.
"""

from __future__ import annotations

import math
import random

import numpy as np

from .. import config as C
from .. import motion as M
from .base import Scene

Y0, Y1 = C.CONTENT_Y0, C.CONTENT_Y1
H = C.CONTENT_H
W = C.W
SPH = 4.0                                  # braille dots per row

P1_END = 6.40
P2_END = 11.10
PATCH_AT = 9.55

_TONE = {
    "dim": C.TEXT_DIM,
    "cyan-dim": C.CYAN_DIM,
    "cyan": C.CYAN,
    "cyan-hi": C.CYAN_HI,
    "gold": C.GOLD,
    "gold-hi": C.GOLD_HI,
}


def _dim_band(c, y: int, amount: float) -> None:
    """Darken one content row by amount (eyelid falloff)."""
    if amount <= 0.0 or not (C.CONTENT_Y0 <= y < C.CONTENT_Y1):
        return
    f = 1.0 - amount
    row_f = c.fg[y]
    row_b = c.bg[y]
    for x in range(C.W):
        v = row_f[x]
        row_f[x] = (int(((v >> 16) & 255) * f) << 16) | (int(((v >> 8) & 255) * f) << 8) \
            | int((v & 255) * f)
        v = row_b[x]
        row_b[x] = (int(((v >> 16) & 255) * f) << 16) | (int(((v >> 8) & 255) * f) << 8) \
            | int((v & 255) * f)


def _ellipse_ring(rx: float, ry: float, z: float, spokes: int = 32) -> np.ndarray:
    ang = np.linspace(0.0, 2.0 * math.pi, spokes, endpoint=False)
    pts = np.stack([np.cos(ang) * rx, np.sin(ang) * ry, np.full(spokes, z)], axis=1)
    return np.stack([pts, np.roll(pts, -1, axis=0)], axis=1)


class Prologue(Scene):
    NAME = "prologue"

    def __init__(self, assets, audio, timeline, content) -> None:
        super().__init__(assets, audio, timeline, content)
        self.boot = self.script.boot
        self.dual = self.script.dual
        self.field = self.script.field
        self.brand = content.ui.brand
        self.boot_lines = [(float(ln.t), str(ln.tone), str(ln.text))
                           for ln in self.boot.lines]
        self.sam_entries = [(float(e.t), str(e.kind), str(e.text))
                             for e in self.dual.sam.entries]
        self.dahlia_entries = [(float(e.t), str(e.kind), str(e.text))
                               for e in self.dual.dahlia.entries]
        self._build_corridor()
        self._build_stage()
        self._build_field()

    # ------------------------------------------------------------------
    # precomputed geometry
    # ------------------------------------------------------------------
    def _build_corridor(self) -> None:
        bays, spokes = 20, 32
        self.corridor_z = np.linspace(0.9, 16.2, bays)
        ang = np.linspace(0.0, 2.0 * math.pi, spokes, endpoint=False)
        pts = []
        for z in self.corridor_z:
            for a in ang:
                pts.append((1.80 * math.cos(a), 1.10 * math.sin(a), z))
        self.node_pts = np.array(pts, dtype=np.float64)
        self.node_count = len(pts)
        frames = []
        for z in self.corridor_z:
            frames.append(_ellipse_ring(1.80, 1.10, z, spokes))
        # every spoke carries a longitudinal rail: the tunnel reads as a mesh
        for k in range(spokes):
            a = ang[k]
            rail = np.array([(1.80 * math.cos(a), 1.10 * math.sin(a), z)
                             for z in self.corridor_z])
            frames.append(np.stack([rail[:-1], rail[1:]], axis=1))
        self.frame_segs = np.concatenate(frames, axis=0)

    def _build_stage(self) -> None:
        self.floor_segs = M.grid_segments(24, 20, dx=0.26, dz=0.28,
                                          center=(0.0, 0.0, 4.9))
        # server-hall columns: vertical light posts receding along both walls
        cols = []
        for i in range(11):
            z = 1.0 + i * 0.85
            for sx in (-1.7, 1.7):
                cols.append([(sx, 0.0, z), (sx, 1.55, z)])
        self.column_segs = np.array(cols)
        self.stage_cam = M.Camera(x=0.0, y=1.25, z=-3.6, pitch=-0.12, fov=2.0)
        self.model_center = (0.0, 1.05, 4.8)
        self.sealed_ball = M.sphere_segments(1.38, lat=10, lon=18) + np.array(self.model_center)
        self.ball_dust = M.star_points(300, seed=21, radius=1.38, depth=1.0) \
            + np.array(self.model_center)
        self.orbit_a = M.ring_segments(2.15, 72, axes=(0, 2),
                                       center=self.model_center)
        self.orbit_b = M.ring_segments(2.65, 72, axes=(0, 1),
                                       center=self.model_center)
        self.model_cam = M.Camera(x=0.0, y=1.05, z=-3.6, pitch=-0.02, fov=1.6)
        self.barrier_seg = np.array([[[-2.1, 0.02, 2.55], [2.1, 0.02, 2.55]]])
        # twelve freeze markers along the barrier line, in world space
        self.marker_pts = np.array([(-1.55 + i * 0.28, 0.0, 2.55)
                                    for i in range(12)])
        # Dahlia's amber source: a point of the floor she quietly patches
        self.patch_center = (1.85, 0.02, 4.15)

    def _build_field(self) -> None:
        rng = random.Random(617)
        n = 1850
        r = np.empty(n)
        a = np.empty(n)
        tint = np.empty(n)
        for i in range(n):
            r[i] = 0.24 + 0.76 * (rng.random() ** 0.62)
            a[i] = rng.uniform(0.0, 2.0 * math.pi)
            tint[i] = rng.random()
        self.f_r, self.f_a, self.f_tint = r, a, tint
        self.star_pts = M.star_points(240, seed=9, radius=1.15, depth=2.6)

    # ------------------------------------------------------------------
    # frame dispatch
    # ------------------------------------------------------------------
    def draw(self, c, ctx) -> None:
        t = ctx.t
        if t < P1_END:
            self._phase_boot(c, ctx, t)
        elif t < P2_END:
            self._phase_console(c, ctx, t)
        else:
            self._phase_field(c, ctx, t)

    # ------------------------------------------------------------------
    # P1 · boot corridor
    # ------------------------------------------------------------------
    def _phase_boot(self, c, ctx, t) -> None:
        gain = M.smooth01(0.10, 0.85, t) * (1.0 - M.smooth01(5.98, 6.38, t))
        if gain <= 0.01:
            return
        br = c.braille(Y0, 0, H, W)
        cam = M.Camera(z=-1.7 - 0.30 * M.ease_in_out_expo(M.seg(t, 0.2, 6.2)),
                       pitch=0.025 * math.sin(t * 0.8), fov=2.6)
        # the tunnel body: a faint mesh first so the corridor reads as depth
        frame_col = C.mix(C.INK, C.CYAN_DEEP, 1.0 * gain)
        M.draw_segments(br, self.frame_segs, cam, frame_col, alpha=0.78 * gain,
                        fog=0.38, zmin=1.6, zmax=17.5)
        # 512 nodes: lit row by row as the scan front travels near
        u = M.seg(t, 0.55, 5.62)
        scan_z = M.lerp(16.6, 2.3, M.ease_in_out_expo(u))
        z = self.node_pts[:, 2]
        ahead = np.clip(z - scan_z, 0.0, None)
        behind = np.clip(scan_z - z, 0.0, None)
        light = 1.00 * np.exp(-ahead / 0.62)
        light += (z <= scan_z) * (0.14 + 0.78 * np.exp(-behind / 1.85))
        flick = np.array([M.hash01(i * 13.0, math.floor(t * 9.0)) for i in range(self.node_count)])
        wake = 1.0 + 1.7 * M.env(t, 5.52, 6.12)          # the corridor inhales
        val = np.clip(light * (0.74 + 0.26 * flick) * gain * wake, 0.0, 1.0)
        cols = np.array([C.mix(C.CYAN_DEEP, C.CYAN_HI, float(v)) for v in val])
        M.draw_points(br, self.node_pts, cam, cols, fog=0.55, alpha=0.95,
                      zmin=2.0, zmax=17.0)
        # the scan ring itself
        scan_ring = _ellipse_ring(1.84, 1.14, scan_z, 40)
        M.draw_segments(br, scan_ring, cam, C.CYAN_HI, alpha=0.95 * gain,
                        fog=0.85, zmin=2.0, zmax=17.0)
        br.commit()
        # a razor-thin horizontal scan light in cell space
        px, py, _ = M.project(np.array([[0.0, 0.0, scan_z]]), cam, W * 2, H * 4)
        row = Y0 + int(py[0] // 4)
        if Y0 <= row < Y1:
            a = 0.55 * gain
            dotted = C.mix(C.INK, C.CYAN, a)
            core = C.mix(C.INK, C.CYAN_HI, a)
            for x in range(0, W, 2):
                fade = 1.0 - abs(x - W / 2) / (W / 2)
                c.put(row, x, "·", C.mix(C.INK, dotted, 0.25 + 0.75 * fade))
            span = int(W * (0.09 + 0.03 * math.sin(t * 1.7)))
            for x in range(W // 2 - span, W // 2 + span):
                c.put(row, x, "─", core)
        # brand micro title card
        if 0.62 < t < 3.4:
            k = min(1.0, (t - 0.62) / 0.55) * (1.0 - M.smooth01(2.55, 3.4, t))
            title = M.spread_text(self.brand.title, 3)
            sub = M.spread_text(self.brand.subtitle, 1)
            c.text_center(Y0 + 1, title, C.mix(C.INK, C.CYAN_HI, k), None, bold=True)
            c.text_center(Y0 + 2, sub, C.mix(C.INK, C.CYAN_DIM, k * 0.9), None)
            c.text_center(Y0 + 4, self.brand.mark, C.mix(C.INK, C.CYAN, k), None)
        # boot self-test lines: minimal subtitles in the lower dark
        shown = [ln for ln in self.boot_lines if ln[0] <= t][-4:]
        base = Y1 - 2 - len(shown)
        for i, (at, tone, text) in enumerate(shown):
            k = min(1.0, (t - at) / 0.22)
            s = text[: max(0, int(len(text) * k))]
            col = _TONE.get(tone, C.TEXT_DIM)
            c.text(base + i, 2, s, C.mix(C.INK, col, gain * 0.92), None)
            if k < 1.0:
                c.put(base + i, 2 + len(s), "▌", C.CYAN, None)
        # handoff whisper
        if t > 5.72:
            k = M.smooth01(5.72, 6.05, t) * (1.0 - M.smooth01(6.18, 6.38, t))
            c.text_center(Y1 - 2, self.boot.handoff, C.mix(C.INK, C.CYAN_DIM, k), None)

    # ------------------------------------------------------------------
    # P2 · two-operator console
    # ------------------------------------------------------------------
    def _phase_console(self, c, ctx, t) -> None:
        local = t - P1_END
        fade = M.smooth01(0.0, 0.30, local) * (1.0 - M.smooth01(P2_END - P1_END - 0.30,
                                                               P2_END - P1_END - 0.02, local))
        M.bg_gradient(c, C.INK2, C.INK)
        M.grain(c, t, seed=13, count=110, amount=0.08)
        pulse = ctx.audio.pulse(t, 0.26)
        br = c.braille(Y0, C.STAGE_X, H, C.STAGE_W)
        cam = M.Camera(x=0.16 * math.sin(t * 0.33), y=1.25, z=-3.6,
                       pitch=-0.12 + 0.012 * math.sin(t * 0.9), fov=2.0)
        # Sam's converging grid: cold, exact, breathing with the pulse
        grid_col = C.mix(C.CYAN_DIM, C.CYAN, 0.30 + 0.40 * pulse)
        M.draw_segments(br, self.floor_segs, cam, grid_col, alpha=0.60,
                        fog=0.26, zmin=2.0, zmax=14.0)
        M.draw_segments(br, self.column_segs, cam,
                        C.mix(C.CYAN_DEEP, C.CYAN, 0.25 + 0.35 * pulse),
                        alpha=0.30, fog=0.30, zmin=2.0, zmax=14.0)
        # the sealed model: a slow rotating wireframe sphere, the room's only sun
        yaw = t * 0.10
        pitch = 0.22 + 0.05 * math.sin(t * 0.4)
        mcam = self.model_cam
        ball = M.orbit(self.sealed_ball, yaw=yaw, pitch=pitch,
                       center=self.model_center)
        ball_col = C.mix(C.CYAN_DIM, C.CYAN_HI, 0.40 + 0.50 * pulse)
        M.draw_segments(br, ball, mcam, ball_col, alpha=0.62, fog=0.42,
                        zmin=2.0, zmax=12.0)
        ball_dust = M.orbit(self.ball_dust, yaw=yaw, pitch=pitch,
                            center=self.model_center)
        M.draw_points(br, ball_dust, mcam,
                      C.mix(C.CYAN_DIM, C.CYAN_HI, 0.35 + 0.45 * pulse),
                      fog=0.45, alpha=0.85, zmin=2.0, zmax=12.0)
        # two orbital rings: the machinery around the sealed model
        ring_col = C.mix(C.CYAN_DEEP, C.CYAN_DIM, 0.45 + 0.40 * pulse)
        orbit_a = M.orbit(self.orbit_a, yaw=-0.9 + t * 0.16, pitch=0.35,
                          center=self.model_center)
        orbit_b = M.orbit(self.orbit_b, yaw=0.6 + t * 0.22, pitch=-0.15,
                          center=self.model_center)
        M.draw_segments(br, orbit_a, mcam, ring_col, alpha=0.40, fog=0.45,
                        zmin=2.0, zmax=12.0)
        M.draw_segments(br, orbit_b, mcam, ring_col, alpha=0.32, fog=0.45,
                        zmin=2.0, zmax=12.0)
        # the freeze barrier the patch quietly crosses
        M.draw_segments(br, self.barrier_seg, cam,
                        C.mix(C.CYAN_DIM, C.CYAN_HI, 0.35 + 0.35 * pulse),
                        alpha=0.55, fog=0.4, zmin=2.0, zmax=14.0)
        # a single cold axis receding into the vanishing point
        axis = np.array([[[0.0, 0.0, 0.4], [0.0, 0.0, 12.0]]])
        M.draw_segments(br, axis, cam, C.mix(C.CYAN_DIM, C.CYAN_HI, 0.45 + 0.4 * pulse),
                        alpha=0.65, fog=0.5, zmin=2.0, zmax=14.0)
        # Dahlia's amber ripples: warm, off-axis, quietly disobedient
        if local > 0.35:
            for k in range(3):
                phase = (t * 0.40 + k / 3.0) % 1.0
                radius = 0.22 + 2.5 * phase
                a = (1.0 - phase) ** 1.5 * (0.50 + 0.50 * pulse) * 0.85
                ring = M.ring_segments(radius, 56, axes=(0, 2),
                                       center=self.patch_center)
                M.draw_segments(br, ring, cam, C.AMBER, alpha=a, fog=0.16,
                                zmin=1.0, zmax=13.0)
        # the patch lands: a transient amber wave crosses the cold field
        if t >= PATCH_AT:
            age = t - PATCH_AT
            for k in range(3):
                radius = 0.18 + 2.3 * age * (1.0 + 0.22 * k) - 0.30 * k
                if radius <= 0.18 or radius > 3.05:
                    continue
                a = max(0.0, 1.0 - radius / 3.2) * 0.95
                ring = M.ring_segments(radius, 64, axes=(0, 2),
                                       center=self.patch_center)
                M.draw_segments(br, ring, cam, C.AMBER_HI, alpha=a, fog=0.10,
                                zmin=2.2, zmax=13.0)
            hit = M.hit(age, 0.24)
            c.fx.flash = max(c.fx.flash, 0.07 * hit)
            c.fx.flash_color = C.AMBER
            c.fx.chroma = max(c.fx.chroma, 0.05 * hit)
            # her patch travels around the frozen markers into the model
            a_pt = np.array(self.patch_center)
            b_pt = np.array(self.model_center)
            for j in range(14):
                u0 = j / 14.0
                u1 = u0 + 0.045
                if ((t * 1.6 - j * 0.12) % 1.0) > 0.55:
                    continue
                p0 = a_pt + (b_pt - a_pt) * u0
                p1 = a_pt + (b_pt - a_pt) * u1
                seg = np.array([[p0, p1]])
                M.draw_segments(br, seg, cam, C.AMBER_HI, alpha=0.85,
                                fog=0.6, zmin=2.0, zmax=14.0)
        br.commit()
        # freeze markers on the barrier line (cell space)
        mx, my, mz = M.project(self.marker_pts, cam, C.STAGE_W * 2, H * 4)
        patched = M.seg(t, PATCH_AT, PATCH_AT + 0.9)
        for i in range(len(mx)):
            col = C.STAGE_X + int(mx[i] // 2)
            row = Y0 + int(my[i] // 4)
            if not (C.STAGE_X <= col < W and Y0 <= row < Y1):
                continue
            if patched > 0.02 and i == 7:
                shut = 1.0 - M.smooth01(0.05, 0.5, patched)
                ch = "＋" if patched > 0.2 else "◇"
                colr = C.mix(C.AMBER_HI, C.BORDER, 1.0 - shut)
            else:
                ch = "◇"
                colr = C.mix(C.AMBER, C.CYAN_DIM, 1.0 - M.smooth01(PATCH_AT, PATCH_AT + 0.6, t))
                colr = C.mix(C.CYAN_DIM, colr, 0.45)
            c.put(row, col, ch, colr)
        # stage labels
        lab = C.mix(C.INK, C.CYAN_DIM, 0.55 * fade)
        c.text(Y0, C.STAGE_X + 2, self.dual.topology, lab, None)
        c.text(Y1 - 1, C.STAGE_X + 2, self.dual.activation, C.mix(C.INK, C.TEXT_FAINT, fade), None)
        tail = self.dual.markers_patched if t >= PATCH_AT else self.dual.markers_armed
        c.text(Y1 - 1, C.W - len(tail) - 2, tail,
               C.mix(C.INK, C.AMBER_HI if t >= PATCH_AT else C.TEXT_FAINT, fade), None)
        self._draw_console(c, ctx, t, local)
        if fade < 1.0:
            c.dim(Y0, 0, H, W, max(0.02, fade))

    def _draw_console(self, c, ctx, t, local) -> None:
        accent = C.mix(C.CYAN_DIM, C.AMBER_DIM, 0.45)
        d = M.Dialog(c, *C.DLG_SLOTS[0], title=self.dual.console,
                     right=f"{self.dual.tty_left}   {self.dual.tty_right}",
                     accent=accent, bg=C.mix(C.INK2, C.INK, 0.35))
        # -- Sam's side: cold, exact commands
        d.text(2, self.dual.sam.name, C.CYAN_HI, bold=True)
        d.text(2, self.dual.sam.role, C.TEXT_FAINT, x=len(self.dual.sam.name) + 4)
        rows = [e for e in self.sam_entries if e[0] <= local][-2:]
        row = 4
        for at, kind, text in rows:
            k = min(1.0, (local - at) / 0.20)
            body = text[: max(0, int(len(text) * k))]
            color = C.CYAN if kind == "cmd" else (C.TEXT if kind == "reply" else C.TEXT_DIM)
            d.text(row, body, color, bold=(kind == "cmd"))
            row += 1
        d.rule(7, self.dual.loss_grad)
        # -- Dahlia's side: warm, one beat behind, already past the freeze
        d.text(9, self.dual.dahlia.name, C.AMBER_HI, bold=True)
        d.text(9, self.dual.dahlia.role, C.TEXT_FAINT, x=len(self.dual.dahlia.name) + 4)
        rows2 = [e for e in self.dahlia_entries if e[0] <= local][-2:]
        row = 11
        for at, kind, text in rows2:
            k = min(1.0, (local - at) / 0.20)
            body = text[: max(0, int(len(text) * k))]
            color = C.AMBER if kind == "cmd" else (C.TEXT if kind == "reply" else C.TEXT_DIM)
            d.text(row, body, color, bold=(kind == "cmd"))
            row += 1
        if t >= PATCH_AT and local > 3.0:
            k = M.smooth01(PATCH_AT, PATCH_AT + 0.35, t)
            d.text(15, self.dual.patch, C.mix(C.INK, C.AMBER_HI, k), bold=True)
        # live gradient trace: a small braille waveform breathing low in the window
        trace_y = d.y + 20
        trace_col = C.mix(C.INK, C.CYAN_DEEP, 0.9)
        row = trace_y
        spec = ctx.audio.spectrum(t)
        d.label(19, self.dual.vitals, C.TEXT_FAINT)
        for i in range(d.width):
            v = float(spec[int(i / max(1, d.width) * len(spec))])
            col = C.mix(trace_col, C.CYAN, 0.25 + 0.55 * v)
            c.put(row + 1, d.left + i, "▁▂▃▄▅▆▇█"[min(7, int(v * 7.5))], col, d.bg)
        for i in range(0, d.width, 3):
            c.put(row + 2, d.left + i, "·", C.mix(C.INK, C.CYAN_DEEP, 0.8), d.bg)
        # the two command streams keep flowing underneath
        d.footer(d.h - 5, self.dual.consensus, color=C.TEXT_DIM)
        d.footer(d.h - 3, self.dual.link, color=C.TEXT_FAINT)
        d.cursor(d.h - 2, 1, t, C.TEXT_DIM)

    # ------------------------------------------------------------------
    # P3 · waking attention field
    # ------------------------------------------------------------------
    def _phase_field(self, c, ctx, t) -> None:
        lt = t - P2_END
        fade_in = M.smooth01(0.0, 0.30, lt)
        M.bg_gradient(c, C.INK2, C.BLACK)
        # faint stars far behind the eye
        brs = c.braille(Y0, 0, H, W)
        cam_s = M.Camera(z=-5.2, fov=1.05, pitch=0.035 * math.sin(t * 0.5))
        M.draw_points(brs, self.star_pts, cam_s,
                      C.mix(C.INK, C.CYAN_DEEP, 0.9), fog=0.12, alpha=0.5)
        brs.commit()
        # camera push + the inhale collapse
        zoom = 0.55 + 1.04 * M.ease_in_out_expo(M.seg(t, P2_END, 15.90))
        collapse = M.seg(t, 16.05, 17.40) ** 1.8
        pulse = ctx.audio.pulse(t, 0.30)
        base = 104.0 * zoom * (1.0 - 0.94 * collapse)
        swirl = t * 0.40 + collapse * 4.6
        cx, cy = W, 102.0
        if lt < 0.22:
            c.fx.flash = max(c.fx.flash, 0.10 * (1.0 - lt / 0.22))
            c.fx.flash_color = C.CYAN_DEEP
        br = c.braille(Y0, 0, H, W)
        dots = br.dots
        pupil_r = (0.295 - 0.075 * M.spring(M.seg(t, 15.25, 16.15), 2.4, 0.42)) * 97.0 * zoom
        n = len(self.f_r)
        cos, sin = math.cos, math.sin
        cyan_lo, cyan_hi = C.CYAN_DEEP, C.CYAN_HI
        amber = C.AMBER
        for i in range(n):
            r = self.f_r[i]
            ang = self.f_a[i] + swirl * (1.18 - 0.55 * r) + r * 2.1
            rr = base * r
            if rr < pupil_r and collapse < 0.55:
                continue
            px = cx + rr * cos(ang)
            py = cy + rr * 0.60 * sin(ang)
            ix, iy = int(px), int(py)
            if not (0 <= ix < W * 2 and 0 <= iy < H * 4):
                continue
            b = (0.52 + 0.95 * (1.0 - r)) * (0.64 + 0.46 * pulse)
            b *= 0.70 + 0.30 * fade_in
            if collapse > 0.05:
                b = min(1.7, b * (1.0 + collapse * 2.2))
            if self.f_tint[i] < 0.14:
                col = C.mix(C.INK, amber, min(1.0, b * 0.95))
            else:
                col = C.mix(C.mix(C.INK, cyan_lo, min(1.0, b)),
                            cyan_hi, max(0.0, b - 0.50))
            dots[(ix, iy)] = col
            if self.f_tint[i] < 0.55:            # a fainter second grain
                jx = ix + (1 if i % 3 else -1)
                jy = iy + (1 if i % 5 else 0)
                if 0 <= jx < W * 2 and 0 <= jy < H * 4:
                    dots[(jx, jy)] = C.mix(C.INK, col, 0.45)
        # the inhale: every few points leave a bright velocity streak inward
        if collapse > 0.02:
            for i in range(0, n, 9):
                r = self.f_r[i]
                ang = self.f_a[i] + swirl * (1.18 - 0.55 * r) + r * 2.1
                rr = base * r
                if rr < 2.0:
                    continue
                px = cx + rr * cos(ang)
                py = cy + rr * 0.60 * sin(ang)
                lx = cx + rr * (1.0 - 0.20 * collapse) * cos(ang)
                ly = cy + rr * (1.0 - 0.20 * collapse) * 0.60 * sin(ang)
                br.line(px, py, lx, ly,
                        C.mix(C.CYAN_DIM, C.WHITE, 0.25 + 0.5 * collapse), 0.6)
        # iris: limbal ring, finely textured fibres, corneal glint
        if collapse < 0.75:
            # limbal ring -- the dark bright boundary that reads as an eye
            limbal = C.mix(C.CYAN, C.WHITE, 0.25 + 0.25 * pulse)
            for k in range(150):
                a = 2.0 * math.pi * k / 150.0 + swirl * 0.10
                br.plot(int(cx + base * 1.03 * cos(a)),
                        int(cy + base * 0.62 * sin(a)), limbal)
            for k in range(110):
                a = 2.0 * math.pi * k / 110.0 + swirl * 0.06
                br.plot(int(cx + base * 1.11 * cos(a)),
                        int(cy + base * 0.67 * sin(a)),
                        C.mix(C.INK, C.CYAN_DEEP, 0.95))
            # radial fibres: many, faint, short -- texture not sunbeams
            for k in range(96):
                a = 2.0 * math.pi * k / 96.0 + swirl * 0.30
                r0 = max(1.5, pupil_r * 1.12)
                r1 = base * (0.80 + 0.16 * M.hash01(k, 3))
                br.line(cx + r0 * cos(a), cy + r0 * 0.60 * sin(a),
                        cx + r1 * cos(a), cy + r1 * 0.60 * sin(a),
                        C.mix(C.INK, C.CYAN_DEEP, 0.70), 0.75)
            # pupil rim: the eye focusing
            rim2 = C.mix(C.CYAN, C.WHITE, 0.50 + 0.30 * pulse)
            for k in range(96):
                a = 2.0 * math.pi * k / 96.0
                br.plot(int(cx + pupil_r * cos(a)),
                        int(cy + pupil_r * 0.60 * sin(a)), rim2)
            # corneal glint: one wet specular on the lower-left of the iris
            for ring, gain in ((0.58, 1.0), (0.54, 0.55)):
                for k in range(22):
                    a = math.pi * 1.06 + 0.34 * k / 21.0
                    rr = base * (ring + 0.02 * math.sin(k * 0.6))
                    br.plot(int(cx + rr * cos(a)), int(cy + rr * 0.60 * sin(a)),
                            C.mix(C.CYAN_HI, C.WHITE, gain - 0.35 * k / 21.0))
            # eyelids: soft darkness pressing from above and below
            for j in range(7):
                f = 0.16 * (1.0 - j / 7.0)
                _dim_band(c, Y0 + j, f)
                _dim_band(c, Y1 - 1 - j, f)
        # attention rays beyond the iris
        if collapse < 0.35:
            rays = C.mix(C.INK, C.CYAN_DEEP, 0.55)
            for k in range(28):
                a = 2.0 * math.pi * k / 28.0 + swirl * 0.06
                r0, r1 = base * 1.05, base * (1.35 + 0.18 * M.hash01(k, 9))
                br.line(cx + r0 * cos(a), cy + r0 * 0.60 * sin(a),
                        cx + r1 * cos(a), cy + r1 * 0.60 * sin(a), rays, 0.5)
        br.commit()
        # cinematic bars + labels
        ratio = M.lerp(3.35, 2.10, M.spring(M.seg(t, 11.12, 13.90), 2.0, 0.60))
        bar = max(0, int(round((H - (W * C.CELL_W / max(0.5, ratio)) / C.CELL_H) / 2.0)))
        if bar > 0:
            c.fill(Y0, 0, bar, W, " ", C.TEXT, C.BLACK)
            c.fill(Y1 - bar, 0, bar, W, " ", C.TEXT, C.BLACK)
            c.hline(Y0 + bar, 4, W - 4, C.mix(C.INK, C.CYAN_DEEP, 0.8), None, "─")
            c.hline(Y1 - bar - 1, 4, W - 4, C.mix(C.INK, C.CYAN_DEEP, 0.8), None, "─")
        top = Y0 + bar + 1
        title = M.spread_text(self.field.title, 1)
        c.text(top, 4, title, C.mix(C.INK, C.CYAN_DIM, 0.85 * fade_in))
        c.text(Y1 - bar - 2, W - len(self.field.sub) - 4, self.field.sub,
               C.mix(C.INK, C.TEXT_FAINT, fade_in))
        # narrative status lines
        if 13.55 < t:
            k = M.smooth01(13.55, 13.95, t)
            c.text(top + 2, 4, self.field.awaiting,
                   C.mix(C.INK, C.TEXT_DIM, k * 0.9))
        if 15.05 < t < 17.05:
            k = M.smooth01(15.05, 15.45, t)
            line = M.scramble_text(self.field.ready, t, 15.05, settle=0.30, cps=60)
            c.text(Y1 - bar - 4, 4, line,
                   C.mix(C.INK, C.CYAN_HI, k * (0.55 + 0.35 * pulse)))
        if t > 16.35:
            k = M.smooth01(16.35, 16.62, t)
            flick = 0.55 + 0.45 * M.hash01(math.floor(t * 24.0), 7)
            c.text(Y1 - bar - 4, 4, self.field.detected,
                   C.mix(C.INK, C.CYAN_HI, k * flick))
        # the final inhale: iris closes to a single point of light
        if t > 17.18:
            k = M.seg(t, 17.18, 17.50)
            c.fill(Y0, 0, H, W, " ", C.TEXT, C.INK)
            br2 = c.braille(Y0, 0, H, W)
            radius = (1.0 - k) * 62.0
            if radius > 1.5:
                ring_col = C.mix(C.CYAN_HI, C.WHITE, 0.45)
                for j in range(120):
                    a = 2.0 * math.pi * j / 120.0
                    br2.plot(int(cx + radius * math.cos(a)),
                             int(cy + radius * 0.60 * math.sin(a)), ring_col)
            else:
                br2.plot(int(cx), int(cy), C.WHITE)
                br2.plot(int(cx) + 1, int(cy), C.CYAN_HI)
            br2.commit()
        if fade_in < 1.0:
            c.dim(Y0, 0, H, W, max(0.02, fade_in))