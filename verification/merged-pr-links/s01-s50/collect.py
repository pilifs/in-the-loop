"""Retain digest-verified campaign outputs from the independent result line."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = HERE / "jobs.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jj(repo, *args):
    return subprocess.check_output(["jj", "--ignore-working-copy", *args], cwd=repo)


def collect(repo, job):
    if not re.fullmatch(r"\d{8}-\d{6}-[a-z0-9-]+", job):
        raise ValueError("invalid job ID")
    day = "/".join((job[:4],job[4:6],job[6:8]))
    job_bytes = (ROOT / f"verification/jobs/{day}/{job}.json").read_bytes()
    spec = json.loads(job_bytes)
    path = f"verification/results/{day}/{job}/result.json"
    rev = jj(repo,"log","--no-graph","-r",f'latest(::@ & files("{path}"))',"-T","commit_id").decode()
    if not re.fullmatch(r"[0-9a-f]{40}", rev):
        raise ValueError("missing collector revision for " + job)
    raw = jj(repo,"file","show","-r",rev,path)
    record = json.loads(raw)
    job_digest = sha(json.dumps(spec, sort_keys=True).encode())
    if record["id"] != job or record["job"]["spec"] != spec or record["job"]["sha256"] != job_digest:
        raise ValueError("collector and committed job disagree for " + job)
    outputs = []
    for output in record["outputs"]:
        rel = Path(output["path"])
        if rel.is_absolute() or ".." in rel.parts or not (ROOT / rel).is_relative_to(HERE) or rel.suffix != ".json":
            raise ValueError("unexpected campaign output " + str(rel))
        data = jj(repo,"file","show","-r",rev,str(rel))
        if sha(data) != output["sha256"] or len(data) != output["bytes"]:
            raise ValueError("collector output differs for " + str(rel))
        json.loads(data)
        dest = ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.read_bytes() != data:
            raise ValueError("existing campaign evidence differs: " + str(rel))
        dest.write_bytes(data)
        outputs.append({k:output[k] for k in ("path","sha256","bytes")})
    return dict(job=job,status=record["status"],source=record["sourceCommit"],collector=rev,
                result=path,resultSha256=sha(raw),outputs=outputs)


def check(rows):
    for row in rows:
        for output in row["outputs"]:
            data = (ROOT/output["path"]).read_bytes()
            if len(data) != output["bytes"] or sha(data) != output["sha256"]:
                raise ValueError("retained evidence changed: " + output["path"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-repo", type=Path)
    p.add_argument("jobs", nargs="*")
    args = p.parse_args()
    rows = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []
    if args.jobs:
        if not args.from_repo:
            p.error("collecting requires the independent checkout")
        by_id = {r["job"]:r for r in rows}
        for job in args.jobs:
            by_id[job] = collect(args.from_repo,job)
        rows = [by_id[job] for job in sorted(by_id)]
        check(rows)
        MANIFEST.write_text(json.dumps(rows,indent=2) + "\n")
    check(rows)
    print(f"Verified {len(rows)} independent jobs and {sum(len(r['outputs']) for r in rows)} output files.")
