"""Run the historical recorder and its cold and retained-record comparisons on the three pinned artifacts."""
import argparse
from contextlib import redirect_stdout
import difflib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from controls import RELEASE, SOURCE_SHA
from historical_frame_control import adapter
from prepare import GUAVA, HERE, digest

ROOT = HERE.parents[2]
EXAMPLE = ROOT / "examples/336-guava-first-array-match"
ORIGINAL = "guava/src/" + GUAVA + "Ints.java"


def load(path):
    return json.loads(path.read_bytes())


def subject(work, row):
    """Use the public preparation recipe for the release and for each already registered benchmark variant."""
    folder = work / row["control"] / EXAMPLE.name
    shutil.copytree(EXAMPLE, folder, ignore=shutil.ignore_patterns("receipts", "records"))
    target = load(folder / "target.json")
    spec, = target["arrayContracts"]
    if row["control"] == "Ints":
        return folder, target, spec

    source_jar = RELEASE / "sources/guava-33.4.8-jre-sources.jar"
    if digest(source_jar.read_bytes()) != SOURCE_SHA:
        raise ValueError("Guava source digest differs")
    with zipfile.ZipFile(source_jar) as jar:
        text = jar.read(GUAVA + "Ints.java").decode()
    start = text.index("  public static int indexOf(int[] array, int target)")
    end = text.index("\n  }", text.index("  private static int indexOf(", start)) + 4
    variant = text[:start] + row["source"]["changedMethods"] + text[end:]
    if digest(variant.encode()) != row["source"]["reboundSourceSha256"]:
        raise ValueError("variant differs from the frozen source control")
    patch = "".join(difflib.unified_diff(text.splitlines(True), variant.splitlines(True), "a/" + ORIGINAL, "b/" + ORIGINAL))
    path = folder / "controls" / (row["control"] + ".patch")
    path.write_text(patch)
    target["history"]["repository"] = "local-git:guava"
    target["history"]["revisions"]["mutant"]["mutant"] = {
        "base": "release", "patch": path.relative_to(folder).as_posix(), "sha256": digest(patch.encode()),
        "description": "Pinned " + row["control"] + " Java benchmark control",
    }
    task, = [t for t in target["tasks"] if t["id"] == spec["bindingTask"]]
    task["id"] = "bind-original-control"
    task["revision"] = "mutant"
    task["requires"] = []
    spec.update(bindingTask=task["id"], revision="mutant")
    (folder / "target.json").write_text(json.dumps(target))
    return folder, target, spec


def compared(folder, target, spec):
    log = StringIO()
    with redirect_stdout(log):
        repeated = adapter.compare(folder, target, spec, 60)
    return {"repeated": repeated, "messages": [line for line in log.getvalue().splitlines()
                                               if "against records/" in line or "no stored record" in line]}


def trial(folder, target, spec, row):
    cold = compared(folder, target, spec)
    if cold["repeated"] or not any("no stored record" in m for m in cold["messages"]):
        raise ValueError(("cold comparison", cold))
    established = adapter.run(folder, target, spec, 60)
    record, = (folder / "records/array-induction" / spec["id"]).glob("*/result.json")
    genuine = load(record)
    expected = row["unchangedProducer"]
    if (genuine["status"] != expected["actual"] or established != (expected["actual"] == "established")
            or genuine["classes"][GUAVA + "Ints"]["sha256"] != row["classSha256"]
            or genuine["obligations"] != expected["obligations"]
            or genuine["certificateSha256"] != expected["formulaSha256"]
            or digest((record.parent / "obligations.smt2").read_bytes()) != expected["formulaSha256"]):
        raise ValueError("ordinary record differs from pinned control " + row["control"])
    warm = compared(folder, target, spec)
    if not warm["repeated"] or not any("the same result" in m for m in warm["messages"]):
        raise ValueError(("retained genuine record", warm))
    return {"key": "336/historical/" + row["control"], "originalRequestSha256": row["requestSha256"],
            "record": genuine, "recordSha256": digest(record.read_bytes()), "withoutStoredRecord": cold,
            "withPristineRecord": warm}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    dest = parser.parse_args().output
    original = load(HERE / "evidence/transfer/results.json")
    expected_rules = load(HERE / "evidence/baseline/336.json")["freshResult"]["rules"]["files"]
    if any(digest((ROOT / rel).read_bytes()) != sha for rel, sha in expected_rules.items()):
        raise ValueError("historical adapter or rule source differs")
    rows = {r["control"]: r for r in original["cases"]}
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        store = work / "sources"
        store.mkdir()
        mirror = Path.home() / ".cache/in-the-loop/git-mirrors/guava.git"
        subprocess.run(["git", "clone", "--quiet", "--mirror", "--shared", mirror, store / "guava"], check=True)
        os.environ["TARGETS_LOCAL_GIT_ROOT"] = str(store)
        trials = [trial(*subject(work, rows[name]), rows[name]) for name in ("Ints", "frame", "miss")]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"schema": "historical-adapter-comparison/v1", "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
                               "cases": trials}, indent=2) + "\n")
    print([(r["key"], r["record"]["status"], r["withoutStoredRecord"]["repeated"],
            r["withPristineRecord"]["repeated"]) for r in trials])


if __name__ == "__main__":
    main()
