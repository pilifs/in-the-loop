"""What decides a result that sync.py keeps between commands: the redactor, the local caches and
the helpers they use. The caches' fingerprint (Redactor.fingerprint) covers the source of the files
in FINGERPRINTED, this one and the rules, so an edit to the rest of sync.py leaves redacted logs,
scan results and verified snapshots cached, and an edit here or to the rules makes them all cold.
That holds only while this file imports nothing from sync.py or metrics.py: everything it runs is
then here, in the rules, in the standard library (the Python version is fingerprinted too) or in
measure.py, which only measures. test_performance.Fingerprints keeps it so. What sync.py hands in
is either part of the fingerprint (this machine's literals), applied when a result is read rather
than stored (reviewed findings), or verified here against a SHA-256 (a stored log, a file's bytes)."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import multiprocessing
import sys
import threading
import time
import weakref
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable

import redaction_rules  # llm-dlc/tools/redaction_rules.py
from measure import perf  # llm-dlc/tools/measure.py
from redaction_rules import NEVER_REVIEWED

FINGERPRINTED = (Path(redaction_rules.__file__), Path(__file__))


def _mask(s: str) -> str:
    """Enough of a finding to recognise it, not enough to repeat it: scan output lands in transcripts."""
    return s if len(s) <= 4 else s[:3] + "…" + s[-2:] + f" ({len(s)} chars)" if len(s) > 12 else s[:2] + "…" + s[-1]


def finding_id(kind: str, value: str) -> str:
    """Names a finding without repeating it: the review list is published."""
    return hashlib.sha256(f"{kind}\0{value}".encode()).hexdigest()[:32]


def atomic_write(path: Path, data: str | bytes, private: bool = False) -> None:
    """Replace path with data in one step, as write_text or write_bytes would write it: into a
    temporary file of its own beside path, created exclusively under a name with this process,
    thread and a random part (two writers never share one, and none is left by a failed write),
    then renamed over path. private: readable by its owner only, from the first byte."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.{os.urandom(4).hex()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o666)
    try:
        with open(fd, "w" if isinstance(data, str) else "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


CACHE_VERSION = 1              # bump when what an entry means changes


def sha256(data) -> str:
    return hashlib.sha256(data).hexdigest()


def decoded(raw: bytes) -> str:
    """raw as Path.read_text(errors="replace") reads it: the default encoding, universal newlines."""
    return io.TextIOWrapper(io.BytesIO(raw), encoding=io.text_encoding(None), errors="replace").read()


def decompress(gz: bytes) -> bytes:
    with perf.phase("decompress"):
        data = gzip.decompress(gz)
    perf.count("log loads")
    perf.count("log bytes decompressed", len(data))
    return data


def prefix_digests(data: bytes, lengths: set[int]) -> dict[int, str]:
    """sha256 of data[:n] for each length n that data has, in one pass over data."""
    hasher, at, out, view = hashlib.sha256(), 0, {}, memoryview(data)
    for n in sorted(lengths):
        if n > len(data):
            break
        hasher.update(view[at:n])
        at = n
        out[n] = hasher.copy().hexdigest()
    return out


# A cold scan or redaction (after a rules edit, `stamp`, a new machine or a new session) is split
# across processes: lines are independent, so each worker builds the same rules from the same
# inputs and gives exactly what this process would. They are started for text of at least
# POOL_MIN_CHARS not yet scanned or redacted: below that, starting them costs more than they save,
# and a commit's new lines stay well below it. Once started, they also take text of POOL_MORE_CHARS
# or more, such as a snapshot scanned past the end of an earlier one. LLM_TRACES_PROCESSES=1 does
# everything in this process.
POOL_MIN_CHARS = 4_000_000
POOL_MORE_CHARS = 250_000


def pool_processes() -> int:
    """How many processes a cold scan or redaction uses: LLM_TRACES_PROCESSES, or the CPUs this
    process may run on."""
    try:
        n = int(os.environ.get("LLM_TRACES_PROCESSES") or 0)
    except ValueError:
        n = 0
    return n if n > 0 else len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count() or 1


def _chunks(lines: list[str], processes: int) -> list[list[str]]:
    """lines in order, in about four chunks per process of similar length, for balance."""
    size = max(sum(map(len, lines)) // (4 * processes), 1 << 18)
    chunks, chunk, n = [], [], 0
    for line in lines:
        chunk.append(line)
        n += len(line)
        if n >= size:
            chunks.append(chunk)
            chunk, n = [], 0
    return chunks + [chunk] if chunk else chunks


_worker: redaction_rules.Rules | None = None  # in a pool's worker: the rules it applies


def _worker_init(inputs: tuple, fingerprint: str) -> None:
    """Build the rules the parent uses, unless they are not those: the rules or this file edited
    after the parent read them. Then every task fails, and the parent does the work itself."""
    global _worker
    _worker = redaction_rules.Rules(*inputs) if Redactor(inputs, {}).fingerprint() == fingerprint else None


def _rules() -> redaction_rules.Rules:
    if _worker is None:
        raise RuntimeError("this worker read other rules than the parent process")
    return _worker


def _worker_scan(lines: list[str]) -> tuple[list, float]:
    """hits_of_line of each line, and the CPU time it took."""
    start, rules = time.process_time(), _rules()
    return [rules.hits_of_line(line) for line in lines], time.process_time() - start


def _worker_redact(lines: list[str]) -> tuple[bytes, float]:
    """Rules.__call__ of the lines joined: line by line, each followed by a newline. A line without
    line breaks is redacted to one line; an empty one gives an empty line, which Rules.__call__
    of it alone would drop."""
    start, rules = time.process_time(), _rules()
    return b"".join(rules(line) if line else b"\n" for line in lines), time.process_time() - start


def _line_key(line: str) -> bytes:
    """The key Rules.hits_of_text keeps a scanned line under in Rules._seen."""
    return hashlib.blake2b(line.encode(errors="replace"), digest_size=16).digest()


class Redactor(redaction_rules.Rules):
    """The rules with this machine's literals, less the false positives a person has reviewed."""

    def __init__(self, inputs: tuple, reviewed: dict[str, dict]) -> None:
        """inputs: Rules' arguments, this machine's literals and user name; reviewed: the ids of
        findings a person reviewed or allowed, left out of what is reported."""
        self.inputs = inputs
        super().__init__(*self.inputs)
        self.reviewed = reviewed
        self.skipped: Counter = Counter()  # kinds of finding left out because a person reviewed them
        self._latest: tuple[str, tuple] | None = None  # callers ask about one text twice
        self._pool: ProcessPoolExecutor | None = None  # started on the first cold text (POOL_MIN_CHARS)
        self._pool_usable, self._processes = True, 1
        self._loaded = self.fingerprint()  # of the rules as read when this was made: what a worker must apply
        self._pool_lock = threading.Lock()

    def _start_pool(self) -> ProcessPoolExecutor | None:
        with self._pool_lock:
            if not self._pool_usable:
                return None
            if self._pool is None:
                self._processes = processes = pool_processes()
                if processes < 2:
                    self._pool_usable = False
                    return None
                # spawn, not fork: push scans from threads, and a forked child can inherit a lock
                # another thread held. Shut down when this redactor goes, or at exit.
                self._pool = ProcessPoolExecutor(processes, mp_context=multiprocessing.get_context("spawn"),
                                                 initializer=_worker_init, initargs=(self.inputs, self._loaded))
                weakref.finalize(self, self._pool.shutdown, cancel_futures=True)
                perf.count("pool processes started", processes)
            return self._pool

    def _pooled(self, chars: int) -> bool:
        """Whether this much text not yet done goes to the pool."""
        return chars >= (POOL_MORE_CHARS if self._pool is not None and self._pool_usable else POOL_MIN_CHARS)

    def _in_pool(self, work, lines: list[str]) -> list | None:
        """work over chunks of lines in the pool, results in order; None when the pool cannot
        (no second CPU, a worker gone or refusing): the caller then does the work itself, with
        the same result."""
        pool = self._start_pool()
        if pool is None:
            return None
        try:
            with perf.phase("pool"):
                done = list(pool.map(work, _chunks(lines, self._processes)))
        except Exception:  # BrokenProcessPool, a worker's error: nothing is taken from it
            perf.count("pool failures")
            with self._pool_lock:
                self._pool_usable = False
                pool.shutdown(wait=False, cancel_futures=True)
            return None
        perf.count("pool chunks", len(done))
        perf.count("pool worker cpu seconds", round(sum(cpu for _, cpu in done), 3))
        return [result for result, _ in done]

    def _prescan(self, text: str) -> None:
        """Scan in the pool the lines of text not scanned before, when there are enough of them,
        into _seen, where hits_of_text then finds them: as if it had scanned them itself, the
        first line under each key standing for the others, as there."""
        if not self._pooled(len(text)):
            return
        todo: dict[bytes, str] = {}
        for line in text.splitlines():
            if (key := _line_key(line)) not in self._seen and key not in todo:
                todo[key] = line
        if not self._pooled(sum(map(len, todo.values()))):
            return
        done = self._in_pool(_worker_scan, list(todo.values()))
        if done is not None:
            self._seen.update(zip(todo, (hits for chunk in done for hits in chunk)))

    def _unreviewed(self, kind: str, value: str) -> bool:
        return kind in NEVER_REVIEWED or finding_id(kind, value) not in self.reviewed

    def _without_reviewed(self, hits: dict[str, Counter]) -> dict[str, Counter]:
        kept: dict[str, Counter] = {}
        for kind, values in hits.items():
            for value, n in values.items():
                if self._unreviewed(kind, value):
                    kept.setdefault(kind, Counter())[value] = n
                else:
                    self.skipped[kind] += n
        return kept

    def fingerprint(self) -> str:
        """Everything besides the content that decides what redacting or scanning gives: the
        rules, this module, the Python version and this machine's literals. Holds no literal."""
        h = hashlib.sha256(f"{CACHE_VERSION}\0{sys.version}\0".encode())
        for source in FINGERPRINTED:
            h.update(source.read_bytes() + b"\0")
        h.update(json.dumps(self.inputs, ensure_ascii=False).encode())
        return h.hexdigest()

    def raw_hits(self, text: str) -> tuple:
        """hits_of_text, measured; no judgement applied."""
        before = len(self._seen)
        with perf.phase("scan"):
            self._prescan(text)
            hits = self.hits_of_text(text)
        perf.count("scan texts")
        perf.count("scan chars", len(text))
        perf.count("scan lines scanned (not cached)", len(self._seen) - before)
        return hits

    def _hits(self, text: str) -> tuple:
        if self._latest is None or self._latest[0] is not text:
            self._latest = (text, self.raw_hits(text))
        return self._latest[1]

    def _counted_without_reviewed(self, found: dict[str, dict[str, list]]) -> dict[str, list]:
        """_without_reviewed for findings kept by finding id (ScanCache): kind -> [[masked, count]]."""
        kept: dict[str, list] = {}
        for kind, rows in found.items():
            for fid, (masked, n) in rows.items():
                if kind in NEVER_REVIEWED or fid not in self.reviewed:
                    kept.setdefault(kind, []).append([masked, n])
                else:
                    self.skipped[kind] += n
        return kept

    def cached_leaks(self, entry: dict) -> list[str]:
        """leaks() of the text a ScanCache entry was made from."""
        return sorted(self._counted_without_reviewed(entry["leaks"]))

    def cached_review(self, entry: dict) -> list[str]:
        """review() of the text a ScanCache entry was made from."""
        return [_review_line(kind, rows) for kind, rows in sorted(self._counted_without_reviewed(entry["review"]).items())]

    def __call__(self, jsonl: str) -> bytes:
        with perf.phase("redact"):
            perf.count("redact chars", len(jsonl))
            if self._pooled(len(jsonl)) and (done := self._in_pool(_worker_redact, jsonl.splitlines())) is not None:
                return b"".join(done)
            return super().__call__(jsonl)

    def leak_hits(self, text: str) -> dict[str, Counter]:
        """What the redactor would still change in this text, by kind, without reviewed false
        positives. Empty for its own output."""
        return self._without_reviewed(self._hits(text)[0])

    def leaks(self, text: str) -> list[str]:
        """Kinds of thing the redactor would still change in this text."""
        return sorted(self.leak_hits(text))

    def review_hits(self, text: str) -> dict[str, Counter]:
        """Things that may identify someone or something and that no rule removes, by kind, without
        reviewed false positives. Public IPs, foreign home directories, unknown token formats."""
        return self._without_reviewed(self._hits(text)[1])

    def review(self, text: str) -> list[str]:
        """The same, as masked warning lines with counts."""
        return [_review_line(kind, [[_mask(v), n] for v, n in c.items()]) for kind, c in sorted(self.review_hits(text).items())]


def _review_line(kind: str, rows: list[list]) -> str:
    """One kind of finding as a warning: [masked value, count] rows in the order they were found,
    the three most frequent shown (Counter.most_common: by count, ties in that order)."""
    top = sorted(rows, key=lambda r: r[1], reverse=True)[:3]
    return (f"{kind} ×{sum(n for _, n in rows)}: " + ", ".join(masked for masked, _ in top)
            + (f", +{len(rows) - 3} more" if len(rows) > 3 else ""))


class LocalCache:
    """A JSON object of entries under a fingerprint of their inputs; one with another fingerprint
    is empty. Saved whole and atomically; when two commands save at once, the later one wins,
    and what the other found is worked out again next time."""

    def __init__(self, path: Path | None, fingerprint: str, trusted: bool = True) -> None:
        self.path, self.fingerprint, self.entries = path, fingerprint, {}
        if path and trusted:
            try:
                stored = json.loads(path.read_text())
                if stored.get("fingerprint") == fingerprint:
                    self.entries = stored["entries"]
            except (OSError, ValueError, KeyError, AttributeError):
                pass

    def save(self, keep: set[str] | None = None) -> None:
        if self.path is None:
            return
        entries = self.entries if keep is None else {k: v for k, v in self.entries.items() if k in keep}
        text = json.dumps({"fingerprint": self.fingerprint, "entries": entries})
        try:
            atomic_write(self.path, text, private=True)
        except OSError:
            pass  # a cache: the work is done again next time


def redacted_incrementally(raw: bytes, key: str, redact: Redactor, cache: LocalCache | None,
                           load: Callable[[str], bytes | None]) -> bytes:
    """redact(decoded(raw)), reusing the log of an earlier, shorter version of the same transcript.
    The redactor works line by line, and a cut right after a newline byte splits the decoded text,
    its lines and so the log at the same place: the log of raw is the log of its first n bytes
    followed by the log of the rest. Reused only when those n bytes have the recorded SHA-256 and
    the stored log the cache names holds the content of its name. An unfinished last line is
    redacted on its own, so that the recorded cut always follows a newline. load(sha) gives the
    stored log named sha, or None; what it gives is used only when it holds that content."""
    start, head = 0, b""
    entry = cache.entries.get(key) if cache else None
    if entry and len(raw) >= entry["source_bytes"]:
        n = entry["source_bytes"]
        with perf.phase("verify cached"):
            same = sha256(memoryview(raw)[:n]) == entry["source_sha256"]
            log = load(entry["log_sha256"]) if same else None
            same = log is not None and len(log) >= entry["log_bytes"] and sha256(log) == entry["log_sha256"]
        if same:
            start, head = n, log[:entry["log_bytes"]]
            perf.count("transcript bytes not redacted again (cached)", n)
        del log
    end = max(start, raw.rfind(b"\n") + 1)
    body = redact(decoded(raw[start:end]))
    data = head + body + redact(decoded(raw[end:]))
    if cache is not None:
        cache.entries[key] = {"source_bytes": end, "source_sha256": sha256(memoryview(raw)[:end]),
                              "log_sha256": sha256(data), "log_bytes": len(head) + len(body)}
    return data


def _counted(hits: dict[str, Counter]) -> dict[str, dict[str, list]]:
    """Findings without their values: kind -> finding id -> [masked value, count], in the order
    they were first found."""
    return {kind: {finding_id(kind, value): [_mask(value), n] for value, n in values.items()}
            for kind, values in hits.items()}


def _add_counted(into: dict, more: dict) -> None:
    for kind, found in more.items():
        rows = into.setdefault(kind, {})
        for fid, (masked, n) in found.items():
            rows.setdefault(fid, [masked, 0])[1] += n


class ScanCache(LocalCache):
    """What scanning a stored log found, by the log's SHA-256: Redactor.hits_of_text, without the
    values. A log not scanned before is scanned from where the longest log scanned before ends,
    when that log is a prefix of it (same SHA-256 over its length, ending in a newline): logs are
    append-only, and the scan is line by line, so the findings of the whole are those of the
    prefix plus those of the rest."""

    def __init__(self, redact: Redactor, path: Path | None, trusted: bool = True) -> None:
        super().__init__(path, redact.fingerprint(), trusted)
        self.redact, self.used = redact, set()
        self.values: dict[str, tuple[str, str]] = {}  # finding id -> (kind, value), of what this run scanned

    def hits(self, sid: str | None, sha: str, data, size: int | None = None) -> dict:
        """{"leaks": ..., "review": ...} for data, whose SHA-256 the caller has computed as sha.
        data may be a function giving the bytes, called only when they are scanned; size is then
        their length. sid None: not a log, so not scanned from the end of an earlier one."""
        self.used.add(sha)
        size = len(data) if size is None else size
        if (entry := self.entries.get(sha)) and entry["bytes"] == size:
            perf.count("scan cache hits")
            return entry
        if callable(data):
            data = data()
        earlier = {e["bytes"]: s for s, e in self.entries.items()
                   if sid is not None and e.get("session") == sid and 0 < e["bytes"] < len(data)}
        with perf.phase("prefixes"):
            digests = prefix_digests(data, set(earlier))
        start = max((n for n, s in earlier.items() if digests.get(n) == s and data[n - 1] == 10), default=0)
        entry = {"session": sid, "bytes": len(data), "leaks": {}, "review": {}}
        if start:
            self.used.add(earlier[start])
            for part in ("leaks", "review"):
                _add_counted(entry[part], self.entries[earlier[start]][part])
            perf.count("scan bytes not scanned again (cached prefix)", start)
        leaks, review = self.redact.raw_hits(data[start:].decode(errors="replace"))
        for hits in (leaks, review):  # in memory only; remember_findings keeps them, never this cache
            self.values |= {finding_id(kind, value): (kind, value) for kind, values in hits.items() for value in values}
        _add_counted(entry["leaks"], _counted(leaks))
        _add_counted(entry["review"], _counted(review))
        self.entries[sha] = entry
        return entry

    def save(self, keep: set[str] | None = None) -> None:
        super().save(self.used if keep is None else keep)


class CheckCache(LocalCache):
    """What `check` worked out from content, besides scanning (ScanCache), each under the SHA-256
    of exactly the content it came from:

    - "gz:<sha of a .gz file's bytes>": the SHA-256 and length of what those bytes decompress to.
      Decompression is deterministic, so the same .gz bytes always hold the same content, and a
      stored snapshot is verified against its name without decompressing it again.
    - "prefixes:<sha of a log>": {length: SHA-256 of the log's first length bytes}.
    - "metrics:<sha of the inputs>": whether a metrics.json is what its log, subagent logs,
      manifest and price list give. That depends on sync.py and metrics.py, which the
      fingerprint leaves out, so the caller puts a digest of them in the key."""

    def __init__(self, redact: Redactor, path: Path | None, trusted: bool = True) -> None:
        super().__init__(path, redact.fingerprint(), trusted)
        self.used: set[str] = set()

    def get(self, key: str):
        self.used.add(key)
        return self.entries.get(key)

    def put(self, key: str, value) -> None:
        self.used.add(key)
        self.entries[key] = value

    def snapshot(self, path: Path) -> tuple[str, int, bytes | None, bytes] | None:
        """(SHA-256, length, content or None, .gz bytes) of a stored snapshot, None if there is no
        file. The content is decompressed only when these .gz bytes were not seen before; the
        caller decompresses the returned .gz bytes when it needs it, never the file again."""
        try:
            gz = path.read_bytes()
        except FileNotFoundError:
            return None
        with perf.phase("hash gz"):
            key = "gz:" + sha256(gz)
        if (entry := self.get(key)) is not None:
            perf.count("snapshot cache hits")
            return entry["sha256"], entry["bytes"], None, gz
        data = decompress(gz)
        with perf.phase("hash"):
            actual = sha256(data)
        self.put(key, {"sha256": actual, "bytes": len(data)})
        return actual, len(data), data, gz

    def prefix_digests(self, sha: str, content, lengths: set[int]) -> dict[int, str]:
        """prefix_digests(content(), lengths) for the log whose content has SHA-256 sha."""
        key = "prefixes:" + sha
        known = {int(n): d for n, d in (self.get(key) or {}).items()}
        if not lengths <= known.keys():
            with perf.phase("prefixes"):
                known |= prefix_digests(content(), lengths)
            self.put(key, {str(n): d for n, d in sorted(known.items())})
        else:
            perf.count("prefix cache hits")
        return {n: known[n] for n in lengths if n in known}

    def save(self, keep: set[str] | None = None) -> None:
        super().save(self.used if keep is None else keep)
