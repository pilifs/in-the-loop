#!/usr/bin/env python3
"""The brief queue: the briefs a watcher runs one after the other, each as a single-agent run (single_run.py), with
a setup phase before it by default (.claude/skills/orchestrate-run/queue.md).

Until 2026-11-23 a watcher kept its queue as prose in its own memory, and the user sent the same message with each
brief: the path, copy it into llm-dlc/loops/, Astra at max effort in the same session, the two prompts, start it
after the current run. The queue is now data any session reads, the message is the defaults below, and the handover
between two briefs is one command.

  llm-dlc/loop-summaries/queue.json   the queue as it stands (gitignored: it changes too often to commit)
  llm-dlc/loops/queue.jsonl           every change to it, one JSON line each, committed with the queue's own commits
  ~/code/scripts/analysis/queue/      the inbox (BRIEF_QUEUE_INBOX overrides it): a brief copied or linked here is
                                      added by the next `inbox` or `next`, in the order the files were put there

Commands (python3 llm-dlc/tools/brief_queue.py COMMAND ...):

  add BRIEF [--name NAME] [--first | --after NAME | --before NAME] [--no-setup] [--generate] [KEY=VALUE ...]
        put a brief on the queue: its copy goes into llm-dlc/loops/ unchanged and is committed. KEY=VALUE overrides a
        default for this brief alone (the keys of DEFAULTS), as does a front-matter block at the brief's top
        (`---`, `queue.KEY: VALUE` lines, `---`). A list of pull requests instead of a brief (a file whose every
        line is a GitHub pull request's link, or any file with --generate) is a generation entry: a brief author
        writes its brief (single_run.py generate) into llm-dlc/loops/NAME-brief.md; once it is landed and names
        every pull request, its copy goes beside the list (~/code/scripts/analysis/NAME-brief.md) and is queued as
        the brief NAME-brief, a brief of the user's like any other: setup phase, notes, domain run. It goes right
        after its list (generatedBrief=next, the default), so each list is generated, set up and proved before the
        next list starts; generatedBrief=end puts it at the end of the queue instead.
  inbox                         add every brief of the inbox that the queue does not have yet
  list | status                 the queue, the run under way, and what `next` would do; `status --json` as data
  move NAME (--first | --after NAME | --before NAME)
  remove NAME                   take a brief off the queue (not one whose run is under way)
  set NAME KEY=VALUE ...        change a brief's settings; `run=RUN` makes the queue follow another run (a fresh
                                session started by hand after a client refused the old one, say)
  defaults [KEY=VALUE ...] [--last-session ID] [--last-generate-session ID]
                                print or change the queue's defaults; --last-session names the session `previous`
                                continues when the queue has started no domain run yet (the run before the queue's),
                                and --last-generate-session the brief author's, which is kept apart from it
  next [--finished]             the handover. It does every step that is due, in order, and records each, so that it
        can be run again after a failure or a crash and carries on where it stopped: bring the inbox in; for a list
        of pull requests at the head, start its generation run, and when that has finished, land it, check that the
        brief accounts for every pull request, put its copy beside the list, queue that copy (next or at the end) and
        checkpoint develop; for the brief at the head, move the workspace onto the line and start its setup run; when that has finished, land it, put its
        notes into both copies of the brief and commit; move the workspace onto the line again and start the domain
        run; when that has finished, land it, checkpoint develop, clear what is safe to clear, and go on to the next
        brief. A run that has stopped is taken as finished only with --finished: one stopped to wait on its jobs is
        continued with `single_run.py jobs` and `start`, not handed over. It never promotes `main` and never runs the
        default tests: both are the user's to decide, and it says so when a brief is done.
  hold [--reason TEXT]          hold the queue: `next` still lands, checkpoints and clears what has finished, but
                                starts no run (no generation, setup or domain run) until `resume`; for a pause
                                between briefs, such as work by hand on the code the next run will start from
  resume                        end a hold: the next `next` starts what is due. A brief with holdAfter=yes holds the
                                queue itself once it is done, so that the briefs before it run on and it stops after
  report [--json]               each brief with its runs, cycles, landing and state
  rules BRIEF ...               what each written brief shows of the four rules a brief author is given for each case
                                (llm-dlc/loops/brief-generation-template.md): the cases with a `Variation` row and
                                those without, the `Remaining defect` rows, and the cases whose words leave an order
                                open. A count, which `next` also gives for a generated brief when it queues it: it
                                refuses nothing, and whether a row keeps its rule takes reading the case

Standard library only.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import conductor
import landing
import run_common
import single_run

REPO = Path(__file__).resolve().parents[2]
QUEUE = "llm-dlc/loop-summaries/queue.json"
LOG = "llm-dlc/loops/queue.jsonl"
LOOPS = "llm-dlc/loops"
PROMPT_TEMPLATE = "llm-dlc/loops/domain-prompt-{}.md"  # a template's two texts, as the setup agent's template has
# What the user asked for with each brief from 2026-11-19 to 2026-11-23: an Opus 5.5 setup phase first (from
# 2026-11-22), then Codex Astra 6.2 at max effort, continuing the session of the domain run before it, in the
# workspace the domain runs share, with no limit on cycles and the two "aspirational" texts. From 2026-11-25 a list
# of pull requests has a generation phase before those: Codex Astra 6.2 at ultra effort writes the brief, in a
# session of its own that every generation continues (never the domain runs' session), compacting at 600k tokens.
DEFAULTS = {
    "generate": "none",                # the brief author's model for a list of pull requests (set by `add`), or none
    "generateClient": single_run.GENERATE_CLIENT,
    "generateEffort": single_run.GENERATE_EFFORT,
    "generateSession": "previous",     # previous (the last generation run's session), new, or a session id
    "generateCompactAt": single_run.GENERATE_COMPACT,
    # Where a generated brief is queued: `next`, right after its list, so that one list is generated, set up and
    # proved before the next list is generated (the user, 2026-11-25: a run that executes the earlier entries first
    # can learn from them); or `end`, the end of the queue, as every generated brief was queued until then.
    "generatedBrief": "next",
    "setup": single_run.SETUP_MODEL,   # the setup agent's model, or `none` for no setup phase
    "setupEffort": single_run.SETUP_EFFORT,
    "client": "codex",
    "model": "gpt-6.2-astra",
    "effort": "max",
    "session": "previous",             # previous (the last domain run's session), new, or a session id
    "workspace": "foundation-domain-streams",
    # yes: when this brief is done (landed, checkpointed, cleared), the queue holds itself (`hold`) before the next
    # one starts, for a person to look at what it did (the user, 2026-11-27, after an architecture refactor).
    "holdAfter": "no",
    "memory": "20G",
    "cycles": "0",
    "prompt": "aspirational",          # PROMPT_TEMPLATE's name
}
STEPS_GENERATE = ("generate-start", "generate-land", "brief")  # then the brief is queued (generatedBrief)
STEPS_SETUP = ("setup-start", "setup-land", "notes")
# A pull request as a list of them names it: a GitHub URL, which `add` reads to tell a list from a brief and the
# `brief` step to check that the brief accounts for each one.
PULL = re.compile(r"https?://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)")
STEPS_DOMAIN = ("domain-start", "domain-land", "checkpoint", "cleanup")
ORDER = ("first", "after", "before")


class Problem(Exception):
    pass


def inbox() -> Path:
    return Path(os.environ.get("BRIEF_QUEUE_INBOX") or "~/code/scripts/analysis/queue").expanduser()


def shown(path: Path) -> str:
    """A path as a person writes it: under the home folder with `~`."""
    try:
        return "~/" + str(path.resolve().relative_to(Path.home().resolve()))
    except ValueError:
        return str(path)


def now() -> str:
    return conductor.now()


@contextlib.contextmanager
def locked(root: Path):
    """The queue, read and written under one lock: two sessions changing it at once would lose a change."""
    path = root / QUEUE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        data.setdefault("defaults", {})
        data.setdefault("entries", [])
        yield data
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1) + "\n")
        os.replace(tmp, path)


def read(root: Path) -> dict:
    try:
        data = json.loads((root / QUEUE).read_text())
    except (OSError, ValueError):
        data = {}
    data.setdefault("defaults", {})
    data.setdefault("entries", [])
    return data


def who() -> str:
    """Who changed the queue, for its log: a person at a terminal, or the session whose shell ran the command, named
    by the id its client gives it (sessions are published under those ids with their logs)."""
    if single_run.person_at_terminal():
        return "a person, at their terminal"
    if os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return f"Claude Code session {os.environ['CLAUDE_CODE_SESSION_ID']}"
    if os.environ.get("CODEX_THREAD_ID"):
        return f"Codex thread {os.environ['CODEX_THREAD_ID']}"
    return "a session"


def inbox_briefs(folder: Path) -> list[Path]:
    """The inbox's briefs in the order they were put there: by the time of the file itself (a link's own time, not
    its target's), then by name. Until 2026-11-24 they went by name alone, and a later brief whose name sorted first
    jumped ahead."""
    return sorted(folder.glob("*.md"), key=lambda p: (p.lstat().st_mtime, p.name))


def log(root: Path, action: str, name: str | None, **fields) -> None:
    path = root / LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({"time": now(), "action": action, **({"name": name} if name else {}), "by": who(), **fields}) + "\n")


def changed(root: Path, paths: list[str]) -> list[str]:
    """Which of these files the working copy has changed."""
    return [p for p in paths if run_common.jj(root, "diff", "-r", "@", "--name-only", "--", p).stdout.strip()]


def commit(root: Path, paths: list[str], title: str, body: str) -> None:
    """Commit these files alone, as CLAUDE.md says (`sync.py commit --only`); a failure that left them uncommitted
    stops the step. Files that did not change are left out."""
    paths = changed(root, paths)
    if not paths:
        return
    r = subprocess.run([sys.executable, str(root / "llm-dlc/tools/sync.py"), "commit", "--only", *paths, "-m", title,
                        "-m", body], cwd=root, capture_output=True, text=True)
    left = run_common.jj(root, "diff", "-r", "@", "--name-only", "--", *paths).stdout.split()
    if left:
        raise Problem(f"could not commit {', '.join(left)}: {(r.stderr or r.stdout).strip()[-600:]}")


def checkpoint(root: Path) -> dict:
    """Put the line's last commit on develop (sync.py checkpoint): unattended, as the user decided on 2026-11-21."""
    r = subprocess.run([sys.executable, str(root / "llm-dlc/tools/sync.py"), "checkpoint", "--rev", "@-"], cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise Problem(f"the develop checkpoint was refused (a refusal is reported, not worked round): "
                      f"{(r.stderr or r.stdout).strip()[-800:]}")
    return {"checkpoint": (r.stdout.strip().splitlines() or ["done"])[-1]}


def pruned(root: Path) -> dict | None:
    """What the pipeline's own prune removed and what it kept, with the reason for each (`pipeline.py prune --json`),
    or None when it could not be asked."""
    r = subprocess.run([sys.executable, str(root / "jobs/pipeline.py"), "prune", "--json"],
                       cwd=root, capture_output=True, text=True)
    try:
        return json.loads(r.stdout) if r.returncode == 0 else None
    except ValueError:
        return None


def cleanup(root: Path) -> dict:
    """What is safe to clear between two briefs: the work folders the runner keeps for jobs that did not pass. The
    pipeline decides which, by one rule (`pipeline.py prune`): the job's result is collected, and the original
    sealed from that very attempt's work folder is verified in the archive. Until 2026-11-27 this function had a
    rule of its own, that every original of the *job* was verified, which says nothing of a later attempt whose
    capture failed. Nothing else is touched."""
    report = pruned(root)
    if report is None:
        return {"cleared": 0, "freedGB": 0.0, "keptNotYetSealed": 0, "problem": "the pipeline's prune could not be asked"}
    return {"cleared": len(report["removed"]), "freedGB": round(report["bytes"] / 2**30, 2),
            "keptNotYetSealed": len(report["kept"])}


def front_matter(text: str) -> dict:
    """A brief's own settings: `queue.KEY: VALUE` lines in a `---` block at its very top."""
    m = re.match(r"---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        k = re.match(r"\s*queue\.([A-Za-z]+)\s*:\s*(.*?)\s*$", line)
        if k:
            out[k.group(1)] = k.group(2)
    return out


def settings(pairs: list[str]) -> dict:
    out = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise Problem(f"a setting is KEY=VALUE: {pair!r}")
        out[key.strip()] = value.strip()
    return out


def checked(over: dict, allow_run: bool = False) -> dict:
    keys = set(DEFAULTS) | ({"run"} if allow_run else set())
    unknown = sorted(set(over) - keys)
    if unknown:
        raise Problem(f"unknown setting(s) {', '.join(unknown)}: the keys are {', '.join(sorted(keys))}")
    if "cycles" in over and not str(over["cycles"]).isdigit():
        raise Problem("cycles is a count, 0 for no limit")
    if "holdAfter" in over and over["holdAfter"] not in ("yes", "no"):
        raise Problem("holdAfter is yes (hold the queue once this brief is done) or no")
    if "generatedBrief" in over and over["generatedBrief"] not in ("next", "end"):
        raise Problem("generatedBrief is next (right after its list) or end (the end of the queue)")
    return over


def effective(data: dict, entry: dict) -> dict:
    return {**DEFAULTS, **data["defaults"], **entry.get("settings", {})}


def name_for(path: Path, taken: set[str]) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    stem = re.sub(r"-brief$", "", stem)[:40].strip("-") or "brief"
    name, n = stem, 2
    while name in taken:
        name, n = f"{stem}-{n}", n + 1
    return name


def placed(entries: list[dict], entry: dict, where: str | None, other: str | None) -> None:
    if where is None:
        entries.append(entry)
        return
    if where == "first":
        at = next((i for i, e in enumerate(entries) if e["state"] == "queued"), len(entries))
        entries.insert(at, entry)
        return
    i = next((i for i, e in enumerate(entries) if e["name"] == other), None)
    if i is None:
        raise Problem(f"no brief {other} on the queue")
    entries.insert(i + 1 if where == "after" else i, entry)


def position(a: argparse.Namespace) -> tuple[str | None, str | None]:
    if getattr(a, "first", False):
        return "first", None
    if getattr(a, "after", None):
        return "after", a.after
    if getattr(a, "before", None):
        return "before", a.before
    return None, None


def pull_requests(text: str) -> list[str]:
    """The pull requests a text names, as owner/repo#number, in order and each once."""
    out = []
    for owner, repo, number in PULL.findall(text):
        key = f"{owner}/{repo}#{number}"
        if key.lower() not in [k.lower() for k in out]:
            out.append(key)
    return out


# The four rules for each case that the generation template gives a brief author (VF-075), as far as a written brief
# shows them to a count: the two roles the rules name for a claim row, and the words that leave an order open. The
# count is for whoever compares the brief, and is never a verdict: whether a `Variation` row changes one input, and
# whether an order may stay open, takes reading the case.
VARIATION, REMAINING_DEFECT = "Variation", "Remaining defect"
CLAIM_ROW = re.compile(r"^\|[^|\n]*?\.\d+\s*·\s*([^|\n]+?)\s*\|", re.M)  # `| ID.N · Role |`, the handoff's format
ORDER_OPEN = re.compile(r"\b(?:either|any|no particular|arbitrary) order\b|\bas (?:a |an unordered )?sets?\b"
                        r"|\border[- ]insensitive\b|\b(?:regardless|irrespective) of (?:the |their )?order\b", re.I)


def case_rules(text: str) -> dict:
    """What a brief shows of the four case rules. Its cases are the sections with claim rows in the handoff's format:
    how many have a `Variation` row and which have none, how many `Remaining defect` rows there are, and which cases
    have words that leave an order open."""
    cases, variation, remaining, without, order_open = 0, 0, 0, [], []
    for section in re.split(r"^## ", text, flags=re.M)[1:]:
        roles = [role.lower() for role in CLAIM_ROW.findall(section)]
        if not roles:
            continue
        cases += 1
        name = re.split(r" [·—] ", section.splitlines()[0], maxsplit=1)[0].strip()
        if any(VARIATION.lower() in role for role in roles):
            variation += 1
        else:
            without.append(name)
        remaining += sum(REMAINING_DEFECT.lower() in role for role in roles)
        if ORDER_OPEN.search(section):
            order_open.append(name)
    return {"cases": cases, "variation": variation, "withoutVariation": without, "remainingDefect": remaining,
            "orderLeftOpen": order_open}


def rules_note(rules: dict) -> str:
    """The count of `case_rules` in a sentence, for a person."""
    if not rules["cases"]:
        return ("no section of it has claim rows in the handoff's format (`| ID.N · Role |`), so the four case rules "
                "could not be counted")

    def some(n: int, what: str) -> str:
        return f"{n} {what}" + ("" if n == 1 else "s")

    def named(names: list[str]) -> str:
        return ", ".join(names[:8]) + (f" and {len(names) - 8} more" if len(names) > 8 else "")
    note = f"a `{VARIATION}` row in {rules['variation']} of its {some(rules['cases'], 'case')}"
    if rules["withoutVariation"]:
        note += f" (none in {named(rules['withoutVariation'])})"
    note += f", {some(rules['remainingDefect'], f'`{REMAINING_DEFECT}` row')}"
    if rules["orderLeftOpen"]:
        note += (f", and words that leave an order open in {some(len(rules['orderLeftOpen']), 'case')} "
                 f"({named(rules['orderLeftOpen'])}), which is right only where a contract leaves the order unspecified")
    return note


# A line of a list of pull requests: the URL alone, or as a Markdown link, bulleted, numbered or bare.
PULL_LINE = re.compile(r"\s*(?:[-*+]|\d+[.)])?\s*(?:\[[^\]]*\]\(\s*<?|<)?" + PULL.pattern + r"[^\s)>]*>?\s*\)?\s*")


def is_pull_request_list(text: str) -> bool:
    """A list of pull requests, not a brief: every line with words on it is a pull request's link (a heading
    aside). A brief that mentions one in a sentence is a brief."""
    lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    return bool(lines) and all(PULL_LINE.fullmatch(l) for l in lines)


def make_entry(root: Path, data: dict, source: Path, name: str | None = None, where: str | None = None,
               other: str | None = None, over: dict | None = None) -> dict:
    """A brief's entry, or a list of pull requests' entry, put on the queue DATA (read under its lock): the file's
    copy is written into llm-dlc/loops/, and the caller logs the entry and commits the copy."""
    source = source.expanduser().resolve()
    if not source.is_file():
        raise Problem(f"no brief at {source}")
    text = source.read_text()
    over = {**front_matter(text), **(over or {})}
    if over.get("generate") in (None, "auto") and is_pull_request_list(text):
        over["generate"] = single_run.GENERATE_MODEL
    elif over.get("generate") == "auto":
        over.pop("generate")
    checked(over)
    generating = over.get("generate", "none") != "none"
    if generating and not pull_requests(text):
        raise Problem(f"{shown(source)} names no GitHub pull request (https://github.com/OWNER/REPO/pull/N): a "
                      f"generation phase writes a brief from a list of them")
    copy = f"{LOOPS}/{source.name}"
    try:
        inside = source.relative_to(root.resolve())
    except ValueError:
        inside = None
    for e in data["entries"]:
        if Path(e["source"]).expanduser().resolve() == source and e["state"] != "removed":
            raise Problem(f"{shown(source)} is on the queue already, as {e['name']}")
    taken = {e["name"] for e in data["entries"]}
    name = name or name_for(source, taken)
    if name in taken:
        raise Problem(f"a brief named {name} is on the queue already")
    single_run.Run(root, name + "-setup")  # the name must make valid run names
    extra = {}
    if generating:
        try:
            single_run.Run(root, name + "-generate")
            single_run.Run(root, name + "-brief-setup")
        except single_run.Problem:
            raise Problem(f"{name} is too long for the names of its runs ({name}-brief-setup): give a shorter --name")
        # The brief the author writes, in the checkout, and its copy beside the list, which is queued as a brief of
        # the user's once it is written: its setup notes go there. Neither may exist yet.
        written, beside = f"{LOOPS}/{name}-brief.md", source.parent / f"{name}-brief.md"
        for path in (root / written, beside):
            if path.exists():
                raise Problem(f"{shown(path)} exists: the brief generated from {shown(source)} would overwrite it. "
                              f"Give another --name")
        extra = {"brief": written, "beside": shown(beside), "pullRequests": pull_requests(text)}
    target = root / copy
    if inside is None:
        if target.exists() and target.read_text() != text:
            raise Problem(f"{copy} exists and differs from {shown(source)}: name the brief's file differently")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    else:
        copy = str(inside)
    entry = {"name": name, "source": shown(source), "copy": copy, "settings": over, "state": "queued", "done": [],
             "runs": {}, "added": now(), **extra}
    placed(data["entries"], entry, where, other)
    return entry


def queued(root: Path, entry: dict, where: str | None = None, other: str | None = None, why: str = "") -> None:
    """An entry just made, logged and its copy committed."""
    at = "at the head" if where == "first" else f"{where} {other}" if where else "at the end"
    over = entry["settings"]
    log(root, "add", entry["name"], source=entry["source"], copy=entry["copy"], settings=over,
        **({"position": where, "other": other} if where else {}),
        **({"brief": entry["brief"], "pullRequests": len(entry["pullRequests"])} if entry.get("brief") else {}),
        **({"generatedBy": entry["generatedBy"]} if entry.get("generatedBy") else {}))
    if entry.get("brief"):
        commit(root, [entry["copy"], LOG],
               f"Queue a brief to be generated from {len(entry['pullRequests'])} pull requests: {entry['name']}",
               f"The list of pull requests {entry['source']} is copied unchanged to {entry['copy']} and put on the brief "
               f"queue (llm-dlc/tools/brief_queue.py), {at}. A brief author ({over['generate']}) writes its brief into "
               f"{entry['brief']}, and that brief is then queued "
               + ("right after the list" if over.get("generatedBrief", DEFAULTS["generatedBrief"]) == "next"
                  else "at the end")
               + ", with a setup phase and a domain run as any other.")
    else:
        commit(root, [entry["copy"], LOG], f"Queue the brief {entry['name']}",
               f"The brief {entry['source']} is copied unchanged to {entry['copy']} and put on the brief queue "
               f"(llm-dlc/tools/brief_queue.py), {at}" + (f", with its own settings {json.dumps(over)}" if over else "")
               + (f". {why}" if why else "") + ".")


def add(root: Path, source: Path, name: str | None = None, where: str | None = None, other: str | None = None,
        over: dict | None = None) -> dict:
    with locked(root) as data:
        entry = make_entry(root, data, source, name, where, other, over)
    queued(root, entry, where, other)
    return entry


def take_inbox(root: Path) -> list[str]:
    folder = inbox()
    if not folder.is_dir():
        return []
    known = {Path(e["source"]).expanduser().resolve() for e in read(root)["entries"] if e["state"] != "removed"}
    added = []
    for path in inbox_briefs(folder):
        if path.resolve() not in known:
            added.append(add(root, path)["name"])
    return added


def run_tool(root: Path, *args: str) -> dict:
    """A single_run.py command, in this process: what it printed, as data, or the problem it named."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = single_run.main([str(a) for a in args], root=root)
    if status != 0:
        raise Problem(f"single_run.py {' '.join(map(str, args[:2]))}: {(err.getvalue() or out.getvalue()).strip()}")
    try:
        return json.loads(out.getvalue())
    except ValueError:
        return {"output": out.getvalue().strip()}


def onto_line(root: Path, workspace: str) -> str:
    """landing.onto_line, with its refusal as this tool's."""
    try:
        return landing.onto_line(root, workspace)
    except run_common.Problem as e:
        raise Problem(str(e))


def prompt_files(root: Path, entry: dict, s: dict) -> tuple[Path, Path]:
    template = root / PROMPT_TEMPLATE.format(s["prompt"])
    try:
        first, cont = single_run.setup_texts(template.read_text(), entry["source"], "")
    except OSError:
        raise Problem(f"no prompt template {template.relative_to(root)}")
    folder = Path.home() / ".cache" / "in-the-loop" / "prompts"
    folder.mkdir(parents=True, exist_ok=True)
    paths = folder / f"{entry['name']}-prompt.txt", folder / f"{entry['name']}-continue.txt"
    paths[0].write_text(first)
    paths[1].write_text(cont)
    return paths


def run_state(root: Path, name: str) -> str:
    run = single_run.Run(root, name)
    data = run.read()
    if not data.get("session"):
        return "none"
    return "running" if run.running() else "stopped"


def step(root: Path, data: dict, entry: dict, s: dict, name: str, finished: bool) -> dict | None:
    """Do one step. None means it is done; a dict means stop here (a run started, or one is under way or stopped)."""
    if name in ("generate-start", "setup-start", "domain-start"):
        kind = name.split("-")[0]
        run = entry["runs"].get(kind) or (entry["name"] if kind == "domain" else f"{entry['name']}-{kind}")
        state = run_state(root, run)
        if state != "none":  # started by an earlier `next` that was cut off before it recorded the step
            entry["runs"][kind] = run
            return None
        moved = onto_line(root, s["workspace"])
        common = ["--workspace", s["workspace"], "--memory", s["memory"], "--cycles", s["cycles"]]
        if kind == "generate":
            # The brief author's own session, which every generation continues: never the domain runs'.
            session = (data.get("lastGenerateSession") if s["generateSession"] == "previous" else None
                       if s["generateSession"] == "new" else s["generateSession"])
            out = run_tool(root, "generate", run, "--input", entry["copy"], "--output", entry["brief"],
                           "--client", s["generateClient"], "--model", s["generate"], "--effort", s["generateEffort"],
                           "--compact-at", s["generateCompactAt"], *common, *(["--session", session] if session else []))
            data["lastGenerateSession"] = out.get("session") or session
        elif kind == "setup":
            out = run_tool(root, "setup", run, "--brief", entry["copy"], "--model", s["setup"], "--effort", s["setupEffort"], *common)
        else:
            first, cont = prompt_files(root, entry, s)
            session = data.get("lastSession") if s["session"] == "previous" else None if s["session"] == "new" else s["session"]
            out = run_tool(root, "start", run, "--prompt-file", first, "--continue-file", cont, "--brief", entry["copy"],
                           "--client", s["client"], "--model", s["model"], "--effort", s["effort"], *common,
                           *(["--session", session] if session else []))
            data["lastSession"] = out.get("session") or session
        entry["runs"][kind] = run
        entry["state"] = kind
        return {"started": run, "workspace": moved, "session": out.get("session"), "model": out.get("model"),
                "next": f"watch it (`single_run.py wait {run}` as a background task); when it has finished, "
                        f"`brief_queue.py next --finished`"}
    if name in ("generate-land", "setup-land", "domain-land"):
        run = entry["runs"][name.split("-")[0]]
        state = run_state(root, run)
        if state == "running":
            return {"underWay": run, "next": f"`single_run.py wait {run}`: nothing to hand over yet"}
        if not finished:
            return {"stopped": run, "next": f"if {run} has finished, `brief_queue.py next --finished`; if it only waits on "
                                            f"its jobs, `single_run.py jobs {run}` and then `single_run.py start {run}`"}
        landed = single_run.Run(root, run).read().get("landed")
        if not landed and single_run.Run(root, run).read().get("workspace"):
            # The watcher's verdicts on the run, and the queue's log, are committed first: a landing that needs a
            # merge refuses while the default workspace has uncommitted files.
            mine = [f"llm-dlc/decisions/single-{run}.jsonl", f"llm-dlc/decisions/single-{run}.md", LOG]
            commit(root, mine, f"Record the watcher's decisions on {run}",
                   f"The watcher's verdicts on the single-agent run {run} (llm-dlc/decisions/single-{run}.jsonl), committed "
                   f"before the run lands, with the brief queue's log.")
            out = run_tool(root, "land", run)
            entry.setdefault("landed", {})[run] = out.get("commit") or out.get("landed")
        return None
    if name == "brief":
        return written_brief(root, data, entry)
    if name == "notes":
        run = entry["runs"]["setup"]
        source = str(Path(entry["source"]).expanduser())
        out = run_tool(root, "notes", run, "--to", source)
        log(root, "notes", entry["name"], changed=out.get("changed", []))
        commit(root, [entry["copy"], LOG], f"Put the setup notes of {entry['name']} into its brief",
               f"The setup run {run} ended its record with a 'Setup Agent Notes' section, and brief_queue.py put it into "
               f"{entry['copy']} and {entry['source']}, for the domain agent.")
        return None
    if name == "checkpoint":
        entry["checkpoint"] = checkpoint(root)["checkpoint"]
        return None
    if name == "cleanup":
        entry["cleanup"] = cleanup(root)
        return None
    raise Problem(f"no step {name}")


def brief_place(s: dict, entry: dict) -> tuple[str | None, str | None]:
    """Where a list's generated brief is queued, as `placed` takes it: right after the list (generatedBrief=next), so
    that it is set up and proved before the next list starts, or at the end of the queue (generatedBrief=end)."""
    return ("after", entry["name"]) if s["generatedBrief"] == "next" else (None, None)


def written_brief(root: Path, data: dict, entry: dict) -> None:
    """The generated brief, landed: it is there, it is a brief, and it accounts for every pull request of the list.
    Its copy then goes beside the list, and that copy is queued as a brief of the user's, right after the list or at
    the end (generatedBrief), with the list's own settings but the generation's: its setup notes go there, and from
    there on nothing differs."""
    brief = root / entry["brief"]
    run = entry["runs"].get("generate")

    def again(why: str) -> Problem:
        # The run is continued and lands again: its next commits are not on the line yet.
        if "generate-land" in entry["done"]:
            entry["done"].remove("generate-land")
        if run:
            single_run.Run(root, run).update(landed=None)
        return Problem(f"{why}: continue the generation run (`single_run.py generate {run}`), and when it has finished, "
                       f"`brief_queue.py next --finished` lands it again and checks the brief")
    if not brief.is_file():
        raise again(f"the generation run {run} landed no brief at {entry['brief']}")
    text = brief.read_text()
    if not text.lstrip().startswith("# "):
        raise again(f"{entry['brief']} does not start with a title (`# ...`), as the handoff's format does")
    named = {k.lower() for k in pull_requests(text)}
    missing = [k for k in entry.get("pullRequests") or [] if k.lower() not in named]
    if missing:
        raise again(f"{entry['brief']} does not name {len(missing)} of the list's pull requests by URL "
                    f"({', '.join(missing[:5])}{'…' if len(missing) > 5 else ''})")
    beside = Path(entry["beside"]).expanduser()
    if beside.exists() and beside.read_text() != text:
        raise Problem(f"{entry['beside']} exists and differs from the generated brief: move it away, then run `next` again")
    beside.write_text(text)
    # What the brief shows of the four case rules is counted and said, and refuses nothing: a person compares it.
    entry["caseRules"] = case_rules(text)
    log(root, "brief", entry["name"], brief=entry["brief"], copy=entry["beside"],
        pullRequests=len(entry.get("pullRequests") or []), caseRules=entry["caseRules"])
    # The list's own settings, but the generation's; and a brief, whatever it looks like (one that is only links
    # and headings would otherwise be taken for another list).
    own = {**{k: v for k, v in entry.get("settings", {}).items() if not k.startswith("generate")}, "generate": "none"}
    where, other = brief_place(effective(data, entry), entry)
    made = make_entry(root, data, beside, f"{entry['name']}-brief", where, other, own)
    made["generatedBy"] = entry["name"]
    entry["queued"] = made["name"]
    entry["queuedAt"] = "next" if where else "end"
    queued(root, made, where, other,
           why=f"It was written by the generation run {run} from the pull requests of {entry['source']}")
    return None


def steps_of(s: dict) -> tuple[str, ...]:
    """A list of pull requests is done once its brief is written, landed, checked and queued (and develop has it);
    a brief has its setup phase, if any, and its domain run."""
    if s["generate"] != "none":
        return STEPS_GENERATE + ("checkpoint",)
    return (STEPS_SETUP if s["setup"] != "none" else ()) + STEPS_DOMAIN


START_STEPS = ("generate-start", "setup-start", "domain-start")


def cmd_next(root: Path, finished: bool) -> dict:
    report = {"inbox": take_inbox(root), "done": [], "steps": []}
    while True:
        with locked(root) as data:
            entry = next((e for e in data["entries"] if e["state"] not in ("done", "removed")), None)
            if entry is None:
                report["next"] = "the queue is empty: nothing to start"
                break
            s = effective(data, entry)
            todo = [n for n in steps_of(s) if n not in entry["done"]]
            stop = None
            for name in todo:
                if name in START_STEPS and data.get("hold"):
                    # Held: what had finished is landed, checkpointed and cleared above; nothing new starts.
                    stop = "held"
                    held = {"brief": entry["name"], "heldAt": name, "hold": data["hold"]}
                    break
                try:
                    stop = step(root, data, entry, s, name, finished)
                except Problem as e:
                    entry["problem"] = f"{name}: {e}"
                    report.update(brief=entry["name"], failedAt=name, problem=str(e),
                                  next="fix what it names, then run `brief_queue.py next` again: it carries on from this step")
                    stop = "failed"
                    break
                if stop is not None and name in ("generate-start", "setup-start", "domain-start"):
                    entry["done"].append(name)  # the start is the step; the run is what comes after it
                    entry.pop("problem", None)
                if stop is not None:
                    break
                entry["done"].append(name)
                entry.pop("problem", None)
                report["steps"].append(f"{entry['name']}: {name}")
                finished = finished and name not in ("generate-land", "setup-land")  # --finished speaks for the run that had stopped
            name = entry["name"]
            if stop is None:
                entry["state"] = "done"
                entry["ended"] = now()
                report["done"].append(name)
                if s.get("holdAfter") == "yes" and not data.get("hold"):
                    data["hold"] = {"since": now(), "by": f"the queue, after {name} (holdAfter=yes)",
                                    "reason": f"{name} is done: a person looks at it before the next brief starts"}
                    report["heldAfter"] = name
                made = entry.get("queued")
                made_at = "right after it" if entry.get("queuedAt") == "next" else "at the end"
                rules = entry.get("caseRules")
        if stop == "failed":
            log(root, "failed", name, step=report["failedAt"], problem=report["problem"])
            break
        if stop == "held":
            report.update(**held, next=f"the queue is held (since {held['hold']['since']}"
                                        + (f": {held['hold']['reason']}" if held["hold"].get("reason") else "")
                                        + f"): {held['heldAt']} of {name} waits for `brief_queue.py resume`")
            log(root, "held", name, step=held["heldAt"])
            break
        if stop is None:
            log(root, "done", name)
            if made:
                report.setdefault("queued", []).append(made)
                report.setdefault("forTheUser", []).append(
                    f"{name}'s brief is written and queued {made_at} as {made}; it is on develop: review it whenever "
                    f"you like, before its setup phase starts or while it runs")
                if rules:
                    report.setdefault("caseRules", {})[made] = rules
                    report["forTheUser"].append(f"{made}, by the four case rules its author was given: {rules_note(rules)}")
            else:
                report.setdefault("forTheUser", []).append(
                    f"{name} is landed and on develop: promoting main and running the default tests are yours to decide")
            finished = False
            continue
        report.update(brief=name, **stop)
        if "started" in stop:
            log(root, "start", name, run=stop["started"], session=stop.get("session"))
        break
    try:  # what this call did is in the log: committed now, so that the default workspace is left clean
        commit(root, [LOG], "Record the brief queue's handover",
               "The brief queue's log (llm-dlc/loops/queue.jsonl) records what `brief_queue.py next` did: the steps it "
               "took, the runs it started, and the briefs it finished.")
    except Problem as e:
        report["logNotCommitted"] = str(e)
    return report


def describe(root: Path) -> dict:
    data = read(root)
    rows = []
    for e in data["entries"]:
        if e["state"] == "removed":
            continue
        s = effective(data, e)
        runs = {k: f"{v} ({run_state(root, v)})" for k, v in e.get("runs", {}).items()}
        due = next((n for n in steps_of(s) if n not in e["done"]), None)
        rows.append({"name": e["name"], "state": e["state"], "source": e["source"], "runs": runs, "nextStep": due,
                     **({"problem": e["problem"]} if e.get("problem") else {}),
                     **({"brief": e["brief"], "pullRequests": len(e.get("pullRequests") or []),
                         "generator": f"{s['generateClient']} {s['generate']} {s['generateEffort']}, compacting at "
                                      f"{s['generateCompactAt']}, session {s['generateSession']}"} if e.get("brief") else {}),
                     **({"generatedBy": e["generatedBy"]} if e.get("generatedBy") else {}),
                     "agent": f"{s['client']} {s['model']} {s['effort']}, session {s['session']}",
                     "setup": s["setup"]})
    folder = inbox()
    known = {Path(e["source"]).expanduser().resolve() for e in data["entries"] if e["state"] != "removed"}
    waiting = [shown(p) for p in inbox_briefs(folder)] if folder.is_dir() else []
    waiting = [w for w in waiting if Path(w).expanduser().resolve() not in known]
    return {"queue": rows, "inboxNotYetAdded": waiting, **({"hold": data["hold"]} if data.get("hold") else {}),
            "lastSession": data.get("lastSession"),
            "lastGenerateSession": data.get("lastGenerateSession"), "defaults": {**DEFAULTS, **data["defaults"]}}


def cmd_report(root: Path) -> list[dict]:
    rows = []
    for e in read(root)["entries"]:
        if e["state"] == "removed":
            continue
        runs = []
        for kind, name in e.get("runs", {}).items():
            run = single_run.Run(root, name)
            cycles = sum(1 for ev in conductor.read_events(run.dir) if ev.get("type") == "cycle-start") if run.dir.exists() else 0
            legs = len(run.read().get("legs") or [])
            runs.append({"kind": kind, "run": name, "state": run_state(root, name), "legs": legs,
                         "cyclesThisLeg": cycles, "landed": run.read().get("landed")})
        rows.append({"name": e["name"], "state": e["state"], "added": e.get("added"), "ended": e.get("ended"),
                     "runs": runs, "checkpoint": e.get("checkpoint"), "cleanup": e.get("cleanup")})
    return rows


def main(argv: list[str] | None = None, root: Path = REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="command", required=True)

    def where(p):
        g = p.add_mutually_exclusive_group()
        g.add_argument("--first", action="store_true")
        g.add_argument("--after")
        g.add_argument("--before")
        return p

    a = where(sub.add_parser("add", help="put a brief on the queue"))
    a.add_argument("brief")
    a.add_argument("--name")
    a.add_argument("--no-setup", action="store_true")
    a.add_argument("--generate", action="store_true", help="the file is a list of pull requests: write its brief first")
    a.add_argument("settings", nargs="*", metavar="KEY=VALUE")
    sub.add_parser("inbox", help="add the inbox's new briefs")
    for c in ("list", "status"):
        sub.add_parser(c, help="the queue and what `next` would do").add_argument("--json", action="store_true")
    m = where(sub.add_parser("move", help="move a brief"))
    m.add_argument("name")
    sub.add_parser("remove", help="take a brief off the queue").add_argument("name")
    s = sub.add_parser("set", help="change a brief's settings")
    s.add_argument("name")
    s.add_argument("settings", nargs="+", metavar="KEY=VALUE")
    d = sub.add_parser("defaults", help="print or change the defaults")
    d.add_argument("settings", nargs="*", metavar="KEY=VALUE")
    d.add_argument("--last-session")
    d.add_argument("--last-generate-session")
    sub.add_parser("next", help="the handover: every step that is due").add_argument("--finished", action="store_true")
    sub.add_parser("report", help="each brief's runs and state").add_argument("--json", action="store_true")
    sub.add_parser("hold", help="land what finishes, start nothing until `resume`").add_argument("--reason", default="")
    sub.add_parser("resume", help="end a hold")
    sub.add_parser("rules", help="what a written brief shows of the four case rules").add_argument("briefs", nargs="+", type=Path)
    args = ap.parse_args(argv)
    root = (args.root or root).resolve()
    try:
        if args.command == "add":
            over = settings(args.settings)
            if args.no_setup:
                over["setup"] = "none"
            if args.generate:
                over.setdefault("generate", single_run.GENERATE_MODEL)
            w, other = position(args)
            print(json.dumps(add(root, Path(args.brief), args.name, w, other, over), indent=1))
        elif args.command == "inbox":
            print(json.dumps({"added": take_inbox(root)}, indent=1))
        elif args.command in ("list", "status"):
            d = describe(root)
            if args.json:
                print(json.dumps(d, indent=1))
            else:
                for i, r in enumerate(d["queue"], 1):
                    runs = ", ".join(f"{k}: {v}" for k, v in r["runs"].items()) or "no run yet"
                    given = (f"{r['source']} ({r['pullRequests']} pull requests) -> {r['brief']}" if r.get("brief")
                             else r["source"] + (f" (generated by {r['generatedBy']})" if r.get("generatedBy") else ""))
                    print(f"{i}. {r['name']} [{r['state']}] {given}: {runs}; next step {r['nextStep'] or '-'}"
                          + (f"; PROBLEM {r['problem']}" if r.get("problem") else ""))
                if d["inboxNotYetAdded"]:
                    print("inbox, not yet added: " + ", ".join(d["inboxNotYetAdded"]))
                if not d["queue"] and not d["inboxNotYetAdded"]:
                    print("the queue is empty")
                if d.get("hold"):
                    print(f"HELD since {d['hold']['since']} by {d['hold']['by']}"
                          + (f": {d['hold']['reason']}" if d["hold"].get("reason") else "")
                          + "; `next` lands what finishes and starts nothing until `resume`")
        elif args.command == "move":
            w, other = position(args)
            if w is None:
                raise Problem("say where: --first, --after NAME or --before NAME")
            with locked(root) as data:
                e = next((e for e in data["entries"] if e["name"] == args.name and e["state"] != "removed"), None)
                if e is None:
                    raise Problem(f"no brief {args.name} on the queue")
                if e["state"] != "queued":
                    raise Problem(f"{args.name} has started ({e['state']}): only a brief still waiting moves")
                data["entries"].remove(e)
                placed(data["entries"], e, w, other)
            log(root, "move", args.name, position=w, other=other)
            print(json.dumps(describe(root)["queue"], indent=1))
        elif args.command == "remove":
            with locked(root) as data:
                e = next((e for e in data["entries"] if e["name"] == args.name and e["state"] != "removed"), None)
                if e is None:
                    raise Problem(f"no brief {args.name} on the queue")
                if any(run_state(root, r) == "running" for r in e.get("runs", {}).values()):
                    raise Problem(f"a run of {args.name} is under way: stop it first (`single_run.py stop`)")
                e["state"] = "removed"
            log(root, "remove", args.name)
            print(json.dumps({"removed": args.name}, indent=1))
        elif args.command == "set":
            over = checked(settings(args.settings), allow_run=True)
            with locked(root) as data:
                e = next((e for e in data["entries"] if e["name"] == args.name and e["state"] != "removed"), None)
                if e is None:
                    raise Problem(f"no brief {args.name} on the queue")
                if "run" in over:
                    kind = next((k for k in ("domain", "setup", "generate") if f"{k}-start" in e["done"] or e["state"] == k),
                                "generate" if e.get("brief") else "setup")
                    single_run.Run(root, over["run"])
                    e["runs"][kind] = over.pop("run")
                e.setdefault("settings", {}).update(over)
            log(root, "set", args.name, settings=over)
            print(json.dumps(next(r for r in describe(root)["queue"] if r["name"] == args.name), indent=1))
        elif args.command == "defaults":
            over = checked(settings(args.settings))
            for given in (args.last_session, args.last_generate_session):
                if given and not run_common.SESSION.fullmatch(given):
                    raise Problem(f"not a session id: {given}")
            if over or args.last_session or args.last_generate_session:
                with locked(root) as data:
                    data["defaults"].update(over)
                    if args.last_session:
                        data["lastSession"] = args.last_session
                    if args.last_generate_session:
                        data["lastGenerateSession"] = args.last_generate_session
                log(root, "defaults", None, settings=over, **({"lastSession": args.last_session} if args.last_session else {}),
                    **({"lastGenerateSession": args.last_generate_session} if args.last_generate_session else {}))
            print(json.dumps({**DEFAULTS, **read(root)["defaults"], "lastSession": read(root).get("lastSession"),
                              "lastGenerateSession": read(root).get("lastGenerateSession")}, indent=1))
        elif args.command == "hold":
            with locked(root) as data:
                was = data.get("hold")
                data["hold"] = was or {"since": now(), "by": who(), "reason": args.reason}
                if was and args.reason:
                    data["hold"]["reason"] = args.reason
            if not was:
                log(root, "hold", None, reason=args.reason)
            print(json.dumps({"hold": read(root)["hold"], **({"already": True} if was else {})}, indent=1))
        elif args.command == "resume":
            with locked(root) as data:
                was = data.pop("hold", None)
            if was:
                log(root, "resume", None, heldSince=was["since"])
            print(json.dumps({"resumed": bool(was), **({"heldSince": was["since"]} if was else {}),
                              "next": "run `brief_queue.py next` (with --finished if a run has ended) to start what is due"
                              if was else "the queue was not held"}, indent=1))
        elif args.command == "next":
            print(json.dumps(cmd_next(root, args.finished), indent=1))
        elif args.command == "rules":
            out = {}
            for path in args.briefs:
                try:
                    rules = case_rules(path.read_text())
                except OSError:
                    raise Problem(f"no brief at {path}")
                out[str(path)] = {**rules, "note": rules_note(rules)}
            print(json.dumps(out, indent=1))
        elif args.command == "report":
            rows = cmd_report(root)
            if args.json:
                print(json.dumps(rows, indent=1))
            else:
                for r in rows:
                    runs = "; ".join(f"{x['kind']} {x['run']} {x['state']}, {x['legs']} leg(s)"
                                     + (f", landed {str(x['landed'])[:12]}" if x["landed"] else "") for x in r["runs"]) or "not started"
                    print(f"- {r['name']} [{r['state']}]: {runs}" + (f"; ended {r['ended']}" if r.get("ended") else ""))
    except (Problem, single_run.Problem) as e:
        print(f"brief_queue.py: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
