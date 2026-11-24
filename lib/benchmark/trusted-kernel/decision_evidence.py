"""Recount the committed experiment, verifying inputs, outcomes, costs and proof-pack digests."""

import argparse
import gzip
import json
from pathlib import Path
import tarfile

from prepare import HERE, digest
from recheck_saved import snapshot_sources
from frame_witness import FILL, Z3, guava_record, original_scope, witness_query
from frozen_range import historical_files, historical_manifest

EV = HERE / "evidence"


def read(p):
    return json.loads(p.read_text())


def require(check, message):
    if not check:
        raise ValueError(message)


def core_version():
    full = read(EV / "baseline/336.json")["freshResult"]["rules"]["files"]
    core = {k: v for k, v in full.items() if k.startswith("lib/python/")}
    return digest(json.dumps(core, sort_keys=True, separators=(",", ":")).encode())


def job_ledger():
    identifiers = (
        "20261123-191504-reproduce-both-guava-any-length-producer",
        "20261123-191505-capture-real-bounded-solver-queries-for",
        "20261123-192639-compare-isolated-rust-and-lean-on-compil",
        "20261123-194123-certify-all-observed-bounded-guava-and-p",
        "20261123-194123-freeze-the-public-ints-proof-and-try-lon",
        "20261123-195310-qualify-the-64-bit-transfer-and-held-bac",
        "20261123-200519-reconcile-both-guava-solver-passes-with",
        "20261123-200519-replay-clean-java-proof-bundles-and-meas",
        "20261123-200520-measure-the-range-fill-and-aliased-calle",
        "20261123-204925-qualify-jdk-range-fill-and-the-independe",
        "20261123-205832-replay-original-solver-failures-on-the-i",
    )
    root = HERE.parents[2]
    result = []
    for job in identifiers:
        path = Path("verification/results/2026/11/23") / job / "result.json"
        r = read(root / path)
        spec = read(root / r["job"]["path"])
        require(
            spec == r["job"]["spec"]
            and digest(json.dumps(spec, sort_keys=True).encode()) == r["job"]["sha256"],
            job + " spec",
        )
        result.append(
            {
                "id": job,
                "status": r["status"],
                "sourceCommit": r["sourceCommit"],
                "summary": r["summary"],
                "attention": r["attention"],
                "receipt": str(path),
            }
        )
    return result


def report():
    cases = []

    def case(route, artifact, claim, control, checker, want, got, reason, source):
        require(want == got, (control, reason))
        cases.append(
            dict(
                route=route,
                classSha256=artifact,
                requestedClaim=claim,
                control=control,
                checkerVersion=checker,
                expected=want,
                actual=got,
                reason=reason,
                evidence=source,
            )
        )

    for number, name in [("336", "Ints"), ("346", "Longs")]:
        rel = f"baseline/{number}.json"
        b = read(EV / rel)
        f = b["freshResult"]
        req = HERE / "requests" / (name + ".request")
        require(b["compareExit"] == 0 and f["status"] == "established", number)
        require(all(o["expected"] == o["obtained"] for o in f["obligations"]), number + " obligations")
        case(
            "Historical Python/Z3",
            digest((HERE / "inputs" / (name + ".bin")).read_bytes()),
            digest(req.read_bytes()),
            name,
            f["rules"]["sha256"],
            "established",
            f["status"],
            [o["obtained"] for o in f["obligations"]],
            rel,
        )
    scalar = read(EV / "scalar/measurements.json")
    for r in scalar["cases"]:
        require(
            len(r["checks"]) == 3 and r["classSha256"] == digest((HERE / "inputs/Scalar.bin").read_bytes()),
            "scalar binding",
        )
        case(
            r["route"],
            r["classSha256"],
            r["requestSha256"],
            r["control"],
            r["checkerVersion"],
            r["expected"],
            r["actual"],
            r["outcome"],
            "scalar/measurements.json",
        )
    for phase in ("freeze", "transfer"):
        rel = phase + "/results.json"
        phase_data = read(EV / rel)
        for row in phase_data["cases"]:
            base = EV / phase / row["control"]
            for key, name in [
                ("classSha256", "artifact.bin"),
                ("certificateSha256", "evidence.cert"),
                ("requestSha256", "external.request"),
            ]:
                require(digest((base / name).read_bytes()) == row[key], phase + " " + name)
            require(
                len(row["checks"]) == 3
                and row["originalJvm"]["stdout"][0] == "entered " + row["classSha256"],
                "JVM class identity",
            )
            case(
                "Rust",
                row["classSha256"],
                row["requestSha256"],
                row["control"],
                row["checkerVersion"],
                row["expected"],
                row["actual"],
                row["outcome"],
                rel,
            )
            old = row["unchangedProducer"]
            # These are observed historical outcomes, with expectations fixed by the input and rule coverage.
            expected = {
                "Ints": "established",
                "Longs": "established",
                "last": "unsupported",
                "start": "unsupported",
                "miss": "unresolved",
                "frame": "unresolved",
                "stuck": "unresolved",
                "narrow": "unsupported",
                "layout": "unsupported",
                "same-store": "established",
            }
            case(
                "Historical rebound rule",
                row["classSha256"],
                row["requestSha256"],
                phase + "/" + row["control"],
                core_version(),
                expected[row["control"]],
                old["actual"],
                old.get("reason") or [o for o in old["obligations"] if o["obtained"] != o["expected"]],
                rel,
            )
        for r in phase_data["substitutions"]:
            case(
                "Rust",
                r["classSha256"],
                r["requestSha256"],
                r["control"],
                r["checkerVersion"],
                r["expected"],
                r["actual"],
                r["stdout"],
                rel,
            )
    frozen = read(EV / "freeze/results.json")
    final = read(EV / "transfer/results.json")
    for name in ("Ints", "Longs"):
        r = read(EV / "pretransfer" / (name + ".json"))
        result = next(q for q in frozen["cases"] if q["control"] == name)
        require(
            r["binarySha256"] == frozen["rustBuild"]["binarySha256"] and r["stdout"] == result["outcome"],
            "pre-edit attempt",
        )
    fault = final["experimentalIssuerFault"]
    case(
        "Rust",
        fault["classSha256"],
        fault["requestSha256"],
        fault["control"],
        fault["checkerVersion"],
        fault["expected"],
        fault["actual"],
        fault["consumer"]["stdout"],
        "transfer/results.json",
    )
    require(all("Permission denied" in s for s in final["readDenials"].values()), "isolation")
    snapshot_sources(EV / "transfer/sources.tar.gz", final["consumerSources"])
    covered = {}
    for family in ("guava", "prefix-sums"):
        folder = EV / "bounded-sat" / family
        rel = f"bounded-sat/{family}/queries.json"
        q = read(EV / rel)
        require(digest((folder / "proofs.tar.gz").read_bytes()) == q["packSha256"], "LRAT pack")
        require(len(q["queries"]) == q["observed"]["unsat"], "UNSAT coverage")
        with tarfile.open(folder / "proofs.tar.gz") as archive:
            for r in q["queries"]:
                require(
                    digest(archive.extractfile(r["key"] + ".lrat").read()) == r["proofSha256"], "LRAT proof"
                )
                case(
                    "SAT/LRAT",
                    r["classSha256"],
                    r["cnfSha256"],
                    family + "/" + r["key"],
                    r["checkerVersion"],
                    r["expected"],
                    r["actual"],
                    {"query": r["queryOneBased"], "assumptions": r["assumptions"]},
                    rel,
                )
        selected = next(r for r in q["queries"] if r["key"] == q["controls"]["selected"])
        require(
            digest(gzip.decompress((folder / "selected.cnf.gz").read_bytes())) == selected["cnfSha256"],
            "selected DIMACS",
        )
        for k in ["truncatedBeforeEmptyClause", "knownSatisfiable"]:
            raw = q["controls"][k]
            got = "rejected" if "s VERIFIED UNSAT" not in raw["stdout"].splitlines() else "accepted"
            formula = (
                selected["cnfSha256"] if k == "truncatedBeforeEmptyClause" else digest(b"p cnf 1 1\n1 0\n")
            )
            case(
                "SAT/LRAT",
                selected["classSha256"] if k == "truncatedBeforeEmptyClause" else None,
                formula,
                family + "/" + k,
                selected["checkerVersion"],
                "rejected",
                got,
                raw["stdout"],
                rel,
            )
        covered[family] = {
            "observed": q["observed"],
            "certified": len(q["queries"]),
            "withoutSolver": q["decisionsWithoutSolver"],
        }
    prices = read(EV / "costs.json")
    require(
        all(len(r[k]["samples"]) == 3 for r in prices["cases"] for k in ["generation", "checking"]),
        "cost samples",
    )
    replay = read(EV / "clean-replay.json")
    require(
        replay["finalBinary"] == final["rustBuild"]["binarySha256"]
        and replay["frozenBinary"] == frozen["rustBuild"]["binarySha256"],
        "replay binaries",
    )
    optional = read(EV / "range-fill.json")
    for r in optional["cases"]:
        for route, ans, version in [
            ("Historical Python/Z3", r["historical"], r["rulesSha256"]),
            ("Rust", r["independent"], final["rustBuild"]["binarySha256"]),
        ]:
            case(
                route,
                r["classSha256"],
                r["requestSha256"],
                r["control"],
                version,
                ans["expected"],
                ans["actual"],
                ans["reason"],
                "range-fill.json",
            )
        physical = r["physical"]
        actual = "replayed refutation" if physical["observationalMismatches"] else "sampled controls held"
        expected = (
            "replayed refutation" if r["control"] == "caller-extra-any-length" else "sampled controls held"
        )
        case(
            "Temurin 21 JVM",
            r["classSha256"],
            r["requestSha256"],
            r["control"],
            "21.0.13+9",
            expected,
            actual,
            physical["stdout"],
            "range-fill.json",
        )
    rel = "range-proof/results.json"
    transfer = read(EV / rel)
    version = transfer["checker"]["binarySha256"]
    require(transfer["previousGuavaCasesReplayed"] == 18, "range checker Guava regressions")
    frozen_sources = historical_files()
    for name, sha in transfer["consumerSources"].items():
        require(digest(frozen_sources[name]) == sha, "range checker source " + name)
    rows = {r["control"]: r for r in transfer["cases"]}
    require(len(rows) == len(transfer["cases"]) == 14, "range case inventory")
    for control, r in rows.items():
        require(
            r["checkerVersion"] == version and r["reason"].split()[0] == r["actual"],
            "range checker version or disposition",
        )
        folder = EV / "range-proof"
        req = folder / (control + ".request")
        if req.exists():
            cert = folder / (control + ".cert")
            require(
                digest(req.read_bytes()) == r["requestedClaim"]
                and digest(cert.read_bytes()) == r["certificateSha256"],
                "range input binding",
            )
            fields = dict(line.split(" ", 1) for line in req.read_text().splitlines())
            owner, bound = fields["class"].split()
            require(bound == r["classSha256"] and len(r["checking"]["checks"]) == 3, "range class or samples")
            artifact = {
                "fill/Range": "extra.bin" if control == "caller-extra-any-length" else "original.bin",
                "fixtures/RangeLoops": "loops.bin",
            }.get(owner)
            if artifact:
                require(digest((folder / artifact).read_bytes()) == bound, "range class bytes")
            if "callee" in fields:
                require(
                    fields["callee"].split() == ["java/util/Arrays", rows["fill-any-length"]["classSha256"]]
                    and r["calleeClassSha256"] == [rows["fill-any-length"]["classSha256"]],
                    "range callee",
                )
        case(
            r["route"],
            r["classSha256"],
            r["requestedClaim"],
            control,
            version,
            r["expected"],
            r["actual"],
            r["reason"],
            rel,
        )
    physical = transfer["jvm"]["rebound-controls"]
    fixtures = [
        ("saved-local", "savedValue [7, 19]", "sampled control held"),
        ("missing-store", "missingStore [11, 19]", "replayed refutation"),
        ("wrong-value", "wrongValue [0, 19]", "replayed refutation"),
        ("strict-empty-guard", "rejectsEmpty IllegalArgumentException", "replayed refutation"),
        ("wrong-observed-root", "readsFilledRoot ArrayIndexOutOfBoundsException", "replayed refutation"),
    ]
    require(len(physical) == len(fixtures), "JVM range controls")
    for (control, expected, disposition), observed in zip(fixtures, physical):
        require(expected == observed, "JVM range control " + control)
        r = rows[control]
        case(
            "Temurin 21 JVM",
            r["classSha256"],
            r["requestedClaim"],
            control,
            transfer["runtime"],
            disposition,
            disposition,
            observed,
            rel,
        )
    rel = "frame-witness/results.json"
    replayed = read(EV / rel)
    require(replayed["solverSha256"] == Z3, "historical witness solver")
    guava_case = guava_record()
    guava = guava_case["unchangedProducer"]
    jdk = read(FILL / "result.json")
    originals = [
        (
            EV / "frame-witness/guava.smt2",
            guava["formulaSha256"],
            guava["obligations"],
            "preserve the input heap",
            guava_case,
        ),
        (
            FILL / "obligations.smt2",
            jdk["certificateSha256"],
            jdk["obligations"],
            "caller read follows from the proved frame",
            rows["caller-extra-any-length"],
        ),
    ]
    require(len(replayed["cases"]) == len(originals), "historical witness cases")
    for r, (path, pin, obligations, name, source) in zip(replayed["cases"], originals):
        idx, prelude, block = original_scope(path.read_bytes(), pin, obligations, name)
        require(
            r["obligation"] == name
            and r["originalFormulaSha256"] == pin
            and r["zeroBasedQuery"] == idx
            and r["classSha256"] == source["classSha256"]
            and r["checkerVersion"] == source["checkerVersion"]
            and r["historicalStatus"] == "unresolved"
            and digest(block.encode()) == r["originalScopeSha256"],
            "historical witness scope",
        )
        require(
            [c["expected"] for c in r["controls"]] == ["sat", "unsat"], "missing witness or benign control"
        )
        for c in r["controls"]:
            require(
                digest(witness_query(prelude, block, c["bindings"]).encode()) == c["querySha256"],
                "concrete witness query",
            )
            case(
                "Historical Z3 on fixed input",
                r["classSha256"],
                c["querySha256"],
                c["control"],
                Z3,
                c["expected"],
                c["actual"],
                {"obligation": name, "scope": idx, "historicalStatus": r["historicalStatus"]},
                rel,
            )
    keys = {
        (
            r["route"],
            json.dumps(r["classSha256"], sort_keys=True),
            r["requestedClaim"],
            r["control"],
            r["checkerVersion"],
        )
        for r in cases
    }
    require(len(keys) == len(cases), "duplicate case key")
    accounting = read(EV / "bounded-sat/accounting.json")
    require(accounting["corrected"] == covered["guava"]["withoutSolver"] >= 0, "per-pass accounting")
    require({r["purpose"] for r in accounting["individualRuns"]} == {"proof", "probe"}, "missing purposes")
    require(
        all(
            r["attempted"] == r["solverCalls"] + r["settledWithoutSolver"]
            for r in accounting["individualRuns"]
        ),
        "native counters",
    )
    manifest = {}
    for name, expected in sorted(historical_manifest().items(), key=lambda item: Path(item[0])):
        data = frozen_sources[name] if name in frozen_sources else (HERE / name).read_bytes()
        manifest[name] = {"sha256": digest(data), "bytes": len(data)}
        require(manifest[name] == expected, "historical evidence " + name)
    return {
        "schema": "trusted-kernel-cases/v1",
        "bundle": manifest,
        "dependencies": {
            "sharedRustSource": {
                "path": "lib/src/digest.rs",
                "sha256": final["consumerSources"]["digest.rs"],
            },
            "rustc": final["rustVersion"],
            "lean": scalar["leanVersion"],
            "leanExecutableSha256": "db7f559d05795e7af52e42bc966c90240a39dcb9712161c54c97afa546e20c00",
            "leanReleaseFileInventorySha256": "38587f83017b1d58cc4dd24092a12e5c2207504af7a412bf17cad05cb5ad8a35",
            "satGenerator": {
                "version": "CaDiCaL 1.9.5",
                "sha256": "0fabbda6d757d7076ca003c8e9ffadd4ef893c3cacaabcf5986c415e0de74ec4",
            },
            "satChecker": {
                "revision": "033aad53",
                "sha256": "c14ff49853e890436d6a2fbf66a85b9492dad1dcd2d76254f16a89f2236c8a54",
            },
        },
        "verification": job_ledger(),
        "key": ["route", "classSha256", "requestedClaim", "control", "checkerVersion"],
        "cases": cases,
        "coverage": covered,
        "cleanReplay": replay,
        "prices": "costs.json",
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    path = EV / "cases.json"
    data = report()
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        require(path.read_text() == content, "stale case table")
    else:
        path.write_text(content)
    print(len(data["cases"]), "keyed cases", data["coverage"])
