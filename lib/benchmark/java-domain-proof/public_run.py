"""Measure every frozen obligation through build.py and keep the original execution receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "organic-java"))
import run as organic
import upstream


def read(path):
    return json.loads(path.read_bytes())


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def measure(argv, output):
    start = time.monotonic()
    with output.open("wb") as log:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        _, status, usage = os.wait4(process.pid, 0)
        process.returncode = os.waitstatus_to_exitcode(status)
    return {"exit":process.returncode, "seconds":round(time.monotonic()-start,6),
            "peakRssBytes":usage.ru_maxrss*1024, "command":argv, "log":output.name}


def native(folder, task, argv, dest):
    source = folder / "receipts" / task
    previous = set(source.glob("*/result.json"))
    record = measure([*argv, "--task", task], dest/(task+".log"))
    results = set(source.glob("*/result.json")) - previous
    if len(results) != 1:
        raise ValueError(f"{task}: expected exactly one fresh qualified workflow result, found {len(results)}")
    result, = results
    row = read(result)
    attempt = row["attempt"]["id"]
    arch = dest/task
    shutil.copytree(result.parent, arch/attempt)
    execution = source/"executions"/attempt
    if execution.is_dir():
        shutil.copytree(execution, arch/"executions"/attempt)
    record.update(status=row["conclusion"]["status"], receipt=str((arch/attempt/"result.json").relative_to(dest)))
    return record


def run(number, stage, seconds):
    case = read(HERE/"cases.json")["cases"][number]
    folder = ROOT/"examples"/case["folder"]
    out = folder/"records"/stage
    out.mkdir(parents=True)
    upstream.bind(case,folder/"records/original-build")
    spec = read(folder/"target.json")
    checker = Path(os.environ["JVMCONTRACT"])
    pin = read(HERE/"opening.json")
    fingerprint = organic.baseline_inputs(pin["inputs"], ROOT)
    if stage == "opening" and fingerprint != (pin["engineAndWorkflowFiles"], pin["engineAndWorkflowSha256"]):
        raise ValueError("the opening workflow or engine inputs differ from the frozen inventory")
    receipt = {"schema":"java-domain-public-run/v1","stage":stage,"example":number,
               "sourceCommit":os.environ["VERIFY_SOURCE_COMMIT"],"libTree":os.environ["JVMCONTRACT_LIB_TREE"],
               "checkerSha256":digest(checker),"inventory":pin["inputs"],"fingerprint":fingerprint[1],
               "subjectJdk":spec["preparation"]["jdks"],"claims":{}}
    receipt["artifacts"] = {side:digest(folder/path) for side,path in spec["preparation"]["capturedBuilds"].items()}
    argv = [sys.executable,"examples/tools/build.py",number,"--checker-seconds",str(seconds)]
    receipt["replay"] = native(folder,"replay",argv,out)
    write(out/"run.json",receipt)
    tasks = [t["id"] for t in spec["tasks"] if t["kind"]=="prove"]
    finite = folder/"records/finite-proofs"
    previous = set(finite.glob("*"))
    receipt["finite"] = measure([*argv,"--finite-domain","--tasks",",".join(tasks)],out/"finite.log")
    batches = set(finite.glob("*")) - previous
    if len(batches) == 1:
        batch, = batches
        shutil.copytree(batch,out/"finite")
    for task in tasks:
        receipt["claims"][task] = native(folder,task,argv,out)
        write(out/"run.json",receipt)
    if (receipt["replay"]["exit"] or receipt["finite"]["exit"] or
            any(not (out/"finite"/(t+".json")).is_file() for t in tasks)):
        raise ValueError("the public replay or finite evidence is incomplete")
    for t in spec["tasks"]:
        if t["kind"]=="prove":
            field = read(out/"finite"/(t["id"]+".json"))
            claim = read(folder/t["claim"])
            if field["inputs"] != claim["adapter"]["cases"] or field["status"] != t["expected"]:
                raise ValueError(f"{t['id']}: finite outcome differs from frozen expectation")
    print(json.dumps({task:row["status"] for task,row in receipt["claims"].items()}))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("example",choices=read(HERE/"cases.json")["cases"])
    p.add_argument("--stage",required=True)
    p.add_argument("--seconds",type=int,default=60)
    args=p.parse_args()
    run(args.example,args.stage,args.seconds)
