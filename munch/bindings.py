"""Loads/saves which pinch shape triggers which click action.

Only two pinch shapes exist (thumb+index, thumb+middle), so "custom
binding" for now means choosing which of the two drives left-click/drag
and which drives right-click/drag — the other slot always gets whichever
shape isn't picked, since there are exactly two of each.
"""

import json
import os

_BINDINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bindings.json")

DEFAULT = {"left": "index", "right": "middle"}


def default_bindings():
    return dict(DEFAULT)


def is_valid(bindings):
    return (
        isinstance(bindings, dict)
        and bindings.get("left") in ("index", "middle")
        and bindings.get("right") in ("index", "middle")
        and bindings["left"] != bindings["right"]
    )


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
