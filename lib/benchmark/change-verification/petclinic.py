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
from xml.etree import ElementTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_evidence, change_inventory, runtime, upgrade_replay

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


def request(port, path, form=None):
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
        status, _, page = request(port, path)
        if status != 200:
            raise ValueError(f"owner listing returned HTTP {status}")
        names.extend(page.words)
        for link in page.links:
            if re.fullmatch(r"/owners\?[^#]*\bpage=\d+[^#]*", link) and link not in seen:
                queue.append(link)
    return names


def workflows(port, registration):
    status, _, page = request(port, "/owners/new")
    result = {"startup": {"status": status, "form": {"firstName", "telephone"} <= page.fields}}
    invalid, valid = (registration["independentExamples"][k] for k in ("invalid", "valid"))
    before = owner_list(port)
    status, _, page = request(port, "/owners/new", invalid)
    after = owner_list(port)
    result["reject-owner"] = {"status": status, "redisplayed": {"lastName", "telephone"} <= page.fields,
                              "errorsShown": any(w in " ".join(page.words).lower() for w in ("empty", "blank", "digits", "numeric", "match")),
                              "unchangedListing": before == after and invalid["firstName"] not in after}
    status, location, _ = request(port, "/owners/new", valid)
    saved = bool(re.fullmatch(r"/owners/\d+", location))
    result["create-and-read-owner"] = {"redirect": status in (302, 303) and saved, "details": False, "search": False}
    if saved:
        detail, _, page = request(port, location)
        result["create-and-read-owner"]["details"] = detail == 200 and all(valid[k] in page.words for k in ("firstName", "lastName", "telephone"))
        status, found, _ = request(port, "/owners?" + urlencode({"lastName": valid["lastName"]}))
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


def target_release(source):
    version = ElementTree.parse(source / "pom.xml").findtext("{*}properties/{*}java.version")
    return int(version.removeprefix("1."))


def build_subject(mirror, side, registration, work, maven, env, historical=False):
    source = work / side
    source.mkdir()
    rev = registration[side]
    archive = work / (side + ".tar")
    subprocess.run(["git", "--git-dir", mirror, "archive", "-o", archive, rev, "pom.xml", "src/main"], check=True)
    with tarfile.open(archive) as contents:
        contents.extractall(source, filter="data")
    classpath = source / "runtime.cp"
    argv = ["mvn", "-B", "-ntp", "-s", str(work / "settings.xml"), "-Dmaven.repo.local=" + str(maven),
            "-Dmaven.artifact.threads=1",
            "-DincludeScope=runtime", "-Dmdep.outputFile=" + str(classpath),
            "org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath"]
    if not historical:
        argv += ["resources:resources", "compiler:compile"]
    clock = time.monotonic()
    log = work / (side + "-resolve.log")
    with log.open("w") as out:
        proc = subprocess.run(argv, cwd=source, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=720)
    if proc.returncode or not classpath.is_file():
        errors = [s for s in log.read_text(errors="replace").splitlines() if s.startswith("[ERROR]")]
        raise ValueError("Maven could not resolve the original runtime: " + next(iter(errors), str(proc.returncode))[:500])
    deps = [Path(p) for p in classpath.read_text().strip().split(os.pathsep)]
    if historical:
        classes, build = compile_source(source, deps, source / "classes", env, release=17)
        if classes is None:
            raise ValueError("building the intended application: " + str(build))
    else:
        classes = source / "target/classes"
        classfiles = list(classes.rglob("*.class"))
        majors = {int.from_bytes(f.read_bytes()[6:8], "big") for f in classfiles}
        release = target_release(source)
        if not (classes / (MAIN.replace(".", "/") + ".class")).is_file() or majors != {release + 44}:
            raise ValueError(f"{side}: Maven emitted class versions {majors} for target {release}")
        build = {"status": "compiled", "goals": ["resources:resources", "compiler:compile"],
                 "targetRelease": release, "classMajor": majors.pop(), "classFiles": len(classfiles)}
    return source, classes, deps, {"commit": rev, "pom": upgrade_replay.sha(source / "pom.xml"),
                                   "classes": change_inventory.file_digest(classes), "runtime": [
                                       {"name": j.name, "sha256": upgrade_replay.sha(j)} for j in deps],
                                   "compile": build, "seconds": round(time.monotonic() - clock, 4)}


def compile_source(source, deps, dest, env, *, release):
    dest.mkdir()
    files = sorted((source / "src/main/java").rglob("*.java"))
    result = subprocess.run([JDK / "bin/javac", "--release", str(release), "-proc:none", "-parameters", "-g", "-encoding", "UTF-8",
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


def positive_receipt(cache, key):
    if cache and cache.is_file():
        try:
            stored = json.loads(cache.read_bytes())
            evidence = stored["result"]
            if (stored["key"] == key and stored["sha256"] == change_inventory.digest(evidence)
                    and evidence["consistent"] and len(evidence["trials"]) == 2
                    and evidence["trials"][0]["observations"] == evidence["trials"][1]["observations"]
                    and set(evidence["claims"]) == {"startup", "reject-owner", "create-and-read-owner"}
                    and all(v == "established" for v in evidence["claims"].values())):
                return evidence
        except (ValueError, KeyError, TypeError):
            pass
    return None


def framework_plan(checker, subjects, measured, registration):
    paths = {"old": [subjects["before"][1], *subjects["before"][2]],
             "new": [subjects["after"][1], *subjects["after"][2]]}
    inventory = change_inventory.framework_inventory(checker, paths, {"old": JDK, "new": JDK})
    required = {"startup": ["GET /owners/new"], "reject-owner": ["POST /owners/new", "GET /owners"],
                "create-and-read-owner": ["POST /owners/new", "GET /owners/{ownerId}", "GET /owners"]}
    declared = {r["id"]: r for r in registration["productionWorkflows"]}
    if required.keys() != declared.keys():
        raise ValueError("registered Petclinic workflow denominator changed")
    entries = {}
    for side in ("old", "new"):
        entries[side] = {entry["id"]: entry["handler"] for entry in inventory[side]}
    claims = []
    for name, deployment in measured["deployments"].items():
        for workflow, spec in declared.items():
            status = deployment["claims"][workflow]
            claims.append({"id": f"{name}/{workflow}", "claimKey": change_inventory.digest([spec, registration["independentExamples"]]),
                           "executionKey": deployment["executionKey"], "scope": spec, "status": status,
                           "source": "two original HTTP trials, compared against separate clean launches",
                           "firstOpenDependency": f"{name}/startup" if status == "open" and workflow != "startup" else None,
                           "dependsOn": [] if workflow == "startup" else [{"id": f"{name}/startup",
                                           "reason": "requires a live container and the actual owner repository",
                                           "rule": "startup enables the observation; its HTTP and database effects require their own trials"}]})
    by_entry = {entry: [w for w, routes in required.items() if entry in routes]
                for entry in entries["old"].keys() | entries["new"].keys()}
    return {"schema": "java-change-plan/v1", "change": "Spring Petclinic on Spring Boot 2.7.3 and 3.0.0",
            "claims": claims, "comparatorSha256": upgrade_replay.sha(checker),
            "entryInventory": [{"id": entry, "old": entries["old"].get(entry), "new": entries["new"].get(entry),
                                "workflows": by_entry[entry], "disposition": "in registered workflows" if by_entry[entry]
                                else "open: outside the frozen acceptance examples"} for entry in sorted(by_entry)],
            "discoveryMisses": {s: sorted({r for routes in required.values() for r in routes} - e.keys()) for s, e in entries.items()},
            "obligations": inventory["obligations"]}


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
    measured = json.loads(args.rebind.read_bytes()) if args.rebind else None
    if measured and "measurement" in measured:
        measured = measured["measurement"]
    historical = measured is not None and "targetRelease" not in measured["builds"]["before"]["compile"]
    for side in ("before", "after"):
        try:
            source, classes, deps, report["builds"][side] = build_subject(mirror, side, registration, work, maven, env, historical)
            subjects[side] = source, classes, deps
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            report["builds"][side] = {"status": "open", "reason": str(error)}
    if len(subjects) != 2:
        return report
    if args.rebind:
        if measured["registrationSha256"] != report["registrationSha256"] or measured["jdk"] != report["jdk"]:
            raise ValueError("the held-back registration or runtime image changed")
        for side, rebuilt in report["builds"].items():
            if any(rebuilt[k] != measured["builds"][side][k] for k in ("commit", "pom", "runtime", "classes")):
                raise ValueError(f"{side}: built client or runtime graph differs from the measured deployment")
        result = framework_plan(args.checker, subjects, measured, registration)
        result["measurementSha256"] = upgrade_replay.sha(args.rebind)
        return result
    old, before, old_deps = subjects["before"]
    _, after, new_deps = subjects["after"]
    _, report["unchangedSourceBuild"] = compile_source(old, new_deps, work / "unchanged-classes", env, release=target_release(old))
    for name, classes, deps in (("old", before, old_deps), ("oldBinaryNewRuntime", before, new_deps), ("adapted", after, new_deps)):
        def binding():
            return change_inventory.digest({"registration": report["registrationSha256"], "jdk": report["jdk"],
                "runner": upgrade_replay.sha(Path(__file__)), "classes": change_inventory.file_digest(classes),
                "runtime": [upgrade_replay.sha(file) for file in deps], "launch": name})
        key = binding()
        cache = (args.cache or work / "accepted") / (key + ".json")
        hit = positive_receipt(cache, key) if args.single_pass and args.cache else None
        first = hit or check_deployment(name, classes, deps, registration, work, env)
        eligible = all(v == "established" for v in first["claims"].values())
        if eligible and hit is None and (args.cache or not args.single_pass):
            change_evidence.write_json(cache, {"key": key, "sha256": change_inventory.digest(first), "result": first})
        if args.single_pass:
            report["deployments"][name] = {**first, "executionKey": key, "action": "exact reuse" if hit else "executed"}
            continue
        clock = time.monotonic()
        rebound = binding()
        stored = positive_receipt(cache, rebound)
        reused = stored is not None
        resumed = stored or check_deployment(name + "-retry", classes, deps, registration, work, env)
        warm = time.monotonic() - clock
        clean = check_deployment(name + "-clean", classes, deps, registration, work, env)
        same = (resumed["claims"] == clean["claims"] and resumed["consistent"] and clean["consistent"]
                and resumed["trials"][0]["observations"] == clean["trials"][0]["observations"])
        report["deployments"][name] = {**first, "executionKey": key, "reuse": reused, "warmWallSeconds": round(warm, 4),
                                      "cleanCost": clean["cost"], "cleanEquivalent": same,
                                      "questions": [w["id"] for w in registration["productionWorkflows"]]}
    return report


def compare_passes(args, work):
    """Start three fresh verifier processes. Each resolves, rebuilds, binds, and answers every deployment question."""
    results, scope, measured = {}, None, None
    for label in ("cold", "exact", "clean"):
        output = work / (label + ".json")
        argv = [sys.executable, "-B", str(Path(__file__).resolve()), "--single-pass", "--output", str(output),
                "--maven-cache", str(args.maven_cache or work / "m2")]
        if args.mirror:
            argv += ["--mirror", str(args.mirror)]
        if label != "clean":
            argv += ["--cache", str(work / "proofs")]
        metrics = {}
        err = work / (label + ".err")
        state, code, wall = runtime._run_one(argv, ROOT, work / (label + ".out"), err, 900, env=os.environ, usage=metrics)
        if state != "exited" or code:
            raise ValueError(f"{label} deployment pass: {state} {code}, {err.read_text()[-700:]}")
        data = json.loads(output.read_bytes())
        if label == "cold":
            measured = data
        outputs = {n: {"executionKey": d["executionKey"], "claims": d["claims"],
                       "launch": d["trials"][0]["launch"], "reason": d["trials"][0].get("reason"),
                       "observations": d["trials"][0]["observations"]} for n, d in data["deployments"].items()}
        stable = {"registration": data["registrationSha256"], "unchangedSource": data["unchangedSourceBuild"],
                  "jdk": data["jdk"], "deployments": outputs}
        if scope is not None and stable != scope:
            raise ValueError(f"{label}: deployment, invocation, caller outcome or scope differs")
        if not all(d["consistent"] for d in data["deployments"].values()):
            raise ValueError(f"{label}: different observations across fresh trials")
        scope = stable
        actions = {n: d["action"] for n, d in data["deployments"].items()}
        expected = {n: "exact reuse" if label == "exact" and all(v == "established" for v in d["claims"].values())
                    else "executed" for n, d in data["deployments"].items()}
        if actions != expected:
            raise ValueError(f"{label}: different actual reuse from the qualified deployment evidence")
        results[label] = {"wallSeconds": wall, **metrics, "actions": actions,
                          "preparationSeconds": sum(d["seconds"] for d in data["builds"].values())}
    return {"schema": "held-back-full-cost/v1", "scope": scope, "passes": results, "measurement": measured,
            "costScope": "Fresh processes, source retrieval, Maven resolution, compilation, input binding, cache reads and writes, original HTTP execution and witness handling. Exact and clean share a populated Maven download cache.",
            "cleanEquivalent": True}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--mirror", type=Path, help="optional local bare clone containing the registered commits")
    ap.add_argument("--maven-cache", type=Path, help="writable cache for the original runtime dependency graphs")
    ap.add_argument("--rebind", type=Path, help="bind an existing measured migration to both application observation inventories")
    ap.add_argument("--checker", type=Path, default=Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")))
    ap.add_argument("--compare-passes", action="store_true", help="measure full cold, exact and clean application runs")
    ap.add_argument("--single-pass", action="store_true", help="resolve, rebuild and evaluate each deployment once")
    ap.add_argument("--cache", type=Path, help="persistent exact positive receipts for a deployment pass")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="held-back-petclinic-") as temp:
        result = compare_passes(args, Path(temp).resolve()) if args.compare_passes else run(args, Path(temp).resolve())
    change_evidence.write_json(args.output, result)
    if args.compare_passes:
        print({k: v["wallSeconds"] for k, v in result["passes"].items()})
        sys.exit(0)
    if args.rebind and "claims" in result:
        print(f"{len(result['claims'])} deployment/workflow obligations, discovery misses {result['discoveryMisses']}")
        sys.exit(0)
    if not result["deployments"]:
        sys.exit("held-back preparation open: see the build diagnoses")
    if not args.single_pass and not all(d["cleanEquivalent"] for d in result["deployments"].values()):
        sys.exit("held-back incremental results differ from clean recomputation")
    print(json.dumps({k: v["claims"] for k, v in result["deployments"].items()}))
