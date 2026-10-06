"""MUNCH settings window — gesture bindings, sensitivity, calibration,
display and camera options.

Four pinch shapes exist (thumb + index/middle/ring/pinky), each bound to
one action (left-click, right-click, middle-click, double-click) — a
permutation: picking a finger already in use for one action swaps it
with whichever action had it, since no two actions can share a finger.
Scroll and the wake pose have their own unique shapes with nothing to
swap against yet, so they're shown as fixed rows rather than dropdowns.
"""

import tkinter as tk

from munch import bindings as bindings_module
from munch import tuning as tuning_module
from munch.theme import BG, BORDER_W, INK, PURPLE, YELLOW

FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_LABEL = ("Segoe UI", 10, "bold")
FONT_BUTTON = ("Segoe UI", 11, "bold")
FONT_VALUE = ("Segoe UI", 9)

_ROW_LABEL_WIDTH = 17
_DROPDOWN_ARROW = "  ▾"  # small flat triangle, drawn as plain text, not a native OS widget

_FINGER_LABELS = {
    "index": "Thumb + index pinch", "middle": "Thumb + middle pinch",
    "ring": "Thumb + ring pinch", "pinky": "Thumb + pinky pinch",
}
_ACTION_LABELS = {
    "left": "Left click / drag", "right": "Right click / drag",
    "middle": "Middle click / drag", "double": "Double-click",
}
_ACTION_ORDER = ("left", "right", "middle", "double")

_SLIDERS = (
    # (tuning key, label, from, to, resolution, value format)
    ("cursor_smoothing_alpha", "Cursor responsiveness", 0.05, 0.6, 0.01, "{:.2f}"),
    ("drag_hold_seconds", "Drag hold time", 0.2, 1.2, 0.05, "{:.2f}s"),
    ("pinch_on_threshold", "Pinch sensitivity", 0.03, 0.09, 0.005, "{:.3f}"),
)

_CALIBRATE_HELP = (
    "Maps your comfortable hand movement to the full screen. "
    "Pinch top-left, then bottom-right of your reach."
)


def _bordered(widget, **kwargs):
    widget.configure(highlightbackground=INK, highlightthickness=BORDER_W - 1, **kwargs)
    return widget


class _SliderWidget:
    """A flat, bordered "sticker" slider — a filled bar + a bold round
    knob — in place of tk.Scale, which renders with the native Windows
    groove/thumb no matter what colors are set on it."""

    _W, _H = 170, 22
    _KNOB_R = 7

    def __init__(self, parent, lo, hi, resolution, initial, on_change):
        self.lo, self.hi, self.res = lo, hi, resolution
        self.on_change = on_change
        self.value = initial

        self.canvas = tk.Canvas(parent, width=self._W, height=self._H, bg=BG, highlightthickness=0)
        self._redraw()
        self.canvas.bind("<Button-1>", self._on_drag)
        self.canvas.bind("<B1-Motion>", self._on_drag)

    def _value_to_x(self, value):
        frac = (value - self.lo) / (self.hi - self.lo)
        return self._KNOB_R + frac * (self._W - 2 * self._KNOB_R)

    def _x_to_value(self, x):
        frac = max(0.0, min(1.0, (x - self._KNOB_R) / (self._W - 2 * self._KNOB_R)))
        raw = self.lo + frac * (self.hi - self.lo)
        steps = round((raw - self.lo) / self.res)
        return round(self.lo + steps * self.res, 6)

    def _redraw(self):
        self.canvas.delete("all")
        mid_y = self._H // 2
        x = self._value_to_x(self.value)

        self.canvas.create_rectangle(
            self._KNOB_R, mid_y - 4, self._W - self._KNOB_R, mid_y + 4,
            fill="white", outline=INK, width=2,
        )
        if x > self._KNOB_R:
            self.canvas.create_rectangle(self._KNOB_R, mid_y - 4, x, mid_y + 4, fill=INK, outline="")
        self.canvas.create_oval(
            x - self._KNOB_R, mid_y - self._KNOB_R, x + self._KNOB_R, mid_y + self._KNOB_R,
            fill="white", outline=INK, width=2,
        )

    def _on_drag(self, event):
        new_value = self._x_to_value(event.x)
        if new_value != self.value:
            self.value = new_value
            self._redraw()
            self.on_change(self.value)

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)


def _add_tooltip(widget, text):
    """A small themed popup on hover — Tk has no built-in tooltip."""
    state = {"win": None}

    def show(_event):
        if state["win"] is not None:
            return
        win = tk.Toplevel(widget)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        tk.Label(
            win, text=text, font=FONT_VALUE, bg=YELLOW, fg=INK,
            highlightbackground=INK, highlightthickness=BORDER_W - 1,
            justify="left", wraplength=230, padx=10, pady=8,
        ).pack()
        x = widget.winfo_rootx() + widget.winfo_width() + 8
        y = widget.winfo_rooty() - 6
        win.geometry(f"+{x}+{y}")
        state["win"] = win

    def hide(_event):
        if state["win"] is not None:
            state["win"].destroy()
            state["win"] = None

    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)


def detect_cameras():
    """Returns [(index, name), ...] for available camera devices, with
    real device names.

    Uses pygrabber to read the DirectShow device list directly instead of
    opening/closing each index with OpenCV to see what responds — that
    probing loop was slow enough (each failed cv2.VideoCapture open can
    take several hundred ms on Windows) to freeze the whole app for a
    couple of seconds every time Settings was opened, and OpenCV itself
    has no way to report a device's actual name anyway. Device order here
    matches the index OpenCV's own CAP_DSHOW backend assigns, since both
    enumerate the same underlying DirectShow device list.

    Callers should cache the result instead of calling this on every
    Settings open — see MunchApp._available_cameras.
    """
    try:
        from pygrabber.dshow_graph import FilterGraph
        names = FilterGraph().get_input_devices()
        if names:
            return list(enumerate(names))
    except Exception:
        pass
    return [(0, "Camera 0")]


class SettingsWindow:
    def __init__(
        self, master, recognizer, mouse, on_calibrate, show_overlay_var, on_overlay_changed,
        camera_index, available_cameras, on_camera_change,
    ):
        self.recognizer = recognizer
        self.mouse = mouse
        self._on_calibrate = on_calibrate
        self._on_camera_change = on_camera_change
        self._active_popup = None
        self._binding_state = dict(recognizer.bindings)  # action -> finger, live working copy
        self._action_btns = {}

        self.win = tk.Toplevel(master)
        self.win.title("MUNCH Settings")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)

        tk.Label(self.win, text="GESTURE BINDINGS", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(16, 6)
        )
        for action in _ACTION_ORDER:
            self._action_btns[action] = self._dropdown_row(
                _ACTION_LABELS[action], list(_FINGER_LABELS.values()),
                _FINGER_LABELS[self._binding_state[action]],
                lambda choice, a=action: self._on_binding_change(a, choice),
            )
        self._fixed_row("Scroll", "Index + middle extended")
        self._fixed_row("Wake / arm", "Open palm, spread")

        _bordered(tk.Button(
            self.win, text="RESET TO DEFAULT PRESET", font=FONT_BUTTON,
            bg="#DDDDDD", fg=INK, activebackground="#DDDDDD", relief="flat", bd=0,
            cursor="hand2", command=self._reset_default,
        )).pack(fill="x", padx=16, pady=(10, 18))

        tk.Label(self.win, text="SENSITIVITY", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(0, 6)
        )
        self._tuning_state = dict(recognizer.tuning)
        for key, label, lo, hi, res, fmt in _SLIDERS:
            self._slider_row(key, label, lo, hi, res, fmt)

        tk.Label(self.win, text="CAMERA", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        self._camera_index_by_name = {name: i for i, name in available_cameras}
        names_by_index = dict(available_cameras)
        current_name = names_by_index.get(camera_index, available_cameras[0][1])
        self._dropdown_row(
            "Device", list(self._camera_index_by_name.keys()), current_name, self._on_camera_select
        )

        tk.Label(self.win, text="DISPLAY", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        tk.Checkbutton(
            self.win, text="Show gesture overlay on cursor", variable=show_overlay_var,
            command=on_overlay_changed, font=FONT_VALUE,
            bg=BG, fg=INK, activebackground=BG, selectcolor=BG, bd=0, highlightthickness=0,
        ).pack(anchor="w", padx=16, pady=(0, 18))

        calib_heading = tk.Frame(self.win, bg=BG)
        calib_heading.pack(anchor="w", padx=16, pady=(0, 6))
        tk.Label(calib_heading, text="CALIBRATE MOTION BOUNDARY", font=FONT_HEADING, bg=BG, fg=INK).pack(side="left")
        help_badge = tk.Canvas(calib_heading, width=16, height=16, bg=BG, highlightthickness=0, cursor="hand2")
        help_badge.create_oval(1, 1, 15, 15, outline=INK, width=2)
        help_badge.create_text(8, 8, text="?", font=("Segoe UI", 8, "bold"), fill=INK)
        help_badge.pack(side="left", padx=(6, 0))
        _add_tooltip(help_badge, _CALIBRATE_HELP)

        _bordered(tk.Button(
            self.win, text="⌖  CALIBRATE", font=FONT_BUTTON,
            bg=PURPLE, fg="white", activebackground=PURPLE, activeforeground="white",
            relief="flat", bd=0, cursor="hand2", command=self._calibrate_clicked,
        )).pack(fill="x", padx=16, pady=(0, 16))

    # ------------------------------------------------------------------
    def _dropdown_row(self, label_text, options, initial_value, on_select):
        """A label + a fully custom dropdown. tk.Menu's popup renders via
        the native Win32 menu control on Windows regardless of what bg/fg
        colors are set on it — the only way to actually theme the popup
        list is to not use a real menu at all, and draw our own borderless
        Toplevel full of styled rows instead."""
        row = tk.Frame(self.win, bg=BG)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text=label_text, font=FONT_LABEL, bg=BG, fg=INK,
                 width=_ROW_LABEL_WIDTH, anchor="w").pack(side="left")

        btn = tk.Label(
            row, text=initial_value + _DROPDOWN_ARROW, font=FONT_VALUE, bg="white", fg=INK,
            anchor="w", padx=8, pady=4, cursor="hand2",
        )
        _bordered(btn)
        btn.pack(side="left", fill="x", expand=True)

        def choose(option):
            btn.configure(text=option + _DROPDOWN_ARROW)
            self._close_popup()
            on_select(option)

        def open_popup(_event=None):
            if self._active_popup is not None:
                self._close_popup()
                return

            btn.update_idletasks()
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height()
            width = max(btn.winfo_width(), 140)

            popup = tk.Toplevel(self.win)
            popup.overrideredirect(True)
            popup.attributes("-topmost", True)
            popup.configure(bg=INK)  # the 2px ring around `inner` reads as its border

            inner = tk.Frame(popup, bg="white")
            inner.pack(padx=2, pady=2)
            for option in options:
                option_row = tk.Label(
                    inner, text=option, font=FONT_VALUE, bg="white", fg=INK,
                    anchor="w", padx=8, pady=6, cursor="hand2", width=max(width // 7, 16),
                )
                option_row.pack(fill="x")
                option_row.bind("<Enter>", lambda _e, w=option_row: w.configure(bg=YELLOW))
                option_row.bind("<Leave>", lambda _e, w=option_row: w.configure(bg="white"))
                option_row.bind("<Button-1>", lambda _e, o=option: choose(o))

            popup.geometry(f"+{x}+{y}")
            popup.bind("<FocusOut>", lambda _e: self._close_popup())
            popup.focus_force()
            self._active_popup = popup

        btn.bind("<Button-1>", open_popup)
        return btn

    def _close_popup(self):
        if self._active_popup is not None:
            self._active_popup.destroy()
            self._active_popup = None

    def _fixed_row(self, label_text, value_text):
        row = tk.Frame(self.win, bg=BG)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text=label_text, font=FONT_LABEL, bg=BG, fg=INK,
                 width=_ROW_LABEL_WIDTH, anchor="w").pack(side="left")
        _bordered(tk.Label(
            row, text=value_text, font=FONT_VALUE, bg="#EAEAEA", fg="#666666",
            anchor="w", padx=8, pady=4,
        )).pack(side="left", fill="x", expand=True)

    def _slider_row(self, key, label_text, lo, hi, res, fmt):
        row = tk.Frame(self.win, bg=BG)
        row.pack(fill="x", padx=16, pady=6)
        tk.Label(row, text=label_text, font=FONT_LABEL, bg=BG, fg=INK,
                 width=_ROW_LABEL_WIDTH, anchor="w").pack(side="left")

        value_label = tk.Label(row, text=fmt.format(self._tuning_state[key]), font=FONT_VALUE,
                                bg=BG, fg=INK, width=6, anchor="e")

        def on_change(value, k=key):
            value_label.configure(text=fmt.format(value))
            self._on_slider_change(k, value)

        slider = _SliderWidget(row, lo, hi, res, self._tuning_state[key], on_change)
        slider.pack(side="left", padx=(0, 10))
        value_label.pack(side="left")

    # ------------------------------------------------------------------
    @staticmethod
    def _finger_for_label(label):
        for finger, text in _FINGER_LABELS.items():
            if text == label:
                return finger
        return "index"

    def _on_binding_change(self, action, choice):
        new_finger = self._finger_for_label(choice)
        old_finger = self._binding_state[action]
        if new_finger == old_finger:
            return
        swap_action = next(a for a, f in self._binding_state.items() if f == new_finger)

        self._binding_state[swap_action] = old_finger
        self._binding_state[action] = new_finger
        self._action_btns[swap_action].configure(text=_FINGER_LABELS[old_finger] + _DROPDOWN_ARROW)
        self._action_btns[action].configure(text=_FINGER_LABELS[new_finger] + _DROPDOWN_ARROW)
        self._apply_bindings()

    def _apply_bindings(self):
        self.recognizer.set_bindings(self._binding_state)
        bindings_module.save_bindings(self._binding_state)

    def _reset_default(self):
        self._binding_state = bindings_module.default_bindings()
        for action in _ACTION_ORDER:
            self._action_btns[action].configure(
                text=_FINGER_LABELS[self._binding_state[action]] + _DROPDOWN_ARROW
            )
        self._apply_bindings()

    def _on_slider_change(self, key, value):
        self._tuning_state[key] = float(value)
        self.recognizer.set_tuning(self._tuning_state)
        self.mouse.set_tuning(self._tuning_state)
        tuning_module.save_tuning(self._tuning_state)

    def _on_camera_select(self, choice):
        self._on_camera_change(self._camera_index_by_name[choice])

    def _calibrate_clicked(self):
        self.close()
        self._on_calibrate()

    def close(self):
        self._close_popup()
        self.win.destroy()
