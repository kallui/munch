"""Sends real keystrokes to whatever window has OS focus via pynput.

Used by both the on-screen keyboard and dictation, so typed text and
transcribed speech land the same way regardless of source.
"""

from pynput.keyboard import Controller, Key


class KeyboardController:
    def __init__(self):
        self._keyboard = Controller()

    def type_text(self, text):
        self._keyboard.type(text)

    def press_key(self, key_name):
        key = _SPECIAL_KEYS.get(key_name, key_name)
        self._keyboard.press(key)
        self._keyboard.release(key)

    def press_combo(self, keys):
        """keys: e.g. ["n"] or ["ctrl", "w"] (lowercase; modifiers
        first, final entry is the key to tap). Holds any modifiers,
        taps the final key, releases modifiers in reverse order."""
        resolved = [_SPECIAL_KEYS.get(k, k) for k in keys]
        *modifiers, final_key = resolved
        for mod in modifiers:
            self._keyboard.press(mod)
        self._keyboard.press(final_key)
        self._keyboard.release(final_key)
        for mod in reversed(modifiers):
            self._keyboard.release(mod)


_SPECIAL_KEYS = {
    "backspace": Key.backspace,
    "enter": Key.enter,
    "space": Key.space,
    "tab": Key.tab,
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
}
