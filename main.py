"""MUNCH entry point.

Wrapped in a crash log so a packaged/windowed build (no console attached)
still leaves a readable trace if startup fails, instead of just vanishing.
"""

import traceback

from munch.paths import user_data_path  # stdlib-only, so it's safe to import before anything can fail

if __name__ == "__main__":
    try:
        from munch.gui import run
        run()
    except Exception:
        with open(user_data_path("munch_crash.log"), "w") as f:
            f.write(traceback.format_exc())
        raise
