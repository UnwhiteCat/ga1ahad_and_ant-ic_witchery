"""Offline audio analysis used to drive beat-reactive TUI animation.

Features are computed once from ``ga1ahad_audio.wav`` at 60 fps and cached in
``build/cache/audio_features.npz`` so both the live viewer and the offline
renderer share the exact same rhythm data.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from . import config as C

FEATURE_FPS = 60
N_BANDS = 24


class Audio:
    def __init__(self, fps: int, rms: np.ndarray, bands: np.ndarray,
                 onset: np.ndarray, flux: np.ndarray,
                 duration: float | None = None) -> None:
        self.fps = fps
        self.rms = rms.astype(np.float32)
        self.bands = bands.astype(np.float32)          # (n, N_BANDS)
        self.onset = onset.astype(np.float32)          # (n,)
        self.flux = flux.astype(np.float32)
        self.duration = float(duration) if duration else len(rms) / fps

    # -- low level -------------------------------------------------------
    def _idx(self, t: float) -> tuple[int, int, float]:
        f = max(0.0, t) * self.fps
        i = int(f)
        frac = f - i
        if i >= len(self.rms) - 1:
            return len(self.rms) - 1, len(self.rms) - 1, 0.0
        return i, i + 1, frac

    def energy(self, t: float) -> float:
        i, j, f = self._idx(t)
        return float(self.rms[i] * (1 - f) + self.rms[j] * f)

    def band(self, t: float, i: int) -> float:
        i, j, f = self._idx(t)
        return float(self.bands[i, i] * (1 - f) + self.bands[j, i] * f)

    def spectrum(self, t: float) -> np.ndarray:
        i, j, f = self._idx(t)
        if i == j:
            return self.bands[i]
        return self.bands[i] * (1 - f) + self.bands[j] * f

    def flux_at(self, t: float) -> float:
        i, j, f = self._idx(t)
        return float(self.flux[i] * (1 - f) + self.flux[j] * f)

    def pulse(self, t: float, decay: float = 0.16) -> float:
        """Envelope follower on the onset strength, 0..1."""
        i, _, _ = self._idx(t)
        span = max(1, int(decay * self.fps))
        lo = max(0, i - span)
        seg = self.onset[lo:i + 1]
        if len(seg) == 0:
            return 0.0
        ages = np.arange(len(seg))[::-1] / self.fps
        vals = seg * np.exp(-ages / decay)
        return float(min(1.0, vals.max() * 1.6))

    def bass(self, t: float) -> float:
        return self.band_mean(t, 0.0, 0.18)

    def band_mean(self, t: float, lo_f: float, hi_f: float) -> float:
        """Mean of normalised log-bands inside a relative frequency window."""
        i, j, f = self._idx(t)
        spec = self.bands[i] * (1 - f) + self.bands[j] * f
        a = int(lo_f * N_BANDS)
        b = max(a + 1, int(hi_f * N_BANDS))
        return float(np.clip(spec[a:b].mean(), 0, 1))

    def kick(self, t: float, decay: float = 0.11) -> float:
        return self.pulse(t, decay)


def _log_bands(spec: np.ndarray, n: int) -> np.ndarray:
    n_bins = len(spec)
    edges = np.geomspace(1, n_bins - 1, n + 1)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = int(edges[i])
        b = max(a + 1, int(edges[i + 1]))
        out[i] = spec[a:b].mean()
    return out


def build_analysis(wav_path: Path, out_path: Path | None = None) -> Audio:
    with wave.open(str(wav_path), "rb") as w:
        n_channels = w.getnchannels()
        sr = w.getframerate()
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sw == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:
        raise ValueError(f"unsupported sample width {sw}")
    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)

    hop = int(round(sr / FEATURE_FPS))
    win = 2048
    n = max(1, (len(data) - win) // hop + 1)
    rms = np.zeros(n, dtype=np.float32)
    bands = np.zeros((n, N_BANDS), dtype=np.float32)
    flux = np.zeros(n, dtype=np.float32)
    hann = np.hanning(win).astype(np.float32)
    prev_mag = np.zeros(win // 2 + 1, dtype=np.float32)
    for i in range(n):
        seg = data[i * hop:i * hop + win]
        if len(seg) < win:
            seg = np.pad(seg, (0, win - len(seg)))
        rms[i] = np.sqrt(np.mean(seg * seg) + 1e-12)
        mag = np.abs(np.fft.rfft(seg * hann))
        bands[i] = _log_bands(mag, N_BANDS)
        flux[i] = np.maximum(mag - prev_mag, 0).sum()
        prev_mag = mag
    # normalise (robust 98th percentile)
    def norm(x: np.ndarray) -> np.ndarray:
        p = np.percentile(x, 98) + 1e-9
        return np.clip(x / p, 0, 1.35).astype(np.float32)

    rms = norm(rms)
    flux = norm(flux)
    bands = np.stack([norm(bands[:, i]) for i in range(N_BANDS)], axis=1)
    # onset: local flux increase
    onset = np.zeros_like(flux)
    for i in range(1, len(flux)):
        onset[i] = max(0.0, flux[i] - 0.6 * flux[i - 1])
    onset = np.clip(onset * 1.4, 0, 1.2).astype(np.float32)
    audio = Audio(FEATURE_FPS, rms, bands, onset, flux,
                  duration=len(data) / sr)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(out_path, fps=FEATURE_FPS, rms=rms, bands=bands,
                            onset=onset, flux=flux, duration=len(data) / sr)
    return audio


def load_audio(wav_path: Path | None = None, cache_path: Path | None = None) -> Audio:
    wav_path = wav_path or C.AUDIO_PATH
    cache_path = cache_path or (C.CACHE_DIR / "audio_features.npz")
    if cache_path.exists() and cache_path.stat().st_mtime >= wav_path.stat().st_mtime:
        try:
            z = np.load(cache_path)
            dur = float(z["duration"]) if "duration" in z.files else None
            return Audio(int(z["fps"]), z["rms"], z["bands"], z["onset"], z["flux"],
                         duration=dur)
        except Exception:
            pass
    return build_analysis(wav_path, cache_path)
