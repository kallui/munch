"""Shared visual language for MUNCH's windows — one source of truth so the
palette can't silently drift between gui.py, overlay.py, and
settings_window.py (it previously was redeclared, identically, in all three).

Flat, loud colors; thick black borders; hard-offset "sticker" shadows;
bold uppercase type reserved for titles/actions/status badges — not for
full sentences, which stay in sentence case so they're actually readable.

BORDER_RADIUS/SHADOW_OFFSET/BORDER_W are taken from neobrutalism.dev's
actual published tokens (border-radius: 5px; shadow: 4px 4px 0 0 black,
no blur; border-2) rather than guessed — see munch/widgets.py for the
reusable button built around that system's exact interaction: pressing
shifts the face to where the shadow was and removes the shadow, reading
as the button physically settling flush into the page.
"""

BG = "#F5F1E6"    # paper background
INK = "#000000"   # true black — ink-on-paper, not a softened "near-black"
YELLOW = "#FFD400"
PINK = "#FF3DAE"
BLUE = "#3A86FF"
GREEN = "#06D6A0"
PURPLE = "#8338EC"

BORDER_W = 3
SHADOW_OFFSET = 4
BORDER_RADIUS = 5

# Impact for the wordmark — a real poster/brutalist display face (condensed,
# ink-heavy, built for a shout), not the generic "Segoe UI Black" every
# other Windows app reaches for. Bahnschrift (also stock on Windows) is an
# industrial grotesk, clearly distinct from Impact, for the tagline — real
# contrast between the two faces instead of one weight doing everything.
FONT_TITLE = ("Impact", 34)
FONT_SUB = ("Bahnschrift", 10)
FONT_STATUS = ("Consolas", 11, "bold")
FONT_BUTTON = ("Bahnschrift SemiBold", 14)
