"""Reconstruct the actual standalone JBMC inputs, including pointer identity, on the unmodified JVM."""
import argparse
import json
import os
from pathlib import Path
import tarfile
import tempfile

from measure import EVIDENCE, FAMILIES, ROOT, Claim, Subject, digest, javaenv, library_paths, load, original, replay_witness, stock_scalar, write


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


def checked_replays(archive, record, lane, scope, work, cp, env):
    key, expected = record["task"], record[lane]["target"]["target"]["property"]
    with archive.extractfile(f"raw/{key}/{lane}/target.json") as raw:
        document = json.load(raw)
    hit, = [prop for part in document for prop in part.get("result", []) if prop["property"] == expected and prop["status"] == "FAILURE"]
    trace = hit["trace"]
    entry = "java::" + record[lane]["target"]["entry"] + ":"
    cells = record[lane]["target"]["inputs"]
    inputs = []
    owner, method = record["target"].split("#")
    for param in record["parameters"].split(",") if record["parameters"] else ():
        typ, name = param.strip().split()
        if typ.endswith("[][]"):
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
            for lane in ("packaged", "comparator", "alias"):
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    report = audit(options.evidence)
    dest = options.evidence / "standalone-replays.json"
    if options.check:
        if report != load(dest): raise SystemExit("standalone witness replay changed")
    else:
        write(dest, report)
    print(sum(len(g["replays"]) for g in report.values()), "standalone counterexamples checked on the original JVM")
