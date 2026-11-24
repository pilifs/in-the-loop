"""Audit the historical Guava query inventories against a separately frozen Java request."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

from certificate import issue
from challenge import isolation
from controls import JDK, RELEASE, cells_arg
from decision_evidence import require
from frame_witness import EV, Z3, read
from historical_frame_control import adapter, result
from prepare import GUAVA, HERE, digest
from recheck_saved import guava_snapshot
from replay import fresh_rust


def confirm_jvm(artifact, classes, cells, target, value, after):
    owner = classes / (GUAVA + "Ints.class")
    owner.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact, owner)
    command = [JDK / "bin/java", "-Xverify:all", "-cp", os.pathsep.join(map(str, (classes, RELEASE / "lib/*"))),
               "Observe", "Ints", str(target), cells_arg(cells)]
    lines = subprocess.run(command, text=True, capture_output=True, check=True, timeout=20).stdout.splitlines()
    require(lines == ["entered " + digest(artifact.read_bytes()), f"return {value}", f"heap {after}"],
            "fresh JVM observation differs from the frozen request")
    return {"cells": cells, "target": target, "returned": value, "after": after, "loaded": lines[0].split()[1]}


def split_queries(smt, count):
    parts = re.split(r"(?m)^; VC (\d+)\n", smt)
    require([int(v) for v in parts[1::2]] == list(range(count)), "nonconsecutive historical solver inventory")
    return parts[0], parts[2::2]


def z3_answers(z3, script):
    proc = subprocess.run([z3, "-in", "-smt2"], input=script, text=True, capture_output=True, check=True, timeout=60)
    return proc.stdout.splitlines()


def check_partial_inventory(z3, original, smt):
    prelude, blocks = split_queries(smt, len(original["obligations"]))
    kept = [i for i in range(len(blocks)) if i != 4]
    partial = prelude + "".join(blocks[i] for i in kept)
    answers = z3_answers(z3, partial)
    queries = [{**original["obligations"][i], "obtained": answer} for i, answer in zip(kept, answers, strict=True)]
    # Read the historical success predicate on this diagnostic inventory. No example record is issued from it.
    predicate = adapter.core.Proof.passed.fget(SimpleNamespace(obligations=queries))
    return {"status": "established" if predicate else "unresolved", "obligations": queries,
            "certificateSha256": digest(partial.encode())}, digest(blocks[4].encode())


def audit_case(row, binary, classes, work, z3):
    name = row["control"]
    bundle = EV / "transfer" / name
    request, artifact, support = (bundle / item for item in ("external.request", "artifact.bin", "support.bin"))
    require(digest(request.read_bytes()) == row["requestSha256"] and
            digest(artifact.read_bytes()) == row["classSha256"], f"{name} fixture changed")
    work.mkdir()
    deployed = work / "Ints.class"
    shutil.copyfile(artifact, deployed)
    proof = result(adapter.core, deployed, work)
    old = row["unchangedProducer"]
    require((proof["status"], proof["obligations"], proof["certificateSha256"], proof["solver"]) ==
            (old["actual"], old["obligations"], old["formulaSha256"], old["solver"]), f"{name} pristine record")
    smt = (work / "obligations.smt2").read_text()
    answers = z3_answers(z3, smt)
    require(answers == [q["obtained"] for q in proof["obligations"]], f"{name} independent Z3 replay")
    primary = row["originalJvm"]
    cert = work / "hints.cert"
    cert.write_text(issue(request, artifact, (str(primary["target"]), cells_arg(primary["input"]))))
    require(digest(cert.read_bytes()) == row["certificateSha256"], f"{name} fresh certificate differs")
    checked = fresh_rust(binary, request, cert, artifact, [support])
    require((checked["exit"], checked["stdout"]) == (row["exit"], row["outcome"]), f"{name} semantic result")
    calls = {"frame": [([7], 7, 0, [0]), ([0], 0, 0, [0])], "miss": [([], 7, 0, [])],
             "Ints": [([7, 7], 7, 0, [7, 7]), ([], 7, -1, [])]}[name]
    out = {"key": f"336/historical/{name}", "request": request.read_text(), "requestSha256": row["requestSha256"],
           "classSha256": row["classSha256"], "supportSha256": digest(support.read_bytes()),
           "genuine": {"producer": proof["status"], "solver": proof["solver"], "answers": answers,
                       "obligations": proof["obligations"], "smtSha256": digest(smt.encode())},
           "independent": {"result": "established" if checked["exit"] == 0 else "counterexample",
                           "details": checked["stdout"], "hintSha256": digest(cert.read_bytes())},
           "jvm": [confirm_jvm(artifact, classes, *call) for call in calls]}
    if name == "Ints":
        exits = [line for line in cert.read_text().splitlines() if line.endswith(">exit result")]
        miss_exit = "indexOf([IIII)I@27>exit result"
        require(miss_exit in exits, "original helper miss exit moved")
        incomplete = work / "absent-exit.cert"
        incomplete.write_text("\n".join(line for line in cert.read_text().splitlines() if line != miss_exit) + "\n")
        refused = fresh_rust(binary, request, incomplete, artifact, [support])
        require((refused["exit"], refused["stdout"]) == (2, "rejected missing obligation " + miss_exit),
                "checker did not derive the missing exit from the release class")
        out["missingHintControl"] = {"required": miss_exit, "output": refused["stdout"],
                                     "hintSha256": digest(incomplete.read_bytes())}
    if name == "frame":
        prior = HERE / "historical-frame-control.json"
        old_control = read(prior)
        require(old_control["genuine"]["formulaSha256"] == digest(smt.encode()) and
                old_control["independent"]["witness"] == checked["stdout"], "prior frame control binding")
        out["historicalFault"] = {"provenance": "managed historical producer experiment",
                                  "receipt": prior.name, "sha256": digest(prior.read_bytes()),
                                  "changedQuery": old_control["zeroBasedQuery"], "producer": old_control["faulty"],
                                  "comparison": old_control["replay"]}
    if name == "miss":
        # The omitted query is a negative input to the inventory audit. The complete genuine proof stays available.
        missing = [i for i, q in enumerate(proof["obligations"]) if q["expected"] != q["obtained"]]
        require(missing == [4] and proof["obligations"][4]["name"] == "return the earliest match or minus one",
                "wrong miss-exit query selected")
        inventory, missing_digest = check_partial_inventory(z3, proof, smt)
        again = work / "retry"
        again.mkdir()
        rerun = result(adapter.core, deployed, again)
        repeated_inventory, repeated_digest = check_partial_inventory(z3, rerun, (again / "obligations.smt2").read_text())
        require(inventory["status"] == "established" and missing_digest == repeated_digest, "query ablation differed")
        pristine = {k: proof[k] for k in inventory}
        drift, _ = adapter.differences(inventory, pristine)
        repeated, _ = adapter.differences(repeated_inventory, inventory)
        require(drift == ["status", "obligations", "certificateSha256"] and not repeated,
                "comparison did not distinguish inputs")
        out["omittedExitControl"] = {"provenance": "query-inventory negative control on fresh pristine SMT",
            "missingOrdinal": 4, "missingQuerySha256": missing_digest,
            "remainingSolverAnswers": [v["obtained"] for v in inventory["obligations"]],
            "historicalPredicateOnSubset": inventory["status"],
            "remainingSmtSha256": inventory["certificateSha256"], "comparisonToPristine": drift,
            "comparisonToSameInventory": repeated, "firstSemanticFailure": checked["stdout"]}
    return out


def audit():
    rows = read(EV / "transfer/results.json")["cases"]
    historical = read(EV / "baseline/336.json")["freshResult"]["rules"]["files"]
    root = HERE.parents[2]
    require(all(digest((root / p).read_bytes()) == expected for p, expected in historical.items()),
            "historical adapter or rule source differs")
    z3 = shutil.which("z3")
    require(z3 and digest(Path(z3).read_bytes()) == Z3, "pinned Z3 executable differs")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        binary = guava_snapshot(work / "snapshot")
        classes = work / "observer"
        classes.mkdir()
        subprocess.run([JDK / "bin/javac", "--release", "21", "-d", classes, HERE / "java/Observe.java"], check=True)
        results = [audit_case(next(r for r in rows if r["control"] == name), binary, classes, work / name, z3)
                   for name in ("Ints", "frame", "miss")]
        return {"schema": "historical-induction-audit/v1", "rules": historical,
                "checkerSha256": digest(binary.read_bytes()), "isolation": isolation(binary), "cases": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    path = parser.parse_args().output
    evidence = audit()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    print([(r["key"], r["genuine"]["producer"], r["independent"]["result"]) for r in evidence["cases"]])
