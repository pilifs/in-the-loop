"""Replay primitive values and integer arrays on each revision's ordered classpath."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from targets import qualification, runtime, runtime_jar
from accept import descriptor_parameters


RETURNS = {"I": ("int", "0", "Long.toString(result)"), "J": ("long", "0", "Long.toString(result)"),
           "Z": ("boolean", "false", "Boolean.toString(result)"),
           "[I": ("int[]", "null", "java.util.Arrays.toString(result)"),
           "[J": ("long[]", "null", "java.util.Arrays.toString(result)"),
           "Ljava/lang/String;": ("java.lang.String", "null",
                                 'result == null ? "null" : java.util.Arrays.toString(result.chars().toArray())')}


def supported(entry, claim):
    _, _, descriptor = runtime_jar.parse_target(entry)
    if not descriptor or descriptor.split(")")[-1] not in RETURNS or claim.get("throws"):
        return False
    params = descriptor_parameters(descriptor)
    return params is not None and all(t in ("boolean", "int", "long", "int[]", "long[]", "java.lang.String") for t in params)


def snapshot_assertion(assertion, inputs, names):
    """For the Java replay, snapshot primitive array cells that the property reads with JML's old operator."""
    if not assertion or "\\old(" not in assertion:
        return assertion, []
    declarations = []
    for index, arg in enumerate(inputs):
        if arg["type"] not in ("int[]", "long[]"):
            continue
        name = arg["name"]
        saved = f"originalArray{index}"
        while saved in names:
            saved += "_"
        # The Rust property harness supports additional old expressions. A replay that cannot express them refuses.
        pattern = r"\\old\(" + re.escape(name) + r"(\[(?:[0-9]+|[A-Za-z_$][A-Za-z0-9_$]*)\]|\.length)\)"
        assertion, count = re.subn(pattern, lambda match: saved + match.group(1), assertion)
        if count:
            declarations.append(f"{arg['type']} {saved} = {name} == null ? null : {name}.clone();")
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


def source(entry, claim, inputs, names, *, argument_expression=None, helper=""):
    """Render a replay of the selected public static entry. Inputs have already been type checked."""
    owner, method, descriptor = runtime_jar.parse_target(entry)
    statements = []
    settings = claim.get("observedRuntime", {})
    if count := settings.get("processors"):
        statements.append(f'if (Runtime.getRuntime().availableProcessors() != {count}) throw new IllegalStateException("processor count");')
    if settings.get("emptyEnvironment"):
        statements.append('if (!System.getenv().isEmpty()) throw new IllegalStateException("process environment");')
    if settings.get("rootWorkingDirectory"):
        statements.append('if (!"/".equals(System.getProperty("user.dir")) || !"/".equals(new java.io.File("").getAbsolutePath())) throw new IllegalStateException("working directory");')
    if settings.get("preinitializeTogether"):
        for name in sorted(claim["observedInitializers"]):
            if not re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*", name):
                raise ValueError("invalid binary name for JVM initialization")
            statements.append(f'Class.forName("{name}", true, ClassLoader.getSystemClassLoader());')
    for arg in inputs:
        value = arg["value"]
        if argument_expression is not None and len(inputs) == 1:
            literal = argument_expression
        elif value is None:
            literal = "null"
        elif isinstance(value, dict):
            literal = names[value["same"]]
        elif isinstance(value, list):
            suffix = "L" if arg["type"] == "long[]" else ""
            literal = "new " + arg["type"] + "{" + ",".join(str(n) + suffix for n in value) + "}"
        elif arg["type"] == "java.lang.String":
            data = value.encode("utf-16-be", "surrogatepass")
            units = [str(int.from_bytes(data[i:i+2], "big")) for i in range(0, len(data), 2)]
            literal = "new String(new char[]{" + ",".join(units) + "})"
        elif type(value) is bool:
            literal = str(value).lower()
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
    ret, initial, render_result = RETURNS[descriptor.split(")")[-1]]
    uses_quantifier = assertion and ("\\forall" in assertion or "\\exists" in assertion)
    result_name = "result"
    if uses_quantifier:
        result_name = "returnedValue"
        while result_name in names:
            result_name += "_"
    statements.extend([f"{ret} {result_name} = {initial};", "Throwable failure = null;",
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
            expr = f'failure == null ? {render_result} : "null"'
        elif kind == "exception":
            expr = 'failure == null ? "null" : ((char)34 + failure.getClass().getName() + (char)34)'
        elif kind == "array-parameter" and o["parameter"] in names:
            expr = f'java.util.Arrays.toString({o["parameter"]})'
        elif kind == "identity" and o["left"] in names and o["right"] in names:
            expr = f'{o["left"]} == {o["right"]}'
        else:
            raise ValueError(f"replay cannot observe {o}")
        statements.append(f"System.out.println({expr});")
    throws = " throws ClassNotFoundException" if settings.get("preinitializeTogether") else ""
    return "class CandidateReplay { public static void main(String[] args)" + throws + " {\n" + "\n".join(statements) + "\n} " + helper + "}\n"


def check(plan, prepared, inputs, work, entry=None, *, checker=None):
    entry = entry or plan.target
    claim = plan.claim
    selected = claim.get("observations") or ["result", "exception"]
    report = {"claimKey": claim.get("key"), "entry": entry, "inputs": inputs, "observations": selected,
              "by": "jvm", "reproduced": False, "sides": {}}
    aliases = qualification.alias_groups([p.split(",") for p in claim.get("mayAlias", [])])
    try:
        if checker is None and not supported(entry, claim):
            raise ValueError("independent replay requires boolean, int, long or integer-array inputs and result")
        jdk = runtime._verifier_jdk(plan, prepared)
        report["jdkRelease"] = jdk["release"]
        work = Path(work)
        work.mkdir(parents=True, exist_ok=True)
        for rev, p in prepared.items():
            where = runtime._preparation_dir(p)
            arts = runtime._checked(where, p)
            original = p.source["target"]["loadedFrom"]
            owner, method, desc = runtime_jar.parse_target(entry)
            if checker is None:
                holder = original if entry == plan.target else next(a.path for a in arts if a.role == "adapter")
            else:
                bound = checker["entryBindings"][rev]
                if bound["entry"] != entry:
                    raise ValueError(f"{rev}: replay entry differs from the bound checker invocation")
                holder = bound["loadedFrom"]
            data = runtime.bound_class(where, p, holder, owner)
            resolved = entry
            if checker is not None:
                if data is None or hashlib.sha256(data).hexdigest() != bound["classSha256"]:
                    raise ValueError(f"{rev}: replay class differs from the bound checker invocation")
                if not desc:
                    candidates = [d for n, d in runtime_jar.methods(data) if n == method]
                    if len(candidates) != 1:
                        raise ValueError(f"{rev}: {entry} has {len(candidates)} declared descriptors")
                    desc = candidates[0]
                    resolved = entry + desc
                if not supported(resolved, claim):
                    raise ValueError(f"{rev}: unsupported JVM witness entry {resolved}")
            names, _ = runtime_jar.parameter_names(data, method, desc)
            if not all(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", n) for n in names):
                raise ValueError("invalid parameter name on the prepared entry")
            params = [{"name": n, "type": t} for n, t in zip(names, descriptor_parameters(desc))]
            problem = qualification.witness_problem(inputs, params, set(claim.get("nullable", [])), aliases,
                                                    claim["bounds"]["maxArrayLength"])
            if problem:
                raise ValueError("domain mismatch: " + problem)
            java = source(resolved, claim, inputs, names)
            path = work / (rev + ".java")
            path.write_text(java)
            if checker is None:
                cp = [a for a in arts if a.path in (original, holder) or a.role in ("dependency", "stub")]
                if entry != plan.target:
                    cp.sort(key=lambda a: a.path != holder)
            else:
                artifacts = {a.path: a for a in arts}
                ordered = checker["classpath"][rev]
                cp = [artifacts[a["path"]] for a in ordered]
                if [a.sha256 for a in cp] != [a["sha256"] for a in ordered]:
                    raise ValueError(f"{rev}: replay classpath differs from the bound checker invocation")
            settings = claim.get("observedRuntime", {})
            flags = [f"-XX:ActiveProcessorCount={settings['processors']}"] if settings.get("processors") else []
            command = [str(Path(jdk["home"]) / "bin/java"), *flags, "-cp", os.pathsep.join(str((where / a.path).absolute()) for a in cp), str(path.absolute())]
            env = {} if settings.get("emptyEnvironment") else runtime._verifier_env(jdk)
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, env=env,
                                    cwd="/" if settings.get("rootWorkingDirectory") else None)
            if result.returncode:
                raise ValueError(f"JVM replay failed on {rev}: {result.stderr[-1000:]}")
            rows = result.stdout.splitlines()
            side = {"entryClassSha256": hashlib.sha256(data).hexdigest(), "classpath": [a.sha256 for a in cp],
                    "program": java, "admitted": bool(rows and rows[0] == "admitted")}
            if checker is not None:
                side["descriptor"] = desc
            if settings:
                side["observedRuntime"] = settings
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
        subject = runtime.bound_class(runtime._preparation_dir(prepared), prepared, classpath[0]["path"], owner)
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
