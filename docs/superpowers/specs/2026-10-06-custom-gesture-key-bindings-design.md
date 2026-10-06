# Custom gesture → key bindings

## Context

MUNCH currently supports exactly four customizable gesture actions, all of the same shape: a thumb+finger pinch mapped to one of left/right/middle/double mouse-click (`munch/bindings.py`, a strict one-to-one permutation of 4 pinch shapes across 4 fixed mouse actions). Scroll and the wake/arm pose are fixed, non-rebindable poses.

The user wants to go further: a library of additional gesture shapes (OK sign, finger-count holds, directional slaps) that can each be freely bound to an arbitrary keyboard key or key combination (e.g. a gesture → "N", for sites that use N as a "next episode" shortcut), with the full set of bindings saveable as named presets (Default + custom), switchable from a dropdown in Settings.

This is a new subsystem, not an extension of the existing 4-pinch permutation model — it targets the keyboard, not mouse actions, and the cardinality is open-ended (any number of bindings) rather than a fixed 1:1 permutation. It stays independent of `bindings.py`/the mouse-click system, which is untouched by this work.

## Goals

- A small, fixed library of additional gesture shapes, detected with the same hand-written geometric technique already used throughout `munch/gesture_recognizer.py` (tip/pip distance ratios, pinch distance, centroid velocity) — no ML, no new dependency, no "record an arbitrary motion" flow.
- Each library gesture can be bound to any keyboard key or modifier+key combination, with any number of bindings active at once.
- Bindings are one-shot (the pose must release and re-form to fire again) — no auto-repeat-while-held.
- The whole binding set can be saved/loaded as a named preset; "Default" always exists and starts empty.
- A Settings UI section to manage bindings and presets, plus a cheat-sheet entry for any active custom bindings.

## Non-goals (explicitly out of scope for this spec)

- Arbitrary user-trained/recorded gestures (true "perform any motion, the app learns it"). Flagged in an earlier conversation as a substantially harder, separate problem; not attempted here.
- Binding library gestures to mouse actions — keyboard only, per the user's own scoping decision. The existing 4-pinch mouse-click system is untouched.
- The "wave" gesture — deferred; only OK sign, finger-count holds, and left/right slaps ship in this pass.
- Hold-to-repeat bindings — one-shot only for v1.

## Gesture library and collision handling

Four new detectors, added to `munch/gesture_recognizer.py`'s per-frame `update()` alongside the existing wake/pinch/scroll checks, all gated on `self.armed` (same invariant every existing gesture already follows, so nothing here can misfire while disarmed):

- **OK sign**: thumb+index tips within pinch distance (reusing the existing pinch-distance threshold) **and** middle, ring, pinky all extended. Today's thumb+index pinch (left-click by default) does not check the state of the other three fingers, so an OK sign currently also satisfies the pinch condition. Fix, applied to the *existing* pinch detector as part of this work: a pinch additionally requires the three non-pinching fingers to be curled (not extended). This makes a pinch and an OK sign geometrically disjoint instead of overlapping.
- **Finger-count holds — 1, 3, 4**: counts fingers currently read as "extended" by the same tip-vs-pip ratio check `_finger_extended()` already uses for scroll's index/middle check.
- **Finger-count hold — 2, as a "peace sign"**: index + middle both extended AND spread apart beyond a "together" threshold, disambiguated from scroll by hand shape rather than a timing trick (see below) — this was explicitly worked out in conversation as better than an earlier draft that tried to resolve the collision by requiring the pose be held still.
- **Slap left / slap right**: open hand (no specific finger pose requirement beyond "roughly open"), horizontal centroid velocity over the last few frames crossing a threshold in one direction. This is the one detector that's motion-based rather than a static-pose snapshot, so it reuses the palm-center calculation (`palm_center()`, already used for cursor tracking) sampled over a short frame window rather than a single-frame landmark check.

**Scroll gets one small, independent fix as part of this work**: a "fingers held together" guard (index-to-middle fingertip lateral distance, normalized against something that scales with hand distance from the camera — e.g. the index-to-middle MCP knuckle distance, the same style of normalization the pinch thresholds already use). Below the threshold → counts as the scroll pose ("pointing a gun," fingers together); above it → does *not* count as scroll, leaving room for the peace-sign/2-count gesture to claim that shape instead. Today scroll has no such guard at all — a peace sign and a pointing hand currently register identically — so this closes a real gap independent of the new feature, not just a workaround for it.

Threshold values for the "together vs. spread" guard and the slap velocity check will need hands-on tuning once a first pass is running (consistent with how `PINCH_ON_THRESHOLD`/`SCROLL_DEADZONE`/etc. were originally tuned by feel, not derived analytically) — expect a short calibration-by-feel loop during implementation, not a one-shot guess.

## Data model and persistence

New file `munch/custom_bindings.py`, mirroring the existing load/save pattern in `bindings.py`/`calibration.py`/`tuning.py`:

- A **binding**: `{"gesture": "<ok_sign|count_1|count_3|count_4|peace_sign|slap_left|slap_right>", "keys": "<string>"}`, where `keys` is a normalized combo string like `"n"` or `"ctrl+w"`.
- A **preset**: `{"name": "<str>", "bindings": [<binding>, ...]}`.
- Storage: one JSON file (e.g. `custom_presets.json`) holding the list of presets plus which one is currently active. "Default" always exists, cannot be deleted (only edited/cleared), and starts with zero bindings.
- No uniqueness constraint across bindings is required by the data model itself (unlike the strict 4-pinch permutation) — a gesture could in principle be bound more than once, or a key combo reused, though the Settings UI should warn/block in the obvious case (same gesture bound twice in one preset) similar in spirit to how `bindings.is_valid()` guards the existing system.

`munch/keyboard_controller.py` gains a `press_combo(keys: list[str])` method (modifier keys held via `pynput`'s `Controller.pressed()` context, then the final key tapped) alongside its existing single-key/text methods — the one piece of new capability needed in that file.

## Settings UI

New "CUSTOM GESTURES" section in `settings_window.py`, built from the same hand-drawn dropdown/row primitives already used for the 4-pinch bindings and the sensitivity sliders (no native `tk.Menu`/`tk.Scale`, consistent with the rest of the app and `CLAUDE.md`'s documented constraints):

- **Preset dropdown** at the top of the section: Default + any saved custom presets. Switching presets loads that preset's bindings into the recognizer live. Save-as-new / Rename / Delete controls for non-Default presets (Default can't be deleted).
- **Binding list**: one row per active binding — a gesture-choice dropdown (populated from the fixed library), a "click to set key" capture field (listens for the next key/modifier-combo pressed and renders it, the same interaction pattern as rebinding a hotkey in most desktop apps), and a remove (×) button. An "+ Add binding" button appends a new, unbound row.
- Applies live (no restart), same as every other Settings control in this app.

## Cheat sheet

`munch/cheat_sheet.py` gains a section listing any bindings in the *currently active* preset, read live the same way the existing 4 pinch-action rows already read live from `recognizer.bindings` — never a stale hardcoded list.

## Testing / verification plan

- Each new static-pose detector (OK sign, counts 1/3/4, peace sign) tested by hand in front of the camera, confirming it fires once per pose formation (not continuously), and confirming it does *not* misfire during normal use of the existing pinch/scroll gestures (and vice versa — existing pinch/scroll must still work correctly after the OK-sign guard and scroll "together" guard are added).
- Slap left/right tested for both directions, confirming it doesn't fire spuriously during ordinary cursor movement (i.e. the velocity threshold is high enough that normal pointer motion doesn't trigger it).
- Binding flow: add a binding (e.g. OK sign → "n"), confirm the keystroke actually lands in a real focused external app (e.g. Notepad), confirm it's one-shot.
- Preset flow: create a second preset, bind something different in it, switch between presets, confirm the active bindings actually change and persist across an app restart.
- Cheat sheet: confirm it reflects whatever the active preset currently has bound, including zero bindings (Default, untouched).
- Regression: full existing gesture set (wake/arm, all 4 pinch actions + drag, scroll, disarm) still behaves correctly — this spec touches shared code (`gesture_recognizer.py`'s pinch and scroll checks), so this is the most important regression surface, not a formality.
