"""Loads/saves custom gesture -> keyboard key/combo bindings, saved as
named presets (Default + any user-created ones). Independent of
bindings.py (the 4 mouse-click pinch permutation) — these target
arbitrary keyboard output instead, and any number can be bound at once.
"""

import json
import os

_PRESETS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "custom_presets.json")

GESTURES = ("ok_sign", "count_1", "count_3", "count_4", "peace_sign", "slap_left", "slap_right")

GESTURE_LABELS = {
    "ok_sign": "OK sign", "count_1": "1 finger up", "count_3": "3 fingers up",
    "count_4": "4 fingers up", "peace_sign": "Peace sign (spread)",
    "slap_left": "Slap left", "slap_right": "Slap right",
}

DEFAULT_PRESET_NAME = "Default"


def default_presets():
    return {"active": DEFAULT_PRESET_NAME, "presets": {DEFAULT_PRESET_NAME: {}}}


def is_valid_combo(keys):
    return isinstance(keys, list) and len(keys) >= 1 and all(isinstance(k, str) and k for k in keys)


def is_valid_bindings(bindings):
    """bindings: {gesture: [keys...]} — any subset of GESTURES, each a
    valid combo. A dict can't have a duplicate key, so "one finger used
    twice" isn't a concern here the way it is for bindings.py."""
    if not isinstance(bindings, dict):
        return False
    for gesture, keys in bindings.items():
        if gesture not in GESTURES or not is_valid_combo(keys):
            return False
    return True


def is_valid_state(state):
    if not isinstance(state, dict) or "active" not in state or "presets" not in state:
        return False
    presets = state["presets"]
    if not isinstance(presets, dict) or DEFAULT_PRESET_NAME not in presets:
        return False
    if state["active"] not in presets:
        return False
    return all(is_valid_bindings(b) for b in presets.values())


def load_state():
    try:
        with open(_PRESETS_PATH, "r") as f:
            data = json.load(f)
        if is_valid_state(data):
            return data
    except (FileNotFoundError, TypeError, json.JSONDecodeError):
        pass
    return default_presets()


def save_state(state):
    with open(_PRESETS_PATH, "w") as f:
        json.dump(state, f)


def active_bindings(state):
    """gesture -> keys list, for whichever preset is marked active."""
    return dict(state["presets"][state["active"]])


def format_combo(keys):
    return "+".join(keys)
