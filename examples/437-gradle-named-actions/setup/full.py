"""Resolve the historical dependency strictly, then build and exercise both full Gradle distributions."""
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
COORD = Path("org/ysb33r/gradle/grolifant/0.16.1")
MIRROR = "https://maven.aliyun.com/repository/jcenter/" + COORD.as_posix() + "/"
JAR_HASH = "362c450c9738834181fdfac1147fa11cf21cefd59d7a5368756e174f93567a43"
POM_HASH = "32671ca0c5a852c4432373c92fb8e8e767496a735cdd21a7194b0bfcea5e6cb5"
JDKS = Path.home()/".sdkman/candidates/java"
JAVA_11 = JDKS/"11.0.33.0+10-tem"
JAVA_17 = JDKS/"17.0.21.0+9-tem"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inputs(cache, repo, fetch):
    for ext, digest in (("jar", JAR_HASH), ("pom", POM_HASH)):
        name = "grolifant-0.16.1." + ext
        dest = repo/COORD/name
        if not dest.exists():
            if not fetch: raise ValueError(f"{name} missing; pass --fetch to retrieve the locked artifact")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=dest.parent) as tmp:
                with urllib.request.urlopen(MIRROR + name, timeout=40) as response:
                    shutil.copyfileobj(response, tmp)
                tmp.flush()
                if sha(Path(tmp.name)) != digest: raise ValueError(f"mirror digest differs for {name}")
                try: os.link(tmp.name, dest)
                except FileExistsError: pass
            time.sleep(1)
        if sha(dest) != digest: raise ValueError(f"{dest.name} differs from the registered bytes")
    pins = json.loads((FOLDER/"comparison.json").read_text())["revisions"]
    for side, pin in pins.items():
        checkout = cache/f"worktrees/L15-gradle-{side}"
        data = subprocess.check_output(["git","-C",checkout,"show",pin+":gradle/verification-metadata.xml"])
        xml = ET.fromstring(data)
        component = next(c for c in xml.findall(".//{*}component")
                         if (c.get("group"),c.get("name"),c.get("version")) == ("org.ysb33r.gradle","grolifant","0.16.1"))
        expected = component.find("{*}artifact[@name='grolifant-0.16.1.jar']/{*}sha256")
        if expected is None or expected.get("value") != JAR_HASH:
            raise ValueError(f"{pin} has a different upstream verification policy")
    return pins


def gradle(cache, repo, cwd, home, arguments, *, offline):
    cmd = [cache/"tools/gradle-7.5.1/bin/gradle","--no-daemon","--no-scan","--no-build-cache",
           "--console=plain","--dependency-verification=strict","-Dl15.verified.repository="+str(repo),
           "-I",HERE/"grolifant.init.gradle"]
    if offline: cmd.append("--offline")
    env = {**os.environ,"JAVA_HOME":str(JAVA_11),"GRADLE_USER_HOME":str(home)}
    subprocess.run([*cmd,*arguments],env=env,cwd=cwd,check=True)


def preflight(cache, repo, pins):
    # Resolve through Gradle itself, using each pin's verification policy and an empty fixture cache.
    checks = {}
    for side, pin in pins.items():
        with tempfile.TemporaryDirectory(prefix="gradle-verification-") as temp:
            work = Path(temp)
            (work/"gradle").mkdir()
            src = cache/f"worktrees/L15-gradle-{side}"
            for name in ("verification-metadata.xml","verification-keyring.keys"):
                data = subprocess.check_output(["git","-C",src,"show",f"{pin}:gradle/{name}"])
                (work/"gradle"/name).write_bytes(data)
            (work/"settings.gradle").write_text("rootProject.name='strict-input-check'\n")
            (work/"build.gradle").write_text(
                "configurations { witness }\n"
                "dependencies { witness('org.ysb33r.gradle:grolifant:0.16.1') { transitive = false } }\n"
                "tasks.register('resolvePin') { doLast { def f=configurations.witness.singleFile; "
                "file('result').text=java.security.MessageDigest.getInstance('SHA-256').digest(f.bytes).encodeHex() } }\n")
            gradle(cache,repo,work,work/"home",["--max-workers=1","-Dorg.gradle.jvmargs=-Xmx192m","resolvePin"],offline=True)
            if (work/"result").read_text() != JAR_HASH: raise ValueError("Gradle resolved different bytes")
            checks[side] = {"pin":pin,"policySha256":sha(work/"gradle/verification-metadata.xml"),"resolvedSha256":JAR_HASH}
            print(side, pin, "resolved under strict upstream verification", flush=True)
    return {"source":MIRROR,"pomSha256":POM_HASH,"gradle":"7.5.1","jdkReleaseSha256":sha(JAVA_11/"release"),"checks":checks}


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
               "-I",cache/"scripts/gradle-L15-openmbee-substitute.init.gradle","install","-Pgradle_installPath="+str(dist)],
               offline=side=="parent")
        if not (dist/"bin/gradle").is_file(): raise ValueError(f"no installed distribution for {pin}")
        (dist/marker).write_text(json.dumps({"pin":pin,"files":inventory(dist)},sort_keys=True)+"\n")
        dist.rename(target)
        return target


def full_build(cache, repo, pins, output):
    (cache/"tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gradle-full-pins-",dir=cache/"tmp") as t:
        work = Path(t)
        classes = callers(cache, work)
        tree = work/"source"
        subprocess.run(["git","clone","--quiet","--shared","--no-checkout",cache/"worktrees/L15-gradle-fix",tree],check=True)
        record = {"pins":pins,"grolifantSha256":JAR_HASH,"pomSha256":POM_HASH,"distributions":{}}
        for side in ("fix","parent"):
            pin = pins[side]
            subprocess.run(["git","-C",tree,"checkout","--quiet","--detach",pin],check=True)
            if subprocess.check_output(["git","-C",tree,"rev-parse","HEAD"],text=True).strip()!=pin:
                raise ValueError("upstream checkout differs")
            dist = installed_distribution(cache,repo,tree,work,side,pin)
            record["distributions"][side] = histories(dist,work/side,side,classes)
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(record,indent=2)+"\n")
        if not all(row["agreesWithMethodReplay"] for d in record["distributions"].values() for row in d["returns"].values()):
            raise ValueError("the full distribution and registered method comparisons disagree; see the recorded histories")


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
    pins=inputs(a.cache,repo,a.fetch)
    if a.releases:
        a.releases.write_text(json.dumps(release_histories(a.cache),indent=2)+"\n")
    else:
        checks=preflight(a.cache,repo,pins)
        if a.preflight_report: a.preflight_report.write_text(json.dumps(checks,indent=2)+"\n")
        if a.output: full_build(a.cache,repo,pins,a.output)
