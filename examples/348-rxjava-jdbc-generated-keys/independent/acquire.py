"""Populate a flat, hash-checked, anonymous cache for the CompSuite i-87 source and its Java toolchain."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

HERE = Path(__file__).resolve().parent


@contextlib.contextmanager
def one_request(lock):
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            time.sleep(1)


def acquire(directory, lock):
    directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / "inputs.json").read_text())
    for item in [manifest["mavenDistribution"], *manifest["artifacts"].values()]:
        dest = directory / item["file"]
        if dest.is_file():
            digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        else:
            with one_request(lock):
                with urllib.request.urlopen(item["url"], timeout=30) as response:
                    data = response.read()
                digest = hashlib.sha256(data).hexdigest()
                if digest == item["sha256"]:
                    dest.write_bytes(data)
        if digest != item["sha256"]:
            raise ValueError(f"Hash mismatch for {dest.name}")
    subject = directory / "subject.git"
    if not subject.exists():
        with one_request(lock):
            subprocess.run(
                [
                    "git",
                    "-c",
                    "credential.helper=",
                    "clone",
                    "--bare",
                    "https://github.com/compsuite-team/rxjava-jdbc.git",
                    str(subject),
                ],
                check=True,
            )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", type=Path)
    p.add_argument(
        "--lock", type=Path, default=Path(os.environ["TMPDIR"]) / "external-upgrade-network.lock"
    )
    args = p.parse_args()
    acquire(args.inputs, args.lock)
