"""Export a neutral, read-only revision pair from a curator's complete file plan."""

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def check(condition):
    if not condition:
        raise ValueError("packet check failed")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def outside(path):
    path = path.resolve()
    check(not any((p / "llm-dlc/tools/sync.py").is_file() for p in (path, *path.parents)))
    return path


def clean_name(name):
    path = PurePosixPath(name)
    check(not path.is_absolute() and ".." not in path.parts and "." not in path.parts and "\\" not in name)
    return path


def scan(name, data, forbidden, depth=0):
    path = clean_name(name)
    parts = {part.lower() for part in path.parts}
    check(not parts.intersection({".git", ".jj", ".hg", ".svn", "test-classes", "surefire-reports", "failsafe-reports"}))
    check(not any(word in name.encode() or word in data for word in forbidden))
    suffix = path.suffix.lower()
    if suffix in {".jar", ".zip", ".war", ".aar", ".jmod"} or data.startswith(b"PK\x03\x04"):
        check(depth < 8)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.infolist():
                if not member.is_dir():
                    with z.open(member) as stream:
                        body = stream.read(64 * 1024 * 1024 + 1)
                    check(len(body) <= 64 * 1024 * 1024)
                    scan(member.filename, body, forbidden, depth + 1)
    elif suffix in {".tar", ".tgz"} or name.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        check(depth < 8)
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            for member in t:
                check(member.isfile() or member.isdir())
                if member.isfile():
                    check(member.size <= 64 * 1024 * 1024)
                    scan(member.name, t.extractfile(member).read(), forbidden, depth + 1)


def retained(data, decision):
    check(digest(data) == decision["original_sha256"])
    action = decision["action"]
    if decision["role"] in {"production", "dependency_descriptor"}:
        check(action == "copy")
    if action == "copy":
        return data
    check(bool(decision["reason"].strip()))
    if action == "omit":
        return None
    check(action == "strip" and bool(decision["deletions"]))
    # Only the specified ranges can change, including an annotation on the removed method.
    out = bytearray()
    last = 0
    for edit in decision["deletions"]:
        start, end = edit["start"], edit["end"]
        check(type(start) is int and type(end) is int and last <= start < end <= len(data))
        check(digest(data[start:end]) == edit["sha256"])
        out.extend(data[last:start])
        last = end
    out.extend(data[last:])
    check(digest(out) == decision["retained_sha256"])
    return bytes(out)


def export_revision(side, dest, forbidden):
    repository = outside(Path(side["repository"]))
    revision = side["revision"]
    check(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision))
    command = ["git", "--no-replace-objects", "-C", str(repository)]
    tree = subprocess.run(command + ["ls-tree", "--full-tree", "-rz", revision],
                          check=True, capture_output=True).stdout
    tracked = {}
    for record in tree.rstrip(b"\x00").split(b"\x00"):
        info, raw_name = record.split(b"\t", 1)
        mode, kind, oid = info.decode("ascii").split()
        name = raw_name.decode("utf-8")
        clean_name(name)
        tracked[name] = (mode, kind, oid)
    check(set(tracked) == set(side["files"]))
    output = {}
    aliases = {}
    with subprocess.Popen(command + ["cat-file", "--batch"], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as reader:
        try:
            for name, (mode, kind, oid) in sorted(tracked.items()):
                decision = side["files"][name]
                protected = name.rsplit("/", 1)[-1] == "pom.xml" or re.search(r"(?:^|/)src/(?:main|generated)/", name)
                if protected:
                    check(decision["action"] == "copy")
                if kind == "commit":
                    # A required submodule is exported as its own pinned tree with a complete plan.
                    if decision["action"] == "omit":
                        check(bool(decision["reason"].strip()) and decision["role"] not in {"production", "dependency_descriptor"})
                        continue
                    nested = decision["submodule"]
                    check(nested["revision"] == oid)
                    for subname, receipt in export_revision(nested, dest / name, forbidden).items():
                        output[name + "/" + subname] = receipt
                    continue
                check(kind == "blob" and mode in {"100644", "100755", "120000"})
                reader.stdin.write(oid.encode() + b"\n")
                reader.stdin.flush()
                returned, datatype, size = reader.stdout.readline().split()
                check(returned.decode() == oid and datatype == b"blob")
                data = reader.stdout.read(int(size))
                check(len(data) == int(size) and reader.stdout.read(1) == b"\n")
                content = retained(data, decision)
                if content is None:
                    continue
                scan(name, content, forbidden)
                target = dest / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if mode == "120000":
                    link = content.decode("utf-8")
                    check(not Path(link).is_absolute())
                    aliases[target] = link
                else:
                    with target.open("xb") as f:
                        f.write(content)
                    target.chmod(0o555 if mode == "100755" else 0o444)
                output[name] = {"mode": mode, "sha256": digest(content)}
        finally:
            reader.stdin.close()
    check(reader.returncode == 0)
    for target, link in aliases.items():
        target.symlink_to(link)
    for target in aliases:
        resolved = target.resolve(strict=True)
        check(resolved.is_relative_to(dest.resolve()) and resolved.is_file())
    return output


def export_runtime(artifacts, dest, forbidden):
    """Keep the supplied original runtime order and verify the full client archive."""
    check(isinstance(artifacts, list) and bool(artifacts))
    result = []
    dest.mkdir(parents=True)
    for i, artifact in enumerate(artifacts):
        role = artifact["role"]
        check(role == ("client" if i == 0 else "dependency"))
        path = outside(Path(artifact["source"]))
        body = path.read_bytes()
        check(digest(body) == artifact["sha256"])
        filename = f"{i:02d}-{role}.jar"
        scan(filename, body, forbidden)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = [m.filename for m in archive.infolist() if not m.is_dir()]
            check(len(names) == len(set(names)))
            if role == "client":
                expected = artifact["production_members"]
                check(isinstance(expected, dict) and set(names) == set(expected))
                check(any(n.endswith(".class") for n in names))
                for name in names:
                    check(digest(archive.read(name)) == expected[name])
        target = dest / filename
        with target.open("xb") as file:
            file.write(body)
        target.chmod(0o444)
        result.append({"side": dest.name, "path": (PurePosixPath(dest.name) / filename).as_posix(),
                       "sha256": artifact["sha256"]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="complete private pre-reviewed file plan")
    parser.add_argument("destination", type=Path, help="fresh neutral release directory")
    args = parser.parse_args()
    try:
        plan = json.loads(outside(args.plan).read_bytes())
        case_id = plan["case_id"]
        check(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", case_id))
        literals = plan["forbidden_literals"]
        check(literals and all(isinstance(word, str) and word for word in literals))
        # Include both upstream revisions automatically, in addition to curated aliases,
        # sequestered methods and duplicate fixtures (including compiled constant pools).
        strings = set(literals) | {plan[side]["revision"] for side in ("old", "new")}
        forbidden = {s.encode(encoding) for s in strings for encoding in ("utf-8", "utf-16le", "utf-16be")}
        destination = outside(args.destination)
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            pair = Path(temporary) / "pair"
            pair.mkdir(mode=0o700)
            receipt = {"case_id": case_id}
            check(("runtime_artifacts" in plan["old"]) == ("runtime_artifacts" in plan["new"]))
            dependencies = Path(temporary) / "dependencies"
            released_artifacts = []
            for side in ("old", "new"):
                side_path = pair / side
                files = export_revision(plan[side], side_path, forbidden)
                check(bool(files))
                receipt[side] = {"tree_sha256": digest(canonical(files))}
                if "runtime_artifacts" in plan[side]:
                    released_artifacts.extend(export_runtime(
                        plan[side]["runtime_artifacts"], dependencies / side, forbidden
                    ))
            (pair / "pair.json").write_bytes(canonical(receipt) + b"\n")
            (pair / "pair.json").chmod(0o444)
            if released_artifacts:
                manifest = dependencies / "manifest.json"
                manifest.write_bytes(canonical({"case_id": case_id, "artifacts": released_artifacts}) + b"\n")
                manifest.chmod(0o444)
                for directory in dependencies.iterdir():
                    if directory.is_dir():
                        directory.chmod(0o555)
            for directory in (item for item in pair.rglob("*") if item.is_dir() and not item.is_symlink()):
                directory.chmod(0o555)
            destination.mkdir(mode=0o700, exist_ok=False)
            try:
                if released_artifacts:
                    dependencies.rename(destination / "dependencies")
                pair.rename(destination / "pair")
            except Exception:
                if (destination / "dependencies").is_dir():
                    (destination / "dependencies").rename(dependencies)
                destination.rmdir()
                raise
            (destination / "pair").chmod(0o555)
            if released_artifacts:
                (destination / "dependencies").chmod(0o555)
        destination.chmod(0o555)
        print(json.dumps(receipt, sort_keys=True))
    except (OSError, KeyError, ValueError, TypeError, RuntimeError, EOFError,
            subprocess.SubprocessError, tarfile.TarError, zipfile.BadZipFile):
        parser.exit(1, "Neutral export failed. Inspect the private plan and source evidence.\n")


if __name__ == "__main__":
    main()
