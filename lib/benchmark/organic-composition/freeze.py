"""Pin or verify the reusable implementation before constructing transfer cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from plan_run import HERE, JDK, ROOT

sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import change_inventory, change_plan, upgrade_replay


def files():
    names = ("change_plan", "change_evidence", "change_helpers", "change_inventory", "upgrade_replay",
             "upgrade_claims", "upgrade_linkage", "upgrade_jdbc", "upgrade_receiver", "runtime_jar",
             "class_binding", "runtime_jdk")
    base=Path("examples/tools/targets")
    return [Path("examples/tools/build.py"),*(base/(name+".py") for name in names),
            *(base/"java"/(name+".java") for name in ("UpgradeTrace","UpgradeObservation","UpgradeClassLookup")),
            *(Path("lib/benchmark/organic-composition")/(name+".py") for name in
              ("plan_run","matrix","native_open","prepare","freeze"))]


def identity():
    checker = Path(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract"))
    return {"files":{str(p):upgrade_replay.sha(ROOT/p) for p in files()},
            "checkerSha256":upgrade_replay.sha(checker),"jdk":change_inventory.jdk_binding(JDK),
            "runnerIdentity":change_plan.runner_identity()}


def verify():
    saved=json.loads((HERE/"freeze.json").read_bytes())
    for key,value in identity().items():
        if saved[key]!=value:
            raise ValueError("transfer differs from reusable freeze: "+key)
    return saved["source"]


def capture(rev):
    def git(*args):
        return subprocess.check_output(["git",*args],cwd=ROOT)
    source=git("rev-parse",rev).decode().strip()
    record=identity()
    for p in files():
        if hashlib.sha256(git("show",source+":"+str(p))).hexdigest()!=record["files"][str(p)]:
            raise ValueError("shared file is different from the committed source: "+str(p))
    record.update(source=source,checkerTree=git("rev-parse",source+":lib/src").decode().strip(),
                  modelTree=git("rev-parse",source+":lib/models").decode().strip(),
                  startup="Fresh process, original startup method and enclosing frame, selected resource URL and bytes when registered.",
                  summary="Exact integral table, closed primitive instructions and normal original JVM returns. A successful native lemma and its proved frame are retained. A strict refusal may use the separate exhaustive closed-body proof.",
                  cache="Positive two-trial original sides and helper proofs are keyed independently by their complete inputs.")
    (HERE/"freeze.json").write_text(json.dumps(record,indent=2)+"\n")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",metavar="REV")
    args=parser.parse_args()
    if args.capture:
        capture(args.capture)
    print(verify())
