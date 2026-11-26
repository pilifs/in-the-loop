"""Dispatch on the reviewed fields. An unimplemented observation carries its first missing operation."""
from targets import observer_io, observer_public_data, observer_state, observer_structures
from targets.observer_recipes import Unsupported


def select(entry, fields, inputs, api):
    if fields in (observer_io.STREAM, observer_io.ARCHIVE, observer_io.TOKENS):
        return observer_io.select(entry, fields, inputs, api)
    if fields in (observer_state.WEIGHTS, observer_state.TRANSITIONS, observer_state.MAP):
        return observer_state.select(entry, fields, inputs, api)
    if fields in (observer_public_data.STACK, observer_public_data.STACK_RETAINED, observer_public_data.CSS, observer_public_data.DATES):
        return observer_public_data.select(entry, fields, inputs, api)
    if fields in (observer_structures.COPIES, observer_structures.EVENTS, observer_structures.SEARCH):
        return observer_structures.select(entry, fields, inputs, api)
    raise Unsupported(f"no construction and readback for {entry} covering {', '.join(fields)}")


def body(recipe):
    if recipe["family"] in {"marked stream and retained destination", "persistent archive rename and reopen", "class-token write and read"}:
        return observer_io.body(recipe)
    if recipe["family"] in {"peek on a retained stack", "CSS grammar with typed dimension readback", "mutable Date property and copies"}:
        return observer_public_data.body(recipe)
    if recipe["family"] in {"paired mutable-property samples", "consume an event-stream response", "reopened block index and sorted hits"}:
        return observer_structures.body(recipe)
    return observer_state.body(recipe)
