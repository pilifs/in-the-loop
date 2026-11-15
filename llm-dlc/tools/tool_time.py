#!/usr/bin/env python3
"""Where feature loops' time went: how long the agent was blocked on tools, by what it ran, by loop,
and by cargo test binary. It reads the redacted logs that sync.py stores (or, with --fetch, the
published copies of those not stored here), never a raw transcript.

    python3 llm-dlc/tools/tool_time.py                       # every loop session the repo names
    python3 llm-dlc/tools/tool_time.py --loop test-cost      # one loop, streams included
    python3 llm-dlc/tools/tool_time.py --since 2026-11-15 --format json

What it counts:
- A session belongs to a loop through the `- session:` line of a brief's Loop settings, or the
  `session ID` its loop-summaries record names. A stream's brief (`foundations-heap`) counts towards
  its loop (`foundations`): the shortest brief name with a session that it equals or starts with
  followed by `-`. `--session SID=LOOP` adds a session no brief names.
- Active time, and the model's share of it, are metrics.py's: each prompt from its start to its last
  record, and the model calls' spans within it, in the main transcript (subagents are left out).
- Blocked time is counted per batch: the tool calls one model call issued, which run in parallel.
  A batch costs the time its calls cover, once, and that time goes to the category of the call
  that finished last, the one the agent was waiting for. A call over two hours (a question left
  overnight, a session suspended) is left out.
- A call is put in the first category its command matches (CATEGORIES). A call that only reads
  or waits on the output of a command started in the background (its task id, its output file, or
  a file it redirected to) counts as waiting on that command's category.
- Cargo's own timings come from the output a cargo test call kept: `Running X` followed by
  `test result: ... finished in Ns` gives a binary's time, `Finished ... in Ns` the compile time.
  Output cut by `grep` or `tail` keeps only some of them, so per-binary numbers are a sample.
  A "full suite" run is a debug `cargo test` with no target, filter or `--ignored`.

Standard library only, besides metrics.py next to it.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shlex
import statistics
import sys
import urllib.request
from pathlib import Path

import metrics

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path.home() / ".cache" / "llm-traces" / "logs"
LONG_MS = 2 * 3600_000

# (category, pattern over a Bash command), first match wins. Order matters: an integration script
# runs cargo test, and `cargo test && sync.py commit` is a test run.
CATEGORIES = [
    ("integration check", r"-integration\.sh\b"),
    ("cargo test", r"\bcargo\s+(?:\+\S+\s+)?(?:test|nextest)\b"),
    ("proof inline", r"\bjbmc\b|(?:\bjvmcontract|\$\{?\w+\}?)\s+(?:prove|verify|equivalence|tlc)\b|\btla2tools\b"
                     r"|\btlc2\b|\bverify\.sh\b"),
    ("benchmark inline", r"\bbenchmark/run\.py\b"),
    ("cargo build", r"\bcargo\s+(?:\+\S+\s+)?(?:build|check|clippy|run|doc)\b"),
    ("python tests", r"\btest_\w+\.py\b|\bunittest\b|\bpytest\b"),
    ("build.py", r"\bbuild\.py\b"),
    ("sync.py", r"\bsync\.py\b"),
]
NON_BASH = {"AskUserQuestion": "asking the user", "Agent": "subagents", "Task": "subagents"}
WAIT = "waiting on background "
OTHER = "other"

VALUE_OPTIONS = {"--manifest-path", "-p", "--package", "-j", "--jobs", "--features", "-F", "--target-dir",
                 "--color", "--message-format", "--target", "--config", "-Z"}
NOT_FULL = {"--test", "--lib", "--doc", "--bin", "--bins", "--tests", "--example", "--examples", "--bench",
            "--benches", "--release", "-r", "--profile", "--all-targets"}
HARNESS_OK = {"--nocapture", "--show-output", "-q", "--quiet", "--color", "--format"}
HARNESS_VALUE = {"--test-threads", "--color", "--format"}


# --------------------------------------------------------------------------- which sessions

def discover(root: Path) -> dict[str, str]:
    """Session id -> the brief it ran, from the briefs' Loop settings and the loop summaries."""
    found: dict[str, str] = {}
    for brief in sorted((root / "llm-dlc" / "loops").glob("*.md")):
        for line in brief.read_text().splitlines():
            m = re.match(r"- session: ([0-9a-f]{8}-[0-9a-f-]{27})\s*$", line)
            if m:
                found[m[1]] = brief.stem
    for record in sorted((root / "llm-dlc" / "loop-summaries").glob("*.md")):
        m = re.search(r"\bsession ([0-9a-f]{8}-[0-9a-f-]{27})\b", record.read_text()[:4000])
        name = re.sub(r"^\d{4}-\d\d-\d\d-\d{6}-", "", record.stem)
        if m and name != record.stem:
            found.setdefault(m[1], name)
    return found


def loop_of(brief: str, briefs: set[str]) -> str:
    """The loop a brief belongs to: the shortest brief it equals or extends with `-...`."""
    return min((b for b in briefs if brief == b or brief.startswith(b + "-")), key=len, default=brief)


# --------------------------------------------------------------------------- reading a log

def load_entries(root: Path, sid: str, fetch: bool, cache: Path = CACHE) -> list[dict] | None:
    """The session's latest redacted log, stored here or (with fetch) its published copy, checked
    against the sha256 it is named by. None when there is neither."""
    manifest_path = root / "llm-dlc" / "traces" / sid / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text())
    log = manifest.get("log") or {}
    sha = log.get("sha256")
    if not sha:
        return None
    candidates = [root / log["path"]] if log.get("path") else []
    candidates.append(cache / sid / f"{sha}.jsonl.gz")
    data = next((gzip.decompress(p.read_bytes()) for p in candidates if p.exists()), None)
    if data is None and fetch:
        url = ((manifest.get("logs") or {}).get(sha) or {}).get("url")
        if not url:
            return None
        req = urllib.request.Request(url, headers={"User-Agent": "llm-traces-tool-time"})
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
        data = gzip.decompress(raw)
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError(f"{url}: content does not match its name")
        candidates[-1].parent.mkdir(parents=True, exist_ok=True)
        candidates[-1].write_bytes(raw)
    if data is None or hashlib.sha256(data).hexdigest() != sha:
        return None
    return read_jsonl(data)


def read_jsonl(data: bytes) -> list[dict]:
    """As sync.py reads a log, so that line numbers and records are the ones metrics.json was built from."""
    out = []
    for line in data.decode(errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def classify(name: str, inp: dict) -> str:
    if name != "Bash":
        return NON_BASH.get(name, OTHER)
    command = inp.get("command") or ""
    return next((cat for cat, pattern in CATEGORIES if re.search(pattern, command)), OTHER)


def _redirects(command: str) -> set[str]:
    """Files a command writes its output to, which a later call may read to wait on it."""
    return {m[1] for m in re.finditer(r"(?:>>?|\btee\s+(?:-a\s+)?)\s*([~/][^\s;&|)'\"]+)", command)}


def _detaches(command: str) -> bool:
    """A foreground command that leaves something running: `... &`, `nohup`, `setsid`."""
    return bool(re.search(r"(?<![&>|])&\s*(?:$|\n|;|\))|\bnohup\b|\bsetsid\b", command))


def _text(content) -> str:
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content if isinstance(content, str) else ""


def read_calls(entries: list[dict]) -> list[dict]:
    """The main transcript's tool calls in order, each with its batch, category, span and output."""
    calls: dict[str, dict] = {}
    background: list[tuple[set[str], str]] = []  # (what names its output, its category)
    for e in entries:
        if e.get("isSidechain"):
            continue
        ts = e.get("timestamp")
        if e.get("type") == "assistant":
            msg = e.get("message") or {}
            for b in metrics._blocks(msg):
                if b.get("type") == "tool_use" and b.get("id") not in calls:
                    inp = b.get("input") or {}
                    calls[b["id"]] = {"batch": msg.get("id") or e.get("requestId"), "name": b.get("name"),
                                      "input": inp, "category": classify(b.get("name"), inp),
                                      "start": metrics._ms(ts), "end": None, "text": ""}
        elif e.get("type") == "user":
            for b in metrics._blocks(e.get("message")):
                call = calls.get(b.get("tool_use_id")) if b.get("type") == "tool_result" else None
                if call is None or call["end"] is not None:
                    continue
                call["end"], call["text"] = metrics._ms(ts), _text(b.get("content"))
                inp = call["input"]
                if call["category"] == OTHER and background:
                    said = json.dumps(inp)
                    for names, category in reversed(background):
                        if any(n in said for n in names):
                            call["category"] = WAIT + category
                            break
                if call["name"] == "Bash" and (inp.get("run_in_background") or _detaches(inp.get("command") or "")):
                    result = e.get("toolUseResult")
                    tid = ((result.get("backgroundTaskId") if isinstance(result, dict) else None)
                           or (re.search(r"background with ID: (\w+)", call["text"]) or [None, None])[1])
                    names = _redirects(inp.get("command") or "") | ({f"{tid}.output", tid} if tid else set())
                    if names:
                        background.append((names, call["category"].removeprefix(WAIT)))
    return [c for c in calls.values() if c["end"] is not None]


def batches(calls: list[dict]) -> list[tuple[str, int]]:
    """(category, blocked ms) per batch, calls over LONG_MS left out."""
    groups: dict[str, list[dict]] = {}
    for c in calls:
        if c["end"] - c["start"] <= LONG_MS:
            groups.setdefault(c["batch"], []).append(c)
    out = []
    for group in groups.values():
        last = max(group, key=lambda c: c["end"])
        out.append((last["category"], metrics.covered_ms((c["start"], c["end"]) for c in group)))
    return out


# --------------------------------------------------------------------------- cargo's own timings

def _seconds(text: str) -> float:
    m = re.fullmatch(r"(?:(\d+)m\s*)?([\d.]+)s", text.strip())
    return (int(m[1] or 0) * 60 + float(m[2])) if m else 0.0


def _binary(path: str) -> str:
    """`tests/conformance.rs` -> `conformance.rs`; `unittests src/lib.rs` -> `src/lib.rs (unit)`."""
    path = path.strip()
    if path.startswith("unittests "):
        return path.split(None, 1)[1] + " (unit)"
    return path.rsplit("/", 1)[-1]


def cargo_timings(command: str, output: str) -> dict:
    """What a cargo test call's output says: compile seconds and each binary's test seconds."""
    single = re.findall(r"--test[ =](\w+)", command)
    compile_s, binaries, current = 0.0, [], None
    for line in output.splitlines():
        line = line.strip()
        if m := re.search(r"Finished `\w+` profile .* in ((?:\d+m )?[\d.]+s)", line):
            compile_s += _seconds(m[1])
        elif m := re.match(r"Running (.+?) \(", line):
            current = _binary(m[1])
        elif m := re.match(r"Doc-tests (\S+)", line):
            current = f"doc-tests {m[1]}"
        elif m := re.search(r"(?:^(\w+):\s*)?test result: \w+\..*finished in ([\d.]+)s", line):
            name = (m[1] + ".rs") if m[1] else current or (single[0] + ".rs" if len(single) == 1 else None)
            binaries.append((name, float(m[2])))
            current = None
    return {"compile_s": compile_s, "binaries": binaries}


def _invocations(command: str) -> list[list[str]]:
    out = []
    for m in re.finditer(r"\bcargo\s+(?:\+\S+\s+)?test\b(.*?)(?=\||;|&&|\|\||\n|2>|>|\)|$)", command):
        try:
            out.append(shlex.split(m[1]))
        except ValueError:
            out.append(m[1].split())
    return out


def full_suite(command: str) -> bool:
    """A debug `cargo test` of every target with no filter: what "run the whole suite" means."""
    invocations = _invocations(command)
    if not invocations or "nextest" in command:
        return False
    for words in invocations:
        harness, skip = False, False
        for w in words:
            if skip:
                skip = False
                continue
            if w == "--":
                harness = True
                continue
            key = w.split("=", 1)[0]
            if not harness:
                if key in NOT_FULL:
                    return False
                if key in VALUE_OPTIONS:
                    skip = "=" not in w
                elif not w.startswith("-"):
                    return False
            else:
                if key in HARNESS_VALUE:
                    skip = "=" not in w
                elif key not in HARNESS_OK:
                    return False
    return True


# --------------------------------------------------------------------------- one session, all sessions

def session_time(sid: str, entries: list[dict]) -> dict:
    found = metrics.session({"session_id": sid}, entries, [], {"models": {}}, lambda s: s)
    calls = read_calls(entries)
    cargo = []
    for c in calls:
        if c["category"] == "cargo test" and c["end"] - c["start"] <= LONG_MS:
            command = c["input"].get("command") or ""
            cargo.append({"ms": c["end"] - c["start"], "full_suite": full_suite(command),
                          "release": bool(re.search(r"\s(?:--release|-r)\b", command)),
                          **cargo_timings(command, c["text"])})
    return {"active_ms": found["time"]["agent_ms"], "model_ms": found["time"]["model_ms"],
            "batches": batches(calls), "cargo": cargo}


def _h(ms: float) -> float:
    return round(ms / 3_600_000, 1)


def analyse(sessions: dict[str, tuple[str, dict]]) -> dict:
    """sessions: id -> (loop, session_time). Everything the report shows, as data."""
    by_cat: dict[str, int] = {}
    by_loop: dict[str, dict] = {}
    cargo = []
    for sid, (loop, t) in sessions.items():
        row = by_loop.setdefault(loop, {"loop": loop, "sessions": 0, "active_ms": 0, "model_ms": 0, "tool_ms": 0,
                                        "cargo_test_ms": 0})
        row["sessions"] += 1
        row["active_ms"] += t["active_ms"]
        row["model_ms"] += t["model_ms"]
        for cat, ms in t["batches"]:
            by_cat[cat] = by_cat.get(cat, 0) + ms
            row["tool_ms"] += ms
            if cat in ("cargo test", WAIT + "cargo test"):
                row["cargo_test_ms"] += ms
        cargo += t["cargo"]
    tool_ms = sum(by_cat.values())
    timed = [c for c in cargo if c["binaries"] or c["compile_s"]]
    per_bin: dict[str, list[float]] = {}
    unnamed = 0.0
    for c in timed:
        for name, s in c["binaries"]:
            if name:
                per_bin.setdefault(name, []).append(s)
            else:
                unnamed += s
    named_s = sum(sum(v) for v in per_bin.values())
    test_s = named_s + unnamed
    cargo_ms = sum(c["ms"] for c in cargo)

    def spread(rows: list[dict]) -> dict:
        ms = sorted(c["ms"] for c in rows)
        return {"calls": len(ms), "ms": sum(ms), "share": round(sum(ms) / cargo_ms, 3) if cargo_ms else 0,
                "median_s": round(statistics.median(ms) / 1000, 1) if ms else None,
                "p90_s": round(ms[int(0.9 * (len(ms) - 1))] / 1000, 1) if ms else None,
                "over_2min": sum(m > 120_000 for m in ms)}
    return {
        "sessions": len(sessions),
        "loops": len(by_loop),
        "active_ms": sum(r["active_ms"] for r in by_loop.values()),
        "model_ms": sum(r["model_ms"] for r in by_loop.values()),
        "tool_ms": tool_ms,
        "by_category": [{"category": k, "ms": v, "share": round(v / tool_ms, 3) if tool_ms else 0}
                        for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])],
        "by_loop": sorted(by_loop.values(), key=lambda r: -r["active_ms"]),
        "cargo_test": {
            "calls": len(cargo), "ms": cargo_ms, "timed_calls": len(timed),
            "compile_s": round(sum(c["compile_s"] for c in timed), 1), "test_s": round(test_s, 1),
            "unnamed_test_s": round(unnamed, 1),
            "full_suite": spread([c for c in cargo if c["full_suite"]]),
            "debug": spread([c for c in cargo if not c["release"]]),
            "release": spread([c for c in cargo if c["release"]]),
            "by_binary": sorted(({"binary": k, "runs": len(v), "total_s": round(sum(v), 1),
                                  "mean_s": round(sum(v) / len(v), 1),
                                  "share": round(sum(v) / named_s, 3) if named_s else 0}
                                 for k, v in per_bin.items()), key=lambda r: -r["total_s"]),
        },
    }


def markdown(a: dict, missing: list[str], top: int = 15) -> str:
    pct = lambda x: f"{100 * x:.0f}%"
    lines = [f"# Where the loops' time went", "",
             f"{a['sessions']} sessions in {a['loops']} loops. Active agent time {_h(a['active_ms'])}h: the model "
             f"{_h(a['model_ms'])}h, blocked on tools {_h(a['tool_ms'])}h.", ""]
    if missing:
        lines += [f"Left out, with no log here (`--fetch` gets the published copy): {', '.join(missing)}.", ""]
    lines += ["## Blocked time by category", "", "| Category | Hours | Share |", "|---|---|---|"]
    shown = [r for r in a["by_category"] if _h(r["ms"]) > 0]
    lines += [f"| {r['category']} | {_h(r['ms'])} | {pct(r['share'])} |" for r in shown]
    if len(shown) < len(a["by_category"]):
        lines += ["", f"{len(a['by_category']) - len(shown)} categories under 0.05h are left out (`--format json` has them)."]
    lines += ["", "## By loop", "", "| Loop | Sessions | Active h | Model h | Tools h | cargo test and waiting on it |",
              "|---|---|---|---|---|---|"]
    lines += [f"| {r['loop']} | {r['sessions']} | {_h(r['active_ms'])} | {_h(r['model_ms'])} | {_h(r['tool_ms'])} | "
              f"{_h(r['cargo_test_ms'])}h, {pct(r['cargo_test_ms'] / r['active_ms']) if r['active_ms'] else '-'} of active |"
              for r in a["by_loop"]]
    c = a["cargo_test"]
    lines += ["", "## cargo test", "",
              f"{c['calls']} calls, {_h(c['ms'])}h. In the {c['timed_calls']} whose output kept cargo's timings, "
              f"compiling took {_h(c['compile_s'] * 1000)}h and running the tests {_h(c['test_s'] * 1000)}h.", "",
              "| Calls | Count | Share of cargo test time | Median | p90 | Over 2 min |", "|---|---|---|---|---|---|"]
    for label, key in (("full-suite debug runs", "full_suite"), ("all debug runs", "debug"), ("release runs", "release")):
        f = c[key]
        lines.append(f"| {label} | {f['calls']} | {pct(f['share'])} | {f['median_s']}s | {f['p90_s']}s | {f['over_2min']} |")
    lines += ["",
              f"{_h(c['unnamed_test_s'] * 1000)}h of the test time is in output that doesn't say which binary ran "
              "(a `grep` kept only the totals); the shares below are of the rest.", "",
              "| Binary | Runs timed | Mean per run | Share of named test time |", "|---|---|---|---|"]
    lines += [f"| `{r['binary']}` | {r['runs']} | {r['mean_s']}s | {pct(r['share'])} |" for r in c["by_binary"][:top]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--loop", action="append", default=[], help="only this loop (repeatable)")
    ap.add_argument("--exclude", action="append", default=[], help="leave this loop out (repeatable)")
    ap.add_argument("--session", action="append", default=[], metavar="SID=LOOP", help="add a session no brief names")
    ap.add_argument("--since", help="sessions started on or after this date (YYYY-MM-DD)")
    ap.add_argument("--until", help="sessions started before this date")
    ap.add_argument("--fetch", action="store_true", help=f"download published logs not stored here, into {CACHE}")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)

    named = discover(args.root)
    briefs = set(named.values())
    for pair in args.session:
        sid, _, loop = pair.partition("=")
        named[sid] = loop
        briefs.add(loop)
    sessions, missing = {}, []
    for sid, brief in sorted(named.items()):
        loop = loop_of(brief, briefs)
        if (args.loop and loop not in args.loop) or loop in args.exclude:
            continue
        manifest = args.root / "llm-dlc" / "traces" / sid / "manifest.json"
        started = json.loads(manifest.read_text()).get("started") or "" if manifest.exists() else ""
        if (args.since and started < args.since) or (args.until and started >= args.until):
            continue
        entries = load_entries(args.root, sid, args.fetch)
        if entries is None:
            missing.append(f"{loop} ({sid[:8]})")
            continue
        sessions[sid] = (loop, session_time(sid, entries))
    result = analyse(sessions)
    if args.format == "json":
        print(json.dumps({**result, "missing": missing}, indent=1))
    else:
        print(markdown(result, missing), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
