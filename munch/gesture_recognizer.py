"""Gesture state machine: turns per-frame hand landmarks into mouse events.

Landmarks follow the MediaPipe Hands layout (21 points, normalized x/y/z).
Priority per frame: wake/arm pose > armed-gate > left/right/middle/double
pinch (in that order) > scroll pose > plain move — so gestures don't
fight each other, and nothing below the gate can act while MUNCH is
"watching" (disarmed).
"""

import time
from collections import deque

from munch import bindings, config, custom_bindings, custom_gestures, tuning
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


_PINCH_SOURCES = {
    "index": (INDEX_TIP, INDEX_PIP),
    "middle": (MIDDLE_TIP, MIDDLE_PIP),
    "ring": (RING_TIP, RING_PIP),
    "pinky": (PINKY_TIP, PINKY_PIP),
}

# Processing order each frame — matters only when more than one pinch
# distance happens to be close in the same frame (e.g. mid hand-shape
# transition); first-in-order wins. "double" has no hold-to-drag
# behavior (a held double-click has no OS equivalent), so it's a plain
# quick-pinch-only action.
_ACTION_PRIORITY = ("left", "right", "middle", "double")
_DRAG_CAPABLE_ACTIONS = {"left", "right", "middle"}

# Hysteresis gap between the (tunable) pinch-on threshold and the
# pinch-off threshold, preserved from the original fixed 0.055/0.075 pair
# so adjusting sensitivity doesn't also need a second slider just to keep
# the anti-flicker gap sane.
_PINCH_HYSTERESIS_GAP = config.PINCH_OFF_THRESHOLD - config.PINCH_ON_THRESHOLD


def _pinch_gesture_name(action):
    return f"{action}_pinch"


def _drag_gesture_name(action):
    return "drag" if action == "left" else f"{action}_drag"  # "drag" kept for the original left-drag name


class GestureRecognizer:
    def __init__(self):
        self.bindings = bindings.load_bindings()  # {action: finger}, one finger per action
        self.tuning = tuning.load_tuning()  # cursor_smoothing_alpha, drag_hold_seconds, pinch_on_threshold

        # Per-action pinch state: active (currently pinched), start (when
        # the pinch began, for drag-hold timing), dragging (crossed the
        # hold threshold), confirm (consecutive close-distance frames
        # before a pinch-down is trusted — see PINCH_CONFIRM_FRAMES).
        self._pinch = {
            action: {"active": False, "start": 0.0, "dragging": False, "confirm": 0}
            for action in bindings.ACTIONS
        }

        self.scroll_baseline_y = None
        self.last_scroll_ticks = 0.0  # sign of the last scroll tick, for live direction feedback

        self.custom_bindings = custom_bindings.active_bindings(custom_bindings.load_state())
        self._custom_active = {gid: False for gid in custom_bindings.GESTURES}
        self._palm_history = deque(maxlen=40)
        self._slap_cooldown_until = 0.0

        self.current_gesture = "idle"

        # Consecutive frames the hand has been continuously seen. Used to
        # debounce brand-new gesture starts (pinch-down, entering scroll
        # pose) for the first couple of frames after the hand (re)appears,
        # since landmarks are least reliable right as the hand enters frame
        # or crosses the edge — without this, that instability can register
        # as a spurious click/scroll.
        self._hand_streak = 0

        # Wake/arm gesture: MUNCH starts every session "watching" (disarmed)
        # and ignores the hand entirely until an open palm is held for
        # ARM_HOLD_SECONDS. Holding it again while armed disarms. This is
        # the core fix for a hand just passing through frame (eating,
        # skincare) being misread as input.
        self.armed = False
        self._wake_last_time = None
        self.wake_progress = 0.0  # 0-1 fill while holding the wake pose, for a progress-ring UI

    def update(self, landmarks, bypass_arm=False):
        """Returns a list of events for this frame, e.g.:
        [("move", x, y)], [("left_down",)], [("left_up",)], [("left_click",)],
        [("right_down",)], [("right_up",)], [("right_click",)],
        [("middle_down",)], [("middle_up",)], [("middle_click",)],
        [("double_click",)], [("scroll", ticks)]

        bypass_arm=True skips the armed-gate for this call (used during
        calibration, which is already a deliberate, hands-on flow).
        """
        if landmarks is None:
            self._hand_streak = 0
            for state in self._pinch.values():
                state["confirm"] = 0
            self._wake_last_time = None
            self.wake_progress = 0.0
            self.armed = False
            events = self._release_held_buttons()
            for gid in self._custom_active:
                self._custom_active[gid] = False
            self._palm_history.clear()
            self.current_gesture = "idle"
            return events

        self._hand_streak += 1
        stable = self._hand_streak >= config.HAND_STABLE_FRAMES

        now = time.monotonic()
        thumb = landmarks[THUMB_TIP]
        index_tip = landmarks[INDEX_TIP]
        middle_tip = landmarks[MIDDLE_TIP]
        pointer = palm_center(landmarks)

        # --- Wake/arm gesture: open palm held briefly arms. Only checked
        # while disarmed — once armed, holding/re-showing the palm is
        # ignored, otherwise just keeping your hand open would arm, wait,
        # disarm, arm, disarm... every ARM_HOLD_SECONDS forever. Disarming
        # happens only via hand-lost (or stopping MUNCH mode).
        if not self.armed:
            ratio = config.WAKE_EXTEND_RATIO
            is_open_palm = (
                _finger_extended(landmarks, INDEX_TIP, INDEX_PIP, ratio)
                and _finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP, ratio)
                and _finger_extended(landmarks, RING_TIP, RING_PIP, ratio)
                and _finger_extended(landmarks, PINKY_TIP, PINKY_PIP, ratio)
                and _fingers_spread(landmarks)
            )
            any_pinch_active = any(state["active"] for state in self._pinch.values())
            holding = stable and is_open_palm and not any_pinch_active

            dt = (now - self._wake_last_time) if self._wake_last_time is not None else 0.0
            self._wake_last_time = now

            if holding:
                self.wake_progress = min(1.0, self.wake_progress + dt / config.ARM_HOLD_SECONDS)
                if self.wake_progress >= 1.0:
                    self.armed = True
                    self.wake_progress = 0.0
                    self.current_gesture = "armed"
                    return []
                self.current_gesture = "wake_hold"
                return []
            else:
                # Pose broke before completing — drain progress back down
                # (faster than it filled) instead of snapping to zero, so
                # briefly losing the pose doesn't feel like starting over
                # from scratch.
                self.wake_progress = max(0.0, self.wake_progress - dt / config.ARM_DRAIN_SECONDS)
                if self.wake_progress > 0.0:
                    self.current_gesture = "wake_hold"
                    return []

        if not (self.armed or bypass_arm):
            self.current_gesture = "idle"
            return []

        self._palm_history.append((now, pointer[0]))

        # --- Pinch actions (left/right/middle click, double-click) ---
        pinch_on = self.tuning["pinch_on_threshold"]
        pinch_off = pinch_on + _PINCH_HYSTERESIS_GAP
        for action in _ACTION_PRIORITY:
            finger = self.bindings[action]
            tip, pip = _PINCH_SOURCES[finger]
            dist = _dist(thumb, landmarks[tip])
            state = self._pinch[action]

            if not state["active"] and finger == "index" and custom_gestures.is_ok_sign(landmarks, pinch_on):
                state["confirm"] = 0
                continue

            if state["active"]:
                if dist > pinch_off:
                    events = self._release_pinch(action)
                elif action in _DRAG_CAPABLE_ACTIONS:
                    events = self._hold_pinch(action, now, pointer)
                else:
                    events = []
                self.current_gesture = (
                    _drag_gesture_name(action) if state["dragging"] else _pinch_gesture_name(action)
                )
                return events

            # A real pinch curls the touching finger toward the thumb, so
            # it's no longer "extended" by the time it touches — this
            # distinguishes it from the scroll pose's fully-extended
            # index/middle.
            approaching = (
                stable and dist < pinch_on and not _finger_extended(landmarks, tip, pip)
            )
            state["confirm"] = state["confirm"] + 1 if approaching else 0

            if state["confirm"] >= config.PINCH_CONFIRM_FRAMES:
                state["active"] = True
                state["start"] = now
                state["dragging"] = False
                state["confirm"] = 0
                self.current_gesture = _pinch_gesture_name(action)
                return []

        # --- Slap left/right: fast horizontal palm motion. Checked
        # before the static custom-gesture poses below because slap and
        # the open-hand "count_4" pose share the same instantaneous hand
        # shape — the only real distinguishing signal is velocity, so a
        # fast-moving hand should always read as a slap attempt, never
        # as someone unrealistically holding a mid-swipe pose still.
        if now >= self._slap_cooldown_until:
            direction = custom_gestures.classify_slap(self._palm_history, now)
            if direction is not None:
                gesture_id = f"slap_{direction}"
                self.current_gesture = gesture_id
                self._slap_cooldown_until = now + config.SLAP_COOLDOWN_SECONDS
                self._palm_history.clear()
                for gid in self._custom_active:
                    self._custom_active[gid] = False
                return self._fire_custom_gesture(gesture_id)

        # --- Custom gesture library (OK sign / finger counts / peace
        # sign), one-shot: must release and re-form to fire again. Only
        # claims the frame (blocking normal cursor movement) when the
        # gesture actually has a key bound — an unbound pose still
        # updates current_gesture for HUD/cheat-sheet feedback, but
        # must not freeze the cursor for users with no custom bindings
        # configured, since count_1/count_4 in particular are natural,
        # unremarkable hand shapes to be moving the cursor with.
        custom_gesture_id = None
        if stable and custom_gestures.is_ok_sign(landmarks, pinch_on):
            custom_gesture_id = "ok_sign"
        else:
            shape = custom_gestures.two_finger_shape(landmarks)
            if stable and shape == "spread":
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
            if self.custom_bindings.get(custom_gesture_id):
                return events
            return [("move", pointer[0], pointer[1])]
        for gid in self._custom_active:
            self._custom_active[gid] = False

        # --- Scroll pose: index + middle extended, together, ring+pinky curled ---
        if stable and custom_gestures.two_finger_shape(landmarks) == "together":
            self.current_gesture = "scroll"
            return self._scroll(index_tip, middle_tip)

        self.scroll_baseline_y = None

        # --- Plain move ---
        self.current_gesture = "move"
        return [("move", pointer[0], pointer[1])]

    def _hold_pinch(self, action, now, pointer):
        state = self._pinch[action]
        events = []
        if not state["dragging"] and (now - state["start"]) >= self.tuning["drag_hold_seconds"]:
            state["dragging"] = True
            events.append((f"{action}_down",))
        if state["dragging"]:
            events.append(("move", pointer[0], pointer[1]))
        return events

    def _release_pinch(self, action):
        state = self._pinch[action]
        events = []
        if state["dragging"]:
            events.append((f"{action}_up",))
        else:
            events.append((f"{action}_click",))
        state["active"] = False
        state["dragging"] = False
        return events

    def _scroll(self, index_tip, middle_tip):
        current_y = (index_tip[1] + middle_tip[1]) / 2.0
        if self.scroll_baseline_y is None:
            self.scroll_baseline_y = current_y
            return []

        offset = current_y - self.scroll_baseline_y  # positive = hand moved down
        magnitude = abs(offset) - config.SCROLL_DEADZONE
        if magnitude <= 0:
            return []

        speed = min(magnitude * config.SCROLL_SPEED_SCALE, config.SCROLL_MAX_SPEED)
        direction = 1.0 if offset > 0 else -1.0
        ticks = -direction * speed  # moving hand down -> scroll down (negative ticks)
        self.last_scroll_ticks = ticks
        return [("scroll", ticks)]

    def set_bindings(self, new_bindings):
        if bindings.is_valid(new_bindings):
            self.bindings = dict(new_bindings)

    def set_tuning(self, new_tuning):
        if tuning.is_valid(new_tuning):
            self.tuning = dict(new_tuning)

    def set_custom_bindings(self, new_bindings):
        if custom_bindings.is_valid_bindings(new_bindings):
            self.custom_bindings = dict(new_bindings)

    def _fire_custom_gesture(self, gesture_id):
        keys = self.custom_bindings.get(gesture_id)
        if not keys:
            return []
        return [("key_combo", keys)]

    def reset_wake(self):
        """Force back to disarmed/watching with a clean slate. Used when
        MUNCH mode is toggled off/on, so a stale `_wake_last_time` from
        before the pause can't produce a huge dt on the next frame (which
        would instantly fill the progress ring if a palm happened to be
        showing already)."""
        self.armed = False
        self.wake_progress = 0.0
        self._wake_last_time = None

    def _release_held_buttons(self):
        """Hand lost mid-gesture, or disarmed mid-gesture: release any
        physically-held mouse button instead of silently dropping the state
        (which would otherwise leave the button stuck down). A pinch that
        hadn't become a drag yet is just dropped — no click fires, which is
        correct since it never completed a press-and-release."""
        events = []
        for action, state in self._pinch.items():
            if state["active"] and state["dragging"]:
                events.append((f"{action}_up",))
            state["active"] = False
            state["dragging"] = False

        self.scroll_baseline_y = None
        return events
