"""Automatic operator. Receives neutral artifact classpaths and a frozen checker. It never receives the reference caller or outcome."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import runtime_jar
sys.path.insert(0,str(ROOT/"lib/tools"))
from process_usage import wait as wait_measured
sys.path.insert(0,str(ROOT/"lib/python"))
import jvmcontract_io as wire

POLICY = {"format":"artifact-only/v1","impactCandidates":24,"attempts":4,"perCheckerSeconds":120,"unwind":16,
          "arrayBound":8,"freshJvmSeeds":12,"impactSeconds":40,"operatorInputs":["ordered binary classpaths"],
          "selection":"public common methods, literal resource links and body changes, then transitive impact and constructibility"}
BASIC = {"Z":"boolean","B":"byte","C":"char","S":"short","I":"int","J":"long","F":"float","D":"double","V":"void"}
SIMPLE = {*BASIC.values(),"java.lang.String"}
OBSERVERS = ("size","length","getValue","value","isEmpty","toByteArray","getPosition","getName","getType","toString","hashCode")
ACTION = re.compile(r"^(?:parse|read|write|encode|decode|format|convert|contains|resolve|find|calculate|compare|add|remove|set|put|with|clone)", re.I)


def digest(b): return hashlib.sha256(b).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=1,ensure_ascii=True)+"\n")


def types(descriptor):
    values = re.findall(r"\[*?(?:[ZBCSIJFDV]|L[^;]+;)", descriptor)
    if not values or "("+''.join(values[:-1])+")"+values[-1] != descriptor:
        raise ValueError("invalid descriptor")
    result=[]
    for v in values:
        base=v.lstrip("[")
        typ=BASIC[base] if base in BASIC else base[1:-1].replace("/",".").replace("$",".")
        result.append(typ+"[]"*(len(v)-len(base)))
    return result[:-1],result[-1]


def simple(t):
    return t!="void" and (t in SIMPLE or t.endswith("[]") and t[:-2] in BASIC.values() and t[:-2]!="void")


def binary(path):
    classes,resources={},{}
    with zipfile.ZipFile(path) as z:
        for key,info in runtime_jar.effective_entries(z,21).items():
            if key.startswith("META-INF/versions/") or key=="module-info.class":continue
            data=z.read(info)
            if key.endswith(".class"):
                if not runtime_jar.class_flags(data) & 1:continue
                pool,methods,_=runtime_jar._declarations(data,with_code=True)
                classes[key[:-6]]=(methods,{v for tag,v in pool.values() if tag==1},runtime_jar.class_flags(data),digest(data))
            elif not key.upper().startswith(("META-INF/MANIFEST","META-INF/MAVEN","META-INF/LICENSE","META-INF/NOTICE")) and not key.upper().endswith((".SF",".RSA",".DSA")):
                resources[key]=digest(data)
    return classes,resources


def extract(jar,dest):
    dest.mkdir(parents=True)
    with zipfile.ZipFile(jar) as z:
        for key,info in runtime_jar.effective_entries(z,21).items():
            if not key or key=="module-info.class" or key.startswith("META-INF/versions/"):continue
            p=dest/key
            if Path(key).is_absolute() or ".." in Path(key).parts or p.exists():raise ValueError("ambiguous member")
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(z.read(info))


def available(method):
    flags,body,_=method
    return flags&1 and not flags&(0x0040|0x1000) and body is not None


def rank(kind, values):
    return digest((kind+"\0"+json.dumps(values,sort_keys=True)).encode())


def candidates(old,new,resources):
    result=[]
    changed={k for k in resources[0].keys()|resources[1].keys() if resources[0].get(k)!=resources[1].get(k)}
    for owner in sorted(old.keys()&new.keys()):
        if not all(re.fullmatch(r"[A-Za-z_$][A-Za-z\d_$]*",p) for p in owner.split("/")) or "$" in owner:continue
        oldm,strings,flags,oldsha=old[owner];newm,ns,nflags,newsha=new[owner]
        java=owner.replace("/",".")
        common={k for k in oldm.keys()&newm.keys() if available(oldm[k]) and available(newm[k])}
        ctors=[]; getters=[]
        for name,desc in common:
            ps,ret=types(desc)
            if len(ps)<=3 and all(map(simple,ps)):
                if name=="<init>" and not (flags|nflags)&0x0600:
                    ctors.append((len(ps),0,desc,name,ps))
                elif oldm[name,desc][0]&8 and newm[name,desc][0]&8 and ret==java:
                    ctors.append((len(ps),1,desc,name,ps))
            if not ps and not (oldm[name,desc][0]|newm[name,desc][0])&8 and simple(ret) and name in OBSERVERS:
                getters.append((OBSERVERS.index(name),name,desc,ret))
        linked=sorted(r for r in changed if r in strings|ns or ("/"+r) in strings|ns)
        for name,desc in common:
            if name.startswith("<") or not re.fullmatch(r"[A-Za-z_$][A-Za-z\d_$]*",name):continue
            ps,ret=types(desc); static=bool(oldm[name,desc][0]&8)
            if static!=bool(newm[name,desc][0]&8):continue
            ctor=None if static or not ctors else min(ctors)
            getter=None if simple(ret) or not getters or static or ret not in ("void",java) else min(getters)
            viable=(len(ps)<=4 and all(map(simple,ps)) and (static or ctor is not None)
                    and (simple(ret) or getter is not None or (ret=="void" and any(p.endswith("[]") for p in ps))))
            key=java+"#"+name+desc
            body_changed=oldm[name,desc][1:]!=newm[name,desc][1:]
            result.append({"id":key,"owner":java,"method":name,"descriptor":desc,"params":ps,"return":ret,"static":static,
                           "exactDispatch":static or bool(flags & nflags & 0x10) or
                                           bool(oldm[name,desc][0] & newm[name,desc][0] & 0x10) or bool(ctor and ctor[1]==0),
                           "constructor":ctor,"getter":getter,"buildable":viable,"codeBytesDiffer":body_changed,
                           "classBytesDiffer":oldsha!=newsha,"changedResources":linked,
                           "rank":[not viable,not (body_changed or linked),not bool(ACTION.match(name)),oldsha==newsha,
                                   len(ps)+(ctor[0] if ctor else 0),rank("public method",key)]})
    return sorted(result,key=lambda c:c["rank"])


def tiered(items,n):
    picked=[];used=set()
    for c in items:
        if c["owner"] not in used:
            used.add(c["owner"]);picked.append(c)
            if len(picked)==n:return picked
    return (picked+[r for r in items if r not in picked])[:n]


def caller(c):
    ps=[];at=0
    def params(types):
        nonlocal at
        names=[]
        for typ in types:
            name=f"p{at}";at+=1;ps.append(f"{typ} {name}");names.append(name)
        return ", ".join(names)
    java=c["owner"];lines=[]
    if c["static"]:receiver=java
    else:
        _,kind,_,factory,cons=c["constructor"]
        args=params(cons)
        make=f"new {java}({args})" if kind==0 else f"{java}.{factory}({args})"
        lines.append(f"{java} receiver = {make};");receiver="receiver"
    call=f"{receiver}.{c['method']}({params(c['params'])})"
    ret=c["return"]
    if c["getter"]:
        _,get,_,ret=c["getter"]
        lines.extend([call+";",f"return receiver.{get}();"])
    else: lines.append(("" if ret=="void" else "return ")+call+";")
    return ("public final class PublicCaller {\n    public static "+ret+" observe("+", ".join(ps)+") throws Throwable {\n"
            +"".join("        "+line+"\n" for line in lines)+"    }\n}\n")


def run(cmd,folder,timeout,stdout,env):
    stdout.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    with stdout.open("wb") as out, stdout.with_suffix(stdout.suffix+".err").open("wb") as err:
        process=subprocess.Popen(list(map(str,cmd)),cwd=folder,env=env,stdout=out,stderr=err,start_new_session=True)
        timed_out,usage=wait_measured(process,timeout,process_group=True)
    code=124 if timed_out else process.returncode
    save(stdout.with_suffix(stdout.suffix+".cost.json"),{"exit":code,"timedOut":timed_out,
         "wallSeconds":time.monotonic()-started,"cpuSeconds":usage.ru_utime+usage.ru_stime,"peakMiB":usage.ru_maxrss/1024})
    return code,stdout.read_bytes()


def literal(typ,value):
    if typ.endswith("[]"):
        if value is None: return b"\0"
        if not isinstance(value,list) or len(value)>POLICY["arrayBound"]: raise ValueError("unsupported array witness")
        return b"\1"+struct.pack(">H",len(value))+b"".join(literal(typ[:-2],v) for v in value)
    if typ in ("java.lang.String","String"):
        if value is None: return b"\0"
        if isinstance(value,dict) and value.get("kind")=="string":
            units=b"".join(struct.pack(">H",v) for v in value["units"])
        elif isinstance(value,str):
            units=value.encode("utf-16-be","surrogatepass")
        else: raise ValueError("unsupported string witness")
        return b"\1"+struct.pack(">H",len(units)//2)+units
    if typ=="boolean":
        if type(value) is not bool: raise ValueError("invalid boolean witness")
        return bytes([value])
    if typ in ("float","double"):
        if isinstance(value,str) and value.startswith("bits:0x"):
            raw=bytes.fromhex(value[7:])
            if len(raw)!=(4 if typ=="float" else 8):raise ValueError("floating witness width")
            return raw
        return struct.pack(">f" if typ=="float" else ">d", float(value))
    if typ=="char" and isinstance(value,str) and len(value)==1:value=ord(value)
    return struct.pack({"byte":">b","short":">h","char":">H","int":">i","long":">q"}[typ],int(value))


def physical(c,graphs,work,output,classes,helpers,jdk,env,label,trial,witness=None):
    observations=[]
    for side,graph in zip(("old","new"),graphs):
        dest=work/(side+label+".obs")
        cmd=[jdk/"bin/java","-Xmx192m","-XX:-UsePerfData","-ea","-cp",os.pathsep.join(map(str,[helpers,classes,*graph])),
             "ArtifactProbe",str(trial),c["owner"],c["method"],dest]
        if witness is not None: cmd.append(witness)
        code,_=run(cmd,work,5,output/f"{side}-{label}.out",env)
        fields=[]
        if code==0 and dest.is_file():
            fields=[base64.b64decode(line,validate=True).decode() for line in dest.read_bytes().splitlines()]
        reached = len(fields)==5 and ((fields[3]=="true" and c["exactDispatch"]) or fields[4]=="true")
        observations.append({"exit":code,"fields":fields if len(fields)==5 else [],"namedEntryReached":reached,
                             "argv":list(map(str,cmd))})
    return observations


def exercise(c,graphs,roots,work,out,checker,jdk,env):
    cp=lambda paths:os.pathsep.join(map(str,paths))
    work.mkdir();out.mkdir()
    record={"candidate":c,"physical":[],"workflow":"generated public return/throw and parameter-array frame"}
    if not c["buildable"]:
        record["status"]="no supported public caller";return record
    src=work/"PublicCaller.java";src.write_text(caller(c))
    record["source"]=src.read_text()
    classes=work/"caller";classes.mkdir()
    code,_=run([jdk/"bin/javac","-proc:none","-parameters","-g","-cp",cp(graphs[0]),"-d",classes,src],
               work,45,out/"compile.out",env)
    if code:record["status"]="public caller did not compile";return record
    record["callerSha256"]=digest((classes/"PublicCaller.class").read_bytes())
    helpers=work.parent/"helpers"
    for i in range(POLICY["freshJvmSeeds"]):
        record["physical"].append(physical(c,graphs,work,out,classes,helpers,jdk,env,str(i),i))
    benchmark_target="PublicCaller#observe"
    roots_c=[]
    for label,root in zip(("old","new"),roots):
        dst=work/label
        # The main JAR is extracted once. Keep a complete copy with this caller on each side.
        shutil.copytree(root,dst,copy_function=os.link)
        if (dst/"PublicCaller.class").exists():
            record["status"]="generated caller name already present";return record
        shutil.copyfile(classes/"PublicCaller.class",dst/"PublicCaller.class")
        roots_c.append(dst)
    empty=work/"empty";empty.mkdir()
    cmd=[checker,"equivalence","--before",roots_c[0],"--after",roots_c[1],"--before-classpath",cp(graphs[0][1:] or [empty]),
         "--classpath",cp(graphs[1][1:] or [empty]),"--target",benchmark_target,"--engine","native","--gaps","strict",
         "--unwind",str(POLICY["unwind"]),"--max-array-length",str(POLICY["arrayBound"]),"--timeout",str(POLICY["perCheckerSeconds"]),
         "--work",work/"strict","--cache",work/"proof-cache","--json"]
    code,data=run(cmd,work,150,out/"native.json",env)
    decoded=wire.decode(data.decode(errors="replace"),"equivalence")
    row=decoded.outcomes[0] if decoded.ok and len(decoded.outcomes)==1 else {}
    record.update(argv=list(map(str,cmd)),exit=code,verdict=row.get("verdict"),stated=row.get("stated"),
                  problem=row.get("problem"),counterexample=row.get("counterexample"),status="measured")
    if record["verdict"]=="violation" and isinstance(record["counterexample"],dict):
        inputs=record["counterexample"].get("inputs")
        param_types=(c["constructor"][4] if c["constructor"] else [])+c["params"]
        try:
            if not isinstance(inputs,list) or len(inputs)!=len(param_types):raise ValueError("witness arity")
            raw=b"".join(literal(t,v["value"]) for t,v in zip(param_types,inputs))
            witness=out/"witness.bin";witness.write_bytes(raw)
            record["witnessReplay"]=physical(c,graphs,work,out,classes,helpers,jdk,env,"witness",0,witness)
            old,new=record["witnessReplay"]
            record["originalReplayChanged"]=bool(old["namedEntryReached"] and new["namedEntryReached"]
                and old["fields"][0]==new["fields"][0] and old["fields"][1:3]!=new["fields"][1:3])
        except (KeyError,ValueError,TypeError,OverflowError,struct.error):
            record["witnessReplayStatus"]="exact input reconstruction unsupported"
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pair",type=Path);parser.add_argument("output",type=Path)
    parser.add_argument("--checker",required=True,type=Path);parser.add_argument("--jdk",required=True,type=Path)
    parser.add_argument("--discover-only",action="store_true")
    args=parser.parse_args();pair=args.pair.resolve();out=args.output.resolve()
    if out.exists():raise ValueError("automatic first report already exists")
    out.mkdir(parents=True)
    bound=json.loads((pair/"inputs.json").read_bytes())
    graphs=[]
    for side in ("old","new"):
        graph=[]
        for spec in bound[side]:
            f=(pair/spec["path"]).resolve()
            if pair not in f.parents or digest(f.read_bytes())!=spec["sha256"]:raise ValueError("unbound classpath operand")
            graph.append(f)
        if not graph: raise ValueError("empty public graph")
        graphs.append(graph)
    started=time.monotonic()
    report={"policy":POLICY,"inputs":bound,"toolSha256":digest(args.checker.read_bytes()),"runs":[]}
    with tempfile.TemporaryDirectory(prefix="artifact-only-") as tmp:
        work=Path(tmp);roots=[work/"old",work/"new"]
        for g,root in zip(graphs,roots):extract(g[0],root)
        b,br=binary(graphs[0][0]);a,ar=binary(graphs[1][0])
        choices=candidates(b,a,(br,ar))
        shortlist=tiered(choices,POLICY["impactCandidates"])
        claims=[{"id":c["id"],"target":c["owner"]+"#"+c["method"]+"("+", ".join(c["params"])+")"} for c in shortlist]
        save(work/"impact.json",claims)
        env=dict(os.environ,JAVA_HOME=str(args.jdk),JVMCONTRACT_JAR_RELEASE="21",PATH=str(args.jdk/"bin")+os.pathsep+os.environ["PATH"])
        cmd=[args.checker,"impact","--before",roots[0],"--after",roots[1],"--claims",work/"impact.json","--json"]
        deps_old=[item["sha256"] for item in bound["old"][1:]]
        deps_new=[item["sha256"] for item in bound["new"][1:]]
        if deps_old and deps_old==deps_new:
            cmd+=["--classpath",os.pathsep.join(map(str,graphs[0][1:]))]
        code,data=run(cmd,work,POLICY["impactSeconds"],out/"impact.json",env)
        try: impacted={r["id"]:r["status"] for r in json.loads(data)["claims"]} if code==0 else {}
        except (ValueError,KeyError,TypeError):impacted={}
        for c in shortlist:c["impact"]=impacted.get(c["id"],"unresolved")
        shortlist.sort(key=lambda c:(not c["buildable"],c["impact"]!="invalidated",*c["rank"]))
        selected=tiered(shortlist,POLICY["attempts"])
        report.update(commonCandidates=len(choices),changedByteCandidates=sum(c["codeBytesDiffer"] for c in choices),
                      impactExit=code,selected=selected,impactCommand=list(map(str,cmd)))
        save(out/"selection.json",report)
        if not args.discover_only:
            helpers=work/"helpers";helpers.mkdir()
            compile_cmd=[args.jdk/"bin/javac","-proc:none","-d",helpers,HERE/"ArtifactProbe.java"]
            code,_=run(compile_cmd,work,40,out/"helper.out",env)
            if code:raise ValueError("physical probe did not compile")
            for i,c in enumerate(selected):
                r=exercise(c,graphs,roots,work/f"case{i}",out/f"case{i}",args.checker,args.jdk,env)
                report["runs"].append(r);save(out/"report.json",report)
            # All cold candidates have completed. Repeat their already-bound invocations with the same caches.
            warm=[]
            for i,r in enumerate(report["runs"]):
                if r.get("status")!="measured":continue
                code,data=run(r["argv"],work/f"case{i}",150,out/f"case{i}/warm.json",env)
                decoded=wire.decode(data.decode(errors="replace"),"equivalence")
                verdict=decoded.outcomes[0].get("verdict") if decoded.ok and len(decoded.outcomes)==1 else None
                warm.append({"candidate":r["candidate"]["id"],"exit":code,"verdict":verdict,"sameVerdict":r["verdict"]==verdict})
            save(out/"warm.json",warm)
    report["seconds"]=time.monotonic()-started
    save(out/"report.json",report)


if __name__=="__main__":main()
