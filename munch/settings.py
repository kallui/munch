"""Loads/saves small user-facing toggles (currently just the gesture HUD)."""

import json
import os

_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")

_DEFAULTS = {"show_overlay": True}


def load():
    try:
        with open(_SETTINGS_PATH, "r") as f:
            data = json.load(f)
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except (FileNotFoundError, TypeError, json.JSONDecodeError):
        return dict(_DEFAULTS)


def save(data):
    with open(_SETTINGS_PATH, "w") as f:
        json.dump(data, f)
