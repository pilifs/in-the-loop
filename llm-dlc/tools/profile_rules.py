#!/usr/bin/env python3
"""Where a cold scan's time goes, rule by rule, and what a rewrite in another language would have
to keep. The measurements behind llm-dlc/performance.md, so they can be taken again.

    python3 llm-dlc/tools/profile_rules.py [--processes N] [LOG.jsonl.gz ...]

Without a log it profiles the largest stored one. For each log it prints:

- each rule's time as a scan applies it (once per JSON string, as Rules.hits_of_line does) and in
  one pass over all the strings joined, which tells the cost of calling a rule 1.5 million times
  from Python from the cost of the regular expression itself;
- how many lines hold a literal that one of the credential rules needs: a cheap per-line gate;
- how many lines a JSON encoder that sorts keys or escapes <, > and & would write differently.

--processes N also scans the distinct lines of the given logs in N processes and in one.
Prints rule names and numbers only, never what a rule matched. Changes nothing."""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redaction_rules  # noqa: E402
import sync  # noqa: E402

# A literal that each credential rule's match contains: a measurement, not a rule. bearer,
# basic-auth, url-password, curl-user and env-secret have none worth gating on.
GATE = re.compile(r"sk-|gh[pousr]_|github_pat_|glpat-|AKIA|AIza|ya29\.|xox[abprs]-|npm_|hf_|k_(?:live|test)_"
                  r"|SG\.|eyJ|-----BEGIN|hooks\.slack|discord|k-lf-|accountUuid|organizationUuid|userID")


def _load(line: str):
    try:
        return json.loads(line)
    except ValueError:
        return line


def _keys_sorted(obj) -> bool:
    if isinstance(obj, dict):
        return list(obj) == sorted(obj) and all(_keys_sorted(v) for v in obj.values())
    return all(_keys_sorted(v) for v in obj) if isinstance(obj, list) else True


def _timed(fn) -> tuple[float, int]:
    start = time.perf_counter()
    n = fn()
    return time.perf_counter() - start, n


def rules(red: sync.Redactor) -> list[tuple[str, list[re.Pattern], str | None]]:
    """(name, patterns, hint kind) in the order hits_of_line applies them. The personal literals
    are one row: their kinds and values are this machine's."""
    rows = [(f"personal literals ({len(red.literals)})", [rx for _k, rx, _r in red.literals], None)]
    rows += [(f"secret {kind}", [rx], kind) for kind, rx, _r in red.secret_res]
    rows += [("email", [redaction_rules.EMAIL_RE], None), ("windows-user", [redaction_rules.WIN_USER_RE], None)]
    rows += [("username", [red.user_re], "username")] if red.user_re is not None else []
    rows += [(f"review {kind}", [rx], None) for kind, rx, _keep in red.review_res]
    return rows


def profile(path: Path, red: sync.Redactor) -> None:
    text = gzip.decompress(path.read_bytes()).decode()
    lines = [line for line in text.split("\n") if line]
    load_s, objs = time.perf_counter(), [_load(line) for line in lines]
    load_s = time.perf_counter() - load_s
    walk_s, strings = time.perf_counter(), [s for o in objs for s in redaction_rules._strings(o)]
    walk_s = time.perf_counter() - walk_s
    joined = "\x00".join(strings)
    print(f"{path.name[:12]}…: {len(text) / 1e6:.1f} M chars, {len(lines)} lines, {len(strings)} strings "
          f"({len(joined) / 1e6:.1f} M chars); json.loads {load_s:.2f} s, string walk {walk_s:.2f} s")
    print(f"  {'rule':32s} {'per string':>10s} {'one pass':>9s}")
    total_each = total_once = 0.0
    trivial = re.compile("\x00\x01\x02")
    for name, patterns, hint in [("(a regex that never matches)", [trivial], None)] + rules(red):
        if hint == "username":
            may = red._user_may_match
        else:
            may = (lambda s, k=hint: red._may_match(k, s)) if hint else (lambda s: True)
        each, _ = _timed(lambda: sum(1 for s in strings if may(s) for rx in patterns for _m in rx.finditer(s)))
        once, _ = _timed(lambda: sum(1 for rx in patterns for _m in rx.finditer(joined)))
        if patterns[0] is not trivial:
            total_each, total_once = total_each + each, total_once + once
        print(f"  {name:32s} {each:9.2f}s {once:8.2f}s")
    print(f"  {'all rules':32s} {total_each:9.2f}s {total_once:8.2f}s")
    gate_s, gated = _timed(lambda: sum(1 for line in lines if GATE.search(line)))
    print(f"  credential gate: {gated} of {len(lines)} lines ({100 * gated / len(lines):.1f}%) hold a literal "
          f"a credential rule needs, found in {gate_s:.2f} s")
    parsed = [o for o in objs if not isinstance(o, str)]
    unsorted = sum(not _keys_sorted(o) for o in parsed)
    html = sum(any(c in line for c in "<>&") for line in lines)
    wide = sum(any(ord(c) > 127 for c in line) for line in lines)
    print(f"  JSON: {len(lines) - len(parsed)} lines not JSON; keys not in sorted order in {unsorted} lines; "
          f"< > or & in {html}; non-ASCII in {wide}")


_red = None


def _init() -> None:
    global _red
    _red = sync.Redactor()


def _scan(chunk: list[str]) -> float:
    start = time.process_time()
    for line in chunk:
        _red.hits_of_line(line)
    return time.process_time() - start


def pooled(paths: list[Path], processes: int) -> None:
    seen: set[str] = set()
    lines = [line for p in paths for line in gzip.decompress(p.read_bytes()).decode().split("\n")
             if line and not (line in seen or seen.add(line))]
    size = sum(map(len, lines)) / (12 * processes) or 1
    chunks, chunk, n = [], [], 0
    for line in lines:
        chunk.append(line)
        n += len(line)
        if n >= size:
            chunks, chunk, n = chunks + [chunk], [], 0
    chunks.append(chunk)
    for workers in sorted({1, processes}):
        start = time.perf_counter()
        with Pool(workers, initializer=_init) as pool:
            cpu = sum(pool.map(_scan, chunks, chunksize=1))
        wall = time.perf_counter() - start
        print(f"{len(lines)} distinct lines in {workers} process(es): {wall:.1f} s wall, {cpu:.1f} s CPU")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("logs", nargs="*", type=Path)
    parser.add_argument("--processes", type=int, default=0)
    args = parser.parse_args(argv)
    paths = args.logs or sorted(sync.TRACES.glob("*/logs/*.jsonl.gz"), key=lambda p: p.stat().st_size)[-1:]
    if not paths:
        print("no stored logs")
        return 1
    red = sync.Redactor()
    for path in paths:
        profile(path, red)
    if args.processes:
        pooled(paths, args.processes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
