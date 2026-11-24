"""Project qualified engine, receiver, Spring and independent-kernel receipts into caller obligations."""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(ROOT / "lib/benchmark/java-semantics-gap"))
import build
import scorecard
from targets import change_evidence, change_inventory, change_plan, route, sidecar, upgrade_replay


def read(path):
    return json.loads(path.read_bytes())


@lru_cache(maxsize=None)
def receipt(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": upgrade_replay.sha(path)}


@lru_cache(maxsize=None)
def target(folder):
    ex = build.load_example(folder)
    return ex, sidecar.load(folder, ex)


def semantic_nodes():
    saved = ROOT / "verification/java-semantics-gap/scorecard.json"
    nodes = []
    retry_root = ROOT / "verification/change-verification/semantics/callers"
    retry = scorecard.subject_rows("callers", required_engines=("native", "jbmc"), directory=retry_root)
    for name, states in read(saved)["subjects"].items():
        record = states["final"]
        path = ROOT / record["claim"]
        folder = path.parents[1]
        ex, manifest = target(folder)
        matches = [t for t in manifest["tasks"] if t.get("claim") == path.relative_to(folder).as_posix()]
        task, = [t for t in matches if t.get("revision") == record["graph"]] if len(matches) > 1 else matches
        plan = route.resolve(folder, ex, manifest, task["id"])
        run = ROOT / record["evidence"]
        measurement = read(run)
        if record["source"] != measurement["source"] or plan.claim["sha256"] != upgrade_replay.sha(path):
            raise ValueError(f"{name} has different source or claim bytes")
        repeated = retry[name]
        if any(record[k] != repeated[k] for k in ("graph", "method", "classes", "jvm", "guard", "bound", "claim")):
            raise ValueError(f"{name}: retry changed the frozen statement or application")
        nodes.append({"id": name, "example": ex["id"], "task": task["id"], "claimKey": plan.claim["key"],
                      "entry": plan.claim["target"], "guard": record["guard"], "bound": record["bound"],
                      "statement": record["statement"], "receipt": receipt(run),
                      "checker": measurement["checkerSha256"], "opening": states["opening"]["native"]["status"],
                      "native": record["native"]["status"], "jbmc": record["jbmc"]["status"],
                      "firstOpenDependency": repeated["native"]["firstUnproved"] or None,
                      "retry": {"receipt": receipt(ROOT / repeated["evidence"]), "source": repeated["source"],
                                "native": repeated["native"]["status"], "jbmc": repeated["jbmc"]["status"]}})
    if len(retry) != len(nodes):
        raise ValueError("different number of registered statements in the retry")
    return {"basis": receipt(saved), "families": len({scorecard.SECTIONS[r["family"]] for r in retry.values()}),
            "native": dict(Counter(n["retry"]["native"] for n in nodes)), "jbmc": dict(Counter(n["retry"]["jbmc"] for n in nodes)),
            "nodes": nodes}


def receiver_nodes():
    saved = ROOT / "verification/receiver-discovery/results.json"
    values = read(saved)
    sites = []
    for name, reported in values["training"]["sites"].items():
        path = saved.parent / "qualification/sites" / name / "result.json"
        raw = read(path)
        if (raw["disposition"] != reported["disposition"] or
                raw["subject"]["binding"]["sha256"] != reported["classSha256"]):
            raise ValueError(f"{name} physical site differs from its candidate")
        current = ROOT / "verification/change-verification/receiver/sites"
        run = read(current / "measurement.json")
        fresh = current / name / "result.json"
        scorecard.collected(fresh, run["job"], run["source"])
        now = read(fresh)
        if (now["subject"]["binding"]["sha256"] != reported["classSha256"] or now["site"] != raw["site"]
                or now["policy"] != raw["policy"] or now["disposition"] != reported["disposition"]):
            raise ValueError(f"{name}: a different site, policy or outcome was measured")
        sites.append({"id": name, "entry": {k: raw["entry"][k] for k in ("owner", "method", "descriptor")},
                      "pc": raw["site"]["pc"], "policy": raw["policy"], "reachability": raw["reachability"],
                      "failureQuery": raw["queries"]["safe"]["verdict"], "disposition": raw["disposition"],
                      "receipt": receipt(path), "retry": {"receipt": receipt(fresh), "reachability": now["reachability"],
                                                         "failureQuery": now["queries"]["safe"]["verdict"]}})
    cohort = values["receiverCohort"]
    return {"basis": receipt(saved), "cases": cohort["cases"], "pairedOverloads": cohort["overloads"],
            "unrestricted": cohort["bareOverloads"], "physical": cohort["physical"],
            "bothNative": cohort["nativeBoth"], "sites": sites}


def spring_nodes():
    path = ROOT / "verification/spring-java-data/spring.json"
    score = read(path)
    roots, shared = [], defaultdict(list)
    for ex in score["examples"].values():
        for name, record in ex["claims"].items():
            if not record["primary"]:
                continue
            checker = record["ordinary"]
            root = {"id": f"{ex['example']}/{name}", "claimKey": record["opening"]["claimKey"],
                    "entry": record["entry"], "guard": record["guard"], "statement": record["statement"],
                    "finite": record["finite"]["status"], "finiteReceipt": receipt(ROOT / record["finite"]["receipt"]),
                    "ordinary": checker["status"], "firstOpenDependency": checker.get("firstBlocker")}
            if record["ordinary"].get("record"):
                proof = ROOT / ex["folder"] / checker["record"]
                root["ordinaryReceipt"] = receipt(proof)
                if checker.get("firstBlocker") and checker["status"] in ("open", "unresolved"):
                    binding = read(proof)
                    key = change_inventory.digest([binding["classpath"], binding["JDK"], binding["checker"],
                                                  checker["firstBlocker"]])
                    shared[key].append(root["id"])
            roots.append(root)
    blockers = [{"key": k, "roots": ids, "count": len(ids),
                 "rule": "retry each ordinary caller after the missing semantics is supplied"}
                for k, ids in shared.items()]
    return {"basis": receipt(path), "nodes": roots, "totals": score["totals"],
            "sharedBlockers": sorted(blockers, key=lambda r: (-r["count"], r["roots"]))}


def portfolio():
    independent = {str(n): change_plan.example_plan(n)["independentEvidence"] for n in (336, 346)}
    return {"schema": "change-portfolio/v1", "semantics": semantic_nodes(), "receivers": receiver_nodes(),
            "spring": spring_nodes(), "independent": {
                k: [{"id": n["id"], "task": n["task"], "kind": n["kind"], "claimKey": n["claimKey"],
                     "disposition": n["disposition"], "scope": n["scope"], "receipt": n["receipt"],
                     "assumptionsRemoved": n["assumptionsRemoved"], "assumptionsRetained": n["assumptionsRetained"]}
                    for n in v["nodes"]] for k, v in independent.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = portfolio()
    if args.check:
        if read(args.output) != result:
            raise SystemExit("portfolio differs from its bound receipts")
    else:
        change_evidence.write_json(args.output, result)
    print(f"{len(result['semantics']['nodes'])} semantic statements, {len(result['receivers']['sites'])} physical sites, "
          f"{len(result['spring']['nodes'])} primary Spring claims")
