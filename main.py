"""MUNCH entry point.

Wrapped in a crash log so a packaged/windowed build (no console attached)
still leaves a readable trace if startup fails, instead of just vanishing.
"""

import os
import sys
import traceback


def _crash_log_path():
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
    return os.path.join(base, "munch_crash.log")


if __name__ == "__main__":
    try:
        from munch.gui import run
        run()
    except Exception:
        with open(_crash_log_path(), "w") as f:
            f.write(traceback.format_exc())
        raise
