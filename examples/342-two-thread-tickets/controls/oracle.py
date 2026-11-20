import json
from itertools import permutations


def driver_args():
    return ["--histories"]


def problems(lines):
    remaining = {0, 1, 2}
    failures = []
    for line in lines:
        h = json.loads(line)
        mode = h["mode"]
        remaining.remove(mode)
        calls, returns = h["invoked"], h["returned"]
        if sorted(calls + returns) != [1, 2, 3, 4] or any(a >= b for a, b in zip(calls, returns)):
            raise ValueError("malformed two-call history")
        if mode < 2 and returns[mode] >= calls[1 - mode]:
            raise ValueError("the promised serial invocation intervals overlap")
        accepted = False
        for first, second in permutations(range(2)):
            if returns[second] < calls[first]:
                continue
            accepted |= h["tickets"][first] == 1 and h["tickets"][second] == 2 and h["final"] == 2
        if not accepted:
            failures.append([mode, f"tickets {h['tickets']}, final {h['final']} admit no sequential order"])
    if remaining:
        raise ValueError("missing invocation modes")
    return failures
