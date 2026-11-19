"""VTT timeline parser (single source of truth) and scene registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config as C

_TS = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})")


def _sec(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


@dataclass(frozen=True)
class Lyric:
    index: int
    start: float
    end: float
    text: str
    instrumental: bool = False

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class SceneSpec:
    key: str
    start: float
    end: float
    number: str

    @property
    def duration(self) -> float:
        return self.end - self.start


# Scene windows define dispatch boundaries; the VTT supplies the timing
# for every lyric line inside these ranges.
# Scene windows are timing-only.  Human-readable titles/orgs live in
# content/<locale>/ui.toml so the whole film can be re-skinned or translated.
SCENE_SPECS: list[SceneSpec] = [
    SceneSpec("prologue", 0.000, 17.540, "00"),
    SceneSpec("s1", 17.540, 40.640, "01"),
    SceneSpec("s2", 40.640, 63.860, "02"),
    SceneSpec("s3", 63.860, 90.190, "03"),
    SceneSpec("s35", 90.190, 157.900, "3.5"),
    SceneSpec("s4", 157.900, 175.320, "04"),
    SceneSpec("s5", 175.320, 206.850, "05"),
    SceneSpec("s6", 206.850, C.DURATION, "06"),
]


class Timeline:
    def __init__(self, lyrics: list[Lyric], path: Path | None = None) -> None:
        self.lyrics = lyrics
        self.path = path
        self.by_text: dict[str, Lyric] = {}
        for ly in lyrics:
            self.by_text[ly.text] = ly

    # -- lookup ----------------------------------------------------------
    def at(self, t: float) -> Lyric:
        # binary search
        lo, hi = 0, len(self.lyrics) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.lyrics[mid].start <= t:
                lo = mid
            else:
                hi = mid - 1
        ly = self.lyrics[lo]
        if t >= ly.end and lo + 1 < len(self.lyrics):
            # t exactly on a boundary belongs to the next line
            if abs(t - ly.end) < 1e-9:
                return self.lyrics[lo + 1]
        return ly

    def index_at(self, t: float) -> int:
        return self.at(t).index

    def local(self, t: float) -> float:
        ly = self.at(t)
        return t - ly.start

    def lyric(self, text: str) -> Lyric:
        return self.by_text[text]

    def scene_at(self, t: float) -> SceneSpec:
        for spec in SCENE_SPECS:
            if spec.start <= t < spec.end:
                return spec
        return SCENE_SPECS[-1]

    def range(self, start: float, end: float) -> list[Lyric]:
        return [ly for ly in self.lyrics if ly.end > start and ly.start < end]

    def scene_of_lyric(self, ly: Lyric) -> SceneSpec:
        return self.scene_at(ly.start + 1e-6)

    def markers(self) -> list[float]:
        return [spec.start for spec in SCENE_SPECS] + [C.DURATION]


def parse_vtt(path: Path) -> Timeline:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    lyrics: list[Lyric] = []
    i = 0
    idx = 0
    while i < len(lines):
        line = lines[i].strip()
        m = _TS.search(line)
        if not m:
            i += 1
            continue
        start = _sec(*m.groups()[:4])
        end = _sec(*m.groups()[4:])
        payload: list[str] = []
        i += 1
        while i < len(lines) and lines[i].strip() and not _TS.search(lines[i]):
            payload.append(lines[i].strip())
            i += 1
        body = " ".join(payload) if payload else ""
        if not body:
            continue
        instrumental = body.startswith("[") and body.endswith("]")
        lyrics.append(Lyric(index=idx, start=round(start, 3), end=round(end, 3),
                            text=body, instrumental=instrumental))
        idx += 1
    if not lyrics:
        raise ValueError(f"no cues parsed from {path}")
    # sanity: contiguous, monotonic coverage
    for a, b in zip(lyrics, lyrics[1:]):
        if b.start < a.end - 1e-6:
            raise ValueError(f"overlapping cues: {a.text!r} / {b.text!r}")
    return Timeline(lyrics, path)


def load_timeline(path: Path | None = None) -> Timeline:
    return parse_vtt(path or C.VTT_PATH)
