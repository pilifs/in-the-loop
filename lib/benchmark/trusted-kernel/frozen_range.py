"""Immutable sources and published file inventory of the original int-range checker."""

from functools import lru_cache
import gzip
from io import BytesIO
import json
from pathlib import Path
import tarfile

from prepare import HERE, digest
from replay import build_kernel

ARCHIVE = HERE / "snapshots/range-inputs.tar.gz"
ARCHIVE_SHA = "ddf5ad4e94e673f71f5aaf2518a96cdb166b4ec444e8e3b084c2454ec365dca7"
INT_BINARY = "635cc9433ada216c0f065c10d823c2b4d3f1cc67f5e9354de9151995f9604da1"
LONG_BINARY = "5591785151ac8237e35c3bfdbe8c5eea25e7f5c5df1e5f4206d0e626a6ab65a5"
LONG_RULE = "24ad23e10d198b6fb9e6f879bdc511db338c60b40255876aa0576ee1a317f32f"
KERNEL_PATH = Path("lib/benchmark/trusted-kernel")


@lru_cache(maxsize=1)
def _snapshot():
    raw = ARCHIVE.read_bytes()
    if digest(raw) != ARCHIVE_SHA:
        raise ValueError("frozen int-range source archive")
    with tarfile.open(fileobj=BytesIO(raw), mode="r:gz") as archive:
        return {item.name: archive.extractfile(item).read() for item in archive.getmembers()}


def historical_manifest():
    return json.loads(_snapshot()["bundle.json"])


def historical_files():
    paths = {k.removeprefix(str(KERNEL_PATH) + "/"): v for k, v in _snapshot().items()
             if k.startswith(str(KERNEL_PATH) + "/")}
    paths["../../src/digest.rs"] = _snapshot()["lib/src/digest.rs"]
    return paths


def _build_frozen(folder, expected, sources):
    source = folder / KERNEL_PATH
    for name, data in sources.items():
        if not name.endswith(".rs"):
            continue
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    binary, build = build_kernel(folder, source)
    if build["binarySha256"] != expected:
        raise ValueError("rebuilt range checker differs from its frozen executable " + expected)
    return binary


def int_kernel(folder):
    return _build_frozen(folder, INT_BINARY, historical_files())


def long_kernel(folder):
    rule = gzip.decompress((HERE / "snapshots/jdk-long-range.rs.gz").read_bytes())
    if digest(rule) != LONG_RULE:
        raise ValueError("frozen long-range induction rule")
    return _build_frozen(folder, LONG_BINARY, {**historical_files(), "range.rs": rule})
