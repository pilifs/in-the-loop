#!/usr/bin/env bash
# VF-018's triage (verification/findings.md), run by a pipeline job from the repository root: why JBMC does not
# finish H5's regression proof of objects.Kernel#price under a correspondence (lib/tests/heap.rs, the output
# relations test, its first case), and whether a smaller bound lets it. It changes no test and no expectation.
#
# 1. Runs the ignored test with JBMC behind a wrapper that records each command line, and a 120 s limit per run:
#    the test is expected to fail; what matters is the commands and the harness it leaves in its work directory.
# 2. Takes the first proof command (one with --trace) of the first case, objects.Kernel#price under --engine jbmc,
#    and measures what it is given: the harness's classes and the goto program's size.
# 3. Reruns that command with JBMC's statistics (--verbosity 8, without --json-ui), each run under a 900 s limit:
#    as given, then at smaller --unwind bounds, then as given with --slice-formula.
#
# Everything goes to lib/target/vf018/; summary.txt has the numbers, and is printed at the end.
set -uo pipefail
out=lib/target/vf018
rm -rf "$out"
mkdir -p "$out/bin" "$out/argv" "$out/runs"
abs=$(cd "$out" && pwd)
real=$(command -v jbmc) || { echo "no jbmc on PATH"; exit 1; }
cat > "$out/bin/jbmc" <<EOF
#!/usr/bin/env bash
printf '%s\\0' "\$@" > "$abs/argv/\$(date +%s%N).argv"
exec "$real" "\$@"
EOF
chmod +x "$out/bin/jbmc"
summary="$out/summary.txt"
echo "VF-018 triage, $(date -u +%FT%TZ), $("$real" --version 2>&1 | head -1)" > "$summary"

echo "== 1. the output relations test, JBMC recorded, 120 s per run"
start=$(date +%s)
(cd lib && PATH="$abs/bin:$PATH" JVMCONTRACT_HEAP_TIME_LIMIT=120 cargo test --release --test heap -- --ignored --exact \
  the_output_relations_have_the_same_verdicts_under_jbmc_and_auto_confirm --nocapture) > "$out/test.log" 2>&1
echo "test exit $? after $(( $(date +%s) - start )) s, $(ls "$out/argv" | wc -l) JBMC command(s) recorded" | tee -a "$summary"
grep -E '^(Jbmc|Auto) confirm=' "$out/test.log" | cut -c1-200 | tee -a "$summary"

echo "== 2. the first proof command and what it is given"
proof=$(python3 - "$out/argv" <<'PY'
import sys, pathlib
for f in sorted(pathlib.Path(sys.argv[1]).glob("*.argv")):
    args = f.read_bytes().split(b"\0")[:-1]
    if b"--trace" in args:
        print(f)
        break
PY
)
[ -n "$proof" ] || { echo "no proof command was recorded" | tee -a "$summary"; cat "$summary"; exit 1; }
mapfile -d '' -t cmd < "$proof"
printf '%q ' jbmc "${cmd[@]}" > "$out/proof-command.txt"; echo >> "$out/proof-command.txt"
echo "proof command: $(cat "$out/proof-command.txt")" | cut -c1-2000 | tee -a "$summary"
cp_arg=""; class="${cmd[0]}"; given_unwind=""
for ((i = 0; i < ${#cmd[@]}; i++)); do
  [ "${cmd[i]}" = "--classpath" ] && cp_arg="${cmd[i+1]}"
  [ "${cmd[i]}" = "--unwind" ] && given_unwind="${cmd[i+1]}"
done
echo "harness class $class, --unwind $given_unwind" | tee -a "$summary"
IFS=: read -ra entries <<< "$cp_arg"
for e in "${entries[@]}"; do
  [ -d "$e" ] && echo "class path entry $e: $(find "$e" -name '*.class' | wc -l) classes, $(du -sk "$e" | cut -f1) KiB" | tee -a "$summary"
done
if javap -c -p -cp "$cp_arg" "$class" > "$out/harness.javap" 2>&1; then
  echo "harness bytecode: $(grep -cE '^ +[0-9]+: ' "$out/harness.javap") instructions over $(grep -cE '^  [a-z].*\(' "$out/harness.javap") methods" | tee -a "$summary"
else
  echo "javap could not read $class" | tee -a "$summary"
fi
plain=()
for a in "${cmd[@]}"; do [ "$a" = "--json-ui" ] || plain+=("$a"); done
timestamps=() # drop "--timestamp monotonic", which only --json-ui reads
for ((i = 0; i < ${#plain[@]}; i++)); do
  if [ "${plain[i]}" = "--timestamp" ]; then i=$((i + 1)); continue; fi
  timestamps+=("${plain[i]}")
done
plain=("${timestamps[@]}")
goto=$(timeout 300 "$real" "${plain[@]}" --show-goto-functions 2>/dev/null | wc -l)
echo "goto program: $goto lines (--show-goto-functions)" | tee -a "$summary"

echo "== 3. the proof with statistics, 900 s each"
with_unwind() { local u=$1; shift; local r=(); for ((i = 0; i < ${#plain[@]}; i++)); do
  if [ "${plain[i]}" = "--unwind" ]; then r+=(--unwind "$u"); i=$((i + 1)); else r+=("${plain[i]}"); fi; done; printf '%s\0' "${r[@]}" "$@"; }
variant() {
  local name=$1; shift
  local s=$(date +%s)
  timeout 900 "$real" "$@" --verbosity 8 > "$out/runs/$name.log" 2>&1
  local code=$? took=$(( $(date +%s) - s ))
  local verdict=$(grep -oE 'VERIFICATION (SUCCESSFUL|FAILED)' "$out/runs/$name.log" | tail -1)
  [ $code -eq 124 ] && verdict="did not finish in 900 s"
  echo "-- $name: ${verdict:-exit $code} after $took s" | tee -a "$summary"
  grep -E 'size of program expression|Generated [0-9]+ VCC|variables, [0-9]+ clauses|Runtime (Symex|Convert SSA|Post-process|Solver|decision procedure)|unwinding assertion|Not unwinding' "$out/runs/$name.log" \
    | sort | uniq -c | sort -rn | head -12 | tee -a "$summary"
}
mapfile -d '' -t v < <(printf '%s\0' "${plain[@]}"); variant "as-given-unwind-$given_unwind" "${v[@]}"
for u in 8 4 2; do
  [ -n "$given_unwind" ] && [ "$u" -ge "$given_unwind" ] && continue
  mapfile -d '' -t v < <(with_unwind "$u"); variant "unwind-$u" "${v[@]}"
done
mapfile -d '' -t v < <(printf '%s\0' "${plain[@]}" --slice-formula); variant "as-given-slice-formula" "${v[@]}"
echo "== summary"
cat "$summary"
