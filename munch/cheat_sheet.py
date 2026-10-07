"""Gesture reference window: the illustrated MUNCH gestures cheat sheet.

Opens at a moderate size and can be resized freely; the illustration
rescales to fit, keeping its proportions.

The illustration shows the default pinch bindings. Clicks can be rebound
in Settings, so when they have been, a short note under the picture says
so instead of letting the picture silently show the wrong pinch.
"""

import os
import tkinter as tk

from PIL import Image, ImageTk

from munch import bindings
from munch.theme import BG, FONT_SUB, INK
from munch.widgets import fade_in

_IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "assets", "MUNCH Gestures Cheat Sheet Guide.png"
)
_DEFAULT_SCREEN_FRACTION = 0.65  # opening height, as a share of the screen height
_MIN_IMAGE_HEIGHT = 320
_PAD = 12
_RESIZE_DELAY_MS = 60  # rescale once dragging pauses, not on every intermediate size


class CheatSheet:
    def __init__(self, master, recognizer):
        self.win = tk.Toplevel(master)
        self.win.attributes("-alpha", 0.0)  # faded in once fully built, at the end of __init__
        self.win.title("MUNCH Gestures")
        self.win.configure(bg=BG)

        self._source = Image.open(_IMAGE_PATH)
        self._aspect = self._source.width / self._source.height
        self._photo = None
        self._shown_size = None
        self._pending_resize = None

        # Packed first and at the bottom, so it stays visible when the
        # window is made small rather than being pushed off by the picture.
        if recognizer.bindings != bindings.default_bindings():
            tk.Label(
                self.win, text="You've changed which pinch does which click. Settings shows your current setup.",
                font=FONT_SUB, bg=BG, fg=INK, wraplength=360, justify="center",
            ).pack(side="bottom", padx=_PAD, pady=(0, _PAD))

        self._image_label = tk.Label(self.win, bg=BG, bd=0)
        self._image_label.pack(fill="both", expand=True, padx=_PAD, pady=_PAD)

        height = min(int(self.win.winfo_screenheight() * _DEFAULT_SCREEN_FRACTION), self._source.height)
        self._show_image(round(height * self._aspect), height)
        self.win.minsize(round(_MIN_IMAGE_HEIGHT * self._aspect) + 2 * _PAD, _MIN_IMAGE_HEIGHT + 2 * _PAD)
        self.win.bind("<Configure>", self._on_configure)

        fade_in(self.win)

    def _show_image(self, width, height):
        if (width, height) == self._shown_size:
            return
        self._shown_size = (width, height)
        resized = self._source.resize((width, height), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(resized)  # kept on self so it isn't garbage-collected
        self._image_label.configure(image=self._photo)

    def _on_configure(self, event):
        if event.widget is not self.win:
            return  # child widgets report their own sizes here too
        if self._pending_resize is not None:
            self.win.after_cancel(self._pending_resize)
        self._pending_resize = self.win.after(_RESIZE_DELAY_MS, self._fit_to_window)

    def _fit_to_window(self):
        self._pending_resize = None
        # The picture's area is whatever the label was given, minus its padding.
        avail_w = self._image_label.winfo_width()
        avail_h = self._image_label.winfo_height()
        if avail_w < 10 or avail_h < 10:
            return
        # Largest size that fits both ways while keeping the proportions.
        height = min(avail_h, round(avail_w / self._aspect))
        self._show_image(round(height * self._aspect), height)

    def close(self):
        self.win.destroy()
