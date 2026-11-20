"""Build both pinned source trees and replay the caller, its upstream test and its mutant offline."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET
import zipfile


HERE = Path(__file__).resolve().parent
ENTRY_CLASS = "org.apache.commons.text.StringEscapeUtilsTest"
CSV_TEST = "testEscapeCsvString()"
FLAGS = ["--release", "8", "-encoding", "ISO-8859-1", "-g", "-parameters", "-proc:none"]
JVM_FLAGS = ["-Xmx384m", "-Dfile.encoding=UTF-8", "-Duser.language=en", "-Duser.country=US", "-Duser.timezone=UTC"]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run(args, cwd, expected=(0,)):
    started, clock = stamp(), time.monotonic()
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True,
                            env={**os.environ, "TZ": "UTC", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
    if result.returncode not in expected:
        raise RuntimeError(f"{args[0]} exited {result.returncode}\n{result.stdout[-1200:]}\n{result.stderr[-1800:]}")
    return result, {"startedUtc": started, "seconds": round(time.monotonic() - clock, 3), "exit": result.returncode}


def pack(destination, roots):
    with zipfile.ZipFile(destination, "w") as output:
        for root in roots:
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                info = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o644 << 16
                output.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)


def files(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}


def compile_jar(jdk, root, sources, dependencies, destination, resources=()):
    classes = destination.with_suffix(".classes")
    classes.mkdir()
    _, timing = run([jdk / "bin/javac", *FLAGS, "-cp", os.pathsep.join(map(str, dependencies)),
                     "-d", classes, *sources], root)
    pack(destination, [classes, *resources])
    return timing


def junit(jdk, root, out, jars, console):
    report = out / "junit"
    command = [jdk / "bin/java", *JVM_FLAGS, "-jar", console, "execute", "--disable-banner",
               "--disable-ansi-colors", "--class-path", os.pathsep.join(map(str, jars)), "--select-class",
               ENTRY_CLASS, "--reports-dir", report, "--fail-if-no-tests", "--details", "summary"]
    process, timing = run(command, root, expected=(0, 1))
    (out / "junit.log").write_text(process.stdout + process.stderr)
    tests = []
    for xml in sorted(report.glob("TEST-*.xml")):
        for test in ET.parse(xml).iter("testcase"):
            if test.get("classname") == ENTRY_CLASS:
                bad = next((child for child in test if child.tag in ("error", "failure", "skipped")), None)
                tests.append({"name": test.get("name"), "status": bad.tag if bad is not None else "passed",
                              **({"message": bad.get("message")} if bad is not None else {})})
    csv = [test for test in tests if test["name"] == CSV_TEST]
    if len(csv) != 1:
        raise ValueError(f"expected exactly one testcase for {ENTRY_CLASS}#{CSV_TEST}, got {csv}")
    return {**timing, "testClass": ENTRY_CLASS, "testCount": len(tests), "csvTest": csv[0],
            "failures": [test for test in tests if test["status"] != "passed"],
            "reportHashes": {p.name: digest(p) for p in sorted(report.glob("TEST-*.xml"))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True, help="the five files in sources.lock.json")
    parser.add_argument("--jdk", type=Path, required=True, help="Temurin 21.0.13+9 home")
    parser.add_argument("--work", type=Path, required=True, help="new directory for extracted trees, classes and results")
    opts = parser.parse_args()
    work, jdk = opts.work.resolve(), opts.jdk.resolve()
    work.mkdir()
    locked = json.loads((HERE / "sources.lock.json").read_text())
    inputs = {name: opts.inputs.resolve() / name for name in locked["inputs"]}
    for name, path in inputs.items():
        if digest(path) != locked["inputs"][name]["sha256"]:
            raise ValueError(f"{name} differs from the input lock")
    spec = importlib.util.spec_from_file_location("csv_oracle", HERE / "controls/oracle.py")
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    cases = {}
    for side in ("old", "new"):
        area = work / side
        area.mkdir()
        with tarfile.open(inputs[f"{side}.tar.gz"]) as archive:
            archive.extractall(area, filter="data")
        cases[side] = area / f"commons-text-{locked['revisions'][side]}"
    inventories = {side: files(root) for side, root in cases.items()}
    differences = [name for name in sorted(set(inventories["old"]) | set(inventories["new"]))
                   if inventories["old"].get(name) != inventories["new"].get(name)]
    if differences != ["pom.xml"]:
        raise ValueError(f"unexpected upstream differences: {differences}")
    mutant = work / "mutant" / "checkout"
    shutil.copytree(cases["new"], mutant)
    run(["git", "apply", str(HERE / "controls/omit-quote-doubling.patch")], mutant)
    cases["mutant"] = mutant
    version, subject_jdk = run([jdk / "bin/java", "-version"], work)
    result = {
        "startedUtc": subject_jdk["startedUtc"], "subjectJdk": {
            "version": version.stderr.strip(), "releaseSha256": digest(jdk / "release"), "modulesSha256": digest(jdk / "lib/modules")
        },
        "jvmFlags": JVM_FLAGS, "compilerFlags": FLAGS, "locale": "C.UTF-8", "timezone": "UTC",
        "differences": differences, "fileCounts": {s: len(v) for s, v in inventories.items()}, "sides": {}
    }
    test_jar = inputs["junit-platform-console-standalone-1.11.0.jar"]
    for side, root in cases.items():
        area = work / side
        lang = inputs["commons-lang3-" + ("3.16.0" if side == "old" else "3.17.0") + ".jar"]
        client, driver, tests = [area / f"{name}.jar" for name in ("client", "driver", "tests")]
        sources = sorted((root / "src/main/java").rglob("*.java"))
        compile_time = compile_jar(jdk, root, sources, [lang], client, [root / "src/main/resources"])
        compile_jar(jdk, root, [HERE / "driver/calibration/CsvFields.java"], [client, lang], driver)
        test_src = root / "src/test/java" / (ENTRY_CLASS.replace(".", "/") + ".java")
        compile_jar(jdk, root, [test_src], [client, lang, test_jar], tests)
        classpath = [driver, client, lang]
        class_log = area / "class-load.log"
        observed, timing = run([jdk / "bin/java", *JVM_FLAGS, f"-Xlog:class+load=info:file={class_log}",
                                "-cp", os.pathsep.join(map(str, classpath)),
                                "calibration.CsvFields", "--all"], root)
        output = area / "observations.jsonl"
        output.write_text(observed.stdout)
        lines = observed.stdout.splitlines()
        mismatches = oracle.problems(lines)
        test = junit(jdk, root, area, [tests, client, lang], test_jar)
        def providers(paths):
            return [{"name": p.name, "sha256": digest(p)} for p in paths]
        declared = {"calibration.CsvFields": driver, "org.apache.commons.text.StringEscapeUtils": client,
                    "org.apache.commons.text.translate.CsvTranslators$CsvEscaper": client,
                    "org.apache.commons.lang3.StringUtils": lang}
        loaded = {}
        for text in class_log.read_text().splitlines():
            subject, _, location = text.rpartition(" source: ")
            name = subject.rsplit(" ", 1)[-1]
            if name in declared:
                actual = Path(unquote(urlparse(location).path)).resolve()
                if actual != declared[name].resolve():
                    raise ValueError(f"{name} loaded from unexpected {actual}")
                with zipfile.ZipFile(actual) as jar:
                    data = jar.read(name.replace(".", "/") + ".class")
                loaded[name] = {"jar": declared[name].name, "classSha256": hashlib.sha256(data).hexdigest()}
        if loaded.keys() != declared.keys():
            raise ValueError(f"missing loaded classes: {declared.keys() - loaded.keys()}")
        row = {
            "loadedClasses": loaded,
            "productionSources": len(sources), "productionClasses": len(list(client.with_suffix(".classes").rglob("*.class"))),
            "productionCompile": compile_time, "jvm": timing, "classpath": providers(classpath), "upstreamJUnit": test,
            "junitLauncher": providers([test_jar])[0], "junitClasspath": providers([tests, client, lang]),
            "observations": len(lines), "normalReturns": sum("returned" in json.loads(line) for line in lines),
            "observationSha256": digest(output), "disagreements": len(mismatches),
            "singleQuote": next(json.loads(line) for line in lines if json.loads(line)["input"] == [34]),
            "firstDifference": mismatches[0] if mismatches else None
        }
        result["sides"][side] = row
        if (len(lines), row["normalReturns"], len(mismatches)) != (156, 156, 71 if side == "mutant" else 0):
            raise ValueError(f"{side}: {row}")
        if side == "mutant":
            if test["csvTest"]["status"] != "failure" or row["singleQuote"]["returned"] != [34, 34, 34]:
                raise ValueError(f"sensitivity control failed: {row}")
        elif test["exit"] or test["failures"] or row["singleQuote"]["returned"] != [34] * 4:
            raise ValueError(f"historical JUnit class or single-quote witness failed: {row}")
    result["finishedUtc"] = stamp()
    save(work / "result.json", result)
    for side, row in result["sides"].items():
        print(f"{side}: {row['observations']} fields, {row['disagreements']} differences, "
              f"original JUnit class {row['upstreamJUnit']['testCount']} tests, "
              f"{len(row['upstreamJUnit']['failures'])} failures")


if __name__ == "__main__":
    main()
