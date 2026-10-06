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
