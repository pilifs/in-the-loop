"""Recheck the frozen 23 receiver cases at their registered scopes, preserving each original binding."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from callers import ASSETS, EXTERNAL, RESULTS, ROOT, prepared_inputs, read, sha
from investigate import write

sys.path.insert(0, str(EXTERNAL))
from engineering_report import checked_finite

BASE = ROOT / "verification/domain-foundations"


def score(key, signatures, raw, prior, host, checker_digest):
    caller_path = Path("callers") / (key + ".json")
    overload_path = Path("overloads/current") / (key + ".json")
    before, caller = read(prior / caller_path), read(raw / caller_path)
    old, now = read(prior / overload_path), read(raw / overload_path)
    if now["id"] != key or caller["cases"] != before["cases"]:
        raise ValueError("different case or inputs: " + key)
    after = caller["nativeCaller"]
    if (
        any(after[k] != before["nativeCaller"][k] for k in ("assume", "maxArrayLength", "unwind", "target"))
        or after["checkerSha256"] != checker_digest
    ):
        raise ValueError("changed caller claim: " + key)
    rows = now.get("nativeOverloads") or [now["native"]]
    overloads = {
        v["target"]: {
            "verdict": (v.get("outcome") or {}).get("verdict"),
            "firstOutstanding": v.get("firstBlocker"),
        }
        for v in rows
    }
    if set(overloads) != set(signatures):
        raise ValueError("different paired overloads: " + key)
    measured = {
        "overloads": overloads,
        "status": checked_finite(host, caller),
        "inputs": len(caller["cases"]),
        "sides": {},
    }
    for side in ("old", "new"):
        for field in ("commit", "callerClassSha256", "orderedSha256"):
            if now["sides"][side].get(field) != old["sides"][side].get(field):
                raise ValueError((key, side, field))
        row = after["sides"][side]
        binding = before["nativeCaller"]["sides"][side]
        for field in ("commit", "callerClassSha256", "orderedClasspathSha256"):
            if row.get(field) != binding.get(field):
                raise ValueError((key, side, field))
        trials = caller["sides"][side].get("trials", [])
        entered = 0
        for trial in trials:
            if trial["qualifiedMethodEntries"] != len(trial.get("receiverAtEntry", [])):
                raise ValueError("physical receiver absent")
            entered += trial["qualifiedMethodEntries"] == 2
        if row.get("raw"):
            path = raw / "callers" / (key + "-receipts") / row["raw"]
            if sha(path) != row["rawSha256"]:
                raise ValueError("changed native receipt")
            (native,) = read(path)
            stated = native.get("stated") or {}
            if (
                native["verdict"] != row["verdict"]
                or native["target"] != after["target"]
                or native["assume"] != after["assume"]
                or native["assert"] != "result"
                or (
                    stated
                    and (
                        stated["gap_mode"] != "strict"
                        or stated["checker"]["engine"] != "native"
                        or any(
                            a.get("id", "").startswith("observed-initializer:") for a in stated["assumptions"]
                        )
                    )
                )
            ):
                raise ValueError("wrong native verdict")
            if (
                native["verdict"] == "verified"
                and (stated.get("vacuity") or {}).get("status") != "non-vacuous"
            ):
                raise ValueError("missing nonvacuity")
        elif row.get("verdict") in ("verified", "violation"):
            raise ValueError("decision lacks native receipt")
        measured["sides"][side] = {
            "jvmInputsReached": entered,
            **{
                k: row.get(k)
                for k in (
                    "verdict",
                    "firstOutstanding",
                    "counterexample",
                    "vacuity",
                    "assumptions",
                    "rawSha256",
                )
            },
        }
    return measured


def measure(group):
    frozen = read(RESULTS / "scope.json")
    pilot = read(BASE / "results.json")["receivers"]["cases"]
    all_methods = frozen["originalOverloads"]
    if (len(all_methods), sum(map(len, all_methods.values()))) != (23, 34):
        raise ValueError("changed opening denominator")
    corpus = {c["id"]: c for c in read(EXTERNAL / "corpus.json")["cases"]}
    selected = {k: v for k, v in all_methods.items() if Path(pilot[k]["receipt"]).parts[-3] == group}
    if not selected:
        raise ValueError("empty group")
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    output = RESULTS / "transfer/cohort" / group
    output.mkdir(parents=True, exist_ok=True)
    data = {
        "job": os.environ["VERIFY_JOB_ID"],
        "source": os.environ["VERIFY_SOURCE_COMMIT"],
        "checkerSha256": sha(checker),
        "cases": {},
    }
    with tempfile.TemporaryDirectory() as d:
        raw = Path(d) / "results"
        raw.mkdir()
        area = prepared_inputs(Path(d) / "preparations", selected)
        common = [
            "--complete",
            area / "modules",
            "--repositories",
            area / "sources/repos.json",
            "--maven-cache",
            ASSETS / "receivers/maven-repository",
            *[v for k in selected for v in ("--case", k)],
        ]
        subprocess.run(
            [
                sys.executable,
                "-B",
                EXTERNAL / "engineering.py",
                "--build",
                "current",
                "--checker",
                checker,
                "--work",
                area / "slices",
                "--output",
                raw / "overloads",
                *common,
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-B",
                EXTERNAL / "check_scenarios.py",
                "--native-caller",
                checker,
                "--preparations",
                area / "slices",
                "--output",
                raw / "callers",
                *common,
            ],
            check=True,
        )
        prior = BASE / "receiver-verified" / group
        data["cases"] = {
            key: score(key, signatures, raw, prior, corpus[key], data["checkerSha256"])
            for key, signatures in selected.items()
        }
        with tarfile.open(output / "receipts.tar.gz", "w:gz") as archive:
            for path in sorted(raw.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(raw))
    data["receiptPackSha256"] = sha(output / "receipts.tar.gz")
    write(output / "measurement.json", data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group")
    measure(parser.parse_args().group)
