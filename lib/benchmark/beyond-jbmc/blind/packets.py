"""Materialize each selected distribution's signed Java dependencies and neutral binary packet."""
import argparse
from collections import deque
import gzip
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from freeze_product import verify
from history import encoded
from seal_panel import KEYRING, fetch, paragraphs, records, sha

AREA = Path.home() / ".cache/in-the-loop/beyond-jbmc/panel"
BASE = AREA / "evaluation"
PORTABLE = HERE / "draw"
CACHE = {}
JAVA_TOOLS = {"ant", "ant-optional", "junit", "junit4", "junit5", "testng", "maven", "groovy", "aspectj", "bsh", "ivy", "scala", "clojure"}
MANIFEST_PACKAGES = {"el-api-3.0.jar":"libel-api-java", "rhino.jar":"librhino-java", "xalan2.jar":"libxalan2-java"}


def unseal():
    _, lock = verify()
    stored = AREA / "sealed.json"
    wanted = (HERE.parent / "panel.sha256").read_text().split()[0]
    data = stored.read_bytes()
    if sha(data) != wanted:
        raise ValueError("blind draw commitment differs")
    doc = json.loads(data)
    for key, name in (("populationSha256","population.json"),("screeningSha256","screening.json")):
        if sha((AREA / name).read_bytes()) != doc[key]:
            raise ValueError("selection record differs: " + name)
    if doc["selectionProgramSha256"] != lock["operatorFiles"]["lib/benchmark/beyond-jbmc/seal_panel.py"]:
        raise ValueError("selection program differs")
    return doc


def suite_packages(suite, release):
    if suite in CACHE:
        return CACHE[suite]
    folder = AREA / suite
    signed = folder / "InRelease"
    if sha(signed.read_bytes()) != release["signedSha256"]:
        raise ValueError("signed release record differs")
    contents = subprocess.check_output(["gpgv","--keyring",KEYRING,"--output","-",signed],stderr=subprocess.DEVNULL)
    meta = next(paragraphs(io.StringIO(contents.decode())))
    sums = {path:digest for digest,_,path in (line.split() for line in meta["SHA256"].splitlines() if line)}
    table, virtual = {}, {}
    for component in ("universe","main"):
        path = Path(release["indexes"]["Packages"]["path"]) if component=="universe" else folder/"main-Packages.xz"
        key = component + "/binary-amd64/Packages" + (".xz" if path.suffix==".xz" else "")
        fetch(AREA,"dists/"+suite+"/"+key,path,sums[key])
        for entry in records(path):
            name=entry["Package"]
            if not (name.endswith("-java") or name in JAVA_TOOLS or entry.get("Section","").split("/")[-1]=="java"):
                continue
            table[name]={k:entry[k] for k in ("Package","Version","Depends","Pre-Depends","Filename","SHA256","Provides") if k in entry}
            for group in entry.get("Provides","").split(","):
                if group.strip():virtual.setdefault(group.strip().split()[0],[]).append(name)
    CACHE[suite]=table,virtual
    return table,virtual


def archive_jars(deb):
    actual, alias = {}, {}
    proc = subprocess.Popen(["dpkg-deb","--fsys-tarfile",deb],stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout,mode="r|") as tar:
            for m in tar:
                path=posixpath.normpath(m.name.removeprefix("./"))
                if not (path.endswith(".jar") and path.startswith(("usr/share/java/","usr/share/maven-repo/","usr/share/maven/lib/"))):
                    continue
                if m.isfile():
                    data=tar.extractfile(m).read()
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        manifest=z.read("META-INF/MANIFEST.MF").decode("utf-8","replace") if "META-INF/MANIFEST.MF" in z.namelist() else ""
                        manifest=manifest.replace("\r\n","\n").replace("\r","\n").replace("\n ","")
                        field=re.search(r"(?im)^Class-Path:[ \t]*([^\n]*)",manifest.split("\n\n")[0])
                        entries=field.group(1).split() if field else []
                    actual[path]=(sha(data),data,entries)
                elif m.issym() or m.islnk():
                    ref=m.linkname
                    alias[path]=posixpath.normpath(ref.lstrip("/") if ref.startswith("/") or m.islnk() else posixpath.join(posixpath.dirname(path),ref))
    finally:
        proc.stdout.close()
        if proc.wait():raise ValueError("cannot extract signed package payload")
    return actual,alias


def choose(group, table, virtual):
    for alternative in group.split("|"):
        term=alternative.strip()
        match=re.fullmatch(r"([\w.+-]+)(?::[\w-]+)?(?:\s*\((<<|<=|=|>=|>>)\s*([^()]+)\))?",term)
        if not match: continue
        name,op,version=match.groups()
        candidates=[name] if name in table else sorted(virtual.get(name,[]))
        for candidate in candidates:
            if not op or subprocess.run(["dpkg","--compare-versions",table[candidate]["Version"],op,version]).returncode==0:
                return candidate
    return None


def graph(row, side, releases, dest):
    index=0 if side=="old" else 1
    rec=row[("before","after")[index]]
    suite=row["suites"][index]
    table,virtual=suite_packages(suite,releases[suite])
    root=row["artifact"]
    if table[root]["SHA256"]!=rec["SHA256"]:raise ValueError("root package changed")
    queue=deque([root]);packages={}; jars={}; links={}; skipped=[]
    while queue:
        name=queue.popleft()
        if name in packages:continue
        pkg=table[name]
        path=AREA/(pkg["SHA256"]+".deb")
        fetch(AREA,pkg["Filename"],path,pkg["SHA256"])
        files, aliases=archive_jars(path)
        packages[name]={"version":pkg["Version"],"file":pkg["Filename"],"sha256":pkg["SHA256"],"requires":[]}
        for k,v in files.items():
            if k in jars and jars[k][:2]!=(name,v[0]):raise ValueError("classpath package file conflict")
            jars[k]=(name,*v)
        links.update(aliases)
        for _,_,entries in files.values():
            for entry in entries:
                basename=posixpath.basename(entry)
                provider=MANIFEST_PACKAGES.get(basename)
                if basename.startswith("fop-transcoder-allinone-"):provider="libfop-java"
                if provider in table and provider not in packages:
                    queue.append(provider)
        for field in ("Pre-Depends","Depends"):
            for group in pkg.get(field,"").replace("\n"," ").split(","):
                if not group.strip():continue
                selected=choose(group,table,virtual)
                if selected:
                    packages[name]["requires"].append(selected)
                    queue.append(selected)
                else:
                    skipped.append({"package":name,"requirement":group.strip()})
    root_file=row["eligibility"][side+"Jar"]
    if jars[root_file][1]!=row["eligibility"][side+"Sha256"]:raise ValueError("selected root JAR differs")
    dest.mkdir(parents=True,exist_ok=True)
    order,done,missing=[],set(),[]
    def add(path):
        original=path
        seen=set()
        while path in links and path not in seen:
            seen.add(path);path=links[path]
        if path not in jars:
            missing.append(original);return
        package,digest,data,entries=jars[path]
        if digest in done:return
        done.add(digest)
        file=f"{len(order):03d}.jar"
        target=dest/file
        if target.exists() and sha(target.read_bytes())!=digest:raise ValueError("neutral file has changed")
        if not target.exists():target.write_bytes(data)
        order.append({"path":side+"/"+file,"sha256":digest,"source":path,"package":package,"manifestClassPath":entries})
        for ref in entries:
            ref=ref.removeprefix("file:")
            add(posixpath.normpath(ref.lstrip("/") if ref.startswith("/") else posixpath.join(posixpath.dirname(original),ref)))
    add(root_file)
    for package in packages:
        for path in sorted(p for p,v in jars.items() if v[0]==package):add(path)
    alternatives={}
    for path in sorted(set(missing)):
        basename=posixpath.basename(path)
        candidates={jars[name][1] for name in jars if posixpath.basename(name)==basename}
        if len(candidates)==1:alternatives[path]=next(iter(candidates))
    return {"suite":suite,"packages":packages,"classpath":order,"unresolvedManifestPaths":sorted(set(missing)),
            "matchingBasenameOnOrderedClasspath":alternatives,
            "nonJavaOrUnresolvedDepends":skipped}


def prepare(doc, indexes):
    population=json.loads((AREA/"population.json").read_bytes())
    for index in indexes:
        row=doc["pairs"][index-1]; folder=BASE/f"{index:02}";folder.mkdir(parents=True,exist_ok=True)
        import tempfile
        temporary=Path(tempfile.mkdtemp(prefix="packet-build-",dir=folder))
        result={s:graph(row,s,population["releases"],temporary/s) for s in ("old","new")}
        packet={s:[{k:r[k] for k in ("path","sha256")} for r in value["classpath"]] for s,value in result.items()}
        (temporary/"inputs.json").write_bytes(encoded(packet))
        current=folder/"packet"
        if current.exists() and (current/"inputs.json").read_bytes()==encoded(packet):
            shutil.rmtree(temporary)
        else:
            if current.exists():
                prior=folder/("packet-previous-"+sha((current/"inputs.json").read_bytes()))
                current.rename(prior)
            temporary.rename(current)
        (folder/"graphs.json").write_bytes(encoded(result))
        print(f"{index:02}",len(packet["old"]),len(packet["new"]),"ordered jars",flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--slots",nargs="+",type=int,choices=range(1,17))
    p.add_argument("--publish",action="store_true")
    args=p.parse_args()
    doc=unseal()
    if args.publish:
        PORTABLE.mkdir(exist_ok=True)
        for name in ("sealed","screening","population"):
            inp=(AREA/(name+".json")).read_bytes()
            (PORTABLE/(name+".json.gz")).write_bytes(gzip.compress(inp,mtime=0))
        for i in range(1,17):
            folder=BASE/f"{i:02}"
            dest=PORTABLE/(f"{i:02}-graphs.json.gz")
            dest.write_bytes(gzip.compress((folder/"graphs.json").read_bytes(),mtime=0))
    else:
        prepare(doc,args.slots or range(1,17))
