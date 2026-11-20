import json


def driver_args():
    return ["--frames"]


def problems(lines):
    pending = {(n, f, t, alias, value) for n in range(4) for f in range(n + 1) for t in range(f, n + 1)
               for alias in (False, True) for value in (-1, 9)}
    errors = []
    for line in lines:
        r = json.loads(line)
        n, f, t, alias, v = len(r["a"]), r["from"], r["to"], r["alias"], r["value"]
        pending.remove((n, f, t, alias, v))
        if r["a"] != list(range(4, 4+n)) or r["other"] != (r["a"] if alias else list(range(20, 21+n))):
            raise ValueError("unexpected input heap")
        want = [v if f <= i < t else old for i, old in enumerate(r["a"])]
        other = want if alias else r["other"]
        if (r["result"], r["after"], r["otherAfter"], r["seen"]) != (n, want, other, other):
            errors.append([r["id"], "range or caller-visible pre-state differs"])
    if pending:
        raise ValueError("missing range or alias configuration")
    return errors
