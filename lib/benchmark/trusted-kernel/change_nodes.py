"""Project the frozen Guava experiment into individually scoped evidence for a change plan."""

import argparse
import json

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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="compare the manifest with its frozen inputs")
    args = ap.parse_args()
    data = manifest()
    if args.check:
        require(read(MANIFEST) == data, "change-plan manifest differs")
    else:
        MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
    print(f"{len(data['nodes'])} independently checked nodes from {data['evaluation']['sha256']}")


if __name__ == "__main__":
    main()
