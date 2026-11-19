"""Compare the released class, a source rebuild and its one-line row-sharing control on a JVM."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
NAME = "org.apache.commons.text.similarity.LongestCommonSubsequence"
CLASS = NAME.replace(".", "/")
FLAGS = ["--release", "21", "-g", "-parameters", "-proc:none", "-encoding", "UTF-8"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(java_home, artifacts, work):
    if work.is_dir() and any(work.iterdir()):
        raise ValueError(f"the build directory must be empty to identify the loaded classes: {work}")
    lock = json.loads((HERE / "sources.lock.json").read_text())
    java, javac, javap = (java_home / "bin" / name for name in ("java", "javac", "javap"))
    jars = {}
    for name, expected in lock["files"].items():
        jar = artifacts / name
        if digest(jar.read_bytes()) != expected:
            raise ValueError(f"{name} differs from sources.lock.json")
        jars[name] = jar
    release = jars["commons-text-1.13.1.jar"]
    with zipfile.ZipFile(release) as archive:
        if digest(archive.read(CLASS + ".class")) != lock["classSha256"]:
            raise ValueError("released class differs from the lock")
    with zipfile.ZipFile(jars["commons-text-1.13.1-sources.jar"]) as archive:
        original = archive.read(CLASS + ".java")
    blob = hashlib.sha1(f"blob {len(original)}\0".encode() + original).hexdigest()
    if blob != lock["sourceBlob"]:
        raise ValueError("source differs from the selected git blob")
    compiler = subprocess.check_output([javac, "-version"], text=True).strip()
    if not compiler.startswith("javac 21."):
        raise ValueError(f"expected JDK 21, found {compiler}")
    adapter = work / "adapter"
    adapter.mkdir(parents=True, exist_ok=True)
    sources = sorted((HERE / "adapter").rglob("*.java")) + sorted((HERE / "driver").rglob("*.java"))
    subprocess.run([javac, *FLAGS, "-cp", release, "-d", adapter, *sources], check=True)
    rows = {}
    for name, differences, ab_aa in [("release", 0, 1), ("rebuilt", 0, 1), ("shared-row", 44, 2)]:
        paths = [adapter, release]
        class_sha = lock["classSha256"]
        if name != "release":
            build = work / name
            build.mkdir(parents=True, exist_ok=True)
            source_file = build / "src/main/java" / (CLASS + ".java")
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(original)
            if name == "shared-row":
                subprocess.run(["patch", "--batch", "--fuzz=0", "--silent", "-p1", "-i", HERE / "controls/shared-row.patch"],
                               cwd=build, check=True)
            subprocess.run([javac, *FLAGS, "-cp", release, "-d", build, source_file], check=True)
            class_sha = digest((build / (CLASS + ".class")).read_bytes())
            paths.insert(1, build)
        cp = os.pathsep.join(map(str, paths))
        bytecode = subprocess.check_output([javap, "-p", "-c", "-cp", cp, NAME], text=True)
        method = bytecode.split("private static int[] algorithmB(", 1)[1].split("\n\n", 1)[0]
        site = re.search(r'(?m)^\s*(\d+): multianewarray\s+#\d+,\s*2\s*// class "\[\[I"', method)
        if not site:
            raise ValueError(f"{name}: algorithmB has no two-dimensional int allocation")
        row = json.loads(subprocess.check_output([java, "-Xmx256m", "-cp", cp, "score.ScoreDriver"], text=True))
        if row != {"pairs": 225, "disagreements": differences, "abAaScore": ab_aa}:
            raise ValueError(f"{name}: unexpected JVM result {row}")
        rows[name] = {**row, "classSha256": class_sha, "allocationOffset": int(site[1])}
    return {"sourceCommit": lock["sourceCommit"], "sourceBlob": blob, "compiler": compiler,
            "runtime": subprocess.run([java, "-version"], capture_output=True, text=True, check=True).stderr.splitlines()[0],
            "flags": FLAGS, "adapterAndOracleSha256": {p.name: digest(p.read_bytes()) for p in sources},
            "input": {"types": ["String", "String"], "alphabet": ["a", "b"], "lengths": [0, 1, 2, 3]},
            "observation": "Integer score", "artifacts": rows}


def native(checker, java_home, artifacts, work):
    sys.path.insert(0, str(HERE.parents[1] / "lib/benchmark"))
    try:
        from run import measure
    finally:
        sys.path.pop(0)
    claim = json.loads((HERE / "claims/score.json").read_text())
    bounds = claim["bounds"]
    command = ["env", f"JAVA_HOME={java_home}", f"PATH={java_home / 'bin'}{os.pathsep}{os.environ['PATH']}",
               str(checker), "prove", "score.LcsScore#score", "--classes", str(work / "adapter"),
               "--classpath", str(artifacts / "commons-text-1.13.1.jar"), "--assume", claim["assume"],
               "--assert", claim["assert"], "--max-array-length", str(bounds["maxArrayLength"]),
               "--unwind", str(bounds["unwind"]), "--engine", "native", "--gaps", "strict",
               "--timeout", "120", "--work", str(work / "native"), "--json"]
    measured = measure(command, 180)
    outcomes = json.loads(measured["stdout"])
    if not isinstance(outcomes, list) or len(outcomes) != 1:
        raise ValueError("expected one native property outcome")
    outcome = outcomes[0]
    (work / "native-outcome.json").write_text(measured["stdout"])
    return {"checkerSha256": digest(checker.read_bytes()), "bounds": bounds,
            "verdict": outcome["verdict"], "firstBlocker": outcome.get("problem"),
            "seconds": measured["seconds"], "peakMiB": measured["peakMB"],
            "outcomeSha256": digest(measured["stdout"].encode()), "phases": (outcome.get("search") or {}).get("phases")}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--java-home", type=Path, required=True)
    cli.add_argument("--artifacts", type=Path, required=True, help="the two JARs in sources.lock.json")
    cli.add_argument("--work", type=Path, help="keep the adapter and both source builds for the native check")
    cli.add_argument("--native", type=Path, help="also run this native checker on the release score claim")
    args = cli.parse_args()
    with tempfile.TemporaryDirectory() as scratch:
        work = (args.work or Path(scratch)).resolve()
        java_home, artifacts = args.java_home.resolve(), args.artifacts.resolve()
        result = run(java_home, artifacts, work)
        if args.native:
            result["native"] = native(args.native.resolve(), java_home, artifacts, work)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
