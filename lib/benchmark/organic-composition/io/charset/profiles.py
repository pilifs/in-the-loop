"""Cross the original stream's selected encoder with its process default and check both saved positions."""
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from register import CASE, reference, sha
from plan_run import JDK, ROOT, OUTPUT


def inspect(lines):
    rows = {}
    cycles = []
    for line in lines.splitlines():
        kind, value = line.split("\t", 1)
        if kind == "cycle":
            before, count, read, after = value.split("\t")
            cycles.append({"before": before, "count": int(count), "afterRead": read, "afterReset": after})
        elif kind in rows:
            raise ValueError("duplicate JVM profile field " + kind)
        else:
            rows[kind] = value
    if len(cycles) != 32 or any(b["before"] != a["afterReset"] for a, b in zip(cycles, cycles[1:])):
        raise ValueError("incomplete consecutive history on the same receiver")
    return rows, cycles


def main():
    records = []
    for side in ("old", "new"):
        manifest = json.loads((CASE / side / "prepared.json").read_bytes())
        source, = manifest["classpath"]
        jar = Path(source["file"])
        if sha(jar) != source["sha256"]:
            raise ValueError("changed original deployment")
        with tempfile.TemporaryDirectory(prefix="charset-profile-") as tmp:
            work = Path(tmp)
            subprocess.run([JDK / "bin/javac", "-proc:none", "-g", "-encoding", "UTF-8", "-cp", jar, "-d", work,
                            CASE / "UpgradeProbe.java", HERE / "CharsetPositions.java"], check=True)
            for locale, default in (("C.UTF-8", "UTF-8"), ("C", "US-ASCII")):
                env = {"LC_ALL": locale, "LANG": locale, "TZ": "UTC", "HOME": tmp, "TMPDIR": tmp,
                       "PATH": str(JDK / "bin") + ":/usr/bin:/bin"}
                for selection in ("explicit", "default"):
                    actual = "UTF-8" if selection == "explicit" else default
                    command = [JDK / "bin/java", "-Dfile.encoding=COMPAT", "-Duser.timezone=UTC", "-cp",
                               os.pathsep.join(map(str, [work, jar])), "CharsetPositions", "two-resets", selection]
                    trials = []
                    for _ in range(2):
                        proc = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, check=True, timeout=12)
                        rows, cycles = inspect(proc.stdout)
                        if Path(rows["source"]) != jar or (rows["default"], rows["encoder"]) != (default, actual):
                            raise ValueError("actual source, default or stream encoder differs")
                        expected, _ = reference("two-resets", side == "new", actual)
                        if rows["observation"] != expected["return"]:
                            raise ValueError("profiled original public observer differs")
                        encoded = "Aé中Z".encode(actual, errors="replace")
                        marked = f"4,1,4,1,4,{len(encoded)},{encoded[1:].hex()}"
                        if rows["marked"] != marked or cycles[0]["before"] != marked:
                            raise ValueError("wrong initial two-position mark")
                        if side == "new":
                            if any(c["afterReset"] != marked or c["count"] != min(3, len(encoded) - 1) for c in cycles):
                                raise ValueError("fixed reset lost the mark, the live positions or readable suffix")
                        elif any(not c["afterReset"].startswith("-1,-1,") for c in cycles) or cycles[-1]["count"] != -1:
                            raise ValueError("parent failed to expose the consumed mark")
                        trials.append((rows, cycles))
                    if trials[0] != trials[1]:
                        raise ValueError("independent process repeats disagree")
                    rows, cycles = trials[0]
                    records.append({"side": side, "commit": manifest["commit"], "jar": source["sha256"],
                                    "processLocale": locale, "file.encoding": "COMPAT", "constructorCharset": selection,
                                    "freshProcessRepeats": 2, "actualDefault": rows["default"], "actualEncoder": rows["encoder"],
                                    "bufferClasses": rows["buffers"].split(","), "publicObservation": rows["observation"],
                                    "initialMark": rows["marked"], "cycles": len(cycles),
                                    "distinctTransitions": [json.loads(v) | {"countOfTransition": count}
                                        for v, count in Counter(json.dumps(c) for c in cycles).items()]})
    out = ROOT / OUTPUT / "io/charset-profiles.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"stateOrder": ["savedChar", "savedByte", "charPosition", "bytePosition", "charLimit",
                               "byteLimit", "remainingByteHex"], "profiles": records}, indent=2) + "\n")
    print(len(records), "profiles, two fresh JVMs each, 32 consecutive read/reset cycles per JVM")


if __name__ == "__main__":
    main()
