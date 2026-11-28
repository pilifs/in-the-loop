#!/usr/bin/env python3
"""Replay the S batch's first setup jobs through delayed setup: the control the brief names beside S48 (VF-070).

On 2026-11-27 the setup of Spring Boot S01-S50 resolved each case's own projects online (a first pass, ended
08:42 UTC), saw all 98 task graphs configure in offline dry runs, and submitted 49 build jobs. 41 failed for setup
reasons, 38 of them on modules of projects the cases' projects depend on, which a dry run does not resolve. A
second pass (09:40 to 10:39 UTC) added 1,392 module versions, and the 41 were resubmitted.

This asks what that first run would have been had each job said what it needs done. The cache is laid as it was
after the first pass (`base.asOf`: every file Gradle's cache wrote after 09:00 UTC is left out, by the files' own
times), and every case is one row of one manifest: a job of three steps (`case_task.sh CASE fix|parent|transplant`,
the cases' own table and Gradle options) that needs one readiness operation, the case's builds and landed tests at
both pins, at the level `tests-run`. The gate commits the batch to a throwaway repository with this checkout's
pipeline, starts a runner, admits the requests as the watcher does (`resolve`, then a commit), and waits.

The authorised source is a folder, not the network: what the second pass fetched, taken from the retained cache
and laid in Maven's layout with each file's SHA-1 (checked against the name Gradle filed it under). So the modules
are the builds the setup itself used, snapshots included, and nothing is asked of a repository twice. It is a
reconstruction, and every receipt says so (`base.why`, and each file's `source`).

  python3 verification/merged-pr-links/s01-s50/setup-control/gate.py --output FILE [--cases S01,S02 | all] [--workers N]

It runs inside one job of the first format, as the other gates do. Exit 0 when every check passed. The checks are
of the mechanism (one request a case, nobody fails for want of an input, every case is explained); how many cases
came ready, in how many rounds and how long, is the record's `summary`, a measurement and not a pass mark.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REL = HERE.relative_to(ROOT).as_posix()
spec = importlib.util.spec_from_file_location("readiness_gate", HERE.parent / "maven-war" / "readiness_gate.py")
readiness_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness_gate)
sys.path.insert(0, str(ROOT / "jobs"))
import readiness  # noqa: E402

CACHE = "~/.cache/in-the-loop/spring-boot-pr-links-s01-s50"
AS_OF = "2026-11-27T09:00:00Z"          # between the first pass's last file (08:42 UTC) and the second's first (09:40)
FILES = "gradle-home/caches/modules-2/files-2.1"
DESCRIPTORS = "gradle-home/caches/modules-2/metadata-2.107/descriptors"
JDKS = "~/.sdkman/candidates/java"
MIRROR = "~/.cache/in-the-loop/git-mirrors/spring-boot.git"     # the worktrees of the base keep their objects here, outside it
BATCH = "s-setup-control"


def mirror(cache: Path, dest: Path) -> dict:
    """Every module version of Gradle's cache that has a file written after AS_OF, whole, in Maven's layout: links
    to the cache's files, and beside each its SHA-1, which must be the name Gradle filed it under (Gradle drops
    leading zeros there). The folder is the control's one authorised source."""
    when = dt.datetime.fromisoformat(AS_OF.replace("Z", "+00:00")).timestamp()
    files = cache / FILES
    late = sorted({p.parents[1] for p in files.glob("*/*/*/*/*") if p.is_file() and p.stat().st_mtime > when})
    made = {"modules": len(late), "files": 0, "bytes": 0, "misfiled": []}
    for version in late:
        group, artifact, number = version.relative_to(files).parts
        folder = dest / group.replace(".", "/") / artifact / number
        folder.mkdir(parents=True, exist_ok=True)
        for path in sorted(p for p in version.glob("*/*") if p.is_file()):
            sha1 = hashlib.sha1(path.read_bytes()).hexdigest()
            if sha1.lstrip("0") != path.parent.name.lstrip("0"):
                made["misfiled"].append(str(path.relative_to(files)))
                continue
            link = folder / path.name
            if not link.is_symlink():
                link.symlink_to(path)
            (folder / (path.name + ".sha1")).write_text(sha1 + "\n")
            made["files"] += 1
            made["bytes"] += path.stat().st_size
    return made


def unknown_then(cache: Path) -> list[str]:
    """The descriptors of the module versions the first pass did not know: those whose every file Gradle's cache
    wrote after AS_OF. A descriptor alone says nothing of when its module arrived: the second pass wrote the
    descriptors of the first pass's snapshots again (a changing module's is refreshed), and the run of this gate
    that left out every late descriptor had Gradle ask for a BOM the first pass had (S25, withheld as absent)."""
    when = dt.datetime.fromisoformat(AS_OF.replace("Z", "+00:00")).timestamp()
    out = []
    for version in sorted(p for p in (cache / FILES).glob("*/*/*") if p.is_dir()):
        times = [f.stat().st_mtime for f in version.glob("*/*") if f.is_file()]
        rel = f"{DESCRIPTORS}/{version.relative_to(cache / FILES).as_posix()}"
        if times and min(times) > when and (cache / rel).is_dir():
            out.append(rel)
    return out


def operation(case: str, row: list, cache: Path, source: str, resources: dict, unknown: list) -> dict:
    revisions = {pin: subprocess.run(["git", "-C", str(cache / "worktrees" / f"{case}-{pin}"), "rev-parse", "HEAD"], check=True,
                                     capture_output=True, text=True).stdout.strip() for pin in ("fix", "parent")}
    return {
        "schema": readiness.OPERATION, "title": f"Build {case}'s jar projects and run its landed tests offline, at both pins", "consumer": case,
        "describes": {"project": "spring-projects/spring-boot", "case": case, "revisions": revisions, "jarProjects": row[1].split(),
                      "tests": row[2].split(), "task": f"{REL}/case_task.sh {case} fix, and parent",
                      "wrapper": "the Gradle each pin's wrapper names, from the base (tools/)",
                      "toolchain": {"java": ["8.0.512.0+9-tem", "11.0.33.0+10-tem", "17.0.21.0+9-tem", "21.0.13.0+9-tem", "25.0.5.0+8-tem"]},
                      "platform": "linux-x86_64"},
        "level": "tests-run",
        "base": {"path": CACHE, "asOf": {"time": AS_OF, "under": [FILES]}, "without": unknown,
                 "why": "The S cache as it was after the setup's first resolution pass, when its 49 build jobs were first submitted: every "
                        "file Gradle's cache wrote after 09:00 UTC on 2026-11-27 is left out, by the files' own times (the first pass's last "
                        "file is of 08:42, the second pass's first of 09:40), and with it the descriptor of each module version all of whose "
                        "files are of the second pass. A descriptor the second pass wrote again for a module the first pass had (a snapshot's) "
                        "stays, as the second pass left it. Gradle's index files are as they are now."},
        "view": {"env": "SPRING_BOOT_S_CACHE"}, "reads": [JDKS, MIRROR], "layout": {"maven": "m2"}, "repositories": [source],
        "task": {"independent": True, "timeout": 3000, "tests": {"reports": ["reports/**/*.xml"], "min": 1},
                 "steps": [{"name": pin, "run": f'bash {REL}/case_task.sh {case} {pin} "$ITL_READINESS_OUT"'} for pin in ("fix", "parent")]},
        "outputs": [{"path": "tests-fix.json"}, {"path": "tests-parent.json"}],
        "resources": resources, "rounds": 14}


def first_jobs(case: str) -> dict:
    """What the case's setup jobs of 2026-11-27 recorded: the first run, the rerun and the third run, where there is one."""
    found = {}
    for label, stamp in (("first", "20261127-0911"), ("rerun", "20261127-11"), ("third", "20261127-1218")):
        for path in sorted((ROOT / "verification/results/2026/11/27").glob(f"{stamp}*-setup-build-spring-boot-*-{case.lower()}-at-bot*/result.json")):
            result = json.loads(path.read_text())
            found[label] = {"job": result["id"], "status": result["status"], "steps": [s.get("status") for s in result["steps"]],
                            "seconds": (result.get("usage") or {}).get("wallSeconds")}
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, required=True, help="where the gate's record is written")
    parser.add_argument("--cases", default="all", help="S01,S02,... or all (every offline case of the cache's cases.tsv)")
    parser.add_argument("--workers", type=int, default=6, help="jobs at once in the throwaway repository's runner")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--wait", type=float, default=10800)
    args = parser.parse_args(argv)
    cache = Path(CACHE).expanduser()
    table = {line.split("\t")[0]: line.rstrip("\n").split("\t") for line in (cache / "scripts/cases.tsv").read_text().splitlines() if line.strip()}
    cases = [c for c in (sorted(table) if args.cases == "all" else args.cases.split(",")) if table[c][4] == "offline"]
    gates = Path.home() / ".cache/in-the-loop/readiness-gates"
    work = args.work or gates / (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-setup-control")
    work.mkdir(parents=True, exist_ok=True)
    source = (gates / "s-setup-mirror").as_uri() + "/"
    resources = {"cpus": 4, "memory": "6G", "duration": "45m"}
    settings = {"isolation": "none", "workers": args.workers, "cpus": 4.0 * args.workers, "memory": f"{6 * args.workers + 2}G", "job_memory_max": "8G",
                "memory_floor": "0", "keep_workdirs": "never", "poll_seconds": 3, "link": [], "after_collect": [],
                "fetch_allow": [source], "fetch_slots": 10}
    gate = readiness_gate.Gate(work, {}, [], {}, settings)
    record = {"schema": "itl-s-setup-control/v1", "startedAt": readiness_gate.now(), "work": str(work), "cases": cases, "asOf": AS_OF, "source": source,
              "settings": {k: settings[k] for k in ("workers", "cpus", "memory", "fetch_slots")}}
    try:
        record["mirror"] = made = mirror(cache, gates / "s-setup-mirror")
        gate.check("the source is the second pass's modules, each file under the SHA-1 Gradle filed it by", made["modules"] > 1000 and not made["misfiled"],
                   {**made, "misfiled": made["misfiled"][:5]})
        gate.build_repository([REL, "verification/merged-pr-links/s01-s50/maven-war/readiness_gate.py"])
        keys, unknown = {}, unknown_then(cache)
        record["descriptorsLeftOut"] = len(unknown)
        for case in cases:
            op = operation(case, table[case], cache, source, resources, unknown)
            keys[case] = readiness.key(op)
            path = gate.repo / readiness.FOLDER / f"{keys[case]}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(op, indent=2) + "\n")
        step = lambda pin, promise: {"name": pin, "phase": "test", "run": f"bash {REL}/case_task.sh {{row}} {pin} control", **promise}
        manifest = {"schema": "itl-job-batch/v1", "batch": BATCH, "title": "The S batch's setup jobs, each needing its builds and tests ready",
                    "created": "2026-11-28T03:00:00+00:00", "submitted": {"by": "the setup control's gate"},
                    "template": {"title": "Setup build of {row}: its jars and landed tests at both pins, and the transplant",
                                 "description": "The S batch's setup job for {row}, on prepared inputs alone: it needs one readiness operation "
                                                "(the case's builds and landed tests at both pins), and runs fix, parent and transplant offline.",
                                 "purpose": "test", "case": "{row}", "resources": resources, "environment": {"network": "none"}, "stopOnFailure": False,
                                 "steps": [step("fix", {"promises": {"tests": {"min": 1, "reports": ["control/reports/fix/**/*.xml"]}}}),
                                           step("parent", {}), step("transplant", {})],
                                 "outputs": ["control/tests-fix.json", "control/tests-parent.json", {"path": "control/tests-transplant.json", "required": False}]},
                    "rows": [{"row": case, "override": {"needs": [{"readiness": keys[case]}]}} for case in cases]}
        (gate.repo / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        said = json.loads(gate.pipeline("submit", "--manifest", "manifest.json", "--json").stdout)
        requests = sorted(p.stem for p in (gate.repo / readiness.FOLDER).glob("*.json"))
        gate.check("one request a case: an operation under its key, and one job that needs it", len(set(keys.values())) == len(cases) == len(requests),
                   {"cases": len(cases), "requests": len(requests), "submitted": {k: len(v) if isinstance(v, list) else v for k, v in said.items()}})
        gate.commit("the batch: every case's job and the readiness it needs")
        began = time.monotonic()
        gate.start_runner()
        rows = lambda: json.loads(gate.pipeline("batch", BATCH, "--json", check=False).stdout)["rows"]
        gate.until(lambda: all(r["state"] == "waiting" for r in rows()), "every case waits for its readiness", 180)
        gate.check("every case waits, and nothing is fetched before the admission", all(r["state"] == "waiting" for r in rows()) and not (gate.store / "pool").exists(),
                   sorted({r["state"] for r in rows()}))
        admitted = json.loads(gate.pipeline("resolve", "--json", "--by", "the gate, as the watcher", "--run-phase", "watcher").stdout)
        resolver = {w["key"]: w["job"] for w in admitted["written"]}
        gate.check("one admission writes one resolution job for each request", sorted(resolver) == sorted(keys.values()) and not admitted["skipped"],
                   {"written": len(admitted["written"]), "skipped": admitted["skipped"]})
        gate.commit("admit the resolutions")
        gate.pipeline("nudge", check=False)
        gate.note(f"admitted {len(resolver)} resolution job(s)")
        first_useful = [None]

        def settled():
            now_ = rows()
            if first_useful[0] is None and any(r["state"] == "finished" for r in now_):
                first_useful[0] = round(time.monotonic() - began, 1)
                gate.note(f"the first case has a result, {first_useful[0]} s after the runner started")
            return all(r["state"] in ("finished", "blocked", "unschedulable", "invalid") for r in now_)
        gate.until(settled, "every case has a result or is blocked with its reason", args.wait)
        elapsed = round(time.monotonic() - began, 1)
        gate.stop_runner()
        final = {r["row"]: r for r in rows()}
        record["rows"] = out = []
        lacks = lambda text: bool(readiness.missing_coordinates(text) or readiness.missing_files(text))
        for case in cases:
            key, row = keys[case], final.get(case) or {}
            receipt = readiness.Store(gate.store).receipt(key) or {}
            entry = {"case": case, "key": key, "state": row.get("state"), "why": row.get("why"), "history": first_jobs(case),
                     "readiness": {"state": receipt.get("state"), "stage": receipt.get("stage"), "outcome": receipt.get("outcome"), "why": (receipt.get("why") or "")[:500] or None,
                                   "rounds": [{"n": r["n"], "result": r["result"], "missing": len(r["missing"]), "missingFiles": len(r.get("missingFiles") or []),
                                               "fetched": len(r["fetched"]), "offlineSeconds": r["offlineSeconds"]} for r in receipt.get("rounds") or []],
                                   "fetch": receipt.get("fetch"), "evidence": (receipt.get("offline") or {}).get("evidence"),
                                   "leftOut": ((receipt.get("base") or {}).get("asOf") or {}).get("leftOut"), "startedAt": receipt.get("startedAt"), "at": receipt.get("at")}}
            try:
                resolved = gate.staged(resolver[key])
                entry["resolution"] = {"job": resolver[key], "status": resolved["status"], "timing": {k: (resolved.get("timing") or {}).get(k) for k in ("queueWait", "elapsed")}}
            except (OSError, ValueError, KeyError) as e:
                entry["resolution"] = {"job": resolver.get(key), "status": None, "why": str(e)}
            try:
                consumed = gate.staged(row.get("job"))
                steps = [{"name": s.get("name"), "status": s.get("status"), "exitCode": s.get("exitCode"), "seconds": s.get("wallSeconds"),
                          "executed": ((s.get("evidence") or [{}])[0] or {}).get("executed") if s.get("evidence") else None,
                          "alone": (s.get("network") or {}).get("alone") is not None, "offline": (s.get("network") or {}).get("enforced"),
                          "lacksAnInput": s.get("status") != "passed" and lacks("\n".join(s.get("tail") or [])), "tail": (s.get("tail") or [])[-3:]}
                         for s in consumed["steps"] if s.get("index", 0) > 0 or s.get("name") in ("fix", "parent", "transplant")]
                tests = {}
                for pin in ("fix", "parent", "transplant"):
                    path = gate.repo / "verification/.state/results" / row["job"] / "outputs/control" / f"tests-{pin}.json"
                    tests[pin] = json.loads(path.read_text()) if path.exists() else None
                wrote = {o["path"]: o.get("sha256") for o in (receipt.get("offline") or {}).get("outputs") or []}
                same = {pin: hashlib.sha256(json.dumps(tests[pin], sort_keys=True).encode() + b"\n").hexdigest() == wrote.get(f"tests-{pin}.json") for pin in ("fix", "parent") if tests[pin]}
                entry["consumer"] = {"job": row["job"], "status": consumed["status"], "summary": consumed["summary"], "previousAttempts": len(consumed["attempt"]["previous"]),
                                     "startedAt": consumed["startedAt"], "finishedAt": consumed["finishedAt"], "steps": steps, "tests": tests, "asTheResolutionSaw": same,
                                     "timing": {k: (consumed.get("timing") or {}).get(k) for k in ("queueWait", "elapsed")}}
            except (OSError, ValueError, KeyError, TypeError) as e:
                entry["consumer"] = None
                entry["consumerWhy"] = f"{type(e).__name__}: {e}"
            ran = entry["consumer"]
            entry["outcome"] = ("ready, and its job passed" if ran and ran["status"] == "passed" else
                                "ready, and its job failed on the transplant alone" if ran and [s["name"] for s in ran["steps"] if s["status"] != "passed"] == ["transplant"] else
                                "ready, and its job failed" if ran else f"withheld ({receipt.get('outcome')})" if receipt.get("state") == "failed" else "unexplained")
            out.append(entry)
        ready = [e for e in out if e["readiness"]["state"] == "ready"]
        ran = [e for e in out if e["consumer"]]
        gate.check("every resolution ended ready, or withheld at a named stage with a named outcome",
                   all(e["readiness"]["state"] == "ready" or (e["readiness"]["stage"] and e["readiness"]["outcome"]) for e in out),
                   [(e["case"], e["readiness"]["state"], e["readiness"]["stage"], e["readiness"]["outcome"]) for e in out if e["readiness"]["state"] != "ready"])
        gate.check("a case whose readiness was withheld ran nothing, and is blocked with the reason",
                   all(e["state"] == "blocked" and not e["consumer"] and e["why"] for e in out if e["readiness"]["state"] != "ready"),
                   [(e["case"], e["state"], e["why"]) for e in out if e["readiness"]["state"] != "ready"][:10])
        gate.check("every case that came ready ran once, after its receipt, with no network and nothing of the machine's own to read",
                   len(ran) == len(ready) and all(e["consumer"]["previousAttempts"] == 0 and e["consumer"]["startedAt"] >= e["readiness"]["at"]
                                                  and all(s["offline"] and s["alone"] for s in e["consumer"]["steps"] if s["status"] != "skipped") for e in ran),
                   [(e["case"], e["consumer"] and e["consumer"]["previousAttempts"]) for e in ready if not e["consumer"]][:10])
        gate.check("no job failed for want of an input: a step that failed named no module or file it lacks",
                   not any(s["lacksAnInput"] for e in ran for s in e["consumer"]["steps"]),
                   [(e["case"], s["name"], s["tail"]) for e in ran for s in e["consumer"]["steps"] if s["lacksAnInput"]][:5])
        gate.check("every case whose fix step passed shows tests that executed, and its counts are the resolution's own",
                   all(s["executed"] and s["executed"] >= 1 for e in ran for s in e["consumer"]["steps"] if s["name"] == "fix" and s["status"] == "passed")
                   and all(all(e["consumer"]["asTheResolutionSaw"].values()) for e in ran if e["consumer"]["status"] == "passed"),
                   [(e["case"], e["consumer"]["asTheResolutionSaw"], [(s["name"], s["status"], s["executed"]) for s in e["consumer"]["steps"]]) for e in ran][:8])
        gate.check("every case is explained", not [e for e in out if e["outcome"] == "unexplained"], [e["case"] for e in out if e["outcome"] == "unexplained"])
        gate.check("at least one case came ready and its job ran: the checks above are not passed by nothing having happened", bool(ran),
                   {e["case"]: (e["readiness"]["outcome"], (e["readiness"]["why"] or "")[:300]) for e in out if not e["consumer"]})
        rounds = [len(e["readiness"]["rounds"]) for e in ready]
        seconds = lambda which: round(sum(r["offlineSeconds"] or 0 for e in out for r in e["readiness"]["rounds"] if which(r)), 1)
        fetch = lambda field: sum((e["readiness"]["fetch"] or {}).get(field, 0) for e in out)
        counted = {}
        for e in out:
            counted[e["outcome"]] = counted.get(e["outcome"], 0) + 1
        history = {label: {status: sum(1 for e in out if (e["history"].get(label) or {}).get("status") == status) for status in ("passed", "failed")}
                   for label in ("first", "rerun", "third")}
        record["summary"] = {
            "cases": len(out), "outcomes": counted, "history": history,
            "consumerJobsThatFailedForWantOfAnInput": sum(1 for e in ran if any(s["lacksAnInput"] for s in e["consumer"]["steps"])),
            "rounds": {"ofReady": sorted(rounds), "median": statistics.median(rounds) if rounds else None, "max": max(rounds) if rounds else None,
                       "all": sum(len(e["readiness"]["rounds"]) for e in out)},
            "offlineSeconds": {"roundsThatFailed": seconds(lambda r: r["result"] != "passed"), "roundsThatPassed": seconds(lambda r: r["result"] == "passed"),
                               "consumerJobs": round(sum((e["consumer"]["timing"]["elapsed"] or {}).get("seconds") or 0 for e in ran), 1)},
            "fetch": {"files": fetch("files"), "bytes": fetch("bytes"), "seconds": round(fetch("seconds"), 1), "reusedFiles": fetch("reused"), "reusedBytes": fetch("reusedBytes")},
            "elapsedSeconds": elapsed, "firstResultSeconds": first_useful[0],
            "view": {k: v for k, v in gate.view().get("totals", {}).items()}}
    except Exception as e:  # noqa: BLE001  (the record says what stopped it)
        gate.check("the gate ran to its end", False, f"{type(e).__name__}: {e}")
    finally:
        gate.stop_runner()
    return readiness_gate.conclude(gate, record, work, args.output)


if __name__ == "__main__":
    sys.exit(main())
