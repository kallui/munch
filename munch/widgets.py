"""Shared neo-brutalist "sticker" button, built around neobrutalism.dev's
actual published tokens (border-radius: 5px; shadow: 4px 4px 0 0 black,
no blur; 2-4px border) and its signature press interaction: the face
shifts to where the shadow was and the shadow disappears on press,
restoring on release — reading as the button physically settling flush
into the page, rather than the plain color-swap feedback used before
this was adopted project-wide.
"""

import tkinter as tk

from PIL import Image, ImageColor, ImageDraw, ImageTk

from munch.theme import BG, BORDER_RADIUS, BORDER_W, INK, SHADOW_OFFSET

_HOVER_GREY = 150
_HOVER_AMOUNT = 0.35


def hover_tint(color, amount=_HOVER_AMOUNT, grey=_HOVER_GREY):
    """Blend `color` toward a neutral grey — the one hover effect used
    everywhere in this app. Border/shadow colors never change on hover,
    only this fill tint, so the shape's outline always stays put."""
    r, g, b = ImageColor.getrgb(color)
    r = int(r * (1 - amount) + grey * amount)
    g = int(g * (1 - amount) + grey * amount)
    b = int(b * (1 - amount) + grey * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def rounded_rect_image(w, h, radius, fill, outline=None, outline_width=0):
    """A PIL RGBA image of a rounded rectangle — Tkinter has no native
    border-radius, so every rounded shape in this app is rasterized."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    inset = outline_width / 2
    ImageDraw.Draw(img).rounded_rectangle(
        [inset, inset, w - 1 - inset, h - 1 - inset],
        radius=radius, fill=fill, outline=outline, width=outline_width,
    )
    return img


class RoundedButton:
    """A Canvas-based button: rounded corners, a hard offset shadow, and
    the neobrutalism.dev press interaction in place of a plain color
    swap. `icon_image` (a PIL Image, see munch/icons.py) takes priority
    over `text` when both are given."""

    def __init__(
        self, parent, width, height, color, on_click,
        text="", icon_image=None, fg=INK, font=("Segoe UI", 12, "bold"),
        radius=BORDER_RADIUS, shadow=SHADOW_OFFSET, border_width=BORDER_W, bg=BG,
    ):
        self._w, self._h = width, height
        self._color = color
        self._fg = fg
        self._text = text
        self._icon_image = icon_image
        self._font = font
        self._radius = radius
        self._shadow = shadow
        self._border_width = border_width
        self._pressed = False
        self._hovering = False
        self._on_click = on_click

        total_w, total_h = width + shadow, height + shadow
        self.canvas = tk.Canvas(
            parent, width=total_w, height=total_h, bg=bg, highlightthickness=0, cursor="hand2"
        )
        self._shadow_photo = None
        self._face_photo = None
        self._icon_photo = None
        self._redraw()

        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def _redraw(self):
        w, h, s = self._w, self._h, self._shadow
        self.canvas.delete("all")

        if not self._pressed:
            shadow_img = rounded_rect_image(w, h, self._radius, INK)
            self._shadow_photo = ImageTk.PhotoImage(shadow_img)
            self.canvas.create_image(s, s, anchor="nw", image=self._shadow_photo)

        face_xy = s if self._pressed else 0
        fill = hover_tint(self._color) if self._hovering else self._color
        face_img = rounded_rect_image(
            w, h, self._radius, fill, outline=INK, outline_width=self._border_width
        )
        self._face_photo = ImageTk.PhotoImage(face_img)
        self.canvas.create_image(face_xy, face_xy, anchor="nw", image=self._face_photo)

        cx, cy = face_xy + w // 2, face_xy + h // 2
        if self._icon_image is not None:
            self._icon_photo = ImageTk.PhotoImage(self._icon_image)
            self.canvas.create_image(cx, cy, image=self._icon_photo)
        elif self._text:
            self.canvas.create_text(cx, cy, text=self._text, font=self._font, fill=self._fg)

    def _on_enter(self, _event):
        self._hovering = True
        self._redraw()

    def _on_leave(self, _event):
        self._hovering = False
        if self._pressed:
            self._pressed = False
        self._redraw()

    def _on_press(self, _event):
        self._pressed = True
        self._redraw()

    def _on_release(self, _event):
        was_pressed = self._pressed
        self._pressed = False
        self._redraw()
        if was_pressed:
            self._on_click()

    def set_text(self, text):
        self._text = text
        self._redraw()

    def set_color(self, color):
        self._color = color
        self._redraw()

    def place(self, **kwargs):
        self.canvas.place(**kwargs)

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        self.canvas.grid(**kwargs)
