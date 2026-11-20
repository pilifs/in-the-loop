"""Report a finite table's independent JVM observations, artifact bindings and smallest differing inputs."""

import argparse
import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from targets import route, workflow
from targets.finite_oracle import Table, agrees


def report(folder):
    example = json.loads((folder / "example.json").read_text())
    target = json.loads((folder / "target.json").read_text())
    oracle = next(c["path"] for c in target["controls"] if c["kind"] == "oracle")
    table = Table(folder / oracle)
    runs = []
    for task in (t for t in target["tasks"] if t["kind"] == "replay"):
        plan = route.resolve(folder, example, target, task["id"])
        candidates = sorted((folder / "receipts" / task["id"]).glob("*/result.json"), reverse=True)
        candidate = next((p for p in candidates if json.loads((p.parent / "plan.json").read_text())["key"]
                          == workflow.inputs_key(plan)), None)
        if candidate is None:
            raise ValueError(f"{task['id']} has no JVM replay matching its current inputs")
        dst = candidate.parent
        manifest = json.loads((dst / "records/streams.json").read_text())["streams"]
        records = json.loads((dst / "records/execution.json").read_text())["records"]
        digest = workflow.file_sha256(folder / oracle)
        for r in records:
            if r["kind"] != "jvm-control" or r["exitCode"] != 0:
                raise ValueError(f"JVM control did not complete in {candidate}")
            identity = r["identities"]
            if identity["inputs"]["oracleSha256"] != digest:
                raise ValueError("the replay used a different finite oracle")
            stdout = next(s for s in manifest if s["source"] == r["stdout"])
            path = dst / stdout["kept"]
            if stdout["truncated"] or workflow.file_sha256(path) != stdout["sha256"]:
                raise ValueError("the archived direct JVM observations are incomplete")
            rows = sorted((json.loads(line) for line in path.read_text().splitlines()), key=lambda row: row["id"])
            data = list(table.observations(rows))
            observations = {}
            for name, field in table.fields.items():
                different = [(case, row) for case, row in data
                             if not agrees(row["direct"][name], table.expected(case, row, name), field)]
                result = {"mismatches": len(different)}
                if different:
                    case, row = different[0]
                    result["first"] = {"id": case["id"], "input": case["input"], "direct": row["direct"][name],
                                       "expected": table.expected(case, row, name),
                                       **({"selection": {k: row["direct"][k] for k in sorted(table.selectors)}} if table.selectors else {})}
                if "entry" in field:
                    result["correspondence"] = table.correspondence(rows, field["entry"])
                    if result["correspondence"]["disagreements"]:
                        raise ValueError(f"the adapter for {name} differs from the direct JVM observation")
                observations[name] = result
            runs.append({"task": task["id"], "revision": r["revision"], "cases": len(rows), "observations": observations,
                         "receipt": candidate.relative_to(folder).as_posix(), "stdoutSha256": stdout["sha256"],
                         "jdk": identity["jdk"], "classpath": identity["classpath"]})
    return {"schema": "finite-jvm-calibration/v1", "tableSha256": workflow.file_sha256(folder / oracle), "runs": runs}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number")
    args = parser.parse_args()
    [folder] = list(TOOLS.parent.glob(args.number + "-*"))
    print(json.dumps(report(folder), ensure_ascii=False, indent=2))
