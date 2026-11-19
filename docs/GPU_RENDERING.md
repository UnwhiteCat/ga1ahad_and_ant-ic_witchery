# GPU rendering

The GPU backend accelerates the final CRT compositor: inverse barrel sampling,
RGB convergence, bloom addition, grain/mask/band multiplication and quantisation.
Scenes and cell rasterisation still run on the CPU. Pillow bloom and seeded
noise generation are shared with the CPU reference. Frames are read back as
RGB24 and sent to ffmpeg; this is not a zero-copy pipeline.

## Installation and selection

Install the optional packages from the lockfile:

```bash
UV_CACHE_DIR=.uv-cache uv sync --locked --extra gpu
```

The headless backend requires a working EGL driver and OpenGL 4.3. No desktop
window or display server is needed. Mesa software renderers such as llvmpipe
are rejected, so they cannot be reported as GPU acceleration. Context creation
uses [ModernGL](https://moderngl.readthedocs.io/en/stable/reference/moderngl.html)
with the [glcontext EGL backend](https://github.com/moderngl/glcontext#egl).

```bash
./ga1ahad_tui render --backend gpu --workers 8
./ga1ahad_tui png --at 190 --crt --backend gpu --out build/gpu190.png
```

| Option | Behaviour |
| --- | --- |
| `--backend auto` | Render default. Probe a real GPU frame once before starting workers; report the device or the CPU fallback reason. |
| `--backend gpu` | Require hardware. A missing package, device or failed shader aborts before rendering. No mid-render fallback. |
| `--backend cpu` | Use the numpy/Pillow reference; also the default for `png` and `sheet`. |
| `--workers N` | Explicit segment concurrency. Without this flag: up to 4 GPU workers or 8 CPU workers, bounded by CPU count and frame count. |
| `--no-crt` / `--crt-strength 0` / `GA1AHAD_CRT=0` | Keep the original flat raster + ffmpeg scale path. Explicit `--backend gpu` with CRT disabled is an error. |

Every worker owns its EGL context and private segment. Maps, weights and masks
are uploaded once. The GPU uses the CPU reference's precomputed float32 maps,
explicit bilinear samples and operation order. Grain remains a function of the
timestamp. Small floating point differences across devices may change a channel
by one level; the paths are not promised to be byte-identical across backends.

## Optional hardware encoding

The default encoder remains `libx264`, using `--crf` and `--preset` as before.
Linux VAAPI H.264 is independently selectable with `--encoder h264_vaapi`.
It uses constant QP (`--qp`, default 18, range 0–51), not CRF. Equal CRF and QP
numbers do not imply equal quality or bitrate. See the
[ffmpeg VAAPI encoder reference](https://ffmpeg.org/ffmpeg-codecs.html#VAAPI-encoders).

The VAAPI path converts RGB24 to NV12, uploads it to the selected render device
and encodes H.264 High with a 60-frame GOP and no B-frames. A real one-frame
encode is tested before segment workers launch; a listed codec alone is
insufficient. The audio mux and segment order are shared with `libx264`.

This command was exercised on the local AMD GPU:

```bash
LIBVA_DRIVER_NAME=radeonsi ./ga1ahad_tui render --backend gpu --encoder h264_vaapi --start 184.5 --end 190.5 --workers 4 --out build/bench_gpu_vaapi.mp4
```

`--vaapi-device` defaults to `/dev/dri/renderD128`. NixOS drivers are discovered
under `/run/opengl-driver/lib/dri`; explicit `LIBVA_DRIVERS_PATH` and
`LIBVA_DRIVER_NAME` environment settings take precedence. This machine's global
environment selected Intel `iHD` despite the AMD device, so the command above
overrides it with `radeonsi` for that process only.

## Validation and measured results

```bash
./tools/py -m unittest discover -s tests -v
./tools/py tools/check_gpu.py
./ga1ahad_tui check
```

The first command checks backend/encoder policy without hardware. The GPU check
requires real hardware and fails if unavailable. It compares all eight scene
samples and an asymmetric RGB ramp at strengths 0.5, 1 and 2; it also checks
timestamp repeatability after out-of-order calls. Acceptance: maximum channel
error ≤1, mean error <0.001 on the 0–255 scale, correct uint8 dimensions and
byte-identical repetitions within the GPU backend. Results are written to
`build/gpu_validation.json`. The existing 74-check gate remains independent.

Measured 2026-11-17 on Ryzen AI 9 H 365 / Radeon 880M, Mesa 26.1.8, ModernGL
5.13.0, at 1920x1080 / 30 fps:

| Workload | CPU CRT + libx264 | GPU CRT + libx264 | GPU CRT + VAAPI |
| --- | ---: | ---: | ---: |
| 184.5–190.5 s, 180 frames, 4 workers, audio included | 15.6 s | 9.5 s | 8.4 s |

All three clips probe as 180 H.264 frames plus AAC, exactly 6.000 s.
The full 6,574-frame GPU CRT + libx264 release render took 258.6 s with
8 workers; the 414-frame acceptance clip took 27.8 s with 4 workers. Logs:
`build/render_gpu_full.log` and `build/render_gpu_clip.log`. These full-render
results have no same-session full-song CPU baseline.
Both release MP4s carry the CRT output stage + libx264. The preview was
rebuilt from decoded full-video frames; the full verifier passed 74/74,
including original audio length/alignment and CRT signatures
(`build/check_gpu_final.log`).

The compositor benchmark, interleaved after warmup, measured medians of
92.93 ms on CPU and 31.05 ms on GPU (2.99×). This includes CPU bloom/grain,
GPU upload and RGB readback, and excludes scene drawing and encoding.
Short-clip timings include worker startup, concat and mux, but exclude the
parent GPU/VAAPI preflight. They do not predict full-song speedup or establish
VAAPI quality equivalence. Logs: `build/bench_cpu.log`, `build/bench_gpu.log`,
`build/bench_gpu_vaapi.log`, `build/gpu_validation.json` (generated, ignored).

## Troubleshooting

- Missing `moderngl`: reinstall with the `gpu` extra. A plain uv sync may remove optional packages.
- llvmpipe or unavailable EGL: check GPU device access and installed drivers.
  In the restricted agent sandbox `/dev/dri` is hidden; the host render was
  tested outside that sandbox. CPU fallback inside it is expected.
- VAAPI initialisation failure: check the render node and driver environment.
  An Intel `iHD` override on an AMD system must be corrected for that command.
- GPU is slower with many workers: contexts and readbacks share GPU/memory
  bandwidth. Use fewer workers and measure a representative segment.
