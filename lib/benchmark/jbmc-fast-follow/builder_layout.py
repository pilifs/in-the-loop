"""Compare unchanged row operation bytecode with javac's assertion entry points in a separate class."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import tempfile

from measure import EVIDENCE, JDK, ROOT, Claim, Subject, classpath, command, compile_sources, digest, integrated, javaenv, library_paths, load, methods, write
from campaign import replay_witness


def method_blocks(listing):
    blocks = {}
    for match in re.finditer(r"^  (?:public |private |protected |static |final |[\w.$]+\().*?^    descriptor: (\([^\n]+)\n(.*?)(?=^  \S|^\})", listing, re.M | re.S):
        # Header includes the declaration, followed by descriptor: and Code:.
        declaration = match.group().splitlines()[0]
        name = declaration.split("(",1)[0].split()[-1]
        body = "\n".join(" ".join(line.split()) for line in re.sub(r"#\d+", "#", match[2]).splitlines() if line.strip())
        blocks[name,match[1]]=body
    return blocks


def prepare(work):
    folder, = (ROOT/"examples").glob("394-*")
    env=javaenv()
    jars=library_paths(folder,"rows")
    proof=folder/"adapter/RaggedProof.java"
    builder=folder/"adapter/MadeRows.java"
    original=work/"original"
    split=work/"split"
    compile_sources([proof,builder],original,jars,env)
    source=proof.read_text()
    before, marker, after=source.partition(" public static void testReverse")
    if not marker: raise ValueError("missing original assertion driver")
    generated=work/"RaggedProof.java"; generated.write_text(before+"}\n")
    compile_sources([generated,builder],split,jars,env)
    assertions=work/"RowAssertions.java"
    driver=marker+after[:after.rfind("}")]
    for name in ("choose","reversed","wrong","iter","snapshot","distinct"):
        driver=re.sub(r"\b"+name+r"\(", "RaggedProof."+name+"(", driver)
    assertions.write_text("public class RowAssertions {\n"+driver+"}\n")
    compile_sources([assertions],work/"assertions",[split,*jars],env)
    base, baseline=methods(JDK/"bin/javap",original/"RaggedProof.class")
    isolated, changed=methods(JDK/"bin/javap",split/"RaggedProof.class")
    if ("<clinit>","()V") not in base or ("<clinit>","()V") in isolated: raise ValueError("unexpected class-initializer layout")
    blocks1,blocks2=method_blocks(baseline),method_blocks(changed)
    code={}
    for name in ("reversed","wrong","iter","snapshot","distinct","choose"):
        key,=[k for k in base if k[0]==name]
        if key not in isolated or blocks1[key]!=blocks2[key] or not blocks1[key]: raise ValueError(f"changed method {name}")
        code[name+key[1]]=hashlib.sha256(blocks1[key].encode()).hexdigest()
    if digest(original/"MadeRows.class")!=digest(split/"MadeRows.class"): raise ValueError("builder class changed")
    observer=work/"LayoutChecks.java"
    observer.write_text("""class LayoutChecks {
    static void check(int i, int j, boolean shared) {
        int[][] g = RaggedJvm.graph(i,j,shared);
        boolean same = g[0] == g[1], distinct = !same || g[0] == null || g[0].length == 0;
        if (!RaggedProof.reversed(RaggedJvm.graph(i,j,shared)) || !RaggedProof.iter(RaggedJvm.graph(i,j,shared))
            || RaggedProof.wrong(RaggedJvm.graph(i,j,shared)) != same
            || RaggedProof.snapshot(RaggedJvm.graph(i,j,shared)) != same || RaggedProof.distinct(g) != distinct)
            throw new AssertionError();
    }
    public static void main(String[] args) {
        for (int i=0;i<14;i++) for (int j=0;j<14;j++) check(i,j,false);
        for (int i=1;i<14;i++) check(i,i,true);
        System.out.println("209 row graphs");
    }
}
""")
    controls=work/"jvm"
    compile_sources([observer,folder/"controls/jvm/RaggedJvm.java",folder/"controls/jvm/Ragged.java"],controls,[original,*jars],env)
    for layout in (original,split):
        for flag in ("-ea","-da"):
            status,out,err,_=command([JDK/"bin/java","-XX:-UsePerfData",flag,"-cp",classpath([controls,layout,*jars]),"LayoutChecks"],env)
            if status or out.strip()!=b"209 row graphs": raise ValueError(err.decode() or out.decode())
    report={"job":env.get("VERIFY_JOB_ID"),"source":env.get("VERIFY_SOURCE_COMMIT"),
            "checkerSha256":digest(env.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract")),
            "jars":{j.name:digest(j) for j in jars},"originalClass":digest(original/"RaggedProof.class"),
            "separatedClass":digest(split/"RaggedProof.class"),"assertionClass":digest(work/"assertions/RowAssertions.class"),
            "builderClass":digest(split/"MadeRows.class"),"instructionsAndHandlers":code,
            "originalJvm":{"graphs":209,"layouts":2,"assertionSettings":["-ea","-da"],"observerSha256":digest(observer)},"runs":{}}
    return folder,env,[original,*jars],[split,*jars],report


def main(check_only=False):
    with tempfile.TemporaryDirectory(prefix="row-layout-") as tmp:
        work=Path(tmp)
        folder,env,original,split,report=prepare(work)
        if check_only:
            print("Six unchanged instruction and handler lists, unchanged builder class, separate assertion driver")
            return
        dest=EVIDENCE/"row-layout"
        target={t["id"]:t for t in load(folder/"target.json")["tasks"]}
        for row in load(folder/"controls/comparison.json"):
            task=target[row["task"]]
            owner,method=task["target"].split("#")
            if owner not in ("RaggedProof","MadeRows"):continue
            claim=Claim(method,row["parameters"],nullable="a" if owner=="RaggedProof" else "",
                        fails=((),) if task["expected"]=="refuted" else ())
            subject=Subject(394,owner,"rows",(claim,),2,7)
            runs={}
            for engine in ("native","jbmc"):
                scratch=work/row["task"]/engine; scratch.mkdir(parents=True)
                raw=dest/row["task"]/engine;raw.mkdir(parents=True,exist_ok=True)
                actual=integrated(subject,claim,engine,scratch,raw,split,env)
                if actual["verdict"]=="violation" and actual["disposition"]=="correct":
                    replay=replay_witness(subject,claim,{"counterexample":{"inputs":actual["jvmReplay"]["inputs"]}},scratch,original,env)
                    if replay["outcome"]!="refuted": raise ValueError("original caller did not reproduce the separated-layout witness")
                    actual["originalClassReplay"]=replay
                runs[engine]=actual
            report["runs"][row["task"]]=runs
        write(dest/"measurement.json",report)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--check-layout",action="store_true")
    main(p.parse_args().check_layout)
