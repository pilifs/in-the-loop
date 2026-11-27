#!/usr/bin/env python3
"""Readiness: what a task needs prepared before it can run offline, resolved once, and proved by running it.

A case reaches a task its setup never exercised (VF-076: the Maven plugin's integration harness of Spring Boot
S48 took five rounds and six jobs to find a BOM and a Maven distribution). Here the consumer says what it needs
done, as an **operation**; a resolution job finds what is missing by running that very operation offline, fetches
only what the run asked for from the sources it is authorised to use, and publishes a **bundle** with a **receipt**
once the operation has run through with the network taken away. The consumer waits for the receipt and nothing else.

    python3 jobs/readiness.py key OPERATION.json        the operation's key
    python3 jobs/readiness.py resolve OPERATION.json    resolve it here: rounds, a bundle, a receipt (exit 1: withheld)
    python3 jobs/readiness.py status KEY                what the store has for a key

An operation (`itl-readiness-operation/v1`) binds what "ready" means: `describes` (project, revisions, module,
task, profiles, wrapper, toolchain, platform, configuration: anything that makes it another operation), the
`level` asked for (`configures` < `resolves` < `builds` < `tests-run` < `readable`), the `base` it is laid over
(prepared inputs on the runner, with `without` to reconstruct an earlier state of them), where the consumer finds
the result (`view.env`), the `repositories` a discovered Maven coordinate may come from, the `pinned` inputs it
declares with their digests (a tool distribution), the `task` (the original task's steps, as the consumer will
run them), and the `outputs` those must leave. Its key is the digest of all of that but the title and who asked
(`consumer`, `requestedBy`) and the estimate for the resolution job (`resources`): two cases that need the same
thing share one resolution, and another toolchain or profile is another key.

A resolution is rounds: lay the base and what is staged so far into a view, run the consumer in a network
namespace with loopback alone (jobs/sandbox.py) with the base read-only, and read its log for what it could not
find. Fetch that, verified (a repository's own checksum for a coordinate, the operation's digest for a pinned
input), into staging, and go again. It ends `ready` when the consumer ran through and its outputs are as
declared; else with the stage it stopped at and a named outcome: `absent` (no authorised source has it),
`digest-mismatch`, `repository-unavailable`, `unauthorized-source`, `undiagnosed` (it failed and named nothing it
lacks), `no-progress` (it asks again for what it was given), `round-limit`, `output-mismatch`. Only a ready
resolution publishes: staging is renamed into the store in one step, and a failed one leaves the store as it was.

Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sandbox  # noqa: E402

OPERATION = "itl-readiness-operation/v1"
RECEIPT = "itl-readiness-receipt/v1"
LEVELS = ("configures", "resolves", "builds", "tests-run", "readable")
FOLDER = "verification/readiness"                   # where a request's operation is committed, by key
NOT_IDENTITY = ("title", "consumer", "requestedBy", "resources")  # who asks and what it may cost to prepare, not what is asked
# What a build tool says when it lacks a module: Gradle's and Maven's lines, group:artifact:version.
COORDINATE = re.compile(r"Could not (?:find|resolve|transfer)(?: artifact)? ([A-Za-z0-9_.\-]+):([A-Za-z0-9_.\-]+):(?:[a-z\-]+:)?([A-Za-z0-9_.\-]+)")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def key(operation: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in operation.items() if k not in NOT_IDENTITY}, sort_keys=True).encode()).hexdigest()


def problems(operation: dict) -> list[str]:
    found = []
    if operation.get("schema") != OPERATION:
        found.append(f"schema is {operation.get('schema')!r}, not {OPERATION!r}")
    if not isinstance(operation.get("describes"), dict) or not operation.get("describes"):
        found.append("no `describes`: the revision, module, task and toolchain that make this operation this one")
    if operation.get("level") not in LEVELS:
        found.append(f"level {operation.get('level')!r} is not one of {', '.join(LEVELS)}")
    if not isinstance(operation.get("task"), dict) or not operation["task"].get("steps"):
        found.append("no task steps: the task itself, as the consumer runs it offline")
    if not isinstance((operation.get("base") or {}).get("path"), str):
        found.append("no base.path: the prepared inputs the bundle is laid over")
    for pin in operation.get("pinned") or []:
        if not pin.get("path") or not pin.get("url") or not (pin.get("sha256") or pin.get("sha512")):
            found.append(f"a pinned input needs a path, a url and a sha256 or sha512: {json.dumps(pin)[:120]}")
    return found


def digest(path: Path, kind: str = "sha256") -> str:
    h = hashlib.new(kind)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tree(folder: Path) -> list[dict]:
    return [{"path": p.relative_to(folder).as_posix(), "sha256": digest(p), "bytes": p.stat().st_size}
            for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "bundle.json"]


def tree_digest(files: list[dict]) -> str:
    return hashlib.sha256(json.dumps([[f["path"], f["sha256"]] for f in files]).encode()).hexdigest()


class Store:
    """Bundles and receipts on a runner, by key. A bundle is published by one rename and never written again."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser()

    def bundle(self, k: str) -> Path:
        return self.root / "bundles" / k

    def receipt_path(self, k: str) -> Path:
        return self.root / "receipts" / f"{k}.json"

    def receipt(self, k: str) -> dict | None:
        try:
            document = json.loads(self.receipt_path(k).read_text())
        except (OSError, ValueError):
            return None
        return document if document.get("schema") == RECEIPT and document.get("key") == k else None

    def write_receipt(self, receipt: dict) -> None:
        path = self.receipt_path(receipt["key"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}")
        tmp.write_text(json.dumps(receipt, indent=2) + "\n")
        os.replace(tmp, path)

    def verify(self, k: str) -> list[str]:
        """What is wrong with a key's published bundle against its receipt, read in full: empty when the bytes
        are the ones the receipt names. A bundle that changed since, or is not there, is not handed to anyone."""
        receipt = self.receipt(k)
        if not receipt or receipt.get("state") != "ready":
            return ["no ready receipt"]
        folder, named = self.bundle(k), receipt["bundle"]
        if not folder.is_dir():
            return [f"its bundle is not there ({folder})"]
        have = tree(folder)
        if tree_digest(have) != named["digest"]:
            was = {f["path"]: f["sha256"] for f in named["files"]}
            now_ = {f["path"]: f["sha256"] for f in have}
            changed = sorted(p for p in set(was) | set(now_) if was.get(p) != now_.get(p))
            return [f"its bundle is not what the receipt names: {', '.join(changed[:5])} differ, are missing or were added"]
        return []

    def check(self, k: str) -> dict:
        """What a key's receipt says to a job that needs it, in the scheduler's words."""
        receipt = self.receipt(k)
        if receipt is None:
            return {"state": "waiting", "why": f"readiness {k[:12]} has no receipt here yet"}
        if receipt.get("state") != "ready":
            return {"state": "failed", "why": f"readiness {k[:12]} was withheld at the {receipt.get('stage')} stage "
                                              f"({receipt.get('outcome')}): {receipt.get('why')}"}
        wrong = self.verify(k)
        if wrong:
            return {"state": "failed", "why": f"readiness {k[:12]}: {wrong[0]}; resolve it again"}
        return {"state": "satisfied", "why": f"readiness {k[:12]} is ready (resolved {receipt.get('at')})"}


def overlay(base: Path, without: list[str], files: dict[str, Path], dest: Path) -> Path:
    """A view of the base with `files` laid over it and the `without` paths absent, as symbolic links. A top-level
    folder that holds something laid over or left out is made of links file by file (a tool that walks a tree does
    not follow a linked folder); every other one is one link."""
    dest.mkdir(parents=True, exist_ok=True)
    special = {p.strip("/") for p in [*without, *files]}
    tops = {p.split("/", 1)[0] for p in special}

    def lay(folder: Path, rel: str) -> None:
        for child in sorted(folder.iterdir()) if folder.is_dir() else []:
            here = f"{rel}/{child.name}" if rel else child.name
            if here in special:
                continue                       # left out, or replaced below
            if child.is_dir() and not child.is_symlink():
                (dest / here).mkdir(exist_ok=True)
                lay(child, here)
            else:
                (dest / here).symlink_to(child)
    for child in sorted(base.iterdir()) if base.is_dir() else []:
        if child.name in tops and child.is_dir():
            (dest / child.name).mkdir(exist_ok=True)
            lay(child, child.name)
        elif child.name not in special:
            (dest / child.name).symlink_to(child)
    for rel, source in files.items():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).symlink_to(source)
    (dest / "tmp").mkdir(exist_ok=True) if not (dest / "tmp").exists() else None
    return dest


class Withheld(Exception):
    """A resolution that cannot go on: the stage, the named outcome, and why."""

    def __init__(self, stage: str, outcome: str, why: str) -> None:
        super().__init__(why)
        self.stage, self.outcome, self.why = stage, outcome, why


def download(url: str, dest: Path, allow: list[str], timeout: float = 120) -> int:
    """One file from an authorised source, with no proxy. Raises Withheld with `unauthorized-source`,
    `absent` (the source answers and does not have it) or `repository-unavailable`."""
    if not any(url.startswith(prefix) for prefix in allow):
        raise Withheld("fetch", "unauthorized-source", f"{url} is not under a source this runner may fetch from ({', '.join(allow) or 'none'})")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.part")
    try:
        with build_opener(ProxyHandler({})).open(url, timeout=timeout) as response, open(tmp, "wb") as out:
            shutil.copyfileobj(response, out)
    except urllib.error.HTTPError as e:
        tmp.unlink(missing_ok=True)
        if e.code in (404, 410):
            raise Withheld("fetch", "absent", f"{url}: HTTP {e.code}") from None
        raise Withheld("fetch", "repository-unavailable", f"{url}: HTTP {e.code}") from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        tmp.unlink(missing_ok=True)
        raise Withheld("fetch", "repository-unavailable", f"{url}: {getattr(e, 'reason', e)}") from None
    os.replace(tmp, dest)
    return dest.stat().st_size


def fetch_coordinate(coordinate: tuple, repositories: list[str], staging: Path, under: str, allow: list[str]) -> list[dict]:
    """A Maven module's POM (and its JAR, when it is not a POM-only module) from the first repository that has it,
    each verified against the repository's own SHA-1. `absent` only when every repository answered and none has
    it; a repository that could not be asked makes the answer `repository-unavailable`."""
    group, artifact, version = coordinate
    stem = f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}"
    said, got = [], []
    for repository in repositories:
        base = repository.rstrip("/") + "/"
        try:
            for suffix in (".pom", ".jar"):
                rel = f"{under}/{stem}{suffix}"
                started = time.monotonic()
                try:
                    size = download(base + stem + suffix, staging / rel, allow)
                    download(base + stem + suffix + ".sha1", staging / (rel + ".sha1"), allow)
                except Withheld as e:
                    if suffix == ".jar" and e.outcome == "absent":
                        break          # a module with a POM and no JAR: a BOM, a parent
                    raise
                expected = (staging / (rel + ".sha1")).read_text().split()[0].lower()
                if digest(staging / rel, "sha1") != expected:
                    raise Withheld("fetch", "digest-mismatch", f"{base + stem + suffix} is not what the repository's own .sha1 says")
                got.append({"path": rel, "source": base + stem + suffix, "bytes": size, "verifiedBy": "the repository's sha1",
                            "seconds": round(time.monotonic() - started, 3)})
                if suffix == ".pom" and "<packaging>pom</packaging>" in (staging / rel).read_text(errors="replace"):
                    break
            return got
        except Withheld as e:
            if e.outcome not in ("absent", "repository-unavailable"):
                raise
            said.append(e)
    if not said:
        raise Withheld("fetch", "absent", f"{':'.join(coordinate)}: the operation names no repository to ask")
    worst = next((e for e in said if e.outcome == "repository-unavailable"), said[0])
    raise Withheld("fetch", worst.outcome, f"{':'.join(coordinate)}: " + "; ".join(e.why for e in said))


def fetch_pinned(pin: dict, staging: Path, allow: list[str]) -> dict:
    kind = "sha512" if pin.get("sha512") else "sha256"
    started = time.monotonic()
    size = download(pin["url"], staging / pin["path"], allow)
    if digest(staging / pin["path"], kind) != pin[kind].lower():
        (staging / pin["path"]).unlink()
        raise Withheld("fetch", "digest-mismatch", f"{pin['url']} is not the {kind} the operation pins for {pin['path']}")
    return {"path": pin["path"], "source": pin["url"], "bytes": size, "verifiedBy": f"the operation's {kind}", "seconds": round(time.monotonic() - started, 3)}


def run_consumer(operation: dict, view: Path, out: Path, cwd: Path, log: Path, base: Path, extra_ro=()) -> tuple[bool, list[dict], dict]:
    """The operation's task with no network and the base read-only: whether every step exited 0, each
    step's record, and what a probe saw in the sandbox it ran in."""
    seen = sandbox.probe()
    if not seen["enforced"]:
        raise Withheld("consumer", "offline-unenforceable", f"the network cannot be taken away here: {seen.get('why')}")
    binds = [("ro", str(p), str(p)) for p in (base, *extra_ro) if Path(p).exists()]
    env = {**os.environ, (operation.get("view") or {}).get("env", "ITL_READINESS_VIEW"): str(view), "ITL_READINESS_VIEW": str(view),
           "ITL_READINESS_OUT": str(out)}
    steps, ok = [], True
    with open(log, "a") as sink:
        for step in operation["task"]["steps"]:
            started = time.monotonic()
            sink.write(f"--- {step.get('name') or step['run'][:60]}\n")
            sink.flush()
            try:
                code = subprocess.run([*sandbox.prefix(binds=binds), "bash", "-c", step["run"]], cwd=cwd / (operation["task"].get("cwd") or "."),
                                      env=env, stdout=sink, stderr=subprocess.STDOUT, timeout=float(operation["task"].get("timeout") or 3600)).returncode
            except subprocess.TimeoutExpired:
                code = 124
            steps.append({"name": step.get("name"), "run": step["run"], "exitCode": code, "seconds": round(time.monotonic() - started, 1)})
            if code != 0:
                ok = False
                break
    return ok, steps, seen


def check_outputs(operation: dict, out: Path, cwd: Path) -> tuple[list[dict], list[str]]:
    rows, wrong = [], []
    for spec in operation.get("outputs") or []:
        path = out / spec["path"]
        row = {"path": spec["path"], "sha256": digest(path) if path.is_file() else None}
        if not path.is_file():
            wrong.append(f"{spec['path']} was not written")
        elif spec.get("equalsJson"):
            row["equalsJson"] = spec["equalsJson"]
            try:
                same = json.loads(path.read_text()) == json.loads((cwd / spec["equalsJson"]).read_text())
            except (OSError, ValueError) as e:
                same = False
                row["problem"] = str(e)
            row["matches"] = same
            if not same:
                wrong.append(f"{spec['path']} is not what {spec['equalsJson']} records")
        elif spec.get("sha256"):
            row["matches"] = row["sha256"] == spec["sha256"]
            if not row["matches"]:
                wrong.append(f"{spec['path']} is not the bytes the operation names")
        rows.append(row)
    return rows, wrong


def resolve(operation: dict, store: Store, cwd: Path, work: Path, allow: list[str], by: dict | None = None) -> dict:
    """Resolve an operation here, and return its receipt (written to the store). `work`: a folder of this attempt's
    own, for the views, the consumer's outputs and its logs."""
    k = key(operation)
    base = Path(operation["base"]["path"]).expanduser()
    without = list(operation["base"].get("without") or [])
    earlier = store.receipt(k)
    receipt = {"schema": RECEIPT, "key": k, "operation": operation, "level": operation["level"], "state": "failed", "stage": None,
               "outcome": None, "why": None, "bundle": None, "offline": None, "rounds": [], "fetch": {"files": 0, "bytes": 0, "seconds": 0.0},
               # An earlier state of the base, reconstructed by leaving paths out, is said: it is not the base as it stands.
               "base": {"path": str(base), "without": without, "reconstructed": bool(without)},
               "resolvedBy": {**(by or {}), "host": socket.gethostname()}, "startedAt": now(), "at": None,
               "attempts": [*((earlier or {}).get("attempts") or []),
                            *([{k2: earlier.get(k2) for k2 in ("state", "stage", "outcome", "at", "resolvedBy")}] if earlier else [])]}
    if earlier and earlier.get("state") == "ready" and not store.verify(k):
        return {**earlier, "reused": True}       # already certified, and its bundle is what it was: nothing to do
    staging = store.root / "staging" / f"{k[:16]}-{secrets.token_hex(4)}"
    staging.mkdir(parents=True)
    work.mkdir(parents=True, exist_ok=True)
    staged, asked_before = [], set()
    try:
        if not base.is_dir():
            raise Withheld("base", "absent", f"the base {base} is not on this runner")
        need = [("pinned", pin) for pin in operation.get("pinned") or [] if pin["path"].strip("/") in {w.strip("/") for w in without} or not (base / pin["path"]).exists()]
        limit = int(operation.get("rounds") or 5)
        for n in range(1, limit + 2):
            entry = {"n": n, "fetched": [], "missing": [], "result": None, "offlineSeconds": None}
            receipt["rounds"].append(entry)
            for kind, item in need:
                got = [fetch_pinned(item, staging, allow)] if kind == "pinned" else \
                    fetch_coordinate(item, operation.get("repositories") or [], staging, (operation.get("layout") or {}).get("maven", "m2"), allow)
                entry["fetched"] += got
                staged += got
            view, out, log = work / f"view-{n}", work / f"out-{n}", work / f"consumer-{n}.log"
            overlay(base, without, {f["path"]: staging / f["path"] for f in staged}, view)
            for f in staged:   # the checksum files beside what they vouch for
                if (staging / (f["path"] + ".sha1")).exists() and not (view / (f["path"] + ".sha1")).exists():
                    (view / (f["path"] + ".sha1")).symlink_to(staging / (f["path"] + ".sha1"))
            out.mkdir(exist_ok=True)
            started = time.monotonic()
            ok, steps, seen = run_consumer(operation, view, out, cwd, log, base, extra_ro=[staging])
            entry["offlineSeconds"] = round(time.monotonic() - started, 1)
            receipt["offline"] = {"network": seen, "steps": steps, "round": n, "log": str(log)}
            if ok:
                rows, wrong = check_outputs(operation, out, cwd)
                receipt["offline"]["outputs"] = rows
                if wrong:
                    raise Withheld("outputs", "output-mismatch", "; ".join(wrong))
                entry["result"] = "passed"
                break
            entry["result"] = "failed"
            text = log.read_text(errors="replace")
            missing = sorted({tuple(part.rstrip(".") for part in m.groups()) for m in COORDINATE.finditer(text)})
            entry["missing"] = [":".join(m) for m in missing]
            if not missing:
                raise Withheld("consumer", "undiagnosed", f"step {steps[-1]['name'] or len(steps)} exited {steps[-1]['exitCode']} offline and "
                                                           f"named nothing it lacks: {' '.join(text.split()[-40:])[-400:]}")
            if set(missing) <= asked_before:
                raise Withheld("consumer", "no-progress", f"it asks again for what it was given: {', '.join(entry['missing'])}")
            if n > limit:
                raise Withheld("rounds", "round-limit", f"{limit} round(s) were not enough; still missing: {', '.join(entry['missing'])}")
            asked_before |= set(missing)
            need = [("coordinate", m) for m in missing]
        # Published in one step, read-only, and only now that the operation ran through without the network.
        files = tree(staging)
        named = {f["path"]: f for f in staged}
        manifest = {"key": k, "digest": tree_digest(files),
                    "files": [{**f, **{x: named[f["path"]][x] for x in ("source", "verifiedBy") if f["path"] in named}} for f in files]}
        (staging / "bundle.json").write_text(json.dumps(manifest, indent=2) + "\n")
        for path in staging.rglob("*"):
            if path.is_file():
                path.chmod(0o444)
        store.bundle(k).parent.mkdir(parents=True, exist_ok=True)
        if store.bundle(k).exists():   # a bundle the receipt no longer vouches for: set aside, never mixed with
            store.bundle(k).rename(store.root / "staging" / f"{k[:16]}-replaced-{secrets.token_hex(4)}")
        os.rename(staging, store.bundle(k))
        receipt.update(state="ready", outcome="ready", bundle={"path": str(store.bundle(k)), "digest": manifest["digest"], "files": manifest["files"]})
    except Withheld as e:
        receipt.update(state="failed", stage=e.stage, outcome=e.outcome, why=e.why)
        failed = store.root / "failed" / staging.name      # kept for whoever reads the diagnosis; never a bundle
        failed.parent.mkdir(parents=True, exist_ok=True)
        os.rename(staging, failed)
    fetched = [f for r in receipt["rounds"] for f in r["fetched"]]
    receipt["fetch"] = {"files": len(fetched), "bytes": sum(f["bytes"] for f in fetched), "seconds": round(sum(f["seconds"] for f in fetched), 3)}
    receipt["at"] = now()
    store.write_receipt(receipt)
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="readiness.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("key")
    p.add_argument("operation")
    p = sub.add_parser("resolve")
    p.add_argument("operation")
    p.add_argument("--store", default=os.environ.get("ITL_READINESS_STORE") or "~/.cache/in-the-loop/readiness")
    p.add_argument("--work", help="a folder for this attempt's views and logs (default: a new one under the store)")
    p.add_argument("--receipt", help="also write the receipt here (a job's declared output)")
    p = sub.add_parser("status")
    p.add_argument("key")
    p.add_argument("--store", default=os.environ.get("ITL_READINESS_STORE") or "~/.cache/in-the-loop/readiness")
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(Store(Path(args.store)).check(args.key), indent=2))
        return 0
    operation = json.loads(Path(args.operation).read_text())
    wrong = problems(operation)
    if wrong:
        sys.exit("not an operation:\n  " + "\n  ".join(wrong))
    if args.command == "key":
        print(key(operation))
        return 0
    store = Store(Path(args.store))
    work = Path(args.work) if args.work else store.root / "work" / f"{key(operation)[:16]}-{secrets.token_hex(4)}"
    allow = json.loads(os.environ.get("ITL_FETCH_ALLOW") or "[]")
    receipt = resolve(operation, store, Path.cwd(), work, allow, by={"job": os.environ.get("VERIFY_JOB_ID")})
    if args.receipt:
        Path(args.receipt).parent.mkdir(parents=True, exist_ok=True)
        public = {k: v for k, v in receipt.items()}
        Path(args.receipt).write_text(json.dumps(public, indent=2) + "\n")
    rounds = receipt["rounds"]
    print(f"readiness {receipt['key'][:12]}: {receipt['state']}" + (" (reused: already certified here)" if receipt.get("reused") else "") +
          (f" after {len(rounds)} round(s), {receipt['fetch']['files']} file(s) fetched" if not receipt.get("reused") else "") +
          (f"; withheld at the {receipt['stage']} stage ({receipt['outcome']}): {receipt['why']}" if receipt["state"] != "ready" else ""))
    return 0 if receipt["state"] == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())
