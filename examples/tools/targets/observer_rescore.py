"""Score new predicates using the qualified fields of a frozen generated observer."""
import json
from pathlib import Path
import tempfile

from targets import change_evidence, change_inventory, change_plan, observer_generation, upgrade_replay


def read(path):
    return json.loads(path.read_bytes())


def stable_domain(node, plan, workflow):
    if workflow.get("deterministicUnderAssumptions") is not True or not workflow.get("assumptions"):
        return False
    if "rescoreDomainClosed" in node:
        return node["rescoreDomainClosed"] is True
    # Older reports checked both shared production launches at publication and downgraded
    # every decided claim on a changed input. A decided question at the same bindings witnesses that check.
    return any(sibling["status"] in ("established", "refuted") and sibling["entryBindings"] == node["entryBindings"]
               for sibling in plan["claims"])


def score(report_path, bundle, predictions):
    plan = read(report_path)
    if plan.get("executionState") != "complete":
        raise ValueError("re-scoring requires completed original JVM observations")
    bindings = change_plan.saved_bindings(plan)
    if bindings["status"] != "recorded":
        raise ValueError("re-scoring requires independently bound original entries")
    by_side = {(b["claim"], b["side"]): b for b in bindings["claims"] if b["deploymentQuestion"] == "adapted"}
    checks = read(predictions)
    _, originals = change_plan.frozen_workflows(bundle / "workflows.json")
    nodes = {n["id"]: n for n in plan["claims"]}
    if len(nodes) != len(plan["claims"]) or set(nodes) != set(originals) or set(nodes) != set(checks):
        raise ValueError("predictions or report belong to other registered questions")
    result = {"schema": "rescored-public-observations/v1", "reportSha256": upgrade_replay.sha(report_path),
              "predictionsSha256": upgrade_replay.sha(predictions), "claims": []}
    with tempfile.TemporaryDirectory(prefix="public-rescore-") as temp:
        dest = Path(temp)
        (dest / "generation.json").write_bytes((bundle / "generation.json").read_bytes())
        observer_generation.workflows(read(bundle / "registration.json"), checks, dest)
        for row in read(dest / "workflows.json")["workflows"]:
            name = row["id"]
            node = nodes[name]
            original, _, _, spec = originals[name]
            if node["claimKey"] != change_inventory.digest({"scope": spec, "intent": original["intent"],
                                                            "assumptions": original["assumptions"]}):
                raise ValueError("saved claim differs from the frozen bundle")
            attempt = {"id": name, "originalStatus": node["status"], "status": "open",
                       "firstOpenDependency": node["firstOpenDependency"]}
            result["claims"].append(attempt)
            ref = node.get("receipt")
            if not ref or (node["status"] == "open" and (type(node["firstOpenDependency"]) is not int
                                                         or node.get("stoppedAt") or node.get("reason"))):
                continue
            if not stable_domain(node, plan, original):
                attempt["firstOpenDependency"] = "no recorded stable deterministic deployment for re-scoring"
                continue
            path = (report_path.parent / ref["path"]).resolve()
            if not path.is_relative_to(report_path.parent.resolve()) or upgrade_replay.sha(path) != ref["sha256"]:
                raise ValueError("original JVM receipt differs")
            evidence = read(path)
            if (evidence.get("generatedObserver", {}).get("bundle") != spec["generatedObserver"]["sha256"]
                    or evidence.get("cases") != spec["cases"]):
                raise ValueError("measurement belongs to another observer or input domain")
            prior = change_evidence.compose(spec, evidence, original["intent"])
            if prior["status"] != node["status"]:
                raise ValueError("saved adjudication disagrees with its qualified original observations")
            if node["status"] == "open" and (prior["firstOpenDependency"] != node["firstOpenDependency"]
                    or any(c[s] is None for c in prior["children"] for s in spec["assertedSides"])):
                continue
            for side in spec["assertedSides"]:
                binding = by_side.get((name, side))
                if (not binding or binding["status"] != "bound"
                        or not any(w["receipt"] == ref for w in binding["witnesses"])
                        or evidence.get("sides", {}).get(side, {}).get("entryBinding") != binding["binding"]):
                    raise ValueError("original JVM receipt differs from the claim's bound deployment")
            new_spec = read(dest / row["scope"])
            scored = change_evidence.compose(new_spec, {**evidence, "cases": new_spec["cases"]}, row["intent"])
            observations = {s: [t["observations"] for t in record["trials"]] for s, record in evidence["sides"].items()}
            attempt.update(scored, receipt=ref, entryBindings=node["entryBindings"],
                           observationsSha256=change_inventory.digest(observations))
    return result
