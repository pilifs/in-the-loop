"""Rebuild the unchanged S16 Boot source pairs on a common, explicitly reconstructed July codec profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import unquote, urlparse
from urllib.request import ProxyHandler, build_opener

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from workspace import scratch


def sha(path):
    with path.open("rb") as src:
        return hashlib.file_digest(src,"sha256").hexdigest()


def source_archive(cache, framework, fetch):
    ref = framework["revision"]
    path = cache/"downloads"/f"framework-{ref}.tar.gz"
    if fetch and not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as download:
            candidate = Path(download.name)
        try:
            with build_opener(ProxyHandler({})).open(
                    "https://codeload.github.com/spring-projects/spring-framework/tar.gz/"+ref,timeout=60) as source, candidate.open("wb") as dest:
                shutil.copyfileobj(source,dest)
            if sha(candidate) != framework["archiveSha256"]:
                raise ValueError("different historical Framework source archive")
            candidate.replace(path)
        finally:
            candidate.unlink(missing_ok=True)
    if not path.is_file() or path.stat().st_size != framework["archiveBytes"] or sha(path) != framework["archiveSha256"]:
        raise ValueError("the pinned historical Framework archive is missing or changed; --fetch retrieves the public original")
    return path


def compile_with(jdk, sources, cp, dest):
    dest.mkdir(parents=True,exist_ok=True)
    subprocess.run([jdk/"bin/javac","-encoding","UTF-8","-parameters","-implicit:none","-proc:none","-d",dest,
                    "-cp",os.pathsep.join(map(str,cp)),*sources],check=True,timeout=50)


def class_digests(root):
    return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob("*.class"))}


def check_origin(output, name, directory):
    prefix = "[Loaded " + name + " from "
    values = [line[len(prefix):-1] for line in output.splitlines() if line.startswith(prefix) and line.endswith("]")]
    if len(values) != 1 or Path(unquote(urlparse(values[0]).path)).resolve() != directory.resolve():
        raise ValueError("different defining source for " + name)
    return sha(directory / (name.replace(".","/") + ".class"))


def run(fetch=False):
    inputs = json.loads((HERE/"reconstruction-inputs.json").read_text())
    cache = Path(os.environ.get("SPRING_BOOT_S_CACHE",Path.home()/".cache/in-the-loop/spring-boot-pr-links-s01-s50"))
    jdk = Path.home()/".sdkman/candidates/java"/inputs["jdk"]
    if sha(jdk/"release") != inputs["jdkReleaseSha256"]:
        raise ValueError("different JDK 8")
    jars = [cache/p for p in inputs["classpath"]]
    if any(sha(jar) != inputs["sha256"][name] for jar,name in zip(jars,inputs["classpath"])):
        raise ValueError("different reconstructed dependency graph")
    framework = inputs["framework"]
    archive = source_archive(cache,framework,fetch)
    result = {"schema":"original-boot-source-on-reconstructed-profile/v1","historicalSnapshotIdentityEstablished":False,
              "inputsSha256":sha(HERE/"reconstruction-inputs.json"),"frameworkRevision":framework["revision"],"sides":{}}
    with scratch("boot-webflux-originals-") as tmp:
        work = Path(tmp)
        fw = work/"framework"
        with tarfile.open(archive) as tar:
            sources = []
            for name, expected in framework["sources"].items():
                data = tar.extractfile("spring-framework-"+framework["revision"]+"/"+name).read()
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError("different Framework source " + name)
                dest = work/"framework-sources"/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(data)
                sources.append(dest)
        compile_with(jdk,sources,jars,fw)
        result["frameworkClasses"] = class_digests(fw)
        caller = work/"caller"
        for side, registration in inputs["boot"].items():
            tree = cache/"worktrees"/("S16-"+side)
            classes = work/side
            sources, factories = [], {}
            for name, expected in registration["sources"].items():
                data = subprocess.check_output(["git","-C",tree,"show",registration["revision"]+":"+name])
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError("different Boot source " + name)
                if "/src/main/java/" in name:
                    path = work/(side+"-sources")/name
                    sources.append(path)
                else:
                    module, part = name.split("/src/main/resources/")
                    directory = work/(side+"-resources")/module
                    factories[module] = directory
                    path = directory/part
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data)
            compile_with(jdk,sources,[fw,*jars],classes)
            libs = [classes,*[factories[k] for k in sorted(factories)],fw,*jars]
            if side == "parent":
                compile_with(jdk,[HERE/"PersonApplication.java"],libs,caller)
            else:
                compile_with(jdk,[HERE/"MilestoneClients.java"],[caller,*libs],caller)
            observed = {}
            for history in (("intent","control") if side == "parent" else ("intent","control","challenge")):
                proc = subprocess.run([jdk/"bin/java","-verbose:class","-Xmx192m","-Dio.netty.eventLoopThreads=2",
                                       "-Dreactor.ipc.netty.workerCount=2","-cp",os.pathsep.join(map(str,[caller,*libs])),
                                       "fixture.webflux.PersonApplication",history],cwd=work,text=True,
                                      stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=35)
                if proc.returncode:
                    raise RuntimeError("original application failed: " + "\n".join(
                        line for line in proc.stdout.splitlines() if "Exception" in line and not line.startswith("[Loaded"))[-1600:])
                rows = [line[4:] for line in proc.stdout.splitlines() if line.startswith("OBS ")]
                if len(rows) != 1:
                    raise ValueError("missing public HTTP measurement")
                boot_names = ["org.springframework.boot.autoconfigure.web.reactive.WebFluxAutoConfiguration"]
                if side == "fix":
                    boot_names.append("org.springframework.boot.autoconfigure.http.codec.CodecsAutoConfiguration")
                if history == "challenge":
                    boot_names.extend(["org.springframework.boot.autoconfigure.web.reactive.function.client.WebClientAutoConfiguration",
                                       "org.springframework.boot.test.autoconfigure.web.reactive.WebTestClientAutoConfiguration"])
                origins = {name:check_origin(proc.stdout,name,classes) for name in boot_names}
                codec = "org.springframework.http.codec.DefaultServerCodecConfigurer"
                origins[codec] = check_origin(proc.stdout,codec,fw)
                observed[history] = {"public":rows[0],"originalClasses":origins}
                print(side,history,rows[0],flush=True)
            result["sides"][side] = {"revision":registration["revision"],"bootClasses":class_digests(classes),"observations":observed}
        result["callerClasses"] = class_digests(caller)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--record", action="store_true")
    args = p.parse_args()
    measured = run(args.fetch)
    target = HERE/"reconstructed-observations.json"
    if args.record:
        target.write_text(json.dumps(measured,indent=2)+"\n")
    elif json.loads(target.read_text()) != measured:
        raise ValueError("original source-profile observations changed")
