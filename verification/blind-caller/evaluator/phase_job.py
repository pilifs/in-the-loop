"""Run or collect one contiguous shard of frozen arm slots with a per-case durable receipt."""
import argparse
from collections import Counter
import errno
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from eligibility_inventory import HERE, ROOT, digest, read, write
from evaluate_arm import filename, run_one
from packet_view import ARMS
from sealed_io import committed_input


def job_files(arm, phase, first, last):
    return [filename(arm, index, phase, "attempt.json").parent for index in range(first, last + 1)]


def pack(directories, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="caller-phase-pack-") as tmp:
        staged = Path(tmp) / "shard.zip"
        with zipfile.ZipFile(staged, "x") as archive:
            for directory in directories:
                for file in sorted(directory.iterdir()):
                    if not file.is_file() or file.is_symlink():
                        raise ValueError("incomplete case receipt")
                    compression = zipfile.ZIP_STORED if file.name == "artifacts.zip" else zipfile.ZIP_DEFLATED
                    archive.writestr(zipfile.ZipInfo(file.relative_to(HERE).as_posix()), file.read_bytes(), compression)
        try:
            os.replace(staged, destination)
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
            with tempfile.TemporaryDirectory(prefix=".shard-publication-", dir=destination.parent) as transfer:
                complete = Path(transfer) / "shard.zip"
                shutil.copyfile(staged, complete)
                os.replace(complete, destination)


def run(args):
    if not 1 <= args.first <= args.last <= 20:
        raise ValueError("slot range must be inside the fixed draw")
    counts = Counter()
    directories = job_files(args.arm, args.phase, args.first, args.last)
    for index in range(args.first, args.last + 1):
        status = run_one(index, args.phase, args.arm, args.reference_seal, args.cold_seal, args.prediction_seal,
                         seconds=None, trace_seal=args.trace_seal)
        counts[status] += 1
        if args.output:
            pack(directories[:index - args.first + 1], args.output)
    print(json.dumps(dict(counts)))


def collect(args):
    revision, job = args.revision, args.job
    if len(job) < 8 or not job[:8].isdigit():
        raise ValueError("invalid verification job identity")
    result_path = Path("verification/results") / job[:4] / job[4:6] / job[6:8] / job / "result.json"
    result = json.loads(committed_input(revision, result_path))
    if result["id"] != job or result["status"] != "passed" or len(result.get("outputs", [])) != 1:
        raise ValueError("verification collector has not passed this shard and retained its single output")
    ref, = result["outputs"]
    rel = Path(ref["path"])
    if not rel.is_relative_to(HERE.relative_to(ROOT) / "shards") or rel.suffix != ".zip" or ".." in rel.parts:
        raise ValueError("unexpected arm shard output")
    raw = committed_input(revision, rel)
    if hashlib.sha256(raw).hexdigest() != ref["sha256"] or len(raw) != ref["bytes"]:
        raise ValueError("collected shard differs from its pipeline receipt")
    with tempfile.TemporaryDirectory(prefix="caller-phase-collect-") as tmp:
        area = Path(tmp)
        folders = set()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for member in archive.infolist():
                p = PurePosixPath(member.filename)
                if (len(p.parts) != 5 or p.parts[0] != "arms" or p.parts[1] not in ARMS or not p.parts[2].isdigit()
                        or not 1 <= int(p.parts[2]) <= 20 or p.parts[3] not in ("predict", "measure", "trace")
                        or p.name not in ("attempt.json", "view.json", "prediction.json", "measurement.json", "trace.json", "artifacts.zip")):
                    raise ValueError("unexpected file in collector shard")
                interim = area / p
                interim.parent.mkdir(parents=True, exist_ok=True)
                with interim.open("xb") as dest:
                    dest.write(archive.read(member))
                folders.add(p.parent)
        for folder in folders:
            incoming = area / folder
            attempt = read(incoming / "attempt.json")
            if (attempt["index"] != int(folder.parts[2]) or attempt["arm"] != folder.parts[1]
                    or attempt["phase"] != folder.parts[3]):
                raise ValueError("shard contains a receipt for another slot")
            dest = HERE / folder
            if dest.exists():
                if {p.name: digest(p) for p in dest.iterdir()} != {p.name: digest(p) for p in incoming.iterdir()}:
                    raise ValueError("a distinct attempt already occupies a collected slot")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                from evaluate_arm import store_new
                store_new(incoming, dest)
    record = {"job": job, "collectorRevision": revision, "sourceRevision": result["sourceCommit"],
              "result": str(result_path), "output": str(rel), "sha256": ref["sha256"], "bytes": ref["bytes"],
              "slots": len(folders)}
    write(HERE / "collector" / (job + ".json"), record)
    print(f"{len(folders)} per-case receipts verified against the immutable collector output")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    execute = commands.add_parser("run")
    execute.add_argument("phase", choices=("predict", "measure", "trace"))
    execute.add_argument("arm", choices=ARMS)
    for flag in ("first", "last"):
        execute.add_argument("--" + flag, required=True, type=int)
    execute.add_argument("--reference-seal", required=True)
    execute.add_argument("--prediction-seal")
    execute.add_argument("--cold-seal")
    execute.add_argument("--trace-seal")
    execute.add_argument("--output", type=Path)
    accept = commands.add_parser("collect")
    accept.add_argument("--revision", required=True)
    accept.add_argument("--job", required=True)
    args = parser.parse_args()
    (run if args.action == "run" else collect)(args)
