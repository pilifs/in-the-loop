#!/usr/bin/env bash
# The integration check of llm-dlc/loops/foundations.md, run by run-streams.sh
# (its "- integration:" setting) from the workspace integration, on a merge of
# the four streams' latest commits, while they run. It runs the integration
# contract's tests, lib/tests/foundations.rs, written in the brief's Phase 0:
# each part of the joint example either reaches its final verdict or stops
# with the named unsupported result its stream hasn't replaced yet. Anything
# else fails, and each stream reads the report at the start of every cycle.
# Compiling and unit-level tests only: proofs stay queued as jobs.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
exec cargo test --manifest-path lib/Cargo.toml --test foundations -- --nocapture
