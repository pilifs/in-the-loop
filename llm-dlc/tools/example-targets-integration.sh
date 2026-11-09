#!/usr/bin/env bash
# The integration check of llm-dlc/loops/example-targets.md, run by run-streams.sh
# (its "- integration:" setting) from the workspace example-targets-integration,
# on a merge of the four streams' latest commits, while they run. run-streams.sh
# reports a merge conflict itself, with the files in conflict; this script tells
# the other outcomes apart, so the report says which one it was:
#   CONTRACT FAILED  a test of the integration contract fails: each Tier A row
#                    either reaches its final outcome on the fixtures or stops at
#                    the named Phase 0 stub its stream hasn't replaced yet
#                    (examples/tools/test_targets_contract.py, written in Phase 0;
#                    a stop is a skip, listed with the stub's name);
#   TESTS FAILED     a suite fails: examples/tools/targets/ (the streams' and the
#                    coordinator's tests), build.py's, pipeline.py's, or a sidecar
#                    in the tree that doesn't validate offline.
# Offline and local: nothing is downloaded and no upstream code is built; the
# fixture JARs are compiled from the fixture sources. Proofs and upstream builds
# stay queued as jobs. It runs in a 3.5 GB scope.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
CONTRACT=examples/tools/test_targets_contract.py
[[ -f "$CONTRACT" ]] || { echo "CONTRACT MISSING: $CONTRACT (Phase 0 writes it)"; exit 1; }

status=0
echo "== the integration contract"
python3 "$CONTRACT" -v 2>&1 || { echo "CONTRACT FAILED"; status=1; }
run() { echo "== $*"; "$@" || { echo "TESTS FAILED: $*"; status=1; }; }
run python3 -m unittest discover -s examples/tools/targets -t examples/tools -p 'test_*.py'
run python3 examples/tools/test_build.py
run python3 verification/test_pipeline.py
# Every sidecar in the tree, validated offline (build.py reads each example, and its sidecar with it).
run bash -c 'python3 examples/tools/build.py --plan >/dev/null'
exit $status
