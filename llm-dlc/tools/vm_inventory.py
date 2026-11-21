#!/usr/bin/env python3
"""What this machine holds of the repository that no other place does, measured and protected.

  python3 llm-dlc/tools/vm_inventory.py measure [--json]
      Numbers only, fit to publish: the remote and local heads, unpushed commits, git and jj sizes, tracked files
      and the widest directories, the runner's state, the upload record, transcripts, run records, stored logs,
      the large blobs a push would send, and the private archive's custody. Run it before and after a change to
      the plumbing, on the same machine, to compare.
  python3 llm-dlc/tools/vm_inventory.py pin
      A git ref under refs/itl/pins/ for every local head that origin does not have, so no garbage collection of
      git or jj can drop a commit that exists only here. jj does not import that namespace.
  python3 llm-dlc/tools/vm_inventory.py protect [--only WHAT ...] [--dry-run]
      Seal into the private archive (artifacts.py) what exists only on this machine: the runner's run directories
      (whole logs, outputs, whole diffs) and kept work directories, in every workspace; the loops' private run
      records; the project's source transcripts, Claude Code's and Codex's, as append-only streams; and the
      example records of the runs named in RECORD_RUNS. WHAT: runs, workdirs, run-records, transcripts, records.
      It can be run again: what was sealed and has not changed is not sealed twice.

`protect` reads transcripts and run records only to hash and seal them, into restricted custody; it prints
counts and bytes, never a path under a session or a line of content. It does not sweep the user's other
projects' sessions, credential stores or dependency caches: only the folders named in this file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import artifacts
import codex_rollout

REPO = Path(__file__).resolve().parents[2]


def result_rel(root: Path, job_id: str) -> str:
    """A job's result folder as a repository path, wherever the job is kept (verification/layout.py)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("verification_layout", REPO / "verification" / "layout.py")
    layout = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(layout)
    return layout.new_result(root, job_id).relative_to(root).as_posix()
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "llm-traces"
ARCHIVED = Path.home() / ".cache/in-the-loop/workspace-archive"  # run records of workspaces that were removed
# The examples whose records the runs of 2026-11-19 to 21 wrote (runs 5 to 7, VF-053): sealed before any trim.
RECORD_RUNS = range(340, 360)
SEALED_MARK = ".captured"  # verification/capture.py's mark in a run directory: its attempt was sealed


def run(*argv: str, cwd: Path | None = None) -> str:
    r = subprocess.run(argv, cwd=cwd or REPO, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def jj(*args: str) -> str:
    return run("jj", "--ignore-working-copy", *args)


def default_root() -> Path:
    out = jj("workspace", "root", "--name", "default").strip()
    return Path(out) if out else REPO


def workspace_roots() -> list[Path]:
    """The default workspace and its siblings named after it that are this repository's workspaces, listed or
    forgotten: a sibling counts when its .jj/repo points at this repository."""
    root = default_root()
    out = [root]
    for path in sorted(root.parent.glob(f"{root.name}-*")):
        pointer = path / ".jj/repo"
        try:
            target = (path / ".jj" / pointer.read_text().strip()).resolve() if pointer.is_file() else pointer.resolve()
        except OSError:
            continue
        if target == (root / ".jj/repo").resolve():
            out.append(path)
    return out


def tree_size(path: Path) -> tuple[int, int]:
    files = size = 0
    for base, _, names in os.walk(path):
        for name in names:
            try:
                size += os.lstat(os.path.join(base, name)).st_size
                files += 1
            except OSError:
                pass
    return files, size


def fingerprint(path: Path) -> str:
    """A folder's names, sizes and times: enough to tell that nothing in it changed since it was sealed."""
    h = hashlib.sha256()
    for base, dirs, names in os.walk(path):
        dirs.sort()
        for name in sorted(names):
            if name == SEALED_MARK and base == str(path):
                continue  # the runner's mark that the folder was sealed says nothing of its content
            st = os.lstat(os.path.join(base, name))
            h.update(f"{os.path.relpath(os.path.join(base, name), path)}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


def claude_projects() -> list[Path]:
    """Claude Code's transcript folders of this repository's workspaces, present or removed: the default
    workspace's and those named after it. Nothing else under ~/.claude/projects is read."""
    name = re.sub(r"[^A-Za-z0-9]", "-", str(default_root()))
    base = Path.home() / ".claude" / "projects"
    return sorted(p for p in base.glob(f"{name}*") if p.is_dir() and (p.name == name or p.name.startswith(name + "-")))


def codex_rollouts() -> list[Path]:
    found = []
    for root in workspace_roots():
        found += codex_rollout.rollouts_in(root) or []
    return sorted(set(found))


# --------------------------------------------------------------------------- measure

def measure() -> dict:
    out: dict = {"repository": str(REPO.name), "workspaces": len(workspace_roots())}
    main = run("git", "rev-parse", "refs/remotes/origin/main").strip()
    develop = run("git", "rev-parse", "--verify", "-q", "refs/remotes/origin/develop").strip()
    heads = [line.split("\t") for line in jj("log", "--no-graph", "-r", "heads(all())", "-T",
                                             'commit_id ++ "\t" ++ working_copies ++ "\n"').splitlines()]
    at = jj("log", "--no-graph", "-r", "@-", "-T", "commit_id").strip()
    out["history"] = {
        "origin_main": main, "origin_develop": develop or None, "local_heads": len(heads), "this_line": at,
        "mutable_commits": len(jj("log", "--no-graph", "-r", "mutable()", "-T", '"x\n"').splitlines()),
        "unpushed_on_this_line": len(jj("log", "--no-graph", "-r", "remote_bookmarks()..@-", "-T", '"x\n"').splitlines()),
        "unpushed_on_any_head": len(jj("log", "--no-graph", "-r", "remote_bookmarks()..heads(all())", "-T", '"x\n"').splitlines()),
        "pins": len(run("git", "for-each-ref", "refs/itl/pins").splitlines()),
    }
    counts = dict(line.split(": ", 1) for line in run("git", "count-objects", "-v").splitlines() if ": " in line)
    store = default_root()
    out["stores"] = {"git_pack_kib": int(counts.get("size-pack", 0)), "git_loose_kib": int(counts.get("size", 0)),
                     "git_loose_objects": int(counts.get("count", 0)), "git_dir_bytes": tree_size(store / ".git")[1],
                     "jj_dir_bytes": tree_size(store / ".jj")[1]}
    files, total, widths, largest = 0, 0, Counter(), []
    for line in run("git", "ls-tree", "-r", "-l", at).splitlines():
        meta, _, path = line.partition("\t")
        size = meta.split()[3]
        files += 1
        total += int(size) if size.isdigit() else 0
        parent = path.rsplit("/", 1)[0] if "/" in path else "."
        widths[parent] += 1
        largest.append((int(size) if size.isdigit() else 0, path))
    dirs = Counter()
    for parent in widths:  # a folder's width also counts its folders
        if parent != ".":
            dirs[parent.rsplit("/", 1)[0] if "/" in parent else "."] += 1
    wide = Counter({p: widths[p] + dirs[p] for p in set(widths) | set(dirs)})
    out["tree"] = {"files": files, "bytes": total,
                   "widest": [{"path": p, "entries": n} for p, n in wide.most_common(6)],
                   "largest": [{"path": p, "bytes": n} for n, p in sorted(largest, reverse=True)[:6]],
                   "by_top": {top: {"files": n} for top, n in Counter(p.split("/")[0] for _, p in largest).most_common(6)}}
    for top in list(out["tree"]["by_top"]):
        out["tree"]["by_top"][top]["bytes"] = sum(n for n, p in largest if p.split("/")[0] == top)
    out["tree"]["verification"] = {k: {"files": sum(1 for _, p in largest if p.startswith(f"verification/{k}/")),
                                      "bytes": sum(n for n, p in largest if p.startswith(f"verification/{k}/"))} for k in ("jobs", "results")}
    out["tree"]["example_records"] = {"files": sum(1 for _, p in largest if re.match(r"examples/[^/]+/records/", p)),
                                      "bytes": sum(n for n, p in largest if re.match(r"examples/[^/]+/records/", p))}
    out["tree"]["traces"] = {"files": sum(1 for _, p in largest if p.startswith("llm-dlc/traces/")),
                             "bytes": sum(n for n, p in largest if p.startswith("llm-dlc/traces/"))}
    runner = {}
    for root in workspace_roots():
        state = root / "verification/.state"
        if state.is_dir():
            runner[root.name] = {d: dict(zip(("entries", "files", "bytes"), (len(list((state / d).iterdir())), *tree_size(state / d))))
                                 for d in ("runs", "work", "results", "set-aside", "uncaptured") if (state / d).is_dir()}
    out["runner_state"] = runner
    try:
        uploads = Counter(v.get("state") for v in json.loads((STATE / "uploads.json").read_text()).values())
    except (OSError, ValueError):
        uploads = Counter()
    logs = unpublished = 0
    for manifest in (REPO / "llm-dlc/traces").glob("*/manifest.json"):
        for info in (json.loads(manifest.read_text()).get("logs") or {}).values():
            logs += 1
            unpublished += not info.get("url") and not info.get("withdrawn")
    stored = [p.stat().st_size for p in (REPO / "llm-dlc/traces").glob("*/logs/*.jsonl.gz")]
    out["traces"] = {"sessions": len(list((REPO / "llm-dlc/traces").glob("*/manifest.json"))), "logs_referenced": logs,
                     "logs_not_uploaded": unpublished, "snapshots_stored_here": len(stored), "snapshot_bytes": sum(stored),
                     "upload_record": dict(uploads)}
    projects = claude_projects()
    rollouts = codex_rollouts()
    out["transcripts"] = {"claude_folders": len(projects), "claude_files": sum(tree_size(p)[0] for p in projects),
                          "claude_bytes": sum(tree_size(p)[1] for p in projects), "codex_rollouts": len(rollouts),
                          "codex_bytes": sum(p.stat().st_size for p in rollouts)}
    out["run_records"] = {root.name: dict(zip(("files", "bytes"), tree_size(root / "llm-dlc/loop-summaries")))
                          for root in workspace_roots() if (root / "llm-dlc/loop-summaries").is_dir()}
    if ARCHIVED.is_dir():
        out["run_records"]["(archived workspaces)"] = dict(zip(("files", "bytes"), tree_size(ARCHIVED)))
    head_ids = [h[0] for h in heads]
    big = []
    if main and head_ids:
        listed = subprocess.run(["git", "rev-list", "--objects", *head_ids, "--not", main], cwd=REPO, capture_output=True, text=True).stdout
        sized = subprocess.run(["git", "cat-file", "--batch-check=%(objecttype) %(objectsize) %(rest)"], cwd=REPO, input=listed,
                               capture_output=True, text=True).stdout
        blobs = [(int(parts[1]), parts[2] if len(parts) > 2 else "") for parts in (line.split(" ", 2) for line in sized.splitlines())
                 if parts[0] == "blob"]
        big = sorted((b for b in blobs if b[0] >= 5 << 20), reverse=True)
        out["outgoing"] = {"objects": len(sized.splitlines()), "blobs": len(blobs), "blob_bytes": sum(b[0] for b in blobs),
                           "blobs_over_5MiB": len(big), "largest": [{"path": p, "bytes": n} for n, p in big[:3]]}
    if (artifacts.home() / "journal.sqlite").exists():
        archive = artifacts.Archive()
        status = archive.status()
        archive.close()
        out["archive"] = {k: status[k] for k in ("occurrences", "objects", "oldest_unverified", "last_remote_verification", "exposure")}
    return out


def cmd_measure(args) -> int:
    doc = measure()
    if args.json:
        print(json.dumps(doc, indent=1))
        return 0
    h, s, t = doc["history"], doc["stores"], doc["tree"]
    print(f"origin/main {h['origin_main'][:12]}, origin/develop {(h['origin_develop'] or 'none')[:12]}; this line at {h['this_line'][:12]}")
    print(f"  {h['local_heads']} local heads, {h['mutable_commits']} mutable commits; unpushed: {h['unpushed_on_this_line']} on this "
          f"line, {h['unpushed_on_any_head']} on any head; {h['pins']} pinned")
    print(f"git: {s['git_dir_bytes']:,} bytes ({s['git_pack_kib']:,} KiB packed, {s['git_loose_objects']:,} loose objects); jj: {s['jj_dir_bytes']:,} bytes")
    print(f"tree at this line: {t['files']:,} files, {t['bytes']:,} bytes; verification/results {t['verification']['results']['files']:,} files "
          f"{t['verification']['results']['bytes']:,} bytes; example records {t['example_records']['files']:,} files "
          f"{t['example_records']['bytes']:,} bytes; traces {t['traces']['files']:,} files {t['traces']['bytes']:,} bytes")
    print("  widest: " + "; ".join(f"{w['path']} {w['entries']:,}" for w in t["widest"]))
    print("  largest: " + "; ".join(f"{w['path']} {w['bytes']:,}" for w in t["largest"][:3]))
    for name, state in doc["runner_state"].items():
        print(f"runner state in {name}: " + ", ".join(f"{d} {v['entries']} ({v['bytes']:,} bytes)" for d, v in state.items()))
    tr, ts = doc["traces"], doc["transcripts"]
    print(f"traces: {tr['sessions']} sessions, {tr['logs_referenced']:,} logs referenced, {tr['logs_not_uploaded']} not uploaded, "
          f"{tr['snapshots_stored_here']:,} snapshots here ({tr['snapshot_bytes']:,} bytes); upload record {tr['upload_record']}")
    print(f"transcripts: Claude Code {ts['claude_files']} files in {ts['claude_folders']} folders ({ts['claude_bytes']:,} bytes); "
          f"Codex {ts['codex_rollouts']} rollouts ({ts['codex_bytes']:,} bytes)")
    print("run records: " + "; ".join(f"{k} {v['files']} files ({v['bytes']:,} bytes)" for k, v in doc["run_records"].items()))
    if o := doc.get("outgoing"):
        print(f"a push of every head would send {o['objects']:,} objects: {o['blobs']:,} blobs of {o['blob_bytes']:,} bytes unpacked, "
              f"{o['blobs_over_5MiB']} over 5 MiB" + "".join(f"\n  {b['bytes']:,} {b['path']}" for b in o["largest"]))
    if a := doc.get("archive"):
        print("archive: " + "; ".join(f"{k} {v['occurrences']} ({v['bytes']:,} bytes)" for k, v in a["occurrences"].items())
              + f"; exposure: {a['exposure']}")
    return 0


# --------------------------------------------------------------------------- pin

def cmd_pin(args) -> int:
    main = run("git", "rev-parse", "refs/remotes/origin/main").strip()
    day = artifacts.now().strftime("%Y%m%d")
    made = 0
    for line in jj("log", "--no-graph", "-r", "heads(all())", "-T", 'commit_id ++ " " ++ change_id.short(12) ++ "\n"').splitlines():
        commit, change = line.split()
        if main and subprocess.run(["git", "merge-base", "--is-ancestor", commit, main], cwd=REPO).returncode == 0:
            continue
        ref = f"refs/itl/pins/{day}/{change}"
        if run("git", "rev-parse", "--verify", "-q", ref).strip() != commit:
            subprocess.run(["git", "update-ref", ref, commit], cwd=REPO, check=True)
            made += 1
        print(f"{ref} -> {commit[:12]}")
    print(f"{made} ref(s) written; every head that origin lacks is held by a ref jj does not move or import")
    return 0


# --------------------------------------------------------------------------- protect

class Protector:
    def __init__(self, dry: bool) -> None:
        self.dry, self.archive = dry, None if dry else artifacts.Archive()
        self.seen_path = artifacts.home() / "inventory-sealed.json"
        try:
            self.seen = json.loads(self.seen_path.read_text())
        except (OSError, ValueError):
            self.seen = {}
        self.tally: Counter = Counter()

    def unchanged(self, key: str, path: Path) -> str | None:
        """None when the folder is as it was last sealed under this key; else its fingerprint, to record."""
        mark = fingerprint(path)
        return None if self.seen.get(key) == mark else mark

    def sealed(self, key: str, mark: str, record: dict | None, what: str) -> None:
        if record:
            self.tally[f"{what} sealed"] += 1
            self.tally[f"{what} bytes"] += record["raw"]["bytes"]
        if not self.dry:
            self.seen[key] = mark
            artifacts.write_durably(self.seen_path, json.dumps(self.seen, indent=1, sort_keys=True).encode())

    def tree(self, what: str, key: str, path: Path, kind: str, logical: str, **meta) -> None:
        mark = self.unchanged(key, path)
        if mark is None:
            self.tally[f"{what} unchanged"] += 1
            return
        if self.dry:
            self.tally[f"{what} to seal"] += 1
            self.tally[f"{what} bytes"] += tree_size(path)[1]
            return
        self.sealed(key, mark, self.archive.capture(path, kind, logical, **meta), what)

    def runs(self) -> None:
        """Each run directory the runner left: the whole logs, the outputs and the whole diff of a job's last run
        here. Sealed as one occurrence a job, laid out as verification/results/ID/ is."""
        for root in workspace_roots():
            state = root / "verification/.state"
            for run_dir in sorted((state / "runs").iterdir()) if (state / "runs").is_dir() else []:
                if (run_dir / ".captured").exists() or not run_dir.is_dir():
                    self.tally["runs sealed by the runner"] += run_dir.is_dir()
                    continue
                source = None
                for result in (root / result_rel(root, run_dir.name) / "result.json", state / "results" / run_dir.name / "result.json"):
                    try:
                        source = json.loads(result.read_text()).get("sourceCommit")
                        break
                    except (OSError, ValueError):
                        pass
                self.tree("runs", f"runs:{root.name}:{run_dir.name}", run_dir, "job-run", result_rel(root, run_dir.name),
                          job=run_dir.name, source={"commit": source} if source else None, exclude=lambda rel, is_dir: rel == SEALED_MARK,
                          notes={"stage": "sealed at the VM inventory: the run directory as the runner left it, before capture "
                                          "was wired into the runner; the attempt's number is not known", "workspace": root.name})
                if not self.dry:  # so the runner, when it runs the job again, does not take it for an attempt nobody sealed
                    (run_dir / SEALED_MARK).write_text(json.dumps({"at": "inventory"}))

    def workdirs(self) -> None:
        """Kept work directories, as what each holds beyond its job's commit."""
        sys.path.insert(0, str(REPO / "verification"))
        import capture
        for root in workspace_roots():
            state = root / "verification/.state"
            for work in sorted((state / "work").iterdir()) if (state / "work").is_dir() else []:
                source = None
                for result in (root / result_rel(root, work.name) / "result.json", state / "results" / work.name / "result.json"):
                    try:
                        source = json.loads(result.read_text()).get("sourceCommit")
                        break
                    except (OSError, ValueError):
                        pass
                key = f"work:{root.name}:{work.name}"
                if not source:
                    self.tally["workdirs with no result to name their commit (left, not sealed)"] += 1
                    continue
                if key in self.seen:
                    self.tally["workdirs unchanged"] += 1
                    continue
                if self.dry:
                    self.tally["workdirs to seal"] += 1
                    continue
                record = self.archive.capture(work, "job-workdir", f"{result_rel(root, work.name)}/workdir", job=work.name,
                                              source={"commit": source}, sparse=True, exclude=capture.beyond_commit(REPO, work, source),
                                              notes={"stage": "sealed at the VM inventory", "workspace": root.name,
                                                     "rule": "files identical to the source commit are left out, and folders that hold none of the rest"})
                self.sealed(key, "sealed", record, "workdirs")

    def run_records(self) -> None:
        for root in workspace_roots():
            folder = root / "llm-dlc/loop-summaries"
            if folder.is_dir():
                self.tree("run-records", f"run-records:{root.name}", folder, "run-record", "llm-dlc/loop-summaries",
                          notes={"workspace": root.name})
        if ARCHIVED.is_dir():
            self.tree("run-records", "run-records:(archived)", ARCHIVED, "run-record", "workspace-archive",
                      notes={"workspace": "(archived workspaces)"})

    def transcripts(self) -> None:
        """Source transcripts, unredacted, into restricted custody, each as a stream: what a session gained since
        it was last sealed. A subagent's transcript is a stream of its own."""
        files = [(artifacts.transcript_key(p), p) for folder in claude_projects() for p in sorted(folder.rglob("*.jsonl"))]
        files += [(artifacts.transcript_key(p), p) for p in codex_rollouts()]
        for key, path in files:
            session = codex_rollout.session_id(path) if key.startswith("codex/") else path.parts[len(Path.home().parts) + 3].removesuffix(".jsonl")
            if self.dry:
                self.tally["transcripts"] += 1
                self.tally["transcript bytes"] += path.stat().st_size
                continue
            record = self.archive.capture_stream(path, key, "session-transcript", f"transcripts/{key}", session=session)
            self.tally["transcripts with something new sealed" if record else "transcripts unchanged"] += 1
            self.tally["transcript bytes sealed"] += record["raw"]["bytes"] if record else 0
        # What Claude Code files beside a transcript (a tool's long output, a subagent's description) is the
        # session's too: each folder's other files, as one tree.
        for folder in claude_projects():
            if any(p.is_file() and p.suffix != ".jsonl" for p in folder.rglob("*")):
                self.tree("transcript side files", f"claude-files/{folder.name}", folder, "session-transcript",
                          f"transcripts/claude/{folder.name}/files", exclude=lambda rel, is_dir: not is_dir and rel.endswith(".jsonl"),
                          sparse=True, notes={"rule": "the folder's files other than the .jsonl transcripts, which are sealed as streams"})

    def records(self) -> None:
        for folder in sorted((REPO / "examples").glob("[0-9][0-9][0-9]-*/records")):
            if int(folder.parent.name[:3]) in RECORD_RUNS:
                at = jj("log", "--no-graph", "-r", "@-", "-T", "commit_id").strip()
                self.tree("records", f"records:{folder.parent.name}", folder, "example-records",
                          f"examples/{folder.parent.name}/records", source={"commit": at},
                          notes={"stage": "sealed whole before any trim of the records in Git (VF-053)"})


def cmd_protect(args) -> int:
    kinds = {"runs": Protector.runs, "workdirs": Protector.workdirs, "run-records": Protector.run_records,
             "transcripts": Protector.transcripts, "records": Protector.records}
    if unknown := set(args.only or []) - set(kinds):
        print(f"unknown: {', '.join(sorted(unknown))}; the kinds are {', '.join(kinds)}", file=sys.stderr)
        return 2
    protector = Protector(args.dry_run)
    for name, step in kinds.items():
        if not args.only or name in args.only:
            step(protector)
    for what, n in sorted(protector.tally.items()):
        print(f"{n:>16,}  {what}")
    if protector.archive:
        status = protector.archive.status()
        print(f"exposure to the loss of this machine: {status['exposure']} (python3 llm-dlc/tools/artifacts.py upload)")
        protector.archive.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vm_inventory.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("measure")
    c.add_argument("--json", action="store_true")
    sub.add_parser("pin")
    c = sub.add_parser("protect")
    c.add_argument("--only", nargs="*")
    c.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    return {"measure": cmd_measure, "pin": cmd_pin, "protect": cmd_protect}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
