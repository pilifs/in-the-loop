"""Seal or verify the checker, evidence profiles, artifact-only operator and selection rules."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

from history import HERE, ROOT, JDK as HISTORY_JDK, JBMC, MODELS, digest, encoded
from wire_campaign import JDK, CACHE
sys.path.insert(0,str(HERE/"blind"))
from run_operator import CODE

LOCK=HERE/"freeze.json"
PRODUCTS=CACHE.parent/"products"
POLICY=(*CODE, "lib/benchmark/beyond-jbmc/blind/run_operator.py","lib/benchmark/beyond-jbmc/blind/PROTOCOL.md",
        "lib/benchmark/beyond-jbmc/panel.sha256","lib/benchmark/beyond-jbmc/seal_panel.py")


def input_files():
    files=[ROOT/"lib/Cargo.toml",ROOT/"lib/Cargo.lock"]
    for directory in ("src","models/classes","models/contracts"):
        files.extend(p for p in (ROOT/"lib"/directory).rglob("*") if p.is_file())
    return sorted(files)


def checker_inputs():
    rows={p.relative_to(ROOT).as_posix():digest(p) for p in input_files()}
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def runtime():
    return {"jdkModulesSha256":digest(JDK/"lib/modules"),"jdkJavaSha256":digest(JDK/"bin/java"),
            "jdkJavacSha256":digest(JDK/"bin/javac"),"historicalJdkModulesSha256":digest(HISTORY_JDK/"lib/modules"),
            "jbmcSha256":digest(JBMC),"coreModelsSha256":digest(MODELS)}


def create(checker,revision):
    names=[p.relative_to(ROOT).as_posix() for p in input_files()]+list(POLICY)
    names.extend(["lib/benchmark/beyond-jbmc/casebook.json","lib/benchmark/beyond-jbmc/historical/manifest.json"])
    commit=subprocess.check_output(["git","rev-parse","--verify",revision+"^{commit}"],cwd=ROOT,text=True).strip()
    if commit!=revision:
        raise ValueError("record the full source commit in the freeze")
    tree=subprocess.check_output(["git","ls-tree","-r","-z",commit,"--","lib","examples/tools/targets/runtime_jar.py"],cwd=ROOT)
    blobs={}
    for entry in tree.split(b"\0"):
        if entry:
            header,name=entry.split(b"\t",1)
            blobs[os.fsdecode(name)]=header.split()[-1].decode()
    for name in names:
        data=(ROOT/name).read_bytes()
        actual=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        if blobs.get(name)!=actual:
            raise ValueError("freeze input differs from the named source revision: "+name)
    sha=digest(checker)
    target=PRODUCTS/sha/"jvmcontract"
    lock={"schema":"beyond-jbmc-freeze/v1","revision":revision,"checkerSha256":sha,"checkerInputsSha256":checker_inputs(),
          "operatorFiles":{n:digest(ROOT/n) for n in POLICY},"casebookSha256":digest(HERE/"casebook.json"),
          "historicalManifestSha256":digest(HERE/"historical/manifest.json"),**runtime()}
    if LOCK.exists() and json.loads(LOCK.read_bytes())!=lock:
        raise ValueError("a different campaign freeze is already recorded")
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as f:
            with checker.open("rb") as original:shutil.copyfileobj(original,f)
        tmp=Path(f.name)
        if digest(tmp)!=sha:raise ValueError("checker changed while sealing")
        tmp.chmod(0o555)
        try:os.link(tmp,target)
        except FileExistsError: pass
        tmp.unlink()
    if digest(target)!=sha:raise ValueError("stored checker differs")
    if not LOCK.exists():
        with LOCK.open("xb") as f:f.write(encoded(lock))
    return lock


def verify():
    lock=json.loads(LOCK.read_bytes())
    target=PRODUCTS/lock["checkerSha256"]/"jvmcontract"
    if (digest(target)!=lock["checkerSha256"] or checker_inputs()!=lock["checkerInputsSha256"]
            or {n:digest(ROOT/n) for n in POLICY}!=lock["operatorFiles"]
            or any(lock[k]!=v for k,v in runtime().items()) or lock["casebookSha256"]!=digest(HERE/"casebook.json")
            or lock["historicalManifestSha256"]!=digest(HERE/"historical/manifest.json")):
        raise ValueError("campaign freeze differs")
    return target,lock


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="action",required=True)
    f=sub.add_parser("create");f.add_argument("--checker",required=True,type=Path);f.add_argument("--revision",required=True)
    sub.add_parser("check")
    r=sub.add_parser("run");r.add_argument("argv",nargs=argparse.REMAINDER)
    a=p.parse_args()
    if a.action=="create":create(a.checker,a.revision)
    target,lock=verify()
    if a.action=="run":
        argv=a.argv[1:] if a.argv[:1]==["--"] else a.argv
        if not argv:p.error("a campaign command is required")
        code=subprocess.run(argv,env=dict(os.environ,JVMCONTRACT=str(target))).returncode
        verify()
        sys.exit(code)
    print("frozen checker",lock["checkerSha256"],"operator",lock["operatorFiles"][CODE[-2]])
