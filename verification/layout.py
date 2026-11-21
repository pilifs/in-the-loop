#!/usr/bin/env python3
"""Where a verification job's specification and its result are kept, by job id.

Every job until now is flat: `verification/jobs/ID.json` and `verification/results/ID/`. Two folders that gain a
few hundred entries a day outgrow what a forge will list and what a reader can scan, so a job may instead be kept
under the UTC day it was submitted, which its id begins with:

    verification/jobs/YYYY/MM/DD/ID.json        verification/results/YYYY/MM/DD/ID/

An id that does not begin with a date goes to the one overflow shard, `undated/`.

A job is written once and never moved. The runner tests the commit that last touched a job's specification when the
job names no revision, so moving a pending job would silently change the code it tests; and the older jobs' paths
are linked from commits, notes and reports. Readers therefore take both layouts, through this module and nothing
else: by id (`find_job`, `find_result`), all of them (`jobs`, `results`), or from a listing of a commit's tree
(`job_id_of`, `result_id_of`), which is how results recorded on other heads are recognised. A result goes beside
its job: flat for a flat job, in the shard for a sharded one.

One id in both layouts: when the two copies are the same bytes the flat one is used, always; when they differ,
the flat one is still what readers get, and `conflicts` reports the id, since two records of one job cannot both
be right.

`WRITE` says where a *new* job goes. It is "flat" until the readers that are not in this repository's tools have
been checked against shards; `VERIFY_LAYOUT=shards` (or `flat`) overrides it for one command.

Standard library only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

JOBS = "verification/jobs"
RESULTS = "verification/results"
WRITE = "flat"
UNDATED = "undated"
_DAY = re.compile(r"^(\d{4})(\d{2})(\d{2})(?=-)")
_SHARD = r"(?:(\d{4}/\d{2}/\d{2}|" + UNDATED + r")/)?"
_JOB = re.compile(rf"^{JOBS}/{_SHARD}([^/]+)\.json$")
_RESULT = re.compile(rf"^{RESULTS}/{_SHARD}([^/]+)/(.+)$")


def writes() -> str:
    asked = os.environ.get("VERIFY_LAYOUT")
    return asked if asked in ("flat", "shards") else WRITE


def shard(job_id: str) -> str:
    """The shard of a job id: the UTC day its id begins with, or the overflow shard."""
    m = _DAY.match(job_id)
    if m and 1 <= int(m[2]) <= 12 and 1 <= int(m[3]) <= 31:
        return f"{m[1]}/{m[2]}/{m[3]}"
    return UNDATED


def job_rel(job_id: str, layout: str = "flat") -> str:
    return f"{JOBS}/{job_id}.json" if layout == "flat" else f"{JOBS}/{shard(job_id)}/{job_id}.json"


def result_rel(job_id: str, layout: str = "flat") -> str:
    return f"{RESULTS}/{job_id}" if layout == "flat" else f"{RESULTS}/{shard(job_id)}/{job_id}"


def job_id_of(path: str) -> str | None:
    """The job whose specification a repository path is, in either layout; None for any other path."""
    m = _JOB.match(path)
    if not m or (m[1] and m[1] != shard(m[2])):
        return None
    return m[2]


def result_id_of(path: str) -> tuple[str, str] | None:
    """(job id, path inside its result folder) for a repository path under a result, in either layout."""
    m = _RESULT.match(path)
    if not m:
        return None
    if m[1] is None and re.fullmatch(r"\d{4}|" + UNDATED, m[2]):
        return None  # a shard's own folder, not a job called 2026
    if m[1] and m[1] != shard(m[2]):
        return None
    return m[2], m[3]


def recorded(paths) -> set[str]:
    """The jobs a listing of repository paths (a commit's tree, say) holds a result.json of."""
    found = (result_id_of(p) for p in paths)
    return {f[0] for f in found if f and f[1] == "result.json"}


def find_job(root: Path, job_id: str) -> Path | None:
    for layout in ("flat", "shards"):
        path = Path(root) / job_rel(job_id, layout)
        if path.is_file():
            return path
    return None


def find_result(root: Path, job_id: str) -> Path | None:
    """The folder of a job's result here (the one that holds result.json), or None."""
    for layout in ("flat", "shards"):
        path = Path(root) / result_rel(job_id, layout)
        if (path / "result.json").is_file():
            return path
    return None


def new_job(root: Path, job_id: str) -> Path:
    """Where a job's specification is written: where it already is, else by the layout new jobs take."""
    return find_job(root, job_id) or Path(root) / job_rel(job_id, writes())


def new_result(root: Path, job_id: str) -> Path:
    """Where a job's result is written: where one already is, else beside its job, else by the layout new jobs take."""
    here = find_result(root, job_id)
    if here is not None:
        return here
    job = find_job(root, job_id)
    layout = writes() if job is None else "flat" if job.parent == Path(root) / JOBS else "shards"
    return Path(root) / result_rel(job_id, layout)


def _shards(base: Path):
    """The shard folders under a base, oldest first: YYYY/MM/DD and the overflow shard."""
    if not base.is_dir():
        return
    for year in sorted(p for p in base.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}", p.name)):
        for month in sorted(p for p in year.iterdir() if p.is_dir() and re.fullmatch(r"\d{2}", p.name)):
            yield from sorted(p for p in month.iterdir() if p.is_dir() and re.fullmatch(r"\d{2}", p.name))
    if (base / UNDATED).is_dir():
        yield base / UNDATED


def jobs(root: Path) -> dict[str, Path]:
    """Every job specification here, by id, in id order. A job in both layouts is its flat copy."""
    base, found = Path(root) / JOBS, {}
    for folder in _shards(base):
        for path in folder.glob("*.json"):
            if job_id_of(path.relative_to(root).as_posix()):
                found[path.stem] = path
    if base.is_dir():
        for path in base.glob("*.json"):
            found[path.stem] = path
    return dict(sorted(found.items()))


def results(root: Path) -> dict[str, Path]:
    """Every result folder here that holds a result.json, by job id, in id order. A job in both layouts is its flat one."""
    base, found = Path(root) / RESULTS, {}
    for folder in _shards(base):
        for path in folder.iterdir():
            if (path / "result.json").is_file() and shard(path.name) == folder.relative_to(base).as_posix():
                found[path.name] = path
    if base.is_dir():
        for path in base.iterdir():
            if (path / "result.json").is_file() and not re.fullmatch(r"\d{4}|" + UNDATED, path.name):
                found[path.name] = path
    return dict(sorted(found.items()))


def conflicts(root: Path) -> list[str]:
    """What is wrong between the two layouts: an id whose flat and sharded records differ. Identical copies are
    not a problem, only a duplicate; they are resolved to the flat one."""
    problems = []
    for job_id in sorted(p.stem for folder in _shards(Path(root) / JOBS) for p in folder.glob("*.json")):
        flat, sharded = Path(root) / job_rel(job_id), Path(root) / job_rel(job_id, "shards")
        if flat.is_file() and sharded.is_file() and flat.read_bytes() != sharded.read_bytes():
            problems.append(f"job {job_id}: {job_rel(job_id)} and {job_rel(job_id, 'shards')} differ; readers use the flat one")
    for folder in _shards(Path(root) / RESULTS):
        for path in sorted(folder.iterdir()):
            flat = Path(root) / result_rel(path.name) / "result.json"
            if flat.is_file() and (path / "result.json").is_file() and flat.read_bytes() != (path / "result.json").read_bytes():
                problems.append(f"result {path.name}: {result_rel(path.name)} and {result_rel(path.name, 'shards')} differ; "
                                "readers use the flat one")
    return problems
