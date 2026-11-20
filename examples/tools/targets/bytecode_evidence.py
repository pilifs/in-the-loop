"""Record the exact selected method, compiler, class-file version and disassembly for a public fixture task."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from targets import route, runtime, runtime_jar


def inspect(folder, target, task, work, extra):
    plan = route.resolve(folder, json.loads((folder / "example.json").read_text()), target, task)
    rows = []
    for rev in plan.revisions:
        p = runtime.prepare(plan, rev, work / rev)
        if p.stage != "artifacts-ready":
            raise ValueError(p.diagnostic)
        jdk = runtime._verifier_jdk(plan, {rev: p})
        cp = runtime._checked(work / rev, p)
        original = work / rev / p.source["target"]["loadedFrom"]
        owner, method, desc = runtime_jar.parse_target(plan.target)
        dumps = {}
        for name in [owner, *extra]:
            data = runtime_jar.read_class(original, runtime_jar.internal(name))
            if not data:
                raise ValueError(f"missing {name} in {rev}")
            code = subprocess.check_output([str(Path(jdk["home"]) / "bin/javap"), "-p", "-s", "-c", "-classpath",
                        str(original), name], text=True)
            import hashlib
            dumps[name] = {"major": int.from_bytes(data[6:8], "big"), "sha256": hashlib.sha256(data).hexdigest(),
                           "methods": [{"name": m, "descriptor": d, "flags": runtime_jar.method_flags(data,m,d)}
                                       for m,d in sorted(runtime_jar.methods(data))], "disassembly": code.splitlines()}
        rows.append({"revision": rev, "entry": plan.target, "compiler": p.toolchain.get("originalCompiler") or
                     {"jdk": p.toolchain["jdk"], "recipe": p.source["recipe"]}, "runtime": jdk["version"],
                     "classpath": [{"path": a.path,"sha256": a.sha256} for a in cp], "classes": dumps})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number")
    parser.add_argument("tasks", nargs="+")
    parser.add_argument("--class", dest="extra", action="append", default=[])
    args = parser.parse_args()
    [folder] = TOOLS.parent.glob(args.number+"-*")
    target = json.loads((folder / "target.json").read_text())
    with tempfile.TemporaryDirectory(prefix="bytecode-evidence-") as tmp:
        data = [row for task in args.tasks for row in inspect(folder,target,task,Path(tmp)/task,args.extra)]
    print(json.dumps(data,indent=2))
