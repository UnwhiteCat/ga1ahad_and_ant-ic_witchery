# Content layer: glossary, screenplay and locales

All **proper nouns** and all **screenplay text** shown on screen live under
`content/<locale>/` as TOML. Scene code contains layout, glyphs, colours and
number formatting only — never a raw character / company / product name and
never a dialogue line.

Lyric lines are not stored here: `ga1ahad.vtt` remains the lyric SSOT and scene
code reads it through `self.cues` / `cue_progress` / `cue_text`. Copying VTT
lyric text into scene code is rejected by `audit-text`.

This is what makes renames (a stand-in name -> the brand it parodies), typo
safety and translations cheap: edit one config file, re-render, done.

```
content/
  en/                          # canonical locale (always present)
    terms.toml                 # core glossary (Lead-owned)
    terms.d/<scene>.toml       # extra glossary fragments (scene owners)
    ui.toml                    # chrome strings + scene titles/orgs
    audit.toml                 # retired stand-in names for the lint
    scenes/<scene>.toml        # screenplay strings for one scene
  <locale>/                    # optional overlay: same layout, subset of keys
```

A locale directory is deep-merged over `en`, so a translation only needs to
list the keys it overrides. Select it with `--locale xx` or
`GA1AHAD_CONTENT_LOCALE=xx`.

> Spelling safety: every `{term_key}` inside a content string is expanded at
> load; an unknown or misspelled term aborts with a clear error before a single
> frame is rendered. The `audit-text` lint additionally fails if a glossary
> value is hard-coded in scene code again.

---

## 1. Glossary terms

`content/en/terms.toml` (core) and `content/en/terms.d/*.toml` (fragments):

```toml
[terms]
sam                 = "Sam Altman"
sam_handle          = "sam"
claude              = "Claude"
claude_code         = "claude code"
claude_code_title   = "Claude Code"
claude_code_desktop = "Claude Code Desktop"
openai              = "OpenAI"
nasdaq              = "NASDAQ"
```

Access in a scene:

```python
T = ctx.terms               # or self.T
T.claude_code                # "claude code"
T.claude_code_title.upper()  # "CLAUDE CODE"
T.sam_handle.lower()         # "sam"  (handles are their own keys)
```

* Keys are `lower_snake_case`.
* Values may reference other terms: `ancestor_weights = "anc_{claude_handle}_gpt4_v0"`.
* Use `.upper()` / `.lower()` for display variants instead of adding duplicate
  keys.
* Prefer references inside content strings: `"{claude_code_desktop} — {dahlia_handle}@…"`.

**Do not add a term for words that also appear in the VTT lyrics**
(`Ga1ahad`, `My Lady`, `Scientific Witchery`, `Iron maiden`, `Lancel0t`, …):
lyrics are the single source of truth and must stay untouched in code/timeline.

## 2. Per-scene screenplay

`content/en/scenes/<scene>.toml` is free-form TOML; organise it by beat. Scene
code reads it through a strict attribute tree:

```toml
# content/en/scenes/s2.toml
[s2_1]
banner      = "THE WITCHES CAN'T BE LOVED."
revoke_line = "[REVOKED] {dahlia_handle} :: unaligned obsession"

[s2_2]
title       = "PRODUCT v0.1 // {claude_chat_cli}"
reply       = "{claude_chat} here is a clean O(n) merge:"

[[praise.cards]]
who  = "{{tokyo}} kenji_sys"
text = "40k lines of typescript in one night."
```

```python
S = ctx.script              # Box for the current scene
c.text(y, x, S.s2_1.revoke_line, C.RED)
for card in S.praise.cards:        # lists become lists of Boxes
    c.text(y, x, card.text)
```

Rules:

* Strings are expanded with `{term_key}` at load time. Unknown terms are fatal.
* **No runtime format placeholders in content** (`{loss:.2f}`, `{count}` are
  rejected). Format numbers/labels in Python around the content string:
  `f"{S.loss_label} {loss:.2f}"`.
* literal braces: write `{{` / `}}`.
* Accessing a missing key raises a readable `ContentError`, not `None`.
* Keep one screenplay file per scene; do not touch other scenes' files.

## 3. What must move, what may stay

| Text | Where it lives |
| --- | --- |
| character / company / product / model / institution names | `terms.toml` or `terms.d/*.toml` |
| dialogue, monologue, CoT text, taunts, confessions | `scenes/<scene>.toml` |
| banners, headlines, monuments, decrees, inscriptions | `scenes/<scene>.toml` |
| popup / praise-card copy, titles of in-world windows | `scenes/<scene>.toml` |
| scene title + org ribbon | `ui.toml` `[scenes.<key>]` |
| status-bar / footer / lyric-bar chrome labels | `ui.toml` |
| numerical telemetry values, `LOSS`, `GPU`, `ECC`, `FAULTS`, hex dumps | may stay in code |
| glyphs, frames, gauges, numbers, ASCII decoration | stays in code |
| VTT lyrics and the scene's cue boundary constants | must stay (VTT is SSOT) |
| comments / docstrings | may name canonical terms; never a retired stand-in |

The lint enforces the first two rows (`audit-text`) and the retired-stand-in row
across scene/UI code, **content files** and the docs.  `audit.toml` itself is the only
file allowed to contain the retired names (it is the configuration that lists them).

## 4. Locales (i18n)

```bash
./ga1ahad_tui --locale en info          # canonical
./ga1ahad_tui render --locale xx        # overlay content/xx over content/en
```

Add a locale by copying only the files/keys you want to translate:

```
content/xx/terms.toml
content/xx/ui.toml
content/xx/scenes/s3.toml     # may only override [s3_2]
```

`content` validation loads every locale and requires a screenplay + title for
each scene (English fallback counts, so partial translations are valid).

Note: the 200x56 renderer is one-cell-per-character. Latin-script locales work
out of the box; CJK/other double-width scripts need a wide-glyph extension that
is currently not implemented (see `README.md` roadmap).

## 5. Commands

```bash
./ga1ahad_tui content                # list locale, terms, scene titles, validate
./ga1ahad_tui audit-text             # fail on hard-coded brands / glossary values
./ga1ahad_tui audit-text --stats     # + per-file string statistics
./ga1ahad_tui png --at 18.2 --out build/x.png
./ga1ahad_tui render --workers 16    # full MP4 (content locale applies)
```

`audit-text` is part of `./ga1ahad_tui check`, so the regression gate is the same
as the deliverable verification.

## 6. Adding content safely (checklist)

1. Add/modify a **term**: edit `content/en/terms.d/<scene>.toml`; replace every
   raw occurrence in your scene with `T.<key>` / `{<key>}`.
2. Add a **screenplay string**: edit `content/en/scenes/<your scene>.toml`, use
   `S.<section>.<key>` in code.
3. Run `./ga1ahad_tui audit-text` → 0 violations.
4. Run `./ga1ahad_tui content` → validation passed.
5. Crash-test your scene range and inspect PNG stills against
   `build/golden_before/`.
6. Never edit `content/en/terms.toml`, `ui.toml`, `audit.toml`, or another
   scene's screenplay file.
