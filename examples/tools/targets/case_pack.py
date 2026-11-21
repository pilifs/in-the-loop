#!/usr/bin/env python3
"""A folder of per-case checker output, kept as one file.

A native-selector run writes two files for each admitted selector (`cases/p17/native.json` and `cases/p17/stderr`):
5,730 files in one folder for one claim of example 359, 16,376 over examples 340 to 359, of the 22,103 files all
their records hold. Git, jj, a scan and a forge's listing pay for each file, while the bytes are few and alike
(12.9 MB that gzip takes to 0.3 MB). So such a folder is kept as `cases.tar.gz` beside where it was, holding the same
bytes under the same names:

    records/…/calls/2df1780ebf1bce4149bd/cases/p17/native.json      as written by the run
    records/…/calls/2df1780ebf1bce4149bd/cases.tar.gz               member p17/native.json, after `pack`

Nothing is lost and nothing has to be fetched: `read` returns a record's bytes whether the folder or the pack is
there, so the validator re-reads every case and compares its digest exactly as before, in a plain checkout. A file
that is present is used before a pack's member, so a run in progress and a restored original read the same way.

The rule the tools hold an example to (`budget`): no folder named `cases` under `records/` with more than
LOOSE_CASES files in it, at most FILES files under `records/`, at most ENTRIES entries in any one of its folders.
`sync.py check` reports the first as an error, with the command that settles it, and the other two as warnings,
since what to keep of a record that is simply large is for a person to say.

    python3 examples/tools/targets/case_pack.py pack NNN...      pack every cases/ folder of those examples' records
    python3 examples/tools/targets/case_pack.py verify NNN...    read every pack; with --against DIR, also show that
                                                                 the records equal the unpacked tree DIR/examples/NNN-…/records
    python3 examples/tools/targets/case_pack.py budget [NNN...]  what is over the budget, for every example or those

Standard library only.
"""
from __future__ import annotations

import argparse
import functools
import gzip
import hashlib
import io
import os
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

EXAMPLES = Path(__file__).resolve().parents[2]
SUFFIX = ".tar.gz"
FOLDER = "cases"
LOOSE_CASES = 50
FILES = 2000
ENTRIES = 1000


def refused(message: str) -> Exception:
    """A claim's refusal, as `workflow.inside` raises it. Imported here and not above, so that the budget, which
    `sync.py check` asks for at every commit, loads nothing but this file."""
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # examples/tools, for `targets`
    from targets import workflow
    return workflow.ClaimError(message)


def pack_of(folder: Path) -> Path:
    return folder.with_name(folder.name + SUFFIX)


def _files(folder: Path) -> list[Path]:
    """Every file under a folder, in the order of their names. A link or anything else that is not a plain file or a
    folder is refused: a pack holds bytes, and what a link meant would be lost."""
    found = []
    for path in sorted(folder.rglob("*"), key=lambda p: p.relative_to(folder).as_posix()):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"{path} is not a plain file or a folder")
        if path.is_file():
            found.append(path)
    return found


def write(folder: Path) -> Path:
    """Write the pack of a folder beside it and read it back against the folder's bytes. The folder is left as it is.
    The same files give the same pack, byte for byte: names in order, no times, owners or modes of the machine."""
    folder = Path(folder)
    files = _files(folder)
    if not files:
        raise ValueError(f"{folder} holds no file")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=9, mtime=0, filename="") as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for path in files:
                info = tarfile.TarInfo(path.relative_to(folder).as_posix())
                info.size, info.mode = path.stat().st_size, 0o644
                with path.open("rb") as stream:
                    tar.addfile(info, stream)
    target = pack_of(folder)
    scratch = target.with_name(target.name + f".{os.getpid()}.tmp")
    try:
        with scratch.open("wb") as out:
            out.write(buffer.getvalue())
            out.flush()
            os.fsync(out.fileno())
        held = _load(scratch)
        if sorted(held) != [p.relative_to(folder).as_posix() for p in files]:
            raise ValueError(f"the pack of {folder} does not list the folder's files")
        for path in files:
            if held[path.relative_to(folder).as_posix()] != path.read_bytes():
                raise ValueError(f"the pack of {folder} differs from {path}")
        os.replace(scratch, target)
    finally:
        scratch.unlink(missing_ok=True)
    return target


def _load(pack: Path) -> dict[str, bytes]:
    held = {}
    with tarfile.open(pack, mode="r:gz") as tar:
        for member in tar:
            if not member.isfile():
                raise ValueError(f"{pack} holds {member.name}, which is not a plain file")
            if member.name in held:
                raise ValueError(f"{pack} holds {member.name} twice")
            held[member.name] = tar.extractfile(member).read()
    return held


@functools.lru_cache(maxsize=8)
def _cached(pack: str, size: int, changed: int) -> dict[str, bytes]:
    return _load(Path(pack))


def members(pack: Path) -> dict[str, bytes]:
    """The files a pack holds, by name. Read once for each state of the file."""
    stat = Path(pack).stat()
    return _cached(str(pack), stat.st_size, stat.st_mtime_ns)


def read(folder, name) -> bytes:
    """The bytes of the file `name` of an example's folder (or of a run's records): the file itself when it is there,
    else the member of the pack that stands for one of the folders above it. Refused, as `workflow.inside` refuses, when
    the name resolves outside the folder or neither holds it."""
    root = Path(folder).resolve()
    resolved = (Path(folder) / name).resolve()
    if root not in resolved.parents:
        raise refused(f"{name} resolves outside the example's folder")
    if resolved.is_file():
        return resolved.read_bytes()
    inner = PurePosixPath(resolved.relative_to(root).as_posix())
    for above in list(inner.parents)[:-1]:
        pack = root / (above.as_posix() + SUFFIX)
        if pack.is_file() and not pack.is_symlink():
            try:
                data = members(pack).get(inner.relative_to(above).as_posix())
            except (OSError, EOFError, tarfile.TarError, ValueError) as e:
                raise refused(f"{above.as_posix() + SUFFIX} cannot be read ({e})")
            if data is not None:
                return data
    raise refused(f"{name} does not exist")


def records(example: str) -> Path:
    found = sorted(EXAMPLES.glob(f"{example}-*/records")) if example.isdigit() else [Path(example)]
    if len(found) != 1 or not found[0].is_dir():
        raise SystemExit(f"no records folder for {example}")
    return found[0]


def loose(root: Path) -> list[Path]:
    """The folders named `cases` under a records folder."""
    return sorted(p for p in root.rglob(FOLDER) if p.is_dir() and not p.is_symlink())


def pack(root: Path) -> tuple[int, int, int]:
    """Pack every `cases` folder under a records folder and remove the folder once its pack reads back the same.
    A folder whose pack is already there is compared with it and removed only when they agree.
    Returns (folders packed, files they held, bytes of the packs)."""
    folders = files = size = 0
    for folder in loose(root):
        held = _files(folder)
        if not held:
            continue
        target = pack_of(folder)
        if target.exists():
            packed = _load(target)
            if sorted(packed) != [p.relative_to(folder).as_posix() for p in held] or any(
                    packed[p.relative_to(folder).as_posix()] != p.read_bytes() for p in held):
                raise SystemExit(f"{target} is there and differs from {folder}: neither was touched")
        else:
            target = write(folder)
        shutil.rmtree(folder)
        folders, files, size = folders + 1, files + len(held), size + target.stat().st_size
    return folders, files, size


def unpacked(root: Path) -> dict[str, str]:
    """Every file of a records folder as it would be with no pack, by name, with its SHA-256."""
    found = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.name == FOLDER + SUFFIX:
            for name, data in _load(path).items():
                found.setdefault(f"{rel[:-len(SUFFIX)]}/{name}", hashlib.sha256(data).hexdigest())
        else:
            found[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def differences(root: Path, original: Path) -> list[str]:
    """How a records folder, its packs opened, differs from an unpacked tree of the same records."""
    here = unpacked(root)
    there = {p.relative_to(original).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(original.rglob("*")) if p.is_file()}
    return ([f"missing here: {n}" for n in sorted(set(there) - set(here))]
            + [f"only here: {n}" for n in sorted(set(here) - set(there))]
            + [f"differs: {n}" for n in sorted(set(here) & set(there)) if here[n] != there[n]])


def budget(root: Path) -> tuple[list[str], list[str]]:
    """(errors, warnings) of one records folder against the rule. An error is settled by `pack`."""
    errors, warnings, files = [], [], 0
    name = root.parent.name
    for folder, _, held in os.walk(root):
        files += len(held)
        entries = len(os.listdir(folder))
        if entries > ENTRIES:
            warnings.append(f"{name}: {Path(folder).relative_to(root.parent).as_posix()} has {entries} entries "
                            f"(over {ENTRIES}, what a forge lists)")
    for folder in loose(root):
        count = sum(len(held) for _, _, held in os.walk(folder))
        if count > LOOSE_CASES:
            errors.append(f"{name}: {folder.relative_to(root.parent).as_posix()} holds {count} loose per-case files; "
                          f"run python3 examples/tools/targets/case_pack.py pack {name[:3]}")
    if files > FILES:
        warnings.append(f"{name}: records/ holds {files} files (over {FILES})")
    return errors, warnings


def over_budget(examples: Path = EXAMPLES) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for root in sorted(examples.glob("[0-9][0-9][0-9]-*/records")):
        if root.is_dir():
            e, w = budget(root)
            errors, warnings = errors + e, warnings + w
    return errors, warnings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("pack", "verify", "budget"):
        p = sub.add_parser(name)
        p.add_argument("examples", nargs="*" if name == "budget" else "+", help="example numbers")
        if name == "verify":
            p.add_argument("--against", help="a folder holding the same examples' records unpacked (examples/NNN-…/records)")
    args = parser.parse_args(argv)
    if args.command == "budget":
        if args.examples:
            found = [budget(records(e)) for e in args.examples]
            errors, warnings = sum((f[0] for f in found), []), sum((f[1] for f in found), [])
        else:
            errors, warnings = over_budget()
        for line in errors:
            print(f"ERROR {line}")
        for line in warnings:
            print(f"warn  {line}")
        print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1 if errors else 0
    status = 0
    for example in args.examples:
        root = records(example)
        if args.command == "pack":
            before = sum(len(held) for _, _, held in os.walk(root))
            folders, files, size = pack(root)
            after = sum(len(held) for _, _, held in os.walk(root))
            print(f"{root.parent.name}: {folders} folder(s) of {files} files packed into {size:,} bytes; "
                  f"records/ went from {before:,} files to {after:,}")
            continue
        packs = sorted(root.rglob(FOLDER + SUFFIX))
        held = sum(len(_load(p)) for p in packs)
        line = f"{root.parent.name}: {len(packs)} pack(s) read, {held:,} members"
        if args.against:
            original = Path(args.against) / "examples" / root.parent.name / "records"
            if not original.is_dir():
                raise SystemExit(f"{original} is not a folder")
            found = differences(root, original)
            line += f"; against {original}: {len(found)} difference(s)" if found else f"; equal to {original}, file for file"
            status = status or (1 if found else 0)
            for d in found[:20]:
                print(f"  {d}")
        print(line)
    return status


if __name__ == "__main__":
    sys.exit(main())
