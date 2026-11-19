"""Scene 3.5 / interlude -- thin dispatcher over the two movement modules.

The 67.7 s interlude is the biggest chapter of the film and is authored as two
independent, testable halves so the four movements can be developed in
parallel:

    ga1ahad/scenes/s35a.py   movements 1-2   90.190 .. 123.180
    ga1ahad/scenes/s35b.py   movements 3-4  123.180 .. 157.900

Each half exposes prepare(scene) for constructor-time geometry and
draw(scene, c, ctx) for the per-frame painting.  This module owns the scene
registration, the split boundary and the conversation-window safety net for
the 617-page revision beat; it contains no visual design of its own.
"""

from __future__ import annotations

import importlib
import traceback

from .. import config as C
from .base import Scene

SPLIT = 123.180                 # movement 2 -> movement 3 boundary
REV_START = 148.890             # s35.toml [revision] window (station B7)
REV_END = 157.900


def _load(name: str):
    try:
        return importlib.import_module(name, __package__)
    except Exception:                       # pragma: no cover - rendered fallback
        traceback.print_exc()
        return None


class Scene35(Scene):
    """Four-movement interlude; delegates the painting to s35a / s35b."""

    NAME = "s35"

    def __init__(self, assets, audio, timeline, content) -> None:
        super().__init__(assets, audio, timeline, content)
        self.m1m2 = _load(".s35a")
        self.m3m4 = _load(".s35b")
        for module in (self.m1m2, self.m3m4):
            if module is None:
                continue
            try:
                module.prepare(self)
            except Exception:               # pragma: no cover - keep rendering
                traceback.print_exc()

    # ------------------------------------------------------------------
    def draw(self, c, ctx) -> None:
        t = ctx.t
        if t < SPLIT:
            if self.m1m2 is not None:
                self.m1m2.draw(self, c, ctx)
            else:
                self._closing(c, ctx, t)
        else:
            if self.m3m4 is not None:
                self.m3m4.draw(self, c, ctx)
            else:
                self._closing(c, ctx, t)
        # Focus-region safety net: the 617-page revision beat is a real
        # human<->LLM conversation and must live in the portrait window even if
        # a movement forgets it.  Never fires when the movement already drew.
        if REV_START <= t < REV_END and not c.dlg_cells:
            self._revision_note(c, ctx)

    # ------------------------------------------------------------------
    def _closing(self, c, ctx, t: float) -> None:
        """Bare, deterministic fallback if a movement module is unavailable."""
        c.fill(C.CONTENT_Y0, 0, C.CONTENT_H, C.W, " ", C.TEXT, C.INK)
        c.text(24, C.STAGE_X + 8, "INTERLUDE // SEGMENT PENDING", C.TERRA_DIM, C.INK)

    def _revision_note(self, c, ctx) -> None:
        from .revision import draw_session

        interlude = self.script.v2.interlude
        beats = list(self.script.revision.beats)
        labels = (interlude.user, interlude.assistant)
        draw_session(c, ctx.t, beats, interlude.desktop_title, labels,
                     C.TERRA_DIM)
