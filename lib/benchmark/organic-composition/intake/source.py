"""Build the original production graph of the selected URL without reading its tests or PR description."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
JAVAS=Path.home()/".sdkman/candidates/java"
RUNTIME=JAVAS/"21.0.13.0+9-tem"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(repo,*args):
    return subprocess.check_output(["git","-C",repo,*args])


def main(url,area,case):
    match=re.fullmatch(r"https://github.com/(stleary/JSON-java)/pull/(\d+)",url)
    if not match:raise ValueError("URL outside the committed selection")
    project,number=match.groups()
    request=urllib.request.Request(f"https://api.github.com/repos/{project}/pulls/{number}",headers={"User-Agent":"in-the-loop-java-verification"})
    with urllib.request.urlopen(request,timeout=30) as response:
        pr=json.load(response)
    merge=pr["merge_commit_sha"]
    if not pr["merged_at"] or not re.fullmatch(r"[0-9a-f]{40}",merge):raise ValueError("PR has no merged endpoint")
    area.mkdir(parents=True,exist_ok=True)
    mirror=area/"source.git"
    if not mirror.exists():subprocess.run(["git","init","--bare","-q",mirror],check=True)
    if subprocess.run(["git","-C",mirror,"cat-file","-e",merge+"^{commit}"],stderr=subprocess.DEVNULL).returncode:
        subprocess.run(["git","-C",mirror,"fetch","-q","--no-tags","--depth=2",f"https://github.com/{project}.git",merge],check=True)
    parent=git(mirror,"rev-parse",merge+"^1").decode().strip()
    if git(mirror,"rev-parse",merge).decode().strip()!=merge:raise ValueError("upstream object mismatch")
    evidence={"url":url,"parent":parent,"merge":merge,"sides":{}}
    for side,rev in (("old",parent),("new",merge)):
        all_names=[n.decode() for n in git(mirror,"ls-tree","-r","--name-only","-z",rev).split(b"\0") if n]
        prefix=next((prefix for prefix in ("src/main/java/","src/") if prefix+"org/json/JSONArray.java" in all_names),"")
        names=[n for n in all_names if n.endswith(".java") and ((prefix and n.startswith(prefix)) or (not prefix and "/" not in n))]
        if not names or any("test" in n.lower().split("/") for n in names):raise ValueError("unqualified production source layout")
        resources=[n for n in all_names if n.startswith("src/main/resources/")]
        pom=git(mirror,"show",rev+":pom.xml")
        xml=ET.fromstring(pom); ns={"m":"http://maven.apache.org/POM/4.0.0"}
        deps=[]
        for dep in xml.findall("m:dependencies/m:dependency",ns):
            scope=dep.findtext("m:scope",default="compile",namespaces=ns)
            if scope not in ("test","provided"):deps.append(dep.findtext("m:artifactId",namespaces=ns))
        if deps:raise ValueError("production dependencies require explicit resolution: "+", ".join(deps))
        props=xml.find("m:properties",ns)
        settings={e.tag.split("}")[-1]:(e.text or "").strip() for e in props} if props is not None else {}
        def version(key):
            value=settings.get("maven.compiler."+key)
            if not value:
                for plugin in xml.findall(".//m:plugin",ns):
                    if plugin.findtext("m:artifactId",namespaces=ns)=="maven-compiler-plugin":
                        value=plugin.findtext("m:configuration/m:"+key,namespaces=ns)
                        if value:break
            if value and value.startswith("${"):value=settings.get(value[2:-1])
            return value
        source=version("source") or version("release")
        target=version("target") or version("release")
        if not source or not target:raise ValueError("upstream source/target declarations require inspection")
        feature=int(target.removeprefix("1."))
        compiler=JAVAS/("8.0.512.0+9-tem" if feature<=8 else "17.0.21.0+9-tem" if feature<=17 else "21.0.13.0+9-tem")
        with tempfile.TemporaryDirectory(dir=area,prefix=side+"-") as temp:
            w=Path(temp); classes=w/"classes";classes.mkdir(); sources={}
            for name in names:
                data=git(mirror,"show",rev+":"+name); sources[name]=sha(data)
                dest=w/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            flags=["-source",source,"-target",target] if feature<=8 else ["--release",str(feature)]
            subprocess.run([compiler/"bin/javac","-proc:none","-g","-encoding","UTF-8",*flags,"-d",classes,
                            *(w/n for n in names)],check=True,capture_output=True)
            members={f.relative_to(classes).as_posix():f.read_bytes() for f in sorted(classes.rglob("*.class"))}
            for n in resources:members[n.removeprefix("src/main/resources/")]=git(mirror,"show",rev+":"+n)
            jar=area/(rev+".jar")
            staged=w/"production.jar"
            with zipfile.ZipFile(staged,"w",zipfile.ZIP_DEFLATED) as z:
                for name,data in sorted(members.items()):
                    info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                    z.writestr(info,data)
            if jar.exists() and jar.read_bytes()!=staged.read_bytes():raise ValueError("rebuild differs from retained artifact")
            if not jar.exists():staged.replace(jar)
        manifest={"commit":rev,"sourceSha256":sha(json.dumps(sources,sort_keys=True).encode()),
                  "scope":"Complete tracked production Java sources and packaged production resources, compiled with the upstream source and target levels.",
                  "classpath":[{"file":str(jar),"sha256":sha(jar.read_bytes())}],"jdkReleaseSha256":sha((RUNTIME/"release").read_bytes())}
        d=case/side;d.mkdir(parents=True,exist_ok=True)
        (d/"prepared.json").write_text(json.dumps(manifest,indent=2)+"\n")
        evidence["sides"][side]={"commit":rev,"tree":git(mirror,"rev-parse",rev+"^{tree}").decode().strip(),"sourcePrefix":prefix,
          "sources":sources,"resourceCount":len(resources),"classCount":len(members)-len(resources),"compiler":str(compiler),
          "javacFlags":flags,"pomSha256":sha(pom),"compileDependencies":deps,"jar":manifest["classpath"][0]}
    (case/"sources.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print(project,number,parent,merge,[(s,r["classCount"]) for s,r in evidence["sides"].items()])

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("url");p.add_argument("--area",type=Path,required=True);p.add_argument("--case",type=Path,required=True)
    a=p.parse_args();main(a.url,a.area.resolve(),a.case.resolve())
