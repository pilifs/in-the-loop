# Closing the Java semantics gap with JBMC

**Implementation brief · 22 November 2026 · Baseline [`pilifs/in-the-loop` at `d717edd2`][head] · Comparator [JBMC 6.11.0][jbmc]**

**Start with immutable lists and floating point.** Lists offer the quickest route to recovering decisions that JBMC already made with models this project owns. Two unchanged Apache Commons Lang callers offer the stronger test of new capability. One rounds a rational to binary32 across 16.8 million inputs. The other narrows a double to an integer across 2⁵² values and observes what happens after mutating the receiver. Stock JBMC decided both and rejected both deliberately wrong alternatives.

Follow those with offset-sensitive UTF-16 matching and caller-supplied reference arrays. Use one public Guava change as an independent check on exception handling and caller-visible state. Agents own the implementation strategy. The deliverable is a larger set of strict, reproducible Java claims at their declared scope, with evidence of which changes carry over to another caller.

## What the comparison actually says

The frozen 7 November benchmark ran both engines on the same 187 claims at `c9995ae1`, with a 120-second deadline, unwind 16 and maximum array length 8. Pairing strict native with the benchmark’s **staged, integrated JBMC** results gives the following counts. [Raw results][historical] · [Benchmark design][bench]

| Both returned the expected verdict | Only native | Only integrated JBMC | Neither |
|---:|---:|---:|---:|
| 133 | 24 | 13 | 17 |

Twelve of the 13 JBMC-only decisions concern immutable lists. The other is `enumValueOf/2`. These counts describe that checkout and its models. The latest Spring/data campaign already decided boxed ragged rows (2/2 primary claims), Vavr transpose (4/4) and three of four Commons Lang NaN-search claims at ordinary native scope. Its positive-tolerance companion covers wide array cells at three fixed target centers. The public decimal parser still has four open native claims. [Campaign results][recent] · [Decimal parser][decimal] · [NaN search][nan]

**Fresh preflight.** The following observations used Debian OpenJDK 21.0.13 and, where indicated, standalone JBMC 6.11.0. The native evidence below comes from the inspected source, checked-in expectations and campaign receipts. A fresh native run requires the execution VM’s checker or Rust toolchain. Rerun the exact entries on the execution VM before crediting a gap or a closure.

| Family | Observed in preflight | Native starting evidence |
|---|---|---|
| Immutable lists | JBMC gave two expected proofs and two JVM-replayed refutations with six repository model classes. With packaged core models alone, both positive controls produced JVM-contradicted failures. | The current conformance register marks all four unverifiable. The native model evidence specifically identifies the varargs and search operations. [Register][conf] · [Model scope][listmodel] |
| Wide floating point | JBMC proved both Commons Lang callers on their full declared intervals. The JVM exhausted the rational-input interval and replayed the narrowing witness and boundary controls. | Most arithmetic and conversions fall back to enumeration of at most 64 reachable operand tuples. Integer-to-double already has a symbolic implementation. [Floating-point engine][fp] |
| Offset prefix | JBMC proved a 16-input control and refuted the wrong end-offset rule at exactly offset 5 with the empty prefix. The JVM agreed on every input. | The interpreter implements the overload. The ordinary `NumberUtils.createNumber` campaign names the symbolic call as its first blocker. [Interpreter][interp] · [Caller results][recent] |
| Reference-array entry | With a nullable `Item[]` parameter, stock JBMC proved the classifier’s range and refuted both “the first cell can never be null” and “the first cell can never contain an item.” The JVM realized all four classifier outcomes. | The low-level symbolic entry filter handles primitive and String arrays. The project also has separate constructor/planned-heap routes. Measure each with its actual input domain. [Entry types][entry] · [Construction route][heap] |
| Covariant stores | On a raw `Object[]` view of a `String[]`, stock JBMC accepted “the write always succeeds.” The JVM threw `ArrayStoreException` on the incompatible value and preserved the old cell. | Native explicitly refuses the incompatible single-element `aastore`. Example 314 already covers partial writes by `System.arraycopy`. [Store implementation][store] · [Example 314][314] |

## The example queue

### 1. Immutable lists from a caller-owned array

Run `conformance/listOfArray/{1,2}` and `conformance/listSearch/{1,2}` through the normal strict runner. The first method constructs immutable lists from two- and three-element `Integer[]` arrays, overwrites the source arrays and reads the lists. The registered expected result is 111 when `n != 9`. Removing that guard admits `n=9`, which passes a null varargs array and throws `NullPointerException`. The lookup method uses both unique and duplicate elements. At `n=5` it returns 90, refuting the proposed invariant `result < 0`. These are four distinct claims. [Claim definitions][cases] · [Java methods][methods]

For an opening receipt with the historical staging policy, run the following from the repository root and repeat with `--cases conformance/listSearch`. Write each result to a separate path.

```sh
python3 lib/benchmark/run.py --groups 1 --engines native,jbmc --modes strict \
  --jbmc-staging staged --cases conformance/listOfArray --timeout 120 \
  --out /tmp/listOfArray-opening.json
```

The six classes that sufficed for standalone JBMC were `List`, `ImmutableCollections` and its nested `List12`, `ListN`, `ListItr` and `AbstractImmutableList`. Preflight used an exception-aware Java assertion wrapper around the checked-in methods. Three of these four claims occur among the historical 13 JBMC-only decisions. Keep the fresh wrapper results and the integrated results distinguishable. [Repository model bytecode][models]

**Transfer.** Use a second public caller that builds a list from a mutable array, then overwrites a slot and mutates a *referenced object*. The slot replacement must be isolated, while the object mutation must remain visible through the retained element reference. A shallow copy and a deep copy return the same initial elements. This history distinguishes them. Bind any identity claim about canonical empty lists to the tested JDK/model. Report the portable shallow-copy claim independently.

### 2. Wide arithmetic on two real Commons Lang callers

Use the exact Commons Lang revision already acquired for the decimal campaign, `5904c573`. These are new callers on that revision. The historical fix changed a different method. The runnable appendix includes both claims and their negative controls. [Fraction source][fraction] · [MutableDouble source][mutable]

| Entry and quantified input | What to prove | What must fail |
|---|---|---|
| `Fraction.getFraction(n, 2).floatValue()`, every integer with 2²⁴ ≤ n < 2²⁵ | Widen the returned float to double. It equals `(n >>> 1) + ((n & 3) == 3 ? 1 : 0)`. In this interval odd numerators put the result halfway between neighboring floats, and the even neighbor wins. | Always taking the floor fails for 4,194,304 of the 16,777,216 JVM inputs. At `n=33_554_431` the method returns 16,777,216. |
| `new MutableDouble(x).intValue()`, then `setValue(-x)` and `intValue()`, every binary64 value with 2³¹ ≤ x < 2³² | The first result is `Integer.MAX_VALUE` and the second is `Integer.MIN_VALUE`. This includes all 2⁵² representable inputs in the interval. | Substituting `(int)(long)x` for `(int)x` fails at exactly 2³¹, raw bits `0x41e0000000000000`. The substituted expression returns `Integer.MIN_VALUE` on the positive input. |

Keep a direct opcode twin for each caller so a first refusal can be attributed to input binding, conversion, arithmetic, dispatch or object construction. A raw-bit `long` input is a viable route for the double case if its mapping covers the declared interval exactly and its public JVM replay reconstructs the same value. A small selector grid earns its own finite result. Maintain the full interval for the primary claim. The machine-level route is open to the agent.

### 3. UTF-16 prefix matching at an offset, then decimal parsing

Start with `"ababa".startsWith(prefix, off)` for `prefix` in `{"","ba"}` and every offset from −1 through 6. The empty prefix succeeds at offsets 0 through 5 inclusive. The other prefix succeeds at 1 and 3. Changing `<= 5` to `< 5` produces one counterexample. JBMC also passed the intended equivalence assertions in its tagged upstream prefix regression. Its deliberately false reachability assertion fails as intended. [Upstream startsWith regression][starts]

**Widen the claim.** Use two independently symbolic, non-null Strings of 0–4 UTF-16 code units, any Java `int` offset, and a separate `charAt` oracle. Reject `off < 0 || off > text.length() - prefix.length()` before comparing cells. Include a lone surrogate, matching surrogate pairs, identical and equal-distinct strings, and both extreme offsets in replay. Check a null prefix at a valid offset as its own exception claim. Record the result under JBMC string refinement and under the project’s usual string configuration. This proposed wider claim has only the small and upstream controls measured so far.

**Transfer.** Rerun the four registered `NumberUtils.createNumber` claims at example 375 on their original classpaths and ordinary startup. The existing oracles observe result class, exact decimal coefficient and scale, and the malformed input’s exception. Report the old and new blocker per claim, including any other parser operation reached after fixing the prefix. An offset proof and an end-to-end parser decision each get their own row. [Example 375][decimal]

### 4. Nullable reference arrays and the receiver behind a declared type

Start at a method whose actual parameter is `Item[]`. With maximum length 2 and object-tree depth 4, exercise the null array, the empty array, a null first cell and a populated first cell. Two opposite false assertions force both element shapes to be reachable. The appendix checks this directly. Upstream has paired regressions for the same distinction. [Null-cell regression][cell1] · [Populated-cell regression][cell2]

Next admit two cells holding equal-valued distinct objects or the same object. Mutate through the first and observe the second. Deliver a replay that reconstructs sharing, and a separate replay that reconstructs equal-but-distinct references. If a backend’s object factory generates only trees, an explicit constructor or selector can supply these graphs for a matched secondary claim. State precisely which heaps the direct-entry claim covers.

**Dispatch and optional public holdout.** In JBMC’s `virtual5` fixture, an assertion about a declared parent parameter returned normally on the JVM for null and an exact parent, and failed with a legal subclass. Run exact-class and parent-or-child input scopes separately. For a public consumer, use Gson #719. Across three JSON kinds (string, object, array) and three requested classes (`JsonElement`, `JsonObject`, `JsonArray`), four incompatible pairs changed from `ClassCastException` to `JsonSyntaxException`. Five compatible pairs preserved the concrete returned class. Both historical trees’ production sources were compiled and all 18 JVM observations were checked. A strict proof of even one incompatible path plus a compatible subclass control would exercise runtime type checks at the public entry. [Dispatch fixture][dispatch] · [Gson parent → fix][gson]

### 5. Soundness control and public transfer for covariant stores

Store a compatible string, null, or an incompatible object through an `Object[]` alias of a one-element `String[]`. Observe the completion class and the original cell through the retained typed reference. For an incompatible in-bounds store the expected outcome is `ArrayStoreException` and the old reference. Add out-of-range and null-array controls to check JVM exception precedence. The preflight stock JBMC disagreement was on the in-bounds incompatible store. This row can earn a strict native decision and expose a comparator disagreement. Track it outside the count of JBMC leads closed. [Native guard][store]

Either public caller can qualify the transfer. The iterator isolates the store and Guava tests whether the fix also preserves input identity on successful paths.

- **Released API.** At Commons Collections 4.5.0, `ObjectArrayListIterator<Number>.set` executes `aastore` at bytecode offset 27. On the JVM, a 12-case grid over `Integer[]` or `Number[]`, before or after `next()`, and replacement integer, null or double produced six `IllegalStateException` outcomes, five successful writes and one `ArrayStoreException`. All seven failures preserved the original cell. [Pinned iterator][iterator]
- **Organic change.** Guava #7955 formats `"%s + %s = %s"` with a caller-owned `Integer[]{5,6,11}`. The parent throws `ArrayStoreException`. The fix returns `"5 + 6 = 11"` and preserves the original references. With a genuine `Object[]{5,6,11}`, both return the same text, but only the parent replaces its elements. This preflight compiled the unmodified historic `Strings.java` on each side against the same released dependencies. Pin both original builds for the campaign proof. [Guava parent → fix][guava]

## Ten additional examples

Start the expansion with **6 (default-method dispatch), 7 (byte reversal) and 8 (Unicode decoding)**. Each has a stock JBMC establishment, a deliberately false claim that reached its assertion, and an independent JVM control. A decision already available on the opening native build counts as existing coverage. Promote the next example whose ordinary entry still exposes a gap.

### 6. Which default interface method runs?

Let `Base.code(x)` return `x+1` and let `Refined extends Base` return `Base.super.code(x)+2`. Call through a `Base` reference on three receivers. One declares `implements Base, Refined`, one reverses that order, and a third supplies a class override returning `x+4`. Stock JBMC established `x+3, x+3, x+4` for all Java ints, including wraparound. On the JVM, `x=0` on the first receiver returned 3 and refuted the declaration-order answer of 1. The appendix reproduces the pair. Keep its JVM replay driver in its own class. In a fresh directory, moving those same replay helpers into the assertion class reversed both JBMC answers while the JVM answers stayed the same. Preserve both classfile variants as a comparator regression. The cause of this sensitivity is open.

The native resolver and concrete interpreter both search implemented interfaces in sequence. Compare both engines with the JVM on the same classfiles. **Acceptance** requires both interface orders, the class override and the qualified `Base.super` call to resolve correctly. This exercises a different rule from a bridge method’s argument cast in #323. [Native resolution][more-resolution] · [Interpreter dispatch][more-interp] · [Upstream default-method controls][more-defaults]

### 7. Reverse every byte of a 32- or 64-bit word

Compare Apache Commons IO 2.19.0’s shift-and-mask implementations `EndianUtils.swapInteger(x)` and `swapLong(x)` with `Integer.reverseBytes` and `Long.reverseBytes`. Stock JBMC proved equality for all 2³² and 2⁶⁴ bit patterns respectively. A half-word rotation is a useful false alternative. At `x=1` the 32-bit results are `0x01000000` and `0x00010000`. The JVM rejected the rotation for both widths and matched both reference calls on 65,536 patterned inputs plus five boundary values per width.

Start strict native at the actual Commons methods. The interpreter already implements `reverseBytes`. The symbolic integer dispatch lists rotations and lacks a dedicated byte-reversal case. Check whether the selected JDK bytecode already supplies the operation. **Acceptance** is both full-width identities and their refutations. A first width that works unchanged is a control for the second. [Commons IO release source][more-endian] · [Symbolic integer dispatch][more-int-bmc] · [Interpreter integer operations][more-int-interp]

### 8. Decode a supplementary character across a `CharSequence` boundary

At Commons Text 1.12.0, call `UnicodeUnpairedSurrogateRemover.translate(sequence, index, writer)` on a custom two-unit `CharSequence` with a recording writer. Its indexed overload delegates through `Character.codePointAt`. Observe both the number of code points consumed and that the writer received no units in a single call. At offset 0 it consumes one for a lone surrogate and zero for a valid high–low pair. At offset 1 a low surrogate is unpaired when decoding starts there, even if unit 0 was high. For `DBFF DFFF`, the two answers are 0 and 1.

Stock JBMC with `--no-refine-strings --unwind 3` proved both offsets over all 2³² ordered unit pairs and refuted “remove every surrogate code unit.” The JVM exercised all 1,048,576 valid pairs and a 589,824-pair boundary grid. Use Commons Lang 3.14.0, the dependency declared by this Text release. For a diagnostic, compare forward and backward decoding with the scalar formula `0x10000 + ((high - 0xD800) << 10) + low - 0xDC00` on valid pairs. **Acceptance** uses the arbitrary `CharSequence` receiver at the public translator. The native engine already handles narrower String and surrogate-helper operations. [Translator][more-translator] · [Remover][more-remover] · [Native JDK method coverage][more-char] · [Upstream code-point regression][more-codepoint]

### 9. Remove through an iterator, then mutate its owner

Construct a two-element `ArrayDeque` with distinct object identities `a,b`. Before the first `next()`, iterator removal throws `IllegalStateException`. After taking `a`, run these two histories from independent fresh deques.

| History | Caller observation on OpenJDK 21.0.13 |
|---|---|
| Iterator removes `a`, then tries to remove it again | The second removal throws `IllegalStateException`. Only `b` remains. The iterator returns that exact object once, then `next()` throws `NoSuchElementException`. |
| Owner calls `pollLast()` before the iterator’s next read | The owner receives the original `b`. The iterator’s next read throws `ConcurrentModificationException` on this implementation and history. |

Stock JBMC reported a failure on the correct claim. Loading eight unmodified `java.base` classes from the target JDK before the packaged models gave the expected establishment and refutation of “the old iterator still returns the next element.” The eight were `ArrayDeque`, `ArrayDeque$DeqIterator`, `AbstractCollection`, `Deque`, `Queue`, `Collection`, `Iterator` and `Objects`. Record their hashes, unwind 16, maximum nondeterministic array length 8 and classpath order. Native has an explicit limited deque model. Check its ordinary JDK-image route separately. Keep the fail-fast claim scoped to this sequential trace and JDK. [Native JDK selection][more-deque-native] · [Deque model scope][more-deque-model] · [JDK iterator][more-deque-jdk]

**Transfer.** Commons Collections 4.5.0’s `FilterIterator` over a `SingletonIterator` distinguishes prefetch from consumption. Two `hasNext()` calls leave the same element pending. `remove()` while it is pending throws `IllegalStateException`. After `next()`, removal delegates and either succeeds or throws `UnsupportedOperationException`, depending on the underlying iterator. Stock JBMC decided the positive and negative claims on the singleton. For the full transfer wrap the actual deque iterator. Removing immediately after consuming `a` leaves `[b]`. Prefetching `b` first makes removal throw while the deque still holds `[a,b]`. After consuming and removing `b`, it holds `[a]`. The released Commons JAR with the same eight JDK classes passed the positive claim and refuted the wrong removal rule. The JVM replayed both histories. [FilterIterator][more-filter] · [SingletonIterator][more-singleton]

### 10. A library constructor calls an override before subclass fields initialize

Subclass the released Commons Lang 3.14.0 `StrBuilder`. Give the subclass a field `phase = 7` and override `append(String)` to record the phase and callback count, then delegate to `super.append`. Pass null, empty or populated text to the superclass constructor. Null skips the callback. Empty text still invokes it. When the constructor calls the override, the subclass field holds its JVM default of 0. After construction, another `append("B")` observes 7 and returns the same builder.

Stock JBMC proved the contents, length, receiver identity, phase and callback count with a nullable source of up to two UTF-16 units. It refuted “empty skips the callback.” A two-case control also refuted “the override sees 7 during construction.” The JVM checked eleven inputs including null, empty, isolated surrogates and a valid pair. **Acceptance** runs the original superclass constructor and checks the callback through the subclass receiver. This is a public test of allocation and initialization order. Its native outcome is open pending preflight. [Pinned constructor][more-ctor]

### 11. Render a negative integer in hexadecimal

For every `16 ≤ n ≤ 255`, require `Integer.toString(-n, 16)` to produce exactly three UTF-16 units. They are a minus sign, the lowercase digit for `n >>> 4`, and the digit for `n & 15`. Compute each digit independently using ASCII arithmetic. Stock JBMC with string refinement established the claim and rejected the rule that places the low digit first. OpenJDK checked all 240 values. The wrong rule disagreed on 225, including `n=190`, which renders as `"-be"`.

The existing native decimal formatting path and the concrete interpreter’s radix conversion offer two starting points. **Acceptance** covers digit order and sign on the original formatting API. Run the packaged string-refinement profile and the project’s ordinary profile separately. If the opening native build already decides the whole interval, widen to `Integer.MIN_VALUE` and a second radix, keeping those results under a new scope. [Java API][more-radix] · [Existing decimal support][more-bytes] · [Interpreter radix conversion][more-radix-interp]

### 12. Decode four bits with an unsigned bounds check

Call Commons Lang’s `Conversion.binaryBeMsb0ToHexDigit(bits, offset)` at `3e50a7f9`. Make the four booleans the high-to-low bits of a nibble `m`. For offsets 0 through 3, require the lowercase hex digit for `m >>> offset`. Every other Java `int` offset must throw the method’s explicit `IndexOutOfBoundsException`. Observe the exception type separately from an accidental `ArrayIndexOutOfBoundsException` arising from an array access.

Stock JBMC proved the production caller for all 16 bit patterns and every signed 32-bit offset under unwind 12. It rejected both replacing the right shift with a left shift and permitting negative offsets. The JVM checked 144 combinations, including both extreme offsets. For example, `1010` at offset 1 encodes `'5'`, and offset −1 must take the explicit exception path. The caller uses `Integer.compareUnsigned`. The interpreter implements it and the symbolic integer dispatch lacks a dedicated case. Confirm strict native at the original method before choosing a change. [Production conversion][more-nibble] · [Symbolic integer dispatch][more-int-bmc]

### 13. Resolve an enum by name and preserve constant identity

Use `enum Mode { OPEN, CLOSED }`. Require `Mode.valueOf(new String("OPEN")) == Mode.OPEN` and check `"CLOSED"` likewise. Null must throw `NullPointerException`. Lowercase `"open"` and unknown `"OTHER"` must throw `IllegalArgumentException`. Check identity and exact exception class. OpenJDK agreed on every case. Both stock JBMC and JBMC with the repository’s `Enum.class` reported JVM-contradicted failures on the lookup properties. Both proved an ordinal control over the two known constants and refuted “the ordinal is always zero” on `CLOSED`.

Rerun the separate frozen `enumValueOf/2` violation first. That historical JBMC-only decision involved one fixed valid name. The expanded lookup is an independent JVM qualification case. Native already checks a backing constants array for enum universes, and the interpreter has lookup logic. **Acceptance** retains the original constant references and distinguishes both error paths through the public generated `Mode.valueOf`. Keep the two scopes in separate scorecard rows. [Historical case][cases] · [Enum universe][more-enum] · [Repository Enum model][more-enum-model]

### 14. Distinguish an absent thread-local value from a stored null

Use two keys on one thread. Each initializer increments its own counter and allocates a fresh item. Repeated `get()` must return the same reference. After `set(null)`, `get()` returns null without calling the initializer. After `remove()`, it initializes again. Include installing the second key’s object in the first, removing an absent key twice, and reading the second key after each history. These observations distinguish value, reference identity and per-key state.

OpenJDK passed four histories both on a `ThreadLocal` subclass and on Spring Core 6.2.0’s public `NamedThreadLocal.withInitial(name, supplier)`. Both refuted “a stored null initializes on the next read.” Stock JBMC’s bundled JAR lacks `ThreadLocal` and reported failures on the true kernel claim. The Spring public transfer was exercised on the JVM. **Acceptance** is strict checking of the supplier calls and observations at the Spring entry. Then rerun one original formatter claim in #374, whose recorded first blocker is the thread-local constructor. Record any next blocker separately. [Spring factory][more-spring] · [Formatter results][recent]

### 15. Identify the monitor shared by two Java threads

Use one caller and one worker, one `start()`, and one shared integer. Initialize it to 5 while the caller holds `Worker.class`. The worker writes 6 under `synchronized(Worker.class)`. Assert the caller still sees 5 inside its critical section. For the negative control, change only the caller’s lock to the worker *instance*. A worker-first execution can now expose 6 at the assertion. Scope this to the two threads, two lock identities and stated histories. Existing #342 and #343 supply bounded monitor-history controls.

With `--java-threading`, stock JBMC established the shared-class-monitor case and refuted the mixed-monitor case. Now change the worker body to a `static synchronized` method. Its monitor is the declaring class. JBMC 6.11.0’s upstream fixture emits a warning that it ignores this modifier and fails the true assertion. The JVM control observed 5 under the lock and 6 after release and join. **Acceptance** includes a JVM-replayable mixed-lock schedule and a matched-lock protection claim with explicit scheduling scope. Record the upstream static-method warning alongside the target property. A proof over a manually enumerated schedule receives credit for that schedule set. [Upstream fixture and known issue][more-monitors] · [Native monitor bytecode path][more-monitor-native] · [Existing two-worker example][more-two-workers]

## Execution and acceptance

1. **Freeze the opening score.** Record the latest execution SHA, JDK, native binary, JBMC binary, model hashes and classpath order. Recount the historical 13 at that head, keeping `enumValueOf/2` and the 24 former native-only rows as regression controls. Run the new claim families once before implementing anything. A case already closed at that head is useful baseline coverage. Allocate example IDs on the execution branch. This inspected branch ends at 375.
2. **Compare equivalent questions.** Run explicit strict native and explicit integrated JBMC. Where the frontend refuses, run stock JBMC on the original compiled Java assertion and label it standalone. Identify any project-supplied model layer. Match guards, receiver construction, aliasing, startup, loaded application bytecode, array and string limits, unwinding and observers. In the opening table, a 120-second per-claim reference budget matches the historical corpus. A higher-budget retry has a separate result. Preserve differential configurations such as JBMC string refinement. [Runner][runner] · [Standalone precedent][sides]
3. **Qualify the result.** Keep the target assertion ID, its reachability control, other property and unwinding results, model provenance, and the JVM replay of each refutation. Record which path and input were reproduced. Report incomplete unwinding, timeout, missing body, model divergence, or frontend refusal by name. The H2 comparison previously reported a successful caller assertion even on a revision where the original JVM refuted the claim. The full run also contained failing properties. [H2 comparison][h2]
4. **Choose the next change from the result.** Start lists and wide arithmetic independently. Prefer an ordinary public caller or a second consumer once the narrow capability works. If a production claim stops at a different subsystem, retain the receipt, name the next blocker and move to the next family unless the fix will serve another queued caller. Keep witnesses, qualified models and runner paths usable by subsequent examples.
5. **Close with a before/after table.** For each frozen claim show expected result, scope, opening native, final native, standalone or integrated JBMC profile, JVM replay, wall time and first unresolved cause. Publish counts for native proofs, replayed native refutations, new decisions on previously JBMC-only rows, native regressions and JVM-contradicted verdicts. Report finite grids, narrowed inputs and assumed models at their own scope. Preserve the frozen denominator if an overlapping campaign lands while work is running.

**Target for a successful run.** Recover at least two independently confirmed JBMC-only rows at unchanged scope, earn one full-interval numeric establishment with its replayed negative control, and decide one additional public-caller claim or one direct-entry reference-array claim. Recheck the matched controls and require zero new JVM-contradicted native verdicts. The stretch is both numeric callers plus either an ordinary #375 decision or a Guava parent/fix pair. If a target remains open, hand back the smallest reproducer, the exact failed obligation and the last original public result. The architecture and division of work are the agent’s choice.

**Scoring the expansion.** Give examples 6–15 their own opening and final rows. For 6–12 record whether the native build can already reach the public entry and match the known JBMC result under the specified model profile. For 13–15 retain separate rows for a JVM-confirmed behavior, a matched comparator control and any model disagreement. The mixed-lock control in 15 can earn a parity decision independently of the static-method disagreement. Aim to gain strict native decisions in two additional semantic families, including a real library caller. Report how many distinct families changed and how many claims moved at the original scope.

## Runnable seed

Save the following block as `Semantics.java`. It supplies eight small JBMC entry points plus a JVM oracle run. Set `LANG_CP` to compiled production classes or a JAR from the pinned Commons Lang revision, and `CORE_MODELS` to the `core-models.jar` packaged with the tested JBMC. The scope flags below reproduce the eight results in this appendix. The repository’s historical integrated benchmark uses its own profile.

```sh
javac -source 8 -target 8 -g -cp "$LANG_CP" Semantics.java
java -ea -cp ".:$LANG_CP" Semantics
for entry in fraction floorOnly narrow wraps prefix categories noNullCell noItemCell; do
  status=0
  jbmc Semantics -cp ".:$LANG_CP:$CORE_MODELS" --function "Semantics.$entry" \
    --unwind 8 --unwinding-assertions --throw-runtime-exceptions \
    --max-nondet-array-length 2 --max-nondet-tree-depth 4 --sat-solver cadical \
    --trace --json-ui > "$entry.json" || status=$?
  case "$status" in 0|10) ;; *) exit "$status" ;; esac
done
```

Preflight produced `SUCCESS` for the named assertions in `fraction`, `narrow`, `prefix` and `categories`, and `FAILURE` for those in `floorOnly`, `wraps`, `noNullCell` and `noItemCell`. Every accompanying property succeeded. Deliberately false assertions give JBMC exit code 10. JVM runs use assertions enabled. The preflight JBMC executable SHA-256 was `2cf572542163ad3926d0030f4594e4697fcd09a0c60b62dc58901ca3aa18065c`. Its packaged model JAR was `2a05026b3ab948ebb4820ccc2fc01040b96e226dc1f58a3be36dfe0c15ed14de`. The VM’s previously recorded 6.11.0 binary has a different digest. [VM tools manifest][vm]

```java
import org.apache.commons.lang3.math.Fraction;
import org.apache.commons.lang3.mutable.MutableDouble;

public final class Semantics {
    static final class Item { int value; }

    public static void fraction(int n) {
        if (n < (1 << 24) || n >= (1 << 25)) return;
        double got = Fraction.getFraction(n, 2).floatValue();
        int floor = n >>> 1;
        assert got == floor + ((n & 3) == 3 ? 1 : 0);
    }
    public static void floorOnly(int n) {
        if (n < (1 << 24) || n >= (1 << 25)) return;
        assert (double) Fraction.getFraction(n, 2).floatValue() == (n >>> 1);
    }
    public static void narrow(double x) {
        if (!(x >= 0x1p31 && x < 0x1p32)) return;
        MutableDouble d = new MutableDouble(x);
        int high = d.intValue();
        d.setValue(-x);
        assert high == Integer.MAX_VALUE && d.intValue() == Integer.MIN_VALUE;
    }
    public static void wraps(double x) {
        if (!(x >= 0x1p31 && x < 0x1p32)) return;
        assert new MutableDouble(x).intValue() == (int) (long) x;
    }
    public static void prefix(int off, boolean empty) {
        if (off < -1 || off > 6) return;
        boolean got = "ababa".startsWith(empty ? "" : "ba", off);
        assert got == (empty ? off >= 0 && off <= 5 : off == 1 || off == 3);
    }
    static int kind(Item[] a) {
        if (a == null) return -2;
        if (a.length == 0) return -1;
        return a[0] == null ? 0 : 1;
    }
    public static void categories(Item[] a) {
        int k = kind(a);
        assert -2 <= k && k <= 1;
    }
    public static void noNullCell(Item[] a) { assert kind(a) != 0; }
    public static void noItemCell(Item[] a) { assert kind(a) != 1; }

    public static void main(String[] args) {
        if (!Semantics.class.desiredAssertionStatus()) throw new IllegalStateException("Use -ea");
        for (int n = 1 << 24; n < 1 << 25; n++) fraction(n);
        narrow(0x1p31);
        narrow(Math.nextUp(0x1p31));
        narrow(Math.nextDown(0x1p32));
        for (int off = -1; off <= 6; off++) {
            prefix(off, false);
            prefix(off, true);
        }
        assert kind(null) == -2 && kind(new Item[0]) == -1;
        assert kind(new Item[1]) == 0 && kind(new Item[]{new Item()}) == 1;
    }
}
```

## Runnable opening checks for the expansion

Save the block as `ExtraOpeners.java`. Set `IO_JAR` to the released Commons IO 2.19.0 JAR and use the same packaged `CORE_MODELS` as above. The JVM entry replays all three false assertions. The six stock JBMC entries below were checked with string refinement and returned the expected named property results.

```sh
javac -source 8 -target 8 -g -cp "$IO_JAR" ExtraOpeners.java
java -ea -cp ".:$IO_JAR" ExtraOpenersReplay
for entry in dispatch firstDeclared endian halfSwap hex lowFirst; do
  status=0
  jbmc ExtraOpeners -cp ".:$IO_JAR:$CORE_MODELS" --function "ExtraOpeners.$entry" \
    --unwind 16 --unwinding-assertions --throw-runtime-exceptions \
    --sat-solver cadical --trace --json-ui > "extra-$entry.json" || status=$?
  case "$status" in 0|10) ;; *) exit "$status" ;; esac
done
```

Expect `SUCCESS` on `dispatch`, `endian` and `hex`. Expect one named assertion `FAILURE` on each of `firstDeclared`, `halfSwap` and `lowFirst`, with the accompanying properties successful.

```java
import org.apache.commons.io.EndianUtils;

public class ExtraOpeners {
    interface Base { default int code(int x) { return x + 1; } }
    interface Refined extends Base {
        default int code(int x) { return Base.super.code(x) + 2; }
    }
    static class BaseFirst implements Base, Refined {}
    static class RefinedFirst implements Refined, Base {}
    static class Own implements Refined { public int code(int x) { return x + 4; } }

    static Base receiver(int k) {
        if (k == 0) return new BaseFirst();
        if (k == 1) return new RefinedFirst();
        return new Own();
    }
    public static void dispatch(int k, int x) {
        assert receiver(k).code(x) == x + (k == 0 || k == 1 ? 3 : 4);
    }
    public static void firstDeclared(int x) { assert receiver(0).code(x) == x + 1; }

    public static void endian(int x) { assert EndianUtils.swapInteger(x) == Integer.reverseBytes(x); }
    public static void halfSwap(int x) { assert EndianUtils.swapInteger(x) == Integer.rotateLeft(x, 16); }

    static char digit(int x) { return (char) (x < 10 ? '0' + x : 'a' + x - 10); }
    public static void hex(int n) {
        if (n < 16 || n > 255) return;
        String s = Integer.toString(-n, 16);
        assert s.length() == 3 && s.charAt(0) == '-'
            && s.charAt(1) == digit(n >>> 4) && s.charAt(2) == digit(n & 15);
    }
    public static void lowFirst(int n) {
        if (n < 16 || n > 255) return;
        assert Integer.toString(-n, 16).charAt(1) == digit(n & 15);
    }

}

class ExtraOpenersReplay extends ExtraOpeners {
    static void rejected(Runnable test) {
        try { test.run(); }
        catch (AssertionError expected) { return; }
        throw new IllegalStateException("A false claim survived");
    }
    public static void main(String[] args) {
        for (int k = 0; k < 3; k++) {
            for (int x : new int[]{0, 5, Integer.MAX_VALUE}) dispatch(k, x);
        }
        endian(1);
        for (int n = 16; n <= 255; n++) hex(n);
        rejected(() -> firstDeclared(0));
        rejected(() -> halfSwap(1));
        rejected(() -> lowFirst(190));
        System.out.println("All three witness replays passed");
    }
}
```

[head]: https://github.com/pilifs/in-the-loop/tree/d717edd200ec3a781b7c7e179200e4a7dc549740
[jbmc]: https://github.com/diffblue/cbmc/tree/cbmc-6.11.0/jbmc
[historical]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/benchmark/results.json
[bench]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/benchmark/README.md
[recent]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/llm-dlc/loops/spring-and-java-data-workstream-results.md
[decimal]: https://github.com/pilifs/in-the-loop/tree/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/375-commons-lang-decimal-precision
[nan]: https://github.com/pilifs/in-the-loop/tree/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/373-commons-lang-nan-search
[conf]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/tests/conformance.rs
[listmodel]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/values.rs#L332
[fp]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/bmc/floating.rs#L233
[interp]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/interp/natives.rs#L1190
[entry]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/bmc/mod.rs#L577
[heap]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/spec/heap.rs
[store]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/bmc/mod.rs#L2976
[314]: https://github.com/pilifs/in-the-loop/tree/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/314-arraycopy-exceptional-prefix
[cases]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/benchmark/conformance.json
[methods]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/tests/conformance/conformance/Conformance.java
[models]: https://github.com/pilifs/in-the-loop/tree/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/models/classes
[fraction]: https://github.com/apache/commons-lang/blob/5904c573ffacaa5d8836ffc2b346f400c8901ed1/src/main/java/org/apache/commons/lang3/math/Fraction.java
[mutable]: https://github.com/apache/commons-lang/blob/5904c573ffacaa5d8836ffc2b346f400c8901ed1/src/main/java/org/apache/commons/lang3/mutable/MutableDouble.java
[starts]: https://github.com/diffblue/cbmc/tree/cbmc-6.11.0/jbmc/regression/jbmc-strings/StartsWith
[cell1]: https://github.com/diffblue/cbmc/tree/d29720523b363987a3c5ccf6d4255a813fb8fe47/jbmc/regression/jbmc/no-main-object-array-elements-maybe-null1
[cell2]: https://github.com/diffblue/cbmc/tree/d29720523b363987a3c5ccf6d4255a813fb8fe47/jbmc/regression/jbmc/no-main-object-array-elements-maybe-null2
[dispatch]: https://github.com/diffblue/cbmc/tree/d29720523b363987a3c5ccf6d4255a813fb8fe47/jbmc/regression/jbmc/virtual5
[gson]: https://github.com/google/gson/compare/10714ef0427536b679e9677f8417807e4cce017d...80c98ef0261826430a601cddfa5f3003627146c5
[iterator]: https://github.com/apache/commons-collections/blob/7f7fb0244abc940a2e9dd28b67508c0483a58c3e/src/main/java/org/apache/commons/collections4/iterators/ObjectArrayListIterator.java
[guava]: https://github.com/google/guava/compare/47b7e9e5ef3f2267f8ac327d68cc56b99e186aa8...148cea0778b7ea2e362c794c02b29a62bd93daa2
[runner]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/benchmark/run.py
[sides]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/benchmark/external-upgrades/baselines/jbmc_sides.py
[h2]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/llm-dlc/loops/external-upgrade-evaluation-results.md
[vm]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/benchmark/external-upgrades/v0.json
[more-resolution]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/classpath.rs#L1741
[more-interp]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/interp/mod.rs#L736
[more-defaults]: https://github.com/diffblue/cbmc/tree/820ff0f555b43fb78e0cd9332e498461bd14244b/jbmc/regression/jbmc/default-methods
[more-endian]: https://github.com/apache/commons-io/blob/2186f41bbae123ed355a77137e9be10c0b4c4630/src/main/java/org/apache/commons/io/EndianUtils.java
[more-int-bmc]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/bmc/mod.rs#L6331
[more-int-interp]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/interp/natives.rs#L2691
[more-translator]: https://github.com/apache/commons-text/blob/2c2d0818b0540c59f055f5174db51d0574af46da/src/main/java/org/apache/commons/text/translate/CodePointTranslator.java#L35
[more-remover]: https://github.com/apache/commons-text/blob/2c2d0818b0540c59f055f5174db51d0574af46da/src/main/java/org/apache/commons/text/translate/UnicodeUnpairedSurrogateRemover.java
[more-char]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/classpath.rs#L1488
[more-codepoint]: https://github.com/diffblue/cbmc/tree/d29720523b363987a3c5ccf6d4255a813fb8fe47/jbmc/regression/jbmc-strings/toCodePoint
[more-deque-native]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/classpath.rs#L1317
[more-deque-model]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/models/java/util/lists/ArrayDeque.java
[more-deque-jdk]: https://github.com/openjdk/jdk21u/blob/ba94eace682733f66e623c089bcafcf4a1b8e39c/src/java.base/share/classes/java/util/ArrayDeque.java#L676
[more-filter]: https://github.com/apache/commons-collections/blob/7f7fb0244abc940a2e9dd28b67508c0483a58c3e/src/main/java/org/apache/commons/collections4/iterators/FilterIterator.java#L103
[more-singleton]: https://github.com/apache/commons-collections/blob/7f7fb0244abc940a2e9dd28b67508c0483a58c3e/src/main/java/org/apache/commons/collections4/iterators/SingletonIterator.java
[more-ctor]: https://github.com/apache/commons-lang/blob/c8774fa74adbbbcd4e5f915ab6bc3aa10d877419/src/main/java/org/apache/commons/lang3/text/StrBuilder.java#L306
[more-radix]: https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/Integer.html#toString(int,int)
[more-bytes]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/bmc/bytes.rs#L34
[more-radix-interp]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/interp/natives.rs#L2663
[more-nibble]: https://github.com/apache/commons-lang/blob/3e50a7f9cf103357d781483d41ec9c9386e69e9d/src/main/java/org/apache/commons/lang3/Conversion.java#L110
[more-enum]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/bmc/enum_universe.rs
[more-enum-model]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/models/java/lang/Enum.java
[more-spring]: https://github.com/spring-projects/spring-framework/blob/v6.2.0/spring-core/src/main/java/org/springframework/core/NamedThreadLocal.java
[more-monitors]: https://github.com/diffblue/cbmc/tree/d29720523b363987a3c5ccf6d4255a813fb8fe47/jbmc/regression/jbmc-concurrency/synchronized-methods
[more-monitor-native]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/bmc/mod.rs#L4362
[more-two-workers]: https://github.com/pilifs/in-the-loop/tree/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/343-synchronized-map-reservations

## Setup Agent Notes

### What is ready, and where

- Everything is under `~/.cache/in-the-loop/jbmc-java-semantics-gap` (`$B`); the [layout](#layout) table says what
  each folder holds. Worktrees for every pinned revision are in `$B/src/`. Released jars with ordered classpaths are
  in `$B/releases/NAME/classpath.txt`, and built jars are in `$B/artifacts/`.
- Commons Lang `5904c573` (§2, §3: `commons-lang-5904c573.jar`) and `3e50a7f9` (#12, `target/` kept). Released Lang
  3.14.0, IO 2.19.0, Text 1.12.0, Collections 4.5.0, Spring Core 6.2.0, and Guava 33.4.8-jre and 33.5.0-jre, all
  signature-checked.
- Gson #719 parent and fix jars (JDK 8). Guava #7955 parent and fix jars, `$B/artifacts/guava-7955-{parent,fix}.jar`,
  built from the original commits by a job, with their runtime classpath in
  `$B/logs/guava-7955-{parent,fix}.guava.classpath.txt` (the same five jars on both sides). Also: 33.4.8-jre and
  33.5.0-jre carry exactly the parent's and the fix's `Strings.java`, and `probes/guava/slice-{parent,fix}/` holds
  each side's own `Strings.class` built against 33.4.8.
- JBMC 6.11.0 in two forms. `/usr/bin/jbmc` with `/usr/lib/core-models.jar` is the 24.04 package, what the runner
  uses by default. `$B/releases/cbmc-6.11.0/ubuntu-22.04/{bin/jbmc,lib/core-models.jar}` is the brief's preflight
  pair, with matching digests. That pair reproduces all 14 seed results; its runs are in `$B/jbmc-runs/preflight-22.04/`.
- The upstream JBMC fixtures, compiled, in `$B/regressions/`. The brief's two seeds, compiled, in
  `$B/probes/seed/cls/`. The JDK 21.0.13 classes the brief names, with digests, in `$B/jdk/temurin-21.0.13/`.

### What was verified on a JVM

Every observation the brief reports that a JVM can make, on Temurin 21.0.13, matched; the [table](#what-was-replayed-on-a-jvm)
lists them. This covers both seeds' oracles, the §2 counts and witnesses, Gson's 18 observations and its regression
(the fix's test fails on the parent with `ClassCastException`), the §5 kernel, iterator grid and Guava parent/fix,
and #6–#15. Two upstream tests were run as parent/fix pairs. Gson's `DefaultTypeAdaptersTest` passes on each side, and
the fix's version fails on the parent with `ClassCastException`. Guava's `StringsTest` passes on each side (21 tests),
and the fix's version errors on the parent in `testLenientFormat` with `ArrayStoreException: java.lang.String`. The
`Lenient` probe gives the brief's §5 answers on the two built Guava jars as well as on the slices and the releases.

On the comparator side (not a JVM check, but the brief's other preflight): the brief's JBMC binary and models
reproduce all 14 seed results, and all 11 `CORE` upstream regression files pass under each pairing.

### What to know before starting

- **Two JBMC packages, and the models matter.** The installed JBMC and models are not the brief's preflight pair. With
  the installed `core-models.jar`, #6 flips both ways: `ExtraOpeners.dispatch` reports FAILURE (brief: SUCCESS) and
  `firstDeclared` reports SUCCESS (brief: FAILURE), the declaration-order answer the JVM refutes. With the 22.04
  models, under either binary, both are as the brief says. Nothing else moves. Name the binary and models jar in
  every comparator row (`$B/jbmc-runs/*/summary.txt`).
- **JDK:** Temurin 21.0.13, not Debian's build. The named `java.base` sources are identical to jdk21u at `ba94eace`;
  class bytes may differ from the brief's preflight, so the #9 hashes recorded here are Temurin's.
- **Gson** needs JDK 8 and Surefire 2.18.1 on the command line (the default Surefire refuses JUnit 3.8.2).
  **Guava** needs the JDK 24 toolchain and the `user.home` redirect given [above](#guava-7955-as-a-job), or its
  plugin downloads a JDK into `~/.m2`. Its build and test now run offline from `$B/m2` (checked by the job). The two
  Guava jars are both version `999.0.0-HEAD-jre-SNAPSHOT`: keep them apart by file name and never `install` either.
  Their `Strings.class` is Java 8 bytecode (major 52); the jars are multi-release, with `module-info` under
  `META-INF/versions/9`.
- **The four setup jobs' results are on another head**, `965e5e2efb74` (the Guava job's own commit is `7ab232b4515a`),
  which this line has not merged; `pipeline.py status` lists them as "recorded on another head". Read them with
  `jj file show -r 7ab232b4515a PATH`, or merge that head first.
- **Commons Lang `3e50a7f9` and `5904c573` are 3.21.0-SNAPSHOT builds** whose jar digests include timestamps:
  compare class digests, not jar digests.
- The CBMC `test.desc` classpaths name `jbmc/lib/java-models-library/target/…`, which the 6.11.0 tree does not
  contain; the job substitutes the packaged `core-models.jar` and `cprover-api.jar` of each pairing.
- No snapshot dependencies were resolved from a remote; every input here is pinned by commit or by release checksum.

### What is left for the domain work on purpose

All claims and scopes, example ids and scaffolding, adapters and sidecars. Also: the opening score (recounting the
historical 13, freezing model hashes for the score), every native and integrated JBMC run, and the choice of §1's
and §3's transfer callers. The grids the brief only sketches (#7's patterned inputs, #8's boundary grid, #15's
schedules) and the #6 classfile-variant comparator regression are not built. Why the models jar flips #6's
`dispatch` and `firstDeclared` is not investigated.
