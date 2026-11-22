"""Locate field writers and consumer instructions in the original Maven bytecode for the startup pilot."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

from startup import ROOT, document, runtime_jdk, runtime_jar, runtime_maven
from targets import route, runtime
sys.path.insert(0, str(ROOT / "lib/python"))
from jvm_disassembly import methods

FACTORY = "org.apache.avro.hadoop.io.AvroDatumConverterFactory"
SEP = "com.github.javaparser.utils.LineSeparator"
NODE = "com.github.javaparser.ast.Node"
SELECT = {
    "355": {
        "organic.WritableBuffer": ["input", "converted", "bounds", "prefix", "rejected", "firstRejected", "directLimit"],
        FACTORY: ["<init>", "create"], FACTORY + "$BytesWritableConverter": ["<init>", "convert", "getWriterSchema"],
        "org.apache.avro.Schema": ["<clinit>", "create"], "org.apache.avro.JsonProperties": ["<clinit>"],
        "org.apache.avro.util.internal.Accessor": ["setAccessor"],
        "org.apache.hadoop.io.BytesWritable": ["<clinit>", "<init>", "getBytes", "getLength", "setSize"],
        "org.apache.hadoop.io.WritableComparator": ["define"],
        "org.apache.hadoop.mapred.JobConf": ["<init>", "getNumReduceTasks"],
        "org.apache.hadoop.conf.Configuration": ["<clinit>", "getInt", "getTrimmed", "getProps", "get", "loadResources"],
        "org.apache.hadoop.security.Credentials": ["<clinit>", "<init>"]},
    "360": {
        "organic.TreeOrder": ["tree", "expected", "find", "postorder", "preorder", "terminal"],
        NODE: ["<clinit>", "findAll"], NODE + "$PostOrderIterator": ["<init>", "next", "hasNext"],
        SEP: ["<clinit>", "asRawString"],
        "com.github.javaparser.printer.configuration.DefaultPrinterConfiguration": ["<init>", "removeOption"],
        "com.github.javaparser.printer.configuration.DefaultConfigurationOption": ["<init>", "value"]},
}
READS = {"getstatic", "putstatic", "getfield", "putfield", "athrow", "new", "checkcast", "instanceof",
         "goto", "tableswitch", "lookupswitch", "monitorenter", "monitorexit"}


def consumer(folder, number, side):
    spec = json.loads((folder / "target.json").read_text())
    task = ("direct-limit-" if number == "355" else "postorder-") + side
    plan = route.resolve(folder, json.loads((folder / "example.json").read_text()), spec, task)
    selected = {}
    with tempfile.TemporaryDirectory(prefix="consumer-dependencies-") as temp:
        work = Path(temp)
        prepared = runtime.prepare(plan, side, work)
        cp = runtime._checked(work, prepared)
        jdk = Path(runtime_jdk.home("21"))
        wanted = set(SELECT[number])
        for artifact in cp:
            if not wanted:
                break
            with zipfile.ZipFile(work / artifact.path) as jar:
                entries = runtime_jar.effective_entries(jar, 21)
                for name in sorted(wanted.copy()):
                    entry = entries.get(name.replace(".", "/") + ".class")
                    if entry is None:
                        continue
                    data = jar.read(entry)
                    local = work / (name.split(".")[-1] + ".class")
                    local.write_bytes(data)
                    parsed, _ = methods(jdk / "bin/javap", local)
                    kept = {}
                    for (method, desc), code in parsed.items():
                        if method == name.split(".")[-1]:
                            method = "<init>"
                        if method not in SELECT[number][name]:
                            continue
                        rows = []
                        for i in code["code"]:
                            if i.op in READS or i.op.startswith(("invoke", "if")) or i.op.endswith("return"):
                                rows.append([i.pc, i.op, i.member or i.arg])
                            elif i.member in ("String line.separator", "String mapreduce.job.reduces"):
                                rows.append([i.pc, i.op, i.member])
                        kept[method + desc] = {"hasExceptionTable": code["handlers"], "instructions": rows}
                    missing = set(SELECT[number][name]) - {m.split("(")[0] for m in kept}
                    if missing:
                        raise ValueError(f"missing methods {name} {missing} on {side}")
                    selected[name] = {"jarSha256": artifact.sha256, "classSha256": hashlib.sha256(data).hexdigest(),
                                      "entry": entry.filename, "methods": kept}
                    wanted.remove(name)
        if wanted:
            raise ValueError(f"unbound consumer classes on {side}: {wanted}")
    return selected


def origin(preceding):
    if preceding.endswith(":literal"):
        return "adjacent literal"
    if preceding.startswith(("GETFIELD:", "GETSTATIC:")):
        return "adjacent field read"
    if any(s in preceding for s in ("java/lang/System.getProperty", "java/lang/System.getenv", "availableProcessors")):
        return "adjacent process input"
    if any(s in preceding for s in ("getResource", "getClassLoader", "ServiceLoader.")):
        return "adjacent class-loader or resource lookup"
    return "unresolved value origin"


def recover(number, side, output):
    folder, = (ROOT / "examples").glob(number + "-*")
    receipts = folder / "records/foundation-profiles" / side
    summary = json.loads((receipts / "profiles.json").read_text())
    def table(key):
        row = summary["tables"][key]
        p = receipts / row["file"]
        if runtime_maven.sha256_of(p) != row["sha256"]:
            raise ValueError("changed field profile: " + str(p))
        return json.loads(gzip.decompress(p.read_bytes()))
    static = table("inventory")
    profiles = table("fieldEvents")
    writers, declarations = {}, {}
    for line in static["bytecode"]:
        cells = line.split("\t")
        if cells[0] == "declaration":
            _, owner, name, descriptor, source = cells
            declarations[owner+"."+name+":"+descriptor] = source
        elif cells[0] == "field" and cells[5] == "PUTSTATIC":
            _, owner, method, signature, pc, _, field, prev = cells
            writers[(owner, method, signature, pc)] = {"symbolicField": field, "precedingInstruction": prev,
                                                      "origin": origin(prev)}
    label = "roots" if number == "355" else "node-lf"
    fields = defaultdict(list)
    by_phase = defaultdict(set)
    for line in profiles[label]["fieldSites"]:
        phase, op, caller, method, signature, pc, owner, field, descriptor = line.split("\t")
        if op != "putstatic":
            continue
        owner, caller = owner[1:-1], caller[1:-1]
        name = owner + "." + field + ":" + descriptor
        site = writers.get((caller, method, signature, pc))
        if site and not site["symbolicField"].endswith("."+field+":"+descriptor):
            raise ValueError("a live JVMTI field writer disagrees with the selected class bytecode")
        fields[name].append({"phase": int(phase), "method": caller+"."+method+signature, "bci": int(pc),
                             **(site or {"origin": "opaque or outside selected application bytecode"})})
        by_phase[phase].add(name)
    original = consumer(folder, number, side)
    for name, row in original.items():
        matched = static["selected"].get(name.replace(".", "/"))
        if matched and matched["sha256"] != row["classSha256"]:
            raise ValueError("consumer and startup selected different class bytes")
    path = output / f"{number}-{side}.json.gz"
    document(path, {"schema": "original-startup-dependencies/v1", "example": number, "side": side,
             "profileReceipt": str((receipts/"profiles.json").relative_to(ROOT)), "recordedPhase": label,
             "classStatusBits": {"1": "verified", "2": "prepared", "4": "initialized", "8": "erroneous"},
             "staticDeclarations": declarations, "observedStaticWriters": dict(fields), "consumerBytecode": original,
             "limits": ["The preceding instruction records bytecode adjacency. Proving a reaching definition requires checking all incoming edges.",
                        "Unobserved branches, external callbacks, native/reflective writes and termination remain open.",
                        "The linked class-status and field-event tables preserve the individual process profiles."]})
    print(number, side, len(declarations), "declarations,", len(fields), "observed static fields, phases",
          {k:len(v) for k,v in sorted(by_phase.items())}, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    for n in SELECT:
        for rev in ("parent", "fix"):
            recover(n, rev, a.output)
