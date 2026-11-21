"""Build one pinned organic PR and run the landed regression tests on both production revisions."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(HERE.parent / "external-upgrades/baselines"))
from targets import runtime_jdk, runtime_maven, upstream_artifact
from public_ci import digest, namespace
from maven_mirror import serve

CORPUS = json.loads((HERE / "cases.json").read_text())
CASES = {**CORPUS["cases"], **CORPUS.get("reserves", {})}
OPTIONS = ["--batch-mode", "--no-transfer-progress", "-Dmaven.javadoc.skip=true", "-Drat.skip=true",
           "-Dcheckstyle.skip=true", "-Dspotless.skip=true", "-Dspotbugs.skip=true", "-Dgpg.skip=true"]
DEPENDENCIES = "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")


def git(repo, *args):
    return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args])


def module_args(case, module):
    selection = ["-f", case["reactorPom"]]
    if module != ".":
        selection.extend(["-pl", module, "-am"])
    return selection


def build_args(case):
    # The Avro reactor publishes test JARs for its dependents. Package them while leaving the
    # separate invoker cross-JDK compatibility suite to upstream CI.
    flags = ["-DskipTests", "-Dinvoker.skip=true"] if case.get("providedHost") else ["-Dmaven.test.skip=true"]
    return [*OPTIONS, *module_args(case, case["module"]), *flags, "install"]


def toolchains(command, case, work, jdk26):
    """Expose the project's requested compilers and test JVMs inside the isolated Maven build."""
    if case["module"] != "guava" and not case.get("providedHost"):
        return command, {}
    homes = {v: runtime_jdk.home(v) for v in ("11", "17", "21")}
    if case["module"] == "guava":
        homes["26"] = jdk26 or runtime_jdk.home("26")
        if homes["26"] is None:
            raise ValueError("Guava requires Temurin 26 for compilation")
        pin = json.loads((HERE / "temurin26.json").read_text())
        if digest(homes["26"] / "lib/modules") != pin["moduleImageSha256"]:
            raise ValueError("Guava compiler differs from the pinned Temurin 26 module image")
    mounts, identities = [], {}
    if case.get("providedHost"):
        # Hadoop's original Job.getInstance uses UnixLoginModule during its JUnit setup.
        # Supply the isolated build's actual UID in its own passwd database.
        uid, gid = os.geteuid(), os.getegid()
        (work / "passwd").write_text(f"builder:x:{uid}:{gid}:Build user:/work/home:/bin/sh\n")
        (work / "group").write_text(f"builder:x:{gid}:\n")
        for name in ("passwd", "group"):
            mounts.extend(["--ro-bind", str(work / name), "/etc/" + name])
    document = ET.Element("toolchains")
    for version, home in homes.items():
        if home is None:
            raise ValueError(f"missing required JDK {version}")
        home = Path(home)
        guest = "/opt/java-" + version
        mounts.extend(["--ro-bind", str(home.resolve()), guest])
        identities[version] = runtime_jdk.identity(home)
        for kind in (("jdk", "testJdk") if version == "21" else ("jdk",)):
            chain = ET.SubElement(document, "toolchain")
            ET.SubElement(chain, "type").text = kind
            provides = ET.SubElement(chain, "provides")
            ET.SubElement(provides, "version").text = version
            ET.SubElement(provides, "vendor").text = "temurin"
            ET.SubElement(ET.SubElement(chain, "configuration"), "jdkHome").text = guest
    where = work / "home/.m2/toolchains.xml"
    where.parent.mkdir(exist_ok=True)
    ET.ElementTree(document).write(where, encoding="utf-8", xml_declaration=True)
    i = command.index("--chdir")
    return [*command[:i], *mounts, *command[i:]], identities


def maven(command, args, directory, name):
    start = time.monotonic()
    log = directory / (name + ".log")
    with log.open("wb") as stream:
        try:
            code = subprocess.run([*command, *args], stdout=stream, stderr=subprocess.STDOUT, timeout=1000).returncode
        except subprocess.TimeoutExpired:
            code = 124
    lines = log.read_text(errors="replace").splitlines()
    return {"argv": ["mvn", *args], "exit": code, "seconds": round(time.monotonic() - start, 2),
            "logSha256": digest(log), "errors": [s[:650] for s in lines if s.startswith("[ERROR]")][:12],
            "tail": lines[-9:]}


def capture(case, side, project, module, local_repo, out, build, cp, jdk, compilers):
    """Store only JARs from the original owning module and Maven's ordered runtime resolution."""
    revision = case[side]
    cls = case["productionClass"].replace(".", "/") + ".class"
    candidates = []
    for path in sorted((module / "target").glob("*.jar")):
        if path.name.endswith(("-sources.jar", "-javadoc.jar", "-tests.jar")) or path.name.startswith("original-"):
            continue
        with zipfile.ZipFile(path) as jar:
            if cls in jar.namelist():
                candidates.append(path)
    if len(candidates) != 1:
        raise ValueError(f"expected one original {cls} provider in this module, found {candidates}")
    original, = candidates
    with zipfile.ZipFile(original) as jar:
        cls_digest = hashlib.sha256(jar.read(cls)).hexdigest()
    if cls_digest != digest(module / "target/classes" / cls):
        raise ValueError("JAR class differs from the original module compiler output")
    cache = runtime_maven.Cache()
    records = []

    def add(path, relative, role, coords, origin):
        checksum = digest(path)
        cache.store(path, checksum)
        records.append({"path": relative, "sha256": checksum, "role": role, "coordinates": coords, "origin": origin})

    jar_name = original.relative_to(project).as_posix()
    add(original, "built/" + original.name, "original", None,
        f"built by maven from {case['repository']} at {revision}: {jar_name}")
    listing = (module / "target/organic-runtime.txt").read_text().strip()
    entries = listing.split(":") if listing else []
    provided = module / "target/organic-compile.txt"
    if case.get("providedHost"):
        declared = ET.parse(module / "pom.xml").findall(".//{*}dependencies/{*}dependency")
        if not any((d.findtext("{*}groupId") + ":" + d.findtext("{*}artifactId")) == case["providedHost"]
                   and d.findtext("{*}scope") == "provided" for d in declared):
            raise ValueError("the original Avro module did not declare its Hadoop host")
        for item in provided.read_text().strip().split(":"):
            if item and item not in entries:
                entries.append(item)
    for item in entries:
        relative = Path(item).relative_to("/work/repository")
        if ".." in relative.parts:
            raise ValueError("dependency outside the resolved Maven repository")
        path = local_repo / relative
        parts = relative.parts
        coords = ".".join(parts[:-3]) + ":" + parts[-3] + ":" + parts[-2]
        installed = (path.parent.parent / "maven-metadata-local.xml").is_file()
        add(path, "lib/" + relative.as_posix(), "dependency", coords,
            "installed in the build's local repository by the recipe" if installed else
            "resolved by Maven from Maven Central (the build's one repository), checksums strict")
    recipe = {"repository": case["repository"], "commit": revision, "class": case["productionClass"],
              "build": {"tool": "maven", "argv": ["mvn", *build_args(case)], "jdk": "21"}}
    if side == "fix":
        recipe["parent"] = case["parent"]
    checkout = {"commit": revision, "tree": git(project, "rev-parse", "HEAD^{tree}").decode().strip(),
                "parents": git(project, "show", "-s", "--format=%P", "HEAD").decode().split(),
                "fetchedFrom": case["repository"], "changedByBuild": []}
    if git(project, "diff", "--name-only", "HEAD") or (side == "fix" and checkout["parents"][:1] != [case["parent"]]):
        raise ValueError("the production build changed its sources or has a different first parent")
    outputs = {"original": jar_name, "jars": [{"path": jar_name, "sha256": records[0]["sha256"], "auxiliary": False}],
               "selectedClass": cls, "selectedClassSha256": cls_digest, "sourceSha256": digest(project / case["productionSource"])}
    record = {"schema": "upstream-jar-build/v1", "recipe": recipe, "artifacts": records,
              "build": {"checkout": checkout, "outputs": outputs, "toolchain": {"jdk": runtime_jdk.identity(jdk), "declaredCompilers": compilers},
                        "steps": [build, cp]}}
    if case.get("providedHost"):
        record["build"]["outputs"]["hostClasspath"] = "Maven runtime, followed by the original module's compile-only entries including its provided Hadoop client"
    upstream_artifact.products(record, {"repository": case["repository"], "commit": revision,
                                       "parent": recipe.get("parent"), **recipe["build"]})
    write(out / ("build-" + side + ".json"), record)
    return outputs


def tests(case, side, project, command, scratch, out):
    sources = {}
    for name in set(case["tests"].values()):
        data = git(project, "show", case["fix"] + ":" + name)
        if side == "parent":
            (project / name).write_bytes(data)
        if (project / name).read_bytes() != data:
            raise ValueError("the transplanted regression differs from its landed source")
        sources[name] = hashlib.sha256(data).hexdigest()
    changed = set(git(project, "diff", "--name-only", "HEAD").decode().splitlines())
    if (side == "fix" and changed) or not changed.issubset(sources):
        raise ValueError("the production checkout changed outside the parent test transplant")
    # The Guava testlib's Java 9 descriptor needs the packaged multi-release Guava JAR.
    # A reactor stopped at the test phase substitutes target/classes and loses its descriptor.
    support = None
    selection = module_args(case, case["testModule"])
    if case["module"] == "guava":
        support = maven(command, [*OPTIONS, "-f", "guava-testlib/pom.xml", "-Dmaven.test.skip=true", "install"],
                        scratch, "install-original-testlib")
        selection = ["-f", "guava-tests/pom.xml"]
    args = [*OPTIONS, *selection, "-Dmaven.build.cache.enabled=false", "-Dsurefire.failIfNoSpecifiedTests=false", "-Dtest=" + ",".join(case["tests"]), "test"]
    run = maven(command, args, scratch, "upstream-tests")
    found = {name: [] for name in case["tests"]}
    for xml in project.glob("**/target/surefire-reports/TEST-*.xml"):
        for t in ET.parse(xml).iter("testcase"):
            name = t.get("classname", "").split(".")[-1] + "#" + t.get("name", "").split("(")[0]
            if name in found:
                status = next((s for s in ("failure", "error", "skipped") if t.find(s) is not None), "passed")
                row = {"status": status, "class": t.get("classname"), "method": t.get("name"), "xmlSha256": digest(xml)}
                failure = t.find(status) if status in ("failure", "error") else None
                if failure is not None:
                    row.update(failureType=failure.get("type"), message=failure.get("message", "")[:600],
                               atNamedTest=(t.get("classname") + "." + t.get("name") + "(") in (failure.text or ""))
                found[name].append(row)
                (out / (side + "-" + xml.name + ".gz")).write_bytes(gzip.compress(xml.read_bytes(), mtime=0))
    return {"execution": run, "packagedTestSupport": support, "testSourceSha256": sources,
            "transplant": sorted(changed), "named": found}


def run_side(case, side, args):
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    jdk = runtime_jdk.home("21")
    status = {"revision": case[side], "side": side}
    with tempfile.TemporaryDirectory(prefix="organic-upstream-") as temp:
        base = Path(temp)
        project, work, scratch, sockets = (base / n for n in ("project", "work", "scratch", "sockets"))
        (work / "home").mkdir(parents=True)
        (scratch / "jvm").mkdir(parents=True)
        sockets.mkdir()
        project.mkdir()
        git(project, "init", "-q")
        origin = (args.repos / case["repository"].rsplit("/", 1)[-1]).resolve().as_uri() if args.repos else case["repository"]
        git(project, "fetch", "-q", "--no-tags", "--depth=2", origin, case["fix"])
        git(project, "checkout", "-q", "--detach", case[side])
        if git(project, "rev-parse", "HEAD").decode().strip() != case[side]:
            raise ValueError("the original checkout differs from the pinned revision")
        command = namespace(project, work, scratch, sockets, args.maven, jdk)
        command, compilers = toolchains(command, case, work, args.jdk26)
        module = project / Path(case["reactorPom"]).parent / case["module"]
        with serve(args.maven_cache, sockets, 3 * 1024**3) as requests:
            build = maven(command, build_args(case), base, "module-build")
            status["build"] = build
            if build["exit"] == 0:
                cp = maven(command, [*OPTIONS, "-f", str((module / "pom.xml").relative_to(project)),
                                     DEPENDENCIES, "-DincludeScope=runtime", "-Dmdep.outputFile=" +
                                     str(Path("/project") / module.relative_to(project) / "target/organic-runtime.txt")],
                           base, "classpath")
                if cp["exit"] == 0 and case.get("providedHost"):
                    host = maven(command, [*OPTIONS, "-f", str((module / "pom.xml").relative_to(project)),
                                 DEPENDENCIES, "-DincludeScope=compile", "-Dmdep.outputFile=" +
                                 str(Path("/project") / module.relative_to(project) / "target/organic-compile.txt")],
                                 base, "host-classpath")
                    status["providedClasspath"] = host
                    if host["exit"] != 0:
                        cp = host
                status["classpath"] = cp
                if cp["exit"] == 0:
                    try:
                        status["artifact"] = capture(case, side, project, module, work / "repository", out, build, cp, jdk, compilers)
                    except (ValueError, OSError, runtime_maven.Blocked) as error:
                        status["artifactError"] = str(error)
            status["upstreamTest"] = tests(case, side, project, command, base, out)
            status["mirror"] = dict(requests)
    write(out / (side + "-upstream.json"), status)
    expected = {"failure", "error"} if side == "parent" else {"passed"}
    return "artifact" in status and all(len(rows) == 1 and rows[0]["status"] in expected
            and (side == "fix" or rows[0].get("atNamedTest"))
            for rows in status["upstreamTest"]["named"].values())


def bind(case, output):
    """Bind both verified Maven products to the existing public target for offline replay."""
    folder = ROOT / "examples" / case["folder"]
    spec = folder / "target.json"
    target = json.loads(spec.read_text())
    captures = {}
    for side in ("parent", "fix"):
        path = output.resolve() / ("build-" + side + ".json")
        record = json.loads(path.read_text())
        recipe = {"tool": "maven", "argv": ["mvn", *build_args(case)], "jdk": "21"}
        upstream_artifact.products(record, {"repository": case["repository"], "commit": case[side],
                                           "parent": case["parent"] if side == "fix" else None, **recipe})
        if record["build"]["outputs"]["selectedClass"] != case["productionClass"].replace(".", "/") + ".class":
            raise ValueError("the build captured another production class")
        captures[side] = path.relative_to(folder).as_posix()
    target["preparation"].update(build=recipe, capturedBuilds=captures)
    write(spec, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=CASES)
    parser.add_argument("--repos", type=Path, help="local clones holding the original public commits")
    parser.add_argument("--maven-cache", type=Path)
    parser.add_argument("--bind-existing", action="store_true", help="bind both collected build records to target.json")
    parser.add_argument("--maven", type=Path, default=Path.home() / ".sdkman/candidates/maven/current")
    parser.add_argument("--jdk26", type=Path, help="pinned Guava build compiler")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.bind_existing:
        bind(CASES[args.example], args.output)
        return 0
    if not args.maven_cache:
        parser.error("a shared --maven-cache is required for original builds")
    results = []
    for side in ("parent", "fix"):
        try:
            passed = run_side(CASES[args.example], side, args)
        except (ValueError, OSError, subprocess.SubprocessError, runtime_maven.Blocked) as error:
            write(args.output / (side + "-error.json"), {"revision": CASES[args.example][side], "error": str(error)})
            passed = False
        results.append(passed)
        print(args.example, side, "qualified" if passed else "open", flush=True)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
