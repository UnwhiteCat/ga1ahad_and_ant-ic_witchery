"""Project self-verification: timeline, scenes, lyric sync, audio, MP4 and CRT."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

from . import config as C
from .content import ContentError, get_content
from .encode import extract_audio, find_ffmpeg, probe
from .timeline import SCENE_SPECS, load_timeline

# dedicated acceptance clip: the Scene 5 "Kiss me tenderly gently violently"
# set piece (0.75 s of lead-in so the abrupt shake onset and the progressive
# error-popup storm are visible, then the absolute-calm snap).
CLIP_START = 184.50
CLIP_END = 198.30
CLIP_DURATION = CLIP_END - CLIP_START          # 13.8 s
CLIP_FRAMES = round(CLIP_DURATION * C.FPS)     # 414

OK = "\x1b[32mPASS\x1b[0m"
BAD = "\x1b[31mFAIL\x1b[0m"
WARN = "\x1b[33mWARN\x1b[0m"


class Report:
    def __init__(self) -> None:
        self.failures = 0
        self.checks = 0

    def ok(self, name: str, detail: str = "") -> None:
        self.checks += 1
        print(f"  [{OK}] {name}" + (f"  \u00b7 {detail}" if detail else ""))

    def fail(self, name: str, detail: str = "") -> None:
        self.checks += 1
        self.failures += 1
        print(f"  [{BAD}] {name}" + (f"  \u00b7 {detail}" if detail else ""))

    def warn(self, name: str, detail: str = "") -> None:
        self.checks += 1
        print(f"  [{WARN}] {name}" + (f"  \u00b7 {detail}" if detail else ""))

    def expect(self, cond: bool, name: str, detail: str = "") -> bool:
        if cond:
            self.ok(name, detail)
        else:
            self.fail(name, detail)
        return cond


# --------------------------------------------------------------------------
def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        nch, sr, sw, n = w.getnchannels(), w.getframerate(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    else:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    if nch > 1:
        data = data.reshape(-1, nch).mean(axis=1)
    return data, sr


def _stream_fps(stream: dict) -> tuple[float, str]:
    """Return (fps, raw_string) using the CFR rate, falling back to average."""
    for key in ("r_frame_rate", "avg_frame_rate"):
        raw = stream.get(key) or ""
        if raw in ("", "0/0"):
            continue
        try:
            num, _, den = raw.partition("/")
            val = float(num) / (float(den) or 1.0)
        except (TypeError, ValueError):
            continue
        if 1.0 < val < 1000.0:
            return val, raw
    return 0.0, ""


def _envelope(data: np.ndarray, sr: int, hop: int = 320) -> np.ndarray:
    n = len(data) // hop
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    seg = data[:n * hop].reshape(n, hop)
    return np.sqrt((seg ** 2).mean(axis=1)).astype(np.float32)


def _crt_signature(video: Path, t: float) -> tuple[float, float]:
    """Decode one frame and measure the CRT corner mask + scanline contrast.

    Returns (darkest corner brightness, odd/even row-mean ratio).  A CRT-stage
    deliverable has near-black corners from the curved bezel and every odd
    output line dimmer than the even ones.
    """
    ff = find_ffmpeg()
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "frame.png"
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y",
                        "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                        str(png)], check=True)
        from PIL import Image
        arr = np.asarray(Image.open(png).convert("RGB"), dtype=np.float32)
    rows = arr.mean(axis=(1, 2))
    ratio = float(rows[1::2].mean() / max(1e-6, rows[::2].mean()))
    corners = np.array([arr[0, 0].mean(), arr[0, -1].mean(),
                        arr[-1, 0].mean(), arr[-1, -1].mean()])
    return float(corners.max()), ratio


# --------------------------------------------------------------------------
def check_files(rep: Report) -> None:
    print("\n\x1b[1m[1] source files and timeline\x1b[0m")
    rep.expect(C.VTT_PATH.exists(), "ga1ahad.vtt present")
    rep.expect(C.AUDIO_PATH.exists(), "ga1ahad_audio.wav present")
    rep.expect(C.CLAUDE_IMAGE.exists(), "claude.webp present")
    tl = load_timeline()
    rep.ok("VTT parsed", f"{len(tl.lyrics)} cues")
    first, last = tl.lyrics[0], tl.lyrics[-1]
    rep.expect(abs(first.start) < 1e-6, "timeline starts at 0.000", f"{first.start:.3f}")
    rep.expect(abs(last.end - C.DURATION) < 0.005, "timeline ends at audio duration",
               f"{last.end:.3f} vs {C.DURATION:.3f}")
    gaps = [(a.text, b.text, b.start - a.end) for a, b in zip(tl.lyrics, tl.lyrics[1:])
            if abs(b.start - a.end) > 1e-6]
    rep.expect(not gaps, "VTT cues are contiguous (no deleted audio)", str(gaps[:3]))
    # scene coverage
    rep.expect(abs(SCENE_SPECS[0].start) < 1e-9, "scene timeline starts at 0")
    rep.expect(abs(SCENE_SPECS[-1].end - C.DURATION) < 1e-6,
               "scene timeline covers full song")
    sc_gaps = [f"{a.key}->{b.key}" for a, b in zip(SCENE_SPECS, SCENE_SPECS[1:])
               if abs(b.start - a.end) > 1e-6]
    rep.expect(not sc_gaps, "scene boundaries contiguous", str(sc_gaps))
    # audio
    data, sr = _read_wav(C.AUDIO_PATH)
    dur = len(data) / sr
    rep.expect(sr == 32000, "audio sample rate 32 kHz", f"{sr}")
    rep.expect(abs(dur - C.DURATION) < 0.002, "audio duration 219.15 s", f"{dur:.6f}s")
    n_lyrics = sum(1 for ly in tl.lyrics if not ly.instrumental)
    rep.expect(len(tl.lyrics) == 75 and n_lyrics == 73,
               "75 VTT cues / 73 sung lines (full uncut song)",
               f"{len(tl.lyrics)} cues, {n_lyrics} lyrics")
    # every lyric lands in exactly one scene
    bad = []
    for ly in tl.lyrics:
        n = sum(1 for s in SCENE_SPECS if s.start <= ly.start + 1e-6 < s.end)
        if n != 1:
            bad.append(ly.text)
    rep.expect(not bad, "every cue mapped to one scene", str(bad[:3]))


def check_content(rep: Report) -> None:
    print("\n\x1b[1m[2] central content layer (glossary + screenplay)\x1b[0m")
    from .audit import audit_text, validate_content

    try:
        content = get_content()
    except ContentError as exc:
        rep.fail("content layer loads", str(exc))
        return
    rep.ok("content layer loads", f"locale={content.locale} terms={len(content.terms)}")
    problems = validate_content()
    rep.expect(not problems, "every locale has screenplay + titles for all scenes",
               "; ".join(problems[:3]))
    titles = {}
    for spec in SCENE_SPECS:
        try:
            titles[spec.key] = content.scene_title(spec.key)
        except ContentError as exc:
            rep.fail(f"scene title {spec.key}", str(exc))
    rep.expect(len(titles) == len(SCENE_SPECS), "scene titles come from ui.toml",
               f"{len(titles)}/{len(SCENE_SPECS)}")
    locales = content.available_locales()
    rep.expect(content.locale in locales, "requested locale available",
               f"{', '.join(locales)}")
    # literal-brace escape must work exactly as documented ({{ -> {, }} -> })
    from .content import Terms as _Terms
    try:
        probe = _Terms({"claude": "Claude"})
        escaped = probe._expand_terms("{{claude}} and {claude}", "selftest")
        rep.expect(escaped == "{claude} and Claude", "content {{brace}} escaping",
                   repr(escaped))
    except Exception as exc:  # pragma: no cover - defensive
        rep.fail("content brace escaping", str(exc))
    violations, stats = audit_text(stats=True)
    rep.expect(not violations, "no hard-coded proper nouns / retired stand-ins",
               f"{len(violations)} violations" + (f" e.g. {violations[0]}" if violations else ""))
    lyric_v = [v for v in violations if getattr(v, "kind", "") == "lyric-copy"]
    rep.expect(not lyric_v, "no hard-coded VTT lyric text in scene code",
               f"{len(lyric_v)} copies" + (f" e.g. {lyric_v[0]}" if lyric_v else ""))
    rep.ok("narrative strings extracted", f"{stats.narrative_literals} long literals remain in scene code")
    # glossary regression: product names must resolve from terms.toml
    terms = content.terms
    rep.expect("Claude Code Desktop" == terms.claude_code_desktop
               and terms.claude_code == "claude code",
               "real-world product names resolved from glossary",
               f"{terms.claude_code_desktop!r} / {terms.claude_code!r}")


def check_rendering(rep: Report, sample: int = 3) -> None:
    print("\n\x1b[1m[3] renderer + lyric synchronisation\x1b[0m")
    from .frame import get_renderer

    r = get_renderer()
    missing = [s.key for s in SCENE_SPECS if s.key not in r.scenes]
    rep.expect(not missing, "all scene modules loaded", str(missing))
    tl = r.timeline
    bad_lyric: list[str] = []
    bad_dims = 0
    bad_clock = 0
    for ly in tl.lyrics:
        if ly.instrumental:
            continue
        fracs = (0.5,) if sample <= 1 else ((0.05, 0.5, 0.95)[:sample])
        for f in fracs:
            t = min(max(ly.start + ly.duration * f, 0.0), C.DURATION - 1e-4)
            c = r.canvas_at(t)
            if c.w != C.W or c.h != C.H:
                bad_dims += 1
            row = c.row_text(C.H - 2)
            # strip the decorative music notes
            clean = row.replace("\u266a", "").strip()
            if ly.text not in clean:
                bad_lyric.append(f"{t:.3f}s {ly.text!r} -> {clean!r}")
            # clock in footer must match t within one frame
            row2 = c.row_text(C.H - 1)
            stamp = C.fmt_clock(t)
            if stamp not in row2:
                bad_clock += 1
    rep.expect(bad_dims == 0, "canvas is exactly 200x56", f"{bad_dims} bad")
    rep.expect(not bad_lyric, "lyric bar matches VTT at every cue",
               f"{len(bad_lyric)} mismatches: {bad_lyric[:2]}")
    rep.expect(bad_clock == 0, "timecode matches frame clock", f"{bad_clock} bad")
    # chrome scene title must come from the content layer
    bad_title = []
    for spec in SCENE_SPECS:
        t = (spec.start + spec.end) / 2
        c = r.canvas_at(t)
        row = c.row_text(C.H - 3)
        want = r.content.scene_title(spec.key)
        if r.content.ui.chrome.uppercase_titles:
            want = want.upper()
        if want not in row:
            bad_title.append((spec.key, want, row.strip()))
    rep.expect(not bad_title, "scene title ribbon matches content config",
               str(bad_title[:2]))
    # spot-check that scenes actually paint and are not blank
    blank = []
    for spec in SCENE_SPECS:
        t = (spec.start + spec.end) / 2
        c = r.canvas_at(t)
        keys = {(c.ch[y][x], c.fg[y][x]) for y in range(2, C.H - 3, 6) for x in range(0, C.W, 8)}
        if len(keys) < 8:
            blank.append(spec.key)
    rep.expect(not blank, "all scenes produce rich content", str(blank))
    # glyphtable sanity
    rep.expect(r.glyphs.count > 300, "glyph atlas built", f"{r.glyphs.count} glyphs")

    # ---- content-row contract ------------------------------------------
    # The canvas clips scene painting to rows 2..52 (synthetic check), and the
    # renderer discards/counts any direct row writes that bypass the clip.
    from .canvas import Canvas
    probe = Canvas(r.glyphs)
    probe.set_content_clip(C.CONTENT_Y0, C.CONTENT_Y1)
    probe.put(0, 0, "X", C.WHITE, C.INK)
    probe.text(C.H - 1, 0, "X", C.WHITE, C.INK)
    probe.fill(C.CONTENT_Y1, 0, 4, 8, "X", C.WHITE, C.INK)
    clipped = probe.clip_count
    probe.clear_clip()
    clean = (not probe.row_text(0).strip() and not probe.row_text(C.H - 1).strip()
             and not probe.row_text(C.CONTENT_Y1).strip())
    rep.expect(clean and clipped >= 3, "canvas clips scene painting to content rows",
               f"clip_count={clipped}")
    # ---- LLM dialog contract -------------------------------------------
    # Conversation windows must be portrait 9:16 with the 1/1/1 margins; the
    # right stage carries the scene animation.  This is the focus-region rule
    # the whole film is composed around (special transitions may exempt
    # themselves via Scene.DIALOG_EXEMPT).
    from . import art as _art
    probe = Canvas(r.glyphs)
    lane_ok = True
    probe_rects = (C.DLG_SLOTS[0], (C.CONTENT_Y0 + 1, C.DLG_X, 16, 18))
    for y, x, h, w in probe_rects:
        probe.clear()
        probe.set_content_clip(C.CONTENT_Y0, C.CONTENT_Y1)
        _art.llm_dialog(probe, y, x, h, w, title="PROBE")
        lane_ok = (lane_ok and probe.dlg_cells == h * w
                   and probe.dlg_stage_bleed == 0)
    rejected = 0
    for bad in ((4, 4, 48, 60), (4, 4, 52, 54), (6, 1, 48, 54),
                (3, 20, 48, 54), (2, 1, 48, 54)):
        try:
            probe.clear()
            probe.set_content_clip(C.CONTENT_Y0, C.CONTENT_Y1)
            _art.llm_dialog(probe, *bad)
        except ValueError:
            rejected += 1
    rep.expect(lane_ok and rejected == 5,
               "LLM dialog helper enforces portrait 9:16 with 1/1/1 margins",
               f"9:16/margins ok={lane_ok}, rejected {rejected}/5 invalid rects")
    # sweep shared with the chrome-row contract (one canvas build per sample)
    bleed = []
    lane_bleed = []
    dialog_scenes = {"prologue", "s1", "s2", "s3", "s35", "s4", "s5"}
    used = {k: False for k in dialog_scenes}
    step = 0.2
    n = int(C.DURATION / step)
    for i in range(n):
        t = i * step
        c = r.canvas_at(t)
        if c.scene_bleed:
            bleed.append(round(t, 2))
        if c.dlg_cells:
            key = r.timeline.scene_at(t).key
            if key in used:
                used[key] = True
        if c.dlg_stage_bleed and not c.dlg_exempt:
            lane_bleed.append(round(t, 2))
    rep.expect(not bleed, "scene draw never writes chrome rows (sweep)",
               f"{len(bleed)} frames: {bleed[:4]}")
    rep.expect(not lane_bleed,
               "LLM dialogs never enter the right animation stage (sweep)",
               f"{len(lane_bleed)} frames: {lane_bleed[:4]}")
    missing_dialog = [k for k, v in used.items() if not v]
    rep.expect(not missing_dialog,
               "every dialog scene pins its conversation to the left lane",
               str(missing_dialog))


def check_video(rep: Report, video: Path, quick: bool = False) -> None:
    print("\n\x1b[1m[4] MP4 video + audio sync\x1b[0m")
    if not video.exists():
        rep.warn("mp4 exists", f"{video} not found (run: ./ga1ahad_tui render)")
        return
    rep.ok("mp4 present", f"{video.stat().st_size / 1e6:.1f} MB")
    info = probe(video)
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    vs = [s for s in streams if s.get("codec_type") == "video"]
    aus = [s for s in streams if s.get("codec_type") == "audio"]
    if not rep.expect(bool(vs), "video stream present"):
        return
    v = vs[0]
    rep.expect(v.get("codec_name") == "h264", "video codec h264", v.get("codec_name", ""))
    rep.expect(int(v.get("width", 0)) == C.OUT_W and int(v.get("height", 0)) == C.OUT_H,
               "resolution 1920x1080", f"{v.get('width')}x{v.get('height')}")
    fps, fps_raw = _stream_fps(v)
    rep.expect(abs(fps - 30.0) < 0.01, "frame rate 30fps", f"{fps_raw} ({fps:.4f})")
    rep.expect(v.get("pix_fmt") == "yuv420p", "pixel format yuv420p", v.get("pix_fmt", ""))
    dur = float(fmt.get("duration", 0))
    rep.expect(abs(dur - C.DURATION) < 0.1, "container duration 219.15 s", f"{dur:.3f}s")
    if not rep.expect(bool(aus), "audio stream present"):
        return
    a = aus[0]
    rep.expect(a.get("codec_name") == "aac", "audio codec aac", a.get("codec_name", ""))
    rep.expect(int(a.get("sample_rate", 0)) == 32000, "audio 32 kHz", a.get("sample_rate", ""))
    rep.expect(int(a.get("channels", 0)) == 1, "audio mono", str(a.get("channels")))
    adur = float(a.get("duration", 0) or fmt.get("duration", 0))
    rep.expect(abs(adur - C.DURATION) < 0.1, "audio stream not truncated", f"{adur:.3f}s")
    # frame count
    nb = v.get("nb_frames")
    if nb:
        n = int(nb)
        rep.expect(abs(n - C.N_FRAMES) <= 2, "full frame count", f"{n} frames")
    # the deliverable must carry the CRT output stage
    corner, ratio = _crt_signature(video, C.DURATION * 0.5)
    rep.expect(corner < 1.0 and ratio < 0.97,
               "MP4 carries the CRT output stage",
               f"corner={corner:.1f}, odd/even row ratio={ratio:.3f}")
    # decode mp4 audio and compare envelope with source
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "mp4audio.wav"
        try:
            extract_audio(video, tmp)
        except subprocess.CalledProcessError:
            rep.fail("decode mp4 audio")
            return
        src, sr1 = _read_wav(C.AUDIO_PATH)
        got, sr2 = _read_wav(tmp)
        rep.expect(sr2 == sr1, "decoded audio sample rate", f"{sr2}")
        n = min(len(src), len(got))
        e1 = _envelope(src[:n], sr1)
        e2 = _envelope(got[:n], sr2)
        m = min(len(e1), len(e2))
        e1, e2 = e1[:m], e2[:m]
        if m > 10:
            corr = float(np.corrcoef(e1, e2)[0, 1])
            rep.expect(corr > 0.97, "audio muxed unmodified (envelope correlation)",
                       f"r={corr:.4f}")
            # zero-lag check: if shifted by 1s the correlation should drop
            shift = int(1.0 * sr1 / 320)
            if m > shift * 4:
                corr_shift = float(np.corrcoef(e1[shift:], e2[:m - shift])[0, 1])
                rep.expect(corr > corr_shift, "audio starts at t=0 (no offset)",
                           f"r0={corr:.4f} vs r1s={corr_shift:.4f}")
        rep.expect(len(got) / sr2 >= C.DURATION - 0.05, "decoded audio length complete",
                   f"{len(got) / sr2:.3f}s")


def check_acceptance_clip(rep: Report, clip: Path) -> None:
    print("\n\x1b[1m[6] acceptance clip (Scene 5 kiss storm)\x1b[0m")
    if not clip.exists():
        rep.warn("kiss acceptance clip present", f"{clip.name} missing")
        return
    rep.ok("kiss acceptance clip present", f"{clip.name} "
           f"{clip.stat().st_size / 1e6:.1f} MB")
    info = probe(clip)
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    vs = [st for st in streams if st.get("codec_type") == "video"]
    aus = [st for st in streams if st.get("codec_type") == "audio"]
    if not rep.expect(bool(vs), "clip: video stream present"):
        return
    v = vs[0]
    rep.expect(v.get("codec_name") == "h264", "clip: video codec h264", v.get("codec_name", ""))
    rep.expect(int(v.get("width", 0)) == C.OUT_W and int(v.get("height", 0)) == C.OUT_H,
               "clip: resolution 1920x1080", f"{v.get('width')}x{v.get('height')}")
    fps, fps_raw = _stream_fps(v)
    rep.expect(abs(fps - 30.0) < 0.01, "clip: frame rate 30fps",
               f"{fps_raw} ({fps:.4f})")
    rep.expect(v.get("pix_fmt") == "yuv420p", "clip: pixel format yuv420p",
               v.get("pix_fmt", ""))
    dur = float(fmt.get("duration", 0))
    rep.expect(abs(dur - CLIP_DURATION) < 0.1, f"clip: duration {CLIP_DURATION:.2f} s",
               f"{dur:.3f}s")
    nb = v.get("nb_frames")
    if nb:
        rep.expect(abs(int(nb) - CLIP_FRAMES) <= 2, "clip: frame count",
                   f"{int(nb)} frames (want {CLIP_FRAMES})")
    corner, ratio = _crt_signature(clip, CLIP_DURATION / 2)
    rep.expect(corner < 1.0 and ratio < 0.97,
               "clip carries the CRT output stage",
               f"corner={corner:.1f}, odd/even row ratio={ratio:.3f}")
    if not rep.expect(bool(aus), "clip: audio stream present"):
        return
    a = aus[0]
    rep.expect(a.get("codec_name") == "aac", "clip: audio codec aac", a.get("codec_name", ""))
    rep.expect(int(a.get("sample_rate", 0)) == 32000, "clip: audio 32 kHz",
               a.get("sample_rate", ""))
    rep.expect(int(a.get("channels", 0)) == 1, "clip: audio mono", str(a.get("channels")))
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "clipaudio.wav"
        try:
            extract_audio(clip, tmp)
        except subprocess.CalledProcessError:
            rep.fail("clip: decode audio")
            return
        src, sr = _read_wav(C.AUDIO_PATH)
        got, sr2 = _read_wav(tmp)
        start = int(round(CLIP_START * sr))
        seg = src[start:start + len(got)]
        if len(seg) < len(got):
            seg = np.pad(seg, (0, len(got) - len(seg)))
        e1 = _envelope(seg, sr)
        e2 = _envelope(got, sr2)
        m = min(len(e1), len(e2))
        if m > 10:
            corr = float(np.corrcoef(e1[:m], e2[:m])[0, 1])
            rep.expect(corr > 0.97, "clip: audio is the original segment (no offset)",
                       f"r={corr:.4f} (start={CLIP_START:.2f}s)")
            shift = int(0.5 * sr2 / 320)
            if m > shift * 4:
                corr_shift = float(np.corrcoef(e1[shift:m], e2[:m - shift])[0, 1])
                rep.expect(corr > corr_shift, "clip: zero-lag alignment beats +0.5 s shift",
                           f"r0={corr:.4f} vs r+0.5s={corr_shift:.4f}")
        rep.expect(len(got) / sr2 >= CLIP_DURATION - 0.1, "clip: audio segment complete",
                   f"{len(got) / sr2:.3f}s")


def check_frames(rep: Report, video: Path, count: int = 12) -> None:
    print("\n\x1b[1m[5] video frame sanity\x1b[0m")
    if not video.exists():
        rep.warn("frame sanity", "mp4 missing")
        return
    ff = find_ffmpeg()
    bad = []
    with tempfile.TemporaryDirectory() as td:
        for i in range(count):
            t = C.DURATION * (i + 0.5) / count
            out = Path(td) / f"f{i:02d}.png"
            subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                            str(out)], check=True)
            from PIL import Image
            arr = np.asarray(Image.open(out).convert("RGB"))
            mean = float(arr.mean())
            std = float(arr.std())
            if mean < 3 or std < 6:
                bad.append((round(t, 2), round(mean, 1), round(std, 1)))
    rep.expect(not bad, "sampled frames are not black/empty", str(bad[:4]))


def check_crt(rep: Report) -> None:
    print("\n\x1b[1m[7] CRT output stage (MP4 filter)\x1b[0m")
    from .frame import get_renderer

    r = get_renderer()
    t = 17.6
    # exercise the real renderer entry point (not just the filter in isolation)
    out = r.output_frame_at(t, crt=C.CRT_STRENGTH)
    flat = r.output_frame_at(t, crt=0.0)
    rep.expect(out.shape == (C.OUT_H, C.OUT_W, 3) and out.dtype == np.uint8
               and flat.shape == out.shape and flat.dtype == np.uint8,
               "renderer emits 1920x1080 for both CRT and flat paths",
               f"crt={out.shape}/{out.dtype}, flat={flat.shape}/{flat.dtype}")
    again = r.output_frame_at(t, crt=C.CRT_STRENGTH)
    rep.expect(np.array_equal(out, again),
               "CRT render is deterministic for a timestamp")
    # inspect the static mask directly: a corner test on the warped frame
    # alone would also pass thanks to the black curvature border
    flt = r._crt_filter(C.CRT_STRENGTH)
    mask = flt._static
    h, w = mask.shape[:2]
    column = mask[:, w // 2, 0]
    ratio = float(column[1::2].mean() / max(1e-6, column[::2].mean()))
    corner = float(mask[0, 0, 0])
    edge_mid = float(mask[0, w // 2, 0])
    centre = float(mask[h // 2, w // 2, 0])
    rep.expect(corner < 0.01 and edge_mid > 0.7 and centre > 0.7 and ratio < 0.95,
               "CRT mask has a rounded bezel, scanlines and vignette",
               f"corner={corner:.3f}, edge-mid={edge_mid:.3f}, "
               f"centre={centre:.3f}, odd/even={ratio:.3f}")
    # curvature contract: the visible screen edge/corner must stay within 1 %
    # of the frame width/height (no big black crop).  Bloom is disabled for
    # this probe so the geometric black border is measurable instead of being
    # filled by the glow.
    probe = np.full((C.PIX_H, C.PIX_W, 3), 160, dtype=np.uint8)
    saved_bloom = flt.bloom_gain
    flt.bloom_gain = 0.0
    try:
        curved = flt.apply(probe, t).astype(np.float32)
    finally:
        flt.bloom_gain = saved_bloom
    bright = curved.mean(axis=2) > 16.0
    h, w = bright.shape
    band_w, band_h = max(1, w // 20), max(1, h // 20)

    def band_x(band):
        cols = np.where(band.any(axis=0))[0]
        return (int(cols[0]), int(cols[-1])) if cols.size else (w - 1, 0)

    def band_y(band):
        rows = np.where(band.any(axis=1))[0]
        return (int(rows[0]), int(rows[-1])) if rows.size else (h - 1, 0)

    # the four screen corners: horizontal extent from the top/bottom edge bands,
    # vertical extent from the left/right edge bands
    tl_x, tr_x = band_x(bright[:band_h])
    bl_x, br_x = band_x(bright[-band_h:])
    tl_y, bl_y = band_y(bright[:, :band_w])
    tr_y, br_y = band_y(bright[:, -band_w:])
    inset_x = max(tl_x, bl_x, w - 1 - tr_x, w - 1 - br_x)
    inset_y = max(tl_y, tr_y, h - 1 - bl_y, h - 1 - br_y)
    frac_x = inset_x / (w - 1)
    frac_y = inset_y / (h - 1)
    rep.expect(frac_x <= 0.01 and frac_y <= 0.01,
               "CRT curvature stays within 1% of the frame",
               f"corner inset x={frac_x * 100:.2f}%, y={frac_y * 100:.2f}%")


# --------------------------------------------------------------------------
def run_checks(video: Path | None, quick: bool = False) -> int:
    print("\x1b[1m\x1b[36mGA1AHAD TUI PROJECT VERIFICATION\x1b[0m")
    rep = Report()
    check_files(rep)
    check_content(rep)
    check_rendering(rep, sample=1 if quick else 3)
    if video is not None:
        check_video(rep, Path(video), quick=quick)
        if not quick:
            check_frames(rep, Path(video))
    check_acceptance_clip(rep, C.ROOT / "ga1ahad_scene5_kiss.mp4")
    check_crt(rep)
    print()
    if rep.failures:
        print(f"\x1b[31m{rep.failures}/{rep.checks} checks FAILED\x1b[0m")
        return 1
    print(f"\x1b[32mall {rep.checks} checks passed\x1b[0m")
    return 0
