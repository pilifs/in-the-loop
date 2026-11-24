"""Materialize the collector's checked campaign outputs and link them to the submitted source."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from plan_run import OUTPUT, ROOT


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def collect(collector):
    jobs = []
    for path in sorted((ROOT/"verification/jobs").rglob("*.json")):
        # Only the organic campaign submits jobs with this path in an actual step.
        doc = json.loads(path.read_bytes())
        if not any("lib/benchmark/organic-composition/" in step["run"] for step in doc.get("steps",[])):
            continue
        result_path = collector/"verification/results"/path.parent.relative_to(ROOT/"verification/jobs")/doc["id"]/"result.json"
        if not result_path.is_file():
            continue
        result = json.loads(result_path.read_bytes())
        if (result["id"] != doc["id"] or result["job"]["spec"] != doc
                or result["job"]["sha256"] != hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest()):
            raise ValueError("collector job specification differs: "+doc["id"])
        outputs = []
        for record in result["outputs"]:
            rel = Path(record["path"])
            if rel.is_absolute() or ".." in rel.parts or not rel.is_relative_to(OUTPUT) or record["change"]=="deleted":
                raise ValueError("unexpected output in "+doc["id"])
            checksum = record["sha256"]
            dest = ROOT/rel
            candidates = [result_path.parent/"outputs"/rel,collector/rel,dest]
            src = next((p for p in candidates if p.is_file() and sha(p)==checksum),None)
            if src is None:
                raise ValueError("could not verify "+str(rel))
            if dest.is_file() and sha(dest) != checksum:
                raise ValueError("an earlier experiment owns a different "+str(rel))
            if not dest.is_file():
                dest.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=dest.parent,delete=False) as f:
                    pending=Path(f.name)
                    with src.open("rb") as stream:
                        shutil.copyfileobj(stream,f)
                if sha(pending)!=checksum:
                    raise ValueError("copied output digest differs")
                pending.replace(dest)
            outputs.append({"path":str(rel),"sha256":checksum})
        jobs.append({"id":doc["id"],"status":result["status"],"source":result["sourceCommit"],
                     "finishedAt":result["finishedAt"],"specSha256":result["job"]["sha256"],
                     "resultSha256":sha(result_path),"usage":result.get("usage"),"outputs":outputs})
    out=ROOT/OUTPUT/"jobs.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(jobs,indent=2)+"\n")
    print(f"{len(jobs)} collected jobs, {sum(len(r['outputs']) for r in jobs)} verified outputs")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("collector",type=Path)
    collect(parser.parse_args().collector.resolve())
