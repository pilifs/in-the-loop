# Java callbacks, numeric conversions and caller-owned arrays

**Ordinary native decisions rose from 7/49 to 49/49.** The final checker proved 29 statements and refuted 20 on witnesses reproduced by the original JVM. The three primary examples opened at 6/37. The two reserve examples opened later at 1/12. Strict integrated JBMC decided 26/49 at matching scope. The original JVM also ran 135 frozen single-input controls.

The public callers use Temurin 21.0.13, pinned release JARs in their original order and explicit strict engines. The original historical benchmark uses its JDK 25 harness. The standalone numeric comparison used the Ubuntu 22.04 JBMC 6.11.0 package. Callbacks, rows and queue histories used the 24.04 package. Both packages ran the bounded strings. The Comparator and Arrays overlays came from the measured JDK image. A qualified refutation has a witness replayed on the original JVM. Times in parentheses cover the checker calls. The job receipts also record preparation and JVM replay. [Per-statement evidence, bounds and first unresolved operations](../../verification/jbmc-fast-follow/scorecard.json)

| Cohort | Statements | Native decisions, opening → final | Integrated JBMC decisions, opening → final |
|---|---|---|---|
| Method-reference conversions | 7 | 0 → 7 | 4 → 7 |
| Direct Guava twins | 2 | 2 → 2 | 2 → 2 |
| Guava ComparisonChain | 4 | 1 → 4 | 0 → 0 |
| Primary numeric conversions | 5 | 0 → 5 | 5 → 5 |
| All Jackson disagreements | 1 | 0 → 1 | 1 → 1 |
| Direct conversion opcode | 1 | 0 → 1 | 1 → 1 |
| Long-mantissa adapter | 1 | 0 → 1 | 0 → 0 |
| Direct reversal and live iterator | 4 | 0 → 4 | 0 → 2 |
| Direct row identity and reachability | 4 | 0 → 4 | 0 → 4 |
| Explicit primitive builders | 3 | 3 → 3 | 1 → 1 |
| Commons Math equal-width and singleton controls | 2 | 0 → 2 | 0 → 0 |
| Commons Math exception observations | 3 | 0 → 3 | 0 → 2 |
| Two-string public comparisons | 6 | 0 → 6 | 0 → 0 |
| Same-reference string diagonal | 1 | 0 → 1 | 0 → 0 |
| Four-operation queue histories | 2 | 1 → 2 | 1 → 1 |
| Reference fills | 3 | 0 → 3 | 0 → 0 |

## Public behavior

At opening, native stopped at method-reference conversion on all seven callback statements. Its long conversions reached a 64-tuple enumeration limit, and the two direct-double statements stopped at parameter intake. Both project engines refused the direct nested-array inputs before the library method. The primitive builders had their own narrower construction histories.

The original integrated Guava run exited 101 during witness replay. The corrected adapters widen the signed result for both Guava interfaces and the Commons Lang short interface. Unboxing a null argument on an active comparison throws. A settled ComparisonChain skips that argument. [Independent five-claim Guava qualification](../../verification/jbmc-fast-follow/guava/callbacks/paired/measurement.json)

Across the 2⁵⁴ admitted long inputs, the two Jackson paths differ at two neighbors of a midpoint in each of 2²³ bins. Even retained significands disagree at offsets +1 and +2, odd ones at −1 and −2, giving 16,777,216 inputs. At 0x0040000040000001L direct conversion gives float bits 0x5a800001 and conversion through double gives 0x5a800000. The direct double interval contains 2⁵² + 1 values. Its halfway endpoint converts to positive zero. [Qualification after the five primary decisions](../../verification/jbmc-fast-follow/classification/numeric/paired/measurement.json)

The direct row domain includes a null outer array, independently sized nullable rows, arbitrary signed cells and shared row references. Both dimensions are bounded by two in the comparison. The original JVM census found 12 shared nonempty graphs among 209 two-slot cases. The stock tree generator accepted the false distinct-row assertion. Explicit alias choice produced a replayed counterexample. [Independent standalone JVM replays](../../verification/jbmc-fast-follow/standalone-replays.json)

The first direct native run proved reversal and live iteration. Its row counterexample search stopped at a class assertion setting because the search could vary the input heap along with that setting. Fixing the concrete input graph allows the checker to vary the JVM setting independently. The companion regression keeps a genuinely setting-dependent claim open. [Initial direct-row comparison](../../verification/jbmc-fast-follow/final/rows/paired/measurement.json)

A separate layout moved the assertion methods out of RaggedProof. Its six public and helper method instruction and handler lists matched, and the MadeRows class bytes matched. On the three explicit primitive builders that layout yielded 3/3 native and 3/3 integrated decisions. Both layouts agreed on all 209 physical graphs with both assertion settings. [Separated assertion drivers](../../verification/jbmc-fast-follow/row-layout/measurement.json) · [Five ordinary counterexamples on both JVM settings](../../verification/jbmc-fast-follow/row-settings.json)

The released Commons Math method was also checked directly at `org.apache.commons.math3.util.MathArrays#checkRectangular([[J)V`. Its equal-width and singleton-null inputs return normally. Its unequal-width inputs throw DimensionMismatchException. Independent JVM enumeration found eight normal returns, seven null-pointer exceptions and six mismatches across 21 non-null shapes. Swapping the two exception fields fails on every unequal non-null pair. [Original descriptor and field results](../../verification/jbmc-fast-follow/successor/matrix/measurement.json)

| Direct Commons Math scope | Native | Integrated JBMC at 4096 MiB | Integrated JBMC at 8192 MiB |
|---|---|---|---|
| equal-width | verified | out of memory | unverifiable |
| singleton-null | verified | process killed | unverifiable |
| unequal-width | verified | process killed | unverifiable |

JBMC on equal-width, singleton-null, unequal-width. Strict checking rejected the solver proof at `stubbed-handler at PropertyHarness.check`, `throwing-initializer at org.apache.commons.math3.exception.MathIllegalNumberException.<clinit>`.

Independent JVM runs reconstructed all 26 failing standalone target traces. 22 refuted the original observation. The JVM observation held for the long-mantissa candidate, the packaged replacement candidate and both covariant-fill candidates. [Witness values, identities and physical outcomes](../../verification/jbmc-fast-follow/standalone-replays.json)

The separate string grid checked 5,329 pairs. Sign normalization failed on 4,756, including U+D800 versus U+D802, where the difference is −2. Guava retained the first reference on all 73 equal-valued, distinct pairs. The same-reference case has its own row.

All 256 four-operation queue histories were checked against a two-slot oracle. On 128 histories, isFull differed from occupancy. The ArrayFill transfer observes both overwritten references and a later write through the shared replacement. A covariant empty array returns normally, while the nonempty incompatible store throws before replacing its first cell. The packaged JBMC model accepted the stale-slot claim. Adding the original JDK Arrays class corrected the replacement and stale-slot results. Its covariant candidate still held on the JVM.

The standalone tables show the selected assertion and its post-return sentinel separately. A failed sentinel establishes that the caller returned. Other failed obligations are counted beside the target.

## Method references

The opening source was `cc7636786154` with checker `e41539fd3d8b935a`. The successor was `701ca64e1980` with checker `b1e0edad5632990e`. The JVM and verifier agreed on 8 product and release class bindings. [Opening paired responses](../../verification/jbmc-fast-follow/opening/callbacks/paired/measurement.json) · [Final paired responses](../../verification/jbmc-fast-follow/successor/callbacks/paired/measurement.json) · [packaged JBMC profile](../../verification/jbmc-fast-follow/opening/callbacks/packaged/measurement.json) · [comparator JBMC profile](../../verification/jbmc-fast-follow/opening/callbacks/comparator/measurement.json)

| Original entry | Expected | Native | Integrated JBMC | Standalone target / post-return sentinel | Original JVM controls |
|---|---|---|---|---|---|
| `Lift#primitiveGood(II)Z` | established | open (0.02 s) → proved (0.04 s) | proved (1.00 s) → proved (1.78 s) | packaged SUCCESS / FAILURE | 4 held, 0 failed |
| `Lift#primitiveWrong(II)Z` | refuted | open (0.02 s) → refuted (0.07 s) | process error (0.49 s) → refuted (1.05 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `Lift#boxedGood(II)Z` | established | open (0.02 s) → proved (0.04 s) | proved (1.41 s) → proved (2.85 s) | packaged SUCCESS / FAILURE | 4 held, 0 failed |
| `Lift#boxedWrong(II)Z` | refuted | open (0.02 s) → refuted (0.07 s) | process error (0.69 s) → refuted (1.20 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `Lift#returnGood(SS)Z` | established | open (0.02 s) → proved (0.04 s) | proved (0.79 s) → proved (1.28 s) | packaged SUCCESS / FAILURE | 3 held, 0 failed |
| `Lift#returnWrong(SS)Z` | refuted | open (0.02 s) → refuted (0.06 s) | process error (0.54 s) → refuted (0.89 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `Lift#boxedNull()Z` | established | open (0.02 s) → proved (0.04 s) | proved (0.70 s) → proved (1.23 s) | packaged SUCCESS / FAILURE | 1 held, 0 failed |
| `Lift#staticGood(II)Z` | established | proved (0.02 s) → proved (0.04 s) | proved (1.10 s) → proved (1.83 s) | packaged SUCCESS / FAILURE | 4 held, 0 failed |
| `Lift#staticWrong(II)Z` | refuted | refuted (0.03 s) → refuted (0.06 s) | refuted (0.56 s) → refuted (0.95 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `Chain#good(II)Z` | established | open (0.02 s) → proved (0.04 s) | unreproduced witness (0.57 s) → unreproduced witness (1.10 s) | packaged SUCCESS / SUCCESS + 1 other failure(s)<br>comparator SUCCESS / FAILURE | 4 held, 0 failed |
| `Chain#wrong(II)Z` | refuted | open (0.02 s) → refuted (0.09 s) | unreproduced witness (0.56 s) → unreproduced witness (1.11 s) | packaged SUCCESS / SUCCESS + 1 other failure(s)<br>comparator FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `Chain#skipsNull()Z` | established | proved (0.02 s) → proved (0.04 s) | open (0.51 s) → open (0.94 s) | packaged SUCCESS / FAILURE<br>comparator SUCCESS / FAILURE | 1 held, 0 failed |
| `Chain#rejectsNull()Z` | established | open (0.02 s) → proved (0.04 s) | open (0.54 s) → open (1.02 s) | packaged SUCCESS / FAILURE<br>comparator SUCCESS / FAILURE | 1 held, 0 failed |

## Numeric conversions

The opening source was `cc7636786154` with checker `e41539fd3d8b935a`. The successor was `701ca64e1980` with checker `b1e0edad5632990e`. The JVM and verifier agreed on 5 product and release class bindings. [Opening paired responses](../../verification/jbmc-fast-follow/opening/numeric/paired/measurement.json) · [Final paired responses](../../verification/jbmc-fast-follow/successor/numeric/paired/measurement.json) · [packaged JBMC profile](../../verification/jbmc-fast-follow/opening/numeric/packaged/measurement.json)

| Original entry | Expected | Native | Integrated JBMC | Standalone target / post-return sentinel | Original JVM controls |
|---|---|---|---|---|---|
| `NodeChecks#direct(J)Z` | established | open (0.03 s) → proved (0.06 s) | proved (5.26 s) → proved (8.71 s) | packaged SUCCESS / FAILURE | 3 held, 0 failed |
| `NodeChecks#same(J)Z` | refuted | open (0.02 s) → refuted (0.05 s) | refuted (5.33 s) → refuted (9.29 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `NodeChecks#publicSubnormal(D)Z` | established | entry refused (0.02 s) → proved (0.04 s) | proved (5.11 s) → proved (8.62 s) | packaged SUCCESS / FAILURE | 3 held, 0 failed |
| `NodeChecks#wrongSubnormal(D)Z` | refuted | entry refused (0.03 s) → refuted (0.06 s) | refuted (2.61 s) → refuted (4.30 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `NodeChecks#commons(J)Z` | established | open (0.02 s) → proved (0.05 s) | proved (4.91 s) → proved (8.15 s) | packaged SUCCESS / FAILURE | 3 held, 0 failed |
| `ConversionEquivalence#classified(J)Z` | established | open (0.02 s) → proved (0.06 s) | proved (4.62 s) → proved (7.10 s) | packaged SUCCESS / FAILURE | 3 held, 0 failed |
| `NodeChecks#intrinsicSubnormal(D)Z` | established | entry refused (0.02 s) → proved (0.03 s) | proved (4.96 s) → proved (9.02 s) | packaged SUCCESS / FAILURE | 3 held, 0 failed |
| `NodeChecks#mantissaSubnormal(J)Z` | established | open (0.02 s) → proved (0.03 s) | unreproduced witness (4.89 s) → unreproduced witness (8.39 s) | packaged FAILURE / FAILURE, JVM held | 3 held, 0 failed |

## Primitive row graphs

The opening source was `cc7636786154` with checker `e41539fd3d8b935a`. The successor was `701ca64e1980` with checker `b1e0edad5632990e`. The JVM and verifier agreed on 8 product and release class bindings. [Opening paired responses](../../verification/jbmc-fast-follow/opening/rows/paired/measurement.json) · [Final paired responses](../../verification/jbmc-fast-follow/successor/rows/paired/measurement.json) · [packaged JBMC profile](../../verification/jbmc-fast-follow/opening/rows/packaged/measurement.json) · [alias JBMC profile](../../verification/jbmc-fast-follow/opening/rows/alias/measurement.json)

| Original entry | Expected | Native | Integrated JBMC | Standalone target / post-return sentinel | Original JVM controls |
|---|---|---|---|---|---|
| `RaggedProof#reversed([[I)Z` | established | entry refused (0.01 s) → proved (0.04 s) | entry refused (0.01 s) → open (5.02 s) | packaged SUCCESS / FAILURE<br>alias SUCCESS / FAILURE | 4 held, 0 failed |
| `RaggedProof#wrong([[I)Z` | refuted | entry refused (0.01 s) → refuted (0.29 s) | entry refused (0.00 s) → refuted (5.25 s) | packaged FAILURE / FAILURE, JVM refuted | 2 held, 1 failed, checker witness replayed |
| `RaggedProof#iter([[I)Z` | established | entry refused (0.01 s) → proved (0.04 s) | entry refused (0.01 s) → open (3.49 s) | packaged SUCCESS / FAILURE | 4 held, 0 failed |
| `RaggedProof#snapshot([[I)Z` | refuted | entry refused (0.00 s) → refuted (0.26 s) | entry refused (0.00 s) → refuted (4.70 s) | packaged FAILURE / FAILURE, JVM refuted | 2 held, 1 failed, checker witness replayed |
| `RaggedProof#distinct([[I)Z` | refuted | entry refused (0.00 s) → refuted (0.26 s) | entry refused (0.01 s) → refuted (4.08 s) | packaged SUCCESS / FAILURE<br>alias FAILURE / FAILURE, JVM refuted | 4 held, 1 failed, checker witness replayed |
| `RowIdentities#nonNullOuter([[I)Z` | refuted | entry refused (0.00 s) → refuted (0.27 s) | entry refused (0.00 s) → refuted (1.37 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `RowIdentities#noEmptyOuter([[I)Z` | refuted | entry refused (0.01 s) → refuted (0.20 s) | entry refused (0.00 s) → refuted (1.18 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `RowIdentities#noDistinctEqualRows([[I)Z` | refuted | entry refused (0.00 s) → refuted (0.22 s) | entry refused (0.00 s) → refuted (1.62 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `MadeRows#reverse(IIZ)Z` | established | proved (0.02 s) → proved (0.05 s) | open (1.49 s) → open (2.59 s) | packaged SUCCESS / FAILURE | 2 held, 0 failed |
| `MadeRows#iterator(IIZ)Z` | established | proved (0.02 s) → proved (0.03 s) | open (1.27 s) → open (2.34 s) | packaged SUCCESS / FAILURE | 2 held, 0 failed |
| `MadeRows#alwaysDistinct(IIZ)Z` | refuted | refuted (0.04 s) → refuted (0.07 s) | refuted (0.89 s) → refuted (1.58 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `MatrixRows#rectangular([[J)Z` | established | entry refused (0.01 s) → proved (0.04 s) | entry refused (0.00 s) → open (37.51 s) | packaged SUCCESS / FAILURE | 3 held, 0 failed |
| `MatrixRows#singleShape([[J)Z` | established | entry refused (0.00 s) → proved (0.05 s) | entry refused (0.00 s) → open (19.59 s) | packaged SUCCESS / FAILURE | 3 held, 0 failed |
| `MatrixRows#shape([[J)Z` | established | entry refused (0.00 s) → proved (0.08 s) | entry refused (0.00 s) → open (35.25 s) | packaged SUCCESS / FAILURE + 1 other failure(s) | 3 held, 0 failed |
| `MatrixRows#same([[J)Z` | refuted | entry refused (0.00 s) → refuted (0.31 s) | entry refused (0.00 s) → refuted (36.00 s) | packaged FAILURE / FAILURE + 1 other failure(s), JVM refuted | 1 held, 1 failed, checker witness replayed |
| `MatrixRows#noNull([[J)Z` | refuted | entry refused (0.00 s) → refuted (0.21 s) | entry refused (0.01 s) → refuted (16.75 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |

## Bounded UTF-16 ordering

The opening source was `1b5d1ce10919` with checker `21f641888609ff2e`. The successor was `701ca64e1980` with checker `b1e0edad5632990e`. The JVM and verifier agreed on 4 product and release class bindings. [Opening paired responses](../../verification/jbmc-fast-follow/opening/strings/paired/measurement.json) · [Final paired responses](../../verification/jbmc-fast-follow/successor/strings/paired/measurement.json) · [packaged JBMC profile](../../verification/jbmc-fast-follow/opening/strings/packaged/measurement.json) · [packaged-22 JBMC profile](../../verification/jbmc-fast-follow/opening/strings/packaged-22/measurement.json)

| Original entry | Expected | Native | Integrated JBMC | Standalone target / post-return sentinel | Original JVM controls |
|---|---|---|---|---|---|
| `ExactOrder#commons(Ljava/lang/String;Ljava/lang/String;)Z` | established | open (0.02 s) → proved (0.04 s) | entry refused (0.01 s) → entry refused (0.01 s) | packaged SUCCESS / FAILURE<br>packaged-22 SUCCESS / FAILURE | 4 held, 0 failed |
| `ExactOrder#onlySign(Ljava/lang/String;Ljava/lang/String;)Z` | refuted | open (0.02 s) → refuted (0.06 s) | entry refused (0.01 s) → entry refused (0.01 s) | packaged FAILURE / FAILURE, JVM refuted<br>packaged-22 FAILURE / FAILURE, JVM refuted | 3 held, 1 failed, checker witness replayed |
| `ExactOrder#guava(Ljava/lang/String;Ljava/lang/String;)Z` | established | open (0.02 s) → proved (0.04 s) | entry refused (0.01 s) → entry refused (0.01 s) | packaged SUCCESS / FAILURE<br>packaged-22 SUCCESS / FAILURE | 4 held, 0 failed |
| `ExactOrder#firstOnTie(Ljava/lang/String;Ljava/lang/String;)Z` | established | open (0.02 s) → proved (0.04 s) | entry refused (0.01 s) → entry refused (0.01 s) | packaged SUCCESS / FAILURE<br>packaged-22 SUCCESS / FAILURE | 4 held, 0 failed |
| `ExactOrder#secondOnTie(Ljava/lang/String;Ljava/lang/String;)Z` | refuted | open (0.02 s) → refuted (0.07 s) | entry refused (0.01 s) → entry refused (0.01 s) | packaged FAILURE / FAILURE, JVM refuted<br>packaged-22 FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `ExactOrder#direct(Ljava/lang/String;Ljava/lang/String;)Z` | established | open (0.03 s) → proved (0.04 s) | entry refused (0.01 s) → entry refused (0.01 s) | packaged SUCCESS / FAILURE<br>packaged-22 SUCCESS / FAILURE | 4 held, 0 failed |
| `ExactOrder#sameReference(Ljava/lang/String;)Z` | established | open (0.02 s) → proved (0.03 s) | entry refused (0.01 s) → entry refused (0.01 s) | packaged SUCCESS / FAILURE<br>packaged-22 SUCCESS / FAILURE | 2 held, 0 failed |

## Queue and fill

The opening source was `1b5d1ce10919` with checker `21f641888609ff2e`. The successor was `701ca64e1980` with checker `b1e0edad5632990e`. The JVM and verifier agreed on 4 product and release class bindings. [Opening paired responses](../../verification/jbmc-fast-follow/opening/queue/paired/measurement.json) · [Final paired responses](../../verification/jbmc-fast-follow/successor/queue/paired/measurement.json) · [packaged JBMC profile](../../verification/jbmc-fast-follow/opening/queue/packaged/measurement.json) · [arrays JBMC profile](../../verification/jbmc-fast-follow/opening/queue/arrays/measurement.json)

| Original entry | Expected | Native | Integrated JBMC | Standalone target / post-return sentinel | Original JVM controls |
|---|---|---|---|---|---|
| `QueueFill#queue(I)Z` | established | open (0.03 s) → proved (0.09 s) | open (6.18 s) → open (10.18 s) | packaged SUCCESS / FAILURE | 4 held, 0 failed |
| `QueueFill#fullMeansOccupied(I)Z` | refuted | refuted (0.03 s) → refuted (0.07 s) | refuted (3.42 s) → refuted (5.61 s) | packaged FAILURE / FAILURE, JVM refuted | 1 held, 1 failed, checker witness replayed |
| `QueueFill#fill(I)Z` | established | open (0.03 s) → proved (0.03 s) | unreproduced witness (0.24 s) → unreproduced witness (0.47 s) | packaged FAILURE / FAILURE, JVM held<br>arrays SUCCESS / FAILURE | 3 held, 0 failed |
| `QueueFill#staleSurvives(I)Z` | refuted | open (0.03 s) → refuted (0.06 s) | open (0.34 s) → open (0.44 s) | packaged SUCCESS / FAILURE<br>arrays FAILURE / FAILURE, JVM refuted | 0 held, 2 failed, checker witness replayed |
| `QueueFill#covariant(Z)Z` | established | open (0.02 s) → proved (0.03 s) | unreproduced witness (0.65 s) → unreproduced witness (1.09 s) | packaged FAILURE / FAILURE, JVM held<br>arrays FAILURE / FAILURE, JVM held | 2 held, 0 failed |

## Remaining operations

Each row below names an entry in the frozen comparison. To reproduce a single integrated claim, use `python3 -B lib/benchmark/jbmc-fast-follow/measure.py repro rows jbmc --methods reversed --output "$TMPDIR"` as the verification job step. Substitute the family and method from the per-statement scorecard. The raw responses retain the full diagnostics and the concrete arguments for any proposed violation.

- JBMC on `Chain#good`. The interpreter returned true for `good(x=0, y=0)`. The comparator approximates `invokedynamic:java.lang.invoke.LambdaMetafactory.metafactory:compare()Ljava/util/Comparator;`.
- JBMC on `Chain#wrong`. The interpreter returned true for `wrong(x=0, y=0)`. The comparator approximates `invokedynamic:java.lang.invoke.LambdaMetafactory.metafactory:compare()Ljava/util/Comparator;`.
- JBMC on `Chain#skipsNull`, `Chain#rejectsNull`. Strict checking refused the approximation at `invokedynamic:java.lang.invoke.LambdaMetafactory.metafactory:compare()Ljava/util/Comparator;`.
- JBMC on `NodeChecks#mantissaSubnormal`. The interpreter returned true for `mantissaSubnormal(k=0)`. The comparator approximates `jdk-static-method:java.lang.Double.longBitsToDouble(J)D@jdk-21.0.13`.
- JBMC on `RaggedProof#reversed`, `RaggedProof#iter`. Strict checking rejected the solver proof at `stubbed-handler at PropertyHarness.check`, `throwing-initializer at RaggedProof.<clinit>`.
- JBMC on `MadeRows#reverse`, `MadeRows#iterator`. Strict checking refused the approximation at `jdk-primitive-method:java.lang.Class.desiredAssertionStatus()Z@jdk-21.0.13`.
- JBMC on `MatrixRows#rectangular`, `MatrixRows#singleShape`, `MatrixRows#shape`. Strict checking rejected the solver proof at `stubbed-handler at PropertyHarness.check`, `throwing-initializer at MatrixRows.<clinit>`, `throwing-initializer at org.apache.commons.math3.exception.MathIllegalNumberException.<clinit>`.
- JBMC on `ExactOrder#commons`, `ExactOrder#onlySign`, `ExactOrder#guava`, `ExactOrder#firstOnTie`, `ExactOrder#secondOnTie`, `ExactOrder#direct`, `ExactOrder#sameReference`. The integrated String input model cannot enforce the stated UTF-16 domain.
- JBMC on `QueueFill#queue`. Strict checking rejected the solver proof at `unmasked-shift at QueueFill.history:11`.
- JBMC on `QueueFill#fill`. The interpreter returned true for `fill(value=0)`. The comparator approximates `jdk-static-method:java.util.Arrays.fill([Ljava/lang/Object;Ljava/lang/Object;)V@jdk-21.0.13`.
- JBMC on `QueueFill#staleSurvives`. Strict checking refused the approximation at `jdk-static-method:java.util.Arrays.fill([Ljava/lang/Object;Ljava/lang/Object;)V@jdk-21.0.13`.
- JBMC on `QueueFill#covariant`. The interpreter returned true for `covariant(empty=false)`. The comparator approximates `jdk-static-method:java.util.Arrays.fill([Ljava/lang/Object;Ljava/lang/Object;)V@jdk-21.0.13`.

## Handoff to receiver construction

The ordinary verifier accepts direct float and double words and one bounded int[][] or long[][] root alongside primitive arguments. Row witnesses preserve null, shared rows, distinct equal values and every cell bit. The native row factory supports bounds through 32. Integrated JBMC uses a scalar descriptor that must fit in 255 JVM argument slots. Constructor-made receivers sharing this heap and cross-engine confirmation of these row inputs remain open. A reachable floating conversion with an unspecified NaN payload also has its own refusal. [Receiver construction and property discovery](receiver-construction-and-property-discovery-brief.md)

The numbered examples retain 49 ordinary task receipts. [Native receipts by example](../../verification/jbmc-fast-follow/successor/example-tasks/measurement.json)

## Predecessor controls and verification

The successor retained 33 proofs and 24 replayed refutations among the 60 preceding statements. The three ordinary monitor statements still first reach Thread construction. Native retained 22 historical proofs and 16 refutations among the 38 historical checks, including 13/13 formerly JBMC-only cases and 24/24 formerly native-only controls. The 187-row distribution belongs to the original historical benchmark. [Historical and public caller repeats](../../verification/jbmc-fast-follow/successor/regressions) · [Decimal cases and exact JVM values](../../verification/jbmc-fast-follow/successor/regressions/decimal/paired/measurement.json)

On the preceding 60, integrated JBMC returned 7 correct proofs and 17 replayed refutations. The JVM contradicted 2 other proofs. The four decimal decisions comprised 3 native proofs and 1 replayed refutation.

The verification ledger contains 26 campaign jobs, 26 passed. The first direct Commons Math run recorded two kernel process kills at its memory limit. The separate retry retained the 120-second claim deadlines and the original release JAR.

Recount the saved evidence with `python3 -B lib/benchmark/jbmc-fast-follow/results.py --check`. Repeat the independent standalone JVM witnesses with `python3 -B lib/benchmark/jbmc-fast-follow/stock_replays.py --check`. The numbered examples expose their ordinary task plans and JVM controls.
