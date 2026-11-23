# JBMC fast-follow · Java callbacks, numeric conversions and array inputs

**Execution brief · 23 November 2026 ·** [`pilifs/in-the-loop` develop at `9d9a860c`][head] · **Comparator** JBMC 6.11.0  
**Queue position** After cycle 3 and the current 15-family campaign, before [receiver construction and property discovery][next].

## Decision

Start with **method-reference argument and return conversion** and **wide numeric conversion**. Both have public library callers where standalone JBMC reaches the assertion and the current native checker refuses. Method references also exposed a defect in the project’s own counterexample replay. Numeric conversion has the cleanest engine comparison: on five fresh Jackson and Commons Lang statements the project’s integrated JBMC decided **5/5** at matched settings and strict native decided **0/5**. Run the callback replay regression first. The numerical investigation can start alongside it.

Then take on **caller-owned ragged arrays**. The two engines behind the project CLI both reject a direct `int[][]` parameter before executing the same library calls they can already verify through a small builder. This makes it possible to isolate input representation from execution. Finish with an unmodified public method whose formal parameter is itself `long[][]`. The queued brief can then use those input and replay capabilities to tackle discovery of legal construction histories.

## What changed in the first two cycles

| Cohort | Opening → cycle 1 → cycle 2 | Interpretation |
|---|---|---|
| 60 registered campaign statements, 15 semantic families | Native **12 → 50 → 57**. The latest 57 comprise 33 proofs and 24 refutations replayed on the original JVM | 45 new original-scope decisions in 14 families. Two initially JVM-contradicted native verdicts fell to zero. Cycle 2 added three direct reference-array and four Gson statements |
| Same 60, correct verdicts on the cycle-2 paired comparison | **24 both, 33 native only, 0 integrated JBMC only, 3 neither** | Integrated JBMC produced 7 correct proofs and 17 correct refutations. Its other rows were 34 open and 2 JVM-contradicted proofs, involving default dispatch and covariant stores |
| Historical 187-claim comparison | Native recovered **6/13 → 13/13 → 13/13** of the old staged-JBMC-only cohort and retained all **24/24** native-only controls | The original 187-way table had 133 both, 24 native only, 13 JBMC only and 17 neither. The campaign selectively reran historical cohorts. A new full-187 distribution requires a full rerun |
| Three remaining ordinary campaign statements | All three stop at the platform `Thread` constructor in example 391 | A separate bounded sequentially consistent two-thread checker already enumerated complete schedules and reproduced observed values. Its scope and evidence are reported separately from the ordinary entries |

The first-cycle checker corrected a default-method selection that accepted an answer contradicted by the JVM. The second cycle also proved original Gson parent/fix behavior through the original public constructors and class initialization. These are meaningful advances in ordinary caller coverage. The 60 were deliberately selected and cannot establish Java-wide parity. [First-cycle decision][cycle1] · [Cycle-2 report][results] · [Paired scorecard][score] · [Two-thread schedules][schedules]

The comparison now turns on the entry a real caller uses. Native is ahead on the frozen public-call campaign, particularly where faithful JDK behavior and replay matter. JBMC still has demonstrated reach on wide operands and javac-generated adapters. For nested arrays, standalone JBMC can enter methods that the shared project front end rejects, while its default tree misses legal aliases. A single aggregate score hides all three differences.

**Handoff from cycle 3.** At kickoff, pin the successor commit and measured checker binary, run `python3 -B lib/benchmark/java-semantics-gap/scorecard.py --check`, read the final report, and repeat the new opening probes below. Where cycle 3 has already decided a seed, keep it as a control and start at its first open transfer. Cycle 3 owns the three ordinary monitor claims. The following brief owns factory search, site discovery, Guava tagged-hex parsing and two-independent-input floating subtraction. The fast-follow needs none of those features to begin.

## Work in example order

### 1. Preserve Java argument and return conversions at a method reference

Use Guava 33.4.8-jre and Commons Lang 3.17.0 with these three javac-emitted method references. The observation is the exact result of a three-way comparison computed independently from `<` and `>`.

| Public call through a functional interface | Domain and observable behavior |
|---|---|
| `long cmp(int,int) = Longs::compare` | All 2⁶⁴ pairs of signed ints. The implementation takes two longs and returns an int. Both arguments widen, then the return value widens with its sign |
| `long cmp(Integer,Integer) = Longs::compare` | Box every pair of ints for the value claim. Separately pass a null first argument. Unboxing throws `NullPointerException` before the comparison can return |
| `long cmp(short,short) = NumberUtils::compare` | All 2³² pairs of shorts on a second library. The implementation already takes shorts. Only the result needs widening |

Preflight used seven independent statements across these callers. **Native refused 7/7** at argument or result conversion. **Standalone JBMC decided 7/7**: four true properties and three false “always nonnegative” properties. Integrated JBMC proved all four positives. On each false claim the project process exited 101 while replaying the witness. The backtrace goes through `Value::as_long`, the interpreter and `witness::replay_in_untimed`. The ordinary JVM reproduced all three stock counterexamples at `(0,1)`. A direct Java call with the identical Guava target and explicit widenings already proved and refuted correctly in all three lanes. [Native call adaptation][calls] · [Interpreter value handling][interp] · [Replay][witness] · [Guava target][guava-longs] · [Commons Lang target][lang-number] · [Java adaptation rules][lambda-spec]

**First deliverable.** Land a replay regression through the normal integrated command. Require either a correctly replayed violation or a structured unresolved result on an unsupported case, then close the three known violations. A caught process panic by itself earns no recovered verdict. On the native path, establish the four positives and refute the three negatives. Keep the product class and assertion driver separate. Verify the bootstrap and target descriptors in the actual classfiles. Freeze the Guava implementation improvement before trying the Commons Lang return-only case.

**Public transfer.** In Guava’s `ComparisonChain`, let the first comparison either settle the result or leave a tie. Pass `Longs::compare` as a real `Comparator<Integer>` for the second comparison. Native already proves a settled chain skips a comparator that would receive null. On the active path it refuses adaptation. Verify the all-int-pairs result, refute “always nonnegative” on the active path, and distinguish skipped-null from active-null unboxing. Standalone JBMC reached the active assertions after adding the unchanged OpenJDK 21.0.13 `Comparator.class` to its packaged models. Record that profile beside stock. [ComparisonChain][chain]

### 2. Characterize a real numeric change across two legal Jackson call paths

Use Jackson 2.19.0 `LongNode` and `DoubleNode`, plus Commons Lang 3.17.0 `MutableLong`. These are unchanged release methods. The counterexample distinguishes two plausible implementations of a client conversion; it makes no claim about a Jackson defect. [Jackson LongNode][jackson-long] · [Jackson DoubleNode][jackson-double] · [Commons Lang MutableLong][lang-long] · [Java conversion rules][convert-spec]

| Frozen statement | Scope | Expected |
|---|---|---|
| `new LongNode(n).floatValue()` rounds to the independently computed nearest-even grid point | Every long `2^54 ≤ n < 2^55`, or 2⁵⁴ inputs | Proved |
| Direct conversion always equals `new DoubleNode(node.doubleValue()).floatValue()` | Same range and original Jackson bytecode | Refuted |
| `DoubleNode.floatValue()` returns zero exactly at the halfway tie and otherwise returns the least positive float | A direct `double` parameter containing every binary64 value in `[2^-150, 2^-149]`, inclusive: 2⁵² + 1 values | Proved |
| Every conversion in that tiny positive interval produces a positive float | Same direct `double` domain | Refuted at `2^-150` |
| `new MutableLong(n).floatValue()` agrees with the first integer oracle | Same 2⁵⁴ longs, second library | Proved |

Standalone and integrated JBMC decided all five as expected. Strict native reached “Long to Float with more than 64 reachable operand tuples” on the three long-input statements, and refused the two direct-double entries at intake. A separately labeled long-mantissa adapter reached the downstream “Double to Float with more than 64 reachable operand tuples” limit. Preserve the direct-double claim and the adapter’s own domain. The JVM replayed the two counterexamples, including `n=0x0040000040000001L`: direct rounding gives float bits `0x5a800001`, while going through double gives `0x5a800000`. The underflow proof uses numerical equality at zero. The JVM can distinguish signed zero in an additional raw-bit replay. The packaged comparator’s raw-bit model can itself introduce nondeterminism. [Native conversion implementation][fp] · [Entry-type filter][params]

**Graduation claim.** Identify *all* disagreements between the two Jackson paths. Let `k=n−2^54`, `hi=k>>>31`, and `delta=(k & 0x7fffffff)−2^30`. They differ for even `hi` with `delta` equal to 1 or 2, and for odd `hi` with `delta` equal to −1 or −2. There are two such inputs in each of 2²³ bins, **16,777,216 disagreements**. Integrated JBMC proved this characterization. The JVM checked both parities at their boundaries. This is the higher-value result for a library-upgrade review: it gives the affected input domain after the first witness has been found.

**Acceptance.** Decide the original five on native. Run the sixth classification after the simpler evidence is green. Check both call paths, ties on even and odd retained significands, the halfway-to-zero endpoint, a direct-double post-return sentinel, and JVM replay of exact operand bits. Leave the encoding and solver choice to the agent. A finite test grid is useful corroboration and has its own scope.

### 3. Accept caller-owned nested arrays and reproduce shared rows

**Public callers.** Run Commons Lang 3.17.0 `ArrayUtils.reverse(Object[])` on a direct `int[][]`. Two outer slots must exchange their original row references. Afterward, complementing the first element of the old left row changes the old right row exactly when the two nonempty rows are the same object. Then run Commons Collections 4.5.0 `ObjectArrayIterator<int[]>` on the same shape. After `next()`, overwrite slot 1 with the first row. The next read must observe the replacement, and `reset()` must expose the first row again. The wrong alternatives are “the first slot never changes” and “the iterator captured the old second slot.” [ArrayUtils][reverse] · [ObjectArrayIterator][iterator]

Use nullable outer arrays with length at most two, nullable rows of length at most two, and arbitrary signed int cells. The reversal and iterator observations are guarded by outer length two. Independently test reachability of null, empty, shared nonempty, and equal-valued distinct nonempty rows. The existing #379 generator covers one flat application component and #369 has a supplied ragged construction. Both are valuable controls. [Direct-input code][ref-input] · [Example 379][379] · [Example 369][369]

- **Observed at ordinary entry.** Both native and integrated JBMC refused `int[][]` before the library method. Standalone JBMC proved reversal and live iteration on its generated input trees and refuted both wrong alternatives. Both counterexamples replayed on the JVM as `new int[][] {new int[0], null}`.
- **Observed when identity matters.** Stock JBMC accepted the false claim that two nonempty rows can never be shared under its default tree generator. Explicitly allowing the second row to alias the first made it refute that claim. An independent JVM census of 209 two-slot graphs with cells in `{-1,0,1}` included 12 shared nonempty cases. A primitive-argument builder with an explicit alias choice let both native and integrated JBMC prove both public operations and refute “always distinct” already.
- **Acceptance.** Extend direct entry through to witness replay. Establish the two true public observations, refute their two wrong alternatives, and reproduce both shared and equal-distinct row identities through the ordinary input representation. Score the stock tree, explicit alias choice and direct alias-complete scopes separately. A proof over the tree alone cannot establish the shared-row case.

**Independent transfer.** On Commons Math 3.6.1, run the actual `MathArrays.checkRectangular(long[][])` descriptor. Two non-null rows of equal length return normally. A one-row matrix containing null also returns normally on this version. JVM enumeration across 21 non-null outer shapes through height and width two produced eight normal returns, seven `NullPointerException`s and six `DimensionMismatchException`s. Standalone JBMC proved the equal-width and singleton controls. Its complete mismatch-property check retained a failed exception obligation. Keep the exact mismatch metadata as a separate investigation. Success on the original `long[][]` entry demonstrates transfer across element width, library and public signature. [Commons Math source][math-arrays]

## If cycle 3 overlaps or the first three cases close early

| Priority | Fresh example | What makes it worth taking |
|---|---|---|
| 4 | Commons Lang `ObjectUtils.compare(a,b)` → Guava `Ordering.natural().compare(a,b)`, on two independent non-null strings of 0–2 unrestricted UTF-16 units | Preserve the **exact** first unequal unsigned-unit difference, or length difference after a shared prefix. A sign-only answer fails, e.g. `U+D800` vs `U+D802` gives −2. Stock JBMC proved the true rule and refuted sign normalization. Native refused erased `Comparable.compareTo(Object)`; the direct `String.compareTo(String)` twin also refused. Integrated JBMC declined the unrestricted String parameters at intake. The JVM checked 5,329 boundary pairs; 4,756 falsified sign normalization. On the Guava transfer, `min(a,b)` must retain the first reference when equal-valued distinct strings tie. Standalone JBMC proved it and refuted selecting the second reference. A finite selector exercises its own input domain. [Commons Lang][object-compare] · [Guava ordering][ordering] |
| 5 | Commons Collections `CircularFifoQueue<Object>(2)` plus Commons Lang `ArrayFill.fill(T[],T)` | Check all 256 histories of four operations drawn from `offer(A), offer(B), poll, clear`, with a two-slot independent oracle. Capacity, head, poll result and indexed identities matter. Native already refutes equating `isFull()` with full occupancy; the positive caller stops at the JDK reference-array fill in `clear()`. In the second release library, verify return-array identity, replacement of stale slots and visibility of a later write through the shared fill object. The stock model can accept the false stale-slot claim. Standalone JBMC with the real JDK `Arrays.class` and the measured class hierarchy decided the compatible fill controls correctly. Add a covariant-array control: filling an empty typed array with an incompatible object succeeds, while a nonempty one throws before replacing the first slot. The JVM reproduced both. [Queue][queue] · [ArrayFill][fill] |

For an application check after numeric work, rerun Commons Lang #375 at its original three selector values. All four ordinary parser obligations still stopped at `Float.valueOf(String)` after cycle 2. A six-input probe of that step gave the expected JVM float bits or the exact malformed exception. The stock JBMC trace chose NaN for the valid literal `0.100000001490116121`; its bundled parse and raw-bit operations were nondeterministic on this path. Treat any newly decided #375 claim as public-caller progress. A conversion proof alone cannot close the lexical parsing and `BigDecimal` obligations. [Original caller and domain][decimal]

## Completion and handoff

1. **Capture the opening comparison.** Keep four columns per frozen statement: strict native, strict integrated JBMC, standalone JBMC with named model/classpath, and original JVM control. Record entry descriptor, artifact/class hashes, domain, bounds, selected property, required unwinding and exception checks. Preserve separate statuses for an original-scope proof, a replayed violation, a front-end refusal, a process error and a result contradicted by the JVM. Keep each false claim paired with a reachable true or post-return control.
2. **Report recovered decisions with denominators.** Show the seven callback rows and five numeric rows independently. The direct-call twins, sixth disagreement characterization, finite JVM sweeps, optional transfers and cycle-3 monitor rows each have a different role. For nested arrays report tree-only and alias-complete coverage separately. Freeze inputs and expected observations before editing the checker. Where whole-program class selection changes, report the new profile.
3. **Demonstrate transfer through the normal entry.** Run Guava’s real comparison chain, Commons Lang’s numeric caller and the Commons Math `long[][]` entry after their respective improvements. Keep at least one second-library transfer unchanged when choosing an implementation. Agents own the solver, runtime and representation changes. A trick tied to class or method names should fail an unchanged independent caller.
4. **Hand the results to the next brief.** Recount the preceding campaign and its 24 historical regression controls. Record the precise first unresolved operation and a minimal reproducer for any partial result. Once the core work and transfer attempts are reported, move on to receiver and property discovery. Give that run the supported raw input shapes, any replay limitations and the independently measured bounds. Pull a reserve case forward if cycle 3 already delivered a primary capability or a measured blocker merits a separate research brief.

## Reproducible opening probes

The appendix includes the primary Boolean observations and assertion drivers used for the fresh comparison. Compile each family on JDK 21 into a separate directory, preserving the product/driver split. Run the original JVM with assertions enabled. The repository campaign has working intake, classpath binding, scorecard and JVM replay conventions. The paths below are local workspace examples for a new run. [Campaign runner][runner] · [JBMC flags][jbmc]

| Dependency or tool | Preflight version / identity |
|---|---|
| JDK and native | OpenJDK 21.0.13. Fresh native build from `9d9a860cf379d64549662bd797b33b0416b10c34`. The committed campaign receipts identify their own measured checker builds |
| Guava and Commons | `com.google.guava:guava:33.4.8-jre`, `org.apache.commons:commons-lang3:3.17.0`, `org.apache.commons:commons-collections4:4.5.0`, `org.apache.commons:commons-math3:3.6.1` |
| Jackson | `com.fasterxml.jackson.core:{jackson-databind,jackson-core,jackson-annotations}:2.19.0`; databind JAR SHA-256 `ceda311f476c3b18e1d2b240c94e2dcb9c8d44e70f8afa9facab88bac4ddc03a` |
| JBMC 6.11.0 Ubuntu 22.04 | Binary `2cf57254…`, packaged core-model JAR `2a05026b…`. Used for the five numerical rows |
| JBMC 6.11.0 Ubuntu 24.04 | Binary `200f4cbb…`, packaged core-model JAR `a31ef93b…`. Used for the callback and ragged-array controls. Both packages qualified the bounded UTF-16 comparison |
| Specific image-backed comparators | OpenJDK `java/util/Comparator.class` SHA-256 `31213c77d79b01f269b7e3ee1008a1cbe0ce11b4442d2401346de6ca80d8d095` for `ComparisonChain`. `java/util/Arrays.class` SHA-256 `4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab` for the reference-fill transfer. Record every other provider in the chosen classpath |

The following extracts the sources from this brief into `fast-follow-fixtures/` when run alongside the Markdown file.

```sh
python3 - <<'PY'
import re
from pathlib import Path

brief = Path("jbmc-fast-follow-calls-conversions-and-arrays.md").read_text()
for name, source in re.findall(r"^#### ([\w/]+\.java)\n\n```java\n(.*?)^```$", brief, re.M | re.S):
    path = Path("fast-follow-fixtures") / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
PY
```

For example, set `JARS` to the ordered classpath containing the three Jackson JARs and Commons Lang, and `CORE_MODELS` to the chosen JBMC package’s core-model JAR. From `fast-follow-fixtures/`:

```sh
mkdir -p out/numeric
javac -g -parameters -cp "$JARS" -d out/numeric numeric/*.java
java -ea -cp "out/numeric:$JARS" NodeAssertions
jvmcontract prove 'NodeChecks#direct' --classes out/numeric --classpath "$JARS" \
  --assert result --engine native --gaps strict --unwind 10 --max-array-length 8 --timeout 120 --json
jvmcontract prove 'NodeChecks#direct' --classes out/numeric --classpath "$JARS" \
  --assert result --engine jbmc --jbmc-staging staged --unwind 10 --max-array-length 8 \
  --gaps strict --timeout 120 --json
jbmc NodeAssertions --function NodeAssertions.direct -cp "out/numeric:$JARS:$CORE_MODELS" \
  --unwind 7 --unwinding-assertions --throw-runtime-exceptions --sat-solver cadical --json-ui
```

Use `Lift#primitiveGood` / `LiftChecks.correct` for callbacks (stock unwind 8). For rows, select `RaggedProof#reversed` with `--nullable a --max-array-length 2 --unwind 7` in the project runner. In standalone JBMC use `RaggedProof.testReverse`, `--max-nondet-array-length 2 --max-nondet-tree-depth 5 --unwind 7 --unwinding-assertions --throw-runtime-exceptions`. Compare `testDistinct` with `testAliasDistinct`. For every negative control inspect the failing assertion ID, structured verdict and physical JVM replay. A nonzero exit can also mean unwinding failure, unhandled exception or a process crash.

<details>
<summary>Java sources for the three primary investigations</summary>

#### callbacks/Lift.java

```java
import com.google.common.primitives.Longs;
import org.apache.commons.lang3.math.NumberUtils;
public class Lift {
 interface Bi { long cmp(int x, int y); }
 interface Box { long cmp(Integer x, Integer y); }
 interface Twice { long cmp(short x, short y); }
 static final Bi lift() { return Longs::compare; }
 static final Box box() { return Longs::compare; }
 static final Twice again() {return NumberUtils::compare;}
 static long oracle(int x,int y) {return (x>y?1:x<y?-1:0);}
 public static boolean primitiveGood(int x,int y) { return lift().cmp(x,y)==oracle(x,y); }
 public static boolean primitiveWrong(int x,int y) {return lift().cmp(x,y)>=0;}
 public static boolean returnGood(short x,short y) {return again().cmp(x,y)==oracle(x,y);}
 public static boolean returnWrong(short x,short y) {return again().cmp(x,y)>=0;}
 public static boolean boxedGood(int x,int y) {return box().cmp(x,y)==oracle(x,y);}
 public static boolean boxedWrong(int x,int y) {return box().cmp(x,y)>=0;}
 public static boolean boxedNull() {try{box().cmp(null,1);return false;}catch(NullPointerException ok){return true;}}
 public static boolean staticGood(int x,int y) {return (long)Longs.compare((long)x,(long)y)==oracle(x,y);}
 public static boolean staticWrong(int x,int y) {return (long)Longs.compare((long)x,(long)y)>=0;}
}
```

#### callbacks/LiftChecks.java

```java
public class LiftChecks {
 public static void correct(int x,int y) { assert Lift.primitiveGood(x,y); }
 public static void wrong(int x,int y) { assert Lift.primitiveWrong(x,y); }
 public static void reach() {Lift.lift().cmp(2,3);assert false;}
 public static void transfer(short x, short y) {assert Lift.returnGood(x,y);}
 public static void transferWrong(short x,short y) {assert Lift.returnWrong(x,y);}
 public static void boxed(int x,int y) {assert Lift.boxedGood(x,y);}
 public static void badBox(int x,int y) {assert Lift.boxedWrong(x,y);}
 public static void boxNull() {assert Lift.boxedNull();}
 public static void boxNullWrong() {assert !Lift.boxedNull();}
 public static void staticOK(int x,int y) {assert Lift.staticGood(x,y);}
 public static void staticBad(int x,int y) {assert Lift.staticWrong(x,y);}
 public static void main(String[] a) {for(int x: new int[]{Integer.MIN_VALUE,-1,0,1,Integer.MAX_VALUE})for(int y: new int[]{Integer.MIN_VALUE,-1,0,1,Integer.MAX_VALUE}){correct(x,y);boxed(x,y);transfer((short)x,(short)y);}boxNull();try{wrong(-1,0);throw new Error();}catch(AssertionError e){}try{transferWrong((short)-1,(short)0);throw new Error();}catch(AssertionError e){}try{boxNullWrong();throw new Error();}catch(AssertionError e){}}
}
```

#### callbacks/Replay.java

```java
final class Replay {
 public static void main(String[] args) {
  if (Lift.primitiveWrong(0,1) || Lift.boxedWrong(0,1) || Lift.returnWrong((short)0,(short)1)
   || Lift.staticWrong(0,1073741824) || Lift.staticWrong(-1,0) || !Lift.boxedNull()) throw new AssertionError();
  System.out.println("All exact control inputs replayed.");
 }
}
```

#### callbacks/Chain.java

```java
import java.util.Comparator;
import com.google.common.collect.ComparisonChain;
import com.google.common.primitives.Longs;
public class Chain {
 public static int guarded(boolean active,Integer x,Integer y) {
  Comparator<Integer> cmp=Longs::compare;
  return ComparisonChain.start().compare(active?0:1,0).compare(x,y,cmp).result();
 }
 public static boolean good(int x,int y){return guarded(true,x,y)==(x>y?1:x<y?-1:0);}
 public static boolean wrong(int x,int y){return guarded(true,x,y)>=0;}
 public static boolean skipsNull(){return guarded(false,null,null)==1;}
 public static boolean rejectsNull(){try{guarded(true,null,0);return false;}catch(NullPointerException e){return true;}}
}
```

#### callbacks/ChainTests.java

```java
public class ChainTests {
 public static void good(int x,int y){assert Chain.good(x,y);}
 public static void wrong(int x,int y){assert Chain.wrong(x,y);}
 public static void reach(){Chain.guarded(true,-1,2);assert false;}
 public static void skips(){assert Chain.skipsNull();}
 public static void rejects(){assert Chain.rejectsNull();}
 public static void main(String[] a){good(-1,2);skips();rejects();try{wrong(0,1);throw new Error();}catch(AssertionError e){}}
}
```

#### numeric/NodeChecks.java

```java
import com.fasterxml.jackson.databind.node.DoubleNode;
import com.fasterxml.jackson.databind.node.LongNode;
import org.apache.commons.lang3.mutable.MutableLong;

public final class NodeChecks {
    static final long BASE = 1L << 54;

    static long roundedInteger(long n) {
        long fraction = n - BASE;
        long high = fraction >>> 31;
        long low = fraction & 0x7fffffffL;
        long halfway = 1L << 30;
        if (low > halfway || (low == halfway && (high & 1L) != 0)) high++;
        return BASE + (high << 31);
    }

    public static boolean direct(long n) {
        if (n < BASE || n >= 2 * BASE) return true;
        return (double)new LongNode(n).floatValue() == (double)roundedInteger(n);
    }

    public static boolean same(long n) {
        if (n < BASE || n >= 2 * BASE) return true;
        LongNode node = new LongNode(n);
        return node.floatValue() == new DoubleNode(node.doubleValue()).floatValue();
    }

    public static boolean publicSubnormal(double x) {
        if (!(x >= 0x1p-150 && x <= 0x1p-149)) return true;
        return new DoubleNode(x).floatValue() == (x == 0x1p-150 ? 0f : 0x1p-149f);
    }

    public static boolean wrongSubnormal(double x) {
        if (!(x >= 0x1p-150 && x <= 0x1p-149)) return true;
        return new DoubleNode(x).floatValue() > 0;
    }

    public static boolean intrinsicSubnormal(double x) {
        if (!(x >= 0x1p-150 && x <= 0x1p-149)) return true;
        return (float)x == (x == 0x1p-150 ? 0f : 0x1p-149f);
    }

    public static boolean mantissaSubnormal(long k) {
        double x = Double.longBitsToDouble(0x3690000000000000L | (k & 0x000fffffffffffffL));
        return new DoubleNode(x).floatValue() == ((k & 0x000fffffffffffffL) == 0 ? 0f : 0x1p-149f);
    }

    public static boolean commons(long n) {
        if (n < BASE || n >= 2 * BASE) return true;
        return (double)new MutableLong(n).floatValue() == (double)roundedInteger(n);
    }
}
```

#### numeric/NodeAssertions.java

```java
public class NodeAssertions {
    public static void direct(long n) { assert NodeChecks.direct(n); }
    public static void same(long n) { assert NodeChecks.same(n); }
    public static void sub(double x) { assert NodeChecks.publicSubnormal(x); }
    public static void bad(double x) { assert NodeChecks.wrongSubnormal(x); }
    public static void intrinsic(double x) { assert NodeChecks.intrinsicSubnormal(x); }
    public static void commons(long n) { assert NodeChecks.commons(n); }
    public static void reachJ() { NodeChecks.same((1L<<54) + (1L<<30) + 1L); assert false; }
    public static void reachD() { NodeChecks.publicSubnormal(0x1p-150); assert false; }
    public static void main(String[] args) {
        java.util.Random rand = new java.util.Random(611);
        for (int i = 0; i < 100000; i++) {
            long n = NodeChecks.BASE + (rand.nextLong() & (NodeChecks.BASE - 1));
            double x = Double.longBitsToDouble(0x3690000000000000L | (rand.nextLong() & 0xfffffffffffffL));
            direct(n); commons(n); sub(x);
        }
        for (double x : new double[]{0x1p-150,Math.nextUp(0x1p-150),Math.nextDown(0x1p-149),0x1p-149}) sub(x);
        try { same((1L << 54) + (1L << 30) + 1); throw new Error(); }
        catch (AssertionError expected) { System.out.println("LongNode double-rounding witness"); }
        try { bad(0x1p-150); throw new Error(); }
        catch (AssertionError expected) { System.out.println("Half-minimum subnormal witness"); }
    }
}
```

#### numeric/ConversionEquivalence.java

```java
import com.fasterxml.jackson.databind.node.DoubleNode;
import com.fasterxml.jackson.databind.node.LongNode;

public final class ConversionEquivalence {
    public static boolean classified(long n) {
        long base = 1L << 54;
        if (n < base || n >= 2 * base) return true;
        long k = n - base;
        long high = k >>> 31;
        long delta = (k & 0x7fffffffL) - (1L << 30);
        boolean mismatch = (high & 1) == 0 ? (delta == 1 || delta == 2) : (delta == -1 || delta == -2);
        LongNode node = new LongNode(n);
        float a = node.floatValue(), b = new DoubleNode(node.doubleValue()).floatValue();
        return (a != b) == mismatch;
    }
}
```

#### rows/RaggedProof.java

```java
import org.apache.commons.lang3.ArrayUtils;
import org.apache.commons.collections4.iterators.ObjectArrayIterator;
public class RaggedProof {
 public static boolean reversed(int[][] a) {
   if(a==null || a.length!=2) return true;
   int[] left=a[0], right=a[1];
   ArrayUtils.reverse(a);
   if(a[0]!=right || a[1]!=left) return false;
   if(left==null || right==null || left.length==0 || right.length==0) return true;
   int r=right[0];left[0]=~left[0];
   return (right[0]!=r)==(left==right);
 }
 public static boolean wrong(int[][] a) {
   if(a==null || a.length!=2) return true;
   int[] left=a[0];ArrayUtils.reverse(a);return a[0]==left;
 }
 public static boolean iter(int[][] a) {
   if(a==null || a.length!=2) return true;
   int[] f=a[0];ObjectArrayIterator<int[]> it=new ObjectArrayIterator<>(a);
   if(it.next()!=f)return false;
   a[1]=f;if(it.next()!=f || it.hasNext())return false;
   it.reset();return it.next()==f;
 }
 public static boolean snapshot(int[][] a) {
   if(a==null || a.length!=2) return true;
   int[] old=a[1];ObjectArrayIterator<int[]> it=new ObjectArrayIterator<>(a);
   it.next();a[1]=a[0];return it.next()==old;
 }
 public static boolean distinct(int[][] a) {
   return a==null || a.length!=2 || a[0]==null || a[0].length==0 || a[1]!=a[0];
 }
 static void choose(int[][] a,boolean tie) {if(tie && a!=null && a.length==2)a[1]=a[0];}
 public static void testReverse(int[][] a){assert reversed(a);}
 public static void testWrong(int[][] a){assert wrong(a);}
 public static void testIter(int[][] a){assert iter(a);}
 public static void testSnapshot(int[][] a){assert snapshot(a);}
 public static void testDistinct(int[][] a){assert distinct(a);}
 public static void testAliasReverse(int[][] a,boolean tie){choose(a,tie);assert reversed(a);}
 public static void testAliasDistinct(int[][] a,boolean tie){choose(a,tie);assert distinct(a);}
}
```

#### rows/MadeRows.java

```java
public class MadeRows {
  static int[][] make(int x,int y,boolean tied) {int[] u={x};return new int[][]{u,tied?u:new int[]{y}};}
  public static boolean reverse(int x,int y,boolean tied) {return RaggedProof.reversed(make(x,y,tied));}
  public static boolean iterator(int x,int y,boolean tied) {return RaggedProof.iter(make(x,y,tied));}
  public static boolean alwaysDistinct(int x,int y,boolean tied){return RaggedProof.distinct(make(x,y,tied));}
}
```

#### rows/Ragged.java

```java
import org.apache.commons.lang3.ArrayUtils;
import org.apache.commons.collections4.iterators.ObjectArrayIterator;
public class Ragged {
 public static void reversed(int[][] a) {
   if(a==null || a.length!=2) return;
   int[] left=a[0], right=a[1];
   ArrayUtils.reverse(a);
   assert a[0]==right && a[1]==left;
   if(left==null || right==null || left.length==0 || right.length==0) return;
   int r=right[0];
   left[0]=~left[0];
   assert (right[0]!=r)==(left==right);
 }
 public static void wrong(int[][] a) {
   if(a==null || a.length!=2) return;
   int[] left=a[0];
   ArrayUtils.reverse(a);
   assert a[0]==left;
 }
 public static void iter(int[][] a) {
   if(a==null || a.length!=2) return;
   int[] first=a[0]; ObjectArrayIterator<int[]> it=new ObjectArrayIterator<>(a);
   assert it.next()==first;
   a[1]=first;
   assert it.next()==first && !it.hasNext();
   it.reset(); assert it.next()==first;
 }
 public static void snapshot(int[][] a) {
   if(a==null || a.length!=2) return;
   int[] a1=a[1]; ObjectArrayIterator<int[]> it=new ObjectArrayIterator<>(a);
   it.next(); a[1]=a[0]; assert it.next()==a1;
 }
 public static void reach(int[][] a) {
   if(a==null || a.length!=2 || a[0]==null || a[1]==null || a[0].length==0 || a[1].length==0) return;
   assert false;
 }
 public static void cross(int[][] a) {
   if(a!=null && a.length==2 && a[0]!=null && a[0].length>0 && a[1]==a[0]) assert false;
 }
}
```

#### rows/RaggedJvm.java

```java
public class RaggedJvm {
 interface Op { void run(int[][] a); }
 static int tests, w1, w2, shared, reached;
 static final int[][] rows=new int[14][];
 static {int k=1; rows[k++]=new int[0]; for(int a=-1;a<=1;a++)rows[k++]=new int[]{a}; for(int a=-1;a<=1;a++)for(int b=-1;b<=1;b++)rows[k++]=new int[]{a,b};}
 static int[][] graph(int a,int b,boolean tie) {
  int[] left=rows[a]==null?null:rows[a].clone(),right=tie?left:(rows[b]==null?null:rows[b].clone());
  return new int[][]{left,right};
 }
 static int fails(Op op,int[][] a) {try{op.run(a);return 0;}catch(AssertionError e){return 1;}}
 static void check(int a,int b,boolean tie) {
   tests++; if(fails(Ragged::reversed,graph(a,b,tie))!=0 || fails(Ragged::iter,graph(a,b,tie))!=0)throw new AssertionError();
   w1+=fails(Ragged::wrong,graph(a,b,tie));w2+=fails(Ragged::snapshot,graph(a,b,tie));shared+=fails(Ragged::cross,graph(a,b,tie));reached+=fails(Ragged::reach,graph(a,b,tie));
 }
 public static void main(String[] args){
  for(int a=0;a<14;a++)for(int b=0;b<14;b++)check(a,b,false);
  for(int a=1;a<14;a++)check(a,a,true);
  if(fails(Ragged::wrong,new int[][]{new int[0],null})!=1 || fails(Ragged::snapshot,new int[][]{new int[0],null})!=1)throw new AssertionError();
  System.out.println("total="+tests+" bad inversion="+w1+" bad snapshot="+w2+" shared nonempty="+shared+" both nonempty="+reached);
 }
}
```

#### rows/MatrixRows.java

```java
import org.apache.commons.math3.util.MathArrays;
import org.apache.commons.math3.exception.DimensionMismatchException;
public class MatrixRows {
  public static boolean shape(long[][] a){
    if(a==null || a.length!=2 || a[0]==null || a[1]==null)return true;
    try{MathArrays.checkRectangular(a);return a[0].length==a[1].length;}
    catch(DimensionMismatchException e){return a[0].length!=a[1].length && e.getDimension()==a[0].length;}
  }
  public static boolean same(long[][] a){
    if(a==null || a.length!=2 || a[0]==null || a[1]==null)return true;
    try{MathArrays.checkRectangular(a);return true;}
    catch(DimensionMismatchException e){return false;}
  }
  public static boolean noNull(long[][] a){
    if(a==null || a.length!=1 || a[0]!=null)return true;
    try{MathArrays.checkRectangular(a);return false;}catch(NullPointerException e){return true;}
  }
  public static boolean rectangular(long[][] a) {
    if(a==null || a.length!=2 || a[0]==null || a[1]==null || a[0].length!=a[1].length)return true;
    MathArrays.checkRectangular(a);return true;
  }
  public static boolean singleShape(long[][] a) {
    if(a==null || a.length!=1 || a[0]!=null)return true;
    MathArrays.checkRectangular(a);return true;
  }
  public static void good(long[][] a){assert rectangular(a);}
  public static void singleGood(long[][] a){assert singleShape(a);}
  public static void correct(long[][] a){assert shape(a);}
  public static void wrong(long[][] a){assert same(a);}
  public static void singleton(long[][] a){assert noNull(a);}
  public static void reach(long[][] a){if(a!=null && a.length==2 && a[0]!=null && a[1]!=null && a[0].length==1 && a[1].length==1){MathArrays.checkRectangular(a);assert false;}}
}
```

#### rows/MatrixJvm.java

```java
import org.apache.commons.math3.util.MathArrays;
import org.apache.commons.math3.exception.DimensionMismatchException;
public class MatrixJvm {
  static long[] row(int n){return n<0?null:new long[n];}
  public static void main(String[] args) {
    int checks=0, normal=0, nulls=0, mismatch=0;
    for(int n=-1;n<=2;n++)for(int x=-1;x<=2;x++)for(int y=-1;y<=2;y++){
      if(n<1 && (x!=-1 || y!=-1))continue;
      if(n<2 && y!=-1)continue;
      long[][] m=n<0?null:n==0?new long[0][]:n==1?new long[][]{row(x)}:new long[][]{row(x),row(y)};
      if(n<0)continue;
      if(!MatrixRows.shape(m))throw new AssertionError();
      try{MathArrays.checkRectangular(m);normal++;
         if(n==2 && (x<0 || y<0 || x!=y))throw new AssertionError();}
      catch(NullPointerException e){nulls++;if(n!=2 || (x>=0 && y>=0))throw new AssertionError();}
      catch(DimensionMismatchException e){mismatch++;if(n!=2 || x<0 || y<0 || x==y || e.getDimension()!=x || e.getArgument().intValue()!=y)throw new AssertionError();}
      checks++;
    }
    if(MatrixRows.noNull(new long[][]{null}))throw new AssertionError();
    System.out.println("nonnull outer shape census="+checks+" normal="+normal+" NPE="+nulls+" dimensions="+mismatch);
  }
}
```

</details>

[head]: https://github.com/pilifs/in-the-loop/tree/9d9a860cf379d64549662bd797b33b0416b10c34
[next]: https://chatgpt.com/library?file_id=libfile_fde3_f-2e191a46fe7c8191a774323fac5df54f_1a220e41ac0481919d2d88e5f0713c02&account_id=personal
[cycle1]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/llm-dlc/decisions/single-jbmc-java-semantics-gap.md
[results]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/llm-dlc/loops/jbmc-java-semantics-gap-results.md
[score]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/verification/java-semantics-gap/scorecard.json
[schedules]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/verification/java-semantics-gap/monitor-schedules/measurement.json
[calls]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/lib/src/bmc/mod.rs#L5459-L5470
[interp]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/lib/src/interp/value.rs#L29-L34
[witness]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/lib/src/witness.rs#L595
[fp]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/lib/src/bmc/floating.rs#L347-L368
[params]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/lib/src/bmc/mod.rs#L586-L597
[ref-input]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/lib/src/bmc/reference_inputs.rs
[369]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/examples/369-boxed-ragged-rows/README.md
[379]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/examples/379-nullable-reference-arrays/README.md
[decimal]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/examples/375-commons-lang-decimal-precision/adapter/datawork/Decimals.java
[runner]: https://github.com/pilifs/in-the-loop/blob/9d9a860cf379d64549662bd797b33b0416b10c34/lib/benchmark/java-semantics-gap/campaign.py
[guava-longs]: https://github.com/google/guava/blob/f06690fa3e874f65515e8fd338a74d636e2c792f/guava/src/com/google/common/primitives/Longs.java
[chain]: https://github.com/google/guava/blob/f06690fa3e874f65515e8fd338a74d636e2c792f/guava/src/com/google/common/collect/ComparisonChain.java
[ordering]: https://github.com/google/guava/blob/f06690fa3e874f65515e8fd338a74d636e2c792f/guava/src/com/google/common/collect/Ordering.java#L620-L625
[lang-number]: https://github.com/apache/commons-lang/blob/29ccc7665f3bc5d84155a3092ab2209a053324e6/src/main/java/org/apache/commons/lang3/math/NumberUtils.java
[lang-long]: https://github.com/apache/commons-lang/blob/29ccc7665f3bc5d84155a3092ab2209a053324e6/src/main/java/org/apache/commons/lang3/mutable/MutableLong.java
[reverse]: https://github.com/apache/commons-lang/blob/29ccc7665f3bc5d84155a3092ab2209a053324e6/src/main/java/org/apache/commons/lang3/ArrayUtils.java#L6822-L6857
[object-compare]: https://github.com/apache/commons-lang/blob/29ccc7665f3bc5d84155a3092ab2209a053324e6/src/main/java/org/apache/commons/lang3/ObjectUtils.java#L311-L325
[fill]: https://github.com/apache/commons-lang/blob/29ccc7665f3bc5d84155a3092ab2209a053324e6/src/main/java/org/apache/commons/lang3/ArrayFill.java#L143
[iterator]: https://github.com/apache/commons-collections/blob/7f7fb0244abc940a2e9dd28b67508c0483a58c3e/src/main/java/org/apache/commons/collections4/iterators/ObjectArrayIterator.java
[queue]: https://github.com/apache/commons-collections/blob/7f7fb0244abc940a2e9dd28b67508c0483a58c3e/src/main/java/org/apache/commons/collections4/queue/CircularFifoQueue.java
[jackson-long]: https://github.com/FasterXML/jackson-databind/blob/f644a920f4ac768797edf7709070411837c83ef8/src/main/java/com/fasterxml/jackson/databind/node/LongNode.java
[jackson-double]: https://github.com/FasterXML/jackson-databind/blob/f644a920f4ac768797edf7709070411837c83ef8/src/main/java/com/fasterxml/jackson/databind/node/DoubleNode.java
[math-arrays]: https://github.com/apache/commons-math/blob/16abfe5de688cc52fb0396e0609cb33044b15653/src/main/java/org/apache/commons/math3/util/MathArrays.java
[lambda-spec]: https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/invoke/LambdaMetafactory.html
[convert-spec]: https://docs.oracle.com/javase/specs/jls/se21/html/jls-5.html
[jbmc]: https://diffblue.github.io/cbmc/man/jbmc.html

## Setup Agent Notes

### What is ready, and where

- `$B = ~/.cache/in-the-loop/jbmc-fast-follow`. Released libraries, signed and checksummed, with sources jars and
  ordered classpaths: `$B/releases/{guava-33.4.8-jre,commons-lang3-3.17.0,commons-collections4-4.5.0,commons-math3-3.6.1,jackson-2.19.0}/classpath.txt`.
  Offline re-resolution works: `mvn -o -s $B/maven-settings.xml` in `$B/resolve/NAME`.
- Source at every revision the brief links, all exactly the release tags: `$B/src/{guava-33.4.8,commons-lang-3.17.0,commons-collections-4.5.0,jackson-databind-2.19.0,commons-math-3.6.1}`.
  The released sources jars equal these files.
- The brief's appendix fixtures, extracted by its own script and compiled on JDK 21.0.13:
  `$B/fixtures/fast-follow-fixtures/{callbacks,numeric,rows}/` with classes in `out/FAMILY/`; the matching library
  classpaths in `$B/fixtures/FAMILY.cp`. Use these for the brief's sample commands (`--classes out/numeric
  --classpath "$(cat $B/fixtures/numeric.cp)"`).
- JBMC 6.11.0: 22.04 package in `$B/jbmc/ubuntu-22.04/` (numerical rows), 24.04 installed (`jbmc` on `PATH`,
  `/usr/lib/core-models.jar`; callbacks and rows). Digests match the brief.
- The JDK classes the brief names, from the Temurin 21.0.13 image, with digests equal to the brief's:
  `$B/jdk/temurin-21.0.13/classes/java/util/{Comparator,Arrays}.class` (51 related classes alongside).
- The checker's release binary at this head: `lib/target/release/jvmcontract` (sha256 `e41539fd…00be65`, built from `c41bda17`'s `lib/`, before any change of yours).

### What was verified on a JVM

Every appendix program behaves as the brief says: `LiftChecks`, `Replay`, `ChainTests`, `NodeAssertions`,
`RaggedJvm` (209 graphs, 12 shared nonempty) and `MatrixJvm` (21 shapes: 8 normal, 7 NPE, 6 mismatch). The exact
witness bits (`0x5a800001` direct vs `0x5a800000` through double; `+0.0f` at `2^-150`), the disagreement
classification on a finite grid of 8,192 bins, and the reserve cases' JVM facts (−2 for `U+D800` vs `U+D802`,
`Ordering.min` identity, `ArrayFill` covariance, `CircularFifoQueue.isFull()` false at two of two) also held. The
javac bootstrap descriptors are recorded in the setup record's
[descriptor table](#method-reference-descriptors-in-the-classfiles).

### What to know before starting

- The repository is past the brief's `9d9a860c`: this head includes the cycle-3 merge (`30a84499`) and the Commons
  Lang decimal decisions. The kickoff check passes here (`scorecard.py --check`: 38 historical, 60 original). Pin
  your successor commit and the checker digest yourself, as the brief asks.
- The fixtures were compiled to class version 65 with the brief's `javac` command. The campaign runner compiles with
  `-source 8 -target 8`; if your intake needs that, recompile — the descriptors above do not change.
- JDK is Temurin 21.0.13, not Debian's build; the two class digests the brief gives match it exactly, so the
  `Comparator` and `Arrays` profiles are reproducible here. Other `java.base` classes were not compared with Debian's.
- The two JBMC models jars are compiled differently and can change answers; name the pairing in each standalone run.
- Nothing is a snapshot: every dependency is a signed release.

### What is left for the domain work on purpose

All JBMC and project-verifier runs (the four-column opening comparison), the replay regression, any example scaffolding
and claims, the choice of standalone classpath profiles (stock models vs. adding `Comparator.class` or `Arrays.class`),
the `-source 8` question, the encodings for the numeric and nested-array work, and every checker change.

## Results

The ordinary native checker decided all 37 statements across method references, numeric conversions and caller-owned primitive rows. It also decided the 12 reserve statements on string ordering and queue histories. Of the 49 decisions, 29 were proofs and 20 were refutations replayed on the original JVM. Strict integrated JBMC decided 26 at matched scope. The per-entry results give both opening checkpoints, named standalone profiles, original JVM controls and the first unresolved comparator operation. [Campaign results](jbmc-fast-follow-calls-conversions-and-arrays-results.md) · [Machine-readable scorecard](../../verification/jbmc-fast-follow/scorecard.json)

The receiver-construction brief can use direct floating-point inputs and a bounded caller-owned `int[][]` or `long[][]`, including nullable, shared and equal-valued distinct rows. The checked examples use height and width two. Automatic discovery of a legal receiver history remains a separate task. [Input and replay handoff](jbmc-fast-follow-calls-conversions-and-arrays-results.md#handoff-to-receiver-construction)

### Method-reference descriptors in the classfiles

These four `LambdaMetafactory.metafactory` sites appear in the opening classfiles. The archived `javap -v` listings identify the interface method type, static target and instantiated method type in that order. [Opening archive with Lift.javap and Chain.javap](../../verification/jbmc-fast-follow/opening/callbacks/paired/raw.tar.gz)

| Caller | Interface method type | Static target | Instantiated method type |
|---|---|---|---|
| Primitive Guava comparison | `(II)J` | `Longs.compare:(JJ)I` | `(II)J` |
| Boxed Guava comparison | `(Ljava/lang/Integer;Ljava/lang/Integer;)J` | `Longs.compare:(JJ)I` | `(Ljava/lang/Integer;Ljava/lang/Integer;)J` |
| Commons Lang short comparison | `(SS)J` | `NumberUtils.compare:(SS)I` | `(SS)J` |
| Guava comparison chain | `(Ljava/lang/Object;Ljava/lang/Object;)I` | `Longs.compare:(JJ)I` | `(Ljava/lang/Integer;Ljava/lang/Integer;)I` |
