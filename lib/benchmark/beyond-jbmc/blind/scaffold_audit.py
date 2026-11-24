"""Collect only source-bound campaign outputs and recheck their public decisions and output hashes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from scaffold_first import DEST, OUTPUT, compressed, digest, read, save
from history import ROOT
import sys
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_evidence


def require(value, message):
    if not value:
        raise ValueError(message)


def collect(collector):
    specs = ROOT / "verification/jobs"
    prefix = DEST.relative_to(ROOT)
    ledger = []
    for spec in sorted(specs.rglob("*.json")):
        job = read(spec)
        requested = list(map(Path, job.get("outputs", [])))
        if not requested or not all(p.is_relative_to(prefix) for p in requested):
            continue
        result_file = collector / "verification/results" / spec.parent.relative_to(specs) / job["id"] / "result.json"
        if not result_file.exists():
            ledger.append({"id": job["id"], "status": "awaiting collection"})
            continue
        result = read(result_file)
        source = result["sourceCommit"]
        frozen_job = subprocess.check_output(["git", "show", source + ":" + spec.relative_to(ROOT).as_posix()], cwd=ROOT)
        require(json.loads(frozen_job) == job == result["job"]["spec"] and result["id"] == job["id"], "job registration differs")
        outputs = []
        if result["status"] == "passed":
            for item in result["outputs"]:
                path = Path(item["path"])
                require(".." not in path.parts and any(path.is_relative_to(p) for p in requested)
                        and item["change"] != "deleted", "unexpected output path")
                dest = ROOT / path
                if not dest.is_file() or digest(dest) != item["sha256"]:
                    locations = [result_file.parent / "outputs" / path, collector / path]
                    origin = next((p for p in locations if p.is_file() and digest(p) == item["sha256"]), None)
                    require(origin is not None, "collected bytes unavailable: " + str(path))
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(origin, dest)
                outputs.append({"path": str(path), "sha256": item["sha256"]})
        ledger.append({"id": job["id"], "status": result["status"], "resultSha256": digest(result_file),
                       "source": source, "usage": result.get("usage"), "outputs": outputs,
                       "failure": result["summary"] if result["status"] != "passed" else None})
    save(DEST / "jobs.json", ledger)


def audit():
    ledger = read(DEST / "jobs.json")
    outputs = {o["path"]: o["sha256"] for j in ledger for o in j.get("outputs", [])}
    for path, h in outputs.items():
        require(digest(ROOT / path) == h, "changed collected output " + path)
    counts = Counter()
    claims = []
    for path in sorted((DEST / "original-plans").glob("*/*/summary.json")):
        doc = read(path)
        slot = path.parent.name
        original = DEST / "registrations" / (slot + ".json")
        archive = path.with_name("plans.zip")
        require(doc["registrationSha256"] == digest(original) and digest(archive) == doc["archiveSha256"], "unbound plan")
        registration = read(original)
        source_data = subprocess.check_output(["git", "show", doc["sourceCommit"] + ":" + original.relative_to(ROOT).as_posix()], cwd=ROOT)
        require(hashlib.sha256(source_data).hexdigest() == doc["registrationSha256"], "job registered different original inputs")
        with zipfile.ZipFile(archive) as z:
            public = {}
            for mode, summaries in doc["runs"].items():
                plan = json.loads(z.read(mode + ".json"))
                require(plan["executionState"] == "complete" and len(plan["claims"]) == len(summaries) == 2, "incomplete plan")
                public[mode] = []
                alternate = plan["deploymentQuestions"].get("originalBinary")
                groups = [plan["claims"]] + ([alternate["claims"]] if isinstance(alternate, dict) else [])
                for group in groups:
                    for other in group:
                        if ref := other.get("receipt"):
                            require(hashlib.sha256(z.read(ref["path"])).hexdigest() == ref["sha256"], "bad receipt")
                for claim, expected, question in zip(plan["claims"], summaries, registration["questions"], strict=True):
                    require(claim["entry"] == question["scope"]["entry"] and claim["domain"] == question["scope"]["cases"]
                            and claim["status"] == expected["status"], "claim differs from registration")
                    if claim.get("receipt"):
                        evidence = json.loads(z.read(claim["receipt"]["path"]))
                        if claim["status"] in ("established", "refuted"):
                            derived = change_evidence.compose(question["scope"], evidence, claim["intent"])
                            require(derived["status"] == claim["status"], "independent composition disagrees")
                        for side, d in evidence.get("sides", {}).items():
                            for trial in d.get("trials", []):
                                counts["qualifiedOriginalEntries"] += trial["qualifiedMethodEntries"]
                                if claim["status"] in ("established", "refuted"):
                                    require(trial["qualifiedMethodEntries"] == 2 and len(trial["observations"]) == 2
                                            and trial["observations"][0] == trial["observations"][1], "unqualified finite decision")
                    public[mode].append((claim["status"], [(c.get("old"), c.get("new")) for c in claim.get("children", [])]))
                counts["plans"] += 1
            if {"cold", "warm", "clean", "wrong"} <= public.keys():
                require(public["cold"] == public["warm"] == public["clean"], "clean and resumed plans differ")
                require([r[0] for r in public["wrong"]] == ["refuted", "established"], "wrong expectation not rejected")
        claims.append({"slot": slot, "phase": doc["phase"], "fullOriginalDomain": doc["fullRegisteredDomain"],
                       "finiteDecisions": [r["status"] for r in doc["runs"]["cold"]], "summary": str(path.relative_to(ROOT))})
    comparisons = []
    for path in sorted((DEST / "remeasured").glob("*/comparison.json.gz")):
        d = compressed(path)
        require(digest(path.with_name("executions.zip")) == d["archiveSha256"], "bad automatic executions")
        first = OUTPUT / ("calibration/artifact-only.json" if d["slot"] == "calibration" else
                          "blind/" + d["slot"] + "/automatic/report.json.gz")
        require(digest(first) == d["firstPassSha256"], "blind first pass differs")
        for row in d["comparisons"]:
            comparisons.append({"slot": d["slot"], **row})
    save(DEST / "audit.json", {"jobs": dict(Counter(j["status"] for j in ledger)), "outputDigests": len(outputs),
                              "counts": counts, "finiteComparisons": claims, "automaticCandidates": comparisons})
    print(len(outputs), "output hashes,", dict(counts), "and", len(comparisons), "automatic candidates checked")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", type=Path)
    args = parser.parse_args()
    if args.collect:
        collect(args.collect.resolve())
    audit()
