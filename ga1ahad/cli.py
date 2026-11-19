"""Command line interface for the Ga1ahad TUI video project."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import config as C
from .content import LOCALE_ENV, ContentError, get_content


def _parse_at(values: list[str]) -> list[float]:
    out: list[float] = []
    for v in values:
        for part in v.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                m, s = part.split(":", 1)
                out.append(int(m) * 60 + float(s))
            else:
                out.append(float(part))
    return out


def _ensure_dirs() -> None:
    C.BUILD_DIR.mkdir(parents=True, exist_ok=True)
    C.CACHE_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_info(args) -> int:
    from .crt import resolve_strength
    from .frame import get_audio, get_renderer, get_specs, get_timeline
    from .encode import find_ffmpeg, find_ffprobe

    _ensure_dirs()
    tl = get_timeline()
    print("\x1b[1mGA1AHAD and Scientific Witchery \u00b7 TUI VIDEO ENGINE\x1b[0m")
    print(f"  canvas        : {C.W} x {C.H} cells  (truecolor cell grid)")
    print(f"  video         : {C.OUT_W}x{C.OUT_H} @ {C.FPS}fps  (internal {C.PIX_W}x{C.PIX_H})")
    print(f"  crt           : strength {resolve_strength(None, None, default=C.CRT_STRENGTH):.2f} "
          f"on the MP4 render path  (--no-crt / GA1AHAD_CRT=0 disables)")
    print(f"  duration      : {C.DURATION:.6f}s ({C.DURATION_DISPLAY})  frames={C.N_FRAMES}")
    print(f"  audio         : {C.AUDIO_PATH.name}  {get_audio().duration:.6f}s")
    print(f"  vtt           : {C.VTT_PATH.name}  cues={len(tl.lyrics)}")
    content = get_content()
    print(f"  content       : locale={content.locale}  terms={len(content.terms)}  "
          f"scenes={content.scene_keys()}")
    print(f"  scenes        : " + ", ".join(f"{s.key}({s.start:.3f}-{s.end:.3f})" for s in get_specs()))
    try:
        print(f"  ffmpeg        : {find_ffmpeg()}")
        print(f"  ffprobe       : {find_ffprobe()}")
    except Exception as exc:
        print(f"  ffmpeg        : MISSING ({exc})")
    r = get_renderer()
    print(f"  scene modules : {sorted(r.scenes)}")
    print(f"  glyphs        : {r.glyphs.count} masks")
    mp4 = C.OUT_MP4
    if mp4.exists():
        print(f"  mp4           : {mp4} ({mp4.stat().st_size / 1e6:.1f} MB)")
    return 0


def cmd_png(args) -> int:
    _ensure_dirs()
    from .crt import resolve_backend, resolve_strength
    from .frame import get_renderer

    crt = resolve_strength(args.crt, args.crt_strength, default=0.0,
                           use_env=False)
    backend = resolve_backend(args.backend, crt)
    if crt > 0 and args.raw:
        print("note: --crt renders at 1920x1080; --raw is ignored", file=sys.stderr)
    times = _parse_at(args.at)
    if not times:
        times = [0.0]
    renderer = get_renderer()
    out = Path(args.out)
    if len(times) > 1 and out.suffix.lower() == ".png":
        out = out.with_suffix("")
        out.mkdir(parents=True, exist_ok=True)
    for t in times:
        t = min(max(t, 0.0), C.DURATION - 1e-3)
        if len(times) > 1 or out.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            path = out / f"frame_{t:08.3f}.png".replace(":", "_")
        else:
            path = out
            path.parent.mkdir(parents=True, exist_ok=True)
        renderer.png_at(t, path, scale=not args.raw, crt=crt, backend=backend)
        print(f"wrote {path}  t={t:.3f}" + ("  (crt)" if crt > 0 else ""))
    return 0


def cmd_sheet(args) -> int:
    _ensure_dirs()
    from .crt import resolve_backend, resolve_strength
    from .frame import get_renderer
    from PIL import Image

    crt = resolve_strength(args.crt, args.crt_strength, default=0.0,
                           use_env=False)
    backend = resolve_backend(args.backend, crt)
    times = _parse_at(args.at) if args.at else []
    if not times:
        from .timeline import SCENE_SPECS
        times = [(s.start + s.end) / 2 for s in SCENE_SPECS]
    cols = args.cols
    rows = (len(times) + cols - 1) // cols
    tw, th = args.tile_w, int(args.tile_w * 9 / 16)
    sheet = Image.new("RGB", (tw * cols, th * rows), (0, 0, 0))
    renderer = get_renderer()
    for i, t in enumerate(times):
        t = min(max(t, 0.0), C.DURATION - 1e-3)
        if crt > 0:
            frame = renderer.output_frame_at(t, crt=crt, backend=backend)
        else:
            frame = renderer.frame_at(t)
        im = Image.fromarray(frame).resize((tw, th), Image.LANCZOS)
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"wrote {out} ({len(times)} tiles)")
    return 0


def cmd_render(args) -> int:
    _ensure_dirs()
    from .crt import resolve_strength
    from .encode import render_video

    start = args.start or 0.0
    end = args.end if args.end is not None else C.DURATION
    out = Path(args.out)
    crt = resolve_strength(args.crt, args.crt_strength, default=C.CRT_STRENGTH)
    render_video(out, start=start, end=end, workers=args.workers, fps=args.fps,
                 crf=args.crf, preset=args.preset, with_audio=not args.no_audio,
                 crt_strength=crt, backend=args.backend, encoder=args.encoder,
                 vaapi_device=args.vaapi_device, qp=args.qp)
    return 0


def cmd_live(args) -> int:
    _ensure_dirs()
    from .live import run_live

    return run_live(start=args.start or 0.0, mute=args.mute,
                    fps_cap=args.fps_cap, max_frames=args.max_frames,
                    force=args.force)


def cmd_segment(args) -> int:
    """Internal worker: render one frame range to a .ts segment (no audio)."""
    from .encode import _segment_worker

    _segment_worker(args.start, args.end, Path(args.out), args.fps, args.crf,
                    args.preset, crt_strength=args.crt_strength, backend=args.backend,
                    encoder=args.encoder, vaapi_device=args.vaapi_device, qp=args.qp)
    return 0


def cmd_audit_text(args) -> int:
    from .audit import audit_text, format_stats

    violations, st = audit_text(stats=args.stats)
    if args.stats:
        print(format_stats(st))
        print()
    if violations:
        for v in violations:
            print(v)
        print(f"\n\x1b[31m{len(violations)} content violation(s)\x1b[0m")
        print("Move the text into content/<locale>/... or use {term_key} placeholders.")
        return 1
    print(f"\x1b[32mcontent audit clean\x1b[0m  "
          f"({st.code_files} files, {st.string_constants} strings, "
          f"{st.narrative_literals} long narrative literals)")
    return 0


def cmd_content(args) -> int:
    from .audit import validate_content
    from .timeline import SCENE_SPECS

    content = get_content(args.locale)
    print(f"locale      : {content.locale}  (available: {', '.join(content.available_locales())})")
    print(f"terms       : {len(content.terms)} glossary entries")
    print(f"scenes      : {', '.join(content.scene_keys())}")
    for spec in SCENE_SPECS:
        try:
            title = content.scene_title(spec.key)
            org = content.scene_org(spec.key)
        except ContentError as exc:
            print(f"  [{spec.number:>3s}] {spec.key:9s} MISSING: {exc}")
            continue
        print(f"  [{spec.number:>3s}] {spec.key:9s} {title}   \u00b7  {org}")
    problems = validate_content(args.locale)
    if problems:
        print("\n\x1b[31mcontent validation failed:\x1b[0m")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\n\x1b[32mcontent validation passed\x1b[0m")
    return 0


def cmd_check(args) -> int:
    _ensure_dirs()
    from .verify import run_checks

    return run_checks(Path(args.video) if args.video else None, quick=args.quick)


def cmd_dump(args) -> int:
    """Dump every cue's start/mid frame to a folder for manual sync review."""
    _ensure_dirs()
    from .frame import get_renderer
    from .timeline import load_timeline

    tl = load_timeline()
    renderer = get_renderer()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for ly in tl.lyrics:
        if ly.instrumental:
            continue
        if args.only and args.only not in ly.text:
            continue
        for frac, tag in ((0.02, "a"), (0.5, "b"), (0.95, "c")):
            t = ly.start + ly.duration * frac
            renderer.png_at(t, out / f"cue{ly.index:02d}{tag}.png")
            n += 1
            if args.limit and n >= args.limit:
                break
        if args.limit and n >= args.limit:
            break
    print(f"wrote {n} frames to {out}")
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ga1ahad_tui",
        description="Ga1ahad and Scientific Witchery -- 200x56 truecolor TUI video engine")

    def add_crt_args(parser, default: str, env_note: str) -> None:
        parser.add_argument("--crt", dest="crt", action=argparse.BooleanOptionalAction,
                            default=None,
                            help=f"CRT output stage (default: {default}; {env_note})")
        parser.add_argument("--crt-strength", type=float, default=None, metavar="S",
                            help="CRT strength 0..2, 0 disables (default: 1.0 for render, 0 for stills)")
        parser.add_argument("--backend", choices=("auto", "cpu", "gpu"),
                            default="auto" if default == "on" else "cpu",
                            help="CRT compositor: auto probes hardware and reports CPU fallback; gpu requires hardware")

    def add_encoder_args(parser) -> None:
        parser.add_argument("--encoder", choices=("libx264", "h264_vaapi"), default="libx264",
                            help="H.264 encoder (VAAPI uses hardware; default: libx264)")
        parser.add_argument("--vaapi-device", default="/dev/dri/renderD128")
        parser.add_argument("--qp", type=int, choices=range(0, 52), default=18, metavar="0..51",
                            help="VAAPI constant QP; independent of libx264 --crf (default: 18)")
    p.add_argument("--version", action="version", version="ga1ahad_tui 1.0")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--locale", default=None,
                        help="content locale under content/ (default: en or $GA1AHAD_CONTENT_LOCALE)")
    sub = p.add_subparsers(dest="cmd")

    info = sub.add_parser("info", parents=[common], help="show project + environment info")
    info.set_defaults(func=cmd_info)

    png = sub.add_parser("png", parents=[common], help="render still frames to PNG")
    png.add_argument("--at", nargs="+", default=["0"], help="time(s) in seconds or mm:ss")
    png.add_argument("--out", default="build/frame.png")
    png.add_argument("--raw", action="store_true", help="keep internal 2000x1120 size")
    add_crt_args(png, "off", "GA1AHAD_CRT applies to render only")
    png.set_defaults(func=cmd_png)

    sheet = sub.add_parser("sheet", parents=[common], help="contact sheet of scene midpoints")
    sheet.add_argument("--at", nargs="*", default=None)
    sheet.add_argument("--out", default="build/contact_sheet.png")
    sheet.add_argument("--cols", type=int, default=4)
    sheet.add_argument("--tile-w", type=int, default=480)
    add_crt_args(sheet, "off", "GA1AHAD_CRT applies to render only")
    sheet.set_defaults(func=cmd_sheet)

    dump = sub.add_parser("dump", parents=[common], help="dump frames around every VTT cue (sync review)")
    dump.add_argument("--out", default="build/cues")
    dump.add_argument("--limit", type=int, default=0)
    dump.add_argument("--only", default=None)
    dump.set_defaults(func=cmd_dump)

    render = sub.add_parser("render", parents=[common], help="render the full 16:9 MP4 with audio")
    render.add_argument("--out", default=str(C.OUT_MP4))
    render.add_argument("--start", type=float, default=0.0)
    render.add_argument("--end", type=float, default=None)
    render.add_argument("--workers", type=int, default=None,
                        help="parallel segments (default: up to 4 on GPU, 8 on CPU)")
    render.add_argument("--fps", type=int, default=C.FPS)
    render.add_argument("--crf", type=int, default=18)
    render.add_argument("--preset", default="medium")
    render.add_argument("--no-audio", action="store_true")
    add_crt_args(render, "on", "GA1AHAD_CRT sets the default")
    add_encoder_args(render)
    render.set_defaults(func=cmd_render)

    live = sub.add_parser("live", parents=[common], help="play the animation live in a 200x56 truecolor terminal")
    live.add_argument("--from", dest="start", type=float, default=0.0)
    live.add_argument("--mute", action="store_true")
    live.add_argument("--fps-cap", type=float, default=30.0)
    live.add_argument("--max-frames", type=int, default=None)
    live.add_argument("--force", action="store_true",
                      help="render ANSI even if stdout is not a TTY (automation)")
    live.set_defaults(func=cmd_live)

    seg = sub.add_parser("_segment")
    seg.add_argument("--start", type=float, required=True)
    seg.add_argument("--end", type=float, required=True)
    seg.add_argument("--out", required=True)
    seg.add_argument("--fps", type=int, default=C.FPS)
    seg.add_argument("--crf", type=int, default=18)
    seg.add_argument("--preset", default="medium")
    seg.add_argument("--crt-strength", type=float, default=0.0)
    seg.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
    add_encoder_args(seg)
    seg.set_defaults(func=cmd_segment)

    audit = sub.add_parser("audit-text", parents=[common],
                           help="lint scene/UI sources for hard-coded proper nouns")
    audit.add_argument("--stats", action="store_true", help="print source string statistics")
    audit.set_defaults(func=cmd_audit_text)

    content_cmd = sub.add_parser("content", parents=[common],
                                 help="inspect / validate the central content layer")
    content_cmd.set_defaults(func=cmd_content)

    check = sub.add_parser("check", parents=[common], help="verify assets, lyric sync, audio and MP4")
    check.add_argument("--video", default=str(C.OUT_MP4))
    check.add_argument("--quick", action="store_true")
    check.set_defaults(func=cmd_check)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not getattr(args, "cmd", None):
        # default: live playback
        args = parser.parse_args(["live"])
    locale = getattr(args, "locale", None)
    if locale:
        os.environ[LOCALE_ENV] = locale
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
