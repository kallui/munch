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
