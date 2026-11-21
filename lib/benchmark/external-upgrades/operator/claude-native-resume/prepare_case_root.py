"""Build the resume profile's case launchers without changing any original pinned JVM or checker bytes."""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import isolation  # noqa: E402


def build(original, output):
    source = original / "root"
    known = json.loads((original / "manifest.json").read_bytes())
    if isolation.tree(source) != known:
        raise ValueError("original V0 tool root does not match its manifest")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    root = output / "root"

    def copy(src, dest):
        try:
            os.link(src, dest)
        except OSError:
            shutil.copy2(src, dest)

    shutil.copytree(source, root, symlinks=True, copy_function=copy)
    bins = root / "opt/jdks/21-tem/bin"
    hashes = {}
    for name in ("java", "javac", "jar", "javap"):
        entry = bins / name
        raw = bins / (".v0-" + name)
        entry.rename(raw)
        hashes[name] = {"temurinBinarySha256": isolation.digest(raw)}
        flag = "-D" if name == "java" else "-J-D"
        # Keep the real launcher in the same JDK bin directory: java.home still leads children through these wrappers.
        wrapper = (
            """#!/bin/sh
TMPDIR=/case/work/tmp
export TMPDIR
want=-Djava.io.tmpdir=/case/work/tmp
argfile_override=
for arg do
    case "$arg" in
        @*)
            file=${arg#@}
            if [ -r "$file" ]; then
                while IFS= read -r line || [ -n "$line" ]; do
                    case "$line" in *-Djava.io.tmpdir=*) argfile_override=1; break;; esac
                done < "$file"
            fi ;;
        -Djava.io.tmpdir=*|-J-Djava.io.tmpdir=*)
            if [ "$arg" != "$want" ] && [ "$arg" != "-J$want" ]; then
                echo 'The case JDK requires java.io.tmpdir=/case/work/tmp' >&2
                exit 2
            fi ;;
    esac
done
# HotSpot processes _JAVA_OPTIONS after command-line properties. Preserve unrelated flags and override only a conflicting temporary directory.
case "${_JAVA_OPTIONS-}" in *-Djava.io.tmpdir=*) argfile_override=1;; esac
if [ -n "$argfile_override" ]; then
    _JAVA_OPTIONS="${_JAVA_OPTIONS:+$_JAVA_OPTIONS }$want"
    export _JAVA_OPTIONS
fi
"""
            + f'exec /opt/jdks/21-tem/bin/.v0-{name} {flag}java.io.tmpdir=/case/work/tmp "$@"\n'
        )
        entry.write_text(wrapper)
        entry.chmod(0o755)
        hashes[name]["wrapperSha256"] = isolation.digest(entry)
    (output / "manifest.json").write_bytes(isolation.canonical(isolation.tree(root)))
    record = {
        "sourceRootSha256": isolation.digest(original / "manifest.json"),
        "toolRootSha256": isolation.digest(output / "manifest.json"),
        "launchers": hashes,
    }
    (output / "java-launchers.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-product", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(build(args.base_product.resolve(), args.output.resolve()), indent=2))
