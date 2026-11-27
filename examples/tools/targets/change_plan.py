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

from targets import change_evidence, change_inventory, entry_binding, entry_discovery, runtime_jar, runtime_jdk, upgrade_replay
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
                       ("classpath", "jdk", "environment", "environmentFiles", "manifestClassPath") if before.get(k) != after.get(k)}
            if changed:
                launches[f"{side}/{kind}"] = changed
    before_entries = {c["entry"] for c in previous["inventory"]["candidates"]}
    after_entries = {c["entry"] for c in current["inventory"]["candidates"]}
    return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "launchChanges": launches, "toolIdentityChanged": previous["tools"] != current["tools"],
            "addedEntries": sorted(after_entries - before_entries), "removedEntries": sorted(before_entries - after_entries),
            "changed": {k: {"before": old[k], "after": new[k]} for k in sorted(old.keys() & new.keys())
                        if old[k] != new[k]}}


def workflow_row(name, scope, probe, assumptions, changes, *, cohort="registered"):
    """Shared portable registration for an authored or generated finite public observer."""
    return {"id": name, "scope": scope, "probe": str(probe), "cohort": cohort,
            "deterministicUnderAssumptions": True, "assumptions": assumptions,
            "intent": {"allowedChanges": changes} if changes else "preserve"}


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
        if "pairedObservation" in spec:
            if (spec["pairedObservation"] not in change_evidence.PAIRED or intent != {"pairedObservation":spec["pairedObservation"]}
                    or spec.get("assertedSides") != ["old","new"] or any(set(c) != {"args"} for c in spec["cases"])):
                raise ValueError(f"{name}: paired observations require an explicitly frozen two-sided predicate")
        elif intent not in ("preserve", "undecided"):
            if not isinstance(intent, dict) or set(intent) != {"allowedChanges"} or not isinstance(intent["allowedChanges"], list):
                raise ValueError(f"{name}: expected preserve, undecided, or explicit allowedChanges")
            seen = set()
            for change in intent["allowedChanges"]:
                i, expected = change["input"], change["expectedNew"]
                if (type(i) is not int or not 0 <= i < len(spec["cases"]) or i in seen
                        or not isinstance(expected, dict) or set(expected) not in ({"return"}, {"throws"})):
                    raise ValueError(f"{name}: ambiguous allowed change or input outside the domain")
                seen.add(i)
        if "checkedHelper" in row:
            row = dict(row)
            row["checkedHelper"] = json.loads((path.parent / row["checkedHelper"]).read_bytes())
        if "generatedObserver" in spec:
            from targets import observer_generation
            if spec["generatedObserver"]["question"] != name:
                raise ValueError("generated scope belongs to a different question")
            observer_generation.checked_bundle(specfile, spec, probe)
        workflows[name] = (row, specfile, probe, spec)
    return doc, workflows


def runner_identity():
    # Includes the evidence parser and bytecode readers as well as the Java adapters.
    modules = ("change_plan", "change_inventory", "change_evidence", "change_helpers", "upgrade_replay", "upgrade_claims",
               "entry_binding", "entry_discovery", "deployment_graph", "upgrade_linkage", "upgrade_jdbc", "runtime_jar", "class_binding", "runtime_jdk")
    files = [*(HERE / (name + ".py") for name in modules), upgrade_replay.LAUNCHER, upgrade_replay.TRACER, upgrade_replay.LOOKUP]
    return digest({"files": {p.name: upgrade_replay.sha(p) for p in files},
                   "python": sys.version, "host": list(platform.uname())})


def compare(args, *, original_binary=True, archive_index=None):
    started = time.monotonic()
    doc, workflows = frozen_workflows(args.workflows) if args.workflows else ({"change": "compiled deployment comparison"}, {})
    archive_index = archive_index or entry_discovery.Index()
    jdks = {"old": args.jdk.resolve(), "new": (args.after_jdk or args.jdk).resolve()}
    images = {p: change_inventory.jdk_binding(p) for p in set(jdks.values())}
    paths, launches, snapshots, tests = {}, {}, {}, {}
    environment = {"locale": "C.UTF-8", "timezone": "UTC", "home": "fresh trial",
                   "inputs": doc.get("environment", [])}
    layout_cache = (args.cache or args.output.parent) / "deployment-layouts"
    for side, manifest, test in (("old", args.before, args.before_test), ("new", args.after, args.after_test)):
        jdk = jdks[side]
        image = images[jdk]
        paths[side], production = change_inventory.resolve(manifest, jdk, image, environment, kind="production" if original_binary or side == "old" else "original-client", layout_cache=layout_cache, index=archive_index)
        launches[side] = {"production": production}
        if test:
            test_files, launches[side]["test"] = change_inventory.resolve(test, jdk, image, environment, kind="test", layout_cache=layout_cache, index=archive_index)
            tests[side + "/test"] = (test_files, launches[side]["test"], jdk)
        snapshots[side] = archive_index.view(paths[side], [r["sha256"] for r in production["classpath"]],
                                             int(runtime_jdk.identity(jdk)["feature"]))
    declared = {spec["entry"] for _, _, _, spec in workflows.values()} | set(getattr(args, "entry", []))
    if getattr(args, "supplied_only", False):
        if not declared:
            raise ValueError("supplied-only qualification needs an approved entry or frozen workflows")
        inventory = {"inputMode": "supplied only", "candidateCount": len(declared),
                     "candidates": [{"entry": e, "independentlyDiscovered": False} for e in sorted(declared)]}
    else:
        inventory = entry_discovery.discover(snapshots, declared, getattr(args, "changed_selector", []))
    if getattr(args,"upstream_history",None):
        from targets import public_histories
        public_histories.apply(inventory,args.upstream_history,snapshots,launches,jdks)
    inventory["coverage"] = archive_index.coverage()
    checker = args.checker.resolve()
    if workflows and not getattr(args, "supplied_only", False):
        if any(launch["production"]["clientIndex"] for launch in launches.values()):
            inventory["applicationEntries"] = {"status": "open", "reason": "framework comparator requires the client as its first root"}
        else:
            inventory["applicationEntries"] = change_inventory.framework_inventory(checker, paths, jdks)
    graphs = {s: (paths[s], launches[s]["production"], jdks[s]) for s in paths}
    selected_entries = declared
    if not declared:
        selected_entries = {row["entry"] for row in inventory["candidates"][:getattr(args, "probe_limit", 8)]}
    all_graphs = {**graphs, **tests}
    measurements = {}
    bindings = entry_binding.qualify(checker, all_graphs, {side: selected_entries for side in all_graphs}, measurements=measurements)
    problems = {}
    for side, records in bindings.items():
        if side in snapshots:
            view = snapshots[side]
        else:
            files, launch, jdk = all_graphs[side]
            view = archive_index.view(files, [r["sha256"] for r in launch["classpath"]], int(runtime_jdk.identity(jdk)["feature"]))
        for entry, record in records.items():
            owner, name, descriptor = runtime_jar.parse_target(entry)
            record["candidateOrigins"] = view.origins(runtime_jar.internal(owner), (name, descriptor))
            if isinstance(record.get("firstOpenDependency"), dict) and "order is unknown" in record["firstOpenDependency"].get("reason", ""):
                for origin in record["candidateOrigins"]:
                    origin.update(selected=None, reason="winner depends on the unknown launch order")
            if "resolvedEntry" in record:
                owner = runtime_jar.parse_target(record["resolvedEntry"])[0]
                record["declarationOrigins"] = view.origins(runtime_jar.internal(owner))
        if side in tests:
            continue
        launches[side]["classes"] = [r["checker"] for r in records.values() if "checker" in r]
        for entry, record in records.items():
            if record["status"] != "bound":
                problems.setdefault(entry, []).append({"side": side, "reason": record["firstOpenDependency"]})
    binding_records = {digest(record): record for records in bindings.values() for record in records.values()}
    old, new = (launches[k]["production"] for k in ("old", "new"))
    clients = {side: launch["classpath"][launch["clientIndex"]]["sha256"] for side, launch in (("old", old), ("new", new))}
    operands = (args.old_dependency or clients["old"], args.new_dependency or clients["new"])
    runner = runner_identity()
    plan = {"schema": SCHEMA, "change": doc["change"], "launches": launches, "inventory": inventory,
            "entryBindings": binding_records, "bindingWitnesses": {},
            "graphs": {g["key"]: g for _, g, _ in all_graphs.values()}, "tools": {"comparator": upgrade_replay.sha(checker), "jvmRunner": runner},
            "deploymentQuestions": {
                "originalBinary": "same client JAR on both deployments" if clients["old"] == clients["new"]
                                  else "open for the original client on the new runtime",
                "unchangedSourceBuild": "both supplied preparations record matching source digests"
                                        if old["sourceSha256"] and old["sourceSha256"] == new["sourceSha256"]
                                        else "open for unchanged source",
                "adaptedApplication": "compare the supplied client and runtime on each side"},
            "claims": [], "preparationSeconds": round(time.monotonic() - started, 4)}
    plan["discovery"] = {"mode": "supplied entry" if declared else inventory["inputMode"], "probed": sorted(selected_entries),
                         "totalCandidates": inventory["candidateCount"], "manualProviderIndices": 0, **measurements}
    eligible = sorted(e for e in selected_entries if all(bindings[s][e]["status"] == "bound" for s in graphs))
    plan["discovery"]["boundOnBothRevisions"] = eligible
    if inventory.get("upstreamHistory") and not declared:
        inventory["intentOptions"] = [
            {"entry": candidate["entry"], "rank": candidate["rank"], "staticRank": candidate.get("staticRank"),
             "observedRank": candidate["observedRank"], "coverage": candidate["originalTestCoverage"]}
            for candidate in inventory["candidates"]
            if candidate["entry"] in eligible and "observedRank" in candidate]
        if len(inventory["intentOptions"]) > 1:
            options = ", ".join(row["entry"] for row in inventory["intentOptions"])
            inventory["intentQuestion"] = "Which of these measured public histories matters to your caller? " + options
    plan["discovery"]["selectedEntries"] = (eligible if declared or inventory["candidateCount"] == 1 else [])
    previous = json.loads(args.previous.read_text()) if args.previous else None
    if previous is not None:
        plan["resumedBindings"] = {key: "requalified" if previous.get("entryBindings", {}).get(key) == value else "new binding"
                                   for key, value in binding_records.items()}
        if "entryBindings" not in previous:
            plan["previousBindingStatus"] = "historical receipt requires requalification"
    if previous is not None and (previous.get("schema") != SCHEMA or previous.get("change") != plan["change"]):
        raise ValueError("previous report belongs to a different change")
    prior_claims = {r["id"]: r for r in (previous or {}).get("claims", [])}
    pending = []
    for name, (row, scope, probe, spec) in workflows.items():
        assumptions = row.get("assumptions", [])
        claim_key = digest({"scope": spec, "intent": row["intent"], "assumptions": assumptions})
        basis = {"sourceClaim": claim_key, "runner": runner, "comparator": plan["tools"]["comparator"],
                 "probe": upgrade_replay.sha(probe), "environment": environment,
                 "seconds": args.seconds, "kind": "production"}
        candidate = next((c for c in inventory["candidates"] if c["entry"] == spec["entry"]), {})
        trace_changes = sorted({s["chain"][-1] for s in candidate.get("sides", {}).values() if s.get("chain")})
        prior = prior_claims.get(name, {})
        if prior.get("claimKey") == claim_key and prior.get("traceInput") == list(getattr(args, "changed_selector", [])):
            trace_changes = prior.get("traceChangedEntries", trace_changes)
        # Direct-entry evidence remains comparable when replacing the other revision makes the bytecode diff empty.
        basis["traceChangedEntries"] = trace_changes or [spec["entry"]]
        if "generatedObserver" in spec:
            from targets import observer_generation
            record, registration = observer_generation.checked_bundle(scope, spec, probe)
            basis["traceChangedEntries"] = sorted(set(registration["changed"]) | set(getattr(args, "changed_selector", []))) or [spec["entry"]]
            basis["generatedObserver"] = spec["generatedObserver"]["sha256"]
            basis["projectionChecker"] = digest(observer_generation.identity())
        helper = row.get("checkedHelper")
        if helper is not None:
            basis["checkedHelper"] = digest(helper)
        execution_key = digest([basis, old["key"], new["key"], *operands])
        node = {"id": name, "claimKey": claim_key, "executionKey": execution_key, "entry": spec["entry"],
                "statement": spec["observer"], "domain": spec["cases"], "scope": spec["basis"],
                "cohort": row["cohort"], "intent": row["intent"], "assumptions": assumptions,
                "status": "open", "firstOpenDependency": "original caller executions"}
        if helper is not None:
            node["derivation"] = "finite public history with a checked, pure helper substituted on both deployments"
        node["traceChangedEntries"] = basis["traceChangedEntries"]
        node["observerProvenance"] = ({"kind": "generated", "bundle": basis["generatedObserver"],
                                      "classes": record["compiled"], "assertedSides": spec["assertedSides"]}
                                     if "generatedObserver" in spec else {"kind": "authored"})
        node["traceInput"] = list(getattr(args, "changed_selector", []))
        node["entryBindings"] = {s: digest(bindings[s][spec["entry"]]) for s in graphs}
        plan["claims"].append(node)
        if spec["entry"] in problems:
            node["firstOpenDependency"] = problems[spec["entry"]]
            continue
        if args.run:
            pending.append((node, basis, row, scope, probe, spec))
    plan["executionState"] = "running" if args.run else "planned"
    if args.run and original_binary:
        change_evidence.write_json(args.output, plan)
    manifests = {s: launches[s]["production"].get("manifestClassPath", {}) for s in jdks}
    missing = {p for manifest in manifests.values() for p in manifest.get("absent", [])}
    unresolved = {s: m["unresolved"] for s, m in manifests.items() if m.get("unresolved")}
    for node, basis, row, scope, probe, spec in pending:
        initially_absent = change_inventory.absences_hold(missing)
        closed = row.get("deterministicUnderAssumptions") is True and node["assumptions"] and not unresolved and initially_absent
        use_cache = args.cache is not None and closed
        side_inputs = {s: {"jdk": images[j], "environmentFiles": launches[s]["production"].get("environmentFiles", [])}
                       for s, j in jdks.items()}
        for side, manifest in manifests.items():
            if manifest:
                side_inputs[side]["manifestClassPath"] = manifest
        new_expected = {c["input"]: c["expectedNew"] for c in row["intent"].get("allowedChanges",[])} if isinstance(row["intent"], dict) else {}
        cache = change_evidence.SideCache(args.cache, basis, side_inputs, defer_writes=True,
                                          new_expected=new_expected) if use_cache else None
        evidence = {}
        try:
            upgrade_replay.evaluate(scope, args.before, args.after, probe, jdks["old"], operands, args.seconds,
                                    fixtures=args.fixtures, progress=evidence, side_cache=cache,
                                    after_jdk=jdks["new"], application_change=True,
                                    trace_changes=basis.get("traceChangedEntries", ()),
                                    entry_bindings={s: bindings[s][spec["entry"]] for s in graphs},
                                    effective_files={s: (paths[s], launches[s]["production"]) for s in graphs},
                                    checked_helper=(row["checkedHelper"], checker, images, args.cache) if "checkedHelper" in row else None)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            evidence.update(status="open", reason=str(error))
        stable = initially_absent and change_inventory.absences_hold(missing)
        changed_files = change_inventory.changed_inputs((old, new))
        if "generatedObserver" in spec:
            node["rescoreDomainClosed"] = bool(closed and stable and not changed_files)
        if cache and stable and not changed_files and evidence.get("status") != "open":
            cache.publish_pending()
        if evidence.get("cases") == spec["cases"]:
            node.update(change_evidence.compose(spec, evidence, row["intent"]))
            for c in node["children"]:
                c["id"] = digest([node["claimKey"], node["executionKey"], c["input"]])
            node["dependsOn"] = [{"id": c["id"], "reason": "original entry on both sides of this admitted input"}
                                 for c in node["children"]]
            needs_closed_domain = node["status"] == "established" or (
                spec.get("pairedObservation") == "different-on-any-input" and node["status"] == "refuted")
            if needs_closed_domain and not closed:
                node.update(status="open", firstOpenDependency="bind all runtime inputs and justify deterministic observations")
        if unresolved or not stable:
            node.update(status="open", firstOpenDependency={"manifestClassPath": unresolved} if unresolved
                        else "a manifest Class-Path changed during the original JVM comparisons")
        if changed_files:
            node.update(status="open", firstOpenDependency={"changedRuntimeFiles": changed_files})
        if "checkedHelper" in row:
            node["helperProofs"] = {side: {k: proof[k] for k in ("key", "entry", "action", "proofDigest")}
                                    for side, proof in evidence.get("helperProofs", {}).items()}
            if node["status"] == "open" and evidence.get("reason"):
                node["firstOpenDependency"] = evidence["reason"]
        for key in ("stoppedAt", "beforeEntryComparison", "linkage", "reason"):
            if key in evidence:
                node[key] = evidence[key]
        node["execution"] = cache.actions if cache else {s: {"action": "executed"} for s in paths if evidence.get("sides", {}).get(s, {}).get("trials")}
        receipt_hash = digest(evidence)
        receipt = args.output.parent / "receipts" / (receipt_hash + ".json")
        change_evidence.write_json(receipt, evidence)
        node["receipt"] = {"path": os.path.relpath(receipt, args.output.parent), "sha256": upgrade_replay.sha(receipt)}
        for side, ref in node["entryBindings"].items():
            trials = evidence.get("sides", {}).get(side, {}).get("trials", [])
            plan["bindingWitnesses"].setdefault(ref, []).append({"claim": node["id"], "receipt": node["receipt"],
                "qualifiedMethodEntries": sum(t.get("qualifiedMethodEntries", 0) for t in trials),
                "changedBodyChains": sorted({tuple(chain) for t in trials for rep in t.get("changedBodyChains", []) for chain in rep}),
                "dispatchedTo": sorted({i["dispatchedTo"] for t in trials for i in t.get("entryInvocations", [])})})
        node["observerAndReplaySeconds"] = evidence.get("elapsedSeconds")
        if original_binary:
            change_evidence.write_json(args.output, plan)
    plan["counts"] = {cohort: dict(Counter(n["status"] for n in plan["claims"] if n["cohort"] == cohort))
                      for cohort in ("registered", "additional", "control")}
    if workflows and original_binary and clients["old"] != clients["new"]:
        # Keep every new deploy-time provider in its original position. The client alone comes from the old build.
        manifest = json.loads(args.after.read_text())
        for item in [*manifest["classpath"], *manifest.get("manifestProviders", []), *manifest.get("environmentFiles", [])]:
            item["file"] = str((args.after.parent / item["file"]).absolute())
        if manifest.get("deploymentRoot"):
            manifest["deploymentRoot"] = str((args.after.parent / manifest["deploymentRoot"]).resolve())
        root_index = next((i for i,r in enumerate(manifest["classpath"]) if r.get("role") == "client"), 0)
        changed_client = manifest["classpath"][root_index]
        changed_client.update(file=str(paths["old"][old["clientIndex"]]), sha256=clients["old"])
        if "deploymentPath" in changed_client:
            # A different client needs its own verified layout; do not claim it occupied the captured new URL.
            manifest["layoutKnown"] = False
            changed_client.pop("deploymentPath")
        manifest.update(sourceSha256=old["sourceSha256"], scope="original binary on the new runtime")
        with tempfile.TemporaryDirectory(prefix="change-binary-") as work:
            path = Path(work) / "prepared.json"
            change_evidence.write_json(path, manifest)
            alternate = argparse.Namespace(**vars(args))
            alternate.after, alternate.after_test, alternate.previous = path, None, None
            if args.new_dependency == clients["new"]:
                alternate.new_dependency = clients["old"]
            binary = compare(alternate, original_binary=False, archive_index=archive_index)
            plan["entryBindings"].update(binary["entryBindings"])
            plan["graphs"].update(binary["graphs"])
        plan["deploymentQuestions"]["originalBinary"] = {"launch": binary["launches"]["new"]["production"],
                                                        "claims": binary["claims"], "counts": binary["counts"],
                                                        "bindingWitnesses": binary["bindingWitnesses"]}
    plan["wallSeconds"] = round(time.monotonic() - started, 4)
    if args.run:
        plan["executionState"] = "complete"
    if previous is not None:
        plan["delta"] = delta(previous, plan)
    # A provider can appear or be replaced after an earlier claim. Check again before publishing the plan.
    if args.run:
        changed_final = change_inventory.changed_inputs((old, new))
        stable_final = not changed_final and change_inventory.absences_hold(missing)
        for node in plan["claims"]:
            if not stable_final and "rescoreDomainClosed" in node:
                node["rescoreDomainClosed"] = False
            if node["status"] != "open" and not stable_final:
                node.update(status="open", firstOpenDependency="deployment changed before plan publication")
        plan["counts"] = {cohort: dict(Counter(n["status"] for n in plan["claims"] if n["cohort"] == cohort))
                          for cohort in ("registered", "additional", "control")}
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
    binding_path = folder / "records" / "entry-bindings.json"
    if binding_path.is_file():
        recorded = json.loads(binding_path.read_text())
        report["entryBindings"] = recorded.get("entryBindings", {})
        report["bindingGraphs"] = recorded.get("graphs", {})
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


def saved_bindings(report, receipt_root=None):
    """Read a saved scaffold or replay without starting a JVM, locating its artifacts or trusting a stale key."""
    if report.get("schema") != SCHEMA:
        raise ValueError("unknown saved change-plan format")
    if "entryBindings" not in report:
        return {"status": "requalification required", "reason": "historical plan predates independent entry bindings",
                "claims": [n["id"] for n in report.get("claims", [])]}
    records = report["entryBindings"]
    graphs = report.get("graphs", {})
    for key, graph in graphs.items():
        identity = {k:v for k,v in graph.items() if k not in ("key", "commit", "sourceSha256", "preparation")}
        if key != graph.get("key") or digest(identity) != key:
            raise ValueError("saved deployment graph differs from its digest")
    for key, record in records.items():
        if key != digest(record) or record.get("graph") not in graphs:
            raise ValueError("saved entry binding or its graph reference differs")
    rows = []
    groups = [("adapted", c, report.get("bindingWitnesses", {})) for c in report.get("claims", [])]
    alternate = report.get("deploymentQuestions", {}).get("originalBinary")
    if isinstance(alternate, dict) and "bindingWitnesses" in alternate:
        groups.extend(("original-client", c, alternate["bindingWitnesses"]) for c in alternate.get("claims", []))
    for profile, claim, witnesses_by_binding in groups:
        for side, ref in claim.get("entryBindings", {}).items():
            record = records.get(ref)
            if not record or record["side"] != side or record["entry"] != claim["entry"]:
                raise ValueError("saved question points to a different side or selector")
            witnesses = [w for w in witnesses_by_binding.get(ref, []) if w["claim"] == claim["id"]]
            if report.get("executionState") == "complete" and claim["status"] in ("refuted", "established") and not witnesses:
                raise ValueError("completed question has no original witness at its bound entry")
            if receipt_root is not None:
                for witness in witnesses:
                    receipt = witness["receipt"]
                    file = (receipt_root / receipt["path"]).resolve()
                    if (not file.is_relative_to(receipt_root.resolve()) or upgrade_replay.sha(file) != receipt["sha256"]
                            or json.loads(file.read_bytes())["sides"][side].get("entryBinding") != ref):
                        raise ValueError("original witness receipt differs from the saved entry binding")
            rows.append({"deploymentQuestion": profile, "claim": claim["id"], "claimKey": claim["claimKey"], "side": side, "entry": record["entry"],
                         "binding": ref, "status": record["status"], "providerIndex": record.get("providerIndex"),
                         "classSha256": record.get("classSha256"), "physicalEntry": record.get("physicalEntry"),
                         "firstOpenDependency": record.get("firstOpenDependency"),
                         "witnesses": witnesses})
    return {"status": "recorded", "graphs": len(graphs), "bindings": len(records), "claims": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    saved = sub.add_parser("bindings", help="read and check saved entry records offline")
    saved.add_argument("report", type=Path)
    saved.add_argument("--output", type=Path)
    saved.add_argument("--verify-receipts", action="store_true", help="also verify the saved original-JVM evidence files")
    rescore = sub.add_parser("rescore", help="evaluate new predictions against qualified frozen public observations")
    for name in ("report", "bundle", "predictions", "output"):
        rescore.add_argument("--" + name, required=True, type=Path)
    helper = sub.add_parser("helper-table", help="derive a checked minimum table from live public call sites")
    for name in ("report", "bundle", "jdk", "output"):
        helper.add_argument("--" + name, required=True, type=Path)
    example = sub.add_parser("example", help="project the target runner's frozen claims, routes and dependencies")
    example.add_argument("number", type=int)
    upgrade = sub.add_parser("upgrade", aliases=["application"], help="compare prepared JVM applications with their ordered classpaths")
    for name in ("before", "after", "jdk"):
        upgrade.add_argument("--" + name, type=Path, required=True)
    upgrade.add_argument("--workflows", type=Path, help="frozen public questions; omit for binary-only entry discovery")
    upgrade.add_argument("--supplied-only", action="store_true", help="qualify approved callers without a cold discovery measurement")
    upgrade.add_argument("--entry", action="append", default=[], help="approved public selector to qualify")
    upgrade.add_argument("--changed-selector", action="append", default=[], help="exact changed selector to discover public callers for")
    upgrade.add_argument("--upstream-history",action="append",type=Path,default=[],
                         help="rank callers with bound raw events from an original upstream test launch")
    upgrade.add_argument("--probe-limit", type=int, default=8, help="maximum cold candidates to look up, without selecting intent")
    for name in ("before-test", "after-test", "after-jdk", "fixtures", "cache", "previous"):
        upgrade.add_argument("--" + name, type=Path)
    for name in ("old-dependency", "new-dependency"):
        upgrade.add_argument("--" + name, help="tracked runtime artifact digest (default: the client JAR)")
    upgrade.add_argument("--checker", type=Path, default=Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")))
    upgrade.add_argument("--seconds", type=int, default=60, help="per-workflow replay budget")
    upgrade.add_argument("--run", action="store_true", help="execute the finite obligations on the original JVM")
    for command in (example, upgrade):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if getattr(args, "probe_limit", 0) < 0:
        parser.error("--probe-limit must be nonnegative")
    try:
        if args.command == "helper-table":
            from targets import observer_generation
            change_evidence.write_json(args.output, observer_generation.helper_table(args.report, args.bundle, args.jdk))
            return 0
        if args.command == "rescore":
            from targets import observer_rescore
            change_evidence.write_json(args.output, observer_rescore.score(args.report, args.bundle, args.predictions))
            return 0
        if args.command == "bindings":
            account = saved_bindings(json.loads(args.report.read_bytes()), args.report.parent if args.verify_receipts else None)
            if args.output:
                change_evidence.write_json(args.output, account)
            else:
                print(json.dumps(account, indent=2))
            return 0
        plan = example_plan(args.number) if args.command == "example" else compare(args)
        change_evidence.write_json(args.output, plan)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"change plan: {error}\n")
    print(f"{len(plan['claims'])} claims in {args.output}")
    return 0
