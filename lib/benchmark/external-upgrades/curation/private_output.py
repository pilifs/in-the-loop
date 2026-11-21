"""Capture a private command's merged streams. Release only an explicitly shaped progress record."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys


SCHEMA = "external-upgrade-private-progress/v1"
STATES = {"ok", "partial", "unavailable", "needs-review"}
LIMIT = 4096


def project(line):
    try:
        record = json.loads(line)
        if not isinstance(record, dict) or set(record) != {"schema", "status", "counts", "flags", "digests"}:
            return None
        if record["schema"] != SCHEMA or record["status"] not in STATES:
            return None
        counts, flags, digests = record["counts"], record["flags"], record["digests"]
        if not all(isinstance(a, list) and len(a) <= 32 for a in (counts, flags, digests)):
            return None
        if not all(type(v) is int and 0 <= v < 2**53 for v in counts):
            return None
        if not all(type(v) is bool for v in flags):
            return None
        if not all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for v in digests):
            return None
        return {"status": record["status"], "counts": counts, "flags": flags, "digests": digests}
    except (ValueError, TypeError, RecursionError):
        return None


def capture(source, directory):
    directory = directory.resolve()
    if any((p / "llm-dlc/tools/sync.py").is_file() for p in (directory, *directory.parents)):
        raise ValueError("private capture belongs outside the checkout")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_mode & 0o077 or directory.stat().st_uid != os.getuid():
        raise ValueError("capture requires an owner-only directory")
    receipt = secrets.token_hex(12)
    fd = os.open(directory / (receipt + ".log"), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    digest, length, tail = hashlib.sha256(), 0, b""
    with os.fdopen(fd, "wb") as retained:
        while block := source.read(65536):
            retained.write(block)
            digest.update(block)
            length += len(block)
            tail = (tail + block)[-(LIMIT + 2):]
        retained.flush()
        os.fsync(retained.fileno())
    capture_id = {"capture_id": receipt, "stream_sha256": digest.hexdigest(), "bytes": length}
    end = tail.rstrip(b"\r\n")
    split = end.rfind(b"\n")
    if split < 0 and length > len(tail):
        return capture_id
    line = end[split + 1:]
    progress = project(line) if len(line) <= LIMIT else None
    if progress is not None:
        capture_id["progress"] = progress
    return capture_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_directory", type=Path)
    parser.add_argument("--require-progress", action="store_true")
    args = parser.parse_args()
    try:
        result = capture(sys.stdin.buffer, args.private_directory)
    except (OSError, ValueError):
        parser.exit(1, "Private capture unavailable. No subject output was released.\n")
    print(json.dumps(result, separators=(",", ":")))
    return 2 if args.require_progress and "progress" not in result else 0


if __name__ == "__main__":
    sys.exit(main())
