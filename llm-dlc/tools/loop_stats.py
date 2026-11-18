#!/usr/bin/env python3
"""What the unattended loops cost and produced: every run of feature-loop.sh and of the verification
loop, added up by category, loop, run, cycle and item.

`sync.py` calls this on every sync and writes llm-dlc/traces/loops.json and loops.md. Like
metrics.py, nothing here touches the disk or the clock: the output is a function of the sessions'
metrics.json and manifests, the published run records (traces/<session>/runs/*.md) and the
verification jobs with their results, so it can be rebuilt from the repo and `check` can tell when
it is stale. llm-dlc/specification.md describes the output.

A loop's turns are prompts like any other in a session's metrics, each with its time, tokens and
cost. This module only decides which prompts belong to which loop:

- A run with a published record owns the prompts of the session its header names between
  its Started line and its end line. The n-th instruction among them starts cycle n, which is the
  record's "- cycle n" line when the cycle committed, and for a templated moonshot takes the n-th
  item of the header's list. A record without an end line (a run that was killed, or is still
  going) owns prompts up to the next run's start, or up to the first prompt that is not the loop's.
- A run with no published record is read from the prompts alone: consecutive cycles of one
  instruction (a brief's "Work on the brief in ...", or one of the first moonshots' one-liners),
  ended by a prompt a person typed, by 30 minutes without a turn, by the loop's closing summary, or
  by the loop's own count of cycles starting over. That is every run before 2026-11-06: the script
  kept no record until 2026-11-03, and the records of the days between were never published.
  `source` says which way a run was found.
- The loop a person ran by hand on 2026-10-31, before the script existed, is read the same way, from
  the three instructions typed that evening (HAND_RUN): each was followed by a commit and a typed
  /compact, which is the cycle the script automated two hours later. Its kind, `moonshot by hand`,
  keeps it apart from what the script ran.
- A session whose every prompt is /run-verification is one run of the verification loop.

Within a run, the instruction turn and whatever answers it (background-task notifications,
messages from other sessions) is the cycle's work; the turns the script adds (the decision to go
on, the status line, the compact, the closing summary, a stream's fork turn) are its overhead.

Standard library only.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import metrics  # llm-dlc/tools/metrics.py

SCHEMA = "llm-trace-loops/v1"
RUN_GAP_MS = metrics.PAUSE_MS  # the script starts a cycle right after the compact: a gap this long is a new run

UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
STAMP = r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d"
RECORD_TITLE = re.compile(r"^# Feature loop: (?P<loop>\S+)[ \t]*$", re.M)
RECORD_STARTED = re.compile(
    rf"^Started (?P<started>{STAMP})(?: (?P<zone>[^,\s]+))?, (?P<cap>[^,\n]*?) cycles?, session (?P<sid>{UUID}), "
    r"(?P<model>\S+) at (?P<effort>\S+) effort", re.M)
# A session carried by Codex is traced under Codex's thread id, not the id the loop gave it: the record says which
# (feature-loop.sh writes the line once the thread exists), and the thread is then the session the run's turns are in.
RECORD_THREAD = re.compile(rf"^Codex thread (?P<thread>{UUID}) carries session (?P<sid>{UUID})\.$", re.M)
RECORD_CYCLE = re.compile(rf"^- cycle (?P<n>\d+), (?:item (?P<item>[^,]*), )?(?P<when>{STAMP}), `(?P<change>[a-z]+)`: (?P<summary>.*)$")
RECORD_NO_COMMIT = re.compile(rf"^- cycle \d+, {STAMP}: no commit$")  # a single-agent run's: what follows is not the last commit's
RECORD_DECIDED = re.compile(r"^  - decided to (?P<decision>continue|stop|unclear)\b")
RECORD_END = re.compile(rf"^(?P<how>Ended|Stopped|Interrupted) (?P<when>{STAMP})(?P<rest>.*)$", re.M)
RECORD_ITEMS = re.compile(r"^Each cycle puts the next item in place of \{\}: (?P<run>.*?) \(the list: (?P<all>.*)\)\.$", re.M)
# Since 2026-11-16 an item may take several cycles, until a judge outside the session finds it
# finished: the header lists the items left, not one per cycle, and each commit line is followed by
# the judge's verdict on its item.
RECORD_ITEMS_JUDGED = re.compile(
    r"^Each item stays in place of \{\} until a judge outside the session finds it finished: (?P<run>.*?) \(the list: (?P<all>.*)\)\.$", re.M)
# "waiting" leaves an item open as "continues" does: the loop comes back to it when its verification jobs are in.
RECORD_VERDICT = re.compile(r"^  - item (?P<item>\S+) (?P<verdict>continues|waiting|finished|left after)\b")
# A single-agent run (feature-loop.sh's `single-agent`): the first cycle takes one text and every later one the
# run's continue message, which a person may change between two cycles, so no opening words tell its instructions.
RECORD_SINGLE = re.compile(r"^Every later cycle takes the run's continue message as it stands when the cycle starts", re.M)
RECORD_BRIEF = re.compile(r"^Brief `(?P<brief>[^`]+)` at sha256 ", re.M)
RECORD_FORK = re.compile(rf"^Session {UUID} was forked from session (?P<parent>{UUID})\.", re.M)
REASONS = (  # how feature-loop.sh words each ending, first match wins
    ("the run was ended there (the watcher", "watcher ended it"), ("the run was ended there (no verdict", "no watcher"),
    ("but the brief's status still says", "status left working"), ("the brief says done", "work done"),
    ("decided the work was done", "work done"), ("the brief says waiting on jobs", "waiting on jobs"),
    ("the brief says blocked", "blocked"), ("the session decided to stop", "decided to stop"),
    ("no items left", "no items left"), ("compacted with no commit", "compacted, no commit"), ("made no commit", "no commit"), ("the brief changed", "brief changed"),
    ("gave no clear", "unclear decision"), ("the fork of session", "fork failed"),
    ("while waiting on the verification jobs", "stopped waiting on jobs"), ("did not come in within", "jobs not in"),
    ("was finished, as asked", "stopped after its item"), (", as asked", "stopped after its item"))

# What the script sends besides the instruction, as the transcripts hold it (metrics.py keeps the
# first 200 characters of a prompt, whitespace collapsed).
DECIDE = re.compile(r"^Cycle (\d+) of the feature loop is committed\.")
SUMMARY = re.compile(r"^The feature loop is ending after (\d+) cycle")
STATUS = "You decided that the loop stops after this cycle"
FORK = "This conversation goes on as one of the parallel streams it planned"
FORK_SINGLE = "This conversation goes on, from here, as an unattended run of one agent"
BRIEF = re.compile(r"^Work on the brief in `([^`]+)`")
EVENTS = ("<cross-session-message", "<agent-message", "<task-notification", "[Request interrupted by user")
VERIFY = "/run-verification"
BOOKKEEPING = "Record session traces"  # `sync.py push`'s commit: it records a session, it is not the loop's work
MIN_PREFIX = 16  # an instruction is told by its opening words, and fewer than this could be anyone's

# The moonshots that ran before any record was published (2026-11-01 to 2026-11-04), by the opening
# words of the instruction each cycle sent. Later ones are read from their records.
EARLY_MOONSHOTS = {
    "features": "Add more advanced features along with examples to the jvmcontract library.",
    "tla": "Add more advanced examples showcasing verification of TLA specs",
    "spring": "Enhance the jvmcontract library to be more useful to expert Spring Boot developers.",
    "relational": "Enhance relational verification capabilities to be more efficient and accurate",
}

# The loop before the loop: on 2026-10-31 a person typed an instruction, let the session commit,
# typed /compact, and did it again, three times, each time for another audience. feature-loop.sh
# was written that night to do the same unattended. Counted as a loop of its own kind, since no
# script ran it: nothing capped a cycle, checked for a commit or compacted for it.
BY_HAND = "moonshot by hand"
HAND_RUN = {
    "examples-by-hand": (
        "Create more novel examples of formal verification against Java bytecode using the jvmcontract library that "
        "feel exciting to expert Java distributed systems principals.",
        "Create examples implementing formal Java bytecode verification using the jvmcontract library that will "
        "impress senior principals working in the Java Spring Boot ecosystem at top firms globally.",
        "Create examples implementing formal Java bytecode verification using the jvmcontract library that will "
        "impress top global Java experts.",
    ),
}

CATEGORIES = ("moonshot", "brief", "verification")
KIND_CATEGORY = {"moonshot": "moonshot", "templated moonshot": "moonshot", BY_HAND: "moonshot", "brief": "brief",
                 "brief stream": "brief", "verification loop": "verification"}
TIMES = ("agent_ms", "model_ms", "tool_ms", "busy_ms")
ADDED = ("api_calls", "tool_calls", *metrics.TOKEN_KEYS, "usd", "uncached_usd", "unpriced_calls", *TIMES,
         "compaction_ms", "compactions", "tool_errors", "overhead_usd", "overhead_ms",
         "jobs", "jobs_passed", "jobs_failed", "jobs_pending", "job_wall_seconds", "job_cpu_seconds")
INF = float("inf")


# --------------------------------------------------------------------------- small helpers

def _iso(ms: int | float | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _squash(text: str) -> str:
    return " ".join(text.split())


def _add(rows: list[dict]) -> dict:
    """The sum of every additive column, for rows that are cycles, runs or loops."""
    out = {k: sum(r.get(k) or 0 for r in rows) for k in ADDED}
    for k in ("usd", "uncached_usd", "overhead_usd", "job_wall_seconds", "job_cpu_seconds"):
        out[k] = round(out[k], 6 if k.endswith("usd") else 1)
    return out


def _measure(prompts: list[dict]) -> dict:
    return {**metrics.tally(prompts), **{k: sum(p[k] for p in prompts) for k in TIMES},
            "tool_errors": sum(p["tool_errors"] for p in prompts)}


# --------------------------------------------------------------------------- run records

def _record_ms(stamp: str, zone: str | None) -> int:
    offset = 0
    if zone and re.fullmatch(r"[+-]\d{4}", zone):
        offset = (1 if zone[0] == "+" else -1) * (int(zone[1:3]) * 60 + int(zone[3:]))
    at = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(at.timestamp() * 1000) - offset * 60_000


def record_session(text: str) -> str | None:
    """The session whose log holds a record's turns: the Codex thread it names for the session of its header, or
    that session itself. None for a text that is no record."""
    head = RECORD_STARTED.search(text)
    if not head:
        return None
    thread = RECORD_THREAD.search(text)
    return thread["thread"] if thread and thread["sid"] == head["sid"] else head["sid"]


def parse_record(name: str, text: str) -> dict | None:
    """A run record of feature-loop.sh as data, or None for a file that is not one. Its times are
    the script's clock: UTC since the script writes it so, and read as UTC from an older record
    whose header names a zone this cannot place (`zone_known` says which)."""
    title, head = RECORD_TITLE.search(text), RECORD_STARTED.search(text)
    if not title or not head:
        return None
    zone = head["zone"]
    at = text.find("\n## Commits")
    header, body = (text[:at], text[at:]) if at >= 0 else (text, "")
    listed = body[:end] if (end := body.find("\n## Summary\n")) >= 0 else body
    quoted = re.search(r"^> (.*)$", header[head.end():], re.M)
    instruction = _squash(quoted[1]) if quoted else ""
    items = RECORD_ITEMS.search(header)
    judged = RECORD_ITEMS_JUDGED.search(header)
    cycles, last = {}, None
    for line in listed.split("\n"):
        if m := RECORD_CYCLE.match(line):
            last = cycles[int(m["n"])] = {"item": m["item"], "at": _record_ms(m["when"], zone), "change": m["change"],
                                          "summary": m["summary"].strip(), "decision": None, "verdict": None}
        elif RECORD_NO_COMMIT.match(line):
            last = None
        elif last is not None and (m := RECORD_DECIDED.match(line)):
            last["decision"] = m["decision"]
        elif last is not None and (m := RECORD_VERDICT.match(line)):
            last["verdict"] = "continue" if m["verdict"] in ("continues", "waiting") else "finished"
    ends = list(RECORD_END.finditer(text))
    end = None
    if ends:
        how, rest = ends[-1]["how"].lower(), ends[-1]["rest"].strip(" :")
        reason = "interrupted" if how == "interrupted" else next(
            (label for words, label in REASONS if words in rest), "cycle count reached" if how == "ended" else "stopped")
        end = {"outcome": how, "at": _record_ms(ends[-1]["when"], zone), "reason": reason, "how": rest}
    return {
        "name": name, "loop": title["loop"], "session_id": record_session(text), "loop_session": head["sid"], "started": _record_ms(head["started"], zone),
        "zone": zone, "zone_known": zone in (None, "UTC", "GMT", "Z") or bool(re.fullmatch(r"[+-]\d{4}", zone or "")),
        "cap": int(head["cap"]) if head["cap"].strip().isdigit() else None, "model": head["model"], "effort": head["effort"],
        "instruction": instruction, "prefix": instruction.split("{}")[0][:80],
        "run_items": items["run"].split() if items else None,
        "all_items": items["all"].split() if items else judged["all"].split() if judged else None,
        "brief": m["brief"] if (m := RECORD_BRIEF.search(header)) else None, "single": bool(RECORD_SINGLE.search(header)),
        "forked_from": m["parent"] if (m := RECORD_FORK.search(text)) else None,
        "cycles": cycles, "end": end,
    }


def _done_items(cycles: list[dict]) -> set:
    """The items a commit closed: an item is done after a committed cycle on it, unless the judge's
    verdict on its latest one was that it continues."""
    state = {}
    for c in cycles:
        if c["outcome"] == "commit" and c["item"] is not None:
            state[c["item"]] = not c.get("item_open")
    return {item for item, done in state.items() if done}


# --------------------------------------------------------------------------- a session's prompts

def _role(prompt: dict) -> tuple[str, int | None]:
    """What a prompt is to a loop, before knowing which loop: `human` is anything typed or sent that
    the script has no fixed words for, an instruction included."""
    kind, text = prompt["kind"], prompt.get("text") or ""
    if kind == "task_notification":
        return "event", None
    if kind == "command":
        return ("compact" if text.strip() == "/compact" else "command"), None
    if m := DECIDE.match(text):
        return "decide", int(m[1])
    if m := SUMMARY.match(text):
        return "summary", int(m[1])
    if text.startswith(STATUS):
        return "status", None
    if text.startswith((FORK, FORK_SINGLE)):
        return "fork", None
    if text.startswith(EVENTS):
        return "event", None
    return "human", None


def _loop_of(text: str, moonshots: dict[str, tuple[str, ...]]) -> str | None:
    """The loop whose instruction this prompt is, by its opening words: `moonshots` gives each
    moonshot's, and more than one for a loop whose instruction a person reworded."""
    if m := BRIEF.match(text):
        return m[1].rsplit("/", 1)[-1].removesuffix(".md")
    openings = [(prefix, name) for name, prefixes in moonshots.items() for prefix in prefixes]
    for prefix, name in sorted(openings, key=lambda pair: -len(pair[0])):
        if len(prefix) >= MIN_PREFIX and text.startswith(prefix):
            return name
    return None


class _Session:
    """One session's metrics, indexed the way the loops read them."""

    def __init__(self, manifest: dict, doc: dict):
        self.sid = manifest.get("session_id") or doc.get("session_id")
        self.prompts = doc["prompts"]
        self.ts = [metrics._ms(p["ts"]) for p in self.prompts]
        self.end = [metrics._ms(p["end"]) for p in self.prompts]
        self.roles = [_role(p) for p in self.prompts]
        self.used = [False] * len(self.prompts)
        self.compactions = [(metrics._ms(c["ts"]), c) for c in doc.get("compactions", []) if c.get("ts")]
        messages = {c.get("change_id"): f"{c.get('summary') or ''}\n{c.get('body') or ''}" for c in manifest.get("commits", [])}
        self.commits = [(metrics._ms(c["ts"]), c, messages.get(c["change_id"], "")) for c in doc.get("commits", [])
                        if c.get("ts") and c.get("summary") and c["summary"] != BOOKKEEPING]
        self.peak, self.models, self.efforts = {}, {}, {}
        for c in doc.get("calls", []):
            at = c.get("prompt")
            if at is None:
                continue
            if c.get("agent") is None:
                self.peak[at] = max(self.peak.get(at, 0), c.get("context_tokens") or 0)
            spent = self.models.setdefault(at, {})
            spent[c.get("model")] = spent.get(c.get("model"), 0) + (c.get("usd") or 0) + 1e-9
            if c.get("effort"):
                self.efforts.setdefault(at, set()).add(c["effort"])

    def next_after(self, index: int) -> float:
        """When the prompt after this one was sent: nothing later belongs to this one's cycle."""
        return self.ts[index + 1] if index + 1 < len(self.ts) else INF


class _Run:
    def __init__(self, session: _Session, loop: str, record: dict | None = None, kind: str | None = None):
        self.session, self.loop, self.record, self.kind = session, loop, record, kind
        self.cycles: list[dict] = []   # {"work": [prompt index], "overhead": [...], "counted": the script's own number}
        self.before: list[int] = []    # a stream's fork turn
        self.after: list[int] = []     # the closing summary
        self.summarized = False
        self.interjections = 0         # prompts inside the run that are not the script's

    def add(self, role: str, detail: int | None, index: int) -> None:
        self.session.used[index] = True
        self.interjections += role in ("human", "command")
        if role == "instruction":
            self.cycles.append({"work": [index], "overhead": [], "counted": None})
        elif role == "summary":
            self.after.append(index)
            self.summarized = True
        elif not self.cycles:
            self.before.append(index)
        elif role in ("decide", "status", "compact"):
            self.cycles[-1]["overhead"].append(index)
            if role == "decide":
                self.cycles[-1]["counted"] = detail
        else:
            self.cycles[-1]["work"].append(index)

    def indexes(self) -> list[int]:
        return sorted(self.before + self.after + [i for c in self.cycles for i in c["work"] + c["overhead"]])


def _record_runs(session: _Session, records: list[dict]) -> list[_Run]:
    """The runs that have a record: each owns its session's prompts inside its window."""
    runs, records = [], sorted(records, key=lambda r: r["started"])
    for at, record in enumerate(records):
        if record["end"]:
            until = record["end"]["at"] + 1000  # the end line is written, to the second, after the last turn
        else:
            until = records[at + 1]["started"] if at + 1 < len(records) else INF
        run = _Run(session, record["loop"], record)
        for index, prompt in enumerate(session.prompts):
            if session.used[index] or not record["started"] <= session.ts[index] < until:
                continue
            role, detail = session.roles[index]
            text = prompt.get("text") or ""
            if role == "human" and (record["single"]  # nobody types into a run's session: each is a cycle's text
                                    or (len(record["prefix"]) >= MIN_PREFIX and text.startswith(record["prefix"]))
                                    or _loop_of(text, {}) == record["loop"]):
                role = "instruction"
            if role in ("human", "command") and not record["end"]:
                break  # no end line, and a person is typing: the run was over by now
            run.add(role, detail, index)
        runs.append(run)
    return runs


def _transcript_runs(session: _Session, moonshots: dict[str, tuple[str, ...]]) -> list[_Run]:
    """The runs no record holds, read from the prompts no record's run claimed."""
    runs: list[_Run] = []
    run, last = None, 0
    for index, prompt in enumerate(session.prompts):
        if session.used[index]:
            run = None
            continue
        role, detail = session.roles[index]
        text = prompt.get("text") or ""
        loop = _loop_of(text, moonshots) if role == "human" else None
        if loop:
            if run is None or run.loop != loop or session.ts[index] - last > RUN_GAP_MS:
                run = _Run(session, loop, kind="brief" if BRIEF.match(text) else BY_HAND if loop in HAND_RUN else "moonshot")
                runs.append(run)
            run.add("instruction", None, index)
        elif run is None:
            continue
        elif role in ("human", "command"):
            run = None
            continue
        elif role == "decide" and detail == 1 and len(run.cycles) > 1:
            # The script counts cycles from 1 in every run: this cycle began a new one.
            cycle = run.cycles.pop()
            run = _Run(session, run.loop, kind=run.kind)
            runs.append(run)
            run.cycles.append(cycle)
            run.add(role, detail, index)
        else:
            run.add(role, detail, index)
            if role == "summary":
                run = None
        last = max(last, session.end[index])
    return runs


def _verification_run(session: _Session) -> _Run | None:
    """A session the verification loop started: nothing in it but /run-verification and what the
    queue sent back."""
    commands = [i for i, p in enumerate(session.prompts) if p["kind"] == "command"]
    if not commands or any(u for u in session.used):
        return None
    for index, prompt in enumerate(session.prompts):
        role, _ = session.roles[index]
        if role != "event" and not (role == "command" and (prompt.get("text") or "").strip() == VERIFY):
            return None
    run = _Run(session, "verification", kind="verification loop")
    run.before = list(range(len(session.prompts)))
    session.used = [True] * len(session.prompts)
    return run


# --------------------------------------------------------------------------- verification jobs

def _job_chains(jobs: list[dict]) -> dict[str, dict]:
    """Each job that reruns no other, with the reruns that followed it: the last of them is the
    verdict, and what all of them took is what the verdict cost."""
    by_id = {j["id"]: j for j in jobs}

    def root(job: dict) -> str:
        seen = set()
        while job.get("supersedes") in by_id and job["id"] not in seen:
            seen.add(job["id"])
            job = by_id[job["supersedes"]]
        return job["id"]

    chains: dict[str, list[dict]] = {}
    for job in jobs:
        chains.setdefault(root(job), []).append(job)
    out = {}
    for first, members in chains.items():
        members.sort(key=lambda j: (j.get("at") or "", j["id"]))
        final = members[-1]
        ran = [j for j in members if j.get("status")]
        out[first] = {
            "job": first, "submitted": by_id[first].get("at"), "session": by_id[first].get("session"),
            "ids": [j["id"] for j in members], "final": final["id"], "status": final.get("status") or "pending",
            "attempts": len(members), "examples": by_id[first].get("examples") or [],
            "wall_seconds": round(sum(j.get("wall_seconds") or 0 for j in ran), 1),
            "cpu_seconds": round(sum(j.get("cpu_seconds") or 0 for j in ran), 1),
            "peak_memory_bytes": max((j.get("peak_memory_bytes") or 0 for j in ran), default=0),
        }
    return out


def _job_ms(at: str | None) -> int | None:
    try:
        return round(datetime.fromisoformat((at or "").replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


# --------------------------------------------------------------------------- rows

def _rows_of(run: _Run, chains: dict[str, dict], taken: set[str]) -> tuple[dict, list[dict], list[dict]]:
    """(the run's row, its cycles' rows, its jobs' rows)."""
    s, record = run.session, run.record
    prompts = lambda indexes: [s.prompts[i] for i in indexes]
    name = record["name"] if record else None
    indexes = run.indexes()
    first = record["started"] if record else s.ts[indexes[0]]
    limit = s.next_after(indexes[-1]) if indexes else INF
    if record and record["end"]:
        limit = min(limit, record["end"]["at"] + 1000)
    if name is None:
        name = datetime.fromtimestamp(first / 1000, timezone.utc).strftime("%Y-%m-%d-%H%M%S") + "-" + run.loop
    kind = run.kind or ("templated moonshot" if record["all_items"] else "brief" if record["brief"] else "moonshot")
    numbers = sorted(set(range(1, len(run.cycles) + 1)) | set(record["cycles"] if record else ()))
    submitted = [(ms, c) for c in chains.values() if (ms := _job_ms(c["submitted"])) is not None]

    cycles, job_rows = [], []
    for n in numbers:
        found = run.cycles[n - 1] if n <= len(run.cycles) else None
        line = record["cycles"].get(n) if record else None
        item = record["run_items"][n - 1] if record and record["run_items"] and n <= len(record["run_items"]) else \
            line["item"] if line else None
        row = {"run": name, "loop": run.loop, "cycle": n, "item": item, "measured": found is not None,
               "item_open": bool(line and line.get("verdict") == "continue")}
        if found:
            work, overhead = prompts(found["work"]), prompts(found["overhead"])
            start = s.ts[found["work"][0]]
            until = s.ts[run.cycles[n]["work"][0]] if n < len(run.cycles) else limit
            compactions = [c for ms, c in s.compactions if start <= ms < until]
            end = max([s.end[i] for i in found["work"] + found["overhead"]]
                      + [ms for ms, _ in s.compactions if start <= ms < until])
            # A commit is the cycle's when the session made it during one of the cycle's turns. One
            # stamped on the session afterwards, while it sat idle, is another session's work.
            turns_end = max(s.end[i] for i in found["work"] + found["overhead"])
            commits = [(c, text) for ms, c, text in s.commits if start <= ms <= turns_end]
            # A job is the cycle's when it was submitted during it and names its session, or, naming
            # none, is named by a commit of the cycle: streams work side by side, so the time alone is not enough.
            owned = [c for ms, c in submitted if start <= ms < until and c["job"] not in taken and (
                c["session"] == s.sid or (not c["session"] and any(i in text for _, text in commits for i in c["ids"])))]
            manual = [c for c in compactions if c.get("trigger") != "auto"]
            row.update(
                started=_iso(start), ended=_iso(end), elapsed_ms=end - start,
                outcome="commit" if line or commits or found["counted"] else "no commit",
                decision=line["decision"] if line else ("continue" if found["counted"] else None),
                commits=len(commits) or int(bool(line or found["counted"])),
                changes=[c["change_id"][:12] for c, _ in commits] or ([line["change"]] if line else []),
                summary=line["summary"] if line else commits[-1][0]["summary"] if commits else None,
                turns=len(work), **_measure(work + overhead),
                overhead_usd=round(sum(p["usd"] or 0 for p in overhead), 6), overhead_ms=sum(p["agent_ms"] for p in overhead),
                compactions=len(compactions), compaction_ms=sum(c.get("ms") or 0 for c in compactions),
                context_tokens=(manual or compactions)[-1].get("pre_tokens") if compactions else None,
                peak_context_tokens=max((s.peak.get(i, 0) for i in found["work"]), default=0))
        else:  # the record lists a commit the session's metrics do not reach yet
            owned = []
            row.update(started=None, ended=_iso(line["at"]), elapsed_ms=None, outcome="commit", decision=line["decision"],
                       commits=1, changes=[line["change"]], summary=line["summary"], turns=0, **_measure([]),
                       overhead_usd=0.0, overhead_ms=0, compactions=0, compaction_ms=0, context_tokens=None,
                       peak_context_tokens=0)
        owned.sort(key=lambda c: (c["submitted"] or "", c["job"]))
        taken.update(c["job"] for c in owned)
        row.update(jobs=len(owned), **{f"jobs_{k}": sum(c["status"] == k for c in owned) for k in ("passed", "failed", "pending")},
                   job_wall_seconds=round(sum(c["wall_seconds"] for c in owned), 1),
                   job_cpu_seconds=round(sum(c["cpu_seconds"] for c in owned), 1))
        job_rows += [{"job": c["job"], "loop": run.loop, "run": name, "cycle": n, "item": item, "submitted": c["submitted"],
                      "attempts": c["attempts"], "final": c["final"], "status": c["status"],
                      "wall_seconds": c["wall_seconds"], "cpu_seconds": c["cpu_seconds"],
                      "peak_memory_bytes": c["peak_memory_bytes"]} for c in owned]
        cycles.append(row)

    aside = prompts(run.before + run.after)  # outside any cycle: all the script's own, or all a verification run is
    whole = _measure(prompts(indexes))
    spent: dict[str, float] = {}
    for i in indexes:
        for model, usd in s.models.get(i, {}).items():
            spent[model] = spent.get(model, 0) + usd
    efforts = sorted({e for i in indexes for e in s.efforts.get(i, ())})
    last = max((s.end[i] for i in indexes), default=first)
    last = max([last] + [ms for ms, _ in s.compactions if first <= ms < limit])
    end = record["end"] if record else None
    verification = kind == "verification loop"
    totals = _add(cycles)
    out = {
        "run": name, "loop": run.loop, "kind": kind, "source": "record" if record else "session" if verification else "transcript",
        "record": f"{s.sid}/runs/{record['name']}.md" if record else None, "session_id": s.sid,
        "started": _iso(first), "ended": _iso(end["at"] if end else last),
        "elapsed_ms": (end["at"] if end else last) - first,
        "outcome": end["outcome"] if end else "ended" if run.summarized or verification else "unrecorded",
        "reason": end["reason"] if end else "summarized" if run.summarized else "" if verification else
                  "typed by hand" if kind == BY_HAND else "no end recorded",
        "how": metrics._clip(end["how"], lambda t: t) if end else "",
        "model": max(spent, key=spent.get) if spent else record["model"] if record else None,
        "models": sorted(m for m in spent if m), "effort": record["effort"] if record else ", ".join(efforts) or None,
        "cycle_cap": record["cap"] if record else None, "items": record["run_items"] if record else None,
        "forked_from": record["forked_from"] if record else None,
        "zone_known": record["zone_known"] if record else True,
        "measured": bool(indexes), "interjections": run.interjections,
        "cycles": len(cycles), "cycles_committed": sum(c["outcome"] == "commit" for c in cycles),
        "commits": sum(c["commits"] for c in cycles) if not verification else
                   sum(1 for ms, _, _ in s.commits if first <= ms < limit),
        **{**totals, **whole},
        "overhead_usd": round(totals["overhead_usd"] + (0 if verification else sum(p["usd"] or 0 for p in aside)), 6),
        "overhead_ms": totals["overhead_ms"] + (0 if verification else sum(p["agent_ms"] for p in aside)),
        "peak_context_tokens": max([c["peak_context_tokens"] for c in cycles] + [s.peak.get(i, 0) for i in indexes], default=0),
    }
    if verification:
        own = [c for ms, c in s.compactions if first <= ms < limit]
        out.update(compactions=len(own), compaction_ms=sum(c.get("ms") or 0 for c in own))
    return out, cycles, job_rows


def _median(values: list) -> int | float | None:
    values = sorted(v for v in values if v is not None)
    return values[len(values) // 2] if values else None


def _group(rows: list[dict], cycles: list[dict]) -> dict:
    """What a set of runs comes to, with their cycles for the medians."""
    measured = [c for c in cycles if c["measured"]]
    added = _add(rows)
    return {
        "runs": len(rows), "cycles": sum(r["cycles"] for r in rows),
        "cycles_committed": sum(r["cycles_committed"] for r in rows), "commits": sum(r["commits"] for r in rows),
        "sessions": len({r["session_id"] for r in rows}), "models": sorted({m for r in rows for m in r["models"]}),
        "first": min((r["started"] for r in rows), default=None), "last": max((r["ended"] for r in rows), default=None),
        "elapsed_ms": sum(r["elapsed_ms"] for r in rows), **added,
        "median_cycle_busy_ms": _median([c["busy_ms"] for c in measured]),
        "median_cycle_usd": _median([c["usd"] for c in measured]),
        "peak_context_tokens": max((r["peak_context_tokens"] for r in rows), default=0),
    }


def loops(sessions: list[tuple[dict, dict]], records: list[tuple[str, str]], jobs: list[dict], pricing: dict) -> dict:
    """Every loop added up. `sessions` is (manifest, metrics) for each session, `records` (file stem,
    text) for each published run record, and `jobs` one dict per verification job: id, at, session,
    supersedes, examples, and from its result, when it has one, status, wall_seconds, cpu_seconds
    and peak_memory_bytes."""
    parsed = [r for name, text in sorted(records) if (r := parse_record(name, text)) is not None]
    moonshots = {**{r["loop"]: (r["prefix"],) for r in parsed if not r["brief"]},
                 **{name: (opening,) for name, opening in EARLY_MOONSHOTS.items()}, **HAND_RUN}
    templated = {r["loop"] for r in parsed if r["all_items"]}
    chains, taken = _job_chains(jobs), set()

    found: list[_Run] = []
    for manifest, doc in sorted(sessions, key=lambda pair: pair[0].get("started") or ""):
        session = _Session(manifest, doc)
        mine = [r for r in parsed if r["session_id"] == session.sid]
        found += _record_runs(session, mine)
        found += _transcript_runs(session, moonshots)
        if (run := _verification_run(session)) is not None:
            found.append(run)
    known = {m.get("session_id") for m, _ in sessions}
    unplaced = sorted(r["name"] for r in parsed if r["session_id"] not in known)

    runs, cycles, job_rows = [], [], []
    for run in found:
        if run.kind == "moonshot" and run.loop in templated:
            run.kind = "templated moonshot"
        row, own, own_jobs = _rows_of(run, chains, taken)
        runs.append(row)
        cycles += own
        job_rows += own_jobs
    runs.sort(key=lambda r: (r["started"] or "", r["run"]))
    order = {r["run"]: n for n, r in enumerate(runs)}
    cycles.sort(key=lambda c: (order[c["run"]], c["cycle"]))
    job_rows.sort(key=lambda j: (order[j["run"]], j["cycle"], j["job"]))

    # A brief named after another loop's, plus a suffix, is one of its streams; so is one whose
    # session was forked from the conversation that planned it.
    briefs = {r["loop"] for r in runs if r["kind"] == "brief"}
    forked = {r["loop"] for r in runs if r["forked_from"]}
    parent = {name: max((p for p in briefs if name.startswith(p + "-")), key=len, default=None) for name in briefs}
    for r in runs:
        r["stream_of"] = parent.get(r["loop"]) if r["kind"] == "brief" else None
        if r["kind"] == "brief" and (r["stream_of"] or r["loop"] in forked):
            r["kind"] = "brief stream"
        r["category"] = KIND_CATEGORY[r["kind"]]
    category = {r["run"]: r["category"] for r in runs}
    for c in cycles:
        c["category"] = category[c["run"]]

    def of(key: str, value: str) -> tuple[list[dict], list[dict]]:
        own = [r for r in runs if r[key] == value]
        names = {r["run"] for r in own}
        return own, [c for c in cycles if c["run"] in names]

    loop_rows = []
    for name in dict.fromkeys(r["loop"] for r in runs):
        own, own_cycles = of("loop", name)
        latest = max((r for r in parsed if r["loop"] == name), key=lambda r: r["started"], default=None)
        items = latest["all_items"] if latest and latest["all_items"] else None
        done = _done_items(own_cycles)
        loop_rows.append({
            "loop": name, "category": own[0]["category"], "kind": own[-1]["kind"], "stream_of": own[-1]["stream_of"],
            "instruction": latest["instruction"] if latest and not latest["brief"] else
                           " / ".join(HAND_RUN[name]) if name in HAND_RUN else EARLY_MOONSHOTS.get(name),
            **_group(own, own_cycles),
            "items": len(items) if items else None, "items_done": len(done & set(items)) if items else None})

    item_rows = []
    for name in sorted(templated):
        own, own_cycles = of("loop", name)
        listed: dict[str, None] = {}
        for r in sorted((r for r in parsed if r["loop"] == name), key=lambda r: r["started"]):
            listed.update(dict.fromkeys(r["all_items"] or []))
        for item in listed:
            tries = [c for c in own_cycles if c["item"] == item]
            kept = [c for c in tries if c["outcome"] == "commit"]
            added = _add(tries)
            item_rows.append({
                "loop": name, "item": item,
                "status": "done" if item in _done_items(tries) else "attempted" if tries else "pending",
                "attempts": len(tries), "runs": list(dict.fromkeys(c["run"] for c in tries)),
                "started": min((c["started"] for c in tries if c["started"]), default=None),
                "committed": kept[0]["ended"] if kept else None,
                "changes": [x for c in kept for x in c["changes"]], "summary": kept[-1]["summary"] if kept else None,
                "commits": sum(c["commits"] for c in tries), "turns": sum(c["turns"] for c in tries), **added,
                "elapsed_ms": sum(c["elapsed_ms"] or 0 for c in tries),
                "peak_context_tokens": max((c["peak_context_tokens"] for c in tries), default=0),
                "proof": "no job" if not added["jobs"] else "failed" if added["jobs_failed"] else
                         "pending" if added["jobs_pending"] else "passed"})

    category_rows = []
    for name in CATEGORIES:
        own, own_cycles = of("category", name)
        if own:
            category_rows.append({"category": name, "loops": len({r["loop"] for r in own}), **_group(own, own_cycles)})
    for c in cycles:  # read for the items done, not published
        c.pop("item_open", None)
    return {
        "schema": SCHEMA,
        "pricing_as_of": pricing.get("as_of"),
        "totals": {"loops": len(loop_rows), **_group(runs, cycles), "jobs_known": len(chains),
                   "runs_from_records": sum(r["source"] == "record" for r in runs),
                   "runs_from_transcripts": sum(r["source"] == "transcript" for r in runs),
                   "records_without_session": unplaced},
        "categories": category_rows,
        "loops": loop_rows,
        "items": item_rows,
        "runs": runs,
        "cycles": cycles,
        "jobs": job_rows,
    }


def failure(error: str) -> dict:
    """What sync.py writes in place of the statistics when computing them failed: no rows, and why."""
    return {"schema": SCHEMA, "error": error}


# --------------------------------------------------------------------------- the page

def _table(header: list[str], rows: list[list]) -> str:
    names = [h.rstrip(">") for h in header]
    rules = ["---:" if h.endswith(">") else "---" for h in header]
    return "\n".join("| " + " | ".join(str(c) for c in row) + " |" for row in [names, rules, *rows])


def _dur(ms: int | float | None) -> str:
    if ms is None:
        return "?"
    minutes = round(ms / 60_000)
    if minutes < 100:
        return f"{ms / 60_000:.1f} min" if minutes < 10 else f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes < 48 * 60 else f"{minutes / 1440:.1f} d"


def _usd(value: float | None) -> str:
    return "?" if value is None else f"${value:,.2f}"


def _cost(row: dict, known: str | None = None) -> str:
    """A row's dollars, saying when model calls with no known price are not in them: a model that is not in
    pricing.json has tokens and no dollars (Codex's, so far), and what is not known is shown as unknown, never as
    nought. `known` is a figure made from the row's dollars (an average, a median), printed when every call has a
    price and `?` otherwise."""
    if not row.get("unpriced_calls"):
        return _usd(row["usd"]) if known is None else known
    if known is not None or not row["usd"]:
        return "?"
    return f"{_usd(row['usd'])}+?"


def _day(ts: str | None) -> str:
    return ts[:16].replace("T", " ") if ts else "?"


def _cell(text: str | None, limit: int = 90) -> str:
    text = _squash(text or "")
    text = text if len(text) <= limit else text[:limit - 1].rstrip() + "…"
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|")


def _per(total: float, count: int) -> str:
    return _usd(total / count) if count else "n/a"


def _period(row: dict) -> str:
    first, last = (row["first"] or "?")[:10], (row["last"] or "?")[:10]
    return first if first == last else f"{first} to {last[5:] if first[:4] == last[:4] else last}"


def _jobs(row: dict) -> str:
    if not row["jobs"]:
        return "0"
    parts = [f"{row[f'jobs_{k}']} {k}" for k in ("passed", "failed", "pending") if row[f"jobs_{k}"]]
    return f"{row['jobs']} ({', '.join(parts)})"


PAGE = """<!-- Generated by llm-dlc/tools/sync.py (loop_stats.py) on every sync. Edit the tool, not this file. -->
# Loop statistics

What the unattended loops cost and produced: every run of [`feature-loop.sh`](../tools/feature-loop.sh) and of the
verification loop, added up by category, loop, run and cycle. [`loops.json`](loops.json) holds the same rows as data,
with every cycle and every verification job a cycle submitted. The [traces overview](README.md) adds up all sessions,
loop or not.

- A **moonshot** repeats a one-line instruction every cycle. A **templated moonshot** puts the next item of a list
  into its instruction each cycle.
- A **brief** is a markdown file the loop works through. A **stream** is one of several loops a brief ran side by
  side, each on its own branch.
- The **verification loop** runs `/run-verification` in a new session whenever proofs are queued. Each session is one run.

## At a glance

{glance}

{by_hand_glance}

## Moonshots

{moonshots}

{by_hand}

{items}

### Every moonshot cycle

Oldest first. A cycle is one turn of the instruction, then the commit, then the compact.

{moonshot_cycles}

## Briefs

A brief's own row is the loop that ran the brief itself: all of it for a brief with one loop, and the merge of the
streams for a brief that ran them. The *with its streams* row adds the streams to it.

{briefs}

## Verification loop

{verification}

## Runs

Every run of `feature-loop.sh`, oldest first. A run with a published record links to it. A run without one (every
run before 2026-11-06) is read from its session's prompts and marked *transcript*.

{runs}

## Reading these numbers

- **Where they come from.** Every figure is added up from the sessions' `metrics.json`, which holds each prompt with
  its time, tokens and cost. A run's record says which session it ran in and when, and so which prompts are its own.
  The page can be rebuilt from the repo, and `sync.py check` fails when it is out of date.
- **Cost** is tokens at the list prices in `llm-dlc/pricing.json`, not what was billed. It leaves out what a
  transcript does not record: the model call that writes a compaction's summary, and Claude Code's side calls.
- **Active** is the time a model call or a tool was running. **Elapsed** is start to end, so it includes waiting for
  background tasks, a machine that hung, and for a run the turns the script adds.
- **Overhead** is what the script's own turns cost: the decision to go on, the status line, the compact command, the
  closing summary and a stream's fork turn. It is included in every cost and shown apart in `loops.json`.
- **A cycle** counts once it starts. *With a commit* counts the cycles that ended in one; a cycle without one stops
  the loop, and its cost still counts.
- **Commits** are those the loop's session made during a cycle's turns. A commit that only names the session, made
  by another while it sat idle (a push's *Record session traces*, a person's approval), is not the cycle's.
- **Jobs** are the verification jobs a cycle submitted: those that name its session and were submitted during it, and
  those a commit of the cycle names. A job that was rerun counts once, with its last result and the compute of every
  attempt. Jobs submitted before 2026-11-15 name their session only when the agent passed it, so older cycles list
  fewer than they submitted.
- **Runs read from transcripts** are split where a person typed a prompt, where 30 minutes passed without a turn, at
  the loop's closing summary, and where the script's count of cycles started over. A cycle a person finished by hand
  after the loop stopped (a typed "Continue") counts up to where the loop left it.
- **By hand.** A loop of kind `moonshot by hand` was typed by a person, so nothing but the person held it to a cycle.
  It is counted with the moonshots and named wherever it is, and `loops.json` gives its kind on every row.
- **Not counted:** prompts a person typed into a loop's session between runs.
{notes}"""


def page(doc: dict) -> str:
    """llm-dlc/traces/loops.md: the tables a person reads, from the same rows as loops.json."""
    if doc.get("error"):
        return ("<!-- Generated by llm-dlc/tools/sync.py (loop_stats.py) on every sync. Edit the tool, not this file. -->\n"
                "# Loop statistics\n\nThe loop statistics could not be computed the last time `sync.py` ran:\n\n"
                f"    {doc['error']}\n\nNothing else is affected. `llm-dlc/tools/loop_stats.py` needs a fix, and the next sync "
                "after it rewrites this page.\n")
    runs, cycles = doc["runs"], doc["cycles"]
    by_run = {r["run"]: r for r in runs}
    loop_rows = {r["loop"]: r for r in doc["loops"]}
    written = lambda r: f"{r['output_tokens']:,}"

    def summed(label: str, r: dict) -> list:
        return [label, r["runs"], r["cycles"], r["cycles_committed"], r["commits"], _jobs(r), _dur(r["busy_ms"]),
                written(r), _cost(r), _cost(r, known=_per(r["usd"], r["cycles_committed"]))]

    glance = _table(["Category", "Loops>", "Runs>", "Cycles>", "With a commit>", "Commits>", "Jobs>", "Active>",
                     "Tokens written>", "Cost>", "Per committed cycle>"],
                    [[r["category"], r["loops"], *summed("", r)[1:]] for r in doc["categories"]]
                    + [["**all**", doc["totals"]["loops"], *summed("", doc["totals"])[1:]]])

    def loop_line(r: dict, label: str | None = None) -> list:
        return [label or f"`{r['loop']}`", r["runs"], r["cycles"], r["cycles_committed"], r["commits"], _jobs(r),
                ", ".join(f"`{m}`" for m in r["models"]) or "?", _period(r), _dur(r["elapsed_ms"]), _dur(r["busy_ms"]),
                _dur(r["median_cycle_busy_ms"]), written(r), _cost(r), _cost(r, known=_usd(r["median_cycle_usd"])),
                _cost(r, known=_per(r["usd"], r["commits"]))]

    def instructions(r: dict) -> str:
        """A moonshot's instruction, or each wording of one a person typed."""
        if r["loop"] in HAND_RUN:
            return f"- `{r['loop']}`, typed by hand, a different wording each cycle:\n" + "\n".join(
                f"  - \"{_cell(text, 400)}\"" for text in HAND_RUN[r["loop"]])
        done = f", {r['items_done']} of {r['items']} items done" if r["items"] else ""
        return f"- `{r['loop']}`{done}: \"{_cell(r['instruction'], 400)}\""

    loop_header = ["Loop", "Runs>", "Cycles>", "With a commit>", "Commits>", "Jobs>", "Model", "When", "Elapsed>",
                   "Active>", "Median cycle>", "Tokens written>", "Cost>", "Median cycle cost>", "Per commit>"]
    moon = [r for r in doc["loops"] if r["category"] == "moonshot"]
    moonshots = (_table(loop_header, [loop_line(r, f"`{r['loop']}` (by hand)" if r["kind"] == BY_HAND else None)
                                      for r in moon]) + "\n\n"
                 + "\n".join(instructions(r) for r in moon)) if moon else "*None yet.*"

    items = []
    for name in dict.fromkeys(i["loop"] for i in doc["items"]):
        rows = [i for i in doc["items"] if i["loop"] == name]
        items.append(
            f"### Items of `{name}`\n\nOne row per item of the list. *Attempts* are the cycles that took the item, and "
            "the figures add them up. *Proof* is what the jobs those cycles submitted came to.\n\n" + _table(
                ["Item", "Status", "Attempts>", "Elapsed>", "Active>", "Model calls>", "Tool calls>", "Failed>",
                 "Tokens written>", "Peak context>", "Cost>", "Jobs>", "Proof", "Proof compute>", "Commit"],
                [[i["item"], i["status"], i["attempts"], _dur(i["elapsed_ms"]) if i["attempts"] else "",
                  _dur(i["busy_ms"]) if i["attempts"] else "", f"{i['api_calls']:,}", f"{i['tool_calls']:,}",
                  i["tool_errors"], written(i), f"{i['peak_context_tokens']:,}", _cost(i) if i["attempts"] else "",
                  _jobs(i), i["proof"] if i["attempts"] else "", f"{i['job_cpu_seconds']:,.0f} CPU s" if i["jobs"] else "",
                  (f"`{i['changes'][-1]}` " if i["changes"] else "") + _cell(i["summary"], 70)] for i in rows]))

    def cycle_line(c: dict) -> list:
        return [f"`{c['run']}`", c["cycle"], c["item"] or "", _day(c["started"]), _dur(c["elapsed_ms"]),
                _dur(c["busy_ms"]) if c["measured"] else "?", f"{c['api_calls']:,}", f"{c['tool_calls']:,}",
                c["tool_errors"], f"{c['output_tokens']:,}", f"{c['peak_context_tokens']:,}",
                _cost(c) if c["measured"] else "?", c["commits"], _jobs(c), _cell(c["summary"], 70) or "*no commit*"]

    hand = [r for r in moon if r["kind"] == BY_HAND]
    names = ", ".join(f"`{r['loop']}`" for r in hand)
    spent = lambda rows: (f"{sum(r['cycles'] for r in rows)} cycles, "
                          + _cost({"usd": sum(r["usd"] for r in rows), "unpriced_calls": sum(r.get("unpriced_calls") or 0 for r in rows)}))
    by_hand_glance = (f"The moonshot row includes {names} ({spent(hand)}), which a person ran by hand before the script "
                      "existed. See the note under [Moonshots](#moonshots).") if hand else ""
    by_hand = ("**Run by hand.** " + names + " is the loop before the loop. On 2026-10-31 a person typed an instruction, "
               "let the session commit, typed `/compact`, and did it again, each time worded for another audience. "
               "`feature-loop.sh` was written that night to do the same unattended, and `features` is its first run. It is "
               "counted here because it is the same cycle, and kept apart by its kind because no script ran it: nothing "
               "capped a cycle, checked for a commit, or compacted for it, and a person chose each instruction after "
               "reading the last result. Its figures are measured the same way as every other row's.") if hand else ""

    moon_cycles = [c for c in cycles if c["category"] == "moonshot"]
    moonshot_cycles = _table(
        ["Run", "Cycle>", "Item", "Started", "Elapsed>", "Active>", "Model calls>", "Tool calls>", "Failed>",
         "Tokens written>", "Peak context>", "Cost>", "Commits>", "Jobs>", "Last commit"],
        [cycle_line(c) for c in moon_cycles]) if moon_cycles else "*None yet.*"

    brief_rows = []
    briefs = [r for r in doc["loops"] if r["category"] == "brief"]
    for r in briefs:
        if r["stream_of"]:
            continue
        streams = [s for s in briefs if s["stream_of"] == r["loop"]]
        brief_rows.append(loop_line(r, f"**`{r['loop']}`**"))
        brief_rows += [loop_line(s, f"&nbsp;&nbsp;stream `{s['loop']}`") for s in streams]
        if streams:
            names = {r["loop"], *(s["loop"] for s in streams)}
            own = [x for x in runs if x["loop"] in names]
            whole = {"loop": r["loop"], **_group(own, [c for c in cycles if by_run[c["run"]]["loop"] in names])}
            brief_rows.append(loop_line(whole, "&nbsp;&nbsp;*with its streams*"))
    brief_rows += [loop_line(s, f"stream `{s['loop']}`") for s in briefs if s["stream_of"] and s["stream_of"] not in loop_rows]

    check = loop_rows.get("verification")
    verification = "*No run yet.*" if not check else (
        f"{check['runs']} runs from {_period(check)}, on {', '.join(f'`{m}`' for m in check['models']) or '?'}: "
        f"{_dur(check['busy_ms'])} active, {check['commits']} commits, {check['output_tokens']:,} tokens written, "
        f"{_usd(check['usd'])} ({_per(check['usd'], check['runs'])} a run). Of the {doc['totals']['jobs_known']} verification "
        f"jobs on record, {len(doc['jobs'])} are tied to the loop cycle that submitted them.")

    def run_line(r: dict) -> list:
        ended = r["reason"] + (f" ({r['outcome']})" if r["outcome"] in ("stopped", "interrupted") and r["reason"] != r["outcome"] else "")
        return [_day(r["started"]), f"[`{r['run']}`]({r['record']})" if r["record"] else f"`{r['run']}`", r["kind"],
                f"`{r['model']}`" if r["model"] else "?", r["cycles"], r["commits"], _dur(r["elapsed_ms"]),
                _dur(r["busy_ms"]) if r["measured"] else "?", _cost(r) if r["measured"] else "?", ended, r["source"]]

    run_table = _table(["Started", "Run", "Kind", "Model", "Cycles>", "Commits>", "Elapsed>", "Active>", "Cost>",
                        "How it ended", "Read from"],
                       [run_line(r) for r in runs if r["category"] != "verification"])
    notes = []
    if unmeasured := [r["run"] for r in runs if not r["measured"]]:
        notes.append("- **Not measured yet:** the session's metrics do not reach these runs, so they count their "
                     "record's commits and no time or cost: " + ", ".join(f"`{n}`" for n in unmeasured) + ".")
    if doc["totals"]["records_without_session"]:
        notes.append("- **Left out:** these records name a session with no trace here: "
                     + ", ".join(f"`{n}`" for n in doc["totals"]["records_without_session"]) + ".")
    if unpriced := [r["run"] for r in runs if r.get("unpriced_calls")]:
        notes.append("- **Cost not known:** these runs made model calls of a model with no price in `llm-dlc/pricing.json` "
                     "(a session Codex carried, so far). Their tokens and time are counted; a cost shown as `?` or "
                     "ending in `+?` leaves those calls out: " + ", ".join(f"`{n}`" for n in unpriced) + ".")
    if typed := [r["run"] for r in runs if r["interjections"]]:
        notes.append("- **Other prompts:** these runs hold prompts that are not the script's, typed into the session "
                     "while the loop ran, and count them as their own: " + ", ".join(f"`{n}`" for n in typed) + ".")
    if zones := [r["run"] for r in runs if not r["zone_known"]]:
        notes.append("- **Clock:** these records give their times in a zone this page cannot place, read as UTC: "
                     + ", ".join(f"`{n}`" for n in zones) + ".")
    text = PAGE.format(glance=glance, moonshots=moonshots, items="\n\n".join(items), moonshot_cycles=moonshot_cycles,
                       by_hand_glance=by_hand_glance, by_hand=by_hand,
                       briefs=_table(loop_header, brief_rows) if brief_rows else "*None yet.*",
                       verification=verification, runs=run_table, notes="\n".join(notes))
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"
