#!/usr/bin/env python3
"""What the repository has retired, and whether a live file still sends a reader to it (llm-dlc/retired.md).

    retired.py list                each entry of the register: its status and the names it retired
    retired.py check [--planned]   every live file that names something retired in a paragraph that does not point
                                   at the register, every retired file that is still here, and every historical
                                   page or finding that names something retired without its line. Exit 1 with any.
                                   --planned counts the entries still `planned` as retired: what a step has left to do
    retired.py banners [--write]   the historical pages and findings that lack their line, with the line each would
                                   get; --write adds them

The register is the page a reader is sent to when a skill, a command or a script is no longer in the repository:
what it was, what replaced it, and the commit that still has it. This tool reads the page's entries and holds the
rest of the repository to them, by the kind of file:

  - A *live* file is one an agent acts on (LIVE below): instructions, skills, tools and their tests. A paragraph
    there that names something retired has to name the register too, or be rewritten.
  - A *historical* page is a brief or a results page that agents still open (HISTORICAL below), and each entry of
    verification/findings.md. Its text is left as it was written. One that names something retired carries one
    dated line that points at the register: among a page's first lines, anywhere in a finding's entry.
  - A *record* is never read and never edited: traces, decisions, jobs, results, and the queue's copies of the
    user's briefs, which the queue's log names.

A paragraph is a run of lines with no empty line among them, so in code a comment or a docstring that still names
a retired command is found with the lines around it. The files in EXEMPT name retired things by design.

Standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTER = "llm-dlc/retired.md"
POINTER = "retired.md"  # what a paragraph that names something retired must also name
STATUSES = ("planned", "retired")
FIELDS = ("Status", "What it was", "Replaced by", "Names", "Files", "Removed in")

# The files an agent acts on, as patterns from the repository's root. Everything else is history or a record.
LIVE = (
    "CLAUDE.md", "README.md", "ARCHITECTURE.md", ".gitignore",
    ".claude/settings.json", ".claude/skills/**/*", ".agents/skills/*", ".codex/**/*", ".claude-plugin/**/*", "plugins/**/*",
    "llm-dlc/*.md", "llm-dlc/*.schema.json", "llm-dlc/tools/*",
    "llm-dlc/loops/brief-generation-template.md", "llm-dlc/loops/setup-agent-template.md", "llm-dlc/loops/domain-prompt-*.md",
    "verification/README.md", "verification/*.py", "verification/pipeline.toml",
    "jobs/*.md", "jobs/*.py", "jobs/**/*.py", "jobs/**/*.md", "jobs/schema/*.json",
    "lib/README.md", "lib/tools/*.py", "lib/tests/costs.json", "lib/tests/fixtures/*/README.md", "lib/tests/*.rs",
    "examples/README.md", "examples/approaches.md", "examples/tools/*.py", "examples/tools/targets/*.py",
    "examples/schema/*.json",
)
# Live files that name retired things because that is their work.
EXEMPT = {
    REGISTER: "the register itself",
    "llm-dlc/tools/retired.py": "this tool",
    "llm-dlc/tools/test_retired.py": "its test",
    "llm-dlc/tools/loop_stats.py": "adds up every loop the repository ever ran, the retired kinds included",
    "llm-dlc/tools/test_loop_stats.py": "tests that, on records of retired loops",
    "llm-dlc/tools/tool_time.py": "says where the loops' time went from their logs, the retired kinds' commands included",
    "llm-dlc/tools/test_tool_time.py": "tests that, on commands of retired loops",
}
# llm-dlc/README.md's table of sessions is generated from the sessions' own prompts (sync.py): a record.
INDEX_BEGIN, INDEX_END = "<!-- index:begin", "<!-- index:end -->"
# Pages agents still open, whose text is left as it was written: one that names something retired carries one
# dated line among its first lines. The ones that are live (above) are held to the stricter rule instead.
HISTORICAL = ("llm-dlc/loops/*.md",)
BANNER_LINES = 5
# The queue's log (brief_queue.py) names its copies of the user's briefs and the briefs written for it: records.
QUEUE_LOG = "llm-dlc/loops/queue.jsonl"
# The findings are historical by entry: each `### VF-NNN` section that names something retired carries a line.
FINDINGS = "verification/findings.md"
FINDING = re.compile(r"(?m)^### VF-\d+")


class Problem(Exception):
    pass


def entries(text: str) -> list[dict]:
    """The register's entries: each `###` heading under `## Entries`, with its `- **Field:** value` lines. A value
    runs on over the indented lines after it. `names` and `files` are the back-quoted words of those two fields."""
    _, found, body = text.partition("\n## Entries\n")
    if not found:
        raise Problem(f"{REGISTER} has no `## Entries` section")
    out = []
    for block in re.split(r"(?m)^### +", body)[1:]:
        head, _, rest = block.partition("\n")
        entry: dict = {"name": head.strip(), "fields": {}}
        key = None
        for line in rest.splitlines():
            if m := re.match(r"- \*\*([^*:]+):\*\* *(.*)$", line):
                key = m[1].strip()
                entry["fields"][key] = m[2].strip()
            elif key and line.startswith("  ") and line.strip():
                entry["fields"][key] += " " + line.strip()
            elif not line.strip() or line.startswith("#"):
                key = None
        entry["status"] = entry["fields"].get("Status", "")
        entry["names"] = re.findall(r"`([^`]+)`", entry["fields"].get("Names", ""))
        entry["files"] = re.findall(r"`([^`]+)`", entry["fields"].get("Files", ""))
        out.append(entry)
    return out


def problems(found: list[dict]) -> list[str]:
    """What is wrong with the register's own form."""
    out, seen = [], set()
    for e in found:
        missing = [f for f in FIELDS if not e["fields"].get(f)]
        if missing:
            out.append(f"the entry {e['name']} lacks: {', '.join(missing)}")
        if e["status"] not in STATUSES:
            out.append(f"the entry {e['name']} has the status {e['status']!r}: one of {', '.join(STATUSES)}")
        if not e["names"]:
            out.append(f"the entry {e['name']} names nothing in back quotes under Names")
        if e["status"] == "retired" and not re.search(r"`[k-z]{8,}`", e["fields"].get("Removed in", "")):
            out.append(f"the entry {e['name']} is retired and names no change under Removed in")
        if e["name"] in seen:
            out.append(f"two entries are called {e['name']}")
        seen.add(e["name"])
    return out


def pattern(names: list[str]) -> re.Pattern | None:
    """One expression for every name, each as a word of its own: `watch.py` is not found in `test_watch.py`, nor
    `runtime.md` in `example-targets-runtime.md`. A name of several words allows any space between them."""
    if not names:
        return None
    words = sorted(names, key=len, reverse=True)
    return re.compile(r"(?<![\w-])(" + "|".join(r"\s+".join(map(re.escape, n.split())) for n in words) + r")(?![\w-])")


def live_files(root: Path) -> list[Path]:
    out = set()
    for glob in LIVE:
        for path in root.glob(glob):
            if path.is_file() and "__pycache__" not in path.parts and path.relative_to(root).as_posix() not in EXEMPT:
                out.add(path)
    return sorted(out)


def text_of(path: Path, root: Path) -> str | None:
    """A live file's text, or None for one that is not text. The generated table of sessions is blanked out, with
    its lines kept so that the numbers a finding gives are the file's own."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return None
    if path.relative_to(root).as_posix() == "llm-dlc/README.md":
        start, end = text.find(INDEX_BEGIN), text.rfind(INDEX_END)
        if 0 <= start < end:
            text = text[:start] + "\n" * text[start:end].count("\n") + text[end:]
    return text


def paragraphs(text: str):
    """(the number of its first line, the paragraph) for each run of lines with no empty line among them."""
    number, block = 0, []
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip():
            if not block:
                number = i
            block.append(line)
        elif block:
            yield number, "\n".join(block)
            block = []
    if block:
        yield number, "\n".join(block)


def scan(root: Path, found: list[dict], planned: bool = False) -> list[dict]:
    """Each paragraph of a live file that names something retired and does not point at the register."""
    owner = {n: e["name"] for e in found if e["status"] == "retired" or planned for n in e["names"]}
    expression = pattern(list(owner))
    if expression is None:
        return []
    out = []
    for path in live_files(root):
        text = text_of(path, root)
        if text is None or not expression.search(text):
            continue
        for number, block in paragraphs(text):
            named = sorted({" ".join(m.split()) for m in expression.findall(block)})
            if named and POINTER not in block:
                out.append({"file": path.relative_to(root).as_posix(), "line": number, "names": named,
                            "entries": sorted({owner[n] for n in named})})
    return out


def present(path: Path) -> bool:
    """Whether a retired file or folder is still here. A folder is here by the files in it, and a cache Python left
    behind is not one: when a change removes a folder, jj takes away the files it tracks and leaves what it
    ignores, so a checkout that once imported a module from there keeps a `__pycache__` of it (the default
    checkout did, 2026-11-27, and its default test run failed on it)."""
    if path.is_symlink() or path.is_file():
        return True
    if not path.is_dir():
        return False
    return any(p.is_symlink() or p.is_file() for p in path.rglob("*")
               if "__pycache__" not in p.relative_to(path).parts and p.suffix != ".pyc")


def still_here(root: Path, found: list[dict], planned: bool = False) -> list[dict]:
    """The files of a retired entry that are still in the repository."""
    return [{"entry": e["name"], "file": f} for e in found if e["status"] == "retired" or planned
            for f in e["files"] if present(root / f)]


def queue_copies(root: Path) -> set[str]:
    """The pages the queue's log names: its copies of the user's briefs, and the briefs written for it."""
    try:
        text = (root / QUEUE_LOG).read_text()
    except OSError:
        return set()
    return set(re.findall(r'"(llm-dlc/loops/[^"]+\.md)"', text))


def historical_files(root: Path) -> list[Path]:
    """The historical pages: HISTORICAL, less the live files and the queue's records."""
    live = {p for glob in LIVE for p in root.glob(glob)}
    records = queue_copies(root)
    return sorted(p for glob in HISTORICAL for p in root.glob(glob)
                  if p.is_file() and p not in live and p.relative_to(root).as_posix() not in records)


def retired_names(found: list[dict], planned: bool = False) -> tuple[dict[str, dict], re.Pattern | None]:
    owner = {n: e for e in found if e["status"] == "retired" or planned for n in e["names"]}
    return owner, pattern(list(owner))


def line_for(named: list[str], owner: dict[str, dict], to_register: str, what: str) -> str:
    """The dated line a historical page or a finding gets: what it names, the change that removed each, and where
    the register says what replaced it. `to_register` is the register's path from the page."""
    entries = list({owner[n]["name"]: owner[n] for n in named}.values())
    changes = sorted({c for e in entries for c in re.findall(r"`([k-z]{8})[k-z]*`", e["fields"].get("Removed in", ""))})
    dates = sorted({d for e in entries for d in re.findall(r"\d{4}-\d\d-\d\d", e["fields"].get("Removed in", ""))})
    both = lambda words: words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    listed = both([f"`{n}`" for n in named[:4]] + ([f"{len(named) - 4} more"] if len(named) > 4 else []))
    one = len(named) == 1
    when = ", ".join(dates) or "not yet"
    by = ("change " if len(changes) == 1 else "changes ") + both([f"`{c}`" for c in changes]) if changes else "planned"
    links = both([f"[`{REGISTER}#{e['name']}`]({to_register}#{e['name']})" for e in entries])
    return (f"**Retired ({when}, {by}):** this {what} names {listed}, which {'is' if one else 'are'} no longer in the "
            f"repository. See {links} for what replaced {'it' if one else 'them'} and the last commit that has "
            f"{'it' if one else 'them'}.")


def scan_historical(root: Path, found: list[dict], planned: bool = False) -> list[dict]:
    """Each historical page that names something retired and has no line among its first that points at the
    register, and each finding that names something retired and points at it nowhere. Each with the line it lacks."""
    owner, expression = retired_names(found, planned)
    if expression is None:
        return []
    out = []
    for path in historical_files(root):
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        named = sorted({" ".join(m.split()) for m in expression.findall(text)})
        if named and POINTER not in "\n".join(text.split("\n")[:BANNER_LINES]):
            here = path.relative_to(root).parent
            to_register = Path(*[".."] * len(here.parts), REGISTER).as_posix() if here.parts[:1] != ("llm-dlc",) else \
                Path(*[".."] * (len(here.parts) - 1), Path(REGISTER).name).as_posix()
            out.append({"file": path.relative_to(root).as_posix(), "names": named, "at": 0,
                        "line": "> " + line_for(named, owner, to_register, "page")})
    try:
        text = (root / FINDINGS).read_text()
    except OSError:
        return out
    starts = [m.start() for m in FINDING.finditer(text)]
    for start, end in zip(starts, starts[1:] + [len(text)]):
        entry = text[start:end]
        entry = entry[:m.start()] if (m := re.search(r"(?m)^## ", entry)) else entry
        named = sorted({" ".join(m.split()) for m in expression.findall(entry)})
        if named and POINTER not in entry:
            body = start + len(entry.split("\n", 1)[0]) + 1  # after the heading's line
            out.append({"file": FINDINGS, "names": named, "at": body, "entry": entry.split(":", 1)[0].lstrip("# "),
                        "line": "- " + line_for(named, owner, f"../{REGISTER}", "entry")})
    return out


def write_lines(root: Path, rows: list[dict]) -> None:
    """Add each line where it belongs: at a page's top, or as the first line under a finding's heading."""
    by_file: dict[str, list[dict]] = {}
    for row in rows:
        by_file.setdefault(row["file"], []).append(row)
    for name, group in by_file.items():
        path = root / name
        text = path.read_text()
        for row in sorted(group, key=lambda r: -r["at"]):  # from the end, so the places before it stay where they are
            if name == FINDINGS:
                rest = text[row["at"]:]
                text = text[:row["at"]] + ("\n" if not rest.startswith("\n") else "") + "\n" + row["line"] + rest
            else:
                text = row["line"] + "\n\n" + text
        path.write_text(text)


def register(root: Path) -> list[dict]:
    try:
        return entries((root / REGISTER).read_text())
    except OSError as e:
        raise Problem(f"{REGISTER} cannot be read: {e}")


def main(argv: list[str] | None = None, root: Path = REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("check").add_argument("--planned", action="store_true")
    sub.add_parser("banners").add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    try:
        found = register(root)
    except Problem as e:
        print(f"retired.py: {e}", file=sys.stderr)
        return 2
    if args.command == "list":
        for e in found:
            print(f"{e['name']} [{e['status']}]: {', '.join(e['names'])}")
        return 0
    if args.command == "banners":
        rows = scan_historical(root, found)
        for row in rows:
            print(f"{row['file']}{' ' + row['entry'] if row.get('entry') else ''}:\n  {row['line']}")
        if args.write:
            write_lines(root, rows)
        print(f"{len(rows)} line(s) {'written' if args.write else 'missing (--write adds them)'}")
        return 0 if args.write or not rows else 1
    wrong = problems(found)
    left = still_here(root, found, args.planned)
    named = scan(root, found, args.planned)
    bare = scan_historical(root, found, args.planned)
    for line in wrong:
        print(line)
    for row in left:
        print(f"{row['file']}: still here, though the entry {row['entry']} retired it")
    for row in named:
        print(f"{row['file']}:{row['line']}: names {', '.join(row['names'])} ({', '.join(row['entries'])}) "
              f"without pointing at {REGISTER}")
    for row in bare:
        print(f"{row['file']}{' ' + row['entry'] if row.get('entry') else ''}: names {', '.join(row['names'])} without the line "
              f"that points at {REGISTER} (retired.py banners --write adds it)")
    print(f"{len(wrong)} problem(s) in the register, {len(left)} retired file(s) still here, "
          f"{len(named)} paragraph(s) in {len({r['file'] for r in named})} live file(s) to rewrite or point at the register, "
          f"{len(bare)} historical page(s) or finding(s) without their line")
    return 1 if wrong or left or named or bare else 0


if __name__ == "__main__":
    sys.exit(main())
