# Merged Java pull requests — behavior at the public API

## Objective

For each landed change, compare what a caller can observe immediately before and after the merge. Each case gives a concrete history, a control and a second way to catch a wrong result. Historical reports and source inspections are identified separately from predictions about running the two revisions.

## apache/lucene#14732 · Apache Lucene #14732 — match documents when an INT index sort defines a missing value

**Change and revisions.** An explicit integer sort substitute could make a numeric range query throw while converting the substitute to a long. The landed change updates both the count and iterator paths. [Merged PR #14732](https://github.com/apache/lucene/pull/14732) · [Landed comparison](https://github.com/apache/lucene/compare/36ddc378eac62f931e98da0ed5cd3edbbddc920e...5c886602a8e8146203deb1a9c3c0121a4241108c)

Before `36ddc378eac62f931e98da0ed5cd3edbbddc920e` → after `5c886602a8e8146203deb1a9c3c0121a4241108c`.

**Public scenario.** Create a single undeleted segment with an IndexWriter configured with a Sort on SortedNumericSortField("dv", Type.INT, false). Set its missing value to Integer.valueOf(7). Give documents A, B and C stored IDs and values 3, 7 and 9 in both SortedNumericDocValuesField("dv", value) and IntPoint("idx", value). Give D only a stored ID. Open a DirectoryReader and IndexSearcher. For [7,8], use new IndexSortSortedNumericDocValuesRangeQuery("dv", 7, 8, SortedNumericDocValuesField.newSlowRangeQuery("dv", 7, 8)). Read stored IDs from search(query, 10) and independently call count(query).

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/lucene#14732.1 · Intent | Ascending INT sort with explicit 7, range [7,8] | The parent is expected to throw ClassCastException on the affected path. The merge returns only B and counts 1. | Only B has a numeric value in the closed interval. IntPoint.newRangeQuery("idx", 7, 8) supplies an independent query. | The merge throws, returns D, omits B or counts anything other than 1. |
| apache/lucene#14732.2 · Control | Leave the missing-value setting unset on the same INT sort | Both revisions return B and count 1. | The default substitute is 0. The recorded values and the point-query oracle stay the same. | Either revision disagrees with the point query or with its own hit set. |
| apache/lucene#14732.3 · Challenge | Rebuild with reverse sort and change D's substitute to Integer.MIN_VALUE, keeping all documents and query bounds fixed | On the merge the stored IDs are still {B} and count is still 1. Varying physical order and moving the substitute outside the range must preserve membership. | The query asks for document values. Missing D has no point or doc value in either index. | Count succeeds but hit enumeration throws, or either includes D or changes membership. |

**Evidence and limits.** The author reports that the added regression fails without the fix. It compares sorted-range hits with point-query hits across random bounds, directions, missing settings and deletions. Reading the parent shows an Object-to-long cast at both sites. The exact exception and the two public observations above are predictions for this deterministic index. Merely opening a sorted index would miss both casts.

**Technical notes.** Use lucene/core and its build.gradle. Keep point values in the separate field idx so that a same-field point-index optimization cannot answer the entire query before it reaches the changed code. Compare stored IDs because reversing the physical index sort can renumber Lucene documents.

**Sources.** [Range query and contract](https://github.com/apache/lucene/blob/5c886602a8e8146203deb1a9c3c0121a4241108c/lucene/core/src/java/org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery.java) · [Point-query regression](https://github.com/apache/lucene/blob/5c886602a8e8146203deb1a9c3c0121a4241108c/lucene/core/src/test/org/apache/lucene/search/TestIndexSortSortedNumericDocValuesRangeQuery.java) · [Core build](https://github.com/apache/lucene/blob/5c886602a8e8146203deb1a9c3c0121a4241108c/lucene/core/build.gradle)

## locationtech/jts#1179 · JTS #1179 — Keep a projection that touches just one endpoint

**Change and revisions.** JTS merged the change from `f1b596aabc664fd59d9028de10885e84b67febd8` to `ecb26e190e539ea1e4303d100f39f7f30ddeec3e`. A projection whose overlap with the target is a single endpoint should return a segment of length zero. [PR #1179](https://github.com/locationtech/jts/pull/1179) · [Landed comparison](https://github.com/locationtech/jts/compare/f1b596aabc664fd59d9028de10885e84b67febd8...ecb26e190e539ea1e4303d100f39f7f30ddeec3e)

**Public scenario.** Construct a horizontal target with `new LineSegment(new Coordinate(0,0), new Coordinate(8,0))`. Construct each source the same way. Call `target.project(source)`, check for null, then read both endpoints with `getCoordinate(0)` and `getCoordinate(1)`. For these two-dimensional integer fixtures the perpendicular projection onto the target line preserves x and sets y to zero.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| locationtech/jts#1179.1 · Intent | Project the segment from (8,2) to (8,4). | Reported null → a `LineSegment` with both endpoints at (8,0). | The closed target interval [0,8] contains 8. Issue #1178 reports the public call and the regression checks its coordinates. | A null return or either endpoint elsewhere on the merge. |
| locationtech/jts#1179.2 · Control | Shift the source horizontally to x=1 and then to x=9, keeping its y coordinates. | Both revisions should return (1,0) twice at x=1 and null at x=9. | The first projected point lies inside [0,8] and the second lies strictly outside. | The interior point is lost or the outside segment is clamped to a target endpoint. |
| locationtech/jts#1179.3 · Challenge | On the merge, use a `GeometryFactory` to represent the same target and the x=8 and x=9 sources as two-coordinate line strings. Call the new `LineSegmentFunctions.project(targetGeometry, sourceGeometry)` for each. | Both results should be `LineString` objects of length zero. At x=8 the result should contain two coordinates at (8,0). At x=9 it should be empty. | An endpoint contact has one spatial location represented by coincident vertices. An empty projection has none. The app function exposes that distinction through geometry cardinality. | Equal lengths conceal an empty contact result, spurious coordinates outside the interval, or a point returned in place of a line string. |

**Evidence and limits.** The original report and `LineSegmentTest.testProjectSegment` cover the core method, including a source with one end above the target endpoint and the other beyond it. The app function was added in the landed change. Its geometry readback is a prediction. Length alone cannot distinguish the two challenge results. [Issue #1178](https://github.com/locationtech/jts/issues/1178) · [Regression](https://github.com/locationtech/jts/blob/ecb26e190e539ea1e4303d100f39f7f30ddeec3e/modules/core/src/test/java/org/locationtech/jts/geom/LineSegmentTest.java#L81-L106)

**Technical notes.** The core method belongs to `org.locationtech.jts:jts-core` (parent version `1.20.1-SNAPSHOT`). The challenge also uses the `modules/app` function from the landed tree. Two vertices per input select its segment overload. [Core POM](https://github.com/locationtech/jts/blob/ecb26e190e539ea1e4303d100f39f7f30ddeec3e/modules/core/pom.xml)

**Sources.** [Projection contract and implementation](https://github.com/locationtech/jts/blob/ecb26e190e539ea1e4303d100f39f7f30ddeec3e/modules/core/src/main/java/org/locationtech/jts/geom/LineSegment.java#L455-L497) · [App geometry function](https://github.com/locationtech/jts/blob/ecb26e190e539ea1e4303d100f39f7f30ddeec3e/modules/app/src/main/java/org/locationtech/jtstest/function/LineSegmentFunctions.java)

## RoaringBitmap/RoaringBitmap#914 · RoaringBitmap — union through a subtype array

**Change and revisions.** Merged into `master`, from `49e120dad9c21349c44f3aa3edfc9a6601e7a7b0` to `b4b0ba16e50d40688753a3cf057a47804773e233`. Both priority-queue union overloads now store intermediate results in an array whose component type accepts them. [PR #914](https://github.com/RoaringBitmap/RoaringBitmap/pull/914) · [Landed comparison](https://github.com/RoaringBitmap/RoaringBitmap/compare/49e120dad9c21349c44f3aa3edfc9a6601e7a7b0...b4b0ba16e50d40688753a3cf057a47804773e233)

**Public scenario.** Allocate a `FastRankRoaringBitmap[4]`. For each index `i = 0..3`, construct a bitmap, call `add((long)i, i + 10L)` and `add(100_000 * i)`, then store it in slot `i`. Pass the array directly to `FastAggregation.priorityqueue_or(bitmaps)`. Read the returned bitmap with `toArray()`. Repeat on the buffer API with a local `class Sub extends MutableRoaringBitmap {}`, a `Sub[4]` and `BufferFastAggregation.priorityqueue_or(bitmaps)`.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| RoaringBitmap/RoaringBitmap#914.1 · Intent | Call each varargs overload with its four-element subtype array. | Upstream reports `ArrayStoreException` before. After, both calls return the integers 0 through 12 inclusive, then 100000, 200000 and 300000, in order. | The four half-open ranges overlap, and 0 is already in the first range. Those 16 integers are the complete set union. | Either merged call throws, or either array omits, duplicates or adds a value. |
| RoaringBitmap/RoaringBitmap#914.2 · Control | Copy the same four references into `new RoaringBitmap[4]` or `new ImmutableRoaringBitmap[4]` respectively. | Both revisions should return the same 16 integers through each API. | Changing the runtime component type of the argument array preserves every operand. | An exception or a different array of values on either pin. |
| RoaringBitmap/RoaringBitmap#914.3 · Challenge | On the merge permute the subtype array, replacing its order by indices 3, 1, 0, 2. After the call, read each input with `toArray()` as well as the result. | The union remains the same 16 integers. Each slot still refers to its original bitmap with precisely its original range and extra integer. | Union is commutative. The aggregate returns a result and the implementation allocates its temporary storage separately from the input. Checking both boundaries exposes writes through shared operands. | A permutation changes the result, a slot is replaced or an input gains an element from another input. |

**Evidence and limits.** The two landed tests compare the public result with the library’s `naive_or`. The PR author reports both tests fail on reversal. The PR description cites an older two-argument `Arrays.copyOf`; the landed parent uses `clone()`, which likewise preserves the runtime component type. A call with four individual arguments permits the compiler to construct a base-type varargs array and can pass on the faulty revision.

**Technical notes.** Both overloads belong to the `roaringbitmap` Gradle module. The buffer entry accepts `ImmutableRoaringBitmap...` and returns `MutableRoaringBitmap`. The subclass array exercises a narrower component type than the ordinary mutable intermediates. [Module build](https://github.com/RoaringBitmap/RoaringBitmap/blob/b4b0ba16e50d40688753a3cf057a47804773e233/roaringbitmap/build.gradle.kts)

**Sources.** [Heap API](https://github.com/RoaringBitmap/RoaringBitmap/blob/b4b0ba16e50d40688753a3cf057a47804773e233/roaringbitmap/src/main/java/org/roaringbitmap/FastAggregation.java) · [Buffer API](https://github.com/RoaringBitmap/RoaringBitmap/blob/b4b0ba16e50d40688753a3cf057a47804773e233/roaringbitmap/src/main/java/org/roaringbitmap/buffer/BufferFastAggregation.java) · [Heap regression](https://github.com/RoaringBitmap/RoaringBitmap/blob/b4b0ba16e50d40688753a3cf057a47804773e233/roaringbitmap/src/test/java/org/roaringbitmap/TestFastAggregation.java) · [Buffer regression](https://github.com/RoaringBitmap/RoaringBitmap/blob/b4b0ba16e50d40688753a3cf057a47804773e233/roaringbitmap/src/test/java/org/roaringbitmap/buffer/TestFastAggregation.java)

## apache/datasketches-java#767 · Apache DataSketches #767 — preserve item quantiles across a queried sketch’s serialization

**Change and revisions.** A read of a heap KLL items sketch could mark live data as sorted after sorting only a copy. A later reader of the serialized image then trusted that flag. The comparison starts at the target parent of the two-parent merge. [Merged PR #767](https://github.com/apache/datasketches-java/pull/767) · [Landed comparison](https://github.com/apache/datasketches-java/compare/3857c0cca71a9f5bd462d92e6208d0e0a1c1ac52...7b4068860c3d50da28f3dd734e14f74cd6c5657d)

Before `3857c0cca71a9f5bd462d92e6208d0e0a1c1ac52` → after `7b4068860c3d50da28f3dd734e14f74cd6c5657d`.

**Public scenario.** Construct KllItemsSketch.newHeapInstance(8, Comparator.<String>naturalOrder(), new ArrayOfStringsSerDe()). Update it with "a", "b", "c", "d", in order. Call getQuantile(0.5, INCLUSIVE), then toByteArray(). Give MemorySegment.ofArray(bytes), the same comparator and the same serializer to KllItemsSketch.heapify. Read getSortedView().getQuantiles(), getCumulativeWeights() on the view and getQuantile on the restored sketch.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/datasketches-java#767.1 · Intent | Serialize immediately after the median query, then heapify | Issue #756 reports median c after restoration versus b before restoration on the faulty code. On the merge expect [a,b,c,d], cumulative weights [1,2,3,4], median b and rank-0.55 quantile c. | With four retained unit-weight observations, inclusive ranks select positions ceil(4r), counting from one. | A duplicate endpoint, incorrect weight, or wrong quantile on the merge, even if getNumRetained() says 4. |
| apache/datasketches-java#767.2 · Control | Serialize a fresh four-item sketch without first asking it a quantile, then heapify | Both pins should produce the same four sorted items, weights and quantiles as the oracle. | The input multiset is unchanged and the issue reports this order of operations works. | Moving serialization before the query still leaves a wrong median or a malformed sorted view. |
| apache/datasketches-java#767.3 · Challenge | Insert the same items as c,a,d,b, query rank 0.55, serialize once and independently call heapify and wrap on the same image | On the merge both consumers should give the original four order statistics with the same cumulative weights. The bytes themselves may vary with insertion order. | In this four-item exact regime each value occurs once, and the comparator defines their order independently of insertion and storage. | One reader reproduces the median but has a nonmonotone view, extra endpoint or a different rank-0.55 quantile. |

**Evidence and limits.** Issue #756 gives the four inputs and the observed six-entry heapified view, and reports the same fault with wrap. The added tests compare heapified and wrapped views with the original, and also exercise eight updates. The test name refers to compaction but the test makes no assertion that compaction occurred. Comparing only the original sketch’s median would miss the persisted defect.

**Technical notes.** The root Maven descriptor for org.apache.datasketches:datasketches-java sets compiler release 25. Use the generic heap items API, java.lang.foreign.MemorySegment and ArrayOfStringsSerDe. The doubles sketch has a different array-access contract.

**Sources.** [Report](https://github.com/apache/datasketches-java/issues/756) · [Items API](https://github.com/apache/datasketches-java/blob/7b4068860c3d50da28f3dd734e14f74cd6c5657d/src/main/java/org/apache/datasketches/kll/KllItemsSketch.java) · [Heap storage](https://github.com/apache/datasketches-java/blob/7b4068860c3d50da28f3dd734e14f74cd6c5657d/src/main/java/org/apache/datasketches/kll/KllHeapItemsSketch.java) · [Rank semantics](https://github.com/apache/datasketches-java/blob/7b4068860c3d50da28f3dd734e14f74cd6c5657d/src/main/java/org/apache/datasketches/quantilescommon/QuantileSearchCriteria.java) · [Serialization tests](https://github.com/apache/datasketches-java/blob/7b4068860c3d50da28f3dd734e14f74cd6c5657d/src/test/java/org/apache/datasketches/kll/KllItemsSketchSerDeTest.java) · [Build](https://github.com/apache/datasketches-java/blob/7b4068860c3d50da28f3dd734e14f74cd6c5657d/pom.xml)

## apache/solr#3158 · Solr #3158 — Count documents in multivalued enum buckets

**Change and revisions.** Solr merged `c367cb75ac453bb3cd642c46649455e2b4b018b3` → `f66aa9ed07fa76b5db45186073a9b2ac20c01fd4`. A JSON terms facet on a multivalued enum backed by sorted numeric doc values should return the documents' enum labels and counts. [PR #3158](https://github.com/apache/solr/pull/3158) · [Landed comparison](https://github.com/apache/solr/compare/c367cb75ac453bb3cd642c46649455e2b4b018b3...f66aa9ed07fa76b5db45186073a9b2ac20c01fd4)

**Public scenario.** In an empty single-core collection, define `severity_mv` as the landed schema does on both revisions. Send six documents to `/update`, using IDs 1 through 6 and these value pairs in order: (Not Available, Low), (Low, Medium), (Medium, High), (High, Not Available), (Not Available, Low), (Low, Medium). Commit. Request `/select` with `q=*:*`, `rows=0`, and `json.facet={"f":{"type":"terms","method":"enum","field":"severity_mv"}}`. Read `facets.count`, then the `val` and `count` of every `facets.f.buckets` entry. Compare label-to-count mappings so a tie's position cannot hide a missing bucket.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/solr#3158.1 · Intent | Six documents as above, default terms sort. | The issue reports empty facet results on affected releases. The merge should return total 6 and exactly Low=4, Medium=3, Not Available=3, High=2. | Count distinct IDs with each label. For example, Low occurs in IDs 1, 2, 5 and 6. The landed test expects all four named buckets. | A missing or extra label, an ordinal returned in place of a label, or an incorrect count on the merge. |
| apache/solr#3158.2 · Control | Copy each document's labels into `labels_sds` and change only the facet field. This field uses the schema's multivalued string-with-doc-values pattern. | Both revisions should return the same six matches and four label counts as the input tally. | String labels have the same membership sets as the enum labels. | The string facet loses a label or changes a document count on either revision. |
| apache/solr#3158.3 · Challenge | On the merge, replace ID 1 with its original enum values plus a second Low entry. Commit and repeat the request. | The total and all bucket counts should stay fixed, including Low=4. | A terms bucket counts documents. Repeating a value in one document leaves its membership and the set of matching IDs unchanged. | Low becomes 5, the total becomes 7, or a second Low bucket appears. |

**Evidence and limits.** SOLR-17649 reports the empty public result from 9.4 onward and earlier success on 8.x. The merged test issues a local query against six documents with shuffled insertion order. It asserts the response for distinct labels per document. Duplicate values are an additional prediction. A correct top-level count of six alone says nothing about the buckets. [Original issue](https://issues.apache.org/jira/browse/SOLR-17649) · [Regression](https://github.com/apache/solr/blob/f66aa9ed07fa76b5db45186073a9b2ac20c01fd4/solr/core/src/test/org/apache/solr/search/facet/TestJsonFacets.java#L4911-L4940)

**Technical notes.** The `solr/core` fixture needs type `solr.EnumFieldType`, enum name `severity`, the `enumsConfig.xml` mapping, and a field with `indexed`, `multiValued` and `docValues` enabled. The field type emits `SortedNumericDocValuesField` for this schema. Keep the default count-descending sort for the main observation because facet method selection also depends on sort. [Schema](https://github.com/apache/solr/blob/f66aa9ed07fa76b5db45186073a9b2ac20c01fd4/solr/core/src/test-files/solr/collection1/conf/schema_latest.xml) · [Enum labels](https://github.com/apache/solr/blob/f66aa9ed07fa76b5db45186073a9b2ac20c01fd4/solr/core/src/test-files/solr/collection1/conf/enumsConfig.xml) · [Field encoding](https://github.com/apache/solr/blob/f66aa9ed07fa76b5db45186073a9b2ac20c01fd4/solr/core/src/java/org/apache/solr/schema/EnumFieldType.java#L194-L210) · [Build](https://github.com/apache/solr/blob/f66aa9ed07fa76b5db45186073a9b2ac20c01fd4/solr/core/build.gradle)

**Sources.** [Facet processor selection](https://github.com/apache/solr/blob/f66aa9ed07fa76b5db45186073a9b2ac20c01fd4/solr/core/src/java/org/apache/solr/search/facet/FacetField.java#L115-L173) · [JSON Facet API](https://github.com/apache/solr/blob/f66aa9ed07fa76b5db45186073a9b2ac20c01fd4/solr/solr-ref-guide/modules/query-guide/pages/json-facet-api.adoc)

## apache/commons-csv#613 · Commons CSV — resume at the byte offset of a record after an emoji delimiter

**Change and revisions.** Byte tracking now accounts for surrogate pairs consumed during multi-character delimiter lookahead. A consumer needs a position counted in the same encoding as the saved CSV. [Merged PR #613](https://github.com/apache/commons-csv/pull/613) · [Landed comparison](https://github.com/apache/commons-csv/compare/d8e12423b47109c76196bbae454726a114cf7c07...871f7457b9373c8668a2324f4d662b18e74d63d3)

Before `d8e12423b47109c76196bbae454726a114cf7c07` → after `871f7457b9373c8668a2324f4d662b18e74d63d3`.

**Public scenario.** Encode `ax😀b\ncx😀d\n` as UTF-8, where `\n` is LF. Configure `CSVFormat.DEFAULT.builder().setDelimiter("x😀").get()`. Open `CSVParser.builder().setInputStream(new ByteArrayInputStream(bytes)).setCharset(UTF_8).setFormat(format).setTrackBytes(true).get()`. Consume its public iterator through exhaustion. For each record, read its size, fields by index and `getBytePosition()`.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-csv#613.1 · Intent | Two LF-terminated records as above. | CSV-329 reports a coding failure during the parent-era lookahead. On the merge expect exactly `[a,b]` at 0 and `[c,d]` at 8. | The bytes before the second row are three ASCII letters, one four-byte emoji and LF. | The merge throws, returns different fields, or reports a second position other than 8. |
| apache/commons-csv#613.2 · Control | Replace every delimiter by ASCII `x` in both the input and the format. | Both revisions return the same two pairs at positions 0 and 4. | The prefix is now the four bytes for `axb\n`. | Either parse fails or disagrees with those fields or offsets. |
| apache/commons-csv#613.3 · Challenge | Keep the emoji delimiter, use CRLF for both record endings, and open a fresh parser on the original byte array sliced at the second reported offset. | On the merge, the second offset is 9. The suffix parser starts with `[c,d]` at its local position 0, then reaches EOF. | Inserting CR before the first LF adds one byte before `c`. Independent suffix readback checks whether a consumer can use the checkpoint. | The full parse succeeds but the offset differs, or the resumed parser loses or changes a field. |

**Evidence and limits.** CSV-329 reports `CharacterCodingException` from the one-row `StringReader` fixture. The landed test reads both rows with package-level `nextRecord()`. The public iterator goes through Commons IO’s `Uncheck.get`, so a caller may see the I/O failure wrapped. The stream, iterator and CRLF suffix histories are predictions. Field-only comparisons miss a valid-looking parse with an unusable checkpoint. [Original report](https://issues.apache.org/jira/browse/CSV-329)

**Technical notes.** The root Maven module declares `commons-io:commons-io:2.22.0`. Its buffered peek is on the reported path. Both the decoder and byte accounting must use UTF-8, and the suffix parser must use the same delimiter and start with the default zero offset.

**Sources.** [Reader](https://github.com/apache/commons-csv/blob/871f7457b9373c8668a2324f4d662b18e74d63d3/src/main/java/org/apache/commons/csv/ExtendedBufferedReader.java) · [Parser iterator](https://github.com/apache/commons-csv/blob/871f7457b9373c8668a2324f4d662b18e74d63d3/src/main/java/org/apache/commons/csv/CSVParser.java) · [Byte position contract](https://github.com/apache/commons-csv/blob/871f7457b9373c8668a2324f4d662b18e74d63d3/src/main/java/org/apache/commons/csv/CSVRecord.java) · [Landed regression](https://github.com/apache/commons-csv/blob/871f7457b9373c8668a2324f4d662b18e74d63d3/src/test/java/org/apache/commons/csv/CSVParserTest.java) · [Maven descriptor](https://github.com/apache/commons-csv/blob/871f7457b9373c8668a2324f4d662b18e74d63d3/pom.xml)

## FasterXML/jackson-dataformats-text#625 · Jackson CSV #625 — detect the end of schema-less row iteration

**Change and revisions.** When the parser finishes an array with no named columns, it must resume reading unnamed values. Returning to the named-column state could make an iterator advertise another row at end of input. [Merged PR #625](https://github.com/FasterXML/jackson-dataformats-text/pull/625) · [Landed comparison](https://github.com/FasterXML/jackson-dataformats-text/compare/fa7e1968282c288589a10af35c45709b01c35421...1600e2068acdb983ace981ff943aa4cdd0a2ac81)

Before `fa7e1968282c288589a10af35c45709b01c35421` → after `1600e2068acdb983ace981ff943aa4cdd0a2ac81`.

**Public scenario.** Build CsvMapper.builder().build(). Obtain mapper.readerFor(String[].class).without(CsvReadFeature.WRAP_AS_ARRAY). Supply the seven-character CSV string `"te,st"` with both enclosing double quotes and no line terminator to readValues. On the MappingIterator<String[]>, call hasNextValue(), nextValue(), hasNextValue() and hasNext(), in that order.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| FasterXML/jackson-dataformats-text#625.1 · Intent | Read the sole quoted cell, then look ahead twice | The parent is reported to misdetect exhaustion after reading the first row. The merge should produce true, the one-element String[] {"te,st"}, false, false. | The comma is inside a quoted field and the closing quote is the last input character. The landed regression checks both lookahead methods. | A second advertised row, exception at normal EOF, or a split first cell. |
| FasterXML/jackson-dataformats-text#625.2 · Control | Give the reader an explicit two-column schema for a bean with public int age and String name fields, in that order. Read `13,"Joe"` and consume the iterator. | Both pins should yield exactly one bean with age 13 and name Joe followed by false. | The two named columns use the named-entry path. The upstream named-schema multiline test also checks exhaustion. | A wrong property value or a further advertised bean on either revision. |
| FasterXML/jackson-dataformats-text#625.3 · Challenge | Keep the schema-less reader and first quoted cell. Append LF and `"x""y"` with no final newline. Call hasNextValue() twice before consuming each row. | On the merge both lookaheads are true for each real row. The decoded rows are ["te,st"] then [x"y]. Both lookahead methods return false after the second row. | An unquoted LF separates records. Two double quotes inside a quoted field encode one quote. Lookahead on a Java iterator must preserve the next element. | Lookahead skips the second row, splits the first at the comma or advertises a third row. |

**Evidence and limits.** Issue #9 reports incorrect end detection. The parent’s TestParserQuotes already asserts the first cell and comments out the exhaustion assertion. The landed tests exercise a public MappingIterator. The two-record, repeated-lookahead result is a prediction. Reading only nextValue() once misses the defect even when the first row decodes perfectly.

**Technical notes.** Use the csv Maven module, tools.jackson.dataformat:jackson-dataformat-csv, with its tools.jackson.core:jackson-databind dependency providing MappingIterator. The parent project version in this tree is 3.2.0-SNAPSHOT. Keep the Jackson 3 package names and the explicit wrapping setting.

**Sources.** [Issue](https://github.com/FasterXML/jackson-dataformats-text/issues/9) · [Parser](https://github.com/FasterXML/jackson-dataformats-text/blob/1600e2068acdb983ace981ff943aa4cdd0a2ac81/csv/src/main/java/tools/jackson/dataformat/csv/CsvParser.java) · [Public mapper](https://github.com/FasterXML/jackson-dataformats-text/blob/1600e2068acdb983ace981ff943aa4cdd0a2ac81/csv/src/main/java/tools/jackson/dataformat/csv/CsvMapper.java) · [Iterator regression](https://github.com/FasterXML/jackson-dataformats-text/blob/1600e2068acdb983ace981ff943aa4cdd0a2ac81/csv/src/test/java/tools/jackson/dataformat/csv/deser/MappingIteratorEnd9Test.java) · [Named-schema control](https://github.com/FasterXML/jackson-dataformats-text/blob/1600e2068acdb983ace981ff943aa4cdd0a2ac81/csv/src/test/java/tools/jackson/dataformat/csv/deser/TestParserQuotes.java) · [CSV module](https://github.com/FasterXML/jackson-dataformats-text/blob/1600e2068acdb983ace981ff943aa4cdd0a2ac81/csv/pom.xml)
