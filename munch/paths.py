"""Where MUNCH keeps per-user files: settings, calibration, gesture
bindings, sensitivity tuning, and the crash log.

Always %APPDATA%\\MUNCH, never next to the code. Next to the code breaks in
both shipped forms: a single-file exe runs from a temp folder that's
deleted on exit (every setting would reset each launch), and an installed
copy lives in Program Files, which apps aren't allowed to write to.
"""

import os
import shutil

_LEGACY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "MUNCH")


def user_data_path(filename):
    os.makedirs(_DATA_DIR, exist_ok=True)
    path = os.path.join(_DATA_DIR, filename)
    legacy = os.path.join(_LEGACY_DIR, filename)
    if not os.path.exists(path) and os.path.isfile(legacy):
        # One-time carry-over from older versions that saved next to the
        # code, so updating doesn't silently reset the user's setup.
        shutil.copy2(legacy, path)
    return path
