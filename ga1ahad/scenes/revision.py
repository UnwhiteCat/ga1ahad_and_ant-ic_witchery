"""The continuous session transcript across the interlude and Scene 4."""

from .. import art
from .. import config as C
from ..canvas import wrap


def draw_session(c, t, beats, title, labels, accent, pauses=None):
    """Draw visible turns and return the lower part of the dialog for status."""
    y, x, h, w = C.DLG_SLOTS[0]
    bg = C.mix(C.PANEL, C.INK, 0.45)
    art.llm_dialog(c, y, x, h, w, title, bg=bg, border=accent,
                   title_fg=C.TEXT_HI, style="rounded")

    left, width = x + 3, w - 6
    pauses = pauses or {}
    rows = []
    for beat in beats:
        if beat.at > t:
            break
        message = next((value for key, value in beat.items()
                        if key not in ("at", "direction")), None)
        if message is None:
            continue
        is_core = "core" in beat
        delay = pauses.get(beat.at, 0.0)
        if t - beat.at < delay:
            message = message.partition(". ")[0] + "."
        rows.append((is_core, wrap(message, width)))

    # Keep the newest turn at the same reading position. When a long reply
    # wraps, reveal its second line without moving the preceding turns.
    row = y + 25
    for index, (is_core, lines) in enumerate(reversed(rows)):
        size = max(2, len(lines))
        top = row - size - 1
        if top <= y:
            break
        color = C.CYAN_HI if is_core else C.TERRA_HI
        fg = C.TEXT_HI if index < 2 else C.TEXT_DIM
        turn_bg = C.mix(bg, color, 0.09) if index == 0 else bg
        if index == 0:
            c.fill(top, left - 1, size + 1, width + 2, " ", fg, turn_bg)
        c.text(top, left, labels[is_core], color, turn_bg, bold=True)
        for i, line in enumerate(lines):
            c.text(top + i + 1, left, line, fg, turn_bg, bold=index == 0)
        row = top - 2

    return y + 26, left, width, bg
