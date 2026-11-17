#!/usr/bin/env python3
"""What a JVM and a checker say of each pair of the conversion countermodels: a harness for whoever writes the model.

    python3 -I check.py --jvmcontract PATH [--work DIR] [--bound N] [--only NAME ...] [--json FILE] [--model-landed]

Compiles `old/` and `new/` (javac -g -parameters --release 21), runs each version's `main` on the `java` of the
PATH, once as it is and once with `-Dfile.encoding=COMPAT` under LC_ALL=C (a default charset that is not UTF-8), and
then checks each method as a pair of versions:

    jvmcontract equivalence --before old --after new --target app.Text#NAME --nullable s --assume 'k >= -1 && k <= 12'
        --engine native --max-array-length N (3 by default: a pair of surrogates and a unit beside it)
        --jbmc /nonexistent/jbmc

The table has, for each method, whether the two versions gave the same on the JVM's inputs, what the README expects
of a check, and the verdict. It exits 1 when a verdict is one the fixtures forbid:

- a pair a JVM tells apart is `verified` (a false proof);
- a pair that agrees on every String is `violation` (a false alarm, which the JVM replay should have dropped);
- with --model-landed, also when one of the six pairs the two models decide is left `unverifiable` (named, written,
  lone and paired for String.getBytes("UTF-8"); asciiWritten and asciiPairs for the US-ASCII conversion). Until
  those models exist every pair stops at a call the checker does not model, and that is no failure. The pairs
  about other names (alias, ascii, latin, unknown, chosen) may stay there under a model that takes the one name.

This is no test of the default run: it needs a built `jvmcontract` and writes where --work says. The test to add to
lib/tests with the model is in the README.
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
# name: (the versions agree on every String, what a sound and complete check says)
EXPECTED = {
    "named": (True, "verified"), "alias": (True, "verified or unverifiable"), "written": (True, "verified"), "asciiWritten": (True, "verified"),
    "ascii": (False, "violation or unverifiable"), "latin": (False, "violation or unverifiable"), "unknown": (False, "violation or unverifiable"),
    "chosen": (False, "violation or unverifiable"), "defaulted": (None, "unverifiable, or a verdict under a stated assumption about the default charset"),
    "lone": (False, "violation"), "paired": (False, "violation"), "asciiPairs": (False, "violation"),
}


def jvm(classes, compat):
    env = dict(os.environ)
    env.pop("JAVA_TOOL_OPTIONS", None)
    argv = ["java"]
    if compat:
        env.update(LC_ALL="C", LANG="C")
        argv.append("-Dfile.encoding=COMPAT")
    out = subprocess.run(argv + ["-cp", str(classes), "app.Text"], check=True, capture_output=True, text=True, env=env).stdout
    return {line.split()[0]: line.split()[1:] for line in out.splitlines()}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--jvmcontract", required=True)
    p.add_argument("--work", type=Path)
    p.add_argument("--bound", type=int, default=3)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--only", nargs="*")
    p.add_argument("--json", type=Path)
    p.add_argument("--model-landed", action="store_true")
    args = p.parse_args()
    work = (args.work or Path(tempfile.mkdtemp(prefix="conversion-countermodels-"))).resolve()
    shutil.rmtree(work, ignore_errors=True)
    classes = {}
    for side in ("old", "new"):
        classes[side] = work / "classes" / side
        subprocess.run(["javac", "-g", "-parameters", "-proc:none", "-nowarn", "-Xlint:-unchecked", "--release", "21", "-d", str(classes[side]), str(HERE / side / "app/Text.java")], check=True)
    plain = {side: jvm(classes[side], False) for side in classes}
    compat = {side: jvm(classes[side], True) for side in classes}
    rows, bad = [], []
    for name, (agree, expected) in EXPECTED.items():
        if args.only and name not in args.only:
            continue
        differing = [a.split("=")[0] or '""' for a, b in zip(plain["old"][name], plain["new"][name]) if a != b]
        differing_compat = [a.split("=")[0] or '""' for a, b in zip(compat["old"][name], compat["new"][name]) if a != b]
        if (agree is True and (differing or differing_compat)) or (agree is False and not differing):
            sys.exit(f"{name}: the JVM does not say of the fixture what the README does: {differing} {differing_compat}")
        argv = [args.jvmcontract, "equivalence", "--before", str(classes["old"]), "--after", str(classes["new"]), "--target", f"app.Text#{name}", "--nullable", "s", "--assume", "k >= -1 && k <= 12",
                "--engine", "native", "--max-array-length", str(args.bound), "--timeout", str(args.timeout), "--jbmc", "/nonexistent/jbmc",
                "--work", str(work / "pairs" / name), "--json"]
        done = subprocess.run(argv, capture_output=True, text=True)
        try:
            out = json.loads(done.stdout)
        except ValueError:
            out = {"verdict": f"no outcome (exit {done.returncode})", "problem": done.stderr.strip()[-300:]}
        verdict = out["verdict"]
        witness = out.get("counterexample")
        problem = out.get("problem") or ""
        wrong = (agree is False and verdict == "verified") or (agree is True and verdict == "violation") or (name == "defaulted" and verdict == "verified" and "default" not in json.dumps(out))
        wrong |= args.model_landed and agree is not None and verdict not in expected.split(" or ")
        if wrong:
            bad.append(name)
        rows.append({"method": name, "jvmDiffersAt": differing, "jvmCompatDiffersAt": differing_compat, "expected": expected, "verdict": verdict,
                     "problem": problem, "witness": witness, "wrong": wrong, "seconds": (out.get("search") or {}).get("seconds")})
        jvm_says = "agree" if not differing else "differ at " + " ".join(differing[:2])
        if differing_compat and not differing:
            jvm_says = "agree; under COMPAT differ at " + " ".join(differing_compat[:2])
        print(f"{'WRONG ' if wrong else ''}{name:13} JVM: {jvm_says:42} expected: {expected.split(',')[0]:25} checker: {verdict}" + (f" ({problem})" if problem else "")
              + (f" at {json.dumps(witness, ensure_ascii=True)[:80]}" if witness else ""))
    if args.json:
        version = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr.splitlines()[0]
        args.json.write_text(json.dumps({"java": version, "bound": args.bound, "rows": rows}, indent=1) + "\n")
    if not args.work:
        shutil.rmtree(work, ignore_errors=True)
    if bad:
        sys.exit(f"verdicts the fixtures forbid: {bad}")


if __name__ == "__main__":
    main()
