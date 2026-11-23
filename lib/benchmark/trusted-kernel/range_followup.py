"""Try the frozen successor on the next family after both public index claims and controls pass."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

from baseline import ROOT, array_induction as adapter
from controls import JDK
from prepare import HERE, digest, request
from recheck_saved import guava_snapshot
from replay import fresh_rust


def result_for(spec, folder, target, binary, work):
    case = spec["id"]
    cmd = [sys.executable, "-B", "examples/tools/build.py", "337", "--array-induction", case, "--compare"]
    compared = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if compared.returncode or "the same result" not in compared.stdout:
        raise ValueError(compared.stdout)
    records = work / "records"
    adapter.run(folder, target, spec, 60, records=records)
    (record,) = (records / case).glob("*/result.json")
    old = json.loads(record.read_text())
    expected = "unresolved" if case == "caller-extra-any-length" else "established"
    unmet = [o for o in old["obligations"] if o["expected"] != o["obtained"]]
    expected_failures = (
        [("caller read follows from the proved frame", "unsat", "sat")] if expected == "unresolved" else []
    )
    observed_failures = [(o["name"], o["expected"], o["obtained"]) for o in unmet]
    if old["status"] != expected or observed_failures != expected_failures:
        raise ValueError((case, old["status"], unmet))
    # Prepare the exact artifacts the original adapter used. The original JDK provides Arrays.
    with zipfile.ZipFile(JDK / "jmods/java.base.jmod") as image:
        arrays = image.read("classes/java/util/Arrays.class")
    if digest(arrays) != old["classes"]["java/util/Arrays"]["sha256"]:
        raise ValueError("JDK class binding")
    data = arrays
    owner = "java/util/Arrays"
    entry = "fill ([IIII)V"
    companion = "rangeCheck (III)V"
    statement = "Every cell in [from,to) has value at return. Every cell outside that range is unchanged."
    home = work / "jvm"
    home.mkdir()
    if "caller" in spec:
        plan, _ = adapter.record_key(folder, target, spec)
        dest = work / "prepare"
        prepared = adapter.route.prepare_revision(plan, spec["revision"], dest, {})
        entries = adapter.runtime._checked(dest, prepared)
        owner = "fill/Range"
        entry = "observe ([I[IIIII)I"
        companion = "fill ([IIII)V"
        candidates = [
            v
            for item in entries
            if item.role in ("original", "dependency")
            and (v := adapter.runtime_jar.read_class(dest / item.path, owner)) is not None
        ]
        (data,) = candidates
        loc = home / (owner + ".class")
        loc.parent.mkdir()
        loc.write_bytes(data)
        statement = "When roots alias and from <= k < to, observe returns value. Otherwise it returns the original other[k]."
    if digest(data) != old["classes"][owner]["sha256"]:
        raise ValueError("actual owner binding")
    artifact = work / "artifact.bin"
    artifact.write_bytes(data)
    req = work / "external.request"
    cert = work / "hints.cert"
    theorem = "range-fill-caller-observation-v1" if "caller" in spec else "range-fill-frame-v1"
    req.write_text(request(theorem, owner, digest(data), entry, companion))
    cert.write_text("certificate 1\nrequest " + digest(req.read_bytes()) + "\nhints range\n")
    rust = fresh_rust(binary, req, cert, artifact)
    if rust["exit"] != 3 or "external theorem" not in rust["stdout"]:
        raise ValueError(rust)
    subprocess.run([JDK / "bin/javac", "-g:none", "-d", home, HERE / "java/ObserveFill.java"], check=True)
    output = subprocess.check_output(
        [
            JDK / "bin/java",
            "-Xverify:all",
            "-cp",
            home,
            "ObserveFill",
            "caller" if "caller" in spec else "callee",
        ],
        text=True,
    ).splitlines()
    if output[0] != f"owner {digest(data)} arrays {digest(arrays)}":
        raise ValueError(output)
    counts = re.fullmatch(
        r"cases (\d+) shared (\d+) distinct (\d+) observed-mismatch (\d+) frame-mismatch (\d+)", output[-1]
    )
    if not counts:
        raise ValueError(output)
    total, shared, distinct, mismatch, frame = map(int, counts.groups())
    if (
        not total
        or shared + distinct != total
        or (mismatch > 0) != (expected == "unresolved")
        or (frame > 0) != (expected == "unresolved")
    ):
        raise ValueError(output)
    return {
        "control": case,
        "requestedClaim": req.read_text(),
        "requestSha256": digest(req.read_bytes()),
        "statement": statement,
        "domain": "Allocated non-null roots, valid half-open range in a and valid k in other for the caller. Shared or distinct roots; independently legal lengths when distinct.",
        "classSha256": {k: v["sha256"] for k, v in old["classes"].items()},
        "rulesSha256": old["rules"]["sha256"],
        "historical": {
            "expected": expected,
            "actual": old["status"],
            "reason": unmet or old["obligations"],
            "obligations": old["obligations"],
            "comparison": compared.stdout.splitlines(),
            "compareExit": compared.returncode,
        },
        "independent": {"expected": "unsupported", "actual": "unsupported", "reason": rust["stdout"]},
        "physical": {
            "checks": total,
            "shared": shared,
            "distinct": distinct,
            "observationalMismatches": mismatch,
            "frameMismatches": frame,
            "stdout": output,
        },
        "firstCapability": (
            "rangeCheck and a changing prefix with an unchanged outside frame"
            if "caller" not in spec
            else "consume the changed-root frame at other[k] for shared and distinct roots"
        ),
    }


def main():
    (folder,) = (ROOT / "examples").glob("337-*")
    target = json.loads((folder / "target.json").read_text())
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        binary = guava_snapshot(tmp / "guava")
        for case in ["fill-any-length", "caller-any-length", "caller-extra-any-length"]:
            (spec,) = [s for s in target["arrayContracts"] if s["id"] == case]
            w = tmp / case
            w.mkdir()
            rows.append(result_for(spec, folder, target, binary, w))
    (HERE / "evidence/range-fill.json").write_text(
        json.dumps({"schema": "trusted-range-transfer/v1", "cases": rows}, indent=2) + "\n"
    )
    print(
        [
            (
                r["control"],
                r["historical"]["actual"],
                r["independent"]["actual"],
                r["physical"]["observationalMismatches"],
            )
            for r in rows
        ]
    )


if __name__ == "__main__":
    main()
