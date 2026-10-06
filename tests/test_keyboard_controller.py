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
