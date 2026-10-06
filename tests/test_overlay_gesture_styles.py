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
