import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import munch.custom_bindings as cb


class TestValidation(unittest.TestCase):
    def test_default_presets_is_valid_state(self):
        self.assertTrue(cb.is_valid_state(cb.default_presets()))

    def test_valid_combo(self):
        self.assertTrue(cb.is_valid_combo(["ctrl", "w"]))
        self.assertTrue(cb.is_valid_combo(["n"]))

    def test_invalid_combo_rejects_empty_or_wrong_type(self):
        self.assertFalse(cb.is_valid_combo([]))
        self.assertFalse(cb.is_valid_combo("n"))
        self.assertFalse(cb.is_valid_combo([""]))

    def test_bindings_reject_unknown_gesture(self):
        self.assertFalse(cb.is_valid_bindings({"not_a_real_gesture": ["n"]}))

    def test_bindings_accept_known_gesture(self):
        self.assertTrue(cb.is_valid_bindings({"ok_sign": ["n"]}))

    def test_state_requires_active_preset_to_exist(self):
        bad = {"active": "Ghost", "presets": {"Default": {}}}
        self.assertFalse(cb.is_valid_state(bad))

    def test_state_requires_default_preset(self):
        bad = {"active": "Custom", "presets": {"Custom": {}}}
        self.assertFalse(cb.is_valid_state(bad))


class TestActiveBindings(unittest.TestCase):
    def test_returns_the_active_presets_bindings(self):
        state = {
            "active": "Anime",
            "presets": {"Default": {}, "Anime": {"ok_sign": ["n"]}},
        }
        self.assertEqual(cb.active_bindings(state), {"ok_sign": ["n"]})


class TestFormatCombo(unittest.TestCase):
    def test_joins_with_plus(self):
        self.assertEqual(cb.format_combo(["ctrl", "w"]), "ctrl+w")
        self.assertEqual(cb.format_combo(["n"]), "n")


class TestLoadSaveRoundTrip(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._orig_path = cb._PRESETS_PATH
        cb._PRESETS_PATH = self._tmp.name

    def tearDown(self):
        cb._PRESETS_PATH = self._orig_path
        if os.path.exists(self._tmp.name):
            os.unlink(self._tmp.name)

    def test_missing_file_returns_default(self):
        os.unlink(self._tmp.name)
        self.assertEqual(cb.load_state(), cb.default_presets())

    def test_save_then_load_round_trips(self):
        state = {
            "active": "Anime",
            "presets": {"Default": {}, "Anime": {"ok_sign": ["n"]}},
        }
        cb.save_state(state)
        self.assertEqual(cb.load_state(), state)

    def test_corrupt_file_falls_back_to_default(self):
        with open(self._tmp.name, "w") as f:
            f.write("not json")
        self.assertEqual(cb.load_state(), cb.default_presets())

    def test_invalid_state_in_file_falls_back_to_default(self):
        with open(self._tmp.name, "w") as f:
            json.dump({"active": "Ghost", "presets": {}}, f)
        self.assertEqual(cb.load_state(), cb.default_presets())


if __name__ == "__main__":
    unittest.main()
