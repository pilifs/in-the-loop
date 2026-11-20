# Twenty Java verification examples for the next in-the-loop run

**Start with ordered classpaths (01), partial array copy (03), and signed time formatting/parsing (04).** Each has a finite JVM result already measured, and each can reveal a different mistake even when ordinary tests look good. One changes the answer without changing the client class. One changes state while throwing the expected exception. One passes every round trip while getting both directions wrong.

This is a follow-up to the foundation and Python architecture work. It contains **20 new cases**, split evenly between historical upstream repairs and controlled Java examples. The IDs below are local to this document. Allocate repository IDs from the implementation branch. Each case is a unit of engineering work with multiple independently assessable claims. [Preceding restart brief](https://chatgpt.com/library?file_id=libfile_fde3_f-3a810ae6cf3081918694f7c356004945_1a220e41ac0481919d2d88e5f0713c02&account_id=personal)

## Starting evidence and operating rules

The repository snapshot inspected for this plan was `11413e85`. Example 197 already reports three public native outcomes for two array roots, with qualified JVM refutations. Example 308 already compares a released Commons Text JAR, rebuilt source and a deliberately changed control against 225 cases. Its recorded native run stopped at multidimensional allocation. Use 197 and 308 as regression checks. The witness qualifier at this snapshot has an explicit path for `int[]` and reports other unsupported non-null types. The current agent may already have advanced these paths on its working branch. Reconcile once at startup, then spend time on the remaining gap. [197 results](https://github.com/pilifs/in-the-loop/blob/11413e858e4019ce402b40687ce53e6e87aace54/examples/197-shared-int-array-poststates/README.md) · [308 baseline](https://github.com/pilifs/in-the-loop/blob/11413e858e4019ce402b40687ce53e6e87aace54/examples/308-commons-text-longest-common-subsequence/README.md) · [Witness qualification](https://github.com/pilifs/in-the-loop/blob/11413e858e4019ce402b40687ce53e6e87aace54/examples/tools/targets/qualification.py#L16)

For each case, freeze the **subject, input domain, observation, independent oracle and expected discriminator** before building the proof harness. For historical repairs, build the parent and fix separately and run the oracle on both. The source links identify an observed repair boundary. A commit that introduced a defect needs independent historical evidence. For controlled cases, record which implementation is the reference, which change should preserve behavior, and which control should differ.

Use the existing public route and handoff. For a registered example, preview it with `python3 examples/tools/build.py --plan ID`. Inspect its evidence with `python3 examples/tools/targets/workflow_handoff.py handoff ID`. Keep separate identities for source claim, prepared artifacts and execution. Bind the actual entry, checker version, ordered dependencies, bounds and observer. For an adapter, check that it corresponds to a direct JVM call on the admitted inputs. Store each accepted witness with the replayed inputs and observed difference. A missed precondition, unobserved field or unrelated JVM discrepancy cannot decide a claim.

**Strength of the starting evidence.** All 10 upstream repair commits and their first parents were verified. **JVM calibration** means the stated finite observations were run on OpenJDK 21.0.13. **Upstream source** means the repair and its source were inspected and the proposed domain still needs JVM replay. **Finite model calibration** identifies an enumeration outside the JVM. **Proposed fixture** gives expected behavior to check. No new symbolic proof jobs were run in preparing this brief. Calibrations supply oracles and witnesses for the agent to reproduce under the project’s evidence rules.

| Wave | Cases | First shared deliverable |
|---|---|---|
| I · Artifacts and observations | 01–05 | Qualify the chosen class bytes, the exact value or state observed, and multiple outcomes on the same input. |
| II · Heaps and sequences | 06–10 | Replay a nested heap and a sequence of calls, including effects visible through another object. |
| III · Language and library boundaries | 11–15 | Identify the actual callback, bridge, exception chain or compiler lowering responsible for a result. |
| IV · Transfer and cost | 16–20 | Qualify abstract inputs, numerical tolerances and schedules. Measure whether checked summary reuse earns its cost. |

## I. Prove what the runtime actually observed

Start **01, 03 and 04** first. They have distinguishing JVM observations ready for comparison and exercise independent branches of the system: artifact selection, caller-visible state, and specification quality. Run 02 and 05 alongside them once the first records exist.

### 01 · Ordered dependency JARs change an unchanged invoice

**JVM calibration.** Compile one `Invoice.total(int q)` that multiplies `q` by `Rate.value()`. Put the same binary class name in two helper JARs, one returning 2, one returning 3. Swap their order on the classpath. On `q ∈ {−2,−1,0,1,2}`, the JVM returned `[-4,-2,0,2,4]` and `[-6,-3,0,3,6]`. The zero-only preservation claim holds. Four inputs refute unrestricted equivalence.

**Engineering outcome.** Observe the value and record the code source of the loaded `Rate` separately. Bind each side’s **ordered** closure and selected class bytes to its prepared claim. A receipt from the opposite order must fail qualification even though the set of JARs and the client bytes are identical. Use a fresh classloader or JVM per side.

### 02 · Commons Lang maximum preserves the sign of zero

**Upstream source.** Check `NumberUtils.max(double...)` on every array of lengths 1–3 over `{−1.0,−0.0,+0.0,+1.0}` (84 arrays). The independent oracle ranks those four bit patterns in that order. For `[-0.0,+0.0]` the parent retains negative zero and the fix returns positive zero. Freeze separate claims for ordinary numeric equality and raw result bits. Both produce numeric zero.

**Engineering outcome.** Carry the selected floating-point observer through planning, the checker and JVM replay. Encode raw bits in a lossless representation that survives JSON. Use reversed input order as a companion and avoid drawing conclusions about NaNs from this domain.

[Parent c3e09d34](https://github.com/apache/commons-lang/commit/c3e09d34864d434ad671944d693d67ee07206cfc) → [fix aafee70b and upstream changes](https://github.com/apache/commons-lang/commit/aafee70bfdfc7617ed509b54e3971441a3a5f57d)

### 03 · Partial array copy before a type mismatch

**JVM calibration.** Copy each `Object[]` of length 0–3 over `{null,"A",Integer(1)}` into an equally long `String[]` filled with `"x"`. Compare `System.arraycopy` with a proposed refactor that checks every element before copying. An independent oracle copies through the last assignable element before the first mismatch. Across 40 JVM inputs, both versions threw `ArrayStoreException` on the same 25, yet 12 final arrays differed. For `["A",1]` the destinations were `["A","x"]` and `["x","x"]`.

**Engineering outcome.** Qualify the exception class and caller-visible state *on exceptional exit* independently. Preserve reference-array component type, per-element runtime type and nulls in the replay. Require a preserving companion on completely assignable inputs. [Java array-copy contract](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/System.html#arraycopy(java.lang.Object,int,java.lang.Object,int,int))

### 04 · ThreeTen-Extra negative fractional seconds

**Upstream JVM calibration.** For `TaiInstant.ofTaiSeconds(s,n)` use seconds −2…2 and nanos in `{0,1,500000000,999999999}`. Independently render the signed total nanoseconds as seconds with nine fractional digits, and feed those canonical strings directly to `parse`. Freeze formatting, parsing and object round-trip as three claims. On 20 inputs the parent had **6 format errors, 6 parse errors, 0 round-trip errors**. The fix had **0/0/0**.

**Engineering outcome.** At −0.5 seconds the correct text is `-0.500000000s(TAI)`. The parent printed `-1.500000000s(TAI)` and parsed the correct text as positive half a second. Actual pinned upstream classes were exercised on OpenJDK 21.0.13. Use different oracle inputs for the two directions and keep each method’s outcome identifiable within a shared preparation.

[Parent 5361f0d3](https://github.com/ThreeTen/threeten-extra/commit/5361f0d32889e1a5104743429c3716e5de0937ce) → [fix 1a51a1dc and upstream changes](https://github.com/ThreeTen/threeten-extra/commit/1a51a1dc391ddbcbcb20eb7b9d13ceedf6a47c3c)

### 05 · Commons CSV format equality across row limits

**Upstream source.** Build `CSVFormat.DEFAULT` variants with `maxRows ∈ {1,2,10}` and keep all other fields fixed. On the nine ordered pairs, the configuration oracle says equal exactly when the limits match. The parent ignores this field. A separate claim requires equal objects to have equal hashes. Add a read of three simple rows to show that limits 1 and 2 produce different row counts.

**Engineering outcome.** Represent immutable builder results and correlate distinct entry points without conflating their contracts. Unequal objects are allowed to share a hash. Refuting equality for a differing configuration must not automatically refute the Java hash contract.

[Parent 69248ba0](https://github.com/apache/commons-csv/commit/69248ba0bed03c71454b71ec0c79805f48f5c447) → [fix 6d5993cb and upstream changes](https://github.com/apache/commons-csv/commit/6d5993cb89f4f723ae416123b20f361bd863c484)

## II. Reconstruct richer inputs and histories

Use the same bounded-input and replay machinery across nested arrays, sequential commands, builders and live views. A real library case is the acceptance consumer for every general facility added here.

### 06 · Theatre seat matrix with independently allocated rows

**Proposed fixture.** Build a rectangular `int[][]` with 1–3 rows and 1–2 columns, initially zero. Mark one valid seat. Compare `new int[rows][cols]` with separately allocated rows as a preserving change and with one row reused for every seat row as a control. Enumerate all 18 shape/seat combinations. The oracle is a coordinate grid plus a row-identity relation. At 2×1, marking `(0,0)` gives `[[1],[0]]` versus `[[1],[1]]`.

**Engineering outcome.** Freeze outer shape, cell values and row identity as three claims. Check the emitted multidimensional allocation and qualify a nested-array witness through the public route. This isolates the allocation blocker seen in 308 and exercises an observer and input reconstruction beyond 197. Re-running 308 is a transfer check for this example.

### 07 · A bounded queue’s acknowledgments and final contents

**Finite model calibration.** Capacity 2. Enumerate all 121 command words of length 0–4 over `{offer A, offer B, poll}`. A full queue rejects an offer, and an empty poll returns a distinct empty marker. Compare with an evict-oldest-and-accept variant. An independent list model compared all traces. In that enumeration 40 acknowledgment/result histories differ and 28 final queues differ. Three offers of A leave identical contents and different acknowledgments. Offers A,B,A also change contents.

**Engineering outcome.** Use one replay format for operation sequences, initial state, per-step result and final state. Minimize traces against the particular disagreement. A witness for the response-history claim can cease to be a witness when only final contents are observed.

### 08 · Guava immutable map with two equal-hash keys

**Upstream source.** Call JVM Guava’s `ImmutableMap.Builder.buildKeepingLast()`. Generate put traces of length 0–4 over three keys, including `"QED"` and `"R&D"`, with the one-based position as each value. The oracle scans backward for each key. The upstream regression puts the two keys alternately with values 1,2,3,4 and expects two entries with values 3 and 4. Keep all-unique inputs as a preservation control.

**Engineering outcome.** Observe `size`, lookup, and the set of key/value pairs from the entry view. Treat entry enumeration order only as part of a separately declared order claim. Reuse the trace machinery from 07 with a builder and a new immutable result. Pin the JVM artifact and the actual runtime key type.

[Parent 825de9a2](https://github.com/google/guava/commit/825de9a2d00de439eea29112e92b98333d81d670) → [fix 87d550f3 and upstream changes](https://github.com/google/guava/commit/87d550f3fe7dc22540b1b6dba21179a1b2b92658)

### 09 · Commons Collections live multiset views

**Upstream source.** Seed a `HashMultiSet` with counts of A and B independently in 1…3. Remove one element via an iterator from `uniqueSet()` or `entrySet()`. The oracle subtracts the full multiplicity of the key actually returned. At counts 3 and 2 the new total must be 2 or 3 depending on which key was removed. The parent can expose correct membership but stale aggregate size. The other element’s count should be preserved.

**Engineering outcome.** Bind iterator, view and underlying multiset identities to the same replay heap. Record the element selected on each side and compare under the same selection, or quantify over permitted selections. This lets both runs satisfy the same oracle even if hash iteration order differs.

[Parent a70ffd61](https://github.com/apache/commons-collections/commit/a70ffd614602fa07d2429d76f77abcd1816d0be9) → [fix e218502f and upstream changes](https://github.com/apache/commons-collections/commit/e218502f9f82237404bbce8e8ba5f81ffb467198)

### 10 · JFreeChart’s numeric range with an empty series

**Upstream source.** Call the shared `TimeSeriesCollection.getRangeBounds(List,Range,boolean)` overload. Give two named series either no point or one point at year 2012 valued −1, 0 or 1. Select both and require at least one finite value. Pin the calendar zone and an x-range covering the year. The independent oracle filters missing values and scans the rest for min/max. One empty series plus `[1.0]` should yield `[1,1]`.

**Engineering outcome.** Check lower and upper fields separately, reverse the selected key order, and use two populated series as a preservation companion. Bind the same historical method descriptor on both revisions. The one-argument overload was added in the fix. The all-empty policy is outside this packet.

[Parent f210e33d](https://github.com/jfree/jfreechart/commit/f210e33d06f03354fb49b98d2b2282f8c9a89303) → [fix 3b1283db and upstream changes](https://github.com/jfree/jfreechart/commit/3b1283db18f530478ea8b71310d713014e7e126a)

## III. Follow execution across Java language boundaries

Use these to distinguish hidden dispatch or compiler behavior from the outcome of the method as seen by its caller. Reuse the evidence formats established in the first two waves.

### 11 · Try-with-resources and ordered suppressed exceptions

**JVM calibration.** Two paint layers L and R, along with body B, can each throw a uniquely tagged instance of the same exception class. Enumerate all eight failure masks. Compare the reference with equivalent nested resource scopes, then with acquisition order reversed. The oracle closes in reverse acquisition order. A body failure remains primary and ensuing failures are appended in order. Reversing acquisition changed the primary tag on 1 mask, the ordered suppressed tags on 2, and the close trace on all 8.

**Engineering outcome.** Store the primary exception and ordered suppressed observations with distinct descriptors. In the all-throw mask both primaries are B but the sequences are `[R,L]` and `[L,R]`. Equality of exception classes alone misses it. Qualify the preserving nested form on the same eight masks. [Java resource semantics](https://docs.oracle.com/javase/specs/jls/se21/html/jls-14.html#jls-14.20.3)

### 12 · A generic bridge and its typed method

**JVM calibration.** Implement `Mapper<Integer>.map(Integer)` so null returns 99 and each other value returns `n+1`. Invoke via erased `map(Object):Object` and the typed descriptor where applicable. Inputs are null, −1, 0, 1, and the string `"one"`. JVM replay showed that the string throws `ClassCastException` before entry to the typed body. A control returns 2 instead of 1 for zero. The string behavior and the answers for null, −1 and 1 are preserved.

**Engineering outcome.** Inspect the emitted bridge flag, descriptors and call target. Record return, exception and typed-body entry count. Restrict any bridge-to-typed equivalence claim to the shared admissible inputs. Publish the wrong-type observation on the erased entry only.

### 13 · Lazy Optional fallback and callback effects

**JVM calibration.** Compare `Optional.orElseGet` with an equivalent explicit branch and with an eager `orElse(fallback.get())`. The fallback returns 7 and records a call. Test empty and present values 0,1,2. Return values agree on all four. The eager control makes an extra callback on all three present values. On empty, all versions call once.

**Engineering outcome.** Represent an observable callback inside a library call and qualify the callback trace separately from the return. Identify the selected supplier implementation and distinguish a proof about the actual callback from a run using a modeled supplier.

### 14 · One source method, two string-concatenation bytecodes

**JVM calibration.** Compile `label(int n,String s)` returning `"S" + n + "/" + s` to an older and newer bytecode target. Inputs use `n ∈ {−1,0,10}` and `s ∈ {null,"","x"}`. Use a nine-entry literal oracle. On the same JDK 21 JVM, the two builds agreed on all nine results although disassembly showed `StringBuilder.append` versus `invokedynamic`. A proposed control omits `/` only for null, changing three results.

**Engineering outcome.** Record compiler version, flags, target class version, disassembly and runtime JDK separately. The calibration used `-source 8 -target 8` with the host JDK and a JDK 21 default build. It establishes same-runtime agreement on this table. A Java 8 runtime claim would require that runtime.

### 15 · Commons Lang duration format tokens separated by a literal

**Upstream source.** Call `DurationFormatUtils.formatDuration` for 0…12 whole hours, either padding flag and patterns `HxH`, `H'x'H`, `HH` (78 inputs). A small table specifies two single-width hour fields separated by x for the first two patterns and one optionally padded field for the third. At five hours the expected strings include `5x5` and padded `05`. An independent formatter can produce them directly from the hour integer.

**Engineering outcome.** Bind the public entry and exact returned characters. Check separated fields, quoting equivalence, and adjacent-field preservation as independent claims. The adapter must pass the raw pattern through to the upstream lexer. Reuse 14’s string observation with a parser behind it.

[Parent 1d3a7462](https://github.com/apache/commons-lang/commit/1d3a74622d000b86cd2a9aa5962ffea5c7bc0ff9) → [fix 3f0c0fd5 and upstream changes](https://github.com/apache/commons-lang/commit/3f0c0fd5cb8af9f2ae6d7f869d7e87c66985ab90)

## IV. Check transfer, scope and cost

Use 16–18 to stress the prior recipes on different libraries. Reserve 19 for an explicitly bounded schedule model and 20 for a like-for-like performance and reuse decision. These five can progress independently when their prerequisites exist.

### 16 · Joda-Time distances between partial calendar dates

**Upstream source.** Use `Days.daysBetween(ReadablePartial,ReadablePartial)` with concrete `MonthDay` objects and ISO chronology in UTC. From Feb 27, Feb 28, Feb 29, Mar 1 and Mar 2, enumerate 25 ordered pairs. Compare with offsets 0…4 on a leap-year template. Feb 28 → Feb 29 should produce one day. Feb 28 → Mar 1 should produce two. March-only cases give a preserving companion.

**Engineering outcome.** Observe normal return versus exception and the signed day count for normal returns. Test reversal only on inputs for which both calls returned. Capture the concrete subtype, chronology and reference-year semantics in the adapter’s scope. A full `LocalDate` would exercise a different path.

[Parent efce9916](https://github.com/JodaOrg/joda-time/commit/efce99164f0bbd2c70e7f9d71884a32473e02c6d) → [fix 3a413d78 and upstream changes](https://github.com/JodaOrg/joda-time/commit/3a413d7844c22dc6ddd50bf5d0d55ff3589e47ac)

### 17 · Commons Math fraction percentage at a representation boundary

**Upstream source.** Call `new Fraction(n,1).percentageValue()`. Use both signs of `21,474,836 + k` for `k ∈ {−2,−1,0,1,2}` and the values −1, 0 and 1. The independent oracle computes `100L*n` and converts that exact integer to double. For `n=21,474,837` the parent wraps to −2,147,483,596 and the correct result is +2,147,483,700. All oracle values in this packet are exactly representable.

**Engineering outcome.** Check value, normal completion, and preservation on the small controls. Reuse 02’s raw floating-point observer on an upstream method that crosses an integer-to-double boundary. Freeze denominator 1, which explains why an exact comparison is justified.

[Parent a49e443c](https://github.com/apache/commons-math/commit/a49e443c44766df45d254e13bea377d4133f5ee6) → [fix 63a48705 and upstream changes](https://github.com/apache/commons-math/commit/63a48705a496bf2506121dcddbd8cac2a78f877c)

### 18 · Commons Geometry’s first intersection at a cube vertex

**Upstream source.** Use `PolyhedronsSet.firstIntersection` on the unit cube with the upstream test tolerance. Freeze the four upstream diagonal rays (forward/reverse, outside/center), plus two perpendicular face-center hits. The independent oracle intersects each ray with the three coordinate intervals using rational arithmetic and takes the first positive boundary parameter. A ray from `(−1,−1,−1)` towards `(1,1,1)` first meets `(0,0,0)`.

**Engineering outcome.** Observe presence of a hit and the coordinates of the returned facet-plane intersection. Several facets share a vertex, so different facet identities can represent the same geometric answer. Pin tolerance and the coordinate comparison rule. Start with six controls and retain a named blocker if the geometry object graph exceeds the checker’s supported profile.

[Parent f57f82be](https://github.com/apache/commons-geometry/commit/f57f82bea38dcf8646edb3c7f5f70818281a4c77) → [fix 17833efe and upstream changes](https://github.com/apache/commons-geometry/commit/17833efe2b8f1b563e8c261a28d26af441a3778c)

### 19 · Two editors incrementing the same revision

**Proposed fixture.** Model two editors as four explicit read/write steps with each editor’s read before its write. Enumerate all six legal schedules from revision 0. One version increments the current value on each write. Another writes back the value saved at read plus one. An independent trace interpreter predicts 2 on both serial schedules and 1 for the second version on the other four. For `read A, read B, write A, write B`, the two answers are 2 and 1.

**Engineering outcome.** Make the schedule part of the admitted input and the replay witness. Preserve the order constraints when minimizing. Report this as a finite, deterministic interleaving model. Generalizing to live Java threads or memory-model behavior requires separate semantics and evidence.

### 20 · Floor tilings as a proof-reuse and cost benchmark

**Proposed fixture.** Count tilings of a row of length `n=0…18` with tiles of lengths 1 and 2. Compare recursive and bottom-up implementations. The independent oracle sums `choose(n−k,k)` for `k=0…floor(n/2)`. There are 4,181 tilings at 18. A control that discards the two-cell choice returns 1 instead of 2 at `n=2`. Exercise both a caller returning the exact count and another reporting its parity.

**Engineering outcome.** Compare inlining with reuse of a checked helper summary on identical bytes, obligations and budgets. Change the helper’s base case in a separate control and verify both dependent callers reassess their evidence. Measure cold/warm preparation, solve and replay, plus peak RSS. Preserve a genuinely slower or interrupted attempt. A higher search bound gets its own qualification. Adopt the optimization only if evidence and comparable costs justify it.

## How to run the campaign

Keep the runs parallel where the implementation allows it. A shared feature is worth merging when a small case exposes the missing behavior and another case can consume it. The pairs below give each infrastructure investment a second customer.

| Shared change | Build against | Demonstrate transfer on |
|---|---|---|
| Artifact binding, ordered classpaths and entry descriptors | 01 | 12 and 14, then the cache-invalidation check in 20 |
| Typed evidence for arrays, nested references and exceptional state | 03 and 06 | 09 for a live view and 11 for ordered exception data |
| One replay format for histories and observable callbacks | 07 | 08, 13 and 19 |
| Explicit field, numeric and string observers | 02 and 04 | 10, 15, 17 and 18 |
| Independent obligations sharing one preparation | 04 and 05 | 11 and 16, then the two consumers in 20 |

**After wave I**, show one example where changing the artifact invalidates old evidence and one where the same execution supports different claim dispositions. **After wave II**, provide a successfully replayed nested-state or multi-operation witness, together with a companion claim it cannot refute. **After wave III**, give one reusable public recipe that a second case can adopt without a new example-specific Python driver. **After wave IV**, report the 20 example dispositions, all predeclared claim/subject pairs, and the evidence for the next shared capability.

If a backend stops at a missing model, first record the unsupported construct, stage and attempted scope. Continue with the independent JVM oracle and another unblocked packet. When two cases hit the same gap, address it once and requeue both at their original bounds. An adapter, smaller domain or modeled operation can earn its own scoped result. Keep the original obligation visible. Use a direct and a distinguishing control for any newly supported backend profile, with independent JVM replay for the selected observer.

**History and measurement.** On one multi-claim batch, reorder the claims and interrupt after the first result. A fresh checkout should recover the same per-claim identities, completed evidence and missing stages. Retry under a new attempt ID. For an expensive case, keep at least one baseline and changed-strategy attempt, including a slower result or genuine timeout if one occurs. Compare resource use only when artifacts, checker, domain, observer and resource policy match apart from the intentional change. Keep cold and warm cache results separate.

**Final report.** For each required claim/subject pair, show the expected result, obtained result, route, scope, independent replay coverage and first blocker or qualifying receipt. Count decided claims, open claims, withdrawals and contradictions separately from attempts or fixtures authored. Report wall time and peak RSS for comparable runs, plus the first phase that dominates. Surface any accepted result contradicted by its oracle immediately. A precise refusal is valuable diagnostic evidence and leaves the corresponding proof obligation open.
