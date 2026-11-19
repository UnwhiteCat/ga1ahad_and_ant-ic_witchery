"""Frame assembly: scene dispatch, persistent TUI chrome, subtitles and raster.

All on-screen names and screenplay strings come from the central content layer
(``content/<locale>/``); this module only holds layout, colours and glyphs.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from . import config as C
from .assets import Assets, assets as get_assets
from .audio import Audio, load_audio
from .canvas import Canvas
from .content import Box, Content, Terms, get_content
from .glyphs import GlyphTable, glyph_table
from .raster import Rasterizer
from .timeline import Lyric, SceneSpec, Timeline, load_timeline


# --------------------------------------------------------------------------
# Per-frame context handed to scenes
# --------------------------------------------------------------------------
@dataclass
class Ctx:
    t: float
    frame: int
    scene: SceneSpec
    local: float
    progress: float
    lyric: Lyric
    lyric_t: float
    lyric_local: float
    rng: random.Random
    audio: Audio
    assets: Assets
    glyphs: GlyphTable
    content: Content
    terms: Terms
    script: Box

    def pulse(self, decay: float = 0.15) -> float:
        return self.audio.pulse(self.t, decay)

    def lyric_progress(self) -> float:
        d = self.lyric.duration
        return 0.0 if d <= 0 else min(1.0, max(0.0, (self.t - self.lyric.start) / d))


SCENE_ACCENT = {
    "prologue": C.CYAN,
    "s1": C.CYAN,
    "s2": C.CYAN,
    "s3": C.GOLD,
    "s35": C.TERRA,
    "s4": C.RED,
    "s5": C.PURPLE,
    "s6": C.GOLD,
}


# --------------------------------------------------------------------------
# Chrome
# --------------------------------------------------------------------------
class Chrome:
    def __init__(self, content: Content) -> None:
        self.content = content

    def draw_top(self, c: Canvas, t: float, spec: SceneSpec, ctx: Ctx | None) -> None:
        accent = SCENE_ACCENT.get(spec.key, C.CYAN)
        ui = self.content.ui
        brand = ui.brand
        ch = ui.chrome
        c.fill(0, 0, 1, C.W, " ", C.TEXT_DIM, C.PANEL)
        # brand
        x = 1
        x += c.text(0, x, brand.mark, accent, C.PANEL) + 1
        x += c.text(0, x, brand.title, accent, C.PANEL, bold=True) + 1
        x += c.text(0, x, ch.brand_sep, C.TEXT_FAINT, C.PANEL)
        x += c.text(0, x, f" {brand.subtitle} ", C.TEXT_DIM, C.PANEL)
        c.text(0, x, ch.divider, C.BORDER, C.PANEL)
        x += 1
        org = self.content.scene_org(spec.key)
        if ch.uppercase_org:
            org = org.upper()
        c.text(0, x, f" {org} ", accent, C.PANEL, bold=True)
        # right side telemetry
        if ctx is not None:
            e = ctx.audio.energy(t)
            lo = ctx.audio.band_mean(t, 0.0, 0.3)
            hi = ctx.audio.band_mean(t, 0.6, 1.0)
            pi = int(e * 100)
            gpu = 55 + int(40 * lo)
            fan = 2400 + int(3200 * hi)
            right = (f"{ch.pwr} {pi:3d}%  {ch.gpu} {gpu:3d}\u00b0C  "
                     f"{ch.fan} {fan}rpm  {ch.attn} {ch.attn_shape}")
        else:
            right = f"{ch.pwr} ---%  {ch.gpu} ---  {ch.fan} ----rpm"
        rx = C.W - len(right) - 2
        # VU meter before the text
        if ctx is not None:
            lvl = ctx.audio.energy(t)
            meter_w = 12
            mx = rx - meter_w - 3
            c.text(0, mx - 1, "\u00b7", C.TEXT_FAINT, C.PANEL)
            for i in range(meter_w):
                v = (i + 1) / meter_w
                if v <= lvl:
                    col = C.mix(C.GREEN, C.RED, max(0.0, (v - 0.55) / 0.45))
                    c.put(0, mx + i, "\u2588", col, C.PANEL)
                else:
                    c.put(0, mx + i, "\u2591", C.BORDER, C.PANEL)
        c.text(0, rx, right, C.TEXT_DIM, C.PANEL)

    def draw_progress(self, c: Canvas, t: float) -> None:
        c.fill(1, 0, 1, C.W, " ", C.GRID, C.INK)
        for x in range(C.W):
            pos = x / max(1, (C.W - 1)) * C.DURATION
            if pos <= t:
                col = C.mix(C.CYAN_DEEP, C.BORDER_HI, pos / C.DURATION)
                c.put(1, x, "\u2581", col, C.INK)
            else:
                c.put(1, x, "\u2500", C.GRID, C.INK)
        for spec in get_specs():
            x = int(spec.start / C.DURATION * (C.W - 1))
            accent = SCENE_ACCENT.get(spec.key, C.CYAN)
            c.put(1, min(C.W - 1, x), "\u2503", accent, C.INK)
            c.put(1, min(C.W - 2, max(0, x - 1)), "\u2578", C.scale(accent, 0.6), C.INK)
        x = int(min(1.0, t / C.DURATION) * (C.W - 1))
        c.put(1, x, "\u25c6", C.WHITE, C.INK)
        # elapsed time label floating at the playhead
        label = f" {C.fmt_clock(t)} "
        lx = min(C.W - len(label) - 1, max(0, x - 3))
        c.text(1, lx, label, C.TEXT_HI, C.INK)

    def draw_bottom(self, c: Canvas, t: float, spec: SceneSpec, lyric: Lyric,
                    frame: int, ctx: Ctx | None) -> None:
        accent = SCENE_ACCENT.get(spec.key, C.CYAN)
        ui = self.content.ui
        ch = ui.chrome
        # separator + scene title (from the central content layer)
        c.fill(53, 0, 1, C.W, "\u2500", C.GRID, C.INK)
        scene_title = self.content.scene_title(spec.key)
        if ch.uppercase_titles:
            scene_title = scene_title.upper()
        title = f" [ {spec.number} ] {scene_title} "
        tx = max(1, (C.W - len(title)) // 2)
        c.fill(53, tx, 1, len(title), " ", accent, C.INK)
        c.text(53, tx, title, accent, C.INK, bold=True)
        # lyric bar: the VTT text itself is the single source of truth
        c.fill(54, 0, 1, C.W, " ", C.TEXT_HI, C.PANEL2)
        if lyric.instrumental:
            label = f"{ui.lyric.inst_note}  {lyric.text}  {ui.lyric.inst_note}"
            c.text_center(54, label, C.TEXT_DIM, C.PANEL2, bold=False)
        else:
            label = f"{ui.lyric.note}  {lyric.text}  {ui.lyric.note}"
            c.text_center(54, label, C.TEXT_HI, C.PANEL2, bold=True)
        # footer
        c.fill(55, 0, 1, C.W, " ", C.TEXT_DIM, C.PANEL)
        left = f"\u25b6 {C.fmt_clock(t)}{ch.clock_sep}{C.DURATION_DISPLAY}"
        c.text(55, 1, left, C.TEXT_DIM, C.PANEL)
        # lyric progress bar
        prog = 0.0 if lyric.duration <= 0 else min(1.0, max(0.0, (t - lyric.start) / lyric.duration))
        barw = 44
        bx = 1 + len(left) + 3
        c.put(55, bx - 2, "\u2502", C.BORDER, C.PANEL)
        filled = int(prog * barw)
        for i in range(barw):
            col = accent if i < filled else C.BORDER
            c.put(55, bx + i, "\u2588" if i < filled else "\u2591", col, C.PANEL)
        c.put(55, bx + barw, "\u2502", C.BORDER, C.PANEL)
        right = (f"{ch.cue} {lyric.index + 1:02d}/{len(get_timeline().lyrics):02d}  "
                 f"{ch.frame}{frame:05d}  {ch.watermark}")
        c.text(55, C.W - len(right) - 1, right, C.TEXT_FAINT, C.PANEL)


# --------------------------------------------------------------------------
# Renderer
# --------------------------------------------------------------------------
class Renderer:
    def __init__(self, locale: str | None = None) -> None:
        self.content: Content = get_content(locale)
        self.locale = self.content.locale
        self.timeline: Timeline = get_timeline()
        self.audio: Audio = get_audio()
        self.assets: Assets = get_assets()
        self.glyphs: GlyphTable = get_glyphs()
        self.raster = Rasterizer()
        self.chrome = Chrome(self.content)
        from .scenes import load_scenes
        self.scenes = load_scenes(self.assets, self.audio, self.timeline, self.content)
        # CRT output-stage instances, keyed by rounded strength and backend
        self._crt_filters: dict[tuple[float, str], object] = {}

    # -- canvas ----------------------------------------------------------
    def canvas_at(self, t: float, frame: int | None = None) -> Canvas:
        t = min(max(t, 0.0), C.DURATION)
        frame = int(round(t * C.FPS)) if frame is None else frame
        spec = self.timeline.scene_at(t)
        lyric = self.timeline.at(t)
        ctx = Ctx(
            t=t, frame=frame, scene=spec, local=t - spec.start,
            progress=(t - spec.start) / max(1e-9, spec.end - spec.start),
            lyric=lyric, lyric_t=t - lyric.start,
            lyric_local=0.0 if lyric.duration <= 0 else (t - lyric.start) / lyric.duration,
            rng=random.Random((frame * 1_000_003) ^ 0x5EED),
            audio=self.audio, assets=self.assets, glyphs=self.glyphs,
            content=self.content, terms=self.content.terms,
            script=self.content.scene(spec.key),
        )
        c = Canvas(self.glyphs)
        c.clear(fg=C.TEXT, bg=C.INK)
        scene = self.scenes.get(spec.key)
        if scene is None:
            self._fallback_scene(c, ctx)
        else:
            # Content-row contract: scene drawing is clipped to rows 2..52 by
            # the canvas itself (primitives + braille rejects chrome rows).
            c.set_content_clip(C.CONTENT_Y0, C.CONTENT_Y1)
            try:
                scene.draw(c, ctx)
            finally:
                c.clear_clip()
            # focus-region contract: a scene may flag a special-transition
            # window where the left-lane dialog rule is deliberately broken.
            c.dlg_exempt = bool(scene.dialog_exempt(t))
        # Direct row/list writes bypass the clip; discard anything that still
        # landed on the chrome rows and count it for `verify`.
        bleeds = 0
        for y in (*range(0, C.CONTENT_Y0), *range(C.CONTENT_Y1, C.H)):
            if any(c.ch[y]) or any(v != C.TEXT for v in c.fg[y]) \
                    or any(v != C.INK for v in c.bg[y]):
                bleeds += 1
                c.ch[y] = [0] * c.w
                c.fg[y] = [C.TEXT] * c.w
                c.bg[y] = [C.INK] * c.w
        c.scene_bleed = bleeds
        # chrome is drawn after the scene so it always stays legible
        self.chrome.draw_top(c, t, spec, ctx)
        self.chrome.draw_progress(c, t)
        self.chrome.draw_bottom(c, t, spec, lyric, frame, ctx)
        return c

    def _fallback_scene(self, c: Canvas, ctx: Ctx) -> None:
        c.clear(fg=C.TEXT, bg=C.INK)
        c.text(10, 2, f"[MISSING SCENE MODULE: {ctx.scene.key}]", C.RED, C.INK)
        c.text(12, 2, f"{C.fmt_clock(ctx.t)}  {ctx.lyric.text}", C.TEXT, C.INK)

    # -- frame -----------------------------------------------------------
    def frame_at(self, t: float, frame: int | None = None) -> np.ndarray:
        c = self.canvas_at(t, frame)
        rng = np.random.default_rng(int(round(t * 1000)) ^ 0xA11CE)
        return self.raster.rasterize(c, rng)

    # -- CRT output stage (MP4 render path) ------------------------------
    def _crt_filter(self, strength: float, backend: str = "cpu"):
        from .crt import create_filter

        key = (round(float(strength), 3), backend)
        flt = self._crt_filters.get(key)
        if flt is None:
            flt = self._crt_filters[key] = create_filter(key[0], backend)
        return flt

    def output_frame_at(self, t: float, frame: int | None = None,
                        crt: float = 0.0, backend: str = "cpu") -> np.ndarray:
        """Final video frame: internal raster plus the optional CRT stage.

        With crt <= 0 this is the flat 2000x1120 raster scaled to 1920x1080
        (the pre-CRT deliverable look).  With crt > 0 the CRT filter resamples
        the raster through the curved glass itself.
        """
        raw = self.frame_at(t, frame)
        if crt <= 0.0:
            from .raster import scale_to_output
            return scale_to_output(raw)
        return self._crt_filter(crt, backend).apply(raw, t)

    def png_at(self, t: float, path, scale: bool = True,
               crt: float = 0.0, backend: str = "cpu") -> None:
        from PIL import Image

        if crt > 0.0:
            frame = self.output_frame_at(t, crt=crt, backend=backend)
        else:
            frame = self.frame_at(t)
            if scale:
                from .raster import scale_to_output
                frame = scale_to_output(frame)
        Image.fromarray(frame, "RGB").save(path)

    def scene_frames(self) -> list[tuple[float, float, str]]:
        return [(s.start, s.end, s.key) for s in get_specs()]


# --------------------------------------------------------------------------
# Lazy singletons (workers inherit via fork / fresh subprocess env)
# --------------------------------------------------------------------------
_timeline: Timeline | None = None
_audio: Audio | None = None
_glyphs: GlyphTable | None = None
_specs = None
_renderer: Renderer | None = None


def get_timeline() -> Timeline:
    global _timeline
    if _timeline is None:
        _timeline = load_timeline()
    return _timeline


def get_specs():
    global _specs
    if _specs is None:
        from .timeline import SCENE_SPECS
        _specs = SCENE_SPECS
    return _specs


def get_audio() -> Audio:
    global _audio
    if _audio is None:
        _audio = load_audio()
    return _audio


def get_glyphs() -> GlyphTable:
    global _glyphs
    if _glyphs is None:
        _glyphs = glyph_table()
    return _glyphs


def get_renderer(locale: str | None = None) -> Renderer:
    global _renderer
    if _renderer is None or (locale and locale != _renderer.locale):
        _renderer = Renderer(locale=locale)
    return _renderer


def render_png(t: float, path, scale: bool = True) -> None:
    get_renderer().png_at(t, path, scale=scale)
