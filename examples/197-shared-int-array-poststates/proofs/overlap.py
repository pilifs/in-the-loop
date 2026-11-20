"""Qualify the integrated JBMC profile on a preserving and a discriminating pair of actual methods."""

import argparse
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


PROFILES = ("nullable-shared-binary-length-2", "distinct-binary-length-1")


def matches_scope(stated, claim):
    domain = stated.get("domain", {})
    bounds = stated.get("bounds", {})
    limit = claim["bounds"]["maxArrayLength"]
    parameters = [(p.get("name"), p.get("type"), p.get("null"), p.get("max_length"))
                  for p in domain.get("parameters", [])]
    guards = [a.get("text") for a in stated.get("assumptions", []) if a.get("kind") == "precondition"]
    return (parameters == [(name, "int[]", name in claim["nullable"], limit) for name in ("left", "right")]
            and domain.get("may_alias", []) == [pair.split(",") for pair in claim["mayAlias"]]
            and bounds.get("unwind") == claim["bounds"]["unwind"] and bounds.get("max_array_length") == limit
            and guards == [claim["assume"]] and (stated.get("spec") or {}).get("observations") == claim["observations"])


def run(work, records=None, profiles=PROFILES, observation="both-roots"):
    exe = os.environ["JVMCONTRACT"]
    builds = {}
    for name in ("baseline", "alternative", "controls/preserving"):
        dest = work / name
        subprocess.run(["javac", "-proc:none", "-parameters", "-g", "--release", "21", "-d", dest,
                        HERE / name / "arrays/Update.java"], check=True)
        builds[name] = dest
    rows = []
    for profile in profiles:
        full = profile == PROFILES[0]
        claim = json.loads((HERE / "claims" / f"{observation}.json").read_text())
        if not full:
            claim.update(nullable=[], mayAlias=[])
            claim["bounds"]["maxArrayLength"] = 1
        semantic = {k: claim[k] for k in ("assume", "nullable", "mayAlias", "bounds", "observations")}
        key = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
        results = []
        skipped = "verified" if observation == "right-root" and not full else "violation"
        for name, expected in [("controls/preserving", "verified"), ("alternative", skipped)]:
            command = [exe, "equivalence", "--before", str(builds["baseline"]), "--after", str(builds[name]),
                       "--target", "arrays.Update#apply", "--engine", "jbmc", "--gaps", "strict",
                       "--unwind", str(claim["bounds"]["unwind"]), "--max-array-length", str(claim["bounds"]["maxArrayLength"]),
                       "--assume", claim["assume"], "--timeout", "90", "--json", "--work", str(work / profile / name)]
            for field, flag in (("nullable", "--nullable"), ("mayAlias", "--may-alias"), ("observations", "--observe")):
                for value in claim[field]:
                    command.extend([flag, json.dumps(value) if isinstance(value, dict) else value])
            measured = measure(command, 120)
            raw = measured["stdout"].encode()
            label = profile if observation == "both-roots" else f"{profile}-{observation}"
            raw_file = f"{label}-{Path(name).name}.stdout"
            if records is not None:
                (records / raw_file).write_bytes(raw)
            try:
                outcome = json.loads(measured["stdout"])
                if not isinstance(outcome, dict) or "verdict" not in outcome:
                    raise ValueError("incomplete verifier outcome")
            except ValueError:
                outcome = {"verdict": "unverifiable", "problem": "timeout" if measured["killed"] else "no complete verifier outcome"}
            stated = outcome.get("stated") or {}
            matched = matches_scope(stated, claim)
            actual_engine = (outcome.get("search") or {}).get("engine")
            complete = (stated.get("bounds") or {}).get("complete") is True and (stated.get("vacuity") or {}).get("status") == "non-vacuous"
            witness = outcome.get("counterexample") or {}
            replayed = (outcome.get("replay") or {}) == {"by": "jvm", "reproduced": True} and witness.get("replay_observations") == claim["observations"]
            if replayed and observation == "right-root":
                roots = witness.get("inputs", [])
                replayed = (len(roots) == 2 and roots[0].get("name") == "left" and roots[1].get("name") == "right"
                            and roots[1].get("value") == {"same": 0} and witness.get("differs") == ["array:right"])
            qualified = actual_engine == "jbmc" and matched and outcome["verdict"] == expected and (complete if expected == "verified" else replayed)
            results.append(qualified)
            rows.append({"profile": profile, "domainAndObservationSha256": key, "semantics": semantic, "pair": name,
                         "engine": actual_engine, "expected": expected, "verdict": outcome["verdict"], "qualified": qualified,
                         "argv": command, "statement": stated,
                         "verifierOutput": raw_file if records is not None else None,
                         "verifierOutputSha256": hashlib.sha256(raw).hexdigest(),
                         "problem": outcome.get("problem"), "replay": outcome.get("replay"), "witness": witness or None,
                         "seconds": measured["seconds"], "peakMiB": measured["peakMB"]})
        if all(results):
            break
    return {"observation": observation, "checkerCommit": os.getenv("VERIFY_SOURCE_COMMIT"), "checkerLibTree": os.getenv("JVMCONTRACT_LIB_TREE"),
            "checkerSha256": hashlib.sha256(Path(exe).read_bytes()).hexdigest(),
            "classSha256": {name: hashlib.sha256((dest / "arrays/Update.class").read_bytes()).hexdigest() for name, dest in builds.items()},
            "rows": rows, "overlapQualified": all(results)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, help="directory for the checker output of each real execution")
    parser.add_argument("--profile", choices=PROFILES, help="run a specific heap domain")
    parser.add_argument("--observation", choices=("both-roots", "right-root"), default="both-roots")
    args = parser.parse_args()
    if args.records:
        args.records.mkdir(parents=True, exist_ok=True)
    profiles = (args.profile,) if args.profile else PROFILES
    if args.observation == "right-root" and not args.profile:
        profiles = (PROFILES[0],)
    with tempfile.TemporaryDirectory() as directory:
        report = run(Path(directory), args.records, profiles, args.observation)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["overlapQualified"] else 1)
