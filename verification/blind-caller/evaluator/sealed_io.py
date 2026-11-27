"""Read immutable evaluator inputs in a workspace or in the verification runner's plain export."""
from functools import lru_cache
import io
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from eligibility_inventory import CACHE, ROOT, digest


def committed_input(revision, name):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("expected the full committed Git object name")
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("expected a repository-relative input")
    # An exported runner checkout deliberately has no .git. Only the evaluator uses
    # the pipeline's documented repository handle; the worker sees materialized bytes.
    repository = ROOT if (ROOT / ".git").exists() else Path(os.environ["VERIFY_RUNNER_ROOT"])
    return subprocess.check_output(["git", "-C", str(repository), "show", f"{revision}:{rel.as_posix()}"],
                                   stderr=subprocess.PIPE)


def pack_files(root, destination):
    with zipfile.ZipFile(destination, "x") as archive:
        for file in sorted(root.rglob("*")):
            if file.is_symlink() or not file.resolve().is_relative_to(root.resolve()):
                raise ValueError("evidence contains an external file reference")
            if file.is_file():
                archive.writestr(zipfile.ZipInfo(file.relative_to(root).as_posix()), file.read_bytes(), zipfile.ZIP_DEFLATED)


@lru_cache(maxsize=4)
def packed_bytes(revision, name):
    return committed_input(revision, name)


def read_member(revision, directory, path):
    try:
        content = packed_bytes(revision, (directory / "artifacts.zip").relative_to(ROOT))
    except subprocess.CalledProcessError:
        return committed_input(revision, (directory / path).relative_to(ROOT))
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return archive.read(Path(path).as_posix())


def retain_checker(checksum):
    """A concurrent build can replace lib/target after the freeze; retain its exact bytes."""
    source = ROOT / "lib/target/release/jvmcontract"
    if not re.fullmatch(r"[0-9a-f]{64}", checksum) or digest(source) != checksum:
        raise ValueError("original checker differs from the SHA-256 in the producer freeze")
    target = CACHE / "blind-caller-pr-verification/checkers" / checksum / "jvmcontract"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=target.parent) as staged:
            with source.open("rb") as original:
                import shutil
                shutil.copyfileobj(original, staged)
            staged.flush()
            os.fsync(staged.fileno())
            if digest(Path(staged.name)) != checksum:
                raise ValueError("checker changed during retention")
            os.chmod(staged.name, 0o555)
            try:
                os.link(staged.name, target)
            except FileExistsError:
                pass
    if digest(target) != checksum:
        raise ValueError("an existing content-addressed checker has different bytes")
    return target


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Retain the frozen checker for verification-runner exports.")
    parser.add_argument("--retain-checker", required=True)
    retain_checker(parser.parse_args().retain_checker)
    print("exact original checker retained for queued measurements")
