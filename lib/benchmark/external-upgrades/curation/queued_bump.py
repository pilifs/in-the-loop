"""Dispatch a frozen, offline BUMP reproduction and emit only aggregate coverage and custody digests."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import UUID


HERE = Path(__file__).resolve().parent
WORKER_SHA256 = "62b4d39efcf5937490d21880694eee15a2877b58d42c220a3177a6f76ccd2b5c"
PUBLIC_RUNTIME = HERE.parent / "baselines/bump/runtime_image.py"
PUBLIC_FIELDS = {"completed", "fresh_exact_named_testcases", "input_verified"}
WORKER_ENTRY = """\
import sys
sys.argv = sys.argv[1:]
program = compile(sys.stdin.buffer.read(), sys.argv[0], "exec")
exec(program, {"__name__": "__main__", "__file__": sys.argv[0]})
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def coverage(stdout, returncode):
    if returncode not in {0, 3} or len(stdout) > 512:
        raise ValueError("private reproduction did not complete")
    data = json.loads(stdout)
    if (not isinstance(data, dict) or set(data) != PUBLIC_FIELDS or data["input_verified"] is not True or
            type(data["completed"]) is not int or data["completed"] != 4 or
            type(data["fresh_exact_named_testcases"]) is not int or not 0 <= data["fresh_exact_named_testcases"] <= 4 or
            (returncode == 0) != (data["fresh_exact_named_testcases"] == 4)):
        raise ValueError("unexpected private coverage result")
    return data


def dispatch(session, packet, manifest_hash, output):
    if str(UUID(session)) != session or not re.fullmatch(r"[0-9a-f]{24}", packet):
        raise ValueError("invalid custody address")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_hash):
        raise ValueError("invalid manifest digest")
    parent = Path.home() / ".cache/in-the-loop/agent-tmp" / session / "external-upgrade-custody-jobs"
    root = parent / packet
    if root.resolve(strict=True) != root or output.exists():
        raise ValueError("expected a custody packet and a fresh public output")
    inputs = root / "input"
    worker = root / "run.py"
    code = worker.read_bytes()
    manifest = inputs / "manifest.json"
    if (sha(code) != WORKER_SHA256 or sha(manifest.read_bytes()) != manifest_hash or
            (inputs / "runtime_image.py").read_bytes() != PUBLIC_RUNTIME.read_bytes()):
        raise ValueError("worker, immutable input or networkless runtime did not verify")
    # Pass the verified program bytes once. Its logical filename locates its private input and output.
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TMPDIR": str(parent.parent)}
    with (root / ".queued-run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.monotonic()
        child = subprocess.run([sys.executable, "-I", "-B", "-c", WORKER_ENTRY, str(worker), manifest_hash],
                               cwd=root, env=env, input=code, capture_output=True)
        data = coverage(child.stdout, child.returncode)
        raw = (root / "output/latest.json").read_bytes()
        retained = json.loads(raw)
        if (retained["input_digest"] != manifest_hash or sha(manifest.read_bytes()) != manifest_hash or
                retained["counts"]["attempted"] != data["completed"] or
                retained["counts"]["fresh_exact_named_testcases"] != data["fresh_exact_named_testcases"]):
            raise ValueError("private receipt is for a different attempt")
        summary = {"packet": packet, "input_sha256": manifest_hash, "private_receipt_sha256": sha(raw),
                   "worker_sha256": WORKER_SHA256, "seconds": round(time.monotonic() - started, 3), **data}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(json.dumps(data, sort_keys=True))
    return child.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        return dispatch(args.session, args.packet, args.input_sha256, args.output)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        # Neither case-specific command lines nor the subject's logs belong in the public queue.
        parser.exit(1, "Private offline BUMP reproduction unavailable. The curator retains the detailed evidence.\n")


if __name__ == "__main__":
    sys.exit(main())
