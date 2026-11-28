#!/usr/bin/env python3
"""A Gradle build reads, offline, a library the resolver fetched: a gate for the readiness view's Gradle init script.

S48's own gate (../maven-war/readiness_gate.py) passed with a replay that brings its own file mirror. An ordinary
Gradle build has none: offline, it reads a remote repository's modules from Gradle's cache and nowhere else, and
the resolver lays what it fetches in Maven's layout. So every readiness view carries an init script
(jobs/readiness.py, GRADLE_INIT) that gives the build a file repository over the view's Maven-layout folder. This
gate shows it on a real build: Spring Boot's core module at S48's parent pin, compiled offline, with
org.jspecify:jspecify taken out of every cache (readiness-operation.json, `base.without`).

One request, as in the other gate: a consumer job that needs the operation and an unrelated job are committed to
a throwaway repository with this checkout's pipeline, the consumer waits, the request is admitted, the resolution
job runs the task offline until it names the library, fetches its POM, its Gradle module metadata and its JAR from
Maven Central, proves the task offline and publishes the bundle, and the consumer compiles the module itself, with
no network, on the view of the base and the bundle. Its compiled.json must be byte for byte what the resolution's
own offline run wrote. compile.sh fails if either of Gradle's caches holds the library after the build: then the
file repository is the only place it can have been read from.

  python3 verification/merged-pr-links/s01-s50/gradle-module/gate.py --output FILE

Exit 0 when every check passed; the record (FILE) has each check with what was seen.
"""
import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REL = HERE.relative_to(ROOT).as_posix()
spec = importlib.util.spec_from_file_location("readiness_gate", HERE.parent / "maven-war" / "readiness_gate.py")
readiness_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness_gate)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, required=True, help="where the gate's record is written")
    parser.add_argument("--work", type=Path, help="a folder for the throwaway repository and the store (default: a new one under ~/.cache/in-the-loop/readiness-gates)")
    parser.add_argument("--wait", type=float, default=3600, help="seconds to wait for the resolution and the consumer (default 3600)")
    args = parser.parse_args(argv)
    operation = json.loads((HERE / "readiness-operation.json").read_text())
    work = args.work or Path.home() / ".cache/in-the-loop/readiness-gates" / (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-gradle-module")
    work.mkdir(parents=True, exist_ok=True)
    settings = {"isolation": "none", "workers": 2, "cpus": float(operation["resources"]["cpus"]) + 1, "memory": "9G", "job_memory_max": "8G",
                "memory_floor": "0", "keep_workdirs": "never", "poll_seconds": 2, "link": [], "after_collect": [],
                "fetch_allow": [readiness_gate.CENTRAL], "fetch_slots": 10}
    gate = readiness_gate.Gate(work, operation, consumer_steps=[("compile", f"bash {REL}/compile.sh")], expected={"compiled.json": None}, settings=settings)
    record = {"schema": "itl-gradle-module-readiness-gate/v1", "startedAt": readiness_gate.now(), "operation": f"{REL}/readiness-operation.json", "work": str(work)}
    try:
        gate.build_repository([REL])
        record["request"] = request = gate.one_request(args.wait)
        fetched = [f["path"] for f in ((request.get("receipt") or {}).get("bundle") or {}).get("files") or []]
        gate.check("the library was fetched with its Gradle module metadata, in Maven's layout",
                   any(p.endswith(".module") for p in fetched) and any(p.endswith(".jar") for p in fetched) and all(p.startswith("m2/org/jspecify/jspecify/") for p in fetched),
                   fetched)
    except Exception as e:  # noqa: BLE001  (the record says what stopped it)
        gate.check("the gate ran to its end", False, f"{type(e).__name__}: {e}")
    finally:
        gate.stop_runner()
    return readiness_gate.conclude(gate, record, work, args.output)


if __name__ == "__main__":
    sys.exit(main())
