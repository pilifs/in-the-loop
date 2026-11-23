"""`sync.py checkpoint`: put a committed revision on the remote `develop`, fast, from wherever work stands.

A checkpoint is a planning snapshot of the code: a remote commit another agent can read while this machine is
still at work. It is not a promotion (`sync.py push --bookmark main`): no default test run, no proof job, no trace
rendering, no log upload and no wait for the private uploader happen here, and nothing in the working copy is read
or written, so another session's uncommitted files stay exactly as they are.

What it does, in order:

  1. resolves REV once, to one committed revision, and reads the remote's `develop` and `main`;
  2. refuses unless `develop` can move forward to it (never a force, never another ref or remote);
  3. reads the git objects and commit messages the push would expose for the first time, through every outgoing
     commit and merge parent (a file deleted at the tip still travels in the parent that held it), and refuses on:
     an unresolved conflict; a raw payload path; an unsafe file name; a blob over the size limit; a credential, or
     this machine's own secrets or account identifiers, in any blob or message; anything the redactor would still
     change in a file the trace tools publish; a redaction decision no person or delegated watcher is recorded as
     having taken. A blob's verdict is kept by its git id and the policy, so the work grows with the new bytes
     (git names each new blob once, by the first path it has: content already on the remote is not new). A value
     the same file already holds on the remote is not new either: an edit to a test that carries a made-up
     credential does not expose it a second time;
  4. pushes exactly `SHA:refs/heads/develop` to `origin`, and if the answer is lost reads the remote before saying
     anything;
  5. writes a receipt outside the tree: the commits, the scan, and which evidence is public, which is pending
     (sealed on this machine only, or queued for upload) and which is verified in the private archive.

`sync.py checkpoint --bootstrap` creates `develop` where the remote `main` is, once.

The module is given sync.py's own module object (`s`), since sync.py runs as __main__.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

POLICY = 3           # bump when a rule below changes what is refused: every kept verdict is then worked out again
REMOTE, DEVELOP, MAIN = "origin", "develop", "main"
MAX_BLOB = 16 << 20  # a larger blob is refused: GitHub warns at 50 MiB and refuses at 100, and none here is meant to be near
RECEIPT_SCHEMA = "itl-checkpoint/v1"
# Publication summaries (llm-dlc/artifacts/) are written for the public: each gets the redactor's whole rule set, as
# a trace file does, and a size limit, so that an unbounded inventory cannot come back into git by this door.
SUMMARIES = "llm-dlc/artifacts/"
SUMMARY_MAX, CATALOG_MAX = 64 << 10, 256 << 10
# A gzip blob is read as what it opens to: a pack of per-case records (examples/tools/targets/case_pack.py) publishes
# every byte inside it, and the rules see none of them in the compressed form. One that opens to more than this is
# refused, since nothing read it. 512 MiB since 2026-11-23: the JBMC fast-follow's packaged-JBMC rows archive opens
# to 267 MiB of JSON (50-64 MiB per file), which is read in full in a few seconds within the watcher's memory cap.
OPENED_MAX = 512 << 20
UNREAD = "compressed-beyond-scan"
# Paths that hold raw payloads or private records and are never committed on purpose: each is gitignored, so one
# among the outgoing objects was forced in or came from a broken ignore file.
RAW_PATHS = [(re.compile(p), why) for p, why in (
    (r"^llm-dlc/traces/[^/]+/logs/", "a session's log snapshot (published through the CDN, never through git)"),
    (r"^llm-dlc/loop-summaries/", "a loop's private run record"),
    (r"^verification/\.state/", "the runner's state"),
    (r"(^|/)\.env(\.[^/]*)?$", "an environment file"),
    (r"(^|/)(r2-credentials|r2-originals-[^/]*|cloudflare-token)$", "a credential file"),
    (r"(^|/)originals/(spool|intake|tmp)/|(^|/)journal\.sqlite(-wal|-shm)?$", "the private archive's spool"),
    (r"(^|/)\.claude\.json$|(^|/)\.claude/projects/|(^|/)\.codex/(sessions|auth\.json)", "a client's own session store"),
)]
ENV_EXAMPLES = re.compile(r"(^|/)\.env\.(example|sample|template)$")
# Credential formats that are recognisable on sight and kinds that are real by construction (this machine's own
# secrets and account identifiers): refused in every outgoing blob and message. The redactor's other kinds are
# shaped by their context (KEY=value, user:password@host, a home directory) and match ordinary code and test
# fixtures, so they are refused only where the redactor's output is what is published: the trace files.
STRICT_KINDS = frozenset({
    "local-secret", "account-id", "anthropic-key", "langfuse-key", "api-key", "github-token", "gitlab-token", "aws-key",
    "google-key", "google-oauth", "slack-token", "slack-webhook", "discord-webhook", "npm-token", "huggingface-token",
    "stripe-key", "sendgrid-key", "private-key",
})
REFUSED_ARGS = ("--all", "--bookmark", "-b", "--remote", "--force", "-f", "--allow-backwards", "--tracked", "--deleted",
                "--mirror", "--tags", "--change", "-c", "--revisions", "-r", "--named", "--allow-new")


def jq(s, *args: str) -> subprocess.CompletedProcess:
    """jj without a snapshot of the working copy: nothing uncommitted here is read, recorded or moved."""
    return s.jj("--ignore-working-copy", *args)


def git(s, *args: str, data: bytes | None = None, timeout: float = 120) -> subprocess.CompletedProcess:
    started = time.perf_counter()
    try:
        return subprocess.run(["git", "-C", str(s.REPO), *args], input=data, capture_output=True, timeout=timeout)
    finally:
        s.perf.count(f"subprocess git {args[0]}")
        s.perf.count(f"subprocess git {args[0]} seconds", time.perf_counter() - started)


def remote_ref(s, name: str) -> str | None:
    """What the remote's branch points at now, asked of the remote. None when it has no such branch."""
    r = git(s, "ls-remote", REMOTE, f"refs/heads/{name}", timeout=60)
    if r.returncode:
        raise RuntimeError(f"cannot read {REMOTE}: {r.stderr.decode(errors='replace').strip()[:300]}")
    for line in r.stdout.decode().splitlines():
        sha, _, ref = line.partition("\t")
        if ref == f"refs/heads/{name}":
            return sha
    return None


def have(s, sha: str) -> bool:
    return git(s, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def is_ancestor(s, old: str, new: str) -> bool:
    return git(s, "merge-base", "--is-ancestor", old, new).returncode == 0


def resolve(s, rev: str) -> dict:
    """REV as one committed revision, or a ValueError saying why it is not one."""
    template = 'commit_id ++ "\\t" ++ change_id ++ "\\t" ++ empty ++ "\\t" ++ conflict ++ "\\t" ++ json(description) ++ "\\n"'
    r = jq(s, "log", "--no-graph", "-r", rev, "-T", template)
    rows = r.stdout.splitlines()
    if r.returncode or len(rows) != 1:
        raise ValueError(f"--rev {rev!r} must name exactly one revision" + (f": {r.stderr.strip()[:200]}" if r.returncode else f", and names {len(rows)}"))
    commit, change, empty, conflict, desc = rows[0].split("\t", 4)
    desc = json.loads(desc)
    if not desc.strip():
        raise ValueError(f"{rev} ({change[:12]}) has no description: it is uncommitted work, which stays local. Name a committed "
                         "revision, such as @- (its owner can commit it first with `sync.py commit --only PATH ...`)")
    return {"commit": commit, "change": change, "description": desc, "conflict": conflict == "true"}


def unsafe_name(path: str) -> str | None:
    if any(ord(c) < 32 or ord(c) == 127 for c in path):
        return "a control character in its name"
    if "\\" in path:
        return "a backslash in its name"
    try:
        path.encode("utf-8")
    except UnicodeEncodeError:
        return "a name that is not UTF-8"
    parts = path.split("/")
    if any(p in ("", ".", "..") or p.lower() == ".git" for p in parts):
        return "an empty, dot or .git component in its path"
    if any(len(p.encode()) > 255 for p in parts) or len(path.encode()) > 4096:
        return "a name longer than a file system takes"
    if any(p != p.rstrip(" .") for p in parts):
        return "a component ending in a space or a dot"
    return None


def path_problems(path: str) -> list[str]:
    problems = [f"is {why}" for pattern, why in RAW_PATHS if pattern.search(path) and not ENV_EXAMPLES.search(path)]
    if (bad := unsafe_name(path)):
        problems.append(f"has {bad}")
    return problems


class Verdicts:
    """What scanning a blob found, kept by its git id: a blob never changes, so neither does its verdict under
    the same policy, rules, literals and decisions. Holds kinds and counts, never a value."""

    def __init__(self, s, redact) -> None:
        self.path = s.STATE / "outgoing-verdicts.json"
        h = hashlib.sha256(f"{POLICY}\0{redact.fingerprint()}\0{sorted(STRICT_KINDS)}\0{OPENED_MAX}\0".encode())  # an unread blob is read again when the room grows
        # The decisions that waive a finding, not the files that hold them: a proposal changes no verdict.
        h.update(json.dumps([sorted(s.load_reviewed()), sorted(s.allowed_ids())]).encode())
        self.fingerprint = h.hexdigest()
        try:
            doc = json.loads(self.path.read_text())
        except (OSError, ValueError):
            doc = {}
        self.entries = doc.get("blobs", {}) if doc.get("fingerprint") == self.fingerprint else {}
        self.fresh = 0

    def save(self, s) -> None:
        if self.fresh:
            s.STATE.mkdir(parents=True, exist_ok=True)
            s.atomic_write(self.path, json.dumps({"fingerprint": self.fingerprint, "blobs": self.entries}, separators=(",", ":")), private=True)


def opened(data: bytes) -> bytes | None:
    """The bytes to scan for a blob: itself, or for a gzip blob what it opens to (every member, and whatever follows
    the last). None when that is more than OPENED_MAX. A blob that only begins like gzip is scanned as it is, after
    whatever of it did open."""
    if data[:2] != b"\x1f\x8b":
        return data
    parts, rest, room = [], data, OPENED_MAX
    try:
        while rest[:2] == b"\x1f\x8b":
            stream = zlib.decompressobj(16 + zlib.MAX_WBITS)
            part = stream.decompress(rest, room + 1)
            room -= len(part)
            if room < 0 or stream.unconsumed_tail:
                return None
            parts.append(part)
            if not stream.eof:
                return b"\n".join(parts)  # cut short: what there is of it
            rest = stream.unused_data
    except zlib.error:
        return b"\n".join([*parts, data])
    return b"\n".join([*parts, rest])


def content_kinds(s, redact, data: bytes, strict: bool) -> dict[str, int]:
    """The kinds the content is refused for, with how often each occurs."""
    data = opened(data)
    if data is None:
        return {UNREAD: 1}
    try:
        text = data.decode()
    except UnicodeDecodeError:
        text = data.decode(errors="replace")
    hits = redact.leak_hits(text)
    return {kind: sum(found.values()) for kind, found in sorted(hits.items()) if not strict or kind in STRICT_KINDS}


def findings(s, redact, data: bytes, strict: bool) -> set[tuple[str, str]]:
    """The (kind, value) pairs the content is refused for. Values stay in this process."""
    data = opened(data)
    if data is None:
        return {(UNREAD, hashlib.sha256(b"").hexdigest())}
    hits = redact.leak_hits(data.decode(errors="replace"))
    return {(kind, value) for kind, found in hits.items() if not strict or kind in STRICT_KINDS for value in found}


def carried(s, redact, oid: str, path: str, bases: list[str], strict: bool) -> bool:
    """Whether everything a blob is refused for is already in the same file at a base (the remote's `develop` or
    `main`): an edit elsewhere in a file that holds a made-up credential, as the redaction tests do, re-issues the
    file whole and exposes nothing that was not public before. A value the base's copy does not hold is new."""
    new = findings(s, redact, git(s, "cat-file", "blob", oid).stdout, strict)
    known: set[tuple[str, str]] = set()
    for base in bases:
        if base:
            r = git(s, "cat-file", "blob", f"{base}:{path}")
            if r.returncode == 0:
                known |= findings(s, redact, r.stdout, strict)
    return bool(new) and new <= known


def outgoing(s, target: str, bases: list[str]) -> tuple[list[str], list[tuple[str, int, str]]]:
    """(commits, blobs as (id, size, path)) that a push of `target` would expose and `bases` do not already hold.
    Every outgoing commit's tree is walked, merge parents included."""
    exclude = [b for b in bases if b]
    r = git(s, "rev-list", target, "--not", *exclude)
    if r.returncode:
        raise RuntimeError(f"git rev-list: {r.stderr.decode(errors='replace').strip()[:300]}")
    commits = r.stdout.decode().split()
    listed = git(s, "rev-list", "--objects", target, "--not", *exclude, timeout=600)
    sized = git(s, "cat-file", "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)", data=listed.stdout, timeout=600)
    blobs = []
    for line in sized.stdout.decode(errors="surrogateescape").splitlines():
        kind, oid, size, *path = line.split(" ", 3)
        if kind == "blob":
            blobs.append((oid, int(size), path[0] if path else ""))
    return commits, blobs


def scan(s, redact, commits: list[str], blobs: list[tuple[str, int, str]], target: str, bases: list[str]) -> tuple[list[str], dict]:
    """(problems, counts) for what a push would expose."""
    problems: list[str] = []
    verdicts = Verdicts(s, redact)
    stats = {"commits": len(commits), "blobs": len(blobs), "bytes": sum(b[1] for b in blobs), "scanned_blobs": 0,
             "scanned_bytes": 0, "kept_verdicts": 0, "carried": 0}
    todo, flagged = [], []
    for oid, size, path in blobs:
        for problem in path_problems(path):
            problems.append(f"{path}: {problem}")
        if size > MAX_BLOB:
            problems.append(f"{path}: is {size:,} bytes, over the {MAX_BLOB:,} a blob may be (blob {oid[:12]})")
            continue
        if path.startswith(SUMMARIES) and size > (CATALOG_MAX if path.rsplit("/", 1)[-1].startswith("catalog-") else SUMMARY_MAX):
            problems.append(f"{path}: is {size:,} bytes, over what a publication summary may be: its detail belongs in the private archive")
        key = f"{oid}:{'trace' if s.trace_owned(path) or path.startswith(SUMMARIES) else 'strict'}"
        if key in verdicts.entries:
            stats["kept_verdicts"] += 1
            if verdicts.entries[key]:
                flagged.append((oid, path, key))
        else:
            todo.append((oid, size, path, key))
    if todo:
        with s.perf.phase("scan outgoing blobs"):
            proc = subprocess.Popen(["git", "-C", str(s.REPO), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            import threading

            def feed() -> None:
                for oid, *_ in todo:
                    proc.stdin.write(oid.encode() + b"\n")
                proc.stdin.close()
            threading.Thread(target=feed, daemon=True).start()
            for oid, size, path, key in todo:
                header = proc.stdout.readline().split()
                data = proc.stdout.read(int(header[2]))
                proc.stdout.read(1)
                found = content_kinds(s, redact, data, strict=not key.endswith(":trace"))
                verdicts.entries[key] = found
                verdicts.fresh += 1
                stats["scanned_blobs"] += 1
                stats["scanned_bytes"] += size
                if found:
                    flagged.append((oid, path, key))
            proc.wait()
        verdicts.save(s)
    for oid, path, key in flagged:
        if carried(s, redact, oid, path, bases, strict=not key.endswith(":trace")):
            stats["carried"] += 1
        else:
            problems.append(f"{path}: holds {_kinds(verdicts.entries[key])} (blob {oid[:12]})")
    if commits:
        log = git(s, "log", "--no-walk=unsorted", "--format=%H%x00%B%x00%x01", *commits[:5000])
        for entry in log.stdout.decode(errors="replace").split("\x01"):
            sha, _, message = entry.strip("\n").partition("\0")
            message = message.rstrip("\0")
            if not sha:
                continue
            if not message.strip():
                problems.append(f"commit {sha[:12]}: has no message")
            elif message.startswith("wip: another session's files"):
                problems.append(f"commit {sha[:12]}: is files `sync.py commit --only` set aside, not a commit of anyone's work")
            if any(ord(c) < 32 and c not in "\n\t" for c in message):
                problems.append(f"commit {sha[:12]}: has a control character in its message")
            if found := content_kinds(s, redact, message.encode(), strict=True):
                problems.append(f"commit {sha[:12]}: its message holds {_kinds(found)}")
        exclude = " | ".join(f"::{b}" for b in bases if b) or "none()"
        conflicted = jq(s, "log", "--no-graph", "-r", f"(::{target} ~ ({exclude})) & conflicts()", "-T", 'change_id.short(12) ++ "\\n"')
        for change in conflicted.stdout.split():
            problems.append(f"change {change}: holds an unresolved conflict")
    return problems, stats


def _kinds(found: dict[str, int]) -> str:
    return ", ".join(f"{kind} ×{n}" for kind, n in found.items())


def evidence(s, commits: list[str], target: str) -> dict:
    """Which evidence of the outgoing commits is public, which is pending, and what the private archive holds:
    ids and counts only. A pending log is one its session's manifest in the target's tree gives no URL for."""
    pointed = {}
    if commits:
        log = git(s, "log", "--no-walk=unsorted", "--format=%B%x01", *commits[:5000])
        for sid, sha in s.TRAILER_RE.findall(log.stdout.decode(errors="replace")):
            if sha:
                pointed[sid, sha] = None
    manifests = s.tree_files([(target, f"llm-dlc/traces/{sid}/manifest.json") for sid, _ in pointed]) if pointed else {}
    public, pending, withdrawn = [], [], []
    for sid, sha in pointed:
        raw = manifests.get((target, f"llm-dlc/traces/{sid}/manifest.json"))
        info = ((json.loads(raw).get("logs") or {}).get(sha) if raw else None) or {}
        (withdrawn if info.get("withdrawn") else public if info.get("url") else pending).append(f"{sid}/{sha[:12]}")
    out = {"trace_logs": {"public": len(public), "pending": len(pending), "withdrawn": len(withdrawn),
                          "pending_ids": sorted(pending)[:100]}}
    try:
        import artifacts
        if (artifacts.home() / "journal.sqlite").exists():
            archive = artifacts.Archive()
            try:
                status = archive.status()
            finally:
                archive.close()
            out["originals"] = {"by_state": {k: v["occurrences"] for k, v in status["occurrences"].items()},
                                "oldest_unverified": status["oldest_unverified"], "exposure": status["exposure"]}
        else:
            out["originals"] = {"note": "this machine has no private archive journal"}
    except Exception as e:  # the receipt says so; the archive never stops a checkpoint
        out["originals"] = {"note": f"the private archive could not be read: {type(e).__name__}"}
    return out


def ensure_immutable(s) -> None:
    """A commit that is on the remote `develop` is published: jj must treat it as immutable, so that no later
    `sync.py commit` stamps a trailer on it and rewrites what others have fetched."""
    wanted = f"builtin_immutable_heads() | present({DEVELOP}@{REMOTE})"
    name = 'revset-aliases."immutable_heads()"'
    if jq(s, "config", "get", name).stdout.strip() != wanted:
        jq(s, "config", "set", "--repo", name, wanted)


def push(s, sha: str, branch: str, expected: str | None) -> tuple[bool, str]:
    """Push exactly SHA to the remote's branch, forward only, and only if the branch is where `expected` says (None:
    not there yet). A push whose answer is lost or refused is settled by reading the remote."""
    lease = f"--force-with-lease=refs/heads/{branch}:{expected or ''}"  # with a forward-only target this forces nothing
    try:
        r = git(s, "push", "--no-follow-tags", "--no-verify", lease, REMOTE, f"{sha}:refs/heads/{branch}", timeout=600)
        said = r.stderr.decode(errors="replace").strip()
    except subprocess.TimeoutExpired:
        r, said = None, "git push did not answer in time"
    try:
        there = remote_ref(s, branch)
    except RuntimeError as e:
        return False, f"{said or 'git push failed'}; and the remote could not be read to see what it holds: {e}"
    if there == sha:
        return True, "pushed" if r is not None and r.returncode == 0 else "the push's answer was lost or an error, and the remote holds the commit"
    return False, f"the remote's {branch} is at {(there or 'nothing')[:12]}, not {sha[:12]}: {said[-300:] or 'git push failed'}"


def usage() -> int:
    print("usage: sync.py checkpoint --rev REV [--dry-run]\n       sync.py checkpoint --bootstrap", file=sys.stderr)
    return 2


def cmd_checkpoint(s, args: list[str]) -> int:
    for i, a in enumerate(args):
        revision = i > 0 and args[i - 1] == "--rev"  # a revset may hold a colon; a refspec is never an argument here
        if a.split("=", 1)[0] in REFUSED_ARGS or "*" in a or (":" in a and not revision and not a.startswith("--")):
            print(f"sync.py checkpoint: {a!r} is not for this command. It pushes one committed revision to {REMOTE}'s "
                  f"{DEVELOP}, forward only: no other ref or remote, no pattern, no force", file=sys.stderr)
            return 2
    # Every jj call of this command, the ones sync.py's own helpers make included, leaves the working copy alone.
    real = s.jj
    s.jj = lambda *a: real(*a) if "--ignore-working-copy" in a else real("--ignore-working-copy", *a)
    try:
        return _checkpoint(s, args)
    finally:
        s.jj = real


def _checkpoint(s, args: list[str]) -> int:
    dry = "--dry-run" in args
    rest = [a for a in args if a != "--dry-run"]
    started, timing = time.perf_counter(), {}
    try:
        if rest == ["--bootstrap"]:
            return bootstrap(s)
        if len(rest) != 2 or rest[0] != "--rev":
            return usage()
        target = resolve(s, rest[1])
        t = time.perf_counter()
        develop, main = remote_ref(s, DEVELOP), remote_ref(s, MAIN)
        timing["remote"] = time.perf_counter() - t
    except (ValueError, RuntimeError) as e:
        print(f"not checkpointed: {e}", file=sys.stderr)
        return 1
    sha = target["commit"]
    if develop is None:
        print(f"not checkpointed: {REMOTE} has no {DEVELOP} yet. Create it where {MAIN} is with `sync.py checkpoint --bootstrap`", file=sys.stderr)
        return 1
    if develop == sha:
        print(f"{DEVELOP} is already at {sha[:12]} ({target['change'][:12]}): nothing to push")
        return 0
    if not have(s, develop):
        print(f"not checkpointed: {REMOTE}'s {DEVELOP} is at {develop[:12]}, which this repository does not have: someone else "
              f"pushed. Fetch it (`jj git fetch --remote {REMOTE}`) and bring this line onto it; a checkpoint never forces", file=sys.stderr)
        return 1
    if not is_ancestor(s, develop, sha):
        print(f"not checkpointed: {sha[:12]} does not descend from {REMOTE}'s {DEVELOP} ({develop[:12]}). A checkpoint moves "
              f"{DEVELOP} forward only: merge or rebase onto it first", file=sys.stderr)
        return 1
    bases = [develop, main if main and have(s, main) else None]
    t = time.perf_counter()
    redact = s.Redactor()
    commits, blobs = outgoing(s, sha, bases)
    problems, stats = scan(s, redact, commits, blobs, sha, bases)
    problems += s.decision_problems(sha)
    timing["scan"] = time.perf_counter() - t
    if problems:
        for p in problems[:200]:
            print("ERROR", p)
        if len(problems) > 200:
            print(f"... and {len(problems) - 200} more")
        print(f"not checkpointed: {len(problems)} problem(s) in what the push would expose ({stats['commits']} commit(s), "
              f"{stats['blobs']:,} new blob(s)); nothing left this machine", file=sys.stderr)
        return 1
    receipt = {"schema": RECEIPT_SCHEMA, "remote": REMOTE, "bookmark": DEVELOP, "before": develop, "after": sha,
               "change": target["change"], "summary": target["description"].split("\n", 1)[0],
               "tree": git(s, "rev-parse", f"{sha}^{{tree}}").stdout.decode().strip(), "main": main,
               "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "policy": POLICY, "scan": stats,
               "evidence": evidence(s, commits, sha),
               "tests": "none run by the checkpoint: a checkpoint confers no test, proof or release status"}
    if dry:
        print(json.dumps(receipt, indent=1))
        print(f"dry run: {sha[:12]} would move {DEVELOP} from {develop[:12]}; nothing was pushed")
        return 0
    t = time.perf_counter()
    done, how = push(s, sha, DEVELOP, develop)
    timing["push"] = time.perf_counter() - t
    if not done:
        print(f"not checkpointed: {how}", file=sys.stderr)
        return 1
    jq(s, "git", "import")
    ensure_immutable(s)
    timing["total"] = time.perf_counter() - started
    receipt["timing_seconds"] = {k: round(v, 2) for k, v in timing.items()}
    receipt["pushed"] = how
    save_receipt(s, receipt)
    e = receipt["evidence"]["trace_logs"]
    print(f"checkpoint: {REMOTE}/{DEVELOP} {develop[:12]} -> {sha[:12]} ({stats['commits']} commit(s), {stats['blobs']:,} new blob(s), "
          f"{stats['scanned_blobs']:,} scanned now) in {timing['total']:.1f} s")
    print(f"  evidence: trace logs {e['public']} public, {e['pending']} pending; originals: "
          f"{(receipt['evidence'].get('originals') or {}).get('exposure') or (receipt['evidence'].get('originals') or {}).get('note')}")
    print(f"  receipt: {receipt_path(s, sha)}")
    return 0


def bootstrap(s) -> int:
    main = remote_ref(s, MAIN)
    develop = remote_ref(s, DEVELOP)
    if develop is not None:
        print(f"{REMOTE} already has {DEVELOP}, at {develop[:12]}: nothing to bootstrap")
        return 0
    if main is None:
        print(f"not bootstrapped: {REMOTE} has no {MAIN} to start {DEVELOP} from", file=sys.stderr)
        return 1
    done, how = push(s, main, DEVELOP, None)  # a commit the remote already has: no object is sent
    if not done:
        print(f"not bootstrapped: {how}", file=sys.stderr)
        return 1
    jq(s, "git", "import")
    ensure_immutable(s)
    print(f"bootstrapped: {REMOTE}/{DEVELOP} created at {MAIN}'s commit {main[:12]}; checkpoints go forward from there")
    return 0


def receipt_path(s, sha: str) -> Path:
    return s.STATE / "checkpoints" / f"{sha}.json"


def save_receipt(s, receipt: dict) -> None:
    """The receipt, on this machine, and as an ordinary occurrence in the private archive, so that a reader on
    another machine can ask for the checkpoint of a given commit (artifacts.py list --source SHA)."""
    path = receipt_path(s, receipt["after"])
    path.parent.mkdir(parents=True, exist_ok=True)
    s.atomic_write(path, json.dumps(receipt, indent=1) + "\n")
    try:
        import artifacts
        if not artifacts.off() and (artifacts.home() / "journal.sqlite").exists():
            archive = artifacts.Archive()
            try:
                archive.capture(path, "checkpoint-receipt", f"checkpoints/{receipt['after']}.json",
                                source={"commit": receipt["after"], "tree": receipt["tree"], "before": receipt["before"]})
            finally:
                archive.close()
            artifacts.kick()
    except Exception as e:
        print(f"note: the receipt was not sealed into the private archive ({type(e).__name__}); it is at {path}", file=sys.stderr)
