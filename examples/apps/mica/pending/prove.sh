#!/usr/bin/env bash
# Runs the regression proof of one patch in this directory against the committed ModifiedUtf8#encodeInto.
#
# Usage: prove.sh PATCH [MAX_ARRAY_LENGTH] [UNWIND]
# The defaults, 8 and 16, are the proof that is waiting for a larger machine: see README.md.
# TIMEOUT sets the seconds per JBMC run, and JVMCONTRACT_JBMC_MEMORY_MB its memory limit.
# Exits 0 if the versions are proved equal, and 1 if they differ or there is no verdict.
set -euo pipefail

patch=$(realpath "$1")
length=${2:-8}
unwind=${3:-16}
cd "$(dirname "$0")/.."

JVMCONTRACT="${JVMCONTRACT:-$(command -v jvmcontract || echo ../../../lib/target/release/jvmcontract)}"
JVMCONTRACT=$(realpath "$JVMCONTRACT")

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

source=src/main/java/net/terminalvalue/mica/classfile/ModifiedUtf8.java
mkdir -p "$work/patched/$(dirname "$source")"
cp "$source" "$work/patched/$source"
patch --quiet --directory="$work/patched" -p1 < "$patch"

javac -parameters -g -proc:none -d "$work/before" "$source"
javac -parameters -g -proc:none -d "$work/after" "$work/patched/$source"

"$JVMCONTRACT" equivalence --before "$work/before" --after "$work/after" \
  --target 'net.terminalvalue.mica.classfile.ModifiedUtf8#encodeInto' \
  --max-array-length "$length" --unwind "$unwind" --timeout "${TIMEOUT:-3600}"
