"""Exhaustively check a bounded integer entry on real JVM bytecode through the public task recipe.

The outer integer envelope is proved by the syntax of the frozen Java guard. The JVM evaluates the
entire guard on each point. Each invocation gets a fresh application class loader on its revision's
ordered classpath. A refutation is also repeated in a separate fresh JVM.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from targets import executions, interfaces, qualification, recipes, replay_candidate, route, runtime, runtime_jar, workflow, workflow_ingest
from targets.finite_oracle import Table, canonical, project

LAUNCHER = Path(__file__).with_name("java") / "IsolatedCases.java"
LIMIT = 4096
CHUNK = 1024


def envelope(guard, name, limit=LIMIT):
    """Prove a superset using only mandatory top-level conjuncts over a signed int and decimal literals."""
    if not guard or re.search(r"[^A-Za-z0-9_$(). \t\n%*/+<>=!&|-]|//|/\*|->|\+\+|--|(?<![<>=!])=(?!=)", guard):
        raise ValueError("the finite checker cannot certify the Java guard syntax")
    level, start, i = 0, 0, 0
    parts = []
    while i < len(guard):
        if guard[i] == "(":
            level += 1
        elif guard[i] == ")":
            level -= 1
            if level < 0:
                raise ValueError("unbalanced guard")
        elif level == 0:
            if guard.startswith("||", i):
                raise ValueError("a top-level disjunction does not imply each interval bound")
            if guard.startswith("&&", i):
                parts.append(guard[start:i].strip())
                i += 1
                start = i + 1
        i += 1
    if level:
        raise ValueError("unbalanced guard")
    parts.append(guard[start:].strip())
    low, high = -(1 << 31), (1 << 31) - 1
    for term in parts:
        m = re.fullmatch(re.escape(name) + r"\s*(<=|>=|==|<|>)\s*(-?(?:0|[1-9][0-9]*))", term)
        if not m:
            continue
        op, n = m.group(1), int(m.group(2))
        if not -(1 << 31) <= n < 1 << 31:
            raise ValueError("interval constant outside signed int")
        if op in ("==", ">=", ">"):
            low = max(low, n + (op == ">"))
        if op in ("==", "<=", "<"):
            high = min(high, n - (op == "<"))
    if type(limit) is not int or limit < 1 or low > high or high - low + 1 > limit:
        raise ValueError(f"no nonempty certified interval of at most {limit} values")
    return low, high


def read_rows(stdout, low, high, fields, property_):
    lines = iter(stdout.splitlines())
    rows = []
    for value in range(low, high + 1):
        if next(lines, None) != f"case {value}":
            raise ValueError(f"missing or unexpected JVM record at {value}")
        status = next(lines, None)
        if status == "outside":
            rows.append({"value": value, "admitted": False})
            continue
        if status != "admitted":
            raise ValueError(f"invalid guard output at {value}")
        row = {"value": value, "admitted": True}
        if property_:
            row["satisfies"] = json.loads(next(lines))
            if type(row["satisfies"]) is not bool:
                raise ValueError("invalid assertion output")
        row["observations"] = [json.loads(next(lines)) for _ in fields]
        rows.append(row)
    if next(lines, None) is not None:
        raise ValueError("unexpected trailing JVM output")
    return rows


def grid_problem(plan, table, controls, sides, entry):
    """Check the independently built direct receiver and the typed adapter at each admitted input."""
    if not table:
        return
    fields = [(k, f) for k, f in table.fields.items() if f.get("entry") == entry]
    if not fields:
        if plan.claim.get("adapter"):
            raise ValueError("the frozen table has no observation for this adapter")
        return
    [(name, field)] = fields
    for rev, side in sides.items():
        record = next(r for r in controls if r.revision == rev)
        observed = {case["id"]: (case, raw) for case, raw in table.observations(record.observations)}
        for row in side["rows"]:
            if row["admitted"]:
                case, raw = observed[row["value"]]
                expect = project(raw["direct"][name], table.expected(case, raw, name), field)
                if row["observations"] != [expect, None]:
                    raise ValueError(f"independent direct observation contradicts the checked projection on {rev}, input {row['value']}")


def run_claim(plan, work, shared, launcher_classes, seconds, case_limit=LIMIT):
    started = time.monotonic()
    recipe = recipes.translate(plan)
    if isinstance(recipe, interfaces.Unsupported):
        raise ValueError(recipe.describe())
    claim = plan.claim
    if (plan.kind not in ("prove", "equivalence") or claim.get("observations") != ["result", "exception"]
            or any(claim.get(k) for k in ("models", "namedModels", "observedInitializers", "boundEnvironment", "assumptions", "allowedChange",
                                            "contracts", "plan", "throws", "nullable", "mayAlias"))
            or not replay_candidate.supported(recipe.entry, claim)):
        raise ValueError("a scalar static int/long result with return and exception observations is required")
    owner, method, desc = runtime_jar.parse_target(recipe.entry)
    if desc not in ("(I)I", "(I)J"):
        raise ValueError("the finite execution strategy requires one int parameter")
    prepared, built = {}, {}
    for rev in plan.revisions:
        p = route.prepare_revision(plan, rev, work / "prepare" / rev, shared["prepared"])
        if isinstance(p, interfaces.Unsupported) or p.stage != "artifacts-ready":
            raise ValueError(p.describe() if isinstance(p, interfaces.Unsupported) else f"{p.failedStage}: {p.diagnostic}")
        prepared[rev] = p
        where = runtime._preparation_dir(p)
        built[rev] = (where, p, runtime._checked(where, p))
    bound = workflow_ingest.bound_revisions(plan, prepared)
    jdk = runtime._verifier_jdk(plan, prepared)
    invocation = recipe.bind(plan, "jvmcontract", built, "verifier", seconds)
    prep_seconds = time.monotonic() - started
    control_key = workflow.canonical_digest({"controls": claim["controls"], "revisions": [
        (r, [(a.path, a.sha256) for a in built[r][2]]) for r in plan.revisions]})
    if control_key not in shared["controls"]:
        controls = runtime.run_controls(plan, prepared, work / "controls")
        if isinstance(controls, interfaces.Unsupported):
            raise ValueError(controls.describe())
        for record in controls:
            problem = workflow_ingest.record_problem(record, bound)
            if problem:
                raise ValueError(problem[1])
        shared["controls"][control_key] = controls
    controls = shared["controls"][control_key]
    table_path = next((c["path"] for c in claim["controls"] if c["kind"] == "oracle" and c["path"].endswith(".json")), None)
    table = Table(Path(plan.folder) / table_path) if table_path else None
    comparisons = []
    if claim.get("adapter"):
        comparisons, problem = qualification.correspondence(plan, prepared, controls)
        if problem:
            raise ValueError(problem)
    controls_seconds = time.monotonic() - started - prep_seconds
    sides, names = {}, {}
    for rev, (where, _, _) in built.items():
        cp = invocation.classpaths[rev]
        data = runtime_jar.read_class(where / cp[0]["path"], runtime_jar.internal(owner))
        if not runtime_jar.method_flags(data, method, desc) & 0x0008:
            raise ValueError("the checked entry is not static")
        [name], _ = runtime_jar.parameter_names(data, method, desc)
        names[rev] = name
        low, high = envelope(claim["assume"], name, case_limit)
        probe = replay_candidate.source(recipe.entry, claim, [{"type": "int", "name": name, "value": "Integer.parseInt(args[0])"}], [name])
        directory = work / rev
        directory.mkdir(parents=True)
        (directory / "CandidateReplay.java").write_text(probe)
        paths = [str(where / a["path"]) for a in cp]
        home = Path(jdk["home"])
        compiled = subprocess.run([str(home / "bin/javac"), "-proc:none", "-cp", os.pathsep.join(paths), "CandidateReplay.java"],
                                  cwd=directory, capture_output=True, text=True, timeout=seconds)
        if compiled.returncode:
            raise ValueError(compiled.stderr[-1200:])
        usage, chunks = {}, []
        prefix = [str(home / "bin/java"), *runtime.CONTROL_FLAGS, "-cp", str(launcher_classes), "IsolatedCases"]
        deadline = time.monotonic() + seconds
        elapsed = 0.0
        width = CHUNK if high - low + 1 > 4096 else high - low + 1
        outs = []
        for first in range(low, high + 1, width):
            last = min(high, first + width - 1)
            stdout = directory / f"out-{first}"
            stderr = directory / f"err-{first}"
            command = [*prefix, str(first), str(last), str(directory), *paths]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("finite JVM exhausted its total deadline")
            measured = {}
            status, code, took = runtime._run_one(command, directory, stdout, stderr, remaining,
                                                  env=runtime._verifier_env(jdk), usage=measured)
            if status != "exited" or code != 0:
                raise ValueError(f"finite JVM {status} ({code}): {stderr.read_text()[-1000:]}")
            chunks.append({"interval":[first,last],"seconds":took,**measured})
            elapsed += took
            usage.update(measured)
            outs.append(stdout.read_bytes())
        (directory / "out").write_bytes(b"".join(outs))
        if len(chunks) > 1:
            usage["chunks"] = chunks
            if all("cpuSeconds" in chunk for chunk in chunks):
                usage["cpuSeconds"] = sum(chunk["cpuSeconds"] for chunk in chunks)
            if all("peakRssBytes" in chunk for chunk in chunks):
                usage["peakRssBytes"] = max(chunk["peakRssBytes"] for chunk in chunks)
        rows = read_rows((directory / "out").read_text(), low, high, claim["observations"], bool(claim["assert"]))
        sides[rev] = {"commit": prepared[rev].commit, "entry": invocation.entries[rev], "classpath": cp, "parameter": name,
                      "program": probe, "probeClassSha256": runtime.sha256(directory / "CandidateReplay.class"),
                      "stdoutSha256": runtime.sha256(directory / "out"), "arguments": command[1:len(runtime.CONTROL_FLAGS)+1],
                      "interval": [low, high], "rows": rows, "seconds": elapsed, **usage}
    grid_problem(plan, table, controls, sides, recipe.entry)
    before = sides[plan.revisions[0]]["rows"]
    if plan.kind == "equivalence":
        after = sides[plan.revisions[1]]["rows"]
        if any(r["observations"][1] is not None for side in (before, after) for r in side if r["admitted"]):
            raise ValueError("an escaping paired exception needs a qualified cross-revision class hierarchy")
        if [(r["value"], r["admitted"]) for r in before] != [(r["value"], r["admitted"]) for r in after]:
            raise ValueError("the two guards admit different finite inputs")
        failed = [a["value"] for a, b in zip(before, after) if a["admitted"] and a["observations"] != b["observations"]]
    else:
        failed = [r["value"] for r in before if r["admitted"] and not r["satisfies"]]
    count = sum(r["admitted"] for r in before)
    if not count:
        raise ValueError("empty admitted domain")
    result = {"status": "refuted" if failed else "established", "entry": recipe.entry, "inputs": count,
              "differences": len(failed), "sides": sides, "jdkRelease": jdk["release"], "correspondence": comparisons,
              "prepareSeconds": round(prep_seconds, 4), "controlSeconds": round(controls_seconds, 4)}
    if failed:
        value = [{"name": names[plan.revisions[0]], "type": "int", "value": failed[0]}]
        replay = replay_candidate.check(plan, prepared, value, work / "witness", recipe.entry)
        replay = qualification.attach_observations(plan, controls, replay)
        checker = {"checkedEntry": recipe.entry, "classpath": invocation.classpaths, "jdkRelease": jdk["release"]}
        problem = replay_candidate.evidence_problem(plan, bound, checker, replay, {"inputs": value})
        if problem:
            raise ValueError(problem)
        result["replay"] = replay
    result["wallSeconds"] = round(time.monotonic() - started, 4)
    if case_limit != LIMIT:
        result["caseLimit"] = case_limit
    return result


def claim_identity(plan):
    locks = {}
    for rev in plan.revisions:
        locked = runtime.lock(plan, rev)
        if isinstance(locked, interfaces.Unsupported) or locked.stage != "source-locked":
            raise ValueError(f"cannot freeze the source lock for {rev}")
        locks[rev] = workflow.canonical_digest(locked.source)
    return {"sourceClaim": plan.claim["key"], "inputsKey": workflow.inputs_key(plan), "revisions": list(plan.revisions),
            "expected": plan.expected, "sourceLocks": locks}


def campaign(folder, example, target, tasks, seconds, retry, stop_after, case_limit=LIMIT):
    plans = [route.resolve(folder, example, target, name) for name in tasks]
    if not tasks or len(set(tasks)) != len(tasks) or any(not isinstance(p, interfaces.TaskPlan) for p in plans):
        raise ValueError("the batch must name distinct plannable tasks")
    attempts = folder / "records/finite-proofs"
    if seconds <= 0 or (stop_after is not None and not 1 <= stop_after < len(tasks)):
        raise ValueError("invalid finite execution budget or interruption point")
    keys = {p.task: claim_identity(p) for p in plans}
    if retry:
        if not executions.ID.fullmatch(retry):
            raise ValueError("invalid prior execution ID")
        prior = json.loads((attempts / retry / "batch.json").read_text())
        if prior["claims"] != keys:
            raise ValueError("the retry changed the frozen claim set or revision bindings")
    batch_id = executions.new_id(executions.now())
    directory = attempts / batch_id
    directory.mkdir(parents=True)
    journal = {"schema": "finite-jvm-batch/v1", "id": batch_id, "retryOf": retry, "order": tasks, "claims": keys,
               "status": "running", "completed": [], "missing": list(tasks), "secondsPerJvm": seconds,
               "launcherSha256": runtime.sha256(LAUNCHER), "scope": "Each integer starts with a fresh application class loader on the pinned runtime and classpath. Intervals above 4096 use consecutive JVM batches on one total deadline."}
    save = lambda: executions.save(directory / "batch.json", journal)
    save()
    shared = {"prepared": {}, "controls": {}}
    ok = True
    with tempfile.TemporaryDirectory(prefix="finite-jvm-") as tmp:
        work = Path(tmp)
        launcher = work / "launcher"
        launcher.mkdir()
        java = runtime.runtime_jdk.home("21")
        if not java:
            journal.update(status="refused", reason="the isolated JVM launcher requires a JDK 21 compiler")
            save()
            return 1
        compiled = subprocess.run([str(Path(java) / "bin/javac"), "--release", "11", "-d", str(launcher), str(LAUNCHER)],
                                  capture_output=True, text=True)
        if compiled.returncode:
            journal.update(status="refused", reason=compiled.stderr[-1000:])
            save()
            return 1
        for p in plans:
            try:
                record = run_claim(p, work / p.task, shared, launcher, seconds, case_limit)
                if retry and (original := attempts / retry / (p.task + ".json")).is_file():
                    predecessor = json.loads(original.read_text())
                    if "sides" in predecessor and (record["jdkRelease"] != predecessor["jdkRelease"]
                            or any(record["sides"][r]["classpath"] != s["classpath"] for r, s in predecessor["sides"].items())):
                        raise ValueError("retry prepared different artifact bytes or JDK")
            except (OSError, ValueError, TypeError, KeyError, StopIteration, runtime.Refused,
                    workflow_ingest.Refused, subprocess.SubprocessError) as e:
                record = {"status": "open", "reason": str(e)}
            record.update(task=p.task, **keys[p.task])
            try:
                validate_record(p, record)
            except (ValueError, KeyError, TypeError) as e:
                record.update(status="open", reason=f"finite evidence rejected: {e}")
            executions.save(directory / (p.task + ".json"), record)
            journal["completed"].append({"task": p.task, "status": record["status"],
                                         "sha256": runtime.sha256(directory / (p.task + ".json"))})
            journal["missing"].remove(p.task)
            save()
            print(f"{example['id']} {p.task} {record['status']} {record.get('inputs', 0)} admitted {record.get('reason', '')[:200]}", flush=True)
            ok &= record["status"] == p.expected
            if stop_after == len(journal["completed"]):
                journal.update(status="interrupted", injected=True)
                save()
                return 75
    journal["status"] = "completed"
    save()
    return 0 if ok else 1


def validate_record(plan, record):
    """Recompute coverage and disposition from the recorded JVM output for the current frozen claim."""
    if record["status"] == "open":
        return
    if any(record.get(k) != v for k, v in claim_identity(plan).items()):
        raise ValueError("the finite evidence is from a different claim or source lock")
    recipe = recipes.translate(plan)
    if record["entry"] != recipe.entry or list(record["sides"]) != list(plan.revisions):
        raise ValueError("wrong checked entry or ordered revisions")
    outputs = []
    for side in record["sides"].values():
        if side["entry"]["entry"] != recipe.entry or not side["classpath"]:
            raise ValueError("missing checked entry or classpath")
        rows = side["rows"]
        name = side["parameter"]
        low, high = envelope(plan.claim["assume"], name, record.get("caseLimit", LIMIT))
        if high - low + 1 > 4096:
            expected_chunks = [[start, min(high, start + CHUNK - 1)] for start in range(low, high + 1, CHUNK)]
            if [chunk["interval"] for chunk in side.get("chunks", [])] != expected_chunks:
                raise ValueError("the recorded JVM batches do not cover the certified interval exactly")
        if side["interval"] != [low, high] or [r["value"] for r in rows] != list(range(low, high + 1)):
            raise ValueError("the finite evidence does not cover its entire integer envelope")
        program = replay_candidate.source(recipe.entry, plan.claim, [{"type": "int", "name": name, "value": "Integer.parseInt(args[0])"}], [name])
        if program != side["program"]:
            raise ValueError("the Java probe differs from the frozen guard, assertion or observer")
        stdout = []
        admitted = {}
        for row in rows:
            n = row["value"]
            stdout.extend([f"case {n}", "admitted" if row["admitted"] else "outside"])
            if row["admitted"]:
                if plan.claim.get("assert"):
                    if type(row["satisfies"]) is not bool:
                        raise ValueError("invalid assertion result")
                    stdout.append(json.dumps(row["satisfies"]))
                values = row["observations"]
                if len(values) != 2 or values[0] is not None and type(values[0]) is not int or values[1] is not None and not isinstance(values[1], str):
                    raise ValueError("invalid return or exception observations")
                stdout.extend(json.dumps(v, ensure_ascii=False) for v in values)
                admitted[n] = row
        import hashlib
        if hashlib.sha256(("\n".join(stdout) + "\n").encode()).hexdigest() != side["stdoutSha256"]:
            raise ValueError("the recorded JVM stream digest differs")
        outputs.append(admitted)
    if not outputs[0] or any(o.keys() != outputs[0].keys() for o in outputs):
        raise ValueError("empty or mismatched admitted inputs")
    if len(outputs) == 1:
        failed = [n for n, row in outputs[0].items() if not row["satisfies"]]
    else:
        if any(row["observations"][1] is not None for side in outputs for row in side.values()):
            raise ValueError("finite paired evidence has an unqualified escaping exception")
        failed = [n for n in outputs[0] if outputs[0][n]["observations"] != outputs[1][n]["observations"]]
    if (record["inputs"], record["differences"], record["status"]) != (len(outputs[0]), len(failed), "refuted" if failed else "established"):
        raise ValueError("the claimed finite disposition did not follow from all observations")
    if failed:
        replay = record["replay"]
        if (replay.get("reproduced") is not True or replay["claimKey"] != plan.claim["key"]
                or replay["entry"] != recipe.entry or replay["jdkRelease"] != record["jdkRelease"]
                or replay["inputs"][0]["value"] != failed[0]):
            raise ValueError("the finite witness lacks its independent JVM qualification")
        for rev, observed in zip(plan.revisions, outputs):
            side = record["sides"][rev]
            actual = replay["sides"][rev]
            if (actual["values"] != observed[failed[0]]["observations"] or actual["admitted"] is not True
                    or actual["classpath"] != [a["sha256"] for a in side["classpath"]]
                    or actual["entryClassSha256"] != side["entry"]["classSha256"]):
                raise ValueError("the fresh JVM replay differs from the enumerated observation or bytes")
        adapter = plan.claim.get("adapter")
        oracle = next((c for c in plan.claim["controls"] if adapter and c["id"] == adapter["correspondence"]), None)
        if oracle and oracle["path"].endswith(".json"):
            table = Table(Path(plan.folder) / oracle["path"])
            joined = replay.get("finiteObservation") or {}
            case = table.cases[failed[0]]
            field = joined.get("field")
            if (field not in table.fields or table.fields[field].get("entry") != recipe.entry
                    or type(joined.get("id")) is not int or joined["id"] != case["id"]
                    or canonical(joined.get("input")) != canonical(case["input"])
                    or joined.get("tableSha256") != oracle["sha256"] or set(joined.get("direct", {})) != set(plan.revisions)):
                raise ValueError("the witness does not identify the frozen direct observation and semantic input")
            for rev, direct in joined["direct"].items():
                expected = table.expected(case, {"direct": direct}, field)
                if replay["sides"][rev]["values"] != [project(direct[field], expected, table.fields[field]), None]:
                    raise ValueError("the decoded direct witness differs from the fresh JVM replay")


def recorded_batches(folder):
    """Collect live journals and manifest-checked archives from unsuccessful pipeline jobs."""
    from targets.claim_history import evidence_folders, has_evidence, read_json
    folder = Path(folder).resolve()
    root = folder.parent.parent
    relative = folder.relative_to(root)
    batches = []
    for directory, manifest in evidence_folders(root, folder):
        for path in sorted((directory / "records/finite-proofs").glob("*/batch.json")):
            if not has_evidence(directory, manifest, relative, path):
                continue
            batch = read_json(path)
            if isinstance(batch, dict) and batch.get("schema") == "finite-jvm-batch/v1" and batch.get("id") == path.parent.name:
                batches.append((path, batch, directory, manifest))
    return batches


def evidence(folder, plan, batches=None):
    """Read linked finite results without treating them as native symbolic results."""
    from targets.claim_history import has_evidence
    folder = Path(folder).resolve()
    relative = folder.relative_to(folder.parent.parent)
    found = []
    seen = set()
    if batches is None:
        batches = recorded_batches(folder)
    for path, batch, directory, manifest in batches:
        item = next((r for r in batch["completed"] if r["task"] == plan.task), None)
        if item is None:
            continue
        file = path.parent / (plan.task + ".json")
        identity = (batch["id"], item["sha256"])
        if identity in seen or not has_evidence(directory, manifest, relative, file):
            continue
        proof = {"batch": batch["id"], "retryOf": batch["retryOf"], "receipt": os.path.relpath(file, folder)}
        try:
            if workflow.file_sha256(file) != item["sha256"]:
                raise ValueError("receipt digest differs")
            seen.add(identity)
            record = json.loads(file.read_text())
            if record.get("reason"):
                proof["recordedReason"] = record["reason"]
            if batch["claims"][plan.task] != claim_identity(plan):
                raise ValueError("the recorded claim or source binding differs")
            validate_record(plan, record)
            proof.update(status=record["status"], inputs=record.get("inputs"), differences=record.get("differences"), scope=batch["scope"])
            if record.get("reason"):
                proof["reason"] = record["reason"]
        except (KeyError, TypeError, ValueError, OSError, StopIteration) as error:
            proof.update(status="ineligible", reason=str(error))
        found.append(proof)
    return sorted(found, key=lambda r: r["batch"])


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number")
    parser.add_argument("--tasks")
    parser.add_argument("--checker-seconds", type=int, default=120)
    parser.add_argument("--max-cases", type=int, default=LIMIT,
                        help="maximum certified selector interval; large intervals run in consecutive JVM batches")
    parser.add_argument("--retry-of")
    parser.add_argument("--stop-after", type=int)
    args = parser.parse_args(argv)
    import build
    from targets import sidecar
    folders = list(build.EXAMPLES.glob(args.number + "-*")) if re.fullmatch(r"[0-9]{3}", args.number) else []
    if len(folders) != 1:
        parser.error("expected the number of a registered example")
    folder = folders[0]
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    if not target:
        parser.error("this example has no target sidecar")
    tasks = args.tasks.split(",") if args.tasks else [t["id"] for t in target["tasks"] if t["kind"] in ("prove", "equivalence")]
    try:
        if args.max_cases <= 0:
            parser.error("--max-cases must be positive")
        return campaign(folder, example, target, tasks, args.checker_seconds, args.retry_of, args.stop_after, args.max_cases)
    except (OSError, ValueError) as error:
        parser.error(str(error))
