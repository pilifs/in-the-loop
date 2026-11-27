#!/usr/bin/env python3
"""Reconcile the job pipeline's records. Read-only.

Joins, by job id: the committed specifications, the collected receipts and what each names (logs, diff, kept
outputs), the result indexes as recomputed from the receipts, and, for the working copy of a checkout, what the
runner holds that no commit has yet (claims, staged results, attempts). It says where two records of one job
disagree, and labels what can no longer be reconstructed instead of guessing it.

  python3 jobs/audit.py                       the working copy and the runner's state here
  python3 jobs/audit.py --rev REV             a revision, from git objects alone
  python3 jobs/audit.py --rev REV --census    only the counts, as JSON (what a frozen census is made with)
  python3 jobs/audit.py manifest --rev REV    one row a job: paths, git blob ids, the result folder's tree id
  python3 jobs/audit.py verify FILE [--rev REV]   a manifest against git: the same revision gives the same
                                              rows, and a later one still has every row it had

Three levels. A **discrepancy** is two records that cannot both be right (one id with two different
specifications, an index row that is not what its receipt gives, a receipt with no job): the command exits 1.
A **gap** is something a record names that the revision does not hold and that nothing here can restore (a kept
output the commit left out, an attempt nobody numbered): it is counted and listed, with the reason where one can
be told. A **note** is a fact of the layout a reader should know (a flat job with its result under a day).

Standard library only.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import records  # noqa: E402

layout = records.layout
AUDIT_SCHEMA = "itl-job-audit/v1"
CENSUS_SCHEMA = "itl-job-census/v1"
MANIFEST_SCHEMA = "itl-job-manifest/v1"
COMMIT_MAX_BYTES = 1 << 20      # jj's snapshot.max-new-file-size: a larger new file is left out of every commit
TERMINAL = ("passed", "failed", "timeout", "out-of-memory", "error", "cancelled")


def parse(data: bytes | None):
    """(document, None) or (None, why not)."""
    if data is None:
        return None, "not there"
    try:
        document = json.loads(data)
    except ValueError as e:
        return None, f"not JSON: {e}"
    return (document, None) if isinstance(document, dict) else (None, "not a JSON object")


class Audit:
    def __init__(self, root: Path, rev: str | None = None) -> None:
        self.root = Path(root)
        self.snapshot = records.Snapshot(self.root, rev)
        self.discrepancies: list[dict] = []
        self.gaps: list[dict] = []
        self.notes: list[dict] = []
        self.specs: dict[str, dict] = {}       # id -> the specification readers get (the flat one of two)
        self.receipts: dict[str, tuple[str, dict]] = {}   # id -> (path, document)

    def where(self) -> str:
        return self.snapshot.rev[:12] if self.snapshot.rev else "the working copy"

    def found(self, level: list, kind: str, job: str | None, detail: str, **more) -> None:
        level.append({"kind": kind, "id": job, "detail": detail, "at": self.where(), **more})

    # ----- the committed records

    def read_specs(self) -> None:
        by_id = self.snapshot.specs()
        blobs = self.snapshot.read(p for paths in by_id.values() for p in paths)
        for job_id, paths in by_id.items():
            documents = []
            for path in paths:
                document, why = parse(blobs[path])
                if why:
                    self.found(self.discrepancies, "malformed-spec", job_id, f"{path} is {why}", path=path)
                    continue
                if document.get("id") != job_id:
                    self.found(self.discrepancies, "spec-id-mismatch", job_id,
                               f"{path} says its id is {document.get('id')!r}", path=path)
                documents.append((path, document))
            if len(paths) > 1:
                same = len({blobs[p] for p in paths}) == 1
                self.found(self.notes if same else self.discrepancies,
                           "duplicate-spec-identical" if same else "duplicate-identity", job_id,
                           f"one id, {len(paths)} specifications" + (", the same bytes" if same else " that differ") +
                           ": readers use the flat one", paths=paths)
            if documents:
                self.specs[job_id] = documents[0][1]

    def read_receipts(self) -> None:
        by_id = self.snapshot.receipts()
        blobs = self.snapshot.read(p for paths in by_id.values() for p in paths)
        spec_paths = self.snapshot.specs()
        for job_id, paths in by_id.items():
            documents = []
            for path in paths:
                document, why = parse(blobs[path])
                if not why and not all(k in document for k in ("id", "status", "summary", "attention", "job", "steps", "outputs")):
                    why = "missing " + ", ".join(k for k in ("id", "status", "summary", "attention", "job", "steps", "outputs") if k not in document)
                if why:
                    self.found(self.discrepancies, "malformed-receipt", job_id, f"{path} is {why}", path=path)
                    continue
                if document["id"] != job_id:
                    self.found(self.discrepancies, "receipt-id-mismatch", job_id,
                               f"{path} says its id is {document['id']!r}", path=path)
                documents.append((path, document))
            if len(paths) > 1:
                same = len({blobs[p] for p in paths}) == 1
                self.found(self.notes if same else self.discrepancies,
                           "duplicate-receipt-identical" if same else "duplicate-identity", job_id,
                           f"one id, {len(paths)} receipts" + (", the same bytes" if same else " that differ") +
                           ": readers use the flat one", paths=paths)
            if not documents:
                continue
            path, receipt = documents[0]
            self.receipts[job_id] = (path, receipt)
            if job_id not in spec_paths:
                self.found(self.discrepancies, "receipt-without-spec", job_id,
                           f"{path} is the receipt of a job with no specification here", path=path)
                continue
            # A result goes beside its job. One that does not is still found by id, and by nothing else.
            spec_flat = spec_paths[job_id][0].count("/") == layout.JOBS.count("/") + 1
            receipt_flat = path.count("/") == layout.RESULTS.count("/") + 2
            if spec_flat != receipt_flat:
                self.found(self.notes, "mixed-layout", job_id,
                           f"its specification is {'flat' if spec_flat else 'under its day'} and its result is "
                           f"{'flat' if receipt_flat else 'under its day'}: found by id, not by a path made from the other",
                           paths=[spec_paths[job_id][0], path])
            spec = self.specs.get(job_id)
            ran = receipt.get("job") or {}
            if spec is not None and ran.get("sha256") and records.spec_digest(spec) != ran["sha256"]:
                moved = {k: v for k, v in spec.items() if k != "$schema"} == {k: v for k, v in (ran.get("spec") or {}).items() if k != "$schema"}
                self.found(self.notes if moved else self.discrepancies, "spec-rewritten-schema-path" if moved else "spec-drift",
                           job_id, "the specification here is not the one the receipt says it ran"
                           + (" (only its $schema path differs)" if moved else ""), path=path)

    def check_indexes(self) -> None:
        committed: dict[str, tuple[str, dict]] = {}
        blobs = self.snapshot.read(self.snapshot.indexes())
        recomputed = records.index_documents(self.receipts)
        for path in self.snapshot.indexes():
            document, why = parse(blobs[path])
            if why or not isinstance(document.get("results"), list):
                self.found(self.discrepancies, "malformed-index", None, f"{path} is {why or 'without a list of results'}", path=path)
                continue
            if path not in recomputed and document["results"]:
                self.found(self.discrepancies, "index-extra-file", None,
                           f"{path} lists {len(document['results'])} result(s) and no receipt belongs in it", path=path)
            if path in recomputed and document.get("shards") != recomputed[path].get("shards"):
                self.found(self.discrepancies, "index-stale-shards", None,
                           f"{path} names the days {document.get('shards')} and the receipts give {recomputed[path].get('shards')}", path=path)
            order = [row.get("id") for row in document["results"] if isinstance(row, dict)]
            for row in document["results"]:
                job_id = row.get("id") if isinstance(row, dict) else None
                if job_id in committed:
                    self.found(self.discrepancies, "index-duplicate-row", job_id,
                               f"indexed in {committed[job_id][0]} and again in {path}", path=path)
                    continue
                committed[job_id] = (path, row)
            if path in recomputed and sorted(order) == sorted(r["id"] for r in recomputed[path]["results"]) \
                    and order != [r["id"] for r in recomputed[path]["results"]]:
                self.found(self.discrepancies, "index-order", None, f"{path} has its rows in another order than newest first", path=path)
        expected = {row["id"]: (path, row) for path, document in recomputed.items() for row in document["results"]}
        for job_id, (path, row) in expected.items():
            if job_id not in committed:
                self.found(self.discrepancies, "index-missing-row", job_id, f"its receipt is collected and {path} has no row for it", path=path)
            elif committed[job_id][0] != path:
                self.found(self.discrepancies, "index-wrong-file", job_id, f"its row is in {committed[job_id][0]} and belongs in {path}", path=path)
            elif committed[job_id][1] != row:
                differs = sorted(k for k in set(row) | set(committed[job_id][1]) if row.get(k) != committed[job_id][1].get(k))
                self.found(self.discrepancies, "index-stale-row", job_id,
                           f"its row in {path} is not what its receipt gives: {', '.join(differs)} differ"
                           + (f" (the index says {committed[job_id][1].get('status')!r}, the receipt {row['status']!r})" if "status" in differs else ""),
                           path=path)
        for job_id, (path, _row) in committed.items():
            if job_id not in expected:
                self.found(self.discrepancies, "index-orphan-row", job_id, f"{path} has a row for it and no receipt is collected", path=path)

    def check_artifacts(self) -> None:
        """What each receipt names in its own folder: every step's log, the diff, and each output it says it kept.
        An applied output is the working copy's, and a later commit may rightly have changed it: not checked here."""
        files = self.snapshot.files
        absent = []
        for job_id, (path, receipt) in self.receipts.items():
            folder = path.rsplit("/", 1)[0]
            for step in receipt.get("steps") or []:
                log = (step.get("log") or {}).get("path")
                if log and f"{folder}/{log}" not in files:
                    absent.append((job_id, f"{folder}/{log}", "log", None))
            diff = receipt.get("changesDiff")
            if diff and receipt.get("collected") and f"{folder}/{diff}" not in files:
                absent.append((job_id, f"{folder}/{diff}", "diff", None))
            collected = receipt.get("collected") or {}
            outputs = {o["path"]: o for o in receipt.get("outputs") or [] if isinstance(o, dict) and "path" in o}
            for rel in list(collected.get("kept") or []) + list(collected.get("conflicts") or []):
                if (outputs.get(rel) or {}).get("change") == "deleted":
                    continue  # nothing to keep: the job removed the file
                if f"{folder}/outputs/{rel}" not in files:
                    absent.append((job_id, f"{folder}/outputs/{rel}", "kept output", (outputs.get(rel) or {}).get("bytes")))
        ignored = self.ignored([p for _, p, _, _ in absent])
        for job_id, path, what, size in absent:
            if size is not None and size > COMMIT_MAX_BYTES:
                why, reason = f"it is {size:,} bytes, over the {COMMIT_MAX_BYTES:,} a commit takes", "over-the-commit-limit"
            elif path in ignored:
                why, reason = "the repository's ignore rules leave its path out of every commit", "ignored-path"
            else:
                why, reason = "nothing here says why", "unexplained"
            originals = (self.receipts[job_id][1].get("originals") or {}).get("occurrences") or {}
            sealed = originals.get({"log": "logs", "diff": "diff", "kept output": "outputs"}[what])
            self.found(self.gaps, "artifact-not-committed", job_id,
                       f"the receipt names {what} {path}, which is not in {self.where()}: {why}"
                       + (f"; the run's originals hold it (occurrence {sealed})" if sealed else "; no original of it was sealed"),
                       path=path, what=what, reason=reason, occurrence=sealed)

    def ignored(self, paths: list[str]) -> set[str]:
        """Which of these paths the ignore rules of the checkout leave out (as the rules stand now)."""
        if not paths:
            return set()
        proc = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"], cwd=self.root, capture_output=True,
                              input="\0".join(paths).encode())
        return {p.decode() for p in proc.stdout.split(b"\0") if p}

    def check_provenance(self) -> None:
        """What a receipt was never given, and that nothing can add now: counted, each as one gap of the corpus."""
        no_attempt = sorted(i for i, (_, r) in self.receipts.items() if not r.get("originals"))
        no_session = sorted(i for i, (_, r) in self.receipts.items() if not (((r.get("job") or {}).get("spec") or {}).get("submitted") or {}).get("session"))
        no_run = sorted(i for i, (_, r) in self.receipts.items() if not (((r.get("job") or {}).get("spec") or {}).get("submitted") or {}).get("run"))
        for kind, ids, what in (
                ("no-attempt-identity", no_attempt, "name no attempt and no sealed originals: which run of the job produced them cannot be told from the record"),
                ("no-submitting-session", no_session, "name no submitting session"),
                ("no-originating-run", no_run, "name no originating run: the session and the commit's time are all that tie them to a run, and neither establishes it")):
            if ids:
                self.gaps.append({"kind": kind, "id": None, "detail": f"{len(ids)} of {len(self.receipts)} receipts {what}",
                                  "at": self.where(), "count": len(ids), "ids": ids})

    # ----- what the runner holds here that no commit has

    def check_live(self, state: Path) -> dict:
        """The runner's state directory: claims, staged results, attempts. Only for the working copy of a checkout."""
        live = {"stateDir": str(state), "available": state.is_dir(), "claims": [], "staged": [], "attempts": 0,
                "setAside": [], "recovery": []}
        if not state.is_dir():
            return live
        for claim in sorted((state / "claims").iterdir()) if (state / "claims").is_dir() else []:
            document, why = parse(claim.read_bytes())
            live["claims"].append({"id": claim.name, **(document or {"unreadable": why})})
            if claim.name not in self.specs and claim.name not in self.snapshot.specs():
                self.found(self.discrepancies, "claim-without-spec", claim.name, f"{claim} claims a job with no specification here", path=str(claim))
        for folder in sorted((state / "results").iterdir()) if (state / "results").is_dir() else []:
            document, why = parse((folder / "result.json").read_bytes() if (folder / "result.json").is_file() else None)
            if why:
                self.found(self.discrepancies, "malformed-staged-result", folder.name, f"{folder}/result.json is {why}", path=str(folder))
                continue
            live["staged"].append({"id": folder.name, "status": document.get("status"),
                                   "attempt": (document.get("attempt") or {}).get("id") or (document.get("originals") or {}).get("attempt")})
            if document.get("status") != "cancelled" and folder.name in self.receipts:
                self.found(self.notes, "staged-and-collected", folder.name,
                           "a result is staged and one is collected: a collect was interrupted, or the job ran again; the next collect settles it")
        for folder in sorted((state / "uncaptured").iterdir()) if (state / "uncaptured").is_dir() else []:
            live["setAside"].append(folder.name)
            self.found(self.gaps, "result-set-aside-unsealed", folder.name.rsplit("-", 1)[0],
                       f"{folder} holds a staged result that no capture sealed: kept, and in no archive", path=str(folder))
        claimed = {c["id"] for c in live["claims"]}
        for run_dir in sorted((state / "runs").iterdir()) if (state / "runs").is_dir() else []:
            # A run directory of before attempts had folders of their own: sealed ones carry a marker.
            if run_dir.is_dir() and run_dir.name not in claimed and not (run_dir / ".captured").exists() and any(run_dir.iterdir()):
                live["recovery"].append({"job": run_dir.name, "kind": "run-directory-unsealed"})
                self.found(self.gaps, "run-directory-unsealed", run_dir.name,
                           f"{run_dir} holds an attempt of before attempts had folders that nothing sealed; `recover` seals it", path=str(run_dir))
        attempts = HERE / "attempts.py"
        if attempts.exists() and (state / "attempts").is_dir():
            ledger = records.load("jobs_attempts", attempts)
            for attempt in ledger.every(state):
                live["attempts"] += 1
                for problem in ledger.problems(attempt):
                    live["recovery"].append({"attempt": attempt.id, "job": attempt.job, **problem})
                    self.found(self.gaps if problem.get("level") == "gap" else self.discrepancies, problem["kind"], attempt.job,
                               problem["detail"], attempt=attempt.id)
        return live

    # ----- the whole of it

    def run(self, state: Path | None = None) -> dict:
        self.read_specs()
        self.read_receipts()
        self.check_indexes()
        self.check_artifacts()
        self.check_provenance()
        live = self.check_live(state) if state is not None and self.snapshot.rev is None else None
        return {"schema": AUDIT_SCHEMA,
                "snapshot": {"revision": self.snapshot.rev, "root": str(self.root),
                             "views": {"committed": {"available": True, "of": self.where()},
                                       "live": {"available": bool(live and live["available"]),
                                                **({"why": "a revision is read from git alone: what a runner holds is not part of it"} if live is None else {})},
                                       "archive": {"available": False, "why": "receipts name their sealed occurrences; the archive's own journal is read by artifacts.py"}}},
                "census": self.census(), "live": live,
                # Why an artifact is not in the commit, by the ignore rules as they stand in this checkout: not part
                # of the census, which a later change of those rules must not move.
                "reasons": dict(sorted(collections.Counter(g["reason"] for g in self.gaps if g.get("reason")).items())),
                "discrepancies": self.discrepancies, "gaps": self.gaps, "notes": self.notes}

    def census(self) -> dict:
        specs, receipts = self.snapshot.specs(), self.snapshot.receipts()
        indexed = set()
        blobs = self.snapshot.read(self.snapshot.indexes())
        rows = 0
        for path in self.snapshot.indexes():
            document, why = parse(blobs[path])
            for row in (document or {}).get("results") or []:
                rows += 1
                indexed.add(row.get("id") if isinstance(row, dict) else None)
        outcomes, days = collections.Counter(), {}
        for job_id, (_, receipt) in self.receipts.items():
            outcomes[receipt["status"]] += 1
            day = days.setdefault(layout.shard(job_id), collections.Counter())
            day[receipt["status"]] += 1
        ids = sorted(set(specs) | set(receipts) | {i for i in indexed if i})
        return {"schema": CENSUS_SCHEMA, "revision": self.snapshot.rev,
                "ids": {"specs": len(specs), "receipts": len(receipts), "indexed": len(indexed), "indexRows": rows,
                        "all": len(ids), "inEverySet": len(set(specs) & set(receipts) & indexed),
                        "sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest()},
                "pending": sorted(set(specs) - set(receipts)),
                "outcomes": dict(sorted(outcomes.items())),
                "days": {day: {"rows": sum(c.values()), **dict(sorted(c.items()))} for day, c in sorted(days.items())},
                "layouts": {"flatSpecs": sum(1 for p in specs.values() if p[0].count("/") == layout.JOBS.count("/") + 1),
                            "specsByDay": sum(1 for p in specs.values() if p[0].count("/") != layout.JOBS.count("/") + 1),
                            "mixed": sorted(n["id"] for n in self.notes if n["kind"] == "mixed-layout")},
                "counts": {"discrepancies": dict(sorted(collections.Counter(d["kind"] for d in self.discrepancies).items())),
                           "gaps": dict(sorted(collections.Counter(g["kind"] for g in self.gaps).items())),
                           "notes": dict(sorted(collections.Counter(n["kind"] for n in self.notes).items()))}}


# ----- the manifest


def manifest(root: Path, rev: str) -> dict:
    snapshot = records.Snapshot(root, rev)
    rows = records.manifest_rows(snapshot)
    indexes = [{"path": p, "blob": snapshot.files[p]} for p in snapshot.indexes()]
    body = "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows)
    return {"schema": MANIFEST_SCHEMA, "revision": snapshot.rev, "jobs": len(rows),
            "files": sum(len(r["specs"]) + sum(f["files"] for f in r["results"]) for r in rows),
            "indexes": indexes, "rowsSha256": hashlib.sha256(body.encode()).hexdigest(), "rows": rows}


def write_manifest(document: dict, path: Path) -> None:
    """The header as one line, then one row a line, gzipped with no time in it: the same revision gives the same bytes."""
    head = {k: v for k, v in document.items() if k != "rows"}
    text = json.dumps(head, sort_keys=True, separators=(",", ":")) + "\n" + \
        "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in document["rows"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(text.encode(), mtime=0))


def read_manifest(path: Path) -> dict:
    lines = gzip.decompress(Path(path).read_bytes()).decode().splitlines()
    document = json.loads(lines[0])
    document["rows"] = [json.loads(line) for line in lines[1:]]
    return document


def verify_manifest(root: Path, path: Path, rev: str | None = None) -> list[str]:
    """What differs between a manifest and git. At the manifest's own revision the rows must be the same. At a
    later one (after a migration, say) every row the manifest has must still be there with the same ids: a job's
    records are written once, so a row that changed or went is a record that was moved, rewritten or lost."""
    kept = read_manifest(path)
    now = manifest(root, rev or kept["revision"])
    problems = []
    body = "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in kept["rows"])
    if hashlib.sha256(body.encode()).hexdigest() != kept["rowsSha256"]:
        problems.append("the manifest's rows are not the ones its header was written for (rowsSha256 differs)")
    have = {r["id"]: r for r in now["rows"]}
    for row in kept["rows"]:
        there = have.get(row["id"])
        if there is None:
            problems.append(f"{row['id']}: in the manifest, and not at {now['revision'][:12]}")
        elif there != row:
            for key, name in (("specs", "specification"), ("results", "result folder")):
                if there[key] != row[key]:
                    was = ", ".join(f"{x['path']} {(x.get('blob') or x.get('tree') or '')[:12]}" for x in row[key]) or "none"
                    is_ = ", ".join(f"{x['path']} {(x.get('blob') or x.get('tree') or '')[:12]}" for x in there[key]) or "none"
                    problems.append(f"{row['id']}: its {name} was {was} and is {is_}")
    if now["revision"] == kept["revision"]:
        extra = sorted(set(have) - {r["id"] for r in kept["rows"]})
        problems += [f"{i}: at {now['revision'][:12]}, and not in the manifest" for i in extra]
        if now["indexes"] != kept["indexes"]:
            problems.append("the result indexes are not the blobs the manifest names")
    return problems


# ----- the command


def render(report: dict, limit: int) -> str:
    census = report["census"]
    ids = census["ids"]
    lines = [f"# Job records at {report['snapshot']['revision'] or 'the working copy'}", "",
             f"- {ids['specs']} specification(s), {ids['receipts']} receipt(s), {ids['indexed']} indexed id(s) in "
             f"{ids['indexRows']} index row(s); {ids['inEverySet']} of {ids['all']} id(s) are in all three",
             f"- outcomes: " + (", ".join(f"{n} {s}" for s, n in census["outcomes"].items()) or "none"),
             f"- not collected: {len(census['pending'])} specification(s) with no receipt"]
    live = report.get("live")
    if live:
        lines.append(f"- here: {len(live['claims'])} claim(s), {len(live['staged'])} staged result(s), {live['attempts']} attempt(s) "
                     f"on record, {len(live['setAside'])} result(s) set aside unsealed" if live["available"]
                     else f"- here: no runner state at {live['stateDir']}")
    for title, key in (("Discrepancies", "discrepancies"), ("Gaps", "gaps"), ("Notes", "notes")):
        found = report[key]
        lines += ["", f"## {title}: {len(found)}", ""]
        kinds = collections.Counter(f["kind"] for f in found)
        for kind, n in sorted(kinds.items()):
            why = ", ".join(f"{m} {r}" for r, m in report["reasons"].items()) if kind == "artifact-not-committed" else ""
            lines.append(f"- **{kind}**: {n}" + (f" ({why})" if why else ""))
            for f in [f for f in found if f["kind"] == kind][:limit]:
                lines.append(f"  - {(f['id'] + ': ') if f.get('id') else ''}{f['detail']}")
            if n > limit:
                lines.append(f"  - ... and {n - limit} more (--json lists every one)")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="audit.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("command", nargs="?", choices=["report", "manifest", "verify"], default="report")
    parser.add_argument("file", nargs="?", help="verify: the manifest; manifest: where to write it (default: stdout, as JSON)")
    parser.add_argument("--root", default=str(HERE.parent), help="the checkout (default: the one this file is in)")
    parser.add_argument("--rev", help="a revision, read from git objects alone (default: the working copy)")
    parser.add_argument("--state-dir", help="the runner's state (default: verification/.state under the root)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--census", action="store_true", help="only the counts, as JSON")
    parser.add_argument("--expect", help="a census file: exit 1 unless this audit's counts are the same")
    parser.add_argument("--limit", type=int, default=5, help="how many of each kind the page lists (default 5)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.command == "manifest":
        if not args.rev:
            parser.error("manifest: give --rev")
        document = manifest(root, args.rev)
        if args.file:
            write_manifest(document, Path(args.file))
            print(f"wrote {args.file}: {document['jobs']} job(s), {document['files']} file(s) at {document['revision'][:12]}")
        else:
            print(json.dumps(document, indent=1, sort_keys=True))
        return 0
    if args.command == "verify":
        if not args.file:
            parser.error("verify: give the manifest's file")
        problems = verify_manifest(root, Path(args.file), args.rev)
        for p in problems[:200]:
            print(p)
        print(f"{len(problems)} difference(s) between {args.file} and git" + (f" at {args.rev}" if args.rev else " at its own revision"))
        return 1 if problems else 0
    audit = Audit(root, args.rev)
    state = Path(args.state_dir) if args.state_dir else root / records.RECORDS / ".state"
    report = audit.run(state)
    status = 1 if report["discrepancies"] else 0
    if args.expect:
        expected = json.loads(Path(args.expect).read_text())
        mine = {k: v for k, v in report["census"].items() if k != "revision"}
        theirs = {k: v for k, v in expected.items() if k not in ("revision", "note", "manifest")}
        differs = sorted(k for k in set(mine) | set(theirs) if mine.get(k) != theirs.get(k))
        if differs:
            print(f"the census differs from {args.expect} in: {', '.join(differs)}", file=sys.stderr)
            status = 1
    if args.census:
        print(json.dumps(report["census"], indent=1, sort_keys=True))
    elif args.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    else:
        print(render(report, args.limit))
    return status


if __name__ == "__main__":
    sys.exit(main())
