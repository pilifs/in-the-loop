"""Compare a typed source claim with what the verifier and the JVM actually examined."""


def alias_groups(pairs):
    groups = []
    for pair in pairs:
        group = set(pair)
        overlap = [g for g in groups if g & group]
        for g in overlap:
            group.update(g)
            groups.remove(g)
        groups.append(group)
    return sorted(sorted(g) for g in groups)


def witness_problem(inputs, parameters, nullable, aliases, bound):
    if not isinstance(inputs, list) or len(inputs) != len(parameters):
        return "the JVM witness does not give every planned root"
    for i, (value, expected) in enumerate(zip(inputs, parameters)):
        if not isinstance(value, dict) or (value.get("name"), value.get("type")) != (expected["name"], expected["type"]) or "value" not in value:
            return "the JVM witness does not identify the planned roots by name and type"
        name, data = expected["name"], value["value"]
        if data is None:
            if expected["type"] == "int" or name not in nullable:
                return f"{name} is null outside its planned domain"
        elif isinstance(data, dict):
            earlier = data.get("same")
            if (expected["type"] != "int[]" or set(data) != {"same"} or type(earlier) is not int or not 0 <= earlier < i
                    or inputs[earlier]["type"] != expected["type"] or inputs[earlier]["value"] is None
                    or not any(name in group and inputs[earlier]["name"] in group for group in aliases)):
                return f"{name} has an alias outside its planned domain"
        elif expected["type"] == "int":
            if type(data) is not int or not -(2**31) <= data < 2**31:
                return f"{name} is outside the planned int domain"
        elif expected["type"] == "int[]":
            if not isinstance(data, list) or len(data) > bound or not all(type(n) is int and -(2**31) <= n < 2**31 for n in data):
                return f"{name} is outside the planned int-array domain at bound {bound}"
        else:
            return f"witness membership for {expected['type']} needs qualification"
    return None


def check(claim, task, outcome, length):
    """Return the first qualification failure for an explicit observation claim, or None."""
    from accept import descriptor_parameters, same_target
    selected = claim.get("observations") or []
    stated = outcome.get("stated") or {}
    environment = claim.get("boundEnvironment") or {}
    actual_models = stated.get("models") or {}
    if ("jdk" in environment and actual_models.get("jdk") != environment["jdk"]
            or "modelDigest" in environment and actual_models.get("digest") != environment["modelDigest"]):
        return "the executed JDK or model differs from the bound environment"
    assumptions = stated.get("assumptions") or []
    if any(a not in assumptions for a in environment.get("assumptions", [])):
        return "the executed statement lacks a bound environment assumption"
    if not selected or not isinstance(selected[0], dict):
        return None
    spec = stated.get("spec") or {}
    contract = spec.get("contract") or {}
    if spec.get("observations") != selected:
        return "the executed observation descriptors differ from the frozen claim"
    def observation_id(o):
        kind = o["kind"]
        if kind == "array-parameter":
            return "array:" + o["parameter"]
        if kind == "field-path":
            return "field:" + o["path"]
        if kind == "effect":
            return "effect:" + o["call"]
        if kind == "identity":
            return "identity:" + o["left"] + "==" + o["right"]
        return kind
    if contract.get("required") != [observation_id(o) for o in selected] or contract.get("approved_changes"):
        return "the executed contract changed which observations must agree"
    target = task["target"]
    if not same_target(contract.get("subject", ""), target):
        return "the executed preservation contract has a different entry"
    domain = stated.get("domain") or {}
    params = domain.get("parameters")
    declared = descriptor_parameters("(" + target.partition("(")[2]) if "(" in target else None
    if (not isinstance(params, list) or declared is None or [p.get("type") for p in params] != declared
            or contract.get("inputs") != [{"name": p.get("name"), "type": p.get("type"), "derivation": {"kind": "identity"}} for p in params]):
        return "the executed roots or their correspondence differ from the frozen entry"
    aliases = alias_groups([p.split(",") for p in claim.get("mayAlias", [])])
    nullable = set(claim.get("nullable", []))
    if ((domain.get("shared_arrays") is not bool(aliases)) or alias_groups(domain.get("may_alias", [])) != aliases
            or {p.get("name") for p in params if p.get("null")} != nullable):
        return "the executed null or alias policy differs from the frozen domain"
    preconditions = [a.get("text") for a in assumptions if a.get("kind") == "precondition"]
    if preconditions != ([claim["assume"]] if claim.get("assume") else []):
        return "the executed precondition differs from the frozen claim"
    bounds = stated.get("bounds") or {}
    ran = bounds.get("max_array_length")
    if type(length) is not int or type(ran) is not int or any(p.get("max_length") != ran for p in params if p.get("kind") == "array"):
        return "the planned or executed input length is unbound"
    verdict = outcome.get("verdict")
    if verdict == "verified":
        if ran < length:
            return f"an establishment at bound {ran} does not cover bound {length}"
        if bounds.get("complete") is not True or outcome.get("problem") or outcome.get("vacuous") or (stated.get("vacuity") or {}).get("status") != "non-vacuous":
            return "the selected proof is incomplete or lacks non-vacuity evidence"
        unwind = (claim.get("bounds") or {}).get("unwind")
        if unwind is not None and bounds.get("unwind") != unwind:
            return "the executed unwinding differs from the planned proof"
    elif verdict == "violation":
        witness, replay = outcome.get("counterexample") or {}, outcome.get("replay") or {}
        if replay.get("by") != "jvm" or replay.get("reproduced") is not True or witness.get("replay_observations") != selected:
            return "the witness lacks a JVM replay of the frozen observation descriptors"
        if not witness.get("differs") or any(o not in (contract.get("required") or []) for o in witness["differs"]):
            return "the witness identifies no disagreement in the selected observations"
        return witness_problem(witness.get("inputs"), params, nullable, aliases, length)
    return None

def library_bindings_problem(plan, outcome, initializer_classes):
    """Match the native engine's actual library assumptions to the frozen states and the prepared classes."""
    assumptions = (outcome.get("stated") or {}).get("assumptions") or []
    ids = {a["id"] for a in assumptions if a.get("kind") == "library" and a.get("basis") == "engine"
           and isinstance(a.get("id"), str) and a["id"].startswith(("observed-initializer:", "jdk-model:"))}
    expected = {"jdk-model:" + name for name in plan.claim.get("namedModels", [])}
    for revision in plan.revisions:
        prefix = "before." if plan.kind == "equivalence" and revision == plan.revisions[0] else ""
        for name, state in plan.claim.get("observedInitializers", {}).items():
            digest = (initializer_classes or {}).get(revision, {}).get(name)
            if not digest:
                return f"{revision} has no prepared class digest for the observed initializer {name}"
            expected.add(f"observed-initializer:{prefix}{name}:{digest}:{state}")
    if ids != expected:
        return "the executed library assumptions differ from the frozen named models, initializer states or prepared classes"
    return None


def statement_problem(plan, outcome, entry, initializer_classes=None):
    """Compare the raw Rust statement with the requested invocation before publishing an eligible result."""
    from accept import descriptor_parameters, same_target
    if not same_target(outcome.get("target") or "", entry):
        return "the checker reported another method"
    stated = outcome.get("stated") or {}
    checker = (stated.get("checker") or {}).get("engine")
    if checker not in ((plan.engine,) if plan.engine != "auto" else ("native", "jbmc")):
        return "the actual engine differs from the selected strategy"
    if checker == "native" and stated.get("gap_mode") != plan.gaps:
        return "the native checker reported a different gap policy"
    claim = plan.claim
    problem = library_bindings_problem(plan, outcome, initializer_classes)
    if problem:
        return problem
    bounds = claim.get("bounds") or {}
    parameters = (stated.get("domain") or {}).get("parameters") or []
    if "(" in entry and [p["type"] for p in parameters] != descriptor_parameters("(" + entry.partition("(")[2]):
        return "the reported input types differ from the entry descriptor"
    if outcome.get("verdict") == "verified":
        actual = stated.get("bounds") or {}
        if actual.get("complete") is not True or (stated.get("vacuity") or {}).get("status") != "non-vacuous":
            return "the establishment lacks a complete, non-vacuous checked statement"
        if actual.get("unwind") != bounds.get("unwind"):
            return "the checked unwind differs from the claim"
        if any(p.get("kind") == "array" for p in parameters) and actual.get("max_array_length") != bounds.get("maxArrayLength"):
            return "the checked array domain differs from the claim"
    if plan.kind == "equivalence" and not any(isinstance(o, dict) for o in claim.get("observations", [])):
        inner = outcome.get("pair") or outcome
        if claim.get("assume") != (inner.get("assume") or None):
            return "the paired checker precondition differs from the frozen claim"
        if claim.get("allowedChange") and outcome.get("verdict") == "verified":
            outside = (stated.get("vacuity") or {}).get("outside")
            if outside != claim["allowedChange"]:
                return "the eligible statement lacks an independently reached comparison outside the allowed change"
    if plan.kind == "prove":
        if (outcome.get("assume") or None, outcome.get("assert"), outcome.get("throws_checked") or outcome.get("throws") or []) != (
                claim.get("assume") or None, claim.get("assert"), claim.get("throws") or []):
            return "the checker property expressions differ from the claim"
    return check(claim, {"target": entry}, outcome, bounds.get("maxArrayLength"))


def attach_observations(plan, controls, replay):
    """Bind an encoded adapter witness back to the direct input and caller-visible observations."""
    from targets import runtime
    from targets.finite_oracle import Table, project
    from pathlib import Path

    adapter = plan.claim.get("adapter")
    if (not adapter or not replay.get("sides") or set(replay["sides"]) != set(plan.revisions)
            or not all(s.get("admitted") and "values" in s for s in replay["sides"].values())):
        return replay
    oracle = next((c for c in plan.claim["controls"] if c["id"] == adapter["correspondence"] and c["path"].endswith(".json")), None)
    if not oracle:
        return replay
    try:
        path = Path(plan.folder) / oracle["path"]
        if runtime.sha256(path) != oracle["sha256"]:
            raise ValueError("the frozen observation table changed")
        table = Table(path)
        [root] = replay["inputs"]
        if root.get("type") != "int" or type(root.get("value")) is not int:
            raise ValueError("this table uses one integer case ID")
        index = root["value"]
        [(name, field)] = [(k, v) for k, v in table.fields.items() if v.get("entry") == replay["entry"]]
        data = {}
        for rev, side in replay["sides"].items():
            record = next(r for r in controls if r.kind == "jvm-control" and r.revision == rev and r.identities.get("jdkRelease") == replay["jdkRelease"])
            rows = {case["id"]: (case, raw) for case, raw in table.observations(record.observations)}
            case, raw = rows[index]
            expected = table.expected(case, raw, name)
            if side["values"] != [project(raw["direct"][name], expected, field), None]:
                raise ValueError("fresh witness result disagrees with the selected direct observation")
            data[rev] = raw["direct"]
        replay["finiteObservation"] = {"id": index, "input": table.cases[index]["input"], "field": name, "direct": data,
                                       "tableSha256": oracle["sha256"]}
    except (ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        replay.update(reproduced=False, reason=f"finite witness qualification: {error}")
    return replay


def correspondence(plan, prepared, records):
    """Re-evaluate the pinned oracle on all the recorded JVM rows of both prepared classpaths."""
    import hashlib
    import json
    import subprocess
    import sys
    from targets import runtime, runtime_jar
    recipe = plan.claim["adapter"]
    oracle = next(c for c in plan.claim["controls"] if c["id"] == recipe["correspondence"] and c["kind"] == "oracle")
    script = ("import importlib.util,json,sys; "
              "s=importlib.util.spec_from_file_location('oracle',sys.argv[1]); m=importlib.util.module_from_spec(s); "
              "s.loader.exec_module(m); print(json.dumps(m.correspondence(json.load(sys.stdin))))")
    rows = []
    for rev, p in prepared.items():
        actual = [r for r in records if r.kind == "jvm-control" and r.revision == rev]
        if not actual:
            return rows, f"{rev} has no JVM correspondence control"
        where = runtime._preparation_dir(p)
        cp = runtime._checked(where, p)
        ordered = [{"path": a.path, "sha256": a.sha256, "role": a.role} for a in cp]
        adapter = next((a for a in cp if a.role == "adapter"), None)
        if not adapter or not p.source["target"].get("adapterCallsTarget"):
            return rows, f"{rev} lacks a prepared adapter calling the upstream target"
        owner, method, desc = runtime_jar.parse_target(recipe["entry"])
        data = runtime_jar.read_class(where / adapter.path, runtime_jar.internal(owner))
        if not data or (method, desc) not in runtime_jar.methods(data):
            return rows, f"{rev} lacks the declared adapter entry"
        for record in actual:
            ids = record.identities
            if (record.status != "exited" or record.exitCode != 0 or not record.observations
                    or ids.get("classpath") != ordered or ids.get("commit") != p.commit
                    or ids.get("inputs", {}).get("oracleSha256") != oracle["sha256"]):
                return rows, f"{rev} lacks complete correspondence observations on the prepared artifacts"
            source = where / ids["inputs"]["oracle"]
            if not source.resolve().is_relative_to(where.resolve()) or runtime.sha256(source) != oracle["sha256"]:
                return rows, f"{rev} correspondence oracle bytes changed"
            try:
                if source.suffix == ".json":
                    from targets.finite_oracle import Table
                    counts = Table(source).correspondence(record.observations, recipe["entry"])
                else:
                    result = subprocess.run([sys.executable, "-I", "-c", script, str(source)], capture_output=True,
                                            input=json.dumps([json.dumps(o) for o in record.observations]), text=True, timeout=30)
                    counts = json.loads(result.stdout) if result.returncode == 0 else {}
            except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as error:
                return rows, f"{rev} correspondence could not be checked: {error}"
            rows.append({"revision": rev, "entry": recipe["entry"], "adapterSha256": adapter.sha256,
                         "adapterClassSha256": hashlib.sha256(data).hexdigest(), "subject": p.source["target"], "mapping": recipe["mapping"], "jdk": ids["jdkRelease"], **counts})
            if counts != {"cases": recipe["cases"], "disagreements": 0}:
                return rows, f"{rev} failed adapter correspondence on the declared {recipe['cases']} inputs"
    return rows, None
