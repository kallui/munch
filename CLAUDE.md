# MUNCH — UI theme & guidelines

MUNCH is a small desktop utility (webcam hand-gesture mouse/keyboard control).
Keep the UI simple, flat, and consistent — this file exists because the
shadow/hover system has broken in the same ways more than once. Read it
before touching any window, button, or color.

## Visual language: Neo-Brutalism (neobrutalism.dev tokens)

Flat, loud colors; thick black borders; hard-offset "sticker" shadows; bold
type. No gradients, no blur, no soft drop-shadows, no glow.

Tokens live in `munch/theme.py` — always import from there, never hardcode
a hex value or font tuple in a window file.

```python
BG = "#F5F1E6"      # paper background
INK = "#000000"     # true black
YELLOW = "#FFD400"
PINK = "#FF3DAE"     # primary action accent (hover rings, enable button)
BLUE = "#3A86FF"     # status/info strips
GREEN = "#06D6A0"    # "on"/active state
PURPLE = "#8338EC"

BORDER_W = 3
SHADOW_OFFSET = 4
BORDER_RADIUS = 5
```

Fonts: `FONT_TITLE` (Impact, wordmark only), `FONT_SUB` (Bahnschrift,
taglines/body), `FONT_STATUS` (Consolas bold, status readouts),
`FONT_BUTTON` (Bahnschrift SemiBold). Bold/uppercase is reserved for
titles, actions, and status badges — not full sentences; those stay in
sentence case so they're actually readable.

## The shadow rule (read this before adding any shadow)

**A shadow is only visible where it has contrast against what's behind
it.** Shadows in this app are always drawn in `INK`. That means:

- Never give a button a `bg` (canvas backdrop) equal to `INK` while also
  giving it its own `INK` shadow — the shadow is drawn in the same color
  as the surface it's sitting on and becomes completely invisible. This
  is not a subtle issue, it happened twice in this project (the header
  icon buttons when their face was also `INK`, and the toggle button
  when its canvas bg was `INK` to match the surrounding card).
- Don't nest shadowed elements inside other shadowed elements (a
  `RoundedButton` with its own shadow, inside a `_shadow_panel` card that
  already has its own shadow). One shadow per visually-distinct "card" is
  enough — a button that lives inside a card should usually be a flat,
  full-bleed color strip with **no shadow of its own** (see the
  ENABLE/DISABLE MUNCH button in `gui.py` for the current example).
- If a button's face color is `INK` (a black icon chip, say), either give
  it a lighter face so the black shadow has contrast against it, or
  don't give it an individual shadow at all. Don't try to fix this by
  changing the shadow's color — every shadow in the app is `INK` by
  convention; vary the *face*, not the shadow.

## Hover rule

One hover effect, used everywhere: tint the **fill** toward grey via
`hover_tint()` in `munch/widgets.py`. Never recolor the border on hover,
and never pick a bespoke per-button hover color — both were tried and
both broke (a colored hover ring is just as likely to match the
surrounding background as the shadow was, and a second one-off color per
button isn't "consistent"). `RoundedButton` does this automatically.
For a plain flat button that isn't a `RoundedButton` (e.g. the ENABLE/
DISABLE MUNCH strip), bind `<Enter>`/`<Leave>` to swap `bg` between the
base color and `hover_tint(base_color)`, and keep a `self._<x>_color`
instance var as the source of truth so the hover handlers and any
state-driven recolor (e.g. toggling pink/green) never fight each other.

## Widgets

- **`munch/widgets.py` → `RoundedButton`**: the shared sticker-button —
  rounded corners, one hard offset shadow, neobrutalism.dev's press
  interaction (face shifts to the shadow's position and the shadow
  disappears on press, restoring on release). Use this for any
  standalone, independently-shadowed button (icon buttons, dock buttons,
  settings action buttons).
- **Plain flat buttons**: for a button that lives *inside* an
  already-shadowed card (no independent depth of its own), just use a
  `tk.Label` with a `bg` color and a `<Button-1>` binding — don't reach
  for `RoundedButton` here, see the shadow rule above.
- **`_shadow_panel()` in `gui.py`**: the square-cornered card/panel
  builder (header, preview frame, control card). Square corners,
  deliberately — this app does not mix square and rounded containers at
  the same nesting level without a reason.
- Tkinter has no native border-radius or restyleable `Scale`/`Menu` on
  Windows — every rounded shape is rasterized via PIL
  (`ImageDraw.rounded_rectangle` → `PhotoImage` on a `Canvas`), and
  sliders/dropdowns are fully custom-built (see `_SliderWidget` and the
  custom popup in `settings_window.py`) rather than using `tk.Scale`/
  `tk.Menu`, which can't be recolored on Windows.

## General

- Keep this a small utility: no new abstractions, no generalized "theming
  engine," no component library beyond what's listed above. Add to this
  file when a visual mistake repeats, not preemptively.
