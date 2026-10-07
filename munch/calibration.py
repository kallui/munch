"""Loads/saves the user's calibrated active zone (the region of the camera
frame, in normalized coords, that maps to the full screen).

A fixed margin-based zone assumes every camera's framing and every user's
seated reach are the same, which they aren't — calibration lets each person
set their own comfortable rectangle once, regardless of camera position or
angle.
"""

import json

from munch import config
from munch.paths import user_data_path

_CALIBRATION_PATH = user_data_path("calibration.json")

_MIN_ZONE_SIZE = 0.05  # reject degenerate calibrations (corners too close together)


def default_zone():
    m = config.ACTIVE_ZONE_MARGIN
    return (m, m, 1.0 - m, 1.0 - m)


def is_valid(zone):
    x_min, y_min, x_max, y_max = zone
    return (x_max - x_min) >= _MIN_ZONE_SIZE and (y_max - y_min) >= _MIN_ZONE_SIZE


def load_zone():
    try:
        with open(_CALIBRATION_PATH, "r") as f:
            data = json.load(f)
        zone = (data["x_min"], data["y_min"], data["x_max"], data["y_max"])
        if is_valid(zone):
            return zone
    except (FileNotFoundError, KeyError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return default_zone()


def save_zone(zone):
    x_min, y_min, x_max, y_max = zone
    with open(_CALIBRATION_PATH, "w") as f:
        json.dump({"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max}, f)
