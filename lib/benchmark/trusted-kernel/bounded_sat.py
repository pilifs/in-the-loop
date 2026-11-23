"""Allow the transcript directory through in this experiment process and qualify every observed UNSAT call."""

import argparse
import collections
import gzip
import io
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tarfile
import tempfile

from prepare import HERE, digest
from capture import benchmark, save
from types import SimpleNamespace
from lrat import CADICAL, CAKE, checked, dimacs, queries
from replay import measured

ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))


def instrumented_task():
    # Identical task, actual CLI, classpath, model, and bounds. Limit the diagnostic setting to this process.
    import build
    from targets import runtime

    runtime.VERIFIER_PASS = (*runtime.VERIFIER_PASS, "JVMCONTRACT_TRANSCRIPTS")
    return build.main(["336", "--task", "first-8-release"])


def certify(capture, profile, out, check_only):
    if digest(CAKE.read_bytes()) != "c14ff49853e890436d6a2fbf66a85b9492dad1dcd2d76254f16a89f2236c8a54":
        raise ValueError("pinned cake_lpr checker differs")
    if (
        not check_only
        and digest(CADICAL.read_bytes()) != "0fabbda6d757d7076ca003c8e9ffadd4ef893c3cacaabcf5986c415e0de74ec4"
    ):
        raise ValueError("pinned CaDiCaL generator differs")
    out.mkdir(parents=True, exist_ok=True)
    previous = json.loads((out / "queries.json").read_text()) if check_only else None
    packed = out / "proofs.tar.gz"
    known = {}
    if previous:
        if digest(packed.read_bytes()) != previous["packSha256"]:
            raise ValueError("proof pack digest")
        known = {v["key"]: v for v in previous["queries"]}
    rows = []
    binaries = {}
    counts = collections.Counter()
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        for trace in profile["traces"]:
            raw = gzip.decompress((capture / trace["file"]).read_bytes())
            if digest(raw) != trace["sha256"]:
                raise ValueError("transcript digest")
            for n, (clauses, assumptions, answer) in enumerate(queries(raw), 1):
                counts[answer] += 1
                if answer != "unsat":
                    continue
                key = trace["file"].split(".")[0] + f"-{n}"
                cnf = tmp / "query.cnf"
                proof = tmp / "query.lrat"
                content = dimacs(clauses, assumptions)
                cnf.write_bytes(content)
                if previous:
                    old = known[key]
                    if old["cnfSha256"] != digest(content) or old["transcriptSha256"] != trace["sha256"]:
                        raise ValueError("exported formula/source binding")
                    with tarfile.open(packed, "r:gz") as archive:
                        data = archive.extractfile(key + ".lrat").read()
                    if digest(data) != old["proofSha256"]:
                        raise ValueError("proof binding")
                    proof.write_bytes(data)
                    checked(cnf, proof, True, tmp)
                    rows.append(old)
                    continue
                generation = measured([CADICAL, "-q", "--lrat", "--no-binary", cnf, proof], tmp)
                if generation["exit"] != 20 or "s UNSATISFIABLE" not in generation["stdout"].splitlines():
                    raise ValueError(generation)
                checks = [checked(cnf, proof, True, tmp) for _ in range(3)]
                data = proof.read_bytes()
                binaries[key + ".lrat"] = data
                rows.append(
                    {
                        "route": "SAT/LRAT",
                        "control": "observed UNSAT",
                        "classSha256": profile["classSha256"],
                        "requestedClaim": profile["claim"],
                        "checkerVersion": digest(CAKE.read_bytes()),
                        "key": key,
                        "trace": trace["file"],
                        "transcriptSha256": trace["sha256"],
                        "queryOneBased": n,
                        "clausesAtSolve": len(clauses),
                        "assumptions": assumptions,
                        "cnfSha256": digest(content),
                        "cnfBytes": len(content),
                        "proofBytes": len(data),
                        "proofSha256": digest(data),
                        "expected": "verified UNSAT",
                        "actual": "verified UNSAT",
                        "generation": generation,
                        "checks": checks,
                        "medianCheckPeakKiB": statistics.median(c["peakKiB"] for c in checks),
                    }
                )
        if not rows:
            raise ValueError("missing UNSAT calls")
        # A materialized nontrivial query demonstrates damage discrimination as well as formula binding.
        representative = max(rows, key=lambda r: r["proofBytes"])
        linked = next(t for t in profile["traces"] if t["file"] == representative["trace"])
        raw = gzip.decompress((capture / linked["file"]).read_bytes())
        selected = next(q for n, q in enumerate(queries(raw), 1) if n == representative["queryOneBased"])
        cnf = tmp / "selected.cnf"
        proof = tmp / "selected.lrat"
        cnf.write_bytes(dimacs(*selected[:2]))
        if previous:
            with tarfile.open(packed, "r:gz") as archive:
                proof.write_bytes(archive.extractfile(representative["key"] + ".lrat").read())
            if gzip.decompress((out / "selected.cnf.gz").read_bytes()) != cnf.read_bytes():
                raise ValueError("selected DIMACS")
        else:
            proof.write_bytes(binaries[representative["key"] + ".lrat"])
            (out / "selected.cnf.gz").write_bytes(gzip.compress(cnf.read_bytes(), mtime=0))
        lines = proof.read_bytes().splitlines(keepends=True)
        stop = next(i for i, line in enumerate(lines) if line.split()[1:2] == [b"0"])
        damaged = tmp / "damaged.lrat"
        damaged.write_bytes(b"".join(lines[:stop]))
        sat = tmp / "known-sat.cnf"
        sat.write_text("p cnf 1 1\n1 0\n")
        controls = {
            "selected": representative["key"],
            "complete": checked(cnf, proof, True, tmp),
            "truncatedBeforeEmptyClause": checked(cnf, damaged, False, tmp),
            "knownSatisfiable": checked(sat, proof, False, tmp),
            "satisfyingAssignment": [1],
            "damageBytes": damaged.stat().st_size,
        }
        if previous:
            if previous["controls"]["selected"] != controls["selected"]:
                raise ValueError("selected query changed")
            if len(rows) != len(known) or counts != previous["observed"]:
                raise ValueError("incomplete query inventory")
        else:
            with packed.open("wb") as f, gzip.GzipFile(
                fileobj=f, mode="wb", mtime=0, filename=""
            ) as gz, tarfile.open(fileobj=gz, mode="w") as archive:
                for name, data in sorted(binaries.items()):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
            (out / "queries.json").write_text(
                json.dumps(
                    {
                        "workload": profile["claim"],
                        "observed": dict(counts),
                        "decisionsWithoutSolver": profile["decisions"] - sum(counts.values()),
                        "packSha256": digest(packed.read_bytes()),
                        "checkerRevision": "033aad53",
                        "generatorVersion": "CaDiCaL 1.9.5",
                        "controls": controls,
                        "queries": rows,
                    },
                    indent=2,
                )
                + "\n"
            )
    print(
        f"{profile['claim']}: certified {len(rows)}/{counts['unsat']} UNSAT, {counts['sat']} SAT calls, {profile['decisions']-sum(counts.values())} constant-false decisions"
    )


def bind_prefix_pair(temp, original, destination):
    """Independently rebuild both workload classes and compare every clause, assumption and answer."""
    (case,) = benchmark.load_cases([3], "held/prefix-sums")
    classes = {}
    bindings = {}
    destination.mkdir(parents=True, exist_ok=True)
    for side in (case["before"], case["after"]):
        (source,) = (benchmark.HERE / benchmark.versions()[side]).rglob("PrefixSums.java")
        classes[side] = benchmark.javac([str(source)], temp / side)
        (artifact,) = classes[side].rglob("PrefixSums.class")
        data = artifact.read_bytes()
        (destination / (side + ".bin")).write_bytes(data)
        bindings[side] = digest(data)
    check = temp / "prefix-work"
    check.mkdir()
    exe = os.environ["JVMCONTRACT"]
    cmd = benchmark.command(
        case, "native", "strict", classes, check, SimpleNamespace(jvmcontract=exe, timeout=120, jbmc="jbmc")
    )
    env = dict(os.environ, JVMCONTRACT_SOLVER="cadical", JVMCONTRACT_TRANSCRIPTS=str(temp / "prefix-stream"))
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
    if json.loads(result.stdout)["verdict"] != "verified":
        raise ValueError("prefix pair did not verify")
    (trace,) = (temp / "prefix-stream").glob("*.icnf")

    def logical(data):
        return [
            line.split(" limit ")[0].split()[:3] if line.startswith("c answer ") else line
            for line in data.decode("ascii").splitlines()
        ]

    if logical(trace.read_bytes()) != logical(gzip.decompress(original.read_bytes())):
        raise ValueError("prefix pair differs from the original logical transcript")
    return bindings


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrumented-task", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.instrumented_task:
        return instrumented_task()
    out = HERE / "evidence/bounded-sat"
    src = HERE / "evidence/sat"
    capture = json.loads((src / "capture.json").read_text())
    reference = capture["boundedConclusion"]["obligations"][0]["evidence"]["search"]["native"]
    if not args.check:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            env = dict(
                os.environ, JVMCONTRACT_TRANSCRIPTS=str(temp / "transcripts"), JVMCONTRACT_SOLVER="cadical"
            )
            run = subprocess.run(
                [sys.executable, "-B", __file__, "--instrumented-task"],
                env=env,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
            )
            print(run.stdout, end="")
            if run.returncode or "as expected" not in run.stdout:
                raise ValueError("diagnostic bounded task failed")
            p = next((ROOT / "examples").glob("336-*")) / run.stdout.rsplit("receipt ", 1)[-1].strip()
            doc = json.loads(p.read_text())
            conclusion = doc["conclusion"]
            actual = conclusion["obligations"][0]["evidence"]["search"]["native"]
            quantities = ("solverCalls", "paths", "variables", "clauses", "gatesEvaluated")
            if (
                conclusion["status"] != "established"
                or conclusion["vacuous"]
                or any(actual[k] != reference[k] for k in quantities)
            ):
                raise ValueError("instrumented task differs from the ordinary bounded claim")
            profile = {
                "claim": "336/first-8-release",
                "classSha256": "ae581f721521c93250639d17348c5b7215f3591a1bb433fb63985caa4364edbb",
                "traces": save(temp / "transcripts", out / "traces"),
                "decisions": actual["solverCalls"],
                "checkerSha256": digest(Path(os.environ["JVMCONTRACT"]).read_bytes()),
                "compared": {k: actual[k] for k in quantities},
                "classBindingReceipt": str(p.relative_to(ROOT)),
                "jdkScope": conclusion["obligations"][0]["evidence"]["domain"],
            }
            if not profile["traces"]:
                raise ValueError("diagnostic directory still empty")
            (backup_trace,) = capture["held/prefix-sums"]
            profile["fallbackClassSha256"] = bind_prefix_pair(
                temp, src / "fallback" / backup_trace["file"], out / "prefix-inputs"
            )
            profile["bytecode"] = doc["attempt"]["bytecode"]
            profile["claimId"] = doc["claim"]["id"]
            (out / "capture.json").write_text(json.dumps(profile, indent=2) + "\n")
    bounded = json.loads((out / "capture.json").read_text())
    certify(out / "traces", bounded, out / "guava", args.check)
    fallback = {
        "traces": capture["held/prefix-sums"],
        "decisions": capture["fallbackSearch"]["native"]["solver_calls"],
        "claim": "held/prefix-sums",
        "classSha256": bounded["fallbackClassSha256"],
    }
    certify(src / "fallback", fallback, out / "prefix-sums", args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
