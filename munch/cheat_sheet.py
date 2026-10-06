"""Toggleable gesture reference panel — read live from the recognizer's
current bindings so it always matches whatever you've customized, not a
stale hardcoded list."""

import tkinter as tk

from munch.theme import BG, INK
from munch import custom_bindings as custom_bindings_module

FONT_HEADING = ("Segoe UI", 13, "bold")
FONT_ROW = ("Segoe UI", 10)

_FINGER_LABELS = {
    "index": "Thumb + index pinch", "middle": "Thumb + middle pinch",
    "ring": "Thumb + ring pinch", "pinky": "Thumb + pinky pinch",
}
_ACTION_LABELS = {
    "left": "Left click / drag", "right": "Right click / drag",
    "middle": "Middle click / drag", "double": "Double-click",
}
_ACTION_ORDER = ("left", "right", "middle", "double")


class CheatSheet:
    def __init__(self, master, recognizer):
        self.win = tk.Toplevel(master)
        self.win.title("MUNCH Gestures")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)

        tk.Label(self.win, text="GESTURES", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(16, 10)
        )
        for action in _ACTION_ORDER:
            finger = recognizer.bindings[action]
            self._row(_ACTION_LABELS[action], _FINGER_LABELS[finger])
        self._row("Scroll", "Index + middle extended, together")
        self._hint(
            "Hold fingers up like a remote, level with the camera — not "
            "pointed at it. Keep index and middle together, like pointing "
            "a gun, to scroll; tilt down to scroll down, up to scroll up. "
            "Spread them apart for the peace-sign gesture instead."
        )
        self._row("Wake / arm", "Open palm, spread, hold ~2s")
        self._row("Disarm", "Hand leaves frame")

        custom_state = custom_bindings_module.load_state()
        active = custom_bindings_module.active_bindings(custom_state)
        if active:
            tk.Label(self.win, text="CUSTOM GESTURES", font=FONT_HEADING, bg=BG, fg=INK).pack(
                anchor="w", padx=16, pady=(14, 6)
            )
            for gesture, keys in active.items():
                self._row(
                    custom_bindings_module.GESTURE_LABELS[gesture],
                    custom_bindings_module.format_combo(keys),
                )

        tk.Label(
            self.win, text="Open Settings to rebind clicks or tune sensitivity.",
            font=("Segoe UI", 9), bg=BG, fg="#666666", wraplength=280, justify="left",
        ).pack(anchor="w", padx=16, pady=(6, 16))

    def _row(self, label_text, value_text):
        row = tk.Frame(self.win, bg=BG)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text=label_text, font=("Segoe UI", 10, "bold"), bg=BG, fg=INK,
                 width=17, anchor="w").pack(side="left")
        tk.Label(row, text=value_text, font=FONT_ROW, bg=BG, fg="#444444", anchor="w").pack(side="left")

    def _hint(self, text):
        """A smaller, muted, wrapped explanation line under a row — for
        gestures (like scroll) where the one-line pose description isn't
        enough on its own to get right on the first try."""
        tk.Label(
            self.win, text=text, font=("Segoe UI", 8), bg=BG, fg="#888888",
            wraplength=280, justify="left", anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 6))

    def close(self):
        self.win.destroy()
