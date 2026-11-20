"""Qualify concrete int, long and int[] witnesses on each revision's own ordered classpath."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from targets import qualification, runtime, runtime_jar
from accept import descriptor_parameters


def supported(entry, claim):
    _, _, descriptor = runtime_jar.parse_target(entry)
    if not descriptor or descriptor.split(")")[-1] not in ("I", "J") or claim.get("throws"):
        return False
    params = descriptor_parameters(descriptor)
    return params is not None and all(t in ("int", "long", "int[]") for t in params)


def snapshot_assertion(assertion, inputs, names):
    """For the Java replay, snapshot primitive array cells that the property reads with JML's old operator."""
    if not assertion or "\\old(" not in assertion:
        return assertion, []
    declarations = []
    for index, arg in enumerate(inputs):
        if arg["type"] != "int[]":
            continue
        name = arg["name"]
        saved = f"originalArray{index}"
        while saved in names:
            saved += "_"
        # The Rust property harness supports additional old expressions. A replay that cannot express them refuses.
        pattern = r"\\old\(" + re.escape(name) + r"(\[(?:[0-9]+|[A-Za-z_$][A-Za-z0-9_$]*)\]|\.length)\)"
        assertion, count = re.subn(pattern, lambda match: saved + match.group(1), assertion)
        if count:
            declarations.append(f"int[] {saved} = {name} == null ? null : {name}.clone();")
    if "\\old(" in assertion:
        raise ValueError("independent JVM replay cannot snapshot this old expression")
    return assertion, declarations


def quantified(expression):
    """Render bounded JML quantifiers as short-circuiting Java expressions on the actual replay objects."""
    head = re.compile(r"\(\s*\\(forall|exists)\s+int\s+([A-Za-z_$][\w$]*)\s*;")
    while matches := list(head.finditer(expression)):
        match = matches[-1]
        depth, end = 1, match.end()
        while end < len(expression) and depth:
            depth += int(expression[end] == "(") - int(expression[end] == ")")
            end += 1
        if depth:
            raise ValueError("unterminated JVM witness quantifier")
        kind, variable = match.groups()
        parts = expression[match.end():end - 1].split(";", 1)
        if len(parts) != 2:
            raise ValueError("a JVM witness quantifier requires a range and predicate")
        v = re.escape(variable)
        bound = re.fullmatch(rf"\s*0\s*<=\s*{v}\s*&&\s*{v}\s*<\s*([A-Za-z_$][\w$]*(?:\.length)?|[0-9]+)\s*", parts[0])
        if not bound:
            raise ValueError("JVM witness quantifier needs a zero-based finite range")
        universal = kind == "forall"
        condition = ("!" if universal else "") + "(" + parts[1] + ")"
        replacement = ("((java.util.function.BooleanSupplier) () -> { for (int " + variable + " = 0; "
                       + variable + " < " + bound.group(1) + "; " + variable + "++) { if (" + condition
                       + ") return " + str(not universal).lower() + "; } return " + str(universal).lower()
                       + "; }).getAsBoolean()")
        expression = expression[:match.start()] + replacement + expression[end:]
    if "\\forall" in expression or "\\exists" in expression:
        raise ValueError("unsupported JVM witness quantifier syntax")
    return expression


def source(entry, claim, inputs, names):
    """Render a replay of the selected public static entry. Inputs have already been type checked."""
    owner, method, descriptor = runtime_jar.parse_target(entry)
    statements = []
    for arg in inputs:
        value = arg["value"]
        if value is None:
            literal = "null"
        elif isinstance(value, dict):
            literal = names[value["same"]]
        elif isinstance(value, list):
            literal = "new int[]{" + ",".join(map(str, value)) + "}"
        elif arg["type"] == "long":
            literal = str(value) + "L"
        else:
            literal = str(value)
        statements.append(f'{arg["type"]} {arg["name"]} = {literal};')
    condition = claim.get("assume") or "true"
    if claim.get("allowedChange"):
        condition = f'({condition}) && !({claim["allowedChange"]})'
    statements.append(f'if (!({quantified(condition)})) {{ System.out.println("outside"); return; }}')
    assertion, snapshots = snapshot_assertion(claim.get("assert"), inputs, names)
    statements.extend(snapshots)
    ret = "long" if descriptor.endswith("J") else "int"
    uses_quantifier = assertion and ("\\forall" in assertion or "\\exists" in assertion)
    result_name = "result"
    if uses_quantifier:
        result_name = "returnedValue"
        while result_name in names:
            result_name += "_"
    statements.extend([f"{ret} {result_name} = 0;", "Throwable failure = null;",
                       f'try {{ {result_name} = {owner}.{method}({", ".join(names)}); }} catch (Throwable t) {{ failure = t; }}'])
    if uses_quantifier:
        statements.append(f"final {ret} result = {result_name};")
    statements.append('System.out.println("admitted");')
    selected = claim.get("observations") or ["result", "exception"]
    if assertion:
        statements.append(f'System.out.println(failure == null && ({quantified(assertion)}));')
    for o in selected:
        kind = o if isinstance(o, str) else o["kind"]
        if kind == "result":
            expr = 'failure == null ? Long.toString(result) : "null"'
        elif kind == "exception":
            expr = 'failure == null ? "null" : ((char)34 + failure.getClass().getName() + (char)34)'
        elif kind == "array-parameter" and o["parameter"] in names:
            expr = f'java.util.Arrays.toString({o["parameter"]})'
        elif kind == "identity" and o["left"] in names and o["right"] in names:
            expr = f'{o["left"]} == {o["right"]}'
        else:
            raise ValueError(f"replay cannot observe {o}")
        statements.append(f"System.out.println({expr});")
    return "class CandidateReplay { public static void main(String[] args) {\n" + "\n".join(statements) + "\n} }\n"


def check(plan, prepared, inputs, work, entry=None):
    entry = entry or plan.target
    claim = plan.claim
    selected = claim.get("observations") or ["result", "exception"]
    report = {"claimKey": claim.get("key"), "entry": entry, "inputs": inputs, "observations": selected,
              "by": "jvm", "reproduced": False, "sides": {}}
    aliases = qualification.alias_groups([p.split(",") for p in claim.get("mayAlias", [])])
    try:
        if not supported(entry, claim):
            raise ValueError("this independent replay requires int or int[] arguments and an int or long result")
        jdk = runtime._verifier_jdk(plan, prepared)
        report["jdkRelease"] = jdk["release"]
        work = Path(work)
        work.mkdir(parents=True, exist_ok=True)
        for rev, p in prepared.items():
            where = runtime._preparation_dir(p)
            arts = runtime._checked(where, p)
            original = p.source["target"]["loadedFrom"]
            holder = original if entry == plan.target else next(a.path for a in arts if a.role == "adapter")
            owner, method, desc = runtime_jar.parse_target(entry)
            data = runtime_jar.read_class(where / holder, runtime_jar.internal(owner))
            names, _ = runtime_jar.parameter_names(data, method, desc)
            if not all(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", n) for n in names):
                raise ValueError("invalid parameter name on the prepared entry")
            params = [{"name": n, "type": t} for n, t in zip(names, descriptor_parameters(desc))]
            problem = qualification.witness_problem(inputs, params, set(claim.get("nullable", [])), aliases,
                                                    claim["bounds"]["maxArrayLength"])
            if problem:
                raise ValueError("domain mismatch: " + problem)
            java = source(entry, claim, inputs, names)
            path = work / (rev + ".java")
            path.write_text(java)
            cp = [a for a in arts if a.path in (original, holder) or a.role in ("dependency", "stub")]
            if entry != plan.target:
                cp.sort(key=lambda a: a.path != holder)
            command = [str(Path(jdk["home"]) / "bin/java"), "-cp", os.pathsep.join(str(where / a.path) for a in cp), str(path)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, env=runtime._verifier_env(jdk))
            if result.returncode:
                raise ValueError(f"JVM replay failed on {rev}: {result.stderr[-1000:]}")
            rows = result.stdout.splitlines()
            side = {"entryClassSha256": hashlib.sha256(data).hexdigest(), "classpath": [a.sha256 for a in cp],
                    "program": java, "admitted": bool(rows and rows[0] == "admitted")}
            report["sides"][rev] = side
            if rows == ["outside"]:
                raise ValueError("domain mismatch: the frozen precondition rejects this input")
            if not side["admitted"] or len(rows) != 1 + len(selected) + bool(claim.get("assert")):
                raise ValueError(f"incomplete JVM replay on {rev}")
            side["values"] = [json.loads(value) for value in rows[-len(selected):]]
            if claim.get("assert"):
                side["satisfies"] = json.loads(rows[1])
        sides = list(report["sides"].values())
        if plan.kind == "prove":
            report["reproduced"] = sides[0].get("satisfies") is False
        elif len(sides) == 2:
            report["reproduced"] = sides[0]["values"] != sides[1]["values"]
        if not report["reproduced"]:
            report["reason"] = "the admitted input satisfies the property or agrees on every selected observation"
    except (ValueError, KeyError, TypeError, StopIteration, OSError, subprocess.TimeoutExpired, runtime.Refused) as error:
        report["reason"] = str(error)
    return report


def evidence_problem(plan, bound, checker, replay, candidate):
    """Reconcile the independent JVM projections and their actual class bytes with this frozen claim."""
    entry = checker["checkedEntry"]
    selected = plan.claim.get("observations") or ["result", "exception"]
    if (replay.get("claimKey") != plan.claim.get("key") or replay.get("entry") != entry
            or replay.get("by") != "jvm" or replay.get("jdkRelease") != checker.get("jdkRelease")
            or replay.get("observations") != selected or replay.get("inputs") != candidate.get("inputs")):
        return "the independent JVM replay belongs to another claim, input or JDK"
    if replay.get("reproduced") is not True:
        return replay.get("reason") or "the independent JVM replay rejected the candidate"
    sides = replay.get("sides") or {}
    if set(sides) != set(bound):
        return "the independent JVM replay lacks a revision"
    owner, method, desc = runtime_jar.parse_target(entry)
    inputs = replay["inputs"]
    for rev, (_, prepared, _) in bound.items():
        side = sides[rev]
        classpath = checker["classpath"][rev]
        if side.get("classpath") != [a["sha256"] for a in classpath]:
            return "the independent replay ran different artifacts"
        subject = runtime_jar.read_class(runtime._preparation_dir(prepared) / classpath[0]["path"], runtime_jar.internal(owner))
        if not subject or side.get("entryClassSha256") != hashlib.sha256(subject).hexdigest():
            return "the independently replayed class differs from the checked entry"
        names, _ = runtime_jar.parameter_names(subject, method, desc)
        params = [{"name": n, "type": t} for n, t in zip(names, descriptor_parameters(desc))]
        aliases = qualification.alias_groups([p.split(",") for p in plan.claim.get("mayAlias", [])])
        problem = qualification.witness_problem(inputs, params, set(plan.claim.get("nullable", [])), aliases,
                                               plan.claim["bounds"]["maxArrayLength"])
        if problem:
            return "domain mismatch: " + problem
        if side.get("admitted") is not True or side.get("program") != source(entry, plan.claim, inputs, names):
            return "domain mismatch or a different frozen JVM replay program"
        if not isinstance(side.get("values"), list) or len(side["values"]) != len(selected):
            return "the independent JVM replay lacks selected values"
    ordered = [sides[r] for r in plan.revisions]
    refuted = ordered[0].get("satisfies") is False if plan.kind == "prove" else ordered[0]["values"] != ordered[1]["values"]
    return None if refuted else "the admitted input satisfies the property or agrees on every selected observation"
