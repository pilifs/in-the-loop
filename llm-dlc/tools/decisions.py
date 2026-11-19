#!/usr/bin/env python3
"""A parallel run's decision record: llm-dlc/decisions/NAME.jsonl, and the views made from it.

The conductor of a parallel run (llm-dlc/loops/stream-conductor.md) decides what it safely can and
records each decision, so the user reviews afterwards instead of approving first; what it can't
decide it queues for the user as an open question. The watcher of a proof loop is a conductor too, and
its answers to the loop's questions are decisions here (conductor.py writes them, to the record named
after the run: prove-change). The record is the one place both are kept:

  llm-dlc/decisions/NAME.jsonl   one JSON object per line, appended, never edited (schema.json)
  llm-dlc/decisions/NAME.md      the review view, generated: flagged first, then open questions, then
                                 decisions not reviewed yet, then the rest

A line is one change of state. A decision line is the conductor's full snapshot of one decision;
a review line (accepted, overturned) and an answer line (the option chosen for an open question)
are the user's. A decision's current state is its latest decision line with the user's lines after
it laid over it. Nobody edits the JSON by hand: the conductor writes with `record` and `depend`,
the user (or a session acting on the user's words) with `review` and `answer`.

Commands (ID is NAME-D007, or D007 when one record holds it or --name says which; a range D003-D007
takes every decision in it):

  decisions.py list [NAME...] [--group G,...] [--markdown]
                    one line per decision, in the view's order; --markdown gives the list the merge
                    loop puts in its for-review list (--group flagged,unreviewed)
  decisions.py show ID [--history]
                    one decision as the view shows it; --history adds its lines
  decisions.py counts [NAME...]
                    open, flagged and unreviewed decisions, on one line (for a status bar)
  decisions.py review accept ID... [--note TEXT] [--name NAME]
  decisions.py review overturn ID... --note TEXT [--name NAME]
                    the user's review of decided decisions: overturn says what they would rather have
  decisions.py answer ID OPTION [--note TEXT] [--name NAME]
                    the user's answer to an open question: an option's id, or `other` with a note
  decisions.py record NAME [--run TIME] < JSON
                    the conductor's write: a JSON object, or an array written as one change. An
                    object without an id is a new decision (open, or decided); one with an id is laid
                    over that decision's current state (objects merged, anything else replaced). A
                    decision taken without a review gets the one the action table gives: unreviewed,
                    or flagged when costly or of medium confidence
  decisions.py depend ID [--commit CHANGE]... [--job JOB]...
                    add what was built on a decision since; past the threshold (three commits or any
                    job) one not yet reviewed is flagged again, before overturning it gets expensive
  decisions.py render [NAME...]
                    rewrite the views (sync.py does it with its other generated files)
  decisions.py check
                    what `sync.py check` reports about the records; exits 1 if anything

Every write is checked against the whole record first and refused if it would leave a problem, and
rewrites the view. A write is committed like any other change (`sync.py commit`).

Standard library only, as sync.py, which imports it.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DECISIONS = REPO / "llm-dlc" / "decisions"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "decisions" / "schema.json"  # always this tool's own

# Past these, a decision not reviewed yet is flagged again: the user's rule weighs how hard a decision
# is to undo, and that grows with what is built on it (stream-conductor.md, Design 3).
DEPENDENTS_THRESHOLD = {"commits": 3, "jobs": 1}

# What the conductor may decide without the user, and the review it starts with (Design 3's table).
# Anything else is queued for the user.
DELEGATED = {("high", "cheap"): None, ("high", "costly"): "costly", ("medium", "cheap"): "medium-confidence"}

GROUPS = ("flagged", "open", "unreviewed", "overturned", "settled")
HEADINGS = {"flagged": "Flagged for review", "open": "Open: waiting for the user",
            "unreviewed": "Decided, not reviewed yet", "overturned": "Overturned, waiting for the conductor",
            "settled": "Settled"}
ID_RE = re.compile(r"^(?:(?P<name>[a-z0-9][a-z0-9-]*)-)?D(?P<a>[0-9]{3,})(?:(?:-|–|\.\.)D?(?P<b>[0-9]{3,}))?$")


class RecordError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_path(name: str, root: Path) -> Path:
    return root / f"{name}.jsonl"


def view_path(name: str, root: Path) -> Path:
    return root / f"{name}.md"


def record_names(root: Path) -> list[str]:
    return sorted(p.stem for p in root.glob("*.jsonl")) if root.is_dir() else []


def parse(text: str, where: str) -> list[dict]:
    lines = []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RecordError(f"{where} line {n}: not JSON ({e.msg})") from None
        if not isinstance(line, dict):
            raise RecordError(f"{where} line {n}: not a JSON object")
        lines.append(line)
    return lines


def read(name: str, root: Path) -> list[dict]:
    path = record_path(name, root)
    return parse(path.read_text(), f"{path.name}") if path.exists() else []


# The schema: a validator for the part of JSON Schema that schema.json uses, so that check needs
# nothing outside the standard library. test_decisions.py compares it with jsonschema where that
# is installed.

_TYPES = {"null": lambda v: v is None, "string": lambda v: isinstance(v, str),
          "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
          "boolean": lambda v: isinstance(v, bool), "object": lambda v: isinstance(v, dict),
          "array": lambda v: isinstance(v, list)}
_schema_cache: dict | None = None


def schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(SCHEMA_PATH.read_text())
    return _schema_cache


def _resolve(node: dict, root: dict) -> dict:
    while "$ref" in node and len(node) == 1:
        node = root["$defs"][node["$ref"].removeprefix("#/$defs/")]
    return node


def _plausible(value, node: dict, root: dict) -> bool:
    """Whether `value` is the kind of thing a oneOf branch describes, to report the right branch's errors."""
    node = _resolve(node, root)
    if "type" in node:
        return _TYPES[node["type"]](value)
    kind = node.get("properties", {}).get("kind", {}).get("const")
    return kind is None or (isinstance(value, dict) and value.get("kind") == kind)


def schema_errors(value, node: dict | None = None, root: dict | None = None, where: str = "") -> list[str]:
    root = root or schema()
    node = root if node is None else node
    at = where or "the line"
    errors = []
    if "$ref" in node:
        errors += schema_errors(value, root["$defs"][node["$ref"].removeprefix("#/$defs/")], root, where)
    if "oneOf" in node:
        results = [(b, schema_errors(value, b, root, where)) for b in node["oneOf"]]
        passed = [b for b, e in results if not e]
        if len(passed) > 1:
            errors.append(f"{at}: matches more than one shape")
        elif not passed:
            near = [e for b, e in results if _plausible(value, b, root)] or [e for _, e in results]
            errors += min(near, key=len)
    if "const" in node and value != node["const"]:
        errors.append(f"{at}: must be {json.dumps(node['const'])}")
    if "enum" in node and value not in node["enum"]:
        errors.append(f"{at}: must be one of {', '.join(json.dumps(v) for v in node['enum'])}")
    if "type" in node and not _TYPES[node["type"]](value):
        return errors + [f"{at}: must be {'an' if node['type'][0] in 'aeiou' else 'a'} {node['type']}"]
    if isinstance(value, str):
        if len(value) < node.get("minLength", 0):
            errors.append(f"{at}: must not be empty")
        if "pattern" in node and not re.search(node["pattern"], value):
            errors.append(f"{at}: {value!r} is not of the form {node['pattern']}")
    if _TYPES["integer"](value) and "minimum" in node and value < node["minimum"]:
        errors.append(f"{at}: must be at least {node['minimum']}")
    if isinstance(value, list):
        if len(value) < node.get("minItems", 0):
            errors.append(f"{at}: needs at least {node['minItems']} item(s)")
        if "items" in node:
            for i, item in enumerate(value):
                errors += schema_errors(item, node["items"], root, f"{where}[{i}]")
    if isinstance(value, dict):
        props = node.get("properties", {})
        for key in node.get("required", ()):
            if key not in value:
                errors.append(f"{at}: {key} is missing")
        for key, item in value.items():
            if key in props:
                errors += schema_errors(item, props[key], root, f"{where}.{key}" if where else key)
            elif node.get("additionalProperties") is False:
                errors.append(f"{at}: {key} is not a field")
    return errors


# The current state

def fold(lines: list[dict]) -> dict[str, dict]:
    """Each decision's current state, by id, in the order first asked: its latest decision line,
    with the user's review and answer lines after it laid over it. `answer` is the user's answer
    since that line (None if none), and `history` every line about it."""
    out: dict[str, dict] = {}
    for line in lines:
        i = line.get("id")
        if line.get("kind") == "decision":
            history = out[i]["history"] if i in out else []
            out[i] = {**copy.deepcopy(line), "answer": None, "history": history + [line]}
        elif i in out:
            d = out[i]
            d["history"].append(line)
            if line.get("kind") == "review":
                d["review"] = {"state": line["state"], **({"note": line["note"]} if "note" in line else {})}
            elif line.get("kind") == "answer":
                d["answer"] = {k: line[k] for k in ("option", "note", "at") if k in line}
    return out


def dependents_grown(d: dict) -> bool:
    deps = (d.get("decision") or {}).get("recovery", {}).get("dependents", {})
    return any(len(deps.get(k, [])) >= n for k, n in DEPENDENTS_THRESHOLD.items())


def effective_review(d: dict) -> dict | None:
    """The review the views show: a decision not reviewed yet whose dependents passed the threshold
    shows as flagged even before the conductor records that."""
    r = d.get("review")
    if d.get("state") == "decided" and r and r.get("state") == "unreviewed" and dependents_grown(d):
        return {"state": "flagged", "why": "dependents-grown"}
    return r


def group(d: dict) -> str:
    if d["state"] == "open":
        return "open"
    if d["state"] == "superseded":
        return "settled"
    state = (effective_review(d) or {}).get("state")
    return {"flagged": "flagged", "unreviewed": "unreviewed", "overturned": "overturned"}.get(state, "settled")


def ordered(current: dict[str, dict]) -> list[dict]:
    return sorted(current.values(), key=lambda d: (GROUPS.index(group(d)), _number(d["id"])))


def _number(i: str) -> int:
    return int(i.rsplit("-D", 1)[1])


def counts(current: dict[str, dict]) -> dict[str, int]:
    c = dict.fromkeys(GROUPS, 0)
    for d in current.values():
        c[group(d)] += 1
    return c


def counts_line(name: str, current: dict[str, dict]) -> str:
    c = counts(current)
    parts = [f"{c['open']} open", f"{c['flagged']} flagged", f"{c['unreviewed']} unreviewed"]
    if c["overturned"]:
        parts.append(f"{c['overturned']} overturned")
    return f"{name}: " + ", ".join(parts)


# Problems: what the schema can't say

def problems(root: Path, label: str = "llm-dlc/decisions") -> list[str]:
    """Everything wrong with the records under `root`, as `sync.py check` errors: lines the schema
    refuses, seq out of order, ids that don't exist, decisions the conductor may not take alone or
    took without the flag they need, reviews it wrote for the user, and views out of date."""
    errors = []
    for name in record_names(root):
        where = f"{label}/{name}.jsonl"
        try:
            lines = read(name, root)
        except RecordError as e:
            errors.append(f"{label}/{e}")
            continue
        errors += record_problems(name, lines, where)
        view = view_path(name, root)
        if not view.exists() or view.read_text() != render(name, lines):
            errors.append(f"{label}/{name}.md does not match {name}.jsonl (run: python3 llm-dlc/tools/decisions.py render)")
    for view in sorted(root.glob("*.md")) if root.is_dir() else ():
        if not record_path(view.stem, root).exists():
            errors.append(f"{label}/{view.name} has no record {view.stem}.jsonl")
    return errors


def record_problems(name: str, lines: list[dict], where: str) -> list[str]:
    errors, current, user_review, answered = [], {}, {}, {}
    for n, line in enumerate(lines, 1):
        at = f"{where} line {n}"
        found = schema_errors(line)
        if found:
            errors += [f"{at}: {e}" for e in found]
            continue
        if line["seq"] != n:
            errors.append(f"{at}: seq is {line['seq']}, not its line number {n}")
        i = line["id"]
        if not i.startswith(f"{name}-D"):
            errors.append(f"{at}: {i} is not an id of the record {name} ({name}-D001, ...)")
        before = current.get(i)
        if line["kind"] == "decision":
            errors += [f"{at}: {e}" for e in decision_problems(line, before, user_review, answered.get(i))]
            current[i] = line
            if line["state"] != "open":
                answered.pop(i, None)
        elif before is None:
            errors.append(f"{at}: the user's {line['kind']} names {i}, which has no decision line before it")
        elif line["kind"] == "review":
            if before["state"] != "decided":
                errors.append(f"{at}: {i} is {before['state']}, so there is nothing to review")
            elif before["decision"]["by"] == "user":
                errors.append(f"{at}: {i} was decided by the user, so there is nothing to review")
            if line["state"] == "overturned" and "note" not in line:
                errors.append(f"{at}: an overturn needs a note saying what the user would rather have")
            user_review[i] = line["state"]
        else:
            if before["state"] != "open":
                errors.append(f"{at}: {i} is {before['state']}, not an open question")
            elif line["option"] not in {o["id"] for o in before["options"]} | {"other"}:
                errors.append(f"{at}: {line['option']} is not one of {i}'s options, nor other")
            if line["option"] == "other" and "note" not in line:
                errors.append(f"{at}: an answer of other needs a note saying what")
            answered[i] = line["option"]
    for i, d in current.items():
        if d["supersedes"]:
            target = current.get(d["supersedes"])
            if target is None:
                errors.append(f"{where}: {i} supersedes {d['supersedes']}, which is not in the record")
            elif target["state"] != "superseded":
                errors.append(f"{where}: {i} supersedes {d['supersedes']}, whose latest line is {target['state']}, "
                              "not superseded")
        if d["state"] == "superseded" and not any(o["supersedes"] == i for o in current.values()):
            errors.append(f"{where}: {i} is superseded, but no decision supersedes it")
    return errors


def decision_problems(line: dict, before: dict | None, reviews: dict[str, str], answered: str | None) -> list[str]:
    """A decision line's problems, given its previous line, the user's latest review of each decision so
    far, and the user's answer to it since it was asked."""
    errors, state, decision, review = [], line["state"], line["decision"], line["review"]
    user_review = reviews.get(line["id"])
    if before and before["run"] != line["run"]:
        errors.append(f"run changed from {before['run']}: a decision stays with the run that asked it")
    if before is None and state == "superseded":
        errors.append("a decision's first line can't be superseded")
    if line["supersedes"] == line["id"]:
        errors.append("a decision can't supersede itself")
    if state == "open":
        if decision is not None or review is not None:
            errors.append("an open question has no decision and no review yet")
        if before and before["state"] != "open":
            errors.append(f"it was {before['state']}: a decision is never reopened; supersede it with a new question")
        return errors
    if state == "decided" and (decision is None or review is None):
        return errors + ["a decided line needs its decision and its review"]
    if decision is not None:
        if decision["option"] not in {o["id"] for o in line["options"]} and decision["option"] != "other":
            errors.append(f"the decision's option {decision['option']} is not one of the options")
        if before and before["decision"] and {k: before["decision"][k] for k in ("option", "by")} != \
                {k: decision[k] for k in ("option", "by")}:
            errors.append("a decision once taken is not changed: supersede it with a new one")
        if state == "decided" and line["blocks"]:
            errors.append("blocks must be empty once it is decided")
    if decision and decision["by"] == "user":
        if review and review["state"] != "accepted":
            errors.append("a decision the user took is accepted as it is: its review must be accepted")
        overturned = line["supersedes"] and reviews.get(line["supersedes"]) == "overturned"
        if (not before or before["state"] == "open") and answered != decision["option"] and not overturned:
            errors.append(f"decided by the user as {decision['option']}, but there is no answer from the user to it, "
                          "and it supersedes no decision the user overturned")
        return errors
    if decision and decision["by"] == "conductor":
        key = (decision["confidence"]["level"], decision["recovery"]["class"])
        if key not in DELEGATED:
            errors.append(f"the conductor decided a {key[0]}-confidence, {key[1]} decision: that is the user's "
                          "(stream-conductor.md, Design 3)")
        elif review and DELEGATED[key] and review["state"] in ("unreviewed",) and not user_review:
            errors.append(f"a {key[0]}-confidence, {key[1]} decision is flagged for review, not left unreviewed")
    if review:
        if user_review and review["state"] != user_review:
            errors.append(f"the user's review says {user_review}, and this line says {review['state']}: "
                          "the conductor carries the user's review forward")
        if not user_review and review["state"] in ("accepted", "overturned"):
            errors.append(f"review {review['state']} with no review line from the user: only the user reviews")
        if review["state"] == "flagged" and "why" not in review:
            errors.append("a flagged review says why")
    return errors


# The view

def _when(t: str) -> str:
    return t.replace("T", " ")[:16]


def _context(ctx: dict) -> str:
    parts = [f"{k} {', '.join(f'`{v}`' for v in vs)}" for k, vs in ctx.items() if vs]
    return "; ".join(parts)


def entry(d: dict) -> list[str]:
    """One decision's section of the view."""
    options = {o["id"]: o for o in d["options"]}
    out = [f"### {d['id']}: {d['asked']['question']}", ""]
    asked = f"- **Asked** by {d['asked']['by']}, {_when(d['asked']['at'])}"
    if ctx := _context(d["context"]):
        asked += f"; about {ctx}"
    out.append(asked)
    for o in d["options"]:
        chosen = " **(chosen)**" if d["decision"] and d["decision"]["option"] == o["id"] else ""
        out.append(f"  - `{o['id']}`{chosen}: {o['summary']}. *{o['consequences']}*")
    if d["answer"]:
        note = f": {d['answer']['note']}" if d["answer"].get("note") else ""
        out.append(f"- **Answered** `{d['answer']['option']}` by the user, {_when(d['answer']['at'])}{note}; "
                   "the conductor applies it next")
    if dec := d["decision"]:
        summary = options[dec["option"]]["summary"] if dec["option"] in options else "other"
        out.append(f"- **Decided** `{dec['option']}` ({summary}) by the {dec['by']}, {_when(dec['at'])}: "
                   f"{dec['rationale']}")
        out.append(f"- **Confidence** {dec['confidence']['level']}: {dec['confidence']['basis']}")
        deps = dec["recovery"]["dependents"]
        built = ", ".join(f"{len(deps[k])} {k if len(deps[k]) > 1 else k[:-1]} ({', '.join(f'`{v}`' for v in deps[k])})"
                          for k in ("commits", "jobs") if deps[k]) or "nothing yet"
        out.append(f"- **Recovery** {dec['recovery']['class']}: {dec['recovery']['undo']} Built on it: {built}.")
    review = effective_review(d)
    if review and d["state"] != "superseded":
        line = f"- **Review** {review['state']}"
        if review.get("why"):
            line += f" ({review['why']})"
        if review.get("note"):
            line += f": {review['note']}"
        out.append(line)
    if d["state"] == "superseded":
        out.append("- **Superseded**" + (f"; it was {d['review']['state']}" if d["review"] else ""))
    if d["blocks"]:
        out.append(f"- **Blocks** {', '.join(d['blocks'])}")
    if d["supersedes"]:
        out.append(f"- **Supersedes** {d['supersedes']}")
    applied = [f"{a['stream']} inbox `{a['item']}`" for a in d["applied"]["inbox"]] + \
              [f"`{c}`" for c in d["applied"]["commits"]]
    if applied:
        out.append(f"- **Applied** {', '.join(applied)}")
    return out + [""]


def settled_line(d: dict) -> str:
    if d["state"] == "superseded":
        how = "superseded"
    else:
        how = d["review"]["state"] if d["decision"]["by"] == "conductor" else "decided by the user"
    dec = d["decision"]
    chosen = f" → `{dec['option']}`" if dec else ""
    return f"- {d['id']} ({how}): {d['asked']['question']}{chosen}"


def render(name: str, lines: list[dict]) -> str:
    current = fold(lines)
    c = counts(current)
    out = [f"# Decisions: {name}", "",
           f"Generated by `llm-dlc/tools/decisions.py` from [`{name}.jsonl`]({name}.jsonl): don't edit it. The user "
           "reviews with `decisions.py review accept ID...` or `decisions.py review overturn ID --note TEXT`, and "
           "answers an open question with `decisions.py answer ID OPTION`.", "",
           f"**{len(current)} decision(s):** " + ", ".join(f"{c[g]} {g}" for g in GROUPS if c[g]) if current
           else "No decisions yet.", ""]
    for g in GROUPS:
        members = [d for d in ordered(current) if group(d) == g]
        if not members:
            continue
        out += [f"## {HEADINGS[g]}", ""]
        if g == "settled":
            out += [settled_line(d) for d in members] + [""]
        else:
            for d in members:
                out += entry(d)
    return "\n".join(out).rstrip("\n") + "\n"


def render_all(root: Path) -> list[Path]:
    """Rewrite each record's view; a record that can't be read (a merge left markers in it) keeps
    its view as it is. Returns the views written."""
    written = []
    for name in record_names(root):
        try:
            text = render(name, read(name, root))
        except (RecordError, KeyError, TypeError, ValueError):
            continue
        path = view_path(name, root)
        if not path.exists() or path.read_text() != text:
            path.write_text(text)
            written.append(path)
    return written


# Writes

def write(name: str, root: Path, new: list[dict]) -> None:
    """Append `new` to the record, numbered, once the record with them has no problem it didn't have."""
    lines = read(name, root)
    for k, line in enumerate(new):
        line["seq"] = len(lines) + k + 1
    where = f"{name}.jsonl"
    old = set(record_problems(name, lines, where))
    found = [p for p in record_problems(name, lines + new, where) if p not in old]
    if found:
        raise RecordError("refused, nothing written:\n" + "\n".join(f"  {p}" for p in found))
    root.mkdir(parents=True, exist_ok=True)
    with record_path(name, root).open("a") as f:
        for line in new:
            f.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")
    view_path(name, root).write_text(render(name, lines + new))


def snapshot(d: dict) -> dict:
    """A folded decision as a decision line again, without what fold added."""
    return {k: copy.deepcopy(v) for k, v in d.items() if k not in ("answer", "history")}


def merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in patch.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def conductor_line(name: str, patch: dict, current: dict[str, dict], run: str | None, stamp: str,
                   taken: list[int]) -> dict:
    """The decision line a `record` object makes: a new decision, or one laid over the current state."""
    if patch.get("kind", "decision") != "decision":
        raise RecordError("record writes decision lines only: the user's lines come from review and answer")
    patch = {k: v for k, v in patch.items() if k not in ("kind", "seq", "at")}
    if patch.get("id") in current:
        line = merge(snapshot(current[patch["id"]]), patch)
    elif "id" in patch:
        raise RecordError(f"{patch['id']} is not in the record; leave the id out for a new decision")
    else:
        number = max([_number(i) for i in current] + taken + [0]) + 1
        taken.append(number)
        latest_run = max((d["run"] for d in current.values()), default=None)
        line = merge({"kind": "decision", "id": f"{name}-D{number:03d}", "run": run or latest_run or stamp,
                      "state": "open", "context": {}, "decision": None, "review": None,
                      "applied": {"inbox": [], "commits": []}, "blocks": [], "supersedes": None}, patch)
        line.setdefault("asked", {}).setdefault("at", stamp)
    line["kind"], line["at"] = "decision", stamp
    dec = line.get("decision")
    if isinstance(dec, dict):
        dec.setdefault("at", stamp)
        dec.setdefault("recovery", {}).setdefault("dependents", {"commits": [], "jobs": []})
        if line.get("review") is None and line["state"] == "decided":
            key = (dec.get("confidence", {}).get("level"), dec["recovery"].get("class"))
            why = DELEGATED.get(key)
            line["review"] = ({"state": "accepted"} if dec.get("by") == "user"
                              else {"state": "flagged", "why": why} if why else {"state": "unreviewed"})
        if line["state"] == "decided":
            line["blocks"] = []
    line["seq"] = 0  # numbered when written
    fields = list(schema()["$defs"]["decision_line"]["properties"])
    return {k: line[k] for k in fields if k in line} | {k: v for k, v in line.items() if k not in fields}


def resolve_ids(specs: list[str], name: str | None, root: Path) -> tuple[str, list[str]]:
    """The record and the decision ids that `specs` name (NAME-D007, D007, D003-D007)."""
    names, wanted = set(), []
    for spec in specs:
        m = ID_RE.match(spec)
        if not m:
            raise RecordError(f"{spec} is not a decision id (NAME-D007, D007, or a range D003-D007)")
        if m["name"]:
            names.add(m["name"])
        wanted.append((int(m["a"]), int(m["b"] or m["a"]), spec))
    if name:
        names.add(name)
    if len(names) > 1:
        raise RecordError(f"these ids name more than one record: {', '.join(sorted(names))}")
    if not names:
        available = record_names(root)
        if len(available) != 1:
            raise RecordError("say which record with --name or a full id: "
                              + (", ".join(available) if available else "there is none"))
        names = set(available)
    record = names.pop()
    current = fold(read(record, root))
    ids = []
    for a, b, spec in wanted:
        found = [i for i in current if a <= _number(i) <= b]
        if not found:
            raise RecordError(f"{spec}: no such decision in {record}")
        ids += [i for i in sorted(found, key=_number) if i not in ids]
    return record, ids


def cmd_review(args, root: Path) -> int:
    if args.verdict == "overturn" and not args.note:
        raise RecordError("say what you would rather have: review overturn ID --note TEXT")
    name, ids = resolve_ids(args.ids, args.name, root)
    current = fold(read(name, root))
    state = {"accept": "accepted", "overturn": "overturned"}[args.verdict]
    stamp = now()
    new = []
    for i in ids:
        d = current[i]
        if d["state"] != "decided" or d["decision"]["by"] == "user":
            if len(ids) > 1 and args.verdict == "accept":
                print(f"skipped {i}: {'decided by the user' if d['state'] == 'decided' else d['state']}")
                continue
            raise RecordError(f"{i} is {d['state']}" + (", by the user" if d["state"] == "decided" else "")
                              + ": only the conductor's decisions are reviewed")
        new.append({"kind": "review", "id": i, "seq": 0, "at": stamp, "by": "user", "state": state,
                    **({"note": args.note} if args.note else {})})
    if new:
        write(name, root, new)
    print(f"{state}: {', '.join(line['id'] for line in new) or 'nothing'}; commit it with sync.py commit")
    return 0


def cmd_answer(args, root: Path) -> int:
    name, ids = resolve_ids([args.id], args.name, root)
    if len(ids) != 1:
        raise RecordError("answer one question at a time")
    line = {"kind": "answer", "id": ids[0], "seq": 0, "at": now(), "by": "user", "option": args.option,
            **({"note": args.note} if args.note else {})}
    write(name, root, [line])
    print(f"answered {ids[0]}: {args.option}; commit it with sync.py commit, and the conductor applies it (while a "
          f"brief's run is under way here its watcher commits the record: leave it uncommitted)")
    return 0


def cmd_record(args, root: Path, stdin=None) -> int:
    try:
        data = json.load(stdin or sys.stdin)
    except json.JSONDecodeError as e:
        raise RecordError(f"the input is not JSON ({e.msg})") from None
    patches = data if isinstance(data, list) else [data]
    if not patches or not all(isinstance(p, dict) for p in patches):
        raise RecordError("give a JSON object, or an array of them")
    current, stamp, taken, new = fold(read(args.name, root)), now(), [], []
    for p in patches:
        line = conductor_line(args.name, p, current, args.run, stamp, taken)
        new.append(line)
        current[line["id"]] = {**line, "answer": None, "history": []}
    write(args.name, root, new)
    for line in new:
        print(f"recorded {line['id']}: {line['state']}"
              + (f", review {line['review']['state']}" if line["review"] else ""))
    return 0


def cmd_depend(args, root: Path) -> int:
    name, ids = resolve_ids([args.id], args.name, root)
    d = fold(read(name, root))[ids[0]]
    if not d["decision"]:
        raise RecordError(f"{ids[0]} is not decided yet, so nothing is built on it")
    line = snapshot(d)
    deps = line["decision"]["recovery"]["dependents"]
    deps["commits"] += [c for c in args.commit if c not in deps["commits"]]
    deps["jobs"] += [j for j in args.job if j not in deps["jobs"]]
    line["at"] = now()
    if line["review"] and line["review"]["state"] == "unreviewed" and dependents_grown(line):
        line["review"] = {"state": "flagged", "why": "dependents-grown"}
    write(name, root, [line])
    print(f"{ids[0]}: built on it {len(deps['commits'])} commit(s), {len(deps['jobs'])} job(s); "
          f"review {line['review']['state']}")
    return 0


def main(argv: list[str], root: Path = DECISIONS, stdin=None) -> int:
    p = argparse.ArgumentParser(prog="decisions.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list")
    s.add_argument("names", nargs="*")
    s.add_argument("--group", default=",".join(GROUPS))
    s.add_argument("--markdown", action="store_true")
    s = sub.add_parser("show")
    s.add_argument("id")
    s.add_argument("--name")
    s.add_argument("--history", action="store_true")
    s = sub.add_parser("counts")
    s.add_argument("names", nargs="*")
    s = sub.add_parser("review")
    s.add_argument("verdict", choices=("accept", "overturn"))
    s.add_argument("ids", nargs="+")
    s.add_argument("--note")
    s.add_argument("--name")
    s = sub.add_parser("answer")
    s.add_argument("id")
    s.add_argument("option")
    s.add_argument("--note")
    s.add_argument("--name")
    s = sub.add_parser("record")
    s.add_argument("name")
    s.add_argument("--run")
    s = sub.add_parser("depend")
    s.add_argument("id")
    s.add_argument("--name")
    s.add_argument("--commit", action="append", default=[])
    s.add_argument("--job", action="append", default=[])
    s = sub.add_parser("render")
    s.add_argument("names", nargs="*")
    sub.add_parser("check")
    args = p.parse_args(argv)
    try:
        if args.cmd == "list":
            groups = set(args.group.split(","))
            for name in args.names or record_names(root):
                for d in ordered(fold(read(name, root))):
                    if group(d) not in groups:
                        continue
                    review = effective_review(d)
                    label = group(d) + (f" ({review['why']})" if review and review.get("why") and group(d) == "flagged"
                                        else "")
                    if args.markdown:
                        dec = d["decision"]
                        print(f"- **{d['id']}** ({label}): {d['asked']['question']}"
                              + (f" Decided `{dec['option']}` by the {dec['by']}, {dec['confidence']['level']} "
                                 f"confidence, {dec['recovery']['class']} to undo." if dec else ""))
                    else:
                        print(f"{d['id']}\t{label}\t{d['asked']['question']}")
            return 0
        if args.cmd == "show":
            name, ids = resolve_ids([args.id], args.name, root)
            current = fold(read(name, root))
            for i in ids:
                print("\n".join(entry(current[i])).rstrip())
                if args.history:
                    print("\nLines:")
                    for line in current[i]["history"]:
                        print("  " + json.dumps(line, ensure_ascii=False))
            return 0
        if args.cmd == "counts":
            print("; ".join(counts_line(n, fold(read(n, root))) for n in args.names or record_names(root))
                  or "no decision records")
            return 0
        if args.cmd == "review":
            return cmd_review(args, root)
        if args.cmd == "answer":
            return cmd_answer(args, root)
        if args.cmd == "record":
            return cmd_record(args, root, stdin)
        if args.cmd == "depend":
            return cmd_depend(args, root)
        if args.cmd == "render":
            for name in args.names or record_names(root):
                view_path(name, root).write_text(render(name, read(name, root)))
            return 0
        found = problems(root)
        for e in found:
            print("ERROR", e)
        print(f"{len(record_names(root))} record(s): {len(found)} problem(s)")
        return 1 if found else 0
    except RecordError as e:
        print(f"decisions.py: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
