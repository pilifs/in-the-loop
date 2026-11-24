"""Plan and resume caller-visible obligations for an application change."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
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
    launches = {}
    for side in ("old", "new"):
        for kind in ("production", "test"):
            before = previous["launches"][side].get(kind) or {}
            after = current["launches"][side].get(kind) or {}
            changed = {k: {"before": before.get(k), "after": after.get(k)} for k in
                       ("classpath", "jdk", "environment", "environmentFiles") if before.get(k) != after.get(k)}
            if changed:
                launches[f"{side}/{kind}"] = changed
    before_entries = {c["entry"] for c in previous["inventory"]["candidates"]}
    after_entries = {c["entry"] for c in current["inventory"]["candidates"]}
    return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "launchChanges": launches, "toolIdentityChanged": previous["tools"] != current["tools"],
            "addedEntries": sorted(after_entries - before_entries), "removedEntries": sorted(before_entries - after_entries),
            "changed": {k: {"before": old[k], "after": new[k]} for k in sorted(old.keys() & new.keys())
                        if old[k] != new[k]}}


def frozen_workflows(path):
    doc = json.loads(path.read_text())
    if doc["schema"] != "caller-workflows/v1":
        raise ValueError("unknown workflow format")
    workflows = {}
    for row in doc["workflows"]:
        name = row["id"]
        if not isinstance(name, str) or not name or name in workflows or row["cohort"] not in {"registered", "additional", "control"}:
            raise ValueError(f"duplicate workflow or unknown cohort for {name}")
        assumptions = row.get("assumptions", [])
        if not isinstance(assumptions, list) or any(not isinstance(a, str) or not a.strip() for a in assumptions):
            raise ValueError(f"{name}: assumptions must name the conditions of the observation")
        specfile = (path.parent / row["scope"]).resolve()
        probe = (path.parent / row["probe"]).resolve()
        spec = json.loads(specfile.read_text())
        if not spec["cases"] or len({tuple(c["args"]) for c in spec["cases"]}) != len(spec["cases"]):
            raise ValueError(f"{name} must declare a nonempty domain of distinct inputs")
        intent = row["intent"]
        if intent not in ("preserve", "undecided"):
            if not isinstance(intent, dict) or set(intent) != {"allowedChanges"} or not isinstance(intent["allowedChanges"], list):
                raise ValueError(f"{name}: expected preserve, undecided, or explicit allowedChanges")
            seen = set()
            for change in intent["allowedChanges"]:
                i, expected = change["input"], change["expectedNew"]
                if (type(i) is not int or not 0 <= i < len(spec["cases"]) or i in seen
                        or not isinstance(expected, dict) or set(expected) not in ({"return"}, {"throws"})):
                    raise ValueError(f"{name}: ambiguous allowed change or input outside the domain")
                seen.add(i)
        workflows[name] = (row, specfile, probe, spec)
    return doc, workflows


def runner_identity():
    # Includes the evidence parser and bytecode readers as well as the Java adapters.
    modules = ("change_plan", "change_inventory", "change_evidence", "upgrade_replay", "upgrade_claims",
               "upgrade_linkage", "upgrade_jdbc", "runtime_jar", "class_binding", "runtime_jdk")
    files = [*(HERE / (name + ".py") for name in modules), upgrade_replay.LAUNCHER, upgrade_replay.TRACER, upgrade_replay.LOOKUP]
    return digest({"files": {p.name: upgrade_replay.sha(p) for p in files},
                   "python": sys.version, "host": list(platform.uname())})


def compare(args, *, original_binary=True):
    started = time.monotonic()
    doc, workflows = frozen_workflows(args.workflows)
    jdks = {"old": args.jdk.resolve(), "new": (args.after_jdk or args.jdk).resolve()}
    images = {p: change_inventory.jdk_binding(p) for p in set(jdks.values())}
    paths, launches, snapshots = {}, {}, {}
    environment = {"locale": "C.UTF-8", "timezone": "UTC", "home": "fresh trial",
                   "inputs": doc.get("environment", [])}
    for side, manifest, test in (("old", args.before, args.before_test), ("new", args.after, args.after_test)):
        jdk = jdks[side]
        image = images[jdk]
        paths[side], production = change_inventory.resolve(manifest, jdk, image, environment, kind="production")
        launches[side] = {"production": production}
        if test:
            _, launches[side]["test"] = change_inventory.resolve(test, jdk, image, environment, kind="test")
        snapshots[side] = change_inventory.deployment(paths[side], jdk)
    declared = {spec["entry"] for _, _, _, spec in workflows.values()}
    inventory = change_inventory.inventory(snapshots["old"], snapshots["new"], declared)
    checker = args.checker.resolve()
    inventory["applicationEntries"] = change_inventory.framework_inventory(checker, paths, jdks)
    asked = []
    for entry in sorted(declared):
        owner, method, descriptor = runtime_jar.parse_target(entry)
        if not descriptor:
            raise ValueError(f"missing exact method descriptor for {entry}")
        asked.append({"class": owner, "method": method, "descriptor": descriptor})
    bound = {}
    for jdk in images:
        env = {**os.environ, "JAVA_HOME": str(jdk), "JVMCONTRACT_JAR_RELEASE": runtime_jdk.identity(jdk)["feature"]}
        group, _ = class_binding.ask(checker, env, Path.cwd(), {
            side: {"classpath": list(map(str, files)), "classes": asked} for side, files in paths.items() if jdks[side] == jdk})
        bound.update(group)
    problems = {}
    for side, bindings in bound.items():
        for entry, selected in zip(sorted(declared), bindings["bindings"], strict=True):
            owner, _, _ = runtime_jar.parse_target(entry)
            original = snapshots[side][0].get(runtime_jar.internal(owner))
            if issue := class_binding.disagreement(owner, selected, paths[side][0], original):
                problems.setdefault(entry, []).append(issue)
            elif not selected["method"]["declared"]:
                problems.setdefault(entry, []).append(f"{side} client does not declare this descriptor")
            elif len(class_binding.candidates(paths[side][0], runtime_jar.internal(owner))) != 1:
                problems.setdefault(entry, []).append(f"{side} original caller requires a measured multi-release JVM class binding")
        launches[side]["classes"] = bindings["bindings"]

    old, new = (launches[k]["production"] for k in ("old", "new"))
    operands = (args.old_dependency or old["classpath"][0]["sha256"], args.new_dependency or new["classpath"][0]["sha256"])
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
    previous = json.loads(args.previous.read_text()) if args.previous else None
    if previous is not None and (previous.get("schema") != SCHEMA or previous.get("change") != plan["change"]):
        raise ValueError("previous report belongs to a different change")
    pending = []
    for name, (row, scope, probe, spec) in workflows.items():
        assumptions = row.get("assumptions", [])
        claim_key = digest({"scope": spec, "intent": row["intent"], "assumptions": assumptions})
        basis = {"sourceClaim": claim_key, "runner": runner, "comparator": plan["tools"]["comparator"],
                 "probe": upgrade_replay.sha(probe), "environment": environment,
                 "seconds": args.seconds, "kind": "production"}
        execution_key = digest([basis, old["key"], new["key"], *operands])
        node = {"id": name, "claimKey": claim_key, "executionKey": execution_key, "entry": spec["entry"],
                "statement": spec["observer"], "domain": spec["cases"], "scope": spec["basis"],
                "cohort": row["cohort"], "intent": row["intent"], "assumptions": assumptions,
                "status": "open", "firstOpenDependency": "original caller executions"}
        plan["claims"].append(node)
        if spec["entry"] in problems:
            node["firstOpenDependency"] = problems[spec["entry"]]
            continue
        if args.run:
            pending.append((node, basis, row, scope, probe, spec))
    plan["executionState"] = "running" if args.run else "planned"
    if args.run and original_binary:
        change_evidence.write_json(args.output, plan)
    for node, basis, row, scope, probe, spec in pending:
        closed = row.get("deterministicUnderAssumptions") is True and node["assumptions"] and not any(inventory["implicitClasspaths"].values())
        use_cache = args.cache is not None and closed
        side_inputs = {s: {"jdk": images[j], "environmentFiles": launches[s]["production"].get("environmentFiles", [])}
                       for s, j in jdks.items()}
        cache = change_evidence.SideCache(args.cache, basis, side_inputs) if use_cache else None
        evidence = {}
        try:
            upgrade_replay.evaluate(scope, args.before, args.after, probe, jdks["old"], operands, args.seconds,
                                    fixtures=args.fixtures, progress=evidence, side_cache=cache,
                                    after_jdk=jdks["new"], application_change=True)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            evidence.update(status="open", reason=str(error))
        if evidence.get("cases") == spec["cases"]:
            node.update(change_evidence.compose(spec, evidence, row["intent"]))
            for c in node["children"]:
                c["id"] = digest([node["claimKey"], node["executionKey"], c["input"]])
            node["dependsOn"] = [{"id": c["id"], "reason": "original entry on both sides of this admitted input"}
                                 for c in node["children"]]
            if node["status"] == "established" and not closed:
                node.update(status="open", firstOpenDependency="bind all runtime inputs and justify deterministic observations")
        for key in ("stoppedAt", "beforeEntryComparison", "linkage", "reason"):
            if key in evidence:
                node[key] = evidence[key]
        node["execution"] = cache.actions if cache else {s: {"action": "executed"} for s in paths if evidence.get("sides", {}).get(s, {}).get("trials")}
        receipt_hash = digest(evidence)
        receipt = args.output.parent / "receipts" / (receipt_hash + ".json")
        change_evidence.write_json(receipt, evidence)
        node["receipt"] = {"path": os.path.relpath(receipt, args.output.parent), "sha256": upgrade_replay.sha(receipt)}
        node["observerAndReplaySeconds"] = evidence.get("elapsedSeconds")
        if original_binary:
            change_evidence.write_json(args.output, plan)
    plan["counts"] = {cohort: dict(Counter(n["status"] for n in plan["claims"] if n["cohort"] == cohort))
                      for cohort in ("registered", "additional", "control")}
    if original_binary and old["classpath"][0]["sha256"] != new["classpath"][0]["sha256"]:
        # Keep every new deploy-time provider in its original position. The client alone comes from the old build.
        manifest = json.loads(args.after.read_text())
        for item in manifest.get("environmentFiles", []):
            item["file"] = str((args.after.parent / item["file"]).resolve())
        files = [paths["old"][0], *paths["new"][1:]]
        hashes = [old["classpath"][0]["sha256"], *(r["sha256"] for r in new["classpath"][1:])]
        manifest.update(sourceSha256=old["sourceSha256"], scope="original binary on the new runtime",
                        classpath=[{"file": str(f), "sha256": h} for f, h in zip(files, hashes, strict=True)])
        with tempfile.TemporaryDirectory(prefix="change-binary-") as work:
            path = Path(work) / "prepared.json"
            change_evidence.write_json(path, manifest)
            alternate = argparse.Namespace(**vars(args))
            alternate.after, alternate.after_test, alternate.previous = path, None, None
            if args.new_dependency == new["classpath"][0]["sha256"]:
                alternate.new_dependency = hashes[0]
            binary = compare(alternate, original_binary=False)
        plan["deploymentQuestions"]["originalBinary"] = {"launch": binary["launches"]["new"]["production"],
                                                        "claims": binary["claims"], "counts": binary["counts"]}
    plan["wallSeconds"] = round(time.monotonic() - started, 4)
    if args.run:
        plan["executionState"] = "complete"
    if previous is not None:
        plan["delta"] = delta(previous, plan)
    return plan


def example_plan(number):
    import build
    from targets import claim_history, sidecar, workflow
    folder, = build.EXAMPLES.glob(f"{number:03d}-*")
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    history = claim_history.inventory(folder, example, target)
    claims = []
    tasks = {t["id"]: t for t in target["tasks"]}
    for group in history["claims"]:
        for subject in group["subjects"]:
            if subject.get("historical"):
                continue
            task = tasks[subject["task"]]
            key = group["claimKey"]
            frozen = workflow.plan_task(folder, example, target, task["id"])
            source = getattr(frozen, "claim", {})
            status = subject.get("overallConclusion", subject["conclusion"])
            claims.append({"id": task["id"], "claimKey": key, "entry": task["target"],
                           "claimFile": group["file"], "statement": source.get("statement"),
                           "scope": {"guard": source.get("assume"), "bounds": source.get("bounds"),
                                     "observations": source.get("observations"), "assumptions": source.get("assumptions", [])},
                           "launches": subject["revisions"],
                           "status": status, "monolithic": subject["conclusion"],
                           "attempt": subject["latestAttempt"], "ordinary": subject["evidence"],
                           "finiteJvm": subject.get("finiteJvm", []), "nativeSelectors": subject.get("nativeSelectors", []),
                           "originalWitnesses": subject.get("originalWitnesses", []),
                           "dependencies": [{"task": p, "reason": "calibrate the original JVM entry" if tasks[p]["kind"] == "replay"
                                              else "declared prerequisite of the frozen task"} for p in task.get("requires", [])]})
    report = {"schema": SCHEMA, "example": number, "change": target["identity"]["case"], "claims": claims,
              "coverage": history["coverage"], "replays": [r["task"] for r in history["replays"]]}
    if number in (336, 346):
        reader = ROOT / "lib/benchmark/trusted-kernel/change_nodes.py"
        checked = subprocess.run([sys.executable, "-B", reader, "--for-plan", folder], input=json.dumps(claims),
                                 capture_output=True, text=True)
        assurance = (json.loads(checked.stdout) if checked.returncode == 0 else
                     {"nodes": [], "reason": checked.stderr.strip() or "Independent evidence could not be read."})
        report["independentEvidence"] = assurance
        by_task = {claim["id"]: claim for claim in claims}
        for node in assurance["nodes"]:
            if node["kind"] == "solver-query":
                by_task[node["task"]].setdefault("independentSubclaims", []).append(node["id"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    example = sub.add_parser("example", help="project the target runner's frozen claims, routes and dependencies")
    example.add_argument("number", type=int)
    upgrade = sub.add_parser("upgrade", aliases=["application"], help="compare prepared JVM applications with their ordered classpaths")
    for name in ("before", "after", "jdk", "workflows"):
        upgrade.add_argument("--" + name, type=Path, required=True)
    for name in ("before-test", "after-test", "after-jdk", "fixtures", "cache", "previous"):
        upgrade.add_argument("--" + name, type=Path)
    for name in ("old-dependency", "new-dependency"):
        upgrade.add_argument("--" + name, help="tracked runtime artifact digest (default: the client JAR)")
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
