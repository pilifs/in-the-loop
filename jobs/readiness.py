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
`level` asked for (`configures` < `resolves` < `builds` < `tests-run` < `readable`; at `tests-run` the offline run
must leave evidence of tests that executed, by `task.tests`), the `base` it is laid over (prepared inputs on the
runner, with `without`, and `asOf` for everything written after a time, to reconstruct an earlier state of them), where the consumer finds
the result (`view.env`; `view.walk` names folders a tool walks, laid file by file), the `repositories` a discovered Maven coordinate may come from, the `pinned` inputs it
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
lacks), `no-progress` (it asks again for what it was given), `round-limit`, `output-mismatch`, `tests-not-shown`
(it ran through at the level `tests-run` and nothing shows a test that executed). Only a ready
resolution publishes: staging is renamed into the store in one step, and a failed one leaves the store as it was.

A file fetched and verified once is kept in the store's pool by the address it came from. Another resolution that
needs it takes it from there, verified again, and does not ask the source: its receipt counts it as reused.

Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
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
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402
import sandbox  # noqa: E402

OPERATION = "itl-readiness-operation/v1"
RECEIPT = "itl-readiness-receipt/v1"
LEVELS = ("configures", "resolves", "builds", "tests-run", "readable")
FOLDER = "verification/readiness"                   # where a request's operation is committed, by key
NOT_IDENTITY = ("title", "consumer", "requestedBy", "resources", "rounds")  # who asks and what it may cost to prepare, not what is asked
# What a build tool says when it lacks a module, as group:artifact:version. Gradle: "Could not find g:a:v.",
# "Could not download a-v.pom (g:a:v): No cached version available for offline mode" (what S48's first replay
# said of its BOM), "No cached version of g:a:v available for offline mode". Maven: "Could not find artifact
# g:a:jar:v", "the artifact g:a:jar:v has not been downloaded from it before".
# The third group is what follows group and artifact: `1.0` (Gradle), `jar:1.0` or `jar:tests:1.0` (Maven: a type, and
# a classifier before the version). The version is its last part.
_GAV = r"([A-Za-z0-9_.\-]+):([A-Za-z0-9_.\-]+):((?:[A-Za-z0-9_.\-]+:){0,2}[A-Za-z0-9_.\-]+)"
# A Gradle plugin asked for by its id is a module by convention: ID:ID.gradle.plugin:VERSION, its marker.
PLUGIN = re.compile(r"Plugin \[id: '([A-Za-z0-9_.\-]+)', version: '([A-Za-z0-9_.\-]+)'\] was not found")
MISSING = [re.compile(p) for p in (
    r"Could not (?:find|resolve|transfer)(?: artifact)? " + _GAV,
    r"Failure to find " + _GAV,
    r"[Cc]ould not resolve plugin artifact '" + _GAV + "'",
    r"\(" + _GAV + r"\): No cached version available for offline mode",
    r"Could not find \S+ \(" + _GAV + r"\)",          # Gradle, of one file of a module whose POM it has: "Could not find a-v.jar (g:a:v)."
    r"No cached version of " + _GAV + r" available for offline mode",
    r"the artifact " + _GAV + r" has not been downloaded",
)]


# A file of a module, named by the tool that lacks it: Gradle's "Could not find netty-x-4.2-linux-x86_64.jar (g:a:v)."
# and "Could not download a-v-tests.jar (g:a:v): No cached version available for offline mode". A module's POM, its
# Gradle metadata and its main JAR come with the module; this is how any other file of it (a classifier's, a
# variant's) is asked for.
MISSING_FILE = re.compile(r"Could not (?:find|download|get resource) ([A-Za-z0-9_.+\-]+\.[A-Za-z][A-Za-z0-9]*) \(" + _GAV + r"\)")


def _named(text: str):
    """(group, artifact, version, type or None, classifier or None) for each module a log names as missing. A line
    whose coordinate has an empty part ("Could not find g:a:.", of a version a BOM would have given) names none."""
    for pattern in MISSING:
        for m in pattern.finditer(text):
            group, artifact, rest = (part.rstrip(".") for part in m.groups())
            parts = rest.split(":")
            if group and artifact and all(parts):
                yield (group, artifact, parts[-1], parts[0] if len(parts) > 1 else None, parts[1] if len(parts) > 2 else None)
    for m in PLUGIN.finditer(text):
        yield (m[1], m[1] + ".gradle.plugin", m[2], "pom", None)


def missing_coordinates(text: str) -> list[tuple]:
    """The modules a log says it could not get, each once, as (group, artifact, version)."""
    return sorted({found[:3] for found in _named(text)})


def missing_files(text: str) -> list[tuple]:
    """The files of a module a log names as not found, each once, as (group, artifact, version, file name): the ones
    a tool names by their file, and what Maven names by a classifier or by a type that is neither jar nor pom."""
    by_name = {(*(part.rstrip(".") for part in m.groups()[1:4]), m[1]) for m in MISSING_FILE.finditer(text)
               if all(part.rstrip(".") for part in m.groups()[1:3]) and ":" not in m[4].rstrip(".")}
    by_kind = {(g, a, v, f"{a}-{v}{'-' + classifier if classifier else ''}.{kind}") for g, a, v, kind, classifier in _named(text)
               if kind and (classifier or kind not in ("jar", "pom"))}
    return sorted(by_name | by_kind)


def parent_of(pom: str) -> tuple | None:
    """The parent a POM names, as (group, artifact, version): no tool reads the POM without it. None when it has
    none, or names it through a property."""
    m = re.search(r"<parent>(.*?)</parent>", re.sub(r"<!--.*?-->", "", pom, flags=re.S), re.S)
    if not m:
        return None
    part = lambda tag: (re.search(rf"<{tag}>\s*([^<\s]+)\s*</{tag}>", m[1]) or [None, None])[1]
    found = (part("groupId"), part("artifactId"), part("version"))
    return found if all(found) and not any("$" in x for x in found) else None


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def key(operation: dict) -> str:
    identity = {k: v for k, v in operation.items() if k not in NOT_IDENTITY}
    if isinstance(identity.get("base"), dict):      # why a base is laid as it is, is prose: a corrected sentence is not another request
        identity["base"] = {k: v for k, v in identity["base"].items() if k != "why"}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


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
    base = operation.get("base") if isinstance(operation.get("base"), dict) else {}
    as_of = base.get("asOf")
    if as_of is not None:
        try:
            zoned = dt.datetime.fromisoformat(str(as_of.get("time")).replace("Z", "+00:00")).tzinfo is not None
        except (ValueError, AttributeError):
            zoned = False
        if not zoned or not isinstance(as_of.get("under"), list) or not as_of.get("under"):
            found.append("base.asOf needs a `time` with its zone (2026-11-27T09:00:00Z) and the folders `under` which it holds")
    # Every path an operation names is laid inside a view or a staging folder: none may lead out of it.
    reads = operation.get("reads") or []
    whole = lambda r: isinstance(r, str) and r.startswith(("/", "~/"))                    # noqa: E731
    with_digest = lambda r: isinstance(r, dict) and whole(r.get("path")) and set(r) <= {"path", "sha256"} \
        and re.fullmatch(r"[0-9a-f]{64}", str(r.get("sha256") or ""))                       # noqa: E731
    if not isinstance(reads, list) or not all(whole(r) or with_digest(r) for r in reads):
        found.append("`reads` lists whole paths on the runner that the task reads beside its base (a JDK): each begins with / or ~/, "
                     "alone or as {\"path\", \"sha256\"} with the digest it must have (readiness.py digest PATH prints it)")
    named = [*(base.get("without") or []), *((as_of or {}).get("under") or [] if isinstance(as_of, dict) else []),
             *((operation.get("view") or {}).get("walk") or []), (operation.get("layout") or {}).get("maven", "m2"),
             *(pin.get("path") or "" for pin in operation.get("pinned") or [])]
    for path in named:
        if not isinstance(path, str) or path.startswith("/") or any(part in ("", ".", "..") for part in path.rstrip("/").split("/")):
            found.append(f"a path is relative to the base and stays inside it: {path!r}")
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


def reads_of(operation: dict) -> list[dict]:
    """What the operation says its task reads beside the base, each as {"path"} or {"path", "sha256"}. A bare path
    is declared and no more (a JDK the machine provides); one with a digest is an input, and is read in full against
    it before the task runs (`check_reads`)."""
    return [{"path": r} if isinstance(r, str) else dict(r) for r in operation.get("reads") or []]


def read_digest(path: Path) -> tuple[str, int, int]:
    """The digest a `reads` entry names, with the files and the bytes it covers. Of a file, the SHA-256 of its
    bytes. Of a folder, that of the list of its files by relative path, each with its own SHA-256, as a bundle's
    digest is made. A link is listed by where it points and not followed: in the task's sandbox it leads only to
    what is bound there, which is declared in its own right."""
    if not path.is_dir():
        return digest(path), 1, path.stat().st_size
    rows, size = [], 0
    for folder, names, files in os.walk(path):
        for name in (*files, *(n for n in names if (Path(folder) / n).is_symlink())):
            p = Path(folder) / name
            if p.is_symlink():
                rows.append((p.relative_to(path), "link:" + os.readlink(p)))
            elif p.is_file():
                rows.append((p.relative_to(path), digest(p)))
                size += p.stat().st_size
    rows.sort()
    return hashlib.sha256(json.dumps([[rel.as_posix(), d] for rel, d in rows]).encode()).hexdigest(), len(rows), size


def check_reads(operation: dict) -> list[dict]:
    """Each thing the task reads beside its base, as it is on this runner now: whether it was verified, and
    against which digest. Raises Withheld at the stage `base`: `absent` when one is not there, `digest-mismatch`
    when one is not what the operation names."""
    reads = reads_of(operation)
    gone = [r["path"] for r in reads if not Path(r["path"]).expanduser().exists()]
    if gone:
        raise Withheld("base", "absent", f"what the operation says its task reads is not on this runner: {', '.join(str(Path(p).expanduser()) for p in gone)}")
    found = []
    for read in reads:
        if not read.get("sha256"):
            found.append({"path": read["path"], "verified": False})
            continue
        got, files, size = read_digest(Path(read["path"]).expanduser())
        if got != read["sha256"]:
            raise Withheld("base", "digest-mismatch", f"{read['path']} is not what the operation says its task reads: its digest is {got} "
                                                      f"({files} file(s), {size} bytes), and the operation names {read['sha256']}")
        found.append({"path": read["path"], "verified": True, "sha256": got, "files": files, "bytes": size})
    return found


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

    def pooled(self, url: str) -> tuple[Path, dict] | None:
        """A file this runner fetched from `url` before and verified, with what was recorded of it, when its bytes
        are still those: else nothing, and it is fetched again."""
        name = hashlib.sha256(url.encode()).hexdigest()
        path = self.root / "pool" / name[:2] / name
        try:
            record = json.loads(path.with_name(name + ".json").read_text())
            if record.get("url") == url and digest(path) == record.get("sha256"):
                return path, record
        except (OSError, ValueError):
            pass
        return None

    def pool(self, url: str, path: Path, verified_by: str) -> None:
        """Keep a verified file by the address it came from. Written beside and renamed, so two resolutions that
        fetch one file at once leave one whole copy."""
        name = hashlib.sha256(url.encode()).hexdigest()
        kept = self.root / "pool" / name[:2] / name
        kept.parent.mkdir(parents=True, exist_ok=True)
        tmp = kept.with_name(f".{name}.{secrets.token_hex(4)}")
        shutil.copyfile(path, tmp)
        record = {"url": url, "sha256": digest(tmp), "sha1": digest(tmp, "sha1"), "bytes": tmp.stat().st_size, "verifiedBy": verified_by, "at": now()}
        os.replace(tmp, kept)
        tmp = kept.with_name(f".{name}.json.{secrets.token_hex(4)}")
        tmp.write_text(json.dumps(record) + "\n")
        os.replace(tmp, kept.with_name(name + ".json"))

    def verify_once(self, k: str) -> list[str]:
        """`verify`, read in full only when the receipt or a file of the bundle changed since the last time (by
        size and time): the scheduler asks at every pass, and a bundle is hundreds of megabytes. Whoever hands a
        bundle to a job reads it in full (`verify`)."""
        folder = self.bundle(k)
        try:
            stat = self.receipt_path(k).stat()
            seen = [[self.receipt_path(k).name, stat.st_size, stat.st_mtime_ns]]
            for root, _, names in os.walk(folder):
                for name in sorted(names):
                    stat = os.lstat(os.path.join(root, name))
                    seen.append([os.path.relpath(os.path.join(root, name), folder), stat.st_size, stat.st_mtime_ns])
        except OSError:
            return self.verify(k)
        signature = hashlib.sha256(json.dumps(sorted(seen)).encode()).hexdigest()
        stamp = self.root / "verified" / f"{k}.json"
        try:
            kept = json.loads(stamp.read_text())
            if kept.get("signature") == signature:
                return kept["wrong"]
        except (OSError, ValueError, KeyError):
            pass
        wrong = self.verify(k)
        stamp.parent.mkdir(parents=True, exist_ok=True)
        tmp = stamp.with_name(f".{stamp.name}.{secrets.token_hex(4)}")
        tmp.write_text(json.dumps({"signature": signature, "wrong": wrong}) + "\n")
        os.replace(tmp, stamp)
        return wrong

    def check(self, k: str) -> dict:
        """What a key's receipt says to a job that needs it, in the scheduler's words."""
        receipt = self.receipt(k)
        if receipt is None:
            return {"state": "waiting", "why": f"readiness {k[:12]} has no receipt here yet"}
        if receipt.get("state") != "ready":
            return {"state": "failed", "why": f"readiness {k[:12]} was withheld at the {receipt.get('stage')} stage "
                                              f"({receipt.get('outcome')}): {receipt.get('why')}"}
        wrong = self.verify_once(k)
        if wrong:
            return {"state": "failed", "why": f"readiness {k[:12]}: {wrong[0]}; resolve it again"}
        return {"state": "satisfied", "why": f"readiness {k[:12]} is ready (resolved {receipt.get('at')})"}


def written_after(base: Path, under: list[str], when: float, by: str = "latest") -> list[str]:
    """Every file under the folders `under` of the base that was written after `when`; a folder whose files were
    all written after it is named whole, and the folders `under` themselves stay. A file's time is the later of
    its content's (mtime) and its entry's (ctime): Maven gives a downloaded file the time its repository says it
    was last modified, years before it arrived, and the entry's time cannot be set back. `by: mtime` goes by the
    content's alone, for a base that was copied since (a copy gives every entry the time of the copy)."""
    out = []
    time_of = (lambda st: st.st_mtime) if by == "mtime" else (lambda st: max(st.st_mtime, st.st_ctime))

    def visit(folder: Path, rel: str) -> tuple[bool, list[str]]:
        newer, kept = [], False
        for child in sorted(os.scandir(folder), key=lambda e: e.name):
            here = f"{rel}/{child.name}"
            if child.is_dir(follow_symlinks=False):
                whole, inner = visit(Path(child.path), here)
                if whole:
                    newer.append(here)
                else:
                    kept = True
                    out.extend(inner)
            elif time_of(child.stat(follow_symlinks=False)) > when:
                newer.append(here)
            else:
                kept = True
        return bool(newer) and not kept, newer

    for root in under:
        root = root.strip("/")
        if (base / root).is_dir():
            out.extend(visit(base / root, root)[1])
    return sorted(out)


def left_out(operation: dict) -> list[str]:
    """The paths of its base an operation's view is laid without: the ones it lists (`base.without`), and with
    `base.asOf` everything under the folders it names that was written after its time. The second is how an
    earlier state of a cache is said in one line, when a later pass added a thousand modules to it; it goes by the
    files' own times, which is as good as nobody having touched them since."""
    base = operation["base"]
    without = list(base.get("without") or [])
    if base.get("asOf"):
        when = dt.datetime.fromisoformat(base["asOf"]["time"].replace("Z", "+00:00")).timestamp()
        without += written_after(Path(base["path"]).expanduser(), base["asOf"]["under"], when, base["asOf"].get("by", "latest"))
    return without


def laid_without(operation: dict) -> dict:
    """What a receipt says of how its base was laid, and what a later view of it is compared with."""
    listed = list(operation["base"].get("without") or [])
    without = left_out(operation)
    return {"without": without, "listed": listed, "leftOut": len(without) - len(listed),
            "digest": hashlib.sha256(json.dumps(without[len(listed):]).encode()).hexdigest()}


def drift(receipt: dict) -> str | None:
    """Why a view laid now would not be the one the receipt's resolution ran on, or None: with `base.asOf`, a
    file whose time changed since moves in or out of the earlier state."""
    was = ((receipt.get("base") or {}).get("asOf") or {})
    if not was:
        return None
    now_ = laid_without(receipt["operation"])
    return None if now_["digest"] == was.get("digest") else \
        f"the base's earlier state (asOf {was.get('time')}) leaves out {now_['leftOut']} path(s) now and left out {was.get('leftOut')} when it was resolved"


def overlay(base: Path, without: list[str], files: dict[str, Path], dest: Path, walk=()) -> Path:
    """A view of the base with `files` laid over it and the `without` paths absent, as symbolic links. A folder on
    the way to something laid over or left out is made here, with a link for each thing in it; every other folder
    is one link, so a base of many gigabytes costs a few hundred links. A folder named in `walk` is laid file by
    file all the way down, for a tool that walks a tree and does not follow a linked folder. A `without` path
    that ends in a slash leaves an empty folder in its place (a temporary folder of the view's own)."""
    dest.mkdir(parents=True, exist_ok=True)
    special = {p.strip("/") for p in [*without, *files]}
    walked = {p.strip("/") for p in walk}
    on_the_way = {s[:i] for s in special for i, c in enumerate(s) if c == "/"}.__contains__

    def lay(folder: Path, rel: str, deep: bool) -> None:
        for child in sorted(folder.iterdir()):
            here = f"{rel}/{child.name}" if rel else child.name
            if here in special:
                continue                       # left out, or laid over below
            if child.is_symlink() and child.is_dir() and on_the_way(here):
                raise Withheld("base", "linked-folder", f"{here} in the base is a link to a folder, and something under it is to be laid "
                                                         "over or left out: that would be done to the folder it links to")
            if child.is_dir() and not child.is_symlink() and (deep or here in walked or on_the_way(here)):
                (dest / here).mkdir(exist_ok=True)
                lay(child, here, deep or here in walked)
            else:
                (dest / here).symlink_to(child)
    if base.is_dir():
        lay(base, "", False)
    for path in without:
        if path.endswith("/"):
            (dest / path.strip("/")).mkdir(parents=True, exist_ok=True)
    for rel, source in files.items():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).symlink_to(source)
    return dest


class Withheld(Exception):
    """A resolution that cannot go on: the stage, the named outcome, and why."""

    def __init__(self, stage: str, outcome: str, why: str, asked: str | None = None) -> None:
        super().__init__(why)
        self.stage, self.outcome, self.why = stage, outcome, why
        self.asked = asked        # for `unauthorized-source`: the URL that was asked for and may not be fetched


def authorise(url: str, allow: list[str]) -> None:
    """Raises unless `url` is under a source the runner allows: the same scheme, host and port, a path under the
    source's as a folder, no user part and no `..`. `https://repo.example.org` does not allow `repo.example.org.evil`."""
    asked = urlsplit(url)

    def under(source: str) -> bool:
        allowed = urlsplit(source)
        folder = allowed.path if allowed.path.endswith("/") else allowed.path + "/"
        try:
            same = (asked.scheme, asked.hostname, asked.port) == (allowed.scheme, allowed.hostname, allowed.port)
        except ValueError:
            return False
        return same and asked.username is None and asked.path.startswith(folder) and ".." not in asked.path.split("/")
    if not any(under(source) for source in allow):
        raise Withheld("fetch", "unauthorized-source", f"{url} is not under a source this runner may fetch from ({', '.join(allow) or 'none'})", asked=url)


def asks_of(operation: dict) -> list[dict]:
    """The sources an operation's own words say a resolution of it fetches from: each repository, and each pinned
    input that the view will not have (the base lacks it, or it is under a path the operation leaves out)."""
    base = Path((operation.get("base") or {}).get("path") or "/nowhere").expanduser()
    without = [w.strip("/") for w in (operation.get("base") or {}).get("without") or []]
    out = [{"url": url, "for": "a repository"} for url in operation.get("repositories") or []]
    for pin in operation.get("pinned") or []:
        rel = str(pin.get("path") or "").strip("/")
        if pin.get("url") and (not (base / rel).exists() or any(rel == w or rel.startswith(w + "/") for w in without)):
            out.append({"url": pin["url"], "for": f"the pinned input {rel}"})
    return out


def not_allowed(operation: dict, allow: list[str]) -> list[dict]:
    """Of the sources an operation asks for (`asks_of`), those this runner may not fetch from. A resolution of it
    would be withheld as `unauthorized-source` at its first fetch from one: said before it is admitted, it is a
    question for whoever decides what the machine fetches from, and no job is spent on it."""
    out = []
    for ask in asks_of(operation):
        try:
            authorise(ask["url"], allow)
        except Withheld:
            out.append(ask)
    return out


class _EveryHop(HTTPRedirectHandler):
    """A source that redirects is followed only to an address that is itself allowed."""

    def __init__(self, allow: list[str]) -> None:
        self.allow = allow

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        authorise(newurl, self.allow)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str, dest: Path, allow: list[str], timeout: float = 120) -> int:
    """One file from an authorised source, with no proxy. Raises Withheld with `unauthorized-source`,
    `absent` (the source answers and does not have it) or `repository-unavailable`."""
    authorise(url, allow)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.part")
    try:
        with build_opener(ProxyHandler({}), _EveryHop(allow)).open(url, timeout=timeout) as response, open(tmp, "wb") as out:
            shutil.copyfileobj(response, out)
    except Withheld:
        tmp.unlink(missing_ok=True)
        raise
    except urllib.error.HTTPError as e:
        e.close()
        tmp.unlink(missing_ok=True)
        if e.code in (404, 410):
            raise Withheld("fetch", "absent", f"{url}: HTTP {e.code}") from None
        raise Withheld("fetch", "repository-unavailable", f"{url}: HTTP {e.code}") from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        tmp.unlink(missing_ok=True)
        if isinstance(getattr(e, "reason", e), FileNotFoundError):     # a repository that is a folder (file://), and has no such file
            raise Withheld("fetch", "absent", f"{url}: no such file") from None
        raise Withheld("fetch", "repository-unavailable", f"{url}: {getattr(e, 'reason', e)}") from None
    os.replace(tmp, dest)
    return dest.stat().st_size


def fetch_file(url: str, staging: Path, rel: str, allow: list[str], store: Store | None = None) -> dict:
    """A repository's file into staging with the repository's own SHA-1 beside it, and the record of it. Taken from
    the store's pool when this runner fetched it from that address before (its bytes checked against what was
    recorded then), and kept there once verified."""
    authorise(url, allow)
    started = time.monotonic()
    dest = staging / rel
    kept = store.pooled(url) if store else None
    if kept:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kept[0], dest)
        dest.with_name(dest.name + ".sha1").write_text(kept[1]["sha1"] + "\n")
        return {"path": rel, "source": url, "bytes": kept[1]["bytes"], "verifiedBy": kept[1]["verifiedBy"], "reused": True,
                "seconds": round(time.monotonic() - started, 3)}
    size = download(url, dest, allow)
    try:
        try:
            download(url + ".sha1", staging / (rel + ".sha1"), allow)
        except Withheld as e:
            if e.outcome == "absent":      # the file is there and nothing vouches for it: said, not passed over as if it were not there
                raise Withheld("fetch", "unverifiable", f"{url} is in the repository with no .sha1 beside it: nothing vouches for it") from None
            raise
        expected = ((staging / (rel + ".sha1")).read_text(errors="replace").split() or [""])[0].lower()
        if digest(dest, "sha1") != expected:
            raise Withheld("fetch", "digest-mismatch", f"{url} is not what the repository's own .sha1 says")
    except Withheld:
        # Staging holds verified files and nothing else: whatever is there when the task has run through is published.
        dest.unlink(missing_ok=True)
        (staging / (rel + ".sha1")).unlink(missing_ok=True)
        raise
    if store:
        store.pool(url, dest, "the repository's sha1")
    return {"path": rel, "source": url, "bytes": size, "verifiedBy": "the repository's sha1", "seconds": round(time.monotonic() - started, 3)}


def _from_first(coordinate: tuple, repositories: list[str], fetch) -> list[dict]:
    """What `fetch(repository address)` gets from the first repository that has it. `absent` only when every
    repository answered and none has it; a repository that could not be asked makes the answer
    `repository-unavailable`."""
    said = []
    for repository in repositories:
        try:
            return fetch(repository.rstrip("/") + "/")
        except Withheld as e:
            if e.outcome not in ("absent", "repository-unavailable"):
                raise
            said.append(e)
    if not said:
        raise Withheld("fetch", "absent", f"{':'.join(coordinate)}: the operation names no repository to ask")
    worst = next((e for e in said if e.outcome == "repository-unavailable"), said[0])
    raise Withheld("fetch", worst.outcome, f"{':'.join(coordinate)}: " + "; ".join(e.why for e in said))


def fetch_coordinate(coordinate: tuple, repositories: list[str], staging: Path, under: str, allow: list[str], store: Store | None = None) -> list[dict]:
    """A Maven module's POM, its Gradle module metadata when the POM says it was published with it (Gradle then
    refuses the POM alone), and its JAR when it is not a POM-only module, from the first repository that has it,
    each verified against the repository's own SHA-1."""
    group, artifact, version = coordinate
    stem = f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}"

    def fetch(base: str) -> list[dict]:
        got, wanted = [], [".pom"]
        while wanted:
            suffix = wanted.pop(0)
            rel = f"{under}/{stem}{suffix}"
            try:
                got.append(fetch_file(base + stem + suffix, staging, rel, allow, store))
            except Withheld as e:
                if suffix != ".pom" and e.outcome == "absent":
                    (staging / rel).unlink(missing_ok=True)
                    continue       # a module with a POM and no JAR (a BOM, a parent), or with no metadata of Gradle's after all
                raise
            if suffix == ".pom":
                pom = (staging / rel).read_text(errors="replace")
                wanted += [".module"] * ("published-with-gradle-metadata" in pom) + [".jar"] * ("<packaging>pom</packaging>" not in pom)
        return got
    return _from_first(coordinate, repositories, fetch)


def fetch_named(named: tuple, repositories: list[str], staging: Path, under: str, allow: list[str], store: Store | None = None) -> list[dict]:
    """One file of a module that a tool named (a classifier's JAR, a variant's), from the first repository that
    has it, verified as every other."""
    group, artifact, version, name = named
    folder = f"{group.replace('.', '/')}/{artifact}/{version}/"
    return _from_first(named[:3], repositories, lambda base: [fetch_file(base + folder + name, staging, f"{under}/{folder}{name}", allow, store)])


def fetch_pinned(pin: dict, staging: Path, allow: list[str], store: Store | None = None) -> dict:
    kind = "sha512" if pin.get("sha512") else "sha256"
    started = time.monotonic()
    authorise(pin["url"], allow)
    kept = store.pooled(pin["url"]) if store else None
    if kept and digest(kept[0], kind) != pin[kind].lower():
        kept = None                        # what the pool has from that address is not what this operation pins: the source is asked
    if kept:
        (staging / pin["path"]).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kept[0], staging / pin["path"])
        size = kept[1]["bytes"]
    else:
        size = download(pin["url"], staging / pin["path"], allow)
    if digest(staging / pin["path"], kind) != pin[kind].lower():
        (staging / pin["path"]).unlink()
        raise Withheld("fetch", "digest-mismatch", f"{pin['url']} is not the {kind} the operation pins for {pin['path']}")
    if store and not kept:
        store.pool(pin["url"], staging / pin["path"], f"an operation's {kind}")
    return {"path": pin["path"], "source": pin["url"], "bytes": size, "verifiedBy": f"the operation's {kind}", **({"reused": True} if kept else {}),
            "seconds": round(time.monotonic() - started, 3)}


# For a Gradle build run offline on a view. A module the resolver fetched is laid in Maven's layout, which Gradle's own
# cache is not: Gradle offline reads a remote repository's modules only from that cache, with its own records of
# them. A file repository is read whatever --offline says, so this gives every project, every build script's class
# path and the plugin resolution one over the modules a resolution fetched, ahead of the build's own repositories
# (first, so that it also answers for a module whose record in Gradle's cache names a repository that no longer
# has the file there). Over the fetched modules alone, each whole (POM, module metadata, JAR), and not over the
# view's whole Maven-layout folder: that one holds the base's Maven local repository, where a module is often a
# POM with no JAR, and Gradle, having read such a POM there first, looks for the JAR nowhere else (the first run
# of the gate for this script failed so, on a module Gradle's own cache had whole). A build that keeps its repositories in its settings gets it there, and its projects are
# left alone, since such a build may refuse a repository a project adds. A build that declares no plugin
# repository keeps Gradle's default beside this one. Plugins of the settings script itself are resolved before
# this runs, and are not served.
GRADLE_INIT = '''// Laid in every readiness view by jobs/readiness.py. Use: gradle --offline -I "$ITL_READINESS_GRADLE_INIT" ...
def laid = System.getenv('ITL_READINESS_FETCHED_M2')
if (laid && new File(laid).isDirectory()) {
    def readiness = { repositories ->
        if (repositories.findByName('itlReadiness') == null) {
            def repository = repositories.maven {
                name = 'itlReadiness'
                url = new File(laid).toURI()
                metadataSources { gradleMetadata(); mavenPom(); artifact() }
            }
            repositories.remove(repository)
            repositories.addFirst(repository)
        }
    }
    settingsEvaluated { settings ->
        def plugins = settings.pluginManagement.repositories
        if (plugins.isEmpty()) {
            plugins.gradlePluginPortal()
        }
        readiness(plugins)
        def managed = settings.dependencyResolutionManagement.repositories
        if (managed.isEmpty()) {
            gradle.allprojects { project ->
                readiness(project.buildscript.repositories)
                readiness(project.repositories)
            }
        } else {
            readiness(managed)
            gradle.allprojects { project -> readiness(project.buildscript.repositories) }
        }
    }
}
'''


def equip(view: Path, operation: dict, files: dict | None = None) -> dict:
    """What a step that runs on a view is told beside the view, as environment: where modules are laid in Maven's
    layout (ITL_READINESS_M2: the base's and the fetched ones, one folder, for a Maven build), the fetched ones
    alone in the same layout (ITL_READINESS_FETCHED_M2, a folder of links made here from `files`, the fetched files
    by their path in the view), and a Gradle init script, written into the view, that lets an offline Gradle
    build read the fetched ones."""
    maven = (operation.get("layout") or {}).get("maven", "m2").strip("/")
    fetched = view / "itl-readiness-fetched"
    fetched.mkdir(exist_ok=True)
    for rel, source in (files or {}).items():
        if rel.startswith(maven + "/"):
            link = fetched / rel[len(maven) + 1:]
            link.parent.mkdir(parents=True, exist_ok=True)
            if not link.is_symlink() and not link.exists():
                link.symlink_to(source)
    init = view / "itl-readiness.init.gradle"
    init.write_text(GRADLE_INIT)
    return {"ITL_READINESS_M2": str(view / maven), "ITL_READINESS_FETCHED_M2": str(fetched), "ITL_READINESS_GRADLE_INIT": str(init)}


def run_consumer(operation: dict, view: Path, out: Path, cwd: Path, log: Path, base: Path, extra_ro=(), fetched=None) -> tuple[bool, list[dict], dict]:
    """The operation's task with no network and the base read-only: whether every step exited 0, each
    step's record, and what a probe saw in the sandbox it ran in. A step that fails ends the run, unless the
    task says its steps are `independent` (one a pin): then each runs, and a round learns what every one lacks."""
    seen = sandbox.probe()
    if not seen["enforced"]:
        raise Withheld("consumer", "offline-unenforceable", f"the network cannot be taken away here: {seen.get('why')}")
    reads = [Path(r["path"]).expanduser() for r in reads_of(operation)]
    gone = [str(p) for p in reads if not p.exists()]
    if gone:
        raise Withheld("base", "absent", f"what the operation says its task reads is not on this runner: {', '.join(gone)}")
    scratch = out.parent / "scratch"      # the task's own, from round to round: a build's compiled scripts, never its inputs
    scratch.mkdir(exist_ok=True)
    # Prepared inputs alone: an empty home and an empty /tmp for this run, its own folders to write in, and the
    # base, what is staged and the tools the operation declares (`reads`) to read. Nothing else under the home.
    box, tmp = sandbox.alone(out.parent / "box" / out.name, [cwd, out.parent], [view, base, *extra_ro, *reads])
    seen["alone"] = {"home": "empty, of this run", "tmp": "empty, of this run", "reads": [str(p) for p in (base, *extra_ro, *reads)]}
    env = {**sandbox.clean(os.environ, Path("/tmp")), **(operation["task"].get("env") or {}),
           (operation.get("view") or {}).get("env", "ITL_READINESS_VIEW"): str(view), "ITL_READINESS_VIEW": str(view),
           "ITL_READINESS_OUT": str(out), "ITL_READINESS_SCRATCH": str(scratch), **equip(view, operation, fetched)}
    steps, ok = [], True
    with open(log, "a") as sink:
        for step in operation["task"]["steps"]:
            started = time.monotonic()
            sink.write(f"--- {step.get('name') or step['run'][:60]}\n")
            sink.flush()
            try:
                code = subprocess.run([*box, "bash", "-c", step["run"]], cwd=cwd / (operation["task"].get("cwd") or "."),
                                      env=env, stdout=sink, stderr=subprocess.STDOUT, timeout=float(operation["task"].get("timeout") or 3600)).returncode
            except subprocess.TimeoutExpired:
                code = 124
            steps.append({"name": step.get("name"), "run": step["run"], "exitCode": code, "seconds": round(time.monotonic() - started, 1)})
            if code != 0:
                ok = False
                if not operation["task"].get("independent"):
                    break
    shutil.rmtree(out.parent / "box" / out.name, ignore_errors=True)       # the run's home and /tmp: nothing of them is a result
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
    own, for the views, the consumer's outputs and its logs. One resolution of a key at a time on a store: a
    second waits, and then finds the first one's receipt, which it does not write over when it is ready."""
    lock = store.root / "locks" / f"{key(operation)}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        return _resolve(operation, store, cwd, work, allow, by)


def _resolve(operation: dict, store: Store, cwd: Path, work: Path, allow: list[str], by: dict | None) -> dict:
    k = key(operation)
    base = Path(operation["base"]["path"]).expanduser()
    listed = list(operation["base"].get("without") or [])
    laid_as = laid_without(operation) if base.is_dir() else {"without": listed, "leftOut": 0, "digest": None}
    without = laid_as["without"]
    as_of = operation["base"].get("asOf")
    earlier = store.receipt(k)
    receipt = {"schema": RECEIPT, "key": k, "operation": operation, "level": operation["level"], "state": "failed", "stage": None,
               "outcome": None, "why": None, "bundle": None, "offline": None, "rounds": [], "fetch": {"files": 0, "bytes": 0, "seconds": 0.0},
               # A base laid without some of its paths is said: it is not the base as it stands. Whether that is a state
               # the base was ever in is the operation's to say (`base.why`); the receipt repeats it and claims nothing.
               "base": {"path": str(base), "without": listed, "reconstructed": bool(without),
                        **({"asOf": {**as_of, "leftOut": laid_as["leftOut"], "digest": laid_as["digest"]}} if as_of else {}),
                        **({"why": operation["base"]["why"]} if operation["base"].get("why") else {})},
               "reads": [], "resolvedBy": {**(by or {}), "host": socket.gethostname()}, "startedAt": now(), "at": None,
               "attempts": [*((earlier or {}).get("attempts") or []),
                            *([{k2: earlier.get(k2) for k2 in ("state", "stage", "outcome", "at", "resolvedBy")}] if earlier else [])]}
    if earlier and earlier.get("state") == "ready" and not store.verify(k):
        return {**earlier, "reused": True}       # already certified, and its bundle is what it was: nothing to do
    staging = store.root / "staging" / f"{k[:16]}-{secrets.token_hex(4)}"
    staging.mkdir(parents=True)
    work.mkdir(parents=True, exist_ok=True)
    staged, modules = [], set()
    repositories, under = operation.get("repositories") or [], (operation.get("layout") or {}).get("maven", "m2").strip("/")

    def module(coordinate: tuple) -> list[dict]:
        """A module, and the parents its POM names (a POM cannot be read without them), as far up as a
        repository has them. A parent no repository here has is left to the task to ask for: the base may hold it."""
        got = fetch_coordinate(coordinate, repositories, staging, under, allow, store)
        modules.add(coordinate)
        child = coordinate
        for _ in range(12):
            pom = next((staging / f["path"] for f in got if f["path"].endswith(f"{child[1]}-{child[2]}.pom")), None)
            parent = parent_of(pom.read_text(errors="replace")) if pom else None
            if not parent or parent in modules:
                break
            try:
                more = fetch_coordinate(parent, repositories, staging, under, allow, store)
            except Withheld as e:
                if e.outcome not in ("absent", "repository-unavailable", "unverifiable"):
                    raise
                break
            modules.add(parent)
            got += [{**f, "for": f"the parent of {':'.join(child)}"} for f in more]
            child = parent
        return got

    try:
        if not base.is_dir():
            raise Withheld("base", "absent", f"the base {base} is not on this runner")
        # What the task reads beside the base is read against its digest once, before the first round runs on it.
        receipt["reads"] = check_reads(operation)
        # A pinned input is fetched when the view will not have it: the base lacks it, or it is under a path left out.
        gone = lambda path: any(path.strip("/") == w.strip("/") or path.strip("/").startswith(w.strip("/") + "/") for w in without)
        need = [("pinned", pin) for pin in operation.get("pinned") or [] if gone(pin["path"]) or not (base / pin["path"]).exists()]
        for pin in operation.get("pinned") or []:      # one the base holds is the pinned one, or the base is not what the operation says
            kind = "sha512" if pin.get("sha512") else "sha256"
            if ("pinned", pin) not in need and digest(base / pin["path"], kind) != pin[kind].lower():
                raise Withheld("base", "digest-mismatch", f"{pin['path']} in the base is not the {kind} the operation pins")
        limit = int(operation.get("rounds") or 5)
        for n in range(1, limit + 2):
            entry = {"n": n, "fetched": [], "missing": [], "result": None, "offlineSeconds": None}
            receipt["rounds"].append(entry)
            nowhere = []
            for kind, item in need:
                try:
                    got = [fetch_pinned(item, staging, allow, store)] if kind == "pinned" else module(item) if kind == "module" else \
                        fetch_named(item, repositories, staging, under, allow, store)
                except Withheld as e:
                    if kind == "pinned" or e.outcome != "absent":
                        raise
                    nowhere.append(e)      # one line of a log read as a module no source has: the others may be all the task lacks
                    continue
                entry["fetched"] += got
                staged += got
            if nowhere:
                entry["absent"] = [e.why for e in nowhere]
                if not entry["fetched"]:
                    raise nowhere[0]
            view, out, log = work / f"view-{n}", work / f"out-{n}", work / f"consumer-{n}.log"
            laid = {f["path"]: staging / f["path"] for f in staged}
            laid.update({rel + ".sha1": staging / (rel + ".sha1") for rel in list(laid) if (staging / (rel + ".sha1")).exists()})   # beside what they vouch for
            overlay(base, without, laid, view, walk=(operation.get("view") or {}).get("walk") or [])
            out.mkdir(exist_ok=True)
            started = time.monotonic()
            ok, steps, seen = run_consumer(operation, view, out, cwd, log, base, extra_ro=[staging], fetched=laid)
            entry["offlineSeconds"] = round(time.monotonic() - started, 1)
            receipt["offline"] = {"network": seen, "steps": steps, "round": n, "log": str(log)}
            if ok:
                rows, wrong = check_outputs(operation, out, cwd)
                receipt["offline"]["outputs"] = rows
                if wrong:
                    raise Withheld("outputs", "output-mismatch", "; ".join(wrong))
                if operation["level"] == "tests-run":
                    # The level is shown, not said: a task that ran through and left no sign of a test is a build.
                    shown = evidence.tests(operation["task"].get("tests") or {}, out, log)
                    receipt["offline"]["evidence"] = {x: shown[x] for x in ("source", "reports", "runs", "executed", "failed", "errors", "skipped", "suites", "promised", "unmet", "why") if x in shown}
                    if shown["unmet"]:
                        raise Withheld("level", "tests-not-shown" if shown["executed"] < shown["promised"]["min"] else "tests-not-as-declared",
                                       "the task ran through, and at the level tests-run that is not enough: " + "; ".join(shown["unmet"]))
                entry["result"] = "passed"
                break
            entry["result"] = "failed"
            text = log.read_text(errors="replace")
            missing, named = missing_coordinates(text), missing_files(text)
            entry["missing"] = [":".join(m) for m in missing]
            if named:
                entry["missingFiles"] = [f"{':'.join(f[:3])} {f[3]}" for f in named]
            stopped = next(s for s in steps if s["exitCode"] != 0)
            if not missing and not named:
                raise Withheld("consumer", "undiagnosed", f"step {stopped['name'] or steps.index(stopped) + 1} exited {stopped['exitCode']} offline and "
                                                           f"named nothing it lacks: {' '.join(text.split()[-40:])[-400:]}")
            have = {f["path"] for f in staged}
            path_of = lambda f: f"{under}/{f[0].replace('.', '/')}/{f[1]}/{f[2]}/{f[3]}"
            # A module's own fetch brings its POM, its Gradle metadata and its main JAR: a file named beside them is
            # asked for by its name, and so is one of those three when the module is here and the file is not.
            with_module = lambda f: f[:3] not in modules and f[3] in {f"{f[1]}-{f[2]}{suffix}" for suffix in (".pom", ".module", ".jar")}
            tried = {":".join(m) for m in missing} & {why.split(": ")[0] for r in receipt["rounds"] for why in r.get("absent") or []}
            need = [("module", m) for m in missing if m not in modules and ":".join(m) not in tried] + \
                [("file", f) for f in named if path_of(f) not in have and not with_module(f)]
            if not need and tried:
                raise Withheld("fetch", "absent", "; ".join(why for r in receipt["rounds"] for why in r.get("absent") or [])[:600])
            if not need:
                # The usual cause: a second tool of the task reads another place than where the files were laid (S48's
                # first run: a POM laid in Maven's layout, and Gradle asking its own cache for it). Its line says which.
                said = next((line.strip() for line in reversed(text.splitlines()) if any(m[1] in line for m in [*missing, *named])), "")
                raise Withheld("consumer", "no-progress", f"it asks again for what it was given: {', '.join(entry['missing'] or entry.get('missingFiles') or [])}. The files are "
                                                           f"under {under}/ in Maven's layout, and what asks now does not read them there: {said[:300]}")
            if n > limit:
                raise Withheld("rounds", "round-limit", f"{limit} round(s) were not enough; still missing: {', '.join(entry['missing'] or entry.get('missingFiles') or [])}")
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
        receipt.update(state="failed", stage=e.stage, outcome=e.outcome, why=e.why, **({"asked": e.asked} if e.asked else {}))
        failed = store.root / "failed" / staging.name      # kept for whoever reads the diagnosis; never a bundle
        failed.parent.mkdir(parents=True, exist_ok=True)
        os.rename(staging, failed)
    fetched = [f for r in receipt["rounds"] for f in r["fetched"]]
    again = [f for f in fetched if f.get("reused")]      # taken from the pool: this runner had fetched and verified them before
    receipt["fetch"] = {"files": len(fetched), "bytes": sum(f["bytes"] for f in fetched), "seconds": round(sum(f["seconds"] for f in fetched), 3),
                        "reused": len(again), "reusedBytes": sum(f["bytes"] for f in again)}
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
    p = sub.add_parser("digest", help="the digest a `reads` entry names for a file or a folder")
    p.add_argument("path")
    p = sub.add_parser("status")
    p.add_argument("key")
    p.add_argument("--store", default=os.environ.get("ITL_READINESS_STORE") or "~/.cache/in-the-loop/readiness")
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(Store(Path(args.store)).check(args.key), indent=2))
        return 0
    if args.command == "digest":
        got, files, size = read_digest(Path(args.path).expanduser())
        print(json.dumps({"path": args.path, "sha256": got, "files": files, "bytes": size}))
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
