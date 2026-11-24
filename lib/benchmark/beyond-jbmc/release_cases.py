"""Compare released public callers, retaining exact checker output and JVM replays."""
import argparse
import gzip
import json
import os
from pathlib import Path
import zipfile

from history import scratch, HERE, ROOT, OUTPUT, JBMC, MODELS, benchmark, digest, encoded
from stock_history import classpath, stock_run
from campaign import JDK, compile_java, javaenv, jvm_controls, replay_witness
from subjects import Claim, Subject
from wire_campaign import CACHE
from disclosed_cases import CASES, COMPANIONS, COMPILE_GRAPH

VEC = "vecmath-1.5.2"
MATH = "commons-math3-3.6.1"
GUAVA = "guava-33.4.8-jre"
GRAPHS = json.loads((HERE / "released-graphs.json").read_bytes())
TIE = ("0x1p-75f","0x1p-75f")
NORMAL = ("1.5f", "2.5f")
SUBJECTS = {
    **CASES,
    "N01-N02": ("numeric", Subject(0, "Product", VEC, (
        Claim("range", "float x, float y", holds=(NORMAL, ("0x1.fffffep0f","0x1.fffffep1f"))),
        Claim("underflow", "float x, float y", holds=(TIE, ("0x1.4p-75f","0x1.8p-75f"))),
        Claim("positive", "float x, float y", holds=(("0x1.8p-75f","0x1.8p-75f"),), fails=(TIE,)),
        Claim("unrounded", "float x, float y", holds=(NORMAL,), fails=(("0x1.000002p0f","0x1.000002p1f"),)),
    ))),
    "N10": ("numeric", Subject(0, "DoubleProduct", MATH, (
        Claim("underflow", "double x, double y", holds=(("0x1p-538","0x1p-537"),("0x1.8p-538","0x1.8p-537"))),))),
    "W02-transfer": ("wire-transfer", Subject(0, "FarmFrame", GUAVA, (
        Claim("littleEndian", "long word", holds=(("0L",),("-1L",),("0x123456789abcdef0L",))),
        Claim("flipped", "long word", holds=(("0L",),), fails=(("0x123456789abcdef0L",),)),))),
    "W02-controls": ("wire-transfer", Subject(0, "ViewChecks", GUAVA, (
        Claim("signed", "short value", holds=(("(short)-1",),("(short)0x1234",))),
        Claim("bounds", "int offset, long value", holds=(("0","1L"),("1","2L"),("Integer.MAX_VALUE","3L"))),
        Claim("atomic", holds=(("0L",),), parameters="long value"),
        Claim("opaqueIdentity", holds=(), fails=((),)),))),
}


def jars_for(graph):
    if graph == "jdk":
        return []
    paths = (CACHE / graph / "classpath.txt").read_text().strip().split(os.pathsep)
    jars = [Path(p) for p in paths]
    if [{"file": p.name, "sha256": digest(p)} for p in jars] != GRAPHS[graph]:
        raise ValueError("published classpath or order differs from pin: " + graph)
    return jars


def run(key, phase, out, physical_only):
    directory, subject = SUBJECTS[key]
    jars = jars_for(subject.graph)
    env = javaenv()
    os.environ.update({k:env[k] for k in ("JAVA_HOME","PATH","JVMCONTRACT_JAR_RELEASE")})
    checker = str(Path(os.environ.get("JVMCONTRACT", ROOT/"lib/target/release/jvmcontract")).resolve())
    if digest(JDK/"lib/modules") != "a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c":
        raise ValueError("subject JDK differs")
    with scratch(prefix="released-java-") as tmp:
        work = Path(tmp)
        classes = work / "claims"
        # The controls also call the Guava public transfer.
        sources = [HERE / directory / (subject.owner+".java")]
        sources += [HERE / directory / (name + ".java") for name in COMPANIONS.get(subject.owner, [])]
        compiler_jars = jars_for(COMPILE_GRAPH.get((subject.owner,subject.graph),subject.graph))
        compile_java(sources, classes, compiler_jars, env)
        cp = [classes, *jars]
        record = {"subject": subject.owner, "classpath": [str(p) for p in jars], "jarsSha256": {p.name: digest(p) for p in jars}, "compileClasspath": list(map(str, compiler_jars)),
                  "subjectSha256": digest(classes/(subject.owner+".class")), "jdkModulesSha256": digest(JDK/"lib/modules"),
                  "jvmcontractSha256": digest(Path(checker)), "jbmcSha256": digest(JBMC), "coreModelsSha256": digest(MODELS),
                  "jvm": jvm_controls(subject, work, cp, env), "rows": [], "phase": phase,
                  "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"), "job": os.environ.get("VERIFY_JOB_ID")}
        measure_subject(key, subject, phase, work, env, cp, record, out, physical_only)


def measure_subject(key, subject, phase, work, env, cp, record, out, physical_only, original_cp=None):
    classes, jars = cp[0], cp[1:]
    checker = str(Path(os.environ.get("JVMCONTRACT", ROOT/"lib/target/release/jvmcontract")).resolve())
    if original_cp is None:
        original_cp = cp
    methods = []
    for c in subject.claims:
        names = ", ".join(p.split()[-1] for p in c.parameters.split(",") if p)
        seed = (c.holds or c.fails)[0]
        methods += [f"public static void {c.method}({c.parameters}) throws Exception {{ assert {subject.owner}.{c.method}({names}); }}",
                    f"public static void {c.method}Reach() throws Exception {{ {subject.owner}.{c.method}({', '.join(seed)}); assert false; }}"]
    adapter = work / "ReleasedAssertions.java"
    adapter.write_text("public final class ReleasedAssertions {\n" + "\n".join(methods) + "\n}\n")
    stock = work / "stock"
    compile_java([adapter], stock, cp, env)
    print(key, record["jvm"]["stdout"], flush=True)
    if physical_only: return
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out / "executions.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(adapter, adapter.name)
        for c in subject.claims:
            params = [tuple(p.strip().split()) for p in c.parameters.split(",") if p]
            name = c.method
            row = {"method": name, "expected": "violation" if c.fails else "verified"}
            for engine in ("native","jbmc"):
                folder = work / (name + "-" + engine)
                folder.mkdir()
                cmd = [checker, "prove", subject.owner+"#"+name, "--classes", str(classes), "--classpath", classpath(jars),
                       "--engine", engine, "--gaps", "strict", "--assert", "result", "--timeout", "120", "--unwind",str(subject.unwind),
                       "--max-array-length",str(subject.bound),"--jbmc",str(JBMC),"--jbmc-staging","staged","--json","--work",str(folder/"proof")]
                m = benchmark.measure(cmd, 240)
                outcome = benchmark.outcome_of({"kind":"property"}, m["stdout"])
                result = benchmark.classify({"kind":"property","expected":row["expected"]}, outcome, m)
                for field in ("seconds","cpuSeconds","peakMB","exit","killed"): result[field] = m[field]
                if outcome and result["verdict"] == "violation":
                    result["jvmReplay"] = replay_witness(subject,c,outcome,folder,original_cp,env)
                archive.writestr(name+"/"+engine+"/argv.json", encoded(cmd))
                for stream in ("stdout","stderr"): archive.writestr(name+"/"+engine+"/"+stream, m[stream])
                row[engine] = result
            stock_cp = [stock,*cp]
            target = stock_run("ReleasedAssertions", name, stock_cp, params, archive, name+"/stock/target", bound=subject.bound, unwind=subject.unwind)
            if "arguments" in target:
                values = [{"value":v} for v in target["arguments"]]
                target["jvmReplay"] = replay_witness(subject,c,{"counterexample":{"inputs":values}},work,original_cp,env)
            reach = stock_run("ReleasedAssertions", name+"Reach", stock_cp, [], archive, name+"/stock/reach", bound=subject.bound, unwind=subject.unwind)
            row["stock"] = {"target":target,"reach":reach}
            record["rows"].append(row)
            print(key, name, row["native"]["verdict"], row["jbmc"]["verdict"], target["status"], reach["status"], flush=True)
    record["executionsSha256"] = digest(out/"executions.zip")
    (out/"results.json.gz").write_bytes(gzip.compress(encoded(record),mtime=0))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase",choices=("opening","qualified","closing"))
    p.add_argument("subjects",nargs="+",choices=SUBJECTS)
    p.add_argument("--physical-only",action="store_true")
    p.add_argument("--output", type=Path, help="directory containing one result directory per subject")
    args=p.parse_args()
    for key in args.subjects: run(key,args.phase,(args.output or OUTPUT/args.phase)/key,args.physical_only)
