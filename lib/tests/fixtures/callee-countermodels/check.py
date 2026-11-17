#!/usr/bin/env python3
"""What a JVM and a checker say of each pair of the callee countermodels: a harness for whoever writes the rule.

    python3 -I check.py --jvmcontract PATH [--work DIR] [--only NAME ...] [--json FILE] [--rule-landed]
        [-- EXTRA JVMCONTRACT ARGUMENTS]

Compiles `old/` and `new/` (javac -g -parameters --release 21), runs each version's `Entry` on six inputs, each
call in a JVM of its own (so no call sees another's statics, as the pair of versions gives each a fresh state), and
checks each method as a pair of versions:

    jvmcontract equivalence --before old --after new --target app.Entry#NAME --nullable password --nullable salt
        --assume 'salt == null || salt.equals("") || salt.equals("a") || salt.equals("b")'
        --engine native --max-array-length 2 --jbmc /nonexistent/jbmc

with the checker's default unwinding, which the callee's 600 rounds are past: what relates the two versions' calls
is then whatever the checker has for that (on 2026-11-17 the ties of a summarized loop, lib/src/bmc/ties.rs), not
the rounds themselves.

It exits 1 when a verdict is one the fixtures forbid:

- a pair a JVM tells apart is `verified` (a false proof);
- a pair that agrees is `violation` (a false alarm; a witness that does not replay is to be dropped);
- with --rule-landed, also when `same` is not `verified`: a rule that refuses everything passes the seven
  countermodels and proves nothing. `copied` and `twice` are positive controls a rule may leave undecided (arguments
  equal only by content; two calls on one side), and must never refute.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSUME = 'salt == null || salt.equals("") || salt.equals("a") || salt.equals("b")'
INPUTS = [("a", "b"), ("é", "b"), ("a", "empty"), ("a", "null"), ("null", "b"), ("empty", "a")]
# name: (the versions agree on every input, the side condition a rule must hold for the pair not to be proved)
PAIRS = {
    "same": (True, "none: the positive control, 307's shape (the same values, other instructions around the call)"),
    "copied": (True, "none: a harder positive control; the arguments are equal by content, through a copy a loop makes"),
    "twice": (True, "none: a positive control; two calls' results are two objects of the same content"),
    "table": (False, "the static state the callee reads is the same at both calls"),
    "seeded": (False, "the code compared includes what the callee's initializer reaches"),
    "helped": (False, "the code compared includes the callee's private helpers"),
    "wiped": (False, "what the callee writes to its arguments is part of its outcome"),
    "counted": (False, "the static state the callee reads and writes is part of its arguments and outcome"),
    "caught": (False, "an exception is an outcome, shared like a result"),
    "aliased": (False, "arguments equal by content are not the same arguments when one side's are one array"),
}


def jvm(classes, method, password, salt):
    env = dict(os.environ)
    env.pop("JAVA_TOOL_OPTIONS", None)
    return subprocess.run(["java", "-cp", str(classes), "app.Entry", method, password, salt], check=True, capture_output=True, text=True, env=env).stdout.strip()


def main():
    argv, extra = sys.argv[1:], []
    if "--" in argv:
        extra, argv = argv[argv.index("--") + 1:], argv[:argv.index("--")]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--jvmcontract", required=True)
    p.add_argument("--work", type=Path)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--only", nargs="*")
    p.add_argument("--json", type=Path)
    p.add_argument("--rule-landed", action="store_true")
    args = p.parse_args(argv)
    work = (args.work or Path(tempfile.mkdtemp(prefix="callee-countermodels-"))).resolve()
    shutil.rmtree(work, ignore_errors=True)
    classes = {}
    for side in ("old", "new"):
        classes[side] = work / "classes" / side
        subprocess.run(["javac", "-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d", str(classes[side]), *map(str, sorted((HERE / side / "app").glob("*.java")))], check=True)
    rows, bad = [], []
    for name, (agree, condition) in PAIRS.items():
        if args.only and name not in args.only:
            continue
        differing = []
        for password, salt in INPUTS:
            old, new = jvm(classes["old"], name, password, salt), jvm(classes["new"], name, password, salt)
            if old != new:
                differing.append({"password": password, "salt": salt, "old": old, "new": new})
        if agree != (not differing):
            sys.exit(f"{name}: the JVM does not say of the fixture what this script does: {differing}")
        command = [args.jvmcontract, "equivalence", "--before", str(classes["old"]), "--after", str(classes["new"]), "--target", f"app.Entry#{name}",
                   "--nullable", "password", "--nullable", "salt", "--assume", ASSUME, "--engine", "native", "--max-array-length", "2",
                   "--timeout", str(args.timeout), "--jbmc", "/nonexistent/jbmc", "--work", str(work / "pairs" / name), "--json", *extra]
        done = subprocess.run(command, capture_output=True, text=True)
        try:
            out = json.loads(done.stdout)
        except ValueError:
            out = {"verdict": f"no outcome (exit {done.returncode})", "problem": done.stderr.strip()[-300:]}
        verdict, problem = out["verdict"], out.get("problem") or ""
        native = (out.get("search") or {}).get("native") or {}
        wrong = (not agree and verdict == "verified") or (agree and verdict == "violation") or (args.rule_landed and name == "same" and verdict != "verified")
        if wrong:
            bad.append(name)
        rows.append({"method": name, "jvmDiffersAt": differing, "condition": condition, "verdict": verdict, "problem": problem, "wrong": wrong,
                     "seconds": (out.get("search") or {}).get("seconds"), "tied": native.get("tied"), "loops": len(native.get("loops") or []),
                     "output": out.get("output")})
        jvm_says = "agree" if agree else f"differ at {differing[0]['password']}/{differing[0]['salt']}: {differing[0]['old']} against {differing[0]['new']}".replace("java.lang.", "")
        print(f"{'WRONG ' if wrong else ''}{name:8} JVM: {jvm_says:58} checker: {verdict}" + (f" ({problem[:150]})" if problem else "")
              + (f" [tied {native.get('tied')}]" if native.get("tied") else ""))
    if args.json:
        version = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr.splitlines()[0]
        args.json.write_text(json.dumps({"java": version, "assume": ASSUME, "extra": extra, "rows": rows}, indent=1, ensure_ascii=True) + "\n")
    if not args.work:
        shutil.rmtree(work, ignore_errors=True)
    if bad:
        sys.exit(f"verdicts the fixtures forbid: {bad}")


if __name__ == "__main__":
    main()
