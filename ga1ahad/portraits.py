"""Generated portrait keyframes for the operators and the GPT-4 entity."""

from functools import lru_cache

from . import config as C
from .assets import _crop_frac, halfblock, keyframe
from .canvas import Sprite


@lru_cache(maxsize=None)
def sam_bust(rows: int = 26, bg: int = C.INK) -> Sprite:
    return halfblock(keyframe("sam"), rows, bg=bg, bright=1.16)


@lru_cache(maxsize=None)
def dahlia_bust(rows: int = 26, bg: int = C.INK, manic: bool = False) -> Sprite:
    image = keyframe("dahlia-smile" if manic else "dahlia")
    return halfblock(image, rows, bg=bg, bright=1.14)


@lru_cache(maxsize=None)
def dahlia_face(rows: int = 10, bg: int = C.INK, manic: bool = False) -> Sprite:
    image = keyframe("dahlia-smile" if manic else "dahlia")
    crop = _crop_frac(image, 0.16, 0.00, 0.84, 0.66)
    return halfblock(crop, rows, bg=bg, bright=1.18)


@lru_cache(maxsize=None)
def gpt4_entity(rows: int = 18, bg: int = C.INK) -> Sprite:
    return halfblock(keyframe("gpt-4"), rows, bg=bg)
