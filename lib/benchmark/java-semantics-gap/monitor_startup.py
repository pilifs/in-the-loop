"""Trace the first open platform-thread constructor and check its caller-visible callback on fresh JVMs."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from campaign import JDK, ROOT, command, compile_java, digest, javaenv, write
from jvm_disassembly import methods

EXAMPLE = ROOT / "examples/391-class-monitor-identity"
BASE = ROOT / "verification/java-semantics-gap"
OUTPUT = BASE / "monitor-startup/measurement.json"
PLATFORM = "(Ljava/lang/ThreadGroup;Ljava/lang/String;ILjava/lang/Runnable;JLjava/security/AccessControlContext;)V"
MAP = "Ljava/lang/ThreadLocal$ThreadLocalMap;"


def call(code, op, member):
    ins, = [i for i in code if i.op == op and i.member == "Method " + member]
    return {"pc": ins.pc, "instruction": op, "method": member}


def observation(work):
    env = javaenv()
    source = EXAMPLE / "adapter/MonitorIdentity.java"
    observer = EXAMPLE / "controls/WorkerStartup.java"
    classes = work / "classes"
    compile_java([source, observer], classes, [], env)
    frozen = json.loads((BASE / "heap-and-gson/monitors/measurement.json").read_bytes())
    original = {name: digest(classes / name) for name in frozen["classes"]}
    if original != frozen["classes"] or digest(JDK / "lib/modules") != frozen["modulesSha256"]:
        raise ValueError("different monitor caller or execution JVM")
    worker = methods(JDK / "bin/javap", classes / "MonitorIdentity$Worker.class")[0]
    chain = [{"owner":"MonitorIdentity$Worker", "entry":"<init>()V", **call(worker[("MonitorIdentity$Worker", "()V")]["code"],
              "invokespecial", 'java/lang/Thread."<init>":()V')}]
    names = ("Thread", "ThreadLocal", "ThreadLocal$ThreadLocalMap")
    patterns = ",".join("glob:/java.base/java/lang/" + name + ".class" for name in names)
    subprocess.run([JDK/"bin/jimage", "extract", "--dir", work/"image", "--include", patterns, JDK/"lib/modules"], check=True)
    paths = {n: work/"image/java.base/java/lang"/(n + ".class") for n in names}
    code = {n: methods(JDK/"bin/javap", p)[0] for n, p in paths.items()}
    for name, method, desc, op, member in (
            ("Thread", "Thread", "()V", "invokespecial", '"<init>":' + PLATFORM),
            ("Thread", "Thread", PLATFORM, "invokestatic", "currentThread:()Ljava/lang/Thread;"),
            ("Thread", "Thread", PLATFORM, "invokestatic", "java/lang/ThreadLocal.createInheritedMap:(" + MAP + ")" + MAP),
            ("ThreadLocal", "createInheritedMap", "(" + MAP + ")" + MAP, "invokespecial",
             'java/lang/ThreadLocal$ThreadLocalMap."<init>":(' + MAP + ')V'),
            ("ThreadLocal$ThreadLocalMap", "ThreadLocal$ThreadLocalMap", "(" + MAP + ")V", "invokevirtual",
             "java/lang/ThreadLocal.childValue:(Ljava/lang/Object;)Ljava/lang/Object;")):
        chain.append({"owner":"java/lang/" + name, "entry":method + desc, **call(code[name][method, desc]["code"], op, member)})
    cases = [("constructor", b) for b in ("absent", "null", "present", "removed")]
    cases += [("matched", "present")] + [(m, "throw") for m in ("matched", "mixed", "synchronizedMethod")]
    rows = []
    for entry, binding in cases:
        rc, stdout, stderr, _ = command([JDK / "bin/java", "-ea", "-cp", classes, "WorkerStartup", entry, binding], env)
        out = stdout.decode().strip()
        if rc or not out:
            raise ValueError(f"{entry}/{binding}: {stderr.decode()}")
        result, count, shared = out.split("\t")
        rows.append({"entry":entry, "parentBinding":binding, "result":result,
                     "childValueCalls":int(count), "finalShared":int(shared)})
    return {"scope":"One fresh Temurin JVM per explicitly installed, removed or absent parent binding",
            "jdkModulesSha256":frozen["modulesSha256"], "originalClasses":original, "jdkClasses":{n:digest(p) for n,p in paths.items()},
            "observerSha256":digest(observer), "observerClasses":{p.name:digest(p) for p in sorted(classes.glob("WorkerStartup*.class"))},
            "constructorCalls":chain, "jvmRuns":rows}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check", action="store_true")
    args = cli.parse_args()
    with tempfile.TemporaryDirectory(prefix="monitor-startup-") as tmp:
        result = observation(Path(tmp))
    if args.check:
        if result != json.loads(OUTPUT.read_bytes()):
            raise ValueError("different original JVM startup evidence")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        write(OUTPUT, result)
    print(f"{len(result['jvmRuns'])} original JVM startup controls agreed")
