"""FFmpeg discovery, raw-frame encoding, parallel segment rendering and muxing."""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from . import config as C

_X264_PARAMS = "keyint=60:min-keyint=60:scenecut=0"


def _glob_ffmpeg() -> str | None:
    pats = [
        "/nix/store/*ffmpeg-headless-*/bin/ffmpeg",
        "/nix/store/*ffmpeg-*-bin/bin/ffmpeg",
        "/nix/store/*ffmpeg-*/bin/ffmpeg",
    ]
    for pat in pats:
        for p in sorted(glob.glob(pat)):
            if os.access(p, os.X_OK):
                return p
    return None


def find_ffmpeg() -> str:
    env = os.environ.get("GA1AHAD_FFMPEG") or os.environ.get("FFMPEG")
    if env and os.access(env, os.X_OK):
        return env
    for name in ("ffmpeg",):
        p = shutil.which(name)
        if p:
            return p
    p = _glob_ffmpeg()
    if p:
        return p
    raise RuntimeError(
        "ffmpeg not found. Install ffmpeg or set GA1AHAD_FFMPEG=/path/to/ffmpeg")


def find_ffprobe() -> str:
    env = os.environ.get("GA1AHAD_FFPROBE")
    if env and os.access(env, os.X_OK):
        return env
    p = shutil.which("ffprobe")
    if p:
        return p
    ff = find_ffmpeg()
    cand = Path(ff).with_name("ffprobe")
    if cand.exists():
        return str(cand)
    raise RuntimeError("ffprobe not found")


# --------------------------------------------------------------------------
# Encoders
# --------------------------------------------------------------------------
class RawVideoEncoder:
    """Pipes raw RGB frames into ffmpeg."""

    def __init__(self, out_path: Path, fps: int = C.FPS, crf: int = 18,
                 preset: str = "medium", container_ts: bool = False,
                 extra_out: list[str] | None = None,
                 in_size: tuple[int, int] | None = None,
                 scale: bool = True, encoder: str = "libx264",
                 vaapi_device: str = "/dev/dri/renderD128", qp: int = 18) -> None:
        self.out_path = Path(out_path)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        in_w, in_h = in_size or (C.PIX_W, C.PIX_H)
        cmd = [
            find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
        ]
        if encoder == "h264_vaapi":
            cmd += ["-vaapi_device", vaapi_device]
        elif encoder != "libx264":
            raise ValueError(f"unsupported encoder: {encoder}")
        cmd += [
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{in_w}x{in_h}", "-r", str(fps), "-i", "-",
        ]
        filters = [f"scale={C.OUT_W}:{C.OUT_H}:flags=lanczos"] if scale else []
        if encoder == "h264_vaapi":
            filters += ["format=nv12", "hwupload"]
        if filters:
            cmd += ["-vf", ",".join(filters)]
        if encoder == "libx264":
            cmd += ["-c:v", encoder, "-preset", preset, "-crf", str(crf),
                    "-pix_fmt", "yuv420p", "-g", "60", "-x264-params", _X264_PARAMS]
        else:
            cmd += ["-c:v", encoder, "-rc_mode", "CQP", "-qp", str(qp),
                    "-g", "60", "-bf", "0", "-profile:v", "high"]
        cmd += ["-movflags", "+faststart"]
        if extra_out:
            cmd += extra_out
        if container_ts:
            cmd += ["-f", "mpegts"]
        cmd += [str(self.out_path)]
        self.cmd = cmd
        env = dict(os.environ)
        if encoder == "h264_vaapi" and Path("/run/opengl-driver/lib/dri").is_dir():
            env.setdefault("LIBVA_DRIVERS_PATH", "/run/opengl-driver/lib/dri")
            vendor = Path("/sys/class/drm") / Path(vaapi_device).name / "device/vendor"
            if vendor.exists() and vendor.read_text().strip() == "0x1002":
                env.setdefault("LIBVA_DRIVER_NAME", "radeonsi")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, env=env)
        self.frames = 0

    def write(self, frame: np.ndarray) -> None:
        self.proc.stdin.write(frame.astype(np.uint8, copy=False).tobytes())
        self.frames += 1

    def close(self) -> None:
        if self.proc.stdin and not self.proc.stdin.closed:
            try:
                self.proc.stdin.close()
            except BrokenPipeError:
                pass
        rc = self.proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg encoder failed (rc={rc}): {' '.join(self.cmd)}")


def _probe_encoder(encoder: str, vaapi_device: str, qp: int) -> None:
    """A listed hardware codec may still lack a working device/driver."""
    if encoder == "libx264":
        return
    if encoder != "h264_vaapi":
        raise ValueError(f"unsupported encoder: {encoder}")
    C.BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="encoder-probe-", dir=C.BUILD_DIR) as tmp:
        enc = RawVideoEncoder(Path(tmp) / "probe.ts", container_ts=True,
                              in_size=(C.OUT_W, C.OUT_H), scale=False,
                              encoder=encoder, vaapi_device=vaapi_device, qp=qp)
        try:
            enc.write(np.zeros((C.OUT_H, C.OUT_W, 3), np.uint8))
        finally:
            enc.close()


# --------------------------------------------------------------------------
# Audio muxing / probing
# --------------------------------------------------------------------------
def mux_audio(video_path: Path, audio_path: Path, out_path: Path,
              start: float = 0.0, duration: float | None = None,
              bitrate: str = "256k") -> None:
    ff = find_ffmpeg()
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_path)]
    if start > 0:
        cmd += ["-ss", f"{start:.6f}"]
    cmd += ["-i", str(audio_path)]
    cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-c:a", "aac", "-b:a", bitrate, "-ar", "32000", "-ac", "1",
            "-movflags", "+faststart"]
    if duration is not None:
        cmd += ["-t", f"{duration:.6f}"]
    elif start > 0:
        cmd += ["-shortest"]
    else:
        cmd += ["-shortest"]
    cmd += [str(out_path)]
    subprocess.run(cmd, check=True)


def concat_segments(segments: list[Path], out_video: Path, list_path: Path) -> None:
    ff = find_ffmpeg()
    list_path.parent.mkdir(parents=True, exist_ok=True)
    with open(list_path, "w", encoding="utf-8") as fh:
        for seg in segments:
            fh.write(f"file '{seg.resolve()}'\n")
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "concat", "-safe", "0", "-i", str(list_path),
           "-c", "copy", "-fflags", "+genpts", "-movflags", "+faststart",
           str(out_video)]
    subprocess.run(cmd, check=True)


def probe(path: Path) -> dict:
    fp = find_ffprobe()
    out = subprocess.run([fp, "-hide_banner", "-v", "error", "-print_format", "json",
                          "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def extract_audio(path: Path, out_wav: Path, mono: bool = True) -> None:
    ff = find_ffmpeg()
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
           "-vn", "-ac", "1" if mono else "2", "-ar", "32000", str(out_wav)]
    subprocess.run(cmd, check=True)


def screenshot(video: Path, t: float, out_png: Path) -> None:
    ff = find_ffmpeg()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}",
           "-i", str(video), "-frames:v", "1", str(out_png)]
    subprocess.run(cmd, check=True)


def write_poster(frame: np.ndarray, path, text: str | None = None) -> None:
    from PIL import Image

    im = Image.fromarray(frame)
    if text:
        from PIL import ImageDraw

        d = ImageDraw.Draw(im)
        d.text((20, 20), text, fill=(255, 255, 255))
    im.save(path)


# --------------------------------------------------------------------------
# Parallel render orchestration
# --------------------------------------------------------------------------
def _segment_worker(start: float, end: float, out_path: Path, fps: int,
                    crf: int, preset: str, crt_strength: float = 0.0,
                    verbose: bool = True, backend: str = "cpu",
                    encoder: str = "libx264", vaapi_device: str = "/dev/dri/renderD128",
                    qp: int = 18) -> Path:
    """Render one contiguous segment (subprocess entry point)."""
    from .frame import get_renderer

    renderer = get_renderer()
    crt = max(0.0, float(crt_strength))
    # The CRT stage resamples the internal raster to 1920x1080 itself, so the
    # worker feeds output-sized raw frames and ffmpeg only encodes.
    out_size = (C.OUT_W, C.OUT_H) if crt > 0.0 else None
    enc = RawVideoEncoder(out_path, fps=fps, crf=crf, preset=preset,
                          container_ts=True, in_size=out_size,
                          scale=out_size is None, encoder=encoder,
                          vaapi_device=vaapi_device, qp=qp)
    f0 = int(round(start * fps))
    f1 = int(round(end * fps))
    total = max(1, f1 - f0)
    last = time.time()
    try:
        for frame in range(f0, f1):
            if crt > 0.0:
                img = renderer.output_frame_at(frame / fps, frame, crt=crt, backend=backend)
            else:
                img = renderer.frame_at(frame / fps, frame)
            enc.write(img)
            done = frame - f0 + 1
            now = time.time()
            if verbose and now - last >= 1.0:
                last = now
                print(f"PROGRESS {done} {total}", flush=True)
    finally:
        try:
            enc.close()
        finally:
            for flt in renderer._crt_filters.values():
                flt.close()
            renderer._crt_filters.clear()
    print(f"PROGRESS {total} {total}", flush=True)
    return out_path


def _reader(stream, idx: int, state: dict, lock, total_frames: int,
            verbose: bool) -> None:
    for line in iter(stream.readline, ""):
        line = line.strip()
        if line.startswith("PROGRESS "):
            parts = line.split()
            try:
                done, tot = int(parts[1]), int(parts[2])
            except Exception:
                continue
            with lock:
                state[idx] = done
                agg = sum(state.values())
            if verbose:
                pct = min(100.0, agg / max(1, total_frames) * 100.0)
                with lock:
                    import sys as _sys
                    _sys.stderr.write(f"\r[render] {pct:5.1f}%  {agg}/{total_frames} frames   ")
                    _sys.stderr.flush()
        elif line:
            print(f"[seg{idx:02d}] {line}", flush=True)
    stream.close()


def render_video(out_path: Path, start: float = 0.0, end: float | None = None,
                 workers: int | None = None, fps: int = C.FPS, crf: int = 18,
                 preset: str = "medium", with_audio: bool = True,
                 crt_strength: float = C.CRT_STRENGTH,
                 verbose: bool = True, backend: str = "auto",
                 encoder: str = "libx264", vaapi_device: str = "/dev/dri/renderD128",
                 qp: int = 18) -> Path:
    """Render [start, end) to an mp4 using N independent worker processes.

    crt_strength (default 1.0) runs the output CRT stage in every worker;
    0 renders the flat raster look.
    """
    import threading
    from .crt import resolve_backend

    end = C.DURATION if end is None else end
    if fps <= 0 or not 0 <= start < end <= C.DURATION:
        raise ValueError("render requires fps > 0 and 0 <= start < end <= song duration")
    f0 = int(round(start * fps))
    f1 = int(round(end * fps))
    total = max(0, f1 - f0)
    if total <= 0:
        raise ValueError("empty frame range")
    _probe_encoder(encoder, vaapi_device, qp)
    crt_arg = max(0.0, float(crt_strength))
    backend = resolve_backend(backend, crt_arg, verbose=verbose)
    if workers is None:
        workers = 4 if backend == "gpu" else 8
    workers = max(1, min(workers, total, os.cpu_count() or 1))
    if verbose:
        print(f"[render] CRT backend: {backend}; workers: {workers}; encoder: {encoder}", file=sys.stderr)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seg_root = C.BUILD_DIR / "segments"
    seg_root.mkdir(parents=True, exist_ok=True)
    # Private per-run directory: a full render and a quick segment preview may
    # run at the same time, and they must never share the same .ts paths.
    seg_dir = Path(tempfile.mkdtemp(prefix=f"{out_path.stem}-", dir=str(seg_root)))

    t_start = time.time()
    chunk = (total + workers - 1) // workers
    chunks = []
    for i in range(workers):
        a = f0 + i * chunk
        b = min(f1, a + chunk)
        if a >= b:
            break
        chunks.append((i, a, b))
    # Each worker is a fresh python process (sandbox forbids POSIX semaphores,
    # so subprocesses with per-segment .ts files are the robust approach).
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", str(C.ROOT))
    procs = []
    segments: list[Path] = []
    for i, a, b in chunks:
        seg = seg_dir / f"seg_{i:03d}.ts"
        segments.append(seg)
        cmd = [sys.executable, "-m", "ga1ahad", "_segment",
               "--start", f"{a / fps:.6f}", "--end", f"{b / fps:.6f}",
               "--out", str(seg), "--fps", str(fps), "--crf", str(crf),
               "--preset", preset,
               "--crt-strength", f"{crt_arg:.6f}", "--backend", backend,
               "--encoder", encoder, "--vaapi-device", vaapi_device, "--qp", str(qp)]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, env=env, cwd=str(C.ROOT))
        procs.append(p)
    state = {i: 0 for i, _, _ in chunks}
    lock = threading.Lock()
    threads = []
    for idx, p in enumerate(procs):
        t = threading.Thread(target=_reader, args=(p.stdout, idx, state, lock,
                                                   total, verbose), daemon=True)
        t.start()
        threads.append(t)
    fail = False
    try:
        for p in procs:
            if p.wait() != 0:
                fail = True
        for t in threads:
            t.join(timeout=2)
    except BaseException:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            p.wait()
        shutil.rmtree(seg_dir, ignore_errors=True)
        raise
    if verbose:
        sys.stderr.write("\r" + " " * 60 + "\r")
        sys.stderr.flush()
    if fail:
        shutil.rmtree(seg_dir, ignore_errors=True)
        raise RuntimeError("one or more render workers failed (see [segXX] output)")
    try:
        if verbose:
            if crt_arg > 0.0:
                sys.stderr.write(f"[render] CRT output stage: strength {crt_arg:.2f}\n")
            sys.stderr.write(f"[render] frames rendered in {time.time() - t_start:.1f}s, "
                             f"concatenating {len(segments)} segment(s) ...\n")
        video_ts = seg_dir / "video.ts"
        if len(segments) > 1:
            concat_segments(segments, video_ts, seg_dir / "concat.txt")
        else:
            video_ts = segments[0]
        if with_audio:
            if verbose:
                sys.stderr.write("[mux] adding original audio track ...\n")
            final_dur = (f1 - f0) / fps
            full_song = start <= 1e-9 and abs(end - C.DURATION) < 1e-6
            # full render: the container ends exactly with the original song
            # even though the last video frame lands ~17 ms earlier.  previews
            # keep the preview length while seeking the audio to its start.
            mux_dur = C.DURATION if full_song else min(final_dur, C.DURATION - start)
            mux_audio(video_ts, C.AUDIO_PATH, out_path, start=start, duration=mux_dur)
        else:
            ff = find_ffmpeg()
            subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(video_ts), "-c", "copy", "-movflags",
                            "+faststart", str(out_path)], check=True)
    finally:
        shutil.rmtree(seg_dir, ignore_errors=True)
    if verbose:
        sys.stderr.write(f"[render] done in {time.time() - t_start:.1f}s -> {out_path}\n")
    return out_path


def _eta(t_start: float, done: int, total: int) -> str:
    if done <= 0:
        return "--"
    el = time.time() - t_start
    remain = el / done * (total - done)
    return f"{remain:5.1f}s"
_worker_cursor: dict = {}


def _eta(t_start: float, done: int, total: int) -> str:
    if done <= 0:
        return "--"
    el = time.time() - t_start
    remain = el / done * (total - done)
    return f"{remain:5.1f}s"
