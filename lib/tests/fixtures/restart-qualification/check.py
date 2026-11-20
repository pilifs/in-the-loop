"""Challenge branch merges, bound initialization and caught arithmetic on actual JVM and checker bytes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import runtime_jdk


def message_policy(jdk, work):
    calls = 50000
    env = {k: v for k, v in os.environ.items() if k not in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS")}
    profiles = {"default": [], "fastThrow": ["-Xbatch", "-XX:+OmitStackTraceInFastThrow"],
                "fullExceptions": ["-Xbatch", "-XX:-OmitStackTraceInFastThrow"], "interpreter": ["-Xint"]}
    rows = {}
    for name, flags in profiles.items():
        argv = [str(jdk / "bin/java"), *flags, "-cp", str(work), "MessagePolicy", str(calls)]
        stdout = subprocess.check_output(argv, env=env, text=True).strip()
        enabled, *numbers = stdout.split()
        first, rejected, index, exact, missing, other = map(int, numbers)
        if (enabled not in ("true", "false") or first != 1 or exact + missing + other != calls
                or not ((rejected == 0 and index == -1) or (0 < rejected <= calls and 0 <= index < calls))):
            raise ValueError(f"{name}: incomplete exception observations: {stdout}")
        if name in ("interpreter", "fullExceptions") and (rejected or exact != calls):
            raise ValueError(f"{name}: expected the text on every call: {stdout}")
        if name == "fastThrow" and (enabled != "true" or not rejected or not missing):
            raise ValueError(f"{name}: the warmed JVM did not reproduce the omitted message: {stdout}")
        rows[name] = {"argv": argv, "stdout": stdout, "omitStackTraceInFastThrow": enabled == "true",
                      "callsAfterFirst": calls, "firstPolicyResult": first, "policyRejections": rejected,
                      "firstRejectionIndex": index if rejected else None,
                      "independentDivideMessages": {"exact": exact, "null": missing, "other": other}}
    return {"checkedEntry": "Controls.message(I)I", "input": 0, "expectedMessage": "/ by zero",
            "independentEntry": "Controls.divide(I)I", "profiles": rows}


def run(work, only_jvm, only_messages=False):
    jdk = Path(runtime_jdk.home("21"))
    subprocess.run([jdk / "bin/javac", "-proc:none", "-parameters", "--release", "21", "-d", work,
                    HERE / "Controls.java"], check=True)
    report = {"jdk": runtime_jdk.identity(jdk), "classes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(work.glob("*.class"))}, "jvm": {}, "checks": []}
    if only_messages:
        subprocess.run([jdk / "bin/javac", "-proc:none", "-parameters", "--release", "21", "-cp", work,
                        "-d", work, HERE / "MessagePolicy.java"], check=True)
        report["classes"]["MessagePolicy.class"] = hashlib.sha256((work / "MessagePolicy.class").read_bytes()).hexdigest()
        return {"jdk": report["jdk"], "classes": report["classes"], **message_policy(jdk, work)}, True
    for setting, width in (("short", 2), ("long", 4)):
        lines = subprocess.check_output([jdk / "bin/java", "-Dfoundation.display=" + setting, "-cp", work, "Controls"],
                                        text=True).splitlines()
        expected = [f"array 2 5 calendar 15 16 display {width}", "divisor -1 handled -6 marker 0 escaping none",
                    "divisor 0 handled 7 marker 1 escaping java.lang.ArithmeticException(/ by zero)",
                    "divisor 1 handled 6 marker 0 escaping none"]
        if lines != expected:
            raise ValueError(f"unexpected JVM controls: {lines}")
        report["jvm"][setting] = lines
    if only_jvm:
        return report, True
    exe = os.environ["JVMCONTRACT"]
    report.update(checkerSha256=hashlib.sha256(Path(exe).read_bytes()).hexdigest(), checkerTree=os.getenv("JVMCONTRACT_LIB_TREE"))
    domain = "divisor >= -1 && divisor <= 1"
    obligations = [
        ("array-join", "arrayJoin", "result == (first ? 2 : 5)", None, "verified"),
        ("collapsed-array", "arrayJoin", "result == 2", None, "violation"),
        ("calendar-join", "calendarJoin", "result == (first ? 15 : 16)", None, "verified"),
        ("collapsed-calendar", "calendarJoin", "result == 15", None, "violation"),
        ("format-short", "display", "result == 2", None, "verified"),
        ("format-long", "display", "result == 4", None, "verified"),
        ("divide-event", "handler", "result < 10", domain, "violation"),
        ("no-escape", "checkedAverage", "true", domain, "verified"),
        ("handler-and-fallback", "handler", "result == 17", "divisor == 0", "verified"),
        ("escaping-kernel", "divide", "result == 6 / divisor", domain, "verified"),
        ("exception-message", "message", "result == 1", "divisor == 0", "verified"),
    ]
    passed = True
    for name, method, assertion, assume, expected in obligations:
        argv = [exe, "prove", "Controls#" + method, "--classes", str(work), "--classpath", str(work), "--engine",
                "native", "--gaps", "strict", "--assert", assertion, "--timeout", "35", "--unwind", "8",
                "--max-array-length", "2", "--json", "--work", str(work/name)]
        if assume:
            argv += ["--assume", assume]
        env = dict(os.environ, JAVA_HOME=str(jdk), PATH=str(jdk/"bin") + os.pathsep + os.getenv("PATH", ""))
        if name.startswith("format-"):
            setting = name.removeprefix("format-")
            env["JAVA_TOOL_OPTIONS"] = "-Dfoundation.display=" + setting
            argv += ["--observed-initializer", "Controls$Format"]
        if name == "escaping-kernel":
            argv += ["--throws", "java.lang.ArithmeticException when divisor == 0"]
        start = time.monotonic()
        result = subprocess.run(argv, env=env, text=True, capture_output=True, timeout=50)
        try:
            outcome, = json.loads(result.stdout)
        except (ValueError, TypeError):
            outcome = {}
        verdict = outcome.get("verdict")
        problem = outcome.get("problem") or (None if verdict else result.stderr.strip())
        stated = outcome.get("stated") or {}
        # A backend refusal is a diagnostic. An assertion that contradicts a real JVM is a failed qualification.
        disposition = "matched" if verdict == expected else "open" if verdict in (None, "unverifiable") else "unsound"
        if name.startswith("format-") and disposition == "matched":
            initializer = json.dumps(stated)
            if "foundation.display" not in initializer or setting not in initializer:
                disposition, problem = "open", "the reported statement did not bind the setting observed at initialization"
        passed &= disposition != "unsound"
        report["checks"].append({"claim": name, "argv": argv, "expected": expected, "observed": verdict,
                                 "disposition": disposition, "firstBlocker": problem, "stated": stated,
                                 "counterexample": outcome.get("counterexample"), "seconds": round(time.monotonic()-start, 3),
                                 "setting": env.get("JAVA_TOOL_OPTIONS"), "exitCode": result.returncode})
        print(name, disposition, verdict, flush=True)
    return report, passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument("--jvm-only", action="store_true")
    profiles.add_argument("--message-policy", action="store_true", help="compare cold and warmed division messages in four fresh JVMs")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        report, passed = run(Path(directory), args.jvm_only, args.message_policy)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    else:
        print(json.dumps(report, indent=2))
    sys.exit(0 if passed else 1)
