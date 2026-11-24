"""Reproduce the case's per-entry oracle with Python's independent TAR reader."""
import hashlib
from pathlib import Path
import tarfile

path = Path.home() / ".cache/in-the-loop/organic-pr-20/worktrees/J07-commons-compress-fix/src/test/resources/COMPRESS-657/orjson-3.7.8.tar"
for historical in (True, False):
    digest = hashlib.sha256()
    with tarfile.open(path) as archive:
        for entry in archive:
            directory = entry.isdir()
            is_file = entry.isfile() or (historical and directory and not entry.name.endswith("/"))
            payload = archive.extractfile(entry).read() if entry.isfile() else b""
            row = "\t".join([entry.name, str(entry.type[0]), str(directory).lower(), str(is_file).lower(),
                             str(len(payload)), hashlib.sha256(payload).hexdigest()]) + "\n"
            digest.update(row.encode())
    print("parent" if historical else "fix", digest.hexdigest())
