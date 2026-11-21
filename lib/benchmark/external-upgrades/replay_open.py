"""Rebuild a disclosed consumer observer from a pinned local Git pair and digest-checked JARs."""

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[3]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def classes_digest(folder):
    result = hashlib.sha256()
    for file in sorted(folder.rglob("*.class")):
        result.update(f"{file.relative_to(folder).as_posix()}\0{digest(file)}\n".encode())
    return result.hexdigest()


def run(argv, cwd, check=True):
    result = subprocess.run(list(map(str, argv)), cwd=cwd, capture_output=True, text=True)
    if check and result.returncode:
        raise ValueError(f"{Path(argv[0]).name} exited {result.returncode}\n{(result.stderr + result.stdout)[-3000:]}")
    return result


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def classpath(paths):
    return os.pathsep.join(map(str, paths))


def reference_paths(files):
    return [{"name": p.name, "sha256": classes_digest(p) if p.is_dir() else digest(p)} for p in files]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def original_file(repo, revision, original, dest):
    file = dest / original
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(git(repo, "show", f"{revision}:{original}"))
    return file


def named_test(recipe, repo, rev, jdk, flags, work, src, runtime, jars):
    test = recipe["namedTest"]
    name, method = test["class"], test["method"]
    original = original_file(repo, rev, test["source"], src)
    tests = work / "tests"
    tests.mkdir()
    dependencies = [tests, *runtime, *(jars / f for f in test["dependencies"])]
    provider = ROOT / "examples/348-rxjava-jdbc-generated-keys/independent/NamedSurefire.java"
    run([jdk / "bin/javac", *recipe["javacFlags"], "-d", tests, "-cp", classpath(dependencies),
         original, provider], work)
    start = time.monotonic()
    result = run([jdk / "bin/java", *flags, "-cp", classpath(dependencies),
                  "NamedSurefire", name, method], work, check=False)
    xml = work / "target/surefire-reports" / f"TEST-{name}.xml"
    if not xml.is_file():
        raise ValueError(f"No new Surefire XML for {name}#{method}: {result.stderr[-900:]}")
    cases = ET.parse(xml).getroot().findall("testcase")
    if (len(cases) != 1 or (cases[0].get("classname"), cases[0].get("name")) != (name, method)
            or cases[0].find("skipped") is not None):
        raise ValueError(f"Expected exactly one executed testcase {name}#{method}")
    failure = next((e for e in cases[0] if e.tag in ("failure", "error")), None)
    if result.returncode != int(failure is not None):
        raise ValueError("Surefire exit and testcase disagree")
    return {"class": name, "method": method, "sourceSha256": digest(original), "xmlSha256": digest(xml),
            "status": "passed" if failure is None else failure.tag, "providerExit": result.returncode,
            "exception": None if failure is None else failure.get("type"),
            "message": None if failure is None else failure.get("message"),
            "classpath": reference_paths(dependencies), "elapsedSeconds": round(time.monotonic() - start, 3)}


def observe(recipe, side, folder, repo, work, jars, jdk):
    rev = recipe["revisions"][side]
    work.mkdir()
    src, client, driver = [work / name for name in ("src", "client", "driver")]
    for directory in (src, client, driver):
        directory.mkdir()
    originals = git(repo, "ls-tree", "-r", "--name-only", rev, "--", *recipe["sources"]).decode().splitlines()
    files = [original_file(repo, rev, name, src) for name in originals]
    sources = [file for file in files if file.suffix == ".java"]
    generated = {}
    if "generator" in recipe:
        spec = recipe["generator"]
        tool = jars / spec[side]
        output = work / "generated"
        output.mkdir()
        for grammar in spec["order"]:
            run([jdk / "bin/java", "-jar", tool, "-package", spec["package"], "-o", output,
                 "-lib", output, grammar], src / spec["directory"])
        generated_files = sorted(output.glob("*.java"))
        generated = {"generatorSha256": digest(tool), "java": {p.name: digest(p) for p in generated_files}}
        sources += generated_files
    runtime = [client, *(jars / f for f in recipe["classpath"][side])]
    compile_deps = [*runtime[1:], *(jars / f for f in recipe.get("compileOnly", []))]
    flags = recipe["jvmFlags"]
    start = time.monotonic()
    run([jdk / "bin/javac", *recipe["javacFlags"], "-d", client, "-cp", classpath(compile_deps), *sources], work)
    run([jdk / "bin/javac", *recipe["javacFlags"], "-d", driver, "-cp", classpath(runtime),
         folder / "independent/Observe.java"], work)
    prep = time.monotonic() - start
    start = time.monotonic()
    result = run([jdk / "bin/java", *flags, "-verbose:class", "-cp", classpath([driver, *runtime]),
                  recipe["observer"]], work)
    elapsed = time.monotonic() - start
    lines, loaded = [], []
    for line in result.stdout.splitlines():
        if line.startswith("[Opened "):
            continue
        if line.startswith("[Loaded ") or "][info][class,load]" in line:
            if any(name + " " in line for name in recipe["checkLoaded"]):
                origin = line.split(" from ", 1)[-1].split(" source: ", 1)[-1].rstrip("]")
                name = next(name for name in recipe["checkLoaded"] if name + " " in line)
                loaded.append({"class": name, "from": Path(origin.rstrip("/")).name})
            continue
        lines.append(line)
    expected = {name: recipe["classpath"][side][location] if isinstance(location, int) else location
                for name, location in recipe["checkLoaded"].items()}
    if {row["class"]: row["from"] for row in loaded} != expected:
        raise ValueError(f"Unexpected class origins: {loaded}, expected {expected}")
    image = jdk / recipe["jdkImage"]
    evidence = {"revision": rev, "originalInputs": {str(p.relative_to(src)): digest(p) for p in files},
                "subjectJdkRelease": digest(jdk / "release"), "subjectJdkImage": digest(image),
                "classpath": reference_paths([driver, *runtime]), "compileClasspath": reference_paths(compile_deps),
                "loaded": loaded, "observations": lines,
                "prepSeconds": round(prep, 3), "observationSeconds": round(elapsed, 3)}
    publication = jars / recipe["compareWithPublished"]
    with zipfile.ZipFile(publication) as archive:
        classes = sorted(client.rglob("*.class"))
        entries = {name for name in archive.namelist() if name.endswith(".class")}
        different = [p.relative_to(client).as_posix() for p in classes
                     if p.relative_to(client).as_posix() not in entries
                     or p.read_bytes() != archive.read(p.relative_to(client).as_posix())]
    evidence["publishedComparison"] = {"jar": publication.name, "sha256": digest(publication),
                                       "classes": len(classes), "different": different}
    if recipe["requiresPublishedEquality"]:
        require(bool(classes) and not different, "caller class files differ from the recorded release")
    if generated:
        evidence["generated"] = generated
    if "namedTest" in recipe:
        evidence["namedTest"] = named_test(recipe, repo, rev, jdk, flags, work, src, runtime, jars)
    return evidence


def grade(number, sides):
    old, new = [sides[s]["observations"] for s in ("old", "new")]
    if number == "350":
        expected_prefix = ["reject", "com.fizzed.rocker.runtime.ParserException", "1", "18"]
        valid = 'return\t1\tString\ts\t"test"'
        for result in (old, new):
            require(len(result) == 2 and result[0].split("\t")[:4] == expected_prefix and result[1] == valid,
                    "Rocker rejection, position or valid declaration differs")
        require("missing ARGUMENT at '<EOF>'" in old[0] and "extraneous input '<EOF>'" in new[0],
                "Rocker diagnostics did not reproduce")
        require(sides["old"]["generated"]["java"] != sides["new"]["generated"]["java"],
                "expected independently regenerated parser sources")
    elif number == "351":
        require(len(old) == len(new) == 4, "expected four SDK observations per revision")
        limit = "9223372036854775807"
        before = ["formatter", limit, "292278994-08-17T07:12:55.807Z"]
        require(old[0].split("\t")[:5] == before + ["throw", "org.joda.time.IllegalFieldValueException"],
                "original exception or formatted instant differs")
        require(new[0].split("\t") == before + ["return", limit], "new formatter did not return the maximum instant")
        require(old[1:] == new[1:], "SDK companion behavior differs")
        require(old[1].split("\t") == ["sdk", *before[1:], "return", limit], "public SDK maximum instant differs")
        for prefix, line in zip(("formatter", "sdk"), old[2:]):
            require(line.split("\t") == [prefix, "946684800123", "2000-01-01T00:00:00.123Z", "return", "946684800123"],
                    "ordinary date failed to round-trip")
    elif number == "352":
        domain = itertools.product((0, 1, 59), (0, 1, 999), (0, 999999))
        expected = []
        for seconds, millis, remainder in domain:
            nanos = (seconds * 1000 + millis) * 1000000 + remainder
            expected.append(f"{nanos}\t{nanos}\t{seconds}.{millis:03d}")
        require(old == expected and new == expected, "incomplete duration grid or incorrect millisecond rendering")
    if "namedTest" in sides["old"]:
        require(sides["old"]["namedTest"]["status"] == "passed", "old named testcase did not pass")
        require(sides["new"]["namedTest"]["status"] in ("failure", "error"), "new named testcase did not fail")


def substitute_parser_runtime(recipe, dest, jars, jdk):
    trials = {}
    for generated in ("old", "new"):
        for runtime in ("old", "new"):
            output = dest / generated
            dependencies = [output / "driver", output / "client", *(jars / n for n in recipe["classpath"][runtime])]
            result = run([jdk / "bin/java", *recipe["jvmFlags"], "-cp", classpath(dependencies),
                          recipe["observer"]], output, check=False)
            trials[f"{generated}-generator_{runtime}-runtime"] = {
                "exit": result.returncode, "observations": result.stdout.splitlines(), "stderr": result.stderr.splitlines(),
                "classpath": reference_paths(dependencies)}
    return trials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=("350", "351", "352"))
    parser.add_argument("--repo", required=True, type=Path, help="Git repository containing both pinned revisions")
    parser.add_argument("--jars", required=True, type=Path, help="local files named in materials.json")
    parser.add_argument("--jdk", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="fresh run directory")
    args = parser.parse_args()
    folder = next((ROOT / "examples").glob(args.example + "-*"))
    recipe = json.loads((folder / "materials.json").read_text())
    require(digest(args.jdk / "release") == recipe["subjectJdk"]["releaseSha256"] and
            digest(args.jdk / recipe["jdkImage"]) == recipe["subjectJdk"]["imageSha256"],
            "subject JDK differs from the calibration lock")
    for name, item in recipe["jars"].items():
        if digest(args.jars / name) != item["sha256"]:
            raise ValueError(f"{name} differs from the calibration lock")
    old, new = (recipe["revisions"][s] for s in ("old", "new"))
    if git(args.repo, "rev-parse", new + "^").decode().strip() != old:
        raise ValueError("Upstream parent differs from the frozen pair")
    changes = git(args.repo, "diff", "--name-only", old, new).decode().splitlines()
    if changes != [recipe["changedPom"]]:
        raise ValueError(f"Unexpected tracked changes: {changes}")
    dest = args.out.resolve()
    dest.mkdir(parents=True, exist_ok=False)
    capture = {"example": args.example, "recipeSha256": digest(folder / "materials.json"),
               "observerSha256": digest(folder / "independent/Observe.java"), "changedPaths": changes, "sides": {}}
    for side in ("old", "new"):
        capture["sides"][side] = observe(recipe, side, folder, args.repo.resolve(), dest / side,
                                         args.jars.resolve(), args.jdk.resolve())
        (dest / "observations.json").write_text(json.dumps(capture, indent=2) + "\n")
    grade(args.example, capture["sides"])
    if "generator" in recipe:
        cross = substitute_parser_runtime(recipe, dest, args.jars.resolve(), args.jdk.resolve())
        (dest / "controlled-substitution.json").write_text(json.dumps(cross, indent=2) + "\n")
        for old_or_new in ("old", "new"):
            require(cross[f"{old_or_new}-generator_{old_or_new}-runtime"]["observations"] ==
                    capture["sides"][old_or_new]["observations"], "classpath substitution changed a matched control")
    print(f"{args.example} independently checked both JVM observations; evidence in {dest / 'observations.json'}")


if __name__ == "__main__":
    main()
