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
from munch import custom_bindings as custom_bindings_module
from munch import tuning as tuning_module
from munch.theme import BG, BORDER_W, INK, PURPLE, YELLOW
from munch.widgets import RoundedButton

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


class _KeyCapture:
    """A "click to set key" field — captures the next real key/modifier
    combo pressed anywhere in the Settings window, via KeyPress (and
    tracking modifier state across KeyPress events, not event.state's
    platform-specific bitmask) so it works for both a lone key and a
    held-modifier combo. Only one capture can listen at a time; starting
    a new one cancels whichever was previously listening."""

    _MODIFIER_KEYSYMS = {
        "Control_L": "ctrl", "Control_R": "ctrl",
        "Alt_L": "alt", "Alt_R": "alt",
        "Shift_L": "shift", "Shift_R": "shift",
    }
    _CAPTURABLE_SPECIAL = {"Return": "enter", "BackSpace": "backspace", "Tab": "tab", "space": "space"}

    def __init__(self, parent, window, initial_keys, on_change, on_start=None):
        self._window = window
        self._on_change = on_change
        self._on_start = on_start
        self._listening = False
        self._held_modifiers = []
        self._bind_id = None
        self._keys = initial_keys

        self.label = tk.Label(
            parent, text=self._format(initial_keys), font=FONT_VALUE, bg="white", fg=INK,
            anchor="w", padx=8, pady=4, cursor="hand2",
        )
        _bordered(self.label)
        self.label.bind("<Button-1>", self._start_listening)

    def _format(self, keys):
        return "+".join(keys) if keys else "Click to set key..."

    def _start_listening(self, _event=None):
        if self._listening:
            return
        if self._on_start:
            self._on_start(self)
        self._listening = True
        self._held_modifiers = []
        self.label.configure(text="Press keys...", bg=YELLOW)
        self._bind_id = self._window.bind("<KeyPress>", self._on_key_press)

    def cancel(self):
        """Stop listening without completing a capture — called when a
        different capture field starts, or this row is about to be
        destroyed by a rebuild."""
        if not self._listening:
            return
        self._listening = False
        if self._bind_id is not None:
            self._window.unbind("<KeyPress>", self._bind_id)
            self._bind_id = None
        try:
            self.label.configure(text=self._format(self._keys), bg="white")
        except tk.TclError:
            pass  # widget already destroyed

    def _on_key_press(self, event):
        keysym = event.keysym
        if keysym in self._MODIFIER_KEYSYMS:
            name = self._MODIFIER_KEYSYMS[keysym]
            if name not in self._held_modifiers:
                self._held_modifiers.append(name)
            return
        if keysym in self._CAPTURABLE_SPECIAL:
            key = self._CAPTURABLE_SPECIAL[keysym]
        elif len(keysym) == 1:
            key = keysym.lower()
        else:
            return  # unsupported key (Escape/F-keys/arrows/etc.) — keep listening
        combo = self._held_modifiers + [key]
        self.cancel()
        self._keys = combo
        self.label.configure(text=self._format(combo))
        self._on_change(combo)

    def pack(self, **kwargs):
        self.label.pack(**kwargs)


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
        self._active_key_capture = None
        self._binding_state = dict(recognizer.bindings)  # action -> finger, live working copy
        self._action_btns = {}

        self.win = tk.Toplevel(master)
        self.win.title("MUNCH Settings")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)

        container = tk.Canvas(self.win, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.win, orient="vertical", command=container.yview)
        container.configure(yscrollcommand=scrollbar.set)
        container.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._content = tk.Frame(container, bg=BG)
        content_window = container.create_window((0, 0), window=self._content, anchor="nw")

        def _on_content_configure(_event=None):
            container.configure(scrollregion=container.bbox("all"))
        self._content.bind("<Configure>", _on_content_configure)

        def _on_canvas_configure(event):
            container.itemconfigure(content_window, width=event.width)
        container.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            container.yview_scroll(int(-1 * (event.delta / 120)), "units")
        container.bind("<MouseWheel>", _on_mousewheel)
        self._content.bind("<MouseWheel>", _on_mousewheel)

        screen_h = self.win.winfo_screenheight()
        self.win.geometry(f"420x{min(700, screen_h - 140)}")

        tk.Label(self._content, text="GESTURE BINDINGS", font=FONT_HEADING, bg=BG, fg=INK).pack(
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

        self.win.update_idletasks()
        btn_width = 368  # 420 window width, minus padding, minus room for the scrollbar
        RoundedButton(
            self._content, btn_width, 34, color="#DDDDDD", on_click=self._reset_default,
            text="RESET TO DEFAULT PRESET", font=FONT_BUTTON, bg=BG,
        ).pack(padx=16, pady=(10, 18))

        tk.Label(self._content, text="SENSITIVITY", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(0, 6)
        )
        self._tuning_state = dict(recognizer.tuning)
        for key, label, lo, hi, res, fmt in _SLIDERS:
            self._slider_row(key, label, lo, hi, res, fmt)

        tk.Label(self._content, text="CAMERA", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        self._camera_index_by_name = {name: i for i, name in available_cameras}
        names_by_index = dict(available_cameras)
        current_name = names_by_index.get(camera_index, available_cameras[0][1])
        self._dropdown_row(
            "Device", list(self._camera_index_by_name.keys()), current_name, self._on_camera_select
        )

        tk.Label(self._content, text="DISPLAY", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        tk.Checkbutton(
            self._content, text="Show gesture overlay on cursor", variable=show_overlay_var,
            command=on_overlay_changed, font=FONT_VALUE,
            bg=BG, fg=INK, activebackground=BG, selectcolor=BG, bd=0, highlightthickness=0,
        ).pack(anchor="w", padx=16, pady=(0, 18))

        calib_heading = tk.Frame(self._content, bg=BG)
        calib_heading.pack(anchor="w", padx=16, pady=(0, 6))
        tk.Label(calib_heading, text="CALIBRATE MOTION BOUNDARY", font=FONT_HEADING, bg=BG, fg=INK).pack(side="left")
        help_badge = tk.Canvas(calib_heading, width=16, height=16, bg=BG, highlightthickness=0, cursor="hand2")
        help_badge.create_oval(1, 1, 15, 15, outline=INK, width=2)
        help_badge.create_text(8, 8, text="?", font=("Segoe UI", 8, "bold"), fill=INK)
        help_badge.pack(side="left", padx=(6, 0))
        _add_tooltip(help_badge, _CALIBRATE_HELP)

        RoundedButton(
            self._content, btn_width, 34, color=PURPLE, on_click=self._calibrate_clicked,
            text="⌖  CALIBRATE", font=FONT_BUTTON, fg="white", bg=BG,
        ).pack(padx=16, pady=(0, 16))

        self._custom_state = custom_bindings_module.load_state()
        self._pending_gestures = set()

        tk.Label(self._content, text="CUSTOM GESTURES", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        preset_row = tk.Frame(self._content, bg=BG)
        preset_row.pack(fill="x", padx=16, pady=4)
        tk.Label(preset_row, text="Preset", font=FONT_LABEL, bg=BG, fg=INK,
                 width=_ROW_LABEL_WIDTH, anchor="w").pack(side="left")
        self._preset_btn = tk.Label(
            preset_row, text=self._custom_state["active"] + _DROPDOWN_ARROW, font=FONT_VALUE,
            bg="white", fg=INK, anchor="w", padx=8, pady=4, cursor="hand2",
        )
        _bordered(self._preset_btn)
        self._preset_btn.pack(side="left", fill="x", expand=True)
        self._preset_btn.bind("<Button-1>", lambda _e: self._open_preset_popup())

        preset_actions = tk.Frame(self._content, bg=BG)
        preset_actions.pack(fill="x", padx=16, pady=(0, 10))
        RoundedButton(
            preset_actions, 110, 28, color="#DDDDDD", on_click=self._save_as_preset,
            text="SAVE AS NEW", font=("Segoe UI", 9, "bold"), bg=BG,
        ).pack(side="left", padx=(0, 6))
        RoundedButton(
            preset_actions, 90, 28, color="#DDDDDD", on_click=self._delete_preset,
            text="DELETE", font=("Segoe UI", 9, "bold"), bg=BG,
        ).pack(side="left")

        self._binding_rows_frame = tk.Frame(self._content, bg=BG)
        self._binding_rows_frame.pack(fill="x")
        self._rebuild_binding_rows()

        RoundedButton(
            self._content, btn_width, 30, color="#DDDDDD", on_click=self._add_binding_row,
            text="+ ADD BINDING", font=FONT_BUTTON, bg=BG,
        ).pack(padx=16, pady=(4, 18))

    # ------------------------------------------------------------------
    def _dropdown_row(self, label_text, options, initial_value, on_select):
        """A label + a fully custom dropdown. tk.Menu's popup renders via
        the native Win32 menu control on Windows regardless of what bg/fg
        colors are set on it — the only way to actually theme the popup
        list is to not use a real menu at all, and draw our own borderless
        Toplevel full of styled rows instead."""
        row = tk.Frame(self._content, bg=BG)
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
            on_select(option)

        btn.bind("<Button-1>", lambda _e: self._popup_choice_list(btn, options, choose))
        return btn

    def _popup_choice_list(self, anchor_widget, options, on_choose):
        """Borderless-popup list anchored under `anchor_widget` — shared
        by the finger/camera dropdowns, the preset picker, and the
        per-row gesture picker."""
        if self._active_popup is not None:
            self._close_popup()

        anchor_widget.update_idletasks()
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        width = max(anchor_widget.winfo_width(), 140)

        popup = tk.Toplevel(self.win)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=INK)

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
            option_row.bind("<Button-1>", lambda _e, o=option: (self._close_popup(), on_choose(o)))

        popup.geometry(f"+{x}+{y}")
        popup.bind("<FocusOut>", lambda _e: self._close_popup())
        popup.focus_force()
        self._active_popup = popup

    def _close_popup(self):
        if self._active_popup is not None:
            self._active_popup.destroy()
            self._active_popup = None

    def _fixed_row(self, label_text, value_text):
        row = tk.Frame(self._content, bg=BG)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text=label_text, font=FONT_LABEL, bg=BG, fg=INK,
                 width=_ROW_LABEL_WIDTH, anchor="w").pack(side="left")
        _bordered(tk.Label(
            row, text=value_text, font=FONT_VALUE, bg="#EAEAEA", fg="#666666",
            anchor="w", padx=8, pady=4,
        )).pack(side="left", fill="x", expand=True)

    def _slider_row(self, key, label_text, lo, hi, res, fmt):
        row = tk.Frame(self._content, bg=BG)
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

    # ------------------------------------------------------------------
    def _active_bindings(self):
        return self._custom_state["presets"][self._custom_state["active"]]

    def _displayed_bindings(self):
        """Active bindings plus any pending (not-yet-keyed) rows, for
        rendering only — pending rows never enter self._custom_state until
        a real key is captured, so an unfilled row can never make the saved
        state invalid."""
        combined = dict(self._active_bindings())
        for gesture in self._pending_gestures:
            combined.setdefault(gesture, [])
        return combined

    def _rebuild_binding_rows(self):
        if self._active_key_capture is not None:
            self._active_key_capture.cancel()
            self._active_key_capture = None
        for child in self._binding_rows_frame.winfo_children():
            child.destroy()
        for gesture, keys in self._displayed_bindings().items():
            self._binding_row(gesture, keys)

    def _binding_row(self, gesture, keys):
        row = tk.Frame(self._binding_rows_frame, bg=BG)
        row.pack(fill="x", padx=16, pady=4)

        gesture_btn = tk.Label(
            row, text=custom_bindings_module.GESTURE_LABELS[gesture] + _DROPDOWN_ARROW,
            font=FONT_VALUE, bg="white", fg=INK, anchor="w", padx=8, pady=4,
            cursor="hand2", width=16,
        )
        _bordered(gesture_btn)
        gesture_btn.pack(side="left", padx=(0, 6))
        gesture_btn.bind("<Button-1>", lambda _e, g=gesture, b=gesture_btn: self._open_gesture_popup(g, b))

        capture = _KeyCapture(
            row, self.win, keys, lambda new_keys, g=gesture: self._on_key_change(g, new_keys),
            on_start=self._on_key_capture_start,
        )
        capture.pack(side="left", fill="x", expand=True, padx=(0, 6))

        remove_btn = tk.Label(
            row, text="×", font=("Segoe UI", 12, "bold"), bg=BG, fg=INK, cursor="hand2", padx=6,
        )
        remove_btn.pack(side="left")
        remove_btn.bind("<Button-1>", lambda _e, g=gesture: self._remove_binding(g))

    def _unused_gestures(self):
        used = set(self._displayed_bindings().keys())
        return [g for g in custom_bindings_module.GESTURES if g not in used]

    def _add_binding_row(self):
        available = self._unused_gestures()
        if not available:
            return
        self._pending_gestures.add(available[0])
        self._rebuild_binding_rows()

    def _remove_binding(self, gesture):
        self._pending_gestures.discard(gesture)
        if gesture in self._active_bindings():
            self._active_bindings().pop(gesture, None)
            self._apply_custom_bindings()
        self._rebuild_binding_rows()

    def _on_key_capture_start(self, capture):
        if self._active_key_capture is not None and self._active_key_capture is not capture:
            self._active_key_capture.cancel()
        self._active_key_capture = capture

    def _open_gesture_popup(self, gesture, anchor_widget):
        choices = [custom_bindings_module.GESTURE_LABELS[g] for g in self._unused_gestures()]
        current_label = custom_bindings_module.GESTURE_LABELS[gesture]
        if current_label not in choices:
            choices = [current_label] + choices

        def choose(label):
            new_gesture = next(
                g for g, l in custom_bindings_module.GESTURE_LABELS.items() if l == label
            )
            if new_gesture == gesture:
                return
            if gesture in self._pending_gestures:
                self._pending_gestures.discard(gesture)
                self._pending_gestures.add(new_gesture)
            else:
                bindings_dict = self._active_bindings()
                bindings_dict[new_gesture] = bindings_dict.pop(gesture)
                self._apply_custom_bindings()
            self._rebuild_binding_rows()

        self._popup_choice_list(anchor_widget, choices, choose)

    def _on_key_change(self, gesture, keys):
        self._pending_gestures.discard(gesture)
        self._active_bindings()[gesture] = keys
        self._apply_custom_bindings()

    def _apply_custom_bindings(self):
        active = custom_bindings_module.active_bindings(self._custom_state)
        self.recognizer.set_custom_bindings(active)
        custom_bindings_module.save_state(self._custom_state)

    def _open_preset_popup(self):
        names = list(self._custom_state["presets"].keys())

        def choose(name):
            self._custom_state["active"] = name
            self._preset_btn.configure(text=name + _DROPDOWN_ARROW)
            self._apply_custom_bindings()
            self._rebuild_binding_rows()

        self._popup_choice_list(self._preset_btn, names, choose)

    def _save_as_preset(self):
        self._prompt_name("New preset name:", self._create_preset)

    def _create_preset(self, name):
        name = name.strip()
        if not name or name in self._custom_state["presets"]:
            return
        self._custom_state["presets"][name] = dict(self._active_bindings())
        self._custom_state["active"] = name
        self._preset_btn.configure(text=name + _DROPDOWN_ARROW)
        self._apply_custom_bindings()
        self._rebuild_binding_rows()

    def _delete_preset(self):
        name = self._custom_state["active"]
        if name == custom_bindings_module.DEFAULT_PRESET_NAME:
            return
        del self._custom_state["presets"][name]
        self._custom_state["active"] = custom_bindings_module.DEFAULT_PRESET_NAME
        self._preset_btn.configure(text=self._custom_state["active"] + _DROPDOWN_ARROW)
        self._apply_custom_bindings()
        self._rebuild_binding_rows()

    def _prompt_name(self, label_text, on_submit):
        win = tk.Toplevel(self.win)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=INK)
        inner = tk.Frame(win, bg=BG)
        inner.pack(padx=2, pady=2)
        tk.Label(inner, text=label_text, font=FONT_LABEL, bg=BG, fg=INK).pack(
            anchor="w", padx=10, pady=(10, 4)
        )
        entry = tk.Entry(inner, font=FONT_VALUE, bg="white", fg=INK, highlightbackground=INK,
                          highlightthickness=1, width=24)
        entry.pack(padx=10, pady=(0, 10))

        def submit(_event=None):
            value = entry.get()
            win.destroy()
            on_submit(value)

        def cancel(_event=None):
            win.destroy()

        entry.bind("<Return>", submit)
        entry.bind("<Escape>", cancel)
        RoundedButton(inner, 80, 26, color="#DDDDDD", on_click=submit, text="OK",
                      font=("Segoe UI", 9, "bold"), bg=BG).pack(pady=(0, 10))
        x = self.win.winfo_rootx() + 60
        y = self.win.winfo_rooty() + 60
        win.geometry(f"+{x}+{y}")
        win.bind("<FocusOut>", cancel)
        win.focus_force()
        entry.focus_set()

    def close(self):
        self._close_popup()
        self.win.destroy()
