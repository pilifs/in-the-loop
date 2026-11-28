"""The job pipeline's committed records, read by job id from a git revision or from a working copy.

A job's specification and its receipt (`result.json`, with the logs, the diff and the kept outputs beside it) are
kept under `verification/jobs` and `verification/results`, flat or under the day the job was submitted
(`verification/layout.py`, the one resolver of those paths). Everything here joins them **by id**: a path that
ends in `result.json` is a receipt only when the layout says so (2,897 files of the corpus of 2026-11-27 are
called `result.json`, and 1,906 of them are receipts: the rest are outputs a job kept), and a result is not
always in the layout its job has (three jobs of 2026-11-22 have a flat specification and a result under its day).

  Snapshot           every file of the two folders at a revision (git objects only) or in a working copy
  index_documents    the result indexes, recomputed from the receipts: `collect` writes them with this, and the
                     audit compares the committed ones with it
  manifest_rows      one row a job: the paths and git ids of its specification, its receipt and its result folder

Standard library only. Nothing here writes.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

RECORDS = "verification"
INDEX_SCHEMA = "verification-results-index/v1"


def load(name: str, path: Path):
    """A module by path: the tools here are run as scripts from several folders, and import each other this way."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


layout = load("verification_layout", Path(__file__).resolve().parents[1] / RECORDS / "layout.py")
JOBS, RESULTS = layout.JOBS, layout.RESULTS
BATCHES = "verification/batches"   # the map of each batch's rows to jobs (jobs/batch.py)


def head(root: Path) -> str:
    """The latest commit of a checkout: jj's @- in a jj workspace (@ is the change being edited, and not
    committed), else git's HEAD."""
    import shutil
    if (Path(root) / ".jj").exists() and shutil.which("jj"):
        proc = subprocess.run(["jj", "log", "--no-graph", "--ignore-working-copy", "-r", "@-", "-T", 'commit_id ++ "\\n"'],
                              cwd=root, capture_output=True, text=True)
        ids = proc.stdout.split()
        if proc.returncode == 0 and len(ids) == 1:
            return ids[0]
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def spec_digest(spec: dict) -> str:
    """The digest a receipt records of the job it ran (`job.sha256`): of the specification as sorted JSON."""
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


class Snapshot:
    """Every file under the two record folders: at a revision, from git objects alone (the working copy is not
    read, so an audit of a pinned revision says the same whatever is checked out), or, with no revision, in the
    working copy as it stands (what a collect wrote and nobody committed yet is then part of it)."""

    def __init__(self, root: Path, rev: str | None = None) -> None:
        self.root, self.rev = Path(root), None
        self.files: dict[str, str | None] = {}   # path -> git blob id (None in a working copy)
        self.sizes: dict[str, int] = {}
        self.trees: dict[str, str] = {}          # folder -> git tree id (a revision only)
        self._by_folder: dict[str, list[str]] | None = None
        if rev is None:
            for base in (JOBS, RESULTS):
                for path in sorted((self.root / base).rglob("*")) if (self.root / base).is_dir() else []:
                    if path.is_file():
                        rel = path.relative_to(self.root).as_posix()
                        self.files[rel], self.sizes[rel] = None, path.stat().st_size
            return
        self.rev = self._git("rev-parse", "--verify", f"{rev}^{{commit}}").strip()
        for row in self._git("ls-tree", "-r", "-t", "-l", "-z", self.rev, "--", JOBS + "/", RESULTS + "/").split("\0"):
            if not row:
                continue
            meta, path = row.split("\t", 1)
            _mode, kind, oid, size = meta.split()
            if kind == "tree":
                self.trees[path] = oid
            elif kind == "blob":
                self.files[path], self.sizes[path] = oid, int(size)

    def _git(self, *args: str, data: bytes | None = None, text: bool = True):
        proc = subprocess.run(["git", *args], cwd=self.root, capture_output=True, input=data,
                              text=text if data is None else False)
        if proc.returncode != 0:
            err = proc.stderr if isinstance(proc.stderr, str) else proc.stderr.decode(errors="replace")
            raise RuntimeError(f"git {' '.join(args[:3])}: {err.strip()}")
        return proc.stdout

    def read(self, paths) -> dict[str, bytes | None]:
        """The bytes of several files, by path, in one git process (None for a file that is not there)."""
        paths = list(paths)
        if self.rev is None:
            found = {}
            for p in paths:
                try:
                    found[p] = (self.root / p).read_bytes()
                except OSError:
                    found[p] = None
            return found
        if not paths:
            return {}
        out = self._git("cat-file", "--batch", data="".join(f"{self.rev}:{p}\n" for p in paths).encode())
        at, found = 0, {}
        for path in paths:
            end = out.find(b"\n", at)
            header = out[at:end].split() if end >= 0 else []
            if len(header) == 3 and header[1] == b"blob":
                size = int(header[2])
                found[path] = out[end + 1:end + 1 + size]
                at = end + 1 + size + 1
            else:
                found[path] = None
                at = end + 1 if end >= 0 else len(out)
        return found

    # ----- by id

    def specs(self) -> dict[str, list[str]]:
        """Every path that is a job's specification, by id. Two paths for one id are the two layouts."""
        found: dict[str, list[str]] = {}
        for path in self.files:
            job_id = layout.job_id_of(path)
            if job_id:
                found.setdefault(job_id, []).append(path)
        return {k: sorted(v, key=lambda p: p.count("/")) for k, v in sorted(found.items())}   # the flat one first

    def receipts(self) -> dict[str, list[str]]:
        """Every path that is a job's receipt (its result folder's own `result.json`), by id."""
        found: dict[str, list[str]] = {}
        for path in self.files:
            inside = layout.result_id_of(path)
            if inside and inside[1] == "result.json":
                found.setdefault(inside[0], []).append(path)
        return {k: sorted(v, key=lambda p: p.count("/")) for k, v in sorted(found.items())}

    def batches(self) -> list[str]:
        """The path of every batch's map (verification/batches/NAME.json)."""
        if self.rev is None:
            folder = self.root / BATCHES
            return sorted(p.relative_to(self.root).as_posix() for p in folder.glob("*.json")) if folder.is_dir() else []
        return sorted(p for p in self._git("ls-tree", "--name-only", self.rev, "--", BATCHES + "/").splitlines() if p.endswith(".json"))

    def indexes(self) -> list[str]:
        """The result indexes: the one of the results kept flat, and one a day."""
        return sorted(p for p in self.files if p.startswith(RESULTS + "/") and p.endswith("/index.json")
                      and layout.result_id_of(p) is None)

    def result_files(self) -> dict[str, list[str]]:
        """Every file of every result folder, by the folder's path: the receipt, the logs, the diff, the outputs."""
        if self._by_folder is None:
            self._by_folder = {}
            for path in self.files:
                inside = layout.result_id_of(path)
                if inside:
                    self._by_folder.setdefault(path[:-len(inside[1]) - 1], []).append(path)
        return self._by_folder


def index_entry(result: dict, rel: str) -> dict:
    """One line of a result index: what `report` and a reader of many results need without opening the receipt.
    `rel` is the receipt's path under the results folder. `wallSeconds` is the requested steps' time alone
    (`usage.wallSeconds`): a job that failed while it was being prepared has 0 here and its elapsed time in the
    receipt's own `wallSeconds`."""
    spec = (result.get("job") or {}).get("spec") or {}
    usage = result.get("usage") or {}
    second = spec.get("schema") == "itl-job/v2"   # its capabilities are a label, and it has a purpose and may have a case
    return {"id": result["id"], "title": result.get("title"), "status": result["status"], "summary": result["summary"],
            "attention": result["attention"],
            "capabilities": (spec.get("labels") or {}).get("capability", []) if second else spec.get("capabilities", []),
            **({k: spec[k] for k in ("purpose", "case") if k in spec} if second else {}),
            "links": spec.get("links", {}), "sourceCommit": result["sourceCommit"], "finishedAt": result["finishedAt"],
            "wallSeconds": usage.get("wallSeconds"), "peakMemoryBytes": usage.get("peakMemoryBytes"),
            "estimate": result.get("estimate"), "host": (result.get("runner") or {}).get("host"),
            "result": rel}


def index_documents(receipts: dict[str, tuple[str, dict]]) -> dict[str, dict]:
    """The result indexes that a set of receipts gives, by the index's repository path. `receipts` is, by job id,
    the receipt's repository path and its document. One index for the results kept flat, which names under
    `shards` each day that has an index of its own; each newest first, and in id order where two finished at the
    same time."""
    flat, days = [], {}
    for job_id in sorted(receipts):
        path, result = receipts[job_id]
        folder = path.rsplit("/", 1)[0]                       # verification/results[/YYYY/MM/DD]/ID
        parent = folder.rsplit("/", 1)[0]
        entry = index_entry(result, path[len(RESULTS) + 1:])
        if parent == RESULTS:
            flat.append(entry)
        else:
            days.setdefault(parent, []).append(entry)
    newest = lambda rows: sorted(rows, key=lambda e: e["finishedAt"] or "", reverse=True)
    shards = {"shards": sorted(d[len(RESULTS) + 1:] for d in days)} if days else {}
    documents = {f"{RESULTS}/index.json": {"schema": INDEX_SCHEMA, **shards, "results": newest(flat)}}
    for folder, rows in days.items():
        documents[f"{folder}/index.json"] = {"schema": INDEX_SCHEMA, "shard": folder[len(RESULTS) + 1:], "results": newest(rows)}
    return documents


def manifest_rows(snapshot: Snapshot) -> list[dict]:
    """One row a job id, for a revision: the path and git blob id of each specification and each receipt it has,
    and the git tree id of each result folder, which fixes every path and every byte beneath it (the logs, the
    diff, the outputs kept), with how many files that is. A row is what `git ls-tree` gives back at that revision,
    so the manifest is verified against git by making it again."""
    if snapshot.rev is None:
        raise ValueError("a manifest is of a revision: git ids are what it records")
    specs, receipts = snapshot.specs(), snapshot.receipts()
    rows = []
    for job_id in sorted(set(specs) | set(receipts)):
        folders = []
        for path in receipts.get(job_id, []):
            folder = path.rsplit("/", 1)[0]
            inside = snapshot.result_files().get(folder, [])
            folders.append({"path": folder, "tree": snapshot.trees.get(folder), "files": len(inside),
                            "bytes": sum(snapshot.sizes[p] for p in inside), "receipt": snapshot.files[path]})
        rows.append({"id": job_id, "specs": [{"path": p, "blob": snapshot.files[p]} for p in specs.get(job_id, [])],
                     "results": folders})
    return rows
