"""Scene base class shared by the prologue and the six chapters.

A scene is a pure function of time: ``draw(canvas, ctx)`` repaints the whole
content area for the current instant.  Use ``ctx.rng`` for deterministic
randomness, ``ctx.audio`` for musical reactivity and ``ctx.lyric`` /
``ctx.lyric_local`` for the exact VTT-synchronised lyric state.
"""

from __future__ import annotations

from .. import config as C
from ..timeline import SCENE_SPECS


class Scene:
    """Base class for chapters.

    Content model
    -------------
    ``self.T``       glossary terms (``self.T.claude_code_desktop``)
    ``self.script``  this scene's screenplay box (``self.script.s2_1.banner``)
    ``self.content`` full content object (locale, ui strings, helpers)

    Proper nouns must never be hard-coded in scene code: use ``ctx.terms`` /
    ``content/<locale>/terms*.toml``.  Story text belongs in
    ``content/<locale>/scenes/<scene>.toml``.

    The lyric lines shown in a scene come from the VTT via ``self.cues`` (the
    cues whose start falls inside this scene's window); reference them by local
    index with ``cue_progress`` / ``cue_local`` / ``cue_text`` instead of
    copying lyric strings into code.
    """

    NAME = "scene"

    # Absolute track time spans where the focus-region dialog rule is
    # deliberately broken (special transitions only, e.g. a full-bleed strobe
    # montage).  Everywhere else art.llm_dialog() windows must stay in the
    # left lane and `./ga1ahad_tui check` enforces it on a frame sweep.
    DIALOG_EXEMPT: tuple[tuple[float, float], ...] = ()

    def dialog_exempt(self, t: float) -> bool:
        """True inside a documented special-transition window."""
        return any(a <= t < b for a, b in self.DIALOG_EXEMPT)

    def __init__(self, assets, audio, timeline, content):
        self.assets = assets
        self.audio = audio
        self.timeline = timeline
        self.content = content
        self.T = content.terms
        self.script = content.scene(self.NAME)
        self.cfg = C
        spec = next((s for s in SCENE_SPECS if s.key == self.NAME), None)
        self._spec = spec
        lo = spec.start - 1e-6 if spec is not None else 0.0
        hi = spec.end - 1e-6 if spec is not None else C.DURATION
        self.cues = [ly for ly in timeline.lyrics if lo <= ly.start < hi]

    # -- required --------------------------------------------------------
    def draw(self, c, ctx) -> None:
        raise NotImplementedError

    # -- cue helpers -----------------------------------------------------
    # Local cue index = position in self.cues (the VTT cues inside this
    # scene's window).  This keeps lyric text out of scene code while the VTT
    # stays the single source of truth for text AND timing.
    def cue(self, index: int):
        return self.cues[index]

    def cue_text(self, index: int) -> str:
        return self.cues[index].text

    def cue_progress(self, ctx, index: int) -> float:
        """0..1 through the index-th local VTT cue."""
        ly = self.cues[index]
        return min(1.0, max(0.0, (ctx.t - ly.start) / max(1e-6, ly.duration)))

    def cue_local(self, ctx, index: int) -> float:
        """Seconds since the index-th local VTT cue started."""
        return ctx.t - self.cues[index].start
