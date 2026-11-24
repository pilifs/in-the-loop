"""Derive the predeclared return, byte writes and helper inputs from an independent byte-sequence model."""
import json
from pathlib import Path
import sys

CASE = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE.parent))
from prepare import prepare, sha

STREAM = "org.apache.commons.io.input.CharSequenceInputStream"
ENTRY = STREAM + "#read([BII)I"
HISTORIES = {
    "two-resets": [13, -1, 13, -1, 13, 24, 12, 60],
    "after-eof": [15, 24, 12, -1, 15, 24, 12, -1, 15, 24, 12, 60],
    "once": [13, -1, 13, 24, 12, 60],
    "short": [24, -1, 24, 12, 60],
}


def reference(history, persistent_mark, charset="utf-8"):
    text = "Aé" if history == "short" else "Aé中Z"
    data = text.encode(charset, errors="replace")
    dest = bytearray.fromhex("51627314253647")
    position = 1
    mark = position
    steps = [str(data[0])]
    copies = []
    for op in HISTORIES[history]:
        if op < 0:
            if mark is not None:
                position = mark
            if not persistent_mark:
                mark = None
            steps.append("R")
            continue
        offset, length = divmod(op, 10)
        remaining = len(data) - position
        count = min(length, remaining)
        if count:
            copies.append({"args": [remaining, length], "result": count, "offset": offset,
                           "bytes": data[position:position + count].hex()})
            dest[offset:offset + count] = data[position:position + count]
            position += count
        returned = -1 if length and not remaining else count
        steps.append(f"{returned}={dest.hex()}")
    return {"return": "/".join(steps)}, copies


def write(name, content):
    (CASE / name).write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n")


def main():
    prepare("io")
    workflows = []
    rows = {}
    for name, histories in (("rewinds", ["two-resets", "after-eof"]), ("preservation", ["once", "short"])):
        cases, changes = [], []
        for index, history in enumerate(histories):
            old, old_copies = reference(history, False)
            new, new_copies = reference(history, True)
            cases.append({"args": [history, "explicit"], "expected": old})
            if old != new:
                changes.append({"input": index, "expectedNew": new})
            for step in old_copies + new_copies:
                rows[tuple(step["args"])] = step["result"]
        scope = {"entry": ENTRY, "probeClass": "UpgradeProbe", "cases": cases,
                 "observer": "The prefix and every subsequent return count and all seven bytes of the same caller-owned destination, including short reads, EOF, zero-length read and both outer guards.",
                 "basis": "Independent byte-sequence model of an explicitly selected UTF-8 encoder with one saved position. The disclosed parent consumes its mark on the first reset; the fix retains it."}
        write(name + ".json", scope)
        workflows.append({"id": name, "cohort": "registered", "scope": name + ".json", "probe": "UpgradeProbe.java",
                          "intent": {"allowedChanges": changes} if changes else "preserve", "deterministicUnderAssumptions": True,
                          "assumptions": ["Fresh original JVM, explicit UTF-8, capacity eight, immutable source, one caller-owned destination and no concurrent operations."]})
    base = {"schema": "caller-workflows/v1", "change": "Commons IO #520, repeated resets on one encoded stream"}
    write("workflows.json", base | {"workflows": workflows})
    helper = {"entry": "java.lang.Math#min(II)I", "callFrom": ENTRY,
              "startupEntry": "java.nio.charset.CharsetEncoder#<init>(Ljava/nio/charset/Charset;FF[B)V",
              "startupWithin": "sun.nio.cs.UTF_8#newEncoder()Ljava/nio/charset/CharsetEncoder;",
              "rows": [{"args": list(args), "result": n} for args, n in sorted(rows.items())]}
    write("helper.json", helper)
    checked = [w | {"checkedHelper": "helper.json"} for w in workflows]
    ordinary = [w | {"id": w["id"] + "-ordinary", "cohort": "control"} for w in workflows]
    write("checked-workflows.json", base | {"workflows": checked + ordinary})
    write("registration.json", {"productCommitment": sha(CASE.parent / "freeze.json"),
          "inputs": {name: sha(CASE / name) for name in ("UpgradeProbe.java", "upstream.json", "rewinds.json",
                    "preservation.json", "workflows.json", "checked-workflows.json", "helper.json", "register.py")},
          "environmentControl": "Cross explicit UTF-8 and a null constructor charset with two real default encodings in fresh JVMs. Only the null selection is expected to follow the process default.",
          "falsifier": "Any wrong count, changed guard or byte outside the computed slice, wrong copied byte, or stale second rewind disagrees with the public byte history.",
          "setup": "The upstream preflight and test outcomes were disclosed. Expectations were generated from a byte sequence before evaluating a change plan."})


if __name__ == "__main__":
    main()
