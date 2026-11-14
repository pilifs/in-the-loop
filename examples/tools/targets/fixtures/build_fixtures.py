#!/usr/bin/env python3
"""Builds the Phase 0 fixture JARs of llm-dlc/loops/example-targets.md from the sources under gate/, locally and
deterministically: the same JDK gives the same bytes. Offline; nothing is fetched.

  python3 examples/tools/targets/fixtures/build_fixtures.py OUT    prints the manifest (JSON) and writes OUT/manifest.json

Each revision (before: vulnerable, after: fixed, mutant: a constructed mutation of after) is one JAR of its Gate and
the unchanged RegexGate, compiled with --release 21 so it runs on JDK 21 and 25, and with -parameters, so the classes
record the parameter names (`code`, `field`) the sidecar's and the claims' predicates use. The adapter is compiled
separately against each revision's JAR (adapter-before.jar, adapter-after.jar, adapter-mutant.jar), never into it,
and the driver once, against the adapter. Every JAR is made with a fixed timestamp and its entries in sorted order. The manifest
records each JAR's sha256, the javac flags, the JDK (`javac -version`, `java -version`), and the mutant's patch hash
against after.
"""

import difflib
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "gate"
RELEASE = "21"
DATE = "2026-01-01T00:00:00Z"
REVISIONS = ("before", "after", "mutant")
JAVAC_FLAGS = ("-parameters",)  # MethodParameters, so a claim's `code` is the class's own name, not arg0 (VF-024)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tool(name):
    """A JDK tool from JAVA_HOME when it is set, else from PATH."""
    import os
    home = os.environ.get("JAVA_HOME")
    return str(Path(home) / "bin" / name) if home else name


def javac(sources, out, classpath=None):
    out.mkdir(parents=True, exist_ok=True)
    cmd = [tool("javac"), "--release", RELEASE, "-encoding", "UTF-8", "-implicit:none", *JAVAC_FLAGS, "-d", str(out)]
    if classpath:
        cmd += ["-cp", classpath]
    subprocess.run(cmd + [str(s) for s in sorted(sources)], check=True, capture_output=True, text=True)


def jar(classes, path):
    entries = sorted(p.relative_to(classes).as_posix() for p in classes.rglob("*.class"))
    args = [a for e in entries for a in ("-C", str(classes), e)]  # -C applies to the one file after it
    subprocess.run([tool("jar"), "--create", "--file", str(path), f"--date={DATE}", "--no-manifest", *args],
                   check=True, capture_output=True, text=True)


def version(name):
    proc = subprocess.run([tool(name), "-version"], capture_output=True, text=True)
    return (proc.stdout + proc.stderr).strip().splitlines()[0]


def build(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".fixtures-", dir=out))
    try:
        jars = {}
        for revision in REVISIONS:
            javac([*GATE.joinpath(revision).rglob("*.java"), *GATE.joinpath("both").rglob("*.java")], work / revision)
            jars[revision] = out / f"{revision}.jar"
            jar(work / revision, jars[revision])
            javac(GATE.joinpath("adapter").rglob("*.java"), work / f"adapter-{revision}", classpath=str(jars[revision]))
            jars[f"adapter-{revision}"] = out / f"adapter-{revision}.jar"
            jar(work / f"adapter-{revision}", jars[f"adapter-{revision}"])
        javac(GATE.joinpath("driver").rglob("*.java"), work / "driver",
              classpath=f"{jars['adapter-after']}:{jars['after']}")
        jars["driver"] = out / "driver.jar"
        jar(work / "driver", jars["driver"])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    after = (GATE / "after/fixture/Gate.java").read_text().splitlines(keepends=True)
    mutant = (GATE / "mutant/fixture/Gate.java").read_text().splitlines(keepends=True)
    patch = "".join(difflib.unified_diff(after, mutant, "after/fixture/Gate.java", "mutant/fixture/Gate.java"))
    manifest = {
        "release": RELEASE, "date": DATE, "flags": list(JAVAC_FLAGS), "javac": version("javac"), "java": version("java"),
        "jars": {name: {"path": path.name, "sha256": sha256(path)} for name, path in sorted(jars.items())},
        "mutant": {"base": "after", "patchSha256": hashlib.sha256(patch.encode()).hexdigest()},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: build_fixtures.py OUT")
    print(json.dumps(build(sys.argv[1]), indent=2))
