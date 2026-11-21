"""Import regular Maven Central JAR/POM artifacts with matching retained SHA-1 checksums from a pinned OCI layer."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile


PREFIX = "root/.m2/repository/"
PART = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*")
SHA1 = re.compile(rb"([a-fA-F0-9]{40})(?:\s+[^\r\n]+)?\s*")


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def member_name(raw):
    if raw.startswith("./"):
        raw = raw[2:]
    if not raw.startswith(PREFIX):
        return None
    tail = raw[len(PREFIX):]
    if not tail or tail.endswith("/"):
        return None
    parts = tail.split("/")
    if len(parts) < 4 or any(not PART.fullmatch(x) for x in parts):
        return None
    return PurePosixPath(*parts)


def gav(path):
    group, artifact, version, filename = path.parts[:-3], *path.parts[-3:]
    if "SNAPSHOT" in version.upper() or filename not in (artifact + "-" + version + ".jar", artifact + "-" + version + ".pom"):
        return False
    return bool(group) and artifact not in ("fscrawler", "assertj-guava")


def safe_output(root, relative):
    if root.is_symlink():
        raise ValueError("refusing a symlink as the Maven cache")
    dest = root
    for part in relative.parts[:-1]:
        dest /= part
        if dest.is_symlink():
            raise ValueError("refusing symlinked cache component")
        dest.mkdir(exist_ok=True)
    target = dest / relative.name
    if target.is_symlink():
        raise ValueError("refusing a symlink as a Maven artifact")
    return target


def import_layer(layer, identity, cache):
    if not re.fullmatch(r"[a-f0-9]{64}", identity) or digest(layer) != identity:
        raise ValueError("OCI layer differs from its digest")
    cache.mkdir(parents=True, exist_ok=True)
    repository = cache / "repository"
    repository.mkdir(exist_ok=True)
    expected, central, seen, rejected = {}, set(), set(), set()
    refused = 0
    with tarfile.open(layer, "r|gz") as stream:
        for item in stream:
            key = member_name(item.name)
            if not key or item.isdir():
                continue
            if not item.isreg() or key in seen:
                refused += 1
                rejected.add(key)
                continue
            seen.add(key)
            if key.name == "_remote.repositories" and item.size <= 32768:
                for line in stream.extractfile(item).read().decode("ascii", "replace").splitlines():
                    name, sep, repo = line.partition(">")
                    if sep and repo.strip() == "central=" and PART.fullmatch(name):
                        central.add(key.with_name(name))
            if key.name.endswith(".sha1") and item.size <= 512:
                match = SHA1.fullmatch(stream.extractfile(item).read())
                if match:
                    expected[key.with_suffix("")] = match[1].decode().lower()
    allowed = {key for key in central & expected.keys() if gav(key) and key not in rejected
               and key.with_name(key.name + ".sha1") not in rejected and key.with_name("_remote.repositories") not in rejected}
    taken, written, reusable = [], 0, 0
    with (cache / "import.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with tarfile.open(layer, "r|gz") as stream:
            for item in stream:
                key = member_name(item.name)
                if key not in allowed or not item.isreg():
                    continue
                allowed.remove(key)
                if not 0 < item.size <= 128 * 1024**2:
                    raise ValueError("unexpected Maven artifact size")
                raw = stream.extractfile(item).read()
                if len(raw) != item.size or hashlib.sha1(raw).hexdigest() != expected[key]:
                    raise ValueError(f"Maven retained SHA-1 mismatch for {key}")
                found = hashlib.sha256(raw).hexdigest()
                dest = safe_output(repository, key)
                if dest.exists():
                    if not dest.is_file() or digest(dest) != found:
                        raise ValueError(f"conflicting artifact {key}")
                    reusable += 1
                else:
                    stage = dest.with_suffix(dest.suffix + ".importing")
                    with stage.open("xb") as file:
                        file.write(raw)
                    stage.replace(dest)
                    written += 1
                taken.append({"file": key.as_posix(), "bytes": item.size, "sha1": expected[key], "sha256": found})
        if allowed:
            raise ValueError("Maven checksums or origins referenced absent inputs")
        proven = {"layerSha256": identity, "centralId": "central", "checksummedArtifacts": len(taken),
                  "bytes": sum(x["bytes"] for x in taken), "newFiles": written, "alreadyPresent": reusable,
                  "nonregularOrDuplicateMembersDiscarded": refused, "files": sorted(taken,key=lambda x:x["file"])}
        provenance = cache / (identity + ".json")
        if not provenance.exists() or json.loads(provenance.read_bytes()).get("files") != proven["files"]:
            stage = provenance.with_suffix(".json.importing")
            stage.write_text(json.dumps(proven, indent=2) + "\n")
            stage.replace(provenance)
    return proven


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layer", type=Path)
    parser.add_argument("sha256")
    parser.add_argument("cache", type=Path)
    args = parser.parse_args()
    result = import_layer(args.layer, args.sha256, args.cache)
    print(json.dumps({k:v for k,v in result.items() if k!="files"}))
