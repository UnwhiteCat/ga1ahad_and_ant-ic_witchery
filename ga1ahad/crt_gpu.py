"""Headless OpenGL CRT compositor. Optional: install the project's gpu extra.

Only the output compositor runs here. Scene drawing, cell rasterisation,
Pillow bloom and timestamp-seeded grain retain their CPU implementations.
The original warp maps/mask are uploaded once; no approximate texture filtering
is used for the warp. Readback stays RGB24 for the existing ffmpeg pipe.
"""

from __future__ import annotations

import ctypes.util
import glob
import os

import numpy as np

from . import config as C
from .crt import (BAND_GAIN, BAND_SIGMA, BAND_SPEED, BLOOM_FLOOR,
                  FLICKER_FAST, FLICKER_SLOW, CRTFilter)


def _library(name: str) -> str:
    """Normal loader first; NixOS stores GLVND outside the default ld path."""
    found = ctypes.util.find_library(name)
    if found:
        return found
    matches = sorted(glob.glob(f"/nix/store/*-libglvnd-*/lib/lib{name}.so.1"))
    if not matches:
        raise RuntimeError(f"lib{name} not found; install an EGL/OpenGL driver")
    return matches[0]


_VERTEX = """#version 430
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

_FRAGMENT = """#version 430
uniform usampler2D source_tex;
uniform usampler2D glow_tex;
uniform isampler2D base_tex;
uniform sampler2D weights_tex;
uniform sampler2D mask_tex;
uniform sampler2D grain_tex;
uniform sampler2D band_tex;
uniform float gain, bloom_gain, bloom_floor, flicker;
uniform int chroma, source_width;
out vec4 colour;

vec3 warped(ivec2 p) {
    int base = texelFetch(base_tex, p, 0).r;
    ivec2 q = ivec2(base % source_width, base / source_width);
    vec4 w = texelFetch(weights_tex, p, 0);
    // Match numpy's float32 operation order, including gain before sampling.
    precise vec3 a = vec3(texelFetch(source_tex, q, 0).rgb) * gain;
    precise vec3 b = vec3(texelFetch(source_tex, q + ivec2(1, 0), 0).rgb) * gain;
    precise vec3 c = vec3(texelFetch(source_tex, q + ivec2(0, 1), 0).rgb) * gain;
    precise vec3 d = vec3(texelFetch(source_tex, q + ivec2(1, 1), 0).rgb) * gain;
    precise vec3 value = ((a * w.x + b * w.y) + c * w.z) + d * w.w;
    vec3 glow = max(vec3(texelFetch(glow_tex, p, 0).rgb) - bloom_floor, vec3(0));
    return value + glow * bloom_gain;
}
void main() {
    ivec2 p = ivec2(gl_FragCoord.xy);
    int width = textureSize(base_tex, 0).x;
    precise vec3 value = warped(p);
    if (chroma > 0) {
        value.r = warped(ivec2(max(0, p.x - chroma), p.y)).r;
        value.b = warped(ivec2(min(width - 1, p.x + chroma), p.y)).b;
    }
    value += texelFetch(grain_tex, p, 0).r;
    value *= texelFetch(mask_tex, p, 0).r;
    value *= texelFetch(band_tex, ivec2(0, p.y), 0).r;
    value *= flicker;
    // numpy truncates to uint8. Explicit flooring avoids GL's round-to-nearest.
    colour = vec4(floor(clamp(value, 0.0, 255.0)) / 255.0, 1.0);
}
"""


class GPUCRTFilter(CRTFilter):
    """One EGL context per worker; call only from its creating thread."""

    def __init__(self, strength: float = C.CRT_STRENGTH,
                 width: int = C.OUT_W, height: int = C.OUT_H) -> None:
        self._resources = []
        self._textures = []
        self.ctx = None
        try:
            import moderngl
        except ImportError as exc:
            raise RuntimeError("install GPU dependencies: UV_CACHE_DIR=.uv-cache uv sync --locked --extra gpu") from exc
        try:
            self.ctx = moderngl.create_standalone_context(
                require=430, backend="egl", libgl=_library("GL"), libegl=_library("EGL"))
            self.device = self.ctx.info["GL_RENDERER"]
            if any(x in self.device.lower() for x in
                   ("llvmpipe", "softpipe", "software", "swrast", "swiftshader")):
                raise RuntimeError(f"EGL selected a software renderer: {self.device}")
            super().__init__(strength, width, height)
            self.program = self._own(self.ctx.program(vertex_shader=_VERTEX,
                                                       fragment_shader=_FRAGMENT))
            self.vao = self._own(self.ctx.vertex_array(self.program, []))
            self.source = self._texture((C.PIX_W, C.PIX_H), 3, "u1")
            self.glow = self._texture((width, height), 3, "u1")
            self._texture((width, height), 1, "i4", self._base)
            weights = np.stack((self._w00, self._w01, self._w10, self._w11), axis=-1)
            self._texture((width, height), 4, "f4", weights)
            self._texture((width, height), 1, "f4", self._static)
            self.noise = self._texture((width, height), 1, "f4")
            self.band = self._texture((1, height), 1, "f4")
            for unit, name in enumerate(("source_tex", "glow_tex", "base_tex", "weights_tex",
                                         "mask_tex", "grain_tex", "band_tex")):
                self.program[name] = unit
            self.program["source_width"] = C.PIX_W
            self.program["bloom_floor"] = BLOOM_FLOOR
            output = self._own(self.ctx.texture((width, height), 3, dtype="f1"))
            self.fbo = self._own(self.ctx.framebuffer(color_attachments=[output]))
            self.ctx.disable(moderngl.BLEND)
            self._pid = os.getpid()
        except Exception:
            self.close()
            raise

    def _own(self, resource):
        self._resources.append(resource)
        return resource

    def _texture(self, size, components, dtype, data=None):
        tex = self._own(self.ctx.texture(size, components, dtype=dtype,
                                        data=None if data is None else data.tobytes(), alignment=1))
        self._textures.append(tex)
        return tex

    def apply(self, frame: np.ndarray, t: float) -> np.ndarray:
        if self.ctx is None or os.getpid() != self._pid:
            raise RuntimeError("GPU CRT context is closed or belongs to another process")
        with self.ctx:
            return self._apply(frame, t)

    def _apply(self, frame: np.ndarray, t: float) -> np.ndarray:
        if self.strength <= 0:
            return super().apply(frame, t)
        if frame.shape != (C.PIX_H, C.PIX_W, 3) or frame.dtype != np.uint8:
            raise ValueError("GPU CRT requires a PIX_H x PIX_W x 3 uint8 frame")
        self.source.write(np.ascontiguousarray(frame).tobytes(), alignment=1)
        self.glow.write(self._glow(frame).tobytes(), alignment=1)
        self.noise.write(self._grain(t).tobytes(), alignment=1)
        pos = ((t * BAND_SPEED) % 1.0) * self.h
        band = 1.0 + BAND_GAIN * self.strength * np.exp(-0.5 * ((self._rows - pos) / BAND_SIGMA) ** 2)
        self.band.write(band.astype(np.float32).tobytes(), alignment=1)
        self.program["gain"] = self.gain
        self.program["bloom_gain"] = self.bloom_gain
        self.program["chroma"] = self.chroma
        self.program["flicker"] = float(1.0 + self.strength * (
            FLICKER_SLOW * np.sin(2.0 * np.pi * 0.7 * t)
            + FLICKER_FAST * np.sin(2.0 * np.pi * 5.3 * t + 1.3)))
        for unit, texture in enumerate(self._textures):
            texture.use(location=unit)
        self.fbo.use()
        self.vao.render(vertices=3)
        # Texture upload and readback both treat row zero as the first row;
        # there is no display surface, so no vertical flip is needed.
        return np.frombuffer(self.fbo.read(components=3, alignment=1), np.uint8).reshape(self.h, self.w, 3)

    def close(self) -> None:
        for resource in reversed(self._resources):
            resource.release()
        self._resources.clear()
        if self.ctx is not None:
            self.ctx.release()
            self.ctx = None
