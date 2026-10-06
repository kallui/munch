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
        history = [(0.0, 0.20), (0.1, 0.50), (0.2, 0.80)]
        self.assertEqual(classify_slap(history, now=0.20), "right")

    def test_fast_leftward_motion_is_a_left_slap(self):
        history = [(0.0, 0.80), (0.1, 0.50), (0.2, 0.20)]
        self.assertEqual(classify_slap(history, now=0.20), "left")

    def test_slow_motion_is_not_a_slap(self):
        history = [(0.0, 0.50), (0.10, 0.51), (0.20, 0.52)]
        self.assertIsNone(classify_slap(history, now=0.20))

    def test_too_little_history_is_not_a_slap(self):
        self.assertIsNone(classify_slap([(0.20, 0.50)], now=0.20))


if __name__ == "__main__":
    unittest.main()
