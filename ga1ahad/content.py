"""Central content layer: glossary terms, UI strings and per-scene screenplay.

Everything that names a character, company, product, model or story beat lives
under :file:`content/<locale>/` as TOML, never inside scene code.  Scene code
receives three handles through the context:

``ctx.terms``   -- glossary (``ctx.terms.claude_code`` -> ``"claude code"``)
``ctx.script``  -- this scene's screenplay strings (``ctx.script.s2_2.dahlia``)
``ctx.content`` -- the whole :class:`Content` object (locale, ui, helpers)

Strings may reference glossary terms with ``{term_key}`` and are expanded on
load (strict: an unknown or misspelled term raises :class:`ContentError`, which
is how typos in the screenplay are caught before rendering).

Locales are directory overlays: ``content/en`` is the canonical base and
``content/<locale>`` overrides any subset of files; missing keys fall back to
English.  Non-Latin scripts would additionally need double-width glyph support
in the renderer, which is documented separately.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

from . import config as C

DEFAULT_LOCALE = "en"
LOCALE_ENV = "GA1AHAD_CONTENT_LOCALE"

_TERM_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")
# Sentinels for literal braces: {{ -> { and }} -> } (per docs/CONTENT.md).
_ESCAPE_L = "\x00"
_ESCAPE_R = "\x01"


class ContentError(RuntimeError):
    """Raised for malformed content, unknown keys, unknown terms or bad locales."""


# --------------------------------------------------------------------------
# TOML helpers
# --------------------------------------------------------------------------
def _read_toml(path: Path) -> dict:
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        raise ContentError(f"content file missing: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ContentError(f"invalid TOML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContentError(f"{path}: expected a TOML table")
    return data


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _load_dir_tree(root: Path) -> dict:
    """Load terms.toml, terms.d/*.toml, ui.toml, scenes/*.toml from a locale dir."""
    raw: dict = {"terms": {}, "ui": {}, "scenes": {}}
    terms = _read_toml(root / "terms.toml") if (root / "terms.toml").exists() else {}
    terms_table = terms.get("terms", terms)
    if not isinstance(terms_table, dict):
        raise ContentError(f"{root/'terms.toml'}: [terms] must be a table")
    raw["terms"].update(terms_table)
    # per-scene glossary fragments (each fragment is a flat table of term = value)
    for frag in sorted((root / "terms.d").glob("*.toml")) if (root / "terms.d").is_dir() else []:
        data = _read_toml(frag)
        table = data.get("terms", data)
        if not isinstance(table, dict):
            raise ContentError(f"{frag}: expected a flat term table")
        for key, value in table.items():
            if key in raw["terms"] and raw["terms"][key] != value:
                raise ContentError(
                    f"duplicate term '{key}' in {frag} (already defined differently)")
            raw["terms"][key] = value
    ui_path = root / "ui.toml"
    if ui_path.exists():
        raw["ui"] = _read_toml(ui_path)
    for scene_file in sorted((root / "scenes").glob("*.toml")) if (root / "scenes").is_dir() else []:
        raw["scenes"][scene_file.stem] = _read_toml(scene_file)
    audit_path = root / "audit.toml"
    if audit_path.exists():
        raw["audit"] = _read_toml(audit_path)
    return raw


# --------------------------------------------------------------------------
# Glossary
# --------------------------------------------------------------------------
class Terms:
    """Attribute-accessible glossary with recursive ``{term}`` expansion."""

    def __init__(self, raw: dict[str, str], locale: str = DEFAULT_LOCALE) -> None:
        self.locale = locale
        self._raw: dict[str, str] = {}
        for key, value in raw.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise ContentError(
                    f"terms.{key}: term keys must be lower_snake_case")
            if not isinstance(value, str):
                raise ContentError(f"terms.{key}: expected a string, got {type(value).__name__}")
            self._raw[key] = value
        self._cache: dict[str, str] = {}
        self._resolving: list[str] = []

    # -- resolution ------------------------------------------------------
    def _resolve(self, key: str) -> str:
        if key in self._cache:
            return self._cache[key]
        if key not in self._raw:
            hint = self._suggest(key)
            raise ContentError(f"unknown content term '{{{key}}}'{hint}")
        if key in self._resolving:
            raise ContentError(f"circular term reference: {' -> '.join(self._resolving + [key])}")
        self._resolving.append(key)
        try:
            value = self._expand_terms(self._raw[key], f"terms.{key}")
        finally:
            self._resolving.pop()
        self._cache[key] = value
        return value

    def _suggest(self, key: str) -> str:
        close = [k for k in self._raw if k.startswith(key[:3]) or key.startswith(k[:3])]
        return f" (did you mean: {', '.join(close[:5])})" if close else ""

    def _expand_terms(self, text: str, where: str) -> str:
        text = text.replace("{{", _ESCAPE_L).replace("}}", _ESCAPE_R)

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in self._raw:
                raise ContentError(f"{where}: unknown term '{{{key}}}'")
            return self._resolve(key)

        out = _TERM_RE.sub(repl, text)
        return out.replace(_ESCAPE_L, "{").replace(_ESCAPE_R, "}")

    # -- access ----------------------------------------------------------
    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._resolve(name)

    def __getitem__(self, key: str) -> str:
        return self._resolve(key)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self._raw

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._resolve(key) if key in self._raw else default

    def keys(self):
        return self._raw.keys()

    def items(self):
        return ((k, self._resolve(k)) for k in self._raw)

    def __len__(self) -> int:
        return len(self._raw)

    def __repr__(self) -> str:
        return f"Terms(locale={self.locale!r}, n={len(self._raw)})"


# --------------------------------------------------------------------------
# Content tree
# --------------------------------------------------------------------------
class Box:
    """Read-only dict wrapper: attribute access, strict missing-key errors."""

    __slots__ = ("_data", "_path", "_expand")

    def __init__(self, data: dict, path: str, expand=None) -> None:
        object.__setattr__(self, "_data", {k: _wrap(v, f"{path}.{k}", expand) for k, v in data.items()})
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "_expand", expand)

    def __getattr__(self, name: str):
        data = object.__getattribute__(self, "_data")
        if name in data:
            return data[name]
        path = object.__getattribute__(self, "_path")
        near = [k for k in data if k.startswith(name[:3])]
        hint = f" (available: {', '.join(sorted(data)[:12])}{'...' if len(data) > 12 else ''})" if data else ""
        raise ContentError(f"missing content key '{path}.{name}'{hint}")

    def __getitem__(self, name: str):
        data = object.__getattribute__(self, "_data")
        if name not in data:
            raise ContentError(f"missing content key '{object.__getattribute__(self, '_path')}.{name}'")
        return data[name]

    def get(self, name: str, default=None):
        return object.__getattribute__(self, "_data").get(name, default)

    def __contains__(self, name: object) -> bool:
        return name in object.__getattribute__(self, "_data")

    def keys(self):
        return object.__getattribute__(self, "_data").keys()

    def items(self):
        return object.__getattribute__(self, "_data").items()

    def to_dict(self) -> dict:
        return {k: _unwrap(v) for k, v in object.__getattribute__(self, "_data").items()}

    def __repr__(self) -> str:
        return f"Box({object.__getattribute__(self, '_path')!r}, keys={list(object.__getattribute__(self, '_data'))[:8]})"


def _unwrap(value):
    if isinstance(value, Box):
        return value.to_dict()
    if isinstance(value, list):
        return [_unwrap(v) for v in value]
    return value


def _wrap(value, path: str, expand=None):
    if isinstance(value, dict):
        return Box(value, path, expand)
    if isinstance(value, list):
        return [_wrap(v, f"{path}[{i}]", expand) for i, v in enumerate(value)]
    if isinstance(value, str) and expand is not None:
        return expand(value, path)
    return value


# --------------------------------------------------------------------------
# Content
# --------------------------------------------------------------------------
class Content:
    def __init__(self, locale: str | None = None, root: Path | None = None) -> None:
        self.root = Path(root) if root else C.CONTENT_ROOT
        self.locale = (locale or os.environ.get(LOCALE_ENV) or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
        base_dir = self.root / DEFAULT_LOCALE
        if not base_dir.is_dir():
            raise ContentError(f"canonical content base missing: {base_dir}")
        raw = _load_dir_tree(base_dir)
        if self.locale != DEFAULT_LOCALE:
            loc_dir = self.root / self.locale
            if not loc_dir.is_dir():
                available = self.available_locales()
                raise ContentError(
                    f"locale '{self.locale}' has no content directory under {self.root} "
                    f"(available: {', '.join(available) or DEFAULT_LOCALE})")
            raw = _deep_merge(raw, _load_dir_tree(loc_dir))
        # Placeholders are intentionally NOT escaped anywhere else, so keep a
        # private copy for expression: terms and scene/UI strings.
        self.terms = Terms(raw.get("terms", {}), self.locale)
        self.ui = _wrap(raw.get("ui", {}), "ui", self._expand)
        self.audit = _wrap(raw.get("audit", {}), "audit", None)
        self._scripts: dict[str, Box] = {
            key: _wrap(value, f"scenes.{key}", self._expand)
            for key, value in raw.get("scenes", {}).items()
        }
        self._raw_scenes = raw.get("scenes", {})

    # -- expansion -------------------------------------------------------
    def _expand(self, text: str, where: str) -> str:
        return self.terms._expand_terms(text, where)

    def t(self, text: str) -> str:
        """Expand ``{terms}`` in an ad-hoc template."""
        return self._expand(text, "<template>")

    # -- scene access ----------------------------------------------------
    def scene(self, key: str) -> Box:
        try:
            return self._scripts[key]
        except KeyError:
            raise ContentError(
                f"no screenplay for scene '{key}' (expected {self.root/self.locale/'scenes'/ (key + '.toml')})") from None

    def scene_keys(self) -> list[str]:
        return sorted(self._scripts)

    def scene_title(self, key: str) -> str:
        try:
            return self.ui.scenes[key].title
        except ContentError:
            raise ContentError(f"ui.toml is missing [scenes.{key}] title") from None

    def scene_org(self, key: str) -> str:
        try:
            return self.ui.scenes[key].org
        except ContentError:
            raise ContentError(f"ui.toml is missing [scenes.{key}] org") from None

    # -- locale ----------------------------------------------------------
    def available_locales(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir()
                      if p.is_dir() and (p / "terms.toml").exists())

    # -- validation ------------------------------------------------------
    def validate(self, required_scene_keys: list[str] | None = None) -> list[str]:
        problems: list[str] = []
        if required_scene_keys:
            for key in required_scene_keys:
                if key not in self._scripts:
                    problems.append(f"missing screenplay: content/{self.locale}/scenes/{key}.toml")
                    continue
                try:
                    self.scene_title(key)
                except ContentError as exc:
                    problems.append(str(exc))
                try:
                    self.scene_org(key)
                except ContentError as exc:
                    problems.append(str(exc))
        if not len(self.terms):
            problems.append("glossary is empty")
        return problems

    def __repr__(self) -> str:
        return f"Content(locale={self.locale!r}, terms={len(self.terms)}, scenes={self.scene_keys()})"


# --------------------------------------------------------------------------
# Singletons
# --------------------------------------------------------------------------
_content_cache: dict[str, Content] = {}


def get_content(locale: str | None = None, root: Path | None = None) -> Content:
    key = f"{locale or os.environ.get(LOCALE_ENV) or DEFAULT_LOCALE}|{root or C.CONTENT_ROOT}"
    if key not in _content_cache:
        _content_cache[key] = Content(locale=locale, root=root)
    return _content_cache[key]


def reset_cache() -> None:
    _content_cache.clear()
