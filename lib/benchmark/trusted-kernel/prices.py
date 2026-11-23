"""Three isolated checks per positive case, with a small native parent for Linux wait4 accounting."""

import argparse
import gzip
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tarfile
import tempfile

from prepare import HERE, digest
from replay import build_kernel, fresh_rust, lean_check, measured
from lrat import CADICAL, CAKE


def stats(checks):
    return {
        "samples": checks,
        "medianPeakKiB": statistics.median(v["peakKiB"] for v in checks),
        "medianSeconds": statistics.median(v["wallSeconds"] for v in checks),
    }


def original_generation(number, destination):
    from baseline import ROOT, array_induction

    (folder,) = (ROOT / "examples").glob(number + "-*")
    target = json.loads((folder / "target.json").read_text())
    (spec,) = [v for v in target["arrayContracts"] if v["id"] == "first-any-length"]
    if not array_induction.run(folder, target, spec, 60, records=destination):
        raise ValueError("original baseline not established")


def price_original(number, name, tmp):
    repo = HERE.parents[2]
    reference = json.loads((HERE / "evidence/baseline" / (number + ".json")).read_text())["freshResult"]
    generation = []
    checking = []
    for i in range(3):
        dest = tmp / (number + "-" + str(i))
        gen = measured([sys.executable, "-B", __file__, "--original", number, dest], repo)
        if gen["exit"]:
            raise ValueError(gen)
        (p,) = dest.glob("*/*/result.json")
        r = json.loads(p.read_text())
        if (
            r["obligations"] != reference["obligations"]
            or r["certificateSha256"] != reference["certificateSha256"]
        ):
            raise ValueError("original generation differs")
        generation.append(gen)
        ck = measured(
            [
                sys.executable,
                "-B",
                "examples/tools/build.py",
                number,
                "--array-induction",
                "first-any-length",
                "--compare",
            ],
            repo,
        )
        if ck["exit"] or "the same result" not in ck["stdout"] or "established" not in ck["stdout"]:
            raise ValueError(ck)
        checking.append(ck)
    sizes = {f.name: f.stat().st_size for f in p.parent.iterdir() if f.is_file()}
    request = HERE / "requests" / (name + ".request")
    return {
        "case": name,
        "route": "Historical Python/Z3",
        "classSha256": digest((HERE / "inputs" / (name + ".bin")).read_bytes()),
        "requestSha256": digest(request.read_bytes()),
        "requestBytes": request.stat().st_size,
        "certificateSha256": r["certificateSha256"],
        "certificateBytes": sizes["obligations.smt2"],
        "producerBundleBytes": sizes,
        "generation": stats(generation),
        "checking": stats(checking),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=HERE / "evidence/costs.json")
    ap.add_argument("--original", nargs=2, metavar=("EXAMPLE", "DESTINATION"))
    args = ap.parse_args()
    if args.original:
        original_generation(*args.original)
        return
    capture = HERE / "evidence"
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        meter = tmp / "meter"
        subprocess.run(["cc", "-O2", "-Wall", "-Werror", HERE / "meter.c", "-o", meter], check=True)
        os.environ["KERNEL_TIME_METER"] = str(meter)
        binary, build = build_kernel(tmp)
        rows = []
        for name in ("add", "Ints", "Longs"):
            scalar = name == "add"
            req = HERE / "requests" / (name + ".request")
            original = HERE / "inputs" / (("Scalar" if scalar else name) + ".bin")
            cert = capture / "scalar/add.cert" if scalar else capture / "transfer" / name / "evidence.cert"
            support = [HERE / "inputs/IntsMethodsForWeb.bin"] if name == "Ints" else []
            if not cert.is_file():
                raise ValueError(f"missing completed evidence for {name}")
            generations = []
            for _ in range(3):
                output = tmp / "issued.cert"
                cmd = [sys.executable, "-B", HERE / "certificate.py", req, original, output]
                if name == "Longs":
                    cmd += ["4294967296", "0,4294967296"]
                result = measured(cmd, tmp)
                if result["exit"] or output.read_bytes() != cert.read_bytes():
                    raise ValueError(("certificate mismatch", name, result))
                generations.append(result)
            for engine in (["Rust", "Lean"] if scalar else ["Rust"]):

                def check():
                    return (
                        fresh_rust(binary, req, cert, original, support)
                        if engine == "Rust"
                        else lean_check(req, cert, original)
                    )

                checks = [check() for _ in range(3)]
                if any(c["exit"] for c in checks):
                    raise ValueError(checks)
                rows.append(
                    {
                        "case": name,
                        "route": engine,
                        "classSha256": digest(original.read_bytes()),
                        "requestSha256": digest(req.read_bytes()),
                        "certificateSha256": digest(cert.read_bytes()),
                        "artifactBytes": original.stat().st_size + sum(p.stat().st_size for p in support),
                        "requestBytes": req.stat().st_size,
                        "certificateBytes": cert.stat().st_size,
                        "generation": stats(generations),
                        "checking": stats(checks),
                    }
                )
        for family in ("guava", "prefix-sums"):
            folder = capture / "bounded-sat" / family
            query = json.loads((folder / "queries.json").read_text())
            selected = next(r for r in query["queries"] if r["key"] == query["controls"]["selected"])
            cnf = tmp / "query.cnf"
            proof = tmp / "query.lrat"
            cnf.write_bytes(gzip.decompress((folder / "selected.cnf.gz").read_bytes()))
            with tarfile.open(folder / "proofs.tar.gz", "r:gz") as archive:
                raw = archive.extractfile(selected["key"] + ".lrat").read()
            if digest(raw) != selected["proofSha256"] or digest(cnf.read_bytes()) != selected["cnfSha256"]:
                raise ValueError("query bundle digest")
            generation = []
            checks = []
            for _ in range(3):
                gen = measured([CADICAL, "-q", "--lrat", "--no-binary", cnf, proof], tmp)
                if gen["exit"] != 20 or proof.read_bytes() != raw:
                    raise ValueError(("generator differs", gen))
                generation.append(gen)
                ck = measured([CAKE, cnf, proof], tmp)
                if ck["exit"] or "s VERIFIED UNSAT" not in ck["stdout"].splitlines():
                    raise ValueError(ck)
                checks.append(ck)
            rows.append(
                {
                    "case": family,
                    "route": "SAT/LRAT",
                    "classSha256": selected["classSha256"],
                    "requestSha256": selected["cnfSha256"],
                    "certificateSha256": selected["proofSha256"],
                    "requestBytes": cnf.stat().st_size,
                    "certificateBytes": len(raw),
                    "generation": stats(generation),
                    "checking": stats(checks),
                }
            )
        rows.extend(price_original(n, name, tmp) for n, name in [("336", "Ints"), ("346", "Longs")])
        cpu = next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            platform.machine(),
        )
        record = {
            "schema": "trusted-kernel-cost/v1",
            "cpu": cpu,
            "machine": platform.machine(),
            "kernel": platform.release(),
            "unit": "KiB peak RSS from wait4, seconds monotonic from exec to exit, three fresh processes",
            "meterSha256": digest((HERE / "meter.c").read_bytes()),
            "build": build,
            "cases": rows,
        }
        args.out.write_text(json.dumps(record, indent=2) + "\n")
        print([(r["route"], r["case"], r["checking"]["medianPeakKiB"]) for r in rows])


if __name__ == "__main__":
    main()
