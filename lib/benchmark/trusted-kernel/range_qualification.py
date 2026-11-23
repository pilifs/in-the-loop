"""Prepare, recheck and measure the independently checked range-fill bundles."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from controls import JDK
from prepare import HERE, digest, request
from replay import build_kernel, fresh_rust, measured, summarize

BUNDLE = HERE / "evidence/range-proof"
EXAMPLE = HERE.parents[2] / "examples/337-jdk-range-fill-alias"
ARRAYS = "4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab"
RANGES = {
    "original": "65a3dcaa8e00b184403c745907a3e1778500beec33b30ad26b3ecd29ba933742",
    "extra": "b180ea7555fe22eb7c84af1a6812cd86ee76650f967d12c7f9ec5060224b3ebe",
}
DIRECT = "range-fill-frame-v1"
CALLER = "range-fill-caller-frame-observation-v1"
# Artifact, method, expected exit, and an independently specified reason.
CASES = {
    "fill-any-length": ("Arrays", "fill", 0, "accepted " + DIRECT),
    "caller-any-length": ("original", "observe", 0, "accepted " + CALLER),
    "caller-extra-any-length": ("extra", "observe", 2, "returned 7, after [7], expected 11 and [11]"),
    "saved-local": ("loops", "savedValue", 0, "accepted " + DIRECT),
    "missing-store": ("loops", "missingStore", 2, "written prefix or progress at back edge"),
    "wrong-value": ("loops", "wrongValue", 2, "written prefix or outside frame at store"),
    "strict-empty-guard": ("loops", "rejectsEmpty", 3, "range guard From Lt To at strictRangeCheck@2"),
    "wrong-observed-root": (
        "loops",
        "readsFilledRoot",
        2,
        "array bounds exception at read 11, expected normal return 31",
    ),
}


def extract_arrays(dest):
    with zipfile.ZipFile(JDK / "jmods/java.base.jmod") as archive:
        data = archive.read("classes/java/util/Arrays.class")
    if digest(data) != ARRAYS:
        raise ValueError("Temurin 21.0.13+9 java.util.Arrays class differs")
    dest.write_bytes(data)
    return dest


def compile_java(source, folder):
    subprocess.run(
        [
            JDK / "bin/javac",
            "--release",
            "21",
            "-encoding",
            "UTF-8",
            "-parameters",
            "-implicit:none",
            "-d",
            folder,
            source,
        ],
        check=True,
    )


def inputs(name, folder, arrays):
    asset = CASES[name][0]
    return (
        folder / (name + ".request"),
        folder / (name + ".cert"),
        arrays if asset == "Arrays" else folder / (asset + ".bin"),
        [arrays] if asset in RANGES or name == "wrong-observed-root" else [],
    )


def prepare(dest, tmp, arrays):
    from range_certificate import issue

    dest.mkdir(parents=True, exist_ok=True)
    for variant, sha in RANGES.items():
        compile_java(EXAMPLE / variant / "fill/Range.java", tmp)
        data = (tmp / "fill/Range.class").read_bytes()
        if digest(data) != sha:
            raise ValueError(variant + " differs from example 337")
        (dest / (variant + ".bin")).write_bytes(data)
    compile_java(HERE / "java/RangeLoops.java", tmp)
    shutil.copyfile(tmp / "fixtures/RangeLoops.class", dest / "loops.bin")
    for name, (asset, method, _, _) in CASES.items():
        req, cert, artifact, callee = inputs(name, dest, arrays)
        sha = digest(artifact.read_bytes())
        owner = {"Arrays": "java/util/Arrays", "loops": "fixtures/RangeLoops"}.get(asset, "fill/Range")
        if callee:
            body = request(CALLER, owner, sha, method + " ([I[IIIII)I", "fill ([IIII)V")
            body += f"callee java/util/Arrays {ARRAYS}\n"
        else:
            guard = "strictRangeCheck" if name == "strict-empty-guard" else "rangeCheck"
            body = request(DIRECT, owner, sha, method + " ([IIII)V", guard + " (III)V")
        req.write_text(body)
        cert.write_text(issue(req, artifact, *callee))


def outcome(name, args, binary, expected, reason, times):
    req, cert, artifact, callee = args
    runs = [fresh_rust(binary, req, cert, artifact, callee) for _ in range(times)]
    checked = summarize(runs)
    if checked["exit"] != expected or reason not in checked["outcome"]:
        raise ValueError((name, expected, reason, checked))
    return {
        "control": name,
        "route": "Rust range",
        "classSha256": digest(artifact.read_bytes()),
        "calleeClassSha256": [digest(p.read_bytes()) for p in callee],
        "requestedClaim": digest(req.read_bytes()),
        "certificateSha256": digest(cert.read_bytes()),
        "expected": ["accepted", None, "rejected", "unsupported"][expected],
        "actual": checked["outcome"].split()[0],
        "reason": checked["outcome"],
        "checking": checked,
        "sizes": {
            "class": artifact.stat().st_size,
            "callees": sum(p.stat().st_size for p in callee),
            "request": req.stat().st_size,
            "certificate": cert.stat().st_size,
        },
    }


def controls(binary, arrays, tmp):
    req, cert, artifact, callee = inputs("caller-any-length", BUNDLE, arrays)
    lines = cert.read_text().splitlines()
    rows = []
    for name, key in [
        ("omit-caller-frame", "observe([I[IIIII)I@"),
        ("omit-distinct-read", "distinct-root"),
        ("omit-loop-decrease", "variant-decreases"),
    ]:
        (line,) = [
            s for s in lines if key in s and (name != "omit-caller-frame" or s.endswith("exact-write-frame"))
        ]
        copy = tmp / (name + ".cert")
        copy.write_text("\n".join(s for s in lines if s != line) + "\n")
        rows.append(outcome(name, (req, copy, artifact, callee), binary, 2, "missing obligation " + line, 1))
    for name, dep, reason in [
        ("missing-callee", [], "expected one external callee class"),
        ("substitute-callee", [artifact], "external callee class digest"),
    ]:
        rows.append(outcome(name, (req, cert, artifact, dep), binary, 2, reason, 1))
    wrong = tmp / "wrong-slot.cert"
    wrong.write_text(
        cert.read_text().replace("hints written-prefix remaining 10 4", "hints written-prefix remaining 10 3")
    )
    rows.append(
        outcome("wrong-loop-slot", (req, wrong, artifact, callee), binary, 3, "range cut point or cursor", 1)
    )
    return rows


def on_jvm(tmp, arrays):
    compile_java(HERE / "java/ObserveFill.java", tmp)
    evidence = {}
    for name in ("fill-any-length", "caller-any-length", "caller-extra-any-length"):
        _, _, artifact, callee = inputs(name, BUNDLE, arrays)
        if callee:
            (tmp / "fill").mkdir(exist_ok=True)
            shutil.copyfile(artifact, tmp / "fill/Range.class")
        output = subprocess.check_output(
            [JDK / "bin/java", "-Xverify:all", "-cp", tmp, "ObserveFill", "caller" if callee else "callee"],
            text=True,
        ).splitlines()
        census = {
            "fill-any-length": "50 shared 10 distinct 40 observed-mismatch 0 frame-mismatch 0",
            "caller-any-length": "75 shared 15 distinct 60 observed-mismatch 0 frame-mismatch 0",
            "caller-extra-any-length": "75 shared 15 distinct 60 observed-mismatch 4 frame-mismatch 31",
        }
        if (
            output[0] != f"owner {digest(artifact.read_bytes())} arrays {ARRAYS}"
            or output[-1] != "cases " + census[name]
        ):
            raise ValueError((name, output))
        if name == "caller-extra-any-length" and output[1:-1] != [
            "witness shared=true before=[11] from=0 to=0 value=7 k=0 expected=11 returned=7 after=[7]"
        ]:
            raise ValueError(output)
        evidence[name] = output
    output = subprocess.check_output(
        [JDK / "bin/java", "-Xverify:all", "-cp", tmp, "fixtures.RangeLoops"], text=True
    ).splitlines()
    if output != [
        "savedValue [7, 19]",
        "missingStore [11, 19]",
        "wrongValue [0, 19]",
        "rejectsEmpty IllegalArgumentException",
        "readsFilledRoot ArrayIndexOutOfBoundsException",
    ]:
        raise ValueError(output)
    evidence["rebound-controls"] = output
    return evidence


def qualify(tmp, arrays, measure):
    generation = {}
    if measure:
        meter = tmp / "meter"
        subprocess.run(["cc", "-O2", "-Wall", "-Werror", HERE / "meter.c", "-o", meter], check=True)
        os.environ["KERNEL_TIME_METER"] = str(meter)
        rebuilt = tmp / "rebuilt"
        prepare(rebuilt, tmp, arrays)
        for path in rebuilt.iterdir():
            if path.read_bytes() != (BUNDLE / path.name).read_bytes():
                raise ValueError("regenerated bundle differs: " + path.name)
        for name in ("fill-any-length", "caller-any-length"):
            req, cert, artifact, callee = inputs(name, BUNDLE, arrays)
            dest = tmp / "issued.cert"
            samples = []
            for _ in range(3):
                sample = measured(
                    [sys.executable, "-B", HERE / "range_certificate.py", req, artifact, dest, *callee], tmp
                )
                if sample["exit"] or dest.read_bytes() != cert.read_bytes():
                    raise ValueError((name, sample))
                samples.append(sample)
            generation[name] = summarize(samples)
    binary, build = build_kernel(tmp)
    rows = [
        outcome(name, inputs(name, BUNDLE, arrays), binary, code, reason, 3 if measure else 1)
        for name, (_, _, code, reason) in CASES.items()
    ]
    rows.extend(controls(binary, arrays, tmp))
    for row in rows:
        row["checkerVersion"] = build["binarySha256"]
    if measure:
        from recheck_saved import verify_saved

        physical = on_jvm(tmp, arrays)
        previous = verify_saved("transfer", binary)
        sources = {p.relative_to(HERE).as_posix(): digest(p.read_bytes()) for p in sorted(HERE.rglob("*.rs"))}
        sources["../../src/digest.rs"] = digest((HERE.parents[1] / "src/digest.rs").read_bytes())
        return {
            "schema": "range-proof-qualification/v1",
            "checker": build,
            "consumerSources": sources,
            "compiler": subprocess.check_output(["rustc", "-V"], text=True).strip(),
            "runtime": subprocess.check_output([JDK / "bin/java", "--version"], text=True).splitlines()[0],
            "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
            "cases": rows,
            "jvm": physical,
            "previousGuavaCasesReplayed": previous,
            "generation": generation,
        }
    saved = json.loads((BUNDLE / "results.json").read_bytes())["cases"]
    fields = (
        "control",
        "classSha256",
        "calleeClassSha256",
        "requestedClaim",
        "certificateSha256",
        "checkerVersion",
        "expected",
        "actual",
        "reason",
        "sizes",
    )
    if [[r[k] for k in fields] for r in rows] != [[r[k] for k in fields] for r in saved]:
        raise ValueError("clean results differ from the recorded range cases")
    return {"cases": rows}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", type=Path, metavar="DIRECTORY")
    group.add_argument("--extract-arrays", type=Path, metavar="FILE")
    group.add_argument("--check", action="store_true")
    group.add_argument("--qualify", type=Path, metavar="RESULT")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as work:
        tmp = Path(work)
        arrays = extract_arrays(args.extract_arrays or tmp / "Arrays.class")
        if args.prepare:
            prepare(args.prepare, tmp, arrays)
        elif not args.extract_arrays:
            result = qualify(tmp, arrays, bool(args.qualify))
            if args.qualify:
                args.qualify.write_text(json.dumps(result, indent=2) + "\n")
            print([(r["control"], r["actual"]) for r in result["cases"]])
