"""Loads/saves which pinch shape (thumb + one other finger) triggers
which click action.

Four pinch shapes exist (thumb+index, thumb+middle, thumb+ring,
thumb+pinky) mapped to four actions (left-click/drag, right-click/drag,
double-click, middle-click) — "custom binding" means a permutation of
fingers across actions, one finger per action, no finger shared.
"""

import json

from munch.paths import user_data_path

_BINDINGS_PATH = user_data_path("bindings.json")

ACTIONS = ("left", "right", "double", "middle")
FINGERS = ("index", "middle", "ring", "pinky")

DEFAULT = {"left": "index", "right": "middle", "double": "ring", "middle": "pinky"}


def default_bindings():
    return dict(DEFAULT)


def is_valid(bindings):
    if not isinstance(bindings, dict):
        return False
    if set(bindings.keys()) != set(ACTIONS):
        return False
    values = list(bindings.values())
    return set(values) == set(FINGERS) and len(values) == len(set(values))


def load_bindings():
    try:
        with open(_BINDINGS_PATH, "r") as f:
            data = json.load(f)
        if is_valid(data):
            return data
    except (FileNotFoundError, TypeError, json.JSONDecodeError):
        pass
    return default_bindings()


def save_bindings(bindings):
    with open(_BINDINGS_PATH, "w") as f:
        json.dump(bindings, f)
