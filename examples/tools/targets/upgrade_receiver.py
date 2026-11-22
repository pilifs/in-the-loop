"""Check the original upgrade caller from its real construction path and decode live JVM receiver shapes."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile


def shape(lines):
    result = {"arguments": [], "fields": {}}
    for line in lines:
        items = line.split("\t")
        if len(items) == 2 and items[0] == "this" and "this" not in result:
            result["this"] = items[1]
        elif len(items) == 2 and items[0] == "arg":
            result["arguments"].append(items[1])
        elif len(items) == 3 and items[0] == "field" and items[1] not in result["fields"]:
            result["fields"][items[1]] = items[2]
        else:
            raise ValueError("malformed JVM receiver metadata")
    if "this" not in result:
        raise ValueError("JVM receiver metadata has no root")
    return result


def at_entry(marks):
    def records(prefix):
        return [base64.b64decode(s[len(prefix):], validate=True).decode().splitlines()
                for s in marks if s.startswith(prefix)]
    entry, = records("UPGRADE-RECEIVER ")
    constructors = []
    for head, *arguments in records("UPGRADE-CONSTRUCTOR "):
        descriptor, caller, index = head.split("\t")
        constructors.append({"descriptor": descriptor, "calledBy": caller, "codeIndex": int(index),
                             "frame": shape(arguments)})
    return {"entry": shape(entry), "observedConstructorEntries": constructors}


def java_string(value):
    if value is None:
        return "null"
    # Java processes Unicode escapes before tokenizing. Use octal for controls, backslash and quote.
    units = value.encode("utf-16-be", "surrogatepass")
    out = []
    for i in range(0, len(units), 2):
        n = int.from_bytes(units[i:i+2], "big")
        if 32 <= n < 127 and n not in (34, 92):
            out.append(chr(n))
        elif n <= 255:
            out.append("\\%03o" % n)
        else:
            out.append("\\u%04x" % n)
    return '"' + ''.join(out) + '"'


def caller_source(observer, cases):
    package, _, simple = observer.rpartition(".")
    lines = ["package " + package + ";"] if package else []
    lines.extend(["public final class UpgradeCallerClaim {", "    public static boolean matches(int selector) {",
                  "        switch (selector) {"])
    for i in range(len(cases)):
        lines.append(f"            case {i}: return input{i}();")
    lines.extend(["            default: throw new IllegalArgumentException();", "        }", "    }"])
    for i, case in enumerate(cases):
        args = ", ".join(map(java_string, case["args"]))
        want = case["expected"]
        lines.extend([f"    static boolean input{i}() {{", "        try {",
                      f"            String value = {simple}.observe(new String[] {{{args}}});"])
        if "throws" in want:
            normal, abrupt = "false", java_string(want["throws"]) + ".equals(failure.getClass().getName())"
        else:
            normal = "value == null" if want["return"] is None else java_string(want["return"]) + ".equals(value)"
            abrupt = "false"
        lines.extend(["            return " + normal + ";", "        } catch (Throwable failure) {",
                      "            return " + abrupt + ";", "        }", "    }"])
    return "\n".join([*lines, "}", ""])


def native_inputs(checker, jdk, temp, compiled, observer, cases, prepared, env, seconds, feature, resources, working_directory, receipts):
    """Compile once against the original probe, run each revision independently at the selected subject JDK."""
    source = temp / "UpgradeCallerClaim.java"
    source.write_text(caller_source(observer, cases), encoding="ascii")
    directory = temp / "native-inputs"
    directory.mkdir()
    env = dict(env, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE=str(feature))
    cp = lambda paths: os.pathsep.join(map(str, paths))
    subprocess.run([jdk/"bin/javac", "-J-Djava.io.tmpdir="+str(temp), "-g", "-parameters", "-proc:none",
                    "-cp", cp([compiled, *prepared["old"][0]]), "-d", directory, source],
                   env=env, cwd=temp, check=True, capture_output=True, timeout=30)
    owner = observer.rsplit(".", 1)[0] + ".UpgradeCallerClaim" if "." in observer else "UpgradeCallerClaim"
    if (compiled / (owner.replace(".", "/")+".class")).exists():
        raise ValueError("the caller fixture already defines the native entry class")
    receipts.mkdir(parents=True, exist_ok=True)
    target = owner + "#matches"
    guard = f"selector >= 0 && selector < {len(cases)}"
    def sha(path):
        with path.open("rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest()
    evidence = {"domain": "registered finite caller inputs", "target": target, "assume": guard,
                "checkerSha256": sha(checker), "adapterClassSha256": sha(directory / (owner.replace(".", "/")+".class")),
                "maxArrayLength": 128, "unwind": 64, "timeoutSeconds": seconds, "sides": {}}
    for side, (paths, _, binding) in prepared.items():
        if any(_contains(p, owner) for p in paths):
            raise ValueError("generated native caller shadows an original class")
        trial = temp / ("caller-"+side)
        trial.mkdir()
        cwd = trial / working_directory
        cwd.mkdir(exist_ok=True)
        for source_file, name in resources:
            dest = trial / "fixtures" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source_file.read_bytes())
        cmd = [checker, "prove", target, "--classes", directory, "--classpath", cp([compiled, *paths]),
               "--engine", "native", "--gaps", "strict", "--assume", guard, "--assert", "result",
               "--unwind", "64", "--max-array-length", "128", "--timeout", str(seconds),
               "--work", temp/("native-"+side), "--json"]
        started = time.monotonic()
        result = {"commit": binding["commit"], "callerClassSha256": binding["callerClassSha256"],
                  "orderedClasspathSha256": binding["classpath"]}
        try:
            proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=seconds+3)
            raw = receipts / (side+".native.json")
            if not proc.stdout:
                raise ValueError("native checker emitted no result: " + proc.stderr.decode(errors="replace")[-400:])
            raw.write_bytes(proc.stdout)
            native, = json.loads(proc.stdout)
            st = native.get("stated") or {}
            if native["target"] != target or native["assume"] != guard or native["assert"] != "result" or (
                    st and st["gap_mode"] != "strict"):
                raise ValueError("native checker returned a different claim")
            result.update(verdict=native["verdict"], firstOutstanding=native["problem"],
                          vacuity=st.get("vacuity"), bounds=st.get("bounds"), assumptions=st.get("assumptions"),
                          counterexample=native.get("counterexample"), raw=raw.name, rawSha256=sha(raw))
        except subprocess.TimeoutExpired:
            result.update(verdict="timeout", firstOutstanding="native caller time budget")
        except (ValueError, OSError) as error:
            result.update(verdict="unverifiable", firstOutstanding=str(error))
        result["seconds"] = round(time.monotonic()-started, 3)
        evidence["sides"][side] = result
    return evidence


def _contains(path, owner):
    with zipfile.ZipFile(path) as jar:
        name = owner.replace(".", "/") + ".class"
        return name in jar.namelist() or any(re.fullmatch(r"META-INF/versions/[0-9]+/" + re.escape(name), n)
                                             for n in jar.namelist())
