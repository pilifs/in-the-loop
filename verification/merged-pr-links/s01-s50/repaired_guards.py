"""Check two repaired control-flow obligations in the original merged class files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from zipfile import ZipFile

from audit import inventory

HERE = Path(__file__).resolve().parent
CLASSES = {"S32":"org.springframework.boot.health.actuate.endpoint.HealthEndpointSupport",
           "S38":"org.springframework.boot.json.AppendableByteArray"}


def method(text, match):
    selected, = [block for block in text.split("\n\n") if match in block.splitlines()[0]]
    return selected


def instructions(block):
    return [(int(pc),op,arg.strip()) for pc,op,arg in re.findall(r"^[ \t]*(\d+):[ \t]+(\w+)[ \t]*([^\n]*)$",block,re.M)]


def missing_child(text):
    body = instructions(method(text," getContributor(java.lang.String[], int)"))
    index, = [i for i,(_,op,arg) in enumerate(body) if op == "invokeinterface" and "Contributor.getChild:" in arg]
    stored,loaded,branch,absent,returned,found = body[index+1:index+7]
    if not (stored[1] == "astore" and loaded[1] == found[1] == "aload" and stored[2] == loaded[2] == found[2]
            and branch[1] == "ifnonnull" and int(branch[2]) == found[0]
            and absent[1] == "aconst_null" and returned[1] == "areturn"):
        raise ValueError("missing child does not return immediately from the traversal")
    return {"member":"getContributor(String[], int)","childRead":body[index][0],"nullReturn":returned[0],
            "nonNullContinuation":found[0]}


def reset_on_exit(text):
    reset = method(text,"private void reset()")
    if "java/nio/ByteBuffer.clear:" not in reset or "java/nio/charset/CharsetEncoder.reset:" not in reset:
        raise ValueError("reset does not clear the buffer and encoder")
    block = method(text,"org.springframework.util.function.ThrowingConsumer<")
    body = instructions(block)
    callbacks = [pc for pc,_,arg in body if "ThrowingConsumer.acceptWithException:" in arg]
    resets = [i for i,(_,op,arg) in enumerate(body) if op == "invokevirtual" and "// Method reset:()V" in arg]
    if len(callbacks) != 1 or len(resets) != 2:
        raise ValueError("expected one callback and normal and exceptional cleanup")
    normal, exceptional = resets
    if body[normal-1][1] != body[exceptional-1][1] or body[normal-1][1] != "aload_2":
        raise ValueError("cleanup no longer uses the same retained buffer")
    if body[normal+2][1] != "areturn" or body[exceptional+2][1] != "athrow":
        raise ValueError("return or rethrow no longer follows cleanup")
    protected = [[int(a),int(b),int(c)] for a,b,c in re.findall(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+any\s*$",block,re.M)]
    handler = body[exceptional-2][0]
    thrown = [pc for pc,op,_ in body if op == "athrow" and pc < handler]
    if not all(any(a <= pc < b and c == handler for a,b,c in protected) for pc in callbacks + thrown):
        raise ValueError("callback or typed exception path is outside the cleanup handler")
    return {"member":block.splitlines()[0].strip(),"normalReset":body[normal][0],
            "exceptionalReset":body[exceptional][0],"catchAllEntries":protected,"resetEffects":["buffer clear","encoder reset"]}


def inspect():
    cache = Path.home()/".cache/in-the-loop/spring-boot-pr-links-s01-s50/artifacts"
    javap = Path.home()/".sdkman/candidates/java/25.0.5.0+8-tem/bin/javap"
    cases = inventory()
    out = {}
    for label,cls in CLASSES.items():
        name,digest = next(iter(cases[label]["builds"]["fix"].items()))
        jar = cache/(label+"-fix")/"jars"/name
        if hashlib.sha256(jar.read_bytes()).hexdigest() != digest:
            raise ValueError("different original JAR")
        with ZipFile(jar) as z:
            bytecode = hashlib.sha256(z.read(cls.replace(".","/")+".class")).hexdigest()
        disassembly = subprocess.check_output([javap,"-classpath",jar,"-p","-c",cls],text=True)
        out[label] = dict(revision=cases[label]["revisions"]["fix"],jarSha256=digest,classSha256=bytecode,
                          originalClass=cls,check=(missing_child if label == "S32" else reset_on_exit)(disassembly))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record",action="store_true")
    args = parser.parse_args()
    results = inspect()
    target = HERE/"repaired-guards.json"
    if args.record:
        target.write_text(json.dumps(results,indent=2)+"\n")
    elif json.loads(target.read_text()) != results:
        raise ValueError("different compiled guards")
    print("Verified the repaired missing-child return and both buffer cleanup paths.")
