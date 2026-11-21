import json

PROBES = ["41"]


def problems(lines):
    rows = [json.loads(line) for line in lines]
    return [] if rows == [{"input": "41", "result": 42}] else [["41", rows]]
