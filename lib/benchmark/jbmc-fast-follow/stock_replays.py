"""Reconstruct the actual standalone JBMC inputs, including pointer identity, on the unmodified JVM."""
import argparse
import json
from pathlib import Path
import tarfile
import tempfile

from measure import EVIDENCE, FAMILIES, JDK, ROOT, Claim, Subject, classpath, command, digest, javaenv, library_paths, load, original, replay_witness, stock_scalar, write


def trace_rows(trace, name, element, bound, driver):
    latest = {}
    for step in trace:
        if step.get("stepType") == "assignment":
            latest[step["lhs"]] = step["value"]
        if step.get("stepType") == "input" and step.get("inputID") == name and step.get("sourceLocation", {}).get("function", "").startswith(driver):
            pointer = step["values"][0]["data"]
            break
    else:
        raise ValueError(f"missing input {name} at {driver}")
    if pointer == "null": return None
    def contents(ptr):
        length = int(latest[ptr + ".length"]["data"])
        if not 0 <= length <= bound:
            raise ValueError(f"standalone trace outside array bound {bound}")
        if length == 0: return []
        backing = latest[ptr + ".data"]["data"]
        return [latest[f"{backing}[{i}L]"] for i in range(length)]
    rows = []
    identities = {}
    for ref in contents(pointer):
        p = ref["data"]
        if p == "null":
            rows.append(None)
        elif p in identities:
            rows.append({"sameCell": identities[p]})
        else:
            identities[p] = len(rows)
            values = [stock_scalar(element, v) for v in contents(p)]
            rows.append([str(v) for v in values] if element == "long" else values)
    return rows


def string_units(trace, name, entry):
    """Read the char backing emitted by JBMC's string-refinement input factory."""
    fields = {}
    buffers = []
    allocated = False
    root = next(step["values"][0]["data"] for step in trace if step.get("stepType") == "input"
                and step.get("inputID") == name and step.get("sourceLocation", {}).get("function", "").startswith(entry))
    if root == "null": raise ValueError("outside the non-null string profile")
    for step in trace:
        if step.get("stepType") == "input" and step.get("inputID") == name and step.get("sourceLocation", {}).get("function", "").startswith(entry):
            break
        if step.get("stepType") != "assignment": continue
        lhs, val = step["lhs"], step["value"]
        fields[lhs] = val
        if lhs == root and not allocated:
            allocated = True
        if allocated and lhs.startswith("nondet_infinite_array_pointer") and val.get("type", "").startswith("char (*)") and val.get("data"):
            buffers.append(val["data"])
    length = int(fields[root + ".length"]["data"])
    if not 0 <= length <= 2: raise ValueError("stock string exceeds frozen bound")
    if not length: return root, []
    backing = fields[root + ".data"].get("data")
    if not backing:
        if len(set(buffers)) != 1: raise ValueError("ambiguous stock char backing")
        backing = buffers[-1]
    materialized = {int(item["index"]): item["value"] for item in fields[backing].get("elements", [])}
    units = []
    for i in range(length):
        val = materialized[i] if i in materialized else fields[f"{backing}[{i}L]"]
        if val.get("width") != 16 or len(val["binary"]) != 16: raise ValueError("invalid stock UTF-16 code unit")
        units.append(int(val["binary"], 2))
    return root, units


def checked_replays(archive, record, lane, scope, work, cp, env):
    key, expected = record["task"], record[lane]["target"]["target"]["property"]
    with archive.extractfile(f"raw/{key}/{lane}/target.json") as raw:
        document = json.load(raw)
    hit, = [prop for part in document for prop in part.get("result", []) if prop["property"] == expected and prop["status"] == "FAILURE"]
    trace = hit["trace"]
    entry = "java::" + record[lane]["target"]["entry"] + ":"
    cells = record[lane]["target"]["inputs"]
    inputs = []
    string_roots = {}
    owner, method = record["target"].split("#")
    for param in record["parameters"].split(",") if record["parameters"] else ():
        typ, name = param.strip().split()
        if typ == "String":
            pointer, units = string_units(trace, name, entry)
            if pointer in string_roots:
                raise ValueError("the independent stock input generator reused a String root")
            string_roots[pointer] = name
            value = {"kind": "string", "units": units}
        elif typ.endswith("[][]"):
            value = trace_rows(trace, name, typ[:-4], scope["maxArrayLength"], entry)
            if lane == "alias" and stock_scalar("boolean", cells["tie"]) and value is not None and len(value) == 2:
                value[1] = None if value[0] is None else {"sameCell": 0}
        else:
            value = stock_scalar(typ, cells[name])
        inputs.append({"type": typ, "value": value})
    claim = Claim(method, record["parameters"])
    subject = Subject(0, owner, "", (claim,))
    replay = replay_witness(subject, claim, {"counterexample": {"inputs": inputs}}, work, cp, env)
    if replay["outcome"] not in ("held", "refuted"):
        raise ValueError(f"{key}: {replay}")
    return dict(replay, property=expected)


def audit(evidence):
    result = {}
    for family, number in FAMILIES.items():
        folder, = (ROOT / "examples").glob(f"{number}-*")
        with tempfile.TemporaryDirectory(prefix="follow-stock-jvm-") as tmp:
            work = Path(tmp)
            env = javaenv()
            cp, _, _ = original(folder, family, work, library_paths(folder, family), work, env)
            for lane in ("packaged", "comparator", "alias", "packaged-22", "arrays"):
                file = evidence / "opening" / family / lane / "measurement.json"
                if not file.exists(): continue
                receipt = load(file)
                if {p.name: digest(p) for p in cp[0].glob("*.class")} != receipt["productClasses"]:
                    raise ValueError(f"{family}: different product bytecode")
                raw = file.with_name("raw.tar.gz")
                if digest(raw) != receipt["rawSha256"]:
                    raise ValueError(f"{family}/{lane}: changed raw report")
                group = {}
                with tarfile.open(raw) as archive:
                    for row in receipt["rows"]:
                        target = row[lane]["target"]
                        if target["status"] != "FAILURE": continue
                        where = work / lane / row["task"]
                        where.mkdir(parents=True)
                        group[row["task"]] = checked_replays(archive, row, lane, row["bounds"], where, cp, env)
                result[f"{family}/{lane}"] = {"job": receipt["job"], "rawSha256": receipt["rawSha256"], "replays": group}
    return result


def assertion_settings(evidence):
    receipt = load(evidence / "successor/rows/paired/measurement.json")
    earlier = load(evidence / "final/rows/paired/measurement.json")
    expected = {
        r["task"] for r in earlier["rows"] if "a JVM-chosen assertion setting" in r["native"]["firstUnproved"]
    }
    if len(expected) != 5:
        raise ValueError("different first row witness boundary")
    (folder,) = (ROOT / "examples").glob("394-*")
    env = javaenv()
    with tempfile.TemporaryDirectory(prefix="row-jvm-settings-") as tmp:
        work = Path(tmp)
        cp, _, _ = original(folder, "rows", work, library_paths(folder, "rows"), work, env)
        if {f.name: digest(f) for f in cp[0].glob("*.class")} != receipt["productClasses"]:
            raise ValueError("different row callers")
        checked = {}
        for r in receipt["rows"]:
            if r["task"] not in expected:
                continue
            owner, method = r["target"].split("#")
            claim = Claim(method, r["parameters"])
            subject = Subject(394, owner, "rows", (claim,), 2, 7)
            where = work / r["task"]
            where.mkdir()
            actual = r["native"]["jvmReplay"]
            replay = replay_witness(
                subject, claim, {"counterexample": {"inputs": actual["inputs"]}}, where, cp, env
            )
            if replay != actual or replay["outcome"] != "refuted":
                raise ValueError("changed original JVM witness")
            code, out, err, _ = command(
                [
                    JDK / "bin/java",
                    "-XX:-UsePerfData",
                    "-da",
                    "-cp",
                    classpath([where / "witness", *cp]),
                    "OriginalWitness",
                ],
                env,
            )
            if code != 0 or out.strip() != b"refuted":
                raise ValueError(f"{method}: assertions disabled: {err.decode()}")
            checked[r["task"]] = {
                "inputs": actual["inputs"],
                "sourceSha256": replay["sourceSha256"],
                "enabled": "refuted",
                "disabled": "refuted",
            }
    return {
        "source": receipt["measuredSource"],
        "job": receipt["job"],
        "jdkModulesSha256": receipt["jdkModulesSha256"],
        "replays": checked,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    standalone = audit(options.evidence)
    reports = {"standalone-replays.json": standalone}
    if (options.evidence / "successor/rows/paired/measurement.json").is_file():
        reports["row-settings.json"] = assertion_settings(options.evidence)
    for name, report in reports.items():
        dest = options.evidence / name
        if options.check:
            if report != load(dest):
                raise SystemExit(f"original JVM replay changed: {name}")
        else:
            write(dest, report)
    print(
        sum(len(g["replays"]) for g in standalone.values()),
        "standalone counterexamples checked on the original JVM",
    )
    if "row-settings.json" in reports:
        print(
            len(reports["row-settings.json"]["replays"]),
            "row counterexamples reproduced with assertions enabled and disabled",
        )
