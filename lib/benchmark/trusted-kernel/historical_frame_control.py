"""Measure a single faulty induction premise on the frozen heap-writing Guava control."""

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

from certificate import issue
from controls import JDK, cells_arg
from decision_evidence import require
from frame_witness import EV, FRAME, guava_record, read
from prepare import HERE, digest
from recheck_saved import guava_snapshot
from replay import fresh_rust

sys.path.insert(0, str(HERE.parents[2] / "examples/tools"))
from targets import array_induction as adapter


def copied_rule(work):
    """Introduce one wrong conclusion in a private copy of the recorded historical rule."""
    core = adapter.core
    rules = read(EV / "baseline/336.json")["freshResult"]["rules"]["files"]
    for path in core.RULE_FILES:
        require(digest(path.read_bytes()) == rules["lib/python/" + path.name], f"historical {path.name} differs")
        shutil.copyfile(path, work / path.name)
    path = work / "jvm_array_induction.py"
    genuine = path.read_text()
    frame = 'self.vc("preserve the input heap", end.path, term("=", end.heap, "initial"))'
    conclusion = 'term("=", end.heap, "initial")'
    fault = frame.replace(conclusion, '"true" if end.heap == "(store heap cursor #x00000000)" else ' + conclusion)
    require(genuine.count(frame) == 1, "historical frame rule changed")
    path.write_text(genuine.replace(frame, fault))
    spec = importlib.util.spec_from_file_location("guava_frame_control_rule", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def result(rule, artifact, work):
    proof = rule.prove(JDK / "bin/javap", artifact, "indexOf", "([II)I", "first-index", work, 60)
    # These are the proof fields consumed by the example adapter's comparison. Deployment and inputs are fixed.
    return {
        "status": "established" if proof.passed else "unresolved",
        "obligations": proof.obligations,
        "certificateSha256": digest(proof.smt.encode()),
        "disassemblySha256": digest(proof.disassembly.encode()),
        "bytecode": proof.trace,
        "solver": proof.solver,
        "heapCellBits": proof.cell_bits,
        "indexBits": proof.index_bits,
    }


def run(work):
    frozen = guava_record()
    bundle = FRAME.parent
    artifact = work / "Ints.class"
    shutil.copyfile(FRAME, artifact)
    require(digest(artifact.read_bytes()) == frozen["classSha256"], "heap-writing class differs")
    base = result(adapter.core, artifact, work)
    reference = frozen["unchangedProducer"]
    require(
        base["status"] == reference["actual"] == "unresolved"
        and base["obligations"] == reference["obligations"]
        and base["certificateSha256"] == reference["formulaSha256"]
        and base["solver"] == reference["solver"], "genuine producer differs",
    )
    original_smt = (work / "obligations.smt2").read_text()
    faulty_rule = copied_rule(work)
    faulty = result(faulty_rule, artifact, work)
    faulty_smt = (work / "obligations.smt2").read_text()
    require(
        faulty["status"] == "established" and faulty["certificateSha256"] == digest(faulty_smt.encode())
        and faulty_smt.count("(not true)") == original_smt.count("(not true)") + 1,
        "the fault did not produce a different checked frame condition",
    )
    before, after = original_smt.splitlines(), faulty_smt.splitlines()
    changes = [(a, b) for a, b in zip(before, after, strict=True) if a != b]
    require(len(changes) == 1, "the control must change exactly one solver assertion")
    old, new = changes[0]
    require(old.replace("(= (store heap cursor #x00000000) initial)", "true") == new, "another premise changed")
    answers = zip(base["obligations"], faulty["obligations"], strict=True)
    changed = [(i, g, f) for i, (g, f) in enumerate(answers) if g != f]
    require(len(changed) == 1, "other obligation answers changed")
    index, genuine_obligation, faulty_obligation = changed[0]
    require(
        genuine_obligation == {"name": "preserve the input heap", "expected": "unsat", "obtained": "sat"}
        and faulty_obligation == {**genuine_obligation, "obtained": "unsat"}, "unexpected frame answer",
    )
    differences, machine = adapter.differences(faulty, base)
    require(differences == ["status", "obligations", "certificateSha256"] and not machine, "honest comparison")
    require(adapter.differences(result(faulty_rule, artifact, work), faulty) == ([], []), "faulty replay changed")
    checker = guava_snapshot(work / "independent")
    request = bundle / "external.request"
    require(digest(request.read_bytes()) == frozen["requestSha256"], "request changed")
    # With the faulty result established, issue every semantic obligation for the same bound request.
    # The fresh consumer reconstructs the obligations from the class bytes in a separate process.
    witness = frozen["originalJvm"]
    certificate = work / "evidence.cert"
    certificate.write_text(issue(request, artifact, (str(witness["target"]), cells_arg(witness["input"]))))
    require(digest(certificate.read_bytes()) == frozen["certificateSha256"], "fresh semantic certificate differs")
    checked = fresh_rust(checker, request, certificate, artifact, [bundle / "support.bin"])
    require(
        checked["exit"] == 2 and checked["stdout"] == frozen["outcome"] and "frame changed" in checked["stdout"],
        "independent replay lost the public-entry frame witness",
    )
    return {
        "schema": "historical-guava-frame-control/v1",
        "control": "heap-writing Guava indexOf",
        "classSha256": frozen["classSha256"],
        "requestSha256": frozen["requestSha256"],
        "producerSource": {
            "genuine": adapter.core.implementation()["sha256"], "faulty": faulty_rule.implementation()["sha256"],
        },
        "solver": base["solver"],
        "zeroBasedQuery": index,
        "genuine": {"disposition": base["status"], "formulaSha256": base["certificateSha256"], "frame": genuine_obligation},
        "faulty": {"disposition": faulty["status"], "formulaSha256": faulty["certificateSha256"], "frame": faulty_obligation},
        "replay": {
            "comparedBy": "examples/tools/targets/array_induction.py:differences",
            "againstGenuineProof": differences, "againstRegeneratedFaultyProof": [],
        },
        "independent": {
            "checkerSha256": digest(checker.read_bytes()), "certificateSha256": frozen["certificateSha256"],
            "disposition": "refuted", "witness": checked["stdout"], "originalJvm": frozen["originalJvm"],
        },
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", type=Path)
    mode.add_argument("--check", type=Path)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        outcome = run(Path(directory))
    if args.record:
        args.record.write_text(json.dumps(outcome, indent=2) + "\n")
    else:
        require(read(args.check) == outcome, "historical fault control differs")
    print("Historical control reproduced: honest frame SAT, faulted frame UNSAT, independent public witness refuted")
