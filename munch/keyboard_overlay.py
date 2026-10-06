"""Big, Wii-pointer-style on-screen keyboard, docked at the bottom of the
screen so whatever you're typing into stays visible above it. Built from
the same flat, bordered "sticker" key language as the rest of the app —
large keys are forgiving targets for a pinch-click pointer."""

import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from munch import icons, win_utils
from munch.theme import BG, INK, YELLOW
from munch.widgets import hover_tint, tween

# Standard keyboard placement: backspace top-right, enter at the end of
# the home row, shift bottom-left, space bar on its own bottom row.
_LETTER_ROWS = [
    list("qwertyuiop") + ["⌫"],
    list("asdfghjkl") + ["⏎"],
    ["⇧"] + list("zxcvbnm,."),
    ["123", "SPACE", "HIDE"],
]

_SYMBOL_ROWS = [
    list("1234567890") + ["⌫"],
    list("@#$%&*-+=") + ["⏎"],
    list("!?\"':;()/_"),
    ["ABC", "SPACE", "HIDE"],
]

# Relative key widths in half-key units (a letter is 2), chosen so every
# row sums to the same total and the rows line up edge to edge.
_KEY_WIDTHS = {"⌫": 3, "⏎": 5, "⇧": 5, "123": 5, "ABC": 5, "SPACE": 13, "HIDE": 5}
_LETTER_WIDTH = 2

# Special keys sit on the paper background color instead of white —
# distinguishable from letters without turning the keyboard into a
# palette of accent colors.
_SPECIAL_KEYS = set(_KEY_WIDTHS)

# Special keys get a real icon glyph instead of a unicode character —
# crisper and more distinctive than relying on font glyph coverage.
_KEY_ICONS = {"⇧": "shift", "⌫": "backspace", "⏎": "enter", "HIDE": "keyboard-hide"}

_RADIUS = 12
_PRESS_FLASH = YELLOW
_SLIDE_PX = 40  # open/close slides just this far while fading — a hint of motion, not a big swoop


class _Key:
    """A single rounded-corner "sticker" key, drawn on a Canvas (Tkinter
    has no native border-radius) with the same hard offset-shadow
    language used for every other panel in the app. Redraws on every
    resize since the grid layout only settles on final pixel sizes after
    packing, and on every state change (hover/press/release) — hover
    only re-tints the drawn fill, never the canvas size, so neighboring
    keys never shift (changing a Frame's highlightthickness, which was
    tried first, changes its actual size and pushes the whole row around).
    Pressing also shrinks the shadow offset a touch, like the key
    physically settles closer to the surface."""

    _SHADOW = 3

    def __init__(self, parent, base_color, text="", icon_name=None):
        # width/height=1: a Canvas otherwise requests ~10cm by default, and
        # those large requested sizes skew how grid splits a row's width —
        # starting from ~0 lets the column weights alone decide key widths.
        self.canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, cursor="hand2", width=1, height=1)
        self._base_color = base_color
        self._text = text
        self._icon_name = icon_name
        self._bg_color = base_color
        self._hovering = False
        self._pressed = False
        self._shadow_offset = self._SHADOW
        self._bg_photo = None
        self._fg_photo = None
        self.canvas.bind("<Configure>", lambda e: self._redraw(e.width, e.height))

    def _update_fill(self):
        if self._pressed:
            self._bg_color = _PRESS_FLASH
        elif self._hovering:
            self._bg_color = hover_tint(self._base_color)
        else:
            self._bg_color = self._base_color
        self._redraw(self.canvas.winfo_width(), self.canvas.winfo_height())

    def set_pressed(self, pressed):
        self._pressed = pressed
        self._shadow_offset = 1 if pressed else self._SHADOW
        self._update_fill()

    def set_hover(self, hovering):
        self._hovering = hovering
        self._update_fill()

    def set_text(self, text):
        self._text = text
        self._redraw(self.canvas.winfo_width(), self.canvas.winfo_height())

    def _redraw(self, w, h):
        if w < 10 or h < 10:
            return
        shadow = self._shadow_offset
        face_w, face_h = w - shadow, h - shadow
        radius = min(_RADIUS, face_w // 4, face_h // 3)

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([shadow, shadow, w - 1, h - 1], radius=radius, fill=INK)
        draw.rounded_rectangle(
            [0, 0, face_w - 1, face_h - 1], radius=radius,
            fill=self._bg_color, outline=INK, width=3,
        )
        self._bg_photo = ImageTk.PhotoImage(img)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)
        w, h = face_w, face_h  # center content on the key face, not the shadow-inclusive canvas
        if self._icon_name:
            icon_size = max(min(w, h) - 18, 12)
            icon_image = icons.load_icon(self._icon_name, INK, icon_size)
            self._fg_photo = ImageTk.PhotoImage(icon_image)
            self.canvas.create_image(w // 2, h // 2, image=self._fg_photo)
        else:
            font_size = 16 if len(self._text) <= 1 else 12
            self.canvas.create_text(
                w // 2, h // 2, text=self._text, font=("Segoe UI", font_size, "bold"), fill=INK
            )

    def bind(self, seq, func):
        self.canvas.bind(seq, func)

    def grid(self, **kwargs):
        self.canvas.grid(**kwargs)


class KeyboardOverlay:
    def __init__(self, master, keyboard, on_close):
        self._keyboard = keyboard
        self._on_close = on_close
        self._shift_on = False
        self._symbols = False
        self._key_widgets = []  # (Key, base_char) for letter re-casing

        self._closing = False
        self._cancel_transition = lambda: None

        self._win = tk.Toplevel(master)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        # Starts fully transparent so it never flashes opaque before the
        # slide-in. Set via Tk here — before prevent_activation, which Tk's
        # own alpha handling would otherwise undo (see win_utils.set_alpha).
        self._win.attributes("-alpha", 0.0)
        self._win.configure(bg=INK)

        screen_w = self._win.winfo_screenwidth()
        self._screen_h = self._win.winfo_screenheight()
        self._height = int(self._screen_h * 0.45)
        self._width = screen_w
        self._place(_SLIDE_PX)
        win_utils.prevent_activation(self._win)

        self._body = tk.Frame(self._win, bg=BG)
        self._body.pack(fill="both", expand=True, padx=4, pady=4)

        self._render_rows()
        self._cancel_transition = tween(self._win, self._slide_in_step)

    def _place(self, offset):
        """Positions the keyboard docked to the bottom, `offset` px lower."""
        y = self._screen_h - self._height + int(offset)
        self._win.geometry(f"{self._width}x{self._height}+0+{y}")

    def _slide_in_step(self, t):
        self._place(_SLIDE_PX * (1 - t))
        win_utils.set_alpha(self._win, t)

    def _slide_out_step(self, t):
        self._place(_SLIDE_PX * t)
        win_utils.set_alpha(self._win, 1 - t)

    def _render_rows(self):
        for child in self._body.winfo_children():
            child.destroy()
        self._key_widgets = []

        rows = _SYMBOL_ROWS if self._symbols else _LETTER_ROWS
        # grid for the rows themselves, not pack — pack's space allocation
        # is greedy toward earlier children rather than splitting evenly,
        # which was starving the 3rd/4th rows of any height at all
        # (grid's row weights divide space exactly as declared).
        self._body.grid_columnconfigure(0, weight=1)
        for row_index, row in enumerate(rows):
            self._body.grid_rowconfigure(row_index, weight=1, uniform="rows")
            row_frame = tk.Frame(self._body, bg=BG)
            row_frame.grid(row=row_index, column=0, sticky="nsew", pady=3)
            row_frame.grid_rowconfigure(0, weight=1)
            for col, key in enumerate(row):
                # uniform makes column widths exactly proportional to weight,
                # so a backspace is reliably 1.5 letters wide, enter 2.5, etc.
                row_frame.grid_columnconfigure(
                    col, weight=_KEY_WIDTHS.get(key, _LETTER_WIDTH), uniform="keys"
                )
                self._make_key(row_frame, key).grid(row=0, column=col, sticky="nsew", padx=3)

    def _make_key(self, parent, key):
        is_letter = len(key) == 1 and key.isalpha()
        label = key.upper() if (is_letter and self._shift_on) else key
        base_color = BG if key in _SPECIAL_KEYS else "white"
        icon_name = _KEY_ICONS.get(key)

        widget = _Key(parent, base_color, text="" if icon_name else label, icon_name=icon_name)

        def hover_on(_event, w=widget):
            w.set_hover(True)

        def hover_off(_event, w=widget):
            w.set_hover(False)

        def press(_event, w=widget):
            w.set_pressed(True)

        def release(_event, k=key, w=widget):
            w.set_pressed(False)
            self._handle_key(k)

        widget.bind("<Enter>", hover_on)
        widget.bind("<Leave>", hover_off)
        widget.bind("<Button-1>", press)
        widget.bind("<ButtonRelease-1>", release)

        if is_letter:
            self._key_widgets.append((widget, key))
        return widget

    def _handle_key(self, key):
        if self._closing:
            return
        if key == "HIDE":
            self.close()
            return
        if key == "123":
            self._symbols = True
            self._render_rows()
            return
        if key == "ABC":
            self._symbols = False
            self._render_rows()
            return
        if key == "⇧":
            self._shift_on = not self._shift_on
            self._refresh_case()
            return
        if key == "⌫":
            self._keyboard.press_key("backspace")
            return
        if key == "⏎":
            self._keyboard.press_key("enter")
            return
        if key == "SPACE":
            self._keyboard.press_key("space")
            return

        # Plain character key.
        char = key.upper() if self._shift_on else key
        self._keyboard.type_text(char)
        if self._shift_on:
            self._shift_on = False
            self._refresh_case()

    def _refresh_case(self):
        for widget, base_char in self._key_widgets:
            widget.set_text(base_char.upper() if self._shift_on else base_char)

    def close(self):
        if self._closing:
            return
        self._closing = True
        # Report closed immediately so the dock/app state updates at once
        # (and a fresh keyboard can open right away); the window just
        # finishes sliding out on its own and then destroys itself.
        self._on_close()
        self._cancel_transition()
        tween(self._win, self._slide_out_step, on_done=self._win.destroy)
