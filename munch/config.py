"""Tunable constants for hand tracking, gesture recognition, and mouse control."""

# Camera
CAMERA_INDEX = 0
FRAME_WIDTH = 400
FRAME_HEIGHT = 300
LOOP_INTERVAL_MS = 15  # Tkinter after() polling interval

# MediaPipe Hands
MAX_NUM_HANDS = 1
MIN_DETECTION_CONFIDENCE = 0.7
MIN_TRACKING_CONFIDENCE = 0.6

# Active zone: fraction of the frame (margin on each side) that maps to the
# full screen, so the hand doesn't need to reach the camera's edges.
ACTIVE_ZONE_MARGIN = 0.15

# Cursor smoothing (exponential moving average). Higher = more responsive
# (follows the fingertip more directly), lower = slower/smoother, damping
# out quick jitter (e.g. the fingertip's own motion while closing a pinch).
CURSOR_SMOOTHING_ALPHA = 0.18

# Pinch detection: normalized (0-1, relative to frame diagonal) distance
# between two fingertips below which they're considered "pinched".
PINCH_ON_THRESHOLD = 0.055
PINCH_OFF_THRESHOLD = 0.075  # hysteresis to avoid flicker at the boundary

# Consecutive frames the hand must be continuously tracked before a brand
# new gesture (pinch-down, entering scroll pose) is allowed to start.
# Landmarks are least reliable the instant a hand enters frame or crosses
# an edge, so this avoids treating that instability as an accidental click.
HAND_STABLE_FRAMES = 2

# Consecutive frames a pinch distance must stay under PINCH_ON_THRESHOLD
# before it's confirmed as a real pinch-down, rather than the thumb
# grazing past a fingertip mid-transition into another gesture (e.g. the
# scroll pose).
PINCH_CONFIRM_FRAMES = 3

# How long a pinch must be held (seconds) before it's treated as a drag
# instead of a click. Long enough that a normal quick click never
# crosses it, short enough that a deliberate hold doesn't feel delayed.
DRAG_HOLD_SECONDS = 0.55

# Wake/arm gesture: an open palm (thumb + all four fingers extended AND
# clearly spread apart) held continuously for this many seconds arms
# MUNCH, moving it from "watching" (ignores the hand entirely — no
# move/click/drag/scroll) to "armed" (gestures act normally). Prevents a
# hand just passing through frame (eating, skincare) from being read as
# input — see the Midas touch problem / wake-gesture precedent from EMG
# prosthetics research.
#
# Deliberately strict, the same way a phone's "raise palm to take a
# photo" gesture is: skincare/eating hands are usually flat with fingers
# together (pressed to a face, wrapped around food), not spread — so
# requiring a pronounced, fingers-apart extension plus a longer hold is
# what keeps it from arming by accident.
ARM_HOLD_SECONDS = 2.0

# If the open-palm pose breaks before the hold completes, progress drains
# back down over this many seconds instead of snapping to zero — faster
# than it fills, so briefly breaking the pose still feels forgiving but
# clearly reads as "losing" progress.
ARM_DRAIN_SECONDS = 0.6

# How much farther (as a multiple of the knuckle-to-wrist distance) a
# fingertip must be from the wrist than its own knuckle to count as
# "extended" for the wake pose specifically — a bit stricter than the
# 1.15 used for scroll/pinch shape checks elsewhere, but not so strict
# that a normal open hand fails it. Only applied to the four fingers —
# the thumb moves sideways rather than up, so this same wrist-distance
# math doesn't translate well to it and it's deliberately not checked.
WAKE_EXTEND_RATIO = 1.2

# Minimum gap between adjacent fingertips (index-middle, middle-ring,
# ring-pinky), as a fraction of wrist-to-middle-fingertip distance, for
# the hand to count as "spread" rather than just extended-but-together.
WAKE_MIN_SPREAD_RATIO = 0.1

# Scroll gesture: index+middle extended together, others curled. Joystick
# style: a baseline Y is captured when the pose starts, and the hand's
# offset from that baseline (past a small deadzone) drives a continuous
# scroll speed, so holding the hand displaced keeps scrolling without
# further movement.
SCROLL_DEADZONE = 0.025  # normalized distance from baseline with no scroll
SCROLL_SPEED_SCALE = 4.0  # scroll ticks/frame per unit of normalized offset
SCROLL_MAX_SPEED = 1.5  # cap on scroll ticks/frame

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
SLAP_VELOCITY_THRESHOLD = 1.0
SLAP_COOLDOWN_SECONDS = 0.6  # minimum gap between two slap firings
