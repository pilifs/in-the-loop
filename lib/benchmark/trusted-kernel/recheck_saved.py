"""Recheck saved semantic bundles, including the original frozen program, with no evidence generator."""

import json
from pathlib import Path
import os
import tarfile
import tempfile

from prepare import HERE, digest
from replay import build_kernel, fresh_rust, lean_check


def read(path):
    return json.loads(path.read_text())


def verify_saved(phase, binary):
    folder = HERE / "evidence" / phase
    report = read(folder / "results.json")
    bindings = {}
    for row in report["cases"]:
        bundle = folder / row["control"]
        req = bundle / "external.request"
        cert = bundle / "evidence.cert"
        artifact = bundle / "artifact.bin"
        if (digest(req.read_bytes()), digest(cert.read_bytes()), digest(artifact.read_bytes())) != (
            row["requestSha256"],
            row["certificateSha256"],
            row["classSha256"],
        ):
            raise ValueError("bundle binding")
        bindings[row["classSha256"]] = artifact
        support = [bundle / "support.bin"] if (bundle / "support.bin").exists() else []
        check = fresh_rust(binary, req, cert, artifact, support)
        if (check["exit"], check["stdout"]) != (row["exit"], row["outcome"]):
            raise ValueError((row["control"], check))
    with tempfile.TemporaryDirectory() as tmp:
        req = Path(tmp) / "request"
        cert = Path(tmp) / "certificate"
        for row in report["substitutions"]:
            req.write_text(row["requestedClaim"])
            cert.write_text(row["certificate"])
            ck = fresh_rust(binary, req, cert, bindings[row["classSha256"]], [folder / "Ints/support.bin"])
            if (ck["exit"], ck["stdout"]) != (row["exit"], row["stdout"]):
                raise ValueError((row["control"], ck))
    return len(report["cases"]) + len(report["substitutions"])


def main():
    ev = HERE / "evidence"
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        archived = tmp / "archived"
        archived.mkdir()
        saved = read(ev / "pretransfer/Ints.json")
        snapshot = ev / "pretransfer/sources.tar.gz"
        with tarfile.open(snapshot, "r:gz") as tar:
            members = {m.name: m for m in tar.getmembers()}
            for name, sha in saved["sources"].items():
                rel = "lib/src/digest.rs" if name == "digest.rs" else "lib/benchmark/trusted-kernel/" + name
                data = tar.extractfile(members.pop(rel)).read()
                if digest(data) != sha:
                    raise ValueError("frozen source digest " + name)
                path = archived / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            if members:
                raise ValueError("unexpected frozen source")
        frozen, _ = build_kernel(archived, archived / "lib/benchmark/trusted-kernel")
        if digest(frozen.read_bytes()) != saved["binarySha256"]:
            raise ValueError("frozen binary digest")
        frozen_checks = verify_saved("freeze", frozen)
        final, _ = build_kernel(tmp)
        finaldoc = read(ev / "transfer/results.json")
        if digest(final.read_bytes()) != finaldoc["rustBuild"]["binarySha256"]:
            raise ValueError("final binary digest")
        final_checks = verify_saved("transfer", final)
        scalar = read(ev / "scalar/measurements.json")
        for row in scalar["cases"]:
            name = row["control"]
            req = HERE / "requests" / (name + ".request")
            cert = ev / "scalar" / (name + ".cert")
            artifact = HERE / "inputs/Scalar.bin"
            ck = (
                fresh_rust(final, req, cert, artifact)
                if row["route"] == "Rust"
                else lean_check(req, cert, artifact)
            )
            if ck["exit"] != row["exit"]:
                raise ValueError((name, ck))
        result = {
            "frozenBundlesAndSubstitutions": frozen_checks,
            "finalBundlesAndSubstitutions": final_checks,
            "scalarRoutes": len(scalar["cases"]),
            "frozenBinary": digest(frozen.read_bytes()),
            "finalBinary": digest(final.read_bytes()),
            "snapshotSha256": digest(snapshot.read_bytes()),
            "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
        }
    (ev / "clean-replay.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result)


if __name__ == "__main__":
    main()
