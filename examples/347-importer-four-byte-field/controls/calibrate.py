"""Run the four dependency configurations with the original application and a split supplementary character."""

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

FOLDER = Path(__file__).resolve().parents[1]
BASE = next(FOLDER.parent.glob("345-*"))
DECODER = next(FOLDER.parent.glob("341-*"))
sys.path.insert(0, str(FOLDER.parent / "tools"))
from targets import finite_check, native_selectors, route, runtime, runtime_jdk, workflow


def main():
    spec = importlib.util.spec_from_file_location("importer_matrix", BASE / "controls/calibrate.py")
    matrix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matrix)
    expected = {
        "parent-parent": [16, 16, 24],
        "fix-parent": [0, 16, 16],
        "parent-fix": [16, 0, 16],
        "fix-fix": [0, 0, 0],
    }
    with tempfile.TemporaryDirectory(prefix="unicode-importer-matrix-") as directory:
        report = matrix.measure(Path(directory), FOLDER, expected, inputs=32, positive=8, witness=14)
    original = json.loads((BASE / "records/matrix/matrix.json").read_text())
    if (
        report["clientClasses"] != original["clientClasses"]
        or report["compileClasspath"] != original["compileClasspath"]
        or any(
            c["runtimeClasspath"] != original["configurations"][key]["runtimeClasspath"]
            for key, c in report["configurations"].items()
        )
    ):
        raise ValueError("the application or library identities differ from the original importer")
    example = json.loads((DECODER / "example.json").read_text())
    target = json.loads((DECODER / "target.json").read_text())
    plan = route.resolve(DECODER, example, target, "units-stream")
    evidence = next(r for r in finite_check.evidence(DECODER, plan) if r["status"] == "established")
    path = DECODER / evidence["receipt"]
    certificate = json.loads(path.read_text())
    finite_check.validate_record(plan, certificate)
    if (
        certificate["jdkRelease"] != report["jdk"]["release"]
        or len(certificate["sides"]["stream"]["rows"]) != 5578
    ):
        raise ValueError("the decoder calibration is from a different image or input domain")
    observations = certificate["sides"]["stream"]["rows"][4:12]
    if not all(
        row["value"] == 4 + i and row["admitted"] and row["satisfies"] for i, row in enumerate(observations)
    ):
        raise ValueError("the standalone decoder evidence omits a partition of the scalar")
    sample = report["configurations"]["fix-fix"]["example"]
    if (
        sample["direct"]["page"] != [[2, ["abc", "😀"]]]
        or not sample["input"]["oneByte"]
        or sample["input"]["doc"].encode("utf-8")[4:8] != bytes.fromhex("f09f9880")
    ):
        raise ValueError("the observation does not include the split four-byte field")
    transfer = {
        "schema": "importer-charset-transfer/v1",
        "jdk": report["jdk"],
        "originalClientClasses": original["clientClasses"],
        "upstreamMatrix": str((BASE / "records/matrix/matrix.json").relative_to(FOLDER.parent.parent)),
        "decoder": {
            "task": plan.task,
            "sourceClaim": plan.claim["key"],
            "inputsKey": workflow.inputs_key(plan),
            "finiteReceipt": str(path.relative_to(FOLDER.parent.parent)),
            "receiptSha256": runtime.sha256(path),
            "standaloneSelectors": list(range(4, 12)),
        },
        "field": {
            "utf8": "f09f9880",
            "utf16": "d83dde00",
            "offsetInDocument": 4,
            "oneByteReadCuts": [5, 6, 7],
        },
        "downstream": {
            "case": 14,
            "directInputsPerCell": 32,
            "correctNumberedRow": sample["direct"]["page"],
            "scope": "The page, bytes and count are checked again on the real CSV, IO and decoder call chain.",
        },
    }
    home = Path(runtime_jdk.home("21"))
    with zipfile.ZipFile(home / "jmods/java.base.jmod") as image:
        transfer["decoder"]["imageClasses"] = {
            name: hashlib.sha256(image.read("classes/" + name + ".class")).hexdigest()
            for name in ("java/io/InputStreamReader", "sun/nio/cs/StreamDecoder", "sun/nio/cs/UTF_8$Decoder")
        }
    proofs = []
    for subject in ("stream", "bom"):
        for observation in ("units", "eof"):
            task = f"four-byte-{observation}-{subject}"
            producer = route.resolve(DECODER, example, target, task)
            eligible = [p for p in native_selectors.evidence(DECODER, producer) if p["status"] == "established"]
            if not eligible:
                continue
            selected = (DECODER / eligible[-1]["record"]).resolve()
            doc = json.loads(selected.read_text())
            if doc["admitted"] != list(range(4, 12)) or doc["JDK"] != report["jdk"]["release"]:
                raise ValueError("the native decoder scope or JDK differs")
            proofs.append({"task": task, "record": str(selected.relative_to(FOLDER.parent.parent)),
                           "sha256": runtime.sha256(selected), "checker": doc["checker"]})
    transfer["decoder"]["nativeProofs"] = proofs
    (FOLDER / "records/decoder-transfer.json").write_text(
        json.dumps(transfer, indent=2, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    main()
