#!/usr/bin/env bash
# VF-023's diagnosis (verification/findings.md), run by a pipeline job from the repository root: why does JBMC,
# on lib/models' immutable lists, refute that a one-element List.of has size 1, where the JVM, the interpreter, the
# tool's own checker and the models themselves run on a JVM (conformance.rs's
# the_models_only_jbmc_runs_agree_with_the_jvm) all give 1? The corpus's listSizes(n=1) and listChange(n=0) are
# the two claims, and every other list claim JBMC decides agrees with the JVM: a two-element List12's size, a
# one-element one's get(0), and EMPTY_LIST's identity included. A one-element List12 stores the static sentinel
# ImmutableCollections.EMPTY as its second element, and size() is `e1 != EMPTY ? 2 : 1`.
#
# Three probes, each a property proof with JBMC alone (--engine jbmc, --work kept):
#   one          List.of(new Object()).size() == 1            the corpus's case, reduced
#   oneAfterInit List.of() first, then the same                ImmutableCollections initialized before List12 runs
#   two          List.of(new Object(), new Object()).size() == 2   the control, which JBMC proves in the corpus
# On a JVM the three return 1, 1 and 2 (printed first). For each, the steps of JBMC's counterexample trace that
# assign ImmutableCollections' statics, a List12's e1, or a class's initialization flag go to NAME-trace.txt.
# It changes nothing in the repository. Everything goes to lib/target/vf023/; summary.txt has the outcomes.
set -uo pipefail
out=lib/target/vf023
rm -rf "$out"
mkdir -p "$out/src/probe" "$out/classes"
summary="$out/summary.txt"
say() { echo "$*" | tee -a "$summary"; }
echo "VF-023 diagnosis, $(date -u +%FT%TZ), $(jbmc --version 2>&1 | head -1), $(jvmcontract --version 2>&1 | head -1)" > "$summary"

cat > "$out/src/probe/Probe.java" <<'EOF'
package probe;

import java.util.List;

public final class Probe {
    private Probe() {
    }

    public static int one(int n) {
        return List.of(new Object()).size();
    }

    public static int oneAfterInit(int n) {
        List<Object> empty = List.of();
        return List.of(new Object()).size() + empty.size();
    }

    public static int two(int n) {
        return List.of(new Object(), new Object()).size();
    }

    public static void main(String[] args) {
        System.out.println(one(0) + " " + oneAfterInit(0) + " " + two(0));
    }
}
EOF
javac -proc:none -parameters -g -d "$out/classes" "$out/src/probe/Probe.java" || { say "compile failed"; exit 1; }
say "on the JVM (one, oneAfterInit, two): $(java -cp "$out/classes" probe.Probe)"

# The trace steps of JBMC's first failed property that touch the sentinel, a List12's e1 or class initialization.
cat > "$out/trace.py" <<'EOF'
import json, re, sys
log, name = sys.argv[1], sys.argv[2]
text = open(log).read()
try:
    messages = json.loads(text[text.index("["):])
except Exception as e:
    print(f"{name}: jbmc.log is not JSON ({e})")
    sys.exit(0)
wanted = re.compile(r"ImmutableCollections|e1\b|clinit|already_initialized|EMPTY", re.I)
for m in messages:
    for r in m.get("result", []) if isinstance(m, dict) else []:
        if r.get("status") != "FAILURE":
            continue
        print(f"{name}: FAILURE of {r.get('property')}: {r.get('description')}")
        for s in r.get("trace", []):
            if s.get("hidden"):
                continue
            where = s.get("sourceLocation", {})
            loc = f"{where.get('function', '')}:{where.get('line', '')}"
            if s.get("stepType") == "assignment" and wanted.search(str(s.get("lhs", ""))):
                print(f"  {loc}  {s.get('lhs')} = {json.dumps(s.get('value'))[:160]}")
            elif s.get("stepType") == "function-call" and wanted.search(str(s.get("function", {}).get("identifier", ""))):
                print(f"  {loc}  call {s.get('function', {}).get('identifier', '')}")
        print("  (full trace: " + log + ")")
        sys.exit(0)
print(f"{name}: no failed property in {log}")
EOF

prove() { # name, assertion
  local name=$1 assertion=$2 start status
  start=$(date +%s%N)
  jvmcontract prove "probe.Probe#$name" --classes "$out/classes" --assert "$assertion" --engine jbmc --timeout 300 \
    --work "$out/work-$name" > "$out/$name.log" 2>&1
  status=$?
  say "-- $name [$assertion]: jvmcontract exit $status in $(( ($(date +%s%N) - start) / 1000000 )) ms"
  grep -E '^(✓|✗|  |    outcome)' "$out/$name.log" | head -8 | tee -a "$summary"
  local found=
  for log in "$out/work-$name"/jbmc*.log; do
    [ -f "$log" ] || continue
    found=yes
    python3 "$out/trace.py" "$log" "$name ($(basename "$log"))" >> "$out/$name-trace.txt"
  done
  if [ -n "$found" ]; then
    head -80 "$out/$name-trace.txt" | tee -a "$summary"
  else
    say "$name: no JBMC log in $out/work-$name"
  fi
}
prove one 'result == 1'
prove oneAfterInit 'result == 1'
prove two 'result == 2'
exit 0
