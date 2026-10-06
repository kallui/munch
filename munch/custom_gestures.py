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
