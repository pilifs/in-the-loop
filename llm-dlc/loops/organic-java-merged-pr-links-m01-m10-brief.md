# Merged Java pull requests M01–M10 — observable behavior across revisions

## Objective

Compare each landed change with the revision immediately preceding it. Follow a concrete caller through the changed behavior, preserve a neighboring case, and test a prediction that the upstream example leaves open. Each claim names an observation that could overturn it.

## RoaringBitmap/RoaringBitmap#863 — Containment across a missing block and the unsigned upper bound

**Change and revisions.** [Merged PR #863](https://github.com/RoaringBitmap/RoaringBitmap/pull/863). The heap and buffer implementations now distinguish a missing final block from a later block at the same insertion point. They also retain the exclusive endpoint 2³² without wrapping its block number to zero. [Landed comparison](https://github.com/RoaringBitmap/RoaringBitmap/compare/ffa685e6dbfb002c484f2bb5e0f3c5d6f5120088...baea79f84f78a8b697b10af5e3e0de034d6c66e8) from `ffa685e6dbfb002c484f2bb5e0f3c5d6f5120088` to `baea79f84f78a8b697b10af5e3e0de034d6c66e8`.

**Public scenario.** Let B = 65,536 and let U be the long value `1L << 32`. Construct `RoaringBitmap.bitmapOfRange(0L, B)`, query `contains(0L, B+1L)`, then add the single integer 3*B and repeat. Also query an independently constructed top block [U−B,U). Repeat with MutableRoaringBitmap and with an ImmutableRoaringBitmap created from its serialized, flipped ByteBuffer. Use long endpoints throughout.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| RoaringBitmap/RoaringBitmap#863.1 · Intent | The low block before and after adding 3*B. Query [0,B+1). Also query [U−B,U) on the top block. | Parent true → merge false for the low block in both histories. Parent false → merge true for the top block. | Integer B is absent in both low sets. The top set contains all B requested values. Issue #862 and the PR describe both boundary errors. | A merged reader accepts the missing B or rejects the full top block, or the parent does not show the predicted contrast. |
| RoaringBitmap/RoaringBitmap#863.2 · Control | On the low fixture query [0,B), before and after adding 3*B. | True on both revisions for heap, mutable and serialized readers. | The range excludes B. Adding an outside value cannot remove any of the original B members. | Any reader returns false in either history. |
| RoaringBitmap/RoaringBitmap#863.3 · Challenge | On the merge hold [U−2,U) fixed. Start with just −2 and −1 as int members. Serialize to a fresh buffer, add 0 to the mutable bitmap, then remove −2 and serialize again. Retain the first immutable reader. | First snapshot true throughout. Live answers true, true, false. The second snapshot returns false. Its rangeCardinality is 1, versus 2 in the first. | Unsigned −2 and −1 are exactly the two queried integers. Zero is outside the range. A snapshot over separate serialized bytes cannot track later mutations. | The old snapshot changes, the query depends on zero, or a reader reports full coverage after one of the two members was removed. |

**Evidence and limits.** The PR reports all six new tests failed before and passed after. The grid in the tests compares containment with range cardinality. The snapshot history adds an independent two-member oracle and a persistence boundary. A point lookup at the first member alone misses both endpoint errors.

**Technical notes.** The Gradle roaringbitmap module supplies the heap and buffer variants. Allocate serializedSizeInBytes() and flip the buffer after serialize(ByteBuffer). Keep the two serialized byte buffers separate.

**Sources.** [Issue #862](https://github.com/RoaringBitmap/RoaringBitmap/issues/862) · [Heap range contract](https://github.com/RoaringBitmap/RoaringBitmap/blob/baea79f84f78a8b697b10af5e3e0de034d6c66e8/roaringbitmap/src/main/java/org/roaringbitmap/RoaringBitmap.java) · [Immutable buffer reader](https://github.com/RoaringBitmap/RoaringBitmap/blob/baea79f84f78a8b697b10af5e3e0de034d6c66e8/roaringbitmap/src/main/java/org/roaringbitmap/buffer/ImmutableRoaringBitmap.java) · [Heap regressions](https://github.com/RoaringBitmap/RoaringBitmap/blob/baea79f84f78a8b697b10af5e3e0de034d6c66e8/roaringbitmap/src/test/java/org/roaringbitmap/TestRoaringBitmap.java) · [Mapped regression](https://github.com/RoaringBitmap/RoaringBitmap/blob/baea79f84f78a8b697b10af5e3e0de034d6c66e8/roaringbitmap/src/test/java/org/roaringbitmap/buffer/TestImmutableRoaringBitmap.java) · [Module build](https://github.com/RoaringBitmap/RoaringBitmap/blob/baea79f84f78a8b697b10af5e3e0de034d6c66e8/roaringbitmap/build.gradle.kts)

## FasterXML/jackson-databind#5913 — Route an alias into a flattened object and write back its canonical name

**Change and revisions.** [Merged PR #5913](https://github.com/FasterXML/jackson-databind/pull/5913). The outer bean deserializer now accepts the aliases declared by properties of an unwrapped child. The target commit squashes the submitted fix and test. [Landed comparison](https://github.com/FasterXML/jackson-databind/compare/e14262e2b96abd0a5db9dcb8d2bc18550488b105...9a7d8eb3e6ae7adba3470ed15a4f1b2361558640) from `e14262e2b96abd0a5db9dcb8d2bc18550488b105` to `9a7d8eb3e6ae7adba3470ed15a4f1b2361558640`.

**Public scenario.** Build the mapper with `JsonMapper.builder().build()`. Define `record Inner(@JsonAlias("a") String c)` and `record Outer(@JsonUnwrapped Inner inner, String b)`. Read `{"a":"Hello","b":"World!"}` as `Outer`. Inspect `inner().c()` and `b()`. Use public records with visible accessors for the serialization check.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| FasterXML/jackson-databind#5913.1 · Intent | Read the alias input with readValue(json, Outer.class). | Parent is expected to miss the nested value or reject the input. Merge yields ("Hello","World!") in the child and sibling respectively. | The alias designates c and @JsonUnwrapped places its input at the outer level. Issue #5911 reports the corresponding record assertion failing on 3.1.1 and 3.1.2. | The merge throws or either binding is wrong. A correct pair on the pinned parent refutes the predicted revision contrast. |
| FasterXML/jackson-databind#5913.2 · Control | Replace the key a with c, keeping both values and the same types. | Both revisions yield the identical two strings. | The primary name is the declared component name. Its routing does not require any aliases. The upstream POJO control checks this route. | Either reader loses the child or sibling, or changes a value. |
| FasterXML/jackson-databind#5913.3 · Challenge | On the merge read the alias form, call writeValueAsString on the resulting Outer, parse the emitted string with `readTree`, and read the emitted text again as Outer. | The tree has exactly {"c":"Hello","b":"World!"} in any field order. The second Outer equals the first. | An input alias gives an alternate spelling for a property. Unwrapping exposes its primary name on output. Reading the canonical representation separately checks the persistence boundary. | A nested inner object or alias a leaks into the output, a value changes, or the second read differs. |

**Evidence and limits.** Issue #5911 compares released versions and reports success on 3.0.4. The landed tests inspect records, ordinary beans, a creator parameter, and a second alias. The exact failure mode on the pinned parent and the write/read round trip are open. Simply accepting the input JSON would miss an unpopulated child.

**Technical notes.** The Maven POM declares Java 17 source and target. The mapper is tools.jackson.databind.json.JsonMapper. The annotations retain their com.fasterxml.jackson.annotation package. Use the same default mapper for all three reads.

**Sources.** [Issue #5911](https://github.com/FasterXML/jackson-databind/issues/5911) · [Outer name collection](https://github.com/FasterXML/jackson-databind/blob/9a7d8eb3e6ae7adba3470ed15a4f1b2361558640/src/main/java/tools/jackson/databind/deser/bean/BeanDeserializerBase.java) · [Alias definitions](https://github.com/FasterXML/jackson-databind/blob/9a7d8eb3e6ae7adba3470ed15a4f1b2361558640/src/main/java/tools/jackson/databind/deser/bean/BeanPropertyMap.java) · [Record and bean tests](https://github.com/FasterXML/jackson-databind/blob/9a7d8eb3e6ae7adba3470ed15a4f1b2361558640/src/test/java/tools/jackson/databind/struct/UnwrappedWithAlias5911Test.java) · [Build and annotations](https://github.com/FasterXML/jackson-databind/blob/9a7d8eb3e6ae7adba3470ed15a4f1b2361558640/pom.xml)

## vavr-io/vavr#3272 — Keep a matched null distinct from an empty search

**Change and revisions.** [Merged PR #3272](https://github.com/vavr-io/vavr/pull/3272). Iterator.findLast now records whether any element satisfied the predicate, independently of the value it keeps. [Landed comparison](https://github.com/vavr-io/vavr/compare/c6f0be585529bf16a4597b35f966439cffde894b...8bd9c6b92ac07259f82ce30a09d037dfc5c78d81) from `c6f0be585529bf16a4597b35f966439cffde894b` to `8bd9c6b92ac07259f82ce30a09d037dfc5c78d81`.

**Public scenario.** Use a fresh `io.vavr.collection.Iterator<Integer>` for each search. Call `findLast`, observe `Option.isDefined()`, then call `getOrElse` with a `Supplier<Integer>` that increments a counter and returns 99. A defined null and an empty option yield different observable pairs.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| vavr-io/vavr#3272.1 · Intent | `Iterator.<Integer>of(null,1,null)`, with `x -> x == null`. | Parent None, yielding 99 with one supplier call. Merge Some(null), yielding null with zero calls. | Indices 0 and 2 match. The last one exists and stores null. The pinned Option documentation explicitly permits Some(null). | The merge reports empty or invokes the fallback. A defined null on the parent refutes the predicted change. |
| vavr-io/vavr#3272.2 · Control | Use [1,2,3] twice, first selecting values >5, then selecting odd values. | Both revisions yield None (fallback 99, one call) and Some(3) (value 3, zero calls), respectively. | The qualifying positions are empty in the first search and 0,2 in the second. | An absent match looks defined, the second search returns 1, or the supplier is invoked for 3. |
| vavr-io/vavr#3272.3 · Challenge | On the merge select null or 7. Compare [7,null,4] with [null,7,4]. Append a further rejected 4 to each and search again. | With 7 before null, the result is a defined null for either suffix length. With null before 7, it is a defined 7. All four suppress the fallback. | The final accepted position moves between values while the rejected suffix cannot affect it. The supplier makes presence observable even when the stored value is null. | The rejected suffix clears the result, reordering leaves the selected value unchanged, or a successful search invokes the fallback. |

**Evidence and limits.** The three added tests compare Option values for two null matches and one empty search. The parent returns Option.of(last), which collapses a null payload into None. The mixed-match, reordered histories and callback observations are source-based predictions. Unwrapping with a null default would conceal the defect.

**Technical notes.** Use the vavr Maven module, Vavr Option and its Iterator. Materialize the same inputs afresh for each call because the iterator is consumed.

**Sources.** [Iterator search](https://github.com/vavr-io/vavr/blob/8bd9c6b92ac07259f82ce30a09d037dfc5c78d81/vavr/src/main/java/io/vavr/collection/Iterator.java) · [Parent return path](https://github.com/vavr-io/vavr/blob/c6f0be585529bf16a4597b35f966439cffde894b/vavr/src/main/java/io/vavr/collection/Iterator.java) · [Option factory and fallback](https://github.com/vavr-io/vavr/blob/8bd9c6b92ac07259f82ce30a09d037dfc5c78d81/vavr/src/main/java/io/vavr/control/Option.java) · [Regression](https://github.com/vavr-io/vavr/blob/8bd9c6b92ac07259f82ce30a09d037dfc5c78d81/vavr/src/test/java/io/vavr/collection/IteratorTest.java) · [Module POM](https://github.com/vavr-io/vavr/blob/8bd9c6b92ac07259f82ce30a09d037dfc5c78d81/vavr/pom.xml)

## apache/commons-compress#334 — Read a prefixed ZIP and recover the bytes before its first entry

**Change and revisions.** [Merged PR #334](https://github.com/apache/commons-compress/pull/334). For ordinary single-disk ZIP32 archives, the reader compensates for bytes prepended after the ZIP was written. It also exposes the first local header’s offset and a bounded stream over the preceding bytes. [Landed comparison](https://github.com/apache/commons-compress/compare/755fad2347c4b9ea4b56c61209d8f1f387cd5a67...0bacf83eb0b3367cd5572ab27e42a444efbcd5f8) from `755fad2347c4b9ea4b56c61209d8f1f387cd5a67` to `0bacf83eb0b3367cd5572ab27e42a444efbcd5f8`.

**Public scenario.** Open the landed COMPRESS-621.zip fixture with Commons Compress’s public `new ZipFile(file)`. Enumerate `getEntries()`, locate `COMPRESS-621.txt` with `getEntry`, then read its size and `getInputStream(entry)` to EOF. On the merge, also call `getFirstLocalFileHeaderOffset()` and drain `getContentBeforeFirstLocalFileHeader()` while the archive is open. The expected prefix is the 15 ASCII bytes of `Before Zip file`. The entry body is the UTF-8 URL `https://issues.apache.org/jira/browse/COMPRESS-621` with no newline.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-compress#334.1 · Intent | Read the prefixed fixture through the common entry APIs, then through the new accessors on the merge. | The parent is expected to enumerate zero entries, consistent with the issue report. The merge should find the named entry, return its exact bytes and byte length, report offset 15, and return exactly the 15 prefix bytes. | The landed regression gives the prefix, name and body independently of any directory-offset calculation. The issue reports the JDK reader found entries in its prefixed example. | The merge opens the file but loses the entry, returns different body bytes, or reads any local-header byte as part of the prefix. |
| apache/commons-compress#334.2 · Control | Drop exactly the first 15 bytes of the fixture and open the remaining ZIP as a new file. | Both revisions should read the same name and body. On the merge the offset should be zero and the prefix accessor should return null. | Removing the post-write prefix restores the coordinate system in which the ZIP offsets were recorded. The accessor documents the empty-prefix result. | Either reader loses the body or the merged reader reports any prefix. |
| apache/commons-compress#334.3 · Challenge | On the merge, write the same prefix and named payload in two ways. First prepend the prefix to an ordinary finished ZIP. In the second file call `ZipArchiveOutputStream.writePreamble(prefix)` before `putArchiveEntry`, write the entry and finish the archive. Use ZIP32 in both. | The merged reader on each file should recover the same payload. For each file the documented physical offset is 15 and the prefix stream should give the original 15 bytes. Source inspection predicts the accessor claim may fail for the writer-produced file. | The first local header physically follows the same 15 bytes in either file. The writer counts the preamble when recording offsets, making the reader’s inferred offset correction zero for that file. | Both entry reads succeed but one getter gives 0 or one prefix stream is null for a file beginning with the supplied preamble. |

**Evidence and limits.** COMPRESS-621 reports a prefixed executable JAR that Commons Compress opened with no entries. The landed test checks the prefixed fixture using the new accessors and an actual entry stream. A pinned-file read independently found 217 bytes, a local header at 15 and a central directory at 133. The end record at 195 gives a directory length of 62 and offset of 118, so the offset correction is 15. The regression does not exercise an archive whose recorded offsets already include its preamble. Successfully listing a name alone also leaves the local entry-data offset unchecked.

**Technical notes.** Use the seekable `ZipFile` in the root Maven module. Restrict the comparison to a nonempty, single-disk non-ZIP64 archive. The PR explicitly excludes ZIP64 prefix adjustment. Only the merged comparison uses the two new accessors.

**Sources.** [Issue COMPRESS-621](https://issues.apache.org/jira/browse/COMPRESS-621) · [ZIP reader](https://github.com/apache/commons-compress/blob/0bacf83eb0b3367cd5572ab27e42a444efbcd5f8/src/main/java/org/apache/commons/compress/archivers/zip/ZipFile.java) · [Preamble writer](https://github.com/apache/commons-compress/blob/0bacf83eb0b3367cd5572ab27e42a444efbcd5f8/src/main/java/org/apache/commons/compress/archivers/zip/ZipArchiveOutputStream.java) · [Regression and fixture expectations](https://github.com/apache/commons-compress/blob/0bacf83eb0b3367cd5572ab27e42a444efbcd5f8/src/test/java/org/apache/commons/compress/archivers/zip/ZipFileTest.java) · [Archive fixture](https://github.com/apache/commons-compress/blob/0bacf83eb0b3367cd5572ab27e42a444efbcd5f8/src/test/resources/COMPRESS-621.zip) · [Maven descriptor](https://github.com/apache/commons-compress/blob/0bacf83eb0b3367cd5572ab27e42a444efbcd5f8/pom.xml)

## apache/commons-rng#65 — Resume a saved random sequence in a different generator

**Change and revisions.** [Merged PR #65](https://github.com/apache/commons-rng/pull/65). A JDKRandom checkpoint now carries the length of its serialized JDK generator. A receiver of the same class can restore without first saving its own state. [Landed comparison](https://github.com/apache/commons-rng/compare/9f30ec9c6dede48347c8939d18b1fd560b9229b8...592ad0be4fe4fa912b5cdaf5f83b006eb8a02f77) from `9f30ec9c6dede48347c8939d18b1fd560b9229b8` to `592ad0be4fe4fa912b5cdaf5f83b006eb8a02f77`.

**Public scenario.** Construct two JDKRandom instances with long seeds 8796746234 and 8796746235. Advance each by ten nextInt() calls. Save the first with saveState(), restore that RandomProviderState into the second, and compare ten more public integer draws in order. Keep an independently seeded java.util.Random advanced ten draws as the oracle for the first sequence.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-rng#65.1 · Intent | Restore the first instance’s checkpoint into the second, which has never called saveState(). | RNG-115 reports the parent cannot restore. Its source predicts IllegalStateException before the receiver’s delegate is replaced, so its next draw should still be draw 11 of its original seed. The merge should restore and return draws 11–20 of the donor seed. | JDKRandom documents java.util.Random.nextInt() as the underlying source. Two reference Random instances with the respective seeds give both continuations. | The parent restores successfully, the failed restore moves its sequence, or the merged receiver throws or returns a different integer. |
| apache/commons-rng#65.2 · Control | After ten integer draws, save a generator, draw ten values, restore that same object and repeat. | The ten values after restore should equal the saved continuation on both revisions, in order. | The restorable-provider contract includes same-object replay. Saving on the original object initialized its state length even on the parent. | Restore throws or the replay differs in any position. |
| apache/commons-rng#65.3 · Challenge | On the merge, save a seeded donor immediately after three nextBoolean() calls. Prepare two differently seeded recipients, one with no draws and one with nineteen boolean draws. Restore each from the same checkpoint. On each take 35 booleans then one nextInt(). | Both recipients should reproduce the uninterrupted donor’s entire continuation, including the 29 booleans left in its first cached word, six booleans from the next word, and the following integer. | Use a java.util.Random with the donor seed. Read bits 3–31 of its first nextInt() and bits 0–5 of its second, least significant first. Its third nextInt() supplies the final integer. This also checks the inherited bit cache. | The integer matches but a boolean differs, the two recipients disagree, or one receiver consumes an extra word at the boundary. |

**Evidence and limits.** The issue describes cross-instance failure. The pinned JUnit regression advances two generators and asserts ten matching integers after restore. Integer-only replay can succeed with the wrong boolean cache. The post-failure draw and mixed-method continuation are source-based predictions.

**Technical notes.** Use the core Maven module and the matching commons-rng-client-api. Compare fresh snapshots within each revision on the same JDK. The state format changed and the same-class API does not promise interoperability between releases. For booleans the independent oracle extracts bits from JDK integer draws rather than calling java.util.Random.nextBoolean().

**Sources.** [Issue RNG-115](https://issues.apache.org/jira/browse/RNG-115) · [Provider contract](https://github.com/apache/commons-rng/blob/592ad0be4fe4fa912b5cdaf5f83b006eb8a02f77/commons-rng-client-api/src/main/java/org/apache/commons/rng/RestorableUniformRandomProvider.java) · [JDK adapter before](https://github.com/apache/commons-rng/blob/9f30ec9c6dede48347c8939d18b1fd560b9229b8/commons-rng-core/src/main/java/org/apache/commons/rng/core/source32/JDKRandom.java) · [JDK adapter after](https://github.com/apache/commons-rng/blob/592ad0be4fe4fa912b5cdaf5f83b006eb8a02f77/commons-rng-core/src/main/java/org/apache/commons/rng/core/source32/JDKRandom.java) · [Boolean caching and bit order](https://github.com/apache/commons-rng/blob/592ad0be4fe4fa912b5cdaf5f83b006eb8a02f77/commons-rng-core/src/main/java/org/apache/commons/rng/core/source32/IntProvider.java) · [Replay regression](https://github.com/apache/commons-rng/blob/592ad0be4fe4fa912b5cdaf5f83b006eb8a02f77/commons-rng-core/src/test/java/org/apache/commons/rng/core/source32/JDKRandomTest.java) · [Core build](https://github.com/apache/commons-rng/blob/592ad0be4fe4fa912b5cdaf5f83b006eb8a02f77/commons-rng-core/pom.xml)

## aeron-io/agrona#202 — Materialize distinct map entries when iterators reuse their cursor

**Change and revisions.** [Merged PR #202](https://github.com/aeron-io/agrona/pull/202). The two-parent merge brings in all five submitted commits. Four entry-set implementations override both toArray overloads to copy each key/value pair before advancing the iterator. [Landed comparison](https://github.com/aeron-io/agrona/compare/45d86347910231d66e5f7270d3b03053a1f80b23...13a9083e32f886c652041a536d13980a1ff982e0) from `45d86347910231d66e5f7270d3b03053a1f80b23` to `13a9083e32f886c652041a536d13980a1ff982e0`.

**Public scenario.** Construct `new Int2IntHashMap(8, 0.6f, -127, true)` and insert the pairs (1,10), (2,20), and (3,30). Call `entrySet().toArray()` and separately `entrySet().toArray(new Map.Entry[0])`. After each call has returned, read all three pairs from its array. Compare as a multiset and leave the backing map unchanged throughout. The same pairing check applies to the changed Int2ObjectHashMap, Object2IntHashMap and Object2ObjectHashMap with equivalent boxed keys or values.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| aeron-io/agrona#202.1 · Intent | Convert the three-entry allocation-avoiding map using both array overloads. | The parent is predicted to expose repeated references to one cursor, so the returned pairs do not cover the map. On the merge each array should contain the three inserted pairs exactly once. The respective runtime array types should be Object[] and Map.Entry[]. | The inserted pairs give the expected contents independent of hash-table order. The overloads have different array component-type contracts. | The merged array has length three but repeats a pair, loses an association or has the wrong runtime type. |
| aeron-io/agrona#202.2 · Control | Change only the Int2IntHashMap constructor’s last argument to false. Repeat both conversions. | Both revisions should return all three original key/value pairs once and preserve the requested array types. | With allocation avoidance disabled the parent iterator already returns a separate entry for each call to next(). | A returned key is associated with a different value, appears twice or is absent on either revision. |
| aeron-io/agrona#202.3 · Challenge | On the merge, add the entries returned by the typed Int2IntHashMap conversion to a fresh HashSet. Probe it with new AbstractMap.SimpleImmutableEntry objects for each inserted pair, with no intervening map modification. | All three probes should succeed. The entries’ respective hash codes should be 11, 22 and 29 for keys 1, 2 and 3. Source inspection predicts at least one failure despite correct getKey() and getValue() results. | Map.Entry defines the hash as key hash XOR value hash. The JDK reference entries compute this independently. The merged copy’s hashCode() calls primitive accessors on the enclosing iterator, whose cursor has moved. | An entry equals its JDK counterpart but has a different hash, or the set reports that an inserted pair is absent. |

**Evidence and limits.** The PR identifies four repaired map implementations and excludes Int2ObjectCache. Their landed tests consume the snapshots through array conversions and an ArrayList constructor, using retained keys to remove mappings. Removal by key cannot detect a broken entry hash. The pre-merge aliasing and merged HashSet outcome above are predictions from the pinned sources.

**Technical notes.** Use org.agrona.collections in the agrona Gradle module. The missing-value sentinel -127 is outside this fixture. The hash challenge is specific to Int2IntHashMap. No assertion depends on iteration order or on retained-entry behavior after mutating the map.

**Sources.** [Primitive map before](https://github.com/aeron-io/agrona/blob/45d86347910231d66e5f7270d3b03053a1f80b23/agrona/src/main/java/org/agrona/collections/Int2IntHashMap.java) · [Primitive map and copied entry](https://github.com/aeron-io/agrona/blob/13a9083e32f886c652041a536d13980a1ff982e0/agrona/src/main/java/org/agrona/collections/Int2IntHashMap.java) · [Int-to-object entries](https://github.com/aeron-io/agrona/blob/13a9083e32f886c652041a536d13980a1ff982e0/agrona/src/main/java/org/agrona/collections/Int2ObjectHashMap.java) · [Object-to-int entries](https://github.com/aeron-io/agrona/blob/13a9083e32f886c652041a536d13980a1ff982e0/agrona/src/main/java/org/agrona/collections/Object2IntHashMap.java) · [Object-to-object entries](https://github.com/aeron-io/agrona/blob/13a9083e32f886c652041a536d13980a1ff982e0/agrona/src/main/java/org/agrona/collections/Object2ObjectHashMap.java) · [Array and list regressions](https://github.com/aeron-io/agrona/blob/13a9083e32f886c652041a536d13980a1ff982e0/agrona/src/test/java/org/agrona/collections/Int2IntHashMapTest.java) · [Gradle build](https://github.com/aeron-io/agrona/blob/13a9083e32f886c652041a536d13980a1ff982e0/build.gradle)

## locationtech/spatial4j#212 — Finish a GeoJSON MultiPoint before serializing its container

**Change and revisions.** [Merged PR #212](https://github.com/locationtech/spatial4j/pull/212). The two submitted commits landed together. Removing the early return after MultiPoint coordinates lets the serializer close the geometry object before Jackson resumes its enclosing array or object. [Landed comparison](https://github.com/locationtech/spatial4j/compare/9180d076b6683b54a961b373419d3e4347ac0b35...81f473f4dc4ad0edc1fab12eb8908dadff69944a) from `9180d076b6683b54a961b373419d3e4347ac0b35` to `81f473f4dc4ad0edc1fab12eb8908dadff69944a`.

**Public scenario.** Register new ShapesAsGeoJSONModule() on a Jackson ObjectMapper. Use a JTS GeometryFactory to make a Point at (100,100) and a MultiPoint from a one-element Point array containing that point. Call mapper.writeValueAsString(Collections.singletonList(geometry)). For successful writes, use a fresh, unconfigured ObjectMapper to parse the output as a tree. Compare type strings, numeric ordinates and array nesting. Field ordering, whitespace and the textual spelling of equivalent numbers may vary.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| locationtech/spatial4j#212.1 · Intent | Write the singleton list containing the one-point MultiPoint. | Issue #210 reports a JsonGenerationException when Jackson tries to end the list with its generator still inside an object. The merge should emit a list of length one whose object has type MultiPoint and coordinates [[100,100]]. | The issue supplies both JTS construction and the exception. A MultiPoint containing one position still has an array of positions. | The merged write throws, or the parsed value loses the list, the point nesting, the type or either ordinate. |
| locationtech/spatial4j#212.2 · Control | Replace the MultiPoint by its constituent Point, keeping the same mapper and singleton list. | Both revisions should emit one object of type Point with coordinates [100,100]. | The issue displays the successful Point output and the two geometries share exactly the same input position. | The Point write fails, produces an extra array level or changes either ordinate. |
| locationtech/spatial4j#212.3 · Challenge | On the merge, keep the MultiPoint fixed. With GeometryFactory.createGeometryCollection, put it before a Point at (7,9), then reverse those two children in a second collection. Serialize a LinkedHashMap with the collection in the first field and integer 17 in the next field. | Each parsed first field should have type GeometryCollection and exactly two elements in its geometries array, in supplied order. The MultiPoint and Point must have the same respective coordinate trees in both runs. The following field must still be a sibling with value 17. | JTS supplies an ordered Geometry array to the collection. The two fixtures give the exact expected children, and the enclosing map independently gives the sibling boundary. The serializer recursively handles collection members. | A child migrates into the preceding object, a geometry or trailing field is lost, either write throws, or the shared MultiPoint changes when its sibling moves. |

**Evidence and limits.** The issue supplies the failing MultiPoint list and successful Point list. The PR changes the serializer and change log and adds no test. The existing writer suite checks a standalone MultiPoint representation. A root geometry can look complete after a generator is closed while an enclosing list or sibling write still fails. The nested readback is an unexecuted prediction.

**Technical notes.** Use the root Maven module with its optional com.fasterxml.jackson.core:jackson-databind:2.9.10.8 and org.locationtech.jts:jts-core:1.18.1 available. ShapesAsGeoJSONModule registers GeometryAsGeoJSONSerializer for JTS Geometry and a separate serializer for Spatial4j Shape. The receivers here are JTS geometries with finite XY positions.

**Sources.** [Reported list serialization](https://github.com/locationtech/spatial4j/issues/210) · [Geometry serializer before](https://github.com/locationtech/spatial4j/blob/9180d076b6683b54a961b373419d3e4347ac0b35/src/main/java/org/locationtech/spatial4j/io/jackson/GeometryAsGeoJSONSerializer.java) · [Geometry serializer after](https://github.com/locationtech/spatial4j/blob/81f473f4dc4ad0edc1fab12eb8908dadff69944a/src/main/java/org/locationtech/spatial4j/io/jackson/GeometryAsGeoJSONSerializer.java) · [Module registration](https://github.com/locationtech/spatial4j/blob/81f473f4dc4ad0edc1fab12eb8908dadff69944a/src/main/java/org/locationtech/spatial4j/io/jackson/ShapesAsGeoJSONModule.java) · [Standalone MultiPoint tests](https://github.com/locationtech/spatial4j/blob/81f473f4dc4ad0edc1fab12eb8908dadff69944a/src/test/java/org/locationtech/spatial4j/io/GeneralGeoJSONTest.java) · [Jackson test setup](https://github.com/locationtech/spatial4j/blob/81f473f4dc4ad0edc1fab12eb8908dadff69944a/src/test/java/org/locationtech/spatial4j/io/jackson/JacksonGeoJSONWriterTest.java) · [Dependency versions](https://github.com/locationtech/spatial4j/blob/81f473f4dc4ad0edc1fab12eb8908dadff69944a/pom.xml)

## checkstyle/checkstyle#14128 — Checkstyle attributes a hidden field to the right enclosing type

**Change and revisions.** [Merged PR #14128](https://github.com/checkstyle/checkstyle/pull/14128). A member record is implicitly static. HiddenField now stops looking for enclosing instance fields when it crosses that record. [Landed comparison](https://github.com/checkstyle/checkstyle/compare/d3f020a5c477edbb57afc0f3fa2d1fab0849d6fb...d150018d141294ac9bb02ae653d01072c5c4c4ae) from `d3f020a5c477edbb57afc0f3fa2d1fab0849d6fb` to `d150018d141294ac9bb02ae653d01072c5c4c4ae`.

**Public scenario.** Audit a UTF-8 file with the Checkstyle CLI, using `-c hidden.xml -f xml Sample.java`. Configure only `Checker → TreeWalker → HiddenField`, with its default properties. Start with `class Sample { int quota; record Entry() { int take(int quota) { return quota; } } }`. Inspect the XML errors from `HiddenFieldCheck`, including the identifier at the reported position. Each variant below is a separate audit.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| checkstyle/checkstyle#14128.1 · Intent | The parameter of `Entry.take` matches only the outer instance field. | Parent source predicts one diagnostic on the parameter `quota`. The merge should produce zero. | A member record has no enclosing Sample instance. The issue shows the same false positive for a Clock parameter and reports that spelling out `static` clears it. | A merged audit reports that parameter, or the parent already produces zero on this fixture. |
| checkstyle/checkstyle#14128.2 · Control | Replace `record Entry()` with the ordinary member declaration `class Entry`, leaving the outer field and method unchanged. | Both revisions should report exactly one HiddenField diagnostic on the parameter. | The ordinary member class has an enclosing Sample instance. Its method parameter shadows the available field. The upstream comparison fixture includes this control. | Either audit produces zero errors or identifies a different token. |
| checkstyle/checkstyle#14128.3 · Challenge | On the merge, give Sample a second field `static int limit;`. Inside Entry add `class Reader { int cap(int limit) { return limit; } }`. Audit once as written, then spell Entry as `static record Entry()`. | Each audit should report exactly the `limit` parameter inside Reader. The `quota` parameter in Entry stays clear. Compare the identified parameters across files, allowing positions to shift. | Nested types can still refer to the enclosing static field. The record boundary cuts access to the enclosing instance, and the redundant modifier changes neither name’s scope. | The checker loses the `limit` finding across the record boundary, reports `quota`, or changes the selected identifiers when `static` is written. |

**Evidence and limits.** Issue #14028 records the CLI output for Checkstyle 10.12.4. The two landed tests use inline configuration with setter and constructor exceptions. Their expected findings are the `pointer` parameter at 35:30 and the ordinary member class’s `x` at 49:27, respectively. Counting violations alone could miss a warning that moved from the accessible static field to an inaccessible instance field. The proposed XML audits are source-based predictions.

**Technical notes.** The main Checkstyle Maven project supplies the Java parser, TreeWalker and HiddenField check. These fixtures exercise record syntax directly through Checkstyle. The English text depends on locale, so match the check source and position when comparing the XML.

**Sources.** [Original CLI report](https://github.com/checkstyle/checkstyle/issues/14028) · [HiddenField contract and configuration](https://github.com/checkstyle/checkstyle/blob/d150018d141294ac9bb02ae653d01072c5c4c4ae/src/xdocs/checks/coding/hiddenfield.xml) · [CLI options](https://github.com/checkstyle/checkstyle/blob/d150018d141294ac9bb02ae653d01072c5c4c4ae/src/main/java/com/puppycrawl/tools/checkstyle/Main.java) · [Field lookup](https://github.com/checkstyle/checkstyle/blob/d150018d141294ac9bb02ae653d01072c5c4c4ae/src/main/java/com/puppycrawl/tools/checkstyle/checks/coding/HiddenFieldCheck.java) · [Regression assertions](https://github.com/checkstyle/checkstyle/blob/d150018d141294ac9bb02ae653d01072c5c4c4ae/src/test/java/com/puppycrawl/tools/checkstyle/checks/coding/HiddenFieldCheckTest.java) · [Record and static field fixture](https://github.com/checkstyle/checkstyle/blob/d150018d141294ac9bb02ae653d01072c5c4c4ae/src/test/resources-noncompilable/com/puppycrawl/tools/checkstyle/checks/coding/hiddenfield/InputHiddenFieldInnerRecordsImplicitlyStatic.java) · [Class and record comparison](https://github.com/checkstyle/checkstyle/blob/d150018d141294ac9bb02ae653d01072c5c4c4ae/src/test/resources-noncompilable/com/puppycrawl/tools/checkstyle/checks/coding/hiddenfield/InputHiddenFieldRecordsImplicitlyStaticClassComparison.java)

## libgdx/libgdx#7278 — libGDX returns a usable polygon when clipping reports an overlap

**Change and revisions.** [Merged PR #7278](https://github.com/libgdx/libgdx/pull/7278). The Polygon overload of Intersector.intersectPolygons now requires at least three coordinate pairs in its clipped result before reporting success or writing to the output polygon. [Landed comparison](https://github.com/libgdx/libgdx/compare/0de4d893abc4d02d8e1bf949edda4a9d5c547e18...7bed7d3666d3b343aebeb1c3f733eae63380dd10) from `0de4d893abc4d02d8e1bf949edda4a9d5c547e18` to `7bed7d3666d3b343aebeb1c3f733eae63380dd10`.

**Public scenario.** Create two clockwise convex Polygons from interleaved float coordinates. Call the static `Intersector.intersectPolygons(subject, clip, out)` with a separate `new Polygon()`. Observe the boolean or exception, then inspect `out.getVertexCount()` and, on success, `out.getBoundingRectangle()`. The small-overlap input is the regression triangle [(3200.1453,88.00839),(3233.9087,190.34174),(3266.2905,0)] and clip [(3213,131),(3214,131),(3214,130),(3213,130)], with each coordinate stored as a Java float.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| libgdx/libgdx#7278.1 · Intent | Use the regression pair with a fresh empty output. Repeat the same call with null output. | The merge should return false in both calls and leave the fresh polygon empty. For the parent, the old nonempty-result branch predicts IllegalArgumentException with the fresh output and true with null if clipping retains one or two vertices. | Polygon requires three points to set its vertices. The pinned regression expects false and zero output vertices. Asking to discard the output should preserve the boolean decision. | The merge throws, reports true for either call, or adds any vertex to the initially empty polygon. The two parent calls can also falsify the predicted branch. |
| libgdx/libgdx#7278.2 · Control | Clip rectangle [(1,2),(1,5),(3,5),(3,2)] against [0,10] × [0,10] in clockwise order. Supply a fresh output. | Both should return true with four vertices and bounds (x=1, y=2, width=2, height=3). Cyclic vertex order may vary. | All four subject vertices are strictly inside the clip. The intersection equals the subject, and these small integers are exactly representable as floats. | Either returns false or produces different bounds or a different vertex count. |
| libgdx/libgdx#7278.3 · Challenge | Keep the same rectangles. Initialize the output as the clockwise square [−4,−2] × [−4,−2] at identity transform. Read its bounds once, then pass it to the clipper. Compare the returned polygon’s local coordinates and post-call bounds with the fresh-output control. | On both, the output should describe the subject after success. Source inspection predicts a discrepancy on both: the four local pairs can change while getBoundingRectangle() still returns the old square’s bounds. | The result polygon is an output parameter. Reading its bounds before reuse cannot change the geometry of the two inputs. Calling its public bounds reader after success tests whether a caller can consume the replacement. | A successful call with new local coordinates and old bounds (−4,−4,2,2) refutes consistency. Fresh and reused outputs agreeing throughout would refute the predicted discrepancy. |

**Evidence and limits.** Issue #6986 reports an exception in 1.11.0 on a different seven-vertex subject. The merged regression asserts false and zero vertices for its triangle. It establishes the expected result for that stored float fixture, without deciding whether an ideal real-arithmetic intersection has positive area. An empty-output test never reaches the equal-length overwrite of an already-read Polygon.

**Technical notes.** The Polygon overload and Polygon’s bounds reader are in the core gdx module. Reuse the same output object at identity transform and copy the initial bound values before the call, since getBoundingRectangle() can return the same mutable Rectangle. The fixture uses only core math classes.

**Sources.** [Original 1.11.0 report](https://github.com/libgdx/libgdx/issues/6986) · [Parent clipper](https://github.com/libgdx/libgdx/blob/0de4d893abc4d02d8e1bf949edda4a9d5c547e18/gdx/src/com/badlogic/gdx/math/Intersector.java) · [Merged clipper](https://github.com/libgdx/libgdx/blob/7bed7d3666d3b343aebeb1c3f733eae63380dd10/gdx/src/com/badlogic/gdx/math/Intersector.java) · [Polygon vertices and bounds](https://github.com/libgdx/libgdx/blob/7bed7d3666d3b343aebeb1c3f733eae63380dd10/gdx/src/com/badlogic/gdx/math/Polygon.java) · [Regression coordinates](https://github.com/libgdx/libgdx/blob/7bed7d3666d3b343aebeb1c3f733eae63380dd10/gdx/test/com/badlogic/gdx/math/IntersectorTest.java) · [Core build](https://github.com/libgdx/libgdx/blob/7bed7d3666d3b343aebeb1c3f733eae63380dd10/gdx/build.gradle)

## apache/tinkerpop#3105 — TinkerPop rejects a second projection on the same dedup step

**Change and revisions.** [Merged PR #3105](https://github.com/apache/tinkerpop/pull/3105). The global deduplication step accepts one by() projection. A second one used to overwrite the first and can silently change which vertices reach the caller. The merge rejects the second call. [Landed comparison](https://github.com/apache/tinkerpop/compare/007fd228a992f1dccba22e25a88e647168e5ba4f...a97db03618fa2fd7c17d24e331ff62adfe9c8df4) from `007fd228a992f1dccba22e25a88e647168e5ba4f` to `a97db03618fa2fd7c17d24e331ff62adfe9c8df4`.

**Public scenario.** Use embedded Java with `g = TinkerFactory.createModern().traversal()`. Keep the handle `t = g.V().dedup().by("age")`, then call `t.by("name")` separately so construction-time errors are observable. If accepted, collect `t.values("name").toList()`. Compare names without imposing traversal order. Use a fresh traversal for each control. In the Modern fixture all six names are distinct. Only marko, vadas, josh and peter have an age, each different.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/tinkerpop#3105.1 · Intent | Apply both projections to the same global dedup in the order age, name. | Parent should accept the second call and yield all six names including lop and ripple. On the merge the second by() itself should throw IllegalStateException before iteration. | The issue records all six elements for the two-key spelling and for name alone. The pinned Java test expects rejection during composition with the keys in reverse order. | The parent omits a name, the merged call returns normally, or the exception appears only when the embedded traversal is iterated. |
| apache/tinkerpop#3105.2 · Control | Use just `g.V().dedup().by("age").values("name").toList()`. | Both should yield each of marko, vadas, josh and peter exactly once. | An absent age gives no productive key. The fixture supplies four distinct ages and the issue’s single-projection run returns these four vertices. | Either includes a software vertex, drops a named person or returns a duplicate. |
| apache/tinkerpop#3105.3 · Challenge | Hold both keys and the graph fixed. Insert a second dedup() immediately before the second by("name"), giving each step one projection, then collect names. | Both should accept the traversal and yield the same four people as the control. On the merge, moving the projection onto its own step should make the composition valid again. | The Java DSL applies by() to the preceding step. The first step admits four people with distinct ages. Their names are also distinct, so a second distinct-by-name operation preserves them. | A legal second step throws, the two steps share a key, or the name multiset differs from the control. |

**Evidence and limits.** TINKERPOP-3148 shows the older console results for age, name and age followed by name. The Java regression calls an anonymous traversal. The Gherkin case specifies an error on software vertices with lang followed by name. The embedded Modern traversal and two-step challenge above have not been executed. After a caught rejection the local step still holds its first projection in source, but GraphTraversal.by(String) records bytecode before checking it. The fixtures establish no guarantee that reusing or serializing a failed builder rolls the bytecode back.

**Technical notes.** Use gremlin-core and the matching tinkergraph-gremlin provider from the pinned revision. TinkerFactory supplies the Modern graph without a server. The exception timing here is for the embedded Java DSL. The feature suite also covers clients where evaluation is deferred.

**Sources.** [Console observations](https://issues.apache.org/jira/browse/TINKERPOP-3148) · [Java traversal API](https://github.com/apache/tinkerpop/blob/a97db03618fa2fd7c17d24e331ff62adfe9c8df4/gremlin-core/src/main/java/org/apache/tinkerpop/gremlin/process/traversal/dsl/graph/GraphTraversal.java) · [Global dedup filtering and validation](https://github.com/apache/tinkerpop/blob/a97db03618fa2fd7c17d24e331ff62adfe9c8df4/gremlin-core/src/main/java/org/apache/tinkerpop/gremlin/process/traversal/step/filter/DedupGlobalStep.java) · [Java regression](https://github.com/apache/tinkerpop/blob/a97db03618fa2fd7c17d24e331ff62adfe9c8df4/gremlin-core/src/test/java/org/apache/tinkerpop/gremlin/process/traversal/step/filter/DedupGlobalStepTest.java) · [Language feature scenario](https://github.com/apache/tinkerpop/blob/a97db03618fa2fd7c17d24e331ff62adfe9c8df4/gremlin-test/src/main/resources/org/apache/tinkerpop/gremlin/test/features/filter/Dedup.feature) · [Modern graph fixture](https://github.com/apache/tinkerpop/blob/a97db03618fa2fd7c17d24e331ff62adfe9c8df4/tinkergraph-gremlin/src/main/java/org/apache/tinkerpop/gremlin/tinkergraph/structure/TinkerFactory.java)

## Setup Agent Notes

### What is ready, and where

- Everything is under `~/.cache/in-the-loop/merged-pr-links-m01-m10` (`$O`); `source $O/scripts/env.sh` gives `$O`, `$M`, `$W`, `$MVN`,
  `GRADLE_USER_HOME`, `TMPDIR` and the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25`. **The default `java` is 25**: name a JDK by path.
- Both revisions of every case at the brief's pins: `$W/MNN-MIRROR-parent` and `$W/MNN-MIRROR-fix` (full SHAs, trees and parents in
  [Upstream revisions](#upstream-revisions)). Every PR's merge SHA is the brief's after pin, and every after pin's first parent is the before pin.
- Built jars of both sides in `$O/artifacts/` (`MNN-MIRROR-ROLE.jar`), with full sha256s and the changed classes' digests in each case's
  **Artifacts** table, and runtime classpath files beside them; each section ends its Artifacts part with a `java -cp` line. M01–M07 and M09 were
  built inline, M08 and M10 by the two jobs in [Jobs](#jobs) (both passed).
- The JDK per case: M01 17, M02 17, M03 21, M04 11, M05 8, M06 8, M07 11, M08 17, M09 17, M10 11 (TinkerPop's enforcer refuses 18+).
- Exact build and test commands, online and checked offline, in each case's **Commands**. Gradle runs from `$O/tools/gradle-VERSION`, never
  `gradlew`.
- Release graphs with sources, resolved with strict checksums: `$O/releases/` (jackson-databind 3.0.4, 3.1.1, 3.1.2, 3.2.0; vavr 1.0.1, 1.1.0;
  commons-compress 1.22, 1.23.0; commons-rng-core 1.2, 1.3; RoaringBitmap 1.6.24, 1.6.25; agrona 1.3.0, 1.4.0; spatial4j 0.8; checkstyle
  10.12.4; gdx 1.11.0, 1.12.1, 1.13.0).
- M04's fixture: `$W/M04-commons-compress-fix/src/test/resources/COMPRESS-621.zip`, 217 bytes, sha256
  `198e954c1f2eaf9cf1cf8b7ce991d74ac3a0e2acfa7616dfbf7c8231ee6b20e0`.
- M08's CLI configuration (`Checker → TreeWalker → HiddenField`, default properties): `$O/scripts/M08-cli-check/hidden.xml`; the CLI command is
  in M08's **Commands**.
- M07's issue #210 reproduction: `$O/repro/M07/Main.java` (the issue's `Main` verbatim).

### What was verified on a JVM

- Landed regressions, at both pins (each case's **Landed tests** table, [Summary by case](#summary-by-case)): the fix's tests pass on the fix,
  the parent's own pass on the parent, and the fix's tests fail on the parent: M01 (6), M02 (4 of 5, child value `null`, no exception),
  M03 (2, `expected: Some(null) but was: None`), M05 (1, `IllegalStateException: java.io.EOFException` on restore), M06 (12), M09 (1,
  `IllegalArgumentException: polygons must contain at least 3 points.`). M04's landed test does not compile on the parent (it calls the new
  accessors); with those four lines removed it fails on the parent (`getEntry("COMPRESS-621.txt")` returns null) and passes on the fix.
- M07 has no landed test: the issue's own reproduction throws `JsonGenerationException: Current context not Array but Object` on the parent and
  writes `[{"type":"MultiPoint","coordinates":[[100.0,100.0]]}]` on the fix; the existing GeoJSON/Jackson tests pass at both pins (90/90).
- M08 (job): fix 19/19, parent 17/17, the fix's test on the parent fails 2 (`testHiddenFieldInnerRecordsImplicitlyStatic`,
  `testHiddenFieldRecordsImplicitlyStaticClassComparison`); the CLI runs on both built jars and on 10.12.4. M10 (job): fix `DedupGlobalStepTest`
  2/2 and Dedup.feature 28/28, parent 1/1 and 27/27; on the parent the fix's tests fail once in each module (`shouldThrowForMultipleByModulators`,
  `Expected exception: java.lang.IllegalStateException`; the feature scenario `g_V_both_hasXlabel_softwareX_dedup_byXlangX_byXnameX_name`).
- Offline builds (`mvn -o`, `gradle --offline`) checked for every case (M08 and M10 by their jobs).

### What to know before starting

- **M02's snapshot inputs are substitutes.** `jackson-base`/`jackson-bom`/`jackson-core` 3.2.0-SNAPSHOT and `jackson-annotations`/`jackson-parent`
  2.22-SNAPSHOT are no longer served by any snapshot repository; they were rebuilt from their own upstreams at the last branch commit before
  the parent pin (same inputs serve both sides; commits in M02's section's table, digests beside them). Released 3.2.0/2.22 came later and are
  not the inputs. Nothing published equals either pin.
- **Released versions are not the pins.** Byte-equal stand-ins: commons-rng-core 1.2 = parent `JDKRandom.java`; agrona 1.3.0 = parent's four
  maps; gdx 1.12.1 = parent `Intersector.java`, 1.13.0 = fix's; spatial4j 0.8 = parent serializer; Checkstyle 10.12.4 = parent
  `HiddenFieldCheck.java`, 10.12.7 = fix's (not resolved as a graph); jackson-databind 3.1.2 = parent `BeanPropertyMap.java` only. Every other
  release carries other changes.
- **M01:** the built jars say version 1.6.24, but the *released* 1.6.24 is older code; the build's `failFast = true` is turned off by
  `$O/scripts/nofailfast_C.init.gradle` so a run reports every failure. M01's wrapper jar is 8.14.3's, not 9.6.1's (unused).
- **M06:** the build generates `Long*` maps from the `Int*` sources, so the fix also changes `Long2LongHashMap`, `Long2ObjectHashMap` and
  `Object2LongHashMap`.
- **M09:** `:gdx` builds alone only with `--configure-on-demand` (the Android backend needs an SDK) and `-Dmaven.repo.local=$O/mavenlocal-empty`;
  classes are Java 7 bytecode.
- **M05:** the state format differs between pins (the fix adds a 4-byte length); surefire reruns a failing test twice.
- **M08:** `dependency:go-offline` fails on a POM-only `axiom:1.2.15`; the job resolves the rest online first. The CLI exits with the number of
  errors and prints a trailer after the XML: use `-o OUT.xml`. Message text depends on locale.
- **M10:** the build is restricted to `-pl gremlin-core,tinkergraph-gremlin -am`; the classpath file's reactor paths are rewritten to the copied
  jars by `$O/scripts/M10_cp.py`.

### What is left for the domain work on purpose

- Every claim, fixture and history in the brief: none of the brief's public scenarios was run (the brief's own records, bitmaps, iterators,
  ZIP variants, RNG sequences, map arrays, nested GeoJSON, Checkstyle audit files, polygon reuse and Modern-graph traversals).
- Example scaffolding, ids, sidecars, adapters and recipes; the choice of which jar (pin build or release) a claim runs against.
