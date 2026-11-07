#!/usr/bin/env bash
# The integration check of llm-dlc/loops/cleanup.md, run by run-streams.sh (its
# "- integration:" setting) from the workspace integration, on a merge of the
# three streams' latest commits, while they run. Compiling and unit-level tests
# only, of the files the streams change: the library's unit tests, the
# integration contract and the joint run's tests, and the Python suites of
# build.py, the benchmark and sync.py. Proofs stay queued as jobs. It runs in a
# 3.5 GB scope, so cargo builds two jobs at a time.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export CARGO_BUILD_JOBS=${CARGO_BUILD_JOBS:-2}
status=0
run() { echo "== $*"; "$@" || { echo "FAILED: $*"; status=1; }; }
run cargo test --manifest-path lib/Cargo.toml --lib --test foundations --test compare --test effects
run python3 examples/tools/test_build.py
run python3 lib/benchmark/test_run.py
run python3 llm-dlc/tools/test_review.py
exit $status
