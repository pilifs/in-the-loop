"""Qualify concrete int and int[] witnesses on each revision's own ordered classpath."""

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
    return params is not None and all(t in ("int", "int[]") for t in params)


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
        else:
            literal = str(value)
        statements.append(f'{arg["type"]} {arg["name"]} = {literal};')
    condition = claim.get("assume") or "true"
    statements.append(f'if (!({condition})) {{ System.out.println("outside"); return; }}')
    ret = "long" if descriptor.endswith("J") else "int"
    statements.extend([f"{ret} result = 0;", "Throwable failure = null;",
                       f'try {{ result = {owner}.{method}({", ".join(names)}); }} catch (Throwable t) {{ failure = t; }}',
                       'System.out.println("admitted");'])
    selected = claim.get("observations") or ["result", "exception"]
    if claim.get("assert"):
        statements.append(f'System.out.println(failure == null && ({claim["assert"]}));')
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
