# Custom Gesture → Key Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a library of additional hand gestures (OK sign, finger-count holds, left/right slaps) that can each be bound to an arbitrary keyboard key/combo, saved as named presets, managed from Settings, and listed in the cheat sheet.

**Architecture:** Pure geometric detectors (same hand-written technique as the existing pinch/scroll code) in a new `custom_gestures.py`, built on landmark-geometry primitives extracted from `gesture_recognizer.py` into a new shared `hand_landmarks.py` (so the new detectors and the existing ones never duplicate/diverge). Bindings+presets persist as JSON via a new `custom_bindings.py`, mirroring the existing `bindings.py`/`tuning.py` load/save pattern. `GestureRecognizer` resolves a fired gesture straight to a `("key_combo", [...])` event, same style as its existing mouse-click events; `gui.py` routes that event kind to `keyboard_controller.py`'s new `press_combo()`.

**Tech Stack:** Python/Tkinter (existing stack, no new runtime dependency). Tests use the stdlib `unittest` (not pytest — not installed in the venv, and the project avoids adding dependencies it doesn't need).

**Spec:** `docs/superpowers/specs/2026-10-06-custom-gesture-key-bindings-design.md`

## Global Constraints

- Keyboard-only binding target (no mouse actions) — spec scope decision.
- One-shot firing only (pose/motion must release and re-form to fire again); no hold-to-repeat — spec scope decision.
- No new runtime dependency; tests use stdlib `unittest`.
- Every new static-pose detector only fires while `self.armed` is true — the existing invariant every current gesture already follows.
- Any new Settings UI widget follows `CLAUDE.md`: no native `tk.Scale`/`tk.Menu`, flat bordered neo-brutalist rows, hover = grey-tint via `hover_tint()` from `munch/widgets.py`, border color never changes on hover.
- The "Default" preset always exists and can never be deleted.

## Review Focus

- A pinch rebound onto the "index" finger must stay distinguishable from an OK sign in a real `update()` call, not just in an isolated detector test — Task 5.
- Hand leaving frame mid-custom-gesture must not leave the one-shot latch stuck `True` forever (which would silently block that gesture from ever firing again) — Task 5.
- A binding whose key combo was never actually set (added but left empty) must not crash `press_combo` or send a garbage keystroke — Tasks 3 and 5.
- Deleting the active non-Default preset must fall back to a valid state (`active` pointing at a preset that still exists) — Tasks 3 and 9.
- Rapid repeated slap motion must not machine-gun key presses — Task 5 (cooldown).

---

### Task 1: Extract shared hand-landmark geometry into `munch/hand_landmarks.py`

**Files:**
- Create: `munch/hand_landmarks.py`
- Create: `tests/test_hand_landmarks.py`
- Modify: `munch/gesture_recognizer.py:1-89` (imports + remove the now-duplicated definitions)

**Interfaces:**
- Produces: `WRIST, THUMB_IP, THUMB_TIP, INDEX_MCP, INDEX_PIP, INDEX_TIP, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP, RING_MCP, RING_PIP, RING_TIP, PINKY_MCP, PINKY_PIP, PINKY_TIP` (ints), `dist(a, b) -> float`, `palm_center(landmarks) -> (x, y)`, `finger_extended(landmarks, tip_idx, pip_idx, ratio=1.15) -> bool`, `fingers_spread(landmarks, min_spread_ratio) -> bool`, `tip_gap_ratio(landmarks, tip_a_idx, tip_b_idx) -> float`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hand_landmarks.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from munch.hand_landmarks import (
    INDEX_PIP, INDEX_TIP, MIDDLE_PIP, MIDDLE_TIP, WRIST,
    dist, finger_extended, fingers_spread, palm_center, tip_gap_ratio,
)


def _base_landmarks():
    return [(0.5, 0.9) for _ in range(21)]


def _set_finger(lm, tip_idx, pip_idx, x, extended):
    wrist = lm[WRIST]
    if extended:
        lm[pip_idx] = (x, wrist[1] - 0.25)
        lm[tip_idx] = (x, wrist[1] - 0.45)
    else:
        lm[pip_idx] = (x, wrist[1] - 0.08)
        lm[tip_idx] = (x, wrist[1] - 0.05)


class TestDist(unittest.TestCase):
    def test_basic_distance(self):
        self.assertAlmostEqual(dist((0, 0), (3, 4)), 5.0)


class TestPalmCenter(unittest.TestCase):
    def test_is_centroid_of_five_points(self):
        lm = _base_landmarks()
        lm[WRIST] = (0.0, 0.0)
        lm[5] = (1.0, 0.0)
        lm[9] = (1.0, 1.0)
        lm[13] = (0.0, 1.0)
        lm[17] = (0.5, 0.5)
        x, y = palm_center(lm)
        self.assertAlmostEqual(x, (0.0 + 1.0 + 1.0 + 0.0 + 0.5) / 5)
        self.assertAlmostEqual(y, (0.0 + 0.0 + 1.0 + 1.0 + 0.5) / 5)


class TestFingerExtended(unittest.TestCase):
    def test_extended_finger_reads_true(self):
        lm = _base_landmarks()
        _set_finger(lm, INDEX_TIP, INDEX_PIP, 0.5, extended=True)
        self.assertTrue(finger_extended(lm, INDEX_TIP, INDEX_PIP))

    def test_curled_finger_reads_false(self):
        lm = _base_landmarks()
        _set_finger(lm, INDEX_TIP, INDEX_PIP, 0.5, extended=False)
        self.assertFalse(finger_extended(lm, INDEX_TIP, INDEX_PIP))


class TestFingersSpread(unittest.TestCase):
    def test_together_tips_not_spread(self):
        lm = _base_landmarks()
        for tip, pip, x in ((8, 6, 0.50), (12, 10, 0.505), (16, 14, 0.51), (20, 18, 0.515)):
            _set_finger(lm, tip, pip, x, extended=True)
        self.assertFalse(fingers_spread(lm, min_spread_ratio=0.1))

    def test_clearly_apart_tips_are_spread(self):
        lm = _base_landmarks()
        for tip, pip, x in ((8, 6, 0.30), (12, 10, 0.45), (16, 14, 0.60), (20, 18, 0.75)):
            _set_finger(lm, tip, pip, x, extended=True)
        self.assertTrue(fingers_spread(lm, min_spread_ratio=0.1))


class TestTipGapRatio(unittest.TestCase):
    def test_together_gives_small_ratio(self):
        lm = _base_landmarks()
        _set_finger(lm, INDEX_TIP, INDEX_PIP, 0.50, extended=True)
        _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.52, extended=True)
        self.assertLess(tip_gap_ratio(lm, INDEX_TIP, MIDDLE_TIP), 0.18)

    def test_spread_gives_large_ratio(self):
        lm = _base_landmarks()
        _set_finger(lm, INDEX_TIP, INDEX_PIP, 0.50, extended=True)
        _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.65, extended=True)
        self.assertGreaterEqual(tip_gap_ratio(lm, INDEX_TIP, MIDDLE_TIP), 0.18)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_hand_landmarks.py -v`
Expected: FAIL/ERROR — `munch.hand_landmarks` doesn't exist yet.

- [ ] **Step 3: Create `munch/hand_landmarks.py`**

```python
"""Shared hand-landmark geometry primitives (MediaPipe Hands layout: 21
points, normalized x/y/z). Used by both the core gesture state machine
(gesture_recognizer.py) and the custom gesture library
(custom_gestures.py) so the two never end up with subtly different
index math over time.
"""

import math

WRIST = 0
THUMB_IP, THUMB_TIP = 3, 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_MCP, RING_PIP, RING_TIP = 13, 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20

_PALM_LANDMARKS = (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def palm_center(landmarks):
    """Centroid of the wrist + four knuckle (MCP) joints — stays stable
    while fingers articulate for a pinch, unlike a fingertip."""
    xs = sum(landmarks[i][0] for i in _PALM_LANDMARKS) / len(_PALM_LANDMARKS)
    ys = sum(landmarks[i][1] for i in _PALM_LANDMARKS) / len(_PALM_LANDMARKS)
    return xs, ys


def finger_extended(landmarks, tip_idx, pip_idx, ratio=1.15):
    wrist = landmarks[WRIST]
    tip = landmarks[tip_idx]
    pip = landmarks[pip_idx]
    return dist(wrist, tip) > dist(wrist, pip) * ratio


def fingers_spread(landmarks, min_spread_ratio):
    """True if adjacent fingertips (index-middle-ring-pinky) are clearly
    apart, not just extended-but-together."""
    hand_scale = dist(landmarks[WRIST], landmarks[MIDDLE_TIP])
    if hand_scale == 0:
        return False
    tips = (INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP)
    for a, b in zip(tips, tips[1:]):
        if dist(landmarks[a], landmarks[b]) < min_spread_ratio * hand_scale:
            return False
    return True


def tip_gap_ratio(landmarks, tip_a_idx, tip_b_idx):
    """Normalized gap between two fingertips, relative to hand size
    (wrist-to-middle-fingertip distance), so one threshold works
    regardless of how close the hand is to the camera."""
    hand_scale = dist(landmarks[WRIST], landmarks[MIDDLE_TIP])
    if hand_scale == 0:
        return 0.0
    return dist(landmarks[tip_a_idx], landmarks[tip_b_idx]) / hand_scale
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_hand_landmarks.py -v`
Expected: all PASS.

- [ ] **Step 5: Point `gesture_recognizer.py` at the extracted module**

In `munch/gesture_recognizer.py`, replace lines 1-43 (the module docstring's imports through `_finger_extended`) with:

```python
"""Gesture state machine: turns per-frame hand landmarks into mouse events.

Landmarks follow the MediaPipe Hands layout (21 points, normalized x/y/z).
Priority per frame: wake/arm pose > armed-gate > left/right/middle/double
pinch (in that order) > scroll pose > plain move — so gestures don't
fight each other, and nothing below the gate can act while MUNCH is
"watching" (disarmed).
"""

import math
import time

from munch import bindings, config, tuning
from munch import hand_landmarks as _hl
from munch.hand_landmarks import (
    INDEX_MCP, INDEX_PIP, INDEX_TIP, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP,
    PINKY_MCP, PINKY_PIP, PINKY_TIP, RING_MCP, RING_PIP, RING_TIP,
    THUMB_TIP, WRIST, palm_center,
)
from munch.hand_landmarks import dist as _dist
from munch.hand_landmarks import finger_extended as _finger_extended


def _fingers_spread(landmarks):
    return _hl.fingers_spread(landmarks, config.WAKE_MIN_SPREAD_RATIO)
```

Remove the old `_PALM_LANDMARKS`, `_dist`, `palm_center`, `_finger_extended`, and `_fingers_spread` definitions (now superseded by the import block above) — everything from `_PINCH_SOURCES = {` onward in the original file stays exactly as-is; every call site (`_dist(...)`, `_finger_extended(...)`, `_fingers_spread(landmarks)`, `palm_center(...)`, bare names like `INDEX_TIP`) keeps working unchanged because the new names resolve to the same functions/values. `gui.py`'s `from munch.gesture_recognizer import GestureRecognizer, palm_center` also keeps working unchanged, since `palm_center` is still present in `gesture_recognizer`'s module namespace via the import.

- [ ] **Step 6: Verify nothing broke**

Run: `./.venv/Scripts/python.exe -c "import munch.gesture_recognizer"`
Expected: no error.

Run: `./.venv/Scripts/python.exe -m unittest tests/test_hand_landmarks.py -v`
Expected: still all PASS (unaffected by this step, confirms no accidental edits broke it).

Launch the app (`./.venv/Scripts/python.exe main.py`) and manually confirm wake/pinch/scroll still behave exactly as before — this step only moved code, it must produce zero behavior change.

- [ ] **Step 7: Commit**

```bash
git add munch/hand_landmarks.py munch/gesture_recognizer.py tests/test_hand_landmarks.py
git commit -m "$(cat <<'EOF'
Extract hand-landmark geometry into munch/hand_landmarks.py

Pulls the primitives shared by the core gesture state machine and the
upcoming custom gesture library (OK sign, finger counts, slaps) into
one tested module instead of letting two copies drift apart.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `munch/custom_gestures.py` + new `config.py` constants

**Files:**
- Create: `munch/custom_gestures.py`
- Create: `tests/test_custom_gestures.py`
- Modify: `munch/config.py` (append new constants at end of file)

**Interfaces:**
- Consumes: `munch.hand_landmarks.{dist, finger_extended, tip_gap_ratio, INDEX_PIP, INDEX_TIP, MIDDLE_PIP, MIDDLE_TIP, PINKY_PIP, PINKY_TIP, RING_PIP, RING_TIP, THUMB_TIP}` (Task 1).
- Produces: `extended_finger_count(landmarks) -> int`, `is_ok_sign(landmarks, pinch_threshold) -> bool`, `two_finger_shape(landmarks) -> "together" | "spread" | None`, `classify_slap(history, now) -> "left" | "right" | None` (where `history` is a sequence of `(timestamp, x)` tuples, oldest first).

- [ ] **Step 1: Append the new config constants**

Append to the end of `munch/config.py`:

```python

# Custom gesture library: index-middle fingertip gap (relative to hand
# scale, like the wake-pose spread check) at/above which the shared
# index+middle-extended shape counts as a "spread" peace sign instead of
# scroll's "together" pointing shape. Starting value — expect to tune by
# feel once this is running, the same way PINCH_ON_THRESHOLD/
# SCROLL_DEADZONE originally were.
TWO_FINGER_SPREAD_RATIO = 0.18

# Slap left/right: horizontal palm-center velocity (normalized units per
# second) over a short trailing window that counts as a deliberate slap
# rather than ordinary cursor movement. Also a feel-tuned starting value.
SLAP_WINDOW_SECONDS = 0.25
SLAP_VELOCITY_THRESHOLD = 2.5
SLAP_COOLDOWN_SECONDS = 0.6  # minimum gap between two slap firings
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_custom_gestures.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from munch.custom_gestures import (
    classify_slap, extended_finger_count, is_ok_sign, two_finger_shape,
)
from munch.hand_landmarks import (
    INDEX_PIP, INDEX_TIP, MIDDLE_PIP, MIDDLE_TIP, PINKY_PIP, PINKY_TIP,
    RING_PIP, RING_TIP, THUMB_TIP, WRIST,
)


def _base_landmarks():
    return [(0.5, 0.9) for _ in range(21)]


def _set_finger(lm, tip_idx, pip_idx, x, extended):
    wrist = lm[WRIST]
    if extended:
        lm[pip_idx] = (x, wrist[1] - 0.25)
        lm[tip_idx] = (x, wrist[1] - 0.45)
    else:
        lm[pip_idx] = (x, wrist[1] - 0.08)
        lm[tip_idx] = (x, wrist[1] - 0.05)


class TestExtendedFingerCount(unittest.TestCase):
    def test_counts_only_extended_of_four(self):
        lm = _base_landmarks()
        _set_finger(lm, INDEX_TIP, INDEX_PIP, 0.50, extended=True)
        _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.54, extended=False)
        _set_finger(lm, RING_TIP, RING_PIP, 0.58, extended=True)
        _set_finger(lm, PINKY_TIP, PINKY_PIP, 0.62, extended=True)
        self.assertEqual(extended_finger_count(lm), 3)


class TestIsOkSign(unittest.TestCase):
    def test_thumb_index_touch_with_others_extended_is_ok_sign(self):
        lm = _base_landmarks()
        lm[THUMB_TIP] = (0.50, 0.60)
        lm[INDEX_TIP] = (0.505, 0.60)
        _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.54, extended=True)
        _set_finger(lm, RING_TIP, RING_PIP, 0.58, extended=True)
        _set_finger(lm, PINKY_TIP, PINKY_PIP, 0.62, extended=True)
        self.assertTrue(is_ok_sign(lm, pinch_threshold=0.055))

    def test_thumb_index_touch_with_others_curled_is_not_ok_sign(self):
        lm = _base_landmarks()
        lm[THUMB_TIP] = (0.50, 0.60)
        lm[INDEX_TIP] = (0.505, 0.60)
        _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.54, extended=False)
        _set_finger(lm, RING_TIP, RING_PIP, 0.58, extended=False)
        _set_finger(lm, PINKY_TIP, PINKY_PIP, 0.62, extended=False)
        self.assertFalse(is_ok_sign(lm, pinch_threshold=0.055))

    def test_fingers_apart_is_not_ok_sign(self):
        lm = _base_landmarks()
        lm[THUMB_TIP] = (0.30, 0.60)
        lm[INDEX_TIP] = (0.70, 0.60)
        self.assertFalse(is_ok_sign(lm, pinch_threshold=0.055))


class TestTwoFingerShape(unittest.TestCase):
    def test_together_is_scroll_shape(self):
        lm = _base_landmarks()
        _set_finger(lm, INDEX_TIP, INDEX_PIP, 0.50, extended=True)
        _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.52, extended=True)
        _set_finger(lm, RING_TIP, RING_PIP, 0.58, extended=False)
        _set_finger(lm, PINKY_TIP, PINKY_PIP, 0.62, extended=False)
        self.assertEqual(two_finger_shape(lm), "together")

    def test_spread_is_peace_shape(self):
        lm = _base_landmarks()
        _set_finger(lm, INDEX_TIP, INDEX_PIP, 0.50, extended=True)
        _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.65, extended=True)
        _set_finger(lm, RING_TIP, RING_PIP, 0.58, extended=False)
        _set_finger(lm, PINKY_TIP, PINKY_PIP, 0.62, extended=False)
        self.assertEqual(two_finger_shape(lm), "spread")

    def test_three_fingers_extended_is_neither(self):
        lm = _base_landmarks()
        _set_finger(lm, INDEX_TIP, INDEX_PIP, 0.50, extended=True)
        _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.54, extended=True)
        _set_finger(lm, RING_TIP, RING_PIP, 0.58, extended=True)
        _set_finger(lm, PINKY_TIP, PINKY_PIP, 0.62, extended=False)
        self.assertIsNone(two_finger_shape(lm))


class TestClassifySlap(unittest.TestCase):
    def test_fast_rightward_motion_is_a_right_slap(self):
        history = [(0.0, 0.30), (0.10, 0.45), (0.20, 0.60)]
        self.assertEqual(classify_slap(history, now=0.20), "right")

    def test_fast_leftward_motion_is_a_left_slap(self):
        history = [(0.0, 0.60), (0.10, 0.45), (0.20, 0.30)]
        self.assertEqual(classify_slap(history, now=0.20), "left")

    def test_slow_motion_is_not_a_slap(self):
        history = [(0.0, 0.50), (0.10, 0.51), (0.20, 0.52)]
        self.assertIsNone(classify_slap(history, now=0.20))

    def test_too_little_history_is_not_a_slap(self):
        self.assertIsNone(classify_slap([(0.20, 0.50)], now=0.20))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_custom_gestures.py -v`
Expected: FAIL/ERROR — `munch.custom_gestures` doesn't exist yet.

- [ ] **Step 4: Create `munch/custom_gestures.py`**

```python
"""Pure, stateless detectors for the optional custom-gesture library
(OK sign, finger-count holds, left/right slaps) — same hand-written
geometric technique as the core pinch/scroll detection in
gesture_recognizer.py, built on the shared primitives in
hand_landmarks.py. Slap is the one motion-based (not single-frame)
check, so it takes a short history of recent palm positions instead of
a single landmarks frame.
"""

from munch import config
from munch.hand_landmarks import (
    INDEX_PIP, INDEX_TIP, MIDDLE_PIP, MIDDLE_TIP, PINKY_PIP, PINKY_TIP,
    RING_PIP, RING_TIP, THUMB_TIP, dist, finger_extended, tip_gap_ratio,
)

_COUNT_SOURCES = (
    (INDEX_TIP, INDEX_PIP), (MIDDLE_TIP, MIDDLE_PIP),
    (RING_TIP, RING_PIP), (PINKY_TIP, PINKY_PIP),
)


def extended_finger_count(landmarks):
    """How many of index/middle/ring/pinky read as extended (thumb
    excluded, same convention as the wake pose — it moves sideways, not
    up, so the wrist-distance check doesn't translate well to it)."""
    return sum(1 for tip, pip in _COUNT_SOURCES if finger_extended(landmarks, tip, pip))


def is_ok_sign(landmarks, pinch_threshold):
    """Thumb+index tips touching (reusing the pinch distance threshold)
    with middle/ring/pinky all extended — the shape that otherwise looks
    identical to a thumb+index pinch to a distance-only check."""
    thumb = landmarks[THUMB_TIP]
    index = landmarks[INDEX_TIP]
    if dist(thumb, index) >= pinch_threshold:
        return False
    return (
        finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP)
        and finger_extended(landmarks, RING_TIP, RING_PIP)
        and finger_extended(landmarks, PINKY_TIP, PINKY_PIP)
    )


def two_finger_shape(landmarks):
    """For the index+middle-extended/ring+pinky-curled hand shape shared
    by scroll ("gun," fingers together) and the peace-sign gesture
    (fingers spread): returns "together", "spread", or None if the hand
    isn't in that base shape at all."""
    if not (
        finger_extended(landmarks, INDEX_TIP, INDEX_PIP)
        and finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP)
        and not finger_extended(landmarks, RING_TIP, RING_PIP)
        and not finger_extended(landmarks, PINKY_TIP, PINKY_PIP)
    ):
        return None
    gap = tip_gap_ratio(landmarks, INDEX_TIP, MIDDLE_TIP)
    return "spread" if gap >= config.TWO_FINGER_SPREAD_RATIO else "together"


def classify_slap(history, now):
    """`history`: a sequence of (timestamp, x) palm-center samples,
    oldest first. Looks at the horizontal displacement across whatever
    part of `history` falls within the last SLAP_WINDOW_SECONDS and
    returns "left"/"right" if the implied velocity clears
    SLAP_VELOCITY_THRESHOLD, else None."""
    window = [(t, x) for t, x in history if now - t <= config.SLAP_WINDOW_SECONDS]
    if len(window) < 2:
        return None
    t0, x0 = window[0]
    t1, x1 = window[-1]
    dt = t1 - t0
    if dt <= 0:
        return None
    velocity = (x1 - x0) / dt
    if abs(velocity) < config.SLAP_VELOCITY_THRESHOLD:
        return None
    return "right" if velocity > 0 else "left"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_custom_gestures.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add munch/custom_gestures.py munch/config.py tests/test_custom_gestures.py
git commit -m "$(cat <<'EOF'
Add custom gesture detectors: OK sign, finger counts, slap, two-finger shape

Pure geometric functions on top of hand_landmarks.py, same technique as
the existing pinch/scroll detection. Not wired into the recognizer yet.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `munch/custom_bindings.py` — binding/preset persistence

**Files:**
- Create: `munch/custom_bindings.py`
- Create: `tests/test_custom_bindings.py`

**Interfaces:**
- Produces: `GESTURES` (tuple of 7 gesture-id strings), `GESTURE_LABELS` (dict gesture-id -> human label), `DEFAULT_PRESET_NAME = "Default"`, `default_presets() -> dict`, `is_valid_combo(keys) -> bool`, `is_valid_bindings(bindings) -> bool`, `is_valid_state(state) -> bool`, `load_state() -> dict`, `save_state(state)`, `active_bindings(state) -> dict`, `format_combo(keys) -> str`.
- State shape: `{"active": "<preset name>", "presets": {"<name>": {"<gesture>": ["<key>", ...], ...}, ...}}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_custom_bindings.py`:

```python
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import munch.custom_bindings as cb


class TestValidation(unittest.TestCase):
    def test_default_presets_is_valid_state(self):
        self.assertTrue(cb.is_valid_state(cb.default_presets()))

    def test_valid_combo(self):
        self.assertTrue(cb.is_valid_combo(["ctrl", "w"]))
        self.assertTrue(cb.is_valid_combo(["n"]))

    def test_invalid_combo_rejects_empty_or_wrong_type(self):
        self.assertFalse(cb.is_valid_combo([]))
        self.assertFalse(cb.is_valid_combo("n"))
        self.assertFalse(cb.is_valid_combo([""]))

    def test_bindings_reject_unknown_gesture(self):
        self.assertFalse(cb.is_valid_bindings({"not_a_real_gesture": ["n"]}))

    def test_bindings_accept_known_gesture(self):
        self.assertTrue(cb.is_valid_bindings({"ok_sign": ["n"]}))

    def test_state_requires_active_preset_to_exist(self):
        bad = {"active": "Ghost", "presets": {"Default": {}}}
        self.assertFalse(cb.is_valid_state(bad))

    def test_state_requires_default_preset(self):
        bad = {"active": "Custom", "presets": {"Custom": {}}}
        self.assertFalse(cb.is_valid_state(bad))


class TestActiveBindings(unittest.TestCase):
    def test_returns_the_active_presets_bindings(self):
        state = {
            "active": "Anime",
            "presets": {"Default": {}, "Anime": {"ok_sign": ["n"]}},
        }
        self.assertEqual(cb.active_bindings(state), {"ok_sign": ["n"]})


class TestFormatCombo(unittest.TestCase):
    def test_joins_with_plus(self):
        self.assertEqual(cb.format_combo(["ctrl", "w"]), "ctrl+w")
        self.assertEqual(cb.format_combo(["n"]), "n")


class TestLoadSaveRoundTrip(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._orig_path = cb._PRESETS_PATH
        cb._PRESETS_PATH = self._tmp.name

    def tearDown(self):
        cb._PRESETS_PATH = self._orig_path
        os.unlink(self._tmp.name)

    def test_missing_file_returns_default(self):
        os.unlink(self._tmp.name)
        self.assertEqual(cb.load_state(), cb.default_presets())

    def test_save_then_load_round_trips(self):
        state = {
            "active": "Anime",
            "presets": {"Default": {}, "Anime": {"ok_sign": ["n"]}},
        }
        cb.save_state(state)
        self.assertEqual(cb.load_state(), state)

    def test_corrupt_file_falls_back_to_default(self):
        with open(self._tmp.name, "w") as f:
            f.write("not json")
        self.assertEqual(cb.load_state(), cb.default_presets())

    def test_invalid_state_in_file_falls_back_to_default(self):
        with open(self._tmp.name, "w") as f:
            json.dump({"active": "Ghost", "presets": {}}, f)
        self.assertEqual(cb.load_state(), cb.default_presets())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_custom_bindings.py -v`
Expected: FAIL/ERROR — `munch.custom_bindings` doesn't exist yet.

- [ ] **Step 3: Create `munch/custom_bindings.py`**

```python
"""Loads/saves custom gesture -> keyboard key/combo bindings, saved as
named presets (Default + any user-created ones). Independent of
bindings.py (the 4 mouse-click pinch permutation) — these target
arbitrary keyboard output instead, and any number can be bound at once.
"""

import json
import os

_PRESETS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "custom_presets.json")

GESTURES = ("ok_sign", "count_1", "count_3", "count_4", "peace_sign", "slap_left", "slap_right")

GESTURE_LABELS = {
    "ok_sign": "OK sign", "count_1": "1 finger up", "count_3": "3 fingers up",
    "count_4": "4 fingers up", "peace_sign": "Peace sign (spread)",
    "slap_left": "Slap left", "slap_right": "Slap right",
}

DEFAULT_PRESET_NAME = "Default"


def default_presets():
    return {"active": DEFAULT_PRESET_NAME, "presets": {DEFAULT_PRESET_NAME: {}}}


def is_valid_combo(keys):
    return isinstance(keys, list) and len(keys) >= 1 and all(isinstance(k, str) and k for k in keys)


def is_valid_bindings(bindings):
    """bindings: {gesture: [keys...]} — any subset of GESTURES, each a
    valid combo. A dict can't have a duplicate key, so "one finger used
    twice" isn't a concern here the way it is for bindings.py."""
    if not isinstance(bindings, dict):
        return False
    for gesture, keys in bindings.items():
        if gesture not in GESTURES or not is_valid_combo(keys):
            return False
    return True


def is_valid_state(state):
    if not isinstance(state, dict) or "active" not in state or "presets" not in state:
        return False
    presets = state["presets"]
    if not isinstance(presets, dict) or DEFAULT_PRESET_NAME not in presets:
        return False
    if state["active"] not in presets:
        return False
    return all(is_valid_bindings(b) for b in presets.values())


def load_state():
    try:
        with open(_PRESETS_PATH, "r") as f:
            data = json.load(f)
        if is_valid_state(data):
            return data
    except (FileNotFoundError, TypeError, json.JSONDecodeError):
        pass
    return default_presets()


def save_state(state):
    with open(_PRESETS_PATH, "w") as f:
        json.dump(state, f)


def active_bindings(state):
    """gesture -> keys list, for whichever preset is marked active."""
    return dict(state["presets"][state["active"]])


def format_combo(keys):
    return "+".join(keys)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_custom_bindings.py -v`
Expected: all PASS.

- [ ] **Step 5: Add `custom_presets.json` to `.gitignore`**

In `.gitignore`, add a line next to the existing `bindings.json`/`tuning.json` entries:

```
custom_presets.json
```

- [ ] **Step 6: Commit**

```bash
git add munch/custom_bindings.py tests/test_custom_bindings.py .gitignore
git commit -m "$(cat <<'EOF'
Add custom_bindings.py: gesture-to-key binding + preset persistence

Mirrors the existing bindings.py/tuning.py load/save pattern. Not
wired into the recognizer or Settings UI yet.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `keyboard_controller.py` — `press_combo()`

**Files:**
- Modify: `munch/keyboard_controller.py`
- Create: `tests/test_keyboard_controller.py`

**Interfaces:**
- Produces: `KeyboardController.press_combo(keys: list[str])` — holds any modifiers in `keys[:-1]`, taps `keys[-1]`, releases modifiers in reverse order.

- [ ] **Step 1: Write the failing test**

Create `tests/test_keyboard_controller.py`. This mocks `pynput`'s `Controller` so the test never sends a real OS keystroke — it only checks press/release call order.

```python
import os
import sys
import unittest
from unittest.mock import call, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPressCombo(unittest.TestCase):
    def test_single_key_presses_and_releases_it(self):
        with patch("munch.keyboard_controller.Controller") as MockController:
            mock_kb = MockController.return_value
            from munch.keyboard_controller import KeyboardController
            kc = KeyboardController()
            kc.press_combo(["n"])
            mock_kb.press.assert_called_once_with("n")
            mock_kb.release.assert_called_once_with("n")

    def test_modifier_combo_presses_modifier_then_key_then_releases_in_reverse(self):
        with patch("munch.keyboard_controller.Controller") as MockController:
            mock_kb = MockController.return_value
            from munch.keyboard_controller import KeyboardController, _SPECIAL_KEYS
            kc = KeyboardController()
            kc.press_combo(["ctrl", "w"])
            mock_kb.press.assert_has_calls([call(_SPECIAL_KEYS["ctrl"]), call("w")])
            mock_kb.release.assert_has_calls([call("w"), call(_SPECIAL_KEYS["ctrl"])])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_keyboard_controller.py -v`
Expected: FAIL — `press_combo` doesn't exist, and `_SPECIAL_KEYS` has no `"ctrl"` entry yet.

- [ ] **Step 3: Implement**

In `munch/keyboard_controller.py`, add modifier entries to `_SPECIAL_KEYS` and a new method:

```python
from pynput.keyboard import Controller, Key


class KeyboardController:
    def __init__(self):
        self._keyboard = Controller()

    def type_text(self, text):
        self._keyboard.type(text)

    def press_key(self, key_name):
        key = _SPECIAL_KEYS.get(key_name, key_name)
        self._keyboard.press(key)
        self._keyboard.release(key)

    def press_combo(self, keys):
        """keys: e.g. ["n"] or ["ctrl", "w"] (lowercase; modifiers
        first, final entry is the key to tap). Holds any modifiers,
        taps the final key, releases modifiers in reverse order."""
        resolved = [_SPECIAL_KEYS.get(k, k) for k in keys]
        *modifiers, final_key = resolved
        for mod in modifiers:
            self._keyboard.press(mod)
        self._keyboard.press(final_key)
        self._keyboard.release(final_key)
        for mod in reversed(modifiers):
            self._keyboard.release(mod)


_SPECIAL_KEYS = {
    "backspace": Key.backspace,
    "enter": Key.enter,
    "space": Key.space,
    "tab": Key.tab,
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_keyboard_controller.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add munch/keyboard_controller.py tests/test_keyboard_controller.py
git commit -m "$(cat <<'EOF'
Add KeyboardController.press_combo for modifier+key combos

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Wire the custom gesture library into `GestureRecognizer`

**Files:**
- Modify: `munch/gesture_recognizer.py`
- Create: `tests/test_gesture_recognizer_custom.py`

**Interfaces:**
- Consumes: `custom_gestures.{is_ok_sign, extended_finger_count, two_finger_shape, classify_slap}` (Task 2), `custom_bindings.{GESTURES, load_state, active_bindings, is_valid_bindings}` (Task 3).
- Produces: `GestureRecognizer.set_custom_bindings(new_bindings)`; `update()` can now return `[("key_combo", ["ctrl", "w"])]`-style events; `current_gesture` can now additionally be one of `"ok_sign", "count_1", "count_3", "count_4", "peace_sign", "slap_left", "slap_right"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gesture_recognizer_custom.py`. It drives `GestureRecognizer.update()` directly with synthetic landmark frames, the same style as the geometry tests but exercising the full state machine.

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from munch.gesture_recognizer import GestureRecognizer
from munch.hand_landmarks import (
    INDEX_PIP, INDEX_TIP, MIDDLE_PIP, MIDDLE_TIP, PINKY_PIP, PINKY_TIP,
    RING_PIP, RING_TIP, THUMB_TIP, WRIST,
)


def _base_landmarks():
    return [(0.5, 0.9) for _ in range(21)]


def _set_finger(lm, tip_idx, pip_idx, x, extended):
    wrist = lm[WRIST]
    if extended:
        lm[pip_idx] = (x, wrist[1] - 0.25)
        lm[tip_idx] = (x, wrist[1] - 0.45)
    else:
        lm[pip_idx] = (x, wrist[1] - 0.08)
        lm[tip_idx] = (x, wrist[1] - 0.05)


def _ok_sign_landmarks():
    lm = _base_landmarks()
    lm[THUMB_TIP] = (0.50, 0.60)
    lm[INDEX_TIP] = (0.505, 0.60)
    _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.54, extended=True)
    _set_finger(lm, RING_TIP, RING_PIP, 0.58, extended=True)
    _set_finger(lm, PINKY_TIP, PINKY_PIP, 0.62, extended=True)
    return lm


def _index_pinch_landmarks():
    lm = _base_landmarks()
    lm[THUMB_TIP] = (0.50, 0.60)
    lm[INDEX_TIP] = (0.505, 0.60)
    _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, 0.54, extended=False)
    _set_finger(lm, RING_TIP, RING_PIP, 0.58, extended=False)
    _set_finger(lm, PINKY_TIP, PINKY_PIP, 0.62, extended=False)
    return lm


def _open_hand_landmarks():
    lm = _base_landmarks()
    lm[THUMB_TIP] = (0.30, 0.80)
    for tip, pip, x in ((INDEX_TIP, INDEX_PIP, 0.50), (MIDDLE_TIP, MIDDLE_PIP, 0.55),
                         (RING_TIP, RING_PIP, 0.60), (PINKY_TIP, PINKY_PIP, 0.65)):
        _set_finger(lm, tip, pip, x, extended=True)
    return lm


def _run_stable(recognizer, landmarks, frames=3):
    events = []
    for _ in range(frames):
        events = recognizer.update(landmarks)
    return events


class TestOkSignVsPinch(unittest.TestCase):
    def setUp(self):
        self.recognizer = GestureRecognizer()
        self.recognizer.armed = True
        self.recognizer.set_custom_bindings({"ok_sign": ["n"]})

    def test_ok_sign_fires_key_combo_once(self):
        events = _run_stable(self.recognizer, _ok_sign_landmarks())
        self.assertIn(("key_combo", ["n"]), events)
        self.assertEqual(self.recognizer.current_gesture, "ok_sign")

    def test_holding_ok_sign_does_not_refire(self):
        _run_stable(self.recognizer, _ok_sign_landmarks())
        events = self.recognizer.update(_ok_sign_landmarks())
        self.assertNotIn(("key_combo", ["n"]), events)

    def test_release_and_reform_fires_again(self):
        _run_stable(self.recognizer, _ok_sign_landmarks())
        _run_stable(self.recognizer, _open_hand_landmarks())
        events = _run_stable(self.recognizer, _ok_sign_landmarks())
        self.assertIn(("key_combo", ["n"]), events)

    def test_normal_index_pinch_still_fires_left_click_not_blocked(self):
        for _ in range(4):
            events = self.recognizer.update(_index_pinch_landmarks())
        self.assertIn("left_pinch", self.recognizer.current_gesture)


class TestScrollVsPeace(unittest.TestCase):
    def setUp(self):
        self.recognizer = GestureRecognizer()
        self.recognizer.armed = True
        self.recognizer.set_custom_bindings({"peace_sign": ["ctrl", "w"]})

    def _two_finger_landmarks(self, middle_x):
        lm = _base_landmarks()
        _set_finger(lm, INDEX_TIP, INDEX_PIP, 0.50, extended=True)
        _set_finger(lm, MIDDLE_TIP, MIDDLE_PIP, middle_x, extended=True)
        _set_finger(lm, RING_TIP, RING_PIP, 0.58, extended=False)
        _set_finger(lm, PINKY_TIP, PINKY_PIP, 0.62, extended=False)
        return lm

    def test_together_is_scroll_not_peace(self):
        _run_stable(self.recognizer, self._two_finger_landmarks(0.52))
        self.assertEqual(self.recognizer.current_gesture, "scroll")

    def test_spread_is_peace_not_scroll(self):
        events = _run_stable(self.recognizer, self._two_finger_landmarks(0.65))
        self.assertEqual(self.recognizer.current_gesture, "peace_sign")
        self.assertIn(("key_combo", ["ctrl", "w"]), events)


class TestUnboundGestureProducesNoEvent(unittest.TestCase):
    def test_ok_sign_with_no_binding_updates_gesture_but_fires_nothing(self):
        recognizer = GestureRecognizer()
        recognizer.armed = True
        recognizer.set_custom_bindings({})
        events = _run_stable(recognizer, _ok_sign_landmarks())
        self.assertEqual(recognizer.current_gesture, "ok_sign")
        self.assertEqual(events, [])


class TestHandLostResetsLatch(unittest.TestCase):
    def test_losing_hand_mid_ok_sign_allows_refire_without_full_release(self):
        recognizer = GestureRecognizer()
        recognizer.armed = True
        recognizer.set_custom_bindings({"ok_sign": ["n"]})
        _run_stable(recognizer, _ok_sign_landmarks())
        recognizer.update(None)  # hand lost
        recognizer.armed = True  # re-arm, as a real session would via the wake pose
        events = _run_stable(recognizer, _ok_sign_landmarks())
        self.assertIn(("key_combo", ["n"]), events)


class TestSlap(unittest.TestCase):
    def test_fast_rightward_palm_motion_fires_slap_right(self):
        recognizer = GestureRecognizer()
        recognizer.armed = True
        recognizer.set_custom_bindings({"slap_right": ["ctrl", "tab"]})
        import time
        now = time.monotonic()
        recognizer._palm_history.append((now - 0.2, 0.30))
        recognizer._palm_history.append((now - 0.1, 0.45))
        events = recognizer.update(_open_hand_landmarks())
        self.assertIn(("key_combo", ["ctrl", "tab"]), events)

    def test_cooldown_prevents_immediate_refire(self):
        recognizer = GestureRecognizer()
        recognizer.armed = True
        recognizer.set_custom_bindings({"slap_right": ["ctrl", "tab"]})
        import time
        now = time.monotonic()
        recognizer._palm_history.append((now - 0.2, 0.30))
        recognizer._palm_history.append((now - 0.1, 0.45))
        first = recognizer.update(_open_hand_landmarks())
        self.assertIn(("key_combo", ["ctrl", "tab"]), first)
        second = recognizer.update(_open_hand_landmarks())
        self.assertNotIn(("key_combo", ["ctrl", "tab"]), second)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_gesture_recognizer_custom.py -v`
Expected: FAIL — `set_custom_bindings` doesn't exist, custom gestures never fire.

- [ ] **Step 3: Implement the wiring**

In `munch/gesture_recognizer.py`:

1. Add to the imports (alongside the Task 1 import block):

```python
from collections import deque

from munch import custom_bindings, custom_gestures
```

2. In `GestureRecognizer.__init__`, after `self.last_scroll_ticks = 0.0`, add:

```python
        self.custom_bindings = custom_bindings.active_bindings(custom_bindings.load_state())
        self._custom_active = {gid: False for gid in custom_bindings.GESTURES}
        self._palm_history = deque(maxlen=40)
        self._slap_cooldown_until = 0.0
```

3. In the `landmarks is None` branch at the top of `update()`, before `return events`, add:

```python
            for gid in self._custom_active:
                self._custom_active[gid] = False
            self._palm_history.clear()
```

4. In the pinch loop, add the OK-sign guard right after `state = self._pinch[action]` and before the `if state["active"]:` check:

```python
            if not state["active"] and finger == "index" and custom_gestures.is_ok_sign(landmarks, pinch_on):
                state["confirm"] = 0
                continue
```

(Placed to only affect a *forming* pinch, never an already-active drag in progress — guarded with `not state["active"]` so it's safe even though it's textually before the `if state["active"]:` branch.)

5. Replace the original scroll block —

```python
        # --- Scroll pose: index + middle extended, ring + pinky curled ---
        if (
            stable
            and _finger_extended(landmarks, INDEX_TIP, INDEX_PIP)
            and _finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP)
            and not _finger_extended(landmarks, RING_TIP, RING_PIP)
            and not _finger_extended(landmarks, PINKY_TIP, PINKY_PIP)
        ):
            self.current_gesture = "scroll"
            return self._scroll(index_tip, middle_tip)

        self.scroll_baseline_y = None
```

— with:

```python
        # --- Custom gesture library (OK sign / finger counts / peace
        # sign), one-shot: must release and re-form to fire again ---
        custom_gesture_id = None
        if stable and custom_gestures.is_ok_sign(landmarks, pinch_on):
            custom_gesture_id = "ok_sign"
        else:
            shape = custom_gestures.two_finger_shape(landmarks)
            if shape == "spread":
                custom_gesture_id = "peace_sign"
            elif stable and shape is None:
                count = custom_gestures.extended_finger_count(landmarks)
                if count in (1, 3, 4):
                    custom_gesture_id = f"count_{count}"

        if custom_gesture_id is not None:
            self.current_gesture = custom_gesture_id
            events = []
            if not self._custom_active[custom_gesture_id]:
                events = self._fire_custom_gesture(custom_gesture_id)
            for gid in self._custom_active:
                self._custom_active[gid] = gid == custom_gesture_id
            return events
        for gid in self._custom_active:
            self._custom_active[gid] = False

        # --- Scroll pose: index + middle extended, together, ring+pinky curled ---
        if stable and custom_gestures.two_finger_shape(landmarks) == "together":
            self.current_gesture = "scroll"
            return self._scroll(index_tip, middle_tip)

        self.scroll_baseline_y = None

        # --- Slap left/right: fast horizontal palm motion ---
        self._palm_history.append((now, pointer[0]))
        if now >= self._slap_cooldown_until:
            direction = custom_gestures.classify_slap(self._palm_history, now)
            if direction is not None:
                gesture_id = f"slap_{direction}"
                self.current_gesture = gesture_id
                self._slap_cooldown_until = now + config.SLAP_COOLDOWN_SECONDS
                self._palm_history.clear()
                return self._fire_custom_gesture(gesture_id)
```

6. Add two new methods, near `set_bindings`/`set_tuning`:

```python
    def set_custom_bindings(self, new_bindings):
        if custom_bindings.is_valid_bindings(new_bindings):
            self.custom_bindings = dict(new_bindings)

    def _fire_custom_gesture(self, gesture_id):
        keys = self.custom_bindings.get(gesture_id)
        if not keys:
            return []
        return [("key_combo", keys)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_gesture_recognizer_custom.py -v`
Expected: all PASS.

Run the full test suite to confirm nothing else regressed:
Run: `./.venv/Scripts/python.exe -m unittest discover -s tests -v`
Expected: all PASS.

- [ ] **Step 5: Manual smoke test**

Launch the app, arm it, and by hand confirm: normal left/right/middle/double pinch clicks and drags still work; the scroll pose (fingers together) still scrolls; forming an OK sign does *not* also fire a left-click.

- [ ] **Step 6: Commit**

```bash
git add munch/gesture_recognizer.py tests/test_gesture_recognizer_custom.py
git commit -m "$(cat <<'EOF'
Wire the custom gesture library into GestureRecognizer

OK sign, finger-count holds (1/3/4), peace-sign (spread) vs scroll
(together), and slap left/right now resolve through the active custom
preset to key_combo events, one-shot, armed-gated like every other
gesture.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: `overlay.py` — HUD tags for the new gestures

**Files:**
- Modify: `munch/overlay.py`
- Create: `tests/test_overlay_gesture_styles.py`

**Interfaces:**
- Consumes: `custom_bindings.GESTURES` (Task 3).
- Produces: `GESTURE_STYLES` gains one entry per new gesture id.

- [ ] **Step 1: Write the failing test**

Create `tests/test_overlay_gesture_styles.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from munch.custom_bindings import GESTURES
from munch.overlay import GESTURE_STYLES


class TestGestureStylesCoverage(unittest.TestCase):
    def test_every_custom_gesture_has_a_hud_style(self):
        missing = [g for g in GESTURES if g not in GESTURE_STYLES]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_overlay_gesture_styles.py -v`
Expected: FAIL — the 7 new gesture ids aren't in `GESTURE_STYLES` yet.

- [ ] **Step 3: Implement**

In `munch/overlay.py`, extend `GESTURE_STYLES`:

```python
GESTURE_STYLES = {
    "armed": ("ARMED", GREEN),
    "left_pinch": ("CLICK", "#FF3DAE"),
    "drag": ("DRAGGING", GREEN),
    "right_pinch": ("RIGHT CLICK", PURPLE),
    "right_drag": ("RIGHT DRAG", PURPLE),
    "middle_pinch": ("MIDDLE CLICK", "#3A86FF"),
    "middle_drag": ("MIDDLE DRAG", "#3A86FF"),
    "double_pinch": ("DOUBLE CLICK", YELLOW),
    "scroll": ("SCROLLING", "#3A86FF"),
    "ok_sign": ("OK SIGN", GREEN),
    "count_1": ("1", YELLOW),
    "count_3": ("3", YELLOW),
    "count_4": ("4", YELLOW),
    "peace_sign": ("PEACE", YELLOW),
    "slap_left": ("SLAP ←", PURPLE),
    "slap_right": ("SLAP →", PURPLE),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m unittest tests/test_overlay_gesture_styles.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add munch/overlay.py tests/test_overlay_gesture_styles.py
git commit -m "$(cat <<'EOF'
Add cursor-HUD tags for the new custom gestures

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: `gui.py` — dispatch `key_combo` events

**Files:**
- Modify: `munch/gui.py:396-402`

**Interfaces:**
- Consumes: `self.keyboard.press_combo(keys)` (Task 4), the `("key_combo", keys)` event kind (Task 5).

- [ ] **Step 1: Implement**

In `munch/gui.py`, in `_loop()`, change:

```python
                elif self.munch_on:
                    self.mouse.handle_events(events)
```

to:

```python
                elif self.munch_on:
                    self.mouse.handle_events(events)
                    for event in events:
                        if event[0] == "key_combo":
                            self.keyboard.press_combo(event[1])
```

- [ ] **Step 2: Manual verification**

This is pure GUI wiring (the existing codebase has no automated tests for `gui.py`, consistent with everything else in it). Launch the app, arm it, bind a custom gesture to a key in Settings once Task 9 lands, and confirm the keystroke reaches a focused external app (e.g. Notepad). Since Task 9 (the UI to actually create a binding) hasn't landed yet at this point in the plan, defer the live check to after Task 9 — for now, confirm only that the app still launches and runs with no exception (nothing in this change can run without a bound custom gesture, which doesn't exist until Task 9).

Run: `./.venv/Scripts/python.exe main.py` (launch, confirm no crash, close).

- [ ] **Step 3: Commit**

```bash
git add munch/gui.py
git commit -m "$(cat <<'EOF'
Dispatch key_combo gesture events to the keyboard controller

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: `cheat_sheet.py` — list active custom bindings, clarify scroll wording

**Files:**
- Modify: `munch/cheat_sheet.py`

**Interfaces:**
- Consumes: `custom_bindings.{load_state, active_bindings, GESTURE_LABELS, format_combo}` (Task 3).

- [ ] **Step 1: Implement**

In `munch/cheat_sheet.py`, add the import:

```python
from munch import custom_bindings as custom_bindings_module
```

Update the scroll hint text (it currently only explains "point like a remote, not at the camera" — now also explain the together/spread split) and append a custom-gestures section. Replace:

```python
        self._row("Scroll", "Index + middle extended, move hand")
        self._hint(
            "Hold fingers up like a remote, level with the camera — not "
            "pointed at it. Tilt down to scroll down, up to scroll up."
        )
        self._row("Wake / arm", "Open palm, spread, hold ~2s")
        self._row("Disarm", "Hand leaves frame")
```

with:

```python
        self._row("Scroll", "Index + middle extended, together")
        self._hint(
            "Hold fingers up like a remote, level with the camera — not "
            "pointed at it. Keep index and middle together, like pointing "
            "a gun, to scroll; tilt down to scroll down, up to scroll up. "
            "Spread them apart for the peace-sign gesture instead."
        )
        self._row("Wake / arm", "Open palm, spread, hold ~2s")
        self._row("Disarm", "Hand leaves frame")

        custom_state = custom_bindings_module.load_state()
        active = custom_bindings_module.active_bindings(custom_state)
        if active:
            tk.Label(self.win, text="CUSTOM GESTURES", font=FONT_HEADING, bg=BG, fg=INK).pack(
                anchor="w", padx=16, pady=(14, 6)
            )
            for gesture, keys in active.items():
                self._row(
                    custom_bindings_module.GESTURE_LABELS[gesture],
                    custom_bindings_module.format_combo(keys),
                )
```

- [ ] **Step 2: Manual verification**

Launch the app, open the cheat sheet, confirm it renders without error and the scroll hint/custom-gestures section look right (the custom-gestures section won't show anything yet since no bindings exist until Task 9 is used).

Run: `./.venv/Scripts/python.exe main.py`

- [ ] **Step 3: Commit**

```bash
git add munch/cheat_sheet.py
git commit -m "$(cat <<'EOF'
List active custom gesture bindings in the cheat sheet; clarify scroll wording

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: `settings_window.py` — "CUSTOM GESTURES" section

**Files:**
- Modify: `munch/settings_window.py`

**Interfaces:**
- Consumes: `custom_bindings.{GESTURES, GESTURE_LABELS, DEFAULT_PRESET_NAME, load_state, save_state, active_bindings, is_valid_bindings}` (Task 3), `recognizer.set_custom_bindings(...)` (Task 5), `RoundedButton`, `hover_tint` (`munch/widgets.py`).

- [ ] **Step 1: Add the import**

In `munch/settings_window.py`, add:

```python
from munch import custom_bindings as custom_bindings_module
```

- [ ] **Step 2: Factor the existing inline popup into a shared helper**

Replace `_dropdown_row`'s body (it currently builds its own popup inline) with a call to a new shared `_popup_choice_list` method, so the preset/gesture pickers added in this task can reuse it instead of duplicating the popup-construction code:

```python
    def _dropdown_row(self, label_text, options, initial_value, on_select):
        """A label + a fully custom dropdown. tk.Menu's popup renders via
        the native Win32 menu control on Windows regardless of what bg/fg
        colors are set on it — the only way to actually theme the popup
        list is to not use a real menu at all, and draw our own borderless
        Toplevel full of styled rows instead."""
        row = tk.Frame(self.win, bg=BG)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text=label_text, font=FONT_LABEL, bg=BG, fg=INK,
                 width=_ROW_LABEL_WIDTH, anchor="w").pack(side="left")

        btn = tk.Label(
            row, text=initial_value + _DROPDOWN_ARROW, font=FONT_VALUE, bg="white", fg=INK,
            anchor="w", padx=8, pady=4, cursor="hand2",
        )
        _bordered(btn)
        btn.pack(side="left", fill="x", expand=True)

        def choose(option):
            btn.configure(text=option + _DROPDOWN_ARROW)
            on_select(option)

        btn.bind("<Button-1>", lambda _e: self._popup_choice_list(btn, options, choose))
        return btn

    def _popup_choice_list(self, anchor_widget, options, on_choose):
        """Borderless-popup list anchored under `anchor_widget` — shared
        by the finger/camera dropdowns, the preset picker, and the
        per-row gesture picker."""
        if self._active_popup is not None:
            self._close_popup()

        anchor_widget.update_idletasks()
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        width = max(anchor_widget.winfo_width(), 140)

        popup = tk.Toplevel(self.win)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=INK)

        inner = tk.Frame(popup, bg="white")
        inner.pack(padx=2, pady=2)
        for option in options:
            option_row = tk.Label(
                inner, text=option, font=FONT_VALUE, bg="white", fg=INK,
                anchor="w", padx=8, pady=6, cursor="hand2", width=max(width // 7, 16),
            )
            option_row.pack(fill="x")
            option_row.bind("<Enter>", lambda _e, w=option_row: w.configure(bg=YELLOW))
            option_row.bind("<Leave>", lambda _e, w=option_row: w.configure(bg="white"))
            option_row.bind("<Button-1>", lambda _e, o=option: (self._close_popup(), on_choose(o)))

        popup.geometry(f"+{x}+{y}")
        popup.bind("<FocusOut>", lambda _e: self._close_popup())
        popup.focus_force()
        self._active_popup = popup
```

(This drops the old toggle-closed-on-second-click-of-the-same-button nuance in favor of always reopening fresh — a minor, acceptable simplification, not a regression in anything that matters.) Delete the old inline `open_popup` function and its body from `_dropdown_row` entirely — `_popup_choice_list` now owns that logic.

- [ ] **Step 3: Add the `_KeyCapture` widget**

Add this class near `_SliderWidget` (top of the file, module level):

```python
class _KeyCapture:
    """A "click to set key" field — captures the next real key/modifier
    combo pressed anywhere in the Settings window, via KeyPress (and
    tracking modifier KeyPress/Release separately, rather than relying
    on event.state's platform-specific bitmask) so it works for both a
    lone key and a held-modifier combo."""

    _MODIFIER_KEYSYMS = {
        "Control_L": "ctrl", "Control_R": "ctrl",
        "Alt_L": "alt", "Alt_R": "alt",
        "Shift_L": "shift", "Shift_R": "shift",
    }

    def __init__(self, parent, window, initial_keys, on_change):
        self._window = window
        self._on_change = on_change
        self._listening = False
        self._held_modifiers = []

        self.label = tk.Label(
            parent, text=self._format(initial_keys), font=FONT_VALUE, bg="white", fg=INK,
            anchor="w", padx=8, pady=4, cursor="hand2",
        )
        _bordered(self.label)
        self.label.bind("<Button-1>", self._start_listening)

    def _format(self, keys):
        return "+".join(keys) if keys else "Click to set key..."

    def _start_listening(self, _event=None):
        if self._listening:
            return
        self._listening = True
        self._held_modifiers = []
        self.label.configure(text="Press keys...", bg=YELLOW)
        self._window.bind("<KeyPress>", self._on_key_press)

    def _on_key_press(self, event):
        keysym = event.keysym
        if keysym in self._MODIFIER_KEYSYMS:
            name = self._MODIFIER_KEYSYMS[keysym]
            if name not in self._held_modifiers:
                self._held_modifiers.append(name)
            return
        key = keysym.lower()
        combo = self._held_modifiers + [key]
        self._listening = False
        self._window.unbind("<KeyPress>")
        self.label.configure(text=self._format(combo), bg="white")
        self._on_change(combo)

    def pack(self, **kwargs):
        self.label.pack(**kwargs)
```

- [ ] **Step 4: Add the section to `SettingsWindow.__init__`**

After the existing `CALIBRATE` button's `.pack(...)` call (the last line of the current `__init__`), append:

```python
        self._custom_state = custom_bindings_module.load_state()

        tk.Label(self.win, text="CUSTOM GESTURES", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        preset_row = tk.Frame(self.win, bg=BG)
        preset_row.pack(fill="x", padx=16, pady=4)
        tk.Label(preset_row, text="Preset", font=FONT_LABEL, bg=BG, fg=INK,
                 width=_ROW_LABEL_WIDTH, anchor="w").pack(side="left")
        self._preset_btn = tk.Label(
            preset_row, text=self._custom_state["active"] + _DROPDOWN_ARROW, font=FONT_VALUE,
            bg="white", fg=INK, anchor="w", padx=8, pady=4, cursor="hand2",
        )
        _bordered(self._preset_btn)
        self._preset_btn.pack(side="left", fill="x", expand=True)
        self._preset_btn.bind("<Button-1>", lambda _e: self._open_preset_popup())

        preset_actions = tk.Frame(self.win, bg=BG)
        preset_actions.pack(fill="x", padx=16, pady=(0, 10))
        RoundedButton(
            preset_actions, 110, 28, color="#DDDDDD", on_click=self._save_as_preset,
            text="SAVE AS NEW", font=("Segoe UI", 9, "bold"), bg=BG,
        ).pack(side="left", padx=(0, 6))
        RoundedButton(
            preset_actions, 90, 28, color="#DDDDDD", on_click=self._delete_preset,
            text="DELETE", font=("Segoe UI", 9, "bold"), bg=BG,
        ).pack(side="left")

        self._binding_rows_frame = tk.Frame(self.win, bg=BG)
        self._binding_rows_frame.pack(fill="x")
        self._rebuild_binding_rows()

        RoundedButton(
            self.win, btn_width, 30, color="#DDDDDD", on_click=self._add_binding_row,
            text="+ ADD BINDING", font=FONT_BUTTON, bg=BG,
        ).pack(padx=16, pady=(4, 18))
```

- [ ] **Step 5: Add the supporting methods**

Add these methods to `SettingsWindow`:

```python
    def _active_bindings(self):
        return self._custom_state["presets"][self._custom_state["active"]]

    def _rebuild_binding_rows(self):
        for child in self._binding_rows_frame.winfo_children():
            child.destroy()
        for gesture, keys in self._active_bindings().items():
            self._binding_row(gesture, keys)

    def _binding_row(self, gesture, keys):
        row = tk.Frame(self._binding_rows_frame, bg=BG)
        row.pack(fill="x", padx=16, pady=4)

        gesture_btn = tk.Label(
            row, text=custom_bindings_module.GESTURE_LABELS[gesture] + _DROPDOWN_ARROW,
            font=FONT_VALUE, bg="white", fg=INK, anchor="w", padx=8, pady=4,
            cursor="hand2", width=16,
        )
        _bordered(gesture_btn)
        gesture_btn.pack(side="left", padx=(0, 6))
        gesture_btn.bind("<Button-1>", lambda _e, g=gesture, b=gesture_btn: self._open_gesture_popup(g, b))

        capture = _KeyCapture(row, self.win, keys, lambda new_keys, g=gesture: self._on_key_change(g, new_keys))
        capture.pack(side="left", fill="x", expand=True, padx=(0, 6))

        remove_btn = tk.Label(
            row, text="×", font=("Segoe UI", 12, "bold"), bg=BG, fg=INK, cursor="hand2", padx=6,
        )
        remove_btn.pack(side="left")
        remove_btn.bind("<Button-1>", lambda _e, g=gesture: self._remove_binding(g))

    def _unused_gestures(self):
        used = set(self._active_bindings().keys())
        return [g for g in custom_bindings_module.GESTURES if g not in used]

    def _add_binding_row(self):
        available = self._unused_gestures()
        if not available:
            return
        self._active_bindings()[available[0]] = []
        self._rebuild_binding_rows()

    def _remove_binding(self, gesture):
        self._active_bindings().pop(gesture, None)
        self._apply_custom_bindings()
        self._rebuild_binding_rows()

    def _open_gesture_popup(self, gesture, anchor_widget):
        choices = [custom_bindings_module.GESTURE_LABELS[g] for g in self._unused_gestures()]
        current_label = custom_bindings_module.GESTURE_LABELS[gesture]
        if current_label not in choices:
            choices = [current_label] + choices

        def choose(label):
            new_gesture = next(
                g for g, l in custom_bindings_module.GESTURE_LABELS.items() if l == label
            )
            if new_gesture == gesture:
                return
            bindings_dict = self._active_bindings()
            bindings_dict[new_gesture] = bindings_dict.pop(gesture, [])
            self._apply_custom_bindings()
            self._rebuild_binding_rows()

        self._popup_choice_list(anchor_widget, choices, choose)

    def _on_key_change(self, gesture, keys):
        self._active_bindings()[gesture] = keys
        self._apply_custom_bindings()

    def _apply_custom_bindings(self):
        active = custom_bindings_module.active_bindings(self._custom_state)
        self.recognizer.set_custom_bindings(active)
        custom_bindings_module.save_state(self._custom_state)

    def _open_preset_popup(self):
        names = list(self._custom_state["presets"].keys())

        def choose(name):
            self._custom_state["active"] = name
            self._preset_btn.configure(text=name + _DROPDOWN_ARROW)
            self._apply_custom_bindings()
            self._rebuild_binding_rows()

        self._popup_choice_list(self._preset_btn, names, choose)

    def _save_as_preset(self):
        self._prompt_name("New preset name:", self._create_preset)

    def _create_preset(self, name):
        name = name.strip()
        if not name or name in self._custom_state["presets"]:
            return
        self._custom_state["presets"][name] = dict(self._active_bindings())
        self._custom_state["active"] = name
        self._preset_btn.configure(text=name + _DROPDOWN_ARROW)
        self._apply_custom_bindings()
        self._rebuild_binding_rows()

    def _delete_preset(self):
        name = self._custom_state["active"]
        if name == custom_bindings_module.DEFAULT_PRESET_NAME:
            return
        del self._custom_state["presets"][name]
        self._custom_state["active"] = custom_bindings_module.DEFAULT_PRESET_NAME
        self._preset_btn.configure(text=self._custom_state["active"] + _DROPDOWN_ARROW)
        self._apply_custom_bindings()
        self._rebuild_binding_rows()

    def _prompt_name(self, label_text, on_submit):
        win = tk.Toplevel(self.win)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=INK)
        inner = tk.Frame(win, bg=BG)
        inner.pack(padx=2, pady=2)
        tk.Label(inner, text=label_text, font=FONT_LABEL, bg=BG, fg=INK).pack(
            anchor="w", padx=10, pady=(10, 4)
        )
        entry = tk.Entry(inner, font=FONT_VALUE, bg="white", fg=INK, highlightbackground=INK,
                          highlightthickness=1, width=24)
        entry.pack(padx=10, pady=(0, 10))
        entry.focus_set()

        def submit(_event=None):
            value = entry.get()
            win.destroy()
            on_submit(value)

        entry.bind("<Return>", submit)
        RoundedButton(inner, 80, 26, color="#DDDDDD", on_click=submit, text="OK",
                      font=("Segoe UI", 9, "bold"), bg=BG).pack(pady=(0, 10))
        x = self.win.winfo_rootx() + 60
        y = self.win.winfo_rooty() + 60
        win.geometry(f"+{x}+{y}")
```

- [ ] **Step 6: Also close the preset/gesture/key-capture popups on Settings close**

`SettingsWindow.close()` already calls `self._close_popup()` — no change needed there (it already handles any one active `_active_popup`, which the preset and gesture pickers both use via `_popup_choice_list`).

- [ ] **Step 7: Manual verification**

Launch the app: `./.venv/Scripts/python.exe main.py`. Open Settings, confirm the CUSTOM GESTURES section renders. Click "+ ADD BINDING", confirm a new row appears with an unused gesture pre-selected. Click the key-capture field, press "Ctrl+W", confirm it renders as "ctrl+w". Change the gesture dropdown on that row, confirm it swaps. Click "SAVE AS NEW", type a name, confirm a new preset is created and selected. Switch back to "Default" via the preset dropdown, confirm its (empty) bindings show. Arm MUNCH, form an OK sign (bound to a real key in your test preset), confirm the keystroke lands in a focused Notepad window. Restart the app, confirm the binding/preset persisted.

- [ ] **Step 8: Commit**

```bash
git add munch/settings_window.py
git commit -m "$(cat <<'EOF'
Add CUSTOM GESTURES section to Settings: bindings, key capture, presets

Factors the dropdown popup into a shared _popup_choice_list helper
(also used for the new preset/gesture pickers) instead of duplicating
it a third time.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Final full-suite check

After Task 9, run the complete automated test suite once more:

Run: `./.venv/Scripts/python.exe -m unittest discover -s tests -v`
Expected: all PASS.
