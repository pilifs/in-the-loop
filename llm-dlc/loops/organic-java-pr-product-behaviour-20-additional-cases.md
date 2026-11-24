## Twenty more organic Java PRs to exercise through the change plan

Use these disclosed cases after the primary freeze-and-transfer experiment. Each starts with something a caller can see, such as the address reopened from a spreadsheet, the spelling printed from a database or the value returned by a cache. The question for the run is whether `in-the-loop` can establish that observation at its public entry, explain the difference, and transfer the work to another project.

**Start with J02 (jsoup), then try J06 (Zip4j) with shared code frozen.** The former can hide a wrong tree behind correct text. The latter lets an independent JDK reader inspect what the product wrote. J08 (Parquet) and J15 (Spring Batch) then test how far the result survives a reset or restart. Interleave J17 (Eclipse Collections) as a preservation-only optimization. The remaining cases can follow whichever capability needs more evidence.

Generate the case-specific caller, fixtures and observations through the existing `single-agent-run` and application change plan. The PR and this brief are the only inputs the user supplies. Save the first result on the frozen implementation, then diagnose any blocker. All 20 are disclosed selections. Count actual public invocations, checks and reuse separately from evidence supplied below.

**How to read the evidence.** Each case links its upstream PR, first-parent-to-merge comparison and a pinned test or production file. A *pinned source build* used both upstream source trees for the named module or profile. A *pinned source overlay* ran the changed classes at both commits over a common dependency set. A *published release pair* exercised distributed artifacts that may contain other changes. Four cases use pinned source builds, fourteen use source overlays and two use release pairs. Each gives the campaign concrete JVM results to reproduce. Record the full original deployment, checker scope and proof receipts when qualifying them.

### Documents and interfaces

#### J01 · CommonMark Java — Keep inline code in an image’s accessible name

Render `` ![`foo` bar](cover.png) `` to HTML. Read the `img` element’s decoded `alt` and `src` attributes. The parent produced ` bar` and the fix produced `foo bar`. With `x & y` as the entire code span, the parent produced an empty name, whereas the fixed HTML contained `x &amp; y` and the decoded attribute read `x & y`.

Keep the image URL, a description made of plain text, emphasis and links, and the rendering of code outside an image as preservation controls. Then edit a `Code` node on the existing syntax tree and render again with the same renderer. A checked visitor summary must account for text collected under an image.

**Pinned source build.** Built both pinned commonmark core trees with their resources and exercised the public parser and renderer. [PR #401](https://github.com/commonmark/commonmark-java/pull/401) · [Compare 9926b761 → 4ad81e44](https://github.com/commonmark/commonmark-java/compare/9926b761eb2e9192d80cda46917ea2f0f0f2c7dc...4ad81e449ca474d3560a1699f9882e37090906f0) · [Upstream regression](https://github.com/commonmark/commonmark-java/blob/4ad81e449ca474d3560a1699f9882e37090906f0/commonmark/src/test/java/org/commonmark/test/HtmlRendererTest.java)

#### J02 · jsoup — Carry a custom tag’s HTML behavior into a cloned parser

Register `foo` as a void tag in an HTML parser, attach an `onNewTag` customizer, and clone the parser. Parse `<foo>one<span>two</span>after` using the clone. The document text was `onetwoafter` in both builds. On the parent, `span.parent()` was `foo` and `foo.text()` contained all the text. On the fix, `span.parent()` was `body` and `foo.text()` was empty.

Inspect an already registered tag, a tag first seen by the clone and a tag registered later on the original. Compare an ordinary built-in tag and test the customizer on a fresh tag name. A useful summary must explain which behavior the clone inherits and how that affects a later tree operation.

**Pinned source build.** Built both pinned production trees with their resources and exercised parser cloning and DOM lookup. [PR #2423](https://github.com/jhy/jsoup/pull/2423) · [Compare cc90f726 → bcbac427](https://github.com/jhy/jsoup/compare/cc90f726cd721ad2c19cbd27997482a5f9b8a7ae...bcbac427ff4bca1748f8eb5125a23d4c739b75e9) · [Upstream regression](https://github.com/jhy/jsoup/blob/bcbac427ff4bca1748f8eb5125a23d4c739b75e9/src/test/java/org/jsoup/parser/ParserTest.java)

#### J03 · JFreeChart — Pan two chart axes when only the first is inverted

Build a headless `XYPlot` with two domain axes, each initialized to `[0,10]`. Invert the first, enable panning and pan by `+0.1`. Its range became `[-1,9]` in both builds. The second axis also moved to `[-1,9]` on the parent, but moved to `[1,11]` on the fix. A user panning one chart sees the second scale move in the opposite direction.

Pan back. Both revisions restored both ranges to `[0,10]`, so retain the intermediate ranges. Compare each axis with an independently panned single-axis plot. Swap axis order, test the range-axis path and include a plot on which neither axis is inverted. Try to reuse the single-axis result without sharing the mutable pan percentage.

**Pinned source build.** Built the pinned non-JavaFX production profile with JCommon and packaged resources on both sides. The public headless plot exercised the changed loop. [PR #44](https://github.com/jfree/jfreechart/pull/44) · [Compare 4e196e9b → f68f7248](https://github.com/jfree/jfreechart/compare/4e196e9bf170ae8af9bc4760a2329b3d933acccc...f68f7248a4145828dfa36fc2f76924db3c543162) · [Changed implementation](https://github.com/jfree/jfreechart/blob/f68f7248a4145828dfa36fc2f76924db3c543162/src/main/java/org/jfree/chart/plot/XYPlot.java)

#### J04 · ical4j — Keep a biweekly invitation on the same dates across locales

Start a public `Recur<LocalDateTime>` at 09:00 on Tuesday, 5 August 1997, with `FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU`. Expand the occurrences in fresh processes under US, French and Egyptian Arabic locales. Keep the ordered dates and the input rule as the observation.

Under US and Egyptian Arabic defaults, the parent returned August 5, 17, 19, 31. The fix returned 5, 10, 19, 24. French already returned the latter. Explicit `WKST=MO` and `WKST=SU` each preserved their own distinct dates in every profile. Bind locale when proving the historical result. Test whether the fix’s default-week-start result transfers across profiles.

**Pinned source overlay.** Recompiled the exact changed `ByDayRule` at both commits over identical ical4j 4.4.0 dependencies. Replayed 18 rule/locale/revision combinations. [PR #960](https://github.com/ical4j/ical4j/pull/960) · [Compare 70955862 → 1342406a](https://github.com/ical4j/ical4j/compare/70955862e728ff5c7392f5d53ed5b27461de6202...1342406adcf9f0576a7e4fa60548eea73f58c5e5) · [Upstream regression](https://github.com/ical4j/ical4j/blob/1342406adcf9f0576a7e4fa60548eea73f58c5e5/src/test/groovy/net/fortuna/ical4j/model/RecurSpec.groovy) · [iCalendar recurrence rules](https://www.rfc-editor.org/rfc/rfc5545#section-3.3.10)

#### J05 · Apache POI — Move a loaded hyperlink and reopen the spreadsheet

Save an XLSX with an external link on A1, reopen it, remove that link and attach the same loaded hyperlink object to A2. Save and reopen again. With a plain URL, the parent threw `IllegalStateException` when reopening. With an external URL and `section` in the location field, it reopened but returned only `section` as A2’s address. The fix returned the full target on A2 in each case, including `https://example.com/page#section` in the latter.

Keep an untouched link as a control. Check A1’s absence, A2’s address and its owning sheet’s external relationship target. Compare resolved targets, since relationship IDs may be renumbered. Extend to cloning the sheet and a third save/reopen. Requalify the affected sheet and compare the untouched sheet’s warm result with clean readback.

**Pinned source overlay.** Ran all three changed POI classes at each revision over the same POI 6.0.0 support. Both no-move controls preserved their addresses. [PR #1584](https://github.com/apache/poi/pull/1584) · [Compare 72ad1d5e → c94ee8ad](https://github.com/apache/poi/compare/72ad1d5e111c2cd00c4842a0431eb1d9ca4b605c...c94ee8ad9096bdb8cf8e5e59d8d12432e950dbf3) · [Upstream regression](https://github.com/apache/poi/blob/c94ee8ad9096bdb8cf8e5e59d8d12432e950dbf3/poi-ooxml/src/test/java/org/apache/poi/xssf/usermodel/TestXSSFHyperlink.java)

### Archives, storage and serialization

#### J06 · Zip4j — Rename one ZIP entry without renaming a neighbor

Create a ZIP containing `cat`, `catalog`, and `other`, each with distinct bytes. Call `ZipFile.renameFile("cat","dog")`, close the archive, then enumerate and read it through the JDK ZIP reader. Compare names and payloads together.

The parent wrote `dog`, `dogalog`, `other`. The fix wrote `dog`, `catalog`, `other` with the payloads intact. As a control, rename directory `cat/` to `dog/` and check that `cat/a` moves while `catalog` stays put. Exercise exact matching for files and prefix matching at a directory boundary. Retain names as part of the persisted observation.

**Pinned source build.** Compiled the full Zip4j production source at each pinned revision and inspected the output with an independent JDK reader. [PR #541](https://github.com/srikanth-lingala/zip4j/pull/541) · [Compare f2e4a5a4 → 6d1678bd](https://github.com/srikanth-lingala/zip4j/compare/f2e4a5a4f762dab1593f97f34c2b45d599a286cf...6d1678bdf03e6eafadebef9a860e74488485fe65) · [Changed implementation](https://github.com/srikanth-lingala/zip4j/blob/6d1678bdf03e6eafadebef9a860e74488485fe65/src/main/java/net/lingala/zip4j/tasks/RenameFilesTask.java)

#### J07 · Apache Commons Compress — Agree on whether a TAR entry is a file or a directory

Enumerate the upstream `orjson-3.7.8.tar` distribution with public `TarFile`. Both revisions read 481 entries and recognized one directory. The parent also classified all 481 entries as files. The fix classified 480 as files, with zero directory/file overlap. The differing entry has a directory type flag and a name without a trailing slash.

Compare the name, header flag and both predicates for each entry. Cross-check against the archive header, include a directory whose name ends in `/`, and read the payloads twice. The preflight preserved 1,438,851 payload bytes. A list of entry names alone misses what an archive browser would present or extract as a file.

**Pinned source overlay.** Ran the exact changed TarArchiveEntry class on both sides over Commons Compress 1.26.0, with the upstream distribution archive. [PR #460](https://github.com/apache/commons-compress/pull/460) · [Compare 3d9a01ec → 45023ddc](https://github.com/apache/commons-compress/compare/3d9a01ec07aa18b5ff341766378e2ea62639d4f5...45023ddcc43e13804dff799ae96f2acce14ce3cd) · [Upstream regression](https://github.com/apache/commons-compress/blob/45023ddcc43e13804dff799ae96f2acce14ce3cd/src/test/java/org/apache/commons/compress/archivers/tar/TarFileTest.java)

#### J08 · Apache Parquet — Read a dictionary-encoded row group after the previous group fell back

Write 1,000 distinct strings to force dictionary-to-plain fallback. Reset the writer for a second row group and write `c0` through `c9` repeatedly for 1,000 values. Decode the second group independently. In the writer-level replay, the parent used `PLAIN` and matched 0 of 1,000 expected values. The fix used `PLAIN_DICTIONARY` and matched all 1,000.

A fresh writer round-tripped the second sequence on both revisions. Use that sequence as an oracle, vary the first group across the fallback threshold, and carry the claim through the public file writer, close and reopen. Record the decoded values, encodings and dictionary used for group two. Keep page reset and row-group reset distinct.

**Pinned source overlay.** Ran both changed Parquet writer classes over identical 1.18.2 support. The measured result is at the encoded-page boundary. Whole-file readback is the next claim. [PR #3638](https://github.com/apache/parquet-java/pull/3638) · [Compare 5c360ff5 → 5e14d7cd](https://github.com/apache/parquet-java/compare/5c360ff5d879d3567f23cea3290894712fb336d9...5e14d7cd43403a95d331be8791e8792dbf38683d) · [Upstream regression](https://github.com/apache/parquet-java/blob/5e14d7cd43403a95d331be8791e8792dbf38683d/parquet-column/src/test/java/org/apache/parquet/column/values/dictionary/TestDictionary.java)

#### J09 · SQLite JDBC — Distinguish SQL NULL from a zero-length BLOB

Step one JDBC `ResultSet` through SQL NULL, `zeroblob(0)` and `zeroblob(5)`. Immediately after each `getBytes(1)`, record both the returned value and `wasNull()`. A consumer should be able to distinguish missing data, a present empty payload and five zero bytes.

Published drivers 3.8.11.2 and 3.14.2 returned `null/true, null/false, 5 bytes/false` and `null/true, 0 bytes/false, 5 bytes/false` respectively. Bind the native driver selected on the test platform. The PR changes JNI C code and bundled Mac binaries. A Java-only replay cannot qualify Linux behavior at the exact PR commits. Rebuild both native sides for that claim.

**Published release pair.** Original Linux x86-64 drivers on JDK 21.0.13. The PR pins identify the native diff and regression tests. [PR #126](https://github.com/xerial/sqlite-jdbc/pull/126) · [Compare d36de443 → 44848544](https://github.com/xerial/sqlite-jdbc/compare/d36de443c9004ac1eb34f00ceb51c46eeaeafb0e...44848544c11e3705ee6b208d844a067ffb535012) · [Upstream regression](https://github.com/xerial/sqlite-jdbc/blob/44848544c11e3705ee6b208d844a067ffb535012/src/test/java/org/sqlite/QueryTest.java)

#### J10 · Kryo — Round-trip the abstract Enum class token in a stream of class tokens

Write `void.class`, `ArrayList.class`, a concrete enum class, `Enum.class` and `String.class` to the same Kryo output. Read the tokens sequentially as `Class.class` and record identity and the final input position. Distinguish an abstract class token from an enum instance or a constant-specific subclass.

The parent threw `IllegalArgumentException` while writing `Enum.class`. The fix read all five identities and ended at byte 64 in the fixture. Omitting `Enum.class` preserved the other four identities and the reader consumed all 46 bytes on both sides. Use consumed length relative to the actual stream end as the property. Bind resolver/registration configuration when reusing dispatch evidence.

**Pinned source overlay.** Both changed production files at each commit over common Kryo 4.0.2 support. [PR #530](https://github.com/EsotericSoftware/kryo/pull/530) · [Compare 7a433cf0 → 73540094](https://github.com/EsotericSoftware/kryo/compare/7a433cf0036101c6693cca6b4410454e211dbd6c...73540094596bef8874a48726edd0fdd014e84e45) · [Upstream regression](https://github.com/EsotericSoftware/kryo/blob/73540094596bef8874a48726edd0fdd014e84e45/test/com/esotericsoftware/kryo/DefaultSerializersTest.java)

### Queries, resolution and recovery

#### J11 · H2 — Keep original text spellings when a SQL sort spills to disk

A reporting query sorts case-insensitively but still has to print what was entered. Insert `abc`, `ABC`, `Abc`, `abc`, and `z` into `VARCHAR_IGNORECASE`. Force an external sort with `MAX_MEMORY_ROWS=1`, materialize the sorted query with `CREATE TABLE AS SELECT`, close the database, and reopen it. Compare the **multiset of original spellings** so ties can appear in any order.

The parent returned four lowercase `abc` values and `z`. The fix retained the original spellings. With a high memory threshold both revisions preserved the spellings, and `DISTINCT` still gave two values. Check whether the persisted result depends on the external-sort representation and collation. A row-count or SQL-equality check alone passes the defect.

**Pinned source overlay.** Recompiled the changed H2 production class at both pins over H2 2.5.252 and exercised it via JDBC and a reopened database. [PR #4575](https://github.com/h2database/h2database/pull/4575) · [Compare df37ff03 → 2b7812b2](https://github.com/h2database/h2database/compare/df37ff0363c0b84758017c8788e313d34646d403...2b7812b20a421be7116cc75b5abf95a5718f7119) · [Upstream regression](https://github.com/h2database/h2database/blob/2b7812b20a421be7116cc75b5abf95a5718f7119/h2/src/test/org/h2/test/db/TestBigResult.java)

#### J12 · Apache Calcite — Run an ordered and an unordered aggregate in one query

Through JDBC, group the input rows `(10,1),(20,7),(10,3),(10,3),(10,2)` by the first column. In one statement request both `COLLECT(n)` and `COLLECT(n) WITHIN GROUP (ORDER BY n DESC)`. In Calcite 1.18.0 the unordered bags were empty for both groups. In 1.19.0 department 10 contained `1,2,3,3` as a multiset and department 20 contained `7`.

The ordered results were `[3,3,2,1]` and `[7]` on both releases. Each aggregate also worked when requested alone. Keep those single-aggregate queries as controls and permute the input. Compare multiplicity for the unordered column and sequence for the ordered column. Bind the generated accumulator for each result and rerun the exact PR pair.

**Published release pair.** Exercised published Calcite 1.18.0 and 1.19.0 through JDBC. The PR includes a pinned mixed-aggregate SQL regression. [PR #1003](https://github.com/apache/calcite/pull/1003) · [Compare f2638b9f → f992e6c8](https://github.com/apache/calcite/compare/f2638b9f7dc878f3f109cbc59d1a6ae02d3d5696...f992e6c8fbc3712c6bd70096fb6b05da448b2cab) · [Upstream regression](https://github.com/apache/calcite/blob/f992e6c8fbc3712c6bd70096fb6b05da448b2cab/core/src/test/resources/sql/agg.iq)

#### J13 · Apache Maven — Resolve a dependency range regardless of repository order

Create Maven’s public `VersionRange` for `[0-alpha,x]`. Present `0-alpha`, `0` and `x` to `matchVersion` in all six orders. The parent threw `InvalidVersionSpecificationException` while constructing the range, before any version could be selected. The fix constructed it and selected `x` in all six orders.

Use `1-alpha < 1-beta` as an unaffected ordering. To explain the failure, run a highest-version fold over the same three candidates with public `ComparableVersion`. On the parent, a comparison cycle gave three different winners, each twice. The fix chose `x` every time. Bind the checked comparison rules to actual range construction and selection before attributing a product verdict to the helper.

**Pinned source overlay.** Ran the pinned Maven comparator, artifact-version, range and artifact sources on both sides with common Maven 3.9.12 support. [PR #13102](https://github.com/apache/maven/pull/13102) · [Compare c7b164f7 → 9da38851](https://github.com/apache/maven/compare/c7b164f76189be25a2c6a48ffe74ff3afc39fcc2...9da38851f517281d66b1b05d25b8785dcc9e7fc9) · [Upstream regression](https://github.com/apache/maven/blob/9da38851f517281d66b1b05d25b8785dcc9e7fc9/compat/maven-artifact/src/test/java/org/apache/maven/artifact/versioning/VersionRangeTest.java)

#### J14 · Apache Lucene — Sort parent search hits when only some children have values

Write two parent/child blocks to an index and reopen it. A’s children have a string sort value of `30` and a missing value. B’s have `20` and `40`. Search with the same public five-argument `ToParentBlockJoinSortField` constructor on both revisions. In ascending order the parent produced `[B:"20", A:"30"]` and the fix `[A:null, B:"20"]`.

Descending order preserved `[B:"40", A:"30"]` and the total hit count stayed two. Keep an all-present block as another control, then vary the child filter. On the fix alone, use the new numeric overload to compare child-missing replacements 5 and 50. Record parent IDs and their returned sort keys separately. Keep parent-level missing values distinct from child-level substitution.

**Pinned source overlay.** Ran the three changed Lucene join classes over a common 10.4.0 distribution, with an index and reader reopened through the public API. [PR #15727](https://github.com/apache/lucene/pull/15727) · [Compare 182ee9c4 → 167503f6](https://github.com/apache/lucene/compare/182ee9c4cc3bc52ace12e699248b750377a3aa2f...167503f6d84d8e43db4ec6ae3baf17337290393f) · [Upstream regression](https://github.com/apache/lucene/blob/167503f6d84d8e43db4ec6ae3baf17337290393f/lucene/join/src/test/org/apache/lucene/search/join/TestBlockJoinSorting.java)

#### J15 · Spring Batch — Recover the latest checkpoint when two executions have the same start time

Create two executions of the same step name and job instance with the same start timestamp, different IDs and different saved-context markers. Query public `SimpleJobRepository.getLastStepExecution` in both DAO enumeration orders. Record the selected execution ID **and its restored marker**.

With IDs 1 and 2, the parent selected 2 or 1 depending on order. The fix selected 2 both ways. Give ID 1 a later timestamp and it must win on both revisions. An unknown step name must still return null. Next persist the metadata, reopen through the JDBC repository, and verify which offset a restarted reader actually resumes from.

**Pinned source overlay.** Exact repository class over Spring Batch 3.0.7 with controlled DAO enumeration. A full JDBC-backed restart remains an execution case. [PR #495](https://github.com/spring-projects/spring-batch/pull/495) · [Compare 1b35bff3 → 0506d379](https://github.com/spring-projects/spring-batch/compare/1b35bff3ec0a681827e507562572f14550a6717f...0506d3793e50a606cd9739ce896de5d80b474e8e) · [Changed implementation](https://github.com/spring-projects/spring-batch/blob/0506d3793e50a606cd9739ce896de5d80b474e8e/spring-batch-core/src/main/java/org/springframework/batch/core/repository/support/SimpleJobRepository.java)

### Shared state, callbacks and telemetry

#### J16 · JGraphT — See a rejected graph-view update in both the view and the backing graph

Give an edge backing weight 2 and a computed view weight 7. Construct an `AsWeightedGraph` with computed weights, caching disabled and write-through enabled. Call `setEdgeWeight(e,9)`. Observe termination, then read the weight through **both** handles.

With assertions off, the parent returned normally and the view still reported 7, although the backing graph had changed to 9. The fix throws `UnsupportedOperationException` and leaves the backing weight at 2. With assertions enabled the parent instead threw `AssertionError`. With caching and write-through enabled, both revisions returned and both handles reported 9. Carry alias, configuration and assertion settings through warm and clean checks.

**Pinned source overlay.** Exact changed AsWeightedGraph source over common JGraphT 1.5.1 support in both assertion profiles. [PR #941](https://github.com/jgrapht/jgrapht/pull/941) · [Compare c01e0290 → 637503d4](https://github.com/jgrapht/jgrapht/compare/c01e02903d45c82a9ecaf5c4329cdf847eb9e183...637503d4ebfbce3bb1ffca97348a90e856f4346e) · [Changed implementation](https://github.com/jgrapht/jgrapht/blob/637503d4ebfbce3bb1ffca97348a90e856f4346e/jgrapht-core/src/main/java/org/jgrapht/graph/AsWeightedGraph.java)

#### J17 · Eclipse Collections — Qualify a collision-heavy map optimization by its preserved behavior

Insert distinct equal-hash keys into a `UnifiedMap`, retain a view of the original map, then run `removeIf` twice with the same predicate. Include an untouched null-key entry. Compare remaining keys, values, size and the returned changed flag with an independent map. Ignore visitation order where the API permits it.

This is a preservation case. The optimized loop moves the final collision-chain item into the newly vacant slot. A predicate that removes both the vacated entry and its replacement catches skipped rechecks. Across all 127 removal subsets for sizes zero through six, both revisions matched the reference and the second call reported false.

**Pinned source overlay.** Exact changed UnifiedMap source over Eclipse Collections 10.2.0 support. Report preservation separately from detected regressions. [PR #786](https://github.com/eclipse-collections/eclipse-collections/pull/786) · [Compare 9084111e → 7ce7a197](https://github.com/eclipse-collections/eclipse-collections/compare/9084111e068612ebf817a3fa6fe80d9623df4c29...7ce7a19722e5471a71a2799737c3c2a0ed5510ff) · [Upstream regression](https://github.com/eclipse-collections/eclipse-collections/blob/7ce7a19722e5471a71a2799737c3c2a0ed5510ff/unit-tests-java8/src/test/java/org/eclipse/collections/test/map/mutable/MutableMapIterableTestCase.java)

#### J18 · Caffeine — Honor immediate expiry when the cache also has a size limit

Build a JCache-backed Caffeine cache with maximum size and an expiry policy that returns zero on creation. Put `(1,10)`, put `(1,20)`, then read key 1 twice. With both settings enabled the parent returned `[20,20]` and never invoked expiry. The fix returned `[null,null]` and invoked creation expiry twice because each entry had already expired.

With expiry alone, both revisions returned `[null,null]`. With size alone, both returned `[20,20]`. A positive-duration policy gives a second discriminator. Both builds returned 20, but only the fix emitted create, update, read, read callbacks in the combined configuration. Use a direct executor. Test size independently by inserting extra keys and triggering maintenance without predicting the victim.

**Pinned source overlay.** Ran the changed CacheFactory over common Caffeine/JCache 2.6.1 and JCache API 1.0.0. Immediate expiry needs no clock advance. [PR #194](https://github.com/ben-manes/caffeine/pull/194) · [Compare 5473cab8 → 78be027a](https://github.com/ben-manes/caffeine/compare/5473cab8afb17ec7aa288b57d74d81de6372351e...78be027a7e89e750e3a1cc27584d7a8224d164bf) · [Upstream regression](https://github.com/ben-manes/caffeine/blob/78be027a7e89e750e3a1cc27584d7a8224d164bf/jcache/src/test/java/com/github/benmanes/caffeine/jcache/expiry/JCacheExpiryAndMaximumSizeTest.java)

#### J19 · Resilience4j — Repeat a circuit-breaker command without creating another transition

Register a public state-transition listener. On one breaker request OPEN twice, HALF_OPEN twice, then CLOSED twice. The parent threw `IllegalStateTransitionException` on each repeat. The fix accepted all three repeats. Both emitted exactly three genuine transitions and had cumulative event counts `1,1,2,2,3,3`.

Use a fresh CLOSED breaker to exercise a genuinely invalid CLOSED → HALF_OPEN request. Both rejected it. Freeze the listener registration and compare state, return or exception, event sequence and count after *each* request. A final-state check misses the change. A reusable helper for transition legality must also account for the no-op case and its event effects.

**Pinned source overlay.** Ran both changed classes at each pin over Resilience4j 1.3.1 support and exercised the public state machine. [PR #892](https://github.com/resilience4j/resilience4j/pull/892) · [Compare 4e564aff → 4ecc7c88](https://github.com/resilience4j/resilience4j/compare/4e564affebf280ba20880bdc8736b42f8f92234a...4ecc7c889cad7bfa6cb574af52252480f7e0d7cf) · [Upstream regression](https://github.com/resilience4j/resilience4j/blob/4ecc7c889cad7bfa6cb574af52252480f7e0d7cf/resilience4j-circuitbreaker/src/test/java/io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachineTest.java)

#### J20 · Micrometer — Expose configured timer percentiles across reporting steps

Use a local SignalFx registry in DELTA mode with a controlled clock, histogram or SLO buckets, and percentiles 0.95 and 0.99. Record `5,20,175,2000` milliseconds. After each of two identical reporting intervals, the timer probe returned count 4, total 2.2 seconds and bucket deltas `[0,1,2,3,4]` on both revisions. The parent snapshot exposed zero percentile entries and the fix exposed two.

Carry the claim to the registry’s emitted datapoints and read the gauge labels and values there. In cumulative mode both snapshots had two percentile entries and the bucket counts accumulated to `[0,2,4,6,8]` in interval two. Add an unconfigured-percentile control. Vary the second interval’s samples and bind the delta calculation to the previous snapshot before reusing its result.

**Pinned source overlay.** Ran the exact changed timer over common Micrometer 1.10.0 support, with package-private construction and public recording and snapshot operations. The upstream test exercises registry construction and publication. [PR #3369](https://github.com/micrometer-metrics/micrometer/pull/3369) · [Compare 41c9493e → f18f09fa](https://github.com/micrometer-metrics/micrometer/compare/41c9493e7f6781f4588906ed36cca87385a5a76c...f18f09fa8d782a39081856f9667827ae00af638a) · [Upstream regression](https://github.com/micrometer-metrics/micrometer/blob/f18f09fa8d782a39081856f9667827ae00af638a/implementations/micrometer-registry-signalfx/src/test/java/io/micrometer/signalfx/SignalFxMeterRegistryTest.java)

### What to retain from each run

| Record | What to capture |
|---|---|
| Public claim | PR and exact built pair, public entry, construction and call sequence, input domain, environment, expected change and preservation control. Identify the observation that a shallower test would miss. |
| Product outcome | Before and after values, intermediate state, exception and any subsequent observable effects. For persisted outputs, identify which reader reopened them. Keep a finite witness, a bounded proof and an unresolved claim distinguishable. |
| Work required | Which artifacts the run generated, any human intervention, and the split between case-specific setup and shared implementation changes. Preserve the first frozen result even when a later repair succeeds. |
| Evidence consumed | Identify the startup facts and checked helper the public claim actually used, if any. On a warm rerun, record what was reused. Perturb a relevant dependency and compare the resulting verdict and scope with a clean run. |

At review, report how many of the 20 reached their public observer, how many yielded a reproduced difference or qualified preservation result, and how many remained open. Separate first frozen runs from assisted reruns. For each recurring blocker, name the cases it affected and the smallest experiment that could distinguish a reusable capability gap from project-specific setup.
