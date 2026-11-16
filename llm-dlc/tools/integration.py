#!/usr/bin/env python3
"""The rolling integration line of a parallel run (llm-dlc/loops/stream-conductor.md, Design 1).

run-streams.sh calls `run` whenever a stream's @- has moved. It works in the run's own workspace,
NAME-integration, which nothing else uses, and never pushes or touches the default workspace's line:

  1. It merges every stream's @- there, with the line's newest passing merge as a parent too, so the
     line is one chain of merges, each known to work.
  2. Generated trace files in conflict are settled by that tree's own `sync.py regenerate`.
  3. Any other conflict stops it, and the script isn't run. Otherwise it runs the brief's
     integration script (the command after `--`, which run-streams.sh wraps in its systemd scope).
     Whatever the script wrote into the tree is dropped afterwards, so the merge holds only the
     streams' work and the regenerated files.
  4. A passing merge is committed on the line, with an `Integration-Line: NAME` trailer and an
     `Integration-Head: STREAM COMMIT` trailer for each stream. A failing merge is left as the
     workspace's working copy, uncommitted, and is abandoned at the next run.

A failure or a conflict is triaged. It is attributed to the streams whose changes since the streams
branched touch the files in conflict, or the files the script's output names (Python tracebacks,
`path:line`, a Java frame's `File.java`). If no file is named, it falls back to the streams that
changed anything since the last passing merge.
  - One stream: that stream is sent a `failure` item saying what to fix.
  - Two or more: an open decision, asked by `integration`, on how their changes meet. Its options
    are each side standing, a rule both adapt to, and the streams settling it themselves. Each side
    is sent a `queued` item: hold back on those files until the decision says how they meet, and go
    on with the rest.
  - None: an open decision, with nothing sent.
The line never decides how two sides meet itself: it can't name a basis, so by Design 3 it queues the
decision. The conductor (step 4) or the user decides it.

A triage is remembered by its result, files and streams, in NAME-integration.json beside the report.
The same failure seen again sends nothing new.

When a merge passes, each open decision the line asked, and no one has answered, is decided as
`settled` by the conductor. That is high confidence, since the script passed on every stream's work
together; it is cheap, since nothing was changed to settle it; and it is left unreviewed. Every stream
that decision held back is sent an `unblocked` item.

The report, llm-dlc/loop-summaries/NAME-integration.md in the default workspace, keeps today's form:
the status bar (streams_status.py) reads its `- Result:` line. Its first word is passed, failed,
conflict, error or unchanged.

Commands:

  integration.py run --name NAME --workspace DIR --report FILE --stream LABEL=WORKSPACE ... -- COMMAND ...
  integration.py line NAME     the newest passing merge on NAME's line, as a change id

The decision record and the inboxes are the default workspace's (decisions.py, inbox.py). Standard
library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import decisions
import inbox

REPO = Path(__file__).resolve().parents[2]
LINE_TRAILER = "Integration-Line"
HEAD_TRAILER = "Integration-Head"
OUTPUT_LINES = 200  # of the script's output, in the report
EXCERPT_LINES = 12  # of it, in an inbox item
SETTLED = "settled"
ASKED_BY = "integration"
TOKEN_RE = re.compile(r"[A-Za-z0-9_./+-]+")


class IntegrationError(Exception):
    pass


def jj(where: Path, *args: str, snapshot: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["jj", *([] if snapshot else ["--ignore-working-copy"]), *args], cwd=where,
                          capture_output=True, text=True)


def must(r: subprocess.CompletedProcess, what: str) -> str:
    if r.returncode != 0:
        raise IntegrationError(f"{what}: {r.stderr.strip() or 'jj failed'}")
    return r.stdout


def short(commit: str) -> str:
    return commit[:12]


# What the repository says

def stream_heads(where: Path, streams: list[tuple[str, str]]) -> dict[str, tuple[str, str]]:
    """Each stream's @-, as (commit id, change id), by its label."""
    out = {}
    for label, ws in streams:
        text = must(jj(where, "log", "--no-graph", "-r", f"{ws}@-", "-T", 'commit_id ++ " " ++ change_id.short(8)'),
                    f"the stream {label}'s workspace {ws}")
        commit, change = text.split()
        out[label] = (commit, change)
    return out


def line_head(where: Path, name: str) -> dict | None:
    """The newest passing merge on NAME's line: its commit, change and stream heads, or None."""
    if not inbox.NAME_RE.match(name):  # so it needs no quoting in the revset
        raise IntegrationError(f"{name!r} is not a brief's name")
    revset = f'latest(heads(description(regex:"(?m)^{LINE_TRAILER}: {name}$")))'
    text = must(jj(where, "log", "--no-graph", "-r", revset, "-T",
                   'commit_id ++ " " ++ change_id.short(8) ++ "\\n" ++ description'), "the integration line")
    if not text.strip():
        return None
    first, _, description = text.partition("\n")
    commit, change = first.split()
    heads = dict(m.groups() for m in re.finditer(rf"^{HEAD_TRAILER}: (\S+) (\S+)$", description, re.M))
    return {"commit": commit, "change": change, "heads": heads}


def conflicted(where: Path) -> list[str]:
    r = jj(where, "resolve", "--list", snapshot=True)
    if r.returncode != 0:
        if "No conflicts" in r.stderr:
            return []
        raise IntegrationError(f"jj resolve --list: {r.stderr.strip()}")
    return [m[1] for m in re.finditer(r"^(.*?)\s{2,}\S.*$", r.stdout, re.M)]


def fork_point(where: Path, commits: list[str]) -> str:
    """Where the streams branched: from each other, and from the default workspace's line if there is one."""
    union = " | ".join(commits)
    for revset in (f"fork_point({union} | default@-)", f"fork_point({union})"):
        r = jj(where, "log", "--no-graph", "-r", revset, "-T", "commit_id")
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    raise IntegrationError("the streams have no common ancestor")


def changed(where: Path, frm: str, to: str) -> set[str]:
    if frm == to:
        return set()
    return set(must(jj(where, "diff", "--name-only", "--from", frm, "--to", to), "jj diff").split("\n")) - {""}


def named_files(output: str, where: Path, candidates: set[str]) -> set[str]:
    """The candidate files the output names: by path (absolute in the workspace, or relative), or by a
    bare file name that only candidates' paths end in."""
    by_name: dict[str, set[str]] = {}
    for c in candidates:
        by_name.setdefault(c.rsplit("/", 1)[-1], set()).add(c)
    prefix, found = f"{where.resolve()}/", set()
    for token in TOKEN_RE.findall(output):
        token = token.rstrip(".,")
        if token.startswith(prefix):
            token = token[len(prefix):]
        token = token.removeprefix("./")
        if token in candidates:
            found.add(token)
        elif "/" not in token and token in by_name:
            found |= by_name[token]
    return found


def excerpt(output: str, files: list[str]) -> str:
    names = {f.rsplit("/", 1)[-1] for f in files}
    lines = output.splitlines()
    picked = [line for line in lines if any(n in line for n in names)] if names else []
    return "\n".join((picked or lines)[-EXCERPT_LINES:])


# The state of the last triage, beside the report

def state_path(report: Path) -> Path:
    return report.with_suffix(".json")


def load_state(report: Path) -> dict:
    try:
        return json.loads(state_path(report).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(report: Path, state: dict) -> None:
    state_path(report).write_text(json.dumps(state, indent=1) + "\n")


# Triage

def listing(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def triage(name: str, how: str, files: list[str], sides: dict[str, list[str]], by: str, heads: dict, detail: str,
           *, code: int | None, report_rel: str, root: Path, stamp: str) -> tuple[str | None, list[str], list[str]]:
    """Record and send what a failing merge calls for. `sides` holds each stream it is attributed to, with
    the files of its own among `files`. Returns the decision (or None), the items sent, and the items that
    couldn't be sent, with why."""
    droot, folder = root / "llm-dlc" / "decisions", root / inbox.FOLDER
    involved = list(sides)
    what = (f"their changes to {'it' if len(files) == 1 else 'them'} conflict when merged" if how == "conflict"
            else f"the integration script fails on the merge of every stream's latest commit (exit {code})")
    shown = listing(files) if files else "no file the output names"
    decision, sent, failed = None, [], []
    commits = [heads[s][1] for s in involved] or [c for _, c in heads.values()]

    def side(s: str) -> str:
        return f"{s} ({', '.join(sides[s])})" if sides[s] else s

    def send(stream: str, kind: str, do: str, decision_ids: list[str]) -> None:
        try:
            sent.append(inbox.send(f"{name}-{stream}", kind, do, detail=detail, decision_ids=decision_ids,
                                   commits=[heads[stream][1]], folder=folder, decisions_root=droot, repo=root,
                                   stamp=stamp))
        except inbox.InboxError as e:
            failed.append(f"{name}-{stream}: {e}")

    if len(involved) == 1:
        s = involved[0]
        why = (f"in {shown}, which only your changes touch" if by == "files"
               else "and no other stream changed anything since the last passing merge")
        fails = "conflicts" if how == "conflict" else f"fails the integration script (exit {code})"
        send(s, "failure", f"The merge of every stream's latest commit {fails} {why}: fix it in your next cycle. "
                           f"The output is in {report_rel}.", [])
        return None, sent, failed
    if involved:
        if how == "conflict":
            question = f"The streams {listing(involved)} both changed {shown}, and {what}: how do they meet?"
        else:
            question = f"The changes of {listing([side(s) for s in involved])} don't work together: {what}. How do they meet?"
        options = []
        for s in involved:
            others = [o for o in involved if o != s]
            options.append({"id": f"{s}-stands", "summary": f"{s}'s side stands, and the others adapt to it",
                            "consequences": f"{listing([side(o) for o in others])} "
                                            f"{'changes its side' if len(others) == 1 else 'change their sides'} to "
                                            f"fit {s}'s; {s} changes nothing"})
        options.append({"id": "rule", "summary": "both sides change to a rule the decision states",
                        "consequences": "each stream changes its side to the stated rule, sent to it as an "
                                        "interface item"})
    else:
        question = f"{what[0].upper() + what[1:]}, and its output names no stream's changes: whose is it?"
        options = [{"id": f"{s}-fixes", "summary": f"{s}'s code is the cause, and {s} fixes it",
                    "consequences": f"{s} is sent a failure item"} for s in heads]
    options.append({"id": SETTLED, "summary": "the streams settle it themselves",
                    "consequences": "nothing is decided here: the next merge of every stream's latest commit that "
                                    "passes closes it, and each side is told it may go on"})
    current = decisions.fold(decisions.read(name, droot))
    line = decisions.conductor_line(name, {"state": "open", "asked": {"by": ASKED_BY, "question": question},
                                           "context": {"commits": commits, "files": files}, "options": options},
                                    current, None, stamp, [])
    decisions.write(name, droot, [line])
    decision = line["id"]
    for s in involved:
        others = [o for o in involved if o != s]
        send(s, "queued", f"Hold back on {shown} until {decision} says how your side and "
                          f"{listing(others)}'s meet: {what}. Go on with the rest of your work meanwhile, and keep "
                          f"your own tests passing. The output is in {report_rel}.", [decision])
    return decision, sent, failed


def settle(name: str, line_change: str, root: Path, stamp: str) -> tuple[list[str], list[str], list[str]]:
    """Decide the line's open questions as settled once a merge of every stream passes, and tell the streams
    they held back that they may go on. Returns the decisions settled, the items sent, and those left (answered
    by the user, for the conductor to apply)."""
    droot, folder = root / "llm-dlc" / "decisions", root / inbox.FOLDER
    current = decisions.fold(decisions.read(name, droot))
    done, sent, left = [], [], []
    for i, d in sorted(current.items()):
        if d["state"] != "open" or d["asked"]["by"] != ASKED_BY:
            continue
        if d.get("answer") or SETTLED not in {o["id"] for o in d["options"]}:
            left.append(i)
            continue
        patch = {"id": i, "state": "decided", "applied": {"commits": d["applied"]["commits"] + [line_change]},
                 "decision": {"option": SETTLED, "by": "conductor",
                              "rationale": f"The integration script passed on the merge of every stream's latest "
                                           f"commit (integration line {line_change}): the disagreement this asked "
                                           f"about no longer shows, so there is nothing left to choose between "
                                           f"the other options.",
                              "confidence": {"level": "high",
                                             "basis": f"the brief's integration script passed at {line_change}"},
                              "recovery": {"class": "cheap",
                                           "undo": "none needed: settling it changed nothing; if the disagreement "
                                                   "comes back, the integration line asks again"}}}
        decisions.write(name, droot, [decisions.conductor_line(name, patch, current, None, stamp, [])])
        done.append(i)
        current = decisions.fold(decisions.read(name, droot))
        for stream in dict.fromkeys(a["stream"] for a in d["applied"]["inbox"]):
            files = d["context"].get("files") or []
            try:
                sent.append(inbox.send(stream, "unblocked",
                                       f"The merge of every stream's latest commit passes now (integration line "
                                       f"{line_change}): go on with {listing(files) if files else 'the work'} "
                                       f"{i} had you hold back on.", decision_ids=[i], commits=[line_change],
                                       folder=folder, decisions_root=droot, repo=root, stamp=stamp))
            except inbox.InboxError as e:
                left.append(f"{stream}: {e}")
    return done, sent, left


# One run

def run(name: str, workspace: Path, streams: list[tuple[str, str]], command: list[str], report: Path, *,
        root: Path, stamp: str | None = None) -> dict:
    """Merge, settle, check, commit or triage, and report. Returns what happened."""
    workspace, stamp = workspace.resolve(), stamp or decisions.now()
    report.parent.mkdir(parents=True, exist_ok=True)
    report_rel = str(report.relative_to(root)) if report.is_relative_to(root) else str(report)
    head = [f"# Integration check of llm-dlc/loops/{name}.md", "", f"- When: {time.strftime('%F %T')}"]
    out = {"result": None, "commit": None, "files": [], "streams": [], "decision": None, "items": [],
           "settled": [], "notes": []}

    def finish(result_line: str, body: list[str] = ()) -> dict:
        tmp = report.with_name(report.name + ".tmp")
        tmp.write_text("\n".join(head + [f"- Result: {result_line}"] + list(body)) + "\n")
        os.replace(tmp, report)
        return out

    try:
        heads = stream_heads(workspace, streams)
        prev = line_head(workspace, name)
    except IntegrationError as e:
        out["result"] = "error"
        return finish(f"error ({e})")
    head.append("- Merged: " + "; ".join(f"{ws}@- {short(heads[label][0])} ({heads[label][1]})"
                                         for label, ws in streams)
                + (f"; and the line's newest passing merge {prev['change']}" if prev else ""))
    head.append(f"- Where: {workspace}")
    if prev and all(prev["heads"].get(label) == heads[label][0] for label in heads):
        out.update(result="unchanged", commit=prev["change"])
        return finish(f"unchanged (every stream's latest commit is already in the line's newest passing merge, "
                      f"{prev['change']})")
    parents = ([prev["commit"]] if prev else []) + [c for c, _ in heads.values()]
    old = jj(workspace, "log", "--no-graph", "-r", "@", "-T", 'if(description, "", commit_id)', snapshot=True)
    r = jj(workspace, "new", *parents, snapshot=True)
    if r.returncode != 0:
        out["result"] = "error"
        return finish(f"error (the merge could not be made: {r.stderr.strip()})")
    if old.returncode == 0 and old.stdout.strip():
        jj(workspace, "abandon", old.stdout.strip())
    try:
        files = conflicted(workspace)
        if files and (workspace / "llm-dlc" / "tools" / "sync.py").exists():
            r = subprocess.run([sys.executable, "llm-dlc/tools/sync.py", "regenerate"], cwd=workspace,
                               capture_output=True, text=True, stdin=subprocess.DEVNULL)
            regenerated = re.findall(r"^regenerated: (.+)$", r.stdout, re.M)
            if regenerated:
                head.append(f"- Regenerated, as generated trace files in conflict: {' '.join(regenerated)}")
            files = conflicted(workspace)
        merged = must(jj(workspace, "log", "--no-graph", "-r", "@", "-T", "commit_id", snapshot=True), "the merge")
    except IntegrationError as e:
        out["result"] = "error"
        return finish(f"error ({e})")

    code, output = None, ""
    if not files:
        with tempfile.TemporaryFile("w+", errors="replace") as f:
            try:
                code = subprocess.run(command, cwd=workspace, stdin=subprocess.DEVNULL, stdout=f,
                                      stderr=subprocess.STDOUT).returncode
            except OSError as e:
                f.write(f"could not run {command[0]}: {e}\n")
                code = 127
            f.seek(0)
            output = f.read()
        jj(workspace, "restore", "--from", merged, snapshot=True)  # drop what the script wrote
    tail = output.splitlines()[-OUTPUT_LINES:]
    output_section = (["", f"## Output, last {OUTPUT_LINES} lines", "", "```", *tail, "```"] if code is not None
                      else [])

    if code == 0:
        message = "\n".join([
            f"integration of {name}: every stream's latest commit, merged and passing", "",
            "Merged " + ", ".join(f"{label} {short(heads[label][0])}" for label in heads)
            + (f", onto the line's previous passing merge {prev['change']}" if prev else "")
            + "; the integration script passed on it. The rolling integration line of a parallel run "
              "(llm-dlc/loops/stream-conductor.md, Design 1): never pushed.", "",
            f"{LINE_TRAILER}: {name}", *(f"{HEAD_TRAILER}: {label} {heads[label][0]}" for label in heads)])
        try:
            must(jj(workspace, "commit", "-m", message, snapshot=True), "jj commit")
            change = must(jj(workspace, "log", "--no-graph", "-r", "@-", "-T", "change_id.short(8)"), "jj log").strip()
        except IntegrationError as e:
            out["result"] = "error"
            return finish(f"error ({e})", output_section)
        out.update(result="passed", commit=change)
        done, sent, left = settle(name, change, root, stamp)
        out.update(settled=done, items=sent, notes=left)
        save_state(report, {"passed": change, "at": stamp})
        body = [f"- Line: `jj new {change}` starts from it, the newest merge known to work."]
        if done:
            body.append(f"- Settled, as the merge passes: {', '.join(done)}"
                        + (f"; sent {', '.join(sent)}" if sent else ""))
        body += [f"- Left for the conductor: {n}" for n in left]
        return finish(f"passed (exit 0), committed on the integration line as {change}", body + output_section)

    # A failing merge: not committed, triaged.
    how = "conflict" if files else "failure"
    try:
        base = fork_point(workspace, [c for c, _ in heads.values()])
        touched = {label: changed(workspace, base, heads[label][0]) for label in heads}
    except IntegrationError as e:
        out["result"] = "error"
        return finish(f"error ({how} not triaged: {e})", output_section)
    by = "files"
    if how == "conflict":
        involved = [label for label in heads if touched[label] & set(files)]
    else:
        files = sorted(named_files(output, workspace, set().union(*touched.values())))
        involved = [label for label in heads if touched[label] & set(files)]
        if not involved:
            try:
                since = {label: changed(workspace, (prev or {}).get("heads", {}).get(label) or base, heads[label][0])
                         for label in heads}
            except IntegrationError:  # a head the line recorded is gone: count from where the streams branched
                since = touched
            involved, by = [label for label in heads if since[label]], "elimination"
            if len(involved) != 1:
                involved = []
    out.update(result="conflict" if how == "conflict" else "failed", files=files, streams=involved)
    body = [f"- Line: {'its newest passing merge is ' + prev['change'] if prev else 'no merge has passed yet'}."]
    if involved:
        body.append("- Streams: " + "; ".join(
            f"{label} (changed {', '.join(sorted(touched[label] & set(files))) or 'files since the last passing merge'})"
            for label in involved) + (", by elimination" if by == "elimination" else ""))
    signature = [how, files, involved]
    state = load_state(report)
    if state.get("signature") == signature:
        out.update(decision=state.get("decision"), items=[])
        body.append(f"- The same {how} as at {state['at']}: "
                    + (f"{state['decision']}, " if state.get("decision") else "")
                    + (f"items {', '.join(state['items'])}" if state.get("items") else "no item")
                    + "; nothing new sent.")
    else:
        detail = (f"Files in conflict: {', '.join(files)}." if how == "conflict"
                  else excerpt(output, files) or "(the script printed nothing)")
        try:
            sides = {label: sorted(touched[label] & set(files)) for label in involved}
            decision, sent, failed = triage(name, how, files, sides, by, heads, detail, code=code,
                                            report_rel=report_rel, root=root, stamp=stamp)
        except (decisions.RecordError, IntegrationError) as e:
            decision, sent, failed = None, [], [f"the decision record: {e}"]
        out.update(decision=decision, items=sent, notes=failed)
        save_state(report, {"signature": signature, "decision": decision, "items": sent, "at": stamp})
        if decision:
            body.append(f"- Decision: {decision}, open: queued for the conductor or the user "
                        f"(llm-dlc/decisions/{name}.md)")
        body.append(f"- Sent: {', '.join(sent)}" if sent else "- Sent: nothing")
        body += [f"- Not sent: {n}" for n in failed]
    if how == "conflict":
        return finish(f"conflict in {len(files)} file{'s' * (len(files) != 1)}, not committed; the script was not "
                      f"run. Files in conflict:", ["", "```", *files, "```", "", *body])
    return finish(f"failed (exit {code}), not committed", body + output_section)


def main(argv: list[str], root: Path | None = None) -> int:
    command = []
    if "--" in argv:
        at = argv.index("--")
        argv, command = argv[:at], argv[at + 1:]
    p = argparse.ArgumentParser(prog="integration.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("run")
    s.add_argument("--name", required=True)
    s.add_argument("--workspace", required=True, type=Path)
    s.add_argument("--report", required=True, type=Path)
    s.add_argument("--stream", action="append", required=True, metavar="LABEL=WORKSPACE")
    s = sub.add_parser("line")
    s.add_argument("name")
    args = p.parse_args(argv)
    root = root or inbox.default_root(REPO)
    if args.cmd == "line":
        found = line_head(root, args.name)
        if not found:
            print(f"integration.py: no merge on {args.name}'s line has passed yet", file=sys.stderr)
            return 1
        print(found["change"])
        return 0
    if not command:
        p.error("run needs the integration script's command after --")
    streams = []
    for spec in args.stream:
        label, _, ws = spec.partition("=")
        if not (inbox.NAME_RE.match(label) and ws):
            p.error(f"--stream {spec}: give LABEL=WORKSPACE")
        streams.append((label, ws))
    out = run(args.name, args.workspace, streams, command, args.report.resolve(), root=root)
    print(f"{out['result']}" + (f": {out['commit']}" if out["commit"] else "")
          + (f"; decision {out['decision']}" if out["decision"] else "")
          + (f"; settled {', '.join(out['settled'])}" if out["settled"] else "")
          + (f"; sent {', '.join(out['items'])}" if out["items"] else "") + f"; see {args.report}")
    return 0 if out["result"] in ("passed", "unchanged", "failed", "conflict") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
