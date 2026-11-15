"""Loads and checks a real-world example's target.json sidecar (examples/schema/target.schema.json).

The schema checks the shape: closed objects, full commit SHAs, fixed artifact versions, relative paths. This module
adds what a schema can't: every path resolves inside the example's folder, every revision, pair and task a sidecar
names is defined, ids are unique, task prerequisites have no cycle, and a constructed mutant stays constructed (one
patch from an upstream or fixture revision, compared only with its base in a mutation pair, never published), and a
source slice names its files and flags, with a published reference compared only in a correspondence pair. A sidecar
that fails any of it is refused
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
    for name, revision in target["history"]["revisions"].items():
        if "fixture" in revision:
            out.append((f"history/revisions/{name}/fixture", revision["fixture"]))
        if "mutant" in revision:
            out.append((f"history/revisions/{name}/mutant/patch", revision["mutant"]["patch"]))
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
    control = target["identity"]["role"] == "control"
    fixtures = [n for n, r in target["history"]["revisions"].items() if "fixture" in r]
    if fixtures and not control:
        problems.append(f"revisions {', '.join(fixtures)}: only a control may name a fixture instead of an upstream commit")
    if target.get("preparation", {}).get("route") == "fixture" and not control:
        problems.append("preparation route fixture: only a control is built from fixtures")
    problems += mutant_problems(target)
    problems += slice_problems(target)
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


def mutant_problems(target):
    """A constructed mutant stays constructed: its base is an upstream or fixture revision of the sidecar, it carries
    no upstream identity, nothing publishes it, and it is compared only in a mutation pair, against its base. A
    mutation pair's `after` is constructed: a mutant, or a control's fixture."""
    problems = []
    revisions = target["history"]["revisions"]
    for name, revision in revisions.items():
        if "mutant" not in revision:
            continue
        base = revision["mutant"]["base"]
        if base == name:
            problems.append(f"revision {name}: a mutant is not its own base")
        elif base not in revisions:
            problems.append(f"revision {name}: its base {base} is not defined")
        elif "mutant" in revisions[base]:
            problems.append(f"revision {name}: its base {base} is a mutant itself; a mutant's base is an upstream "
                            "commit or a fixture, so its provenance is one patch deep")
        upstream = [k for k in ("parent", "parentReason", "tag", "release") if k in revision]
        if upstream:
            problems.append(f"revision {name}: a constructed mutant has no upstream {', '.join(upstream)}")
    for a in target.get("preparation", {}).get("artifacts", []):
        if "mutant" in revisions.get(a["revision"], {}):
            problems.append(f"artifact {a['coordinates']}: revision {a['revision']} is a constructed mutant, which "
                            "nothing publishes")
    for p in target["history"].get("pairs", []):
        before, after = revisions.get(p["before"], {}), revisions.get(p["after"], {})
        if p["kind"] != "mutation":
            for side, revision in (("before", before), ("after", after)):
                if "mutant" in revision:
                    problems.append(f"pair {p['name']}: {side} {p[side]} is a constructed mutant, compared only in a "
                                    f"mutation pair, never in a pair of kind {p['kind']}")
            continue
        if "mutant" in before:
            problems.append(f"pair {p['name']}: before {p['before']} is a mutant; a mutation pair compares the mutant, "
                            "as after, with its base")
        if after and "commit" in after:
            problems.append(f"pair {p['name']}: after {p['after']} is an upstream commit, and a mutation pair's after "
                            "is constructed (a mutant, or a control's fixture)")
        if "mutant" in after and after["mutant"]["base"] != p["before"]:
            problems.append(f"pair {p['name']}: the mutant {p['after']} is built from {after['mutant']['base']}, and "
                            f"the pair compares it with {p['before']}")
    return problems


SLICE_FLAG = re.compile(r"^(-g|-g:none|-g:(source|lines|vars)(,(source|lines|vars))*|-parameters)$")
SLICE_VALUED = {"-source": re.compile(r"^(1\.[5-8]|[0-9]{1,2})$"), "-target": re.compile(r"^(1\.[5-8]|[0-9]{1,2})$"),
                "--release": re.compile(r"^[0-9]{1,2}$"), "-encoding": re.compile(r"^[A-Za-z0-9_.-]+$")}


def slice_flag_problems(flags):
    """What is wrong with a source-slice's javac flags: only the debugging, parameter, language-level and encoding
    flags that decide the classes' bytes, each valued flag followed by its value; never a classpath, a processor or an
    output directory, which preparation sets itself."""
    problems, i = [], 0
    while i < len(flags):
        flag = flags[i]
        if flag in SLICE_VALUED:
            if i + 1 >= len(flags) or not SLICE_VALUED[flag].match(flags[i + 1]):
                problems.append(f"slice flag {flag} needs a value it accepts")
            i += 2
            continue
        if not SLICE_FLAG.match(flag):
            problems.append(f"slice flag {flag!r} is not one a slice may set (-g, -g:none, -g:..., -parameters, -source, "
                            "-target, --release, -encoding)")
        i += 1
    return problems


def slice_problems(target):
    """The source-slice route: its recipe names files for exactly the revisions it compiles (every upstream commit
    without a route of its own; a mutant compiles its base's); a revision's own route (published-artifact) only on
    this route, for an upstream commit that is no mutant's base and has its JARs listed; and a correspondence pair
    compares one slice revision with one such published revision."""
    problems = []
    prep = target.get("preparation") or {}
    revisions = target["history"]["revisions"]
    is_slice = prep.get("route") == "source-slice"
    own = {n for n, r in revisions.items() if "route" in r}
    if own and not is_slice:
        problems.append(f"revisions {', '.join(sorted(own))}: a revision's own route is only for the source-slice "
                        "route's published references")
    if "slice" in prep and not is_slice:
        problems.append(f"preparation.slice is the source-slice route's recipe, and the route is {prep.get('route')}")
    if not is_slice:
        return problems
    recipe = prep.get("slice")
    if recipe is None:
        return problems + ["the source-slice route names no slice (files, jdk, flags)"]
    compiled = {n for n, r in revisions.items() if "commit" in r and "route" not in r}
    files = set(recipe["files"])
    for name in sorted(files - compiled):
        why = ("not defined" if name not in revisions else "a mutant, which compiles its base's files" if "mutant" in
               revisions[name] else "published by its own route")
        problems.append(f"slice.files names revision {name}, which is {why}")
    for name in sorted(compiled - files):
        problems.append(f"revision {name} is compiled by the slice, and slice.files names no files for it")
    problems += slice_flag_problems(recipe["flags"])
    for name in sorted(set(recipe.get("matches") or {}) - files):
        problems.append(f"slice.matches names revision {name}, whose slice.files it doesn't compile")
    listed ={a["revision"] for a in prep.get("artifacts", [])}
    bases = {r["mutant"]["base"] for r in revisions.values() if "mutant" in r}
    for name in sorted(own):
        if "commit" not in revisions[name]:
            problems.append(f"revision {name}: only an upstream commit has a published route of its own")
        if name in bases:
            problems.append(f"revision {name}: a published reference is no mutant's base")
        if name not in listed:
            problems.append(f"revision {name} has its own published route and preparation.artifacts lists no JAR for it")
    for p in target["history"].get("pairs", []):
        sides = {p["before"], p["after"]}
        if p["kind"] == "correspondence" and (len(sides & own) != 1 or len(sides & compiled) != 1):
            problems.append(f"pair {p['name']}: a correspondence compares one slice revision with one published "
                            "reference")
        elif p["kind"] != "correspondence" and sides & own:
            problems.append(f"pair {p['name']}: the published reference {', '.join(sorted(sides & own))} is compared "
                            "only in a correspondence pair")
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
