"""Floating vertical dock of square icon buttons (keyboard, mic), shown
only while MUNCH is ARMED, anchored to the screen edge.

The mic button explains itself visually rather than with text: while
listening its icon becomes sound-wave bars that move with the live input
level (flat when it hears nothing), and a caption bubble beside it
previews the words being heard. Once recording stops, the previewed words
grey out under an animated "Processing" line until the final text is
typed. Hovering either button shows a short label naming it. The dock,
labels and caption all fade in and out rather than popping.
"""

import time
import tkinter as tk
from collections import deque

from PIL import Image, ImageDraw

from munch import icons, win_utils
from munch.theme import BORDER_W, FONT_BUTTON, FONT_SUB, INK, MUTED, SHADOW_OFFSET, YELLOW
from munch.widgets import RoundedButton, fade_in, fade_out

_BTN = 52
_GAP = 10
_ICON = 28
_RECORDING = "#FF4444"

_ANIM_INTERVAL = 0.07  # seconds between icon animation frames
_DOT_STEP = 0.3  # seconds per step of the "processing" dots
_WAVE_SHAPE = (0.55, 0.8, 1.0, 0.8, 0.55)  # per-bar height multipliers, peaked in the middle
_NOISE_GATE = 0.08  # levels below this draw as flat bars, i.e. "hearing nothing"

_CAPTION_WIDTH = 380
_PROGRESS_H = 12
_ERROR_MS = 5000  # how long a "download failed" message stays up
_CAPTION_MAX_CHARS = 160  # longer previews show only their tail, so the bubble can't grow unbounded
_TOOLTIP_FADE_MS = 100


def _wave_icon(levels):
    img = Image.new("RGBA", (_ICON, _ICON), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bar_w, gap = 4, 2
    x0 = (_ICON - (len(_WAVE_SHAPE) * bar_w + (len(_WAVE_SHAPE) - 1) * gap)) // 2
    for i, (shape, level) in enumerate(zip(_WAVE_SHAPE, levels)):
        h = int(4 + (_ICON - 8) * shape * level)
        x = x0 + i * (bar_w + gap)
        y = (_ICON - h) // 2
        draw.rounded_rectangle([x, y, x + bar_w - 1, y + h - 1], radius=2, fill=INK)
    return img


def _dots_icon(phase):
    img = Image.new("RGBA", (_ICON, _ICON), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i in range(3):
        r = 4 if i == phase else 2
        cx, cy = 6 + i * 8, _ICON // 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=INK)
    return img


def _floating_window(master, bg):
    win = tk.Toplevel(master)
    # Hidden from the very first moment, before Windows ever shows it.
    # These are created at app startup; if one appeared even briefly it
    # would take the focus Windows grants a newly launched app, then hand
    # it back to whatever launched MUNCH once hidden — e.g. Explorer
    # jumping back in front of the main window right after it opens.
    win.withdraw()
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.0)  # before prevent_activation — see win_utils.set_alpha
    win.configure(bg=bg)
    win_utils.prevent_activation(win)  # never pull focus off the user's textbox
    return win


class SideDock:
    def __init__(self, master, on_keyboard_toggle, on_mic_toggle):
        self._win = _floating_window(master, INK)

        total_btn = _BTN + SHADOW_OFFSET
        screen_w = self._win.winfo_screenwidth()
        screen_h = self._win.winfo_screenheight()
        total_h = total_btn * 2 + _GAP
        self._x = screen_w - total_btn - 16
        self._y = (screen_h - total_h) // 2
        self._win.geometry(f"{total_btn}x{total_h}+{self._x}+{self._y}")

        self._mic_icon = icons.load_icon("mic", INK, _ICON)
        self._keyboard_btn = self._make_button(0, "keyboard", on_keyboard_toggle)
        self._mic_btn = self._make_button(total_btn + _GAP, "mic", on_mic_toggle)
        self._keyboard_center_y = self._y + _BTN // 2
        self._mic_center_y = self._y + total_btn + _GAP + _BTN // 2

        self._tooltip = _floating_window(master, INK)
        self._tooltip_label = tk.Label(self._tooltip, font=FONT_SUB, bg=YELLOW, fg=INK, padx=10, pady=6)
        self._tooltip_label.pack(padx=BORDER_W - 1, pady=BORDER_W - 1)
        self._bind_tooltip(self._keyboard_btn, lambda: "Keyboard", lambda: self._keyboard_center_y)
        self._bind_tooltip(
            self._mic_btn,
            lambda: "Stop voice typing" if self._mic_state == "recording" else "Voice typing",
            lambda: self._mic_center_y,
        )

        self._caption = _floating_window(master, INK)
        caption_body = tk.Frame(self._caption, bg="white")
        caption_body.pack(padx=BORDER_W, pady=BORDER_W, fill="both")
        self._caption_label = tk.Label(
            caption_body, font=FONT_BUTTON, bg="white", fg=INK, padx=12, pady=8,
            wraplength=_CAPTION_WIDTH - 24, justify="left", anchor="w",
        )
        self._caption_label.pack(fill="x")
        self._status_label = tk.Label(
            caption_body, font=FONT_SUB, bg="white", fg=INK, padx=12, anchor="w",
        )
        self._progress_bar = tk.Canvas(
            caption_body, width=_CAPTION_WIDTH - 24 - 2 * BORDER_W, height=_PROGRESS_H,
            bg="white", highlightthickness=0,
        )
        self._caption_text = ""
        self._download_fraction = 0.0

        self._mic_state = "idle"
        self._levels = deque([0.0] * len(_WAVE_SHAPE), maxlen=len(_WAVE_SHAPE))
        self._dot_phase = 0
        self._last_anim = 0.0

        self._visible = False
        self._caption_visible = False
        self._cancel_dock_fade = lambda: None
        self._cancel_caption_fade = lambda: None
        self._cancel_tooltip_fade = lambda: None

    def _make_button(self, y, icon_name, on_click):
        btn = RoundedButton(
            self._win, _BTN, _BTN, color="white", on_click=on_click,
            icon_image=icons.load_icon(icon_name, INK, _ICON), bg=INK,
        )
        btn.place(x=0, y=y)
        return btn

    # ------------------------------------------------------------------
    def _bind_tooltip(self, btn, get_text, get_center_y):
        # add="+": RoundedButton binds <Enter>/<Leave> itself for its hover
        # tint, and a plain bind would silently replace those handlers.
        btn.canvas.bind("<Enter>", lambda _e: self._show_tooltip(get_text(), get_center_y()), add="+")
        btn.canvas.bind("<Leave>", lambda _e: self._hide_tooltip(), add="+")

    def _show_tooltip(self, text, center_y):
        self._tooltip_label.configure(text=text)
        self._tooltip.update_idletasks()
        w, h = self._tooltip.winfo_reqwidth(), self._tooltip.winfo_reqheight()
        self._tooltip.geometry(f"+{self._x - w - 10}+{center_y - h // 2}")
        self._cancel_tooltip_fade()
        self._cancel_tooltip_fade = fade_in(self._tooltip, _TOOLTIP_FADE_MS)

    def _hide_tooltip(self):
        self._cancel_tooltip_fade()
        self._tooltip.withdraw()

    # ------------------------------------------------------------------
    def set_mic_state(self, state):
        """state: "idle", "recording" (listening), "transcribing"
        (recording stopped, final text being produced), or "downloading"
        (first-use speech model download)."""
        self._mic_state = state
        self._mic_btn.set_color(
            {"recording": _RECORDING, "transcribing": YELLOW, "downloading": YELLOW}.get(state, "white")
        )
        if state == "downloading":
            self._dot_phase = 0
            self._mic_btn.set_icon(_dots_icon(self._dot_phase))
            self._caption_text = ""
            self.set_download_progress(0.0)
            return
        if state == "recording":
            self._levels.extend([0.0] * len(_WAVE_SHAPE))
            self._mic_btn.set_icon(_wave_icon(self._levels))
            self._caption_label.configure(fg=INK)
        elif state == "transcribing":
            self._dot_phase = 0
            self._mic_btn.set_icon(_dots_icon(self._dot_phase))
            # Words already heard stay visible but greyed, as "pending",
            # with a moving "Processing" line making clear the final text
            # is on its way and just needs a moment.
            self._caption_label.configure(fg=MUTED)
            self._status_label.configure(text=self._processing_text())
            self._layout_caption()
        else:
            self._mic_btn.set_icon(self._mic_icon)
            self.hide_caption()

    def _processing_text(self):
        return "Processing" + "." * (self._dot_phase + 1)

    def animate(self, level):
        """Call every frame; redraws the mic icon at a steady rate. `level`
        is the live 0-1 input loudness while recording (ignored otherwise)."""
        now = time.monotonic()
        if self._mic_state in ("idle", "error") or now - self._last_anim < _ANIM_INTERVAL:
            return
        self._last_anim = now
        if self._mic_state == "recording":
            gated = max(0.0, (level - _NOISE_GATE) / (1 - _NOISE_GATE)) ** 0.5
            self._levels.append(gated)
            self._mic_btn.set_icon(_wave_icon(self._levels))
        else:
            phase = int(now / _DOT_STEP) % 3
            if phase != self._dot_phase:
                self._dot_phase = phase
                self._mic_btn.set_icon(_dots_icon(phase))
                if self._mic_state == "transcribing":
                    self._status_label.configure(text=self._processing_text())

    # ------------------------------------------------------------------
    def set_download_progress(self, fraction):
        """Shows first-use model download progress (0-1) in the bubble."""
        self._download_fraction = fraction
        self._status_label.configure(text=f"Downloading speech model… {int(fraction * 100)}%")
        bar = self._progress_bar
        bar.delete("all")
        w, h = int(bar.cget("width")), _PROGRESS_H
        bar.create_rectangle(1, 1, w - 1, h - 1, fill="white", outline=INK, width=2)
        if fraction > 0:
            bar.create_rectangle(1, 1, 1 + (w - 2) * fraction, h - 1, fill=INK, outline="")
        self._layout_caption()

    def show_download_failed(self):
        """Puts the mic back to its normal look, with a short-lived
        explanation in the bubble; clicking the mic simply retries."""
        self._mic_state = "error"
        self._mic_btn.set_color("white")
        self._mic_btn.set_icon(self._mic_icon)
        self._status_label.configure(
            text="Couldn't download the speech model.\nCheck your internet connection and try again.",
            justify="left",
        )
        self._layout_caption()
        self._win.after(_ERROR_MS, self._hide_error)

    def _hide_error(self):
        if self._mic_state == "error":  # a retry may already be using the bubble
            self._mic_state = "idle"
            self.hide_caption()

    def set_caption(self, text):
        if len(text) > _CAPTION_MAX_CHARS:
            text = "…" + text[-_CAPTION_MAX_CHARS:].lstrip()
        self._caption_text = text
        self._caption_label.configure(text=text)
        self._layout_caption()

    def _layout_caption(self):
        # Rebuilt from scratch each time so row order never drifts: words
        # first (skipped entirely if nothing was heard), then the
        # "Processing" line while the final text is being produced.
        self._caption_label.pack_forget()
        self._status_label.pack_forget()
        self._progress_bar.pack_forget()
        if self._caption_text:
            self._caption_label.pack(fill="x")
        if self._mic_state in ("transcribing", "error"):
            self._status_label.pack(fill="x", pady=(0 if self._caption_text else 8, 8))
        elif self._mic_state == "downloading":
            self._status_label.pack(fill="x", pady=(8, 4))
            self._progress_bar.pack(padx=12, pady=(0, 10), anchor="w")
        self._caption.update_idletasks()
        h = self._caption.winfo_reqheight()
        self._caption.geometry(f"{_CAPTION_WIDTH}x{h}+{self._x - _CAPTION_WIDTH - 12}+{self._mic_center_y - h // 2}")
        if self._visible and not self._caption_visible:
            self._caption_visible = True
            self._cancel_caption_fade()
            self._cancel_caption_fade = fade_in(self._caption)

    def hide_caption(self):
        self._caption_text = ""
        if self._caption_visible:
            self._caption_visible = False
            self._cancel_caption_fade()
            self._cancel_caption_fade = fade_out(self._caption, on_done=self._clear_caption_if_hidden)

    def _clear_caption_if_hidden(self):
        # A new recording can start (and set fresh text) before this fade
        # finishes — only clear if the bubble is still meant to be hidden.
        if not self._caption_visible:
            self._caption_label.configure(text="")

    # ------------------------------------------------------------------
    def set_keyboard_state(self, active):
        self._keyboard_btn.set_color(YELLOW if active else "white")

    def show(self):
        if not self._visible:
            self._visible = True
            self._cancel_dock_fade()
            self._cancel_dock_fade = fade_in(self._win)

    def hide(self):
        if self._visible:
            self._visible = False
            self._hide_tooltip()
            self.hide_caption()
            self._cancel_dock_fade()
            self._cancel_dock_fade = fade_out(self._win)

    def destroy(self):
        self._tooltip.destroy()
        self._caption.destroy()
        self._win.destroy()
