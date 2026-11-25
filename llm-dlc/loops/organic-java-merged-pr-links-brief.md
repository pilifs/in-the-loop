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
