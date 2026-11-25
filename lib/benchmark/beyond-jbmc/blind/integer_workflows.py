"""Exercise artifact-only integer codec discovery on the successor panel and two independent released libraries."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

from successor import OUT as PANEL, SLOTS, JDK, compressed, digest, packet, read, save, scratch
from scaffold_first import HERE, JVM_FLAGS, observe
from history import ROOT
from release_cases import Claim, Subject, jars_for, javaenv, jvm_controls, measure_subject
from stock_history import classpath

OUT = PANEL.parent / "integer-codecs"
TRANSFERS = {"lucene": ("lucene-core-8.11.0", "lucene-core-9.0.0"), "protobuf": ("protobuf-java-3.25.5","protobuf-java-4.33.0")}


def distributions(case, work):
    if case == "wrong":
        graphs = {}
        for side in ("old", "new"):
            directory = work / side
            directory.mkdir()
            source = directory / "Packed.java"
            correction = " ^ 1" if side == "new" else ""
            source.write_text("package fixture; public class Packed { public static int toBits(int n) {return ((n << 1) ^ (n >> 31))"
                              + correction + ";} public static int fromBits(int n){return (n >>> 1) ^ -(n & 1);} }\n")
            subprocess.run([JDK / "bin/javac", "-J-XX:-UsePerfData", "-g", "-parameters", "-d", directory, source], check=True)
            jar = directory / "ordinary.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr(zipfile.ZipInfo("fixture/Packed.class"), (directory / "fixture/Packed.class").read_bytes())
            graphs[side] = [jar]
        return graphs
    if case in TRANSFERS:
        return {side: jars_for(version) for side,version in zip(("old","new"), TRANSFERS[case])}
    root = work / "packet"
    inputs = packet(case, root)
    return {s: [root / row["path"] for row in rows] for s,rows in inputs.items()}


def discover(case):
    with scratch(prefix="discover-original-integers-") as tmp:
        work = Path(tmp)
        graphs = distributions(case, work)
        for side,files in graphs.items():
            save(work/(side+".json"), {"classpath":[{"file":str(p),"sha256":digest(p)} for p in files]})
        dest = OUT / "discovery" / case
        subprocess.run([sys.executable,"-B", ROOT / "examples/tools/build.py", "--discover-integer-codecs",
                        "--before",work/"old.json","--after",work/"new.json","--jdk",JDK,"--output",dest],check=True)
        result = read(dest/"discovery.json")
        if case == "02" and result["inputs"] != {s: [r["sha256"] for r in g["classpath"]]
                         for s,g in compressed(PANEL/"deployments/02.json.gz").items()}:
            raise ValueError("different signed DSI deployment")


def measure(case, side):
    dest = OUT / "discovery" / case
    discovery = read(dest / "discovery.json")
    with scratch(prefix="measure-original-integers-") as tmp:
        work = Path(tmp)
        graphs = distributions(case, work)
        if discovery["inputs"] != {s:[digest(p) for p in g] for s,g in graphs.items()}:
            raise ValueError("generated caller inputs have changed")
        closed = 0
        for candidate in discovery["measuredCandidates"]:
            if candidate["firstScaffoldStop"] is not None:
                continue
            label = candidate["directory"]
            source = dest / label / "IntegerCodec.java"
            regfile = source.with_name("registration.json")
            registration, receipt = read(regfile), read(source.with_name("scaffold.json"))
            if (digest(source) != registration["callerSha256"] or digest(regfile) != receipt["registrationSha256"]
                    or registration["inputs"] != discovery["inputs"] or receipt["firstScaffoldStop"]
                    or digest(JDK / "lib/modules") != registration["jdkModulesSha256"]):
                raise ValueError("incomplete public question or original controls")
            run = work / label
            classes = run / "classes"
            classes.mkdir(parents=True)
            subprocess.run([JDK / "bin/javac", "-J-XX:-UsePerfData", "-proc:none", "-g", "-parameters", "-classpath",
                            classpath(graphs["old"]), "-d", classes, source],check=True)
            if digest(classes / "IntegerCodec.class") != receipt["callerClassSha256"]:
                raise ValueError("different consumer bytecode")
            physical = receipt["sides"][side]["rows"]
            count = len(registration["expectedSamples"])
            if physical[:count] != registration["expectedSamples"]:
                raise ValueError("original decoder or encoder disagreed")
            seeds = tuple((str(n),) for n,_,_ in physical)
            def raw_signed(n):
                x = n & 0xffffffff
                return x // 2 if x % 2 == 0 else -1 - x // 2
            false_raw = tuple((str(n),) for n,decoded,_ in physical if decoded != raw_signed(n))
            subject = Subject(0,"IntegerCodec","unmodified release",
                (Claim("primary","int n",holds=seeds),Claim("control","int n",holds=seeds),
                 Claim("inverse","int n",holds=seeds[count:],fails=seeds[:count]),
                 Claim("unsigned","int n",holds=tuple(s for s in seeds if s not in false_raw),fails=false_raw)),8,16)
            env = javaenv()
            os.environ.update(env)
            cp = [classes, *graphs[side]]
            controls = jvm_controls(subject,run,cp,env)
            record={"jvm":controls,"rows":[],"job":os.environ.get("VERIFY_JOB_ID"),"source":os.environ.get("VERIFY_SOURCE_COMMIT"),
                    "originalScaffoldSha256":digest(source.with_name("scaffold.json")),"callerSha256":receipt["callerClassSha256"],
                    "registrationSha256":digest(regfile),"orderedJars":discovery["inputs"][side],
                    "checkerSha256":digest(Path(os.environ["JVMCONTRACT"]))}
            measure_subject(case,subject,"post-disclosure",run,env,cp,record,OUT/"matched"/case/side/label,False)
            closed += 1
        if not closed:
            raise ValueError("no generated question qualified for this measurement")


def original_loaders(case):
    ref = OUT / "discovery" / case / "candidate-1"
    reg, physical = read(ref / "registration.json"), read(ref / "scaffold.json")
    with scratch(prefix="codec-original-loaders-") as tmp:
        work = Path(tmp)
        graphs = distributions(case, work)
        launcher, classes = work / "launcher", work / "caller"
        launcher.mkdir()
        classes.mkdir()
        subprocess.run([JDK / "bin/javac", "-J-XX:-UsePerfData", "-proc:none", "-d", launcher, HERE / "LoaderObservations.java"], check=True)
        wrapper = work / "ReferenceAPI.java"
        wrapper.write_text("public class ReferenceAPI { public static long primary(int n) {return IntegerCodec.decode(n);} public static long control(int n) {return IntegerCodec.roundTrip(n);} }\n")
        subprocess.run([JDK / "bin/javac", "-J-XX:-UsePerfData", "-proc:none", "-g", "-parameters", "-cp", classpath(graphs["old"]),
                        "-d", classes, ref / "IntegerCodec.java", wrapper], check=True)
        if digest(classes / "IntegerCodec.class") != physical["callerClassSha256"]:
            raise ValueError("different original consumer")
        record = {"jdkModulesSha256":digest(JDK / "lib/modules"), "flags":JVM_FLAGS, "registrationSha256":digest(ref / "registration.json"),
                  "launcherSha256":digest(HERE / "LoaderObservations.java"), "callerClassSha256":physical["callerClassSha256"], "sides":{}}
        for side, jars in graphs.items():
            expected = physical["sides"][side]["rows"]
            record["sides"][side] = {}
            for mode in ("direct", "record"):
                got = observe(work / (side + mode), launcher, classes, jars, mode, [r[0] for r in expected])
                if got["exit"] or got["rows"] != expected or (mode == "record" and
                      any(got["classProviders"].get(reg[k][0]) != 1 for k in ("encoder", "decoder"))):
                    raise ValueError("public value or defining loader disagrees")
                record["sides"][side][mode] = got
        save(OUT / "original-loaders" / (case + ".json.gz"), record)


def startup(case):
    if case != "protobuf":
        raise ValueError("the observed startup question is registered for Protobuf")
    bounds = [0, 1, 127, 128, 16383, 16384, 2**31-1, -2**31, -1, -2**63, 2**63-1]
    sources = HERE / "integer-startup"
    with scratch(prefix="protobuf-startup-registration-") as tmp:
        work = Path(tmp)
        classes = work / "classes"
        classes.mkdir()
        graphs = distributions(case, work)
        src = sources / "PublishedWidths.java"
        subprocess.run([JDK / "bin/javac", "-J-XX:-UsePerfData", "-proc:none", "-parameters", "-g", "-cp", classpath(graphs["old"]),
                        "-d", classes, src, sources / "AfterStartup.java"], check=True)
        record = {"entry":"com.google.protobuf.CodedOutputStream methods after a successful ordinary class initialization on the specified JDK and original classpath",
                  "positive":"Round trip on nonnegative int; unsigned varint lengths on all int or long bits.",
                  "unchangedControl":"Independent unsigned-shift length and wrong64 inverse", "callerSha256":digest(classes / "PublishedWidths.class"),
                  "callerSourceSha256":digest(src), "jdkModulesSha256":digest(JDK / "lib/modules"), "sides":{}}
        for side, graph in graphs.items():
            log = work / (side + "-java-init.log")
            args = [JDK / "bin/java", "-ea", "-XX:-UsePerfData", "-Xlog:class+init=info:file="+str(log), "-cp", classpath([classes,*graph]),
                    "AfterStartup", graph[0], *map(str,bounds)]
            lines = subprocess.check_output(args, text=True, env=javaenv()).splitlines()
            names = sorted(set(re.findall(r"Initializing '((?:com/google/protobuf/|java/util/logging/)[^']*)'", log.read_text())))
            if lines != [str(n)+" true true true false" for n in bounds] or "com/google/protobuf/CodedOutputStream" not in names:
                raise ValueError("original initialization or downstream behavior changed")
            record["sides"][side] = {"orderedJars":[digest(p) for p in graph], "observations":lines, "initializers":names}
        save(OUT / "startup" / "registration.json", record)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("discover","measure","loaders","startup"))
    p.add_argument("cases",nargs="+",choices=[*SLOTS,*TRANSFERS,"wrong"])
    p.add_argument("--side",choices=("old","new"))
    a=p.parse_args()
    if a.action=="measure" and not a.side:p.error("measurement requires --side")
    for c in a.cases:
        if a.action=="discover":discover(c)
        elif a.action=="loaders":original_loaders(c)
        elif a.action=="startup":startup(c)
        else:measure(c,a.side)
