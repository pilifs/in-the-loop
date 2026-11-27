"""Every execution of a job, as a record of its own on the machine that ran it.

A job can run more than once: the runner was stopped, the machine ran short of memory, a person asked again. Each
run is an **attempt**, and each attempt gets, before it writes its first byte:

    STATE/attempts/JOB/NNN-TOKEN/
        attempt.json    who, when, at which commit; then how it ended, and what became of its bytes
        run/            the whole logs, the outputs it produced, the diff
        work/           the export of the commit that its steps ran in

Nothing is reused. Until 2026-11-27 every run of a job wrote into the same two folders, and a rerun cleared
them: the private archive was asked to keep the earlier attempt first, and when it could not (a full disk, a
journal that did not open), the attempt's bytes went with the folder. An attempt's folders now stay until a rule
releases them, and the record says which rule did:

  - a passed job's work directory is not an original (the archive keeps the logs, the outputs and the diff), and
    is released when the job ends;
  - anything else is released only by `prune`, once the job's result is collected, every original sealed from
    *this* attempt is verified in the store, and the folder still is what was sealed (`fingerprint`).

`capture` in the record says where the attempt's originals stand: `off` (nothing captures here), `sealed`,
`recovered` (sealed later, by `recover`), or `failed` with the reason. A `failed` one, and an attempt whose runner
died (`interrupted`), are what `recover` seals when the archive answers again, and what the audit lists until then.

The number is the one the archive has for the attempt when it could be asked, so `originals.attempt` in a receipt
and the folder agree; the id carries a token as well, since two checkouts of one machine number their attempts
apart when the archive cannot be asked.

Standard library only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import secrets
import shutil
import socket
import stat
from pathlib import Path

SCHEMA = "itl-job-attempt/v1"
FOLDER = "attempts"
RECORD = "attempt.json"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write_durably(path: Path, document: dict) -> None:
    """The record is on disk, and so is its name, before the caller goes on: an attempt that the machine loses
    power under is still an attempt somebody can find."""
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with open(tmp, "w") as f:
        f.write(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    try:
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def fingerprint(folder: Path) -> dict | None:
    """What a folder holds, from its entries' names, kinds, sizes and times alone (nothing is read): the digest of
    that list, and how many files and bytes. A folder that was changed, added to or emptied since it was sealed
    gives another digest, and is then not what the archive holds. None for a folder that is not there."""
    folder = Path(folder)
    if not folder.is_dir():
        return None
    h, files, total = hashlib.sha256(), 0, 0
    for base, dirs, names in os.walk(folder):
        dirs.sort()
        for name in sorted(dirs + names):
            full = Path(base) / name
            try:
                st = full.lstat()
            except OSError:
                continue
            rel = full.relative_to(folder).as_posix()
            if stat.S_ISLNK(st.st_mode):
                row = f"l {rel} {os.readlink(full)}"
            elif stat.S_ISDIR(st.st_mode):
                row = f"d {rel}"
            else:
                row = f"f {rel} {st.st_size} {st.st_mtime_ns}"
                files += 1
                total += st.st_size
            h.update(row.encode(errors="surrogateescape") + b"\n")
    return {"sha256": h.hexdigest(), "files": files, "bytes": total}


class Attempt:
    """One attempt's record and folders. Every change to the record is written at once."""

    def __init__(self, folder: Path, record: dict) -> None:
        self.folder, self.record = Path(folder), record

    id = property(lambda self: self.record["id"])
    job = property(lambda self: self.record["job"])
    number = property(lambda self: self.record["number"])
    run_dir = property(lambda self: self.folder / "run")
    work_dir = property(lambda self: self.folder / "work")

    def save(self, **changes) -> "Attempt":
        self.record.update(changes)
        write_durably(self.folder / RECORD, self.record)
        return self

    def finished(self, status: str | None) -> "Attempt":
        return self.save(state="finished", status=status, finishedAt=now())

    def captured(self, state: str, occurrences: dict | None = None, error: str | None = None, number: int | None = None) -> "Attempt":
        """Where the attempt's originals stand. With `sealed` or `recovered`, what each folder was when it was
        sealed, so that a later prune can tell the folder is still that."""
        capture = {"state": state, "at": now()}
        if occurrences:
            capture["occurrences"] = occurrences
        if number is not None:
            capture["attempt"] = number
        if error:
            capture["error"] = error
        if state in ("sealed", "recovered"):
            capture["fingerprints"] = {name: fingerprint(self.folder / name) for name in ("run", "work")}
        return self.save(capture=capture)

    def release(self, what: str, why: str) -> int:
        """Remove one of the attempt's folders ("run" or "work"), and say in its record that it went and by which
        rule. The bytes it freed."""
        folder = self.folder / what
        size = (fingerprint(folder) or {}).get("bytes", 0)
        shutil.rmtree(folder, ignore_errors=True)
        self.save(released=[*self.record.get("released", []), {"what": what, "at": now(), "why": why, "bytes": size}])
        return size

    def alive(self) -> bool:
        """Whether the runner that started the attempt is still there (on this host: another host's is not known)."""
        if self.record.get("state") != "running":
            return False
        if self.record.get("runnerHost") not in (None, socket.gethostname()):
            return True
        try:
            os.kill(int(self.record.get("pid") or 0), 0)
        except (ProcessLookupError, ValueError):
            return False
        except PermissionError:
            return True
        return bool(self.record.get("pid"))

    def state(self) -> str:
        """`running`, `finished`, or `interrupted`: started, never finished, and its runner is gone."""
        if self.record.get("state") == "running" and not self.alive():
            return "interrupted"
        return self.record.get("state") or "unknown"


def _folder(state_dir: Path, job_id: str) -> Path:
    return Path(state_dir) / FOLDER / job_id


def of(state_dir: Path, job_id: str) -> list[Attempt]:
    """A job's attempts on record here, oldest first. A folder whose record cannot be read is still an attempt:
    its bytes are there, and it is listed with what could be told."""
    found = []
    base = _folder(state_dir, job_id)
    for folder in sorted(base.iterdir()) if base.is_dir() else []:
        if not folder.is_dir():
            continue
        try:
            record = json.loads((folder / RECORD).read_text())
            if not isinstance(record, dict):
                raise ValueError("not an object")
        except (OSError, ValueError) as e:
            head = folder.name.split("-", 1)[0]
            record = {"schema": SCHEMA, "id": f"{job_id}.{folder.name}", "job": job_id,
                      "number": int(head) if head.isdigit() else 0, "state": "unknown", "unreadable": str(e)}
        found.append(Attempt(folder, record))
    return sorted(found, key=lambda a: (a.number, a.folder.name))


def every(state_dir: Path) -> list[Attempt]:
    base = Path(state_dir) / FOLDER
    return [a for job in sorted(base.iterdir()) if job.is_dir() for a in of(state_dir, job.name)] if base.is_dir() else []


def find(state_dir: Path, attempt_id: str) -> Attempt | None:
    job_id = attempt_id.rsplit(".", 2)[0] if attempt_id.count(".") >= 2 else attempt_id
    return next((a for a in of(state_dir, job_id) if a.id == attempt_id), None)


def next_number(state_dir: Path, job_id: str) -> int:
    """The number a job's next attempt has by the records here alone."""
    return max([a.number + 1 for a in of(state_dir, job_id)] + [1])


def begin(state_dir: Path, job_id: str, source: str | None, host: str, at_least: int = 0) -> Attempt:
    """A new attempt of a job: its number, its folders and its record, all on disk before this returns. The number
    is one more than the job's last here, and no less than `at_least` (the number the archive gave, when it could
    be asked; a run directory an older runner left sealed counts too)."""
    base = _folder(state_dir, job_id)
    base.mkdir(parents=True, exist_ok=True)
    earlier = of(state_dir, job_id)
    number = max([a.number + 1 for a in earlier] + [at_least, 1])
    while True:
        token = secrets.token_hex(3)
        folder = base / f"{number:03d}-{token}"
        try:
            folder.mkdir()
            break
        except FileExistsError:
            continue
    (folder / "run" / "logs").mkdir(parents=True)
    record = {"schema": SCHEMA, "id": f"{job_id}.{number:03d}.{token}", "job": job_id, "number": number, "token": token,
              "host": host, "runnerHost": socket.gethostname(), "pid": os.getpid(), "source": source,
              "startedAt": now(), "state": "running", "status": None, "finishedAt": None,
              "previous": earlier[-1].id if earlier else None,
              "capture": {"state": "pending"}, "released": []}
    return Attempt(folder, record).save()


def problems(attempt: Attempt | dict) -> list[dict]:
    """What the audit says of an attempt: bytes that only this machine holds and that the archive was meant to
    have, and a record that names a folder which is gone with no release on record."""
    if not isinstance(attempt, Attempt):
        return []
    record, found = attempt.record, []
    if record.get("unreadable"):
        return [{"kind": "attempt-record-unreadable", "level": "discrepancy",
                 "detail": f"{attempt.folder / RECORD} cannot be read ({record['unreadable']}); its folders are kept"}]
    state, capture = attempt.state(), (record.get("capture") or {}).get("state")
    if state == "interrupted" and capture in ("pending", "failed"):
        found.append({"kind": "attempt-interrupted-unsealed", "level": "gap",
                      "detail": f"attempt {attempt.id} never finished (its runner is gone) and nothing sealed it: its "
                                f"bytes are in {attempt.folder} and nowhere else; `recover` seals them"})
    elif state == "finished" and capture == "failed":
        found.append({"kind": "attempt-capture-failed", "level": "gap",
                      "detail": f"attempt {attempt.id} finished ({record.get('status')}) and its originals were not "
                                f"sealed ({(record.get('capture') or {}).get('error')}): its bytes are in "
                                f"{attempt.folder} and nowhere else; `recover` seals them"})
    released = {r["what"] for r in record.get("released") or []}
    for name in ("run", "work"):
        made = True if name == "run" else bool(record.get("prepared"))   # the work folder comes with the export
        if made and state != "running" and name not in released and not (attempt.folder / name).exists():
            found.append({"kind": "attempt-folder-gone", "level": "discrepancy",
                          "detail": f"attempt {attempt.id}: its {name} folder is gone and its record names no release"})
    return found
