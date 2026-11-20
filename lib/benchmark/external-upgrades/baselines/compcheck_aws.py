"""Run the published CompCheck CLI on one disclosed AWS production call site in two isolated treatments."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time


TOOL_REVISION = "937d1d1495c4ff5449443183b70f465d1fe0b4d0"
TOOL_ARCHIVE = "bf657aa970fbd87ac98f086aea7628492f0d6b84a17c694ef4a5176b4a3871f8"
SUBJECT = "28f5c5f31ae04a20d9256f05bb306ecda5196867"
API = "org.joda.time.format.DateTimeFormatter.parseMillis(Ljava/lang/String;)J"
CID = "c15-2"
CALLER = "com.amazonaws.util.DateUtils.doParseISO8601Date(Ljava/lang/String;)Ljava/util/Date;"
FULL_KNOWLEDGE = "81b2f6d2327df2cbac7c59de66842f682892b74bc0f4f9e7f12e74dc33674240"
INCIDENT = {"k14-1": "DateUtilsTest#testIssue233JodaTimeLimit", "k15-1": "DateUtilsTest#testIssue233Overflows"}
MAVEN_ARCHIVE = "26ad91d751b3a9a53087aefa743f4e16a17741d3915b219cf74112bf87a438c5"
JODA = {"2.8.1": "b4670b95f75957c974284c5f3ada966040be2578f643c5c6083d262162061fa2",
        "2.10.5": "4ee73e7ff8e2df0d4e3408cf1a1527a59f265dd9fb43fb9b2eb818d87f93759e"}
JDK_RELEASE = "b965ee876a40eb8b76e7146403b3efc54e309ebd573064a18c7b87665ce4d89e"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(path, digest):
    if sha(path) != digest:
        raise ValueError(f"input differs from the lock: {path.name}")


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), text=True, capture_output=True, **kwargs)


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def extract_checked(archive, expected, target):
    verify(archive, expected)
    with tarfile.open(archive) as tree:
        tree.extractall(target, filter="data")


def knowledge(path, treatment):
    verify(path, FULL_KNOWLEDGE)
    original = json.loads(path.read_bytes())
    removed = [k for k in original if k["client"] == "aws-sdk-java" and k["lib"] == "joda-time:joda-time"
               and k["versions"] == ["2.8.1"] and k["new_version"] == "2.10.5"
               and INCIDENT.get(k["id"]) == k["test"]]
    if len(original) != 24 or {k["id"] for k in removed} != INCIDENT.keys():
        raise ValueError("unexpected incident membership in the pinned knowledge")
    data = original
    if treatment == "leave-issue-233-out":
        data = [k for k in original if k not in removed]
        path.write_text(json.dumps(data, indent=2) + "\n")
    return {"before": len(original), "after": len(data), "bytes": path.stat().st_size, "sha256": sha(path),
            "applicableApiRecords": sum(k["API"] == API for k in data)}


def one(args, root, maven, treatment):
    started, clock = stamp(), time.monotonic()
    root.mkdir()
    unpack = root / "checkout"
    extract_checked(args.inputs / "compcheck.tar.gz", TOOL_ARCHIVE, unpack)
    tool = unpack / ("CompCheck-" + TOOL_REVISION)
    kp = tool / "knowledge/knowledge.json"
    kb = knowledge(kp, treatment)
    registry = json.loads((tool / "check/callsites.json").read_bytes())
    [site] = [c for c in registry if c["id"] == CID]
    if (site["client"], site["API"], site["caller"], site["line"], site["sha"]) != (
            "aws-sdk-java", API, CALLER, "104", SUBJECT):
        raise ValueError("the stock registry points to a different AWS call site")
    source = tool / "check/_downloads/aws-sdk-java"
    source.parent.mkdir()
    run(["git", "-c", "core.hooksPath=/dev/null", "clone", "-q", "--no-checkout", "--no-local", "--no-tags",
         "--depth=1", args.inputs.joinpath("aws.git").resolve().as_uri(), source], check=True)
    # A source mirror can have another HEAD. Ask for the authored commit explicitly with local transfer only.
    run(["git", "-C", source, "fetch", "-q", "--no-tags", "--depth=1", "origin", SUBJECT], check=True)
    run(["git", "-C", source, "-c", "core.hooksPath=/dev/null", "checkout", "-q", "--detach", SUBJECT], check=True)
    sha_source = run(["git", "-C", source, "rev-parse", "HEAD^{tree}"], check=True).stdout.strip()
    mapped = run(["git", "-C", source, "show", "HEAD:aws-java-sdk-core/src/main/java/com/amazonaws/util/DateUtils.java"], check=True).stdout.splitlines()[103].strip()
    if "iso8601DateFormat.parseMillis(temp)" not in mapped:
        raise ValueError("line 104 does not call the registered dependency API")
    scratch, m2 = root / "tmp", root / "m2"
    scratch.mkdir()
    m2.mkdir()
    (m2 / "settings.xml").write_text("<settings><offline>true</offline></settings>\n")
    for version, digest in JODA.items():
        name = f"joda-time-{version}.jar"
        jar = args.inputs / name
        verify(jar, digest)
        dest = m2 / "repository/joda-time/joda-time" / version / name
        dest.parent.mkdir(parents=True)
        shutil.copyfile(jar, dest)
    private_home = str(Path.home())
    command = ["bwrap", "--unshare-net", "--die-with-parent", "--ro-bind", "/usr", "/usr",
               "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
               "--ro-bind", "/etc", "/etc", "--proc", "/proc", "--dev", "/dev", "--bind", str(tool), "/case",
               "--ro-bind", str(args.jdk), "/jdk", "--ro-bind", str(maven), "/maven",
               "--bind", str(m2), private_home + "/.m2", "--bind", str(scratch), "/tmp",
               "--chdir", "/case/compcheck", "--", "/usr/bin/python3", "main.py", "--check", "--id", CID]
    env = {"PATH": "/jdk/bin:/maven/bin:/usr/bin:/bin", "JAVA_HOME": "/jdk", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "TZ": "UTC", "TMPDIR": "/tmp", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "PYTHONWARNINGS": "ignore::SyntaxWarning", "MAVEN_OPTS": "-Xmx768m"}
    at, start = stamp(), time.monotonic()
    process = run(command, env=env, timeout=360)
    observed = process.stdout + process.stderr
    ctx = tool / "check/context" / CID / "context.json"
    matched = tool / "check/matching/relax_prim_poly-0.7.json"
    testlogs = tool / "check/_test_logs" / CID
    build = scratch / (CID + ".build")
    # Only this named call site's stage markers and selected diagnostics leave the isolated tree.
    stages = [m for m in ("Extracting Call Site Context", "Call site found", "Call site not found",
                           "Processing CFG file", "API CALL SITE MATCH!", "API CALL SITE NOT MATCH",
                           "Running incompatibility revealing", "Running test generation") if m in observed]
    if not build.is_file():
        raise RuntimeError("the original CLI failed before its Maven invocation: " + observed[:240])
    build_text = build.read_text(errors="replace")
    retained = [line.strip()[:550] for line in build_text.splitlines() if (
        "Non-resolvable parent POM" in line or "Unresolveable build extension" in line
        or "Error resolving version for plugin" in line or "Cannot access central" in line
        or "PluginResolutionException" in line or "Plugin " in line and "could not be resolved" in line
    )][:4]
    failed = "BUILD FAILURE" in build_text or any(line.startswith("[ERROR]") for line in build_text.splitlines())
    match = json.loads(matched.read_bytes()).get(CID) if matched.is_file() else None
    report = {"startedUtc": started, "elapsedSecondsIncludingSetup": round(time.monotonic() - clock, 3),
              "toolStartedUtc": at, "toolSeconds": round(time.monotonic() - start, 3), "exit": process.returncode,
              "treatment": treatment, "knowledge": kb, "site": site, "clientTree": sha_source, "sourceLine": mapped,
              "argv": ["python3", "main.py", "--check", "--id", CID], "stages": stages,
              "mavenBuildFailed": failed, "mavenDiagnostics": retained, "mavenLogSha256": sha(build),
              "staticContextGenerated": ctx.is_file(), "match": match, "generatedJUnitLogFiles": (
                  sum(p.is_file() for p in testlogs.rglob("*")) if testlogs.exists() else 0),
              "toolStdoutSha256": hashlib.sha256(process.stdout.encode()).hexdigest(),
              "toolStderrSha256": hashlib.sha256(process.stderr.encode()).hexdigest()}
    if ctx.is_file():
        report["contextSha256"] = sha(ctx)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, help="directory containing the pinned tool and Maven archives, aws.git, and the two Joda JARs")
    parser.add_argument("--jdk", type=Path, default=Path.home() / ".sdkman/candidates/java/8.0.512.0+9-tem")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.inputs is None:
        root = Path.home() / ".cache/in-the-loop/agent-tmp"
        candidates = [p / "compcheck-aws-inputs-v1" for p in root.iterdir() if (p / "compcheck-aws-inputs-v1").is_dir()]
        if len(candidates) != 1:
            parser.error("provide --inputs DIR with the locked calibration inputs")
        args.inputs = candidates[0]
    args.inputs = args.inputs.resolve()
    args.jdk = args.jdk.resolve()
    verify(args.jdk / "release", JDK_RELEASE)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    temp_root = args.inputs.parent if not os.environ.get("TMPDIR") else Path(os.environ["TMPDIR"])
    if str(temp_root).startswith("/tmp"):
        temp_root = args.inputs.parent
    with tempfile.TemporaryDirectory(prefix="compcheck-aws-run-", dir=temp_root) as d:
        work = Path(d)
        extract_checked(args.inputs / "apache-maven-3.6.3-bin.tar.gz", MAVEN_ARCHIVE, work)
        mvn = work / "apache-maven-3.6.3"
        result = {"case": "open-aws-issue-233", "toolRevision": TOOL_REVISION, "sourceArchiveSha256": TOOL_ARCHIVE,
                  "subjectRevision": SUBJECT, "subjectJdkReleaseSha256": JDK_RELEASE,
                  "mavenVersion": "3.6.3", "searchBudgetSeconds": 60, "strategy": "relax_prim_poly", "threshold": 0.7,
                  "clientInputs": "Stock registry c15-2; cached upstream AWS Git source, original unmodified published analyzer and per-treatment cold Maven repository with both real Joda-Time JARs. Maven works offline. All user files except named run inputs are outside the sandbox.",
                  "treatments": []}
        for treatment in ("normal", "leave-issue-233-out"):
            row = one(args, work / treatment, mvn, treatment)
            result["treatments"].append(row)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            print(treatment, "CLI exit", row["exit"], "context", row["staticContextGenerated"],
                  "match", row["match"], "test logs", row["generatedJUnitLogFiles"], flush=True)


if __name__ == "__main__":
    main()
