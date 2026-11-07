#!/usr/bin/env bash
# VF-010's reproducer (verification/findings.md): the own checker's regression proof of the rounding refactor of
# `fixtures.Pricing#total`, the one `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` makes, run 8 times
# alike. The refactor changes behaviour, so each run should find the violation (exit 1). While the branch probes are
# budgeted by wall-clock time, which side of a branch is left undecided depends on the machine's speed, and some runs
# take another path order and run out of time.
#
# Usage: vf-010.sh WORK [RUNS] [TIMEOUT]. Needs javac and jvmcontract on PATH. Prints one line per run (exit code,
# seconds, the own checker's numbers) and the end of the report of any run that did not find the violation, keeps
# the same in WORK/summary.txt, and exits 0 when every run gave the violation, 1 otherwise.
set -u
work=${1:?usage: vf-010.sh WORK [RUNS] [TIMEOUT]}
runs=${2:-8}
timeout=${3:-40}
mkdir -p "$work/src-before/fixtures" "$work/src-after/fixtures"
# Kept as lib/tests/integration.rs has them: PRICING_BEFORE, and the refactor that rounds the unit price first.
cat > "$work/src-before/fixtures/Pricing.java" <<'JAVA'
package fixtures;
public final class Pricing {
    public static long total(long priceCents, int seats) {
        if (priceCents < 0 || seats < 0) throw new IllegalArgumentException("negative");
        long total = Math.multiplyExact(priceCents, seats);
        return seats >= 6 ? total - total / 10 : total;
    }
}
JAVA
cat > "$work/src-after/fixtures/Pricing.java" <<'JAVA'
package fixtures;
public final class Pricing {
    public static long total(long priceCents, int seats) {
        if (priceCents < 0 || seats < 0) throw new IllegalArgumentException("negative");
        long unit = seats >= 6 ? priceCents - priceCents / 10 : priceCents;
        return Math.multiplyExact(unit, seats);
    }
}
JAVA
for v in before after; do
  rm -rf "$work/$v" && javac -g -parameters -d "$work/$v" "$work/src-$v/fixtures/Pricing.java" || exit 2
done
: > "$work/summary.txt"
found=0
for i in $(seq 1 "$runs"); do
  rm -rf "$work/run-$i"
  start=$(date +%s%N)
  jvmcontract equivalence --before "$work/before" --after "$work/after" --target 'fixtures.Pricing#total' \
    --engine native --timeout "$timeout" --work "$work/run-$i" > "$work/run-$i.log" 2>&1
  code=$?
  took=$(awk -v a="$start" -v b="$(date +%s%N)" 'BEGIN { printf "%.1f", (b - a) / 1e9 }')
  numbers=$(grep -h -o '[A-Za-z]*: [0-9]* paths, .*' "$work/run-$i.log" "$work/run-$i"/*.log 2>/dev/null | head -1)
  printf 'run %d: exit %d, %s s, %s\n' "$i" "$code" "$took" "${numbers:-no numbers}" | tee -a "$work/summary.txt"
  if [[ $code -eq 1 ]]; then
    found=$((found + 1))
  else
    tail -n 15 "$work/run-$i.log" | sed 's/^/    /' | tee -a "$work/summary.txt"
  fi
done
echo "$found of $runs runs found the violation" | tee -a "$work/summary.txt"
[[ $found -eq $runs ]]
