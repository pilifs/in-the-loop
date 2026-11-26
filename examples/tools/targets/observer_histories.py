"""Dispatch on the reviewed fields. An unimplemented observation carries its first missing operation."""
from targets import observer_io, observer_state
from targets.observer_recipes import Unsupported


def select(entry, fields, inputs, api):
    if fields in (observer_io.STREAM, observer_io.ARCHIVE, observer_io.TOKENS):
        return observer_io.select(entry, fields, inputs, api)
    if fields in (observer_state.WEIGHTS, observer_state.TRANSITIONS, observer_state.MAP):
        return observer_state.select(entry, fields, inputs, api)
    raise Unsupported(f"no construction and readback for {entry} covering {', '.join(fields)}")


def body(recipe):
    if recipe["family"] in {"marked stream and retained destination", "persistent archive rename and reopen", "class-token write and read"}:
        return observer_io.body(recipe)
    return observer_state.body(recipe)
