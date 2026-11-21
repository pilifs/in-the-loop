"""Restore the corpus's pinned historical Maven files into the shared external release cache."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

from maven_mirror import artifact_path


def install_missing(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent) as staging:
        staging.write(data)
        staging.flush()
        os.link(staging.name, path)


def restore(repository, archive, name, expected):
    relative = artifact_path(name)
    if relative is None:
        raise ValueError("invalid Maven release path")
    destination = (repository / relative).resolve()
    if not destination.is_relative_to(repository):
        raise ValueError("release escapes the shared cache")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (repository.parent / "resolution.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cached = destination.exists()
        if cached:
            with destination.open("rb") as stream:
                raw = stream.read(expected["bytes"] + 1)
        else:
            url = archive + name
            with urlopen(url, timeout=35) as response:
                if response.geturl() != url:
                    raise ValueError("unexpected release location: " + name)
                raw = response.read(expected["bytes"] + 1)
        if len(raw) != expected["bytes"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
            source = "existing cached" if cached else "archived"
            raise ValueError(f"{source} bytes differ from the pinned release: {name}")
        if not cached:
            install_missing(destination, raw)
        # Maven 3 checks SHA-1 when the isolated mirror serves the already SHA-256-verified bytes.
        sidecar = destination.with_name(destination.name + ".sha1")
        sha1 = hashlib.sha1(raw).hexdigest()
        if not sidecar.exists():
            install_missing(sidecar, (sha1 + "\n").encode("ascii"))
        elif sidecar.read_text().split()[:1] != [sha1]:
            raise ValueError("cached Maven checksum differs from the pinned release: " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maven-cache", required=True, type=Path)
    args = parser.parse_args()
    repository = args.maven_cache.resolve()
    if repository.is_relative_to(Path(__file__).resolve().parents[4]):
        parser.error("the shared Maven cache belongs outside the checkout")
    manifest = json.loads(Path(__file__).with_name("archived-releases.json").read_text())
    for name, expected in manifest["files"].items():
        restore(repository, manifest["archive"], name, expected)
    print(f"Verified {len(manifest['files'])} historical Maven release files.")


if __name__ == "__main__":
    main()
