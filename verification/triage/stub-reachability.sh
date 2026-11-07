#!/usr/bin/env bash
# Step 1 of llm-dlc/loops/stub-reachability.md, run by a pipeline job from the repository root: can JBMC's solver,
# not its symbolic execution alone, show that a proof never enters a stub, and at what cost next to the proof?
# The case is VF-015's (verification/findings.md): `prove Hex#toDigit --assume 'ch == 1632' --assert 'result == 0'`
# on commons-codec's old Hex (87f6aa28), which JBMC proves but whose preflight counts JBMC's stub of
# String.format(String, Object[]) as entered, called by DecoderException(String, Object...) on toDigit's exception
# path, which ch == 1632 makes infeasible. It changes nothing in the repository.
#
# 1. Clones and compiles the old commons-codec, and a copy of DecoderException whose call of String.format first
#    calls a probe, Reach.reach, that fails an assertion of its own (`throw new AssertionError()`, which JBMC
#    takes as an assertion, as jvmcontract's GapIntrinsics.open does).
# 2. Runs VF-015's step 3 unchanged, with --work kept, JBMC behind a wrapper that records each command line, its
#    exit and its seconds; and a control: the same proof without the --assume, where the exception path is open.
# 3. For the case and the control, on the harness each left and the last proof command (--trace) each ran, with any
#    input interval stage dropped, so that it is over every input as the proof's last run is:
#    A. --cover location in place of --unwinding-assertions and --trace: which goals of DecoderException's
#       constructor, String.format's stub and toDigit are covered; then the same with --property on the
#       constructor's first goal alone, to measure what one goal costs;
#    B. the proof command as given, with the probe's class directory second on the class path, after the harness:
#       the probe's assertion fails if and only if a path within the bounds reaches the call.
#
# Everything goes to lib/target/stub-reach/; summary.txt has the outcomes and the times, and is printed at the end.
set -uo pipefail
out=lib/target/stub-reach
rm -rf "$out"
mkdir -p "$out/bin" "$out/argv"
abs=$(cd "$out" && pwd)
real=$(command -v jbmc) || { echo "no jbmc on PATH"; exit 1; }
cat > "$out/bin/jbmc" <<EOF
#!/usr/bin/env bash
id=\$(date +%s%N)
printf '%s\\0' "\$@" > "$abs/argv/\$id.argv"
start=\$(date +%s%N)
"$real" "\$@"
status=\$?
echo "\$status \$(( (\$(date +%s%N) - start) / 1000000 ))ms" > "$abs/argv/\$id.done"
exit \$status
EOF
chmod +x "$out/bin/jbmc"
summary="$out/summary.txt"
say() { echo "$*" | tee -a "$summary"; }
since() { echo "$(( ($(date +%s%N) - $1) / 1000000 )) ms"; }
echo "stub reachability experiment, $(date -u +%FT%TZ), $("$real" --version 2>&1 | head -1)" > "$summary"

echo "== 1. clone and compile"
(cd "$out" && git clone -q --filter=blob:none https://github.com/apache/commons-codec codec && git -C codec worktree add -q ../base 87f6aa28) || { say "clone failed"; exit 1; }
src="$out/base/src/main/java"
mkdir -p "$out/base-classes" "$out/probe-src/org/apache/commons/codec" "$out/probe-classes"
javac -proc:none -parameters -g -nowarn -d "$out/base-classes" $(find "$src" -name '*.java') || { say "compile failed"; exit 1; }
sed 's/super(String\.format(message, args));/super(String.format(Reach.reach(message), args));/' \
  "$src/org/apache/commons/codec/DecoderException.java" > "$out/probe-src/org/apache/commons/codec/DecoderException.java"
grep -q 'Reach.reach(message)' "$out/probe-src/org/apache/commons/codec/DecoderException.java" || { say "the probe could not be patched in: DecoderException's String.format call differs"; exit 1; }
cat > "$out/probe-src/org/apache/commons/codec/Reach.java" <<'EOF'
package org.apache.commons.codec;

final class Reach {
    static String reach(final String message) {
        throw new AssertionError();
    }
}
EOF
javac -proc:none -parameters -g -nowarn -cp "$out/base-classes" -d "$out/probe-classes" $(find "$out/probe-src" -name '*.java') || { say "the probe does not compile"; exit 1; }
say "probe: $(grep -n 'Reach.reach' "$out/probe-src/org/apache/commons/codec/DecoderException.java")"

# The JBMC commands one jvmcontract run recorded, from the file names `first` and `last` (by time).
commands_of() { find "$abs/argv" -name '*.argv' -newer "$1" ! -newer "$2" | sort; }
describe() {
  local f=$1 kind=other
  local args; args=$(tr '\0' ' ' < "$f")
  case " $args " in
    *" --show-goto-functions "*) kind=listing ;;
    *" --program-only "*) kind=symbolic ;;
    *" --trace "*) kind=proof ;;
  esac
  local done="${f%.argv}.done"
  echo "$kind exit=$(cut -d' ' -f1 "$done" 2>/dev/null) time=$(cut -d' ' -f2 "$done" 2>/dev/null)"
}

prove() { # name, extra jvmcontract arguments...
  local name=$1; shift
  touch "$out/$name.begin"; sleep 0.01
  local start; start=$(date +%s%N)
  (cd "$out" && PATH="$abs/bin:$PATH" jvmcontract prove 'org.apache.commons.codec.binary.Hex#toDigit' --classes base-classes "$@" --timeout 300 --work "work-$name") > "$out/$name.log" 2>&1
  local status=$?
  sleep 0.01; touch "$out/$name.end"
  say "-- $name: jvmcontract exit $status in $(since "$start"); its last lines:"
  tail -n 4 "$out/$name.log" | cut -c1-400 | sed 's/^/   /' | tee -a "$summary"
  for f in $(commands_of "$out/$name.begin" "$out/$name.end"); do say "   jbmc $(describe "$f")"; done
}

echo "== 2. VF-015's step 3, unchanged, and the control"
say "== 2. the proofs (case: --assume 'ch == 1632'; control: no --assume)"
prove case --assume 'ch == 1632' --assert 'result == 0'
prove control --assert 'result == 0'

# The last proof command a run recorded, with `--java-assume-inputs-interval X` dropped, rewritten by `mode`.
rewrite() { # argv file, mode (cover | probe), [property]
  python3 - "$@" <<'PY'
import sys
argv = open(sys.argv[1], "rb").read().split(b"\0")[:-1]
args = [a.decode() for a in argv]
mode = sys.argv[2]
out, skip = [], 0
drop_with_value = {"--java-assume-inputs-interval", "--timestamp"}
drop = {"--json-ui", "--trace"}
if mode == "cover":
    drop |= {"--unwinding-assertions"}
for i, a in enumerate(args):
    if skip:
        skip -= 1
        continue
    if a in drop_with_value:
        skip = 1
        continue
    if a in drop:
        continue
    out.append(a)
if mode == "cover":
    out += ["--cover", "location"]
    if len(sys.argv) > 3:
        out += ["--property", sys.argv[3]]
if mode == "probe":
    i = out.index("--classpath")
    entries = out[i + 1].split(":")
    out[i + 1] = ":".join(entries[:1] + [sys.argv[3]] + entries[1:])
sys.stdout.write("\0".join(out) + "\0")
PY
}

run_variant() { # label, file, argv...
  local label=$1 file=$2; shift 2
  local start; start=$(date +%s%N)
  (cd "$out" && timeout 300 "$real" "$@") > "$file" 2>&1
  local status=$?
  say "   $label: jbmc exit $status in $(since "$start") ($file)"
}

ctor='DecoderException.<init>:(Ljava/lang/String;[Ljava/lang/Object;)V'
format='java.lang.String.format:(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;'
for name in case control; do
  say "== 3. $name"
  proof=$(for f in $(commands_of "$out/$name.begin" "$out/$name.end"); do grep -qz -- '^--trace$' "$f" && echo "$f"; done | tail -n 1)
  [ -n "$proof" ] || { say "   no proof command was recorded"; continue; }
  printf '%q ' jbmc $(tr '\0' '\n' < "$proof") > "$out/$name-proof-command.txt"
  say "   proof command: $(cut -c1-1500 "$out/$name-proof-command.txt")"

  mapfile -d '' -t cmd < <(rewrite "$proof" cover)
  run_variant "A. --cover location" "$out/$name-cover.txt" "${cmd[@]}"
  say "   A. $(grep -E '^\*\* [0-9]+ of [0-9]+ covered' "$out/$name-cover.txt" | head -1)"
  say "   A. the goals of DecoderException(String, Object...), String.format's stub and toDigit:"
  grep -F -e "$ctor" -e "$format" -e 'Hex.toDigit:' "$out/$name-cover.txt" | grep -E 'SATISFIED|FAILED' | cut -c1-400 | sed 's/^/      /' | tee -a "$summary"
  [ -n "$(grep -F -e "$format" "$out/$name-cover.txt" | grep -E 'SATISFIED|FAILED')" ] || say "      (no goal of String.format's stub is listed)"
  goal=$(grep -F -e "$ctor" "$out/$name-cover.txt" | grep -E 'SATISFIED|FAILED' | head -1 | sed -n 's/^\[\([^]]*\)\].*/\1/p')
  if [ -n "$goal" ]; then
    mapfile -d '' -t cmd < <(rewrite "$proof" cover "$goal")
    run_variant "A'. --cover location --property $goal" "$out/$name-cover-one.txt" "${cmd[@]}"
    say "   A'. $(grep -F -e "$goal" "$out/$name-cover-one.txt" | grep -E 'SATISFIED|FAILED' | head -1 | cut -c1-400)"
  else
    say "   A'. not run: no goal of the constructor to name"
  fi

  mapfile -d '' -t cmd < <(rewrite "$proof" probe "$abs/probe-classes")
  run_variant "B. the proof with the probe" "$out/$name-probe.txt" "${cmd[@]}"
  say "   B. $(grep -E '^VERIFICATION (SUCCESSFUL|FAILED)' "$out/$name-probe.txt" | head -1)"
  say "   B. the probe's and the harness's properties:"
  grep -E '^\[.*\] .*: (SUCCESS|FAILURE)' "$out/$name-probe.txt" | grep -F -e 'Reach.reach' -e 'PropertyHarness' | cut -c1-400 | sed 's/^/      /' | tee -a "$summary"
done

echo "== summary"
cat "$summary"
