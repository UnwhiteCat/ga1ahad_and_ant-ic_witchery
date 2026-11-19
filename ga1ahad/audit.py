"""Content lint: catch hard-coded proper nouns and validate the screenplay.

Two jobs:

``audit_text``
    Scan scene/UI Python sources and the user-facing docs for forbidden
    retired stand-in names (``content/<locale>/audit.toml``) and for raw
    glossary values that should have come from ``{term_key}`` interpolation.
    This is the "never hallucinate the product name again" gate.

``validate_content``
    Load every locale, require a screenplay + title/org for every scene window,
    and report unknown/missing keys.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config as C
from .content import Content, ContentError, get_content
from .timeline import SCENE_SPECS, load_timeline

# Python sources whose on-screen strings must be content-driven.
CODE_SOURCES = [
    "ga1ahad/scenes",
    "ga1ahad/frame.py",
    "ga1ahad/timeline.py",
]
# User-facing docs that must not mention the retired stand-ins.
DOC_SOURCES = [
    "README.md",
    "docs/CONTENT.md",
    "docs/SCENE_AUTHORING.md",
]
# Never scanned (they are the source of truth for content/audit itself).
SKIP_NAMES = {"__pycache__"}

_BOUND_LEFT = r"(?<![A-Za-z0-9_])"
_BOUND_RIGHT = r"(?![A-Za-z0-9_])"


@dataclass
class Violation:
    path: str
    line: int
    kind: str          # "forbidden" | "term" | "doc-forbidden"
    needle: str        # offending fragment
    message: str
    snippet: str = ""

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.kind}] {self.message}  ({self.snippet})"


@dataclass
class Stats:
    code_files: int = 0
    string_constants: int = 0
    narrative_literals: int = 0
    lyric_copies: int = 0
    per_file: dict[str, tuple[int, int]] = field(default_factory=dict)


def _iter_py_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for entry in CODE_SOURCES:
        target = root / entry
        if target.is_dir():
            files += [p for p in sorted(target.rglob("*.py")) if p.name not in SKIP_NAMES]
        elif target.exists():
            files.append(target)
    return files


def _docstrings(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _string_nodes(tree: ast.AST):
    docs = _docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node, id(node) in docs


def _build_term_patterns(terms) -> list[tuple[str, str, re.Pattern[str]]]:
    """One pattern per distinct canonical value (avoids duplicate reports)."""
    patterns: list[tuple[str, str, re.Pattern[str]]] = []
    seen: set[str] = set()
    for key in terms.keys():
        try:
            value = terms[key]
        except ContentError:
            continue
        norm = value.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        pat = re.compile(_BOUND_LEFT + re.escape(value.strip()) + _BOUND_RIGHT, re.IGNORECASE)
        patterns.append((key, value, pat))
    return patterns


def _forbidden_patterns(content: Content) -> list[str]:
    try:
        names = content.audit.audit.forbidden
    except ContentError:
        names = []
    return [str(n) for n in names]


def audit_text(root: Path | None = None, locale: str | None = None,
               stats: bool = False) -> tuple[list[Violation], Stats]:
    root = Path(root) if root else C.ROOT
    content = get_content(locale)
    term_patterns = _build_term_patterns(content.terms)
    forbidden = _forbidden_patterns(content)
    forbidden_lower = [(name, name.lower()) for name in forbidden]
    violations: list[Violation] = []
    st = Stats()

    for path in _iter_py_files(root):
        rel = path.relative_to(root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            violations.append(Violation(str(rel), exc.lineno or 0, "forbidden", "",
                                        f"python syntax error: {exc.msg}"))
            continue
        st.code_files += 1
        file_strings = file_narrative = 0
        for node, is_doc in _string_nodes(tree):
            text = node.value
            file_strings += 1
            if len(text) > 25 and " " in text:
                file_narrative += 1
            if is_doc:
                # docstrings may explain concepts but must not name real brands
                for needle, low in forbidden_lower:
                    if low and low in text.lower():
                        violations.append(Violation(str(rel), node.lineno, "forbidden", needle,
                                                    f"forbidden stand-in name {needle!r} in docstring"))
                continue
            # skip the per-frame VTT lyric duplicates? no: lyrics are names-free
            for needle, low in forbidden_lower:
                if low and low in text.lower():
                    violations.append(Violation(str(rel), node.lineno, "forbidden", needle,
                                                f"forbidden stand-in name {needle!r}",
                                                snippet=text[:48]))
            for key, value, pat in term_patterns:
                m = pat.search(text)
                if m:
                    violations.append(Violation(
                        str(rel), node.lineno, "term", value,
                        f"hard-coded glossary value {value!r} (use term {key!r})",
                        snippet=text[max(0, m.start() - 18):m.end() + 18]))
        st.string_constants += file_strings
        st.narrative_literals += file_narrative
        st.per_file[str(rel)] = (file_strings, file_narrative)

    # VTT lyric lines must not be copied into scene code: lyrics are read from
    # the timeline (self.cues / self.cue_* helpers), never duplicated.
    try:
        timeline = load_timeline()
        lyrics = [ly.text.strip() for ly in timeline.lyrics
                  if len(ly.text.strip()) >= 8 and not ly.instrumental]
    except Exception:  # pragma: no cover - VTT is validated by `check` first
        lyrics = []
    if lyrics:
        for rel in CODE_SOURCES:
            path = root / rel
            if not path.exists():
                continue
            files = _iter_py_files(path) if path.is_dir() else [path]
            for src in files:
                tree = ast.parse(src.read_text(encoding="utf-8"))
                docs = _docstrings(tree)
                rel_src = str(src.relative_to(root))
                for node, is_doc in _string_nodes(tree):
                    if is_doc:
                        continue
                    value = node.value
                    for lyric in lyrics:
                        if lyric in value:
                            violations.append(Violation(
                                rel_src, getattr(node, "lineno", 0), "lyric-copy", lyric,
                                "hard-coded VTT lyric (read self.cues / cue_text instead)",
                                snippet=value[:64]))
                            st.lyric_copies += 1
                            break

    # The screenplay/glossary itself must be clean too: a retired stand-in
    # inside content/<locale>/ terms/ui/scenes would silently ship on screen.
    # (audit.toml is skipped: it is the configuration that *lists* these names.)
    def walk(value, path: str) -> None:
        from .content import Box

        if isinstance(value, Box):
            for key, child in value.items():
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")
        elif isinstance(value, str):
            low = value.lower()
            for needle, nl in forbidden_lower:
                if nl and nl in low:
                    violations.append(Violation(
                        f"content/{content.locale}", 0, "content-forbidden", needle,
                        f"forbidden stand-in name {needle!r} in content {path}",
                        snippet=value[:64]))

    walk(content.terms, "terms")
    walk(content.ui, "ui")
    for key in content.scene_keys():
        walk(content.scene(key), f"scenes.{key}")

    for doc in DOC_SOURCES:
        path = root / doc
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            low = line.lower()
            for needle, nl in forbidden_lower:
                if nl and nl in low:
                    violations.append(Violation(doc, idx, "doc-forbidden", needle,
                                                f"forbidden stand-in name {needle!r} in docs",
                                                snippet=line.strip()[:64]))

    # stable order
    violations.sort(key=lambda v: (v.path, v.line, v.kind, v.needle))
    return violations, st


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def validate_content(locale: str | None = None, all_locales: bool = True) -> list[str]:
    problems: list[str] = []
    required = [s.key for s in SCENE_SPECS]
    base = get_content(locale)
    locales = base.available_locales() if all_locales else [base.locale]
    for loc in locales:
        try:
            content = get_content(loc)
        except ContentError as exc:
            problems.append(f"locale {loc}: {exc}")
            continue
        problems += [f"locale {loc}: {p}" for p in content.validate(required)]
    # cross-check that every canonical term is reachable and every scene uses
    # at least one content string (otherwise the screenplay file is probably
    # still the empty placeholder).
    try:
        content = get_content(locale)
        for key in required:
            box = content.scene(key)
            if not list(box.keys()):
                problems.append(f"scene {key}: screenplay file is empty")
    except ContentError as exc:
        problems.append(str(exc))
    return problems


def format_stats(st: Stats) -> str:
    lines = [f"scanned {st.code_files} python files, "
             f"{st.string_constants} string constants, "
             f"{st.narrative_literals} long narrative literals, "
             f"{st.lyric_copies} VTT lyric copies"]
    for path, (strings, narrative) in sorted(st.per_file.items()):
        lines.append(f"  {path:34s} strings={strings:4d}  narrative={narrative:4d}")
    return "\n".join(lines)
