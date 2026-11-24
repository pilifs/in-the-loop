"""Evaluate the pre-registered Petclinic migration from the original classes and runtime POMs."""
import argparse
from html.parser import HTMLParser
import http.client
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.parse import urlencode, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_evidence, change_inventory, upgrade_replay

JDK = Path.home() / ".sdkman/candidates/java/17.0.21.0+9-tem"
MAIN = "org.springframework.samples.petclinic.PetClinicApplication"


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.fields, self.links, self.words = set(), [], []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input" and values.get("name"):
            self.fields.add(values["name"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])

    def handle_data(self, text):
        self.words.extend(text.split())


def http(port, path, form=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        data = urlencode(form) if form else None
        conn.request("POST" if form else "GET", path, data,
                     {"Content-Type": "application/x-www-form-urlencoded", "Accept-Language": "en"})
        response = conn.getresponse()
        return response.status, urlsplit(response.getheader("Location", "")).path, Page(response.read().decode("utf-8"))
    finally:
        conn.close()


def owner_list(port):
    queue, seen, names = ["/owners?lastName="], set(), []
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        if len(seen) >= 20:
            raise ValueError("owner listing exceeded the declared small database")
        seen.add(path)
        status, _, page = http(port, path)
        if status != 200:
            raise ValueError(f"owner listing returned HTTP {status}")
        names.extend(page.words)
        for link in page.links:
            if re.fullmatch(r"/owners\?[^#]*\bpage=\d+[^#]*", link) and link not in seen:
                queue.append(link)
    return names


def workflows(port, registration):
    status, _, page = http(port, "/owners/new")
    result = {"startup": {"status": status, "form": {"firstName", "telephone"} <= page.fields}}
    invalid, valid = (registration["independentExamples"][k] for k in ("invalid", "valid"))
    before = owner_list(port)
    status, _, page = http(port, "/owners/new", invalid)
    after = owner_list(port)
    result["reject-owner"] = {"status": status, "redisplayed": {"lastName", "telephone"} <= page.fields,
                              "errorsShown": any(w in " ".join(page.words).lower() for w in ("empty", "blank", "digits", "numeric", "match")),
                              "unchangedListing": before == after and invalid["firstName"] not in after}
    status, location, _ = http(port, "/owners/new", valid)
    saved = bool(re.fullmatch(r"/owners/\d+", location))
    result["create-and-read-owner"] = {"redirect": status in (302, 303) and saved, "details": False, "search": False}
    if saved:
        detail, _, page = http(port, location)
        result["create-and-read-owner"]["details"] = detail == 200 and all(valid[k] in page.words for k in ("firstName", "lastName", "telephone"))
        status, found, _ = http(port, "/owners?" + urlencode({"lastName": valid["lastName"]}))
        result["create-and-read-owner"]["search"] = status in (302, 303) and found == location
    return result


def application(classes, jars, registration, work, env):
    started = time.monotonic()
    cp = os.pathsep.join(map(str, [classes, *jars]))
    with (work / "server.log").open("w") as log:
        process = subprocess.Popen([JDK / "bin/java", "-Xmx512m", "-XX:ActiveProcessorCount=2", "-Duser.timezone=UTC",
            "-Duser.language=en", "-Duser.country=US", "-Dspring.devtools.restart.enabled=false",
            "-cp", cp, MAIN, "--server.address=127.0.0.1", "--server.port=0"], cwd=work, env=env, stdout=log, stderr=log)
        try:
            while process.poll() is None and time.monotonic() - started < registration["budget"]["secondsPerStartup"]:
                text = (work / "server.log").read_text(errors="replace")
                port = re.search(r"Tomcat started on port\(s\): (\d+)", text)
                if port and "Started PetClinicApplication" in text:
                    return {"launch": "started", "startupSeconds": round(time.monotonic()-started, 3),
                            "observations": workflows(int(port[1]), registration)}
                time.sleep(0.1)
            lines = (work / "server.log").read_text(errors="replace").splitlines()
            causes = [s.strip() for s in lines if s.lstrip().startswith("Caused by:")]
            return {"launch": "failed" if process.poll() is not None else "timeout", "observations": {},
                    "reason": causes[-1] if causes else "application did not reach its ready event within the budget",
                    "logSha256": upgrade_replay.sha(work / "server.log")}
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def build_subject(mirror, side, registration, work, maven, env):
    source = work / side
    source.mkdir()
    rev = registration[side]
    archive = work / (side + ".tar")
    subprocess.run(["git", "--git-dir", mirror, "archive", "-o", archive, rev, "pom.xml", "src/main"], check=True)
    with tarfile.open(archive) as contents:
        contents.extractall(source, filter="data")
    classpath = source / "runtime.cp"
    argv = ["mvn", "-B", "-ntp", "-s", str(work / "settings.xml"), "-Dmaven.repo.local=" + str(maven),
            "-DincludeScope=runtime", "-Dmdep.outputFile=" + str(classpath),
            "org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath"]
    clock = time.monotonic()
    log = work / (side + "-resolve.log")
    with log.open("w") as out:
        proc = subprocess.run(argv, cwd=source, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=720)
    if proc.returncode or not classpath.is_file():
        errors = [s for s in log.read_text(errors="replace").splitlines() if s.startswith("[ERROR]")]
        raise ValueError("Maven could not resolve the original runtime: " + next(iter(errors), str(proc.returncode))[:500])
    deps = [Path(p) for p in classpath.read_text().strip().split(os.pathsep)]
    classes, build = compile_source(source, deps, source / "classes", env)
    if classes is None:
        raise ValueError("building the intended application: " + str(build))
    return source, classes, deps, {"commit": rev, "pom": upgrade_replay.sha(source / "pom.xml"),
                                   "classes": change_inventory.file_digest(classes), "runtime": [
                                       {"name": j.name, "sha256": upgrade_replay.sha(j)} for j in deps],
                                   "compile": build, "seconds": round(time.monotonic() - clock, 4)}


def compile_source(source, deps, dest, env):
    dest.mkdir()
    files = sorted((source / "src/main/java").rglob("*.java"))
    result = subprocess.run([JDK / "bin/javac", "--release", "17", "-proc:none", "-parameters", "-g", "-encoding", "UTF-8",
                             "-cp", os.pathsep.join(map(str, deps)), "-d", dest, *files], env=env,
                            text=True, capture_output=True, timeout=90)
    if result.returncode:
        return None, {"status": "failed", "diagnoses": list(dict.fromkeys(
            s.split("error: ",1)[1] for s in result.stderr.splitlines() if "error: " in s))[:12]}
    shutil.copytree(source / "src/main/resources", dest, dirs_exist_ok=True)
    return dest, {"status": "compiled", "sources": len(files), "classFiles": len(list(dest.rglob("*.class")))}


def check_deployment(name, classes, deps, registration, work, env):
    started = time.monotonic()
    prior = resource.getrusage(resource.RUSAGE_CHILDREN)
    trials = []
    for repetition in range(2):
        directory = work / (name + str(repetition))
        directory.mkdir()
        trials.append(application(classes, deps, registration, directory, env))
    observed = trials[0]["observations"]
    consistent = (trials[0]["launch"], observed, trials[0].get("reason")) == (
        trials[1]["launch"], trials[1]["observations"], trials[1].get("reason"))
    expected = {"startup": {"status": 200, "form": True}, "reject-owner": {"status": 200, "redisplayed": True,
                "errorsShown": True, "unchangedListing": True}, "create-and-read-owner": {"redirect": True, "details": True, "search": True}}
    claims = {}
    for identifier, target in expected.items():
        claims[identifier] = ("established" if observed[identifier] == target else "refuted") if consistent and identifier in observed else "open"
    if consistent and trials[0]["launch"] == "failed" and trials[0]["reason"].startswith("Caused by:"):
        claims["startup"] = "refuted"
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"trials": trials, "consistent": consistent, "claims": claims, "cost": {
        "wallSeconds": round(time.monotonic() - started, 4),
        "cpuSeconds": round(usage.ru_utime + usage.ru_stime - prior.ru_utime - prior.ru_stime, 4),
        "childRssHighWaterKiB": usage.ru_maxrss}}


def run(args, work):
    registration = json.loads((HERE / "petclinic.json").read_text())
    env = {**os.environ, "JAVA_HOME": str(JDK), "PATH": str(JDK / "bin") + ":" + os.environ["PATH"],
           "TZ": "UTC", "LC_ALL": "C.UTF-8"}
    (work / "settings.xml").write_text('<settings><mirrors><mirror><id>central</id><mirrorOf>*</mirrorOf>'
                                      '<url>https://repo.maven.apache.org/maven2</url></mirror></mirrors></settings>')
    mirror = args.mirror
    if not mirror:
        mirror = work / "petclinic.git"
        subprocess.run(["git", "clone", "--quiet", "--bare", registration["repository"], mirror], check=True, timeout=90)
    maven = args.maven_cache or work / "m2"
    report = {"schema": "held-back-change-result/v1", "registrationSha256": upgrade_replay.sha(HERE / "petclinic.json"),
              "jdk": change_inventory.jdk_binding(JDK), "builds": {}, "deployments": {}}
    subjects = {}
    for side in ("before", "after"):
        try:
            source, classes, deps, report["builds"][side] = build_subject(mirror, side, registration, work, maven, env)
            subjects[side] = source, classes, deps
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            report["builds"][side] = {"status": "open", "reason": str(error)}
    if len(subjects) != 2:
        return report
    old, before, old_deps = subjects["before"]
    _, after, new_deps = subjects["after"]
    _, report["unchangedSourceBuild"] = compile_source(old, new_deps, work / "unchanged-classes", env)
    for name, classes, deps in (("old", before, old_deps), ("oldBinaryNewRuntime", before, new_deps), ("adapted", after, new_deps)):
        def binding():
            return change_inventory.digest({"registration": report["registrationSha256"], "jdk": report["jdk"],
                "runner": upgrade_replay.sha(Path(__file__)), "classes": change_inventory.file_digest(classes),
                "runtime": [upgrade_replay.sha(file) for file in deps], "launch": name})
        key = binding()
        first = check_deployment(name, classes, deps, registration, work, env)
        eligible = all(v == "established" for v in first["claims"].values())
        cache = work / "accepted" / (key + ".json")
        if eligible:
            change_evidence.write_json(cache, {"key": key, "sha256": change_inventory.digest(first), "result": first})
        clock = time.monotonic()
        rebound = binding()
        stored = json.loads(cache.read_text()) if cache.exists() and rebound == key else None
        reused = bool(stored and stored["key"] == rebound and change_inventory.digest(stored["result"]) == stored["sha256"])
        resumed = stored["result"] if reused else check_deployment(name + "-retry", classes, deps, registration, work, env)
        warm = time.monotonic() - clock
        clean = check_deployment(name + "-clean", classes, deps, registration, work, env)
        same = (resumed["claims"] == clean["claims"] and resumed["consistent"] and clean["consistent"]
                and resumed["trials"][0]["observations"] == clean["trials"][0]["observations"])
        report["deployments"][name] = {**first, "executionKey": key, "reuse": reused, "warmWallSeconds": round(warm, 4),
                                      "cleanCost": clean["cost"], "cleanEquivalent": same,
                                      "questions": [w["id"] for w in registration["productionWorkflows"]]}
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--mirror", type=Path, help="optional local bare clone containing the registered commits")
    ap.add_argument("--maven-cache", type=Path, help="writable cache for the original runtime dependency graphs")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="held-back-petclinic-") as temp:
        result = run(args, Path(temp).resolve())
    change_evidence.write_json(args.output, result)
    if not result["deployments"]:
        sys.exit("held-back preparation open: see the build diagnoses")
    if not all(d["cleanEquivalent"] for d in result["deployments"].values()):
        sys.exit("held-back incremental results differ from clean recomputation")
    print(json.dumps({k: v["claims"] for k, v in result["deployments"].items()}))
