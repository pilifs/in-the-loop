"""Register public map results and path predictions before running the original Gson deployments."""
import json
from pathlib import Path
import sys

CASE = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE.parent))
from matrix import write
from prepare import prepare, sha

BASE = "com.google.gson."
READER = BASE + "stream.JsonReader"
TREE = BASE + "internal.bind.JsonTreeReader"
PARSE = "java.lang.Integer#parseInt(Ljava/lang/String;)I"
ENTRIES = {route: BASE + "Gson#fromJson(" + arg + "Lcom/google/gson/reflect/TypeToken;)Ljava/lang/Object;"
           for route, arg in (("stream", "Ljava/lang/String;"), ("tree", "Lcom/google/gson/JsonElement;"))}
CALLERS = {"stream": READER + "#nextInt()I", "tree": BASE + "JsonPrimitive#getAsInt()I"}
DIGITS = {"1": 1, "2": 2, "01": 1, "002": 2}


def prediction(route, history, projection, repaired):
    docs = [[("1", "x"), ("2", "y")]]
    if history == "mixed":
        docs.extend([[("01", "a"), ("002", None)], [("002", "z"), ("01", "r")]])
    results = []
    for doc in docs:
        pairs, paths = [], []
        for key, value in doc:
            path = "$." + (key if repaired else "")
            paths.append(path)
            if value is None:
                paths.append("error=" + path)
                site = READER + ".unexpectedTokenError" if route == "stream" else TREE + ".nextString"
                outcome = "JsonSyntaxException/IllegalStateException@" + site
                break
            pairs.append(f"{int(key)}={value}")
            paths.append(path)
        else:
            outcome = ",".join(pairs)
        results.append(outcome + ("|" + ",".join(paths) if projection == "paths" else ""))
    return {"return": ";".join(results)}


def main():
    prepare("gson")
    registered, controls = [], []
    files = ["upstream.json", "register.py", "UpgradeProbe.java", "old/prepared.json", "new/prepared.json"]
    for route, entry in ENTRIES.items():
        name = route + "-helper.json"
        helper = {"entry": PARSE, "callFrom": CALLERS[route], "startupEntry": READER + "#<clinit>()V",
                  "startupWithin": "UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;",
                  "rows": [{"args": [s], "result": n} for s, n in DIGITS.items()]}
        write(CASE / name, helper)
        files.append(name)
        for projection in ("paths", "values"):
            label = route + "-" + projection
            cases, changes = [], []
            for idx, history in enumerate(("plain", "mixed")):
                old, new = [prediction(route, history, projection, fix) for fix in (False, True)]
                cases.append({"args": [route, history, projection], "expected": old})
                if old != new:
                    changes.append({"input": idx, "expectedNew": new})
            scope = label + ".json"
            write(CASE / scope, {"entry": entry, "probeClass": "UpgradeProbe", "cases": cases,
                "observer": "Ordered integer keys and values, the original exception site on an array value, and subsequent successful reuse of the same Gson. The paths projection adds getPath, getPreviousPath and the path extracted from the original diagnostic.",
                "basis": "Predicted from literal object member spellings, mathematical decimal keys and the declared reader-specific failure site. The padded keys distinguish the original name from the parsed integer."})
            workflow = {"id": label, "cohort": "registered", "scope": scope, "probe": "UpgradeProbe.java",
                        "intent": {"allowedChanges": changes} if changes else "preserve",
                        "assumptions": ["Fresh pinned JVM for each trial. One Gson and one registered value adapter for all documents in a history."],
                        "deterministicUnderAssumptions": True}
            registered.append(workflow)
            controls.append(workflow | {"id": label + "-parsed", "cohort": "control", "checkedHelper": name})
            files.append(scope)
    doc = {"schema": "caller-workflows/v1", "change": "Gson #3098, promoted integer map keys and public diagnostics"}
    for name, workflows in (("workflows.json", registered), ("checked-workflows.json", registered + controls)):
        write(CASE / name, doc | {"workflows": workflows})
        files.append(name)
    write(CASE / "registration.json", {"productCommitment": sha(CASE.parent / "freeze.json"),
        "inputs": {f: sha(CASE / f) for f in files},
        "exposure": "Named PR, preflight and upstream implementations disclosed. Registered expectations use only the original key spellings, decimal values and public error origins.",
        "falsifier": "A missing key name at either observation, the wrong name at the subsequent failed value, a wrong map or failure site, or a stale reader-specific proof accepted on the other reader refutes its respective prediction."})


if __name__ == "__main__":
    main()
