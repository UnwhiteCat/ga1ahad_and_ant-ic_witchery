# Scene authoring guide (Ga1ahad TUI video)

This project renders a 200x56 truecolor TUI animation for the full 219.15 s song
`Ga1ahad and Scientific Witchery`, then encodes it to a 1920x1080 MP4 with the
original audio. Scene windows are defined by `SCENE_SPECS` in
`ga1ahad/timeline.py`; `ga1ahad.vtt` supplies the lyric text and timing.
The current scene implementation and `content/` provide the starting point for
future creative changes.

## Content layer (mandatory)

Scene code never hard-codes a proper noun or a story line.  All names live in
`content/<locale>/terms*.toml` and all screenplay text in
`content/<locale>/scenes/<scene>.toml`; scene code reads them through
`ctx.terms` / `ctx.script` (or `self.T` / `self.script`).  `./ga1ahad_tui
audit-text` fails the build if a raw glossary value or a retired stand-in
name is hard-coded again.  Read **[docs/CONTENT.md](CONTENT.md)** before
editing a scene; the prologue (`ga1ahad/scenes/prologue.py` +
`content/en/scenes/prologue.toml`) is the reference implementation.

## Hard constraints

1. **Canvas is exactly 200 columns x 56 rows.** The framework draws the chrome:
   - row 0: brand / telemetry status bar
   - row 1: song progress bar
   - rows 2..52: **your scene content area (51 rows, 200 columns)**
   - row 53: scene title separator
   - row 54: VTT lyric subtitle (auto — never hide or duplicate it)
   - row 55: timecode / cue footer
   Draw only inside `rows 2..52`. The renderer clips scene painting to those
   rows (primitive calls are clipped, direct row-list writes are discarded and
   fail `verify`); the chrome is then painted over the reserved rows.
2. **Lyric sync is sacred.** Every VTT cue inside your scene range must be
   visually accounted for and must not drift. Use the VTT-derived helpers:
   ```python
   ctx.lyric            # current Lyric(start, end, text, index, instrumental)
   ctx.lyric_t          # seconds since the current cue started
   ctx.lyric_local      # 0..1 progress inside the cue
   self.cue_progress(ctx, i)   # 0..1, locked to the i-th VTT cue in this scene
   self.cue_local(ctx, i)      # seconds into that cue
   self.cue_text(i)            # the VTT text of that cue
   self.cues                   # all VTT cues whose start falls in this scene
   ```
   Do NOT copy lyric strings from `ga1ahad.vtt` into scene code: use the cue
   helpers above (the VTT cue list is built in `Scene.__init__`). `audit-text`
   rejects hard-coded VTT lyrics. Note the curly apostrophes in the VTT
   (`I’ll`, `Don’t`, `you've`, `There's`). Test at cue start/mid/end.
3. **No cuts.** Your scene receives every frame in `[START, END)`; render
   continuously, no gaps or blank frames.
4. **Deterministic.** No mutable cross-frame state, no wall-clock, no unseeded
   RNG. Use `ctx.rng` (a `random.Random` seeded from the frame number) for
   randomness. Constructor-time caching of static art is fine.
5. **Performance budget:** keep `draw()` under ~50 ms per frame on this machine.
   The full render uses 8-20 worker processes.

## LLM dialog window (portrait focus region)

The film is composed around a single focus region: **every human <-> LLM
conversation lives in ONE portrait 9:16 window pinned to the left of the frame,
and the right stage is reserved for the animation**.  A conversation is anything
that shows the LLM talking or a human prompting it (chat / response terminals,
CLI agent panes, CoT buffers, governance inquiry and error notices, desktop chat
panes).  Monitoring / training-data panels are animation and stay on the stage.

```python
from .. import art
from .. import config as C

# C.DLG_SLOTS = ((4, 4, 48, 54),)   # (row, col, h, w)
y, x, h, w = C.DLG_SLOTS[0]
art.llm_dialog(c, y, x, h, w, "OPERATOR SHELL", bg=C.INK2,
               border=C.CYAN_DIM, right="tty0")
# ... draw live content into rows y+1 .. y+h-2, cols x+2 .. x+w-3
```

Rules enforced by the helper (and by `./ga1ahad_tui check` on a frame sweep):

1. **Portrait 9:16 in pixels.** The cell grid is 10x20 px, so a window must
   satisfy `|8*w - 9*h| <= 1`.  The standard window is `55x49` cells =
   550x980 px (54x48 is the exact relation; with the 1-cell vertical margins the
   49 rows can only reach 55.125 cols, so 55 is used and the ratio is 0.2 % off
   -- visually exact).  `art.llm_dialog` rejects any other aspect.
2. **Margins 1 / 1 / 1 (inside the content band).** Chrome rows 0..1 and 53..55
   are frame-owned, so margins are measured inside content rows 2..52.  The
   window starts at `C.DLG_X = 1` (margin-left: column 0 empty) and
   `C.DLG_TOP = 3` (margin-top: content row 2 empty), and ends at row 51
   (`y + h == C.CONTENT_Y1 - C.DLG_BOTTOM == 52`, margin-bottom 1: content row
   52 empty).  On the 200x56 canvas this leaves exactly one 55x49 portrait
   window, which is what `C.DLG_SLOTS[0]` is; the right gutter (cols 56..63)
   also stays glyph-free while a window is shown.
3. **One window per conversation / per scene.** Do not add a second dialog
   window.  Everything that used to be a secondary box -- a second chat thread,
   an operator/input pane, a CoT trace, a governance inquiry, an error popup, an
   emotion or verdict readout -- becomes a *section inside* the portrait window
   (separators, labelled messages, footer strips).  Voices are distinguished by
   text colour and glyph effects, not by separate boxes.
4. **Never on the stage.** Dialog cells are recorded on the canvas mask; any
   marked cell at column `>= C.STAGE_X` (`64`) fails the renderer sweep.  The
   right stage (`x >= 64`, 136 columns) must carry the scene animation.
5. **Adapt the content, not the rule.** A 55x49 window has 53x48 usable cells:
   wrap / trim / scroll / typewrite the screenplay text to fit instead of
   growing the window.  Keep cue-synced typing (`cue_local` / cue helpers) and
   lyric alignment unchanged.

Community-feed popups (the programmer praise cards in Scene 2, social comment
windows) are *not* human <-> LLM conversations: keep them out of
`art.llm_dialog`. When the story needs the "outside noise" reading they live on
the top layer over the stage/lane: mostly drifting upright rectangles with
irregular sizes, edge clipping and overlap, plus a small quota of shaped
silhouettes -- Scene 2 keeps at most `n_visible // 10` (<=9.1 %) shaped cards,
rotating a diamond, a five-point star and a dotted oval.

Special transitions may break the rule deliberately (flight-in popups,
full-bleed strobe montages).  Declare the absolute-time window on the scene
class and keep it as short as the effect needs:

```python
class Scene5(Scene):
    DIALOG_EXEMPT = ((191.80, 192.35),)   # 0.55 s full-bleed strobe cut
```

The sweep skips those spans, but every other frame must obey the rule.

## How a scene is wired

`ga1ahad/scenes/__init__.py` imports `scenes/<key>.py` and instantiates
`<Class>(assets, audio, timeline)`. Existing example: `ga1ahad/scenes/prologue.py`.

```python
from .. import art
from .. import config as C
from .base import Scene

class Scene1(Scene):
    NAME = "s1"
    TITLE = "CLI TRAINING GROUND"
    def draw(self, c, ctx) -> None:
        t = ctx.t          # absolute seconds
        local = ctx.local  # seconds since scene START
        ...
```

The class name must be exactly `Scene1`, `Scene2`, `Scene3`, `Scene35`,
`Scene4`, `Scene5`, `Scene6` (see registry).

## Output CRT stage (MP4 only)

The delivered MP4 is not the raw cell raster: when a video is generated the
renderer runs the internal 2000x1120 raster through a CRT output stage
(`ga1ahad/crt.py`) before encoding -- barrel-curved glass, scanlines, bloom,
RGB convergence error, vignette, a rounded bezel, a rolling refresh band, mains
flicker and phosphor grain. Scene code does nothing for it, and the curvature
is capped so the visible screen edge and the four corners stay within 1% of the
frame width/height; keep anything essential out of that outer 1% strip. Preview
a still with `png --crt`, and use `render --no-crt` when you want to inspect
the flat raster.

`render` applies the stage by default (strength 1.0); `--no-crt` and
`--crt-strength 0..2` override it, and the `GA1AHAD_CRT` environment variable
(0..2, or on/off) sets the default strength for renders. `png`/`sheet` are flat
unless `--crt` is passed; the env default only affects renders.

## Canvas API (`ga1ahad/canvas.py`)

Coordinates are `(row, col)`, colours are packed `0xRRGGBB` ints from
`ga1ahad/config.py` (e.g. `C.CYAN`, `C.TERRA_HI`, `C.mix(a, b, t)`).

```python
c.clear(fg=C.TEXT, bg=C.INK)              # optional: frame is pre-cleared
c.put(row, col, "█", fg, bg=None)         # bg=None keeps current bg
c.text(row, col, "string", fg, bg=None, bold=False)
c.text_center(row, "string", fg, bg=None, bold=True)
c.fill(row, col, h, w, " ", fg, bg)       # rectangular fill
c.fill_bg(row, col, h, w, bg)             # recolour background only
c.hline/vline(...), c.frame(...), c.panel(...)   # see source for args
c.blend_bg(row, col, colour, 0.3)
c.sprite(row, col, sprite)                # Sprite from assets
br = c.braille(row, col, h, w)            # sub-pixel 2x4 dots per cell
br.plot(px, py, colour); br.line(...); br.commit()
c.fx.glitch = 0.4                          # 0..1 cell glitch/tear
c.fx.chroma = 0.5                          # RGB split
c.fx.flash = 0.2; c.fx.flash_color = C.WHITE
c.fx.invert = 0.5; c.fx.shake_x = 3; c.fx.scan = 1.0
```

`ga1ahad/motion.py` is the shared cinematic motion language used by the
current chapters: 3D Braille camera projection (ring/sphere/grid/contour/mesh/star
geometry), spring and easing curves, monumental 5x7 block typography, iris /
letterbox / shutter / feathered-keyframe transitions and a sparse `motion.Dialog`
layout inside the portrait conversation window.  Prefer it for camera moves,
kinetic type and transitions instead of ad-hoc loops.

`ga1ahad/art.py` has ready-made widgets: `dialog`, `panel`/`separator`,
`bar`, `gradient_bar`, `gauge`, `line_chart` (braille), `wave`, `spectrum`,
`heatmap`, `particles`, `confetti`, `starfield`, `scroll_lines`, `typewriter`,
`prompt_line`, `ticker`, `big_banner`, `title_bar`, `wave_band`.
Read their signatures before use.

## Assets (`ga1ahad/assets.py`)

```python
ctx.assets.claude_full(rows=40)    # half-block sprite from the 2D anime keyframe
ctx.assets.claude_bust(rows=24)    # head + shoulders
ctx.assets.claude_face(rows=12, dark=True)
ctx.assets.sun(rows=5)             # sunflower emblem (Anthropic)
ctx.assets.sunburst(rows=12)
ctx.assets.sam(rows=24)            # Sam Altman bust
ctx.assets.dahlia(rows=24, manic=False)
ctx.assets.gpt4(rows=18)           # OpenAI GPT-4 wireframe entity
```
Sprites are half-block graphics; place them with `c.sprite(row, col, sp)`.
Sizes are in rows; width follows the artwork aspect ratio.

### Claude's avatar

Follow the [maintainer convention](../AGENTS.md#conventions) for every
appearance of the avatar, including AI-generated keyframes, eye close-ups,
reflections and fused portraits. Use the [original design](../claude.webp)
as the reference for her copper-orange hair, sunflower clip and lace dress.
Use drawn outlines and cel shading to keep her face and costume visibly 2D.

Screen glow, scanlines and brief interference can reinforce her virtual
presence. When she appears alongside a live-action character or shares a
face with one, check the rendered frame to make sure her outlines and drawn
features remain readable through the composite and CRT effects.

## Audio reactivity

```python
ctx.audio.energy(t)          # 0..1 overall loudness
ctx.audio.pulse(t, 0.15)     # onset envelope (0..1)
ctx.audio.bass(t)            # low band
ctx.audio.spectrum(t)        # 24 log bands 0..1
ctx.audio.pulse / flux_at / band_mean
```

## Testing / reviewing your work

```bash
./ga1ahad_tui png --at 18.0,22.5,28.0 --out build/s1/    # several stills
./ga1ahad_tui render --start 17.54 --end 28.0 \
    --workers 4 --no-audio --out build/s1_preview.mp4    # preview clip
./ga1ahad_tui dump --out build/cues --only "The magical" --limit 3
```
Open PNGs with your image reader and iterate on composition. The final frames
are 1920x1080 (aspect 16:9). `./tools/py` is the project Python (numpy/Pillow
available); use it for ad-hoc scripts.

To verify lyric coverage of your range in code:

```python
from ga1ahad.timeline import load_timeline
tl = load_timeline()
for ly in tl.lyrics:
    if 17.54 <= ly.start < 40.64:
        print(ly.index, ly.start, ly.end, repr(ly.text))
```

## Coordination rules

- **Only edit the file(s) assigned to you.** Shared modules (`canvas.py`,
  `art.py`, `config.py`, `frame.py`, `assets.py`, ...) are owned by the Lead.
  If you need a new shared helper, implement it locally inside your scene or
  message the Lead.
- Keep the visual language consistent: dark terminal background, dense
  telemetry, box-drawing panels, braille charts, 24-bit accent colours.
  Use the palette from `config.py` (cyan = OpenAI/Sam, amber/red = Dahlia,
  terracotta/gold = Claude/Anthropic, purple = identity fusion).
- Report back with: scene status, key timestamps, screenshots you like, and any
  requested API help.