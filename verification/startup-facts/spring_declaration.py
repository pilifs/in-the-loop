"""Bind the cached override's measured erased declaration on the same frozen producer."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"lib/benchmark/startup-facts"))
from transfers import compile_java, digest, jvm
from freeze import RECORD, frozen_sources


def measure():
    sealed = digest(RECORD)
    frozen = frozen_sources()
    base = ROOT/"examples/480-spring-nested-return-type"
    manifest = json.loads((base/"runtime.json").read_bytes())
    jdk = Path.home()/".sdkman/candidates/java"/manifest["jdk"]
    result = []
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or Path.home()/".cache/in-the-loop/agent-tmp") as tmp:
        work = Path(tmp)
        tools = work/"tools"
        sources = work/"frozen-sources"
        sources.mkdir()
        for name, content in frozen.items():
            if name.startswith("lib/src/observed/") and name.endswith(".java"):
                (sources/Path(name).name).write_bytes(content)
        compile_java(jdk, tools, sorted(sources.glob("*.java")))
        for side, entries in manifest["deployments"]["pins"]["classpath"].items():
            cache = Path.home()/".cache/in-the-loop"/manifest["cache"]
            jars = [cache/name for name in entries]
            assert [digest(p) for p in jars] == [manifest["sha256"][name] for name in entries]
            classes = work/side
            compile_java(jdk, classes, [base/"caller/PublicCaller.java", ROOT/"lib/benchmark/startup-facts/CachedSpringMethod.java"], jars)
            trace, log = work/(side+".json"), work/(side+".log")
            window = "ObservedInitializer#initializeRoots([Ljava/lang/String;Ljava/lang/ClassLoader;ZI)Ljava/lang/Class;"
            cp = os.pathsep.join(map(str,[tools,classes,*jars]))
            proc = jvm(jdk,["-cp",tools,"StartupTrace",trace,window,"--methods","-XX:-UsePerfData",
                          "-Xlog:class+init=info:file="+str(log)+"::filecount=0","-cp",cp,"--main","ObservedInitializer",
                          "--record-methods","CachedSpringMethod",log])
            if proc.returncode:
                raise ValueError(proc.stderr.decode(errors="replace")[-1100:])
            recorded = json.loads(proc.stdout.decode().split("@observed ",1)[1])
            obj, = [o for o in recorded["objects"] if o["k"]=="method"]
            events = json.loads(trace.read_bytes())["events"]
            store, = [e for e in events if e.get("field")=="CachedSpringMethod#METHOD"]
            known = digest(classes/"PublicCaller$Text.class")
            if obj["declaringSha256"] != known:
                raise ValueError("the actual declaring class differs from the prepared sibling")
            for key in ("owner","name","descriptor","modifiers","accessibleOverride"):
                if store["member"][key] != obj[key]:
                    raise ValueError("assigned Method differs from the final field in "+key)
            if obj["modifiers"] & 0x40:
                raise ValueError("the field selected a bridge")
            result.append({"side":side,"jdk":recorded["jdk"],"originalClassSha256":known,"assignmentSite":store["stack"][0],
                           "field":store["field"],"member":obj,"lookupEvents":[e["operation"] for e in events if e["operation"].startswith("getMethod(")],
                           "coverage":"assignment and erased declaration; the frozen recorder does not correlate getDeclaredMethods array elements"})
    return {"producer":sealed,"rows":result}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    data=json.dumps(measure(),indent=2)+"\n"
    path=Path(__file__).with_name("spring-declaration.json")
    if args.check:
        if data!=path.read_text():raise SystemExit("Spring declaration evidence changed")
    else:path.write_text(data)
    print("two original non-bridge Method assignments and declaring class digests match")
