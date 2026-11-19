"""Scene registry.  Each chapter lives in its own module so authors can work
independently; missing modules fall back to a diagnostic panel at render time.
"""

from __future__ import annotations

import importlib
import traceback

MODULES: dict[str, tuple[str, str]] = {
    "prologue": (".prologue", "Prologue"),
    "s1": (".s1", "Scene1"),
    "s2": (".s2", "Scene2"),
    "s3": (".s3", "Scene3"),
    "s35": (".s35", "Scene35"),
    "s4": (".s4", "Scene4"),
    "s5": (".s5", "Scene5"),
    "s6": (".s6", "Scene6"),
}


def load_scenes(assets, audio, timeline, content) -> dict:
    scenes: dict = {}
    for key, (mod_name, cls_name) in MODULES.items():
        try:
            mod = importlib.import_module(mod_name, __package__)
        except ModuleNotFoundError as exc:
            if exc.name and mod_name.lstrip(".") in exc.name:
                continue
            traceback.print_exc()
            continue
        except Exception:
            traceback.print_exc()
            continue
        try:
            klass = getattr(mod, cls_name)
            scenes[key] = klass(assets, audio, timeline, content)
        except Exception:
            traceback.print_exc()
    return scenes
