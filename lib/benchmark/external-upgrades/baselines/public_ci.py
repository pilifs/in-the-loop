"""Run the disclosed upstream Linux CI lifecycle with original sources and a serial Maven Central mirror."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
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
    settings.write_text(f"<settings><mirrors><mirror><id>isolated-central</id><mirrorOf>*</mirrorOf>"
                        f"<url>http://127.0.0.1:{port}/</url></mirror></mirrors></settings>\n")
    if arguments == ["--smoke"]:
        from urllib.request import urlopen
        path = "junit/junit/4.12/junit-4.12.jar"
        with urlopen(f"http://127.0.0.1:{port}/{path}", timeout=10) as body:
            print(hashlib.sha256(body.read()).hexdigest(), flush=True)
        return subprocess.call(["mvn", "--version"])
    return subprocess.call(["mvn", "--settings", str(settings), "-T", "1", "-Dmaven.repo.local=/work/repository",
                            "-Dmaven.artifact.threads=1", "-Daether.connector.basic.threads=1",
                            "-Daether.metadataResolver.threads=1", *arguments])


def namespace(project, work, scratch, socket_dir, maven, jdk):
    cmd = ["bwrap", "--unshare-all", "--unshare-user", "--disable-userns", "--die-with-parent", "--new-session",
           "--cap-drop", "ALL", "--clearenv", "--ro-bind", "/usr", "/usr"]
    for name in ("bin", "sbin", "lib", "lib64"):
        path = Path("/") / name
        if path.is_symlink():
            cmd += ["--symlink", os.readlink(path), str(path)]
        elif path.exists():
            cmd += ["--ro-bind", str(path), str(path)]
    cmd += ["--ro-bind", str(maven), "/opt/maven", "--ro-bind", str(jdk), "/opt/jdk"]
    for file in ("public_ci.py", "maven_mirror.py"):
        cmd += ["--ro-bind", str(HERE / file), "/control/" + file]
    cmd += ["--bind", str(work), "/work", "--bind", str(project), "/project",
            "--bind", str(scratch), "/scratch", "--symlink", "/scratch", "/tmp",
            "--ro-bind", str(socket_dir), "/mirror", "--proc", "/proc", "--dev", "/dev"]
    env = {"HOME": "/work/home", "PATH": "/opt/jdk/bin:/opt/maven/bin:/usr/bin", "JAVA_HOME": "/opt/jdk",
           "MAVEN_OPTS": "-Duser.home=/work/home", "JAVA_TOOL_OPTIONS": "-Djava.io.tmpdir=/scratch/jvm",
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
    maven = args.maven.resolve(strict=True)
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
            for side in (("new",) if args.smoke else ("old", "new")):
                baseline = dict(counters)
                side_dir = area / side
                side_dir.mkdir()
                project, work, scratch = (side_dir / name for name in ("project", "work", "scratch"))
                (work / "home").mkdir(parents=True)
                (scratch / "jvm").mkdir(parents=True)
                subprocess.run(["git", "clone", "--quiet", "--no-checkout", "--no-hardlinks", str(repo), project], check=True)
                revision = case[side]
                subprocess.run(["git", "-C", project, "checkout", "--quiet", "--detach", revision], check=True)
                out = args.out / side
                out.mkdir()
                log = side_dir / "maven.log"
                clock = time.monotonic()
                with log.open("wb") as stream:
                    command = namespace(project, work, scratch, sockets, maven, jdk)
                    try:
                        status = subprocess.run([*command, *(["--smoke"] if args.smoke else case["argv"])],
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
    parser.add_argument("--maven", type=Path, default=Path.home() / ".sdkman/candidates/maven/3.10.0")
    parser.add_argument("--repository", type=Path, default=CACHE / "maven/repository")
    parser.add_argument("--smoke", action="store_true", help="exercise a cached JAR and Maven startup only")
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    sys.exit(main())
