"""Publish smaller LRAT certificates for an existing caller without changing its native solver transcript."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from history import OUTPUT, ROOT, digest, scratch
import jvmcontract_lrat as lrat

TRIM_SOURCE = lrat.CACHE / "cadical-1.9.5/test/cnf/lrat-trim.c"
TRIM_SHA256 = "c104c8145344a261561ddd93abce1b9a6409dc8b3797763b32e904e367424be4"


def rup_additions(proof):
    """Positive LRAT hints use only reverse unit propagation. Extra live clauses preserve these derivations."""
    additions = []
    for line in proof.splitlines(keepends=True):
        if line.partition(b" ")[2].startswith(b"d "):
            continue
        _, sep, hints = line.partition(b" 0 ")
        if not sep or b"-" in hints:
            return proof  # A RAT pivot may require deletions. Keep the trimmer's complete proof.
        additions.append(line)
    return b"".join(additions)


def compact(source, dest, work, trimmer):
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(dest, "x", zipfile.ZIP_DEFLATED) as smaller:
        manifest = json.loads(original.read("manifest.json"))
        for name in original.namelist():
            if name.startswith("traces/"):
                smaller.writestr(name, original.read(name))
        for event in manifest["events"]:
            if event["status"] != "unsat":
                continue
            name = f"proofs/{event['key']}.lrat"
            raw = original.read(name)
            if lrat.digest(raw) != event["proofSha256"]:
                raise ValueError(f"{name}: original proof digest differs")
            old, new = work / "query.lrat", work / "trimmed.lrat"
            old.write_bytes(raw)
            subprocess.run([trimmer, "--ascii", "--quiet", old, new], check=True, timeout=120)
            candidate = rup_additions(new.read_bytes())
            proof = candidate if len(candidate) < len(raw) else raw
            smaller.writestr(name, proof)
            event["proofSha256"] = lrat.digest(proof)
        smaller.writestr("manifest.json", json.dumps(manifest, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path, nargs="?", default=OUTPUT / "followup/iscwt-assurance")
    ap.add_argument("--source", type=Path, help="original evidence.zip from the registered job")
    args = ap.parse_args()
    folder = args.folder
    pin = json.loads((folder / "original-bundle.json").read_bytes())
    output = Path(pin["output"])
    if output.is_absolute() or ".." in output.parts or output.name != "evidence.zip":
        raise ValueError("invalid original bundle path")
    with scratch(prefix="compact-lrat-") as tmp, tempfile.TemporaryDirectory(dir=folder) as prepared:
        work = Path(tmp)
        source = args.source or Path(os.environ.get("VERIFY_RUNNER_ROOT", ROOT)) / output
        if args.source is None and not source.is_file():
            archive = work / "archive"
            subprocess.run([sys.executable, ROOT / "llm-dlc/tools/artifacts.py", "fetch", pin["archiveOccurrence"],
                            "--flat", "--to", archive], check=True)
            source = archive / output
        if source.stat().st_size != pin["bytes"] or digest(source) != pin["sha256"] or digest(TRIM_SOURCE) != TRIM_SHA256:
            raise ValueError("original solver bundle or proof trimmer differs from its pin")
        trimmer = work / "lrat-trim"
        compile_cmd = ["cc", "-O2", "-o", str(trimmer), str(TRIM_SOURCE)]
        subprocess.run(compile_cmd, check=True)
        bundle = Path(prepared) / "trimmed.zip"
        compact(source, bundle, work, trimmer)
        cmd = [sys.executable, "-B", lrat.__file__, "--check", str(folder / "request.json"),
               str(folder / "boundary.json"), str(bundle)]
        checked = json.loads(subprocess.check_output(cmd, text=True))
        original = json.loads((folder / "assurance.json").read_bytes())
        for field in ("status", "ordinary", "requestSha256", "boundarySha256", "checkerSha256", "answers", "passes"):
            if checked[field] != original[field]:
                raise ValueError("different solver boundary or assurance: " + field)
        request = json.loads((folder / "request.json").read_bytes())
        request["claim"]["observation"] = "always false after the public calls"
        boundary = json.loads((folder / "boundary.json").read_bytes())
        try:
            lrat.verify(request, boundary, bundle)
        except ValueError as exc:
            if "request differs" not in str(exc):
                raise
        else:
            raise ValueError("the smaller bundle accepted a different observation")
        report = {"job": os.environ.get("VERIFY_JOB_ID"), "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
                  "original": pin, "bundleSha256": digest(bundle), "bundleBytes": bundle.stat().st_size,
                  "trimmerSourceSha256": TRIM_SHA256, "trimmerSha256": digest(trimmer), "compileArgv": compile_cmd,
                  "trimArgv": [str(trimmer), "--ascii", "--quiet", str(work / "query.lrat"), str(work / "trimmed.lrat")],
                  "freshCheckArgv": cmd, "wrongObservationRejected": True, "checked": checked}
        os.replace(bundle, folder / "trimmed.zip")
        lrat.save(folder / "trimmed.json", report)
        print(f"{pin['bytes']:,} to {report['bundleBytes']:,} bytes; {checked['answers']}", flush=True)


if __name__ == "__main__":
    main()
