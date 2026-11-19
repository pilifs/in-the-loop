#!/usr/bin/env python3
"""Inboxes: what a parallel run's conductor needs a stream to act on (llm-dlc/loops/stream-conductor.md, Design 2).

A stream can't be told anything through its brief (editing it stops its loop) or its Progress (its
own). Each stream gets an inbox instead, in the default workspace, gitignored like the integration
report:

  llm-dlc/loop-summaries/NAME-STREAM-inbox.md     what the stream reads every cycle, generated
  llm-dlc/loop-summaries/NAME-STREAM-inbox.jsonl  the conductor's lines it is generated from: one per item
                                                  sent, one per acknowledgement found

NAME-STREAM is the stream's brief (llm-dlc/loops/NAME-STREAM.md), and an item's id is NAME-STREAM-I001,
never reused. feature-loop.sh adds one sentence to every cycle's instruction (`instruction` below):
read the inbox, acknowledge each open item by its id in the commit's Progress update, and the
precedence, the brief, then the user's decisions, then the conductor's messages, so a message that
contradicts the brief is reported, not obeyed.

Not distracting the streams is a rule, and this tool holds the conductor to it: an item goes to a
stream only if that stream has to change something or may now go on. Each item is one of these kinds,
says what the stream is to do, and names what it comes from (a decision in llm-dlc/decisions/, or a
commit):

  failure     an integration failure in its code: what to fix
  interface   the rule two streams' interfaces are to meet by (a decided decision)
  answer      an answer it was waiting for (a decided decision)
  queued      a question about its work is queued for the user (an open decision): what to go on with
              meanwhile
  unblocked   it may now go on with what it was waiting for
  foundation  what the foundation stage of the run built before the stream started (brief_run.py): what to build on
              and not build again, with the stage's own report and its commit
  overturned  a decision overturned that touches its work: the decision that replaced it (whose
              supersedes names it), and the undo steps the overturned one's record lists

What the conductor did elsewhere, its upkeep, and decisions that change nothing for a stream have no
kind, and stay out. An item sent for a decision is added to that decision's `applied.inbox`, so the
record shows what each decision told whom.

A stream acknowledges an item by naming its id in the Progress of a commit. `collect` reads each
stream's committed Progress (its workspace's @-, from the brief's `- workspace:` setting) and records
each id it finds there, with the commit and the Progress line, which says what the stream did,
or that it reported the item as contradicting its brief. Acknowledged items leave the open list.

Commands:

  inbox.py send NAME-STREAM --kind KIND --do TEXT [--detail TEXT] [--decision ID]... [--commit CHANGE]...
  inbox.py list [NAME-STREAM...] [--open]
  inbox.py collect [NAME-STREAM...]       every inbox, without names
  inbox.py render [NAME-STREAM...]
  inbox.py instruction NAME-STREAM        the sentence feature-loop.sh adds to a cycle's instruction

Standard library only, as decisions.py, which it writes `applied.inbox` through.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import decisions

REPO = Path(__file__).resolve().parents[2]
FOLDER = Path("llm-dlc") / "loop-summaries"
LOOPS = Path("llm-dlc") / "loops"

# The only-what-to-act-on rule: the kinds of item a stream may be sent, each with what it says.
KINDS = {
    "failure": "an integration failure in your code",
    "interface": "the rule two streams' interfaces are to meet by",
    "answer": "an answer you were waiting for",
    "queued": "a question about your work is queued for the user",
    "unblocked": "you may go on",
    "overturned": "a decision overturned that touches your work",
    "foundation": "what the run's foundation stage built before you started",
    "delivered": "work done outside your stream is on the line for you",
}
# The state a decision an item names must be in, by kind (None: any).
DECISION_STATES = {"interface": {"decided"}, "answer": {"decided"}, "queued": {"open"},
                   "overturned": {"decided", "superseded"}, "failure": None, "unblocked": None, "foundation": None,
                   "delivered": None}

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ITEM_RE = re.compile(r"^(?P<name>[a-z0-9][a-z0-9-]*)-I(?P<n>[0-9]{3,})$")
ITEM_KEYS = {"kind", "id", "seq", "at", "about", "do", "detail", "from"}
ACK_KEYS = {"kind", "id", "seq", "at", "commit", "said"}


class InboxError(Exception):
    pass


def jj(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["jj", "--ignore-working-copy", *args], cwd=repo, capture_output=True, text=True)


def default_root(repo: Path = REPO) -> Path:
    """The default workspace, where the inboxes are, from any workspace of the repo."""
    r = jj(repo, "workspace", "root", "--name", "default")
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else repo


def inbox_path(name: str, folder: Path) -> Path:
    return folder / f"{name}-inbox.md"


def lines_path(name: str, folder: Path) -> Path:
    return folder / f"{name}-inbox.jsonl"


def inbox_names(folder: Path) -> list[str]:
    return sorted(p.name[:-len("-inbox.jsonl")] for p in folder.glob("*-inbox.jsonl")) if folder.is_dir() else []


def instruction(name: str) -> str:
    """The sentence feature-loop.sh adds to every cycle's instruction for the brief NAME."""
    path = f"$(jj workspace root --name default)/{FOLDER}/{name}-inbox.md"
    return (f"Then read your inbox, `{path}`, if it exists: each item under Open there is something the conductor "
            f"needs you to act on, so acknowledge each by its id in this cycle's Progress update with what you did "
            f"about it, and weigh it below your brief and the user's decisions, which come first, so an item that "
            f"contradicts the brief is reported in Progress, by its id, not obeyed.")


# The lines

def read(name: str, folder: Path) -> list[dict]:
    path = lines_path(name, folder)
    try:
        return decisions.parse(path.read_text(), path.name) if path.exists() else []
    except decisions.RecordError as e:
        raise InboxError(str(e)) from None


def line_problems(name: str, lines: list[dict]) -> list[str]:
    found, items, acked = [], set(), set()
    for n, line in enumerate(lines, 1):
        where = f"{name}-inbox.jsonl line {n}"
        kind, i = line.get("kind"), line.get("id")
        if line.get("seq") != n:
            found.append(f"{where}: seq is {line.get('seq')}, not {n}")
        m = ITEM_RE.match(i) if isinstance(i, str) else None
        if not m or m["name"] != name:
            found.append(f"{where}: {i!r} is not an item id of this inbox ({name}-I001)")
        if kind == "item":
            if set(line) - ITEM_KEYS:
                found.append(f"{where}: unknown fields {', '.join(sorted(set(line) - ITEM_KEYS))}")
            if line.get("about") not in KINDS:
                found.append(f"{where}: kind of item {line.get('about')!r} is not one a stream acts on "
                             f"({', '.join(KINDS)})")
            if not str(line.get("do", "")).strip():
                found.append(f"{where}: no `do`: an item says what the stream is to do")
            src = line.get("from") or {}
            if not (src.get("decisions") or src.get("commits")):
                found.append(f"{where}: names neither a decision nor a commit it comes from")
            if i in items:
                found.append(f"{where}: {i} sent twice")
            items.add(i)
        elif kind == "ack":
            if set(line) - ACK_KEYS:
                found.append(f"{where}: unknown fields {', '.join(sorted(set(line) - ACK_KEYS))}")
            if i not in items:
                found.append(f"{where}: acknowledges {i}, which was not sent before it")
            if i in acked:
                found.append(f"{where}: {i} acknowledged twice")
            acked.add(i)
        else:
            found.append(f"{where}: kind {kind!r} is neither item nor ack")
    return found


def fold(lines: list[dict]) -> list[dict]:
    """Each item sent, in order, with `ack` set to its acknowledgement line or None."""
    items = {line["id"]: dict(line, ack=None) for line in lines if line.get("kind") == "item"}
    for line in lines:
        if line.get("kind") == "ack" and line["id"] in items:
            items[line["id"]]["ack"] = line
    return list(items.values())


def append(name: str, folder: Path, new: list[dict]) -> None:
    lines = read(name, folder)
    for k, line in enumerate(new):
        line["seq"] = len(lines) + k + 1
    old = set(line_problems(name, lines))
    found = [p for p in line_problems(name, lines + new) if p not in old]
    if found:
        raise InboxError("refused, nothing sent:\n" + "\n".join(f"  {p}" for p in found))
    folder.mkdir(parents=True, exist_ok=True)
    with lines_path(name, folder).open("a") as f:
        for line in new:
            f.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")
    inbox_path(name, folder).write_text(render(name, lines + new))


# The inbox a stream reads

def _when(t: str) -> str:
    return t.replace("T", " ").replace("Z", " UTC")


def _sources(src: dict) -> str:
    parts = [f"decision `{d}`" for d in src.get("decisions", [])] + [f"commit `{c}`" for c in src.get("commits", [])]
    return ", ".join(parts)


def render(name: str, lines: list[dict]) -> str:
    items = fold(lines)
    open_items = [i for i in items if not i["ack"]]
    out = [f"# Inbox: {name}", "",
           f"What the conductor needs this stream to act on (llm-dlc/loops/stream-conductor.md, Design 2). Generated "
           f"by llm-dlc/tools/inbox.py from `{name}-inbox.jsonl` beside it: don't edit it.", "",
           "- **Only what you have to act on comes here:** something to change, or word that you may go on.",
           "- **Acknowledge each open item by its id** in the Progress update of the commit that takes it on, with "
           "what you did. It moves to Acknowledged once that commit is in.",
           "- **Precedence:** your brief, then the user's decisions, then these messages. An item that contradicts "
           "your brief is reported in Progress, by its id, not obeyed.", "",
           f"## Open ({len(open_items)})", ""]
    if not open_items:
        out += ["Nothing to act on.", ""]
    for i in open_items:
        out += [f"### {i['id']}: {KINDS[i['about']]}", "", f"**Do:** {i['do']}", ""]
        if i.get("detail"):
            out += [i["detail"], ""]
        out += [f"Sent {_when(i['at'])}, from {_sources(i['from'])}.", ""]
    acked = [i for i in items if i["ack"]]
    if acked:
        out += ["## Acknowledged", ""]
        for i in acked:
            a = i["ack"]
            out.append(f"- `{i['id']}` ({i['about']}, sent {_when(i['at'])}): acknowledged in `{a['commit']}`"
                       f"{': ' + a['said'] if a.get('said') else ''}")
        out.append("")
    return "\n".join(out)


# Sending

def brief_path(name: str, repo: Path) -> Path:
    return repo / LOOPS / f"{name}.md"


def send(name: str, about: str, do: str, *, detail: str | None = None, decision_ids: list[str] = (),
         commits: list[str] = (), folder: Path, decisions_root: Path, repo: Path, stamp: str | None = None) -> str:
    """Send one item to the stream NAME and return its id; refused, with nothing written, if it breaks the rule."""
    if not NAME_RE.match(name) or not brief_path(name, repo).exists():
        raise InboxError(f"no stream brief {LOOPS / (name + '.md')}: an inbox is named after its stream's brief")
    if about not in KINDS:
        raise InboxError(f"{about!r} is not a kind of item a stream acts on ({', '.join(KINDS)}): what the conductor "
                         f"did elsewhere, its upkeep, and decisions that change nothing for the stream stay out of "
                         f"its inbox (stream-conductor.md, Design 2)")
    stamp = stamp or decisions.now()
    # The decisions it names, and their new lines, which add this item to applied.inbox.
    by_record: dict[str, list[str]] = {}
    for spec in decision_ids:
        try:
            record, ids = decisions.resolve_ids([spec], None, decisions_root)
        except decisions.RecordError as e:
            raise InboxError(str(e)) from None
        by_record.setdefault(record, []).extend(i for i in ids if i not in by_record.get(record, []))
    lines = read(name, folder)
    number = max([int(ITEM_RE.match(line["id"])["n"]) for line in lines if ITEM_RE.match(line.get("id", ""))]
                 + [0]) + 1
    item_id = f"{name}-I{number:03d}"
    writes = []
    for record, ids in by_record.items():
        current = decisions.fold(decisions.read(record, decisions_root))
        new = []
        for i in ids:
            d = current[i]
            wanted = DECISION_STATES[about]
            if wanted and d["state"] not in wanted:
                raise InboxError(f"{i} is {d['state']}: an item of kind {about} names a decision that is "
                                 f"{' or '.join(sorted(wanted))}")
            applied = d["applied"]["inbox"] + [{"stream": name, "item": item_id}]
            new.append(decisions.conductor_line(record, {"id": i, "applied": {"inbox": applied}}, current, None,
                                                stamp, []))
        writes.append((record, new))
    all_ids = [i for ids in by_record.values() for i in ids]
    if about == "overturned" and not any(line["supersedes"] for _, new in writes for line in new):
        raise InboxError("an overturned item names the decision that replaced the overturned one (its supersedes "
                         "says which), and may name the overturned one too")
    line = {"kind": "item", "id": item_id, "seq": 0, "at": stamp, "about": about, "do": do,
            **({"detail": detail} if detail else {}), "from": {"decisions": all_ids, "commits": list(commits)}}
    found = [p for p in line_problems(name, lines + [dict(line, seq=len(lines) + 1)])
             if p not in set(line_problems(name, lines))]
    if found:
        raise InboxError("refused, nothing sent:\n" + "\n".join(f"  {p}" for p in found))
    for record, new in writes:
        try:
            decisions.write(record, decisions_root, new)
        except decisions.RecordError as e:
            raise InboxError(str(e)) from None
    append(name, folder, [line])
    return item_id


# Acknowledgements

def setting(text: str, key: str) -> str | None:
    """A `- key: value` line under the brief's ## Loop settings, as feature-loop.sh reads it."""
    inside = False
    for raw in text.splitlines():
        if raw.startswith("## "):
            inside = re.match(r"^## +Loop settings\s*$", raw) is not None
            continue
        m = re.match(rf"^[-*] +{re.escape(key)}: *(.*)$", raw) if inside else None
        if m:
            return re.sub(r"[`\s]", "", m[1]) or None
    return None


def progress(text: str) -> list[str]:
    """The lines of the brief's ## Progress section."""
    out, inside = [], False
    for raw in text.splitlines():
        if raw.startswith("## "):
            inside = re.match(r"^## +Progress\s*$", raw) is not None
            continue
        if inside:
            out.append(raw)
    return out


def committed_brief(name: str, repo: Path) -> tuple[str, str]:
    """The stream's committed brief, from its workspace's @-, and that commit's change id."""
    settings = brief_path(name, repo).read_text() if brief_path(name, repo).exists() else ""
    workspace = setting(settings, "workspace")
    rev = f"{workspace}@-" if workspace else "@-"
    r = jj(repo, "log", "--no-graph", "-r", rev, "-T", "change_id.short(8)")
    if r.returncode != 0:
        raise InboxError(f"{name}: can't read {rev}: {r.stderr.strip()}")
    shown = jj(repo, "file", "show", "-r", rev, str(LOOPS / f"{name}.md"))
    if shown.returncode != 0:
        raise InboxError(f"{name}: no brief at {rev}: {shown.stderr.strip()}")
    return shown.stdout, r.stdout.strip()


def collect(name: str, folder: Path, repo: Path, stamp: str | None = None) -> list[str]:
    """Record the open items the stream's committed Progress names; return their ids."""
    items = [i for i in fold(read(name, folder)) if not i["ack"]]
    if not items:
        return []
    text, commit = committed_brief(name, repo)
    lines = progress(text)
    stamp = stamp or decisions.now()
    new = []
    for i in items:
        said = next((ln.strip().lstrip("-* ").strip() for ln in lines
                     if re.search(rf"(?<![\w-]){re.escape(i['id'])}(?![\w-])", ln)), None)
        if said is not None:
            new.append({"kind": "ack", "id": i["id"], "seq": 0, "at": stamp, "commit": commit, "said": said})
    if new:
        append(name, folder, new)
    return [line["id"] for line in new]


def main(argv: list[str], folder: Path | None = None, decisions_root: Path | None = None,
         repo: Path | None = None) -> int:
    p = argparse.ArgumentParser(prog="inbox.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send")
    s.add_argument("name")
    s.add_argument("--kind", required=True)
    s.add_argument("--do", required=True)
    s.add_argument("--detail")
    s.add_argument("--decision", action="append", default=[])
    s.add_argument("--commit", action="append", default=[])
    s = sub.add_parser("list")
    s.add_argument("names", nargs="*")
    s.add_argument("--open", action="store_true")
    s = sub.add_parser("collect")
    s.add_argument("names", nargs="*")
    s = sub.add_parser("render")
    s.add_argument("names", nargs="*")
    s = sub.add_parser("instruction")
    s.add_argument("name")
    args = p.parse_args(argv)
    if args.cmd == "instruction":
        print(instruction(args.name))
        return 0
    repo = repo or REPO
    root = default_root(repo)
    folder = folder or root / FOLDER
    decisions_root = decisions_root or root / "llm-dlc" / "decisions"
    try:
        if args.cmd == "send":
            item = send(args.name, args.kind, args.do, detail=args.detail, decision_ids=args.decision,
                        commits=args.commit, folder=folder, decisions_root=decisions_root, repo=root)
            print(f"sent {item} to {inbox_path(args.name, folder)}"
                  + ("; commit the decision record with sync.py commit" if args.decision else ""))
            return 0
        if args.cmd == "list":
            for name in args.names or inbox_names(folder):
                for i in fold(read(name, folder)):
                    if args.open and i["ack"]:
                        continue
                    state = f"acknowledged in {i['ack']['commit']}" if i["ack"] else "open"
                    print(f"{i['id']}\t{i['about']}\t{state}\t{i['do']}")
            return 0
        if args.cmd == "collect":
            for name in args.names or inbox_names(folder):
                found = collect(name, folder, root)
                left = sum(1 for i in fold(read(name, folder)) if not i["ack"])
                print(f"{name}: {len(found)} acknowledged now"
                      + (f" ({', '.join(found)})" if found else "") + f", {left} open")
            return 0
        for name in args.names or inbox_names(folder):
            inbox_path(name, folder).write_text(render(name, read(name, folder)))
        return 0
    except InboxError as e:
        print(f"inbox.py: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
