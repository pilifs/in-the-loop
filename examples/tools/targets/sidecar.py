"""Loads and checks a real-world example's target.json sidecar (examples/schema/target.schema.json).

The schema checks the shape: closed objects, full commit SHAs, fixed artifact versions, relative paths. This module
adds what a schema can't: every path resolves inside the example's folder, every revision, pair and task a sidecar
names is defined, ids are unique, and task prerequisites have no cycle. A sidecar that fails any of it is refused
with SidecarError, and nothing reads it. Offline: it reads two files.
"""

import json
import re
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[2] / "schema" / "target.schema.json"
VERSION = "example-target/v1"
# A version a resolver could move: refused even where the schema's pattern lets it through.
MUTABLE_VERSION = re.compile(r"(SNAPSHOT|LATEST|RELEASE|[+\[\](),])", re.I)


class SidecarError(ValueError):
    """Why a sidecar is refused."""


def path_of(folder, example):
    """The sidecar's path, from example.json's `target`, or None for an example without one."""
    name = example.get("target")
    return Path(folder) / name if name else None


def load(folder, example):
    """The checked sidecar of the example in `folder`, or None when its example.json names none. Raises
    SidecarError for a sidecar that is missing, not JSON, invalid against the schema, or inconsistent."""
    path = path_of(folder, example)
    if path is None:
        return None
    if example.get("origin") != "real-world":
        raise SidecarError(f"{path}: only a real-world example has a target sidecar")
    if not path.is_file():
        raise SidecarError(f"{path}: example.json names it, and it does not exist")
    try:
        target = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SidecarError(f"{path}: not JSON: {e}") from None
    check(target, folder, path)
    return target


def check(target, folder, path="target.json"):
    """Raises SidecarError for the first problem in a parsed sidecar; returns None when it has none."""
    try:
        import jsonschema
    except ImportError:
        raise SidecarError(f"{path}: cannot be validated: the Python module jsonschema is not installed") from None
    schema = json.loads(SCHEMA.read_text())
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(target), key=lambda e: list(e.absolute_path))
    if errors:
        e = errors[0]
        where = "/".join(str(p) for p in e.absolute_path) or "(top level)"
        raise SidecarError(f"{path}: {where}: {e.message}")
    problems = consistency_problems(target, Path(folder))
    if problems:
        raise SidecarError(f"{path}: " + "; ".join(problems))


def files(target):
    """Every path the sidecar names, with where it names it."""
    out = []
    for i, task in enumerate(target.get("tasks", [])):
        if "claim" in task:
            out.append((f"tasks/{i}/claim", task["claim"]))
    for i, control in enumerate(target.get("controls", [])):
        out.append((f"controls/{i}/path", control["path"]))
    for i, adapter in enumerate(target.get("preparation", {}).get("adapters", [])):
        out.append((f"preparation/adapters/{i}", adapter))
    for i, blocker in enumerate(target.get("handoff", {}).get("blockers", [])):
        if "packet" in blocker:
            out.append((f"handoff/blockers/{i}/packet", blocker["packet"]))
    return out


def consistency_problems(target, folder):
    problems = []
    root = folder.resolve()
    for where, name in files(target):
        resolved = (folder / name).resolve()
        if resolved != root and root not in resolved.parents:
            problems.append(f"{where}: {name} resolves outside the example's folder")
    revisions = set(target["history"]["revisions"])
    pairs = {}
    for p in target["history"].get("pairs", []):
        if p["name"] in pairs:
            problems.append(f"pair {p['name']} is defined twice")
        pairs[p["name"]] = p
        for side in ("before", "after"):
            if p[side] not in revisions:
                problems.append(f"pair {p['name']}: {side} names revision {p[side]}, which history.revisions does not define")
        if p["before"] == p["after"]:
            problems.append(f"pair {p['name']} compares revision {p['before']} with itself")
    for a in target.get("preparation", {}).get("artifacts", []):
        if a["revision"] not in revisions:
            problems.append(f"artifact {a['coordinates']}: revision {a['revision']} is not defined")
        if MUTABLE_VERSION.search(a["coordinates"].rsplit(":", 1)[-1]):
            problems.append(f"artifact {a['coordinates']}: a mutable version is not an artifact identity")
    tasks = {}
    for t in target["tasks"]:
        if t["id"] in tasks:
            problems.append(f"task {t['id']} is defined twice")
        tasks[t["id"]] = t
    for t in target["tasks"]:
        if "revision" in t and t["revision"] not in revisions:
            problems.append(f"task {t['id']}: revision {t['revision']} is not defined")
        if "pair" in t and t["pair"] not in pairs:
            problems.append(f"task {t['id']}: pair {t['pair']} is not defined")
        for r in t.get("requires", []):
            if r not in tasks:
                problems.append(f"task {t['id']}: requires {r}, which is not a task")
        if "parent" in t and t["parent"] not in tasks:
            problems.append(f"task {t['id']}: parent {t['parent']} is not a task")
        if t.get("parent") == t["id"]:
            problems.append(f"task {t['id']} is its own parent")
    cycle = requirement_cycle(tasks)
    if cycle:
        problems.append("task prerequisites form a cycle: " + " -> ".join(cycle))
    controls = set()
    for c in target.get("controls", []):
        if c["id"] in controls:
            problems.append(f"control {c['id']} is defined twice")
        controls.add(c["id"])
        if "revision" in c and c["revision"] not in revisions:
            problems.append(f"control {c['id']}: revision {c['revision']} is not defined")
        if "task" in c and c["task"] not in tasks:
            problems.append(f"control {c['id']}: task {c['task']} is not a task")
    for b in target.get("handoff", {}).get("blockers", []):
        if "task" in b and b["task"] not in tasks:
            problems.append(f"blocker: task {b['task']} is not a task")
    return problems


def requirement_cycle(tasks):
    """One cycle among the tasks' `requires`, as a list of ids that starts and ends with the same one, or None."""
    state = {}

    def visit(tid, trail):
        state[tid] = "open"
        for r in tasks[tid].get("requires", []):
            if r not in tasks:
                continue
            if state.get(r) == "open":
                return trail[trail.index(r):] + [r] if r in trail else [tid, r]
            if r not in state:
                found = visit(r, trail + [r])
                if found:
                    return found
        state[tid] = "done"
        return None

    for tid in tasks:
        if tid not in state:
            found = visit(tid, [tid])
            if found:
                return found
    return None
