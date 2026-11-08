#!/usr/bin/env bash
# VF-023's third probe (verification/findings.md), run by a pipeline job from the repository root.
#
# The second probe (vf023-choice.sh, job 20261108-091002-...) found the ingredient: JBMC refutes `l.size()` whenever
# `l` is a choice between two lists made on different branches, even two List12s (oneOrTwo), and proves it for one
# list alone. Its trace of oneOrTwo(n=1) shows JBMC calling ImmutableCollections$ListN.size on a List12 (whose class
# identifier it had just set to List12), which reads a ListN's `elements` and returns 0. Every refuted probe also
# reaches `java.util.List.size()` as JBMC's stub: the model java.util.List (lib/models/java/util/List.java) declares
# List's own abstract methods (get, set, indexOf, ...) but not the ones it inherits from Collection (size, isEmpty,
# iterator, contains, ...), and Collection is not on JBMC's class path. The JDK's java.util.List re-declares them all.
# Every list claim JBMC got right asks a method the model declares (listGet's get) or has one list only; the ones it
# gets wrong ask size, isEmpty or iterator of a choice.
#
# The hypothesis: with the interface method undeclared, JBMC's dispatch of `invokeinterface List.size` on a reference
# that may be either of two objects is wrong; on a single object symbolic execution resolves it. This probe tests it
# without changing the repository, in two variants of the class path JBMC sees:
#   as-is     the tool's models, as every job so far;
#   declared  the same models, with java.util.List re-declaring Collection's abstract methods as the JDK's List does
#             (compiled from a patched copy of lib/models/java/util into lib/target, put on --classpath, which comes
#             before the tool's models on JBMC's class path).
# Each variant runs six property proofs with JBMC alone: the corpus's listSizes and listChange under their
# assumptions, and the second probe's oneOrTwo, oneOrThree, emptyOrOne (refuted as-is) and oneAssumed (proved as-is).
# For each it keeps the verdict, and the dispatch of the probe method's size()/isEmpty() calls in JBMC's goto program
# (jbmc-goto.txt): the class-identifier tests and the functions they call.
# On a JVM every claim holds (printed first). It changes nothing in the repository; everything goes to
# lib/target/vf023-dispatch/, and summary.txt has the outcomes.
set -uo pipefail
out=lib/target/vf023-dispatch
rm -rf "$out"
mkdir -p "$out/src/probe" "$out/classes" "$out/declared/src/java/util" "$out/declared/classes"
summary="$out/summary.txt"
say() { echo "$*" | tee -a "$summary"; }
echo "VF-023 third probe, $(date -u +%FT%TZ), $(jbmc --version 2>&1 | head -1), $(jvmcontract --version 2>&1 | head -1)" > "$summary"

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

    public static void main(String[] args) {
        for (int n = 0; n <= 3; n++) {
            System.out.println("n=" + n + ": oneOrTwo " + oneOrTwo(n) + ", oneOrThree " + oneOrThree(n) + ", emptyOrOne "
                + emptyOrOne(n) + ", oneAssumed " + oneAssumed(n));
        }
    }
}
EOF
javac -proc:none -parameters -g -d "$out/classes" "$out/src/probe/Choice.java" || { say "compile failed: Choice"; exit 1; }
javac -proc:none -parameters -g -d "$out/classes" lib/tests/conformance/conformance/Conformance.java || { say "compile failed: Conformance"; exit 1; }
say "on the JVM:"
java -cp "$out/classes" probe.Choice | tee -a "$summary"

# The declared variant: the models' java.util sources, with Collection's abstract methods re-declared in List, as
# the JDK's List declares them, right after the interface's opening line.
cp lib/models/java/util/*.java "$out/declared/src/java/util/"
python3 - "$out/declared/src/java/util/List.java" <<'EOF'
import sys
path = sys.argv[1]
text = open(path).read()
opening = "public interface List<E> extends Collection<E> {\n"
assert text.count(opening) == 1, "the model's List no longer opens as expected"
declared = """
    int size();

    boolean isEmpty();

    boolean contains(Object o);

    Iterator<E> iterator();

    Object[] toArray();

    <T> T[] toArray(T[] a);

    boolean add(E e);

    boolean remove(Object o);

    boolean containsAll(Collection<?> c);

    boolean addAll(Collection<? extends E> c);

    boolean removeAll(Collection<?> c);

    boolean retainAll(Collection<?> c);

    void clear();

    boolean equals(Object o);

    int hashCode();
"""
open(path, "w").write(text.replace(opening, opening + declared))
EOF
javac --release 8 -Xlint:-options -g -d "$out/declared/classes" "$out/declared/src/java/util/"*.java \
  || { say "compile failed: the declared variant of the models"; exit 1; }
say "the declared variant's List (javap):"
javap "$out/declared/classes/java/util/List.class" | grep -E "size|isEmpty|iterator" | tee -a "$summary"

# The dispatch of the probe method's size() and isEmpty() calls in JBMC's goto program: the function's body from its
# header (`pretty name /* id */`) to END_FUNCTION, the lines that test a class identifier or call size, isEmpty or a stub.
cat > "$out/dispatch.py" <<'EOF'
import re, sys
path, method = sys.argv[1], sys.argv[2]
try:
    lines = open(path, errors="replace").read().splitlines()
except OSError as e:
    print(f"  no goto program: {e}")
    sys.exit(0)
inside, shown = False, 0
for line in lines:
    if not inside and f"/* {method} */" in line:
        inside = True
        print(f"  {line.strip()}")
        continue
    if inside:
        if line.strip() == "END_FUNCTION":
            print("  END_FUNCTION")
            break
        if re.search(r"class_identifier|\.size:|\.isEmpty:|ListN|List12|stub|nondet", line):
            print(f"  {line.strip()[:220]}")
            shown += 1
            if shown >= 60:
                print("  ...")
                break
if not inside:
    print(f"  {method} not found in {path}")
EOF

prove() { # variant, name, target, method symbol, assumption, assertion
  local variant=$1 name=$2 target=$3 symbol=$4 assumption=$5 assertion=$6 start status extra=()
  [ "$variant" = declared ] && extra=(--classpath "$out/declared/classes")
  local work="$out/work-$variant-$name"
  start=$(date +%s%N)
  jvmcontract prove "$target" --classes "$out/classes" "${extra[@]}" --assume "$assumption" --assert "$assertion" \
    --engine jbmc --timeout 300 --work "$work" > "$out/$variant-$name.log" 2>&1
  status=$?
  say "-- $variant $name: $target [assume $assumption; assert $assertion]: jvmcontract exit $status in $(( ($(date +%s%N) - start) / 1000000 )) ms"
  grep -E "^(✓|✗|note|  jbmc gap)" "$out/$variant-$name.log" | head -8 | tee -a "$summary"
  say "  the dispatch in $symbol (jbmc-goto.txt):"
  python3 "$out/dispatch.py" "$work/jbmc-goto.txt" "$symbol" | tee -a "$summary"
}

for variant in as-is declared; do
  say "== $variant"
  prove "$variant" corpusSizes conformance.Conformance#listSizes 'java::conformance.Conformance.listSizes:(I)I' 'n >= 1 && n <= 3' 'result == n * 10'
  prove "$variant" corpusChange conformance.Conformance#listChange 'java::conformance.Conformance.listChange:(I)I' 'n == 0 || n == 8' 'result == 1'
  prove "$variant" oneOrTwo probe.Choice#oneOrTwo 'java::probe.Choice.oneOrTwo:(I)I' 'n >= 1 && n <= 2' 'result == n'
  prove "$variant" oneOrThree probe.Choice#oneOrThree 'java::probe.Choice.oneOrThree:(I)I' 'n >= 1 && n <= 3' '(n != 1 || result == 1) && (n == 1 || result == 3)'
  prove "$variant" emptyOrOne probe.Choice#emptyOrOne 'java::probe.Choice.emptyOrOne:(I)I' 'n >= 0 && n <= 1' 'result == n'
  prove "$variant" oneAssumed probe.Choice#oneAssumed 'java::probe.Choice.oneAssumed:(I)I' 'n >= 1 && n <= 3' 'result == 1'
done
say "== outcomes"
for log in "$out"/as-is-*.log "$out"/declared-*.log; do
  printf '%s: %s\n' "$(basename "$log" .log)" "$(grep -cE '^✓' "$log") proved, $(grep -cE '^✗' "$log") not" | tee -a "$summary"
done
exit 0
