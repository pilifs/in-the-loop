"""Build one pinned organic PR and run the landed regression tests on both production revisions."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import urllib.request
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
CASES = {**CORPUS["cases"], **CORPUS.get("reserves", {}), **CORPUS.get("adoptions", {})}
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
    flags = ["-DskipTests", "-Dinvoker.skip=true"] if case.get("providedHost") or case.get("packageTestJars") else ["-Dmaven.test.skip=true"]
    selection = (["-f", case["module"] + "/pom.xml"] if case.get("prerequisitePoms")
                 else module_args(case, case["module"]))
    return [*OPTIONS, *case.get("mavenProperties", []), *selection, *flags, "install"]


def toolchains(command, case, work, jdk26):
    """Expose the project's requested compilers and test JVMs inside the isolated Maven build."""
    if case["module"] != "guava" and not case.get("providedHost") and not case.get("declaredToolchains"):
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


def packaged_class(case, module, artifact, entry, compiled, packaged):
    """A shading pass may renumber the constant pool in an otherwise unchanged class."""
    if not case.get("qualifyShadedClass"):
        raise ValueError("JAR class differs from the original module compiler output")
    before_shade = module / "target" / ("original-" + artifact.name)
    with zipfile.ZipFile(before_shade) as jar:
        if jar.read(entry) != compiled.read_bytes():
            raise ValueError("the module's pre-shade JAR differs from its compiler product")
    jdk = Path(runtime_jdk.home("21"))
    helper = HERE / "ComparePackagedClass.java"
    with tempfile.TemporaryDirectory(prefix="qualify-shaded-") as tmp:
        altered = Path(tmp) / "packaged.class"
        altered.write_bytes(packaged)
        check = subprocess.run([jdk/"bin/java", "-Djava.io.tmpdir="+tmp, "--add-exports",
            "java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED", helper, compiled, altered],
            text=True, capture_output=True, timeout=45)
        if check.returncode or not re.fullmatch("[a-f0-9]{64}", check.stdout.strip()):
            raise ValueError("the packaged class differs after normalizing the constant pool: "+check.stderr[-400:])
    return {"preShadeJarSha256":digest(before_shade), "compilerClassSha256":digest(compiled),
            "packagedClassSha256":hashlib.sha256(packaged).hexdigest(), "canonicalClassSha256":check.stdout.strip(),
            "normalizerSourceSha256":digest(helper), "normalizerJdkModulesSha256":digest(jdk/"lib/modules")}


def capture(case, side, project, module, local_repo, out, build, cp, jdk, compilers, prerequisites):
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
        packaged = jar.read(cls)
    cls_digest = hashlib.sha256(packaged).hexdigest()
    compiled = module / "target/classes" / cls
    qualification = packaged_class(case, module, original, cls, compiled, packaged) if cls_digest != digest(compiled) else None
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
              "build": {"tool": "maven", "argv": ["mvn", *build_args(case)], "jdk": case.get("buildJdk", "21")}}
    if side == "fix":
        recipe["parent"] = case["parent"]
    checkout = {"commit": revision, "tree": git(project, "rev-parse", "HEAD^{tree}").decode().strip(),
                "parents": git(project, "show", "-s", "--format=%P", "HEAD").decode().split(),
                "fetchedFrom": case["repository"], "changedByBuild": []}
    if git(project, "diff", "--name-only", "HEAD") or (side == "fix" and checkout["parents"][:1] != [case["parent"]]):
        raise ValueError("the production build changed its sources or has a different first parent")
    outputs = {"original": jar_name, "jars": [{"path": jar_name, "sha256": records[0]["sha256"], "auxiliary": False}],
               "selectedClass": cls, "selectedClassSha256": cls_digest, "sourceSha256": digest(project / case["productionSource"])}
    if case.get("buildTool"):
        outputs["buildTool"] = case["buildTool"]
    if qualification:
        outputs["packagedClassQualification"] = qualification
    record = {"schema": "upstream-jar-build/v1", "recipe": recipe, "artifacts": records,
              "build": {"checkout": checkout, "outputs": outputs, "toolchain": {"jdk": runtime_jdk.identity(jdk), "declaredCompilers": compilers},
                        "steps": [*prerequisites, build, cp]}}
    if case.get("providedHost"):
        record["build"]["outputs"]["hostClasspath"] = "Maven runtime, followed by the original module's compile-only entries including its provided Hadoop client"
    upstream_artifact.products(record, {"repository": case["repository"], "commit": revision,
                                       "parent": recipe.get("parent"), **recipe["build"]})
    write(out / ("build-" + side + ".json"), record)
    return outputs


def method_name(name):
    return re.split(r"[\[(]", name, maxsplit=1)[0]


def named_failure(testcase, failed, execution):
    """Surefire can truncate XML stack text at an isolated surrogate. Its text summary retains the source line."""
    method = testcase.get("classname") + "." + method_name(testcase.get("name", ""))
    if method + "(" in (failed.text or ""):
        return "XML stack frame"
    short = method.rsplit(".", 2)[-2:]
    pattern = re.compile(r"^\[ERROR\]\s+" + re.escape(".".join(short)) + r":[1-9][0-9]*\s")
    if failed.tag == "failure" and any(pattern.match(line) for line in execution.get("errors", [])):
        return "Surefire named assertion and source line"
    return None


def tests(case, side, project, command, scratch, out):
    sources = {}
    transplanted = []
    for name in sorted(set(case["tests"].values()) | set(case.get("testFixtures", []))):
        data = git(project, "show", case["fix"] + ":" + name)
        if side == "parent":
            target = project / name
            if not target.is_file() or target.read_bytes() != data:
                transplanted.append(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        if (project / name).read_bytes() != data:
            raise ValueError("the transplanted regression differs from its landed source")
        sources[name] = hashlib.sha256(data).hexdigest()
    if side == "parent":
        # A moved test can retain its old Java package. Leaving its parent copy in
        # place would compile the same class twice. Only move paths in the actual diff.
        moves = git(project, "diff", "--find-renames", "--name-status", case["parent"], case["fix"], "--",
                    ":(glob)**/src/test/**", ":(glob)src/test/**").decode().splitlines()
        for change in moves:
            fields = change.split("\t")
            if len(fields) == 3 and fields[0].startswith("R") and fields[2] in sources:
                (project / fields[1]).unlink()
                transplanted.append(fields[1])
    changed = set(git(project, "diff", "--name-only", "HEAD").decode().splitlines())
    new_sources = git(project, "ls-files", "--others", "--exclude-standard").decode().splitlines()
    changed.update(path for path in new_sources if "/src/" in "/" + path)
    if changed != set(transplanted):
        raise ValueError("the production checkout changed outside the parent test transplant")
    # The Guava testlib's Java 9 descriptor needs the packaged multi-release Guava JAR.
    # A reactor stopped at the test phase substitutes target/classes and loses its descriptor.
    support = None
    test_dependencies = []
    selection = (["-f", case["testModule"] + "/pom.xml"] if case.get("testModuleOnly")
                 else module_args(case, case["testModule"]))
    if case["module"] == "guava":
        support = maven(command, [*OPTIONS, "-f", "guava-testlib/pom.xml", "-Dmaven.test.skip=true", "install"],
                        scratch, "install-original-testlib")
        selection = ["-f", "guava-tests/pom.xml"]
    if case.get("testPrerequisitePoms"):
        for pom in case["testPrerequisitePoms"]:
            test_dependencies.append(maven(command, [*OPTIONS, "-N", "-f", pom, "-Dmaven.test.skip=true", "install"],
                                           scratch, "test-support-" + Path(pom).parent.name))
        selection = ["-f", case["testModule"] + "/pom.xml"]
    selectors = [key + ("*" if key in case.get("testParameters", {}) else "") for key in case["tests"]]
    args = [*OPTIONS, *case.get("mavenProperties", []), *selection, "-Dmaven.build.cache.enabled=false", "-Dsurefire.failIfNoSpecifiedTests=false", "-Dtest=" + ",".join(selectors), "test"]
    run = maven(command, args, scratch, "upstream-tests")
    found = {name: [] for name in case["tests"]}
    for xml in project.glob("**/target/surefire-reports/TEST-*.xml"):
        for t in ET.parse(xml).iter("testcase"):
            name = t.get("classname", "").split(".")[-1] + "#" + method_name(t.get("name", ""))
            if name in found:
                status = next((s for s in ("failure", "error", "skipped") if t.find(s) is not None), "passed")
                row = {"status": status, "class": t.get("classname"), "method": t.get("name"), "xmlSha256": digest(xml)}
                failure = t.find(status) if status in ("failure", "error") else None
                if failure is not None:
                    row.update(failureType=failure.get("type"), message=failure.get("message", "")[:600],
                               atNamedTest=bool(named_failure(t, failure, run)))
                found[name].append(row)
                saved_xml = out / (side + "-" + xml.name + ".gz")
                if not saved_xml.exists():
                    saved_xml.write_bytes(gzip.compress(xml.read_bytes(), mtime=0))
    return {"execution": run, "packagedTestSupport": support, "testPrerequisites": test_dependencies, "testSourceSha256": sources,
            "transplant": sorted(changed), "named": found}


def git_source(args, repository):
    return (args.repos / repository.rsplit("/", 1)[-1]).resolve().as_uri() if args.repos else repository


def build_tool(case, work):
    """Extract just the pinned compiler binary into this isolated build."""
    pin = case.get("buildTool")
    if pin is None:
        return None
    archive = work / "compiler.deb"
    cache = runtime_maven.Cache()
    if not cache.restore(pin["packageSha256"], archive)[0]:
        with urllib.request.urlopen(pin["url"], timeout=60) as response, archive.open("wb") as dest:
            shutil.copyfileobj(response, dest)
        if digest(archive) != pin["packageSha256"]:
            raise ValueError("the compiler package differs from the distribution checksum")
        cache.store(archive, pin["packageSha256"])
    dest = work / "tools" / Path(pin["member"]).name
    dest.parent.mkdir()
    with subprocess.Popen(["dpkg-deb", "--fsys-tarfile", archive], stdout=subprocess.PIPE) as proc:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for member in tar:
                if member.name.removeprefix("./") == pin["member"] and member.isfile():
                    with dest.open("xb") as stream:
                        shutil.copyfileobj(tar.extractfile(member), stream)
        if proc.wait() or not dest.is_file() or digest(dest) != pin["executableSha256"]:
            raise ValueError("the isolated compiler differs from the pinned distribution binary")
    dest.chmod(0o755)
    return pin


def upstream_parents(case, args, work, command, scratch):
    """Install the exact original POMs selected for dated Maven snapshots."""
    steps = []
    for index, parent in enumerate(case.get("buildParents", [])):
        relative = Path("build-parents", str(index))
        project = work / relative
        project.mkdir(parents=True)
        git(project, "init", "-q")
        git(project, "fetch", "-q", "--no-tags", "--depth=1", git_source(args, parent["repository"]), parent["commit"])
        git(project, "checkout", "-q", "--detach", parent["commit"])
        if git(project, "rev-parse", "HEAD").decode().strip() != parent["commit"]:
            raise ValueError("unexpected Maven parent commit")
        for pom in parent["poms"]:
            identity = digest(project / pom)
            step = maven(command, [*OPTIONS, "-N", "-f", str(Path("/work") / relative / pom), "install"],
                         scratch, "external-parent-" + str(len(steps)))
            step.update(repository=parent["repository"], commit=parent["commit"], pom=pom, pomSha256=identity)
            steps.append(step)
            if step["exit"]:
                return steps
        if git(project, "diff", "--name-only", "HEAD"):
            raise ValueError("building the Maven parent modified its tracked source")
    return steps


def qualified_tests(case, side, results):
    for selector in case["tests"]:
        rows = results.get(selector, [])
        parameters = case.get("testParameters", {}).get(selector)
        if parameters is None:
            if len(rows) != 1:
                return False
        else:
            indices = [re.search(r"\[(\d+)\]", row["method"]) for row in rows]
            if not all(indices) or sorted(int(m.group(1)) for m in indices) != sorted(parameters):
                return False
        should_pass = side == "fix" or selector in case.get("parentControls", [])
        for row in rows:
            if should_pass and row["status"] != "passed":
                return False
            if not should_pass and (row["status"] not in ("failure", "error") or not row.get("atNamedTest")):
                return False
    return True


def run_side(case, side, args):
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    jdk = runtime_jdk.home(case.get("buildJdk", "21"))
    status = {"revision": case[side], "side": side}
    with tempfile.TemporaryDirectory(prefix="organic-upstream-") as temp:
        base = Path(temp)
        project, work, scratch, sockets = (base / n for n in ("project", "work", "scratch", "sockets"))
        (work / "home").mkdir(parents=True)
        (scratch / "jvm").mkdir(parents=True)
        sockets.mkdir()
        project.mkdir()
        git(project, "init", "-q")
        origin = git_source(args, case["repository"])
        git(project, "fetch", "-q", "--no-tags", "--depth=2", origin, case["fix"])
        git(project, "checkout", "-q", "--detach", case[side])
        if git(project, "rev-parse", "HEAD").decode().strip() != case[side]:
            raise ValueError("the original checkout differs from the pinned revision")
        tool = build_tool(case, work)
        if tool:
            status["buildTool"] = tool
        command = namespace(project, work, scratch, sockets, args.maven, jdk)
        command, compilers = toolchains(command, case, work, args.jdk26)
        module = project / Path(case["reactorPom"]).parent / case["module"]
        with serve(args.maven_cache, sockets, 3 * 1024**3) as requests:
            prerequisites = upstream_parents(case, args, work, command, base)
            for i, pom in enumerate(case.get("prerequisitePoms", [])):
                # Maven resolves extensions of every module while reading an aggregator.
                # Build the original prerequisite POMs individually when an unrelated distribution module is unavailable.
                step = maven(command, [*OPTIONS, "-N", "-f", pom, "-Dmaven.test.skip=true", "install"],
                             base, "prerequisite-" + str(i))
                prerequisites.append(step)
                if step["exit"]:
                    break
            status["prerequisites"] = prerequisites
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
                        status["artifact"] = capture(case, side, project, module, work / "repository", out, build, cp, jdk, compilers, prerequisites)
                    except (ValueError, OSError, runtime_maven.Blocked) as error:
                        status["artifactError"] = str(error)
            status["upstreamTest"] = tests(case, side, project, command, base, out)
            status["mirror"] = dict(requests)
    write(out / (side + "-upstream.json"), status)
    return "artifact" in status and all(not step["exit"] for step in prerequisites) and qualified_tests(case, side, status["upstreamTest"]["named"])


def bind(case, output):
    """Bind both verified Maven products to the existing public target for offline replay."""
    folder = ROOT / "examples" / case["folder"]
    spec = folder / "target.json"
    target = json.loads(spec.read_text())
    captures = {}
    for side in ("parent", "fix"):
        path = output.resolve() / ("build-" + side + ".json")
        record = json.loads(path.read_text())
        recipe = {"tool": "maven", "argv": ["mvn", *build_args(case)], "jdk": case.get("buildJdk", "21")}
        upstream_artifact.products(record, {"repository": case["repository"], "commit": case[side],
                                           "parent": case["parent"] if side == "fix" else None, **recipe})
        if record["build"]["outputs"]["selectedClass"] != case["productionClass"].replace(".", "/") + ".class":
            raise ValueError("the build captured another production class")
        captures[side] = path.relative_to(folder).as_posix()
    target["preparation"].update(build=recipe, capturedBuilds=captures)
    write(spec, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("--cases", type=Path, help="a campaign manifest of original builds")
    parser.add_argument("--repos", type=Path, help="local clones holding the original public commits")
    parser.add_argument("--maven-cache", type=Path)
    parser.add_argument("--bind-existing", action="store_true", help="bind both collected build records to target.json")
    parser.add_argument("--maven", type=Path, default=Path.home() / ".sdkman/candidates/maven/current")
    parser.add_argument("--jdk26", type=Path, help="pinned Guava build compiler")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())["cases"] if args.cases else CASES
    if args.example not in cases:
        parser.error("unknown example in the selected corpus")
    if args.bind_existing:
        bind(cases[args.example], args.output)
        return 0
    if not args.maven_cache:
        parser.error("a shared --maven-cache is required for original builds")
    results = []
    for side in ("parent", "fix"):
        try:
            passed = run_side(cases[args.example], side, args)
        except (ValueError, OSError, subprocess.SubprocessError, runtime_maven.Blocked) as error:
            write(args.output / (side + "-error.json"), {"revision": cases[args.example][side], "error": str(error)})
            passed = False
        results.append(passed)
        print(args.example, side, "qualified" if passed else "open", flush=True)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
