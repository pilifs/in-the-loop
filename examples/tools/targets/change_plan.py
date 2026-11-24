"""Plan and resume caller-visible obligations for an application change."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from targets import change_evidence, change_inventory, class_binding, runtime_jar, runtime_jdk, upgrade_replay
from targets.change_inventory import digest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCHEMA = "java-change-plan/v1"


def delta(previous, current):
    def subjects(report):
        return {n["id"]: (n["claimKey"], n["executionKey"], n["status"]) for n in report["claims"]}
    old, new = subjects(previous), subjects(current)
    return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "changed": {k: {"before": old[k], "after": new[k]} for k in sorted(old.keys() & new.keys())
                        if old[k] != new[k]}}


def frozen_workflows(path):
    doc = json.loads(path.read_text())
    if doc["schema"] != "caller-workflows/v1":
        raise ValueError("unknown workflow format")
    workflows = {}
    for row in doc["workflows"]:
        name = row["id"]
        if name in workflows or row["cohort"] not in {"registered", "additional", "control"}:
            raise ValueError(f"duplicate workflow or unknown cohort for {name}")
        specfile = (path.parent / row["scope"]).resolve()
        probe = (path.parent / row["probe"]).resolve()
        spec = json.loads(specfile.read_text())
        if not spec["cases"] or len({tuple(c["args"]) for c in spec["cases"]}) != len(spec["cases"]):
            raise ValueError(f"{name} must declare a nonempty domain of distinct inputs")
        workflows[name] = (row, specfile, probe, spec)
    return doc, workflows


def runner_identity():
    # Includes the evidence parser and bytecode readers as well as the Java adapters.
    files = [*sorted(HERE.glob("*.py")), upgrade_replay.LAUNCHER, upgrade_replay.TRACER, upgrade_replay.LOOKUP]
    return digest({"files": {p.name: upgrade_replay.sha(p) for p in files},
                   "python": sys.version, "host": list(platform.uname())})


def compare(args):
    started = time.monotonic()
    doc, workflows = frozen_workflows(args.workflows)
    jdk = args.jdk.resolve()
    image = change_inventory.jdk_binding(jdk)
    paths, launches, snapshots = {}, {}, {}
    environment = {"locale": "C.UTF-8", "timezone": "UTC", "home": "fresh trial",
                   "inputs": doc.get("environment", [])}
    for side, manifest, test in (("old", args.before, args.before_test), ("new", args.after, args.after_test)):
        paths[side], production = change_inventory.resolve(manifest, jdk, image, environment, kind="production")
        launches[side] = {"production": production}
        if test:
            _, launches[side]["test"] = change_inventory.resolve(test, jdk, image, environment, kind="test")
        snapshots[side] = change_inventory.deployment(paths[side], jdk)
    declared = {spec["entry"] for _, _, _, spec in workflows.values()}
    inventory = change_inventory.inventory(snapshots["old"], snapshots["new"], declared)
    checker = args.checker.resolve()
    inventory["applicationEntries"] = change_inventory.framework_inventory(checker, paths, jdk)
    asked = []
    for entry in sorted(declared):
        owner, method, descriptor = runtime_jar.parse_target(entry)
        if not descriptor:
            raise ValueError(f"missing exact method descriptor for {entry}")
        asked.append({"class": owner, "method": method, "descriptor": descriptor})
    env = {**os.environ, "JAVA_HOME": str(jdk), "JVMCONTRACT_JAR_RELEASE": runtime_jdk.identity(jdk)["feature"]}
    bound, _ = class_binding.ask(checker, env, Path.cwd(), {
        side: {"classpath": list(map(str, files)), "classes": asked} for side, files in paths.items()})
    problems = {}
    for side, bindings in bound.items():
        for entry, selected in zip(sorted(declared), bindings["bindings"], strict=True):
            owner, _, _ = runtime_jar.parse_target(entry)
            original = snapshots[side][0].get(runtime_jar.internal(owner))
            if issue := class_binding.disagreement(owner, selected, paths[side][0], original):
                problems.setdefault(entry, []).append(issue)
        launches[side]["classes"] = bindings["bindings"]

    old, new = (launches[k]["production"] for k in ("old", "new"))
    runner = runner_identity()
    plan = {"schema": SCHEMA, "change": doc["change"], "launches": launches, "inventory": inventory,
            "tools": {"comparator": upgrade_replay.sha(checker), "jvmRunner": runner},
            "deploymentQuestions": {
                "originalBinary": "same client JAR on both deployments" if old["classpath"][0]["sha256"] == new["classpath"][0]["sha256"]
                                  else "open for the original client on the new runtime",
                "unchangedSourceBuild": "both supplied preparations record matching source digests"
                                        if old["sourceSha256"] and old["sourceSha256"] == new["sourceSha256"]
                                        else "open for unchanged source",
                "adaptedApplication": "compare the supplied client and runtime on each side"},
            "claims": [], "preparationSeconds": round(time.monotonic() - started, 4)}
    for name, (row, scope, probe, spec) in workflows.items():
        assumptions = row.get("assumptions", [])
        claim_key = digest({"scope": spec, "intent": row["intent"], "assumptions": assumptions})
        basis = {"sourceClaim": claim_key, "runner": runner, "comparator": plan["tools"]["comparator"],
                 "probe": upgrade_replay.sha(probe), "jdk": image, "environment": environment,
                 "seconds": args.seconds, "kind": "production"}
        execution_key = digest([basis, old["key"], new["key"], args.old_dependency, args.new_dependency])
        node = {"id": name, "claimKey": claim_key, "executionKey": execution_key, "entry": spec["entry"],
                "statement": spec["observer"], "domain": spec["cases"], "scope": spec["basis"],
                "cohort": row["cohort"], "intent": row["intent"], "assumptions": assumptions,
                "status": "open", "firstOpenDependency": "original caller executions"}
        plan["claims"].append(node)
        if spec["entry"] in problems:
            node["firstOpenDependency"] = problems[spec["entry"]]
            continue
        if not args.run:
            continue
        use_cache = (args.cache is not None and row.get("deterministicUnderAssumptions") is True
                     and assumptions and not any(inventory["implicitClasspaths"].values()))
        cache = change_evidence.SideCache(args.cache, basis) if use_cache else None
        evidence = {}
        try:
            upgrade_replay.evaluate(scope, args.before, args.after, probe, jdk,
                                    (args.old_dependency, args.new_dependency), args.seconds,
                                    fixtures=args.fixtures, progress=evidence, side_cache=cache)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            evidence.update(status="open", reason=str(error))
        if evidence.get("cases") == spec["cases"]:
            node.update(change_evidence.compose(spec, evidence))
        if node["status"] == "open" and evidence.get("reason"):
            node["reason"] = evidence["reason"]
        for key in ("stoppedAt", "beforeEntryComparison", "linkage", "reason"):
            if key in evidence:
                node[key] = evidence[key]
        node["execution"] = cache.actions if cache else {s: {"action": "executed"} for s in paths if evidence.get("sides", {}).get(s, {}).get("trials")}
        receipt_hash = digest(evidence)
        receipt = args.output.parent / "receipts" / (receipt_hash + ".json")
        change_evidence.write_json(receipt, evidence)
        node["receipt"] = {"path": os.path.relpath(receipt, args.output.parent), "sha256": upgrade_replay.sha(receipt)}
    plan["counts"] = {cohort: dict(Counter(n["status"] for n in plan["claims"] if n["cohort"] == cohort))
                      for cohort in ("registered", "additional", "control")}
    plan["wallSeconds"] = round(time.monotonic() - started, 4)
    if args.previous:
        previous = json.loads(args.previous.read_text())
        if previous.get("schema") != SCHEMA or previous["change"] != plan["change"]:
            raise ValueError("previous report belongs to a different change")
        plan["delta"] = delta(previous, plan)
    return plan


def example_plan(number):
    import build
    from targets import claim_history, sidecar
    folder, = build.EXAMPLES.glob(f"{number:03d}-*")
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    history = claim_history.inventory(folder, example, target)
    claims = []
    for group in history["claims"]:
        for subject in group["subjects"]:
            if subject.get("historical"):
                continue
            task = next(t for t in target["tasks"] if t["id"] == subject["task"])
            key = group["claimKey"]
            status = subject.get("overallConclusion", subject["conclusion"])
            claims.append({"id": task["id"], "claimKey": key, "entry": task["target"],
                           "statement": group["file"], "launches": subject["revisions"],
                           "status": status, "monolithic": subject["conclusion"],
                           "attempt": subject["latestAttempt"], "ordinary": subject["evidence"],
                           "finiteJvm": subject.get("finiteJvm", []), "nativeSelectors": subject.get("nativeSelectors", []),
                           "originalWitnesses": subject.get("originalWitnesses", []),
                           "dependencies": [{"task": p, "reason": "calibrate the original JVM entry"} for p in task.get("requires", [])]})
    return {"schema": SCHEMA, "example": number, "change": target["identity"]["case"], "claims": claims,
            "coverage": history["coverage"], "replays": [r["task"] for r in history["replays"]]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    example = sub.add_parser("example", help="project the target runner's frozen claims, routes and dependencies")
    example.add_argument("number", type=int)
    upgrade = sub.add_parser("upgrade", help="compare prepared JVM applications with their ordered classpaths")
    for name in ("before", "after", "jdk", "workflows"):
        upgrade.add_argument("--" + name, type=Path, required=True)
    for name in ("before-test", "after-test", "fixtures", "cache", "previous"):
        upgrade.add_argument("--" + name, type=Path)
    for name in ("old-dependency", "new-dependency"):
        upgrade.add_argument("--" + name, required=True)
    upgrade.add_argument("--checker", type=Path, default=ROOT / "lib/target/release/jvmcontract")
    upgrade.add_argument("--seconds", type=int, default=60, help="per-workflow replay budget")
    upgrade.add_argument("--run", action="store_true", help="execute the finite obligations on the original JVM")
    for command in (example, upgrade):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        plan = example_plan(args.number) if args.command == "example" else compare(args)
        change_evidence.write_json(args.output, plan)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"change plan: {error}\n")
    print(f"{len(plan['claims'])} claims in {args.output}")
    return 0
