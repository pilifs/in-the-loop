"""Public operation histories supported by the deterministic observer generator."""
from targets.observer_recipes import Unsupported


def select(entry, fields, inputs, api):
    raise Unsupported(f"no construction and readback for {entry} covering {', '.join(fields)}")


def body(recipe):
    raise Unsupported("unknown history family: " + recipe["family"])
