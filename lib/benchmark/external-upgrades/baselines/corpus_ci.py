"""Run Maven verification on the original upgrade revisions and identify fresh historical testcase results."""

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
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from engineering import failure, git, read, source_side
from pin import digest
import maven_mirror
from public_ci import namespace


def config_files(repo, commit):
    files = git(repo, "ls-tree", "-r", "--name-only", commit).decode().splitlines()
    names = [f for f in files if f in (".travis.yml","Jenkinsfile","appveyor.yml",".circleci/config.yml")
             or f.startswith(".github/workflows/") and f.endswith((".yaml",".yml"))]
    results = {}
    for name in names:
        raw = git(repo, "show", commit + ":" + name)
        lines = [s.strip() for s in raw.decode(errors="replace").splitlines()
                 if re.search(r"(?<![\w.-])(?:\./)?mvnw?\s+[^#]*\b(?:test|verify|install|package)\b",s)
                 and not re.search(r"password|credential|token|secret",s,re.I)]
        results[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "mavenCommandLines": lines[:8]}
    return results


def fresh_reports(project, name, out):
    tests = failures = errors = skipped = 0
    named, failed, files = [], [], {}
    for area in ("surefire-reports", "failsafe-reports"):
        for file in sorted(project.glob("**/target/"+area+"/TEST-*.xml")):
            doc = ET.parse(file).getroot()
            rel = file.relative_to(project).as_posix()
            files[rel] = digest(file)
            for t in doc.iter("testcase"):
                tests += 1
                outcome = next((k for k in ("failure","error","skipped") if t.find(k) is not None), "passed")
                failures += outcome == "failure"
                errors += outcome == "error"
                skipped += outcome == "skipped"
                cls, method = t.get("classname",""), t.get("name","")
                elem = t.find(outcome) if outcome != "passed" else None
                row = {"class": cls, "method": method, "outcome": outcome}
                if elem is not None and outcome in ("failure","error"):
                    row.update(type=elem.get("type"), message=(elem.get("message") or "")[:700])
                    if len(failed) < 12: failed.append(row)
                if name and cls.rsplit(".",1)[-1] == name[0] and re.fullmatch(re.escape(name[1])+r"(?:\[.*\]|\(.*\))?",method):
                    named.append(row)
                    keep = out / "testcases" / (hashlib.sha256(rel.encode()).hexdigest()[:12]+".xml.gz")
                    keep.parent.mkdir(parents=True,exist_ok=True)
                    keep.write_bytes(gzip.compress(file.read_bytes(),mtime=0))
    return {"tests":tests,"failures":failures,"errors":errors,"skipped":skipped,"named":named,"firstFailures":failed,
            "reportCount":len(files),"reportsSha256":hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()}


def run_side(case, side, repo, args, out):
    commit = source_side(case, side, repo)
    config = config_files(repo, commit)
    record = {"revision":commit,"historicalCiFiles":config,"selectedLifecycle":"Maven verify on the original owning module and required reactor modules"}
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="upgrade-original-ci-") as temporary:
        root = Path(temporary)
        project, work, scratch, sockets = (root/x for x in ("project","work","scratch","sockets"))
        (work/"home").mkdir(parents=True)
        (scratch/"jvm").mkdir(parents=True)
        sockets.mkdir()
        git_env = {"PATH": "/usr/bin:/bin", "HOME": str(work/"home"), "GIT_CONFIG_NOSYSTEM": "1",
                   "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "clone", "-q", "--no-checkout", "--no-hardlinks",
                        str(repo), str(project)], env=git_env, check=True)
        subprocess.run(["git", "-C", str(project), "-c", "core.hooksPath=/dev/null", "checkout", "-q", "--detach", commit],
                       env=git_env, check=True)
        if git(project, "rev-parse", "HEAD").decode().strip() != commit:
            raise ValueError("CI checkout is not at the recorded revision")
        for kind in ("surefire-reports","failsafe-reports"):
            for d in project.glob("**/target/"+kind):
                shutil.rmtree(d)
        older = case["origin"].startswith("CompSuite") or case["id"] in ("whatjdk-12","ea-async-27","incremental-analysis-28","reflector-35")
        jdk, maven = (args.jdk8,args.maven8) if older else (args.jdk21,args.maven)
        module=Path(case["modulePom"]).parent
        named = case.get("namedTest","").split("#")
        if len(named)!=2: named=None
        # A published test may live in a sibling module (including an integration-test module).
        if named:
            paths=[p for p in project.rglob(named[0]+".java") if ("/src/test/" in p.as_posix() or "/test/" in p.as_posix())]
            if len(paths)==1:
                nearest=next((p for p in paths[0].parents if (p/"pom.xml").is_file() and p.is_relative_to(project)),None)
                if nearest:module=nearest.relative_to(project)
        reactor = ["-pl",module.as_posix(),"-am"] if module!=Path(".") and (project/"pom.xml").is_file() else []
        goals=[*reactor,"verify"]
        record.update(module=module.as_posix(),goals=goals,jdkReleaseSha256=digest(jdk/"release"),
                      mavenHome=maven.name,network="isolated client and serialized Maven Central mirror")
        out.mkdir(parents=True)
        log=work/"maven.log"
        with maven_mirror.serve(args.maven_cache,sockets,6*1024**3) as counters, log.open("wb") as stream:
            command=namespace(project,work,scratch,sockets,maven,jdk)
            try:
                status=subprocess.run([*command,*goals],stdout=stream,stderr=subprocess.STDOUT,timeout=args.seconds).returncode
            except subprocess.TimeoutExpired:
                status=124
            record["resolver"]=dict(counters)
        text=log.read_text(errors="replace")
        reports=fresh_reports(project,named,out)
        record.update(exit=status,seconds=round(time.monotonic()-start,2),logSha256=digest(log),freshReports=reports)
        if status or not reports["tests"]:
            record["diagnostic"]=failure(text)[-5:]
        if named:
            record["namedTest"]=case["namedTest"]
            record["namedTestExecuted"]=any(r["outcome"]!="skipped" for r in reports["named"])
        record["disposition"]=("timed out" if status==124 else "failed before tests" if status and not reports["tests"]
                               else "tests or lifecycle failed" if status else "zero tests" if not reports["tests"] else "passed")
        (out/"summary.json").write_text(json.dumps(record,indent=2)+"\n")
    return record


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case",action="append",required=True)
    for name in ("repositories","maven-cache","output"):
        ap.add_argument("--"+name,type=Path,required=True)
    home=Path.home()
    ap.add_argument("--maven",type=Path,default=home/".sdkman/candidates/maven/current")
    ap.add_argument("--maven8",type=Path,default=home/".cache/in-the-loop/external-upgrades/ci-tools/apache-maven-3.6.3")
    ap.add_argument("--jdk21",type=Path,default=home/".sdkman/candidates/java/21.0.13.0+9-tem")
    ap.add_argument("--jdk8",type=Path,default=home/".sdkman/candidates/java/8.0.512.0+9-tem")
    ap.add_argument("--seconds",type=int,default=600)
    a=ap.parse_args()
    repos=read(a.repositories);cases={c["id"]:c for c in read(HERE.parent/"corpus.json")["cases"]}
    for cid in a.case:
        for side in ("old","new"):
            out=a.output/cid/side
            if out.exists(): ap.error("refusing to replace an original CI result")
            try:
                r=run_side(cases[cid],side,Path(repos[cid]),a,out)
            except (OSError,ValueError,subprocess.SubprocessError,ET.ParseError) as exc:
                r={"disposition":"unavailable","diagnostic":[str(exc)],"revision":cases[cid]["revisions"][side]}
                out.mkdir(parents=True,exist_ok=True)
                (out/"summary.json").write_text(json.dumps(r,indent=2)+"\n")
            print(cid,side,r["disposition"],r.get("freshReports",{}).get("tests",0),flush=True)


if __name__=="__main__":
    main()
