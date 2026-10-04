"""MUNCH settings window — gesture bindings, calibration, display options.

Only two pinch shapes exist today (thumb+index, thumb+middle), so binding
is a simple swap: pick which one drives left-click/drag, the other
automatically drives right-click/drag. Scroll and the wake pose each have
their own unique shape with nothing to swap against yet, so they're shown
as fixed rows (same label+value layout as the bindable ones, just not
editable) rather than dropdowns.
"""

import tkinter as tk

from munch import bindings as bindings_module
from munch.theme import BG, BORDER_W, INK, PURPLE, YELLOW

FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_LABEL = ("Segoe UI", 10, "bold")
FONT_BUTTON = ("Segoe UI", 11, "bold")
FONT_VALUE = ("Segoe UI", 9)

_ROW_LABEL_WIDTH = 17
_DROPDOWN_ARROW = "  ▾"  # small flat triangle, drawn as plain text, not a native OS widget

_PINCH_LABELS = {"index": "Thumb + index pinch", "middle": "Thumb + middle pinch"}
_OTHER_SOURCE = {"index": "middle", "middle": "index"}

_CALIBRATE_HELP = (
    "Sets how far you need to move your hand to reach the edges of your "
    "screen. Pinch at two opposite corners of your comfortable reach — "
    "top-left, then bottom-right — and MUNCH maps that rectangle to the "
    "full screen."
)


def _bordered(widget, **kwargs):
    widget.configure(highlightbackground=INK, highlightthickness=BORDER_W - 1, **kwargs)
    return widget


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
        self, master, recognizer, on_calibrate, show_overlay_var, on_overlay_changed,
        camera_index, available_cameras, on_camera_change,
    ):
        self.recognizer = recognizer
        self._on_calibrate = on_calibrate
        self._on_camera_change = on_camera_change
        self._active_popup = None

        self.win = tk.Toplevel(master)
        self.win.title("MUNCH Settings")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)

        tk.Label(self.win, text="GESTURE BINDINGS", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(16, 6)
        )
        self._left_btn = self._dropdown_row(
            "Left click / drag", list(_PINCH_LABELS.values()),
            _PINCH_LABELS[recognizer.bindings["left"]], self._on_left_change,
        )
        self._right_btn = self._dropdown_row(
            "Right click / drag", list(_PINCH_LABELS.values()),
            _PINCH_LABELS[recognizer.bindings["right"]], self._on_right_change,
        )
        self._fixed_row("Scroll", "Index + middle extended")
        self._fixed_row("Wake / arm", "Open palm, spread")

        _bordered(tk.Button(
            self.win, text="RESET TO DEFAULT PRESET", font=FONT_BUTTON,
            bg="#DDDDDD", fg=INK, activebackground="#DDDDDD", relief="flat", bd=0,
            cursor="hand2", command=self._reset_default,
        )).pack(fill="x", padx=16, pady=(10, 18))

        tk.Label(self.win, text="CAMERA", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(0, 6)
        )
        self._camera_index_by_name = {name: i for i, name in available_cameras}
        names_by_index = dict(available_cameras)
        current_name = names_by_index.get(camera_index, available_cameras[0][1])
        self._dropdown_row(
            "Device", list(self._camera_index_by_name.keys()), current_name, self._on_camera_select
        )

        tk.Label(self.win, text="DISPLAY", font=FONT_HEADING, bg=BG, fg=INK).pack(
            anchor="w", padx=16, pady=(0, 6)
        )
        tk.Checkbutton(
            self.win, text="Show gesture overlay on cursor", variable=show_overlay_var,
            command=on_overlay_changed, font=FONT_VALUE,
            bg=BG, fg=INK, activebackground=BG, selectcolor=BG, bd=0, highlightthickness=0,
        ).pack(anchor="w", padx=16, pady=(0, 18))

        calib_heading = tk.Frame(self.win, bg=BG)
        calib_heading.pack(anchor="w", padx=16, pady=(0, 6))
        tk.Label(calib_heading, text="CALIBRATION", font=FONT_HEADING, bg=BG, fg=INK).pack(side="left")
        help_badge = tk.Canvas(calib_heading, width=16, height=16, bg=BG, highlightthickness=0, cursor="hand2")
        help_badge.create_oval(1, 1, 15, 15, outline=INK, width=2)
        help_badge.create_text(8, 8, text="?", font=("Segoe UI", 8, "bold"), fill=INK)
        help_badge.pack(side="left", padx=(6, 0))
        _add_tooltip(help_badge, _CALIBRATE_HELP)

        _bordered(tk.Button(
            self.win, text="⌖  CALIBRATE REACH", font=FONT_BUTTON,
            bg=PURPLE, fg="white", activebackground=PURPLE, activeforeground="white",
            relief="flat", bd=0, cursor="hand2", command=self._calibrate_clicked,
        )).pack(fill="x", padx=16, pady=(0, 16))

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

    @staticmethod
    def _source_for_label(label):
        for source, text in _PINCH_LABELS.items():
            if text == label:
                return source
        return "index"

    def _on_left_change(self, choice):
        left_source = self._source_for_label(choice)
        right_source = _OTHER_SOURCE[left_source]
        self._right_btn.configure(text=_PINCH_LABELS[right_source] + _DROPDOWN_ARROW)
        self._apply(left_source, right_source)

    def _on_right_change(self, choice):
        right_source = self._source_for_label(choice)
        left_source = _OTHER_SOURCE[right_source]
        self._left_btn.configure(text=_PINCH_LABELS[left_source] + _DROPDOWN_ARROW)
        self._apply(left_source, right_source)

    def _apply(self, left_source, right_source):
        new_bindings = {"left": left_source, "right": right_source}
        self.recognizer.set_bindings(new_bindings)
        bindings_module.save_bindings(new_bindings)

    def _reset_default(self):
        default = bindings_module.default_bindings()
        self._left_btn.configure(text=_PINCH_LABELS[default["left"]] + _DROPDOWN_ARROW)
        self._right_btn.configure(text=_PINCH_LABELS[default["right"]] + _DROPDOWN_ARROW)
        self._apply(default["left"], default["right"])

    def _on_camera_select(self, choice):
        self._on_camera_change(self._camera_index_by_name[choice])

    def _calibrate_clicked(self):
        self.close()
        self._on_calibrate()

    def close(self):
        self._close_popup()
        self.win.destroy()
