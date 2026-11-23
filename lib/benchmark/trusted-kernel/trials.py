"""Qualify a frozen Rust consumer on the original Java bytes and independently rebound controls."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

import controls
from challenge import isolation, issuer_frame_case
from prepare import HERE, digest
from replay import build_kernel, fresh_rust, measured, summarize

sys.path.insert(0, str(HERE.parents[1] / "python"))
import jvm_array_induction as original


def old_rule(case, artifact):
    """Run the unchanged historical semantic rule on the rebound class without treating it as a release artifact."""
    name = controls.owner_of(case)
    desc = "([II)I" if name == "Ints" else "([JJ)I"
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        f = work / (name + ".class")
        shutil.copy2(artifact, f)
        try:
            proof = original.prove(controls.JDK / "bin/javap", f, "indexOf", desc, "first-index", work, 60)
        except (ValueError, KeyError) as exc:
            return {"actual": "unsupported", "reason": str(exc)}
        return {
            "actual": "established" if proof.passed else "unresolved",
            "obligations": proof.obligations,
            "formulaSha256": digest(proof.smt.encode()),
            "solver": proof.solver,
            "bytecode": proof.trace,
        }


def case_row(binary, case, phase, out, driver):
    bundle = out / case
    req, artifact, support, source = controls.prepare(case, bundle)
    cert = bundle / "evidence.cert"
    target, values, _, _ = controls.INPUTS[case]
    gen = measured(
        [
            sys.executable,
            "-B",
            HERE / "certificate.py",
            req,
            artifact,
            cert,
            str(target),
            controls.cells_arg(values),
        ],
        HERE,
    )
    if gen["exit"]:
        raise ValueError(gen)
    witness = controls.observe(case, artifact, driver)
    old = old_rule(case, artifact)
    expected = (
        "unsupported"
        if phase == "freeze" and case == "Longs"
        else "accepted" if case in ("Ints", "Longs", "layout", "same-store") else "rejected"
    )
    checked = summarize([fresh_rust(binary, req, cert, artifact, support) for _ in range(3)])
    actual = checked["outcome"].split()[0]
    if actual != expected or checked["exit"] != dict(accepted=0, rejected=2, unsupported=3)[expected]:
        raise ValueError((case, expected, checked))
    if expected == "rejected" and "checked witness" not in checked["outcome"]:
        raise ValueError(f"{case} was rejected without a replayed semantic distinction")
    if case == "frame":
        failed = [o for o in old.get("obligations", []) if o["expected"] != o["obtained"]]
        if not failed or any(
            o["name"] != "preserve the input heap" or o["obtained"] != "sat" for o in failed
        ):
            raise ValueError(("unexpected honest frame obligations", old))
    for p in support:
        shutil.copyfile(p, bundle / "support.bin")
    return {
        "route": "Rust",
        "control": case,
        "expected": expected,
        "actual": actual,
        "classSha256": digest(artifact.read_bytes()),
        "requestSha256": digest(req.read_bytes()),
        "requestedClaim": req.read_text(),
        "checkerVersion": digest(binary.read_bytes()),
        "certificateSha256": digest(cert.read_bytes()),
        "sizes": {p.name: p.stat().st_size for p in bundle.iterdir()},
        "generation": gen,
        "originalJvm": witness,
        "unchangedProducer": old,
        "source": source,
        **checked,
    }


def substitution_rows(binary, out):
    src = out / "Ints"
    original = (src / "external.request").read_text()
    good = (src / "evidence.cert").read_text()
    keys = good.splitlines()
    frame = next(k for k in keys if k.startswith("indexOf([IIII)I") and k.endswith(">exit frame"))
    other = next(
        k for k in keys if k != frame and k.startswith("indexOf([IIII)I") and k.endswith(">exit frame")
    )
    wrong = original.replace("theorem least-index-frame-total-v1", "theorem return-only")
    missing = original.replace("companion indexOf", "companion absent")
    descriptor = original.replace("([IIII)I", "([III)I")
    altered = good.replace("hints first-prefix remaining", "hints none none")
    samples = [
        ("swap-class", original, good, out / "Longs/artifact.bin", "external class digest"),
        (
            "swap-certificate",
            original,
            (out / "Longs/evidence.cert").read_text(),
            src / "artifact.bin",
            "does not bind",
        ),
        (
            "remove-one-return-frame",
            original,
            "\n".join(k for k in keys if k != frame) + "\n",
            src / "artifact.bin",
            "missing obligation",
        ),
        (
            "substitute-other-return-frame",
            original,
            good.replace(frame, other),
            src / "artifact.bin",
            "duplicate obligation",
        ),
        (
            "weaken-external-theorem",
            wrong,
            good.replace(digest(original.encode()), digest(wrong.encode())),
            src / "artifact.bin",
            "external theorem",
        ),
        ("weaken-evidence", original, altered, src / "artifact.bin", "missing prefix invariant"),
        (
            "replace-helper-name",
            missing,
            good.replace(digest(original.encode()), digest(missing.encode())),
            src / "artifact.bin",
            "missing method",
        ),
        (
            "replace-helper-descriptor",
            descriptor,
            good.replace(digest(original.encode()), digest(descriptor.encode())),
            src / "artifact.bin",
            "element descriptor",
        ),
    ]
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        req = temp / "external.request"
        cert = temp / "evidence.cert"
        for label, text, evidence, artifact, reason in samples:
            req.write_text(text)
            cert.write_text(evidence)
            check = fresh_rust(binary, req, cert, artifact, [src / "support.bin"])
            if check["exit"] not in (2, 3) or reason not in check["stdout"]:
                raise ValueError((label, check))
            rows.append(
                {
                    "route": "Rust",
                    "classSha256": digest(artifact.read_bytes()),
                    "requestedClaim": text,
                    "requestSha256": digest(text.encode()),
                    "control": label,
                    "checkerVersion": digest(binary.read_bytes()),
                    "expected": (
                        "unsupported"
                        if label in ("weaken-external-theorem", "replace-helper-descriptor")
                        else "rejected"
                    ),
                    "actual": check["stdout"].split()[0],
                    "certificate": evidence,
                    **check,
                }
            )
    return rows


def run(phase, out):
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        binary, build = build_kernel(tmp)
        driver = tmp / "driver"
        driver.mkdir()
        java_build = measured(
            [controls.JDK / "bin/javac", "-g:none", "-d", driver, HERE / "java/Observe.java"], tmp
        )
        if java_build["exit"]:
            raise ValueError(java_build)
        order = ["Ints", "last", "start", "miss", "frame", "stuck", "Longs"]
        if phase == "transfer":
            order += ["narrow", "layout", "same-store"]
        rows = [case_row(binary, case, phase, out, driver) for case in order]
        altered = substitution_rows(binary, out)
        isolated = isolation(binary)
        fault = issuer_frame_case(
            binary, out / "frame", next(r["originalJvm"] for r in rows if r["control"] == "frame")
        )
    record = {
        "schema": "trusted-kernel-trials/v1",
        "phase": phase,
        "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
        "rustBuild": build,
        "javaDriverBuild": java_build,
        "hardware": platform.machine(),
        "rustVersion": subprocess.check_output(["rustc", "-V"], text=True).strip(),
        "consumerSources": {
            p.name: digest(p.read_bytes())
            for p in [*sorted(HERE.glob("*.rs")), HERE.parents[1] / "src/digest.rs"]
        },
        "cases": rows,
        "substitutions": altered,
        "experimentalIssuerFault": fault,
        "readDenials": isolated,
    }
    (out / "results.json").write_text(json.dumps(record, indent=2) + "\n")
    print([(r["control"], r["actual"]) for r in [*rows, *altered]])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("phase", choices=["freeze", "transfer"])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    run(args.phase, args.out or HERE / "evidence" / args.phase)
