"""Floating vertical dock of square icon buttons (keyboard, mic), shown
only while MUNCH is ARMED, anchored to the screen edge."""

import tkinter as tk

from munch import icons, win_utils
from munch.theme import INK, SHADOW_OFFSET, YELLOW
from munch.widgets import RoundedButton

_BTN = 52
_GAP = 10
_RECORDING = "#FF4444"


class SideDock:
    def __init__(self, master, on_keyboard_toggle, on_mic_toggle):
        self._win = tk.Toplevel(master)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg=INK)
        win_utils.prevent_activation(self._win)

        total_btn = _BTN + SHADOW_OFFSET
        screen_w = self._win.winfo_screenwidth()
        screen_h = self._win.winfo_screenheight()
        total_h = total_btn * 2 + _GAP
        x = screen_w - total_btn - 16
        y = (screen_h - total_h) // 2
        self._win.geometry(f"{total_btn}x{total_h}+{x}+{y}")

        self._keyboard_btn = self._make_button(0, "keyboard", on_keyboard_toggle)
        self._mic_btn = self._make_button(total_btn + _GAP, "mic", on_mic_toggle)

        self._win.withdraw()
        self._visible = False

    def _make_button(self, y, icon_name, on_click):
        btn = RoundedButton(
            self._win, _BTN, _BTN, color="white", on_click=on_click,
            icon_image=icons.load_icon(icon_name, INK, 28), bg=INK,
        )
        btn.place(x=0, y=y)
        return btn

    def set_mic_state(self, state):
        self._mic_btn.set_color({"recording": _RECORDING, "transcribing": YELLOW}.get(state, "white"))

    def set_keyboard_state(self, active):
        self._keyboard_btn.set_color(YELLOW if active else "white")

    def show(self):
        if not self._visible:
            self._win.deiconify()
            self._visible = True

    def hide(self):
        if self._visible:
            self._win.withdraw()
            self._visible = False

    def destroy(self):
        self._win.destroy()
