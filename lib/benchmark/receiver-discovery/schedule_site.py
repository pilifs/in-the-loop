"""Bind the third-commit assertion in original worker bytecode and replay a discovered schedule on a JVM."""

import json
import os
from pathlib import Path
import sys
import tempfile

from callers import JDK, RESULTS, ROOT, sha
from deeper import build, schedule
from investigate import class_bytes, command, compiler, inventory, original, write

sys.path.insert(0, str(ROOT / "lib/python"))
from jvm_disassembly import methods


def measure(stage, tmp, checker):
    _, cp, drivers = build("schedule", tmp, stage)
    board = "Duty$Board#" + ("finish" if stage == "single-monitor" else "commit")
    subject = inventory(checker, cp, board)
    raw = tmp / "Board.class"
    raw.write_bytes(class_bytes(subject["binding"]))
    table, _ = methods(JDK / "bin/javap", raw)
    insns = table[subject["method"], "(IZ)V"]["code"]
    (pc,) = [
        code.pc
        for i, code in enumerate(insns)
        if i
        and code.op == "athrow"
        and insns[i - 1].op == "invokespecial"
        and "java/lang/AssertionError" in insns[i - 1].member
    ]
    # The scheduler finishes the discovery and cross-check before choosing an order to replay.
    searches = schedule(cp, drivers)
    result = {
        "classSha256": sha(raw),
        "owner": subject["owner"],
        "method": subject["method"],
        "descriptor": subject["descriptor"],
        "pc": pc,
        "protocols": {},
    }
    tools = compiler(tmp)
    for name, data in searches.items():
        witness = data["witness"] or next(iter(data["histories"]))
        expected = data["histories"][witness]
        split = "split" if name.startswith("split") else "atomic"
        force = str(name.endswith("terminal")).lower()
        root = tmp / name
        root.mkdir()
        source = root / "SelectedSchedule.java"
        # The selected schedule comes only from the completed search. The original Board is never rewritten.
        args = ", ".join(map(json.dumps, [split, force, witness]))
        source.write_text(
            "public final class SelectedSchedule { public static boolean replay() throws Exception {"
            "ScheduleSearch.main(new String[]{" + args + "}); return true; } }\n"
        )
        paths = [root, drivers, *cp]
        command(
            [
                JDK / "bin/javac",
                "-proc:none",
                "-g",
                "-parameters",
                "-cp",
                os.pathsep.join(map(str, [drivers, *cp])),
                "-d",
                root,
                source,
            ]
        )
        entry = inventory(checker, paths, "SelectedSchedule#replay")
        lines = original(tools, paths, subject, {"pc": pc, "kind": "assertion"}, entry, [])
        expected_line = " ".join(
            [witness, str(expected["mask"]), "3", str(expected["failures"]), ";".join(expected["events"])]
        )
        hits = sum(s.startswith("hit ") for s in lines)
        throws = [s for s in lines if s.startswith("raised ")]
        if (
            expected_line not in lines
            or hits != expected["failures"]
            or len(throws) != hits
            or not all(s.startswith("raised java.lang.AssertionError caught Duty#turn") for s in throws)
        ):
            raise ValueError((stage, name, witness, lines))
        result["protocols"][name] = {
            "order": witness,
            "completeSchedules": data["orders"],
            "mask": expected["mask"],
            "hits": hits,
            "originalJvm": lines,
        }
    return result


if __name__ == "__main__":
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    result = {
        "job": os.environ["VERIFY_JOB_ID"],
        "source": os.environ["VERIFY_SOURCE_COMMIT"],
        "checkerSha256": sha(checker),
        "revisions": {},
    }
    for stage in ("opening", "single-monitor"):
        with tempfile.TemporaryDirectory() as d:
            result["revisions"][stage] = measure(stage, Path(d), checker)
    out = RESULTS / "deeper/selected/schedule"
    out.mkdir(parents=True, exist_ok=True)
    write(out / "measurement.json", result)
