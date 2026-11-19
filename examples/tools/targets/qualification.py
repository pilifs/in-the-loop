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
            if name not in nullable:
                return f"{name} is null outside its planned domain"
        elif isinstance(data, dict):
            earlier = data.get("same")
            if (set(data) != {"same"} or type(earlier) is not int or not 0 <= earlier < i
                    or inputs[earlier]["value"] is None
                    or not any(name in group and inputs[earlier]["name"] in group for group in aliases)):
                return f"{name} has an alias outside its planned domain"
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
