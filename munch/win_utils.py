"""Windows-specific helpers for the floating always-on-top overlays."""

try:
    import win32con
    import win32gui
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

# Keeps each window's subclass callback (and the original WNDPROC it
# replaced) alive for the window's lifetime — if the Python callback gets
# garbage collected, Windows is left holding a dangling function pointer
# and crashes the process on the next click.
_subclassed = {}


def prevent_activation(toplevel):
    """Stops a Toplevel from stealing OS focus/activation when clicked, so
    an external window you were typing into (e.g. a browser textbox)
    stays focused. Critical for the on-screen keyboard and dictation,
    which both send synthetic keystrokes to whatever window currently has
    OS focus — without this, clicking a key focused our own window
    instead, so keystrokes went nowhere useful.

    WS_EX_NOACTIVATE alone only stops *automatic* activation (e.g. on
    first show) — Windows still sends WM_MOUSEACTIVATE and activates the
    window on an actual mouse click regardless of that style. Reliably
    blocking click-to-activate requires also intercepting
    WM_MOUSEACTIVATE and returning MA_NOACTIVATE, which is what the
    window subclass below does.

    Mouse clicks on the window still work normally; only activation
    (becoming the foreground/focused window) is suppressed.
    """
    if not _AVAILABLE:
        return
    toplevel.update_idletasks()
    try:
        # winfo_id() is Tk's inner client window, not the real top-level
        # wrapper Windows activates — the style and the subclass must go
        # on the wrapper, or Windows ignores them entirely.
        hwnd = win32gui.GetAncestor(toplevel.winfo_id(), win32con.GA_ROOT)
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_NOACTIVATE)

        def _wnd_proc(hwnd, msg, wparam, lparam):
            if msg == win32con.WM_MOUSEACTIVATE:
                return win32con.MA_NOACTIVATE
            return win32gui.CallWindowProc(original_proc, hwnd, msg, wparam, lparam)

        original_proc = win32gui.SetWindowLong(hwnd, win32con.GWL_WNDPROC, _wnd_proc)
        _subclassed[hwnd] = (_wnd_proc, original_proc)
    except Exception:
        pass


def set_alpha(toplevel, alpha):
    """Sets a Toplevel's opacity (0-1), for fade transitions.

    For windows made non-activating above, this must not go through Tk's
    own `-alpha` attribute: Tk rewrites the window's extended style when
    applying it, silently dropping WS_EX_NOACTIVATE — and clicks start
    stealing focus from the user's textbox again. Setting the opacity
    directly through Win32 only touches the opacity. Ordinary windows
    keep using Tk's attribute.
    """
    if _AVAILABLE:
        try:
            hwnd = win32gui.GetAncestor(toplevel.winfo_id(), win32con.GA_ROOT)
            if hwnd in _subclassed:
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if not style & win32con.WS_EX_LAYERED:
                    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_LAYERED)
                win32gui.SetLayeredWindowAttributes(hwnd, 0, int(alpha * 255), win32con.LWA_ALPHA)
                return
        except Exception:
            pass
    toplevel.attributes("-alpha", alpha)
