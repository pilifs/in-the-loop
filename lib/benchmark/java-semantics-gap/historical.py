"""Rerun the frozen differential through the normal benchmark, including its original-JVM replays."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run as benchmark

ROOT = benchmark.REPO
FROZEN = HERE.parent / "results.json"
FROZEN_SHA = "14c25280da82eaba7116753d704c33527aedf0e2008ff0eb664a805068d1de75"
GROUPS = ("listOfArray", "listSearch", "other-leads", "native-controls")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def freeze():
    if digest(FROZEN) != FROZEN_SHA:
        raise ValueError("the historical corpus must be the 7 November receipt")
    historical = json.loads(FROZEN.read_bytes())
    runs = {(r["case"], r["engine"]): r for r in historical["runs"] if r["mode"] == "strict"
            and (r["engine"] == "native" or (r["engine"] == "jbmc" and r["staging"] == "staged"))}
    rows = {}
    for case in historical["cases"]:
        cid = case["id"]
        success = tuple(runs[cid, engine]["class"] == "correct" for engine in ("native", "jbmc"))
        rows[cid] = {"historical": {(True, True): "both", (True, False): "native-only",
                     (False, True): "jbmc-only", (False, False): "neither"}[success], "expected": case["expected"]}
    if Counter(r["historical"] for r in rows.values()) != {"both": 133, "native-only": 24, "jbmc-only": 13, "neither": 17}:
        raise ValueError("the frozen differential changed")
    return rows


def selected(rows, group):
    if group in ("listOfArray", "listSearch"):
        return [f"conformance/{group}/{i}" for i in (1, 2)]
    if group == "native-controls":
        return [k for k, v in rows.items() if v["historical"] == "native-only"]
    listed = set(selected(rows, "listOfArray") + selected(rows, "listSearch"))
    return [k for k, v in rows.items() if v["historical"] == "jbmc-only" and k not in listed]


def measure(phase, group, output_root=None):
    rows = freeze()
    ids = selected(rows, group)
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    jbmc = Path(shutil.which("jbmc")).resolve()
    java = Path(shutil.which("java")).resolve()
    models = ROOT / "lib/models/classes"
    with tempfile.TemporaryDirectory(prefix="semantics-history-") as build:
        options = argparse.Namespace(groups="1,2,3,4", cases=None, selection=f"java-semantics-gap/{group}",
                    engines="native,jbmc", modes="strict", jbmc_staging="staged", timeout=120,
                    search=200000, build=build, jvmcontract=str(checker), jbmc=str(jbmc), quiet=False)
        result = benchmark.run(options, case_ids=ids)
    if ([(c["id"], c["expected"]) for c in result["cases"]] != [(cid,rows[cid]["expected"]) for cid in ids]
            or len(result["runs"]) != 2 * len(ids)):
        raise ValueError("incomplete or mismatched original cases")
    for record in result["runs"]:
        if record["verdict"] == "none":
            raise ValueError(f"missing checker response for {record['case']}: {record.get('problem')}")
        if record["class"] == "correct" and record["verdict"] == "violation" and not record.get("witnessOnTheJvm"):
            raise ValueError("a refutation lacks an original-JVM replay")
    result["historical"] = {cid: rows[cid] for cid in ids}
    result["frozenResultSha256"] = FROZEN_SHA
    result["binaries"] = {p.name: digest(p) for p in (checker, jbmc, java, java.parents[1]/"lib/modules",
                                                      Path("/usr/lib/core-models.jar"))}
    result["repositoryModels"] = {p.relative_to(models).as_posix(): digest(p) for p in sorted(models.rglob("*.class"))}
    out = (output_root or ROOT / "verification/java-semantics-gap") / phase
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{group}.json").write_text(json.dumps(result, indent=1) + "\n")
    print(group, Counter((r["engine"], r["class"]) for r in result["runs"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("opening", "final", "qualified", "direct-arrays", "heap-and-gson"))
    parser.add_argument("group", choices=GROUPS)
    args = parser.parse_args()
    measure(args.phase, args.group)
