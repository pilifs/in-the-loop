"""Register calendar and cursor histories using a JDK-only oracle before exercising either original JAR."""
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile

CASE = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE.parent))
from plan_run import JDK
from prepare import prepare, sha

BASE = "org.apache.commons.lang3.time."
FORMAT = BASE + "FastDateFormat"
PARSER = BASE + "FastDateParser"
ENTRY = FORMAT + "#parse(Ljava/lang/String;Ljava/text/ParsePosition;Ljava/util/Calendar;)Z"
CTOR = "#<init>(Ljava/lang/String;Ljava/util/TimeZone;Ljava/util/Locale;Ljava/util/Date;)V"


def write(name, obj):
    (CASE / name).write_text(json.dumps(obj, indent=2) + "\n")


def main():
    prepare("lang")
    workflows, references = [], []
    with tempfile.TemporaryDirectory(prefix="week-reference-") as classes:
        subprocess.run([JDK / "bin/javac", "-proc:none", "-d", classes, CASE / "WeekReference.java"], check=True)
        for history in ("mixed", "preserved"):
            cases, changes = [], []
            for index, (locale, mode) in enumerate(itertools.product(("US", "DE"), ("strict", "lenient"))):
                args = [locale, mode, history]
                observed = {}
                for side in ("old", "new"):
                    raw = subprocess.check_output([JDK / "bin/java", "-cp", classes, "WeekReference", side, *args], text=True)
                    steps = []
                    for line in raw.splitlines():
                        fields, instant, end, error = line.split("\t")
                        steps.append({"calendarAndCursor": fields, "simpleDateFormat": {
                            "instant": instant, "index": int(end), "errorIndex": int(error)}})
                    references.append({"side": side, "args": args, "steps": steps})
                    observed[side] = {"return": "/".join(s["calendarAndCursor"] for s in steps)}
                cases.append({"args": args, "expected": observed["old"]})
                if observed["new"] != observed["old"]:
                    changes.append({"input": index, "expectedNew": observed["new"]})
            if len(changes) != (4 if history == "mixed" else 0):
                raise ValueError("unexpected reference partition")
            write(history + ".json", {"entry": ENTRY, "probeClass": "UpgradeProbe", "cases": cases,
                "observer": "Each parse reports its return or exception, index and error index, Calendar.isSet mask, and the instant (or invalid state) in both the original mode and a lenient snapshot. One formatter, calendar and cursor serve the complete history.",
                "basis": "A separate Java program with a JDK-only classpath specifies Calendar field writes and resolves ISO weeks. SimpleDateFormat independently compares the acceptance and instants of the repaired calendar specification."})
            workflows.append({"id": history, "cohort": "registered", "scope": history + ".json", "probe": "UpgradeProbe.java",
                              "intent": {"allowedChanges": changes} if changes else "preserve",
                              "deterministicUnderAssumptions": True,
                              "assumptions": ["Fresh original JVM, UTC, GregorianCalendar in the chosen locale and mode; the same ParsePosition has its index moved to the next token by its caller, keeping its error index."]})
    base = {"schema": "caller-workflows/v1", "change": "Commons Lang #1839, partial calendar updates, ISO weekdays and recovery"}
    write("workflows.json", base | {"workflows": workflows})
    helper = {"entry": PARSER + "#toCalendarDayOfWeek(I)I", "callFrom": PARSER + "#access$800(I)I",
              "startupEntry": PARSER + CTOR, "startupWithin": FORMAT + CTOR,
              "rows": [{"args": [i], "result": (i % 7 + 1) if 1 <= i <= 7 else i} for i in (0, 1, 7, 8, 15)]}
    write("helper.json", helper)
    private = [w | {"id": w["id"] + "-private", "cohort": "control", "checkedHelper": "helper.json"} for w in workflows]
    write("checked-workflows.json", base | {"workflows": workflows + private})
    write("jdk-reference.json", references)
    write("registration.json", {"productCommitment": sha(CASE.parent / "freeze.json"),
          "inputs": {name: sha(CASE / name) for name in ("UpgradeProbe.java", "WeekReference.java", "upstream.json",
                   "old/prepared.json", "new/prepared.json", "mixed.json", "preserved.json", "helper.json", "workflows.json",
                   "checked-workflows.json", "jdk-reference.json", "register.py")},
          "falsifier": "Any unexpected partial Calendar mutation, cursor position, exception, valid-date instant or subsequent recovery refutes that finite history. A fixed helper receipt accepted on the parent, where its original method is absent, invalidates the helper derivation.",
          "exposure": "Named disclosed PR and setup preflight; the expected histories and cursor and calendar state were generated without either production JAR on the reference classpath."})


if __name__ == "__main__":
    main()
