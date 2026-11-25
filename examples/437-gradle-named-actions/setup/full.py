"""Verify archived build inputs, then build and exercise both historical Gradle distributions."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
LOCK = HERE / "archive-inputs.json"
ARCHIVES = json.loads(LOCK.read_text())
JDKS = Path.home()/".sdkman/candidates/java"
JAVA_11 = JDKS/"11.0.33.0+10-tem"
JAVA_17 = JDKS/"17.0.21.0+9-tem"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def artifact_path(coordinate, extension):
    group, module, version = coordinate.split(":")
    return Path(*group.split("."), module, version, f"{module}-{version}.{extension}")


def prepare_inputs(repo, fetch):
    for coordinate, archive in ARCHIVES.items():
        for extension, digest in archive["sha256"].items():
            relative = artifact_path(coordinate, extension)
            dest = repo / relative
            if not dest.is_file():
                if not fetch:
                    raise ValueError(f"{relative} missing; pass --fetch to retrieve the locked artifact")
                dest.parent.mkdir(parents=True, exist_ok=True)
                url = archive["repository"] + "/" + relative.as_posix()
                with tempfile.NamedTemporaryFile(dir=dest.parent) as tmp:
                    with urllib.request.urlopen(url, timeout=40) as response:
                        shutil.copyfileobj(response, tmp)
                    tmp.flush()
                    if sha(Path(tmp.name)) != digest:
                        raise ValueError(f"mirror digest differs for {relative}")
                    try:
                        os.link(tmp.name, dest)
                    except FileExistsError:
                        pass  # A simultaneous build installed it. Verify the winner below.
                time.sleep(1)
            if sha(dest) != digest:
                raise ValueError(f"{relative} differs from the registered bytes")


def verify_policy(work, repo):
    policy = work / "gradle/verification-metadata.xml"
    xml = ET.parse(policy)
    ring = work / "keyring.gpg"
    subprocess.run(["gpg", "--no-options", "--homedir", work, "--batch", "--dearmor", "--output", ring,
                    work / "gradle/verification-keyring.keys"], check=True)
    signers = {}
    for coordinate, archive in ARCHIVES.items():
        group, module, version = coordinate.split(":")
        jar = repo / artifact_path(coordinate, "jar")
        if "signer" not in archive:
            component = f".//{{*}}component[@group='{group}'][@name='{module}'][@version='{version}']"
            expected = xml.find(component + f"/{{*}}artifact[@name='{jar.name}']/{{*}}sha256")
            if expected is None or expected.get("value") != archive["sha256"]["jar"]:
                raise ValueError(f"{coordinate} differs from the upstream checksum policy")
            continue

        signer = archive["signer"]
        rule = f".//{{*}}trusted-key[@id='{signer.lower()}']/{{*}}trusting[@group='{group}'][@name='{module}']"
        if xml.findtext(".//{*}verify-signatures") != "true" or xml.find(rule) is None:
            raise ValueError(f"{coordinate} signer is outside the upstream trust policy")
        for extension in ("jar", "pom"):
            artifact = repo / artifact_path(coordinate, extension)
            result = subprocess.run(["gpgv", "--homedir", work, "--keyring", ring, "--status-fd", "1",
                                     str(artifact) + ".asc", artifact], capture_output=True, text=True, check=True)
            valid = [line.split()[2] for line in result.stdout.splitlines() if line.startswith("[GNUPG:] VALIDSIG ")]
            if valid != [signer]:
                raise ValueError(f"unexpected signing key for {artifact.name}")
        signers[coordinate] = signer
    return signers


def gradle(cache, repo, cwd, home, arguments, *, offline):
    cmd = [cache/"tools/gradle-7.5.1/bin/gradle","--no-daemon","--no-scan","--no-build-cache",
           "--console=plain","--dependency-verification=strict","-Dl15.verified.repository="+str(repo),
           "-Dl15.archive.inputs="+str(LOCK), "-I",HERE/"archive.init.gradle"]
    if offline: cmd.append("--offline")
    env = {**os.environ,"JAVA_HOME":str(JAVA_11),"GRADLE_USER_HOME":str(home)}
    subprocess.run([*cmd,*arguments],env=env,cwd=cwd,check=True)


def preflight(cache, repo, pins):
    checks = {}
    expected = {coordinate: archive["sha256"]["jar"] for coordinate, archive in ARCHIVES.items()}
    for side, pin in pins.items():
        with tempfile.TemporaryDirectory(prefix="gradle-verification-") as temp:
            work = Path(temp)
            (work/"gradle").mkdir()
            src = cache/f"worktrees/L15-gradle-{side}"
            for name in ("verification-metadata.xml","verification-keyring.keys"):
                data = subprocess.check_output(["git","-C",src,"show",f"{pin}:gradle/{name}"])
                (work/"gradle"/name).write_bytes(data)
            signers = verify_policy(work, repo)
            (work/"settings.gradle").write_text("rootProject.name='strict-input-check'\n")
            dependencies = "\n".join(f"    witness('{coordinate}') {{ transitive = false }}" for coordinate in ARCHIVES)
            (work/"build.gradle").write_text(
                "configurations { witness }\ndependencies {\n" + dependencies + "\n}\n"
                "tasks.register('resolvePin') { doLast {\n"
                "    def resolved = configurations.witness.resolvedConfiguration.resolvedArtifacts.collectEntries { a ->\n"
                "        [(a.moduleVersion.id.toString()): java.security.MessageDigest.getInstance('SHA-256')"
                ".digest(a.file.bytes).encodeHex().toString()]\n"
                "    }\n    file('result.json').text = groovy.json.JsonOutput.toJson(resolved)\n} }\n")
            gradle(cache,repo,work,work/"home",["--max-workers=1","-Dorg.gradle.jvmargs=-Xmx192m","resolvePin"],offline=True)
            if json.loads((work / "result.json").read_text()) != expected:
                raise ValueError(f"{pin} resolved different artifacts")
            checks[side] = {"pin": pin, "policySha256": sha(work / "gradle/verification-metadata.xml"),
                            "keyringSha256": sha(work / "gradle/verification-keyring.keys"),
                            "resolvedSha256": expected, "verifiedJarAndPomSigners": signers}
            print(side, pin, "resolved", len(expected), "archives under strict upstream verification", flush=True)
    return {"archiveInputsSha256": sha(LOCK), "gradle": "7.5.1",
            "jdkReleaseSha256": sha(JAVA_11 / "release"), "checks": checks}


def histories(dist, work, side, classes):
    launcher, = (dist/"lib").glob("gradle-launcher-*.jar")
    core, = (p for p in (dist/"lib").glob("gradle-core-*.jar") if p.name[len("gradle-core-"):][0].isdigit())
    with ZipFile(core) as jar:
        class_hash = hashlib.sha256(jar.read("org/gradle/api/internal/AbstractTask.class")).hexdigest()
    questions = json.loads((FOLDER/"comparison.json").read_text())["questions"]
    reference = json.loads((FOLDER/"observations.json").read_text())["deployments"]["pinned-method-on-7.6"]["observations"]
    rows = {}
    for q in questions:
        trial = work/q["args"][0]
        trial.mkdir(parents=True)
        actual = subprocess.check_output([JAVA_17/"bin/java","-Xmx128m","-cp",str(classes)+os.pathsep+str(launcher),
                    "FullHistory",q["args"][0],launcher,class_hash],cwd=trial,text=True,timeout=150).strip()
        baseline = next(r["outcome"]["return"] for r in reference if r["id"] == q["id"] and r["side"] == side)
        rows[q["id"]] = {"return":actual,"agreesWithMethodReplay":actual==baseline}
        print(side, q["id"], actual, flush=True)
    return {"launcherSha256":sha(launcher),"coreSha256":sha(core),"abstractTaskSha256":class_hash,"returns":rows}


def callers(cache, work):
    classes = work/"callers"; classes.mkdir()
    subprocess.run([JAVA_17/"bin/javac","-proc:none","-g","-d",classes,"-cp",
                    cache/"tools/gradle-7.6/lib/gradle-bootstrap-7.6.jar",
                    FOLDER/"caller/PublicCaller.java",HERE/"FullHistory.java"],check=True)
    return classes


def release_histories(cache):
    with tempfile.TemporaryDirectory(prefix="gradle-releases-") as t:
        work = Path(t)
        classes = callers(cache, work)
        return {version:histories(cache/("tools/gradle-"+version),work/side,side,classes)
                for side,version in (("parent","7.5.1"),("fix","7.6"))}


def installed_distribution(cache, repo, tree, work, side, pin):
    target = cache/"tools"/("gradle-full-L15-"+pin)
    marker = "l15-build.json"
    def inventory(dist):
        return {p.relative_to(dist).as_posix():sha(p) for p in sorted(dist.rglob("*"))
                if p.is_file() and p.relative_to(dist).as_posix()!=marker}
    with (target.parent/(target.name+".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if target.exists():
            manifest = json.loads((target/marker).read_text())
            if manifest["pin"]!=pin or manifest["files"]!=inventory(target):
                raise ValueError(f"previous installation no longer matches {pin}")
            return target
        dist = work/("distribution-"+side)
        gradle(cache,repo,tree,cache/"gradle-home-L15",["--max-workers=4","-Dorg.gradle.jvmargs=-Xmx3g -XX:MaxMetaspaceSize=768m",
               "-Porg.gradle.java.installations.auto-download=false",
               "-Porg.gradle.java.installations.paths="+",".join(map(str,(JDKS/"8.0.512.0+9-tem",JAVA_11,JAVA_17))),
               ":distributions-full:install","-Pgradle_installPath="+str(dist)],
               offline=side=="parent")
        if not (dist/"bin/gradle").is_file(): raise ValueError(f"no installed distribution for {pin}")
        (dist/marker).write_text(json.dumps({"pin":pin,"files":inventory(dist)},sort_keys=True)+"\n")
        dist.rename(target)
        return target


def full_build(cache, repo, pins, checks, output):
    record = {"pins": pins, "strictResolution": checks, "distributions": {}}
    output.parent.mkdir(parents=True, exist_ok=True)

    def save(stage, side):
        record["stage"] = stage
        record["side"] = side
        output.write_text(json.dumps(record, indent=2) + "\n")

    save("verified inputs", None)
    (cache/"tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gradle-full-pins-",dir=cache/"tmp") as t:
        work = Path(t)
        classes = callers(cache, work)
        tree = work/"source"
        subprocess.run(["git","clone","--quiet","--shared","--no-checkout",cache/"worktrees/L15-gradle-fix",tree],check=True)
        for side in ("fix","parent"):
            pin = pins[side]
            save("building distribution", side)
            subprocess.run(["git","-C",tree,"checkout","--quiet","--detach",pin],check=True)
            if subprocess.check_output(["git","-C",tree,"rev-parse","HEAD"],text=True).strip()!=pin:
                raise ValueError("upstream checkout differs")
            dist = installed_distribution(cache,repo,tree,work,side,pin)
            save("running public histories", side)
            record["distributions"][side] = histories(dist,work/side,side,classes)
        save("comparing both distributions", None)
        if not all(row["agreesWithMethodReplay"] for d in record["distributions"].values() for row in d["returns"].values()):
            raise ValueError("the full distribution and registered method comparisons disagree; see the recorded histories")
        save("verified both distributions", None)


if __name__ == "__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache",type=Path,default=Path.home()/".cache/in-the-loop/merged-pr-links-l01-l20")
    ap.add_argument("--repository",type=Path)
    ap.add_argument("--fetch",action="store_true",help="retrieve missing public inputs and verify their SHA-256")
    ap.add_argument("--preflight-report",type=Path,help="save both strict resolution checks")
    group=ap.add_mutually_exclusive_group()
    group.add_argument("--releases",type=Path,help="run the same histories on released Gradle 7.5.1 and 7.6")
    group.add_argument("--output",type=Path,help="also build both complete distributions and record the six histories")
    a=ap.parse_args()
    repo=(a.repository or a.cache/"dl/L15-exact-repository").resolve()
    if a.releases:
        a.releases.write_text(json.dumps(release_histories(a.cache),indent=2)+"\n")
    else:
        prepare_inputs(repo, a.fetch)
        pins = json.loads((FOLDER / "comparison.json").read_text())["revisions"]
        checks=preflight(a.cache,repo,pins)
        if a.preflight_report: a.preflight_report.write_text(json.dumps(checks,indent=2)+"\n")
        if a.output: full_build(a.cache,repo,pins,checks,a.output)
