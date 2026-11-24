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
from scores import qualified, raw_disposition
import sys
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_evidence


def require(value, message):
    if not value:
        raise ValueError(message)


def source_digest(revision, path):
    data = subprocess.check_output(["git", "show", revision + ":" + path.relative_to(ROOT).as_posix()], cwd=ROOT)
    return hashlib.sha256(data).hexdigest()


def generated_results():
    policy = read(DEST / "successor-freeze.json")
    generators = {str(Path(p).relative_to("examples/tools/targets")): h for p, h in policy["resourceSelector"].items()}
    records = []
    for file in sorted((DEST / "resource-discovery").glob("*/discovery.json")):
        slot = file.parent.name
        d = read(file)
        require(d["operatorFiles"] == generators, "different generator used on one packet")
        fixture = compressed(DEST / "scaffolds" / (slot + ".json.gz"))
        require(d["inputs"] == {s: [x["sha256"] for x in p] for s, p in fixture["classpath"].items()}, "different discovery input")
        for c in d["candidates"]:
            directory = file.parent / c["directory"]
            reg = read(directory / "registration.json")
            physical = read(directory / "scaffold.json")
            require(reg["stage"] == "registered before populated JVM trials" and
                    physical["stage"] == "original JVM controls passed" and digest(directory / "UpgradeProbe.java") == reg["probeSha256"],
                    "incomplete generated scaffold")
            scopes = {name: read(directory / (name + ".json")) for name in reg["scopeSha256"]}
            require(all(digest(directory / (n + ".json")) == h for n, h in reg["scopeSha256"].items()), "scope changed")
            require(all(r["actual"] == r["expected"] for rows in physical["physical"].values() for r in rows), "physical disagreement")
            result = {"slot": slot, "entry": c["entry"], "resources": reg["resources"], "rowsPerSide": len(physical["physical"]["old"])}
            measured = DEST / "resource-plans" / slot / c["directory"] / "summary.json"
            if measured.exists():
                report = read(measured)
                original = directory / "registration.json"
                require(digest(original) == source_digest(report["source"], original) == report["registered"], "different registered caller")
                archive = measured.with_name("plans.zip")
                require(digest(archive) == report["archiveSha256"], "unbound generated plan archive")
                results = {}
                with zipfile.ZipFile(archive) as z:
                    for mode, rows in report["runs"].items():
                        plan = json.loads(z.read(mode + ".json"))
                        actual = []
                        for claim, row in zip(plan["claims"], rows, strict=True):
                            ref = claim["receipt"]
                            data = z.read(ref["path"])
                            require(hashlib.sha256(data).hexdigest() == ref["sha256"], "generated receipt changed")
                            evidence = json.loads(data)
                            scope = scopes[row["id"]]
                            require(claim["domain"] == scope["cases"] and claim["entry"] == scope["entry"], "generated entry/domain changed")
                            rebuilt = change_evidence.compose(scope, evidence, claim["intent"])
                            require(rebuilt["status"] == claim["status"] == row["status"], "generated finite result disagrees")
                            actual.append(row["status"])
                        results[mode] = actual
                require(results["cold"] == results["warm"] == results["clean"] == ["established", "established"]
                        and results["wrong"] == ["refuted", "established"], "unexpected generated controls")
                result["qualifiedPlans"] = results
            profiles = {}
            for side in ("old", "new"):
                path = DEST / "resource-comparators" / slot / side / "results.json.gz"
                if path.exists():
                    measured = compressed(path)
                    require(measured["registered"] == digest(directory / "registration.json") and
                            measured["executionsSha256"] == digest(path.with_name("executions.zip")), "different symbolic measurement")
                    profiles[side] = [qualified(row) for row in measured["rows"]]
            result["symbolicProfiles"] = profiles
            records.append(result)
    return records


def matched_results():
    result = []
    for file in sorted((DEST / "matched-native").glob("*/summary.json")):
        slot = file.parent.name
        current = read(file)
        changes, primary = [], []
        for r in current["rows"]:
            group = file.parent / r["deployment"]
            original = compressed(group / "results.json.gz")
            require(digest(group / "executions.zip") == original["executionsSha256"], "unbound matched native measurement")
            raw = next(x for x in original["rows"] if x["method"] == r["method"])
            require(raw["native"] == r["new"], "matched summary differs from the measured outcome")
            prior, now = (raw_disposition(r[key], raw["expected"], False) for key in ("old", "new"))
            if prior != now:
                changes.append([r["deployment"], r["method"], prior, now])
            if r["method"] == "primary":
                primary.append({"deployment": r["deployment"], "status": now, "firstProblem": r["new"].get("problem")})
        result.append({"slot": slot, "basis": current["basis"], "properties": len(current["rows"]),
                       "primary": primary, "changedDispositions": changes})
    return result


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
        require(source_digest(doc["sourceCommit"], original) == doc["registrationSha256"], "job registered different original inputs")
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
                                counts["qualifiedEntryReferences"] += trial["qualifiedMethodEntries"]
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
    historic_path = OUTPUT / "followup/historical-native/results.json.gz"
    historic = compressed(historic_path)
    policy = read(DEST / "successor-freeze.json")
    require(historic["binaries"]["jvmcontract"] == policy["checkerSha256"] and
            len(historic["cases"]) == 187 and not historic["followup"]["changed"], "different historical checker or denominator")
    resources = {}
    for variant in ("manifest-controls", "manifest-case-controls"):
        file = DEST / variant / "summary.json"
        if file.exists():
            doc = read(file)
            require(digest(file.with_name("plans.zip")) == doc["archiveSha256"], "different manifest controls")
            for name, status in (("absent", "established"), ("repeat", "established"), ("appeared", "open"),
                                 ("bound", "refuted"), ("bound-clean", "refuted"), ("restored", "established")):
                row = doc["observations"][name]
                require(row["status"] == status and row["newReturn"] == ("82" if name in ("appeared", "bound", "bound-clean") else "0"),
                        "unexpected manifest control")
            resources[variant] = doc["observations"]
    save(DEST / "audit.json", {"jobs": dict(Counter(j["status"] for j in ledger)), "outputDigests": len(outputs),
                              "counts": counts, "finiteComparisons": claims, "automaticCandidates": comparisons,
                              "originalMatchedNative": matched_results(), "generatedWorkflows": generated_results(),
                              "historicalReuse": {"sha256": digest(historic_path), "checkerSha256": policy["checkerSha256"],
                                                  "dispositions": historic["followup"]["dispositions"]},
                              "manifestControls": resources})
    print(len(outputs), "output hashes,", dict(counts), "and", len(comparisons), "automatic candidates checked")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", type=Path)
    args = parser.parse_args()
    if args.collect:
        collect(args.collect.resolve())
    audit()
