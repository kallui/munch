"""Loads/saves user-adjustable sensitivity settings (cursor smoothing,
drag-hold time, pinch sensitivity) — applied live from Settings sliders,
on top of the config.py defaults, with no restart needed.
"""

import json

from munch import config
from munch.paths import user_data_path

_TUNING_PATH = user_data_path("tuning.json")

DEFAULTS = {
    "cursor_smoothing_alpha": config.CURSOR_SMOOTHING_ALPHA,
    "drag_hold_seconds": config.DRAG_HOLD_SECONDS,
    "pinch_on_threshold": config.PINCH_ON_THRESHOLD,
}

# (min, max) each slider is allowed to set.
RANGES = {
    "cursor_smoothing_alpha": (0.05, 0.6),
    "drag_hold_seconds": (0.2, 1.2),
    "pinch_on_threshold": (0.03, 0.09),
}


def default_tuning():
    return dict(DEFAULTS)


def is_valid(data):
    if not isinstance(data, dict):
        return False
    for key, (lo, hi) in RANGES.items():
        value = data.get(key)
        if not isinstance(value, (int, float)) or not (lo <= value <= hi):
            return False
    return True


def load_tuning():
    try:
        with open(_TUNING_PATH, "r") as f:
            data = json.load(f)
        if is_valid(data):
            return data
    except (FileNotFoundError, TypeError, json.JSONDecodeError):
        pass
    return default_tuning()


def save_tuning(data):
    with open(_TUNING_PATH, "w") as f:
        json.dump(data, f)
