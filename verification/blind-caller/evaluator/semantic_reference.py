"""Derive private finite reference obligations from registered histories and attributed upstream declarations."""
import argparse
import base64
import os
from pathlib import Path
import re
import subprocess
import tempfile

from eligibility_inventory import CACHE, HERE, JDKS, example, read, write
from reference_rows import capture, reference


JDK = JDKS / "25.0.5.0+8-tem"
SOURCE = HERE / "ReferenceFacts.java"
ADDITIVE_LABEL = re.compile(r"(?<![\w.])([A-Za-z][A-Za-z0-9_.]{0,35})=([^\s,;|\]}]*)")


def numeric(value):
    if value in ("true", "false"):
        return value == "true"
    if value == "null":
        return None
    if re.fullmatch(r"-?(?:0|[1-9][0-9]{0,15})", value):
        return int(value)
    return value


def translated_args(history):
    literal = [m[1] for m in re.finditer(r"`([^`]+)`", history)]
    values = []
    for value in literal:
        distinct = numeric(value)
        if any(isinstance(v, dict) and type(v["value"]) is type(distinct) and v["value"] == distinct for v in values):
            continue
        typ = ("boolean" if type(distinct) is bool else "integer" if type(distinct) is int else
               "null" if distinct is None else "registered literal or expression")
        values.append({"name": f"registered literal {len(values)+1}", "type": typ, "value": distinct})
    return [{"name": "registered public input and prestate", "type": "public history constraint", "constraint": history}, *values]


def static_facts(row, record, classes, directory):
    folder = example(row["number"])
    runtime = read(folder / "runtime.json")
    deployment = next(iter(runtime["deployments"].values()))
    side = deployment.get("compileAgainst", "fix")
    files = sorted((folder / "caller").rglob("*.java"))
    keys = set(read(folder / "observations.json")["inputs"])
    files = [f for f in files if f.relative_to(folder).as_posix() in keys]
    original = [CACHE / runtime["cache"] / name for name in deployment["classpath"][side]]
    primary = record["questions"][record["primaryIndex"]]
    directory.mkdir()
    (directory / "source-files").write_text("\n".join(map(str, files)))
    (directory / "arguments").write_text("\n".join(base64.b64encode(a.encode()).decode() for a in primary["privateCallerArgs"]))
    (directory / "classpath").write_text(os.pathsep.join(map(str, original)))
    if not files:
        return [], [], "Java historical source unavailable"
    run = subprocess.run([JDK / "bin/java", "-XX:ActiveProcessorCount=2", "-Xmx256m", "-cp", classes, "ReferenceFacts", directory],
                         capture_output=True, timeout=25)
    if run.returncode:
        return [], [], "original source attribution incomplete"
    actions, inputs, errors = [], [], 0
    for line in (directory / "facts").read_text().splitlines():
        values = [base64.b64decode(v).decode() for v in line.split("\t")]
        if values[0] == "action":
            _, selector, ret, branch, receiver, assigned, args = values
            actions.append({"member": selector, "type": ret, "branch": branch,
                            **({"receiverHandle": receiver} if receiver else {}),
                            **({"resultHandle": assigned} if assigned else {}),
                            **({"argumentHandles": dict(v.split("=") for v in args.split(","))} if args else {})})
        elif values[0] == "argument":
            _, selector, position, typ, value = values
            inputs.append({"member": selector, "position": int(position), "type": typ, "value": value})
        elif values[0] == "analysis":
            errors = int(values[1])
    return actions, inputs, "partially resolved source declarations" if errors else "resolved source declarations"


def entry_selector(label, actions, variants):
    known = {cls for v in variants.values() for b in v["bindings"].values() for cls in b["providers"]}
    owners = {p.rsplit(".", 1)[0] + "." for p in known}
    domain = [a for a in actions if a["member"].split("#", 1)[0] in known or
              any(a["member"].startswith(prefix) for prefix in owners)]
    choices = []
    for a in domain:
        owner, method = a["member"].split("#", 1)
        method = method.split("(")[0]
        simple = owner.rsplit(".", 1)[-1]
        if re.search(r"\b" + re.escape(simple) + r"(?:[.#]" + re.escape(method) + r"\b|\b.*\b" + re.escape(method) + r"\b)", label):
            choices.append(a["member"])
    selected = list(dict.fromkeys(choices))
    return selected[0] if len(selected) == 1 else label, domain, selected


def wire_fields(record, question):
    actual = {v: {s: fields for s, fields in values["actual"].items()} for v, values in question["variants"].items()}
    base = [{"name": "public.outcome", "type": "JVM outcome kind", "readback": "Normal return or escaping exception from the full registered history"},
            {"name": "public.readback", "type": "registered Java return or exception", "readback": question["registeredHistory"]}]
    table = {}
    named = []
    for variant, sides in actual.items():
        table[variant] = {}
        for side, observed in sides.items():
            if len(observed) != 1:
                raise ValueError("historical JVM receipt has an ambiguous outcome")
            field, = observed
            table[variant][side] = {"public.outcome": field["field"], "public.readback": field["value"]}
            pairs = ADDITIVE_LABEL.findall(field["value"]) if isinstance(field["value"], str) else []
            labels = {k: numeric(v) for k, v in pairs if sum(name == k for name, _ in pairs) == 1}
            named.append(labels)
    stable = sorted(set.intersection(*(set(v) for v in named))) if named else []
    for label in stable:
        key = f"public.readback.{label}"
        types = sorted({type(v[label]).__name__ for v in named})
        base.append({"name": key, "type": " | ".join(types), "readback": f"Named {label} component of the independently recorded public observation"})
    for side, names in zip((s for variant in table.values() for s in variant.values()), named, strict=True):
        side.update({f"public.readback.{key}": names[key] for key in stable})
    return base, table


def describe(row, record, classes, directory):
    if record["safetyAbstention"]:
        return {"withheldForSafety": True}
    q = record["questions"][record["primaryIndex"]]
    history = q["registeredHistory"]
    actions, literals, analysis = static_facts(row, record, classes, directory)
    entry, original_api, entries = entry_selector(record["entry"], actions, record["variants"])
    fields, actual = wire_fields(record, q)
    inputs = translated_args(history)
    # Only a literal that the independently registered prestate actually states may
    # enter the reviewed view. Raw historical caller arguments remain evaluator-only.
    for item in literals:
        if item["member"] not in entries or item["value"] not in history or not item["value"]:
            continue
        item = {"name": f"argument {item['position']} of {item['member']}", "type": item["type"], "value": numeric(item["value"])}
        if item not in inputs:
            inputs.append(item)
    registered_steps = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\s+then\s+", history, flags=re.I) if s.strip()]
    selected_calls = [a for a in original_api if a["branch"] == "on selected source branch"]
    witnesses = [{k: a[k] for k in ("member", "receiverHandle", "argumentHandles") if k in a}
                 for a in selected_calls]
    retained = sorted({h for w in witnesses for h in (w.get("receiverHandle", ""), *w.get("argumentHandles", {}).values())
                       if h.startswith("constructed-")})
    needs_actions = (len(selected_calls) > 1 or len(registered_steps) > 1 or bool(re.search(
        r"\b(?:same|retain\w*|reuse\w*|reopen\w*|subscribe\w*|then|after|before)\b", history, re.I)))
    binding = {"publicEntry": entry, "registeredEntry": record["entry"], "sourceCandidateMembers": entries,
               "physicalProviders": sorted({name for v in record["variants"].values() for b in v["bindings"].values() for name in b["providers"]})}
    return {"entry": entry, "history": history, "inputs": inputs, "actions": registered_steps,
            "fields": fields, "bindings": [binding], "observedFields": actual,
            "requiresActionWitness": needs_actions, "actionWitnesses": witnesses,
            "distinctHandles": [[a, b] for i, a in enumerate(retained) for b in retained[i+1:]],
            "publicSourceActions": original_api, "allAttributedPublicCalls": actions, "sourceAttribution": analysis,
            "semanticLimits": "The preserved source identifies public declarations and possible branches. Runtime object identities and alternative routes require independent witnesses. The complete historical encoding and every separately named component remain obligations."}


def build(draw, output, *, also_semantics=None):
    roster = {r["number"]: r for r in read(HERE / "eligibility.json")["rows"]}
    semantics = {}
    with tempfile.TemporaryDirectory(prefix="caller-reference-facts-") as tmp:
        root = Path(tmp)
        classes = root / "classes"
        classes.mkdir()
        subprocess.run([JDK / "bin/javac", "-proc:none", "-d", str(classes), SOURCE], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
        for index, selected in enumerate(draw["cases"]):
            row = roster[selected["number"]]
            ref = reference(row)
            try:
                facts = describe(row, ref, classes, root / str(index))
            except subprocess.TimeoutExpired:
                raise ValueError("the bounded static reference compiler timed out")
            semantics[row["canonicalPR"]] = facts
    if also_semantics:
        write(also_semantics, semantics)
    capture(draw, semantics, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draw", type=Path, default=HERE / "draw.json")
    parser.add_argument("--output", type=Path, default=HERE / "references.json")
    args = parser.parse_args()
    build(read(args.draw), args.output)
