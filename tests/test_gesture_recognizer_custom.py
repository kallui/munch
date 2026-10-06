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
    lm[INDEX_PIP] = (0.50, 0.58)
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
    all_events = []
    for _ in range(frames):
        all_events.extend(recognizer.update(landmarks))
    return all_events


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
        self.assertFalse(any(event[0] == "key_combo" for event in events))


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
        recognizer._palm_history.append((now - 0.05, 0.30))
        events = recognizer.update(_open_hand_landmarks())
        self.assertIn(("key_combo", ["ctrl", "tab"]), events)

    def test_cooldown_prevents_immediate_refire(self):
        recognizer = GestureRecognizer()
        recognizer.armed = True
        recognizer.set_custom_bindings({"slap_right": ["ctrl", "tab"]})
        import time
        now = time.monotonic()
        recognizer._palm_history.append((now - 0.05, 0.30))
        first = recognizer.update(_open_hand_landmarks())
        self.assertIn(("key_combo", ["ctrl", "tab"]), first)
        second = recognizer.update(_open_hand_landmarks())
        self.assertNotIn(("key_combo", ["ctrl", "tab"]), second)


if __name__ == "__main__":
    unittest.main()
