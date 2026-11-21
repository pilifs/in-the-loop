#!/usr/bin/env python3
"""The private archive of original outputs: capture, custody, and reads.

A producer (the verification runner, the collector, a loop, the trace tools) hands the bytes it made to
`capture` before it shortens, replaces or deletes them. The bytes are sealed once into a spool on this
machine's disk, outside the checkout, with a full private inventory; a restartable uploader then puts
them in a private R2 bucket, reads them back, and only then calls them `remote_verified`. Any project
agent can list and fetch them afterwards, from this machine or from a fresh one that has nothing but
the bucket. See llm-dlc/specification.md ("Original outputs") for the contract.

  occurrence   one capture of one logical output: a job attempt's logs, a run's records, a segment of a
               session transcript. Its id is made here (time and random bits), so two captures of the
               same path, or of identical bytes, are two occurrences.
  object       stored bytes, named by the SHA-256 of the original (uncompressed) bytes they hold: a
               whole file, a part of a large one, a pack of small ones, or a manifest. Never rewritten.
  manifest     the private inventory of an occurrence: every member's path, type, mode, length and
               SHA-256, and where its bytes are. Its own SHA-256 is the occurrence's inventory digest.
  receipt      the immutable remote record of a verified occurrence. Receipts and manifests are all a
               fresh machine needs to rebuild the catalog.

Custody states, per occurrence: expected -> locally_sealed -> transferring -> remote_verified, and
retryable_error, missing_input, integrity_failure. Nothing here deletes a stored byte, locally or
remotely: expiry and remote deletion are off for this rollout.

Access classes are buckets, since a prefix cannot keep a bucket-wide reader out: `ordinary` (job logs,
outputs, diffs, records: every project agent reads it) and `restricted` (source transcripts, private
run records, and anything not yet classified: the watcher's private analysis only). Neither is bound
to the public Worker that serves redacted traces.

Commands (python3 llm-dlc/tools/artifacts.py COMMAND ...):
  capture PATH --kind KIND --logical NAME [--run R] [--job J] [--attempt N] [--session S]
          [--source REV] [--stream KEY] [--partial] [--expect PATH ...]
                        seal a file, a folder, or (with --stream) what an append-only file gained
  missing --kind KIND --logical NAME --reason TEXT [...]
                        record an output that never materialized or was lost, with what is known of it
  upload [--drain | --loop] [--limit N] [--workers N]
                        put sealed objects in the store, read them back, write receipts: one pass, or
                        (--drain) passes until nothing is left to do now, as the spool's one uploader
  status [--json]       custody: bytes and counts by state, oldest unverified, disk headroom, retries
  list [--run R] [--job J] [--attempt N] [--session S] [--source REV] [--digest D] [--kind K]
       [--include-attempts] [--remote-only] [--json]
  show ID [--json]      one occurrence: its receipt, state and where it can be read
  fetch ID --to DIR [--prefix]
                        fetch, verify and lay out an occurrence's members under DIR (offline when cached);
                        --prefix on a stream segment restores the file as it was at that capture
  analyze ID --purpose TEXT
                        safe derived facts about a restricted occurrence (lengths, counts, digests);
                        the id and the purpose are logged, and no content is printed
  recover               register what a crash left sealed on disk but not in the journal
  canary                exercise the real store on made-up bytes: custody, a restore from an empty cache,
                        and the access policy of each credential and of the public Worker
  verify [ID ...]       re-hash the spool's copies (and with --remote, read the store's again)

Environment: ITL_ORIGINALS_HOME (the spool and journal; default ~/.local/share/in-the-loop/originals),
ITL_ORIGINALS_CACHE (a reader's private cache; default ~/.cache/in-the-loop/originals-cache),
ITL_ORIGINALS_STORE (`dir:PATH` for a store on disk, as the tests use; default R2 with the tokens in
~/.config/in-the-loop/r2-originals-*), ITL_ORIGINALS_OFF=1 (capture does nothing: the rollback switch).

Standard library only.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import gzip
import hashlib
import hmac
import http.client
import io
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import stat as stat_
import sys
import time
import urllib.parse
import zlib
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

MANIFEST_SCHEMA = "itl-original-manifest/v1"
OCCURRENCE_SCHEMA = "itl-occurrence/v1"
BUCKETS = {"ordinary": "in-the-loop-originals", "restricted": "in-the-loop-originals-restricted"}
CREDENTIALS = Path.home() / ".config" / "in-the-loop"
# What each credential may do, and which class it reads: the writer is the uploader's alone.
CREDENTIAL_FILES = {"writer": "r2-originals-writer", "ordinary": "r2-originals-reader",
                    "restricted": "r2-originals-restricted-reader"}
# Kinds whose bytes every project agent may read. Any other kind is restricted until someone classifies it here:
# unclassified bytes are received into restricted custody, never into ordinary.
ORDINARY_KINDS = frozenset({
    "job-logs", "job-outputs", "job-diff", "job-result", "job-workdir", "job-run", "example-records",
    "selector-cases", "trace-log", "decisions", "checkpoint-receipt", "promotion-receipt", "canary",
})
RESTRICTED_KINDS = frozenset({"session-transcript", "run-record", "watcher-record", "canary-restricted"})
STATES = ("expected", "locally_sealed", "transferring", "remote_verified", "retryable_error", "missing_input",
          "integrity_failure")
SMALL_MAX = 1 << 20      # a file under this goes into a pack with its siblings
PACK_MAX = 32 << 20      # a pack is closed once it holds this much
PART_MAX = 256 << 20     # a larger file is stored as parts of at most this, each an object of its own
READ = 1 << 20
GZIP_LEVEL = 6           # as the trace logs: same input, same bytes (mtime=0)
RESERVE = 2 << 30        # free disk a capture leaves alone, so the machine's other work is not starved
LEASE_SECONDS = 900
BACKOFF = (30, 120, 600, 3600)  # seconds before a failed transfer is tried again, by attempt


def home() -> Path:
    return Path(os.environ.get("ITL_ORIGINALS_HOME") or Path.home() / ".local/share/in-the-loop/originals")


def cache_home() -> Path:
    return Path(os.environ.get("ITL_ORIGINALS_CACHE") or Path.home() / ".cache/in-the-loop/originals-cache")


def off() -> bool:
    return bool(os.environ.get("ITL_ORIGINALS_OFF"))


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(t: datetime | None = None) -> str:
    return (t or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(t: datetime | None = None) -> str:
    """An occurrence id: when it was made, to the second and then to the microsecond, and 40 random bits, so ids
    sort in the order they were made. Neither a time nor a path names an occurrence."""
    t = t or now()
    return f"{t.strftime('%Y%m%dT%H%M%SZ')}-{t.microsecond:06d}{secrets.token_hex(5)}"


def id_date(occurrence: str) -> str:
    return f"{occurrence[:4]}/{occurrence[4:6]}/{occurrence[6:8]}"


def access_of(kind: str) -> str:
    return "ordinary" if kind in ORDINARY_KINDS else "restricted"


def transcript_key(path: Path) -> str | None:
    """The stream a client's transcript file is sealed under, or None for a file that is not in a client's own
    session store (a test's, a copy): Claude Code's by its place under ~/.claude/projects, a Codex rollout by name."""
    path = Path(path).resolve()
    claude, codex = (Path.home() / ".claude" / "projects").resolve(), (Path.home() / ".codex").resolve()
    if claude in path.parents:
        return f"claude/{path.relative_to(claude).as_posix()}"
    if codex in path.parents:
        return f"codex/{path.name}"
    return None


def canonical(doc) -> bytes:
    return (json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def sha256_file(path: Path, limit: int | None = None) -> tuple[str, int]:
    h, n = hashlib.sha256(), 0
    with open(path, "rb") as f:
        while limit is None or n < limit:
            data = f.read(READ if limit is None else min(READ, limit - n))
            if not data:
                break
            h.update(data)
            n += len(data)
    return h.hexdigest(), n


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def install(tmp: Path, dest: Path) -> bool:
    """Put a finished temporary file at dest, durably, unless dest is already there (then tmp is dropped).
    Whether it was installed. A name is the hash of its content, so a file already there is the same file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(tmp, dest)
        made = True
    except FileExistsError:
        made = False
    os.unlink(tmp)
    fsync_dir(dest.parent)
    return made


def write_durably(path: Path, data: bytes, replace: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if replace:
        os.replace(tmp, path)
        fsync_dir(path.parent)
    else:
        install(tmp, path)


# Already-compressed content gains nothing from gzip; told by its first bytes, so the same content always gets
# the same encoding and so the same object name.
_PACKED = (b"\x1f\x8b", b"PK\x03\x04", b"\x28\xb5\x2f\xfd", b"\xfd7zXZ", b"\x89PNG", b"\xff\xd8\xff", b"BZh")


def encoding_for(first: bytes) -> str:
    return "identity" if first.startswith(_PACKED) else "gzip"


def object_key(digest: str, encoding: str) -> str:
    return f"objects/sha256/{digest[:2]}/{digest}.{'gz' if encoding == 'gzip' else 'raw'}"


class ManifestError(Exception):
    """A manifest that cannot be laid out safely: an escaping path, an ambiguous member, bytes that do not match."""


class SpoolFull(OSError):
    """A capture that would take the disk under its reserve. Nothing was acknowledged; the source must be kept."""


class Unavailable(Exception):
    """Evidence that cannot be read now: missing, unverified, restricted, or damaged. Says which."""


# --------------------------------------------------------------------------- stores

class StoreError(Exception):
    """A request the store did not answer usefully: retried later. Never carries a key or a signature."""


class DirStore:
    """A store on disk, one folder per bucket: what the tests and the local rehearsals use. `faults` lets a test
    make it fail the way a network does."""

    def __init__(self, root: Path, bucket: str, readonly: bool = False) -> None:
        self.root, self.bucket, self.readonly = Path(root) / bucket, bucket, readonly
        self.faults: dict[str, object] = {}

    def _fault(self, op: str, key: str) -> None:
        fault = self.faults.get(op)
        if fault and (fault is True or (callable(fault) and fault(key))):
            raise StoreError(f"{op} failed (injected)")

    def put_if_absent(self, key: str, path: Path, digest: str | None = None) -> bool:
        if self.readonly:
            raise StoreError("PUT refused: read-only credential")
        self._fault("put", key)
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.{secrets.token_hex(4)}")
        shutil.copyfile(path, tmp)
        try:
            os.link(tmp, dest)
            made = True
        except FileExistsError:
            made = False
        os.unlink(tmp)
        self._fault("put-after", key)  # the object is there, the answer is lost
        return made

    def open(self, key: str):
        self._fault("get", key)
        try:
            return open(self.root / key, "rb")
        except FileNotFoundError:
            return None

    def size(self, key: str) -> int | None:
        self._fault("head", key)
        try:
            return (self.root / key).stat().st_size
        except FileNotFoundError:
            return None

    def list(self, prefix: str):
        self._fault("list", prefix)
        base = self.root
        for path in sorted(base.rglob("*")) if base.exists() else []:
            key = path.relative_to(base).as_posix()
            if path.is_file() and key.startswith(prefix) and not path.name.startswith("."):
                yield key, path.stat().st_size


class R2Store:
    """One R2 bucket through its S3 API, signed with AWS Signature Version 4, streaming both ways. It can create
    an object if none is there, read, size and list: it has no way to overwrite or delete. Errors name the
    status and S3 error code only."""

    def __init__(self, credential: Path, bucket: str, probing: bool = False) -> None:
        """`probing`: a bucket the credential's file does not name, asked only to see the store refuse (canary)."""
        values = {}
        for line in credential.read_text().splitlines():
            key, eq, value = line.partition("=")
            if eq:
                values[key.strip()] = value.strip()
        if not re.fullmatch(r"[0-9a-f]{32}", values.get("account_id", "")):
            raise StoreError(f"{credential.name}: no Cloudflare account id")
        if not probing and bucket not in [b.strip() for b in values.get("buckets", bucket).split(",")]:
            raise StoreError(f"{credential.name} is not for bucket {bucket}")
        self.host, self.bucket = f"{values['account_id']}.r2.cloudflarestorage.com", bucket
        self._key, self._secret = values.get("access_key_id", ""), values.get("secret_access_key", "")

    def _signed(self, method: str, path: str, query: dict[str, str], headers: dict[str, str], payload: str) -> dict:
        at = now()
        amz, day = at.strftime("%Y%m%dT%H%M%SZ"), at.strftime("%Y%m%d")
        headers = {**headers, "host": self.host, "x-amz-date": amz, "x-amz-content-sha256": payload}
        canon = {k.lower(): " ".join(str(v).split()) for k, v in headers.items()}
        names = sorted(canon)
        q = "&".join(f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}" for k, v in sorted(query.items()))
        request = "\n".join([method, path, q, *(f"{k}:{canon[k]}" for k in names), "", ";".join(names), payload])
        scope = f"{day}/auto/s3/aws4_request"
        to_sign = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(request.encode()).hexdigest()])
        key = f"AWS4{self._secret}".encode()
        for part in (day, "auto", "s3", "aws4_request"):
            key = hmac.new(key, part.encode(), hashlib.sha256).digest()
        signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
        return {**headers, "Authorization": f"AWS4-HMAC-SHA256 Credential={self._key}/{scope}, "
                                             f"SignedHeaders={';'.join(names)}, Signature={signature}"}, q

    def _request(self, method: str, key: str, query: dict[str, str] | None = None, headers: dict[str, str] | None = None,
                 body=None, payload: str = hashlib.sha256(b"").hexdigest(), timeout: float = 300):
        path = "/" + urllib.parse.quote(f"{self.bucket}/{key}" if key else self.bucket, safe="/-_.~")
        signed, q = self._signed(method, path, query or {}, headers or {}, payload)
        conn = http.client.HTTPSConnection(self.host, timeout=timeout)
        try:
            conn.request(method, path + (f"?{q}" if q else ""), body=body, headers=signed)
            return conn, conn.getresponse()
        except (OSError, http.client.HTTPException) as e:
            conn.close()
            raise StoreError(f"R2 {method}: {type(e).__name__}") from None

    @staticmethod
    def _failed(method: str, response) -> StoreError:
        code = re.search(rb"<Code>([A-Za-z]{1,64})</Code>", response.read(4096) or b"")
        return StoreError(f"R2 {method}: HTTP {response.status}" + (f" {code.group(1).decode()}" if code else ""))

    def put_if_absent(self, key: str, path: Path, digest: str | None = None) -> bool:
        digest = digest or sha256_file(path)[0]
        with open(path, "rb") as f:
            conn, r = self._request("PUT", key, body=f, payload=digest, headers={
                "content-length": str(os.fstat(f.fileno()).st_size), "content-type": "application/octet-stream",
                "if-none-match": "*"})
        with contextlib.closing(conn):
            if r.status in (200, 201):
                r.read()
                return True
            if r.status == 412:
                r.read()
                return False
            raise self._failed("PUT", r)

    def open(self, key: str):
        conn, r = self._request("GET", key)
        if r.status == 200:
            return _Body(conn, r)
        with contextlib.closing(conn):
            if r.status == 404:
                r.read()
                return None
            raise self._failed("GET", r)

    def size(self, key: str) -> int | None:
        conn, r = self._request("HEAD", key)
        with contextlib.closing(conn):
            r.read()
            if r.status == 200:
                return int(r.getheader("content-length") or 0)
            if r.status == 404:
                return None
            raise StoreError(f"R2 HEAD: HTTP {r.status}")

    def list(self, prefix: str):
        token = None
        while True:
            query = {"list-type": "2", "prefix": prefix, **({"continuation-token": token} if token else {})}
            conn, r = self._request("GET", "", query=query)
            with contextlib.closing(conn):
                if r.status != 200:
                    raise self._failed("LIST", r)
                root = ElementTree.fromstring(r.read())
            ns = root.tag.partition("}")[0] + "}" if root.tag.startswith("{") else ""
            for item in root.iter(f"{ns}Contents"):
                yield item.findtext(f"{ns}Key"), int(item.findtext(f"{ns}Size") or 0)
            token = root.findtext(f"{ns}NextContinuationToken")
            if not token:
                return


class _Body:
    """A response being read, and the connection it keeps open until it is closed."""

    def __init__(self, conn, response) -> None:
        self.conn, self.response = conn, response

    def read(self, n: int = -1) -> bytes:
        return self.response.read(n) if n >= 0 else self.response.read()

    def close(self) -> None:
        self.response.close()
        self.conn.close()


def read_all(store, key: str) -> bytes | None:
    r = store.open(key)
    if r is None:
        return None
    with contextlib.closing(r):
        try:
            return r.read()
        except (OSError, http.client.HTTPException) as e:
            raise StoreError(f"read failed: {type(e).__name__}") from None


def store_for(access: str, role: str = "reader"):
    """The store of an access class, with the writer's credential (the uploader) or the class's reader. With
    ITL_ORIGINALS_STORE=dir:PATH, folders on disk stand in for the buckets."""
    bucket = BUCKETS[access]
    where = os.environ.get("ITL_ORIGINALS_STORE", "")
    if where.startswith("dir:"):
        return DirStore(Path(where[4:]), bucket, readonly=role != "writer")
    credential = CREDENTIALS / CREDENTIAL_FILES["writer" if role == "writer" else access]
    if not credential.exists():
        raise Unavailable(f"no credential here to {'write' if role == 'writer' else 'read'} the {access} archive "
                          f"({credential.name} is not in {CREDENTIALS})")
    return R2Store(credential, bucket)


def read_verified(store, key: str, digest: str, encoding: str, raw_bytes: int | None, to: Path | None = None) -> str:
    """Read an object back from the store and compare the original bytes it decodes to with their name and length:
    "ok", "absent", or "mismatch". The bytes are the store's own, read with a credential; a size or an ETag is not
    asked. With `to`, the stored bytes are kept there once they are shown to match."""
    r = store.open(key)
    if r is None:
        return "absent"
    h, n = hashlib.sha256(), 0
    unpack = zlib.decompressobj(wbits=31) if encoding == "gzip" else None
    tmp = to.with_name(f".{to.name}.{secrets.token_hex(4)}") if to else None
    if tmp:
        tmp.parent.mkdir(parents=True, exist_ok=True)
    out = open(tmp, "wb") if tmp else None
    try:
        with contextlib.closing(r):
            while True:
                try:
                    data = r.read(READ)
                except (OSError, http.client.HTTPException) as e:
                    raise StoreError(f"read failed: {type(e).__name__}") from None
                if not data:
                    break
                if out:
                    out.write(data)
                try:
                    raw = unpack.decompress(data) if unpack else data
                except zlib.error:
                    return "mismatch"
                h.update(raw)
                n += len(raw)
        if unpack:
            try:
                raw = unpack.flush()
            except zlib.error:
                return "mismatch"
            h.update(raw)
            n += len(raw)
            if not unpack.eof:
                return "mismatch"
        if h.hexdigest() != digest or (raw_bytes is not None and n != raw_bytes):
            return "mismatch"
        if out:
            out.flush()
            os.fsync(out.fileno())
            out.close()
            out = None
            os.replace(tmp, to)
            tmp = None
        return "ok"
    finally:
        if out:
            out.close()
        if tmp and tmp.exists():
            tmp.unlink()


# --------------------------------------------------------------------------- the spool and its journal

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS objects (
  access TEXT NOT NULL, digest TEXT NOT NULL, encoding TEXT NOT NULL, role TEXT NOT NULL,
  raw_bytes INTEGER NOT NULL, stored_bytes INTEGER NOT NULL, stored_sha256 TEXT NOT NULL,
  state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, next_try REAL NOT NULL DEFAULT 0,
  lease_owner TEXT, lease_until REAL NOT NULL DEFAULT 0, sealed_at TEXT NOT NULL, verified_at TEXT,
  PRIMARY KEY (access, digest, encoding));
CREATE TABLE IF NOT EXISTS occurrences (
  id TEXT PRIMARY KEY, access TEXT NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL, status TEXT NOT NULL,
  run TEXT, session TEXT, job TEXT, attempt INTEGER, logical TEXT NOT NULL, source TEXT,
  manifest TEXT, raw_bytes INTEGER NOT NULL DEFAULT 0, members INTEGER NOT NULL DEFAULT 0,
  captured_at TEXT NOT NULL, verified_at TEXT, last_error TEXT, record TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS occurrences_job ON occurrences (job, attempt);
CREATE INDEX IF NOT EXISTS occurrences_state ON occurrences (state);
CREATE TABLE IF NOT EXISTS needs (occurrence TEXT NOT NULL, digest TEXT NOT NULL, encoding TEXT NOT NULL,
  PRIMARY KEY (occurrence, digest, encoding));
CREATE INDEX IF NOT EXISTS needs_object ON needs (digest, encoding);
CREATE TABLE IF NOT EXISTS streams (key TEXT PRIMARY KEY, generation INTEGER NOT NULL, offset INTEGER NOT NULL,
  prefix_sha256 TEXT NOT NULL, occurrence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempts (job TEXT NOT NULL, attempt INTEGER NOT NULL, started_at TEXT NOT NULL,
  PRIMARY KEY (job, attempt));
CREATE TABLE IF NOT EXISTS events (n INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, subject TEXT NOT NULL,
  event TEXT NOT NULL, detail TEXT);
"""


class ObjectWriter:
    """One object being sealed into the spool: original bytes in, stored bytes on disk, both hashed as they pass."""

    def __init__(self, archive: "Archive", access: str, encoding: str, role: str) -> None:
        self.archive, self.access, self.encoding, self.role = archive, access, encoding, role
        self.tmp = archive.tmp / f"{os.getpid()}.{secrets.token_hex(6)}"
        self.file = open(self.tmp, "wb")
        self.stored, self.stored_bytes = hashlib.sha256(), 0
        self.raw, self.raw_bytes = hashlib.sha256(), 0
        self.gz = gzip.GzipFile(filename="", mode="wb", compresslevel=GZIP_LEVEL, fileobj=self, mtime=0) \
            if encoding == "gzip" else None

    def write(self, data: bytes) -> int:  # the stored side: what the gzip stream, or add(), writes to disk
        self.stored.update(data)
        self.stored_bytes += len(data)
        return self.file.write(data)

    def flush(self) -> None:
        self.file.flush()

    def add(self, data: bytes) -> None:
        self.raw.update(data)
        self.raw_bytes += len(data)
        (self.gz or self).write(data)

    def seal(self) -> dict:
        try:
            if self.gz:
                self.gz.close()
            self.file.flush()
            os.fsync(self.file.fileno())
        finally:
            self.file.close()
        info = {"digest": self.raw.hexdigest(), "encoding": self.encoding, "role": self.role,
                "raw_bytes": self.raw_bytes, "stored_bytes": self.stored_bytes, "stored_sha256": self.stored.hexdigest()}
        install(self.tmp, self.archive.object_path(self.access, info["digest"], self.encoding))
        return info

    def abort(self) -> None:
        with contextlib.suppress(OSError):
            self.file.close()
        with contextlib.suppress(OSError):
            self.tmp.unlink()


class Archive:
    """The spool on this machine and its journal. One per process or thread: each holds its own connection."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or home())
        self.tmp, self.intake = self.root / "tmp", self.root / "intake"
        for d in (self.root, self.tmp, self.intake, self.root / "spool"):
            d.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.root / "journal.sqlite", timeout=60, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")  # an acknowledged capture survives a power cut
        self.db.executescript(SCHEMA_SQL)
        self.worker = f"{socket.gethostname()}:{os.getpid()}:{secrets.token_hex(3)}"

    def close(self) -> None:
        self.db.close()

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        self.db.execute("COMMIT")

    def event(self, subject: str, event: str, detail: str | None = None) -> None:
        self.db.execute("INSERT INTO events (at, subject, event, detail) VALUES (?,?,?,?)", (iso(), subject, event, detail))

    def object_path(self, access: str, digest: str, encoding: str) -> Path:
        return self.root / "spool" / access / digest[:2] / f"{digest}.{'gz' if encoding == 'gzip' else 'raw'}"

    # ----- capture

    def headroom(self, needed: int) -> None:
        free = shutil.disk_usage(self.root).free
        reserve = int(os.environ.get("ITL_ORIGINALS_RESERVE", RESERVE))
        if free - needed < reserve:
            raise SpoolFull(f"the spool's disk has {free:,} bytes free; a capture of {needed:,} would leave less than "
                            f"the {reserve:,} reserve. Nothing was sealed: keep the source")

    def begin_attempt(self, job: str) -> int:
        """The number of a job's new attempt: one more than its last, whoever ran it on this machine."""
        with self.transaction():
            n = self.db.execute("SELECT COALESCE(MAX(attempt), 0) + 1 FROM attempts WHERE job=?", (job,)).fetchone()[0]
            self.db.execute("INSERT INTO attempts VALUES (?,?,?)", (job, n, iso()))
        return n

    def _seal_file(self, access: str, path: Path, pack: list, objects: list, limit: int | None = None,
                   skip: int = 0, hasher=None) -> tuple[str, int, list[dict]]:
        """Seal one file's bytes (from `skip`, at most `limit`): into the open pack if it is small, else as objects
        of its own. Returns (sha256, length, parts). `hasher` is fed the same bytes (a stream's running digest)."""
        h, n, parts = hashlib.sha256(), 0, []
        with open(path, "rb") as f:
            if skip:
                f.seek(skip)
            size = os.fstat(f.fileno()).st_size - skip if limit is None else limit
            if size < SMALL_MAX:
                data = f.read(size) if limit is not None else f.read()
                h.update(data)
                if hasher:
                    hasher.update(data)
                if data:
                    if pack[0] is None:
                        pack[0] = ObjectWriter(self, access, "gzip", "pack")
                    parts.append({"pack": pack[0], "offset": pack[0].raw_bytes, "bytes": len(data)})
                    pack[0].add(data)
                    if pack[0].raw_bytes >= PACK_MAX:
                        self._close_pack(pack, objects)
                return h.hexdigest(), len(data), parts
            writer = None

            def close():
                nonlocal writer
                info, writer = writer.seal(), None
                objects.append(info)
                parts.append({"object": info["digest"], "encoding": info["encoding"], "offset": 0, "bytes": info["raw_bytes"]})
            try:
                while limit is None or n < limit:
                    data = f.read(READ if limit is None else min(READ, limit - n))
                    if not data:
                        break
                    h.update(data)
                    if hasher:
                        hasher.update(data)
                    n += len(data)
                    while data:
                        if writer is None:
                            writer = ObjectWriter(self, access, encoding_for(data), "part")
                        room = PART_MAX - writer.raw_bytes
                        writer.add(data[:room])
                        data = data[room:]
                        if writer.raw_bytes >= PART_MAX:
                            close()
                if writer is not None:
                    close()
            except BaseException:
                if writer is not None:
                    writer.abort()
                raise
        return h.hexdigest(), n, parts

    def _close_pack(self, pack: list, objects: list) -> None:
        if pack[0] is not None:
            writer, pack[0] = pack[0], None
            info = writer.seal()
            writer.info = info
            objects.append(info)

    @staticmethod
    def _settle(members: list[dict]) -> None:
        """Once every pack is sealed, a part that named its pack's writer names the pack's digest."""
        for m in members:
            for part in m.get("parts", []):
                writer = part.pop("pack", None)
                if writer is not None:
                    part["object"], part["encoding"] = writer.info["digest"], "gzip"

    def capture(self, path: Path, kind: str, logical: str, *, run: str | None = None, job: str | None = None,
                attempt: int | None = None, session: str | None = None, source: dict | None = None,
                status: str = "complete", expected: list[str] | None = None, exclude=None, notes: dict | None = None,
                access: str | None = None, deleted: list[str] | None = None, conflicts: list[str] | None = None,
                sparse: bool = False) -> dict | None:
        """Seal a file or a folder as one occurrence, and acknowledge only once it and its inventory are durable.
        `expected` names the members the producer meant to make: those not found are recorded, and the occurrence
        is partial. `exclude(relative path, is_dir)` leaves members out, by a rule the caller records in `notes`;
        with `sparse`, so are the folders that then hold no member.
        Returns the occurrence's record, or None when capture is switched off."""
        if off():
            return None
        path, access = Path(path), access or access_of(kind)
        if not path.exists() and not path.is_symlink():
            return self.missing(kind, logical, "the path was not there when its capture was asked for", run=run, job=job,
                                attempt=attempt, session=session, source=source, expected=expected, notes=notes)
        entries = []
        if path.is_dir() and not path.is_symlink():
            for base, dirs, files in os.walk(path):
                dirs.sort()
                rel_base, folders = Path(base).relative_to(path), set(dirs)
                for name in sorted(dirs + files):
                    full = Path(base) / name
                    rel = (rel_base / name).as_posix()
                    is_dir = name in folders and not full.is_symlink()
                    if exclude and exclude(rel, is_dir):
                        if is_dir:
                            dirs.remove(name)
                        continue
                    entries.append((rel, full))
            root_kind = "tree"
        else:
            entries.append((path.name, path))
            root_kind = "blob"
        self.headroom(sum(p.lstat().st_size for _, p in entries))
        members, objects, pack, total = [], [], [None], 0
        try:
            for rel, full in entries:
                st = full.lstat()
                if stat_.S_ISLNK(st.st_mode):
                    members.append({"path": rel, "type": "symlink", "target": os.readlink(full)})
                elif stat_.S_ISDIR(st.st_mode):
                    members.append({"path": rel, "type": "dir"})
                elif stat_.S_ISREG(st.st_mode):
                    digest, n, parts = self._seal_file(access, full, pack, objects)
                    total += n
                    members.append({"path": rel, "type": "file", "mode": f"{st.st_mode & 0o777:o}", "bytes": n,
                                    "sha256": digest, "parts": parts})
                else:  # a socket, a pipe, a device: no bytes to keep, and said so
                    members.append({"path": rel, "type": "other", "what": stat_.filemode(st.st_mode)[0]})
            self._close_pack(pack, objects)
        except BaseException:
            if pack[0] is not None:
                pack[0].abort()
            raise
        self._settle(members)
        if sparse:
            holding = {str(parent) for m in members if m["type"] != "dir" for parent in PurePosixPath(m["path"]).parents}
            members = [m for m in members if m["type"] != "dir" or m["path"] in holding]
        found = {m["path"] for m in members}
        absent = sorted(e for e in (expected or []) if e not in found and not any(f.startswith(e.rstrip("/") + "/") for f in found))
        record = {"raw": {"bytes": total, "sha256": members[0]["sha256"]} if root_kind == "blob" and members[0]["type"] == "file" else {"bytes": total}}
        return self._commit(kind, logical, access, root_kind, members, objects,
                            "partial" if absent or status == "partial" else "complete",
                            run=run, job=job, attempt=attempt, session=session, source=source,
                            extra={**record, "absent": absent, "deleted": sorted(deleted or []),
                                   "conflicts": sorted(conflicts or []), "notes": notes or {}})

    def capture_stream(self, path: Path, key: str, kind: str, logical: str, **meta) -> dict | None:
        """Seal what an append-only file gained since its last capture under `key`, as a segment with its offset,
        length, predecessor and the digest of the whole prefix it completes. A file that no longer starts with what
        was captured (rotated, replaced, truncated) starts a new generation, whole. None when nothing was gained."""
        if off():
            return None
        path, access = Path(path), meta.pop("access", None) or access_of(kind)
        size = path.stat().st_size
        row = self.db.execute("SELECT * FROM streams WHERE key=?", (key,)).fetchone()
        generation, offset, predecessor, reason = 1, 0, None, "first capture"
        running = hashlib.sha256()
        if row is not None:
            have, _ = sha256_file(path, row["offset"]) if size >= row["offset"] else (None, 0)
            if have == row["prefix_sha256"]:
                if size == row["offset"]:
                    return None
                generation, offset, predecessor, reason = row["generation"], row["offset"], row["occurrence"], "appended"
                with open(path, "rb") as f:  # the running digest of the prefix, to be carried through the segment
                    left = offset
                    while left:
                        data = f.read(min(READ, left))
                        running.update(data)
                        left -= len(data)
            else:
                generation = row["generation"] + 1
                reason = "truncated" if size < row["offset"] else "replaced: its first bytes are no longer those captured"
        self.headroom(size - offset)
        objects, pack = [], [None]
        try:
            digest, n, parts = self._seal_file(access, path, pack, objects, limit=size - offset, skip=offset, hasher=running)
            self._close_pack(pack, objects)
        except BaseException:
            if pack[0] is not None:
                pack[0].abort()
            raise
        members = [{"path": path.name, "type": "file", "mode": "600", "bytes": n, "sha256": digest, "parts": parts}]
        self._settle(members)
        stream = {"key": key, "generation": generation, "offset": offset, "bytes": n, "predecessor": predecessor,
                  "prefix_bytes": offset + n, "prefix_sha256": running.hexdigest(), "why": reason}
        return self._commit(kind, logical, access, "segment", members, objects, "complete", stream=stream,
                            extra={"raw": {"bytes": n, "sha256": digest}, "stream": stream, "notes": meta.pop("notes", None) or {}}, **meta)

    def missing(self, kind: str, logical: str, reason: str, *, derivatives: list[dict] | None = None, lost: bool = False,
                expected: list[str] | None = None, notes: dict | None = None, **meta) -> dict | None:
        """Record an output with no bytes to keep: one that never materialized (a failed attempt's declared output)
        or, with `lost`, one known to have been produced and gone before capture. `derivatives` says what does
        survive of it (a shortened log in Git, a digest in a result) and where."""
        if off():
            return None
        return self._commit(kind, logical, meta.pop("access", None) or access_of(kind), "none", [], [], "missing",
                            extra={"raw": {"bytes": 0}, "gap": {"reason": reason, "lost": lost, "derivatives": derivatives or []},
                                   "absent": sorted(expected or []), "notes": notes or {}}, **meta)

    def _commit(self, kind, logical, access, root_kind, members, objects, status, *, run=None, job=None, attempt=None,
                session=None, source=None, extra=None, stream=None) -> dict:
        safe_member_path(logical)
        occurrence = new_id()
        manifest_info = None
        if root_kind != "none":
            listed = {(o["digest"], o["encoding"]): o for o in objects}
            manifest = canonical({"schema": MANIFEST_SCHEMA, "root": root_kind, "members": members,
                                  "objects": [{k: o[k] for k in ("digest", "encoding", "raw_bytes", "stored_bytes", "stored_sha256", "role")}
                                              for _, o in sorted(listed.items())]})
            writer = ObjectWriter(self, access, "gzip", "manifest")
            try:
                writer.add(manifest)
                manifest_info = writer.seal()
            except BaseException:
                writer.abort()
                raise
            objects = [*listed.values(), manifest_info]
        record = {"schema": OCCURRENCE_SCHEMA, "id": occurrence, "kind": kind, "access": access, "logical": logical,
                  "run": run, "session": session, "job": job, "attempt": attempt, "source": source or {},
                  "captured_at": iso(), "captured_on": socket.gethostname(), "status": status, "root": root_kind,
                  "inventory": {"sha256": manifest_info["digest"], "members": len(members),
                                "files": sum(m["type"] == "file" for m in members),
                                "encoding": "gzip", "stored_bytes": manifest_info["stored_bytes"],
                                "stored_sha256": manifest_info["stored_sha256"]} if manifest_info else None,
                  **(extra or {})}
        row = {"id": occurrence, "state": "missing_input" if status == "missing" else "locally_sealed", "record": record,
               "objects": objects, "stream": stream}
        # The intake record is on disk before the journal has it, so a crash between the two is found (recover).
        write_durably(self.intake / f"{occurrence}.json", canonical(row))
        self._journal(row)
        return record

    def _journal(self, row: dict) -> None:
        record = row["record"]
        with self.transaction():
            if self.db.execute("SELECT 1 FROM occurrences WHERE id=?", (record["id"],)).fetchone():
                return
            for o in row["objects"]:
                self.db.execute("INSERT OR IGNORE INTO objects (access, digest, encoding, role, raw_bytes, stored_bytes, "
                                "stored_sha256, state, sealed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                                (record["access"], o["digest"], o["encoding"], o["role"], o["raw_bytes"], o["stored_bytes"],
                                 o["stored_sha256"], "locally_sealed", record["captured_at"]))
                self.db.execute("INSERT OR IGNORE INTO needs VALUES (?,?,?)", (record["id"], o["digest"], o["encoding"]))
            self.db.execute("INSERT INTO occurrences (id, access, kind, state, status, run, session, job, attempt, logical, "
                            "source, manifest, raw_bytes, members, captured_at, record) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (record["id"], record["access"], record["kind"], row["state"], record["status"], record["run"],
                             record["session"], record["job"], record["attempt"], record["logical"],
                             (record["source"] or {}).get("commit"), (record["inventory"] or {}).get("sha256"),
                             record["raw"]["bytes"], (record["inventory"] or {}).get("members", 0), record["captured_at"],
                             json.dumps(record, sort_keys=True)))
            if stream := row.get("stream"):
                self.db.execute("INSERT OR REPLACE INTO streams VALUES (?,?,?,?,?)",
                                (stream["key"], stream["generation"], stream["prefix_bytes"], stream["prefix_sha256"], record["id"]))
            self.event(record["id"], row["state"], record["kind"])

    def recover(self) -> dict:
        """After a crash: journal every intake record the journal lacks, and register every sealed file in the spool
        that no record names (its capture died before its inventory was written; the producer still has the source,
        since nothing was acknowledged). A sealed file is decoded and hashed again before it is registered."""
        found = {"occurrences": 0, "orphans": 0, "damaged": []}
        for path in sorted(self.intake.glob("*.json")):
            row = json.loads(path.read_text())
            if not self.db.execute("SELECT 1 FROM occurrences WHERE id=?", (row["record"]["id"],)).fetchone():
                self._journal(row)
                found["occurrences"] += 1
        for path in sorted((self.root / "spool").glob("*/*/*")):
            access, (digest, _, ext) = path.parts[-3], path.name.partition(".")
            encoding = "gzip" if ext == "gz" else "identity"
            if self.db.execute("SELECT 1 FROM objects WHERE access=? AND digest=? AND encoding=?", (access, digest, encoding)).fetchone():
                continue
            actual, raw_bytes = self._decode_hash(path, encoding)
            if actual != digest:
                found["damaged"].append(str(path))
                continue
            stored, stored_bytes = sha256_file(path)
            with self.transaction():
                self.db.execute("INSERT OR IGNORE INTO objects (access, digest, encoding, role, raw_bytes, stored_bytes, "
                                "stored_sha256, state, sealed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                                (access, digest, encoding, "orphan", raw_bytes, stored_bytes, stored, "locally_sealed", iso()))
                self.event(digest, "orphan registered", access)
            found["orphans"] += 1
        for path in self.tmp.iterdir():  # what a killed capture was writing: never acknowledged, never named
            if time.time() - path.stat().st_mtime > 3600:
                path.unlink(missing_ok=True)
        return found

    @staticmethod
    def _decode_hash(path: Path, encoding: str) -> tuple[str | None, int]:
        h, n = hashlib.sha256(), 0
        try:
            with (gzip.open(path, "rb") if encoding == "gzip" else open(path, "rb")) as f:
                while data := f.read(READ):
                    h.update(data)
                    n += len(data)
        except (OSError, EOFError, zlib.error):
            return None, n
        return h.hexdigest(), n

    # ----- upload

    def _lease(self, limit: int) -> list[sqlite3.Row]:
        at = time.time()
        with self.transaction():
            rows = self.db.execute(
                "SELECT * FROM objects WHERE state IN ('locally_sealed','transferring','retryable_error') AND next_try<=? "
                "AND lease_until<=? ORDER BY sealed_at LIMIT ?", (at, at, limit)).fetchall()
            for r in rows:  # the attempt is committed before any byte moves
                self.db.execute("UPDATE objects SET state='transferring', attempts=attempts+1, lease_owner=?, lease_until=? "
                                "WHERE access=? AND digest=? AND encoding=?",
                                (self.worker, at + LEASE_SECONDS, r["access"], r["digest"], r["encoding"]))
        return rows

    def _settle_object(self, r, state: str, error: str | None = None) -> None:
        with self.transaction():
            attempts = self.db.execute("SELECT attempts FROM objects WHERE access=? AND digest=? AND encoding=?",
                                       (r["access"], r["digest"], r["encoding"])).fetchone()[0]
            wait = BACKOFF[min(attempts, len(BACKOFF)) - 1] if state == "retryable_error" else 0
            self.db.execute("UPDATE objects SET state=?, last_error=?, next_try=?, lease_owner=NULL, lease_until=0, "
                            "verified_at=CASE WHEN ?='remote_verified' THEN ? ELSE verified_at END "
                            "WHERE access=? AND digest=? AND encoding=?",
                            (state, error, time.time() + wait, state, iso(), r["access"], r["digest"], r["encoding"]))
            self.event(r["digest"], state, error)

    def upload_object(self, r, store) -> str:
        """Put one object and prove the store returns its original bytes. An object already there, from an earlier
        attempt whose answer was lost or from another worker, is read and judged the same way."""
        key, path = object_key(r["digest"], r["encoding"]), self.object_path(r["access"], r["digest"], r["encoding"])
        try:
            if not path.exists():
                self._settle_object(r, "integrity_failure", "the sealed file is gone from the spool")
                return "integrity_failure"
            store.put_if_absent(key, path, r["stored_sha256"])
            seen = read_verified(store, key, r["digest"], r["encoding"], r["raw_bytes"])
        except StoreError as e:
            self._settle_object(r, "retryable_error", str(e))
            return "retryable_error"
        if seen == "ok":
            self._settle_object(r, "remote_verified")
            return "remote_verified"
        if seen == "absent":
            self._settle_object(r, "retryable_error", "the store accepted the object but does not return it")
            return "retryable_error"
        self._settle_object(r, "integrity_failure", "the store holds other bytes under this object's name; the sealed "
                                                    "copy stays pinned in the spool")
        return "integrity_failure"

    def receipt_of(self, row) -> dict:
        record = json.loads(row["record"])
        objects = self.db.execute("SELECT o.* FROM needs n JOIN objects o ON o.digest=n.digest AND o.encoding=n.encoding "
                                  "AND o.access=? WHERE n.occurrence=?", (row["access"], row["id"])).fetchall()
        record["custody"] = {
            "state": "remote_verified", "bucket": BUCKETS[row["access"]],
            "manifest_key": object_key(row["manifest"], "gzip") if row["manifest"] else None,
            "objects": len(objects), "stored_bytes": sum(o["stored_bytes"] for o in objects),
            "verified_at": iso(), "verified_by": self.worker.rsplit(":", 2)[0],
            "verified_how": "each object was read back from the store with a credential and decoded; the original "
                            "bytes' SHA-256 and length matched its name and the inventory"}
        return record

    @staticmethod
    def stub_of(record: dict) -> dict:
        """What the ordinary archive says of a restricted occurrence: that it exists, and nothing a name could leak."""
        keep = ("schema", "id", "kind", "access", "run", "session", "job", "attempt", "captured_at", "status", "root")
        return {**{k: record.get(k) for k in keep}, "raw": {"bytes": (record.get("raw") or {}).get("bytes")},
                "custody": {"state": (record.get("custody") or {}).get("state", "pending")}}

    def _put_json(self, store, key: str, doc: dict, read_back: bool = True) -> None:
        """Create a small immutable document, or agree with the one already there. A receipt is read back whatever
        the store answered; an intent only when the store says one is there already."""
        data = canonical(doc)
        tmp = self.tmp / f"doc.{os.getpid()}.{secrets.token_hex(6)}"
        tmp.write_bytes(data)
        try:
            made = store.put_if_absent(key, tmp, hashlib.sha256(data).hexdigest())
        finally:
            tmp.unlink(missing_ok=True)
        if made and not read_back:
            return
        there = read_all(store, key)
        if there is None:
            raise StoreError("the store accepted a record but does not return it")
        if there != data and json.loads(there).get("id") != doc.get("id"):
            raise StoreError("the store holds another record under this id")

    def _finalize(self, store, row, receipt: dict) -> None:
        key = f"occurrences/{id_date(row['id'])}/{row['id']}.json"
        self._put_json(store(row["access"]), key, receipt)
        if row["access"] == "restricted":
            self._put_json(store("ordinary"), f"restricted/{key}", self.stub_of(receipt))

    def _fan(self, items: list, work, workers: int) -> list:
        """work(archive, item) for every item, on up to `workers` threads, each with a journal connection of its own."""
        if workers <= 1 or len(items) <= 1:
            return [work(self, item) for item in items]
        import threading
        from concurrent.futures import ThreadPoolExecutor
        local, opened = threading.local(), []

        def one(item):
            if not hasattr(local, "archive"):
                local.archive = Archive(self.root)
                local.archive.worker = self.worker
                opened.append(local.archive)
            return work(local.archive, item)
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                return list(pool.map(one, items))
        finally:
            for archive in opened:
                with contextlib.suppress(sqlite3.Error):
                    archive.close()

    def upload(self, limit: int = 1000, stores: dict | None = None, workers: int = 8) -> dict:
        """One pass: an intent for each new occurrence (so that it is discoverable while pending, whatever happens to
        this pass), then objects, then a receipt for each occurrence whose every object is verified. Safe to run
        from several workers at once and to kill at any point."""
        import threading
        stores, guard = dict(stores or {}), threading.Lock()

        def store(access):
            with guard:
                if access not in stores:
                    stores[access] = store_for(access, "writer")
                return stores[access]
        done = {"objects": {}, "receipts": 0, "intents": 0, "errors": []}

        def intend(archive, row):
            try:
                doc = json.loads(row["record"])
                archive._put_json(store(row["access"]), f"intents/{id_date(row['id'])}/{row['id']}.json", doc, read_back=False)
                if row["access"] == "restricted":
                    archive._put_json(store("ordinary"), f"restricted/intents/{id_date(row['id'])}/{row['id']}.json",
                                      archive.stub_of(doc), read_back=False)
                with archive.transaction():
                    archive.event(row["id"], "intent written")
                return None
            except (StoreError, Unavailable) as e:
                return str(e)
        new = self.db.execute("SELECT * FROM occurrences WHERE state NOT IN ('remote_verified','expected') AND id NOT IN "
                              "(SELECT subject FROM events WHERE event IN ('intent written','gap recorded remotely'))").fetchall()
        for error in self._fan(new, intend, workers):
            done["intents"] += error is None
            if error and error not in done["errors"]:
                done["errors"].append(error)

        def put(archive, r):
            try:
                return archive.upload_object(r, store(r["access"]))
            except Unavailable as e:
                archive._settle_object(r, "retryable_error", str(e))
                return "retryable_error"
        for outcome in self._fan(self._lease(limit), put, workers):
            done["objects"][outcome] = done["objects"].get(outcome, 0) + 1

        def settle(archive, row):
            """One occurrence, from its objects' states: (receipts written, intents written, error)."""
            db = archive.db
            if row["status"] == "missing":  # a gap: its record goes to the store, and there are no bytes to verify
                if db.execute("SELECT 1 FROM events WHERE subject=? AND event='gap recorded remotely'", (row["id"],)).fetchone():
                    return 0, None
                receipt = archive.receipt_of(row)
                receipt["custody"]["state"] = "missing_input"
                try:
                    archive._finalize(store, row, receipt)
                except (StoreError, Unavailable) as e:
                    return 0, str(e)
                with archive.transaction():
                    db.execute("UPDATE occurrences SET verified_at=?, record=? WHERE id=?", (iso(), json.dumps(receipt, sort_keys=True), row["id"]))
                    archive.event(row["id"], "gap recorded remotely")
                return 1, None
            states = [s[0] for s in db.execute(
                "SELECT o.state FROM needs n JOIN objects o ON o.digest=n.digest AND o.encoding=n.encoding AND o.access=? "
                "WHERE n.occurrence=?", (row["access"], row["id"]))]
            new, error, record, receipts = row["state"], None, row["record"], 0
            if "integrity_failure" in states:
                new = "integrity_failure"
            elif all(s == "remote_verified" for s in states):
                receipt = archive.receipt_of(row)
                try:  # the receipt is the last thing written: a store that has it has everything it names
                    archive._finalize(store, row, receipt)
                    new, record, receipts = "remote_verified", json.dumps(receipt, sort_keys=True), 1
                except (StoreError, Unavailable) as e:
                    new, error = "retryable_error", str(e)
            elif "retryable_error" in states:
                new = "retryable_error"
            elif "transferring" in states:
                new = "transferring"
            if new != row["state"] or (error and error != row["last_error"]):
                with archive.transaction():
                    db.execute("UPDATE occurrences SET state=?, last_error=?, verified_at=?, record=? WHERE id=?",
                               (new, error, iso() if new == "remote_verified" else None, record, row["id"]))
                    archive.event(row["id"], new, error)
            return receipts, error
        rows = self.db.execute("SELECT * FROM occurrences WHERE state NOT IN ('remote_verified','expected')").fetchall()
        for receipts, error in self._fan(rows, settle, workers):
            done["receipts"] += receipts
            if error and error not in done["errors"]:
                done["errors"].append(error)
        return done

    def drain(self, workers: int = 8) -> dict | None:
        """Upload until a pass finds nothing it can do now, as the one uploader of this spool: None when another
        process holds that place already. What failed waits out its backoff for the next drain."""
        import fcntl
        with open(self.root / "uploader.lock", "w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return None
            total = {"objects": {}, "receipts": 0, "intents": 0, "errors": [], "passes": 0}
            while True:
                done = self.upload(workers=workers)
                total["passes"] += 1
                for k, v in done["objects"].items():
                    total["objects"][k] = total["objects"].get(k, 0) + v
                total["receipts"] += done["receipts"]
                total["intents"] += done["intents"]
                total["errors"] = (total["errors"] + [e for e in done["errors"] if e not in total["errors"]])[:10]
                if not (done["objects"] or done["receipts"] or done["intents"]) or done["errors"]:
                    return total

    # ----- what custody looks like

    def status(self) -> dict:
        by_state = {}
        for r in self.db.execute("SELECT state, COUNT(*) n, SUM(raw_bytes) b FROM occurrences GROUP BY state"):
            by_state[r["state"]] = {"occurrences": r["n"], "bytes": r["b"] or 0}
        objects = {r["state"]: {"objects": r["n"], "stored_bytes": r["b"] or 0, "retries": r["a"] or 0} for r in self.db.execute(
            "SELECT state, COUNT(*) n, SUM(stored_bytes) b, SUM(MAX(attempts - 1, 0)) a FROM objects GROUP BY state")}
        oldest = self.db.execute("SELECT MIN(captured_at) FROM occurrences WHERE state NOT IN ('remote_verified','missing_input')").fetchone()[0]
        unverified = self.db.execute(
            "SELECT run, job, COUNT(*) n FROM occurrences WHERE state NOT IN ('remote_verified','missing_input') "
            "GROUP BY run, job ORDER BY n DESC LIMIT 20").fetchall()
        usage = shutil.disk_usage(self.root)
        local_only = sum(v["bytes"] for k, v in by_state.items() if k not in ("remote_verified", "missing_input"))
        return {"home": str(self.root), "occurrences": by_state, "objects": objects,
                "oldest_unverified": oldest, "last_remote_verification": self.db.execute("SELECT MAX(verified_at) FROM objects").fetchone()[0],
                "disk": {"free_bytes": usage.free, "reserve_bytes": int(os.environ.get("ITL_ORIGINALS_RESERVE", RESERVE))},
                "unverified_runs": [{"run": r["run"], "job": r["job"], "occurrences": r["n"]} for r in unverified],
                # Until an occurrence is remote_verified its only copies are on this machine: the source and the spool.
                "exposure": f"{local_only:,} original bytes are on this machine only" if local_only else "none: every sealed original is remote_verified",
                "errors": [dict(r) for r in self.db.execute(
                    "SELECT digest, state, attempts, last_error FROM objects WHERE state IN ('retryable_error','integrity_failure') LIMIT 20")]}

    def releasable(self, occurrence: str) -> bool:
        """Whether a producer may release its last source copy of this occurrence: only once it is remote_verified."""
        row = self.db.execute("SELECT state FROM occurrences WHERE id=?", (occurrence,)).fetchone()
        return bool(row) and row["state"] == "remote_verified"

    def rows(self, **where) -> list[dict]:
        clauses, values = [], []
        for column, value in where.items():
            if value is not None:
                clauses.append(f"{column}=?")
                values.append(value)
        sql = "SELECT * FROM occurrences" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY rowid"
        out = []
        for r in self.db.execute(sql, values):
            record = json.loads(r["record"])
            record.setdefault("custody", {})["state"] = r["state"] if r["state"] != "locally_sealed" else "pending"
            if r["state"] not in ("remote_verified", "missing_input"):
                record["custody"]["note"] = "local only: sealed on the capturing machine, not yet verified in the store"
            out.append(record)
        return out


# --------------------------------------------------------------------------- reading: the catalog, fetch, analysis

def safe_member_path(path: str) -> PurePosixPath:
    p = PurePosixPath(path)
    if not path or p.is_absolute() or "\0" in path or any(part in ("", ".", "..") for part in p.parts) or path != p.as_posix():
        raise ManifestError(f"a member's path escapes or is not plain: {path!r}")
    return p


def check_members(members: list[dict]) -> None:
    """Refuse a manifest whose members cannot all be laid out as they are named: a path that escapes, the same
    path twice, a file where another member needs a folder, a link that leaves the tree."""
    seen, kinds = set(), {}
    for m in members:
        p = safe_member_path(m["path"])
        if m["path"] in seen:
            raise ManifestError(f"two members are named {m['path']!r}")
        seen.add(m["path"])
        kinds[m["path"]] = m["type"]
    for path in seen:
        for parent in PurePosixPath(path).parents:
            if str(parent) != "." and kinds.get(str(parent), "dir") != "dir":
                raise ManifestError(f"{path!r} lies under {str(parent)!r}, which is not a folder")


def link_is_safe(path: str, target: str) -> bool:
    if os.path.isabs(target) or "\0" in target:
        return False
    return not os.path.normpath(os.path.join(os.path.dirname(path), target)).startswith("..")


class Reader:
    """Reads the archive as any project agent may: receipts and objects from the store, kept in a private cache
    once verified, so a second read needs no network. It never writes to the store, queues nothing, applies nothing."""

    def __init__(self, cache: Path | None = None, journal: Archive | None = None, offline: bool = False) -> None:
        self.cache, self.journal, self.offline = Path(cache or cache_home()), journal, offline
        self.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._stores: dict[str, object] = {}
        self.remote_error: str | None = None

    def store(self, access: str):
        if self.offline:
            raise Unavailable("offline: only what the cache holds can be read")
        if access not in self._stores:
            self._stores[access] = store_for(access, "reader")
        return self._stores[access]

    def _get_json(self, access: str, key: str, immutable: bool = True) -> dict | None:
        cached = self.cache / "catalog" / access / key
        if immutable and cached.exists():
            return json.loads(cached.read_text())
        if self.offline:
            return json.loads(cached.read_text()) if cached.exists() else None
        data = read_all(self.store(access), key)
        if data is None:
            return None
        write_durably(cached, data)
        return json.loads(data)

    def catalog(self, remote_only: bool = False) -> dict[str, dict]:
        """Every occurrence that can be known of from here, by id: the store's receipts (verified), its intents
        (pending), the ordinary archive's stubs of restricted ones, and, on the capturing machine, the journal."""
        found: dict[str, dict] = {}
        local = {} if self.journal is None or remote_only else {r["id"]: r for r in self.journal.rows()}
        try:
            if self.offline:
                raise Unavailable("offline")
            store, keys = self.store("ordinary"), {}
            for prefix in ("intents/", "restricted/intents/", "occurrences/", "restricted/occurrences/"):
                for key, _ in store.list(prefix):
                    keys.setdefault(key.rsplit("/", 1)[1].removesuffix(".json"), {})[prefix] = key
            wanted = []
            for occurrence, by in keys.items():
                final = by.get("occurrences/") or by.get("restricted/occurrences/")
                mine = local.get(occurrence)
                if mine is not None and (mine.get("custody") or {}).get("state") in ("remote_verified", "missing_input"):
                    continue  # this machine wrote that receipt: its journal holds the same record
                wanted.append((occurrence, final or by.get("intents/") or by["restricted/intents/"], bool(final)))

            def get(item):
                occurrence, key, final = item
                return occurrence, final, self._get_json("ordinary", key, immutable=final)
            if len(wanted) > 4:  # a first read on a fresh machine: many small documents, fetched side by side
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=16) as pool:
                    docs = list(pool.map(get, wanted))
            else:
                docs = [get(item) for item in wanted]
            for occurrence, final, doc in docs:
                if doc:
                    if not final:
                        doc.setdefault("custody", {})["state"] = "pending" if doc.get("status") != "missing" else "missing_input"
                    found[occurrence] = doc
        except (StoreError, Unavailable) as e:  # the receipts already read are in the cache
            self.remote_error = None if self.offline else str(e)
            for path in sorted((self.cache / "catalog" / "ordinary").glob("**/occurrences/*/*/*/*.json")):
                doc = json.loads(path.read_text())
                found.setdefault(doc["id"], doc)
        for record in local.values():
            if record["id"] not in found or found[record["id"]].get("custody", {}).get("state") == "pending":
                found[record["id"]] = record if record["access"] == "ordinary" else {**Archive.stub_of(record), "custody": record["custody"]}
        return found

    def find(self, remote_only: bool = False, **where) -> list[dict]:
        out = []
        for doc in self.catalog(remote_only).values():
            source = doc.get("source") or {}
            checks = {
                "run": doc.get("run"), "job": doc.get("job"), "session": doc.get("session"), "kind": doc.get("kind"),
                "attempt": doc.get("attempt")}
            if any(where.get(k) is not None and str(checks[k]) != str(where[k]) for k in checks):
                continue
            if where.get("source") and not any(str(v).startswith(where["source"]) for v in source.values() if v):
                continue
            if where.get("digest") and where["digest"] not in ((doc.get("raw") or {}).get("sha256"), (doc.get("inventory") or {}).get("sha256")):
                continue
            out.append(doc)
        return sorted(out, key=lambda d: d["id"])

    def receipt(self, occurrence: str) -> dict:
        """A verified occurrence's receipt, or Unavailable saying why there is none to read."""
        key = f"occurrences/{id_date(occurrence)}/{occurrence}.json"
        doc = self._get_json("ordinary", key)
        if doc is None:
            stub = self._get_json("ordinary", f"restricted/{key}") or self._get_json("ordinary", f"restricted/intents/{id_date(occurrence)}/{occurrence}.json", immutable=False)
            if stub is not None:
                raise Unavailable(f"{occurrence} is restricted: its bytes are in the restricted archive, read only by the "
                                  "watcher's private analysis (artifacts.py analyze)")
            if self._get_json("ordinary", f"intents/{id_date(occurrence)}/{occurrence}.json", immutable=False) is not None:
                raise Unavailable(f"{occurrence} is pending: captured, but not yet verified in the store")
            raise Unavailable(f"{occurrence} is not in the archive" + (" (as far as the cache says: offline)" if self.offline else ""))
        if (doc.get("custody") or {}).get("state") == "missing_input":
            gap = doc.get("gap") or {}
            raise Unavailable(f"{occurrence} has no bytes: {gap.get('reason', 'its output never materialized')}")
        return doc

    def _object(self, access: str, digest: str, encoding: str, raw_bytes: int | None) -> Path:
        """A verified object's stored bytes in the cache, fetched if they are not there."""
        path = self.cache / "objects" / access / digest[:2] / f"{digest}.{'gz' if encoding == 'gzip' else 'raw'}"
        if path.exists():
            return path
        seen = read_verified(self.store(access), object_key(digest, encoding), digest, encoding, raw_bytes, to=path)
        if seen != "ok":
            raise Unavailable(f"object {digest[:12]} is {'missing from the store' if seen == 'absent' else 'damaged in the store: its bytes do not match its name'}")
        return path

    def manifest(self, receipt: dict) -> dict:
        inventory = receipt["inventory"]
        path = self._object(receipt["access"], inventory["sha256"], "gzip", None)
        try:
            data = gzip.decompress(path.read_bytes())
        except (OSError, EOFError, zlib.error):
            data = b""
        if hashlib.sha256(data).hexdigest() != inventory["sha256"]:
            path.unlink(missing_ok=True)
            raise Unavailable(f"the cached inventory of {receipt['id']} is damaged; fetch it again")
        doc = json.loads(data)
        check_members(doc["members"])
        if len(doc["members"]) != inventory["members"]:
            raise Unavailable(f"the inventory of {receipt['id']} lists {len(doc['members'])} members, its receipt {inventory['members']}")
        return doc

    def fetch(self, occurrence: str, to: Path, prefix: bool = False, flat: bool = False) -> dict:
        """Lay an occurrence's members out under `to`, at its logical path (or directly, with `flat`), every byte
        checked against the inventory. With `prefix`, a stream segment's whole file as it was at that capture."""
        receipt = self.receipt(occurrence)
        chain = [receipt]
        if prefix:
            if receipt.get("root") != "segment":
                raise Unavailable(f"{occurrence} is not a segment of a stream")
            while chain[0]["stream"]["predecessor"]:
                chain.insert(0, self.receipt(chain[0]["stream"]["predecessor"]))
        base = Path(to) if flat else Path(to) / safe_member_path(receipt["logical"])
        done = {"id": occurrence, "to": str(base), "members": 0, "files": 0, "bytes": 0, "unsafe_links": [], "other": []}
        scratch = self.cache / "raw" / f"{os.getpid()}.{secrets.token_hex(4)}"
        scratch.mkdir(parents=True)
        try:
            if prefix:
                self._lay_prefix(chain, base, done, scratch)
            else:
                self._lay(receipt, self.manifest(receipt), base, done, scratch)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        return done

    def _raw(self, access: str, part: dict, sizes: dict, scratch: Path) -> Path:
        """An object's original bytes as a file, decoded once for the fetch and hashed as they are written."""
        raw = scratch / f"{part['object']}.{part['encoding']}"
        if not raw.exists():
            stored = self._object(access, part["object"], part["encoding"], sizes.get((part["object"], part["encoding"])))
            h = hashlib.sha256()
            try:
                with (gzip.open(stored, "rb") if part["encoding"] == "gzip" else open(stored, "rb")) as f, open(raw, "wb") as out:
                    while data := f.read(READ):
                        h.update(data)
                        out.write(data)
            except (OSError, EOFError, zlib.error):
                h.update(b"damaged")  # it cannot be decoded: not the object its name says
            if h.hexdigest() != part["object"]:
                stored.unlink(missing_ok=True)
                raw.unlink(missing_ok=True)
                raise Unavailable(f"the cached copy of object {part['object'][:12]} is damaged; fetch it again")
        return raw

    def _write_member(self, access: str, m: dict, dest, sizes: dict, scratch: Path) -> None:
        h, n = hashlib.sha256(), 0
        for part in m.get("parts", []):
            with open(self._raw(access, part, sizes, scratch), "rb") as f:
                f.seek(part["offset"])
                left = part["bytes"]
                while left:
                    data = f.read(min(READ, left))
                    if not data:
                        break
                    h.update(data)
                    dest.write(data)
                    left -= len(data)
                    n += len(data)
        if n != m["bytes"] or h.hexdigest() != m["sha256"]:
            raise Unavailable(f"member {m['path']!r} does not match its inventory: {n} bytes where {m['bytes']} were sealed"
                              if n != m["bytes"] else f"member {m['path']!r} does not match its inventory's SHA-256")

    def _lay(self, receipt: dict, manifest: dict, base: Path, done: dict, scratch: Path) -> None:
        access = receipt["access"]
        sizes = {(o["digest"], o["encoding"]): o["raw_bytes"] for o in manifest["objects"]}
        blob = manifest["root"] in ("blob", "segment")
        (base.parent if blob else base).mkdir(parents=True, exist_ok=True)
        for m in manifest["members"]:
            dest = base if blob else base / m["path"]
            done["members"] += 1
            if m["type"] == "dir":
                dest.mkdir(parents=True, exist_ok=True)
            elif m["type"] == "symlink":
                if link_is_safe(m["path"], m["target"]):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if dest.is_symlink() or dest.exists():
                        dest.unlink()
                    os.symlink(m["target"], dest)
                else:  # recorded, never made: it would point outside what was fetched
                    done["unsafe_links"].append(m["path"])
            elif m["type"] == "file":
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_name(f".{dest.name}.{secrets.token_hex(4)}")
                try:
                    with open(tmp, "wb") as f:
                        self._write_member(access, m, f, sizes, scratch)
                    os.chmod(tmp, int(m.get("mode", "644"), 8) & 0o755 | 0o600)
                    os.replace(tmp, dest)
                finally:
                    tmp.unlink(missing_ok=True)
                done["files"] += 1
                done["bytes"] += m["bytes"]
            else:
                done["other"].append(m["path"])

    def _lay_prefix(self, chain: list[dict], base: Path, done: dict, scratch: Path) -> None:
        last = chain[-1]["stream"]
        base.parent.mkdir(parents=True, exist_ok=True)
        tmp = base.with_name(f".{base.name}.{secrets.token_hex(4)}")
        h = hashlib.sha256()

        class Tee:
            def __init__(self, f):
                self.f = f

            def write(self, data):
                h.update(data)
                return self.f.write(data)
        try:
            with open(tmp, "wb") as f:
                at = 0
                for receipt in chain:
                    if receipt["stream"]["offset"] != at or receipt["stream"]["generation"] != last["generation"]:
                        raise Unavailable(f"the segments before {chain[-1]['id']} do not join: {receipt['id']} starts at "
                                          f"{receipt['stream']['offset']}, after {at} bytes")
                    manifest = self.manifest(receipt)
                    sizes = {(o["digest"], o["encoding"]): o["raw_bytes"] for o in manifest["objects"]}
                    self._write_member(receipt["access"], manifest["members"][0], Tee(f), sizes, scratch)
                    at += receipt["stream"]["bytes"]
            if at != last["prefix_bytes"] or h.hexdigest() != last["prefix_sha256"]:
                raise Unavailable(f"the restored prefix of {chain[-1]['id']} does not match the digest sealed with it")
            os.replace(tmp, base)
        finally:
            tmp.unlink(missing_ok=True)
        done.update(members=1, files=1, bytes=at, segments=len(chain))


def kick() -> bool:
    """Start an uploader for this spool in the background, unless one is at work or uploads are left to a person
    (ITL_ORIGINALS_UPLOAD=manual): transfer starts when a capture seals, not at the next push. Whether one was
    started. Its output goes to upload.log in the spool."""
    import subprocess
    if off() or os.environ.get("ITL_ORIGINALS_UPLOAD") == "manual":
        return False
    try:
        with open(home() / "upload.log", "ab") as log:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "upload", "--drain"], stdin=subprocess.DEVNULL,
                             stdout=log, stderr=log, start_new_session=True, cwd=str(home()))
        return True
    except OSError:
        return False


def analyze(occurrence: str, purpose: str, archive: Archive) -> dict:
    """Safe derived facts about an occurrence in restricted custody, for the watcher's private analysis: lengths,
    counts and digests, read from the journal and the sealed inventory on this machine. No member's bytes and no
    member's name are returned. The id and the purpose are logged before anything is read."""
    if not purpose.strip():
        raise Unavailable("a private analysis states its purpose")
    with archive.transaction():
        archive.event(occurrence, "private analysis", purpose.strip()[:500])
    row = archive.db.execute("SELECT * FROM occurrences WHERE id=?", (occurrence,)).fetchone()
    if row is None:
        raise Unavailable(f"{occurrence} is not in this machine's journal")
    record = json.loads(row["record"])
    facts = {"id": occurrence, "kind": row["kind"], "access": row["access"], "state": row["state"], "status": row["status"],
             "bytes": row["raw_bytes"], "members": row["members"], "inventory_sha256": row["manifest"],
             "raw_sha256": (record.get("raw") or {}).get("sha256"), "stream": record.get("stream")}
    if row["manifest"]:
        path = archive.object_path(row["access"], row["manifest"], "gzip")
        if path.exists():
            members = json.loads(gzip.decompress(path.read_bytes()))["members"]
            files = [m for m in members if m["type"] == "file"]
            facts["files"] = len(files)
            facts["largest_file_bytes"] = max((m["bytes"] for m in files), default=0)
            facts["suffixes"] = dict(sorted(((s, sum(1 for m in files if PurePosixPath(m["path"]).suffix == s))
                                             for s in {PurePosixPath(m["path"]).suffix for m in files}), key=lambda kv: -kv[1])[:12])
    return facts


def canary() -> list[tuple[str, bool, str]]:
    """The real store, exercised on bytes made up here: (check, passed, detail) for custody, a restore from an
    empty cache, and the access policy (who can read which class, that readers cannot write or delete, that the
    public Worker serves neither class, that the public traces' token reads neither). The canary objects stay in
    the buckets, a few kilobytes each run, since nothing here can delete; the one DELETE sent is a reader's, on a
    canary key, to see it refused. Prints no credential and no key."""
    import tempfile
    import urllib.error
    import urllib.request
    out: list[tuple[str, bool, str]] = []

    def check(name: str, test) -> None:
        try:
            passed, detail = test()
        except (StoreError, Unavailable, ManifestError, OSError) as e:
            passed, detail = False, f"{type(e).__name__}: {e}"
        out.append((name, bool(passed), detail))

    def refused(fn) -> tuple[bool, str]:
        try:
            got = fn()
        except StoreError as e:
            return "HTTP 403" in str(e) or "refused" in str(e), str(e)
        return False, f"answered {got!r}"

    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or None) as tmp:
        tmp = Path(tmp)
        archive = Archive(tmp / "home")
        tree = tmp / "canary"
        files = {"logs/1-run.log": b"canary line\n" * 50000, "cases/p0/native.json": b'{"canary": true}\n',
                 "cases/p0/empty": b"", "bin/blob": secrets.token_bytes(4096)}
        for rel, data in files.items():
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            (tree / rel).write_bytes(data)
        run = f"canary-{new_id()}"
        ordinary = archive.capture(tree, "canary", f"canary/{run}", run=run, job=run, attempt=1)
        (tmp / "restricted.bin").write_bytes(secrets.token_bytes(2048))
        restricted = archive.capture(tmp / "restricted.bin", "canary-restricted", f"canary/{run}.bin", run=run)
        done = archive.upload()
        states = {r["id"]: r["state"] for r in archive.db.execute("SELECT id, state FROM occurrences")}
        check("writer: both classes sealed, put, read back and receipted",
              lambda: (set(states.values()) == {"remote_verified"} and not done["errors"], json.dumps(done["objects"])))
        reader = Reader(cache=tmp / "fresh-cache")

        def restore():
            listed = reader.find(remote_only=True, run=run)
            got = reader.fetch(ordinary["id"], tmp / "restored", flat=True)
            same = all((tmp / "restored" / rel).read_bytes() == data for rel, data in files.items())
            return same and len(listed) == 2, f"{got['files']} files, {got['bytes']} bytes from an empty cache; {len(listed)} listed"
        check("reader: lists by run and restores every member from the store alone", restore)

        def offline():
            got = Reader(cache=tmp / "fresh-cache", offline=True).fetch(ordinary["id"], tmp / "again", flat=True)
            return got["bytes"] == sum(map(len, files.values())), "the same fetch repeated with no network"
        check("reader: a verified cache hit reads offline", offline)

        def restricted_listed():
            doc = next(d for d in reader.find(remote_only=True, run=run) if d["id"] == restricted["id"])
            try:
                reader.fetch(restricted["id"], tmp / "no")
            except Unavailable as e:
                return doc.get("logical") is None and "restricted" in str(e), "listed as restricted, with no name and no bytes"
            return False, "an ordinary reader fetched a restricted occurrence"
        check("reader: a restricted occurrence is discoverable, not readable", restricted_listed)
        if not os.environ.get("ITL_ORIGINALS_STORE"):
            key = object_key(restricted["raw"]["sha256"], "gzip")
            okey = f"occurrences/{id_date(ordinary['id'])}/{ordinary['id']}.json"
            ordinary_reader = lambda bucket: R2Store(CREDENTIALS / CREDENTIAL_FILES["ordinary"], bucket, probing=True)
            check("ordinary token: GET of a known restricted key is refused",
                  lambda: refused(lambda: read_all(ordinary_reader(BUCKETS["restricted"]), key)))
            check("ordinary token: PUT is refused",
                  lambda: refused(lambda: ordinary_reader(BUCKETS["ordinary"]).put_if_absent(f"canary/forged-{run}", tmp / "restricted.bin")))

            def delete():
                conn, r = ordinary_reader(BUCKETS["ordinary"])._request("DELETE", okey)
                with contextlib.closing(conn):
                    r.read()
                    return r.status == 403 and read_all(reader.store("ordinary"), okey) is not None, f"HTTP {r.status}; the receipt is still there"
            check("ordinary token: DELETE is refused", delete)
            check("restricted token: reads its class",
                  lambda: (read_verified(R2Store(CREDENTIALS / CREDENTIAL_FILES["restricted"], BUCKETS["restricted"]), key,
                                         restricted["raw"]["sha256"], "gzip", 2048) == "ok", "the restricted canary, read back whole"))
            check("restricted token: the ordinary class and writes are refused", lambda: (
                refused(lambda: read_all(R2Store(CREDENTIALS / CREDENTIAL_FILES["restricted"], BUCKETS["ordinary"], probing=True), okey))[0]
                and refused(lambda: R2Store(CREDENTIALS / CREDENTIAL_FILES["restricted"], BUCKETS["restricted"]).put_if_absent(
                    f"canary/forged-{run}", tmp / "restricted.bin"))[0], "GET of the ordinary receipt and PUT both HTTP 403"))
            traces = Path.home() / ".config/llm-traces/r2-credentials"
            if traces.exists():
                check("public traces' token: reads neither class", lambda: (
                    all(refused(lambda b=b, k=k: read_all(R2Store(traces, b, probing=True), k))[0]
                        for b, k in ((BUCKETS["ordinary"], okey), (BUCKETS["restricted"], key))), "both HTTP 403"))

            def worker():
                seen = []
                for k in (okey, key, f"{BUCKETS['ordinary']}/{okey}"):
                    try:
                        with urllib.request.urlopen(urllib.request.Request(
                                f"https://terminalvalue.net/raw-traces/{k}", headers={"User-Agent": "in-the-loop-artifacts-canary"}), timeout=30) as r:
                            seen.append(r.status)
                    except urllib.error.HTTPError as e:
                        seen.append(e.code)
                    time.sleep(1)
                return all(code == 404 for code in seen), f"HTTP {seen} for the canary's keys"
            check("public Worker: serves neither class", worker)
        archive.close()
    return out


# --------------------------------------------------------------------------- command line

def _source(rev: str | None) -> dict | None:
    return {"commit": rev} if rev else None


def _line(doc: dict) -> str:
    custody = doc.get("custody") or {}
    where = doc.get("logical") or "(restricted)"
    size = (doc.get("raw") or {}).get("bytes")
    return (f"{doc['id']}  {custody.get('state', '?'):16} {doc.get('access', '?'):10} {doc.get('kind', '?'):18} "
            f"{(str(size) if size is not None else '-'):>12}  {doc.get('job') or doc.get('session') or doc.get('run') or '-'}"
            f"{'#' + str(doc['attempt']) if doc.get('attempt') else ''}  {where}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="artifacts.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def identity(c):
        for flag in ("--run", "--job", "--session", "--source"):
            c.add_argument(flag)
        c.add_argument("--attempt", type=int)

    c = sub.add_parser("capture")
    c.add_argument("path")
    c.add_argument("--kind", required=True)
    c.add_argument("--logical", required=True)
    c.add_argument("--stream")
    c.add_argument("--partial", action="store_true")
    c.add_argument("--expect", nargs="*", default=[])
    identity(c)
    c = sub.add_parser("missing")
    c.add_argument("--kind", required=True)
    c.add_argument("--logical", required=True)
    c.add_argument("--reason", required=True)
    c.add_argument("--lost", action="store_true")
    identity(c)
    c = sub.add_parser("upload")
    c.add_argument("--loop", action="store_true")
    c.add_argument("--drain", action="store_true")
    c.add_argument("--workers", type=int, default=8)
    c.add_argument("--limit", type=int, default=1000)
    c.add_argument("--interval", type=int, default=60)
    c = sub.add_parser("status")
    c.add_argument("--json", action="store_true")
    c = sub.add_parser("list")
    identity(c)
    for flag in ("--digest", "--kind"):
        c.add_argument(flag)
    c.add_argument("--include-attempts", action="store_true")
    c.add_argument("--remote-only", action="store_true")
    c.add_argument("--offline", action="store_true")
    c.add_argument("--json", action="store_true")
    c = sub.add_parser("show")
    c.add_argument("id")
    c.add_argument("--offline", action="store_true")
    c = sub.add_parser("fetch")
    c.add_argument("id")
    c.add_argument("--to", required=True)
    c.add_argument("--prefix", action="store_true")
    c.add_argument("--flat", action="store_true")
    c.add_argument("--offline", action="store_true")
    c = sub.add_parser("analyze")
    c.add_argument("id")
    c.add_argument("--purpose", required=True)
    sub.add_parser("recover")
    sub.add_parser("canary")
    c = sub.add_parser("verify")
    c.add_argument("ids", nargs="*")
    args = p.parse_args(argv)

    journal = lambda: Archive() if (home() / "journal.sqlite").exists() else None
    try:
        if args.cmd == "capture":
            archive, meta = Archive(), dict(run=args.run, job=args.job, attempt=args.attempt, session=args.session, source=_source(args.source))
            record = archive.capture_stream(Path(args.path), args.stream, args.kind, args.logical, **meta) if args.stream else \
                archive.capture(Path(args.path), args.kind, args.logical, status="partial" if args.partial else "complete",
                                expected=args.expect, **meta)
            print(json.dumps({k: record[k] for k in ("id", "kind", "access", "status", "raw", "inventory")}, indent=1) if record
                  else "nothing captured (nothing new, or capture is switched off)")
        elif args.cmd == "missing":
            record = Archive().missing(args.kind, args.logical, args.reason, lost=args.lost, run=args.run, job=args.job,
                                       attempt=args.attempt, session=args.session, source=_source(args.source))
            print(record["id"] if record else "capture is switched off")
        elif args.cmd == "upload":
            archive = Archive()
            if args.drain:
                done = archive.drain(args.workers)
                print(f"{iso()} " + (json.dumps(done) if done else "another uploader is at work on this spool"), flush=True)
                return 1 if done and (done["errors"] or done["objects"].get("integrity_failure")) else 0
            while True:
                done = archive.upload(args.limit, workers=args.workers)
                print(json.dumps(done), flush=True)
                if not args.loop:
                    return 1 if done["errors"] or done["objects"].get("integrity_failure") else 0
                time.sleep(args.interval)
        elif args.cmd == "status":
            status = Archive().status()
            if args.json:
                print(json.dumps(status, indent=1))
            else:
                print(f"spool {status['home']}: {status['disk']['free_bytes']:,} bytes free (reserve {status['disk']['reserve_bytes']:,})")
                for state in STATES:
                    if state in status["occurrences"]:
                        o = status["occurrences"][state]
                        print(f"  {state:18} {o['occurrences']:6} occurrence(s)  {o['bytes']:>15,} original bytes")
                for state, o in sorted(status["objects"].items()):
                    print(f"  objects {state:18} {o['objects']:6}  {o['stored_bytes']:>15,} stored bytes  {o['retries']} retries")
                print(f"  oldest unverified: {status['oldest_unverified'] or 'none'}; last remote verification: {status['last_remote_verification'] or 'none'}")
                print(f"  exposure to the loss of this machine: {status['exposure']}")
                for e in status["errors"]:
                    print(f"  {e['state']}: object {e['digest'][:12]} after {e['attempts']} attempt(s): {e['last_error']}")
        elif args.cmd == "list":
            reader = Reader(journal=journal(), offline=args.offline)
            found = reader.find(remote_only=args.remote_only, run=args.run, job=args.job, session=args.session, kind=args.kind,
                                attempt=args.attempt, source=args.source, digest=args.digest)
            if not args.include_attempts and args.attempt is None:  # each job's last attempt only
                last = {}
                for doc in found:
                    if doc.get("job"):
                        last[doc["job"]] = max(last.get(doc["job"], 0), doc.get("attempt") or 0)
                found = [d for d in found if not d.get("job") or (d.get("attempt") or 0) == last[d["job"]]]
            if reader.remote_error:
                print(f"warn: the store was not read ({reader.remote_error}); this is what this machine knows", file=sys.stderr)
            print(json.dumps(found, indent=1) if args.json else "\n".join(_line(d) for d in found) or "no occurrence matches")
        elif args.cmd == "show":
            reader = Reader(journal=journal(), offline=args.offline)
            doc = next((d for d in reader.catalog().values() if d["id"] == args.id), None)
            if doc is None:
                raise Unavailable(f"{args.id} is not in the archive")
            print(json.dumps(doc, indent=1, sort_keys=True))
        elif args.cmd == "fetch":
            print(json.dumps(Reader(offline=args.offline).fetch(args.id, Path(args.to), prefix=args.prefix, flat=args.flat), indent=1))
        elif args.cmd == "analyze":
            print(json.dumps(analyze(args.id, args.purpose, Archive()), indent=1))
        elif args.cmd == "recover":
            print(json.dumps(Archive().recover(), indent=1))
        elif args.cmd == "canary":
            results = canary()
            for name, passed, detail in results:
                print(f"{'pass' if passed else 'FAIL'}  {name}: {detail}")
            print(f"{sum(p for _, p, _ in results)} of {len(results)} checks passed")
            return 0 if all(p for _, p, _ in results) else 1
        elif args.cmd == "verify":
            archive, bad, n = Archive(), [], 0
            for r in archive.db.execute("SELECT * FROM objects").fetchall():
                if args.ids and not archive.db.execute(
                        f"SELECT 1 FROM needs WHERE digest=? AND occurrence IN ({','.join('?' * len(args.ids))})", (r["digest"], *args.ids)).fetchone():
                    continue
                n += 1
                if Archive._decode_hash(archive.object_path(r["access"], r["digest"], r["encoding"]), r["encoding"])[0] != r["digest"]:
                    bad.append(r["digest"])
            print(f"{n} sealed object(s) re-hashed, {len(bad)} damaged or gone" + "".join(f"\n  {d}" for d in bad))
            return 1 if bad else 0
    except (Unavailable, ManifestError, SpoolFull, StoreError) as e:
        print(f"unavailable: {e}" if isinstance(e, Unavailable) else f"error: {e}", file=sys.stderr)
        return 3 if isinstance(e, Unavailable) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
