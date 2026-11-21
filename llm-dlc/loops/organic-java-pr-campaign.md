# Prove six real Java library fixes from their upstream pull requests

**Engineering brief for `pilifs/in-the-loop` · 20 November 2026**

**Start with Guava #8509.** Two ordinary calls to the same public view give a decisive test of the verifier. On the parent, the view’s total size looks right, its per-key count is negative, and reading the only entry throws. The fix makes all three observations agree. Examples 319 and 320 already exercise Guava maps and live multiset views. This PR asks the checker to use those capabilities together on an upstream change, across two backing objects and two ways of observing the same key.

Commission **six merged upstream PRs across five Java projects**. Run Guava and Commons Lang first. Avro can proceed independently. Use the two Gson changes in order, then run Commons Codec to test whether the work on chunked input helps another project. Two additional PRs are reserved for specific engineering questions. Use the team’s existing repository workflow. These are disclosed engineering cases and stay outside the blind dependency-upgrade evaluation.

## Starting point and work order

At the inspected `main` commit, `4f87fd1f`, examples 312–331 had 125 bounded claims decided by finite JVM execution. Strict native verification decided 107 at their original scope, including 29 refutations. Example 320 already covered six live-view claims on actual Java collections. Example 308 demonstrated bounded reasoning over a real Commons Text implementation. The opportunity is to preserve the relevant facts across a public call, a second object, or a second read. Record the current baseline before extending anything. The active importer and array campaign may already have closed part of a gap. The published example index was checked for these PRs. Commons Numbers #223 was dropped because it is already example 105. [Campaign ledger](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/verification/twenty-example-fast-follow-results.json) · [Example 320](https://github.com/pilifs/in-the-loop/tree/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/320-collections-live-multiset-views) · [Example 308](https://github.com/pilifs/in-the-loop/tree/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/308-commons-text-longest-common-subsequence) · [Example index](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/index.json)

| Order | Upstream change | What should become easier to verify |
|---|---|---|
| 1 | [Guava #8509](https://github.com/google/guava/pull/8509) | Agreement between lookup and iteration on a live view, including saturating arithmetic |
| 2, parallel with 1 | [Commons Lang #1719](https://github.com/apache/commons-lang/pull/1719) | Exact UTF-16 output across a cut, then reuse on a second public string operation |
| 3, independent | [Avro #3878](https://github.com/apache/avro/pull/3878) | A buffer’s logical limit and accessible bytes across Hadoop, Avro and the JDK |
| 4 | [Gson #3034](https://github.com/google/gson/pull/3034) | Carry a scanner’s overflow state through token classification and retrieval of the original text |
| 5, after 4 | [Gson #3137](https://github.com/google/gson/pull/3137) | Preserve absolute input position across short reads on the same parser |
| 6, after 5 | [Commons Codec #135](https://github.com/apache/commons-codec/pull/135) | Preserve an unfinished byte across nonzero-offset writes in a different project |

## What to prove on each PR

### 1. Guava #8509 · Can every observer see the saturated count?

Build two real `HashMultiset<String>` instances, add `"a"` with count `1 << 30` to each, then construct `Multisets.sum(left, right)` once. Each add stores a count, so this needs only one distinct key per bag. On the JVM the parent returned `Integer.MAX_VALUE` for `size()`, `Integer.MIN_VALUE` for `count("a")`, and threw `IllegalArgumentException` when reading the first entry. The fix returned `Integer.MAX_VALUE` from all three observations. An absent key returned zero on both. Two counts of three produced six through every observer on both.

**Target claim.** For operand counts in `{0, 1, 3, 2^30−1, 2^30, 2^30+1, Integer.MAX_VALUE}`, check lookup against a widened mathematical sum capped at `Integer.MAX_VALUE`. Grade iteration separately. Expect one matching entry if either count is positive, and no entries if both are zero. Keep an absent-key check and an exhausted-iterator check. In a separate small-count control, increase one backing count from three to four after creating the view and re-read the total of seven through both observers. Start with the single concrete key so hash collisions and element ordering cannot obscure the first failure. A checked summary of the sum alone earns credit only when the actual view and iterator use it, with their backing counts intact. [Upstream implementation and both regression tests](https://github.com/google/guava/pull/8509/files)

### 2. Commons Lang #1719 · Can a substring cut preserve a surrogate pair?

Run `StringUtils.truncate("a😀b", 0, 2)` and compare UTF-16 **code units**. The parent produced `[0061,D83D]`, the fix `[0061]`. Cutting from the other direction with `truncate("😀ab", 1, 2)` produced `[DE00,0061]` and `[0061]`. Cutting exactly around the pair kept `[D83D,DE00]` on both. Logging rendered strings can conceal a lone surrogate.

**Target claim.** Generate all strings of up to four tokens over `{a, 😀}`, with offsets and widths from zero through the UTF-16 length plus one. Freeze an independent oracle that clamps the original window, moves endpoints inward if they bisect a pair, and returns the exact remaining units, including empty results. First prove one symbolic cut on a fixed mixed string, then cover the registered domain. Transfer to `abbreviate("😀abcdef", 4)`: the parent emitted a lone high surrogate and three dots, the fix emitted just the dots. At width five both preserve the whole pair and the dots. Start from existing string and surrogate support. Example 311 already exercises supplementary-character search on a real StringBuilder. This case checks which original code units survive a cut. [Example 311](https://github.com/pilifs/in-the-loop/tree/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/311-commons-lang-utf16-search) · [Upstream implementation and tests](https://github.com/apache/commons-lang/pull/1719/files)

### 3. Apache Avro #3878 · How much of a backing array is visible?

Use the real `AvroDatumConverterFactory.create(BytesWritable.class)` path. Start with Hadoop `BytesWritable([1,2,3,4,5])`, call `setSize(3)`, then convert. The upstream test requires `remaining()==3` and values 1, 2, 3 at indices 0, 1, 2. Those three reads alone cannot distinguish the fix. The parent wraps the whole five-byte backing array. The fix supplies the logical length to `ByteBuffer.wrap`. On the fixed buffer an absolute read at index 3 must throw even though the backing array still contains that byte.

**Target claim.** For original backing lengths 0–5 and each logical length from zero through capacity, observe initial position, limit, capacity, the readable prefix, and the first rejected absolute index. With a freshly constructed five-byte backing array shrunk to three, the fixed tuple is `(0,3,5)`. Record that absolute reads leave position unchanged. Use fresh objects on each run and include full-length and zero-length controls. The likely reusable work is carrying distinct length, limit and capacity facts across the real converter and JDK view. If factory initialization blocks a native run, retain that result and report a direct run of the public nested converter under its own scope. [Upstream implementation and regression test](https://github.com/apache/avro/pull/3878/files)

### 4. Gson #3034 · Can the scanner distinguish overflow from a leading zero?

Give a strict `JsonReader` the decimal text `18446744073709551616` followed by one digit. The prefix is 2⁶⁴. Java’s signed `long` accumulator wraps to zero, while the input remains a valid JSON integer literal. For all ten suffixes, the parent threw `MalformedJsonException` at `peek()`. On the fix, `peek()` returned `NUMBER` and `nextString()` returned the entire input. On both revisions `10` succeeded and `00` and `01` were rejected.

**Target claim.** Keep the 20-character prefix constant and make the final ASCII digit symbolic. Check both public calls on the same reader, token type and all 21 returned characters. Register the three controls above. Preserve Java’s 64-bit wraparound and the independent “fits in long” flag through the scan. A numeric conversion helper or an assertion about `peekNumber` alone misses the promised public behavior. Save the reader fixture and checked summaries for case 5. [Upstream regression](https://github.com/google/gson/blob/004e7a4949e08b430e3c8996998ee5a17ff9423a/gson/src/test/java/com/google/gson/stream/JsonReaderTest.java#L829) · [Production change](https://github.com/google/gson/pull/3034/files)

### 5. Gson #3137 · Is only the initial byte-order mark consumed?

Use a lenient `JsonReader` over a real `StringReader` and a reader that caps how many characters it returns per read. For input `U+FEFF U+FEFF f o o`, the parent returned `foo` with a cap of one or two, and preserved the second mark with a cap of 100. The fix returned `U+FEFF` followed by `foo` for all three caps. Zero or one initial mark gave `foo` on both versions under every cap.

**Target claim.** Cross 0, 1 and 2 leading marks with caps 1, 2 and 100. Keep the suffix fixed initially. Observe `nextString()` as code units and record the read lengths during replay. Reuse the public reader setup from #3034, preserving differences between the two historical Gson versions. The narrow new capability is tracking where the buffer begins in the original stream after compaction. A model that always fills the requested buffer erases the regression. [Upstream regression](https://github.com/google/gson/blob/845664ba1c307e6c1910d07cfed2f622e0ad8df1/gson/src/test/java/com/google/gson/stream/JsonReaderTest.java#L1687) · [Production change](https://github.com/google/gson/pull/3137/files)

### 6. Commons Codec #135 · Does the decoder preserve a half-byte between writes?

Use a real `Base16OutputStream(sink, false)` and one ASCII byte array containing `4142434445`. Write slices with offsets and lengths `(0,3), (3,4), (7,3)`, close, and inspect the sink bytes. The parent produced `ABCD` and the fix produced `ABCDE`. A single write and a 2+4+4 partition produced `ABCDE` on both. Upstream exercises package-level `Base16.decode` with a shared context. The public stream replay establishes that the same defect matters to a caller.

**Target claim.** For four hex characters from `{0,1,A,F}`, enumerate all eight ways to partition the four positions into contiguous nonempty writes. Compare the final two bytes to independent nibble arithmetic. Also keep the ten-character upstream case. Pass the original array with the actual offset on every write. Replacing slices with zero-offset copies weakens the case. Reuse the way case 5 represents a sequence of short transfers and state carried between calls. Record which parts actually transfer across libraries and which require new code. Example 109 already covers the separate question of which characters a hex decoder accepts. [Example 109](https://github.com/pilifs/in-the-loop/tree/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/109-commons-codec-43a9aa66-hex-decoding-restricted-to-ascii) · [Upstream fix and regression](https://github.com/apache/commons-codec/pull/135/files)

## Exact revisions and calibration evidence

Use the first parent of the landed commit for the old side. The links below pin both revisions. The distinguishing observations above were independently replayed on OpenJDK 21.0.13. The focused runs exercised the real Java entry points. The verification team still owns the upstream test runs, recorded builds and all formal verdicts.

| PR | First parent | Landed revision | JVM calibration performed for this brief |
|---|---|---|---|
| Guava #8509 | [117b5277](https://github.com/google/guava/commit/117b5277123e3a2cb1cad35ec8e47c852a3a8858) | [ee548013](https://github.com/google/guava/commit/ee548013ec9aa94394c9bca2761edaca3be5e1ed) | Built the 609 JRE production sources excluding the module descriptor on each revision. Replayed overflow and small counts through the public APIs. |
| Commons Lang #1719 | [2c2ed9d8](https://github.com/apache/commons-lang/commit/2c2ed9d80dac4b46e9426041c091ddcaadb4df2b) | [75d85a80](https://github.com/apache/commons-lang/commit/75d85a807d7b66da432a822de6fc75c48134decf) | Built the full main Java source tree for each revision. Observed both cut directions, an intact pair, ASCII, and abbreviation widths four and five. |
| Avro #3878 | [cc134b3f](https://github.com/apache/avro/commit/cc134b3ff6016d86a5f97798afc77ef1a47b7d73) | [f3bb10ea](https://github.com/apache/avro/commit/f3bb10eaea1f03eb17893bc779eb26213da8177c) | Compiled each original factory and converter interface over Avro 1.12.1 support and Hadoop 3.4.3. The real factory with `new JobConf(false)` produced remaining lengths 5/5/5 on the parent and 0/3/5 on the fix at logical lengths 0/3/5. Position stayed zero, capacity five. At logical index 3 the parent returned 4 and the fix threw. Repeat with the revisions’ declared build closures. |
| Gson #3034 | [ed239750](https://github.com/google/gson/commit/ed2397502708ebaba53643e5c3d60e0974d7045f) | [004e7a49](https://github.com/google/gson/commit/004e7a4949e08b430e3c8996998ee5a17ff9423a) | Built original production sources per revision with their generated version constant and annotation dependencies. Ran all ten final digits and three controls. |
| Gson #3137 | [216c41b6](https://github.com/google/gson/commit/216c41b6e70dc04e6856418dd76bb00c854eb6b4) | [845664ba](https://github.com/google/gson/commit/845664ba1c307e6c1910d07cfed2f622e0ad8df1) | Same build approach on this PR’s own parent and fix. Ran all nine combinations of leading marks and read caps. |
| Commons Codec #135 | [b22276db](https://github.com/apache/commons-codec/commit/b22276db7282efa0794e2cca02a32006c0bca0dd) | [7ccbc3d0](https://github.com/apache/commons-codec/commit/7ccbc3d0c39aaf49ff70f19d85f173f98550d0fb) | Built full production sources per revision. Replayed three partitions of the upstream input plus `1234` in 1+2+1 characters, which yielded one byte on the parent and two on the fix. |

The upstream test selectors below identify the historical regressions. Select the JRE module for Guava and the mapred module for Avro.

| PR | Test class and method |
|---|---|
| Guava #8509 | `MultisetsTest.testSumCountOverflow` and `testSumEntryIteratorOverflow` |
| Commons Lang #1719 | `StringUtilsTest.testTruncate_StringIntInt_surrogatePair` and `StringUtilsAbbreviateTest.testAbbreviateSurrogatePair` |
| Avro #3878 | `TestAvroDatumConverterFactory.convertBytesWritableRespectsLogicalLength` |
| Gson #3034 | `JsonReaderTest.testNumberLongAccumulatorOverflowsToZero` |
| Gson #3137 | `JsonReaderTest.testRepeatedBom` |
| Commons Codec #135 | `Base16Test.testOddEvenDecoding` |

## Execution and acceptance

1. **Baseline all six from the same verifier commit before reviewing repairs.** Allocate the next available example IDs. Check the current worktree and registered PR URLs for concurrent work. Build each exact upstream pair, pin the subject JDK, retain JAR hashes and ordered classpaths, and confirm the class containing the change came from the intended revision. Run the named upstream test or transplant its assertion unchanged onto the parent if it was introduced in the fix. Save a fresh test report with the selected method and execution count. Use the independent public-call replays above as a second check.
2. **Freeze the original claim before the checker learns anything new.** Give each observer its own task. Record entry point, receiver state, inputs, expected return or exception, post-state, bounds and a preservation control. Require one real parent witness, one fixed-side property and one behavior preserved on both sides. A parent witness should violate the same contract the fixed side establishes. Run a wrong-result control for each proposed summary, such as dropping a nibble, forgetting the buffer limit or returning a wrapped count. Check that the property would reject it.
3. **Improve the first operation where the checker loses a necessary fact.** Keep the first unsupported instruction or call, failing observation, or timeout. Show the original task before and after the improvement. Prefer an existing string, buffer, arithmetic, JDK or heap model when it already fits. Preserve the original library code on the executed path. A fixture may create receivers, supply input, and read public results. If a narrower entry, a constrained startup, or a smaller domain is necessary, give it a separate task and leave the original verdict visible.
4. **Run through the existing internal workflow.** Replace `NNN` and `TASK` with the assigned example and task. Use the project’s normal task plan to select the replay and queue heavy proofs. Capture the verifier commit, case setup time, solver time, peak memory and any per-PR handwritten adapter. [Project workflow](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/README.md#run-an-example) · [Verification queue](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/verification/README.md)

```sh
python3 examples/tools/build.py --plan NNN
python3 examples/tools/build.py NNN --task TASK
python3 verification/pipeline.py submit --example NNN --task TASK
python3 examples/tools/validate_example.py NNN --replay
python3 examples/tools/targets/workflow_handoff.py handoff NNN --markdown
```

**Campaign scorecard.** Give each of the six PRs a row with the baseline verdict, parent JVM witness, fixed-side scope, preserved control, strict native verdict, finite-JVM coverage, first remaining blocker, and reusable change. Mark sampled runs as samples. Report complete finite grids with their domain and cardinality. A strict native result needs a non-vacuous property over the stated domain and a replay for each reported refutation. An unexplained disagreement between a formal assurance and the JVM goes to the top of the engineering queue.

**Investment decision.** A worthwhile first milestone would be all six original cases reproducible, at least four with the parent witness and fixed-side original-scope property decided natively, and one verifier improvement used by a second PR with no change to its semantics. These are proposed targets. Use actual misses to choose the next capability. If every primary claim already closes at baseline, extend one meaningful dimension on the same public path, such as Guava’s second key or variable read schedules. Record the wider claim separately.

## Two reserves, selected by what the first six teach us

| Open this case when… | Organic PR and concrete witness | Bounded next step |
|---|---|---|
| Mutation and sequence post-state turn out to be the reusable gain | **[Eclipse Collections #1434](https://github.com/eclipse-collections/eclipse-collections/pull/1434/files)**. Insert `[false,true]` at index 0 into `BooleanArrayList[true,false,true]`. The parent throws `IndexOutOfBoundsException`. The fix returns true and the list becomes `[false,true,true,false,true]`. Indices 2 and 3 succeeded on both. Index 4 threw on both. Replayed each original `BooleanArrayList` over Eclipse Collections 11.1.0 implementation and API support. [Parent](https://github.com/eclipse-collections/eclipse-collections/commit/8a34cc65bd5449e4f45c9c39e75d7d92ec2717e6) · [Fix](https://github.com/eclipse-collections/eclipse-collections/commit/88982ba82c3195039ace015ef8ba88ddc979cfe4) | Keep original and inserted lengths at most four and three respectively. Check return/exception, size and exact prefix/inserted/suffix contents on the same receiver. Start within one `BitSet` word. The actual reverse-shift loop is the target. |
| Iterator work can carry a result across nested frames | **[JavaParser #4538](https://github.com/javaparser/javaparser/pull/4538/files)**. Calling `findAll(Node.class, POSTORDER)` on an empty `CompilationUnit` threw `EmptyStackException` on the parent. The fix returned a singleton containing the original root. With package `com`, both revisions returned `Name, PackageDeclaration, CompilationUnit` in postorder. Replayed each original `Node.java` and its nested classes over the same JavaParser 3.26.2 support JAR. [Parent](https://github.com/javaparser/javaparser/commit/e0eb16b8870fc05c03ab794e502dd76f97422e26) · [Fix](https://github.com/javaparser/javaparser/commit/6529f264066e31bd9e78c71111ade3a20142d285) | Construct both trees with public constructors. Check order, object identity and terminal `hasNext()` after traversal. Use preorder on both trees as a control. Verify the two tiny shapes before introducing parsed source or larger trees. |
