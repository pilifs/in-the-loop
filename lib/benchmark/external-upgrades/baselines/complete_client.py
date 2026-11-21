"""Prepare a complete original Maven module, including generated classes and processed resources, for a caller replay."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET

from corpus_ci import maven_mirror, namespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engineering import HERE, classpath_rows, resolved_operand, digest, failure, read, source_side


def declared_scope(pom, coordinate):
    group, artifact = coordinate.split(":")
    rows = [entry for entry in ET.parse(pom).findall("{*}dependencies/{*}dependency")
            if entry.findtext("{*}groupId") == group and entry.findtext("{*}artifactId") == artifact]
    return (rows[0].findtext("{*}scope") or "compile") if len(rows) == 1 else None


def jar_directory(directory, target, *, include_directories=False):
    """Package original Maven output without recompiling or modifying any member."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as jar:
        for file in sorted(directory.rglob("*")):
            if file.is_symlink():
                raise ValueError("compiled module has a symbolic link")
            if file.is_dir() and include_directories:
                # Package scanners use ClassLoader.getResources("package/path").
                jar.writestr(zipfile.ZipInfo(file.relative_to(directory).as_posix() + "/"), b"")
            elif file.is_file():
                item = zipfile.ZipInfo(file.relative_to(directory).as_posix())
                jar.writestr(item, file.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)


def copy_asset(path, store):
    checksum=digest(path)
    dest=store/(checksum+".jar")
    if not dest.is_file():
        with tempfile.NamedTemporaryFile(dir=store) as tmp:
            with path.open("rb") as source:
                shutil.copyfileobj(source,tmp)
            tmp.flush()
            try:os.link(tmp.name,dest)
            except FileExistsError:pass
    if digest(dest)!=checksum:raise ValueError("cached complete module bytes differ")
    return dest


def side(case, rev, repo, args, socketdir):
    commit=source_side(case,rev,repo)
    root=args.preparations/case["id"]/rev
    root.mkdir(parents=True,exist_ok=True)
    store=(args.preparations/"assets").resolve()
    store.mkdir(exist_ok=True)
    started=time.monotonic()
    original={"commit":commit,"sourceSha256":case["sourceSha256"],"scope":"complete original Maven production module",
              "module":case["modulePom"]}
    with tempfile.TemporaryDirectory(prefix="original-maven-module-") as t:
        area=Path(t);project=area/"project";work=area/"work";scratch=area/"scratch"
        (work/"home").mkdir(parents=True);(scratch/"jvm").mkdir(parents=True)
        env={"PATH":"/usr/bin:/bin","HOME":str(work/"home"),"GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":os.devnull}
        subprocess.run(["git","-c","core.hooksPath=/dev/null","clone","-q","--no-hardlinks","--no-checkout",str(repo),str(project)],check=True,env=env)
        subprocess.run(["git","-C",str(project),"-c","core.hooksPath=/dev/null","checkout","-q","--detach",commit],check=True,env=env)
        module=Path(case["modulePom"]).parent
        pom = project / case["modulePom"]
        scope = declared_scope(pom, case["dependency"])
        original.update(declaredDependencyScope=scope, modulePomSha256=digest(pom), operandScope=args.operand_scope)
        if args.operand_scope != "runtime" and scope != args.operand_scope:
            raise ValueError("the original module does not declare this operand with the requested scope")
        reactor=["-pl",module.as_posix(),"-am"] if module!=Path(".") else []
        older=case["origin"].startswith("CompSuite") or case["id"] in ("ea-async-27","whatjdk-12","incremental-analysis-28","reflector-35")
        jdk=args.jdk8 if older else args.jdk21;maven=args.maven8 if older else args.maven
        primary_scope = "test" if args.operand_scope == "test" else "runtime"
        fixtures = args.with_test_fixtures
        skip_tests = "-DskipTests" if args.operand_scope == "test" or fixtures else "-Dmaven.test.skip=true"
        phase = "test-compile" if fixtures and args.phase == "compile" else args.phase
        argv=[*reactor,skip_tests,"-DincludeScope="+primary_scope,"-Dmdep.outputFile=target/upgrade-runtime.cp",
              phase,"org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath"]
        original.update(subjectJdk=jdk.name,jdkReleaseSha256=digest(jdk/"release"),goals=argv)
        log=area/"package.log"
        releases = maven_mirror.declared_releases(project, case.get("repositoryPoms", []))
        original["declaredReleaseRepositories"] = releases
        with maven_mirror.serve(args.maven_cache, socketdir, 6*1024**3, releases), log.open("wb") as stream:
            try:
                invocation = namespace(project,work,scratch,socketdir,maven,jdk)
                status=subprocess.run([*invocation,*argv],stdout=stream,
                                      stderr=subprocess.STDOUT,timeout=args.seconds).returncode
                if status == 0 and (args.operand_scope == "provided" or fixtures):
                    extra_scope = "test" if fixtures else "provided"
                    host_args = ["-DincludeScope=" + extra_scope if a == "-DincludeScope=runtime" else
                                 "-Dmdep.outputFile=target/upgrade-" + extra_scope + ".cp" if a.startswith("-Dmdep.outputFile=")
                                 else a for a in argv]
                    original[extra_scope + "Goals"] = host_args
                    status=subprocess.run([*invocation, *host_args],stdout=stream,stderr=subprocess.STDOUT,
                                          timeout=max(1, args.seconds-(time.monotonic()-started))).returncode
            except subprocess.TimeoutExpired:status=124
        classes=project/module/"target/classes";cpfile=project/module/"target/upgrade-runtime.cp"
        owner=case["entry"].split("#")[0].replace(".","/")+".class"
        if status or not (classes/owner).is_file() or not cpfile.is_file():
            tail=[l for l in log.read_text(errors="replace").splitlines() if l.strip() and not l.startswith(("Download","Progress"))]
            return {**original,"stage":"original Maven build unavailable","exit":status,"diagnostic":failure("\n".join(tail)),
                    "logTail":tail[-10:],"logSha256":digest(log),"seconds":round(time.monotonic()-started,2)}
        jar=area/"client.jar";jar_directory(classes,jar,include_directories=fixtures)
        inputs=[copy_asset(jar,store)]
        guest_paths = cpfile.read_text().strip().split(":")
        if args.operand_scope == "provided":
            guest_paths.extend((project/module/"target/upgrade-provided.cp").read_text().strip().split(":"))
            original["scope"] = "original production module and runtime with the declared container-provided artifacts"
        elif args.operand_scope == "test":
            original["scope"] = "original production module on its declared Maven test classpath"
        def materialize(guest_path):
            if guest_path.startswith("/work/repository/"):
                rel=guest_path.removeprefix("/work/repository/")
                if ".." in Path(rel).parts:raise ValueError("Maven dependency path escapes its repository")
                local=work/"repository"/rel;shared=args.maven_cache/rel
                if shared.is_file() and digest(local)==digest(shared):
                    return shared.resolve()
                return copy_asset(local,store)
            elif guest_path.startswith("/project/"):
                local=(project/guest_path.removeprefix("/project/")).resolve()
                if not local.is_relative_to(project):raise ValueError("reactor path escapes its checkout")
                if local.is_dir():
                    packed=area/"reactor.jar";jar_directory(local,packed,include_directories=fixtures);local=packed
                return copy_asset(local,store)
            else:raise ValueError("unknown Maven runtime classpath location")
        runtime_paths = list(dict.fromkeys(p for p in guest_paths if p))
        inputs.extend(materialize(p) for p in runtime_paths)
        anchor, relocations = resolved_operand(args.maven_cache, case, rev)
        if relocations: original["dependencyRelocations"] = relocations
        if not anchor.is_file() or digest(anchor) not in {digest(f) for f in inputs[1:]}:
            return {**original,"stage":"original Maven "+args.operand_scope+" operand unavailable","exit":status}
        if fixtures:
            test_classes = project/module/"target/test-classes"
            if not test_classes.is_dir() or not any(test_classes.rglob("*.class")):
                raise ValueError("original Maven test classes unavailable")
            test_jar = area/"test-classes.jar"
            jar_directory(test_classes, test_jar, include_directories=True)
            original["frameworkFixtures"] = {"runtimeCount": len(inputs), "testClassesSha256": digest(test_jar)}
            inputs.append(copy_asset(test_jar, store))
            test_paths = (project/module/"target/upgrade-test.cp").read_text().strip().split(":")
            inputs.extend(materialize(p) for p in dict.fromkeys(test_paths) if p and p not in runtime_paths)
            original["scope"] = "original production runtime followed by original Maven test classes, resources and companions"
        prepared={**original,"stage":"artifacts ready","classpath":classpath_rows(inputs),"compiledClasses":len(list(classes.rglob("*.class"))),
                  "resources":sum(f.is_file() and f.suffix!=".class" for f in classes.rglob("*")),"seconds":round(time.monotonic()-started,2)}
        tmp=root/"prepared.tmp"
        tmp.write_text(json.dumps(prepared,indent=2)+"\n");tmp.replace(root/"prepared.json")
        return prepared


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case",action="append",required=True)
    for name in ("repositories","preparations","maven-cache","output"):ap.add_argument("--"+name,type=Path,required=True)
    home=Path.home();ap.add_argument("--jdk8",type=Path,default=home/".sdkman/candidates/java/8.0.512.0+9-tem")
    ap.add_argument("--jdk21",type=Path,default=home/".sdkman/candidates/java/21.0.13.0+9-tem")
    ap.add_argument("--maven",type=Path,default=home/".sdkman/candidates/maven/current")
    ap.add_argument("--maven8",type=Path,default=home/".cache/in-the-loop/external-upgrades/ci-tools/apache-maven-3.6.3")
    ap.add_argument("--seconds",type=int,default=420)
    ap.add_argument("--phase", choices=("package", "compile"), default="package",
                    help="compile retains original classes and processed resources when packaging tooling is unavailable")
    ap.add_argument("--operand-scope", choices=("runtime", "provided", "test"), default="runtime",
                    help="provided adds the original module's declared host classpath; test selects its test environment")
    ap.add_argument("--with-test-fixtures", action="store_true",
                    help="append original compiled test fixtures and their dependencies after the unchanged production classpath")
    args=ap.parse_args()
    if args.with_test_fixtures and args.operand_scope != "runtime":
        ap.error("--with-test-fixtures requires a runtime operand")
    cases={c["id"]:c for c in read(HERE/"corpus.json")["cases"]};repos=read(args.repositories)
    args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="complete-maven-mirror-") as temp:
        for cid in args.case:
            case=cases[cid];out=args.output/(cid+".json")
            if out.exists():raise ValueError("refusing to replace module evidence")
            result={}
            for rev in ("old","new"):
                try:val=side(case,rev,Path(repos[cid]),args,Path(temp))
                except (OSError,ValueError,subprocess.SubprocessError) as e:
                    val={"stage":"original Maven build unavailable","diagnostic":[str(e)]}
                result[rev]={k:v for k,v in val.items() if k!="classpath"}
                if "classpath" in val:result[rev]["orderedClasspathSha256"]=[v["sha256"] for v in val["classpath"]]
                out.write_text(json.dumps(result,indent=2)+"\n")
                print(cid,rev,val["stage"],flush=True)


if __name__=="__main__":
    main()
