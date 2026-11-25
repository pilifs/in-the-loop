# Five merged Java changes — caller-visible behavior across revisions

## Objective

Compare the same public calls immediately before and after each change. Check the result a caller can use, including what a second call reads from a reused object. Each case distinguishes upstream observations from predictions to exercise on the pinned revisions.

## apache/commons-cli#450 · Apache Commons CLI — option defaults across parses

**Change and revisions.** [PR #450](https://github.com/apache/commons-cli/pull/450) landed as one commit containing both submitted changes. Before `d959de8fb66f8aee8964dd3080920dfb9cdfcdc3`, after `e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516`. A property supplies a value for the returned command line. Reusing the option definition should leave the next invocation free to supply its own value. [Revision history](https://github.com/apache/commons-cli/blob/e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516/src/changes/changes.xml) · [landed comparison](https://github.com/apache/commons-cli/compare/d959de8fb66f8aee8964dd3080920dfb9cdfcdc3...e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516)

**Public scenario.** Register `Option.builder("o").hasArg().get()` in one `Options`. Call `new DefaultParser().parse(options, new String[0], properties)`. Read `getOptionValue("o")` on the returned `CommandLine` and `options.getOption("o").getValues()` on the definition. Retain the first result when using the same options again.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-cli#450.1 · Intent | With an initially empty option and the same parser, parse `o=first`, then `o=second`, each with empty argv. | Before, expect results `first, first` and stored values `["first"]`. After, expect `first, second`, the first result still reading `first`, and stored values `null` after either call. | Each invocation supplies exactly one default. A fresh definition would yield the current one. The merged parse contract expressly preserves the registered values. | The second merged result reads `first`, the retained result changes, or a registered value appears. |
| apache/commons-cli#450.2 · Control | On a fresh definition set `option.getValuesList().add("preset")` before registration. Parse empty argv with `o=fallback`. | Both revisions should return `preset` and the definition should still contain exactly `["preset"]`. | A property fills an absent value. The parent already contains a regression for a caller-supplied value. | Either call returns the fallback, or drops or appends to the preset. |
| apache/commons-cli#450.3 · Challenge | Add a required flag `Option.builder("r").required().get()`. First parse empty argv with `o=discarded`. Catch `MissingOptionException`; then use a fresh parser, the same options, argv `["-r"]` and `o=retry`. Compare with the retry alone on fresh definitions. | Both should reject the first call for missing `r`. Before, predict the retried result reads `discarded` while the fresh result reads `retry`. After, both should read `retry`, contain flag `r`, and have an empty argument list. | The error prevents a command line from reaching the caller. Its default should not outlive the failed invocation. The source processes properties before the required-option check. | The merged retry differs from the fresh invocation, or the first call succeeds. |

**Evidence and limits.** The PR author reports three new tests failing on master and passing with the change, including leakage into a later command line with `-D` properties. The pinned tests exercise successful parses. Reading the first command line alone misses the mutated definition. The failed-parse retry is a source-derived prediction.

**Technical notes.** These calls are in the single Maven artifact `commons-cli:commons-cli`. Its POM targets Java 8. A single property avoids relying on iteration order.

**Sources.** [PR #450](https://github.com/apache/commons-cli/pull/450) · [landed comparison](https://github.com/apache/commons-cli/compare/d959de8fb66f8aee8964dd3080920dfb9cdfcdc3...e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516) · [Parent preset test](https://github.com/apache/commons-cli/blob/d959de8fb66f8aee8964dd3080920dfb9cdfcdc3/src/test/java/org/apache/commons/cli/DefaultParserTest.java) · [Merged parser and public contract](https://github.com/apache/commons-cli/blob/e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516/src/main/java/org/apache/commons/cli/DefaultParser.java) · [Landed regressions](https://github.com/apache/commons-cli/blob/e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516/src/test/java/org/apache/commons/cli/DefaultParserTest.java) · [Option value accessors](https://github.com/apache/commons-cli/blob/e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516/src/main/java/org/apache/commons/cli/Option.java) · [Maven descriptor](https://github.com/apache/commons-cli/blob/e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516/pom.xml)

## HdrHistogram/HdrHistogram#145 · HdrHistogram — equality after growth and reset

**Change and revisions.** [PR #145](https://github.com/HdrHistogram/HdrHistogram/pull/145) merged one submitted commit into first parent `89b0d5981bafb6b4b4ac624473a1771405d4da20` at `1b51671cf06062671af931f98a8af2a53d335a70`. Histograms with the same precision and recorded counts should compare equal even if one previously grew larger. The comparison now reads recorded values when storage sizes differ. [landed comparison](https://github.com/HdrHistogram/HdrHistogram/compare/89b0d5981bafb6b4b4ac624473a1771405d4da20...1b51671cf06062671af931f98a8af2a53d335a70)

**Public scenario.** Use two `org.HdrHistogram.Histogram` instances created with `new Histogram(3)`. Let `x = (1L << 62) - 1`. Record `x`, then `Long.MAX_VALUE`, in A. Call `A.reset()` and record `x` again. Record only `x` in B. Check `getTotalCount()` and `getCountAtValue(x)` on each, then call `A.equals(B)` and `B.equals(A)` independently so an exception in one direction does not hide the other.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| HdrHistogram/HdrHistogram#145.1 · Intent | Compare the grown-and-reset A and the smaller B above. | Both should report one sample at `x`. Before, predict `A.equals(B)` throws `ArrayIndexOutOfBoundsException` and `B.equals(A)` returns true. After, both directions should return true. | Reset discards observations. The two remaining one-element samples coincide. Issue #144 explains the receiver-sized loop, and the landed regression compares A to B. | Either merged comparison throws or returns false despite the matching samples, or the predicted direction of the parent failure is reversed. |
| HdrHistogram/HdrHistogram#145.2 · Control | Start two fresh three-digit histograms. Record 10, 20, 30 in A and 30, 10, 20 in B. Then record another 20 in B. | On both revisions the first comparison should be true both ways. After the extra sample it should be false both ways, with total counts 3 and 4. | A histogram counts occurrences independently of insertion order. The extra observation changes exactly one count. | Reordering alone makes the pair unequal, or the extra occurrence leaves it equal. |
| HdrHistogram/HdrHistogram#145.3 · Challenge | Give A the growth/reset history above through the reset, then record 10, 20, 20, 40. In fresh B record 10, 30, 30, 40. Compare in both directions. | On both revisions expect false both ways. Each has four samples and the same extrema, but the counts at 20 and 30 are respectively (2, 0) and (0, 2). | These small integers occupy distinct bins at three-digit precision. The unequal interior counts occur within both storage ranges, before the old loop could reach an unavailable index. | Both public count profiles match the fixture but either comparison accepts the pair or throws. |

**Evidence and limits.** Issue #144 reports an out-of-bounds comparison. The landed regression asserts storage lengths of 54,272 and 55,296 across the two growth steps and checks equality with the larger receiver. Its public equality assertion expresses the expected outcome. Symmetry and the mismatched interior counts are source-based predictions. Agreement on total, minimum and maximum alone misses the challenge.

**Technical notes.** The one-argument `Histogram(int)` enables automatic resizing. Using the fixed-range constructor changes the fixture. The Maven descriptor for `org.hdrhistogram:HdrHistogram` sets compiler source and target to 1.6.

**Sources.** [PR #145](https://github.com/HdrHistogram/HdrHistogram/pull/145) · [landed comparison](https://github.com/HdrHistogram/HdrHistogram/compare/89b0d5981bafb6b4b4ac624473a1771405d4da20...1b51671cf06062671af931f98a8af2a53d335a70) · [Issue #144](https://github.com/HdrHistogram/HdrHistogram/issues/144) · [Parent equality](https://github.com/HdrHistogram/HdrHistogram/blob/89b0d5981bafb6b4b4ac624473a1771405d4da20/src/main/java/org/HdrHistogram/AbstractHistogram.java) · [Merged equality, reset and count access](https://github.com/HdrHistogram/HdrHistogram/blob/1b51671cf06062671af931f98a8af2a53d335a70/src/main/java/org/HdrHistogram/AbstractHistogram.java) · [Constructor and count storage](https://github.com/HdrHistogram/HdrHistogram/blob/1b51671cf06062671af931f98a8af2a53d335a70/src/main/java/org/HdrHistogram/Histogram.java) · [Landed regression](https://github.com/HdrHistogram/HdrHistogram/blob/1b51671cf06062671af931f98a8af2a53d335a70/src/test/java/org/HdrHistogram/HistogramAutosizingTest.java) · [Maven descriptor](https://github.com/HdrHistogram/HdrHistogram/blob/1b51671cf06062671af931f98a8af2a53d335a70/pom.xml)

## ThreeTen/threeten-extra#463 · ThreeTen-Extra — arithmetic across the British calendar cutover

**Change and revisions.** [PR #463](https://github.com/ThreeTen/threeten-extra/pull/463) squashed three submitted commits into `c5f44114d357c1dc25d0e6f00dec5a126cae5cc6`, immediately after `ded297257577f8dba1aa06f4ddd879a9b2d0d486`. It distinguishes selecting a day field from resolving a month or year, recomputes British period remainders in elapsed days, and detects overflow in Julian-era conversion. [landed comparison](https://github.com/ThreeTen/threeten-extra/compare/ded297257577f8dba1aa06f4ddd879a9b2d0d486...c5f44114d357c1dc25d0e6f00dec5a126cae5cc6)

**Public scenario.** Use the explicit `BritishCutoverDate.of` and `JulianDate.of` factories. Read a returned date as `YEAR`, `MONTH_OF_YEAR` and `DAY_OF_MONTH`. For a period also read `YEARS`, `MONTHS` and `DAYS`, add it back to the start with `plus(period)`, and compare `toEpochDay()` with the intended end. British 2 September 1752 (Julian) and 14 September (Gregorian) are consecutive days.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| ThreeTen/threeten-extra#463.1 · Intent | Add one `MONTHS` unit to British 12 August 1752. Separately add one `YEARS` unit to British 12 September 1751. | Both reach the same nominal 12 September. Before, predict 23 September 1752. After, expect 2 September 1752. | The parent interprets the missing date as Julian, eleven days ahead in Gregorian labels. The new package rules resolve the smaller field to the previous valid day when adding months or years. | The two operations disagree, or either merged operation lands on 23 September. |
| ThreeTen/threeten-extra#463.2 · Control | From British 2 September 1752 add one `DAYS` unit, then subtract one day. Separately select `with(DAY_OF_MONTH, 12)` on that start. | On both revisions, the day step should yield 14 September with epoch delta +1, then recover 2 September. Directly selecting day 12 should yield 23 September. | A day step advances elapsed time. Direct selection of an interior missing day uses its Julian interpretation. This exercises the same nominal day as claim 1. | A missing label appears, the day step advances twelve elapsed days, or selecting day 12 clamps it to 2. |
| ThreeTen/threeten-extra#463.3 · Challenge | Let S be British 18 March 1753 and E be British 1 September 1752. Read `p = S.until(E)`, then `S.plus(p)` and its epoch day. | Before, predict (0 years, −6 months, −17 days) and a readback eleven days before E. After, expect (0, −6, −6) and exact readback at E. | Subtracting six months lands on 18 September. Going back four days reaches the 14th, one more reaches the 2nd and one more the 1st. The ISO epoch-day oracle for E is `LocalDate.of(1752, 9, 12).toEpochDay()`. | A merged period has the expected components but reads back to a different epoch day, or the merged residual differs from −6. |
| ThreeTen/threeten-extra#463.4 · Intent | On `JulianDate.of(2011,2,26)`, set `DAY_OF_MONTH` to 30. Repeat at 32. | At 30, expect 28 February before and 2 March after. At 32 both should throw `DateTimeException`. | The year is common. Adding four elapsed days to 26 February reaches 2 March. The outer day field admits 1 through 31. | The merged date stays in February at 30 or accepts 32. |
| ThreeTen/threeten-extra#463.5 · Intent | Call `prolepticYear(JulianEra.BC, Integer.MIN_VALUE)` on both singleton chronologies. Also pass `Integer.MAX_VALUE` as the BC year. | Minimum input: predict −2147483647 before, `DateTimeException` after. Maximum input: both should return −2147483646. | The formula is 1 minus year-of-era. The first mathematical result is 2147483649, outside signed int. The second fits. | Either merged converter wraps the first result or rejects the representable second result. |

**Evidence and limits.** The release note identifies the reversal in month/year resolution. The two pinned suites give worked dates, overflow cases and period add-back assertions. Their British backward example starts on 20 March and ends on 2 September. The 18 March to 1 September readback above is a separate prediction with an ISO-date oracle. Checking only the month component of a period misses an eleven-day residual error.

**Technical notes.** Use `org.threeten:threeten-extra` and the library's `JulianEra` for **both** chronologies. Explicit factories avoid provider lookup. `until(end)` returns a chronology-specific `ChronoPeriod`; `until(end, MONTHS)` returns a number and cannot check the remainder.

**Sources.** [PR #463](https://github.com/ThreeTen/threeten-extra/pull/463) · [landed comparison](https://github.com/ThreeTen/threeten-extra/compare/ded297257577f8dba1aa06f4ddd879a9b2d0d486...c5f44114d357c1dc25d0e6f00dec5a126cae5cc6) · [Calendar design rules](https://github.com/ThreeTen/threeten-extra/blob/c5f44114d357c1dc25d0e6f00dec5a126cae5cc6/src/main/java/org/threeten/extra/chrono/package-info.java) · [British date before](https://github.com/ThreeTen/threeten-extra/blob/ded297257577f8dba1aa06f4ddd879a9b2d0d486/src/main/java/org/threeten/extra/chrono/BritishCutoverDate.java) · [British date after](https://github.com/ThreeTen/threeten-extra/blob/c5f44114d357c1dc25d0e6f00dec5a126cae5cc6/src/main/java/org/threeten/extra/chrono/BritishCutoverDate.java) · [Julian day adjustment](https://github.com/ThreeTen/threeten-extra/blob/c5f44114d357c1dc25d0e6f00dec5a126cae5cc6/src/main/java/org/threeten/extra/chrono/JulianDate.java) · [British tests](https://github.com/ThreeTen/threeten-extra/blob/c5f44114d357c1dc25d0e6f00dec5a126cae5cc6/src/test/java/org/threeten/extra/chrono/TestBritishCutoverChronology.java) · [Julian tests](https://github.com/ThreeTen/threeten-extra/blob/c5f44114d357c1dc25d0e6f00dec5a126cae5cc6/src/test/java/org/threeten/extra/chrono/TestJulianChronology.java) · [Release note](https://github.com/ThreeTen/threeten-extra/blob/c5f44114d357c1dc25d0e6f00dec5a126cae5cc6/src/changes/changes.xml) · [Maven descriptor](https://github.com/ThreeTen/threeten-extra/blob/c5f44114d357c1dc25d0e6f00dec5a126cae5cc6/pom.xml)

## Esri/geometry-api-java#329 · Esri Geometry API — restoring a closed polyline after subtraction

**Change and revisions.** [PR #329](https://github.com/Esri/geometry-api-java/pull/329) landed both submitted commits in `1ac0c090047076329cb8c3906286086f313ac9de`, with `0318320724ef2b94d4d11e056cd18c04eeb23661` as its parent. When the subtractor meets the repeated first vertex of a closed path, the restoration code must choose a starting edge that belongs to the retained line. [landed comparison](https://github.com/Esri/geometry-api-java/compare/0318320724ef2b94d4d11e056cd18c04eeb23661...1ac0c090047076329cb8c3906286086f313ac9de)

**Public scenario.** Import the following coordinates as two paths of one `MULTILINESTRING` with `OperatorImportFromWkt.local().execute(0, Geometry.Type.Polyline, wkt, null)`. Use the same importer for the subtractor. Call `GeometryEngine.difference(left, right, null)`. On the returned `Polyline`, read the paths using `getPathCount()`, `getPathStart(i)`, `getPathEnd(i)` (exclusive) and `getPoint(j)`. Include a closing edge when the path is implicitly closed. Compare the nonzero straight segments by coordinates, allowing equivalent path order, traversal direction, start vertex and collinear splits.

- First path, in order: A (117422, −64366), B (119336, −64652), C (119218, −65440), D (114999, −64810), E (115034, −64578), F (115117, −64022), A.
- Second path, in order: (111611, −62617), (111365, −64268), (110476, −64135), (110722, −62484), (110975, −62522), then its first point again.
- The touching subtractor runs from A to T (117911, −61089). All coordinates are planar XY.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| Esri/geometry-api-java#329.1 · Intent | Subtract A–T from the two paths. Repeat with T–A. | The issue discussion reports a Java exception for A–T. Predict that the pinned parent throws on A–T. The reversed Java parent outcome is open. On the merge, expect a polyline covering all six first-loop edges and all five second-loop edges exactly once in either direction of the subtractor. | The inputs share A and no positive-length interval. The landed Java test spells out both original paths as its expected JSON for both orientations. | A merged call throws, omits either closing segment or the remote loop, or includes a positive-length piece of A–T. |
| Esri/geometry-api-java#329.2 · Control | Use just the open first path A–B–C–D–E–F and subtract A–T. | Both Java revisions should return exactly the five input edges with no F–A closure. | Removing the final A removes one real edge. The reported open-path control succeeded in the C# port. | Either Java result drops a segment, closes the line, includes the subtractor, or throws. |
| Esri/geometry-api-java#329.3 · Challenge | Hold both original loops fixed. Extend the reversed subtractor T–A by one segment to B. Read the returned segments and their lengths. | On the merge, A–B should disappear. The five other first-loop edges and all five remote edges should remain exactly once. Total length should be the input length less the Euclidean distance A–B, with absolute error at most 1e−7 coordinate units using `calculateLength2D()` and `Math.hypot(1914, -286)`. Parent behavior for this mixed contact and overlap is open. | T–A contributes only point contact. A–B is the only full edge shared with either loop. Its removal gives an independent edge-by-edge oracle. | The result is nonempty but still covers any interior of A–B, loses a remote edge, adds a positive-length piece of T–A, or counts an edge twice. |

**Evidence and limits.** Issue #328 reports an internal error for both subtractor directions in a C# derivative on .NET Framework 4.8. A follow-up reports the forward Java operator call also throwing on these WKT inputs, without naming a revision or exception class. The landed Java regression calls `OperatorDifference.local().execute` and checks the two JSON strings. The public Java facade delegates to that operator. A nonempty result or an empty line-dimensional intersection says nothing about which edges survived. The Java parent exception and the extended subtractor have not been executed here.

**Technical notes.** Use `com.esri.geometry:esri-geometry-api`, null spatial reference and the explicit repeated endpoints from the WKT. A polygon would introduce an area interior and change the subtraction.

**Sources.** [PR #329](https://github.com/Esri/geometry-api-java/pull/329) · [landed comparison](https://github.com/Esri/geometry-api-java/compare/0318320724ef2b94d4d11e056cd18c04eeb23661...1ac0c090047076329cb8c3906286086f313ac9de) · [Original C# report and controls](https://github.com/Esri/geometry-api-java/issues/328) · [Java observation in the issue](https://github.com/Esri/geometry-api-java/issues/328#issuecomment-5455650694) · [Java regression and full WKT](https://github.com/Esri/geometry-api-java/blob/1ac0c090047076329cb8c3906286086f313ac9de/src/test/java/com/esri/core/geometry/TestDifference.java) · [Public facade](https://github.com/Esri/geometry-api-java/blob/1ac0c090047076329cb8c3906286086f313ac9de/src/main/java/com/esri/core/geometry/GeometryEngine.java) · [Difference contract](https://github.com/Esri/geometry-api-java/blob/1ac0c090047076329cb8c3906286086f313ac9de/src/main/java/com/esri/core/geometry/OperatorDifference.java) · [Restoration](https://github.com/Esri/geometry-api-java/blob/1ac0c090047076329cb8c3906286086f313ac9de/src/main/java/com/esri/core/geometry/TopologicalOperations.java) · [Path readback](https://github.com/Esri/geometry-api-java/blob/1ac0c090047076329cb8c3906286086f313ac9de/src/main/java/com/esri/core/geometry/MultiPath.java) · [Maven descriptor](https://github.com/Esri/geometry-api-java/blob/1ac0c090047076329cb8c3906286086f313ac9de/pom.xml)

## spring-projects/spring-framework#37322 · Spring JDBC — allocating IDs after a sequence transaction fails

**Change and revisions.** [PR #37322](https://github.com/spring-projects/spring-framework/pull/37322) landed one submitted change at `f96403da2a821f9b8281161847e32a1c4e35e470` on parent `eb9928f993fc650ba92a833ecfd28194c28afd3e`. When commit or restoration of auto-commit throws, the incrementer discards the rest of its cached ID range. The next public request must reserve a range against the sequence table again. [landed comparison](https://github.com/spring-projects/spring-framework/compare/eb9928f993fc650ba92a833ecfd28194c28afd3e...f96403da2a821f9b8281161847e32a1c4e35e470)

**Public scenario.** Start each history with an InnoDB sequence table `myseq(seq BIGINT NOT NULL)` containing only 98 and a separate empty table with a `BIGINT PRIMARY KEY` supplied by the caller. Use one `new MySQLMaxValueIncrementer(dataSource, "myseq", "seq")`, call `setUseNewConnection(true)`, `setCacheSize(2)` and `afterPropertiesSet()`. Call `nextLongValue()` sequentially with no competing writers. After each successful return, insert that ID and commit the insert. Read the durable sequence value and inserted IDs on an independent connection with fresh reads.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37322.1 · Intent | Fail the first allocation at commit after the connection has read 100. Establish by an independent read that the transaction rolled back to 98. On the same incrementer request and insert three IDs. | Both initially throw `DataAccessResourceFailureException` and return no ID. Before, the PR reports 100, 99, 100 and a duplicate-key failure on the third insert. After, it reports 99, 100, 101, all inserts successful. Expect final sequence 102 on the merge. | With durable value 98, the next confirmed two-ID reservation covers 99–100. The following one covers 101–102. The primary key independently exposes reuse. | With rollback confirmed, the merged allocator serves 100 before 99, issues a duplicate, or returns 101 while the sequence still reads 100. |
| spring-projects/spring-framework#37322.2 · Control | On a fresh fixture let every reservation commit normally. Read the sequence after each of three requests. | Both revisions should return 99, 100, 101 with durable maxima 100, 100, 102. All three inserts should succeed. | A reservation of two advances the durable row once. Its second use consumes the cached ID without raising the maximum. | An ID repeats, a second reservation occurs before returning 100, or the durable row fails to cover an issued ID. |
| spring-projects/spring-framework#37322.3 · Challenge | Keep the first public call exceptional, but let the real commit succeed. Start its connection in auto-commit mode, then have only the first post-commit `setAutoCommit(true)` throw `SQLException`. Independently confirm the row is 100. Allow all subsequent calls to succeed. | Both should report `DataAccessResourceFailureException` initially. Before, predict subsequent IDs 100, 101, 102, ending at durable maximum 102. After, predict 101, 102, 103, ending at 104. Expect three successful inserts on both revisions. On the merge 99–100 remain unused. | Commit and restoring auto-commit share a catch block. Here 99–100 really were reserved, so discarding them leaves a gap. An exception alone cannot identify which range the database will grant next. | Given the confirmed first commit and no concurrent writer, the merged retry serves any ID ≤100, reports success without the corresponding reservation, or inserts a duplicate. |

**Evidence and limits.** The PR reports testing MySQL 9.1.0 and confirming rollback from a separate connection. The landed Mockito test supplies maxima 2, 2, 4, fails the first commit, expects 1, 2, 3, 4 on subsequent calls and counts three commits. It cannot establish durable state or insert uniqueness. The post-commit restoration case is predicted from the catch block. The durable read distinguishes it from the reported rollback even though the caller sees the same exception.

**Technical notes.** Use the `spring-jdbc` Gradle module and a transactional sequence table. The reservation update and `select last_insert_id()` run on the same physical connection because MySQL tracks that value per connection. A JDBC test double can establish calls and returned IDs. Durable row and uniqueness claims require a transactional database and a separate reader.

**Sources.** [PR #37322](https://github.com/spring-projects/spring-framework/pull/37322) · [landed comparison](https://github.com/spring-projects/spring-framework/compare/eb9928f993fc650ba92a833ecfd28194c28afd3e...f96403da2a821f9b8281161847e32a1c4e35e470) · [Parent allocator](https://github.com/spring-projects/spring-framework/blob/eb9928f993fc650ba92a833ecfd28194c28afd3e/spring-jdbc/src/main/java/org/springframework/jdbc/support/incrementer/MySQLMaxValueIncrementer.java) · [Merged allocator and table contract](https://github.com/spring-projects/spring-framework/blob/f96403da2a821f9b8281161847e32a1c4e35e470/spring-jdbc/src/main/java/org/springframework/jdbc/support/incrementer/MySQLMaxValueIncrementer.java) · [Public ID entry](https://github.com/spring-projects/spring-framework/blob/f96403da2a821f9b8281161847e32a1c4e35e470/spring-jdbc/src/main/java/org/springframework/jdbc/support/incrementer/AbstractDataFieldMaxValueIncrementer.java) · [Landed JDBC regression](https://github.com/spring-projects/spring-framework/blob/f96403da2a821f9b8281161847e32a1c4e35e470/spring-jdbc/src/test/java/org/springframework/jdbc/support/incrementer/DataFieldMaxValueIncrementerTests.java) · [Module build](https://github.com/spring-projects/spring-framework/blob/f96403da2a821f9b8281161847e32a1c4e35e470/spring-jdbc/spring-jdbc.gradle)

## Setup Agent Notes

### What is ready, and where

- `source ~/.cache/in-the-loop/merged-pr-links-n01-n05/scripts/env.sh` sets `$O`, `$W`, `$MVN`, `$J8` … `$J25`, `TMPDIR`, `GRADLE_USER_HOME`.
  The default `java` on `PATH` is JDK 25: name the JDK by path.
- Worktrees at both pins of every case: `$W/N01-commons-cli-{parent,fix}`, `$W/N02-HdrHistogram-{parent,fix}`, `$W/N03-threeten-extra-{parent,fix}`,
  `$W/N04-geometry-api-java-{parent,fix}`, `$W/N05-spring-framework-{parent,fix}`; full commit ids in [Upstream revisions](#upstream-revisions).
- Built jars, digests and classpaths: `$O/artifacts/CASE-ROLE/` (`SHA256SUMS`, `runtime-classpath.txt`, `test-classpath.txt`); full digests in
  [Digests of the built artifacts](#digests-of-the-built-artifacts-n01n05). N01 and N02 have no runtime dependencies (the jar alone);
  N03 needs `jspecify-1.0.1.jar` and `joda-convert-2.2.4.jar` only as optional deps; N04 needs `jackson-core-2.9.6.jar` (paths in `runtime-classpath.txt`).
- Offline Maven commands per case (each a few seconds) in the case sections: N01 and N03 on `$J17`, N02 and N04 on `$J8` (their bytecode
  targets are 1.6 and 1.7). Everything they need is in `$O/m2`.
- N05: Gradle 9.8.0 at `$O/tools/gradle-9.8.0`, run through `$O/scripts/gradle_case.sh` (JDK 25 launcher, toolchains 17/25, no build cache, no scan);
  dependencies are in `$O/gradle-home`. Built by job `20261125-225459-setup-build-spring-jdbc-at-both-37322-re` (passed):
  `$O/artifacts/N05-{fix,parent}/spring-jdbc-7.0.10-SNAPSHOT.jar`, `runtimeClasspath.txt` (22 entries) and `testRuntimeClasspath.txt` (56 entries),
  `:`-joined absolute paths that all exist (Spring project jars copied under `tree/`, third-party jars in `$O/gradle-home`), and `SHA256SUMS`.
  The worktrees are clean again; a rebuild is the offline command in the N05 section.
- For N05's durable claims: Docker image `mysql@sha256:0255b469f0135a0236d672d60e3154ae2f4538b146744966d96440318cc822c6` (`mysql:9.1.0`, the version the PR
  tested), Connector/J `$O/releases/mysql-connector-j-9.1.0/mysql-connector-j-9.1.0.jar` (sha256 in [Released artifacts](#released-artifacts-and-signatures));
  a connection smoke worked (InnoDB default, REPEATABLE-READ, autocommit on). Command in the N05 section.
- Released jars with checked checksums and signatures in `$O/releases/` (commons-cli 1.11.0, HdrHistogram 2.1.10/2.1.11, threeten-extra 1.11.0,
  esri-geometry-api 2.2.4, spring-jdbc 7.0.9/7.0.10).

### What was verified on a JVM

- Each landed regression passes on the fix and fails on the parent, as the brief says:
  - N01: three new `DefaultParserTest` tests fail on the parent (`expected: <second> but was: <first>` in `testPropertiesReuseOptions`, and two more).
  - N02: `testHistogramEqualsAfterResizing` errors on the parent with `ArrayIndexOutOfBoundsException: 54272` inside `AbstractHistogram.equals`.
  - N03: 51 of the 1668 landed British/Julian tests fail on the parent (`test_prolepticYear_overflow`, `test_with_TemporalField_dayOverflow`,
    `test_until_Period_plusIsInverse`, `test_until_CLD_backwardAcrossCutover`, …).
  - N04: `testIssue328` errors on the parent with `GeometryException: internal error` in `TopologicalOperations.restorePolylineParts_`, on the
    **forward** (A–T) call; the backward call is never reached on the parent.
  - N05: `mySQLMaxValueIncrementerWithCommitFailure()` fails on the parent with `AssertionFailedError` at `DataFieldMaxValueIncrementerTests.java:258`,
    the first `nextLongValue()` after the failed commit not returning 1; the other 11 tests of the class pass there (job
    `20261125-225459-setup-build-spring-jdbc-at-both-37322-re`). This is the landed Mockito regression only; nothing ran against MySQL beyond
    the connection smoke.
- Each Maven case's full upstream `package` passes at both pins (N01 998/995, N02 150/149, N03 13857/13787, N04 506/505 tests).
- N05's spring-jdbc test task passes at both pins, offline (972 / 971 tests, 6 skipped each).
- N05's built `MySQLMaxValueIncrementer.class` at the fix equals the one in released spring-jdbc 7.0.10 byte for byte.

### What to know before starting

- All four Maven builds are `-SNAPSHOT` or unreleased versions of the pinned trees, not published artifacts: N04's builds say `2.3.0`, but no
  2.3.0 is on Maven Central (2.2.4 is the newest, and its `TopologicalOperations.java` = the parent's). N02's fix landed in release 2.1.11, N05's in 7.0.10
  (`MySQLMaxValueIncrementer.java` byte for byte); commons-cli and threeten-extra have no release with their fix yet.
- N02 is a merge commit: diff against its first parent `89b0d5981bafb6b4b4ac624473a1771405d4da20`.
- N03's build runs surefire twice (`default-test`, `test-without-modules`); the reports folder keeps one set.
- N05: no MySQL driver is on spring-jdbc's classpaths; Connector/J 9.1.0 is in `$O/releases/`. The MySQL image's entrypoint restarts its server
  once during init: wait for a TCP ping. Spring's build applies the Develocity conventions plugin; keep `--no-scan --no-build-cache` (as
  `gradle_case.sh` does) so nothing is uploaded or fetched from ge.spring.io. The version is `7.0.10-SNAPSHOT`, so the build also lists
  repo.spring.io's milestone and snapshot repositories; none of the resolved artifacts came from them.
- HdrHistogram 2.1.10's signature could not be checked (signing key on no keyserver tried); its sha1 matched Central.
- N05 rebuilds take about a minute per pin offline (58 s and 66 s in the job, the whole spring-jdbc test task included), at the limit above
  which this repository queues a build as a verification job. `N05_job.sh` and `gradle_case.sh` are the commands to queue.
- N05's `SHA256SUMS` line for `MySQLMaxValueIncrementer.class` is the entry inside the jar: `sha256sum -c` reports it missing (see the digests section).
- N05's job result was recorded by the runner on the default line (commit `b3390c67f58f80e874a730080a36fba5b4bfe7c5`), not on this record's line; the merge brings it in.

### What is left for the domain work on purpose

- Every scenario and claim of the brief: harnesses against the built jars, the predictions (N01 failed-parse retry, N02 symmetry and the
  interior-count challenge, N03 18 March → 1 September readback, N04 reversed and extended subtractors on both revisions), and N05's JDBC test
  double or MySQL fixture (failing commit, failing `setAutoCommit(true)`, independent reader). No example folders, claims or sidecars exist.
