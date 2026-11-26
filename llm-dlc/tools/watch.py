#!/usr/bin/env python3
"""The watcher's tools: what the session that runs /prove-java-change uses to start the run's other sessions, watch
the proof loop, and act between its cycles and examples (llm-dlc/runtime.md#the-watcher).

The watcher is one session, on Opus 5.5. It does none of the work itself. It starts the sessions that do, in order,
keeps the user informed, and judges what a script can't:

    watch.py session [--new | --use ID]    the id of the fixed session: the one that evaluates the changes and then
                                           proves them (made on first use, kept in the run's state); --use
                                           takes an existing session instead, such as an earlier moonshot's
    watch.py stage evaluate PROMPT         run the evaluation in the fixed session, on Fable 5.2 at high effort
    watch.py stage setup PROMPT [--example NNN] [--workspace NAME]
                                           run the examples' setup in a new session, on Opus 5.5 at high effort
                                           (both print the session's report; --model, --effort and --memory override).
                                           --example records the attempt as that example's, for the summary and
                                           the measures; --workspace runs it in the jj workspace NAME (made beside
                                           the checkout, from the loop's line, when there is none), so that it can
                                           run while the loop proves: its commits come in by `merge`, and `add`
                                           gives the loop the example
    watch.py preflight [--after-setup NNN,...] NNN ...
                                           check examples named by number before a loop takes them: which are
                                           catalog entries still to set up (toSetUp), and what a prepared one lacks,
                                           as missing artifacts or as a fault in its form (toRepair). Exit 0:
                                           nothing; 1: something a setup session may put right; 2: an example that
                                           is not there at all. --after-setup names the catalog entries a setup
                                           session was run for: one of them still lacking is left out (leftOut)
                                           and no longer counts against the rest
    watch.py claims NNN ...                what each example claims, in its own words, for the user to confirm
                                           before the loop: every claim's statement, bounds, and the answer expected
                                           on each revision
    watch.py claims NNN ... --accept "REASON"   the watcher's word for them: a decision for each example in the
                                           run's decision record, flagged for the user to review afterwards (in a
                                           run they are away from, or quoting what they said when they confirmed
                                           them in the session). The claim files' hashes are kept beside the
                                           record, so a later run reuses the review while they are unchanged
                                           (preflight's `reviewed`)
    watch.py plan [--check]                where stage 2's plan is, and with --check whether plan.json is formed
                                           as llm-dlc/prove-plan.schema.json says
    watch.py verification start|stop|status   the verification loop, on Sonnet 5.5, which runs the jobs the
                                           sessions queue; started once, before the examples are set up
    watch.py verification nudge            say that the queue changed, so the runner or the waiting loop looks at
                                           once; `wait` does it by itself for a job it sees queued, and starts the
                                           verification loop again if it is gone while jobs wait
    watch.py loop [OPTION ...] NNN ...     start the proof loop on these examples, continuing the fixed session at
                                           high effort; it runs detached, and the options are prove-loop.sh's
    watch.py wait [--interval SECONDS]     block until there is something for the watcher, and print it: a question
                                           of the loop's to answer, a proof that has come in, the loop's end, or,
                                           when the interval has passed since the last one, a summary
    watch.py summary                       a summary now, from llm-dlc/watch-summary-template.md: where the loop,
                                           the example under way and the verification jobs stand, with what changed
                                           since the last summary first
    watch.py status [--json]               everything the summary is made from, for a question about the run
    watch.py interval SECONDS              how often `wait` gives a summary (1800 by default)
    watch.py merge add|done|list [NAME]    workspaces the user asked to have merged: the loop waits for the watcher
                                           between two examples while one is queued
    watch.py stop-after example|cycle|never   end the loop once the example, or the cycle, under way is done
    watch.py add NNN ...                   give the running loop more examples, after the ones it has: an example
                                           a setup prepared while the loop proved, once it is merged
    watch.py proof NNN                     block until the verification jobs of example NNN are in: the shell the
                                           watcher keeps on an example the loop has left to wait for its proof

The answers to the loop's questions go through conductor.py (`decide`), which `wait` names with each question.
The run's state is in llm-dlc/loop-summaries/prove-change/ (gitignored): watch.json beside the loop's own files.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import changes        # llm-dlc/tools/changes.py
import claude_setup   # llm-dlc/tools/claude_setup.py
import conductor      # llm-dlc/tools/conductor.py
import decisions      # llm-dlc/tools/decisions.py
import mode           # llm-dlc/tools/mode.py

REPO = Path(__file__).resolve().parents[2]
RUN = "llm-dlc/loop-summaries/prove-change"
TEMPLATE = "llm-dlc/watch-summary-template.md"
INTERVAL = 1800  # a run of days is watched by a session whose context every summary adds to
# Stage 2 reviews and designs the claims on every run (examples named by number included): the hardest judgment of
# a run, so it runs at high effort, in the session that will prove them.
STAGES = {"evaluate": {"model": "claude-fable-5-2", "effort": "high", "fixed": True},
          "setup": {"model": "claude-opus-5-5", "effort": "high", "fixed": False}}
SILENT = 20 * 60  # a session that has written nothing for this long may be stuck: the summary says so
LONG_COMMAND = 10 * 60  # a setup's command still running after this long is told to the watcher
LEFT = ("finished", "capped")  # item states that end an example in this run


def now() -> float:
    return time.time()


def clock(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M")


def span(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def stamp(text: str | None) -> float | None:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


class Run:
    """A run's directory and the watcher's own state in it."""

    def __init__(self, root: Path = REPO):
        self.root = root
        self.dir = root / RUN
        self.path = self.dir / "watch.json"

    def read(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def update(self, **fields) -> dict:
        self.dir.mkdir(parents=True, exist_ok=True)
        data = {**self.read(), **fields}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1) + "\n")
        os.replace(tmp, self.path)
        return data

    def run_json(self) -> dict:
        try:
            return json.loads((self.dir / "run.json").read_text())
        except (OSError, ValueError):
            return {}


def alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (TypeError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    return True


# -- the sessions the watcher starts

def transcript(root: Path, session: str) -> Path:
    """Where Claude Code keeps a session of this checkout (as feature-loop.sh's project_dir)."""
    projects = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    return projects / re.sub(r"[^A-Za-z0-9]", "-", str(root)) / f"{session}.jsonl"


def fixed_session(run: Run, new: bool = False, use: str | None = None) -> str:
    session = use or (None if new else run.read().get("session"))
    if use and not transcript(run.root, use).exists():
        raise SystemExit(f"watch.py: no session {use} of this checkout to continue ({transcript(run.root, use).parent})")
    if not session:
        session = str(uuid.uuid4())
    if session != run.read().get("session"):
        run.update(session=session)
    return session


def stage_command(run: Run, name: str, prompt: str, model: str | None, effort: str | None, memory: str | None) -> list[str]:
    spec = STAGES[name]
    command = ["claude", "-p", prompt, "--model", model or spec["model"], "--effort", effort or spec["effort"]]
    if spec["fixed"]:
        session = fixed_session(run)
        command += ["--resume", session] if transcript(run.root, session).exists() else ["--session-id", session]
    if mode.mode(run.root) == "runtime":  # a user's own Claude Code setup is no part of the work
        command += claude_setup.clean_flags(run.root)
    command += ["--permission-mode", "auto", "--output-format", "stream-json", "--verbose"]
    if memory:
        command = ["systemd-run", "--user", "--scope", "--quiet", "--collect", "-p", f"MemoryMax={memory}",
                   "-p", "MemorySwapMax=0", *command]
    return command


def workspace_root(run: Run, name: str) -> Path:
    """The jj workspace NAME's folder, made beside the checkout from the loop's line (@-) when there is none."""
    listed = subprocess.run(["jj", "--quiet", "workspace", "list"], capture_output=True, text=True, cwd=run.root).stdout
    if re.search(rf"^{re.escape(name)}( \(current\))?:", listed, re.M):
        r = subprocess.run(["jj", "--quiet", "workspace", "root", "--name", name], capture_output=True, text=True, cwd=run.root)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    path = run.root.parent / f"{run.root.name}-{name}"
    subprocess.run(["jj", "--quiet", "workspace", "add", "--name", name, "-r", "@-", str(path)],
                   cwd=run.root, check=True, capture_output=True, text=True)
    return path


def turn_cost(run: Run, session: str | None, total: float | None, fresh: bool) -> float | None:
    """What one turn cost. A result's total_cost_usd is the session's running total, so a resumed session's turn is
    its total less the total last seen for that session: None for the first turn seen of a session that was resumed,
    whose earlier total is not known here."""
    if session is None or total is None:
        return None
    totals = run.read().get("sessionTotals") or {}
    before = totals.get(session)
    run.update(sessionTotals={**totals, session: total})
    if before is not None:
        return max(0.0, total - before)
    return total if fresh else None


def head_change(where: Path) -> str | None:
    r = subprocess.run(["jj", "--quiet", "log", "--no-graph", "-r", "@-", "-T", 'change_id.short(8) ++ " " ++ description.first_line()'],
                       capture_output=True, text=True, cwd=where)
    return r.stdout.strip() or None if r.returncode == 0 else None


def cmd_stage(run: Run, name: str, prompt: str, model: str | None, effort: str | None, memory: str | None,
              example: str | None = None, workspace: str | None = None) -> int:
    command = stage_command(run, name, prompt, model, effort, memory)
    run.dir.mkdir(parents=True, exist_ok=True)
    log = run.dir / f"stage-{name}.jsonl"
    cwd = workspace_root(run, workspace) if workspace else run.root
    env = {**os.environ, **(claude_setup.CLEAN_ENV if mode.mode(run.root) == "runtime" else {})}
    stages = run.read().get("stages") or {}
    stages[name] = {"started": conductor.now(), "log": str(log), "command": [c for c in command if c != prompt]}
    attempt = None
    if example:
        setups = run.read().get("setups") or []
        attempt = {"example": example, "stage": name,
                   "attempt": 1 + sum(1 for a in setups if a["example"] == example and a["stage"] == name),
                   "started": conductor.now(), "log": str(log), "offset": log.stat().st_size if log.exists() else 0,
                   "workspace": workspace, "cwd": str(cwd)}
        run.update(setups=setups + [attempt])
    run.update(stages=stages)
    result = None
    with open(log, "a") as out:
        p = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
        if attempt:
            set_attempt(run, attempt, pid=p.pid)
        for line in p.stdout:
            out.write(line)
            out.flush()
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("type") == "result":
                result = event
        status = p.wait()
    ok = status == 0 and result is not None and result.get("subtype") == "success" and not result.get("is_error")
    cost = turn_cost(run, (result or {}).get("session_id"), (result or {}).get("total_cost_usd"), "--resume" not in command)
    stages = run.read().get("stages") or stages
    stages[name] = {**stages.get(name, {}), "ended": conductor.now(), "ok": ok, "session": (result or {}).get("session_id"),
                    "cost": cost}
    run.update(stages=stages)
    if cost is not None:
        run.update(costs={**(run.read().get("costs") or {}), f"{name}-{conductor.now()}": cost})
    if attempt:
        row = (changes.listing(cwd, [example])["examples"] or [{}])[0]
        set_attempt(run, attempt, ended=conductor.now(), ok=ok, session=(result or {}).get("session_id"),
                    cost=cost, commit=head_change(cwd), state=row.get("state"),
                    invocation=uninvoked(cwd, row) if row.get("path") else [],
                    report=((result or {}).get("result") or "")[-600:])
    print((result or {}).get("result") or f"the {name} session ended with status {status} and no report: see {log}")
    return 0 if ok else 1


def set_attempt(run: Run, attempt: dict, **fields) -> None:
    setups = run.read().get("setups") or []
    for a in setups:
        if (a["example"], a["stage"], a["attempt"], a["started"]) == (attempt["example"], attempt["stage"], attempt["attempt"], attempt["started"]):
            a.update(fields)
    run.update(setups=setups)


def activity(attempt: dict) -> dict:
    """Where a setup attempt stands from its stream: its tool calls, the command under way and for how long, the last
    run of validate_example.py and whether it passed, and when it last wrote anything."""
    out = {"toolCalls": 0, "command": None, "commandSince": None, "validation": None, "lastOutput": None}
    try:
        path = Path(attempt["log"])
        out["lastOutput"] = path.stat().st_mtime
        with open(path) as f:
            f.seek(attempt.get("offset") or 0)
            lines = f.readlines()
    except (OSError, KeyError):
        return out
    open_calls: dict[str, tuple[str, float]] = {}
    validating = set()
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        for c in ((e.get("message") or {}).get("content") or []) if isinstance(e, dict) else []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                out["toolCalls"] += 1
                i = c.get("input") or {}
                what = f"{c.get('name')}: {i.get('description') or i.get('command') or i.get('file_path') or ''}"[:160]
                open_calls[c.get("id")] = (what, time.time())
                if "validate_example.py" in str(i.get("command") or ""):
                    validating.add(c.get("id"))
            elif c.get("type") == "tool_result":
                open_calls.pop(c.get("tool_use_id"), None)
                if c.get("tool_use_id") in validating:
                    text = json.dumps(c.get("content"))
                    out["validation"] = "passed" if "passed" in text and "FAIL" not in text else "failed"
    if open_calls:
        what, _ = list(open_calls.values())[-1]
        out["command"] = what
        out["commandSince"] = out["lastOutput"]
    return out


def setups_state(run: Run) -> dict:
    setups = run.read().get("setups") or []
    active = [a for a in setups if not a.get("ended")]
    return {"active": [{**a, **activity(a)} for a in active], "done": [a for a in setups if a.get("ended")]}


# -- examples that are already prepared

def schema_gaps(root: Path, row: dict) -> list[dict]:
    """example.json against its schema, which build.py checks only when it builds the example's page."""
    try:
        import jsonschema
        schema = json.loads((root / "examples/schema/example.schema.json").read_text())
        example = json.loads((root / row["path"] / "example.json").read_text())
    except (ImportError, OSError, ValueError, KeyError):
        return []  # nothing to check with, or a file changes.py has reported already
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(example), key=lambda e: list(e.absolute_path))
    return [changes.gap(changes.FORM, f"example.json, {'/'.join(map(str, e.absolute_path)) or 'the document'}: {e.message}"[:300])
            for e in errors[:5]]


INVOKED = ("route", "adapter", "gap")


def uninvoked(root: Path, row: dict) -> list[dict]:
    """The proof tasks of a set-up example whose sidecar doesn't say how the proof is invoked (`invocation`): through
    the route, through a validated adapter, or not until a named gap of the verifier is closed, which an observed
    blocker of the task records. It is the setup's deliverable (llm-dlc/runtime.md); one missing doesn't stop a run."""
    try:
        target = json.loads((root / row["path"] / "target.json").read_text())
    except (OSError, ValueError, KeyError, TypeError):
        return []
    observed = {b.get("task") for b in (target.get("handoff") or {}).get("blockers") or [] if b.get("observed")}
    out = []
    for t in target.get("tasks") or []:
        if t.get("kind") == "replay":
            continue
        how = (t.get("invocation") or {}).get("how")
        if how not in INVOKED:
            out.append({"task": t["id"], "what": "how its proof is invoked is not recorded (route, adapter or gap)"})
        elif how == "gap" and t["id"] not in observed and None not in observed:
            out.append({"task": t["id"], "what": "invoked only once a gap is closed, and no observed blocker names it"})
    return out


def claim_hashes(root: Path, row: dict) -> dict[str, str]:
    """The sha256 of each claim file the example's tasks name, by its path in the checkout."""
    import hashlib
    try:
        folder = root / row["path"]
        target = json.loads((folder / "target.json").read_text())
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    out = {}
    for name in sorted({t["claim"] for t in target.get("tasks") or [] if t.get("claim")}):
        try:
            out[f"{row['path']}/{name}"] = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        except OSError:
            out[f"{row['path']}/{name}"] = "missing"
    return out


def ledger_path(run: Run) -> Path | None:
    """Beside the run's decision record: the claims each accepted review covered, by their files' hashes."""
    where = conductor.decision_record(run.dir)
    return None if where is None else where[1] / f"{where[0]}-claims.json"


def ledger(run: Run) -> dict:
    path = ledger_path(run)
    try:
        data = json.loads(path.read_text()) if path else {}
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def review_state(run: Run, row: dict) -> str:
    """`reviewed`: its claims are the ones an accepted review covered; `changed`: one was accepted, and a claim file
    has changed since; `new`: none was; `catalogued`: nothing states a claim yet."""
    if row["state"] == "catalogued":
        return "catalogued"
    entry = ledger(run).get(row["id"])
    if not entry:
        return "new"
    return "reviewed" if entry.get("files") == claim_hashes(run.root, row) else "changed"


def preflight(run: Run, numbers: list[str], set_up: list[str] | tuple = ()) -> dict:
    """What each example named lacks. `set_up` names the catalog entries a setup session has been run for: one that
    still lacks something is left out of the run, and the others go on without it."""
    numbers = list(dict.fromkeys(numbers))
    out = []
    for row in changes.listing(run.root, numbers)["examples"]:
        gaps = list(row.get("gaps") or [])
        if not any(g["kind"] == changes.ABSENT for g in gaps) and row.get("path"):
            gaps += schema_gaps(run.root, row)
        entry = {"id": row["id"], "path": row.get("path"), "state": row["state"], "ok": not gaps,
                 **{kind: [g for g in gaps if g["kind"] == kind] for kind in changes.KINDS}}
        if row.get("path") and row["state"] not in ("catalogued", "unknown"):
            entry["invocation"] = uninvoked(run.root, row)
        if row.get("path"):
            entry["review"] = review_state(run, row)
        if row["state"] == "unknown":
            entry["note"] = "no target sidecar: only its example.json was checked, and its claims are whatever its page states"
        out.append(entry)
    left_out = [e["id"] for e in out if not e["ok"] and e["id"] in set_up and not e[changes.ABSENT]]
    counted = [e for e in out if e["id"] not in left_out]
    return {"examples": out, "ok": all(e["ok"] for e in counted),
            "absent": [e["id"] for e in out if e[changes.ABSENT]],
            "toSetUp": [e["id"] for e in counted if e[changes.CATALOGUE]],
            "toRepair": [e["id"] for e in counted if e[changes.ARTIFACTS] or e[changes.FORM]],
            "leftOut": left_out,
            "toProve": [e["id"] for e in out if e["ok"] and e["state"] != "decided"],
            "decided": [e["id"] for e in out if e["ok"] and e["state"] == "decided"],
            # Stage 2 runs on every run: it designs the claims of what is not reviewed and reuses the rest's review
            "toReview": [e["id"] for e in counted if e.get("review") in ("new", "changed", "catalogued")],
            "reviewed": [e["id"] for e in counted if e.get("review") == "reviewed"],
            "toClassify": [e["id"] for e in counted if e.get("invocation")]}


def cmd_preflight(run: Run, numbers: list[str], set_up: list[str] | tuple = ()) -> int:
    found = preflight(run, numbers, set_up)
    print(json.dumps(found, indent=1))
    return 0 if found["ok"] else 2 if found["absent"] else 1


def claims(run: Run, numbers: list[str]) -> list[dict]:
    """Each example's claims as its own files state them: one entry per claim file, with the tasks that put it to a
    revision and the answer each expects. A task with no claim file yet is listed with its statement missing."""
    out = []
    for row in changes.listing(run.root, list(dict.fromkeys(numbers)))["examples"]:
        entry = {"id": row["id"], "title": row.get("title"), "source": row.get("source"), "state": row["state"],
                 "path": row.get("path"), "claims": []}
        out.append(entry)
        if not row.get("path"):
            continue
        folder = run.root / row["path"]
        try:
            target = json.loads((folder / "target.json").read_text())
        except (OSError, ValueError):
            continue  # no sidecar, or one changes.py has reported: nothing states a claim in a form to list
        by_file: dict[str | None, dict] = {}
        for task in target.get("tasks") or []:
            if task.get("kind") == "replay":
                continue
            name = task.get("claim")
            if name not in by_file or name is None:
                claim = {}
                try:
                    claim = json.loads((folder / name).read_text()) if name else {}
                except (OSError, ValueError):
                    pass
                c = {"file": name, "statement": claim.get("statement"), "bounds": claim.get("bounds") or {},
                     "assumptions": [a.get("text") for a in claim.get("assumptions") or [] if isinstance(a, dict)],
                     "tasks": []}
                entry["claims"].append(c)
                if name is not None:
                    by_file[name] = c
            else:
                c = by_file[name]
            c["tasks"].append({"task": task["id"], "on": task.get("revision") or task.get("pair"),
                               "expected": task.get("expected"),
                               **({"allowedChange": task["allowedChange"]} if task.get("allowedChange") else {})})
    return out


def cmd_claims(run: Run, numbers: list[str], as_json: bool) -> int:
    found = claims(run, numbers)
    if as_json:
        print(json.dumps(found, indent=1))
        return 0
    for e in found:
        print(f"## {e['id']}: {e['title'] or '(no title)'}")
        if e.get("source"):
            print(e["source"])
        if not e["claims"]:
            print(f"\nNo claim: the example is {e['state']}.")
        for i, c in enumerate(e["claims"], 1):
            print(f"\n{i}. {c['statement'] or '(no claim file yet: nothing states this claim)'}")
            for t in c["tasks"]:
                change = f"; the change may affect only: {t['allowedChange']}" if t.get("allowedChange") else ""
                print(f"   - expected {t['expected'] or 'not said'} on {t['on']} (task {t['task']}){change}")
            if c["bounds"]:
                print("   - bounds: " + ", ".join(f"{k} {v}" for k, v in c["bounds"].items()))
            for a in c["assumptions"]:
                print(f"   - assuming: {a}")
            if c["file"]:
                print(f"   - {c['file']}")
        print()
    return 0


def accept_claims(run: Run, numbers: list[str], reason: str) -> tuple[list[str], list[str]]:
    """The watcher's own word for the claims of examples it had set up, in a run the user is away from (the skill's
    --unattended): one decision for each example in the run's decision record, flagged for the user because proving
    the wrong claim costs the loop's hours. Returns the decisions' ids, and instead of any of them what stands in
    the way: an example that states no claim, or a claim with no claim file, is not the watcher's to accept."""
    found = claims(run, numbers)
    missing = [f"{e['id']}: it states no claim (the example is {e['state']})" for e in found if not e["claims"]]
    missing += [f"{e['id']}: a task names no claim file" for e in found if any(not c["statement"] for c in e["claims"])]
    where = conductor.decision_record(run.dir)
    if where is None:
        missing.append(f"{run.dir} is in no checkout, so there is no decision record")
    if missing:
        return [], missing
    import decisions
    name, root = where
    current, stamp, taken, lines = decisions.fold(decisions.read(name, root)), decisions.now(), [], []
    events = conductor.read_events(run.dir)
    for e in found:
        folder = Path(e["path"] or "")
        patch = {
            "state": "decided",
            "asked": {"by": run.dir.name, "at": stamp,
                      "question": f"The setup of example {e['id']} stated {len(e['claims'])} claim(s): does the loop "
                                  "prove them as stated, while the user is away?"},
            "context": {"files": sorted(str(folder / c["file"]) for c in e["claims"])},
            "options": [
                {"id": "accept", "summary": "prove the claims as stated",
                 "consequences": "the loop's hours and tokens go to these claims, and the user reads them afterwards"},
                {"id": "hold", "summary": "leave the example out until the user has read its claims",
                 "consequences": "the example is not proved in this run"}],
            "decision": {"option": "accept", "by": "conductor", "rationale": reason,
                         "confidence": {"level": "high",
                                        "basis": "the claims as `watch.py claims` prints them, read against the "
                                                 "example's source and its change"},
                         "recovery": {"class": "costly",
                                      "undo": "have another setup session state the claim the user meant, and name the "
                                              "example in a later run; what was proved stays, of the claim as it was"}},
        }
        lines.append(decisions.conductor_line(name, patch, current, events[0]["time"] if events else None, stamp, taken))
    decisions.write(name, root, lines)
    rows = {r["id"]: r for r in changes.listing(run.root, [e["id"] for e in found])["examples"]}
    kept = ledger(run)
    for e, line in zip(found, lines):
        kept[e["id"]] = {"files": claim_hashes(run.root, rows[e["id"]]), "decision": line["id"], "at": stamp}
    path = ledger_path(run)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kept, indent=1, sort_keys=True) + "\n")
    return [line["id"] for line in lines], []


def cmd_accept_claims(run: Run, numbers: list[str], reason: str) -> int:
    try:
        ids, missing = accept_claims(run, numbers, reason)
    except Exception as e:  # decisions.py refuses a line it finds a problem in
        print(f"not recorded: {e}", file=sys.stderr)
        return 1
    for line in missing:
        print(f"not accepted: {line}", file=sys.stderr)
    if missing:
        return 1
    print(f"accepted the claims of {' '.join(numbers)} for the user to review afterwards: {' '.join(ids)} "
          "(python3 llm-dlc/tools/decisions.py list --group flagged)")
    return 0


# -- stage 2's plan

PLAN_SCHEMA = "llm-dlc/prove-plan.schema.json"


def plan_problems(run: Run) -> list[str]:
    """What is wrong with stage 2's plan.json: its form (PLAN_SCHEMA, where jsonschema is installed) and what the
    schema can't say: the order names each example once, and an example whose claims stage 2 designed carries them."""
    path = run.dir / "plan.json"
    try:
        plan = json.loads(path.read_text())
    except OSError:
        return [f"no plan: stage 2 writes {path}"]
    except ValueError as e:
        return [f"{path} is not JSON: {e}"]
    out = []
    try:
        import jsonschema
        schema = json.loads((run.root / PLAN_SCHEMA).read_text())
        out += [f"{'/'.join(map(str, e.absolute_path)) or 'the plan'}: {e.message}"[:300]
                for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(plan), key=lambda e: list(e.absolute_path))[:10]]
    except (ImportError, OSError, ValueError):
        pass
    if out or not isinstance(plan, dict):
        return out or ["the plan is not an object"]
    ids = [e.get("id") for e in plan.get("examples") or []]
    if sorted(plan.get("order") or []) != sorted(ids) or len(set(ids)) != len(ids):
        out.append(f"the order ({' '.join(plan.get('order') or [])}) must name each example of the plan once ({' '.join(map(str, ids))})")
    for e in plan.get("examples") or []:
        if e.get("review") == "designed" and not (e.get("claimFiles") and e.get("tasks")):
            out.append(f"{e.get('id')}: its claims were designed here, and the plan carries no claimFiles or tasks for them")
    return out


def cmd_plan(run: Run, check: bool) -> int:
    print(run.dir / "plan.json")
    if not check:
        return 0
    problems = plan_problems(run)
    for line in problems:
        print(f"  {line}")
    print("the plan is formed as the schema says" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


# -- the verification loop and the proof loop

def store(directory: str | Path) -> str | None:
    """The jj repository a directory's workspace belongs to (as prove-loop.sh's store)."""
    repo = Path(directory) / ".jj" / "repo"
    try:
        if repo.is_dir():
            return str(repo.resolve())
        return str((repo.parent / repo.read_text().strip()).resolve())
    except OSError:
        return None


def verification_running(root: Path) -> int | None:
    mine = store(root)
    r = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", r"llm-dlc/tools/verification-loop\.sh"],
                       capture_output=True, text=True)
    for pid in r.stdout.split():
        try:
            words = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            theirs = store(os.readlink(f"/proc/{pid}/cwd"))
        except OSError:
            continue
        # the script as a word of its own: a shell that only mentions it (`bash -lc "…loop.sh; read"`, the window a
        # loop was started in, still open after the loop ended) is not the loop
        if mine and theirs == mine and any(w.endswith(b"verification-loop.sh") for w in words):
            return int(pid)
    return None


def detached(command: list[str], root: Path, log: Path) -> int:
    with open(log, "a") as out:
        p = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                             start_new_session=True)
    return p.pid


def start_verification(run: Run) -> int:
    run.dir.mkdir(parents=True, exist_ok=True)
    pid = detached([str(run.root / "llm-dlc/tools/verification-loop.sh")], run.root, run.dir / "verification.log")
    run.update(verification={"pid": pid, "started": conductor.now()})
    return pid


def nudge(root: Path) -> str:
    """Say to the pipeline that its queue changed (verification/pipeline.py nudge). What it answers, or why not."""
    r = subprocess.run([sys.executable, str(root / "verification/pipeline.py"), "nudge"], capture_output=True, text=True, cwd=root)
    return r.stdout.strip() if r.returncode == 0 else f"the pipeline took no nudge: {(r.stderr or r.stdout).strip()[-200:]}"


QUEUE_LOOK = 30  # seconds between two looks of `wait` at the verification queue


def tend_queue(run: Run) -> dict | None:
    """The watcher's part in the verification queue, at each look of `wait`: a job that is queued and can run here
    is announced to the pipeline once (most are announced already, by the commit that queued them: this is for one
    that came another way), and if no verification loop is running while jobs wait, one is started, unless the
    watcher was the one to stop it. Returns what to tell the watcher, if anything."""
    r = subprocess.run([sys.executable, str(run.root / "verification/pipeline.py"), "status", "--json"],
                       capture_output=True, text=True, cwd=run.root)
    try:
        rows = json.loads(r.stdout).get("pending", [])
    except ValueError:
        return None
    waiting = [m[0] for row in rows if "; cannot run here:" not in row and (m := conductor.JOB_ID.search(row))]
    data = run.read()
    known = [j for j in data.get("nudged") or [] if j in waiting]  # forgotten once it is no longer waiting
    if not waiting:
        if data.get("nudged"):
            run.update(nudged=[])
        return None
    if [j for j in waiting if j not in known]:
        nudge(run.root)
        run.update(nudged=waiting)
    verification = data.get("verification") or {}
    # Outside a jj repository nothing says whose loop a process is, so none is started on a guess.
    if store(run.root) and verification_running(run.root) is None and not verification.get("stopped"):
        try:
            pid = start_verification(run)
        except OSError:
            return None
        return {"kind": "verification", "pid": pid,
                "note": f"no verification loop was running while {len(waiting)} job(s) waited: started one "
                        f"(its output: {run.dir / 'verification.log'}). Tell the user; nothing else to do."}
    return None


def cmd_verification(run: Run, action: str) -> int:
    running = verification_running(run.root)
    ours = (run.read().get("verification") or {}).get("pid")
    if action == "start":
        if running:
            print(f"a verification loop is already running for this repository (pid {running}): leaving the queue to it")
            return 0
        pid = start_verification(run)
        print(f"started the verification loop (pid {pid}; its output: {run.dir / 'verification.log'})")
    elif action == "nudge":
        print(nudge(run.root))
    elif action == "stop":
        if not ours or not alive(ours):
            print("this run started no verification loop that is still running")
            return 0
        os.kill(int(ours), signal.SIGUSR1)  # it ends after the job under way, as prove-loop.sh asks it to
        run.update(verification={**run.read().get("verification", {}), "stopped": conductor.now()})  # not to be started again
        print(f"asked the verification loop (pid {ours}) to end after the job under way")
    else:
        print(f"running (pid {running})" + (", started by this run" if running == ours else "") if running else "not running")
    return 0


def cmd_loop(run: Run, arguments: list[str]) -> int:
    state = run.run_json()
    if state and not state.get("ended") and alive(state.get("pid")):
        print(f"a proof loop is already running here (pid {state['pid']}, examples {' '.join(state.get('examples', []))})",
              file=sys.stderr)
        return 1
    session = fixed_session(run)
    run.dir.mkdir(parents=True, exist_ok=True)
    command = [str(run.root / "llm-dlc/tools/prove-loop.sh"), "--session", session, *arguments]
    pid = detached(command, run.root, run.dir / "loop.log")
    run.update(loop={"pid": pid, "started": conductor.now(), "arguments": arguments}, lastSummary=None, announced=[])
    print(f"started the proof loop (pid {pid}) in session {session}; its output: {run.dir / 'loop.log'}")
    return 0


# -- where the run stands

def jobs(root: Path) -> dict:
    r = subprocess.run([sys.executable, str(root / "verification/pipeline.py"), "status", "--json"],
                       capture_output=True, text=True, cwd=root)
    try:
        status = json.loads(r.stdout)
    except ValueError:
        return {"pending": [], "running": [], "finished": [], "collected": {}}
    ids = lambda rows: [m[0] for row in rows if (m := conductor.JOB_ID.search(row))]
    collected = {}
    for row in status.get("collected", []):
        if m := conductor.JOB_ID.search(row):
            collected[m[0]] = (re.findall(r"\[([a-z -]+)\]\s*$", row) or ["?"])[0]
    return {"pending": ids(status.get("pending", [])), "running": ids(status.get("running", [])),
            "finished": ids(status.get("finished, not collected", [])), "collected": collected}


def since_revset(since: str) -> str:
    """A revset for `since` that still names one commit when it is a change id that has turned divergent (VF-049: a
    trace rewrite gave the base change a new commit, a bookmark kept the old one visible, and `BASE..@-` failed, so
    the run's commit list went empty). A change id (jj writes them in the letters k to z) is read as its version on
    this line; a commit id is taken as it is."""
    return f"heads(change_id({since}) & ::@-)" if re.fullmatch(r"[k-z]+", since) else since


def commits(root: Path, since: str | None) -> list[str]:
    """The commits on the loop's line after change `since`, oldest first: `change summary`. All of the last five
    without one."""
    revset = f"{since_revset(since)}..@-" if since else "ancestors(@-, 5)"
    r = subprocess.run(["jj", "--quiet", "log", "--no-graph", "--reversed", "-r", revset, "-T",
                        'change_id.short(8) ++ " " ++ description.first_line() ++ "\n"'],
                       capture_output=True, text=True, cwd=root)
    return [line for line in r.stdout.splitlines() if line.strip()] if r.returncode == 0 else []


def turn(path: str | None) -> dict:
    """How far the session's turn has come: tool calls so far, and when it last wrote anything."""
    try:
        file = Path(path)
        calls = sum(line.count('"type":"tool_use"') + line.count('"type": "tool_use"') for line in file.open())
        return {"toolCalls": calls, "lastOutput": file.stat().st_mtime}
    except (TypeError, OSError):
        return {"toolCalls": None, "lastOutput": None}


def decisions_state(run: Run) -> dict:
    """Where the run's decision record stands: the watcher's answers the user has not reviewed, the ones flagged for
    them, and the ones they overturned, which wait for the watcher."""
    where = conductor.decision_record(run.dir)
    if where is None:
        return {}
    try:
        current = decisions.fold(decisions.read(*where))
    except (decisions.RecordError, OSError):
        return {}
    by = {g: [d["id"] for d in current.values() if decisions.group(d) == g] for g in ("flagged", "unreviewed", "overturned")}
    return {"record": where[0], "flagged": len(by["flagged"]), "unreviewed": len(by["unreviewed"]), "overturned": by["overturned"]}


def cycle_total(event: dict) -> tuple[str | None, float | None]:
    """The session and its running total, from the result the turn file of a cycle-start event ends with."""
    try:
        lines = Path(event.get("turn") or "").read_text().splitlines()
    except OSError:
        return None, None
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("type") == "result":
            return e.get("session_id"), e.get("total_cost_usd")
    return None, None


def measures(run: Run, events: list[dict], claims: dict) -> dict:
    """Whether the stronger review pays for itself: the time from the run's first stage to the loop's first cycle,
    the setups each example needed beyond its first, how many examples' first setup left every proof task's
    invocation recorded, and the claims answered for each dollar the run's sessions cost so far."""
    data = run.read()
    starts = [stamp(st.get("started")) for st in (data.get("stages") or {}).values()]
    starts += [stamp(a.get("started")) for a in data.get("setups") or []]
    starts = [t for t in starts if t]
    first_cycle = next((stamp(e.get("time")) for e in events if e.get("type") == "cycle-start"), None)
    setups = [a for a in data.get("setups") or [] if a.get("stage") == "setup"]
    by_example: dict[str, list[dict]] = {}
    for a in setups:
        by_example.setdefault(a["example"], []).append(a)
    first = [v[0] for v in by_example.values() if v[0].get("ended")]
    cost = sum(v or 0 for v in (data.get("costs") or {}).values()) + sum(v or 0 for v in (data.get("cycleCosts") or {}).values())
    answered = sum(1 for statuses in claims.values() for status in statuses.values() if status in changes.ANSWERS)
    return {"toFirstCycle": (first_cycle - min(starts)) if first_cycle and starts else None,
            "setupRework": {k: len(v) - 1 for k, v in by_example.items() if len(v) > 1},
            "firstAttemptInvoked": [sum(1 for a in first if a.get("ok") and not a.get("invocation")), len(first)],
            "cost": round(cost, 2), "claimsAnswered": answered,
            "claimsPerDollar": round(answered / cost, 4) if cost else None}


def unfinished_or_none(root: Path) -> dict | None:
    """conductor.unfinished_jobs, or None when the queue can't be read: never an empty answer that reads as "in"."""
    try:
        return conductor.unfinished_jobs(root)
    except conductor.QueueUnreadable:
        return None


def state(run: Run) -> dict:
    events = conductor.read_events(run.dir)
    loop = run.run_json()
    examples = loop.get("examples") or []
    started = [e for e in events if e.get("type") == "cycle-start"]
    current = started[-1] if started else {}
    items: dict[str, str] = {}
    for e in events:
        if e.get("type") == "cycle-start":
            items[e["item"]] = "under way"
        elif e.get("type") == "item" and e.get("state") != "resumed":
            items[e["item"]] = {"continue": "under way"}.get(e["state"], e["state"])
    ended = next((e for e in events if e.get("type") == "ended"), None)
    under_way = None if ended else current.get("item")
    rows = {r["id"]: r for r in changes.listing(run.root, examples)["examples"]} if examples else {}
    claims = {i: {t: changes.answer(c) or c["status"] for t, c in (rows[i].get("claims") or {}).items()} for i in rows}
    head = commits(run.root, None)
    return {"time": now(), "started": stamp(loop.get("started")), "session": loop.get("session"),
            "examples": examples, "items": items, "item": under_way,
            "cycle": current.get("cycle"), "itemCycle": current.get("itemCycle"),
            "cycleStarted": stamp(current.get("time")), "turn": turn(current.get("turn")) if under_way else {},
            "claims": claims, "exampleState": {i: rows[i]["state"] for i in rows},
            "head": head[-1].split()[0] if head else None, "jobs": jobs(run.root),
            "unfinished": unfinished_or_none(run.root) or {},
            "loopAlive": alive(loop.get("pid")) if loop else False, "ended": ended,
            "verification": verification_running(run.root),
            "mergeQueue": merge_queue(run), "asked": conductor.pending(run.dir), "decisions": decisions_state(run),
            "setups": setups_state(run), "measures": measures(run, events, claims)}


# -- the summary

def tally(statuses: dict) -> str:
    counts: dict[str, int] = {}
    for status in statuses.values():
        name = status if status in changes.ANSWERS else ("left open" if status else "no answer yet")
        counts[name] = counts.get(name, 0) + 1
    return ", ".join(f"{n} {name}" for name, n in counts.items()) or "no claim stated"


def changed(s: dict, last: dict | None, root: Path) -> list[str]:
    """What is different from the last summary, most telling first."""
    if not last:
        return ["this is the first summary of the run"]
    out = []
    for item, was in (last.get("items") or {}).items():
        if (is_now := s["items"].get(item)) != was:
            out.append(f"example {item}: {was} → {is_now}")
    out += [f"example {item} started" for item in s["items"] if item not in (last.get("items") or {})]
    for item, statuses in s["claims"].items():
        before = (last.get("claims") or {}).get(item) or {}
        out += [f"example {item}, claim {task}: {before.get(task) or 'no answer'} → {status or 'no answer'}"
                for task, status in statuses.items() if status != before.get(task)]
    new = commits(root, last.get("head")) if last.get("head") and last.get("head") != s["head"] else []
    out += [f"commit {line}" for line in new[-6:]]
    if len(new) > 6:
        out.insert(len(out) - 6, f"{len(new) - 6} more commits before these")
    was_collected = last.get("jobs", {}).get("collected") or {}
    for job, result in s["jobs"]["collected"].items():
        if job not in was_collected:
            out.append(f"job {job} is in: {result}")
    was_queued = set(last.get("jobs", {}).get("pending") or []) | set(last.get("jobs", {}).get("running") or [])
    queued = [j for j in s["jobs"]["pending"] + s["jobs"]["running"] if j not in was_queued and j not in s["jobs"]["collected"]]
    out += [f"job {job} was queued" for job in queued]
    if last.get("cycle") != s["cycle"] and s["cycle"]:
        out.append(f"the loop is on cycle {s['cycle']} (it was on {last.get('cycle') or 'none'})")
    return out or ["nothing"]


def attention(s: dict) -> list[str]:
    out = []
    if s["ended"]:
        out.append(f"the loop has ended (status {s['ended'].get('status')}): report, and stop the verification loop when the queue is clear")
    elif s["examples"] and not s["loopAlive"]:
        out.append("the loop's process is gone and it recorded no end: look at loop.log")
    if s["asked"]:
        out.append(f"the loop is waiting for an answer to its {s['asked'].get('type')} question (event {s['asked']['n']})")
    last_output = (s["turn"] or {}).get("lastOutput")
    if s["item"] and last_output and s["time"] - last_output > SILENT:
        out.append(f"the session has written nothing for {span(s['time'] - last_output)}: it may be waiting on a long command, or stuck")
    for a in (s.get("setups") or {}).get("active", []):
        quiet = s["time"] - a["lastOutput"] if a.get("lastOutput") else None
        if a.get("command") and quiet and quiet > LONG_COMMAND:
            out.append(f"example {a['example']}'s setup has had one command running for {span(quiet)}: {a['command']}")
        elif quiet and quiet > SILENT:
            out.append(f"example {a['example']}'s setup has written nothing for {span(quiet)}")
        if a.get("validation") == "passed" and not a.get("commandSince"):
            out.append(f"example {a['example']}'s setup has passed its validation and is waiting only to commit")
    if (s["jobs"]["pending"] or s["jobs"]["running"]) and not s["verification"]:
        out.append("jobs are queued and no verification loop is running: `watch.py verification start`")
    out += [f"job {job} came back {result}" for job, result in s["jobs"]["collected"].items()
            if result not in ("passed", "?") and job in s.get("newlyCollected", ())]
    if s["mergeQueue"]:
        out.append(f"queued to merge at the next change of example: {', '.join(s['mergeQueue'])}")
    recorded = s.get("decisions") or {}
    out += [f"the user overturned {i}: act on its undo line (`decisions.py show {i}`), then record what was done as "
            f"the decision that supersedes it" for i in recorded.get("overturned", [])]
    if recorded.get("flagged"):
        out.append(f"{recorded['flagged']} of the watcher's answers are flagged for the user's review: "
                   f"`python3 llm-dlc/tools/decisions.py list {recorded['record']} --group flagged`")
    return out


def render(s: dict, last: dict | None, root: Path = REPO) -> str:
    s = {**s, "newlyCollected": [j for j in s["jobs"]["collected"] if j not in ((last or {}).get("jobs", {}).get("collected") or {})] if last else []}
    by_state = lambda *names: [i for i in s["examples"] if s["items"].get(i) in names]
    done, waiting = by_state(*LEFT), by_state("waiting")
    left = [i for i in s["examples"] if i not in s["items"]]
    examples = f"{len(done)} of {len(s['examples'])} done"
    examples += f" ({' '.join(done)})" if done else ""
    examples += f" · waiting on a proof: {' '.join(f'{i} ({len(s['unfinished'].get(i, []))} jobs out)' for i in waiting)}" if waiting else ""
    examples += f" · not started: {' '.join(left)}" if left else ""
    if s["item"]:
        t = s["turn"] or {}
        loop = (f"cycle {s['cycle']}, on example {s['item']}, its cycle {s['itemCycle']}, "
                f"{span(s['time'] - (s['cycleStarted'] or s['time']))} in")
        loop += f", {t['toolCalls']} tool calls so far" if t.get("toolCalls") is not None else ""
        loop += f", last output {span(s['time'] - t['lastOutput'])} ago" if t.get("lastOutput") else ""
        example = f"{s['exampleState'].get(s['item'], 'unknown')}: {tally(s['claims'].get(s['item']) or {})}"
        out = len(s["unfinished"].get(s["item"], []))
        example += f"; {out} of its verification jobs not in yet" if out else ""
    else:
        loop = "ended" if s["ended"] else ("between examples" if s["loopAlive"] else "not running")
        example = "none under way"
    j = s["jobs"]
    jobs_line = (f"{len(j['running'])} running, {len(j['pending'])} queued, {len(j['finished'])} finished and not "
                 f"collected, {len(j['collected'])} collected" + ("" if s["verification"] else " · no verification loop running"))
    since = f"{span(s['time'] - last['time'])} since the last summary" if last else "the first summary"
    values = {"time": clock(s["time"]), "elapsed": span(s["time"] - (s["started"] or s["time"])), "since": since,
              "changed": "\n".join(f"- {line}" for line in changed(s, last, root)),
              "loop": loop, "examples": examples, "item": s["item"] or "none", "example": example,
              "jobs": jobs_line, "attention": "\n".join(f"- {line}" for line in attention(s)) or "- nothing",
              "setup": setup_line(s), "measures": measures_line(s)}
    template = (root / TEMPLATE).read_text() if (root / TEMPLATE).exists() else DEFAULT_TEMPLATE
    body = template.split("<!-- template -->", 1)[-1].strip("\n")
    return body.format_map(values)


def setup_line(s: dict) -> str:
    st = s.get("setups") or {}
    parts = []
    for a in st.get("active", []):
        bit = f"{a['example']} (attempt {a['attempt']}{', in ' + a['workspace'] if a.get('workspace') else ''}, {a['toolCalls']} tool calls"
        bit += f", now {a['command']}" if a.get("command") else ""
        bit += f", validation {a['validation']}" if a.get("validation") else ""
        parts.append(bit + ")")
    done = st.get("done", [])
    if done:
        parts.append("done: " + ", ".join(f"{a['example']} #{a['attempt']} {'ok' if a.get('ok') else 'failed'}"
                                          f"{' at ' + a['commit'].split()[0] if a.get('commit') else ''}"
                                          f"{', invocation not recorded for ' + str(len(a['invocation'])) + ' task(s)' if a.get('invocation') else ''}"
                                          for a in done[-4:]))
    return "; ".join(parts) or "none"


def measures_line(s: dict) -> str:
    m = s.get("measures") or {}
    first = f"{span(m['toFirstCycle'])} to the first proof cycle" if m.get("toFirstCycle") else "no proof cycle yet"
    invoked, of = m.get("firstAttemptInvoked") or [0, 0]
    rework = ", ".join(f"{k} ×{v}" for k, v in (m.get("setupRework") or {}).items()) or "none"
    per = f"{m['claimsPerDollar']} claims answered per dollar" if m.get("claimsPerDollar") is not None else "no cost recorded yet"
    return (f"{first} · setups redone: {rework} · invocation recorded at the first setup: {invoked} of {of} · "
            f"{m.get('claimsAnswered', 0)} claims answered for ${m.get('cost', 0)}, {per}")


DEFAULT_TEMPLATE = """### {time} UTC · {elapsed} into the run · {since}

**Changed**
{changed}

**Loop:** {loop}
**Examples:** {examples}
**Example {item}:** {example}
**Verification jobs:** {jobs}
**Setup:** {setup}
**Measures:** {measures}

**Needs attention**
{attention}
"""


def snapshot(s: dict) -> dict:
    return {k: s[k] for k in ("time", "items", "claims", "head", "cycle", "jobs")}


def cmd_summary(run: Run) -> int:
    s = state(run)
    print(render(s, run.read().get("lastSummary"), run.root))
    run.update(lastSummary=snapshot(s))
    return 0


# -- waiting for something to do

def assessment(run: Run, event: dict) -> dict:
    """What the watcher needs beside a `cycle` question: where the example stands by its own folder and the queue."""
    item = event.get("item")
    rows = changes.listing(run.root, [item])["examples"] if item else []
    row = rows[0] if rows else {}
    known = unfinished_or_none(run.root)
    out = len(known.get(item, [])) if known is not None else "unknown (the queue could not be read)"
    hint = ("every claim has its answer: finished, unless the report says work is left" if row.get("state") == "decided"
            else "its claims are not all answered, and jobs of it are queued: waiting if the session has nothing else to do, else continue" if out
            else "its claims are not all answered and nothing of it is queued: continue, unless what is left needs a "
                 "person or can't be decided here. `blocked` names the open claims that stop at an observed gap of "
                 "the verifier, and the example's own verdict and hand-off below say what was tried")
    found = row.get("claims") or {}
    return {"example": row.get("state"),
            "claims": {t: changes.answer(c) or c["status"] for t, c in found.items()},
            "besideRoute": sorted(t for t, c in found.items() if c["status"] not in changes.ANSWERS and changes.answer(c)),
            "blocked": {t: c["blocked"] for t, c in found.items() if c.get("blocked")},
            "jobsNotIn": out, "verdict": row.get("verdict"), "next": row.get("next"), "hint": hint}


def next_thing(run: Run, interval: float) -> dict | None:
    event = conductor.pending(run.dir)
    if event is not None:
        if event.get("type") == "ended":
            (run.dir / "ended.seen").write_text(conductor.now() + "\n")
            return {"kind": "ended", "event": event}
        out = {"kind": "question", "event": {**event, "secondsLeft": int(event["deadline"] - time.time())},
               "answer": f"python3 llm-dlc/tools/conductor.py decide {RUN} {event['n']} {'|'.join(conductor.answers(event))} --reason TEXT [--confidence medium]"}
        if event.get("type") == "cycle":
            out["assessment"] = assessment(run, event)
            started = [e for e in conductor.read_events(run.dir) if e.get("type") == "cycle-start"]
            key = str(started[-1].get("cycle")) if started else None
            if key and key not in (run.read().get("cycleCosts") or {}):
                # the cycle's turn less what the session had cost before it (its compaction included)
                cost = turn_cost(run, *cycle_total(started[-1]), fresh=False)
                if cost is not None:
                    run.update(cycleCosts={**(run.read().get("cycleCosts") or {}), key: cost})
        if event.get("type") == "example":
            out["mergeQueue"] = merge_queue(run)
        return out
    data = run.read()
    told = set(data.get("setupsTold") or [])
    for a in data.get("setups") or []:
        key = f"{a['example']}#{a['attempt']}:{a['stage']}"
        if a.get("ended") and key + ":ended" not in told:
            run.update(setupsTold=sorted(told | {key + ":ended"}))
            return {"kind": "setup", "attempt": {k: a.get(k) for k in ("example", "attempt", "workspace", "ok", "commit",
                                                                         "state", "invocation", "cost", "report")},
                    "note": "a setup in a workspace: queue its merge (`watch.py merge add NAME`), and once merged, "
                            "`watch.py add NNN` gives the loop the example" if a.get("workspace") else
                            "check it again with `watch.py preflight --after-setup NNN ...`"}
        if not a.get("ended"):
            act = activity(a)
            quiet = now() - act["lastOutput"] if act.get("lastOutput") else 0
            if quiet > (LONG_COMMAND if act.get("command") else SILENT) and key + ":quiet" not in told:
                run.update(setupsTold=sorted(told | {key + ":quiet"}))
                return {"kind": "setup-quiet", "example": a["example"], "attempt": a["attempt"], "for": span(quiet),
                        "command": act.get("command"), "validation": act.get("validation"),
                        "note": "look at its stream before acting: a long build or replay is usual"}
    waiting = {e["item"] for e in conductor.read_events(run.dir) if e.get("type") == "item" and e.get("state") == "waiting"}
    announced = set(data.get("announced") or [])
    if waiting - announced:
        out_jobs = unfinished_or_none(run.root)
        for item in sorted(waiting - announced) if out_jobs is not None else []:
            if not out_jobs.get(item):
                run.update(announced=sorted(announced | {item}))
                return {"kind": "proof", "item": item,
                        "note": "its verification jobs are in: the loop takes it up again when it next changes example"}
    last = (data.get("lastSummary") or {}).get("time") or stamp((data.get("loop") or {}).get("started")) or 0
    if now() - last >= interval:
        return {"kind": "summary"}
    return None


def cmd_wait(run: Run, interval: float | None, timeout: float) -> int:
    interval = interval if interval is not None else run.read().get("interval", INTERVAL)
    until, looked = time.monotonic() + timeout, None
    while True:
        thing = next_thing(run, interval)
        if thing is None and (looked is None or time.monotonic() - looked >= QUEUE_LOOK):
            looked = time.monotonic()
            thing = tend_queue(run)
        if thing is not None:
            if thing["kind"] == "summary":
                return cmd_summary(run)
            print(json.dumps(thing, indent=1))
            return 0
        if time.monotonic() >= until:
            print(json.dumps({"kind": "nothing", "note": "nothing yet: wait again"}))
            return 3
        time.sleep(2)


# -- what the user asks for between examples

def merge_queue(run: Run) -> list[str]:
    try:
        return [line.strip() for line in (run.dir / conductor.MERGE_QUEUE).read_text().splitlines() if line.strip()]
    except OSError:
        return []


def cmd_merge(run: Run, action: str, name: str | None) -> int:
    queue = merge_queue(run)
    if action == "add":
        workspaces = subprocess.run(["jj", "--quiet", "workspace", "list"], capture_output=True, text=True, cwd=run.root).stdout
        if not re.search(rf"^{re.escape(name)}( \(current\))?:", workspaces, re.M):
            print(f"no workspace {name} in this repository (jj workspace list)", file=sys.stderr)
            return 2
        queue = queue + [name] if name not in queue else queue
    elif action == "done":
        queue = [q for q in queue if q != name]
    run.dir.mkdir(parents=True, exist_ok=True)
    (run.dir / conductor.MERGE_QUEUE).write_text("".join(q + "\n" for q in queue))
    print("queued to merge between examples: " + (", ".join(queue) or "nothing"))
    return 0


def cmd_stop_after(run: Run, what: str) -> int:
    conductor.cmd_command(run.dir, {"example": "item", "cycle": "stop", "never": "inf"}[what])
    print({"example": "the loop ends once the example under way is done",
           "cycle": "the loop ends after the cycle under way",
           "never": "the loop runs until its examples are done"}[what])
    return 0


def cmd_add(run: Run, items: list[str]) -> int:
    """Leave the loop a line that adds examples after the ones it has (feature-loop.sh's `add`)."""
    loop = run.run_json()
    if not loop or not alive(loop.get("pid")):
        print("no proof loop is running: start one with these examples (`watch.py loop`)", file=sys.stderr)
        return 1
    conductor.cmd_command(run.dir, "add " + " ".join(items))
    loop["examples"] = list(dict.fromkeys((loop.get("examples") or []) + items))  # what the summary lists
    (run.dir / "run.json").write_text(json.dumps(loop, indent=1) + "\n")
    print(f"the loop takes {' '.join(items)} after the examples it has, when it next changes example")
    return 0


def cmd_proof(run: Run, item: str, timeout: float) -> int:
    until = time.monotonic() + timeout
    while True:
        known = unfinished_or_none(run.root)
        out = known.get(item, []) if known is not None else ["(the queue could not be read)"]
        if not out:
            row = (changes.listing(run.root, [item])["examples"] or [{}])[0]
            print(json.dumps({"item": item, "jobs": "in", "example": row.get("state"),
                              "claims": {t: c["status"] for t, c in (row.get("claims") or {}).items()}}, indent=1))
            return 0
        if time.monotonic() >= until:
            print(json.dumps({"item": item, "jobs": "not in yet", "waitingFor": out}))
            return 3
        time.sleep(min(15, max(0.2, until - time.monotonic())))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="command", required=True)
    se = sub.add_parser("session").add_mutually_exclusive_group()
    se.add_argument("--new", action="store_true")
    se.add_argument("--use", metavar="ID")
    st = sub.add_parser("stage")
    st.add_argument("name", choices=sorted(STAGES))
    st.add_argument("prompt")
    st.add_argument("--model")
    st.add_argument("--effort")
    st.add_argument("--memory")
    st.add_argument("--example", metavar="NNN")
    st.add_argument("--workspace", metavar="NAME")
    sub.add_parser("add").add_argument("items", nargs="+", metavar="NNN")
    pf = sub.add_parser("preflight")
    pf.add_argument("examples", nargs="+", metavar="NNN")
    pf.add_argument("--after-setup", default="", metavar="NNN,...")
    cl = sub.add_parser("claims")
    cl.add_argument("examples", nargs="+", metavar="NNN")
    cl.add_argument("--json", action="store_true")
    cl.add_argument("--accept", metavar="REASON")
    sub.add_parser("plan").add_argument("--check", action="store_true")
    sub.add_parser("verification").add_argument("action", choices=("start", "stop", "status", "nudge"))
    sub.add_parser("loop").add_argument("arguments", nargs="*")
    w = sub.add_parser("wait")
    w.add_argument("--interval", type=float)
    w.add_argument("--timeout", type=float, default=3300)
    sub.add_parser("summary")
    sub.add_parser("status").add_argument("--json", action="store_true")
    sub.add_parser("interval").add_argument("seconds", type=int)
    m = sub.add_parser("merge")
    m.add_argument("action", choices=("add", "done", "list"))
    m.add_argument("name", nargs="?")
    sub.add_parser("stop-after").add_argument("what", choices=("example", "cycle", "never"))
    pr = sub.add_parser("proof")
    pr.add_argument("item")
    pr.add_argument("--timeout", type=float, default=3300)
    # What follows `loop` is prove-loop.sh's own, in the order given: argparse would take the options out from
    # between their values (`--memory 12G --wait-for-proofs 288` as `--memory --wait-for-proofs 12G 288`).
    argv = list(sys.argv[1:] if argv is None else argv)
    at = 2 if argv[:1] == ["--root"] else 0
    loop_arguments = argv[at + 1:] if argv[at:at + 1] == ["loop"] else []
    args = ap.parse_args(argv[:at + 1] if argv[at:at + 1] == ["loop"] else argv)
    run = Run(args.root.resolve())
    if args.command == "session":
        print(fixed_session(run, args.new, args.use))
    elif args.command == "stage":
        return cmd_stage(run, args.name, args.prompt, args.model, args.effort, args.memory, args.example, args.workspace)
    elif args.command == "add":
        return cmd_add(run, args.items)
    elif args.command in ("preflight", "claims"):
        set_up = [n for n in getattr(args, "after_setup", "").split(",") if n]
        bad = [n for n in args.examples + set_up if not (len(n) == 3 and n.isdigit())]
        if bad:
            ap.error(f"not an example's number: {' '.join(bad)}")
        if args.command == "claims":
            if args.accept is not None:
                if not args.accept.strip():
                    ap.error("--accept takes the reason the claims are the ones to prove")
                return cmd_accept_claims(run, args.examples, args.accept)
            return cmd_claims(run, args.examples, args.json)
        return cmd_preflight(run, args.examples, set_up)
    elif args.command == "verification":
        return cmd_verification(run, args.action)
    elif args.command == "loop":
        return cmd_loop(run, loop_arguments)
    elif args.command == "wait":
        return cmd_wait(run, args.interval, args.timeout)
    elif args.command == "summary":
        return cmd_summary(run)
    elif args.command == "plan":
        return cmd_plan(run, args.check)
    elif args.command == "status":
        s = state(run)
        print(json.dumps(s, indent=1) if args.json else render(s, run.read().get("lastSummary"), run.root))
    elif args.command == "interval":
        run.update(interval=args.seconds)
        print(f"a summary every {span(args.seconds)}")
    elif args.command == "merge":
        if args.action != "list" and not args.name:
            ap.error("merge add and merge done take a workspace's name")
        return cmd_merge(run, args.action, args.name)
    elif args.command == "stop-after":
        return cmd_stop_after(run, args.what)
    elif args.command == "proof":
        return cmd_proof(run, args.item, args.timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
