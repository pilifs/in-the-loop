"""What a step did besides exiting: which tests executed, and where that was read.

An exit code says a command ended as its job expected. It does not say a test ran: on 2026-11-26 a setup job
passed, 8 of 8 steps, and three of its builds had stopped at a test compile, because the script around them
exited 0 whatever the build did (VF-070, item 11). A step that *promises* tests (`promises.tests` in a job of the
second format) is therefore held to evidence of them, read here:

  - from JUnit XML reports, when the step says where they are (`reports`, as globs): what Gradle, Maven's
    surefire and most other runners write, with every test's name and how it ended;
  - else from the step's log: the summary lines of cargo, unittest, pytest, Maven and Gradle.

`tests(...)` gives the record a result keeps: the source read, the suites, how many tests executed, failed by
assertion, ended in an error and were skipped, and the names of the ones that did not pass. `kept(...)` says
whether that keeps the promise. A compile-only step promises nothing and is not looked at. A step that expects
named tests to fail (a regression test on the revision before its fix) keeps its promise when exactly those
failed, in a test: a build that broke before any test ran has not shown the failure it was to show.

Standard library only.
"""
from __future__ import annotations

import glob
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# A step's log, when no report says more: (source, pattern); each match is one suite or one run.
LOG_SUMMARIES = [
    ("cargo test", re.compile(r"^test result: (?:ok|FAILED)\. (?P<passed>\d+) passed; (?P<failed>\d+) failed; (?P<skipped>\d+) ignored", re.M)),
    ("unittest", re.compile(r"^Ran (?P<run>\d+) tests? in [\d.]+s\s*\n\s*\n(?:OK|FAILED)(?: \((?P<detail>[^)]*)\))?", re.M)),
    ("pytest", re.compile(r"^=+ (?P<pytest>[^=\n]*\b(?:passed|failed|errors?)\b[^=\n]*) in [\d.]+s[^=\n]*=+\s*$", re.M)),
    ("maven surefire", re.compile(r"^(?:\[\w+\]\s+)?Tests run: (?P<run>\d+), Failures: (?P<failed>\d+), Errors: (?P<errors>\d+), Skipped: (?P<skipped>\d+)\s*$", re.M)),
    ("gradle", re.compile(r"^(?P<run>\d+) tests completed(?:, (?P<failed>\d+) failed)?(?:, (?P<skipped>\d+) skipped)?", re.M)),
]


def _count(text: str, word: str) -> int:
    m = re.search(rf"(\d+) {word}", text)
    return int(m[1]) if m else 0


def from_reports(root: Path, patterns: list[str], since: float | None = None) -> dict | None:
    """The tests that JUnit XML reports record, or None when no file matches. A report that cannot be read is
    counted as one, and named: a damaged report is not evidence of nothing. With `since`, only reports written
    from that time on: what was there before the step began is not what it ran."""
    files = sorted({p for pattern in patterns for p in glob.glob(str(Path(root) / pattern), recursive=True)})
    older = [p for p in files if since is not None and Path(p).stat().st_mtime < since]
    files = [p for p in files if p not in older]
    if not files:
        return None
    record = {"source": "junit-xml", "reports": len(files), "suites": [], "executed": 0, "failed": 0, "errors": 0,
              "skipped": 0, "failing": [], "erroring": [], "unreadable": []}
    for name in files:
        try:
            top = ET.parse(name).getroot()
        except (ET.ParseError, OSError) as e:
            record["unreadable"].append(f"{Path(name).name}: {e}")
            continue
        for suite in ([top] if top.tag == "testsuite" else top.iter("testsuite")):
            cases = list(suite.iter("testcase"))
            skipped = sum(1 for c in cases if c.find("skipped") is not None)
            record["suites"].append(suite.get("name") or Path(name).stem)
            record["executed"] += len(cases) - skipped
            record["skipped"] += skipped
            for case in cases:
                label = f"{case.get('classname')}.{case.get('name')}" if case.get("classname") else str(case.get("name"))
                if case.find("failure") is not None:
                    record["failed"] += 1
                    record["failing"].append(label)
                elif case.find("error") is not None:
                    record["errors"] += 1
                    record["erroring"].append(label)
    record["suites"] = sorted(set(record["suites"]))[:50]
    return record


def from_log(log: Path) -> dict | None:
    """The tests a log's summary lines record, or None when it has none. Names are not in a summary: `failing`
    stays empty, and a promise that names tests needs reports."""
    try:
        text = Path(log).read_text(errors="replace")
    except OSError:
        return None
    for source, pattern in LOG_SUMMARIES:
        found = list(pattern.finditer(text))
        if not found:
            continue
        record = {"source": f"log: {source}", "runs": len(found), "suites": [], "executed": 0, "failed": 0, "errors": 0,
                  "skipped": 0, "failing": [], "erroring": [], "unreadable": []}
        for m in found:
            g = m.groupdict()
            if g.get("pytest") is not None:
                failed, errors, skipped = _count(g["pytest"], "failed"), _count(g["pytest"], "errors?"), _count(g["pytest"], "skipped")
                executed = _count(g["pytest"], "passed") + failed + errors
            elif source == "cargo test":
                failed, errors, skipped = int(g["failed"]), 0, int(g["skipped"])
                executed = int(g["passed"]) + failed
            elif source == "unittest":
                detail = g.get("detail") or ""
                failed, errors = 0, 0
                for part in detail.split(","):
                    key, _, value = part.strip().partition("=")
                    if key == "failures":
                        failed = int(value or 0)
                    elif key == "errors":
                        errors = int(value or 0)
                skipped = next((int(p.strip().partition("=")[2] or 0) for p in detail.split(",") if p.strip().startswith("skipped=")), 0)
                executed = int(g["run"]) - skipped
            else:
                failed, errors, skipped = int(g.get("failed") or 0), int(g.get("errors") or 0), int(g.get("skipped") or 0)
                executed = int(g["run"]) - skipped
            record["executed"] += executed
            record["failed"] += failed
            record["errors"] += errors
            record["skipped"] += skipped
        return record
    return None


def tests(promise: dict, work: Path, log: Path, since: float | None = None) -> dict:
    """The record of a step that promised tests: what executed, by the best source there is, or that nothing says
    any did (`source: none`, executed 0), which is a fact of its own and not a count of zero from a report."""
    record = from_reports(work, promise["reports"], since) if promise.get("reports") else None
    if record is None:
        record = from_log(log)
    if record is None:
        looked = (f"no file matches {', '.join(promise['reports'])}, and " if promise.get("reports") else "") + \
            "the log has no test summary of cargo, unittest, pytest, Maven or Gradle"
        record = {"source": "none", "why": looked, "suites": [], "executed": 0, "failed": 0, "errors": 0, "skipped": 0,
                  "failing": [], "erroring": [], "unreadable": []}
    record["type"] = "tests"
    record["promised"] = {"min": promise.get("min", 1), **({"failing": sorted(promise["failing"])} if promise.get("failing") else {})}
    record["unmet"] = kept(promise, record)
    return record


def kept(promise: dict, record: dict) -> list[str]:
    """What of the promise the evidence does not show, in words; empty when it is kept."""
    unmet = []
    least = promise.get("min", 1)
    if record["executed"] < least:
        unmet.append(f"{record['executed']} test(s) executed, and the step promised at least {least}"
                     + (f" ({record['why']})" if record.get("why") else f" (read from {record['source']})"))
    if record.get("unreadable"):
        unmet.append(f"{len(record['unreadable'])} report(s) could not be read: {record['unreadable'][0]}")
    expected = sorted(promise.get("failing") or [])
    if expected:
        if record["source"] != "junit-xml":
            unmet.append("the step names tests it expects to fail, and only a report names the tests that did: give `reports`")
        else:
            failing = sorted(record["failing"])
            matches = lambda want: [f for f in failing if f == want or f.endswith("." + want) or f.split(".")[-1] == want]
            missing = [want for want in expected if not matches(want)]
            others = [f for f in failing if not any(f in matches(want) for want in expected)]
            if missing:
                unmet.append(f"expected to fail by assertion, and did not: {', '.join(missing)}")
            if others:
                unmet.append(f"failed, and was not expected to: {', '.join(others[:5])}")
            if record["errors"]:
                unmet.append(f"{record['errors']} test(s) ended in an error, not an assertion: {', '.join(record['erroring'][:5])}")
    elif record["failed"] or record["errors"]:
        unmet.append(f"{record['failed']} test(s) failed and {record['errors']} ended in an error")
    return unmet
