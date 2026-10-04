"""Gesture state machine: turns per-frame hand landmarks into mouse events.

Landmarks follow the MediaPipe Hands layout (21 points, normalized x/y/z).
Priority per frame: wake/arm pose > armed-gate > left pinch > right pinch >
scroll pose > plain move — so gestures don't fight each other, and nothing
below the gate can act while MUNCH is "watching" (disarmed).
"""

import math
import time

from munch import bindings, config

WRIST = 0
THUMB_IP, THUMB_TIP = 3, 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_MCP, RING_PIP, RING_TIP = 13, 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20

_PALM_LANDMARKS = (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def palm_center(landmarks):
    """Centroid of the wrist + four knuckle (MCP) joints — stays stable
    while fingers articulate for a pinch, unlike a fingertip. Used to
    drive cursor position so clicking doesn't flick the cursor off-target
    (pinch/click detection stays fingertip-based, fully decoupled)."""
    xs = sum(landmarks[i][0] for i in _PALM_LANDMARKS) / len(_PALM_LANDMARKS)
    ys = sum(landmarks[i][1] for i in _PALM_LANDMARKS) / len(_PALM_LANDMARKS)
    return xs, ys


def _finger_extended(landmarks, tip_idx, pip_idx, ratio=1.15):
    wrist = landmarks[WRIST]
    tip = landmarks[tip_idx]
    pip = landmarks[pip_idx]
    return _dist(wrist, tip) > _dist(wrist, pip) * ratio


_PINCH_SOURCES = {
    "index": (INDEX_TIP, INDEX_PIP),
    "middle": (MIDDLE_TIP, MIDDLE_PIP),
}


def _fingers_spread(landmarks):
    """True if adjacent fingertips (index-middle-ring-pinky) are clearly
    apart, not just extended-but-together — distinguishes a deliberate
    "spread open palm" from a flat hand with fingers held side-by-side
    (e.g. pressed against a cheek during skincare)."""
    hand_scale = _dist(landmarks[WRIST], landmarks[MIDDLE_TIP])
    if hand_scale == 0:
        return False
    tips = (INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP)
    for a, b in zip(tips, tips[1:]):
        if _dist(landmarks[a], landmarks[b]) < config.WAKE_MIN_SPREAD_RATIO * hand_scale:
            return False
    return True


class GestureRecognizer:
    def __init__(self):
        self.bindings = bindings.load_bindings()  # {"left": "index"|"middle", "right": the other}

        self.left_pinch_active = False
        self.left_pinch_start = 0.0
        self.left_dragging = False

        self.right_pinch_active = False
        self.right_pinch_start = 0.0
        self.right_dragging = False

        self.scroll_baseline_y = None

        self.current_gesture = "idle"

        # Consecutive frames the hand has been continuously seen. Used to
        # debounce brand-new gesture starts (pinch-down, entering scroll
        # pose) for the first couple of frames after the hand (re)appears,
        # since landmarks are least reliable right as the hand enters frame
        # or crosses the edge — without this, that instability can register
        # as a spurious click/scroll.
        self._hand_streak = 0

        # Consecutive frames a pinch distance has stayed under threshold
        # before it's confirmed as a real pinch-down. Right-click
        # (thumb+middle) and scroll (index+middle extended) both involve the
        # middle finger, and the thumb can graze past the middle fingertip
        # for a frame or two while the hand is still mid-transition into the
        # scroll shape — requiring a few consecutive close frames filters
        # that out without adding noticeable click latency.
        self._left_pinch_frames = 0
        self._right_pinch_frames = 0

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
        [("scroll", ticks)]

        bypass_arm=True skips the armed-gate for this call (used during
        calibration, which is already a deliberate, hands-on flow).
        """
        if landmarks is None:
            self._hand_streak = 0
            self._left_pinch_frames = 0
            self._right_pinch_frames = 0
            self._wake_last_time = None
            self.wake_progress = 0.0
            self.armed = False
            events = self._release_held_buttons()
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
            holding = stable and is_open_palm and not (self.left_pinch_active or self.right_pinch_active)

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

        # Which physical pinch (thumb+index vs thumb+middle) drives left
        # vs right click is configurable (see munch/bindings.py); resolve
        # that here so the rest of the state machine just deals in
        # "left"/"right" action slots like before.
        left_tip, left_pip = _PINCH_SOURCES[self.bindings["left"]]
        right_tip, right_pip = _PINCH_SOURCES[self.bindings["right"]]
        left_dist = _dist(thumb, landmarks[left_tip])
        right_dist = _dist(thumb, landmarks[right_tip])

        # --- Left pinch (click / drag) ---
        if self.left_pinch_active:
            if left_dist > config.PINCH_OFF_THRESHOLD:
                events = self._release_pinch("left")
            else:
                events = self._hold_pinch("left", now, pointer)
            self.current_gesture = "drag" if self.left_dragging else "left_pinch"
            return events

        # A real pinch curls the touching finger toward the thumb, so it's
        # no longer "extended" by the time it touches — this distinguishes
        # it from the scroll pose's fully-extended index/middle.
        left_approaching = (
            stable
            and left_dist < config.PINCH_ON_THRESHOLD
            and not _finger_extended(landmarks, left_tip, left_pip)
        )
        self._left_pinch_frames = self._left_pinch_frames + 1 if left_approaching else 0

        if self._left_pinch_frames >= config.PINCH_CONFIRM_FRAMES:
            self.left_pinch_active = True
            self.left_pinch_start = now
            self.left_dragging = False
            self._left_pinch_frames = 0
            self.current_gesture = "left_pinch"
            return []

        # --- Right pinch (right click / right drag) ---
        if self.right_pinch_active:
            if right_dist > config.PINCH_OFF_THRESHOLD:
                events = self._release_pinch("right")
            else:
                events = self._hold_pinch("right", now, pointer)
            self.current_gesture = "right_drag" if self.right_dragging else "right_pinch"
            return events

        right_approaching = (
            stable
            and right_dist < config.PINCH_ON_THRESHOLD
            and not _finger_extended(landmarks, right_tip, right_pip)
        )
        self._right_pinch_frames = self._right_pinch_frames + 1 if right_approaching else 0

        if self._right_pinch_frames >= config.PINCH_CONFIRM_FRAMES:
            self.right_pinch_active = True
            self.right_pinch_start = now
            self.right_dragging = False
            self._right_pinch_frames = 0
            self.current_gesture = "right_pinch"
            return []

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

        # --- Plain move ---
        self.current_gesture = "move"
        return [("move", pointer[0], pointer[1])]

    def _hold_pinch(self, side, now, pointer):
        start_attr = f"{side}_pinch_start"
        dragging_attr = f"{side}_dragging"
        start = getattr(self, start_attr)
        dragging = getattr(self, dragging_attr)

        events = []
        if not dragging and (now - start) >= config.DRAG_HOLD_SECONDS:
            dragging = True
            setattr(self, dragging_attr, True)
            events.append((f"{side}_down",))
        if dragging:
            events.append(("move", pointer[0], pointer[1]))
        return events

    def _release_pinch(self, side):
        active_attr = f"{side}_pinch_active"
        dragging_attr = f"{side}_dragging"
        dragging = getattr(self, dragging_attr)

        events = []
        if dragging:
            events.append((f"{side}_up",))
        else:
            events.append((f"{side}_click",))
        setattr(self, active_attr, False)
        setattr(self, dragging_attr, False)
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
        return [("scroll", ticks)]

    def set_bindings(self, new_bindings):
        if bindings.is_valid(new_bindings):
            self.bindings = dict(new_bindings)

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
        if self.left_pinch_active and self.left_dragging:
            events.append(("left_up",))
        if self.right_pinch_active and self.right_dragging:
            events.append(("right_up",))

        self.left_pinch_active = False
        self.left_dragging = False
        self.right_pinch_active = False
        self.right_dragging = False
        self.scroll_baseline_y = None
        return events
