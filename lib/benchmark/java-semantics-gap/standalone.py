"""Run exception-aware Java assertions outside the integrated frontend and retain every property."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile

from campaign import (CACHE, CLAIMS, GRAPHS, HERE, JDK, ROOT, command, compile_java, digest, javaenv,
                      java_source, jvm_controls, replay_witness, write)
from subjects import Claim, Subject

DEQUE = ["java/util/" + n for n in ("ArrayDeque","ArrayDeque$DeqIterator","AbstractCollection","Deque","Queue",
                                     "Collection","Iterator")] + ["java/util/Objects"]
LISTS = ["java/util/" + n for n in ("List","ImmutableCollections","ImmutableCollections$List12","ImmutableCollections$ListN",
                                    "ImmutableCollections$ListItr","ImmutableCollections$AbstractImmutableList")]


def layer(work, profile):
    dest = work/"layer"
    layers = {}
    if profile == "six-lists":
        names, base = LISTS, ROOT/"lib/models/classes"
    elif profile == "eight-deque":
        names, base = DEQUE, CACHE/"jdk/temurin-21.0.13/classes"
    elif profile == "repo-enum":
        names, base = ["java/lang/Enum"], ROOT/"lib/models/classes"
    else:
        return [], {}
    for name in names:
        p = dest/(name+".class")
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base/(name+".class"),p)
        layers[name] = digest(p)
    return [dest], layers


def decode(out, err, code, method):
    if code == 124: return {"status":"timeout"}
    try:
        doc = json.loads(out)
    except (ValueError, UnicodeDecodeError):
        return {"status":"no property report","diagnostic":err.decode(errors="replace")[-1200:]}
    props = [r for part in doc for r in part.get("result",[])]
    def target(p):
        return (p.get("sourceLocation",{}).get("propertyClass") == "assertion"
                and p.get("property","").startswith(f"java::GapAssertions.{method}:"))
    matches = [p for p in props if target(p)]
    others = [p for p in props if not target(p) and p.get("status") != "SUCCESS"]
    def brief(p):
        return {k:p.get(k) for k in ("property","description","status","sourceLocation")}
    warnings = [m["messageText"] for m in doc if m.get("messageType") in ("WARNING","ERROR") and "messageText" in m]
    verdict = doc[-1].get("cProverStatus") if doc else None
    valid = (code,verdict) in ((0,"success"),(10,"failure")) and len(matches)==1
    summary = {"status":matches[0]["status"] if valid else "incomplete property report", "exit":code,
               "target":brief(matches[0]) if len(matches)==1 else None,"totalProperties":len(props),
               "otherFailures":[brief(p) for p in others], "warnings":warnings}
    if len(matches)==1:
        summary["inputs"] = {s["inputID"]:s["values"][0] for s in matches[0].get("trace",[])
                             if s.get("stepType")=="input" and len(s.get("values",[]))==1
                             and s.get("sourceLocation",{}).get("function","").startswith(f"java::GapAssertions.{method}:")}
    return summary


def wrapper(claim, subject):
    params = [p.strip().split() for p in claim.parameters.split(",") if p.strip()]
    args = ", ".join(name for _,name in params)
    guard = [claim.guard] if claim.guard else []
    for typ,name in params:
        if typ == "String" or typ.endswith("[]"):
            nullable = name == claim.nullable
            if not nullable: guard.append(f"{name} != null")
            length = "length()" if typ == "String" else "length"
            guard.append(f"({name} == null || {name}.{length} <= {subject.bound})")
    domain = "if (!(" + " && ".join(f"({g})" for g in guard) + ")) return;" if guard else ""
    # An unexpected exception violates the caller's assertion. Keep property and reach in distinct entries.
    call = f"{subject.owner}.{claim.method}({args})"
    return ("public final class GapAssertions {\n"
            + f"public static void target({claim.parameters}) {{ {domain} boolean ok; "
              f"try {{ ok = {call}; }} catch (Throwable unexpected) {{ ok = false; }} assert ok; }}\n"
            + f"public static void reached({claim.parameters}) {{ {domain} "
              f"try {{ {call}; }} catch (Throwable unexpected) {{}} assert false; }}\n}}")


def historical_lists(work, env):
    classes = work/"registered"
    conformance = ROOT/"lib/tests/conformance/conformance/Conformance.java"
    # This corpus uses modern Java syntax. The exact list method bytecode is shared across the four assertions.
    import subprocess
    subprocess.run([JDK/"bin/javac","-parameters","-g","-proc:none","-d",classes,conformance],env=env,check=True)
    src = java_source(work/"RegisteredLists.java", """
import conformance.Conformance;
public final class RegisteredLists {
    static boolean array(int n) { try { return Conformance.listOfArray(n) == 111; } catch (RuntimeException e) { return false; } }
    public static boolean guardedArray(int n) { return array(n); }
    public static boolean allArrays(int n) { return array(n); }
    public static boolean guardedSearch(int n) { try { return Conformance.listSearch(n) == 90; } catch (RuntimeException e) { return false; } }
    public static boolean allSearch(int n) { try { return Conformance.listSearch(n) < 0; } catch (RuntimeException e) { return false; } }
}""")
    return Subject(376,"RegisteredLists","jdk",(
        Claim("guardedArray","int n","n != 9",(("0",),)),Claim("allArrays","int n",holds=(("0",),),fails=(("9",),)),
        Claim("guardedSearch","int n","n == 5",(("5",),)),Claim("allSearch","int n",holds=(("2",),),fails=(("5",),)))),src,[classes]


def measure(key, profile, pairing, outdir, only=None):
    env = javaenv()
    prefix = CACHE/"releases/cbmc-6.11.0/ubuntu-22.04"
    binary, core = (Path("/usr/bin/jbmc"),Path("/usr/lib/core-models.jar")) if pairing=="installed" else (prefix/"bin/jbmc",prefix/"lib/core-models.jar")
    dest = outdir/key/(pairing+"-"+profile)
    dest.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semantics-jbmc-") as tmp:
        work = Path(tmp)
        if key == "registered-lists":
            subject, source, jars = historical_lists(work,env)
        else:
            subject = CLAIMS[key]
            source, = (ROOT/"examples").glob(f"{subject.example}-*/adapter/**/{subject.owner}.java")
            jars = [CACHE/r["path"] for r in GRAPHS[subject.graph]]
            if any(digest(j)!=r["sha256"] for j,r in zip(jars,GRAPHS[subject.graph])):
                raise ValueError("historical JAR mismatch")
        classes = work/"classes"
        compile_java([source],classes,jars,env)
        real_cp = [classes,*jars]
        extra, model_hashes = layer(work,profile)
        report = {"key":key,"profile":profile,"binarySha256":digest(binary),"coreModelsSha256":digest(core),
                  "classpath":["assertions","caller",*[j.name for j in jars],*(["selected models"] if extra else []),"core-models.jar"],
                  "classes":{p.relative_to(d).as_posix():digest(p) for d in real_cp if d.is_dir() for p in d.rglob("*.class")},
                  "jars":{j.name:digest(j) for j in jars if j.is_file()}, "selectedModels":model_hashes,
                  "originalJvm":jvm_controls(subject,work,real_cp,env), "job":os.environ.get("VERIFY_JOB_ID"), "runs":[]}
        for claim in subject.claims:
            if only and claim.method not in only: continue
            scratch = work/claim.method
            scratch.mkdir()
            src = java_source(scratch/"GapAssertions.java",wrapper(claim,subject))
            wrapper_dir = scratch/"assertions"
            compile_java([src],wrapper_dir,real_cp,env)
            cp = os.pathsep.join(map(str,[wrapper_dir,*real_cp,*extra,core]))
            flags = ["--unwind",str(subject.unwind),"--unwinding-assertions","--throw-runtime-exceptions",
                     "--max-nondet-array-length",str(subject.bound),"--max-nondet-tree-depth","4",
                     "--max-nondet-string-length",str(subject.bound),"--sat-solver","cadical","--trace","--json-ui"]
            if profile in ("ordinary","eight-deque") or key=="surrogates": flags += ["--no-refine-strings"]
            if key=="monitors": flags += ["--java-threading"]
            row = {"method":claim.method,"flags":flags,"wrapperSha256":digest(wrapper_dir/"GapAssertions.class")}
            for method in ("target","reached"):
                code, out, err, secs = command([binary,"GapAssertions","-cp",cp,"--function","GapAssertions."+method,*flags],env)
                data = decode(out,err,code,method)
                name = f"{claim.method}-{method}.json.gz"
                (dest/name).write_bytes(gzip.compress(out,mtime=0))
                if err: (dest/(name+".stderr")).write_bytes(err)
                row[method] = dict(data,seconds=secs,raw=name,sha256=digest(dest/name))
            result = row["target"]
            if result["status"] == "FAILURE":
                args = []
                for param in claim.parameters.split(",") if claim.parameters else ():
                    typ,name = param.strip().split()
                    v = result["inputs"].get(name,{})
                    if typ=="boolean" and v.get("data") in ("true","false"): value = v["data"]=="true"
                    elif typ in ("int","long","char") and v.get("binary"):
                        bits=v["binary"]; value=int(bits,2)
                        if typ!="char" and bits[0]=="1": value-=1<<len(bits)
                    else: break
                    args.append({"type":typ,"value":value})
                params = claim.parameters.split(",") if claim.parameters else []
                if len(args)==len(params) and claim.method!="mixed":
                    result["jvmReplay"]=replay_witness(subject,claim,{"counterexample":{"inputs":args}},scratch,real_cp,env)
            report["runs"].append(row)
            print(key,profile,claim.method,result["status"],row["reached"]["status"],flush=True)
        write(dest/"measurement.json",report)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("profile",choices=("packaged","ordinary","six-lists","eight-deque","repo-enum"))
    p.add_argument("subjects",nargs="+",choices=[*CLAIMS,"registered-lists"])
    p.add_argument("--pairing",choices=("installed","preflight"),default="preflight")
    p.add_argument("--only",nargs="+")
    p.add_argument("--output",type=Path,default=ROOT/"verification/java-semantics-gap/standalone")
    a=p.parse_args()
    for s in a.subjects: measure(s,a.profile,a.pairing,a.output.resolve(),a.only)
