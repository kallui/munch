"""On-screen overlays: a full-screen instructional overlay for calibration
(with a live tracked-hand marker so you can see it's actually following
you), and a small neo-brutalist "reticle" HUD that follows the system
cursor to show MUNCH's state."""

import tkinter as tk

from munch.theme import GREEN, INK, PURPLE, YELLOW

_KEY_COLOR = "#FF00FE"  # chroma-key background made transparent via -transparentcolor

# (label, color) per gesture, matching the main window's sticker palette.
# "wake_hold" isn't here — it gets the progress ring instead of a text tag.
GESTURE_STYLES = {
    "armed": ("ARMED", GREEN),
    "left_pinch": ("CLICK", "#FF3DAE"),
    "drag": ("DRAGGING", GREEN),
    "right_pinch": ("RIGHT CLICK", PURPLE),
    "right_drag": ("RIGHT DRAG", PURPLE),
    "middle_pinch": ("MIDDLE CLICK", "#3A86FF"),
    "middle_drag": ("MIDDLE DRAG", "#3A86FF"),
    "double_pinch": ("DOUBLE CLICK", YELLOW),
    "scroll": ("SCROLLING", "#3A86FF"),
    "ok_sign": ("OK SIGN", GREEN),
    "count_1": ("1", YELLOW),
    "count_3": ("3", YELLOW),
    "count_4": ("4", YELLOW),
    "peace_sign": ("PEACE", YELLOW),
    "slap_left": ("SLAP ←", PURPLE),
    "slap_right": ("SLAP →", PURPLE),
}

_TRACK_COLOR = "#555555"


class CursorHud:
    """A tiny, mostly-silent indicator that follows the system cursor: a
    small dot (green while armed, the gesture's color during an action),
    and — only while holding the wake pose — a circular progress pie that
    fills up clockwise instead of any text, so arming reads as "loading,"
    not more words on screen. Bordered in black to match the flat-color,
    thick-outline "sticker" language used elsewhere in the app."""

    _SIZE = 30
    _CENTER = _SIZE // 2
    _RADIUS = 11

    def __init__(self, master):
        self._win = tk.Toplevel(master)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg=_KEY_COLOR)
        try:
            self._win.attributes("-transparentcolor", _KEY_COLOR)
        except tk.TclError:
            pass  # platform doesn't support color-key transparency; HUD still works

        self._canvas = tk.Canvas(
            self._win, width=self._SIZE, height=self._SIZE,
            bg=_KEY_COLOR, highlightthickness=0,
        )
        self._canvas.pack(side="left")

        self._tag = tk.Label(
            self._win, text="", font=("Segoe UI", 10, "bold"),
            fg=INK, highlightbackground=INK, highlightthickness=2,
            padx=6, pady=1,
        )

        self._win.withdraw()
        self._visible = False

    def update(self, x, y, gesture, wake_progress=0.0, scroll_ticks=0.0):
        c, r = self._CENTER, self._RADIUS
        self._canvas.delete("all")

        if gesture == "wake_hold":
            self._draw_wake_dial(c, r, wake_progress)
            self._tag.pack_forget()
        else:
            text, color = GESTURE_STYLES.get(gesture, ("", None))
            if gesture == "scroll" and scroll_ticks:
                # Negative ticks = scroll down (see gesture_recognizer._scroll) —
                # shown live so hand orientation can be corrected in the moment,
                # not just guessed from the static cheat-sheet wording.
                text = ("↓ " if scroll_ticks < 0 else "↑ ") + text
            dot_color = color or GREEN
            dot_r = 6
            self._canvas.create_oval(
                c - dot_r, c - dot_r, c + dot_r, c + dot_r, fill=dot_color, outline=INK, width=2
            )
            if text:
                self._tag.configure(text=text, bg=color)
                self._tag.pack(side="left", padx=(5, 0))
            else:
                self._tag.pack_forget()

        self._win.geometry(f"+{x + 16}+{y + 16}")
        if not self._visible:
            self._win.deiconify()
            self._visible = True
        # Other topmost windows (the keyboard overlay, the side dock) can
        # still end up stacked above this one, since "topmost" only means
        # "above normal windows," not "above other topmost windows" — so
        # the click-feedback tag needs to actively reassert itself on top
        # every frame, or it silently renders underneath whatever topmost
        # window was created most recently.
        self._win.lift()

    def _draw_wake_dial(self, c, r, progress):
        # Dark track circle, bordered in black, with a flat yellow pie
        # wedge filling clockwise from the top as progress fills — one
        # bold bordered shape rather than a thin default-looking arc.
        self._canvas.create_oval(c - r, c - r, c + r, c + r, fill=_TRACK_COLOR, outline=INK, width=2)
        if progress > 0:
            self._canvas.create_arc(
                c - r, c - r, c + r, c + r,
                start=90, extent=-360 * progress,
                style=tk.PIESLICE, fill=YELLOW, outline=INK, width=2,
            )

    def hide(self):
        if self._visible:
            self._win.withdraw()
            self._visible = False

    def destroy(self):
        self._win.destroy()


class CalibrationOverlay:
    """Full-screen, semi-transparent instructional overlay shown while
    calibrating the active zone. Includes a marker that tracks the hand
    live, so it's obvious the app is actually watching you move."""

    def __init__(self, master, on_cancel):
        self._win = tk.Toplevel(master)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha", 0.85)
        self._win.configure(bg=INK)

        self._w = self._win.winfo_screenwidth()
        self._h = self._win.winfo_screenheight()
        self._win.geometry(f"{self._w}x{self._h}+0+0")

        self._label = tk.Label(
            self._win, text="", font=("Segoe UI", 28, "bold"),
            fg=YELLOW, bg=INK, wraplength=int(self._w * 0.8), justify="center",
        )
        self._label.place(relx=0.5, rely=0.3, anchor="center")

        self._sub = tk.Label(
            self._win, text="Press ESC to cancel", font=("Segoe UI", 12, "bold"),
            fg="#AAAAAA", bg=INK,
        )
        self._sub.place(relx=0.5, rely=0.38, anchor="center")

        # A flat bordered crosshair reticle — not an emoji, to stay
        # consistent with the rest of the app's hard-edged, no-gradients,
        # no-realistic-icons visual language.
        self._tracker_size = 40
        self._tracker = tk.Canvas(
            self._win, width=self._tracker_size, height=self._tracker_size,
            bg=INK, highlightthickness=0,
        )
        mid = self._tracker_size // 2
        self._tracker.create_oval(2, 2, self._tracker_size - 2, self._tracker_size - 2,
                                   outline=YELLOW, width=3)
        self._tracker.create_line(mid, 4, mid, self._tracker_size - 4, fill=YELLOW, width=2)
        self._tracker.create_line(4, mid, self._tracker_size - 4, mid, fill=YELLOW, width=2)

        self._win.bind("<Escape>", lambda _event: on_cancel())
        self._win.focus_force()

    def set_text(self, text):
        self._label.configure(text=text)

    def update_tracking(self, norm_pos):
        """norm_pos = (x, y) in 0-1 frame coords, or None if no hand seen."""
        if norm_pos is None:
            self._tracker.place_forget()
            self._sub.configure(text="No hand detected. Move into frame.")
            return
        x, y = norm_pos
        self._tracker.place(x=x * self._w, y=y * self._h, anchor="center")
        self._sub.configure(text="Press ESC to cancel")

    def destroy(self):
        self._win.destroy()
