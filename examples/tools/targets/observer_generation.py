"""Materialize a reviewed public history and persist the exact older-API caller for replay."""
import base64
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from targets import change_evidence, change_inventory, deployment_graph, observer_fields, observer_fixtures, observer_recipes, runtime_jdk, upgrade_replay
from targets.change_inventory import digest
from targets.observer_recipes import Unsupported
from targets.upgrade_replay import sha

HERE = Path(__file__).resolve().parent


def identity():
    files = [Path(__file__), HERE / "observer_recipes.py", HERE / "observer_histories.py", HERE / "observer_state.py",
             HERE / "observer_io.py", HERE / "observer_public_data.py", HERE / "observer_structures.py",
             HERE / "observer_fields.py", HERE / "observer_fixtures.py", observer_recipes.TEMPLATE]
    return {p.name: sha(p) for p in files}


def arguments(value):
    """Length-delimited typed tree for String[]. Payload strings can contain every marker."""
    if value is None:
        return ["n"]
    if isinstance(value, bool):
        return ["b" + str(value).lower()]
    if type(value) is int and -(2**31) <= value < 2**31:
        return ["i" + str(value)]
    if isinstance(value, str):
        return ["s" + value]
    if isinstance(value, list):
        return ["a" + str(len(value)), *(w for item in value for w in arguments(item))]
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return ["m" + str(len(value)), *(w for k in sorted(value) for item in (k, value[k]) for w in arguments(item))]
    raise Unsupported("unsupported registered input type")


def wire(value):
    return {"return": json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False)}


def portable_manifest(path):
    doc = json.loads(path.read_bytes())
    for key in ["classpath", "manifestProviders", "environmentFiles"]:
        for item in doc.get(key, []):
            item["file"] = str((path.parent / item["file"]).absolute())
    if "deploymentRoot" in doc:
        doc["deploymentRoot"] = str((path.parent / doc["deploymentRoot"]).absolute())
    return doc


def validate(reg):
    if reg.get("schema") != "reviewed-public-observations/v1":
        raise ValueError("unknown public observation registration")
    required = {"schema", "change", "entry", "changed", "fields", "assumptions", "questions"}
    if reg.keys() != required or not reg["questions"] or not reg["assumptions"]:
        raise ValueError("expected a reviewed entry, changes, fields, assumptions and frozen questions")
    seen = set()
    for q in reg["questions"]:
        if (q.keys() != {"id", "history", "cohort", "sides", "inputs"} or not isinstance(q["id"], str)
                or not q["id"] or q["id"] in seen or q["cohort"] not in {"registered", "control", "additional"}
                or q["sides"] not in (["old"], ["new"], ["old", "new"]) or not q["history"].strip()
                or not isinstance(q["inputs"], list) or not q["inputs"]):
            raise ValueError("a question needs a unique ID, history, cohort, side scope, and input meanings")
        encoded = [tuple(arguments(v)) for v in q["inputs"]]
        if len(set(encoded)) != len(encoded):
            raise ValueError("duplicate inputs in registered history")
        seen.add(q["id"])


def compile_caller(work, src, files, jdk):
    classes = work / "classes"
    classes.mkdir()
    compile_run = subprocess.run([jdk / "bin/javac", "-proc:none", "-encoding", "UTF-8", "-g", "-classpath",
                                  os.pathsep.join(map(str, files)), "-d", classes, src],
                                 cwd=work, capture_output=True, text=True, timeout=45)
    if compile_run.returncode:
        raise Unsupported("older API compiler: " + compile_run.stderr[-2300:])
    members = {}
    with zipfile.ZipFile(work / "caller.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(classes.glob("*.class")):
            if not re.fullmatch(r"UpgradeProbe(?:\$[\w$]+)?\.class", path.name):
                raise ValueError("unexpected generated class")
            members[path.name] = sha(path)
            archive.writestr(zipfile.ZipInfo(path.name), path.read_bytes(), zipfile.ZIP_DEFLATED)
            path.unlink()
    classes.rmdir()
    return members


def generate(reg, before, after, jdk, work, *, fixture_root=None):
    """Operator phase. Receives only reviewed input meanings, classpaths and the pinned JDK."""
    jdk, work = jdk.resolve(), work.resolve()
    packet = reg
    reg, fixtures = observer_fixtures.resolve(packet, work, from_source=fixture_root)
    validate(reg)
    if fixtures:
        change_evidence.write_json(work/"reviewed-packet.json",packet)
    change_evidence.write_json(work / "registration.json", reg)
    record = {"schema": "generated-public-observer/v1", "registration": digest(reg), "generator": identity(),
              "inputPolicy": "reviewed semantic data and public production declarations", "model": None,
              "candidateBudget": observer_recipes.CANDIDATE_BUDGET, "compilePolicy": "once against old",
              "jdkReleaseSha256": sha(jdk / "release"), "status": "open", "rejected": [], "declarations": {},
              "reviewedPacket": digest(packet), "fixtures":fixtures}
    cp = {}
    manifests = {s: portable_manifest(p) for s, p in (("old", before), ("new", after))}
    for side, manifest in manifests.items():
        change_evidence.write_json(work / (side + ".json"), manifest)
    step = "resolve the pinned original deployment"
    try:
        feature = int(runtime_jdk.identity(jdk)["feature"])
        for side, manifest in manifests.items():
            if manifest.get("jdkReleaseSha256", record["jdkReleaseSha256"]) != record["jdkReleaseSha256"]:
                raise Unsupported(f"{side} preparation needs its registered JDK")
            files, _, graph = deployment_graph.resolve(manifest, work, feature, change_inventory.file_digest)
            if graph.get("manifestClassPath", {}).get("unresolved"):
                raise Unsupported(f"{side} needs its original manifest deployment locations")
            cp[side] = files
        inputs = [x for q in reg["questions"] for x in q["inputs"]]
        step = "resolve public construction, operation and field reads"
        api = observer_recipes.API(cp["old"], feature)
        try:
            recipe = observer_recipes.select(reg["entry"], reg["fields"], inputs, api)
        finally:
            record["declarations"]["old"] = api.used
            record["signatureSearch"] = {"inspected": len(api.inspected), "rejectedOverloads": api.rejected}
        record["recipe"] = recipe
        if recipe["family"] == "marked stream and retained destination":
            from targets import entry_discovery, runtime_jar
            owner, name, desc = runtime_jar.parse_target(reg["entry"])
            data = api.definition(owner)
            declaration = entry_discovery.Definition(owner, hashlib.sha256(data).hexdigest(), 0, data)
            calls = declaration.methods()[name, desc][1]
            if ("java/lang/Math", "min", "(II)I") in calls:
                record["helperCandidate"] = {"entry": "java.lang.Math#min(II)I", "consumer": reg["entry"],
                                             "independentOperation": "minimum"}
        # A removed declaration stays measurable on the original-client path; record the gap separately.
        new_api = observer_recipes.API(cp["new"], feature)
        try:
            observer_recipes.select(reg["entry"], reg["fields"], inputs, new_api)
        except Unsupported as e:
            record["newApiGap"] = str(e)
        record["declarations"]["new"] = new_api.used
        src = work / "UpgradeProbe.java"
        src.write_text(observer_recipes.source(recipe))
        record["sourceSha256"] = sha(src)
        record["fieldSources"] = observer_fields.mapping(reg["fields"],recipe,reg["entry"])
        step = "compile once against the older public API"
        record["compiled"] = compile_caller(work, src, cp["old"], jdk)
        record["archiveSha256"] = sha(work / "caller.zip")
        record["status"] = "compiled"
    except (ValueError, OSError, subprocess.TimeoutExpired, zipfile.BadZipFile) as e:
        record["firstOpenDependency"] = str(e)
        record["stoppedAt"] = step
        record["rejected"].append({"entry": reg["entry"], "reason": str(e)})
    change_evidence.write_json(work / "generation.json", record)
    return record


def finite_domain(question, expected):
    sides, inputs = question["sides"], question["inputs"]
    if set(expected) != set(sides) or any(len(values) != len(inputs) for values in expected.values()):
        raise ValueError("prediction differs from the approved side scope or domain: " + question["id"])
    cases = [{"args": arguments(item), "expected": wire(v)} for item, v in zip(inputs, expected[sides[0]], strict=True)]
    changes = [{"input": i, "expectedNew": wire(v)} for i, v in enumerate(expected.get("new", []))
               if len(sides) == 2 and wire(v) != cases[i]["expected"]]
    return cases, changes


def workflows(reg, predictions, work):
    """Evaluator phase. Its only generated files are scopes and workflow declarations."""
    from targets import change_plan
    if set(predictions) != {q["id"] for q in reg["questions"]}:
        raise ValueError("expected predicates must identify exactly the frozen questions")
    recipe = json.loads((work / "generation.json").read_bytes())["recipe"]
    rows = []
    for index, q in enumerate(reg["questions"]):
        cases, changes = finite_domain(q, predictions[q["id"]])
        name = f"scope-{index + 1}.json"
        spec = {"entry": recipe.get("bindingEntry",reg["entry"]), "probeClass": "UpgradeProbe", "observer": ", ".join(reg["fields"]),
                "basis": q["history"], "cases": cases, "assertedSides": q["sides"],
                "generatedObserver": {"file": "generation.json", "sha256": sha(work / "generation.json"), "question": q["id"]}}
        if "invocationVia" in recipe:
            spec["invocationVia"] = recipe["invocationVia"]
        if "requiredDispatch" in recipe:
            spec["requiredDispatch"] = recipe["requiredDispatch"]
        spec["predictionEncoding"] = "typed-public-fields/v1"
        change_evidence.write_json(work / name, spec)
        rows.append(change_plan.workflow_row(q["id"], name, "UpgradeProbe.java", reg["assumptions"], changes,
                                             cohort=q["cohort"]))
    change_evidence.write_json(work / "workflows.json", {"schema": "caller-workflows/v1", "change": reg["change"], "workflows": rows})


def materialize(registration, predictions, before, after, jdk, output):
    """Publish one complete frozen bundle. A failed attempt also has a durable reason."""
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    reg = json.loads(registration.read_bytes())
    if (output / "generation.json").is_file():
        record = json.loads((output / "generation.json").read_bytes())
        expanded, _ = observer_fixtures.resolve(reg, output)
        if (digest(reg) != record.get("reviewedPacket",record["registration"]) or
                json.loads((output / "registration.json").read_bytes()) != expanded
                or any(json.loads((output / (s + ".json")).read_bytes()) != portable_manifest(p)
                       for s, p in (("old", before), ("new", after)))
                or sha(jdk / "release") != record["jdkReleaseSha256"]):
            raise ValueError("a different reviewed experiment needs a new scaffold")
        if record["status"] == "compiled":
            expected = json.loads(predictions.read_bytes())
            with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
                proposed = Path(tmp)
                (proposed / "generation.json").write_bytes((output / "generation.json").read_bytes())
                workflows(expanded, expected, proposed)
                for p in sorted(proposed.glob("*.json")):
                    existing = output / p.name
                    if existing.exists() and existing.read_bytes() != p.read_bytes():
                        raise ValueError("saved predictions differ; re-score the frozen observations in a new evaluation")
                for p in sorted(proposed.glob("scope-*.json")):
                    checked_bundle(output / p.name, json.loads(p.read_bytes()), output / "UpgradeProbe.java")
                for p in sorted(proposed.glob("*.json"), key=lambda p: p.name == "workflows.json"):
                    if not (output / p.name).exists():
                        change_evidence.write_json(output / p.name, json.loads(p.read_bytes()))
        return record
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".public-observer-") as scratch:
        work = Path(scratch) / "bundle"
        work.mkdir()
        record = generate(reg, before, after, jdk, work, fixture_root=registration.parent)
        if record["status"] == "compiled":
            workflows(json.loads((work/"registration.json").read_bytes()), json.loads(predictions.read_bytes()), work)
        try:
            work.rename(output)
        except OSError as error:
            if error.errno not in (errno.EEXIST, errno.ENOTEMPTY) or not (output/"generation.json").is_file():
                raise
            return materialize(registration, predictions, before, after, jdk, output)
    return record


def checked_bundle(scope, spec, probe):
    """Check source, the frozen semantic domain, and the exact older-API class archive before reuse."""
    ref = spec["generatedObserver"]
    root = scope.parent
    if ref["file"] != "generation.json" or ref["sha256"] != sha(root / "generation.json"):
        raise ValueError("generated observer manifest changed")
    record = json.loads((root / "generation.json").read_bytes())
    reg = json.loads((root / "registration.json").read_bytes())
    if record.get("fixtures"):
        packet = json.loads((root/"reviewed-packet.json").read_bytes())
        expanded, fixtures = observer_fixtures.resolve(packet, root)
        if digest(packet) != record["reviewedPacket"] or expanded != reg or record["fixtures"] != fixtures:
            raise ValueError("saved fixture differs from the frozen input meanings")
    if (record.get("schema") != "generated-public-observer/v1" or record.get("status") != "compiled"
            or digest(reg) != record["registration"] or sha(probe) != record["sourceSha256"]
            or sha(root / "caller.zip") != record["archiveSha256"]):
        raise ValueError("generated observer source, registration or compiled archive differs")
    if record["generator"] == identity() and probe.read_text() != observer_recipes.source(record["recipe"]):
        raise ValueError("the caller does not implement the generated public projection")
    q = next((q for q in reg["questions"] if q["id"] == ref["question"]), None)
    if (not q or [arguments(x) for x in q["inputs"]] != [c["args"] for c in spec["cases"]]
            or spec["entry"] != record["recipe"].get("bindingEntry",reg["entry"]) or q["sides"] != spec["assertedSides"]
            or spec["observer"] != ", ".join(reg["fields"]) or q["history"] != spec["basis"]
            or spec.get("invocationVia") != record["recipe"].get("invocationVia")
            or spec.get("requiredDispatch") != record["recipe"].get("requiredDispatch")):
        raise ValueError("generated observer scope differs from the reviewed question")
    return record, reg


def install(root, record, output):
    with zipfile.ZipFile(root / "caller.zip") as archive:
        expected = record["compiled"]
        if sorted(expected) != sorted(archive.namelist()) or "UpgradeProbe.class" not in expected:
            raise ValueError("incomplete compiled caller")
        for name in expected:
            if not re.fullmatch(r"UpgradeProbe(?:\$[\w$]+)?\.class", name):
                raise ValueError("unrelated compiled caller class")
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != expected[name]:
                raise ValueError("compiled observer class differs: " + name)
            (output / name).write_bytes(data)


def numeric_input(mark):
    def text(value):
        return base64.b64decode(value, validate=True).decode("utf-16-be", "surrogatepass")

    spelling, target, *fixture = mark.split("\t")
    kind = target.rsplit(".", 1)[-1]
    package = "java.math." if kind in {"BigInteger", "BigDecimal"} else "java.lang."
    if kind not in observer_recipes.NUMBERS or target != package + kind:
        raise ValueError("unrecognized numeric class at public entry")
    value = {"text": text(spelling), "type": kind}
    if fixture == ["null"]:
        value["format"] = None
    elif fixture:
        if len(fixture) != 4 or fixture[0] != "decimal" or fixture[3] not in ("true", "false"):
            raise ValueError("missing DecimalFormat construction or parsing mode at public entry")
        value["format"] = {"locale": text(fixture[1]), "pattern": text(fixture[2]), "parseBigDecimal": fixture[3] == "true"}
    return value


def formatter_reads(conversions, marks, outcomes):
    """Match each direct getter to this call's argument and normal exit on the original JVM."""
    kinds = {"UPGRADE-FORMAT-ARG", "UPGRADE-NUMBER", "UPGRADE-FORMAT-READ"}
    actions = iter((kind, payload) for line in marks for kind, _, payload in [line.partition(" ")] if kind in kinds)

    def take(kind):
        name, payload = next(actions, (None, None))
        if name != kind:
            raise ValueError("formatter readback is missing or out of order at " + kind)
        return payload.split("\t")

    records = []
    for index, (call, outcome) in enumerate(zip(conversions, outcomes, strict=True)):
        thread, alias = map(int, take("UPGRADE-FORMAT-ARG"))
        take("UPGRADE-NUMBER")
        if "readAfterReturn" in call and outcome[0] == "return":
            reader, receiver, value = take("UPGRADE-FORMAT-READ")
            if (thread != int(reader) or alias != int(receiver) or alias < 0 or value not in ("true", "false")):
                raise ValueError("the getter must read the same retained argument on the calling thread")
            outcome.append(value == "true")
            records.append({"call": index, "argument": 2, "receiverAlias": alias, "threadAlias": thread,
                            "member": observer_recipes.FORMAT_GETTER, "afterNormalReturn": True, "value": outcome[-1]})
    if next(actions, None) is not None:
        raise ValueError("unexpected formatter action after the registered history")
    return records


def correspondence(recipe, inputs, marks, observation):
    """Independent JVM call counts and receiver identities; the scalar projection also reads each return or throw."""
    aliases = [int(m.split()[1]) for m in marks if m.startswith("UPGRADE-PUBLIC-CALL ")]
    if not aliases or set(observation) != {"return"}:
        raise ValueError("no qualified generated public readback")
    values = json.loads(observation["return"])
    if not isinstance(values, list):
        raise ValueError("public observation requires an ordered sequence")
    family = recipe["family"]
    result = {"entryCalls": len(aliases), "receiverAliases": aliases, "observationSha256": digest(values)}
    if family == "typed numeric conversions":
        actual_inputs = [numeric_input(m.partition(" ")[2]) for m in marks if m.startswith("UPGRADE-NUMERIC-INPUT ")]
        conversions = inputs["conversions"]
        if actual_inputs != [{k:v for k,v in call.items() if k != "readAfterReturn"} for call in conversions]:
            raise ValueError("actual numeric arguments at public entry differ from the reviewed conversions")
        result["numericArguments"] = actual_inputs
        events = [m.partition(" ")[2] for m in marks if m.startswith("UPGRADE-NUMBER ")]
        reads = []
        for event in events:
            fields = event.split("\t")
            if fields == ["null"]:
                reads.append(["return", None, None])
            elif len(fields) == 2 and fields[0] == "throws":
                reads.append(fields)
            elif len(fields) == 2:
                reads.append(["return", *fields])
            else:
                raise ValueError("unsupported live numeric representation: " + event)
        if recipe.get("argumentRead") == observer_recipes.FORMAT_GETTER:
            result["argumentReads"] = formatter_reads(conversions, marks, reads)
        if wire(reads) != wire(values) or len(aliases) != len(conversions) or len(reads) != len(aliases):
            raise ValueError("numeric projection disagrees with the returns or exceptions of the live public invocations")
    elif family == "selection and lazy default":
        if (len(aliases) != len(inputs["selections"]) or len(values) != len(aliases)
                or any(len(row) != 3 or type(row[0]) is not bool or type(row[2]) is not int for row in values)):
            raise ValueError("incomplete nullable selection or lazy callback observation")
    elif family == "marked stream and retained destination":
        windows = inputs["readWindowsByEpoch"]
        if (len(aliases) != sum(map(len, windows)) or len(set(aliases)) != 1 or
                len(values) != len(aliases) + len(windows)):
            raise ValueError("read history did not retain the registered stream or all sampling points")
    elif family == "persistent archive rename and reopen":
        if len(aliases) != len(inputs["names"])-1 or len(values) != len(aliases):
            raise ValueError("reopened archive missing after a rename")
    elif family == "weight view and backing graph":
        readers = [int(m.split()[1]) for m in marks if m.startswith("UPGRADE-PUBLIC-READ ")]
        if (len(set(aliases)) != 1 or len(aliases) != len(inputs["writes"]) or len(values) != len(aliases)
                or readers != aliases):
            raise ValueError("writes did not target one retained view throughout the registered history")
    elif family == "commands on one listener-backed state machine":
        if len(set(aliases)) != 1 or len(values) != len(inputs["states"]) + 1:
            raise ValueError("incomplete listener and state history")
    elif family == "class-token write and read":
        if len(values) != 1 or not values[0] or len(aliases) != (
                values[0][1] + 1 if values[0][0] == "write" else len(inputs["classTokens"])):
            raise ValueError("writer did not reach the reported token")
    elif family == "collision subsets on a live map view":
        if len(values) != 2**(inputs["maximumSize"] + 1) - 1 or len(aliases) != 2*len(values) or any(
                a != b for a,b in zip(aliases[::2], aliases[1::2])):
            raise ValueError("missing paired removal on a retained map")
    elif family == "paired mutable-property samples":
        arity = [2,2,2] if inputs["mode"] == "paired mutations" else [3]
        if len(aliases) != 1 or [len(v) for v in values] != arity:
            raise ValueError("missing public samples of the original, copy or recording target")
    elif family == "consume an event-stream response":
        if len(aliases) != len(inputs["streams"]) or len(values) != len(aliases) or any(
                len(v) != 4 or not isinstance(v[0], list) or v[1] not in {"error","complete"} for v in values):
            raise ValueError("missing a subscribed public stream or terminal signal")
    elif family == "reopened block index and sorted hits":
        if len(aliases) < 1 or not values or any(len(v) != 2 or type(v[0]) != int or len(v[1]) != v[0]
                for v in values if v != ["overload-absent"]):
            raise ValueError("missing sorted public hits or total after reopening the index")
    tuples = []
    for line in marks:
        if line.startswith("UPGRADE-HELPER-VALUE "):
            pc, args, returned = line.partition(" ")[2].split("\t")
            tuples.append({"bci": int(pc), "args": list(map(int, args.split(","))), "returned": int(returned)})
    if tuples:
        result["helperObservations"] = tuples
    return result


def rescore(report_path, bundle, predictions):
    """Compatibility entry point for callers of the independent offline evaluator."""
    from targets import observer_rescore
    return observer_rescore.score(report_path, bundle, predictions)


def matches(actual, expected):
    """An approved integer bound can leave the precise stream cursor to the measurement."""
    if set(actual) != {"return"} or set(expected) != {"return"}:
        return actual == expected
    def compare(value, predicate):
        if isinstance(predicate, dict):
            if set(predicate) == {"oneOf"} and isinstance(predicate["oneOf"], list) and predicate["oneOf"]:
                return any(compare(value, option) for option in predicate["oneOf"])
            if set(predicate) == {"differentFrom"}:
                return not compare(value, predicate["differentFrom"])
            if set(predicate) != {"integerAtLeast"} or type(predicate["integerAtLeast"]) != int:
                raise ValueError("unknown typed public-field predicate")
            return type(value) == int and value >= predicate["integerAtLeast"]
        if isinstance(predicate, list):
            return isinstance(value, list) and len(value) == len(predicate) and all(
                compare(v, p) for v, p in zip(value, predicate))
        return type(value) == type(predicate) and value == predicate
    return compare(json.loads(actual["return"]), json.loads(expected["return"]))


def helper_table(plan_file, bundle, jdk):
    from targets import change_helpers, change_plan
    record = json.loads((bundle / "generation.json").read_bytes())
    candidate = record.get("helperCandidate")
    if not candidate or candidate["independentOperation"] != "minimum":
        raise Unsupported("no directly consumed integral minimum in the frozen observer")
    plan = json.loads(plan_file.read_bytes())
    if plan.get("executionState") != "complete":
        raise Unsupported("helper discovery needs completed ordinary JVM replays")
    change_plan.saved_bindings(plan, plan_file.parent)
    seen = set()
    sources = []
    for node in plan["claims"]:
        if node["entry"] != candidate["consumer"] or node.get("status") not in {"established", "refuted"}:
            raise Unsupported("unqualified public consumer: " + node["id"])
        receipt = node["receipt"]
        path = (plan_file.parent / receipt["path"]).resolve()
        if not path.is_relative_to(plan_file.parent.resolve()) or sha(path) != receipt["sha256"]:
            raise ValueError("public helper-discovery receipt differs")
        evidence = json.loads(path.read_bytes())
        if evidence.get("generatedObserver", {}).get("bundle") != sha(bundle / "generation.json"):
            raise ValueError("other generated consumer")
        for side in ("old", "new"):
            for trial in evidence["sides"][side]["trials"]:
                reps = trial.get("publicProjections", [])
                if len(reps) != 2 or not reps[0].get("helperObservations") or reps[0] != reps[1]:
                    raise Unsupported("no repeatable marked helper applications on " + node["id"] + "/" + side)
                for live in reps[0]["helperObservations"]:
                    args = tuple(live["args"])
                    if len(args) != 2 or live["bci"] < 0 or live["returned"] != min(args):
                        raise Unsupported("helper return disagrees with independent minimum at the recorded site")
                    seen.add(args)
        sources.append({"question": node["id"], "receiptSha256": receipt["sha256"]})
    if not seen or sha(jdk / "release") != record["jdkReleaseSha256"]:
        raise Unsupported("no measured tuples on the registered JDK")
    owner = candidate["entry"].split("#")[0]
    data, _ = change_helpers.original_class(owner, [], jdk)
    consumer = candidate["consumer"]
    return {"entry": candidate["entry"], "callFrom": consumer, "startupEntry": consumer, "startupWithin": consumer,
            "requireAllApplications": True, "boundClassSha256": hashlib.sha256(data).hexdigest(),
            "rows": [{"args": list(args), "result": min(args)} for args in sorted(seen)],
            "provenance": {"operation": "minimum of the two independently observed arguments",
                           "premise": "entry of the original public consumer", "receipts": sources}}
