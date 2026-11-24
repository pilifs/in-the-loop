"""Project the frozen Guava experiment into individually scoped evidence for a change plan."""

import argparse
import json
from pathlib import Path
import sys

from decision_evidence import EV, read, report as recount, require
from prepare import HERE, digest

ROOT = HERE.parents[2]
MANIFEST = HERE / "change-nodes.json"


def pin(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path.read_bytes())}


def method_node(number, name, trials):
    folder = EV / "transfer" / name
    row, = (r for r in trials["cases"] if r["control"] == name)
    baseline = read(EV / "baseline" / f"{number}.json")["freshResult"]
    req = pin(HERE / "requests" / f"{name}.request")
    cert = pin(folder / "evidence.cert")
    owner = baseline["entry"].split("#")[0].replace(".", "/")
    artifacts = [pin(HERE / "inputs" / (c.split("/")[-1] + ".bin")) for c in baseline["classes"]]
    for artifact, bound in zip(artifacts, baseline["classes"].values(), strict=True):
        require(artifact["sha256"] == bound["sha256"], "bound class differs")
    require(
        baseline["classes"][owner]["sha256"] == row["classSha256"]
        and req["sha256"] == row["requestSha256"] and cert["sha256"] == row["certificateSha256"]
        and trials["rustBuild"]["binarySha256"] == row["checkerVersion"]
        and row["actual"] == "accepted"
        and all(c["exit"] == 0 and c["stdout"] == row["outcome"] for c in row["checks"]),
        f"{name} external request, acceptance or artifacts differ",
    )
    task = "first-any-length"
    return {
        "id": f"{number}/{task}",
        "kind": "java-method",
        "example": number,
        "task": task,
        "claimKey": baseline["sourceKey"],
        "entry": baseline["entry"],
        "statement": "The public call terminates normally, returns the first matching index or -1 when absent, and preserves the heap.",
        "scope": baseline["domain"],
        "disposition": "established",
        "artifacts": artifacts,
        "request": req,
        "certificate": cert,
        "receipt": {**pin(EV / "transfer/results.json"), "control": name},
        "checker": {"name": "Rust Guava semantic checker", "sha256": row["checkerVersion"]},
        "assumptionsRemoved": ["historical Python induction rule", "javap", "Z3", "certificate issuer", "prior verdict and cache"],
        "assumptionsRetained": [
            "Verified class bytes, pinned resolution, successful initialization and single-threaded JVM execution.",
            "Sufficient VM resources and no asynchronous termination.",
            "Independent class decoding and induction rules, their correspondence to JVM execution, SHA-256 and the Rust toolchain.",
        ],
    }


def formula_nodes():
    folder = EV / "bounded-sat"
    capture = read(folder / "capture.json")
    records = read(folder / "guava/queries.json")
    pack = pin(folder / "guava/proofs.tar.gz")
    artifact = pin(HERE / "inputs/Ints.bin")
    require(pack["sha256"] == records["packSha256"], "Guava LRAT pack differs")
    result = []
    for q in records["queries"]:
        require(
            q["requestedClaim"] == capture["claim"] == "336/first-8-release"
            and q["classSha256"] == artifact["sha256"] == capture["classSha256"]
            and q["actual"] == "verified UNSAT"
            and all(c["exit"] == 0 and "s VERIFIED UNSAT" in c["stdout"].splitlines() for c in q["checks"]),
            "query receipt differs",
        )
        result.append({
            "id": capture["claim"] + "/" + q["key"],
            "kind": "solver-query",
            "example": 336,
            "task": "first-8-release",
            "parentNativeClaimId": capture["claimId"],
            "claimKey": q["cnfSha256"],
            "statement": "The clause prefix for this solve is unsatisfiable under its recorded assumption units.",
            "scope": {"queryOneBased": q["queryOneBased"], "transcriptSha256": q["transcriptSha256"], "assumptions": q["assumptions"]},
            "disposition": "established",
            "artifacts": [artifact, pin(folder / "traces" / q["trace"])],
            "certificate": {**pack, "member": q["key"] + ".lrat", "memberSha256": q["proofSha256"]},
            "receipt": {**pin(folder / "guava/queries.json"), "query": q["key"]},
            "checker": {"name": "cake_lpr", "revision": records["checkerRevision"], "sha256": q["checkerVersion"]},
            "assumptionsRemoved": ["CaDiCaL's UNSAT answer and proof generation"],
            "assumptionsRetained": [
                "Transcript binding, clause-prefix extraction and assumption encoding.",
                "cake_lpr and its verified checker toolchain.",
                "A Java verdict also requires sound bytecode modeling, reachability and coverage of every execution.",
            ],
        })
    return result


def manifest():
    cases_path = EV / "cases.json"
    frozen = read(cases_path)
    require(recount() == frozen, "frozen kernel case table or its underlying evidence differs")
    trials = read(EV / "transfer/results.json")
    return {
        "schema": "change-independent-evidence/v1",
        "evaluation": pin(cases_path),
        "nodes": [method_node(336, "Ints", trials), method_node(346, "Longs", trials), *formula_nodes()],
    }


def for_plan(folder, claims, data):
    """Match a method contract or a captured invocation's query to a currently planned subject."""
    sys.path.insert(0, str(ROOT / "examples/tools"))
    from targets import array_induction

    number = int(read(folder / "example.json")["id"])
    target = read(folder / "target.json")
    methods = {s["id"]: s for s in target.get("arrayContracts", [])}
    prepared = {
        (c["id"], e["preparedClaim"]): c["claimKey"]
        for c in claims for e in c.get("ordinary", [])
        if e.get("route") == "ordinary" and e.get("preparedClaim")
    }
    current, historical = [], []
    for node in data["nodes"]:
        if node["example"] != number:
            continue
        task = node["task"]
        if node["kind"] == "java-method":
            spec = methods.get(task)
            try:
                applies = spec is not None and node["claimKey"] == array_induction.record_key(folder, target, spec)[1]
            except (KeyError, OSError, ValueError):
                applies = False
            binding = {"kind": "array-contract", "task": task, "claimKey": node["claimKey"]}
            reason = "The current array contract or its source lock differs from the frozen contract."
        else:
            key = prepared.get((task, node["parentNativeClaimId"]))
            applies = key is not None
            binding = {
                "kind": "captured-solver-query", "task": task, "claimKey": key,
                "preparedClaim": node["parentNativeClaimId"], "cnfSha256": node["claimKey"],
            }
            reason = "The current ordinary task has no eligible receipt for the captured prepared claim."
        if applies:
            current.append({**node, "boundTo": binding})
        else:
            historical.append({"id": node["id"], "claimKey": node["claimKey"], "recordedDisposition": node["disposition"],
                               "receipt": node["receipt"], "reason": reason})
    return {"manifest": pin(MANIFEST), "evaluation": data["evaluation"], "nodes": current, "historical": historical}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare the manifest with its frozen inputs")
    mode.add_argument("--for-plan", type=Path, metavar="EXAMPLE", help="read current claim subjects from stdin")
    args = ap.parse_args()
    try:
        data = manifest()
        if args.check or args.for_plan:
            require(read(MANIFEST) == data, "change-plan manifest differs")
            if args.for_plan:
                print(json.dumps(for_plan(args.for_plan, json.load(sys.stdin), data)))
                return
        else:
            MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
    except (KeyError, OSError, ValueError) as error:
        ap.exit(1, f"Guava kernel evidence: {error}\n")
    print(f"{len(data['nodes'])} independently checked nodes from {data['evaluation']['sha256']}")


if __name__ == "__main__":
    main()
