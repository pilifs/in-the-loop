"""Pin independent job results and verify their original archives on the feature line."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/"collector.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def archive(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if invalid := z.testzip():
            raise ValueError("corrupt job archive member " + invalid)


def jj(directory,*args):
    return subprocess.check_output(["jj","--ignore-working-copy",*args],cwd=directory)


def collect(directory, job):
    if not re.fullmatch(r"\d{8}-\d{6}-[a-z0-9-]+",job):
        raise ValueError("invalid verification job id")
    report = json.loads(subprocess.check_output(["python3","verification/pipeline.py","report","--format","json",
                                                  "--tail","0",job],cwd=directory))["results"]
    if len(report) != 1 or report[0]["id"] != job:
        raise ValueError("the collector has no result for " + job)
    row = report[0]
    file = row["result"]
    revision = jj(directory,"log","--no-graph","-r",'latest(::@ & files("'+file+'"))',"-T","commit_id").decode()
    result = jj(directory,"file","show","-r",revision,file)
    record = json.loads(result)
    if record["id"] != job or record["status"] != row["status"]:
        raise ValueError("reported job differs from its collected revision")
    outputs = []
    for output in record.get("outputs",[]):
        path = Path(output["path"])
        if path.suffix != ".zip" or not path.is_relative_to("verification/blind-caller") or ".." in path.parts:
            raise ValueError("uncatalogued output of a blind-caller verification job")
        data = jj(directory,"file","show","-r",revision,str(path))
        if len(data) != output["bytes"] or sha(data) != output["sha256"]:
            raise ValueError("original collector archive digest differs")
        archive(data)
        dest = ROOT/path
        if dest.exists() and sha(dest.read_bytes()) != sha(data):
            raise ValueError("another campaign result is already archived at " + str(path))
        dest.write_bytes(data)
        outputs.append({"path":str(path),"bytes":len(data),"sha256":sha(data)})
    return {"id":job,"status":row["status"],"summary":row["summary"],"attention":row["attention"],
            "collectorRevision":revision,"sourceRevision":record["sourceCommit"],"result":file,
            "resultSha256":sha(result),"outputs":outputs}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-repo",type=Path)
    p.add_argument("jobs",nargs="*")
    args=p.parse_args()
    doc = json.loads(MANIFEST.read_bytes()) if MANIFEST.exists() else {"schema":"blind-caller-collector/v1","jobs":[]}
    if args.jobs:
        if not args.from_repo:
            p.error("collecting requires the independent pipeline checkout")
        prior={r["id"]:r for r in doc["jobs"]}
        for job in args.jobs:
            prior[job]=collect(args.from_repo,job)
        doc["jobs"]=[prior[k] for k in sorted(prior)]
        MANIFEST.write_text(json.dumps(doc,indent=2)+"\n")
    for row in doc["jobs"]:
        for output in row["outputs"]:
            data = (ROOT/output["path"]).read_bytes()
            if len(data) != output["bytes"] or sha(data) != output["sha256"]:
                raise ValueError("archived bytes changed: "+output["path"])
            archive(data)
    print(len(doc["jobs"]),"verified collector records")


if __name__ == "__main__":
    main()
