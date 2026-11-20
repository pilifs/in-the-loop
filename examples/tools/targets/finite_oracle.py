"""An explicit finite JVM domain with independent expected observations for every input.

A driver emits JSON rows containing id, input, direct and (for adapters) adapter.
The direct fields carry their JSON types unchanged. An adapter entry may expose
an exact integer, a finite alphabet index, or agreement with a per-input value.
"""

import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def project(value, expected, field):
    encoding = field["encoding"]
    if encoding == "matches":
        return int(canonical(value) == canonical(expected))
    if encoding == "integer" and type(value) is int:
        return value
    if encoding in ("index", "digits"):
        alphabet = [canonical(cell) for cell in field["alphabet"]]
        if not alphabet or len(set(alphabet)) != len(alphabet):
            raise ValueError("the observation alphabet must contain distinct values")
        if encoding == "index":
            return alphabet.index(canonical(value))
        if not isinstance(value, list) or not isinstance(expected, list) or len(value) != len(expected):
            raise ValueError("the sequence projection requires the declared input's fixed length")
        code = 0
        for element in value:
            code = code * len(alphabet) + alphabet.index(canonical(element))
        return code
    raise ValueError(f"invalid observation encoding or value for {encoding}")


class Table:
    def __init__(self, path):
        spec = json.loads(Path(path).read_text())
        if spec["schema"] != "finite-jvm-observations/v1":
            raise ValueError("unknown finite JVM observation format")
        self.fields = spec["fields"]
        self.cases = {case["id"]: case for case in spec["cases"]}
        if (not self.fields or not self.cases or len(self.cases) != len(spec["cases"])
                or any(type(case["id"]) is not int or set(case["expected"]) != set(self.fields)
                       for case in spec["cases"])):
            raise ValueError("the finite domain needs distinct integer IDs and every expected field")
        entries = [field["entry"] for field in self.fields.values() if "entry" in field]
        if len(set(entries)) != len(entries):
            raise ValueError("two fields select the same adapter entry")

    def driver_args(self):
        return ["--all"]

    def observations(self, rows):
        pending = dict(self.cases)
        for row in rows:
            index = row["id"]
            if type(index) is not int or index not in pending:
                raise ValueError(f"unknown or duplicate input ID {index!r}")
            case = pending.pop(index)
            if canonical(row["input"]) != canonical(case["input"]) or set(row["direct"]) != set(self.fields):
                raise ValueError(f"input or observation descriptors differ at {index}")
            yield case, row
        if pending:
            raise ValueError(f"{len(pending)} finite inputs missing")

    def problems(self, rows):
        return [[case["id"], name] for case, row in self.observations(rows) for name in self.fields
                if canonical(row["direct"][name]) != canonical(case["expected"][name])]

    def correspondence(self, rows, entry):
        fields = [(name, field) for name, field in self.fields.items() if field.get("entry") == entry]
        if len(fields) != 1:
            raise ValueError(f"the table has no unique projection for {entry}")
        name, field = fields[0]
        mismatches = 0
        for case, row in self.observations(rows):
            value = row["adapter"][name]
            direct = project(row["direct"][name], case["expected"][name], field)
            mismatches += type(value) is not int or value != direct
        return {"cases": len(self.cases), "disagreements": mismatches}
