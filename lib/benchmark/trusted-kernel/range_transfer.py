"""Replay release transfers with source-frozen checkers and JVMs loading the pinned artifacts."""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
import zipfile

import certificate
from controls import JDK
from frozen_range import int_kernel, long_kernel
from prepare import HERE, INDEX, digest, request
from range_certificate import issue as range_issue
import range_qualification as rq
from recheck_saved import verify_saved
from replay import fresh_rust

CACHE = Path(os.environ.get("KERNEL_RECOVERY_CACHE",
                            Path.home() / ".cache/in-the-loop/trusted-kernel-receiver-recovery"))
GUAVA = "com/google/common/primitives/"
RELEASES = {
    "guava-31.1-jre": ("a42edc9cab792e39fe39bb94f3fca655ed157ff87a8af78e1d6ba5b07c4a00ab", GUAVA),
    "beam-vendor-guava-32_1_2-jre-0.1":
        ("44669a8f43cdef8ac20e02484ead0d1cf8199d47e00c7f1828b579b7dfb0f9a2",
         "org/apache/beam/vendor/guava/v32_1_2_jre/" + GUAVA),
    "fastutil-8.5.15": ("cffeb6673bdf1e6e4377d684df2f55ac359cf5cf6df613e05e62deeea500936a",
                        "it/unimi/dsi/fastutil/"),
}
PROBES = "ca8f1afe8027670c711468b7f66b90df74e44bbf9d605a72835c11730d177fc2"


def release(name):
    path = CACHE / "releases" / name / "lib" / (name + ".jar")
    if digest(path.read_bytes()) != RELEASES[name][0]:
        raise ValueError("release digest " + name)
    return path


def probe(tmp, name, args=(), classpath=(), options=()):
    archive = (HERE / "snapshots/recovery-jvm-probes.tar.gz").read_bytes()
    if digest(archive) != PROBES:
        raise ValueError("baseline JVM probe source archive")
    with tarfile.open(fileobj=BytesIO(archive), mode="r:gz") as tar:
        source = tmp / (name + ".java")
        source.write_bytes(tar.extractfile(source.name).read())
    cp = os.pathsep.join(map(str, [tmp, *classpath]))
    subprocess.run([JDK / "bin/javac", "--release", "21", "-proc:none", "-cp", cp, "-d", tmp, source], check=True)
    run = subprocess.check_output([JDK / "bin/java", "-Xverify:all", *options, "-cp", cp, name, *args], text=True)
    return {"sourceSha256": digest(source.read_bytes()), "classSha256": digest((tmp / (name + ".class")).read_bytes()),
            "jvmOptions": ["-Xverify:all", *options], "observations": run.splitlines()}


def check(binary, req, cert, artifact, support, expected_exit, reason):
    result = fresh_rust(binary, req, cert, artifact, support)
    if result["exit"] != expected_exit or reason not in result["stdout"]:
        raise ValueError((req.read_text(), expected_exit, reason, result))
    return {**result, "checkerSha256": digest(binary.read_bytes())}


def bound_case(tmp, text, artifact, issuer, support=()):
    req, cert = tmp / "external.request", tmp / "evidence.cert"
    req.write_text(text)
    started = time.perf_counter()
    cert.write_text(issuer(req, artifact))
    evidence = {"request": text, "requestSha256": digest(req.read_bytes()), "certificate": cert.read_text(),
                "certificateSha256": digest(cert.read_bytes()), "generationSeconds": time.perf_counter() - started,
                "classSha256": digest(artifact.read_bytes()), "supportSha256": [digest(p.read_bytes()) for p in support]}
    return (req, cert, artifact, support), evidence


def regression(binary, arrays, tmp):
    guava = verify_saved("transfer", binary)
    cases = [rq.outcome(name, rq.inputs(name, rq.BUNDLE, arrays), binary, code, reason, 1)
             for name, (_, _, code, reason) in rq.CASES.items()]
    cases.extend(rq.controls(binary, arrays, tmp))
    return {"guavaChecks": guava, "rangeChecks": [
        {"case": row["control"], "disposition": row["actual"], "firstDecision": row["reason"]} for row in cases]}


def extract(archive, owner, tmp):
    path = tmp / (owner.rsplit("/", 1)[-1] + ".bin")
    path.write_bytes(archive.read(owner + ".class"))
    return path


def guava_releases(tmp, baseline):
    cases = {}
    for name, (sha, pkg) in RELEASES.items():
        if name.startswith("fastutil"):
            continue
        jar = release(name)
        with zipfile.ZipFile(jar) as archive:
            for kind, desc in [("Ints", "I"), ("Longs", "J")]:
                owner = pkg + kind
                artifact = extract(archive, owner, tmp)
                support = []
                parent = None
                if kind == "Ints":
                    sup = extract(archive, pkg + "IntsMethodsForWeb", tmp)
                    support.append(sup)
                    parent = pkg + "IntsMethodsForWeb " + digest(sup.read_bytes())
                text = request(INDEX, owner, digest(artifact.read_bytes()), f"indexOf ([{desc}{desc})I",
                               f"indexOf ([{desc}{desc}II)I", parent)
                args, data = bound_case(tmp, text, artifact, certificate.issue, support)
                req, _, _, _ = args
                old = HERE / "evidence/transfer" / kind / "evidence.cert"
                data["oldCertificate"] = check(baseline, req, old, artifact, support, 2, "bind external request")
                count = 34 if kind == "Ints" else 35
                data["result"] = check(baseline, *args, 0, f"obligations {count}")
                data["jarSha256"] = sha
                cases[f"{name}/{kind}"] = data
        physical = probe(tmp, "IndexOfReleases", [jar, pkg.rstrip("/").replace("/", ".")])
        lines = physical["observations"]
        for kind in ("Ints", "Longs"):
            row = cases[f"{name}/{kind}"]
            assert f"{kind} loaded sha256 " + row["classSha256"] in lines
            row["jvm"] = physical
        if lines[-2:] != ["int calls=780 agree=780 heapUnchanged=780", "long calls=1554 agree=1554 heapUnchanged=1554"]:
            raise ValueError(lines)
    return cases


def jdk_stage(tmp):
    baseline, successor = int_kernel(tmp / "int"), long_kernel(tmp / "long")
    arrays = rq.extract_arrays(tmp / "Arrays.bin")
    text = request(rq.DIRECT, "java/util/Arrays", rq.ARRAYS, "fill ([JIIJ)V", "rangeCheck (III)V")
    args, long = bound_case(tmp, text, arrays, range_issue)
    long["before"] = check(baseline, *args, 3, "range-fill descriptors")
    long["after"] = check(successor, *args, 0, "obligations 37")
    long["jvm"] = probe(tmp, "LongFill")
    observations = long["jvm"]["observations"]
    if not (observations[0].startswith("checks=245 pass=245 narrowChanged=80 extendChanged=140 ")
            and observations[1] == "oneCell4294967296 -> 4294967296 (narrowed would be 0)"):
        raise ValueError(observations)
    cases = {"jdk-21.0.13/long-fill": long, **guava_releases(tmp, baseline)}
    jar = release("fastutil-8.5.15")
    owner = "it/unimi/dsi/fastutil/ints/IntArrays"
    with zipfile.ZipFile(jar) as archive:
        artifact = extract(archive, owner, tmp)
        text = request(rq.DIRECT, owner, digest(artifact.read_bytes()), "fill ([IIII)V", "ensureFromTo ([III)V")
        args, row = bound_case(tmp, text, artifact, range_issue)
        row["before"] = check(successor, *args, 3, "range-fill descriptors")
        row["jarSha256"] = RELEASES["fastutil-8.5.15"][0]
        cases["fastutil-8.5.15/fill-before-external-guard"] = row
    return {"schema": "independent-range-transfer/v1", "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
            "compiler": subprocess.check_output(["rustc", "-V"], text=True).strip(),
            "jdk": subprocess.check_output([JDK / "bin/java", "--version"], text=True).splitlines()[0],
            "regressions": regression(successor, arrays, tmp), "cases": cases}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        data = jdk_stage(Path(td))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    print(f"{len(data['cases'])} release requests, {data['regressions']['guavaChecks']} Guava controls, "
          f"{len(data['regressions']['rangeChecks'])} range controls")


if __name__ == "__main__":
    main()
