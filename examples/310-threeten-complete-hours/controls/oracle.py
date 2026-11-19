"""Read the independently constructed JVM calls and the signed-minute oracle for each complete grid row."""

import json


def driver_args():
    return ["--all"]


def totals(lines):
    rows = [json.loads(line) for line in lines]
    if len(rows) != 193 or set(rows[-1]) != {"forward", "backward"}:
        raise ValueError("the JVM observations are missing a grid row or the midnight witness")
    counts = dict.fromkeys(("correspondence", "clock", "sameDay", "reverse"), 0)
    for i, row in enumerate(rows[:-1]):
        if row["startTick"] != i or row["ends"] != 192:
            raise ValueError("incomplete or duplicated clock grid")
        for name in counts:
            value = row[name]
            if type(value) is not int or not 0 <= value <= row["ends"]:
                raise ValueError(f"invalid {name} count")
            counts[name] += value
    return {"cases": 192 * 192, **counts, **rows[-1]}


def correspondence(lines):
    result = totals(lines)
    return {"cases": result["cases"], "disagreements": result["correspondence"]}


def problems(lines):
    result = totals(lines)
    return [(name, f"{result[name]} discrepancies") for name in ("clock", "sameDay", "reverse", "correspondence")
            if result[name]]
