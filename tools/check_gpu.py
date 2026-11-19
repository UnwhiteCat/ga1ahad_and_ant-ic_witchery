"""Compare the real GPU compositor to the CPU reference and write a timing report.

Run with ./tools/py tools/check_gpu.py. Missing hardware is a failure, not a skip.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time

import numpy as np

from ga1ahad import config as C
from ga1ahad.crt import CRTFilter
from ga1ahad.crt_gpu import GPUCRTFilter
from ga1ahad.frame import get_renderer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("build/gpu_validation.json"))
    args = parser.parse_args()
    renderer = get_renderer()
    times = [0.0, 17.6, 45.0, 75.0, 100.0, 160.0, 190.0, 215.0]
    frames = [renderer.frame_at(t) for t in times]
    # Asymmetric RGB ramps catch channel, row-order and edge-clamping errors.
    yy, xx = np.indices((C.PIX_H, C.PIX_W))
    ramp = np.stack((xx % 256, yy % 256, (xx + 3 * yy) % 256), axis=-1).astype(np.uint8)
    rows = []
    device = None
    for strength in (0.5, 1.0, 2.0):
        cpu, gpu = CRTFilter(strength), GPUCRTFilter(strength)
        device = gpu.device
        try:
            for t, frame in [*zip(times, frames), (3.141, ramp)]:
                a, b = cpu.apply(frame, t), gpu.apply(frame, t)
                diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
                assert b.shape == (C.OUT_H, C.OUT_W, 3) and b.dtype == np.uint8
                assert diff.max() <= 1 and diff.mean() < 0.001, (strength, t, diff.max(), diff.mean())
                # Applying another timestamp must not change an earlier frame.
                gpu.apply(frame, t + 1)
                assert np.array_equal(b, gpu.apply(frame, t))
                rows.append(dict(strength=strength, t=t, max_error=int(diff.max()),
                                 mean_error=float(diff.mean())))
            if strength == 1.0:
                timings = {"cpu": [], "gpu": []}
                # Interleave warmed runs; timings include upload and RGB readback.
                for _ in range(2):
                    for t, frame in zip(times, frames):
                        for name, flt in (("cpu", cpu), ("gpu", gpu)):
                            begin = time.perf_counter()
                            flt.apply(frame, t)
                            timings[name].append(time.perf_counter() - begin)
        finally:
            gpu.close()
    medians = {k: statistics.median(v) for k, v in timings.items()}
    report = dict(device=device, comparisons=rows, deterministic=True,
                  median_seconds=medians, compositor_speedup=medians["cpu"] / medians["gpu"],
                  timing_scope="CRT only, includes CPU bloom/grain and GPU transfer; excludes scenes and encoding")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "comparisons"}, indent=2))
    print(f"27 CPU/GPU comparisons passed -> {args.out}")


if __name__ == "__main__":
    main()
