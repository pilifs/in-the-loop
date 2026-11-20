# Twenty Java verification examples

All 125 declared claim and subject pairs were decided on their stated domains. Exhaustive JVM checking established **92** and refuted **33**. Each refutation reproduced in a separate JVM. The strict native checker independently established **47**, refuted **20** and left **58** open. There were **zero withdrawals and zero contradictions** across the accepted evidence.

The campaign covers ten historical repairs and ten controlled examples. The ten upstream fixes and their first parents were pinned separately. Direct JVM drivers ran 639 case inputs across the twenty domains, or 1,355 revision/input combinations when each distinct revision is counted once. The runtime was Eclipse Temurin 21.0.13+9. The register below counts a source claim on a particular revision or revision pair once, however often it ran. [Machine-readable claim register](../../verification/twenty-example-fast-follow-results.json)

## Case outcomes

The grid size is per revision. The two JVM counts are established and refuted claim/subject pairs. The native column counts pairs decided on that route. Each example links to its subject, frozen claims and replay instructions.

| Example | Grid | JVM established / refuted | Native decided | Direct JVM observation |
|---|---:|---:|---:|---|
| [312 Ordered invoice JARs](../../examples/312-invoice-ordered-rate-jars/README.md) | 5 | 3 / 1 | 4 / 4 | Changing the first Rate provider changed four totals. Zero agreed and the unchanged client class had the same digest. |
| [313 Signed-zero maximum](../../examples/313-commons-lang-signed-zero-max/README.md) | 84 | 3 / 1 | 4 / 4 | Seven parent arrays returned the wrong zero bits. Numeric equality held on all 84. The fix matched every bit pattern. |
| [314 Exceptional array copy](../../examples/314-arraycopy-exceptional-prefix/README.md) | 40 | 2 / 1 | 3 / 3 | Both copies threw on 25 inputs. The precheck lost an already-copied prefix on 12. Fully assignable copies agreed. |
| [315 Signed fractional seconds](../../examples/315-tai-signed-fraction/README.md) | 20 | 4 / 2 | 2 / 6 | The parent had six formatting errors and six independently observed parsing errors. All 20 round trips passed on both revisions. |
| [316 CSV row limits](../../examples/316-commons-csv-row-limit-equality/README.md) | 9 | 5 / 1 | 0 / 6 | Six unequal configurations compared equal on the parent. The hash implication and actual row counts held on both revisions. |
| [317 Theatre seats](../../examples/317-theatre-seat-matrix/README.md) | 18 | 7 / 2 | 9 / 9 | Sharing a row changed the marked cells and row identity on 15 inputs. Shape and the independently allocated-row implementation held. |
| [318 Bounded queue](../../examples/318-bounded-queue-histories/README.md) | 121 | 2 / 2 | 4 / 4 | The evicting implementation changed 40 response histories and 28 final queues. Both observers first differed at three commands. |
| [319 Guava map collisions](../../examples/319-guava-last-put-hash-collision/README.md) | 121 | 5 / 3 | 8 / 8 | With String keys QED and R&D the parent had two wrong sizes, ten wrong lookups and two wrong unordered entry sets. Unique keys held. |
| [320 Live multiset views](../../examples/320-collections-live-multiset-views/README.md) | 18 | 5 / 1 | 0 / 6 | All 18 parent sizes were stale. After either iterator removal, membership and the other key’s count agreed with the oracle for the selected key. |
| [321 JFreeChart ranges](../../examples/321-jfreechart-empty-series-range/README.md) | 30 | 6 / 2 | 0 / 8 | The parent missed 12 lower and 12 upper endpoints. Both populated series and the fix passed in both selected-key orders. |
| [322 Suppressed exceptions](../../examples/322-ordered-suppressed-exceptions/README.md) | 8 | 6 / 3 | 1 / 9 | Reversed acquisition changed one primary, two ordered suppressed sequences and all eight close traces. Explicitly nested resources preserved all three. |
| [323 Erased generic bridge](../../examples/323-erased-mapper-bridge/README.md) | 5 | 7 / 1 | 8 / 8 | The changed implementation differed only for zero. A String threw before entry to the typed body. Typed and erased calls agreed on their four shared inputs. |
| [324 Optional callback](../../examples/324-optional-fallback-effects/README.md) | 4 | 5 / 1 | 6 / 6 | All four results agreed. Eager fallback made an extra call on all three present values. The explicit branch preserved both observations. |
| [325 String concatenation bytecode](../../examples/325-compiler-string-concatenation/README.md) | 9 | 2 / 1 | 3 / 3 | The same source compiled to class versions 52 and 65 agreed on all nine strings. The changed implementation omitted the slash on three nulls. |
| [326 Duration format tokens](../../examples/326-commons-lang-separated-duration-tokens/README.md) | 78 | 5 / 1 | 0 / 6 | Separated hour fields produced 52 incorrect parent strings. Quoting equivalence and the adjacent-field controls held. |
| [327 Joda-Time partial dates](../../examples/327-joda-monthday-distance/README.md) | 25 | 8 / 2 | 0 / 10 | The parent threw on nine pairs and disagreed on 17 day observations including throws. Reversal held on all 16 parent and 25 fixed pairs where both calls returned. |
| [328 Fraction percentage](../../examples/328-commons-math-fraction-percentage/README.md) | 13 | 5 / 1 | 0 / 6 | The parent overflowed on four raw double results with denominator one. Both revisions completed normally and agreed on the three small controls. |
| [329 Cube intersections](../../examples/329-commons-geometry-cube-vertex/README.md) | 6 | 2 / 2 | 0 / 4 | The parent missed all four diagonal hits. Both face-center controls hit. The fix matched the rational first-hit coordinates within 1e-10 per coordinate. |
| [330 Two-editor schedules](../../examples/330-two-editor-interleavings/README.md) | 6 | 3 / 1 | 4 / 4 | Saved writes lost one increment on four schedules. Both serial schedules ended at two. The claim covers the six legal deterministic schedules. |
| [331 Floor tilings](../../examples/331-floor-tiling-proof-reuse/README.md) | 19 | 7 / 4 | 11 / 11 | Recursive and iterative counts agreed through 4,181 at length 18. Dropping two-cell tiles changed 17 counts and six parities. The changed base case changed 18 counts and 13 parities. |

## What transferred across the four waves

1. **Artifact binding and independent claims.** Invoice loaded Rate from the first JAR on each ordered classpath. The public qualifier rejected the swapped preparation despite identical client bytes and the same dependency set. ThreeTen supplied an independent text input for parsing. At negative half a second, the parent formatted the wrong string and parsed the canonical string as positive half a second, yet round-tripped the original object.  [Invoice origins and rejection](../../examples/312-invoice-ordered-rate-jars/records/ordered-origins.json) · [ThreeTen direct observations](../../examples/315-tai-signed-fraction/records/finite-grid.json)

2. **Exceptional heaps and sequence witnesses.** For an Object array containing string A followed by integer 1, both sides threw ArrayStoreException. The destinations were ["A","x"] and ["x","x"]. On a 2×1 theatre, writing the first row changed the second only in the shared-row version. For the queue, three offers of A changed the reply and left the same final contents. The public candidate review replayed each input on its companion claim. The queue and Guava used the same sequence minimizer, which checked all 13 shorter queue words and all 40 shorter Guava words for each observer.  [Array poststate](../../examples/314-arraycopy-exceptional-prefix/receipts/exceptional-poststate/executions/20261120T033731Z-bfe21e76/replay.json) · [Exception companion](../../examples/314-arraycopy-exceptional-prefix/receipts/exception-class/executions/20261120T033736Z-3e128d94/replay.json) · [Seat cells](../../examples/317-theatre-seat-matrix/receipts/cells-shared/executions/20261120T033744Z-9d9129f8/replay.json) · [Seat shape](../../examples/317-theatre-seat-matrix/receipts/shape-shared/executions/20261120T033746Z-e3a11ed1/replay.json) · [Queue responses](../../examples/318-bounded-queue-histories/receipts/history-evict/executions/20261120T033749Z-2862b479/replay.json) · [Queue contents](../../examples/318-bounded-queue-histories/receipts/contents-evict/executions/20261120T033751Z-672da4d1/replay.json) · [Guava minimum traces](../../examples/319-guava-last-put-hash-collision/records/finite-grid.json)

3. **Dispatch and compiler boundaries.** The shared public recipe ran the erased bridge and the actual Supplier. Disassembly binds the bridge flags, descriptors and cast, the selected Fallback class, and javac’s two different concatenation lowerings. The native checker executes Optional’s bytecode from the selected JDK image and dispatches the actual application callback. The table and public entry recipe also checked the upstream duration formatter without a case-specific Python driver.  [Bridge methods](../../examples/323-erased-mapper-bridge/records/bytecode.json) · [Supplier and caller](../../examples/324-optional-fallback-effects/records/bytecode.json) · [Concatenation bytecode](../../examples/325-compiler-string-concatenation/records/bytecode.json) · [Duration replay](../../examples/326-commons-lang-separated-duration-tokens/records/finite-grid.json)

4. **Numerics, schedules and cost.** Raw hexadecimal bits preserved signed zero and exact Fraction values. Geometry admitted four diagonal rays and two face controls at a fixed tolerance. Its historical POM requested a mutable Commons Numbers 1.0-SNAPSHOT. Both revisions used the same pinned 1.0-beta1 dependencies. The two-editor witness is an explicit, deterministic interleaving. Its nonserial input falls outside the serial-only guard.  [Signed zero](../../examples/313-commons-lang-signed-zero-max/records/finite-grid.json) · [Fractions](../../examples/328-commons-math-fraction-percentage/records/finite-grid.json) · [Geometry scope](../../examples/329-commons-geometry-cube-vertex/example.json) · [Editor witness](../../examples/330-two-editor-interleavings/receipts/revision-saved/executions/20261120T033753Z-9db619f8/replay.json) · [Serial guard](../../examples/330-two-editor-interleavings/receipts/serial-saved/executions/20261120T033755Z-d423323c/replay.json)

### Regression transfer

Native multidimensional allocation now creates distinct rows and handles partial ranks. The matrix-only Commons Text run then reached Integer.valueOf. With bounded Integer boxing and unboxing, strict native checking proved the released Commons Text 1.13.1 LCS score for all 225 original string pairs at array bound 4 and unwind 18. The first completed proof took 0.726 s and 77.8 MiB. A second run preserving the full checker output took 0.997 s and 78.7 MiB. Release and rebuilt source had zero disagreements. The shared-row control disagreed 44 times. A fresh check of the two-root array example proved return preservation on the original 71 heaps. Three heaps differed at the right root and 21 at the two roots together. Both native violations reproduced on the JVM.  [Two-root regression job](../../verification/results/20261120-042933-recheck-both-array-roots-after-the-fast/result.json) · [Original array-root example](../../examples/197-shared-int-array-poststates/README.md) · [Matrix-only run](../../examples/308-commons-text-longest-common-subsequence/records/matrix-transfer.json) · [Boxing transfer](../../examples/308-commons-text-longest-common-subsequence/records/boxing-transfer.json) · [Repeat and oracle](../../examples/308-commons-text-longest-common-subsequence/records/release-score-transfer.json) · [Full release checker output](../../examples/308-commons-text-longest-common-subsequence/records/release-score-native.json)

The native checker and interpreter now preserve the copied, assignable prefix of System.arraycopy on exceptional exit, including overlap and bounds behavior. Native signed-long decimal append and checked UTF-16 replacement reached the actual TAI formatter on both revisions. Parsing and round-trip obligations currently stop at Matcher.group(int).  [Native array copy](../../lib/src/bmc/arraycopy.rs) · [Copy evidence](../../examples/314-arraycopy-exceptional-prefix/records/finite-grid.json) · [Format and parse claims](../../examples/315-tai-signed-fraction/target.json)

### Interrupted batch

The first ThreeTen batch completed round-trip, then stopped before parsing or formatting. Its collected journal and receipt remained intact. A fresh pipeline checkout linked a new attempt and ran format, round-trip and parse. All three finished. The repeated result had identical source keys, revision locks, ordered classpath, JDK, compiled probe and JVM stdout digest. The earlier journal still lists its original two missing stages.  [Linked batches, digests and jobs](../../examples/315-tai-signed-fraction/records/batch-recovery.json)

## Cost of the checked tiling helper

Each of the 24 measurements used the same checker, solver, JDK, input range 0–18, unwind 24, array bound 0 and 25-second checker budget for the given caller and revision. Every measurement started a fresh process. The repeat reused prepared artifacts. Only the exact-cache strategy retained a proof store. The operating-system page cache was uncontrolled. Wall time is end to end. Peak RSS is the maximum reported process RSS, in MiB.  [All measurements and raw-output hashes](../../examples/331-floor-tiling-proof-reuse/records/reuse/comparison.json)

| Recursive caller | Strategy | First wall / peak RSS | Repeat wall / peak RSS | First main checker phase |
|---|---|---:|---:|---|
| Exact | Inline helper | 24.257 s / 208.1 MiB | 18.440 s / 208.6 MiB | 23.437 s |
| Exact | Prove helper and use it | 2.001 s / 111.3 MiB | 1.905 s / 113.6 MiB | 0.026 s |
| Exact | Exact-result cache | 17.483 s / 210.1 MiB | 0.102 s / 49.2 MiB | 16.759 s |
| Parity | Inline helper | 17.749 s / 208.3 MiB | 17.104 s / 208.1 MiB | 17.062 s |
| Parity | Prove helper and use it | 1.914 s / 111.4 MiB | 1.922 s / 111.2 MiB | 0.039 s |
| Parity | Exact-result cache | 18.125 s / 210.2 MiB | 0.132 s / 49.1 MiB | 17.323 s |

The inline runs spent most of their wall time in the main checker. Proving the helper by induction reduced that phase to 0.026 s for exact and 0.039 s for parity. Checking the helper and compiling the Java expressions then accounted for most of the remaining time. Preparation of the exact recursive caller took 1.3645 s cold and 0.0013 s warm. Successful caller proofs needed no counterexample replay. An unchanged cached result returned in 0.102 s for exact and 0.132 s for parity.

Changing only the helper’s base case left both caller classes byte-identical. Inline and exact-cache runs refuted both callers in both phases. The first inline witness replays took 0.022 s for exact and 0.036 s for parity. The checked-lemma strategy refused the changed helper in each attempt. The two healthy recursive callers now use the bounded checked lemma through the public verifier, and the statement for each records its proved basis.  [Checked helper](../../examples/331-floor-tiling-proof-reuse/claims/helper.contract) · [Both caller strategies](../../examples/331-floor-tiling-proof-reuse/target.json) · [Public verification job](../../verification/results/20261120-041029-prove-both-recursive-tiling-callers-with/result.json)

## Strict native results on the numerical examples

Native coverage rose from **55 to 67 of 125**. Commons Lang contributed three proofs and one refutation. Guava contributed five proofs and three refutations. Every new native counterexample also reproduced on the original JVM grid.

- **Commons Lang.** Both revisions agree numerically on 84 arrays each. The parent returns negative zero for `[-0.0, +0.0]`, where the oracle requires positive zero. The fix preserves the required bits on every array. [Parent witness](../../examples/313-commons-lang-signed-zero-max/receipts/raw-bits-parent/20261120T054508Z-1c434c6c/result.json) · [Fixed raw-bit proof](../../examples/313-commons-lang-signed-zero-max/receipts/raw-bits-fix/20261120T054508Z-d257f99d/result.json)
- **Guava.** On the parent, the puts `R&D, QED, R&D, QED` leave three entries for two keys. The trace `X, R&D, QED, R&D` gives a wrong lookup with the expected size and entry set. The original 121 traces exercise Java’s floating-point table-size calculation, identity-key replacement and boxed Boolean dispatch. The strict native checker decided each observer independently. [Size counterexample](../../examples/319-guava-last-put-hash-collision/receipts/size-parent/20261120T054455Z-edc320a4/result.json) · [Lookup counterexample](../../examples/319-guava-last-put-hash-collision/receipts/lookup-parent/20261120T054516Z-13942d30/result.json) · [Guava batch](../../verification/results/20261120-052129-prove-guava-duplicate-entry-handling-wit/result.json)
- **Numerical scope.** Native comparison preserves both signed zeros and the JVM’s two unordered comparison biases. Widening an int to double covers every int. Other arithmetic evaluates up to 64 reachable operand tuples and checks that their complement is unsatisfiable. The controls cover rounding ties at 2²⁴ and 2⁵³, subnormal underflow, saturating casts and a 65th tuple that forces a refusal. The selected JDK supplies the bytecode and scaling helpers for `hypot`. [Checker](../../lib/src/bmc/floating.rs) · [JVM controls](../../lib/tests/fixtures/floating/FloatingChecks.java)
- **Regression checks.** The finished checker repeated all three native array-root outcomes on 71 heaps. It also proved the released Commons Text LCS score at array bound 4 and unwind 18 in 0.663 s with 78.1 MiB peak RSS. The two real artifacts agreed with the oracle on all 225 pairs. The shared-row control disagreed 44 times. [Array-root regression](../../verification/results/20261120-053727-confirm-both-array-roots-after-the-numer/result.json) · [LCS measurement](../../examples/308-commons-text-longest-common-subsequence/records/numeric-checker-transfer.json)

## Remaining native capabilities

Commons Geometry’s four original obligations reach `Math.sin` at the binary64 value nearest to −π/2 (`0xbff921fb54442d18`). The native checker currently supplies the specified sine result at signed zero. Its six-ray JVM grid still distinguishes the four missed diagonal hits from the two passing face controls. All six Fraction obligations stop earlier, in `Fraction.<clinit>`. [Geometry attempts](../../verification/results/20261120-053726-recheck-cube-intersections-with-linked-j/result.json) · [Fraction attempts](../../verification/results/20261120-053726-recheck-fraction-percentages-on-the-fina/result.json)

The 58 open native obligations span nine examples. Other first blockers include `Matcher.group` in ThreeTen’s parser, character boxing in Commons CSV, multiset views, JFreeChart’s listener initialization, ordered Throwable suppression, the Commons Lang duration lexer's list use, and Joda-Time initialization. The register gives each original obligation’s bounds and diagnostic. [Full claim register](../../verification/twenty-example-fast-follow-results.json)

## Claim register

Each receipt identifies the checked entry, original subject, ordered classpath, source bindings, full guard, observations and runtime. **Failures / admitted** counts the inputs violating that particular claim. A refutation on one field does not change the result for another field on the same input. Each native entry links to either its qualifying receipt or its first recorded blocker on the latest attempt. The JSON register also includes the statement, configured bounds, calibration size per revision, per-claim wall time and measured JVM peak RSS. [Complete register](../../verification/twenty-example-fast-follow-results.json)

<details>
<summary>312 · Ordered invoice JARs · 4 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `invoice-values` | two-first → three-first | refuted | [refuted](../../examples/312-invoice-ordered-rate-jars/records/finite-proofs/20261120T034454Z-a16ee9d7/invoice-values.json) | 4 / 5 | [refuted](../../examples/312-invoice-ordered-rate-jars/receipts/invoice-values/20261120T030129Z-04200fd6/result.json) |
| `zero-only` | two-first → three-first | established | [established](../../examples/312-invoice-ordered-rate-jars/records/finite-proofs/20261120T034454Z-a16ee9d7/zero-only.json) | 0 / 1 | [established](../../examples/312-invoice-ordered-rate-jars/receipts/zero-only/20261120T030136Z-05e8042b/result.json) |
| `rate-two-first` | two-first | established | [established](../../examples/312-invoice-ordered-rate-jars/records/finite-proofs/20261120T034454Z-a16ee9d7/rate-two-first.json) | 0 / 5 | [established](../../examples/312-invoice-ordered-rate-jars/receipts/rate-two-first/20261120T030136Z-ca2dcc39/result.json) |
| `rate-three-first` | three-first | established | [established](../../examples/312-invoice-ordered-rate-jars/records/finite-proofs/20261120T034454Z-a16ee9d7/rate-three-first.json) | 0 / 5 | [established](../../examples/312-invoice-ordered-rate-jars/receipts/rate-three-first/20261120T030137Z-1b2451f1/result.json) |

</details>

<details>
<summary>313 · Signed-zero maximum · 4 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `numeric-parent` | parent | established | [established](../../examples/313-commons-lang-signed-zero-max/records/finite-proofs/20261120T034454Z-9ad67524/numeric-parent.json) | 0 / 84 | [established](../../examples/313-commons-lang-signed-zero-max/receipts/numeric-parent/20261120T054455Z-c595ebc2/result.json) |
| `numeric-fix` | fix | established | [established](../../examples/313-commons-lang-signed-zero-max/records/finite-proofs/20261120T034454Z-9ad67524/numeric-fix.json) | 0 / 84 | [established](../../examples/313-commons-lang-signed-zero-max/receipts/numeric-fix/20261120T054502Z-67115a12/result.json) |
| `raw-bits-parent` | parent | refuted | [refuted](../../examples/313-commons-lang-signed-zero-max/records/finite-proofs/20261120T034454Z-9ad67524/raw-bits-parent.json) | 7 / 84 | [refuted](../../examples/313-commons-lang-signed-zero-max/receipts/raw-bits-parent/20261120T054508Z-1c434c6c/result.json) |
| `raw-bits-fix` | fix | established | [established](../../examples/313-commons-lang-signed-zero-max/records/finite-proofs/20261120T034454Z-9ad67524/raw-bits-fix.json) | 0 / 84 | [established](../../examples/313-commons-lang-signed-zero-max/receipts/raw-bits-fix/20261120T054508Z-d257f99d/result.json) |

</details>

<details>
<summary>314 · Exceptional array copy · 3 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `exception-class` | reference → precheck | established | [established](../../examples/314-arraycopy-exceptional-prefix/records/finite-proofs/20261120T034454Z-9a227db3/exception-class.json) | 0 / 40 | [established](../../examples/314-arraycopy-exceptional-prefix/receipts/exception-class/20261120T034903Z-f27a022e/result.json) |
| `exceptional-poststate` | reference → precheck | refuted | [refuted](../../examples/314-arraycopy-exceptional-prefix/records/finite-proofs/20261120T034454Z-9a227db3/exceptional-poststate.json) | 12 / 40 | [refuted](../../examples/314-arraycopy-exceptional-prefix/receipts/exceptional-poststate/20261120T034909Z-1c1bc422/result.json) |
| `assignable-poststate` | reference → precheck | established | [established](../../examples/314-arraycopy-exceptional-prefix/records/finite-proofs/20261120T034454Z-9a227db3/assignable-poststate.json) | 0 / 15 | [established](../../examples/314-arraycopy-exceptional-prefix/receipts/assignable-poststate/20261120T034910Z-ebda4f36/result.json) |

</details>

<details>
<summary>315 · Signed fractional seconds · 6 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `format-parent` | parent | refuted | [refuted](../../examples/315-tai-signed-fraction/records/finite-proofs/20261120T034454Z-8536ecfa/format-parent.json) | 6 / 20 | [refuted](../../examples/315-tai-signed-fraction/receipts/format-parent/20261120T040416Z-779870aa/result.json) |
| `format-fix` | fix | established | [established](../../examples/315-tai-signed-fraction/records/finite-proofs/20261120T040416Z-76458c1a/format-fix.json) | 0 / 20 | [established](../../examples/315-tai-signed-fraction/receipts/format-fix/20261120T040423Z-02e00333/result.json) |
| `parse-parent` | parent | refuted | [refuted](../../examples/315-tai-signed-fraction/records/finite-proofs/20261120T034454Z-8536ecfa/parse-parent.json) | 6 / 20 | [open · java.util.regex.Matcher.group](../../verification/results/20261120-023617-check-signed-time-in-each-direction-on-t/outputs/examples/315-tai-signed-fraction/receipts/parse-parent/executions/20261120T024337Z-8d5a841a/attempt.json) |
| `parse-fix` | fix | established | [established](../../examples/315-tai-signed-fraction/records/finite-proofs/20261120T040416Z-76458c1a/parse-fix.json) | 0 / 20 | [open · java.util.regex.Matcher.group](../../verification/results/20261120-023617-check-signed-time-in-each-direction-on-t/outputs/examples/315-tai-signed-fraction/receipts/parse-fix/executions/20261120T024340Z-05b8342a/attempt.json) |
| `round-trip-parent` | parent | established | [established](../../examples/315-tai-signed-fraction/records/finite-proofs/20261120T034454Z-8536ecfa/round-trip-parent.json) | 0 / 20 | [open · java.util.regex.Matcher.group](../../verification/results/20261120-041223-recheck-both-signed-tai-round-trips-afte/outputs/examples/315-tai-signed-fraction/receipts/round-trip-parent/executions/20261120T042026Z-02cd7e8f/attempt.json) |
| `round-trip-fix` | fix | established | [established](../../examples/315-tai-signed-fraction/records/finite-proofs/20261120T040416Z-76458c1a/round-trip-fix.json) | 0 / 20 | [open · java.util.regex.Matcher.group](../../verification/results/20261120-041223-recheck-both-signed-tai-round-trips-afte/outputs/examples/315-tai-signed-fraction/receipts/round-trip-fix/executions/20261120T042029Z-1b2b78b6/attempt.json) |

</details>

<details>
<summary>316 · CSV row limits · 6 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `equals-parent` | parent | refuted | [refuted](../../examples/316-commons-csv-row-limit-equality/records/finite-proofs/20261120T034454Z-8f630591/equals-parent.json) | 6 / 9 | [open · java.lang.Character.valueOf](../../verification/results/20261120-025230-check-csv-row-limit-equality-hash-implic/outputs/examples/316-commons-csv-row-limit-equality/receipts/equals-parent/executions/20261120T030129Z-120da780/attempt.json) |
| `equals-fix` | fix | established | [established](../../examples/316-commons-csv-row-limit-equality/records/finite-proofs/20261120T034454Z-8f630591/equals-fix.json) | 0 / 9 | [open · java.lang.Character.valueOf](../../verification/results/20261120-025230-check-csv-row-limit-equality-hash-implic/outputs/examples/316-commons-csv-row-limit-equality/receipts/equals-fix/executions/20261120T030133Z-7556da59/attempt.json) |
| `hash-contract-parent` | parent | established | [established](../../examples/316-commons-csv-row-limit-equality/records/finite-proofs/20261120T034454Z-8f630591/hash-contract-parent.json) | 0 / 9 | [open · java.lang.Character.valueOf](../../verification/results/20261120-025230-check-csv-row-limit-equality-hash-implic/outputs/examples/316-commons-csv-row-limit-equality/receipts/hash-contract-parent/executions/20261120T030136Z-ec83b449/attempt.json) |
| `hash-contract-fix` | fix | established | [established](../../examples/316-commons-csv-row-limit-equality/records/finite-proofs/20261120T034454Z-8f630591/hash-contract-fix.json) | 0 / 9 | [open · java.lang.Character.valueOf](../../verification/results/20261120-025230-check-csv-row-limit-equality-hash-implic/outputs/examples/316-commons-csv-row-limit-equality/receipts/hash-contract-fix/executions/20261120T030140Z-50dcde95/attempt.json) |
| `rows-parent` | parent | established | [established](../../examples/316-commons-csv-row-limit-equality/records/finite-proofs/20261120T034454Z-8f630591/rows-parent.json) | 0 / 9 | [open · java.lang.Character.valueOf](../../verification/results/20261120-025230-check-csv-row-limit-equality-hash-implic/outputs/examples/316-commons-csv-row-limit-equality/receipts/rows-parent/executions/20261120T030143Z-adcfd7cc/attempt.json) |
| `rows-fix` | fix | established | [established](../../examples/316-commons-csv-row-limit-equality/records/finite-proofs/20261120T034454Z-8f630591/rows-fix.json) | 0 / 9 | [open · java.lang.Character.valueOf](../../verification/results/20261120-025230-check-csv-row-limit-equality-hash-implic/outputs/examples/316-commons-csv-row-limit-equality/receipts/rows-fix/executions/20261120T030147Z-198dd26a/attempt.json) |

</details>

<details>
<summary>317 · Theatre seats · 9 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `shape-matrix` | matrix | established | [established](../../examples/317-theatre-seat-matrix/records/finite-proofs/20261120T034454Z-944587fa/shape-matrix.json) | 0 / 18 | [established](../../examples/317-theatre-seat-matrix/receipts/shape-matrix/20261120T030129Z-22d73d5c/result.json) |
| `shape-separate` | separate | established | [established](../../examples/317-theatre-seat-matrix/records/finite-proofs/20261120T034454Z-944587fa/shape-separate.json) | 0 / 18 | [established](../../examples/317-theatre-seat-matrix/receipts/shape-separate/20261120T030131Z-5fcd36d9/result.json) |
| `shape-shared` | shared | established | [established](../../examples/317-theatre-seat-matrix/records/finite-proofs/20261120T034454Z-944587fa/shape-shared.json) | 0 / 18 | [established](../../examples/317-theatre-seat-matrix/receipts/shape-shared/20261120T030133Z-6517c6a9/result.json) |
| `cells-matrix` | matrix | established | [established](../../examples/317-theatre-seat-matrix/records/finite-proofs/20261120T034454Z-944587fa/cells-matrix.json) | 0 / 18 | [established](../../examples/317-theatre-seat-matrix/receipts/cells-matrix/20261120T030135Z-3c67f20c/result.json) |
| `cells-separate` | separate | established | [established](../../examples/317-theatre-seat-matrix/records/finite-proofs/20261120T034454Z-944587fa/cells-separate.json) | 0 / 18 | [established](../../examples/317-theatre-seat-matrix/receipts/cells-separate/20261120T030135Z-775b0bc5/result.json) |
| `cells-shared` | shared | refuted | [refuted](../../examples/317-theatre-seat-matrix/records/finite-proofs/20261120T034454Z-944587fa/cells-shared.json) | 15 / 18 | [refuted](../../examples/317-theatre-seat-matrix/receipts/cells-shared/20261120T030135Z-b5e0f983/result.json) |
| `identity-matrix` | matrix | established | [established](../../examples/317-theatre-seat-matrix/records/finite-proofs/20261120T034454Z-944587fa/identity-matrix.json) | 0 / 18 | [established](../../examples/317-theatre-seat-matrix/receipts/identity-matrix/20261120T030136Z-5bba76b1/result.json) |
| `identity-separate` | separate | established | [established](../../examples/317-theatre-seat-matrix/records/finite-proofs/20261120T034454Z-944587fa/identity-separate.json) | 0 / 18 | [established](../../examples/317-theatre-seat-matrix/receipts/identity-separate/20261120T030136Z-9bf84491/result.json) |
| `identity-shared` | shared | refuted | [refuted](../../examples/317-theatre-seat-matrix/records/finite-proofs/20261120T034454Z-944587fa/identity-shared.json) | 15 / 18 | [refuted](../../examples/317-theatre-seat-matrix/receipts/identity-shared/20261120T030136Z-d6a577cb/result.json) |

</details>

<details>
<summary>318 · Bounded queue · 4 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `history-reject` | reject | established | [established](../../examples/318-bounded-queue-histories/records/finite-proofs/20261120T034454Z-a5539027/history-reject.json) | 0 / 121 | [established](../../examples/318-bounded-queue-histories/receipts/history-reject/20261120T030128Z-f3987814/result.json) |
| `history-evict` | evict | refuted | [refuted](../../examples/318-bounded-queue-histories/records/finite-proofs/20261120T034454Z-a5539027/history-evict.json) | 40 / 121 | [refuted](../../examples/318-bounded-queue-histories/receipts/history-evict/20261120T030131Z-467bd917/result.json) |
| `contents-reject` | reject | established | [established](../../examples/318-bounded-queue-histories/records/finite-proofs/20261120T034454Z-a5539027/contents-reject.json) | 0 / 121 | [established](../../examples/318-bounded-queue-histories/receipts/contents-reject/20261120T030133Z-ae022f0d/result.json) |
| `contents-evict` | evict | refuted | [refuted](../../examples/318-bounded-queue-histories/records/finite-proofs/20261120T034454Z-a5539027/contents-evict.json) | 28 / 121 | [refuted](../../examples/318-bounded-queue-histories/receipts/contents-evict/20261120T030134Z-12f69504/result.json) |

</details>

<details>
<summary>319 · Guava map collisions · 8 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `size-parent` | parent | refuted | [refuted](../../examples/319-guava-last-put-hash-collision/records/finite-proofs/20261120T034454Z-5b5f79c1/size-parent.json) | 2 / 121 | [refuted](../../examples/319-guava-last-put-hash-collision/receipts/size-parent/20261120T054455Z-edc320a4/result.json) |
| `size-fix` | fix | established | [established](../../examples/319-guava-last-put-hash-collision/records/finite-proofs/20261120T034454Z-5b5f79c1/size-fix.json) | 0 / 121 | [established](../../examples/319-guava-last-put-hash-collision/receipts/size-fix/20261120T054507Z-18f9e47e/result.json) |
| `lookup-parent` | parent | refuted | [refuted](../../examples/319-guava-last-put-hash-collision/records/finite-proofs/20261120T034454Z-5b5f79c1/lookup-parent.json) | 10 / 121 | [refuted](../../examples/319-guava-last-put-hash-collision/receipts/lookup-parent/20261120T054516Z-13942d30/result.json) |
| `lookup-fix` | fix | established | [established](../../examples/319-guava-last-put-hash-collision/records/finite-proofs/20261120T034454Z-5b5f79c1/lookup-fix.json) | 0 / 121 | [established](../../examples/319-guava-last-put-hash-collision/receipts/lookup-fix/20261120T054517Z-1292c5f4/result.json) |
| `entries-parent` | parent | refuted | [refuted](../../examples/319-guava-last-put-hash-collision/records/finite-proofs/20261120T034454Z-5b5f79c1/entries-parent.json) | 2 / 121 | [refuted](../../examples/319-guava-last-put-hash-collision/receipts/entries-parent/20261120T054517Z-82196ccb/result.json) |
| `entries-fix` | fix | established | [established](../../examples/319-guava-last-put-hash-collision/records/finite-proofs/20261120T034454Z-5b5f79c1/entries-fix.json) | 0 / 121 | [established](../../examples/319-guava-last-put-hash-collision/receipts/entries-fix/20261120T054518Z-8f460ca2/result.json) |
| `unique-parent` | parent | established | [established](../../examples/319-guava-last-put-hash-collision/records/finite-proofs/20261120T034454Z-5b5f79c1/unique-parent.json) | 0 / 16 | [established](../../examples/319-guava-last-put-hash-collision/receipts/unique-parent/20261120T054519Z-12e06050/result.json) |
| `unique-fix` | fix | established | [established](../../examples/319-guava-last-put-hash-collision/records/finite-proofs/20261120T034454Z-5b5f79c1/unique-fix.json) | 0 / 16 | [established](../../examples/319-guava-last-put-hash-collision/receipts/unique-fix/20261120T054520Z-5f6bfc43/result.json) |

</details>

<details>
<summary>320 · Live multiset views · 6 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `total-parent` | parent | refuted | [refuted](../../examples/320-collections-live-multiset-views/records/finite-proofs/20261120T034454Z-9ad4b907/total-parent.json) | 18 / 18 | [open · java.util.Map.entrySet](../../verification/results/20261120-032646-native-320-commons-collections-views-upd/outputs/examples/320-collections-live-multiset-views/receipts/total-parent/executions/20261120T034844Z-73eea1bf/attempt.json) |
| `total-fix` | fix | established | [established](../../examples/320-collections-live-multiset-views/records/finite-proofs/20261120T034454Z-9ad4b907/total-fix.json) | 0 / 18 | [open · java.util.Map.entrySet](../../verification/results/20261120-032646-native-320-commons-collections-views-upd/outputs/examples/320-collections-live-multiset-views/receipts/total-fix/executions/20261120T034852Z-1258abf4/attempt.json) |
| `membership-parent` | parent | established | [established](../../examples/320-collections-live-multiset-views/records/finite-proofs/20261120T034454Z-9ad4b907/membership-parent.json) | 0 / 18 | [open · java.util.Map.entrySet](../../verification/results/20261120-032646-native-320-commons-collections-views-upd/outputs/examples/320-collections-live-multiset-views/receipts/membership-parent/executions/20261120T034859Z-7d9d294b/attempt.json) |
| `membership-fix` | fix | established | [established](../../examples/320-collections-live-multiset-views/records/finite-proofs/20261120T034454Z-9ad4b907/membership-fix.json) | 0 / 18 | [open · java.util.Map.entrySet](../../verification/results/20261120-032646-native-320-commons-collections-views-upd/outputs/examples/320-collections-live-multiset-views/receipts/membership-fix/executions/20261120T034859Z-d695cb6d/attempt.json) |
| `other-count-parent` | parent | established | [established](../../examples/320-collections-live-multiset-views/records/finite-proofs/20261120T034454Z-9ad4b907/other-count-parent.json) | 0 / 18 | [open · java.util.Map.entrySet](../../verification/results/20261120-032646-native-320-commons-collections-views-upd/outputs/examples/320-collections-live-multiset-views/receipts/other-count-parent/executions/20261120T034900Z-4ef3f8d7/attempt.json) |
| `other-count-fix` | fix | established | [established](../../examples/320-collections-live-multiset-views/records/finite-proofs/20261120T034454Z-9ad4b907/other-count-fix.json) | 0 / 18 | [open · java.util.Map.entrySet](../../verification/results/20261120-032646-native-320-commons-collections-views-upd/outputs/examples/320-collections-live-multiset-views/receipts/other-count-fix/executions/20261120T034900Z-bdca62ed/attempt.json) |

</details>

<details>
<summary>321 · JFreeChart ranges · 8 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `lower-parent` | parent | refuted | [refuted](../../examples/321-jfreechart-empty-series-range/records/finite-proofs/20261120T034454Z-7ad0de0d/lower-parent.json) | 12 / 30 | [open · javax.swing.event.EventListenerList constructor](../../verification/results/20261120-032646-native-321-jfreechart-range-endpoints-wi/outputs/examples/321-jfreechart-empty-series-range/receipts/lower-parent/executions/20261120T034844Z-999136c4/attempt.json) |
| `lower-fix` | fix | established | [established](../../examples/321-jfreechart-empty-series-range/records/finite-proofs/20261120T034454Z-7ad0de0d/lower-fix.json) | 0 / 30 | [open · javax.swing.event.EventListenerList constructor](../../verification/results/20261120-032646-native-321-jfreechart-range-endpoints-wi/outputs/examples/321-jfreechart-empty-series-range/receipts/lower-fix/executions/20261120T034854Z-21c63c4a/attempt.json) |
| `upper-parent` | parent | refuted | [refuted](../../examples/321-jfreechart-empty-series-range/records/finite-proofs/20261120T034454Z-7ad0de0d/upper-parent.json) | 12 / 30 | [open · javax.swing.event.EventListenerList constructor](../../verification/results/20261120-032646-native-321-jfreechart-range-endpoints-wi/outputs/examples/321-jfreechart-empty-series-range/receipts/upper-parent/executions/20261120T034903Z-35d9ca0a/attempt.json) |
| `upper-fix` | fix | established | [established](../../examples/321-jfreechart-empty-series-range/records/finite-proofs/20261120T034454Z-7ad0de0d/upper-fix.json) | 0 / 30 | [open · javax.swing.event.EventListenerList constructor](../../verification/results/20261120-032646-native-321-jfreechart-range-endpoints-wi/outputs/examples/321-jfreechart-empty-series-range/receipts/upper-fix/executions/20261120T034903Z-c14633a6/attempt.json) |
| `populated-lower-parent` | parent | established | [established](../../examples/321-jfreechart-empty-series-range/records/finite-proofs/20261120T034454Z-7ad0de0d/populated-lower-parent.json) | 0 / 18 | [open · javax.swing.event.EventListenerList constructor](../../verification/results/20261120-032646-native-321-jfreechart-range-endpoints-wi/outputs/examples/321-jfreechart-empty-series-range/receipts/populated-lower-parent/executions/20261120T034904Z-3ecadab7/attempt.json) |
| `populated-lower-fix` | fix | established | [established](../../examples/321-jfreechart-empty-series-range/records/finite-proofs/20261120T034454Z-7ad0de0d/populated-lower-fix.json) | 0 / 18 | [open · javax.swing.event.EventListenerList constructor](../../verification/results/20261120-032646-native-321-jfreechart-range-endpoints-wi/outputs/examples/321-jfreechart-empty-series-range/receipts/populated-lower-fix/executions/20261120T034907Z-53203fc8/attempt.json) |
| `populated-upper-parent` | parent | established | [established](../../examples/321-jfreechart-empty-series-range/records/finite-proofs/20261120T034454Z-7ad0de0d/populated-upper-parent.json) | 0 / 18 | [open · javax.swing.event.EventListenerList constructor](../../verification/results/20261120-032646-native-321-jfreechart-range-endpoints-wi/outputs/examples/321-jfreechart-empty-series-range/receipts/populated-upper-parent/executions/20261120T034905Z-e39b1db1/attempt.json) |
| `populated-upper-fix` | fix | established | [established](../../examples/321-jfreechart-empty-series-range/records/finite-proofs/20261120T034454Z-7ad0de0d/populated-upper-fix.json) | 0 / 18 | [open · javax.swing.event.EventListenerList constructor](../../verification/results/20261120-032646-native-321-jfreechart-range-endpoints-wi/outputs/examples/321-jfreechart-empty-series-range/receipts/populated-upper-fix/executions/20261120T034908Z-82d13b84/attempt.json) |

</details>

<details>
<summary>322 · Suppressed exceptions · 9 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `primary-original` | original | established | [established](../../examples/322-ordered-suppressed-exceptions/records/finite-proofs/20261120T040416Z-7d1df947/primary-original.json) | 0 / 8 | [open · java.lang.Throwable.addSuppressed](../../verification/results/20261120-035022-native-retry-resource-closure-after-bind/outputs/examples/322-ordered-suppressed-exceptions/receipts/primary-original/executions/20261120T040416Z-99c89ed1/attempt.json) |
| `primary-nested` | nested | established | [established](../../examples/322-ordered-suppressed-exceptions/records/finite-proofs/20261120T040416Z-7d1df947/primary-nested.json) | 0 / 8 | [open · java.lang.Throwable.addSuppressed](../../verification/results/20261120-035022-native-retry-resource-closure-after-bind/outputs/examples/322-ordered-suppressed-exceptions/receipts/primary-nested/executions/20261120T040420Z-6683b8b5/attempt.json) |
| `primary-reversed` | reversed | refuted | [refuted](../../examples/322-ordered-suppressed-exceptions/records/finite-proofs/20261120T040416Z-7d1df947/primary-reversed.json) | 1 / 8 | [open · java.lang.Throwable.addSuppressed](../../verification/results/20261120-035022-native-retry-resource-closure-after-bind/outputs/examples/322-ordered-suppressed-exceptions/receipts/primary-reversed/executions/20261120T040423Z-9bb72fbe/attempt.json) |
| `suppressed-original` | original | established | [established](../../examples/322-ordered-suppressed-exceptions/records/finite-proofs/20261120T040416Z-7d1df947/suppressed-original.json) | 0 / 8 | [open · Throwable.getSuppressed](../../verification/results/20261120-035022-native-retry-resource-closure-after-bind/outputs/examples/322-ordered-suppressed-exceptions/receipts/suppressed-original/executions/20261120T040426Z-6b0d8114/attempt.json) |
| `suppressed-nested` | nested | established | [established](../../examples/322-ordered-suppressed-exceptions/records/finite-proofs/20261120T040416Z-7d1df947/suppressed-nested.json) | 0 / 8 | [open · Throwable.getSuppressed](../../verification/results/20261120-035022-native-retry-resource-closure-after-bind/outputs/examples/322-ordered-suppressed-exceptions/receipts/suppressed-nested/executions/20261120T040426Z-c3a537e2/attempt.json) |
| `suppressed-reversed` | reversed | refuted | [refuted](../../examples/322-ordered-suppressed-exceptions/records/finite-proofs/20261120T040416Z-7d1df947/suppressed-reversed.json) | 2 / 8 | [open · Throwable.getSuppressed](../../verification/results/20261120-035022-native-retry-resource-closure-after-bind/outputs/examples/322-ordered-suppressed-exceptions/receipts/suppressed-reversed/executions/20261120T040427Z-3085ccf5/attempt.json) |
| `close-original` | original | established | [established](../../examples/322-ordered-suppressed-exceptions/records/finite-proofs/20261120T040416Z-7d1df947/close-original.json) | 0 / 8 | [open · java.lang.Throwable.addSuppressed](../../verification/results/20261120-035022-native-retry-resource-closure-after-bind/outputs/examples/322-ordered-suppressed-exceptions/receipts/close-original/executions/20261120T040427Z-83f66c6b/attempt.json) |
| `close-nested` | nested | established | [established](../../examples/322-ordered-suppressed-exceptions/records/finite-proofs/20261120T040416Z-7d1df947/close-nested.json) | 0 / 8 | [open · java.lang.Throwable.addSuppressed](../../verification/results/20261120-035022-native-retry-resource-closure-after-bind/outputs/examples/322-ordered-suppressed-exceptions/receipts/close-nested/executions/20261120T040427Z-dd71c831/attempt.json) |
| `close-reversed` | reversed | refuted | [refuted](../../examples/322-ordered-suppressed-exceptions/records/finite-proofs/20261120T040416Z-7d1df947/close-reversed.json) | 8 / 8 | [refuted](../../verification/results/20261120-035022-native-retry-resource-closure-after-bind/outputs/examples/322-ordered-suppressed-exceptions/receipts/close-reversed/20261120T040428Z-4c8e35fc/result.json) |

</details>

<details>
<summary>323 · Erased generic bridge · 8 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `value-original` | original | established | [established](../../examples/323-erased-mapper-bridge/records/finite-proofs/20261120T034454Z-a67ccec8/value-original.json) | 0 / 5 | [established](../../examples/323-erased-mapper-bridge/receipts/value-original/20261120T034844Z-5e8a9a64/result.json) |
| `value-changed` | changed | refuted | [refuted](../../examples/323-erased-mapper-bridge/records/finite-proofs/20261120T034454Z-a67ccec8/value-changed.json) | 1 / 5 | [refuted](../../examples/323-erased-mapper-bridge/receipts/value-changed/20261120T034846Z-e8b1f408/result.json) |
| `exception-original` | original | established | [established](../../examples/323-erased-mapper-bridge/records/finite-proofs/20261120T034454Z-a67ccec8/exception-original.json) | 0 / 5 | [established](../../examples/323-erased-mapper-bridge/receipts/exception-original/20261120T034850Z-2287fae1/result.json) |
| `exception-changed` | changed | established | [established](../../examples/323-erased-mapper-bridge/records/finite-proofs/20261120T034454Z-a67ccec8/exception-changed.json) | 0 / 5 | [established](../../examples/323-erased-mapper-bridge/receipts/exception-changed/20261120T034850Z-768c8d4a/result.json) |
| `entries-original` | original | established | [established](../../examples/323-erased-mapper-bridge/records/finite-proofs/20261120T034454Z-a67ccec8/entries-original.json) | 0 / 5 | [established](../../examples/323-erased-mapper-bridge/receipts/entries-original/20261120T034850Z-cc6f8ae2/result.json) |
| `entries-changed` | changed | established | [established](../../examples/323-erased-mapper-bridge/records/finite-proofs/20261120T034454Z-a67ccec8/entries-changed.json) | 0 / 5 | [established](../../examples/323-erased-mapper-bridge/receipts/entries-changed/20261120T034851Z-346e7629/result.json) |
| `typed-agreement-original` | original | established | [established](../../examples/323-erased-mapper-bridge/records/finite-proofs/20261120T034454Z-a67ccec8/typed-agreement-original.json) | 0 / 4 | [established](../../examples/323-erased-mapper-bridge/receipts/typed-agreement-original/20261120T034851Z-8ca55c75/result.json) |
| `typed-agreement-changed` | changed | established | [established](../../examples/323-erased-mapper-bridge/records/finite-proofs/20261120T034454Z-a67ccec8/typed-agreement-changed.json) | 0 / 4 | [established](../../examples/323-erased-mapper-bridge/receipts/typed-agreement-changed/20261120T034854Z-1f4e6a8a/result.json) |

</details>

<details>
<summary>324 · Optional callback · 6 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `value-lazy` | lazy | established | [established](../../examples/324-optional-fallback-effects/records/finite-proofs/20261120T034503Z-11a54bf6/value-lazy.json) | 0 / 4 | [established](../../examples/324-optional-fallback-effects/receipts/value-lazy/20261120T042026Z-0dd02a5f/result.json) |
| `value-branch` | branch | established | [established](../../examples/324-optional-fallback-effects/records/finite-proofs/20261120T034503Z-11a54bf6/value-branch.json) | 0 / 4 | [established](../../examples/324-optional-fallback-effects/receipts/value-branch/20261120T042028Z-2596ad8f/result.json) |
| `value-eager` | eager | established | [established](../../examples/324-optional-fallback-effects/records/finite-proofs/20261120T034503Z-11a54bf6/value-eager.json) | 0 / 4 | [established](../../examples/324-optional-fallback-effects/receipts/value-eager/20261120T042029Z-ee7994dc/result.json) |
| `callbacks-lazy` | lazy | established | [established](../../examples/324-optional-fallback-effects/records/finite-proofs/20261120T034503Z-11a54bf6/callbacks-lazy.json) | 0 / 4 | [established](../../examples/324-optional-fallback-effects/receipts/callbacks-lazy/20261120T042031Z-bf90af17/result.json) |
| `callbacks-branch` | branch | established | [established](../../examples/324-optional-fallback-effects/records/finite-proofs/20261120T034503Z-11a54bf6/callbacks-branch.json) | 0 / 4 | [established](../../examples/324-optional-fallback-effects/receipts/callbacks-branch/20261120T042032Z-08f1a411/result.json) |
| `callbacks-eager` | eager | refuted | [refuted](../../examples/324-optional-fallback-effects/records/finite-proofs/20261120T034503Z-11a54bf6/callbacks-eager.json) | 3 / 4 | [refuted](../../examples/324-optional-fallback-effects/receipts/callbacks-eager/20261120T042032Z-4451747b/result.json) |

</details>

<details>
<summary>325 · String concatenation bytecode · 3 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `label-legacy` | legacy | established | [established](../../examples/325-compiler-string-concatenation/records/finite-proofs/20261120T034507Z-3e2f5c9c/label-legacy.json) | 0 / 9 | [established](../../examples/325-compiler-string-concatenation/receipts/label-legacy/20261120T034844Z-6267baa9/result.json) |
| `label-modern` | modern | established | [established](../../examples/325-compiler-string-concatenation/records/finite-proofs/20261120T034507Z-3e2f5c9c/label-modern.json) | 0 / 9 | [established](../../examples/325-compiler-string-concatenation/receipts/label-modern/20261120T034846Z-f06ec2cc/result.json) |
| `label-changed` | changed | refuted | [refuted](../../examples/325-compiler-string-concatenation/records/finite-proofs/20261120T034507Z-3e2f5c9c/label-changed.json) | 3 / 9 | [refuted](../../examples/325-compiler-string-concatenation/receipts/label-changed/20261120T034849Z-7460f0f9/result.json) |

</details>

<details>
<summary>326 · Duration format tokens · 6 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `separated-parent` | parent | refuted | [refuted](../../examples/326-commons-lang-separated-duration-tokens/records/finite-proofs/20261120T034509Z-84c589a8/separated-parent.json) | 52 / 52 | [open · java.util.ArrayList constructor](../../verification/results/20261120-032647-native-326-commons-lang-duration-fields/outputs/examples/326-commons-lang-separated-duration-tokens/receipts/separated-parent/executions/20261120T034846Z-a8c9a05b/attempt.json) |
| `separated-fix` | fix | established | [established](../../examples/326-commons-lang-separated-duration-tokens/records/finite-proofs/20261120T034509Z-84c589a8/separated-fix.json) | 0 / 52 | [open · java.util.ArrayList constructor](../../verification/results/20261120-032647-native-326-commons-lang-duration-fields/outputs/examples/326-commons-lang-separated-duration-tokens/receipts/separated-fix/executions/20261120T034855Z-20907feb/attempt.json) |
| `quoting-parent` | parent | established | [established](../../examples/326-commons-lang-separated-duration-tokens/records/finite-proofs/20261120T034509Z-84c589a8/quoting-parent.json) | 0 / 52 | [open · java.util.ArrayList constructor](../../verification/results/20261120-032647-native-326-commons-lang-duration-fields/outputs/examples/326-commons-lang-separated-duration-tokens/receipts/quoting-parent/executions/20261120T034903Z-69346dc9/attempt.json) |
| `quoting-fix` | fix | established | [established](../../examples/326-commons-lang-separated-duration-tokens/records/finite-proofs/20261120T034509Z-84c589a8/quoting-fix.json) | 0 / 52 | [open · java.util.ArrayList constructor](../../verification/results/20261120-032647-native-326-commons-lang-duration-fields/outputs/examples/326-commons-lang-separated-duration-tokens/receipts/quoting-fix/executions/20261120T034904Z-3f6af132/attempt.json) |
| `adjacent-parent` | parent | established | [established](../../examples/326-commons-lang-separated-duration-tokens/records/finite-proofs/20261120T034509Z-84c589a8/adjacent-parent.json) | 0 / 26 | [open · java.util.ArrayList constructor](../../verification/results/20261120-032647-native-326-commons-lang-duration-fields/outputs/examples/326-commons-lang-separated-duration-tokens/receipts/adjacent-parent/executions/20261120T034905Z-0f97d4d4/attempt.json) |
| `adjacent-fix` | fix | established | [established](../../examples/326-commons-lang-separated-duration-tokens/records/finite-proofs/20261120T034509Z-84c589a8/adjacent-fix.json) | 0 / 26 | [open · java.util.ArrayList constructor](../../verification/results/20261120-032647-native-326-commons-lang-duration-fields/outputs/examples/326-commons-lang-separated-duration-tokens/receipts/adjacent-fix/executions/20261120T034905Z-c8e01175/attempt.json) |

</details>

<details>
<summary>327 · Joda-Time partial dates · 10 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `normal-parent` | parent | refuted | [refuted](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T034511Z-025a4e09/normal-parent.json) | 9 / 25 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-032647-native-327-joda-time-distances-between-l/outputs/examples/327-joda-monthday-distance/receipts/normal-parent/executions/20261120T034856Z-013d5433/attempt.json) |
| `normal-fix` | fix | established | [established](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T034511Z-025a4e09/normal-fix.json) | 0 / 25 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-032647-native-327-joda-time-distances-between-l/outputs/examples/327-joda-monthday-distance/receipts/normal-fix/executions/20261120T034902Z-4959777e/attempt.json) |
| `days-parent` | parent | refuted | [refuted](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T034511Z-025a4e09/days-parent.json) | 17 / 25 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-032647-native-327-joda-time-distances-between-l/outputs/examples/327-joda-monthday-distance/receipts/days-parent/executions/20261120T034908Z-28f37a21/attempt.json) |
| `days-fix` | fix | established | [established](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T034511Z-025a4e09/days-fix.json) | 0 / 25 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-032647-native-327-joda-time-distances-between-l/outputs/examples/327-joda-monthday-distance/receipts/days-fix/executions/20261120T034908Z-b9a7eb02/attempt.json) |
| `reversal-parent` | parent | established | [established](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T034511Z-025a4e09/reversal-parent.json) | 0 / 25 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-032647-native-327-joda-time-distances-between-l/outputs/examples/327-joda-monthday-distance/receipts/reversal-parent/executions/20261120T034909Z-4fca3728/attempt.json) |
| `reversal-fix` | fix | established | [established](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T034511Z-025a4e09/reversal-fix.json) | 0 / 25 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-032647-native-327-joda-time-distances-between-l/outputs/examples/327-joda-monthday-distance/receipts/reversal-fix/executions/20261120T034909Z-d7144c3a/attempt.json) |
| `march-parent` | parent | established | [established](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T034511Z-025a4e09/march-parent.json) | 0 / 4 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-032647-native-327-joda-time-distances-between-l/outputs/examples/327-joda-monthday-distance/receipts/march-parent/executions/20261120T034910Z-68acb49b/attempt.json) |
| `march-fix` | fix | established | [established](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T034511Z-025a4e09/march-fix.json) | 0 / 4 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-032647-native-327-joda-time-distances-between-l/outputs/examples/327-joda-monthday-distance/receipts/march-fix/executions/20261120T034911Z-3ed12eb6/attempt.json) |
| `reversal-on-returns-parent` | parent | established | [established](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T040416Z-74246d38/reversal-on-returns-parent.json) | 0 / 16 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-035732-check-natively-reversal-on-normal-monthd/outputs/examples/327-joda-monthday-distance/receipts/reversal-on-returns-parent/executions/20261120T040416Z-67e17c33/attempt.json) |
| `reversal-on-returns-fix` | fix | established | [established](../../examples/327-joda-monthday-distance/records/finite-proofs/20261120T040416Z-74246d38/reversal-on-returns-fix.json) | 0 / 25 | [open · org.joda.time.MonthDay static initializer](../../verification/results/20261120-035732-check-natively-reversal-on-normal-monthd/outputs/examples/327-joda-monthday-distance/receipts/reversal-on-returns-fix/executions/20261120T040425Z-23d1d66c/attempt.json) |

</details>

<details>
<summary>328 · Fraction percentage · 6 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `bits-parent` | parent | refuted | [refuted](../../examples/328-commons-math-fraction-percentage/records/finite-proofs/20261120T040416Z-8051dd38/bits-parent.json) | 4 / 13 | [open · org.apache.commons.math3.fraction.Fraction static initializer](../../verification/results/20261120-053726-recheck-fraction-percentages-on-the-fina/outputs/examples/328-commons-math-fraction-percentage/receipts/bits-parent/executions/20261120T054455Z-d9f1bf90/attempt.json) |
| `bits-fix` | fix | established | [established](../../examples/328-commons-math-fraction-percentage/records/finite-proofs/20261120T040416Z-8051dd38/bits-fix.json) | 0 / 13 | [open · org.apache.commons.math3.fraction.Fraction static initializer](../../verification/results/20261120-053726-recheck-fraction-percentages-on-the-fina/outputs/examples/328-commons-math-fraction-percentage/receipts/bits-fix/executions/20261120T054502Z-6f733ee9/attempt.json) |
| `normal-parent` | parent | established | [established](../../examples/328-commons-math-fraction-percentage/records/finite-proofs/20261120T040416Z-8051dd38/normal-parent.json) | 0 / 13 | [open · org.apache.commons.math3.fraction.Fraction static initializer](../../verification/results/20261120-053726-recheck-fraction-percentages-on-the-fina/outputs/examples/328-commons-math-fraction-percentage/receipts/normal-parent/executions/20261120T054508Z-57f44e51/attempt.json) |
| `normal-fix` | fix | established | [established](../../examples/328-commons-math-fraction-percentage/records/finite-proofs/20261120T040416Z-8051dd38/normal-fix.json) | 0 / 13 | [open · org.apache.commons.math3.fraction.Fraction static initializer](../../verification/results/20261120-053726-recheck-fraction-percentages-on-the-fina/outputs/examples/328-commons-math-fraction-percentage/receipts/normal-fix/executions/20261120T054508Z-a00f1d1c/attempt.json) |
| `small-parent` | parent | established | [established](../../examples/328-commons-math-fraction-percentage/records/finite-proofs/20261120T040416Z-8051dd38/small-parent.json) | 0 / 3 | [open · org.apache.commons.math3.fraction.Fraction static initializer](../../verification/results/20261120-053726-recheck-fraction-percentages-on-the-fina/outputs/examples/328-commons-math-fraction-percentage/receipts/small-parent/executions/20261120T054508Z-e8ae1584/attempt.json) |
| `small-fix` | fix | established | [established](../../examples/328-commons-math-fraction-percentage/records/finite-proofs/20261120T040416Z-8051dd38/small-fix.json) | 0 / 3 | [open · org.apache.commons.math3.fraction.Fraction static initializer](../../verification/results/20261120-053726-recheck-fraction-percentages-on-the-fina/outputs/examples/328-commons-math-fraction-percentage/receipts/small-fix/executions/20261120T054509Z-3d06e031/attempt.json) |

</details>

<details>
<summary>329 · Cube intersections · 4 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `presence-parent` | parent | refuted | [refuted](../../examples/329-commons-geometry-cube-vertex/records/finite-proofs/20261120T034517Z-3bcc6d74/presence-parent.json) | 4 / 6 | [open · java.lang.Math.sin(D)D beyond signed zero, reachable argument 0xbff921fb54442d18](../../verification/results/20261120-053726-recheck-cube-intersections-with-linked-j/outputs/examples/329-commons-geometry-cube-vertex/receipts/presence-parent/executions/20261120T054455Z-c4cdcf4f/attempt.json) |
| `presence-fix` | fix | established | [established](../../examples/329-commons-geometry-cube-vertex/records/finite-proofs/20261120T034517Z-3bcc6d74/presence-fix.json) | 0 / 6 | [open · java.lang.Math.sin(D)D beyond signed zero, reachable argument 0xbff921fb54442d18](../../verification/results/20261120-053726-recheck-cube-intersections-with-linked-j/outputs/examples/329-commons-geometry-cube-vertex/receipts/presence-fix/executions/20261120T054459Z-da74e44f/attempt.json) |
| `point-parent` | parent | refuted | [refuted](../../examples/329-commons-geometry-cube-vertex/records/finite-proofs/20261120T034517Z-3bcc6d74/point-parent.json) | 4 / 6 | [open · java.lang.Math.sin(D)D beyond signed zero, reachable argument 0xbff921fb54442d18](../../verification/results/20261120-053726-recheck-cube-intersections-with-linked-j/outputs/examples/329-commons-geometry-cube-vertex/receipts/point-parent/executions/20261120T054503Z-96c1d96f/attempt.json) |
| `point-fix` | fix | established | [established](../../examples/329-commons-geometry-cube-vertex/records/finite-proofs/20261120T034517Z-3bcc6d74/point-fix.json) | 0 / 6 | [open · java.lang.Math.sin(D)D beyond signed zero, reachable argument 0xbff921fb54442d18](../../verification/results/20261120-053726-recheck-cube-intersections-with-linked-j/outputs/examples/329-commons-geometry-cube-vertex/receipts/point-fix/executions/20261120T054503Z-f358dd3d/attempt.json) |

</details>

<details>
<summary>330 · Two-editor schedules · 4 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `revision-current` | current | established | [established](../../examples/330-two-editor-interleavings/records/finite-proofs/20261120T034518Z-803c244c/revision-current.json) | 0 / 6 | [established](../../examples/330-two-editor-interleavings/receipts/revision-current/20261120T034856Z-f133faa5/result.json) |
| `revision-saved` | saved | refuted | [refuted](../../examples/330-two-editor-interleavings/records/finite-proofs/20261120T034518Z-803c244c/revision-saved.json) | 4 / 6 | [refuted](../../examples/330-two-editor-interleavings/receipts/revision-saved/20261120T034859Z-a91cd714/result.json) |
| `serial-current` | current | established | [established](../../examples/330-two-editor-interleavings/records/finite-proofs/20261120T034518Z-803c244c/serial-current.json) | 0 / 2 | [established](../../examples/330-two-editor-interleavings/receipts/serial-current/20261120T034902Z-c00a3e19/result.json) |
| `serial-saved` | saved | established | [established](../../examples/330-two-editor-interleavings/records/finite-proofs/20261120T034518Z-803c244c/serial-saved.json) | 0 / 2 | [established](../../examples/330-two-editor-interleavings/receipts/serial-saved/20261120T034903Z-ccfc17f2/result.json) |

</details>

<details>
<summary>331 · Floor tilings · 11 claims</summary>

| Task | Subject revision(s) | Expected | Exhaustive JVM | Failures / admitted | Strict native |
|---|---|---|---|---:|---|
| `exact-recursive` | recursive | established | [established](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/exact-recursive.json) | 0 / 19 | [established](../../examples/331-floor-tiling-proof-reuse/receipts/exact-recursive/20261120T042205Z-ea69413b/result.json) |
| `exact-iterative` | iterative | established | [established](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/exact-iterative.json) | 0 / 19 | [established](../../examples/331-floor-tiling-proof-reuse/receipts/exact-iterative/20261120T034922Z-23222961/result.json) |
| `exact-one-tile` | one-tile | refuted | [refuted](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/exact-one-tile.json) | 17 / 19 | [refuted](../../examples/331-floor-tiling-proof-reuse/receipts/exact-one-tile/20261120T034924Z-331e5dfc/result.json) |
| `exact-base-change` | base-change | refuted | [refuted](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/exact-base-change.json) | 18 / 19 | [refuted](../../examples/331-floor-tiling-proof-reuse/receipts/exact-base-change/20261120T034926Z-9875af35/result.json) |
| `parity-recursive` | recursive | established | [established](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/parity-recursive.json) | 0 / 19 | [established](../../examples/331-floor-tiling-proof-reuse/receipts/parity-recursive/20261120T042029Z-46548055/result.json) |
| `parity-iterative` | iterative | established | [established](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/parity-iterative.json) | 0 / 19 | [established](../../examples/331-floor-tiling-proof-reuse/receipts/parity-iterative/20261120T034959Z-4ae158ef/result.json) |
| `parity-one-tile` | one-tile | refuted | [refuted](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/parity-one-tile.json) | 6 / 19 | [refuted](../../examples/331-floor-tiling-proof-reuse/receipts/parity-one-tile/20261120T035001Z-567a9b7e/result.json) |
| `parity-base-change` | base-change | refuted | [refuted](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/parity-base-change.json) | 13 / 19 | [refuted](../../examples/331-floor-tiling-proof-reuse/receipts/parity-base-change/20261120T035003Z-b7d30100/result.json) |
| `helper-preservation` | recursive → iterative | established | [established](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/helper-preservation.json) | 0 / 19 | [established](../../examples/331-floor-tiling-proof-reuse/receipts/helper-preservation/20261120T035016Z-d28c57a8/result.json) |
| `caller-exact-preservation` | recursive → iterative | established | [established](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/caller-exact-preservation.json) | 0 / 19 | [established](../../examples/331-floor-tiling-proof-reuse/receipts/caller-exact-preservation/20261120T035036Z-62973020/result.json) |
| `caller-parity-preservation` | recursive → iterative | established | [established](../../examples/331-floor-tiling-proof-reuse/records/finite-proofs/20261120T034523Z-3b228fe6/caller-parity-preservation.json) | 0 / 19 | [established](../../examples/331-floor-tiling-proof-reuse/receipts/caller-parity-preservation/20261120T035056Z-6004d1c1/result.json) |

</details>

## Verification history

The pipeline collected 79 jobs. 49 met their declared expectations and 30 retained a failure. All are listed in the JSON register. The two initial finite jobs that failed were retried after repairing the bound argument in resource closure and declaring the actual package-private companions in the Fraction source slice. Both retries passed with complete coverage. Native jobs whose checker refused an original obligation remain recorded as failed. Their individual current dispositions appear above.

The receipts contain 261 current-claim native executions and candidate reviews and 99 eligible native receipts. There were 27 finite batches and 146 finite claim attempts including retries, the interrupted completion and earlier ineligible attempts. These counts exclude the 24 separate benchmark measurements. Both queued JBMC/auto corpus comparison jobs passed.  [JBMC and auto corpus comparison](../../verification/results/20261120-033506-check-the-fast-follow-boxing-change-with/result.json) · [Auto-confirm JVM corpus comparison](../../verification/results/20261120-033516-confirm-jvm-corpus-results-after-fast-fo/result.json)

To inspect one case, run `python3 examples/tools/targets/workflow_handoff.py handoff 315 --markdown`. The public handoff retains ordinary and exhaustive outcomes, their disputes, archived job diagnostics, and linked attempts. Use `python3 examples/tools/build.py --plan 315` for the frozen tasks and `python3 examples/tools/targets/finite_report.py 318 --sequence-field commands` for the independently minimized observation histories.
