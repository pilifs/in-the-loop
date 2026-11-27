"""Seal the shared startup recorders and input policy before scoring the disclosed transfers."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "verification/startup-facts/freeze.json"
FILES = ["lib/src/observed.rs","lib/src/property.rs","lib/src/equivalence.rs","lib/src/jvm_witness.rs","lib/src/classpath.rs",
         "lib/src/bmc/observed.rs","lib/src/bmc/reflection.rs","lib/src/bmc/bytes.rs","lib/src/bmc/mod.rs",
         "examples/schema/target-claim.schema.json","examples/tools/targets/recipes.py","examples/tools/targets/replay_candidate.py",
         "examples/tools/targets/qualification.py","examples/tools/targets/property_reads.py","examples/tools/targets/startup_facts.py",
         "examples/tools/targets/workflow.py","llm-dlc/tools/watch.py"]

def files(archived=None):
    if archived is None:
        paths = {p.relative_to(ROOT).as_posix() for area in ("lib/src","examples/tools/targets")
                 for p in (ROOT/area).rglob("*") if p.is_file() and p.suffix in (".rs",".java",".py",".c")}
        def contents(name): return (ROOT/name).read_bytes()
    else:
        paths = {p for p in archived if Path(p).suffix in (".rs",".java",".py",".c")}
        def contents(name): return archived[name]
    names = set(FILES) | {p for p in paths if p.startswith("lib/src/observed/")}
    result = {name:hashlib.sha256(contents(name)).hexdigest() for name in sorted(names)}
    for directory in ("lib/src","examples/tools/targets"):
        tree = [(p,hashlib.sha256(contents(p)).hexdigest()) for p in sorted(paths,key=Path) if p.startswith(directory+"/")]
        result[directory+" (source tree)"] = hashlib.sha256(json.dumps(tree,separators=(",",":")).encode()).hexdigest()
    result["lib/Cargo.lock"] = hashlib.sha256(contents("lib/Cargo.lock")).hexdigest()
    return result

def frozen_sources():
    doc=json.loads(RECORD.read_bytes())
    inputs=["lib/src","examples/tools/targets","lib/Cargo.lock","llm-dlc/tools/watch.py","examples/schema/target-claim.schema.json"]
    data=subprocess.check_output(["git","archive",doc["producerRevision"],*inputs],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archived={m.name:archive.extractfile(m).read() for m in archive if m.isfile()}
    if files(archived)!=doc["sharedSources"]:
        raise ValueError("the archived original producer differs from its sealed digests")
    return archived

def check():
    doc=json.loads(RECORD.read_bytes())
    if doc["sharedSources"]!=files():
        raise ValueError("shared implementation differs from the frozen transfer producer")
    return hashlib.sha256(RECORD.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--seal",action="store_true")
    ap.add_argument("--verify-original",action="store_true");args=ap.parse_args()
    if args.verify_original:
        frozen_sources()
        print(hashlib.sha256(RECORD.read_bytes()).hexdigest())
        return
    if args.seal:
        if RECORD.exists(): raise SystemExit("transfer producer already sealed")
        rev=subprocess.check_output(["jj","--ignore-working-copy","log","-r","@-","--no-graph","-T","commit_id"],cwd=ROOT,text=True).strip()
        doc={"schema":"startup-transfer-freeze/v1","producerRevision":rev,"sharedSources":files(),
             "policy":{"operatorInputs":["original ordered artifacts and effective JDK","registered public caller and history","approved launch profile","first strict diagnostic"],
             "evaluatorOnly":["historical observations and failure text","expected values","altered labelled fixtures"],
             "procedure":"Record the first result with this implementation. Retry a deficient evaluation harness separately. Keep unsupported operations, failed boundaries and partial observations open."},
             "transfers":[{"id":8,"case":"Commons Configuration 565 and 601","profiles":["own","inherited","saved then replaced and removed"]},
             {"id":9,"case":"JavaParser 4538 and paper 332","profiles":["LF","CRLF","removed","nine before/after pairs per implementation"]},
             {"id":10,"case":"Spring 480","profiles":["original public caller","cached non-bridge Method"]},
             {"id":11,"case":"Avro 3878","profiles":["four ordered roots on both 124-entry deployments","reordered","withheld root"]}]}
        with RECORD.open("x") as out: json.dump(doc,out,indent=2);out.write("\n")
    print(check())

if __name__=="__main__":main()
