"""Register the two-deployment rollover histories using fixed-offset civil-day arithmetic."""
import hashlib
import itertools
import json
from pathlib import Path
import sys
import zipfile

CASE = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE.parent))
from matrix import write
from prepare import SETUP, prepare, sha

PROCESSOR = "org.apache.logging.log4j.core.appender.rolling.PatternProcessor"
ENTRY = PROCESSOR + "#getNextTime(JIZ)J"
PLUGIN = "META-INF/org/apache/logging/log4j/core/config/plugins/Log4j2Plugins.dat"
START = 1393927200000
DAY = 86_400_000


def expected(offset, time_based):
    shift = offset * 3_600_000
    first = ((START + shift) // DAY + 1) * DAY - shift
    prev = 0
    rows = ["13,17" if time_based else "0,0"]
    for i, now in enumerate((START, first - 1, first)):
        deadline = ((now + shift) // DAY + 1) * DAY - shift
        recorded = deadline - DAY
        rows.append(",".join(map(str, (deadline, recorded, prev, 31 + i, recorded, 0))))
        prev = recorded
    return {"return": "/".join(rows)}


def main():
    prepare("log4j")
    files = ["upstream.json", "register.py", "UpgradeProbe.java"]
    setup = {name: digest for digest, name in (l.split() for l in (SETUP / "logs/artifacts.sha256").read_text().splitlines())}
    for side in ("old", "new"):
        name = side + "/prepared.json"
        binding = json.loads((CASE / name).read_bytes())
        api, core = (Path(item["file"]) for item in binding["classpath"])
        if any(sha(jar) != setup[jar.name] for jar in (api, core)):
            raise ValueError("original API or core differs from the setup builds")
        with zipfile.ZipFile(core) as z:
            binding["resources"][PLUGIN] = hashlib.sha256(z.read(PLUGIN)).hexdigest()
        write(CASE / name, binding)
        files.append(name)
    original, controls = [], []
    for mode in ("explicit", "omitted"):
        cases, changes = [], []
        for idx, (offset, time_based) in enumerate(itertools.product((10, -10), (True, False))):
            args = [f"GMT{offset:+d}:00", mode, "time-based" if time_based else "ordinary"]
            old = expected(offset, time_based)
            new = expected(-6 if mode == "explicit" else offset, time_based)
            cases.append({"args": args, "expected": old})
            if old != new:
                changes.append({"input": idx, "expectedNew": new})
        name = mode + ".json"
        write(CASE / name, {"entry": ENTRY, "probeClass": "UpgradeProbe", "cases": cases,
            "observer": "One constructed PatternProcessor, an initial update on a seeded receiver, and three schedules with updates immediately before and at the first deadline. Observe next, recorded, previous and current epoch milliseconds.",
            "basis": "Fixed-offset local midnight derived independently by integer arithmetic on epoch milliseconds, with the previous recorded midnight retained across calls."})
        workflow = {"id": mode, "cohort": "registered", "scope": name, "probe": "UpgradeProbe.java",
                    "intent": {"allowedChanges": changes} if changes else "preserve", "deterministicUnderAssumptions": True,
                    "assumptions": ["Fresh JDK 21 JVM. The specified process default is set before public construction. Daily pattern, fixed offset, one receiver, no external Log4j configuration."]}
        original.append(workflow)
        controls.append(workflow | {"id": mode + "-max", "cohort": "control", "checkedHelper": "helper.json"})
        files.append(name)
    write(CASE / "helper.json", {"entry": "java.lang.Math#max(II)I", "callFrom": "java.util.Calendar#selectFields()I",
          "startupEntry": "java.net.URL#openStream()Ljava/io/InputStream;",
          "startupWithin": "org.apache.logging.log4j.core.config.plugins.processor.PluginCache#loadCacheFiles(Ljava/util/Enumeration;)V",
          "rows": [{"args": [a, b], "result": max(a, b)} for a, b in ((0, 0), (0, 1), (1, 0))]})
    files.append("helper.json")
    for name, workflows in (("workflows.json", original), ("checked-workflows.json", original + controls)):
        write(CASE / name, {"schema": "caller-workflows/v1", "change": "Log4j #1173, daily rollover timezone and retained scheduling state", "workflows": workflows})
        files.append(name)
    write(CASE / "registration.json", {"productCommitment": sha(CASE.parent / "freeze.json"), "inputs": {p: sha(CASE / p) for p in files},
        "exposure": "Named PR and public setup examples disclosed. The integer oracle uses neither Log4j nor a Java Calendar.",
        "falsifier": "Any unexpected deadline or intermediate timestamp, disagreement across defaults with an explicit repaired zone, lost dependency on the default with an omitted zone, or changing the selected plugin without invalidating the original derivation."})


if __name__ == "__main__":
    main()
