#!/usr/bin/env bash
# VF-023's second probe (verification/findings.md), run by a pipeline job from the repository root. Under JBMC alone
# the corpus's listSizes(n=1) [assume n >= 1 && n <= 3; assert result == n * 10] and listChange(n=0)
# [assume n == 0 || n == 8; assert result == 1] are refuted with a witness the JVM doesn't reproduce, while the first
# probe (vf023.sh, job 20261108-082244-...) showed JBMC proving List.of(new Object()).size() == 1 alone, before and
# after ImmutableCollections' initializer, and a two-element list's size 2. So a one-element List12 alone is fine.
# What the corpus's two methods add is a choice between lists made on different branches (listSizes: List.of() or
# a List12 of one or two or a ListN of three; listChange: a List12 of one or a ListN of three, then a switch over
# the lists' changes), an assumption over n, and objects made before the list.
#
# Each probe is a property proof with JBMC alone (jvmcontract prove --engine jbmc, --work kept), one ingredient at a
# time. The first two are the corpus's own methods, compiled from lib/tests/conformance, which must reproduce:
#   corpusSizes    Conformance#listSizes   n >= 1 && n <= 3      result == n * 10
#   corpusChange   Conformance#listChange  n == 0 || n == 8      result == 1
#   oneOrTwo       n == 1 ? List.of(a) : List.of(a, b)              two List12s
#   oneOrThree     n == 1 ? List.of(a) : List.of(a, b, c)           a List12 or a ListN
#   emptyOrOne     n == 0 ? List.of() : List.of(a)                  EMPTY_LIST (a ListN) or a List12
#   oneAssumed     List.of(new Object()).size(), under listSizes' assumption
#   oneMadeFirst   three objects made first, then List.of(a).size()  as listSizes makes them
#   changeNoSwitch listChange's choice of list, without its switch
#   oneThenSwitch  listChange's switch over a List12 of one, without the choice
# On a JVM every probe's claim holds (printed first, for n from -2 to 12). For each refuted probe, JBMC's failed
# property, its description, and the trace's steps that assign a list's fields, ImmutableCollections' statics, a
# class identifier or an initialization flag go to NAME-trace.txt, with the last steps before the failure.
# It changes nothing in the repository. Everything goes to lib/target/vf023-choice/; summary.txt has the outcomes.
set -uo pipefail
out=lib/target/vf023-choice
rm -rf "$out"
mkdir -p "$out/src/probe" "$out/classes"
summary="$out/summary.txt"
say() { echo "$*" | tee -a "$summary"; }
echo "VF-023 second probe, $(date -u +%FT%TZ), $(jbmc --version 2>&1 | head -1), $(jvmcontract --version 2>&1 | head -1)" > "$summary"

cat > "$out/src/probe/Choice.java" <<'EOF'
package probe;

import java.util.List;

public final class Choice {
    private Choice() {
    }

    public static int oneOrTwo(int n) {
        Object a = new Object(), b = new Object();
        List<Object> l = n == 1 ? List.of(a) : List.of(a, b);
        return l.size();
    }

    public static int oneOrThree(int n) {
        Object a = new Object(), b = new Object(), c = new Object();
        List<Object> l = n == 1 ? List.of(a) : List.of(a, b, c);
        return l.size();
    }

    public static int emptyOrOne(int n) {
        Object a = new Object();
        List<Object> l = n == 0 ? List.of() : List.of(a);
        return l.size();
    }

    public static int oneAssumed(int n) {
        return List.of(new Object()).size();
    }

    public static int oneMadeFirst(int n) {
        Object a = new Object(), b = new Object(), c = new Object();
        return List.of(a).size();
    }

    public static int changeNoSwitch(int n) {
        List<Object> l = n < 10 ? List.of(new Object()) : List.of(new Object(), new Object(), new Object());
        return l.size();
    }

    public static int oneThenSwitch(int n) {
        List<Object> l = List.of(new Object());
        Object x = new Object();
        switch (n % 10) {
            case 1: l.add(x); break;
            case 2: l.set(0, x); break;
            case 3: l.remove(0); break;
            case 4: l.remove(x); break;
            case 5: l.clear(); break;
            case 6: l.addAll(List.of(x)); break;
            case 7: l.iterator().remove(); break;
            default: break;
        }
        return l.size();
    }

    public static void main(String[] args) {
        StringBuilder s = new StringBuilder();
        for (int n = -2; n <= 12; n++) {
            s.append("n=").append(n).append(": oneOrTwo ").append(oneOrTwo(n)).append(", oneOrThree ").append(oneOrThree(n))
                .append(", emptyOrOne ").append(emptyOrOne(n)).append(", oneAssumed ").append(oneAssumed(n))
                .append(", oneMadeFirst ").append(oneMadeFirst(n)).append(", changeNoSwitch ").append(changeNoSwitch(n));
            if (n % 10 == 0 || n % 10 == 8 || n % 10 == 9) {
                s.append(", oneThenSwitch ").append(oneThenSwitch(n));
            }
            s.append('\n');
        }
        System.out.print(s);
    }
}
EOF
javac -proc:none -parameters -g -d "$out/classes" "$out/src/probe/Choice.java" || { say "compile failed: Choice"; exit 1; }
javac -proc:none -parameters -g -d "$out/classes" lib/tests/conformance/conformance/Conformance.java || { say "compile failed: Conformance"; exit 1; }
say "on the JVM:"
java -cp "$out/classes" probe.Choice | tee -a "$summary"
mkdir -p "$out/src/run"
cat > "$out/src/run/Corpus.java" <<'EOF'
package run;

import conformance.Conformance;

public final class Corpus {
    public static void main(String[] args) {
        System.out.println("listSizes(1, 2, 3) = " + Conformance.listSizes(1) + " " + Conformance.listSizes(2) + " "
            + Conformance.listSizes(3) + ", listChange(0, 8) = " + Conformance.listChange(0) + " " + Conformance.listChange(8));
    }
}
EOF
javac -proc:none -cp "$out/classes" -d "$out/classes" "$out/src/run/Corpus.java" || { say "compile failed: Corpus"; exit 1; }
say "on the JVM, the corpus: $(java -cp "$out/classes" run.Corpus)"

# JBMC's first failed property, and the steps of its trace that touch a list, the sentinel, a class identifier or
# class initialization, then the last steps before the failure whatever they assign.
cat > "$out/trace.py" <<'EOF'
import json, re, sys
log, name = sys.argv[1], sys.argv[2]
text = open(log).read()
try:
    messages = json.loads(text[text.index("["):])
except Exception as e:
    print(f"{name}: jbmc.log is not JSON ({e})")
    sys.exit(0)
wanted = re.compile(r"ImmutableCollections|List12|ListN|\be0\b|\be1\b|elements|EMPTY|clinit|already_initialized|class_identifier", re.I)
def show(s):
    where = s.get("sourceLocation", {})
    loc = f"{where.get('function', '')}:{where.get('line', '')}"
    kind = s.get("stepType")
    if kind == "assignment":
        value = s.get("value", {})
        value = value.get("data", value) if isinstance(value, dict) else value
        return f"  {loc}  {s.get('lhs')} = {json.dumps(value)[:160]}"
    if kind in ("function-call", "function-return"):
        return f"  {loc}  {kind} {s.get('function', {}).get('identifier', '')}"
    if kind == "input":
        return f"  {loc}  input {s.get('inputID')} = {json.dumps([v.get('data', v) for v in s.get('values', [])])[:160]}"
    if kind == "failure":
        return f"  {loc}  FAILURE {s.get('property')}: {s.get('reason')}"
    return None
for m in messages:
    for r in m.get("result", []) if isinstance(m, dict) else []:
        if r.get("status") != "FAILURE":
            continue
        where = r.get("sourceLocation", {})
        print(f"{name}: FAILURE of {r.get('property')}: {r.get('description')} at {where.get('function', '')}:{where.get('line', '')}")
        steps = [s for s in r.get("trace", []) if not s.get("hidden")]
        print("  the steps that touch a list, the sentinel, a class identifier or initialization:")
        for s in steps:
            line = show(s)
            text = json.dumps(s)
            if line and (s.get("stepType") in ("input", "failure") or wanted.search(text)):
                print(line)
        print("  the last 40 steps:")
        for s in steps[-40:]:
            line = show(s)
            if line:
                print(line)
        print("  (full trace: " + log + ")")
        sys.exit(0)
print(f"{name}: no failed property in {log}")
EOF

prove() { # name, target, assumption, assertion
  local name=$1 target=$2 assumption=$3 assertion=$4 start status
  start=$(date +%s%N)
  jvmcontract prove "$target" --classes "$out/classes" --assume "$assumption" --assert "$assertion" --engine jbmc \
    --timeout 300 --work "$out/work-$name" > "$out/$name.log" 2>&1
  status=$?
  say "-- $name: $target [assume $assumption; assert $assertion]: jvmcontract exit $status in $(( ($(date +%s%N) - start) / 1000000 )) ms"
  head -12 "$out/$name.log" | tee -a "$summary"
  local found=
  for log in "$out/work-$name"/jbmc*.log; do
    [ -f "$log" ] || continue
    found=yes
    python3 "$out/trace.py" "$log" "$name ($(basename "$log"))" >> "$out/$name-trace.txt"
  done
  if [ -n "$found" ]; then
    head -120 "$out/$name-trace.txt" | tee -a "$summary"
  else
    say "$name: no JBMC log in $out/work-$name"
  fi
}
prove corpusSizes conformance.Conformance#listSizes 'n >= 1 && n <= 3' 'result == n * 10'
prove corpusChange conformance.Conformance#listChange 'n == 0 || n == 8' 'result == 1'
prove oneOrTwo probe.Choice#oneOrTwo 'n >= 1 && n <= 2' 'result == n'
prove oneOrThree probe.Choice#oneOrThree 'n >= 1 && n <= 3' '(n != 1 || result == 1) && (n == 1 || result == 3)'
prove emptyOrOne probe.Choice#emptyOrOne 'n >= 0 && n <= 1' 'result == n'
prove oneAssumed probe.Choice#oneAssumed 'n >= 1 && n <= 3' 'result == 1'
prove oneMadeFirst probe.Choice#oneMadeFirst 'n >= 1 && n <= 3' 'result == 1'
prove changeNoSwitch probe.Choice#changeNoSwitch 'n == 0 || n == 8' 'result == 1'
prove oneThenSwitch probe.Choice#oneThenSwitch 'n == 0 || n == 8' 'result == 1'
exit 0
