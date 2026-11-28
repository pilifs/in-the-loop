#!/usr/bin/env python3
"""The scripts under verification/, each with who calls it: an inventory to read before moving or removing one.

A script there may have no Python import anywhere and still be live: a committed job runs it by a command line,
a test loads it by a path it builds, a skill or a page names it. So every kind of caller is looked for:

  jobs      the `run` of a step of a committed job (by the script's path, or by its name from the step's folder),
            with the last such job and how it ended: the last revision the script is known to have worked at
  tests     a test file that names its path, or imports it by name after putting its folder on the path
  code      any other Python or shell file that does
  pages     a Markdown page, a skill, a hook or a settings file that names it (session logs under llm-dlc/traces
            are not pages)
  records   a page that records one run or one problem and directs no one: a brief or a results page under
            llm-dlc/loops, the findings. It shows that the script was used, not that anything still uses it

and each script gets a class from them: `shared runner code`, `compatibility entry point`, `test`, `supported
campaign replay` (a test, other code or a live page keeps it usable), `historical-only tool` (committed jobs ran
it, or a run's record names it, and nothing live does: it must stay where those jobs' commands and that record's
reader find it), or `orphan candidate` (no caller of any kind was found, which is a reason to look and not yet a
reason to delete).

A class is no stronger than what gives it: a script that only historical tools call is historical with them, and
one that only orphan candidates call is a candidate too (`settle`), so a helper does not look supported because a
script nothing uses imports it.

A page names a script by its path, by its file name from the script's own folder, or by its file name on a line
that also names the script's folder; code may also build the path from parts anywhere in the file. So a page that
reports what this inventory found should point at verification/scripts.md, not list the scripts: a list of orphan
candidates by path would be read as a record of each, and the next inventory would call them historical.

  python3 jobs/script_inventory.py            the page (verification/scripts.md) on stdout
  python3 jobs/script_inventory.py --write    write the page and verification/scripts.json
  python3 jobs/script_inventory.py --json

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "itl-script-inventory/v1"
RECORDS = ("verification/jobs/", "verification/results/")
RUN_RECORDS = ("llm-dlc/loops/", "verification/findings")
SHARED = {"verification/layout.py": "where a job and its result are, by id; loaded by path from jobs/ and seven tools",
          "verification/capture.py": "hands the runner's and the collector's originals to the private archive"}
ENTRY = {"verification/pipeline.py": "runs jobs/pipeline.py under the name every committed job, hook and note uses"}
CLASSES = ("shared runner code", "compatibility entry point", "test", "supported campaign replay", "historical-only tool", "orphan candidate")


def tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-s"], cwd=root, check=True, capture_output=True, text=True).stdout
    return [line.split("\t", 1)[1] + ("\0x" if line.startswith("100755") else "") for line in out.splitlines() if "\t" in line]


def scripts(files: list[str]) -> list[str]:
    """Every program under verification/ that is not a record: a .py or .sh file, or any file marked executable."""
    found = []
    for entry in files:
        path, _, executable = entry.partition("\0")
        if path.startswith("verification/") and not path.startswith(RECORDS) and (path.endswith((".py", ".sh")) or executable):
            found.append(path)
    return sorted(found)


def job_callers(root: Path, names: list[str]) -> dict[str, list[dict]]:
    """For each script, the committed jobs whose steps run it."""
    statuses = {}
    for index in (root / "verification/results").rglob("index.json"):
        try:
            for row in json.loads(index.read_text()).get("results", []):
                statuses[row["id"]] = (row.get("status"), row.get("sourceCommit"))
        except (OSError, ValueError, KeyError):
            continue
    by_name = {}
    for name in names:
        by_name.setdefault(Path(name).name, []).append(name)
    found = {name: [] for name in names}
    for path in sorted((root / "verification/jobs").rglob("*.json")):
        try:
            job = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        hit = set()
        for step in job.get("steps") or []:
            run, cwd = str(step.get("run", "")), str(step.get("cwd") or ".").strip("./")
            for base, candidates in by_name.items():
                if base not in run:
                    continue
                # By its path from the repository's root, or by its path from the folder the step runs in or cd's to.
                starts = [cwd] if cwd else []
                starts += [m.strip("\"'./") for m in re.findall(r"cd\s+(\S+)\s*(?:&&|;)", run)]
                for name in candidates:
                    if name in run or any(name.startswith(s + "/") and os.path.relpath(name, s) in run for s in starts if s):
                        hit.add(name)
        for name in hit:
            status, source = statuses.get(job.get("id"), (None, None))
            found[name].append({"job": job.get("id"), "status": status, "sourceCommit": source})
    return found


def text_callers(root: Path, files: list[str], names: list[str]) -> dict[str, dict[str, list[str]]]:
    """For each script, the tests, the other code, the live pages and the run records that name it."""
    found = {name: {"tests": [], "code": [], "pages": [], "records": []} for name in names}
    stems = {}
    for name in names:
        if name.endswith(".py"):
            stems.setdefault(Path(name).stem, []).append(name)
    importing = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
    bases = {}
    for name in names:
        bases.setdefault(Path(name).name, []).append(name)
    any_base = re.compile("|".join(sorted(map(re.escape, bases), key=len, reverse=True)))
    for entry in files:
        path = entry.partition("\0")[0]
        if path.startswith(RECORDS) or path.startswith("llm-dlc/traces/") or path in ("verification/scripts.md", "verification/scripts.json"):
            continue
        kind = "tests" if Path(path).name.startswith("test_") and path.endswith(".py") else \
            "code" if path.endswith((".py", ".sh")) else "pages" if path.endswith((".md", ".json", ".toml", ".yml", ".yaml")) else None
        if kind is None:
            continue
        if kind == "pages" and path.startswith(RUN_RECORDS):
            kind = "records"
        try:
            text = (root / path).read_text(errors="replace")
        except OSError:
            continue
        here = str(Path(path).parent)
        program = kind in ("tests", "code")
        imported = set(importing.findall(text)) if program else set()
        lines = None
        # Only the scripts whose file name is in the text, or whose module is imported, can be called from here.
        candidates = {n for base in set(any_base.findall(text)) for n in bases[base]} | {n for stem in imported for n in stems.get(stem, [])}
        for name in sorted(candidates):
            if name == path:
                continue
            folder, base = str(Path(name).parent), Path(name).name
            # Named by its path, or by its file name from its own folder. From elsewhere, a program may build the
            # path from parts (the folder's name anywhere in the file is enough); a page has to name the folder on
            # the line that names the file, or every page that mentions an audit.py would call every audit.py.
            named = name in text or (base in text and folder == here)
            if not named and base in text and Path(folder).name in text:
                part = re.compile(r"(?<![\w-])" + re.escape(Path(folder).name) + r"(?![\w-])")
                if program:
                    named = bool(part.search(text))
                else:
                    lines = text.splitlines() if lines is None else lines
                    named = any(base in line and part.search(line) for line in lines)
            # Imported by name: from the same folder, or from a file that builds the folder's path (its last part is
            # in the text) and puts it on the import path, as verification/test_merged_pr_qualification.py does.
            by_import = Path(name).stem in imported and name.endswith(".py") and (
                folder == here or ("sys.path" in text and Path(folder).name in text) or (folder == "verification" and "verification" in text))
            if named or by_import:
                found[name][kind].append(path)
    return found


def classify(name: str, jobs: list, callers: dict) -> tuple[str, str]:
    if name in SHARED:
        return "shared runner code", SHARED[name]
    if name in ENTRY:
        return "compatibility entry point", ENTRY[name]
    if Path(name).name.startswith("test_"):
        return "test", "run by the default test run"
    pages = [p for p in callers["pages"] if not p.startswith(RUN_RECORDS)]
    records = callers.get("records", []) + [p for p in callers["pages"] if p.startswith(RUN_RECORDS)]
    if callers["tests"]:
        return "supported campaign replay", "a test names it, and the default test run runs that test"
    if callers["code"] or pages:
        return "supported campaign replay", "other code or a live page names it" + (", beside the jobs that ran it" if jobs else "")
    if jobs:
        return "historical-only tool", "committed jobs ran it, and nothing live names it: it stays where their commands find it"
    if records:
        return "historical-only tool", "a run's record names it, and no job, test, code or live page does: it stays for that record's reader"
    return "orphan candidate", "no caller of any kind was found"


LIVE = ("shared runner code", "compatibility entry point", "test", "supported campaign replay")


def settle(rows: list[dict]) -> list[dict]:
    """Lower a script that is supported only through scripts that are not: support comes from a test, a live page,
    code outside this inventory, or a supported script, and is followed from those (so two scripts that only call
    each other are not each other's support)."""
    by = {r["script"]: r for r in rows}
    held = {r["script"] for r in rows if r["class"] in LIVE and (
        r["class"] != "supported campaign replay" or r["tests"] or r["pagesCount"] or any(c not in by for c in r["code"]))}
    grew = True
    while grew:
        grew = False
        for r in rows:
            if r["class"] == "supported campaign replay" and r["script"] not in held and any(c in held for c in r["code"]):
                held.add(r["script"])
                grew = True
    lowered = [r for r in rows if r["class"] == "supported campaign replay" and r["script"] not in held]
    for r in lowered:
        r["class"] = None
    # Among those, what a committed job or a run's record names is historical, and so is what a historical tool calls.
    historical = {r["script"] for r in rows if r["class"] == "historical-only tool"}
    grew = True
    while grew:
        grew = False
        for r in lowered:
            if r["class"] is None and (r["jobs"] or r["recordsCount"] or any(c in historical for c in r["code"])):
                r["class"] = "historical-only tool"
                r["why"] = "committed jobs ran it, and only historical tools or orphan candidates call it: it stays where those commands find it" if r["jobs"] \
                    else "a run's record names it, and only historical tools or orphan candidates call it: it stays for that record's reader" if r["recordsCount"] \
                    else "nothing but historical tools call it: it stays with them"
                historical.add(r["script"])
                grew = True
    for r in lowered:
        if r["class"] is None:
            r["class"], r["why"] = "orphan candidate", "only orphan candidates call it"
    return rows


def replay_check(jobs: list, callers: dict) -> dict:
    """What would show that the script still works: a test that names it, or else the last job that passed with it."""
    if callers["tests"]:
        return {"kind": "test", "by": callers["tests"][0]}
    passed = [j for j in jobs if j["status"] == "passed"]
    if passed:
        return {"kind": "job", "by": passed[-1]["job"], "at": passed[-1]["sourceCommit"]}
    return {"kind": "none", "by": None}


def inventory(root: Path = ROOT) -> dict:
    files = tracked(root)
    names = scripts(files)
    jobs, callers = job_callers(root, names), text_callers(root, files, names)
    rows = []
    for name in names:
        kind, why = classify(name, jobs[name], callers[name])
        ran = jobs[name]
        passed = [j for j in ran if j["status"] == "passed"]
        last = (passed or ran or [None])[-1]
        parts = name.split("/")
        rows.append({"script": name, "class": kind, "why": why, "owner": parts[1] if len(parts) > 2 else "the pipeline",
                     "jobs": len(ran), "lastJob": last and last["job"], "lastJobStatus": last and last["status"],
                     "lastWorkedAt": passed[-1]["sourceCommit"] if passed else None,
                     "replayCheck": {"kind": "test", "by": name} if kind == "test" else replay_check(ran, callers[name]),
                     "tests": callers[name]["tests"], "code": callers[name]["code"], "pages": callers[name]["pages"][:6],
                     "pagesCount": len(callers[name]["pages"]), "records": callers[name]["records"][:6],
                     "recordsCount": len(callers[name]["records"])})
    settle(rows)
    counts = {kind: sum(1 for r in rows if r["class"] == kind) for kind in CLASSES}
    return {"schema": SCHEMA, "scripts": rows, "totals": {"unit": "scripts", "of": len(rows), "byClass": {k: n for k, n in counts.items() if n}}}


def render(document: dict) -> str:
    rows, totals = document["scripts"], document["totals"]
    out = ["# The scripts under `verification/`, and who calls each", "",
           "Generated by [`jobs/script_inventory.py`](../jobs/script_inventory.py) (`--write`); don't edit it by hand. A script here can be "
           "live with no Python import anywhere: a committed job runs it by a command line, a test loads it by a path it builds, a page "
           "names it. Read this before moving or removing one, and see [`llm-dlc/retired.md`](../llm-dlc/retired.md) for how one is retired.", "",
           "A brief, a results page or a finding that names a script is a *record*: it shows the script was used and keeps nothing "
           "usable, so it does not make a script supported. What would show that a script still works is the test in its row; where "
           "there is none, the last job that passed with it, run again at the commit it ran at (`replayCheck` and `lastWorkedAt` in "
           "[`scripts.json`](scripts.json)); a row with neither has no replay check. A script is no more supported than its callers: "
           "one that only historical tools call is historical with them, and one that only orphan candidates call is a candidate too.", "",
           f"{totals['of']} scripts: " + ", ".join(f"{n} {kind}" for kind, n in totals["byClass"].items()) + ".", ""]
    for kind in CLASSES:
        of = [r for r in rows if r["class"] == kind]
        if not of:
            continue
        out += [f"## {kind[0].upper() + kind[1:]} ({len(of)})", "", "| Script | Owner | Committed jobs that run it | Tests | Other callers |", "|---|---|---|---|---|"]
        for r in of:
            ran = f"{r['jobs']}, the last `{r['lastJob']}` ({r['lastJobStatus'] or 'not collected'})" if r["jobs"] else "none"
            others = [f"`{p}`" for p in r["code"][:3]] + ([f"{r['pagesCount']} page(s), such as `{r['pages'][0]}`"] if r["pages"] else []) \
                + ([f"{r['recordsCount']} run record(s), such as `{r['records'][0]}`"] if r["records"] else [])
            out.append(f"| `{r['script'].removeprefix('verification/')}` | {r['owner']} | {ran} | "
                       f"{', '.join(f'`{Path(t).name}`' for t in r['tests'][:3]) or 'none'} | {'; '.join(others) or 'none'} |")
        out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="write verification/scripts.md and verification/scripts.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    document = inventory()
    if args.write:
        (ROOT / "verification/scripts.json").write_text(json.dumps(document, indent=1) + "\n")
        (ROOT / "verification/scripts.md").write_text(render(document) + "\n")
        print(f"wrote verification/scripts.md and verification/scripts.json: {document['totals']}")
    elif args.json:
        print(json.dumps(document, indent=1))
    else:
        print(render(document))
    return 0


if __name__ == "__main__":
    sys.exit(main())
