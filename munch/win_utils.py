"""Windows-specific helpers for the floating always-on-top overlays."""

try:
    import win32con
    import win32gui
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def prevent_activation(toplevel):
    """Stops a Toplevel from stealing OS focus/activation when clicked, so
    an external window you were typing into (e.g. a browser textbox)
    stays focused. Critical for the on-screen keyboard and dictation,
    which both send synthetic keystrokes to whatever window currently has
    OS focus — without this, clicking a key focused our own window
    instead, so keystrokes went nowhere useful.

    Mouse clicks on the window still work normally; only activation
    (becoming the foreground/focused window) is suppressed.
    """
    if not _AVAILABLE:
        return
    toplevel.update_idletasks()
    try:
        hwnd = toplevel.winfo_id()
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_NOACTIVATE)
    except Exception:
        pass
