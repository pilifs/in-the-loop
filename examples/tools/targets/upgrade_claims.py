"""Find caller methods that invoke a changed dependency. Emit exact descriptors and observable claim candidates."""

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile

from targets import runtime_jar


MEMBER = re.compile(r"^  (\S.*)\((.*)\).*;$")
CALL = re.compile(r"\b(invokevirtual|invokestatic|invokespecial|invokeinterface)\s+.*?// (?:InterfaceMethod|Method) ([^: ]+):(\S+)")
CALLBACKS = {"onNext", "onError", "onComplete", "onCompleted", "complete", "completeExceptionally"}


def named_overloads(old_data, new_data, name):
    """Keep exact common declarations and drop compiler bridges when the source method is present."""
    def members(data):
        return {desc for n, desc in runtime_jar.methods(data) if n == name
                and not runtime_jar.method_flags(data, n, desc) & (0x0040 | 0x1000)}
    old, new = members(old_data), members(new_data)
    return {"common": sorted(old & new), "removed": sorted(old-new), "added": sorted(new-old)}


def calls_in_methods(javap, owner):
    calls = defaultdict(list)
    member = descriptor = None
    for line in javap.splitlines():
        if match := MEMBER.fullmatch(line):
            member = match[1].split()[-1]
            if member == owner.replace("/", "."):
                member = "<init>"
            descriptor = None
        elif line == "  static {};":
            member, descriptor = "<clinit>", None
        elif member and line.startswith("    descriptor: "):
            descriptor = line.split(": ", 1)[1].strip()
        elif descriptor and (match := CALL.search(line)):
            target = match[2].replace('"', "")
            cls, dot, method = target.rpartition(".")
            calls[member, descriptor].append((cls if dot else owner, method, match[3]))
    return calls


def listing(jdk, classpath, owner, seconds):
    tmp = os.environ.get("TMPDIR")
    argv = [str(Path(jdk)/"bin/javap"), *([f"-J-Djava.io.tmpdir={tmp}"] if tmp else []), "-p", "-s", "-c",
            "-classpath", os.pathsep.join(map(str,classpath)), owner.replace("/", ".")]
    output = subprocess.check_output(argv, text=True, errors="replace", timeout=seconds)
    return calls_in_methods(output, owner)


def jar_index(jar, feature):
    with zipfile.ZipFile(jar) as archive:
        view = runtime_jar.effective_entries(archive, feature)
        return {name[:-6]: hashlib.sha256(archive.read(item)).hexdigest() for name,item in view.items()
                if name.endswith(".class") and not name.startswith("META-INF/") and not name.endswith("module-info.class")}


def discover(client, old_dep, new_dep, jdk, feature, *, owner=None, seconds=120):
    started = time.monotonic()
    old, new = jar_index(old_dep, feature), jar_index(new_dep, feature)
    changed = {n for n in old.keys() | new.keys() if old.get(n)!=new.get(n)}
    provided = set()
    for dep in (old_dep, new_dep):
        with zipfile.ZipFile(dep) as z:
            provided.update(n.removeprefix("META-INF/services/").replace(".","/") for n in z.namelist()
                            if n.startswith("META-INF/services/") and not n.endswith("/"))
    packages = {n.rpartition("/")[0] for n in provided}
    candidates, complete = [], True
    with zipfile.ZipFile(client) as jar:
        entries = runtime_jar.effective_entries(jar, feature)
        for name, info in sorted(entries.items()):
            if not name.endswith(".class") or name.startswith("META-INF/") or name.endswith("module-info.class"):
                continue
            cls=name[:-6]
            if owner and cls != owner.replace(".","/"):
                continue
            data=jar.read(info)
            relevant=lambda c: c in old or c in new or c.rpartition("/")[0] in packages
            if not any(relevant(c) for c,_,_ in runtime_jar.references(data)):
                continue
            remaining=seconds-(time.monotonic()-started)
            if remaining<=0:
                complete=False
                break
            try:
                methods=listing(jdk,[client,old_dep],cls,remaining)
            except subprocess.TimeoutExpired:
                complete=False
                break
            for (method,desc),calls in methods.items():
                flags=runtime_jar.method_flags(data,method,desc)
                if flags is None or flags & (0x0040|0x1000) or method in ("<init>","<clinit>"):
                    continue
                edges=sorted(set(c for c in calls if relevant(c[0])))
                if not edges:
                    continue
                callbacks=sorted({f"{c.replace('/','.')}#{m}" for c,m,_ in calls if m in CALLBACKS})
                observable=("return and escaping exception" if not desc.endswith(")V") else
                            "emitted values and escaping exception" if callbacks else "caller-visible effects and escaping exception")
                candidates.append({"entry":cls.replace("/",".")+"#"+method+desc,"observation":observable,
                    "boundaryCalls":[{"entry":c.replace("/",".")+"#"+m+d,
                                      "basis":"changed dependency class" if c in changed else
                                              "dependency class" if c in old or c in new else "service interface package"}
                                     for c,m,d in edges],
                    "callbacks":callbacks,"publicOrProtected":bool(flags & (0x0001 | 0x0004)),
                    "callerClassSha256":hashlib.sha256(data).hexdigest()})
    candidates.sort(key=lambda c:(not c["publicOrProtected"],not any(x["basis"]=="changed dependency class" for x in c["boundaryCalls"]),
                                  not c["callbacks"],c["entry"]))
    return {"status":"candidates" if candidates else "open","complete":complete,"candidates":candidates,
            "scope":"Direct bytecode calls in the supplied client. A service package is a candidate boundary. Each proposed claim still needs a concrete receiver, input domain and verification."}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for argument in ("client","old-dependency","new-dependency","jdk"):
        parser.add_argument("--"+argument,required=True,type=Path)
    parser.add_argument("--owner")
    parser.add_argument("--seconds",type=int,default=120)
    args=parser.parse_args(argv)
    from targets import runtime_jdk
    feature=int(runtime_jdk.identity(args.jdk)["feature"])
    answer=discover(args.client,args.old_dependency,args.new_dependency,args.jdk,feature,owner=args.owner,seconds=args.seconds)
    print(json.dumps(answer,indent=2))
    return 0
