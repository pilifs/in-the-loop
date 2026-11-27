"""Qualify a closed integral application property using bytes observed on the original JVM and read by stock JBMC."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from targets import change_evidence, change_helpers, change_inventory, entry_binding, runtime_jar, runtime_jdk, upgrade_replay

MEMBER = re.compile(r"(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*#[A-Za-z_$][\w$]*\([IJZCBS]*\)[IJZCBS]")
READ, OPEN, CLOSE = 1,32,16


def monitor(config, argv):
    """Observe access to private, immutable input files during this one stock process."""
    original=json.loads(Path(config).read_bytes())
    binary=Path(original["stock"])
    if upgrade_replay.sha(binary)!=original["stockSha256"]:
        raise ValueError("the stock executable changed")
    if "--function" not in argv:
        return subprocess.run([binary,*argv]).returncode
    if "--classpath" not in argv:
        raise ValueError("the actual stock invocation has no explicit classpath")
    cp=[Path(x).resolve() for x in argv[argv.index("--classpath")+1].split(os.pathsep)]
    root=Path(original["root"]).resolve()
    if root not in cp:
        raise ValueError("the final stock invocation omitted the qualified application classes")
    libc=ctypes.CDLL(None,use_errno=True)
    fd=libc.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
    if fd<0:
        raise OSError(ctypes.get_errno(),"stock file-read observation unavailable")
    watches={}
    events={name:0 for name in original["classes"]}
    try:
        for name, digest in original["classes"].items():
            classpath_name=name.replace(".","/")+".class"
            path=root/classpath_name
            if upgrade_replay.sha(path)!=digest:
                raise ValueError("changed physical stock class before invocation")
            # Account for every root the stock binary actually received. The projection
            # must be the first physical provider of each application class.
            for earlier in cp[:cp.index(root)]:
                if earlier.is_dir() and (earlier/classpath_name).exists():
                    raise ValueError("earlier class shadows the qualified stock input")
                if earlier.is_file():
                    with zipfile.ZipFile(earlier) as jar:
                        if any(n == classpath_name or (n.startswith("META-INF/versions/") and n.split("/",3)[-1] == classpath_name) for n in jar.namelist()):
                            raise ValueError("earlier jar shadows the qualified stock input")
            wd=libc.inotify_add_watch(fd,os.fsencode(path),READ|OPEN|CLOSE)
            if wd<0:
                raise OSError(ctypes.get_errno(),"cannot watch an original class read")
            watches[wd]=name
        result=subprocess.run([binary,*argv],stdout=subprocess.PIPE)
        while True:
            try: buffer=os.read(fd,65536)
            except BlockingIOError: break
            pos=0
            while pos<len(buffer):
                wd,mask,_,length=struct.unpack_from("=iIII",buffer,pos)
                pos+=16+length
                if wd not in watches:
                    raise ValueError("lost physical input events during the stock invocation")
                events[watches[wd]]|=mask
    finally:
        os.close(fd)
    try:
        messages=json.loads(result.stdout)
    except (ValueError,UnicodeDecodeError):
        messages=[]
    properties=[{"property":p.get("property"),"status":p.get("status")} for m in messages if isinstance(m,dict)
                for p in m.get("result",[]) if isinstance(p,dict)]
    record={"function":argv[argv.index("--function")+1],"argv":argv,"stockSha256":original["stockSha256"],
            "exit":result.returncode,"properties":properties,"classAccess":{
                name:{"opened":bool(mask&OPEN),"read":bool(mask&READ),"closed":bool(mask&CLOSE),"sha256":original["classes"][name]}
                for name,mask in events.items()}}
    file=Path(original["records"])/(str(os.getpid())+".json")
    change_evidence.write_json(file,record)
    sys.stdout.buffer.write(result.stdout)
    return result.returncode


def public_files(files, feature, owner):
    logical=runtime_jar.internal(owner)+".class"
    for i,file in enumerate(files):
        if file.is_dir():
            path=file/logical
            if path.is_file():return i,logical,path.read_bytes()
        else:
            with zipfile.ZipFile(file) as jar:
                if len(jar.namelist()) != len(set(jar.namelist())):
                    raise ValueError("ambiguous original jar entries")
                member=runtime_jar.effective_entries(jar,feature).get(logical)
                if member is not None:
                    return i,member.filename,jar.read(member)
    raise ValueError("no original application class for "+owner)


def closure(files, jdk, target, work):
    feature=int(runtime_jdk.feature(runtime_jdk.release(jdk)["JAVA_VERSION"]))
    lookup=work/"lookup";lookup.mkdir()
    subprocess.run([jdk/"bin/javac","-proc:none","-d",lookup,upgrade_replay.LOOKUP],check=True,capture_output=True)
    pending=[target]; seen={}; classes={}; edges=[]
    while pending:
        request=pending.pop()
        if request in seen:continue
        if len(seen)>=32 or not MEMBER.fullmatch(request):raise ValueError("closed integral stock scope needs bounded static primitive members")
        owner,method,desc=runtime_jar.parse_target(request)
        if owner in {"PropertyHarness","UpgradeClassLookup"} or owner.startswith(("java.","javax.","jdk.","sun.","com.sun.","jvmcontract.")):
            raise ValueError("this stock scope requires an original application member")
        i,physical,data=public_files(files,feature,owner)
        binding,=entry_binding.observe(jdk,lookup,files,[{"class":owner,"method":method,"descriptor":desc}])
        sha=hashlib.sha256(data).hexdigest()
        origin=urlsplit(binding["codeSource"])
        if (binding["status"]!="bound" or origin.scheme!="file" or Path(unquote(origin.path)).resolve()!=files[i]
                or binding["sha256"]!=sha or binding["physicalEntry"]!=physical or binding["declaringClass"]!=owner):
            raise ValueError("original JVM loader or physical member disagrees with the ordered classpath")
        pool,methods,_=runtime_jar._declarations(data,with_code=True)
        flags,code,handlers=methods[method,desc]
        if (runtime_jar.this_class(data)!=runtime_jar.internal(owner) or runtime_jar.super_class(data)!="java/lang/Object"
                or runtime_jar.interfaces(data) or not runtime_jar.class_flags(data)&1 or ("<clinit>","()V") in methods
                or flags&9!=9 or flags&0x120 or not code or handlers):
            raise ValueError("stock input is outside the closed integral static scope")
        checked=bytearray(code)
        for pc,op in change_inventory.instructions(code):
            if op==0xb8:
                ref=runtime_jar._member_ref(pool,pool[int.from_bytes(code[pc+1:pc+3],"big")][1])
                callee=ref[0].replace("/",".")+"#"+ref[1]+ref[2]
                pending.append(callee);edges.append({"caller":request,"bci":pc,"callee":callee})
                checked[pc:pc+3]=b"\0\0\0"
        if not change_helpers.local_integral_body(bytes(checked),pool):
            raise ValueError("stock input needs an operation outside the checked method closure")
        seen[request]={"originalJvm":binding,"providerIndex":i,"physicalEntry":physical,"classSha256":sha}
        classes[owner]=data
    return seen,classes,edges


def deciding_calls(calls, verdict, names):
    """Only the stock command that actually adjudicated the generated assertion provides binding evidence."""
    decisions=[]
    for call in calls:
        if call["function"] != "PropertyHarness.check":
            continue
        statuses=[p["status"] for p in call["properties"] if p["property"] and
                  p["property"].startswith("java::PropertyHarness.check:()V.assertion.")]
        if not statuses:
            continue
        reads=call["classAccess"]
        if set(reads) != set(names) or not all(r["read"] and r["opened"] for r in reads.values()):
            raise ValueError("deciding stock command did not read every qualified application class")
        decisions.append(statuses)
    if not decisions or verdict not in {"verified","violation"}:
        raise ValueError("no deciding stock assertion for the qualified property")
    flat=[status for statuses in decisions for status in statuses]
    if (verdict=="verified" and any(s!="SUCCESS" for s in flat)) or (verdict=="violation" and "FAILURE" not in flat):
        raise ValueError("reported property verdict differs from the actual stock assertion result")
    return decisions


def check(files,jdk,target,value,checker,stock,work,*,expected=None):
    files=[Path(p).resolve(strict=True) for p in files]
    jdk=Path(jdk).resolve();checker=Path(checker).resolve();stock=Path(stock).resolve()
    if not MEMBER.fullmatch(target) or not target.endswith("()I") or not -(2**31)<=value<2**31:
        raise ValueError("this stock qualification accepts a closed public ()I method and a signed integer expectation")
    version=subprocess.check_output([stock,"--version"],text=True).strip()
    if version.split()[0] != "6.11.0":raise ValueError("this stock version has not been qualified")
    original={str(p):change_inventory.file_digest(p) for p in files}
    scope=work/"private";scope.mkdir(mode=0o700)
    members,classes,edges=closure(files,jdk,target,scope)
    hashes={n:hashlib.sha256(data).hexdigest() for n,data in classes.items()}
    if expected is not None and hashes!=expected:raise ValueError("original class binding differs from the registered stock projection")
    projected=scope/"classes";projected.mkdir()
    for name,data in classes.items():
        out=projected/(runtime_jar.internal(name)+".class");out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(data);out.chmod(0o444)
    records=scope/"invocations";records.mkdir()
    config=scope/"binding.json"
    change_evidence.write_json(config,{"root":str(projected),"records":str(records),"stock":str(stock),"stockSha256":upgrade_replay.sha(stock),"classes":hashes})
    wrapper=scope/"checked-stock"
    wrapper.write_text("#!"+sys.executable+"\nimport runpy,sys\nm=runpy.run_path("+repr(str(Path(__file__).resolve()))+")\nraise SystemExit(m['monitor']("+repr(str(config))+",sys.argv[1:]))\n")
    wrapper.chmod(0o700)
    env={**os.environ,"JAVA_HOME":str(jdk),"PATH":str(jdk/"bin")+os.pathsep+os.environ.get("PATH",""),
         "JVMCONTRACT_JAR_RELEASE":str(runtime_jdk.feature(runtime_jdk.release(jdk)["JAVA_VERSION"]))}
    cmd=[checker,"prove",target,"--engine","jbmc","--gaps","strict","--classes",projected,
         "--assert","result == "+str(value),"--jbmc",wrapper,"--work",scope/"check","--json"]
    proc=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120)
    if not proc.stdout.strip():raise ValueError("stock supplied no property outcome: "+proc.stderr[-350:])
    row,=json.loads(proc.stdout)
    calls=[json.loads(p.read_bytes()) for p in sorted(records.glob("*.json"))]
    deciding = deciding_calls(calls,row["verdict"],classes)
    if any(change_inventory.file_digest(p)!=original[str(p)] for p in files) or any(upgrade_replay.sha(projected/(runtime_jar.internal(n)+".class"))!=s for n,s in hashes.items()):
        raise ValueError("the original or selected stock class changed during the proof")
    return {"schema":"original-bound-stock-property/v1","target":target,"expected":value,"verdict":row["verdict"],"scope":"closed integral static application methods",
            "originalClasspath":[{"file":str(p),"sha256":original[str(p)]} for p in files],"jdk":runtime_jdk.identity(jdk),
            "jdkReleaseSha256":upgrade_replay.sha(jdk/"release"),"stockVersion":version,"stockSha256":upgrade_replay.sha(stock),
            "checkerSha256":upgrade_replay.sha(checker),"members":members,"edges":edges,"executions":calls,"stockAssertions":deciding,"outcome":row}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classpath",action="append",type=Path,required=True)
    parser.add_argument("--jdk",type=Path,required=True);parser.add_argument("--target",required=True)
    parser.add_argument("--expect",type=int,required=True);parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--checker",type=Path,required=True);parser.add_argument("--stock",type=Path,default=shutil.which("jbmc"))
    args=parser.parse_args(argv)
    try:
        if not args.stock:
            raise ValueError("stock JBMC is unavailable")
        with tempfile.TemporaryDirectory(prefix="bound-stock-scalar-") as tmp:
            doc=check(args.classpath,args.jdk,args.target,args.expect,args.checker,args.stock,Path(tmp))
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:
        doc={"schema":"original-bound-stock-property/v1","target":args.target,"expected":args.expect,
             "verdict":"unverifiable","firstOpenDependency":str(error)}
    change_evidence.write_json(args.output,doc)
    print(doc["verdict"],doc.get("firstOpenDependency",args.target))
    return int(doc["verdict"]=="unverifiable")


if __name__=="__main__":
    sys.exit(main())

