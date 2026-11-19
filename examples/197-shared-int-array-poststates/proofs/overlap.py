"""Qualify the integrated JBMC profile on a preserving and a discriminating pair of actual methods."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1] / "lib/benchmark"))
from run import measure


def run(work):
    exe = os.environ["JVMCONTRACT"]
    builds = {}
    for name in ("baseline", "alternative", "controls/preserving"):
        dest = work / name
        subprocess.run(["javac", "-proc:none", "-parameters", "-g", "--release", "21", "-d", dest,
                        HERE / name / "arrays/Update.java"], check=True)
        builds[name] = dest
    rows = []
    for full in (True, False):
        profile = "nullable-shared-binary-length-2" if full else "distinct-binary-length-1"
        claim = json.loads((HERE / "claims/both-roots.json").read_text())
        if not full:
            claim.update(nullable=[], mayAlias=[])
            claim["bounds"]["maxArrayLength"] = 1
        semantic = {k: claim[k] for k in ("assume", "nullable", "mayAlias", "bounds", "observations")}
        key = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
        results = []
        for name, expected in [("controls/preserving", "verified"), ("alternative", "violation")]:
            command = [exe, "equivalence", "--before", str(builds["baseline"]), "--after", str(builds[name]),
                       "--target", "arrays.Update#apply", "--engine", "jbmc", "--gaps", "strict",
                       "--unwind", str(claim["bounds"]["unwind"]), "--max-array-length", str(claim["bounds"]["maxArrayLength"]),
                       "--assume", claim["assume"], "--timeout", "90", "--json", "--work", str(work / profile / name)]
            for field, flag in (("nullable", "--nullable"), ("mayAlias", "--may-alias"), ("observations", "--observe")):
                for value in claim[field]:
                    command.extend([flag, json.dumps(value) if isinstance(value, dict) else value])
            measured = measure(command, 120)
            try:
                outcome = json.loads(measured["stdout"])
                if not isinstance(outcome, dict) or "verdict" not in outcome:
                    raise ValueError("incomplete verifier outcome")
            except ValueError:
                outcome = {"verdict": "unverifiable", "problem": "timeout" if measured["killed"] else "no complete verifier outcome"}
            stated = outcome.get("stated") or {}
            matched = (stated.get("spec") or {}).get("observations") == claim["observations"]
            actual_engine = (outcome.get("search") or {}).get("engine")
            complete = (stated.get("bounds") or {}).get("complete") is True and (stated.get("vacuity") or {}).get("status") == "non-vacuous"
            witness = outcome.get("counterexample") or {}
            replayed = (outcome.get("replay") or {}) == {"by": "jvm", "reproduced": True} and witness.get("replay_observations") == claim["observations"]
            qualified = actual_engine == "jbmc" and matched and outcome["verdict"] == expected and (complete if expected == "verified" else replayed)
            results.append(qualified)
            rows.append({"profile": profile, "domainAndObservationSha256": key, "semantics": semantic, "pair": name,
                         "engine": actual_engine, "expected": expected, "verdict": outcome["verdict"], "qualified": qualified,
                         "problem": outcome.get("problem"), "replay": outcome.get("replay"), "witness": witness or None,
                         "seconds": measured["seconds"], "peakMiB": measured["peakMB"]})
        if all(results):
            break
    return {"checkerCommit": os.getenv("VERIFY_SOURCE_COMMIT"), "checkerLibTree": os.getenv("JVMCONTRACT_LIB_TREE"),
            "classSha256": {name: hashlib.sha256((dest / "arrays/Update.class").read_bytes()).hexdigest() for name, dest in builds.items()},
            "rows": rows, "overlapQualified": all(results)}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        report = run(Path(directory))
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["overlapQualified"] else 1)
