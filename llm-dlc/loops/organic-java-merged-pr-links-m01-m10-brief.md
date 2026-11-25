# Merged Java pull requests M01–M10 — observable behavior across revisions

## Objective

Compare each landed change with the revision immediately preceding it. Follow a concrete caller through the changed behavior, preserve a neighboring case, and test a prediction that the upstream example leaves open. Each claim names an observation that could overturn it.

## RoaringBitmap/RoaringBitmap#863 — Containment across a missing block and the unsigned upper bound

**Change and revisions.** [Merged PR #863](https://github.com/RoaringBitmap/RoaringBitmap/pull/863). The heap and buffer implementations now distinguish a missing final block from a later block at the same insertion point. They also retain the exclusive endpoint 2³² without wrapping its block number to zero. [Landed comparison](https://github.com/RoaringBitmap/RoaringBitmap/compare/ffa685e6dbfb002c484f2bb5e0f3c5d6f5120088...baea79f84f78a8b697b10af5e3e0de034d6c66e8) from `ffa685e6dbfb002c484f2bb5e0f3c5d6f5120088` to `baea79f84f78a8b697b10af5e3e0de034d6c66e8`.

**Public scenario.** Let B = 65,536 and U = 1L << 32. Construct RoaringBitmap.bitmapOfRange(0L, B), query contains(0L, B+1L), then add the single integer 3*B and repeat. Also query an independently constructed top block [U−B,U). Repeat with MutableRoaringBitmap and with an ImmutableRoaringBitmap created from its serialized, flipped ByteBuffer. Use long endpoints throughout.

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

**Public scenario.** Build JsonMapper.builder().build(). Define record Inner(@JsonAlias("a") String c) and record Outer(@JsonUnwrapped Inner inner, String b). Read {"a":"Hello","b":"World!"} as Outer. Inspect inner().c() and b(). Use public records with visible accessors for the serialization check.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| FasterXML/jackson-databind#5913.1 · Intent | Read the alias input with readValue(json, Outer.class). | Parent is expected to miss the nested value or reject the input. Merge yields ("Hello","World!") in the child and sibling respectively. | The alias designates c and @JsonUnwrapped places its input at the outer level. Issue #5911 reports the corresponding record assertion failing on 3.1.1 and 3.1.2. | The merge throws or either binding is wrong. A correct pair on the pinned parent refutes the predicted revision contrast. |
| FasterXML/jackson-databind#5913.2 · Control | Replace the key a with c, keeping both values and the same types. | Both revisions yield the identical two strings. | The primary name is the declared component name. Its routing does not require any aliases. The upstream POJO control checks this route. | Either reader loses the child or sibling, or changes a value. |
| FasterXML/jackson-databind#5913.3 · Challenge | On the merge read the alias form, call writeValueAsString on the resulting Outer, parse those bytes of JSON text with readTree, and read the emitted text again as Outer. | The tree has exactly {"c":"Hello","b":"World!"} in any field order. The second Outer equals the first. | An input alias gives an alternate spelling for a property. Unwrapping exposes its primary name on output. Reading the canonical representation separately checks the persistence boundary. | A nested inner object or alias a leaks into the output, a value changes, or the second read differs. |

**Evidence and limits.** Issue #5911 compares released versions and reports success on 3.0.4. The landed tests inspect records, ordinary beans, a creator parameter, and a second alias. The exact failure mode on the pinned parent and the write/read round trip are open. Simply accepting the input JSON would miss an unpopulated child.

**Technical notes.** The Maven POM declares Java 17 source and target. The mapper is tools.jackson.databind.json.JsonMapper. The annotations retain their com.fasterxml.jackson.annotation package. Use the same default mapper for all three reads.

**Sources.** [Issue #5911](https://github.com/FasterXML/jackson-databind/issues/5911) · [Outer name collection](https://github.com/FasterXML/jackson-databind/blob/9a7d8eb3e6ae7adba3470ed15a4f1b2361558640/src/main/java/tools/jackson/databind/deser/bean/BeanDeserializerBase.java) · [Alias definitions](https://github.com/FasterXML/jackson-databind/blob/9a7d8eb3e6ae7adba3470ed15a4f1b2361558640/src/main/java/tools/jackson/databind/deser/bean/BeanPropertyMap.java) · [Record and bean tests](https://github.com/FasterXML/jackson-databind/blob/9a7d8eb3e6ae7adba3470ed15a4f1b2361558640/src/test/java/tools/jackson/databind/struct/UnwrappedWithAlias5911Test.java) · [Build and annotations](https://github.com/FasterXML/jackson-databind/blob/9a7d8eb3e6ae7adba3470ed15a4f1b2361558640/pom.xml)

## vavr-io/vavr#3272 — Keep a matched null distinct from an empty search

**Change and revisions.** [Merged PR #3272](https://github.com/vavr-io/vavr/pull/3272). Iterator.findLast now records whether any element satisfied the predicate, independently of the value it keeps. [Landed comparison](https://github.com/vavr-io/vavr/compare/c6f0be585529bf16a4597b35f966439cffde894b...8bd9c6b92ac07259f82ce30a09d037dfc5c78d81) from `c6f0be585529bf16a4597b35f966439cffde894b` to `8bd9c6b92ac07259f82ce30a09d037dfc5c78d81`.

**Public scenario.** Use a fresh io.vavr.collection.Iterator<Integer> for each search. Call findLast, observe Option.isDefined(), then call getOrElse with a Supplier<Integer> that increments a counter and returns 99. A defined null and an empty option yield different observable pairs.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| vavr-io/vavr#3272.1 · Intent | Iterator.<Integer>of(null,1,null), with x -> x == null. | Parent None, yielding 99 with one supplier call. Merge Some(null), yielding null with zero calls. | Indices 0 and 2 match. The last one exists and stores null. The pinned Option documentation explicitly permits Some(null). | The merge reports empty or invokes the fallback. A defined null on the parent refutes the predicted change. |
| vavr-io/vavr#3272.2 · Control | Use [1,2,3] twice, first selecting values >5, then selecting odd values. | Both revisions yield None (fallback 99, one call) and Some(3) (value 3, zero calls), respectively. | The qualifying positions are empty in the first search and 0,2 in the second. | An absent match looks defined, the second search returns 1, or the supplier is invoked for 3. |
| vavr-io/vavr#3272.3 · Challenge | On the merge select null or 7. Compare [7,null,4] with [null,7,4]. Append a further rejected 4 to each and search again. | The first pair of histories ending in one or two 4s always returns a defined null. The reordered histories always return a defined 7. All four suppress the fallback. | The final accepted position moves between values while the rejected suffix cannot affect it. The supplier makes presence observable even when the stored value is null. | The rejected suffix clears the result, reordering leaves the selected value unchanged, or a successful search invokes the fallback. |

**Evidence and limits.** The three added tests compare Option values for two null matches and one empty search. The parent returns Option.of(last), which collapses a null payload into None. The mixed-match, reordered histories and callback observations are source-based predictions. Unwrapping with a null default would conceal the defect.

**Technical notes.** Use the vavr Maven module, Vavr Option and its Iterator. Materialize the same inputs afresh for each call because the iterator is consumed.

**Sources.** [Iterator search](https://github.com/vavr-io/vavr/blob/8bd9c6b92ac07259f82ce30a09d037dfc5c78d81/vavr/src/main/java/io/vavr/collection/Iterator.java) · [Parent return path](https://github.com/vavr-io/vavr/blob/c6f0be585529bf16a4597b35f966439cffde894b/vavr/src/main/java/io/vavr/collection/Iterator.java) · [Option factory and fallback](https://github.com/vavr-io/vavr/blob/8bd9c6b92ac07259f82ce30a09d037dfc5c78d81/vavr/src/main/java/io/vavr/control/Option.java) · [Regression](https://github.com/vavr-io/vavr/blob/8bd9c6b92ac07259f82ce30a09d037dfc5c78d81/vavr/src/test/java/io/vavr/collection/IteratorTest.java) · [Module POM](https://github.com/vavr-io/vavr/blob/8bd9c6b92ac07259f82ce30a09d037dfc5c78d81/vavr/pom.xml)
