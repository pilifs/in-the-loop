"""Run the disclosed upstream Linux CI lifecycle with original sources and a serial Maven Central mirror."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from xml.etree import ElementTree as ET

import maven_mirror


HERE = Path(__file__).resolve().parent
CACHE = Path.home() / ".cache/in-the-loop/external-upgrades"
CASES = {
    "348": {
        "client": "rxjava-jdbc", "old": "5e04239e1f831878884972fbf72ab1f529b0647d",
        "new": "735c4108c0ebfd9ad4f350d496e9c74bc0893bb7", "jdk": "8.0.512.0+9-tem",
        "workflow": ".travis.yml", "argv": ["--batch-mode", "test"],
        "suite": "com.github.davidmoten.rx.jdbc.DatabaseSyncTest",
    },
    "349": {
        "client": "commons-text",
        "old": "c252787dca5fe36e1f1f6c131061bbf016b1e1b6", "new": "a8e4f42ef23fe396a7c45df3124157401c0da17c",
        "jdk": "21.0.13.0+9-tem", "workflow": ".github/workflows/maven.yml",
        "argv": ["--errors", "--show-version", "--batch-mode", "--no-transfer-progress",
                 "-Dpolyglot.engine.WarnInterpreterOnly=false"],
        "suite": "org.apache.commons.text.StringEscapeUtilsTest",
    },
    "352": {
        "client": "cucumber-reporting",
        "old": "9e98993fbccbdd19a6be628fd9dcc4d8e2a4ff79", "new": "29697966eacf46448a806ea03c6dd2d10e2665ec",
        "jdk": "11.0.33.0+10-tem", "workflow": ".github/workflows/build.yml",
        "argv": ["--batch-mode", "verify"], "suite": "net.masterthought.cucumber.json.ResultTest",
    },
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def guest(arguments):
    port = maven_mirror.guest_server()
    settings = Path("/work/settings.xml")
    settings.write_text(f"<settings><localRepository>/work/repository</localRepository>"
                        f"<mirrors><mirror><id>isolated-central</id><mirrorOf>*</mirrorOf>"
                        f"<url>http://127.0.0.1:{port}/</url></mirror></mirrors></settings>\n")
    if len(arguments) == 2 and arguments[0] == "--stock-compcheck" and re.fullmatch(r"c[0-9]+-[0-9]+", arguments[1]):
        default = Path("/work/home/.m2")
        default.mkdir(exist_ok=True)
        shutil.copyfile(settings, default / "settings.xml")
        # The stock tool locates JARs under ~/.m2/repository, and Maven writes into /work/repository.
        (default / "repository").symlink_to("/work/repository", target_is_directory=True)
        os.environ["MAVEN_OPTS"] += " -Dmaven.artifact.threads=1 -Daether.connector.basic.threads=1 -Daether.metadataResolver.threads=1"
        return subprocess.call(["python3", "main.py", "--check", "--id", arguments[1]], cwd="/project/compcheck")
    if arguments[:1] == ["--stock-compsuite"]:
        default = Path("/work/home/.m2")
        default.mkdir(exist_ok=True)
        shutil.copyfile(settings, default / "settings.xml")
        os.environ["MAVEN_OPTS"] += " -Dmaven.artifact.threads=1 -Daether.connector.basic.threads=1 -Daether.metadataResolver.threads=1"
        suite = Path("/work/compsuite")
        (suite / "repos").mkdir()
        (suite / "repos/rxjava-jdbc").symlink_to("/project")
        (suite / "logs").mkdir()
        interpreter = "/opt/python/bin/python3.11"
        subprocess.run([interpreter, "--version"], check=True)
        if arguments[1] == "combined":
            subprocess.run([interpreter, "main.py", "--info", "i-87"], cwd=suite, check=True)
        flag = {"combined": "--incompat", "old": "--testold", "new": "--testnew"}[arguments[1]]
        return subprocess.call([interpreter, "main.py", flag, "i-87"], cwd=suite)
    if arguments == ["--smoke"]:
        from urllib.request import urlopen
        path = "junit/junit/4.12/junit-4.12.jar"
        with urlopen(f"http://127.0.0.1:{port}/{path}", timeout=10) as body:
            print(hashlib.sha256(body.read()).hexdigest(), flush=True)
        if Path("/opt/python/bin/python3.11").exists():
            subprocess.run(["/opt/python/bin/python3.11", "--version"], check=True)
            subprocess.run(["/opt/python/bin/python3.11", "/work/compsuite/main.py", "--info", "i-87"], check=True)
        return subprocess.call(["mvn", "--version"])
    return subprocess.call(["mvn", "--settings", str(settings), "-T", "1", "-Dmaven.repo.local=/work/repository",
                            "-Dmaven.artifact.threads=1", "-Daether.connector.basic.threads=1",
                            "-Daether.metadataResolver.threads=1", *arguments])


def namespace(project, work, scratch, socket_dir, maven, jdk, python=None):
    cmd = ["bwrap", "--unshare-all", "--unshare-user", "--disable-userns", "--die-with-parent", "--new-session",
           "--cap-drop", "ALL", "--clearenv", "--ro-bind", "/usr", "/usr"]
    for name in ("bin", "sbin", "lib", "lib64"):
        path = Path("/") / name
        if path.is_symlink():
            cmd += ["--symlink", os.readlink(path), str(path)]
        elif path.exists():
            cmd += ["--ro-bind", str(path), str(path)]
    cmd += ["--ro-bind", str(maven), "/opt/maven", "--ro-bind", str(jdk), "/opt/jdk"]
    if python is not None:
        cmd += ["--ro-bind", str(python), "/opt/python"]
    for file in ("public_ci.py", "maven_mirror.py"):
        cmd += ["--ro-bind", str(HERE / file), "/control/" + file]
    hosts = work / "hosts"
    hosts.write_text("127.0.0.1 localhost ci-host\n::1 localhost ci-host\n")
    cmd += ["--hostname", "ci-host", "--ro-bind", str(hosts), "/etc/hosts",
            "--bind", str(work), "/work", "--bind", str(project), "/project",
            "--bind", str(scratch), "/scratch", "--symlink", "/scratch", "/tmp",
            "--ro-bind", str(socket_dir), "/mirror", "--proc", "/proc", "--dev", "/dev"]
    env = {"HOME": "/work/home", "PATH": "/opt/jdk/bin:/opt/maven/bin:/usr/bin", "JAVA_HOME": "/opt/jdk",
           "MAVEN_OPTS": "-Duser.home=/work/home", "JAVA_TOOL_OPTIONS": "-Djava.io.tmpdir=/scratch/jvm -Duser.home=/work/home",
           "TMPDIR": "/scratch", "TZ": "UTC", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    for name, value in env.items():
        cmd += ["--setenv", name, value]
    return [*cmd, "--chdir", "/project", "--", "python3", "/control/public_ci.py", "guest"]


def collect(project, suite, out):
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    named, failures, reports = [], [], {}
    for file in sorted(project.rglob("TEST-*.xml")):
        if file.parent.name not in {"surefire-reports", "failsafe-reports"}:
            continue
        reports[file.relative_to(project).as_posix()] = digest(file)
        data = ET.parse(file)
        for test in data.iter("testcase"):
            reason = next((t for t in ("failure", "error", "skipped") if test.find(t) is not None), None)
            counts["tests"] += 1
            if reason:
                counts[{"failure": "failures", "error": "errors", "skipped": "skipped"}[reason]] += 1
            if reason in {"failure", "error"}:
                failures.append({"class": test.get("classname"), "name": test.get("name"),
                                 "outcome": reason, "type": test.find(reason).get("type")})
            if test.get("classname") == suite:
                named.append({"name": test.get("name"), "outcome": reason or "passed"})
        if any(test.get("classname") == suite for test in data.iter("testcase")):
            (out / (file.name + ".gz")).write_bytes(gzip.compress(file.read_bytes(), mtime=0))
    return {"counts": counts, "namedSuite": suite, "namedTests": named, "nonpassing": failures, "xmlSha256": reports}


def run(args):
    case = CASES[args.example]
    repo = args.repo or CACHE / "ci-sources" / (case["client"] + ".git")
    default_maven = (CACHE / "ci-tools/apache-maven-3.6.3" if args.example == "348"
                     else Path.home() / ".sdkman/candidates/maven/3.10.0")
    maven = (args.maven or default_maven).resolve(strict=True)
    python = CACHE / "ci-tools/cpython-3.11.14" if args.stock_compsuite else None
    jdk = (args.jdk or (Path.home() / ".sdkman/candidates/java" / case["jdk"])).resolve(strict=True)
    repository = args.repository.resolve(strict=True)
    source_diff = subprocess.check_output(["git", "-C", repo, "diff", "--name-only", case["old"], case["new"]], text=True)
    if source_diff.splitlines() != ["pom.xml"]:
        raise ValueError("expected the original POM-only proposed change")
    supplied_tmp = Path(os.environ.get("TMPDIR", "/tmp")).resolve()
    tmp = supplied_tmp if supplied_tmp.is_relative_to(Path.home() / ".cache/in-the-loop") else CACHE / "ci-tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    evidence = {"example": args.example, "ciWorkflow": case["workflow"], "subjectJdk": jdk.name,
                "jdkReleaseSha256": digest(jdk / "release"), "mavenCoreSha256": digest(next((maven / "lib").glob("maven-core-*.jar"))),
                "originalGoals": case["argv"], "host": "Linux", "dependencySource": maven_mirror.CENTRAL,
                "historicalMatrixCoverage": "one Linux JDK per revision", "sides": {}}
    with tempfile.TemporaryDirectory(dir=tmp) as area:
        area = Path(area)
        sockets = area / "mirror"
        sockets.mkdir()
        with maven_mirror.serve(repository, sockets, 3 * 1024**3) as counters:
            sides = ("new",) if args.smoke else ("combined", "old", "new") if args.stock_compsuite else ("old", "new")
            for side in sides:
                baseline = dict(counters)
                side_dir = area / side
                side_dir.mkdir()
                project, work, scratch = (side_dir / name for name in ("project", "work", "scratch"))
                (work / "home").mkdir(parents=True)
                (scratch / "jvm").mkdir(parents=True)
                subprocess.run(["git", "clone", "--quiet", "--no-checkout", "--no-hardlinks", str(repo), project], check=True)
                revision = case["new" if side == "combined" else side]
                subprocess.run(["git", "-C", project, "checkout", "--quiet", "--detach", revision], check=True)
                out = args.out / side
                out.mkdir()
                log = side_dir / "maven.log"
                clock = time.monotonic()
                goals = ["--smoke"] if args.smoke else case["argv"]
                if args.stock_compsuite:
                    reference = HERE.parents[3] / "examples/348-rxjava-jdbc-generated-keys/records/compsuite-cli.json"
                    expected = {r["file"]: r["sha256"] for r in json.loads(reference.read_bytes())["unchangedScriptSources"]}
                    expected["incompatibilities.json"] = "ceff4d4209e1798db3b008824ba45e05a93bd16ade7afdaaafd404493a82123e"
                    interpreter = json.loads((reference.parent / "comp-suite-python.json").read_bytes())
                    if any(digest(python / name) != checksum for name, checksum in interpreter["installedFilesSha256"].items()):
                        raise ValueError("CompSuite CPython differs from the independently verified distribution")
                    if evidence["mavenCoreSha256"] != "f572ed9e2a6ea3e30522d13448c5d9b3b80ce62a23dac652111952d4941e2a3b":
                        raise ValueError("CompSuite reference environment requires the original Maven 3.6.3 core")
                    suite = work / "compsuite"
                    suite.mkdir()
                    for name, checksum in expected.items():
                        shutil.copyfile(CACHE / "ci-tools/compsuite-6e6d738c8b0c-i87" / name, suite / name)
                        if digest(suite / name) != checksum:
                            raise ValueError("original CompSuite script or entry differs")
                    evidence["compsuiteSources"] = expected
                    evidence["python311Sha256"] = digest(python / "bin/python3.11")
                    if not args.smoke:
                        goals = ["--stock-compsuite", side]
                with log.open("wb") as stream:
                    command = namespace(project, work, scratch, sockets, maven, jdk, python)
                    try:
                        status = subprocess.run([*command, *goals],
                                                stdout=stream, stderr=subprocess.STDOUT,
                                                timeout=max(1, 7200 - (clock - start))).returncode
                    except subprocess.TimeoutExpired:
                        status = "timeout"
                text = log.read_text(errors="replace").splitlines()
                log_gz = out / "maven.log.gz"
                with log.open("rb") as source, gzip.GzipFile(filename=str(log_gz), mode="wb", mtime=0) as target:
                    shutil.copyfileobj(source, target)
                row = {**collect(project, case["suite"], out), "revision": revision,
                       "workflowSha256": digest(project / case["workflow"]), "exit": status,
                       "seconds": round(time.monotonic() - clock, 3), "logSha256": digest(log),
                       "resolver": {k: v - baseline.get(k, 0) for k, v in counters.items()},
                       "firstErrors": [line[:550] for line in text if line.startswith("[ERROR]")][:8]}
                row["mavenStarted"] = any("Scanning for projects" in line for line in text)
                if status == "timeout":
                    row["ciOutcome"] = "timeout"
                elif args.stock_compsuite and not args.smoke:
                    row["wrapper"] = goals
                    row["wrapperMessages"] = text
                    row["originalMavenLogs"] = {}
                    for raw in sorted((work / "compsuite/logs").rglob("*.log")):
                        name = raw.name
                        original = raw.read_bytes()
                        (out / (name + ".gz")).write_bytes(gzip.compress(original, mtime=0))
                        row["originalMavenLogs"][name] = digest(raw)
                        if b"Scanning for projects" in original:
                            row["mavenStarted"] = True
                    row["ciOutcome"] = "wrapper exit and original testcase evidence recorded independently"
                    row["authoritativeNamedReplay"] = side in {"old", "new"}
                elif row["counts"]["tests"]:
                    row["ciOutcome"] = "passed" if status == 0 else "failed"
                else:
                    row["ciOutcome"] = "no tests executed"
                evidence["sides"][side] = row
                (args.out / "result.json").write_text(json.dumps(evidence, indent=2) + "\n")
                print(json.dumps({"side": side, "exit": status, **row["counts"],
                                  "named": len(row["namedTests"]), "seconds": row["seconds"]}), flush=True)
                if args.smoke:
                    if digest(repository / "junit/junit/4.12/junit-4.12.jar") not in text or status != 0:
                        raise ValueError("Maven or the isolated mirror missed its positive control")
                    return
    if not all(row["mavenStarted"] for row in evidence["sides"].values()):
        raise ValueError("an original Maven invocation did not reach project scanning")


def main():
    if sys.argv[1:2] == ["guest"]:
        return guest(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=CASES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--jdk", type=Path)
    parser.add_argument("--maven", type=Path)
    parser.add_argument("--repository", type=Path, default=CACHE / "maven/repository")
    parser.add_argument("--smoke", action="store_true", help="exercise a cached JAR and Maven startup only")
    parser.add_argument("--stock-compsuite", action="store_true", help="348 original CLI and two independent named replays")
    args = parser.parse_args()
    if args.stock_compsuite and args.example != "348":
        parser.error("--stock-compsuite requires the disclosed i-87 case")
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
