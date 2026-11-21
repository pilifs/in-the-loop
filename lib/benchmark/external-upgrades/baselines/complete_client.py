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

from corpus_ci import maven_mirror, namespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engineering import HERE, classpath_rows, resolved_operand, digest, failure, read, source_side


def jar_directory(directory, target):
    """Package original Maven output without recompiling or modifying any member."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as jar:
        for file in sorted(directory.rglob("*")):
            if file.is_file():
                if file.is_symlink():
                    raise ValueError("compiled module has a symbolic link")
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
        reactor=["-pl",module.as_posix(),"-am"] if module!=Path(".") else []
        older=case["origin"].startswith("CompSuite") or case["id"] in ("ea-async-27","whatjdk-12","incremental-analysis-28","reflector-35")
        jdk=args.jdk8 if older else args.jdk21;maven=args.maven8 if older else args.maven
        argv=[*reactor,"-Dmaven.test.skip=true","-DincludeScope=runtime","-Dmdep.outputFile=target/upgrade-runtime.cp",
              "package","org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath"]
        original.update(subjectJdk=jdk.name,jdkReleaseSha256=digest(jdk/"release"),goals=argv)
        log=area/"package.log"
        with log.open("wb") as stream:
            try:
                status=subprocess.run([*namespace(project,work,scratch,socketdir,maven,jdk),*argv],stdout=stream,
                                      stderr=subprocess.STDOUT,timeout=args.seconds).returncode
            except subprocess.TimeoutExpired:status=124
        classes=project/module/"target/classes";cpfile=project/module/"target/upgrade-runtime.cp"
        owner=case["entry"].split("#")[0].replace(".","/")+".class"
        if status or not (classes/owner).is_file() or not cpfile.is_file():
            tail=[l for l in log.read_text(errors="replace").splitlines() if l.strip() and not l.startswith(("Download","Progress"))]
            return {**original,"stage":"original Maven build unavailable","exit":status,"diagnostic":failure("\n".join(tail)),
                    "logTail":tail[-10:],"logSha256":digest(log),"seconds":round(time.monotonic()-started,2)}
        jar=area/"client.jar";jar_directory(classes,jar)
        inputs=[copy_asset(jar,store)]
        for guest_path in cpfile.read_text().strip().split(":"):
            if not guest_path:continue
            if guest_path.startswith("/work/repository/"):
                rel=guest_path.removeprefix("/work/repository/")
                if ".." in Path(rel).parts:raise ValueError("Maven dependency path escapes its repository")
                local=work/"repository"/rel;shared=args.maven_cache/rel
                if shared.is_file() and digest(local)==digest(shared):inputs.append(shared.resolve())
                else:inputs.append(copy_asset(local,store))
            elif guest_path.startswith("/project/"):
                local=(project/guest_path.removeprefix("/project/")).resolve()
                if not local.is_relative_to(project):raise ValueError("reactor path escapes its checkout")
                if local.is_dir():
                    packed=area/"reactor.jar";jar_directory(local,packed);local=packed
                inputs.append(copy_asset(local,store))
            else:raise ValueError("unknown Maven runtime classpath location")
        anchor, relocations = resolved_operand(args.maven_cache, case, rev)
        if relocations: original["dependencyRelocations"] = relocations
        if not anchor.is_file() or digest(anchor) not in {digest(f) for f in inputs[1:]}:
            return {**original,"stage":"original Maven runtime operand unavailable","exit":status}
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
    args=ap.parse_args()
    cases={c["id"]:c for c in read(HERE/"corpus.json")["cases"]};repos=read(args.repositories)
    args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="complete-maven-mirror-") as temp, maven_mirror.serve(args.maven_cache,Path(temp),6*1024**3):
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
