"""Floating vertical dock of square icon buttons (keyboard, mic), shown
only while MUNCH is ARMED, anchored to the screen edge."""

import tkinter as tk

from PIL import ImageTk

from munch import icons, win_utils
from munch.theme import INK, YELLOW

_BTN = 56
_GAP = 10
_RECORDING = "#FF4444"


class SideDock:
    def __init__(self, master, on_keyboard_toggle, on_mic_toggle):
        self._win = tk.Toplevel(master)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg=INK)
        win_utils.prevent_activation(self._win)

        screen_w = self._win.winfo_screenwidth()
        screen_h = self._win.winfo_screenheight()
        total_h = _BTN * 2 + _GAP
        x = screen_w - _BTN - 16
        y = (screen_h - total_h) // 2
        self._win.geometry(f"{_BTN}x{total_h}+{x}+{y}")

        self._keyboard_canvas = self._make_button(0, "keyboard", on_keyboard_toggle)
        self._mic_canvas = self._make_button(_BTN + _GAP, "mic", on_mic_toggle)

        self._win.withdraw()
        self._visible = False

    def _make_button(self, y, icon_name, on_click):
        canvas = tk.Canvas(
            self._win, width=_BTN, height=_BTN, bg="white",
            highlightbackground=INK, highlightthickness=3, cursor="hand2",
        )
        canvas.place(x=0, y=y)

        icon_image = icons.load_icon(icon_name, INK, 30)
        photo = ImageTk.PhotoImage(icon_image)
        canvas.create_image(_BTN // 2, _BTN // 2, image=photo)
        canvas.image = photo  # keep a reference alive (avoid GC)

        canvas.bind("<Button-1>", lambda _event: on_click())
        return canvas

    def set_mic_state(self, state):
        self._mic_canvas.configure(bg={"recording": _RECORDING, "transcribing": YELLOW}.get(state, "white"))

    def set_keyboard_state(self, active):
        self._keyboard_canvas.configure(bg=YELLOW if active else "white")

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
