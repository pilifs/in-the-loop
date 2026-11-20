"""Run one public workflow task with the frozen V0 executable, image, solver and product files."""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

from pin import ROOT, digest


HERE = Path(__file__).resolve().parent


def check_files(lock):
    raw = gzip.decompress((HERE / "v0-files.json.gz").read_bytes())
    manifest = json.loads(raw)
    if hashlib.sha256(raw).hexdigest() != lock["sourceManifestSha256"] or manifest["revision"] != lock["revision"]:
        raise ValueError("source list differs from the pinned product")
    for name, (mode, blob) in manifest["files"].items():
        path = ROOT / name
        if path.is_symlink():
            actual_mode, data = "120000", os.fsencode(os.readlink(path))
        else:
            actual_mode = "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"
            data = path.read_bytes()
        actual_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual_mode != mode or actual_blob != blob:
            raise ValueError("pinned product file differs: " + name)
    return len(manifest["files"])


def tools(lock, checker, jdk, solver):
    deps = {"jvmcontract": checker}
    for name in ("release", "bin/java", "bin/javac", "lib/modules", "lib/server/libjvm.so"):
        deps[name] = jdk / name
    for name in ("libbitwuzla.so.0", "libbitwuzlabv.so", "libbitwuzlabb.so", "libbitwuzlals.so"):
        deps[name] = solver / name
    for name, file in deps.items():
        if digest(file) != lock["sha256"][name]:
            raise ValueError(f"{name} differs from the frozen product lock")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("task")
    parser.add_argument("--checker", type=Path, help="V0 binary; defaults to its digest in the project cache")
    parser.add_argument("--jdk", type=Path, default=Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem")
    parser.add_argument("--solver", type=Path, default=Path.home() / "tools/bitwuzla/current/lib/x86_64-linux-gnu")
    parser.add_argument("--output", type=Path, required=True, help="fresh results directory")
    parser.add_argument("--seconds", type=int, default=7200, help="wall seconds left since case intake")
    args = parser.parse_args()
    if not 0 < args.seconds <= 7200:
        parser.error("remaining time must be within the original two-hour budget")
    lockfile = HERE / "v0.json"
    lock = json.loads(lockfile.read_text())
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "in-the-loop/external-upgrades"
    checker = (args.checker or cache / lock["sha256"]["jvmcontract"] / "jvmcontract").resolve()
    jdk, solver = args.jdk.resolve(), args.solver.resolve()
    before = check_files(lock)
    tools(lock, checker, jdk, solver)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, JVMCONTRACT=str(checker), JVMCONTRACT_BITWUZLA=str(solver / "libbitwuzla.so.0"),
               JVMCONTRACT_SOLVER=lock["native"]["solver"], JAVA_HOME=str(jdk),
               PATH=str(jdk / "bin") + os.pathsep + os.environ["PATH"], TZ="UTC", LANG="C.UTF-8", LC_ALL="C.UTF-8")
    # The queue's build ID belongs to its separate release executable.
    env.pop("JVMCONTRACT_LIB_TREE", None)
    argv = [sys.executable, "examples/tools/build.py", args.example, "--task", args.task]
    started = now()
    start = time.monotonic()
    with (out / "workflow.log").open("wb") as log:
        try:
            run = subprocess.run(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=args.seconds)
            status = run.returncode
        except subprocess.TimeoutExpired:
            status = 124
    elapsed = round(time.monotonic() - start, 3)
    after = check_files(lock)
    tools(lock, checker, jdk, solver)
    receipt = {"schema": "external-upgrade-pinned-task/v1", "example": args.example, "task": args.task,
               "productRevision": lock["revision"], "productLockSha256": digest(lockfile),
               "checkerSha256": digest(checker), "sourceFilesBefore": before, "sourceFilesAfter": after,
               "nativeSolver": env["JVMCONTRACT_SOLVER"], "solverSha256": digest(solver / "libbitwuzla.so.0"),
               "verifierJdkModulesSha256": digest(jdk / "lib/modules"), "argv": ["python3", *argv[1:]],
               "startedUtc": started, "finishedUtc": now(), "remainingSecondsAtStart": args.seconds,
               "elapsedSeconds": elapsed, "workflowExit": status, "logSha256": digest(out / "workflow.log")}
    (out / "invocation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"{args.example} {args.task}: workflow exit {status} after {elapsed}s on {lock['revision'][:12]}")
    return status


if __name__ == "__main__":
    sys.exit(main())
