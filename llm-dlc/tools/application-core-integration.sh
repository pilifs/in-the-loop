#!/usr/bin/env bash
# The integration check of llm-dlc/loops/application-core.md, run by
# run-streams.sh (its "- integration:" setting) from the workspace
# application-core-integration, on a merge of the four streams' latest commits,
# while they run. run-streams.sh reports a merge conflict itself, with the files
# in conflict; this script tells the other three outcomes apart, so the report
# says which one it was:
#   COMPILE FAILED   the merged library or its tests don't build;
#   CONTRACT FAILED  a test of the integration contract fails: each acceptance row
#                    either reaches its final verdict or stops with the named
#                    unsupported result its stream hasn't replaced yet
#                    (lib/tests/application_core.rs, written in Phase 0);
#   TESTS FAILED     a unit test, an earlier contract (foundations, compare,
#                    effects) or a Python suite fails: build.py's, and sync.py's
#                    review, run records and performance suites.
# Compiling and unit-level tests only: proofs and the combined fixture checks stay
# queued as jobs. It runs in a 3.5 GB scope, so cargo builds two jobs at a time.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export CARGO_BUILD_JOBS=${CARGO_BUILD_JOBS:-2}
MANIFEST=lib/Cargo.toml
CONTRACT=(--test application_core)
OTHERS=(--lib --test foundations --test compare --test effects)
[[ -f lib/tests/application_core.rs ]] || { echo "CONTRACT MISSING: lib/tests/application_core.rs (Phase 0 writes it)"; exit 1; }

echo "== build"
if ! cargo test --manifest-path "$MANIFEST" --no-run "${CONTRACT[@]}" "${OTHERS[@]}"; then
  echo "COMPILE FAILED"
  exit 1
fi
status=0
echo "== the integration contract"
cargo test --manifest-path "$MANIFEST" "${CONTRACT[@]}" -- --nocapture || { echo "CONTRACT FAILED"; status=1; }
run() { echo "== $*"; "$@" || { echo "TESTS FAILED: $*"; status=1; }; }
run cargo test --manifest-path "$MANIFEST" "${OTHERS[@]}"
run python3 examples/tools/test_build.py
run python3 llm-dlc/tools/test_review.py
run python3 llm-dlc/tools/test_runs.py
run python3 llm-dlc/tools/test_performance.py
exit $status
