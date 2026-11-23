"""Check which original classes each JVM actually loaded; replay standalone default and heap traces."""
import argparse
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlparse

from campaign import CACHE, CLAIMS, GRAPHS, JDK, ROOT, compile_java, digest, java_source, javaenv, jvm_controls, write
from scorecard import BASE, collected, read, require

sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import class_binding

PUBLIC = {
    "numbers": ["org.apache.commons.lang3.math.Fraction","org.apache.commons.lang3.mutable.MutableDouble"],
    "store-iterator":["org.apache.commons.collections4.iterators.ObjectArrayListIterator"],
    "endian":["org.apache.commons.io.EndianUtils"],"surrogates":["org.apache.commons.text.translate.UnicodeUnpairedSurrogateRemover"],
    "construction":["org.apache.commons.lang3.text.StrBuilder"],"nibble":["org.apache.commons.lang3.Conversion"],
    "deque":["org.apache.commons.collections4.iterators.FilterIterator","org.apache.commons.collections4.iterators.SingletonIterator"],
    "locals":["org.springframework.core.NamedThreadLocal"],
    **{f"guava-{side}":["com.google.common.base.Strings"] for side in ("parent","fix")},
    **{f"gson-{side}":["com.google.gson.Gson"] for side in ("parent","fix")},
}


def checker(report):
    job=report["job"]
    p=ROOT/"verification/results"/job[:4]/job[4:6]/job[6:8]/job/"result.json"
    receipt=read(p)
    require(receipt["jvmcontract"]["libTree"]==report["libTree"] and receipt["sourceCommit"]==report["source"],
            job+" different checker tree or source")
    exe=Path(os.environ.get("SEMANTICS_BINDING_CHECKER",receipt["jvmcontract"]["path"]))
    require(digest(exe)==report["checkerSha256"],job+" binding requires the measured checker bytes")
    return exe


def origins(key,phase,work,helper):
    subject=CLAIMS[key]
    path=BASE/phase/key/"measurement.json"
    record=read(path);collected(path,record["job"],record["source"])
    exe=checker(record)
    source,=(ROOT/"examples").glob(f"{subject.example}-*/adapter/**/{subject.owner}.java")
    jars=[CACHE/r["path"] for r in GRAPHS[subject.graph]]
    require(all(digest(j)==r["sha256"] for j,r in zip(jars,GRAPHS[subject.graph])),key+" changed original JAR")
    classes=work/"classes";env=javaenv()
    compile_java([source],classes,jars,env)
    require({p.name:digest(p) for p in classes.glob("*.class")}==record["classes"],key+" changed caller classfile")
    cp=[classes,*jars]
    measured=jvm_controls(subject,work,cp,env)
    require(measured==record["originalJvm"],key+" different original observations")
    trace=work/"loaded.log"
    run=subprocess.run([JDK/"bin/java","-ea","-Xlog:class+load=info:file="+str(trace)+":none","-cp",
                        os.pathsep.join(map(str,[work/"original",*cp])),"OriginalChecks"],capture_output=True,env=env,check=True,text=True)
    require(run.stdout.strip()==measured["stdout"],"class tracing changed the controls")
    names={}
    for line in trace.read_text().splitlines():
        if " source: file:" not in line: continue
        name,uri=line.split(" source: ",1)
        if "/" in name: continue  # hidden generated classes have no classfile entry on the classpath
        provider=Path(unquote(urlparse(uri).path)).resolve()
        if provider in cp:
            require(name not in names or names[name]==provider,key+" loaded the same name from two providers")
            names[name]=provider
    require(set([subject.owner,*PUBLIC.get(key,[])])<=names.keys(),key+" did not enter its public classes")
    classes_used=sorted(names)
    jvm=subprocess.run([JDK/"bin/java","-cp",os.pathsep.join(map(str,[helper,*cp])),"LoadedClasses",work,*classes_used],
                       capture_output=True,text=True,env=env,check=True)
    observed={name:((work/provider).resolve(),sha) for name,provider,sha in (l.split("\t") for l in jvm.stdout.splitlines())}
    require(observed.keys()==names.keys(),"incomplete JVM binding")
    answer,release=class_binding.ask(exe,env,work,{"original":{"classpath":list(map(str,cp)),
                                "classes":[{"class":name} for name in classes_used]}})
    require(release==21,"wrong multi-release JAR selection")
    bound={}
    for name,selected in zip(classes_used,answer["original"]["bindings"],strict=True):
        expected,sha=observed[name]
        require(expected==names[name] and not class_binding.disagreement(name,selected,str(expected),sha),
                f"{key}: class provider or bytes disagree for {name}")
        bound[name]={"provider":cp.index(expected),"entry":selected["entry"],"sha256":sha}
    return {"source":record["source"],"checkerSha256":record["checkerSha256"],"jdkSha256":record["modulesSha256"],
            "classpath":record["classpath"],"jvmChecks":measured["checks"],"classes":bound}


def array_witnesses(work):
    key="arrays"
    path=BASE/"standalone"/key/"preflight-packaged/measurement.json"
    d=read(path);source,=(ROOT/"examples").glob("379-*/adapter/**/ReferenceCells.java")
    classes=work/"classes";compile_java([source],classes,[],javaenv())
    result={}
    for r in d["runs"]:
        method=r["method"]
        if method not in ("noNullCell","noItemCell"): continue
        f=path.parent/r["target"]["raw"];collected(f,d["job"])
        target,=[v for msg in json.loads(gzip.decompress(f.read_bytes())) for v in msg.get("result",[])
                 if v["property"]==r["target"]["target"]["property"] and v["status"]=="FAILURE"]
        assignments={}
        for step in target["trace"]:
            if step.get("stepType")=="input" and step["inputID"]=="values":
                root=step["values"][0]["data"];break
            if step.get("stepType")=="assignment": assignments[step["lhs"]]=step["value"]
        else: raise ValueError("missing reference-array root in trace")
        length=int(assignments[root+".length"]["data"]);backing=assignments[root+".data"]["data"]
        require(0<length<=2,"trace outside the array bound")
        cells=[assignments[f"{backing}[{i}L]"]["data"] for i in range(length)]
        ids=list(dict.fromkeys(v for v in cells if v!="null"))
        values=[int(assignments[v+".value"]["data"]) for v in ids]
        body=[f"ReferenceCells.Item i{i}=new ReferenceCells.Item(); i{i}.value={v};" for i,v in enumerate(values)]
        refs=["null" if v=="null" else f"i{ids.index(v)}" for v in cells]
        body.append(f"if (ReferenceCells.{method}(new ReferenceCells.Item[]{{{','.join(refs)}}})) throw new AssertionError();")
        j=java_source(work/"OriginalHeap.java","class OriginalHeap { public static void main(String[] args) {"
                      +"\n".join(body)+'System.out.println("refuted");}}')
        driver=work/"witness"
        compile_java([j],driver,[classes],javaenv())
        replay=subprocess.run([JDK/"bin/java","-ea","-cp",os.pathsep.join(map(str,[driver,classes])),"OriginalHeap"],
                              capture_output=True,text=True,env=javaenv(),check=True)
        require(replay.stdout.strip()=="refuted","standalone heap witness held on the original JVM")
        result[method]={"target":target["property"],"rawSha256":digest(f),"length":length,"cells":refs,
                        "itemValues":values,"sourceSha256":digest(j),"jvm":"refuted"}
    return result


def default_witnesses(work):
    p=BASE/"seed-profiles/measurement.json";seed=read(p);collected(p,seed["job"])
    text=(ROOT/"llm-dlc/loops/jbmc-java-semantics-gap-brief.md").read_text()
    _,extra=[s+"\n" for s in re.findall(r"^```java\n(.*?)\n```$",text,re.M|re.S)]
    jar=CACHE/GRAPHS["io"][0]["path"]
    result=[]
    for layout in ("separate","combined"):
        root=work/layout;root.mkdir();v=seed["variants"][layout]
        src=java_source(root/"ExtraOpeners.java",extra.rstrip("\n") if layout=="separate" else
                        extra.replace("\n}\n\nclass ExtraOpenersReplay extends ExtraOpeners {","").rstrip("\n"))
        require(digest(src)==v["sourceSha256"],"different default layout")
        subprocess.run([JDK/"bin/javac","-source","8","-target","8","-Xlint:-options","-g","-proc:none","-cp",jar,"-d",root,src],check=True)
        require({f.name:digest(f) for f in root.glob("*.class")}==v["classes"],"different default-dispatch bytecode")
        cp=os.pathsep.join(map(str,[root,jar]))
        for r in v["runs"]:
            if r["status"]!="FAILURE":continue
            vals={}
            for k,w in r["inputs"].items():
                b=w["binary"];require(len(b)==32,"unexpected default argument width")
                vals[k]=int(b,2)-(1<<32 if b[0]=="1" else 0)
            args=[vals[k] for k in (("k","x") if r["entry"]=="dispatch" else ("x",))]
            call=f"ExtraOpeners.{r['entry']}({','.join(map(str,args))});"
            java=java_source(root/"ReplayDefault.java",'class ReplayDefault {public static void main(String[] a) {try {'+
                             call+'System.out.println("held");} catch (AssertionError e) {System.out.println("refuted");}}}')
            replay=subprocess.run([JDK/"bin/java","-ea","-cp",cp,java],check=True,capture_output=True,text=True)
            expected="held" if r["entry"]=="dispatch" else "refuted"
            require(replay.stdout.strip()==expected,"different original default outcome")
            result.append({"layout":layout,"binary":r["binary"],"models":r["models"],"entry":r["entry"],"inputs":vals,
                           "target":r["target"]["property"],"jvm":expected,"rawSha256":r["sha256"]})
    return result


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--phase",choices=("opening","final","qualified"),default="qualified")
    cli.add_argument("--output",type=Path,default=BASE/"origins.json")
    cli.add_argument("--check",action="store_true")
    a=cli.parse_args()
    with tempfile.TemporaryDirectory(prefix="semantics-origins-") as tmp:
        work=Path(tmp);helper=work/"observer";helper.mkdir()
        subprocess.run([JDK/"bin/javac","-d",helper,ROOT/"examples/tools/targets/java/LoadedClasses.java"],check=True)
        rows={}
        for key in CLAIMS:
            stage=work/key;stage.mkdir();rows[key]=origins(key,a.phase,stage,helper)
        heaps=work/"heap-witnesses";heaps.mkdir()
        defaults=work/"defaults";defaults.mkdir()
        result={"graphs":rows,"arrayWitnesses":array_witnesses(heaps),"defaultWitnesses":default_witnesses(defaults)}
        if a.check: require(read(a.output)==result,"original class bindings or JVM witnesses changed")
        else: write(a.output,result)
        print(len(rows),"graphs;",sum(len(r["classes"]) for r in rows.values()),"original class bindings")
