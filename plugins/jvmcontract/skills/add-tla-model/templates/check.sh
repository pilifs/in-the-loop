#!/usr/bin/env bash
# Checks the TLA+ model of this module against the code: derives the kernel's behavioural contract from the compiled
# classes, fails if it differs from the committed one (a change in what the kernel decides is reviewed as a contract
# diff, then recorded with `check.sh --update`), regenerates the TLA+ operator from it, and runs TLC on the model.
#
#   bash spec/check.sh            check; exit 1 on a changed contract, a violated invariant or no verdict
#   bash spec/check.sh --update   accept the current behaviour: rewrite the contract, then check
#
# Needs jvmcontract on the PATH (cargo install --git https://github.com/pilifs/in-the-loop --locked jvmcontract) and
# TLC: tla2tools.jar in ~/tools or $TLA2TOOLS_JAR, or tlc on the PATH. Written by the /add-tla-model skill.
set -euo pipefail
cd "$(dirname "$0")/.."

# ---- filled in by the skill ----------------------------------------------------------------------------------------
CLASSES="build/classes/java/main"                       # the module's compiled main classes (PATH-separated if several)
CLASSPATH=""                                            # the module's dependencies, PATH-separated, if the kernel needs them
TARGET="com.example.orders.OrderLifecycle#decide"       # the kernel
CONTRACT="spec/OrderLifecycle.decide.contract"          # its committed behavioural contract
OPERATOR="spec/OrderLifecycleContract.tla"              # the generated TLA+ operator (do not edit)
SPEC="spec/Orders.tla"                                  # the model; Orders.cfg sits next to it
DEADLOCK=""                                             # "--deadlock" to also report states where nothing can move
# -------------------------------------------------------------------------------------------------------------------

update=
[ "${1:-}" = "--update" ] && update=1

command -v jvmcontract >/dev/null || { echo "check.sh: jvmcontract not found: cargo install --git https://github.com/pilifs/in-the-loop --locked jvmcontract" >&2; exit 2; }
for dir in ${CLASSES//:/ }; do
  [ -d "$dir" ] || { echo "check.sh: $dir does not exist: compile the module first" >&2; exit 2; }
done

cp_args=()
[ -n "$CLASSPATH" ] && cp_args=(--classpath "$CLASSPATH")

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
jvmcontract derive "$TARGET" --classes "$CLASSES" "${cp_args[@]}" > "$tmp"

if [ -n "$update" ] || [ ! -f "$CONTRACT" ]; then
  cp "$tmp" "$CONTRACT"
  echo "check.sh: wrote $CONTRACT"
elif ! diff -u "$CONTRACT" "$tmp"; then
  echo >&2
  echo "check.sh: $TARGET no longer behaves as $CONTRACT says (the diff above, as the code decides it now)." >&2
  echo "          Review it like an API change; if it is intended, run: bash spec/check.sh --update" >&2
  exit 1
fi

jvmcontract tla "$CONTRACT" "$OPERATOR"
jvmcontract tlc "$SPEC" $DEADLOCK
