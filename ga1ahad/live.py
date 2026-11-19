"""Realtime terminal renderer (truecolor ANSI, 200x56) with optional audio sync."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from . import config as C
from .canvas import Canvas


# --------------------------------------------------------------------------
# ANSI conversion
# --------------------------------------------------------------------------
def _fg(code: int) -> str:
    return f"\x1b[38;2;{(code >> 16) & 255};{(code >> 8) & 255};{code & 255}m"


def _bg(code: int) -> str:
    return f"\x1b[48;2;{(code >> 16) & 255};{(code >> 8) & 255};{code & 255}m"


class AnsiPainter:
    def __init__(self) -> None:
        self.prev_ch: list[list[int]] | None = None
        self.prev_fg: list[list[int]] | None = None
        self.prev_bg: list[list[int]] | None = None
        self.cur_fg = -1
        self.cur_bg = -1
        self.glyphs = None

    def reset(self) -> None:
        self.prev_ch = self.prev_fg = self.prev_bg = None

    def paint(self, canvas: Canvas, force: bool = False) -> str:
        if self.glyphs is None:
            self.glyphs = canvas.glyphs
        chars = self.glyphs.chars
        out: list[str] = []
        full = force or self.prev_ch is None
        if full:
            out.append("\x1b[H")
        pch, pfg, pbg = self.prev_ch, self.prev_fg, self.prev_bg
        cur_fg, cur_bg = self.cur_fg, self.cur_bg
        for y in range(canvas.h):
            chrow = canvas.ch[y]
            fgrow = canvas.fg[y]
            bgrow = canvas.bg[y]
            x = 0
            while x < canvas.w:
                changed = (full or pch is None or chrow[x] != pch[y][x]
                           or fgrow[x] != pfg[y][x] or bgrow[x] != pbg[y][x])
                if not changed:
                    x += 1
                    continue
                x0 = x
                while x < canvas.w:
                    if not (full or pch is None or chrow[x] != pch[y][x]
                            or fgrow[x] != pfg[y][x] or bgrow[x] != pbg[y][x]):
                        break
                    x += 1
                out.append(f"\x1b[{y + 1};{x0 + 1}H")
                for xx in range(x0, x):
                    fg = fgrow[xx]
                    bg = bgrow[xx]
                    if fg != cur_fg:
                        out.append(_fg(fg))
                        cur_fg = fg
                    if bg != cur_bg:
                        out.append(_bg(bg))
                        cur_bg = bg
                    out.append(chars[chrow[xx]])
        out.append("\x1b[0m")
        self.prev_ch = [row[:] for row in canvas.ch]
        self.prev_fg = [row[:] for row in canvas.fg]
        self.prev_bg = [row[:] for row in canvas.bg]
        self.cur_fg = cur_fg
        self.cur_bg = cur_bg
        return "".join(out)


# --------------------------------------------------------------------------
# Audio playback
# --------------------------------------------------------------------------
def _audio_cmd(path: str, start: float) -> list[str] | None:
    env = os.environ.get("GA1AHAD_PLAYER")
    if env:
        return [env, path]
    from .encode import find_ffmpeg

    ffplay = shutil.which("ffplay")
    if ffplay:
        return [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet",
                "-ss", f"{start:.3f}", path]
    mpv = shutil.which("mpv")
    if mpv:
        return [mpv, "--no-video", "--really-quiet", f"--start={start:.3f}", path]
    paplay = shutil.which("paplay")
    if paplay and start < 0.05:
        return [paplay, path]
    try:
        ff = find_ffmpeg()
    except Exception:
        return None
    # direct ALSA output through ffmpeg (works on most Linux desktops)
    return [ff, "-hide_banner", "-loglevel", "quiet", "-nostdin",
            "-ss", f"{start:.3f}", "-i", path, "-f", "alsa", "default"]


def start_audio(start: float) -> subprocess.Popen | None:
    if not C.AUDIO_PATH.exists():
        return None
    cmd = _audio_cmd(str(C.AUDIO_PATH), start)
    if not cmd:
        return None
    try:
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    except Exception:
        return None


# --------------------------------------------------------------------------
# Live loop
# --------------------------------------------------------------------------
def run_live(start: float = 0.0, mute: bool = False, fps_cap: float = 30.0,
             max_frames: int | None = None, force: bool = False) -> int:
    if not sys.stdout.isatty() and not force:
        print("live mode needs an interactive terminal; use "
              "`ga1ahad_tui png --at T` or `ga1ahad_tui render` instead "
              "(or pass --force to dump ANSI to stdout).",
              file=sys.stderr)
        return 2
    from .frame import get_renderer

    size = shutil.get_terminal_size((80, 24))
    if size.columns < C.W or size.lines < C.H:
        print(f"\x1b[33m[ga1ahad] terminal is {size.columns}x{size.lines}; "
              f"the TUI is {C.W}x{C.H} and will wrap.\x1b[0m", file=sys.stderr)
    renderer = get_renderer()
    painter = AnsiPainter()
    out = sys.stdout
    out.write("\x1b[?1049h\x1b[?25l\x1b[2J")
    out.flush()
    player = None if mute else start_audio(start)
    if not mute and player is None:
        out.write("\x1b[1;1H\x1b[33m[no audio player found -- running silently]\x1b[0m")
        out.flush()
    t0 = time.monotonic()
    last_frame = -1
    shown = 0
    frame_period = 1.0 / max(1.0, fps_cap)
    try:
        while True:
            now = time.monotonic()
            t = start + (now - t0)
            if t >= C.DURATION:
                break
            frame = int(t * C.FPS)
            if frame == last_frame:
                time.sleep(min(0.004, frame_period / 2))
                continue
            last_frame = frame
            # skip-ahead if rendering can't keep up (stay in sync with audio)
            canvas = renderer.canvas_at(t, frame)
            out.write(painter.paint(canvas))
            out.flush()
            shown += 1
            if max_frames is not None and shown >= max_frames:
                break
            target = t0 + (frame + 1) / C.FPS - start
            sleep = target - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
    except KeyboardInterrupt:
        pass
    finally:
        if player is not None:
            try:
                player.terminate()
            except Exception:
                pass
        out.write("\x1b[0m\x1b[2J\x1b[?25h\x1b[?1049l")
        out.flush()
    return 0
