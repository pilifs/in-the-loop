"""A batch of jobs from one manifest: one ordinary job a row, and a published map from rows to jobs.

A batch of 30 to 50 cases was, until 2026-11-27, one `submit` typed for each case and a wait improvised around
them (VF-072). A manifest says the batch once: a template of a job and the rows that fill it in.

    {"schema": "itl-job-batch/v1", "batch": "boot-s-setup", "title": "...", "created": "2026-11-28T09:00:00+00:00",
     "submitted": {"by": "the watcher", "run": "single-boot-s"},
     "template": {"title": "Build {row}", "description": "...", "purpose": "build", "resources": {...},
                  "steps": [{"name": "build", "run": "tools/build_case.sh {row} {module}"}], "outputs": ["out/{row}"]},
     "rows": [{"row": "S01", "vars": {"module": "core"}}, {"row": "S02", "vars": {...}, "override": {"priority": 5}}]}

`{name}` in any string of the template is the row's variable of that name (`{row}` is the row's own identity,
`{batch}` the batch's; `{{` and `}}` are braces). A row's `override` replaces top-level keys of the job after that.
`needs` may name another row (`{"row": "S01"}`), which becomes that row's job.

Submitting a manifest writes nothing a second submission of it would write differently: there is no clock and no
session in what it writes, so two sessions, two workspaces or a submission killed half way end with the same files.

  - **A row's work identity** is the digest of what it asks to be done: the steps, the environment, the outputs,
    the requirements, the prerequisites, the source revision, the purpose, the workload and the case. Not the
    title, the estimate or the priority.
  - **A job's id** is the batch's `created` time, its name, the row and the first characters of the work identity.
    A job whose file is already there with that work identity is left as it is, whoever wrote it.
  - **A row whose work changed** (another revision, another task, other inputs) gets another id: a new job that
    names the old one under `supersedes`. That is not a retry. A rerun of the same job is an attempt of it
    (jobs/attempts.py), and a `resubmit` with other resources is a new job with the *same* work identity that
    supersedes the old one. The row's history in the map keeps the three apart: one entry a job, each with its
    work identity and why it came.
  - **The map** (`verification/batches/BATCH.json`) is written whole each time, from the manifest and what the
    rows already had, under a lock, after every job file.

Nothing is run here: a batch's jobs are committed and scheduled like any other.

Standard library only.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import re
from pathlib import Path

MANIFEST_SCHEMA = "itl-job-batch/v1"
MAP_SCHEMA = "itl-job-batch-map/v1"
VIEW_SCHEMA = "itl-job-batch-view/v1"
FOLDER = "verification/batches"
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")
# What a row asks to be done: a change to any of these is other work. Everything else describes or estimates it.
WORK_KEYS = ("purpose", "workload", "steps", "environment", "outputs", "requires", "needs", "source", "stopOnFailure", "case")
# A row in one of these states is not going to change by waiting: it has a result, or it will not start as things are.
SETTLED = ("finished", "collected", "recorded-elsewhere", "blocked", "unschedulable", "invalid")


class Problem(Exception):
    """A manifest that cannot be submitted as it is: every reason, found before anything is written."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def fill(value, variables: dict, where: str, problems: list[str]):
    """`value` with `{name}` replaced in every string of it, at any depth."""
    if isinstance(value, str):
        def one(m):
            if m[0] in ("{{", "}}"):
                return m[0][0]
            if m[1] not in variables:
                problems.append(f"{where}: no variable {m[1]!r} (it has {', '.join(sorted(variables)) or 'none'})")
                return m[0]
            return str(variables[m[1]])
        return re.sub(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value)
    if isinstance(value, list):
        return [fill(v, variables, where, problems) for v in value]
    if isinstance(value, dict):
        return {k: fill(v, variables, where, problems) for k, v in value.items()}
    return value


def work_identity(job: dict) -> str:
    return hashlib.sha256(json.dumps({k: job[k] for k in WORK_KEYS if k in job}, sort_keys=True).encode()).hexdigest()


def stamp(created: str) -> str:
    """The UTC time a batch was created, as a job id begins: YYYYMMDD-HHMMSS."""
    digits = re.sub(r"\D", "", created)
    return f"{digits[:8]}-{digits[8:14]}"


def job_id(created: str, batch: str, row: str, work: str, slug) -> str:
    return f"{stamp(created)}-{slug(batch, 20)}-{slug(row, 20)}-{work[:8]}"


def expand(manifest: dict, p) -> list[dict]:
    """The job of each row, in the manifest's order, or Problem with everything that is wrong with the batch: the
    whole of it is checked before any of it is written. `p` is the pipeline module."""
    problems = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        problems.append(f"schema is {manifest.get('schema')!r}, not {MANIFEST_SCHEMA!r}")
    batch = manifest.get("batch")
    if not isinstance(batch, str) or not NAME.match(batch):
        problems.append(f"batch {batch!r} is not a name of lower-case letters, digits and hyphens")
    created = manifest.get("created")
    if not isinstance(created, str) or not re.fullmatch(r"\d{8}-\d{6}", stamp(created)):
        problems.append("no `created` time (such as 2026-11-28T09:00:00+00:00): the jobs' ids begin with it, and it is "
                        "what makes a second submission of the manifest give the same ids")
    template, rows = manifest.get("template"), manifest.get("rows")
    if not isinstance(template, dict):
        problems.append("no template: the job every row fills in")
    if not isinstance(rows, list) or not rows:
        problems.append("no rows")
    if problems:
        raise Problem(problems)
    names = [r.get("row") if isinstance(r, dict) else None for r in rows]
    for name in sorted({n for n in names if names.count(n) > 1 and n is not None}):
        problems.append(f"row {name!r} is there {names.count(name)} times: a row's identity is its name")
    by_row = {}
    for n, row in enumerate(rows, 1):
        if not isinstance(row, dict) or not isinstance(row.get("row"), str) or not row["row"].strip():
            problems.append(f"row {n}: no `row` to identify it by")
            continue
        where = f"row {row['row']}"
        variables = {**(row.get("vars") or {}), "row": row["row"], "batch": batch}
        job = fill(copy.deepcopy(template), variables, where, problems)
        job.update(copy.deepcopy(row.get("override") or {}))
        job.setdefault("case", row["row"])
        by_row.setdefault(row["row"], job)
    resolved = {}

    def identity(row, trail=()):
        """The row's job id, which needs the ids of the rows it needs first: a job names its prerequisites by id."""
        if row in resolved:
            return resolved[row]
        if row in trail:
            problems.append(f"row {row}: its prerequisites come back to itself ({' -> '.join((*trail, row))})")
            return None
        job = by_row[row]
        needs = []
        for need in job.get("needs") or []:
            if isinstance(need, dict) and "row" in need:
                if need["row"] not in by_row:
                    problems.append(f"row {row}: needs row {need['row']!r}, which the batch does not have")
                    continue
                other = identity(need["row"], (*trail, row))
                if other:
                    needs.append({"job": other})
            else:
                needs.append(need)
        if needs or "needs" in job:
            job["needs"] = needs
        work = work_identity(job)
        resolved[row] = job_id(created, batch, row, work, p.slug)
        job["batch"] = {"id": batch, "row": row, "work": work}
        return resolved[row]

    out = []
    for row, job in by_row.items():
        if identity(row) is None:
            continue
        job["schema"] = p.JOB_SCHEMA_V2
        job["id"] = resolved[row]
        # Who and when, as the manifest says it: nothing of whoever happens to run the submission, so that two of
        # them write the same bytes. Who ran it is in their session's own record.
        job["submitted"] = {**(manifest.get("submitted") or {}), "at": created}
        job.pop("$schema", None)
        for problem in p.validate(job, "job.schema.json"):
            problems.append(f"row {row}: {problem}")
        out.append(job)
    ids = [j["id"] for j in out]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"two rows give the job id {dup}: their names are the same once shortened; rename one")
    if problems:
        raise Problem(list(dict.fromkeys(problems)))
    return out


def map_path(root: Path, batch: str) -> Path:
    return Path(root) / FOLDER / f"{batch}.json"


def read_map(root: Path, batch: str) -> dict | None:
    try:
        document = json.loads(map_path(root, batch).read_text())
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) and document.get("schema") == MAP_SCHEMA else None


def maps(root: Path) -> dict[str, dict]:
    folder = Path(root) / FOLDER
    found = {}
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        document = read_map(root, path.stem)
        if document:
            found[path.stem] = document
    return found


def _locked(root: Path, batch: str):
    folder = Path(root) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    held = root / "verification/.state"       # not beside the maps: a lock file there would be committed with them
    held.mkdir(parents=True, exist_ok=True)
    lock = open(held / f"batch-{batch}.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    return lock


def submit(manifest: dict, p, dry_run: bool = False) -> dict:
    """Write the batch's jobs and its map, or (dry run) say what would be written. What it did, row by row:
    `written`, `there` (the same work, already a job: left as it is) or `superseded` (the row's work changed: a new
    job, naming the old one). A second submission of the same manifest, at the same time or after a first one was
    killed, ends with the same files."""
    root = p.ROOT
    jobs = expand(manifest, p)          # the whole batch, before anything is written
    batch = manifest["batch"]
    lock = None if dry_run else _locked(root, batch)
    try:
        earlier = read_map(root, batch)
        if earlier and earlier.get("created") != manifest["created"]:
            raise Problem([f"batch {batch} was created {earlier.get('created')}, and this manifest says {manifest['created']}: "
                           f"it is another batch (give it another name), or the manifest's `created` was changed (put it back)"])
        rows, report = dict((earlier or {}).get("rows") or {}), []
        for job in jobs:
            row, work = job["batch"]["row"], job["batch"]["work"]
            had = rows.get(row)
            if had and had["work"] == work:
                # The row's work is what it was. Its current job may be a later one with the same work (a resubmission).
                report.append({"row": row, "job": had["current"], "did": "there"})
                continue
            path = p.layout.find_job(root, job["id"]) or p.layout.new_job(root, job["id"])
            if had:
                job["supersedes"] = had["current"]
            there = None
            if path.exists():
                try:
                    there = json.loads(path.read_text())
                except ValueError:
                    raise Problem([f"row {row}: {path.relative_to(root)} is there and is not JSON"])
                if (there.get("batch") or {}) != job["batch"]:
                    raise Problem([f"row {row}: {path.relative_to(root)} is there and is another job's"])
            if there is None and not dry_run:
                p.write_json(path, p.ordered({"$schema": p.schema_ref(path, "job.schema.json", True), **job}))
            history = [*((had or {}).get("history") or []),
                       {"job": job["id"], "work": work, "why": "the row's work changed" if had else "submitted"}]
            rows[row] = {"current": job["id"], "work": work, "history": history}
            report.append({"row": row, "job": job["id"], "did": "superseded" if had else ("there" if there is not None else "written"),
                           **({"supersedes": had["current"]} if had else {})})
        order = [j["batch"]["row"] for j in jobs]
        gone = [row for row in rows if row not in order]
        document = {"schema": MAP_SCHEMA, "batch": batch, "title": manifest.get("title"), "created": manifest["created"],
                    "manifest": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                    "rows": {row: rows[row] for row in order + gone},
                    # A row the manifest no longer has keeps its jobs and its history here: nothing is withdrawn silently.
                    **({"withdrawn": sorted(gone)} if gone else {})}
        if not dry_run:
            p.write_json(map_path(root, batch), document)
        return {"batch": batch, "created": manifest["created"], "map": map_path(root, batch).relative_to(root).as_posix(),
                "rows": report, "jobs": [rows[row]["current"] for row in order], "withdrawn": sorted(gone)}
    finally:
        if lock:
            lock.close()


def follow(root: Path, p, old_job: dict, new_id: str, why: str) -> bool:
    """A job of a batch was replaced by another with the same work (`resubmit`): the row's current job is the new
    one, and its history says why it came. Whether the old job was a batch's row's current job."""
    of = old_job.get("batch") or {}
    if not read_map(root, of.get("id") or ""):
        return False
    lock = _locked(root, of["id"])
    try:
        document = read_map(root, of["id"])
        row = (document or {}).get("rows", {}).get(of.get("row"))
        if not row or row["current"] != old_job.get("id"):
            return False
        row["history"] = [*row["history"], {"job": new_id, "work": row["work"], "why": why}]
        row["current"] = new_id
        p.write_json(map_path(root, of["id"]), document)
        return True
    finally:
        lock.close()


def view(document: dict, jobs_by_id: dict) -> dict:
    """What became of every row of a batch (`itl-job-batch-view/v1`), from its map and the lifecycle view's rows by
    job id: the row's current job with its state, its reason and its result's status, and the jobs it had before.
    A row whose job nobody can find is `missing`, and counted as that."""
    rows, counts, statuses = [], {}, {}
    for name, entry in document["rows"].items():
        job = jobs_by_id.get(entry["current"])
        state = job["state"] if job else "missing"
        result = (job or {}).get("result") or {}
        row = {"row": name, "job": entry["current"], "state": state,
               "why": job.get("why") if job else "no such job in the queue's commits or in the working copy",
               "status": result.get("status"), "fulfillment": (result.get("fulfillment") or {}).get("state"),
               "attempts": len((job or {}).get("attempts") or []),
               "history": [{**h, "state": (jobs_by_id.get(h["job"]) or {}).get("state", "missing"),
                            "status": ((jobs_by_id.get(h["job"]) or {}).get("result") or {}).get("status")}
                           for h in entry["history"]],
               "withdrawn": name in (document.get("withdrawn") or [])}
        rows.append(row)
        counts[state] = counts.get(state, 0) + 1
        if row["status"]:
            statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    unsettled = [r["row"] for r in rows if r["state"] not in SETTLED]
    return {"schema": VIEW_SCHEMA, "batch": document["batch"], "title": document.get("title"), "created": document.get("created"),
            "totals": {"unit": "rows", "of": len(rows), "byState": counts, "byStatus": statuses,
                       "withResult": sum(statuses.values())},
            "settled": not unsettled, "unsettled": unsettled, "rows": rows}
