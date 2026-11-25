"""Additional released wire cases. Qualify the symbolic pair against isolated, unmodified original JARs."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

from history import HERE, ROOT, OUTPUT, JBMC, MODELS, digest, encoded, scratch
from stock_history import RELOCATOR, classpath
from wire_campaign import VERSIONS, runtime_jar
from release_cases import JDK, javaenv, compile_java, jvm_controls, measure_subject, jars_for, Claim, Subject

SHORTS=(("(short)0",),("(short)0x80ff",),("Short.MIN_VALUE",))
LONGS=(("0L",),("-1L",),("0x01020304050607ffL",),("Long.MIN_VALUE",))
INTS=tuple((str(i),) for i in (0,127,128,16383,16384,-1,-2147483648))
RECORDS=(("0x01020304","0x04030201"),("0x12212112","-1"),("0","128"))
GROUPS = {
    "W03": tuple(Claim(m,t+" v",holds=seeds) for m,t,seeds in
                 ((m,t,s) for t,s in (("short",SHORTS),("long",LONGS)) for m in (t+"OldNew",t+"NewOld"))),
    "W05": (Claim("protoToLucene","int n",holds=INTS),
            Claim("swappedEntrypoint","int n",holds=(("127",),),fails=(("-1",),))),
    "W06": (Claim("size32","int n",holds=INTS), Claim("size64","long n",holds=LONGS)),
    "W07": tuple(Claim(m+s,t+" n",holds=seeds) for m,t,seeds in
                 (("uint32","int",INTS),("uint64","long",LONGS),("sint64","long",LONGS)) for s in ("OldNew","NewOld")),
    "W08": tuple(Claim("record"+s,"int header, int payload",holds=RECORDS) for s in ("OldNew","NewOld")),
}


def bridges(work, sources):
    result = []
    for side, prefix in enumerate(("before","current")):
        folder=work/"bridge-source"/prefix
        folder.mkdir(parents=True)
        for src in sources:
            owner=src.stem
            code = ["package before;" if side==0 else "", f"public final class {owner} {{"]
            signature=r'public static ([\w\[\]]+) (\w+)\(([^()]*)\)(?: throws ((?:java\.io\.)?IOException|Exception))?\s*\{'
            for ret, method, params, throws in re.findall(signature,src.read_text()):
                pair=[p.strip().split() for p in params.split(",") if p.strip()]
                types=", ".join(t+".class" for t,_ in pair)
                args="".join(", "+n for _,n in pair)
                boxed={"long":"Long","int":"Integer"}.get(ret,ret)
                declared = " throws " + ("Exception" if throws == "Exception" else "java.io.IOException") if throws else ""
                observe = "" if ret == "void" else f"return ({boxed})"
                code += [f'    public static {ret} {method}({params}){declared} {{',
                         f'        {observe}witness.OriginalGraph.call({side}, "{owner}", "{method}", new Class<?>[]{{{types}}}{args});','    }']
            if len(code)==2: raise ValueError("no bridged methods in " + owner)
            f=folder/src.name
            f.write_text("\n".join([*code,"}"])+"\n")
            result.append(f)
    return result


def prepare_pair(work, sources, old, new, claims, *, ordered=False):
    env=javaenv()
    os.environ.update({k:env[k] for k in ("JAVA_HOME","PATH","JVMCONTRACT_JAR_RELEASE")})
    caller=work/"caller"
    compile_java(sources,caller,old,env)
    raw=work/"old-input"
    shutil.copytree(caller,raw)
    entry_map={}
    shadowed=[]
    for jar in old:
        with zipfile.ZipFile(jar) as z:
            for logical,item in runtime_jar.effective_entries(z,21).items():
                if not logical.endswith(".class") or logical=="module-info.class" or logical.startswith("META-INF/"): continue
                f=raw/logical
                if f.exists():
                    if not ordered or logical not in entry_map:raise ValueError("ambiguous old class " + logical)
                    shadowed.append([logical,jar.name,item.filename])
                    continue
                f.parent.mkdir(parents=True,exist_ok=True)
                f.write_bytes(z.read(item))
                entry_map[logical]=[jar.name,item.filename]
    tools,previous=work/"tools",work/"old"
    tools.mkdir()
    subprocess.run([JDK/"bin/javac","-d",tools,RELOCATOR,HERE/"java/PairClasses.java"],check=True,env=env)
    subprocess.run([JDK/"bin/java","-cp",tools,"net.terminalvalue.contracts.PairClasses",raw,previous],check=True,env=env)
    classes=work/"claims"
    cp=[classes,caller,previous,*new]
    compile_java(claims,classes,cp[1:],env)
    original=work/"original"
    compile_java([*bridges(work,sources),HERE/"wire-more/OriginalGraph.java",*claims],original,[],env)
    env.update(WIRE_ORIGINAL_BEFORE=classpath([caller,*old]),WIRE_ORIGINAL_AFTER=classpath([caller,*new]))
    return cp,[original],env,{"old":{p.name:digest(p) for p in old},"new":{p.name:digest(p) for p in new},
                            "thinCallers":{p.name:digest(p) for p in caller.glob("*.class")},"symbolicClaimClasses":{p.name:digest(p) for p in classes.glob("*.class")},
                            "oldEntryMapSha256":hashlib.sha256(encoded(entry_map)).hexdigest(),"shadowedOldClasses":shadowed,
                            "relocatorSha256":digest(RELOCATOR),
                            "jdkModulesSha256":digest(JDK/"lib/modules"),"jbmcSha256":digest(JBMC),"coreModelsSha256":digest(MODELS)}


def prepare(work):
    old=[*jars_for("lucene-core-"+VERSIONS[0]),*jars_for("protobuf-java-3.25.5")]
    new=[*jars_for("lucene-core-"+VERSIONS[1]),*jars_for("protobuf-java-4.33.0")]
    src=HERE/"wire-more"
    return prepare_pair(work,[HERE/"wire/WireAPI.java",src/"WireMore.java",src/"ProtoAPI.java"],old,new,[src/"MoreWireClaims.java"])


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase",choices=("qualified","closing"))
    p.add_argument("groups",nargs="+",choices=GROUPS)
    p.add_argument("--physical-only",action="store_true")
    a=p.parse_args()
    with scratch(prefix="wire-transfer-") as tmp:
        work=Path(tmp);cp,original,env,identity=prepare(work)
        for key in a.groups:
            d=work/key;d.mkdir()
            subject=Subject(0,"MoreWireClaims","two independent releases",GROUPS[key],bound=16)
            physical=jvm_controls(subject,d,original,env)
            paired=jvm_controls(subject,d,cp,env)
            if physical!=paired: raise ValueError("physical and symbolic type bindings disagree on the controls")
            record={**identity,"jvm":physical,"rows":[],"phase":a.phase,"subject":subject.owner,"job":os.environ.get("VERIFY_JOB_ID"),
                    "jvmcontractSha256":digest(Path(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract"))),
                    "sourceCommit":os.environ.get("VERIFY_SOURCE_COMMIT")}
            measure_subject(key,subject,a.phase,d,env,cp,record,OUTPUT/a.phase/key,a.physical_only,original_cp=original)
