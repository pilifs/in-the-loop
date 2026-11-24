"""Bind a native verdict's incremental SAT calls to their original formulas and independently checked answers."""

import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import zipfile

CADICAL_SHA = "0fabbda6d757d7076ca003c8e9ffadd4ef893c3cacaabcf5986c415e0de74ec4"
CAKE_SHA = "c14ff49853e890436d6a2fbf66a85b9492dad1dcd2d76254f16a89f2236c8a54"
CACHE = Path.home() / ".cache/in-the-loop/trusted-kernel/src"
ANSWERS = {"S": "sat", "U": "unsat", "?": "unknown", "F": "constant-false"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def save(path, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    os.replace(stream.name, path)


def tool(variable, name, expected):
    path = Path(os.environ.get(variable, CACHE / name))
    if digest(path.read_bytes()) != expected:
        raise ValueError(f"{path.name}: executable differs from the pinned {expected}")
    return str(path.resolve())


def queries(raw):
    clauses = []
    called = None
    header = False
    for line in raw.decode("utf-8").splitlines():
        if line.startswith("c answer "):
            if called is None:
                raise ValueError("answer without a solve")
            answer = line.split()[2]
            if answer not in {"sat", "unsat", "unknown"}:
                raise ValueError("unknown answer token")
            yield tuple(clauses), called, answer
            called = None
        elif line.startswith("c") or not line:
            continue
        elif line == "p inccnf" and not header:
            header = True
        else:
            if not header or called is not None:
                raise ValueError("interleaved or headerless formula")
            fields = line.split()
            solve = fields[0] == "a"
            lits = [int(s) for s in fields[int(solve) :]]
            if not lits or lits[-1] != 0 or 0 in lits[:-1]:
                raise ValueError("unterminated clause or assumption")
            if solve:
                called = tuple(lits[:-1])
            else:
                clauses.append(tuple(lits[:-1]))
    if called is not None or not header:
        raise ValueError("incomplete transcript")


def dimacs(clauses, assumptions):
    rows = (*clauses, *((a,) for a in assumptions))
    maximum = max((abs(v) for row in rows for v in row), default=0)
    return (
        f"p cnf {maximum} {len(rows)}\n" + "".join(" ".join(map(str, (*row, 0))) + "\n" for row in rows)
    ).encode()


def capture(request, ordinary, work, trace_dir, runs):
    """Anchor every reported native pass to its actual log, attempt ledger and clause stream before issuing proofs."""
    trace_paths = {p.resolve() for p in trace_dir.glob("*.icnf")}
    logs = {}
    for log in sorted(work.rglob("bmc.log")):
        raw = log.read_bytes()
        summaries = [line for line in raw.decode().splitlines() if "; solver calls written to " in line]
        if len(summaries) != 1:
            raise ValueError(f"{log.relative_to(work)}: expected one native solver summary, found {len(summaries)}")
        line = summaries[0]
        summary = re.match(r"^(Verified|Violation|Unverifiable): .*?, ([0-9,]+) solver calls .*?, ([0-9,]+) clauses", line)
        link = re.search(r"; solver boundary \[([SU?F]*)\]; solver calls written to (.+)$", line)
        if not summary or not link:
            raise ValueError(f"{log.relative_to(work)}: missing native call boundary or transcript")
        boundary, filename = link.groups()
        path = Path(filename).resolve()
        if path not in trace_paths:
            raise ValueError(f"{log.relative_to(work)}: native pass has no unique emitted transcript")
        trace_paths.remove(path)
        verdict, attempts, clauses = summary.groups()
        if len(boundary) != int(attempts.replace(",", "")):
            raise ValueError(f"{log.relative_to(work)}: attempt count differs from solver boundary")
        purpose = "probe" if "probe" in log.relative_to(work).parts else "proof"
        logs[path] = {
            "purpose": purpose, "ending": verdict.lower(), "calls": boundary, "clauses": int(clauses.replace(",", "")),
            "nativeLog": log.relative_to(work).as_posix(), "nativeLogSha256": digest(raw),
            "transcriptSha256": digest(path.read_bytes()),
        }
    if trace_paths:
        raise ValueError(f"unmatched native transcript {min(trace_paths).name}")
    if not runs:
        raise ValueError("ordinary verdict records no native pass")
    passes, streams = [], []
    for i, run in enumerate(runs, 1):
        if run.get("checker") != "native":
            raise ValueError(f"pass {i}: unsupported checker {run.get('checker')}")
        # Run::of in deadline.rs distinguishes two ways the native Unverifiable result can end.
        ending = "unverifiable" if run["ended"] in ("out-of-time", "no-verdict") else run["ended"]
        matching = [p for p, info in logs.items() if info["ending"] == ending and
                    info["purpose"] == run["purpose"] and info["clauses"] == run["formula"]["clauses"]]
        if len(matching) != 1:
            raise ValueError(f"pass {i}/{run['purpose']}: {len(matching)} matching native logs")
        path = matching[0]
        passes.append({"id": f"{i}-{run['purpose']}", **logs.pop(path)})
        streams.append(path)
    if logs:
        raise ValueError(f"unmatched native pass {next(iter(logs.values()))['nativeLog']}")
    harnesses = {p.relative_to(work).as_posix(): digest(p.read_bytes()) for p in sorted(work.rglob("*.class"))
                 if "classes" not in p.relative_to(work).parts[:-1]}
    return {"schema": "native-sat-boundary/v1", "requestSha256": identity(request), "ordinary": ordinary,
            "generatedClasses": harnesses, "passes": passes}, streams


def trace_events(raw, run):
    """Reconstruct the active incremental prefix at each call, retaining the *actual* SAT valuation."""
    pass_id = run["id"]
    if digest(raw) != run["transcriptSha256"]:
        raise ValueError(f"{pass_id}: transcript digest")
    lines = raw.decode("utf-8").splitlines()
    end = re.fullmatch(r"c end: (\d+) clauses, (\d+) calls; (\w+).*", lines[-1] if lines else "")
    if not end or int(end[1]) != run["clauses"] or end[3].lower() != run["ending"]:
        raise ValueError(f"{pass_id}: transcript footer differs from native pass")
    clauses_seen = sum(1 for line in lines if line and line[0] in "-0123456789")
    if clauses_seen != run["clauses"] or sum(line.startswith("c end:") for line in lines) != 1:
        raise ValueError(f"{pass_id}: emitted clause count differs from native pass")
    models = {}
    for line in lines:
        if line.startswith("c model "):
            match = re.fullmatch(r"c model (\d+) ([01]*)", line)
            if not match or int(match[1]) in models:
                raise ValueError(f"{pass_id}: malformed or repeated SAT model")
            models[int(match[1])] = match[2]
    stream = iter(queries(raw))
    calls = 0
    for ordinal, decision in enumerate(run["calls"], 1):
        key = f"{pass_id}/{ordinal}"
        status = ANSWERS[decision]
        row = {"key": key, "attempt": ordinal, "status": status}
        if decision == "F":
            yield row, None
            continue
        calls += 1
        query = next(stream, None)
        if query is None or query[2] != status:
            raise ValueError(f"{key}: call boundary expects {status}")
        clauses, units, _ = query
        formula = dimacs(clauses, units)
        row.update(call=calls, clausePrefix=len(clauses), assumptionUnits=list(units), formulaSha256=digest(formula))
        if status == "sat":
            model = models.pop(calls, None)
            if model is None:
                raise ValueError(f"{key}: missing original SAT assignment")

            def holds(lit):
                return abs(lit) <= len(model) and (model[abs(lit) - 1] == "1") == (lit > 0)

            if not all(holds(a) for a in units) or not all(any(holds(lit) for lit in clause) for clause in clauses):
                raise ValueError(f"{key}: original SAT assignment violates the clause prefix or assumption units")
            row["modelSha256"] = digest(model.encode())
        if status == "unknown":
            raise ValueError(f"{key}: solver returned unknown or interrupted")
        yield row, formula
    if next(stream, None) is not None or models or calls != int(end[2]):
        raise ValueError(f"{pass_id}: transcript contains an unmatched model or call")
    if run["ending"] == "unverifiable":
        raise ValueError(f"{pass_id}: native pass ended without a verdict")


def issue(request, boundary, streams, target):
    """Untrusted generator. The independent verifier below reconstructs the expected event sequence anew."""
    generator = None
    if len(streams) != len(boundary["passes"]):
        raise ValueError("native pass count differs from the capture")
    manifest = {"schema": "native-sat-evidence/v1", "requestSha256": identity(request),
                "boundarySha256": identity(boundary), "generatorSha256": None, "events": []}
    with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as pack:
        cnf, proof = Path(temp) / "query.cnf", Path(temp) / "query.lrat"
        for pas, src in zip(boundary["passes"], streams, strict=True):
            raw = Path(src).read_bytes()
            pack.writestr(f"traces/{pas['id']}.icnf", raw)
            for event, formula in trace_events(raw, pas):
                if event["status"] == "unsat":
                    if generator is None:
                        generator = tool("KERNEL_CADICAL", "cadical-1.9.5/build/cadical", CADICAL_SHA)
                        manifest["generatorSha256"] = CADICAL_SHA
                    proof.unlink(missing_ok=True)
                    cnf.write_bytes(formula)
                    done = subprocess.run([generator, "--lrat", "--no-binary", str(cnf), str(proof)],
                                          capture_output=True, text=True, timeout=120)
                    if done.returncode != 20 or "s UNSATISFIABLE" not in done.stdout.splitlines():
                        raise ValueError(f"{event['key']}: generator did not establish UNSAT")
                    data = proof.read_bytes()
                    pack.writestr(f"proofs/{event['key']}.lrat", data)
                    event["proofSha256"] = digest(data)
                manifest["events"].append(event)
        pack.writestr("manifest.json", json.dumps(manifest, separators=(",", ":")))


def verify(request, boundary, target):
    """Verify using the caller's own request and captured boundary, supplied independently of the bundle."""
    checker = None
    if boundary.get("schema") != "native-sat-boundary/v1" or boundary.get("requestSha256") != identity(request):
        raise ValueError("top-level request differs from the retained native boundary")
    ordinary = boundary["ordinary"]
    if (request.get("schema") != "native-sat-request/v1" or not isinstance(request.get("run"), str)
            or not request["run"] or ordinary.get("execution") != request["run"]):
        raise ValueError("native boundary belongs to another execution")
    if not boundary["passes"] or ordinary["status"] not in ("established", "refuted"):
        raise ValueError("ordinary verdict has no eligible completed native passes")
    if ordinary.get("conclusion", {}).get("vacuous") is True:
        raise ValueError("ordinary verdict is vacuous")
    if ordinary["status"] == "refuted" and not any(
            r.get("by") == "jvm" and r.get("reproduced") is True for r in ordinary.get("jvmReplay", [])):
        raise ValueError("ordinary refutation lacks a reproduced original JVM witness")
    with zipfile.ZipFile(target) as pack, tempfile.TemporaryDirectory() as temp:
        cnf, proof = Path(temp) / "query.cnf", Path(temp) / "query.lrat"
        names = pack.namelist()
        duplicates = [name for name, n in collections.Counter(names).items() if n > 1]
        if duplicates:
            raise ValueError(f"duplicate file in the evidence bundle: {duplicates[0]}")
        manifest = json.loads(pack.read("manifest.json"))
        if manifest.get("schema") != "native-sat-evidence/v1" or manifest.get("requestSha256") != identity(request):
            raise ValueError("bundle belongs to another top-level request")
        if manifest["boundarySha256"] != identity(boundary):
            raise ValueError("bundle belongs to another ordinary execution")
        if not isinstance(manifest.get("events"), list):
            raise ValueError("the bundle has no event list")
        rows = iter(manifest["events"])
        required = {"manifest.json"}
        counts = collections.Counter()
        passes = []
        for pas in boundary["passes"]:
            trace = f"traces/{pas['id']}.icnf"
            if trace in required:
                raise ValueError(f"{pas['id']}: repeated native pass identity")
            required.add(trace)
            if trace not in names:
                raise ValueError(f"{pas['id']}: missing transcript")
            per_pass = collections.Counter()
            for expected, formula in trace_events(pack.read(trace), pas):
                key, status = expected["key"], expected["status"]
                item = next(rows, {})
                if not isinstance(item, dict) or item.get("key") != key:
                    raise ValueError(f"{key}: missing or misordered event (found {item.get('key') if isinstance(item, dict) else None})")
                actual = dict(item)
                checksum = actual.pop("proofSha256", None)
                # JSON booleans and integers are distinct even though True == 1 in Python.
                if identity(actual) != identity(expected):
                    field = next(k for k in sorted(actual.keys() | expected.keys()) if k not in actual
                                 or k not in expected or identity(actual[k]) != identity(expected[k]))
                    raise ValueError(f"{key}: {field} differs from the native call")
                if status == "unsat":
                    name = f"proofs/{key}.lrat"
                    if name not in names:
                        raise ValueError(f"{key}: missing LRAT proof")
                    required.add(name)
                    payload = pack.read(name)
                    if digest(payload) != checksum:
                        raise ValueError(f"{key}: proof digest")
                    if checker is None:
                        checker = tool("KERNEL_CAKE", "cake_lpr-033aad53/cake_lpr", CAKE_SHA)
                    cnf.write_bytes(formula)
                    proof.write_bytes(payload)
                    run = subprocess.run([checker, str(cnf), str(proof)], capture_output=True, timeout=120)
                    if run.returncode != 0 or b"s VERIFIED UNSAT" not in run.stdout.splitlines():
                        raise ValueError(f"{key}: cake_lpr did not verify this exact formula and its assumption units")
                elif checksum is not None:
                    raise ValueError(f"{key}: unexpected proof on {status}")
                counts[status] += 1
                per_pass[status] += 1
            passes.append({"id": pas["id"], "solverFree": not any(k in per_pass for k in ("sat", "unsat", "unknown")),
                           "attempts": len(pas["calls"]), "answers": dict(per_pass)})
        for extra in rows:
            label = extra.get("key") if isinstance(extra, dict) else repr(extra)
            raise ValueError(f"unmatched event after the final native pass: {label}")
        for name in names:
            if name not in required:
                raise ValueError(f"unmatched file after the final native pass: {name}")
    return {"status": "checked", "ordinary": ordinary["status"], "requestSha256": identity(request),
            "boundarySha256": identity(boundary), "checkerSha256": CAKE_SHA if checker else None,
            "unsatCoverage": "all UNSAT answers certified" if counts["unsat"] else "no UNSAT calls",
            "satModelsChecked": counts["sat"], "answers": dict(counts), "passes": passes}


def complete(folder, request, boundary, streams):
    """Publish the certificate only after a fresh process checked the caller-bound evidence."""
    save(folder / "boundary.json", boundary)
    start = time.monotonic()
    issue(request, boundary, streams, folder / "evidence.zip")
    generated = time.monotonic()
    checked = subprocess.run([sys.executable, "-B", __file__, "--check", str(folder / "request.json"),
                              str(folder / "boundary.json"), str(folder / "evidence.zip")], capture_output=True, text=True)
    if checked.returncode:
        raise ValueError(checked.stderr.strip() or "fresh verification process failed")
    result = json.loads(checked.stdout)
    result.update(generationSeconds=generated - start, freshCheckSeconds=time.monotonic() - generated,
                  bundleBytes=(folder / "evidence.zip").stat().st_size)
    save(folder / "assurance.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", required=True, nargs=3, metavar=("REQUEST", "BOUNDARY", "BUNDLE"), type=Path)
    args = parser.parse_args()
    request_path, boundary_path, pack_path = args.check
    try:
        result = verify(json.loads(request_path.read_text()), json.loads(boundary_path.read_text()), pack_path)
    except (OSError, ValueError, KeyError, IndexError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        sys.exit(f"LRAT assurance withheld: {error}")
    print(json.dumps(result))
