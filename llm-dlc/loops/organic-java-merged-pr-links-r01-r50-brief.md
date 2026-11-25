# Organic Java R01–R50 — changes observable through public APIs

## Objective

Determine what each merged change lets a Java caller observe, which results should stay the same on both revisions, and where an independent use of the result could contradict the upstream regression. Compare the pinned revisions using the public histories below.

## eclipse-collections/eclipse-collections#1786 · A throwing value update leaves the map usable

**Change and revisions.** [Merged PR #1786](https://github.com/eclipse-collections/eclipse-collections/pull/1786). Compute the proposed value before publishing the missing key in both mutable map implementations. Before `3b3c55a47406ca11ece6c077b96c9564f73dfc53`, after `4af700cda608e6817d7d17ab340b91442278cf14`. [Landed comparison](https://github.com/eclipse-collections/eclipse-collections/compare/3b3c55a47406ca11ece6c077b96c9564f73dfc53...4af700cda608e6817d7d17ab340b91442278cf14).

**Public scenario.** Create an empty UnifiedMap. Call updateValue(4, factory, increment), where the factory throws a saved RuntimeException. Catch it, inspect size, containsKey and entrySet, then retry with a factory returning 5. Repeat with UnifiedMapWithHashingStrategy and a strategy using ordinary integer equality.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| eclipse-collections/eclipse-collections#1786.1 · Intent | Update absent key 4 in an empty map with the throwing factory. | The parent can publish key 4 before the throw. On the merge the same exception object escapes, size is zero, containsKey(4) is false and iteration is empty. | An update that supplies no value should leave the original mapping intact. Both pinned implementations move the key write. | A caught sentinel accompanied by a visible key, an entry or a nonzero size on the merge. |
| eclipse-collections/eclipse-collections#1786.2 · Control | Start with 4 mapped to 9. Supply a factory that counts calls and an updater returning its argument plus one. | Both return 10, retain exactly 4→10 and leave the factory count at zero. | A present key supplies its current value directly. | Either map invokes the factory, inserts another entry or returns a value different from get(4). |
| eclipse-collections/eclipse-collections#1786.3 · Challenge | Seed a strategy map with 1→7. Use a constant hash and integer equality. For absent key 4, let updateValueWith obtain 5 and then throw in its binary function. Retry with parameter 2 and addition. | On the merge the catch sees only 1→7. The retry returns 7 and entry iteration then yields exactly 1→7 and 4→7, in either order. | Colliding keys are distinct under equality. A fresh update after failure must still take the absent-key path. | The original key changes, retry sees a phantom value, or size and entries disagree. |

**Evidence and limits.** The pinned tests check exception identity, membership, contents and size. The MutableMapIterable Javadoc explicitly promises the previous map state if either callback throws. Merely catching the exception misses a key published with no value. The colliding-key retry is a prediction.

**Technical notes.** Use the Maven eclipse-collections implementation with the matching eclipse-collections-api. The standard and strategy maps have distinct insertion code. Keep callbacks free of other map mutations.

**Sources.** [MutableMapIterable.java](https://github.com/eclipse-collections/eclipse-collections/blob/4af700cda608e6817d7d17ab340b91442278cf14/eclipse-collections-api/src/main/java/org/eclipse/collections/api/map/MutableMapIterable.java) · [UnifiedMap.java](https://github.com/eclipse-collections/eclipse-collections/blob/4af700cda608e6817d7d17ab340b91442278cf14/eclipse-collections/src/main/java/org/eclipse/collections/impl/map/mutable/UnifiedMap.java) · [UnifiedMapWithHashingStrategy.java](https://github.com/eclipse-collections/eclipse-collections/blob/4af700cda608e6817d7d17ab340b91442278cf14/eclipse-collections/src/main/java/org/eclipse/collections/impl/map/strategy/mutable/UnifiedMapWithHashingStrategy.java) · [MutableMapIterableTestCase.java](https://github.com/eclipse-collections/eclipse-collections/blob/4af700cda608e6817d7d17ab340b91442278cf14/unit-tests-java8/src/test/java/org/eclipse/collections/test/map/mutable/MutableMapIterableTestCase.java) · [pom.xml](https://github.com/eclipse-collections/eclipse-collections/blob/4af700cda608e6817d7d17ab340b91442278cf14/eclipse-collections/pom.xml).

## apache/commons-collections#688 · A rejected unique key leaves both collection views intact

**Change and revisions.** [Merged PR #688](https://github.com/apache/commons-collections/pull/688). Adding a value with an occupied transformed key used to mutate the caller’s collection before rejecting it. A unique index now checks the key first. Before `dad2ff61e516a601da8179708959263e38af8d68`, after `ca83f8699e10403be6987b92fb1a877743df8262`. [Landed comparison](https://github.com/apache/commons-collections/compare/dad2ff61e516a601da8179708959263e38af8d68...ca83f8699e10403be6987b92fb1a877743df8262).

**Public scenario.** Wrap an empty mutable list of strings with `IndexedCollection.uniqueIndexedCollection(list, Integer::valueOf)`. Add `"01"`, attempt to add `"1"`, catch the rejection, then read the original list, the decorator’s iterator and its integer-key lookup. Keep the list reference so the two reads are independent.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-collections#688.1 · Intent | Add the two distinct strings in that order under unique indexing. | Both should throw IllegalArgumentException on the second add. The PR reports that the parent nevertheless appends the second string. On the merge the list and iteration must contain only `"01"`, and `get(1)` must return `"01"`. | Both spellings denote integer key 1. The caller-owned list reveals a write even if the old index still returns its original value. | Merged code accepts the second string, changes either view, or loses the original mapping. |
| apache/commons-collections#688.2 · Control | Use distinct keys by adding `"01"` and `"2"` to a fresh unique wrapper. | Both adds succeed on each revision. The list is precisely those two strings, and lookups at 1 and 2 return the corresponding original spellings. | The two transformed keys are mathematically distinct, and the backing list preserves insertion order. | A valid add is rejected, or iteration and lookup disagree. |
| apache/commons-collections#688.3 · Challenge | After the rejected add, call `reindex()` on the same wrapper and then add `"2"`. | On the merge reindex should finish, add should succeed and both lookups should match the two values in the list. A leftover duplicate on the parent predicts another rejection during reindex. | Rebuilding solely from the caller-owned collection independently checks whether the earlier exception left a valid unique index. | On the merge reindex throws, a spurious entry reappears, or either surviving value is unreachable. |

**Evidence and limits.** The PR reports the exception after mutation and names the regression for `"01"` and `"1"`. Catching the exception or looking only at the first indexed value misses the corrupted backing list. Rebuilding and performing a later valid add are predictions. [Original COLLECTIONS-892 report](https://issues.apache.org/jira/browse/COLLECTIONS-892)

**Technical notes.** Apache Commons Collections uses its root Maven project. Supply an initially empty, ordered ArrayList and a deterministic transformer. An external write to the list would invalidate the premise.

**Sources.** [IndexedCollection.java](https://github.com/apache/commons-collections/blob/ca83f8699e10403be6987b92fb1a877743df8262/src/main/java/org/apache/commons/collections4/collection/IndexedCollection.java) · [IndexedCollectionTest.java](https://github.com/apache/commons-collections/blob/ca83f8699e10403be6987b92fb1a877743df8262/src/test/java/org/apache/commons/collections4/collection/IndexedCollectionTest.java) · [pom.xml](https://github.com/apache/commons-collections/blob/ca83f8699e10403be6987b92fb1a877743df8262/pom.xml).

## vavr-io/vavr#3276 · A remapping that yields null still reports a present key

**Change and revisions.** [Merged PR #3276](https://github.com/vavr-io/vavr/pull/3276). A present key whose remapping function returns null now produces a defined result option alongside the updated persistent map. Before `f74004d3cef44fcccc7996783d34f734ba25ffd3`, after `2b77936d4788fee24b99e8a372fd93923d8b6c12`. [Landed comparison](https://github.com/vavr-io/vavr/compare/f74004d3cef44fcccc7996783d34f734ba25ffd3...2b77936d4788fee24b99e8a372fd93923d8b6c12).

**Public scenario.** Start with Vavr’s immutable `HashMap.of(1, "v")`. Call `computeIfPresent(1, (k,v) -> null)`, retaining the original receiver. Inspect the tuple’s first option and query key 1 on its second component.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| vavr-io/vavr#3276.1 · Intent | Remap key 1 to null. | Before, the first component is `None`. After, `isDefined()` is true and `get()` is null. Both resulting maps contain key 1 with a null value. | The public map contract returns Some for an associated value. The pinned regression compares both tuple components. | The merge returns an empty option, drops key 1, or supplies a non-null value. |
| vavr-io/vavr#3276.2 · Control | Use missing key 2 and a callback that counts invocations. | On both, the option is empty, the count stays zero, and the returned map still contains exactly the original entry. | The callback is conditional on key membership. | The callback runs, key 2 appears, or key 1 changes. |
| vavr-io/vavr#3276.3 · Challenge | On the map returned by the null remap, call `computeIfPresent(1, ...)` again. Record its callback arguments and return "restored". | On both, the second callback receives (1,null) once, both its option and the final map contain "restored", and the original map still yields "v". | A second lookup distinguishes a stored null from absence. The original receiver provides an independent check of persistent updates. | The second callback is skipped, receives the old value, or lookup on the original now yields null. |

**Evidence and limits.** The one-line change switches the option constructor. The new abstract map regression checks tuple equality. Merely inspecting the updated map would pass on the parent too. The two-call history remains a prediction.

**Technical notes.** Use the Vavr collection module and its own Option and Tuple2 types. A Java Map remapping function has a different null contract.

**Sources.** [Map.java](https://github.com/vavr-io/vavr/blob/2b77936d4788fee24b99e8a372fd93923d8b6c12/vavr/src/main/java/io/vavr/collection/Map.java) · [Maps.java](https://github.com/vavr-io/vavr/blob/2b77936d4788fee24b99e8a372fd93923d8b6c12/vavr/src/main/java/io/vavr/collection/Maps.java) · [AbstractMapTest.java](https://github.com/vavr-io/vavr/blob/2b77936d4788fee24b99e8a372fd93923d8b6c12/vavr/src/test/java/io/vavr/collection/AbstractMapTest.java) · [pom.xml](https://github.com/vavr-io/vavr/blob/2b77936d4788fee24b99e8a372fd93923d8b6c12/vavr/pom.xml).

## vigna/fastutil#325 · Copy a primitive immutable list into a larger array

**Change and revisions.** [Merged PR #325](https://github.com/vigna/fastutil/pull/325). Limit the primitive array copy to the number of list elements. Before `faa22ac0b26ec1af680ada5eabf94bdedf9c824f`, after `a1840bcc81f0fe2fb495856dded719125d869242`. [Landed comparison](https://github.com/vigna/fastutil/compare/faa22ac0b26ec1af680ada5eabf94bdedf9c824f...a1840bcc81f0fe2fb495856dded719125d869242).

**Public scenario.** Create IntImmutableList.of(0,1,2,3) and a five-element int array filled with 77. Call toArray(destination), compare references, inspect all cells, then read the list through getInt.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| vigna/fastutil#325.1 · Intent | Pass the five-element array to the four-element immutable list. | The PR reports ArrayIndexOutOfBoundsException before. Afterward the result is the destination and begins [0,1,2,3]. | Four source elements fit into five slots. The primitive driver returns its chosen array. | An exception, a different returned reference, or the wrong prefix on the merge. |
| vigna/fastutil#325.2 · Control | Pass a two-element array filled with 77. | Both should return a separate four-element [0,1,2,3] and leave the short destination intact. | The existing branch allocates when the supplied array cannot hold the list. | A truncated list, reuse of the short array or a changed caller sentinel. |
| vigna/fastutil#325.3 · Challenge | On the merge compare five- and seven-element destinations with different nonzero suffixes. Mutate destination[0] after each copy. | Each suffix retains its original values under the pinned copy implementation. The list still returns 0 at index 0. | The copied interval is [0,4). Later writes to a caller-owned copy cannot mutate immutable list storage. | A zeroed or overwritten spare cell, or getInt(0) follows the caller's write. |

**Evidence and limits.** The landed mutable and immutable int tests compare a five-cell array against [0,1,2,3,0]. A fresh zero-filled array conceals an unwanted suffix write. The sentinel observation concerns this implementation.

**Technical notes.** fastutil generates its primitive implementations from drv/ImmutableList.drv. Exercise the generated int specialization and its primitive int[] overload. The boxed Object[] overload has different conventions.

**Sources.** [ImmutableList.drv](https://github.com/vigna/fastutil/blob/a1840bcc81f0fe2fb495856dded719125d869242/drv/ImmutableList.drv) · [IntArrayListTest.java](https://github.com/vigna/fastutil/blob/a1840bcc81f0fe2fb495856dded719125d869242/test/it/unimi/dsi/fastutil/ints/IntArrayListTest.java) · [IntImmutableListTest.java](https://github.com/vigna/fastutil/blob/a1840bcc81f0fe2fb495856dded719125d869242/test/it/unimi/dsi/fastutil/ints/IntImmutableListTest.java) · [build.xml](https://github.com/vigna/fastutil/blob/a1840bcc81f0fe2fb495856dded719125d869242/build.xml).

## google/guava#8811 · Rotating a primitive subarray by the smallest integer distance

**Change and revisions.** [Merged PR #8811](https://github.com/google/guava/pull/8811). Guava changes distance normalization in its primitive array rotation methods so the most negative int has its mathematical meaning. The JRE and Android sources both carry the change. Before `efae76a11d06cff9bd2a9d0865e0e4cfe554804d`, after `c0a8a1edc69393e8141424037571d9825f5fc0f4`. [Landed comparison](https://github.com/google/guava/compare/efae76a11d06cff9bd2a9d0865e0e4cfe554804d...c0a8a1edc69393e8141424037571d9825f5fc0f4).

**Public scenario.** Start with the distinct int values 1, 2, 3. Call `Ints.rotate(array, Integer.MIN_VALUE)` and inspect every slot of the same array. Compare with `Collections.rotate` on a separate mutable boxed list initialized from the original values.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| google/guava#8811.1 · Intent | Rotate [1,2,3] by Integer.MIN_VALUE. | The PR reports [2,3,1] on the parent. Expect [3,1,2] on the merge. | −2147483648 has remainder 1 modulo 3 in the mathematical sense. A right rotation by one moves the last element to the front. | Any merged array differing from [3,1,2], even if it retains all three values. |
| google/guava#8811.2 · Control | Rotate a fresh [1,2,3] by −1. | Both revisions should produce [2,3,1]. | The value at index 1 moves to index 0 under a one-place left rotation. This distance can be negated exactly. | A reversed direction, lost element, or exception on either revision. |
| google/guava#8811.3 · Challenge | In [9,1,2,3,4,5,8], rotate only the half-open range [1,6) by Integer.MIN_VALUE. Box the original middle five and rotate that list independently. | On the merge expect [9,4,5,1,2,3,8]. Vary the two outside sentinels independently and the five middle results must stay fixed. | The distance is congruent to 2 modulo 5. Only the subrange participates in its period and its permutation. | The boxed and primitive middle ranges disagree, or an outside value moves or affects a middle slot. |

**Evidence and limits.** The PR gives the exact three-element parent result and cites the documented Collections.rotate equivalence. Its primitive tests exercise the extreme argument. A length-two fixture would conceal the sign reversal because both directions give the same permutation.

**Technical notes.** The linked `Ints` implementation and test target the JRE module. Android and seven other primitive specializations also changed. A result for one artifact and primitive type covers that pair.

**Sources.** [Ints.java](https://github.com/google/guava/blob/c0a8a1edc69393e8141424037571d9825f5fc0f4/guava/src/com/google/common/primitives/Ints.java) · [IntsTest.java](https://github.com/google/guava/blob/c0a8a1edc69393e8141424037571d9825f5fc0f4/guava-tests/test/com/google/common/primitives/IntsTest.java) · [Ints.java](https://github.com/google/guava/blob/c0a8a1edc69393e8141424037571d9825f5fc0f4/android/guava/src/com/google/common/primitives/Ints.java) · [pom.xml](https://github.com/google/guava/blob/c0a8a1edc69393e8141424037571d9825f5fc0f4/guava/pom.xml) · [Related PR #8807](https://github.com/google/guava/pull/8807).

## apache/commons-lang#1865 · Representable quotients at the signed integer boundary

**Change and revisions.** [Merged PR #1865](https://github.com/apache/commons-lang/pull/1865). Fraction division reduces the two products before checking whether the resulting numerator and positive denominator fit in int. Before `ef7586831c7842c97ad4be8693ddef6f94bb8b64`, after `355f246760cad21ca597424b49bb1151c0a63a96`. [Landed comparison](https://github.com/apache/commons-lang/compare/ef7586831c7842c97ad4be8693ddef6f94bb8b64...355f246760cad21ca597424b49bb1151c0a63a96).

**Public scenario.** Construct fractions with `Fraction.getFraction(int,int)`. Call `divideBy` and inspect `getNumerator()` and `getDenominator()` on the result. Let m be Integer.MIN_VALUE.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-lang#1865.1 · Intent | Divide m/1 by m/1. | The PR reports ArithmeticException before. After, the result has numerator 1 and denominator 1. | A nonzero rational divided by itself is one, although its reciprocal alone needs a denominator of 2³¹. | An exception or any pair other than (1,1) on the merge. |
| apache/commons-lang#1865.2 · Control | Divide 1/1 by m/1, then separately divide 3/4 by 1/2. | Both revisions should throw ArithmeticException for the first and return 3/2 for the second. | The first exact denominator exceeds Integer.MAX_VALUE. Twice three quarters is three halves. | A wrapped denominator, an exception on the small inputs, or different reduced components. |
| apache/commons-lang#1865.3 · Challenge | Hold the dividend at 1/1. Express the same divisor as m/2 and as −1073741824/1. | After, both give (−1,1073741824). Before, the first representation is predicted to throw while the second succeeds. | Dividing the first divisor’s numerator and denominator by two gives the second representation exactly. | Equal rational divisors produce different merged outcomes, or both silently round to zero. |

**Evidence and limits.** The PR reports ten formerly failing boundary-test invocations and a separate BigInteger comparison. The landed test checks exact components and genuine overflow. Checking only a double approximation could hide a wrong denominator.

**Technical notes.** Commons Lang packages Fraction under org.apache.commons.lang3.math. Use the two-int getFraction overload to preserve the unreduced representation. The PR reports a JDK 25 build targeting Java 8.

**Sources.** [Fraction.java](https://github.com/apache/commons-lang/blob/355f246760cad21ca597424b49bb1151c0a63a96/src/main/java/org/apache/commons/lang3/math/Fraction.java) · [FractionTest.java](https://github.com/apache/commons-lang/blob/355f246760cad21ca597424b49bb1151c0a63a96/src/test/java/org/apache/commons/lang3/math/FractionTest.java) · [pom.xml](https://github.com/apache/commons-lang/blob/355f246760cad21ca597424b49bb1151c0a63a96/pom.xml).

## locationtech/jts#1168 · Deep-clone a coordinate sequence without duplicating its points

**Change and revisions.** [Merged PR #1168](https://github.com/locationtech/jts/pull/1168). Replace each shallow coordinate reference in the cloned list with a copied coordinate. Before `45744222b0b8a861c44dbc2c03dcf4f1e85c27fd`, after `c406f5abe914d471ceb9cf0b872e8a634a1a1be6`. [Landed comparison](https://github.com/locationtech/jts/compare/45744222b0b8a861c44dbc2c03dcf4f1e85c27fd...c406f5abe914d471ceb9cf0b872e8a634a1a1be6).

**Public scenario.** Construct a CoordinateList from (0,0), (1,1), (2,2), allowing repeated coordinates. Cast clone() to CoordinateList. Read size and toCoordinateArray(true) and change the middle coordinate of the clone.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| locationtech/jts#1168.1 · Intent | Clone the three-point list and enumerate in forward order. | Issue #1163 reports a doubled list, predicting six entries for these three inputs on the parent. The merge should return exactly the original three coordinate values in order. | Copying a sequence preserves its number of positions. The issue identifies the shallow list followed by indexed insertions. | The merge returns six points, drops a point or reorders unequal coordinates. |
| locationtech/jts#1168.2 · Control | Clone an empty list and append (4,5) to the clone. | On both revisions the original remains empty and the clone contains only (4,5). | An empty list has no coordinate references to duplicate. The two list containers are independent. | The original changes size or the clone gains a second entry. |
| locationtech/jts#1168.3 · Challenge | Clone a list containing two distinct Coordinate objects with equal XY values, preserving repetitions. Write x=9 to the first coordinate of the clone. | On the merge the clone still has two positions. Only its first x changes. Both original points and the second cloned point keep their prior x. | Multiplicity is part of the ordered list. Deep copying must isolate subsequent coordinate mutations. | An equal-valued point is collapsed, or changing one position changes any original or the other cloned coordinate. |

**Evidence and limits.** The merged JTS regression compares the forward coordinate values and length. Value equality immediately after cloning cannot establish independent mutable Coordinates. The repeated-point mutation extends the regression.

**Technical notes.** Use the JTS core Maven module, concrete CoordinateList and mutable Coordinate objects. Enable repeated points when constructing the two-equal-point fixture.

**Sources.** [CoordinateList.java](https://github.com/locationtech/jts/blob/c406f5abe914d471ceb9cf0b872e8a634a1a1be6/modules/core/src/main/java/org/locationtech/jts/geom/CoordinateList.java) · [CoordinateListTest.java](https://github.com/locationtech/jts/blob/c406f5abe914d471ceb9cf0b872e8a634a1a1be6/modules/core/src/test/java/org/locationtech/jts/geom/CoordinateListTest.java) · [pom.xml](https://github.com/locationtech/jts/blob/c406f5abe914d471ceb9cf0b872e8a634a1a1be6/modules/core/pom.xml) · [Issue #1163](https://github.com/locationtech/jts/issues/1163).

## jgrapht/jgrapht#1379 · Edits to a listened-to graph keep connectivity queries current

**Change and revisions.** [Merged PR #1379](https://github.com/jgrapht/jgrapht/pull/1379). The inspector now handles vertex and edge notifications before all connected sets have been computed. An edge can also invalidate a component cached by a single-vertex query. Before `fabfabe6f279c0dd61b417a543d33d94fd039249`, after `955e5cfb9b22d7ac2ef956849523d22041baf730`. [Landed comparison](https://github.com/jgrapht/jgrapht/compare/fabfabe6f279c0dd61b417a543d33d94fd039249...955e5cfb9b22d7ac2ef956849523d22041baf730).

**Public scenario.** Wrap a simple graph in a DefaultListenableGraph. Construct a ConnectivityInspector for that same wrapper and register it using addGraphListener. Keep all modifications on the wrapper. Observe the exceptions from mutations as well as the answers to connectedSetOf, pathExists and connectedSets.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| jgrapht/jgrapht#1379.1 · Intent | Register on an empty graph, add vertices a and b, add their edge, then ask for a’s component. | Issue #1162 reports a NullPointerException on listener updates with uninitialized state. On the merge each mutation must return normally and the component must be {a,b}. | There are only two vertices and one connecting edge. The component can be enumerated without any cache. | A merged mutation throws, or querying a omits b or includes anything else. |
| jgrapht/jgrapht#1379.2 · Control | Start with vertices a,b,c and edge a–b. Register on that graph, call connectedSets(), then add b–c. | Both revisions should report one component {a,b,c} and pathExists(a,c) should be true. | The path a,b,c witnesses connectivity after insertion. Set enumeration order has no bearing on reachability. | A full-cache update throws or any vertex is absent from the component. |
| jgrapht/jgrapht#1379.3 · Challenge | With the same three initial vertices and a–b, query only connectedSetOf(a), add b–c, and query a again. Repeat with the edge directed from c to b on a directed graph. | On the merge a's component should become {a,b,c} in both histories, and agree with a fresh inspector on each final graph. | The inspector defines weak connectivity for directed graphs. Query order and edge orientation cannot partition this underlying connected graph. | Only the reused inspector remains at {a,b}, or reversing the edge changes the weak component. |

**Evidence and limits.** The linked issue documents the listener exception. The PR reports eight regressions failing before and the connectivity suite passing after. Merely registering without an exception leaves the stale-single-component question unanswered.

**Technical notes.** The public API and regression belong to jgrapht-core. Use a simple graph with explicit distinct vertices and a DefaultEdge supplier. Match connected components as sets, using fresh queries after each mutation.

**Sources.** [ConnectivityInspector.java](https://github.com/jgrapht/jgrapht/blob/955e5cfb9b22d7ac2ef956849523d22041baf730/jgrapht-core/src/main/java/org/jgrapht/alg/connectivity/ConnectivityInspector.java) · [ConnectivityInspectorTest.java](https://github.com/jgrapht/jgrapht/blob/955e5cfb9b22d7ac2ef956849523d22041baf730/jgrapht-core/src/test/java/org/jgrapht/alg/connectivity/ConnectivityInspectorTest.java) · [pom.xml](https://github.com/jgrapht/jgrapht/blob/955e5cfb9b22d7ac2ef956849523d22041baf730/jgrapht-core/pom.xml) · [Issue #1162](https://github.com/jgrapht/jgrapht/issues/1162).

## google/guava#8801 · Cycle detection in a disconnected undirected graph

**Change and revisions.** [Merged PR #8801](https://github.com/google/guava/pull/8801). Graphs.hasCycle continues to examine the remaining neighbors after encountering the edge by which it reached a vertex. Before `ae0fa4bdaeef91c6f309c886263eb3b319b21568`, after `ca8aedb2fdaf40fd6937a0643180aea51ca4154e`. [Landed comparison](https://github.com/google/guava/compare/ae0fa4bdaeef91c6f309c886263eb3b319b21568...ca8aedb2fdaf40fd6937a0643180aea51ca4154e).

**Public scenario.** Build an undirected MutableGraph<Integer> with GraphBuilder. Insert edges (1,2), (2,3), (3,1), then add isolated vertex 4. Call Graphs.hasCycle(graph). Use distinct nodes and no parallel edges.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| google/guava#8801.1 · Intent | Triangle plus isolated vertex, as in the pinned test. | The PR reports a possible false negative on the parent when a vertex enumerates its parent first. The merge must return true for every neighbor order. | The three edges form the explicit closed walk 1–2–3–1 with no repeated edge. | The merged call returns false for this triangle. |
| google/guava#8801.2 · Control | Remove only (3,1), leaving the isolated vertex and path 1–2–3. | Both revisions should return false. | A return traversal on this path would necessarily reuse an undirected edge. | Either call reports a cycle after removing the closing edge. |
| google/guava#8801.3 · Challenge | Reinsert (3,1). Compare the same graph first without vertex 4, then with 4 and a separate acyclic edge (5,6). | The merged answer stays true in both states. The parent may produce true for the connected triangle yet miss the cycle after unrelated vertices are added. | The triangle remains intact. The extra components change the edge-to-node count, which governs the shortcut described by the PR. | Adding the disconnected components changes the merged answer to false. |

**Evidence and limits.** The new assertions run the public method on the disconnected fixture in both Guava source trees. A connected triangle alone satisfies the edge-count shortcut, so its positive answer would leave the traversal untested.

**Technical notes.** The JRE implementation and tests are in guava and guava-tests. The Android distribution carries the same change. Do not require a particular default adjacency iteration order when interpreting a parent result.

**Sources.** [Graphs.java](https://github.com/google/guava/blob/ca8aedb2fdaf40fd6937a0643180aea51ca4154e/guava/src/com/google/common/graph/Graphs.java) · [GraphPropertiesTest.java](https://github.com/google/guava/blob/ca8aedb2fdaf40fd6937a0643180aea51ca4154e/guava-tests/test/com/google/common/graph/GraphPropertiesTest.java) · [Graphs.java](https://github.com/google/guava/blob/ca8aedb2fdaf40fd6937a0643180aea51ca4154e/android/guava/src/com/google/common/graph/Graphs.java) · [pom.xml](https://github.com/google/guava/blob/ca8aedb2fdaf40fd6937a0643180aea51ca4154e/guava/pom.xml) · [Related PR #8796](https://github.com/google/guava/pull/8796).

## jgrapht/jgrapht#1376 · Return a closed tour when edge weights are negative

**Change and revisions.** [Merged PR #1376](https://github.com/jgrapht/jgrapht/pull/1376). Let the farthest-insertion heuristic select a finite negative edge and a finite negative distance to the current tour. Before `e5bc1c06804bd90c5cf549954587728fc8dae101`, after `9fc7edbcc3d1e753bc1863bda0cf1c2f652e083a`. [Landed comparison](https://github.com/jgrapht/jgrapht/compare/e5bc1c06804bd90c5cf549954587728fc8dae101...9fc7edbcc3d1e753bc1863bda0cf1c2f652e083a).

**Public scenario.** Populate a SimpleWeightedGraph with three integer vertices 0, 1 and 2. Assign weights −3, −2 and −1 to edges 01, 02 and 12. Use the default FarthestInsertionHeuristicTSP and call getTour(graph). Examine the returned vertices, edges and total weight.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| jgrapht/jgrapht#1376.1 · Intent | Run the default heuristic on the all-negative triangle. | The PR reports NullPointerException on the parent. The merge should produce a closed three-edge cycle of weight −6 with each vertex present once before closure. | Every Hamiltonian tour of a triangle uses all three edges exactly once, independent of start or direction. | An exception, missing vertex, open walk or returned weight other than −6. |
| jgrapht/jgrapht#1376.2 · Control | Add five to each edge to get weights 2, 3 and 4. | Both revisions should produce a closed tour of weight 9. | The three positive edges admit the same triangle traversal. The independent sum is 9. | Either revision fails or reports a tour other than a traversal of all three edges. |
| jgrapht/jgrapht#1376.3 · Challenge | Use the PR's K4 with weights 01=10, 02=−3, 03=−2, 12=−5, 13=−4, 23=−1. Reconstruct the weight from the returned vertex sequence and the input graph. | The PR reports an index exception on the parent. On the merge the walk should contain all four vertices once before closure and its four traversed edge weights should sum to getWeight(). Any such tour is eligible. | The positive edge allows initialization and leaves only negative candidates for expansion. Public graph readback checks the reported tour independently. | A repeated interior vertex, absent edge or disagreement between reported and reconstructed weight. |

**Evidence and limits.** The regression adds both graph sizes and checks Hamiltonian tours. Success without an exception does not establish that the returned weight describes the path. Neither a unique order nor optimality is required. [Original issue](https://github.com/jgrapht/jgrapht/issues/1324).

**Technical notes.** Use the jgrapht-core Maven module, finite integral double weights and complete undirected graphs. The default constructor exercises initial-edge selection as well as insertion.

**Sources.** [FarthestInsertionHeuristicTSP.java](https://github.com/jgrapht/jgrapht/blob/9fc7edbcc3d1e753bc1863bda0cf1c2f652e083a/jgrapht-core/src/main/java/org/jgrapht/alg/tour/FarthestInsertionHeuristicTSP.java) · [FarthestInsertionHeuristicTSPTest.java](https://github.com/jgrapht/jgrapht/blob/9fc7edbcc3d1e753bc1863bda0cf1c2f652e083a/jgrapht-core/src/test/java/org/jgrapht/alg/tour/FarthestInsertionHeuristicTSPTest.java) · [pom.xml](https://github.com/jgrapht/jgrapht/blob/9fc7edbcc3d1e753bc1863bda0cf1c2f652e083a/jgrapht-core/pom.xml).

## apache/commons-io#931 · Bulk reads and skip count the characters that survive a filter

**Change and revisions.** [Merged PR #931](https://github.com/apache/commons-io/pull/931). The reader now continues past an entirely discarded chunk during a positive-length read. Skipping traverses the filtered stream so discarded characters do not consume the caller’s skip budget. Before `31cc5e824df9726d08cf5ee8154c1721abc2668d`, after `1af75d36371fb56603cccca8bfd8083f5c97d6f2`. [Landed comparison](https://github.com/apache/commons-io/compare/31cc5e824df9726d08cf5ee8154c1721abc2668d...1af75d36371fb56603cccca8bfd8083f5c97d6f2).

**Public scenario.** Construct a CharacterFilterReader over a fresh StringReader with x as the character to remove. Record each read count, the slice actually written, the count returned by skip and the next character. Use a new reader for each history.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-io#931.1 · Intent | Bulk-read xx a (the three characters `xxa`) into a two-character array, then read again. | The PR reports an initial zero before the change. On the merge the first read must return 1 with a at index 0, then −1. | Filtering the entire input leaves exactly the one-character stream a. A positive-length read at its beginning must make progress. | The merged reader returns zero, exposes x, or signals end before delivering a. |
| apache/commons-io#931.2 · Control | Filter x from `abc`. Skip 1, call read(), then read the remaining characters. | Both revisions should report 1 skipped followed by b, then c, then EOF. | No input character is removed. This is the ordinary StringReader sequence after consuming its first character. | Either revision leaks a skipped character, drops c or misreports the count. |
| apache/commons-io#931.3 · Challenge | Filter x from `xaxb`, skip 1 and call read(). Compare with the same history over an independent StringReader on `ab`. Repeat with extra leading x characters. | The PR reports a on the parent for `xaxb`. On the merge each filtered variant must return skip count 1, then b, then EOF. | Deleting x first leaves ab in every case. Skipping its first retained character can only leave b. | Adding discarded input changes the successor, or the reported count is correct while read() still yields a. |

**Evidence and limits.** The PR gives the parent outputs and reports the concrete-reader regressions under JDK 17, including failures with the earlier released artifact. Checking the skip return alone misses a skip that consumes raw input instead of a retained character.

**Technical notes.** Commons IO’s root Maven module contains AbstractCharacterFilterReader and tests of both concrete filters. Use in-memory ASCII input and positive read sizes for the progress claim.

**Sources.** [AbstractCharacterFilterReader.java](https://github.com/apache/commons-io/blob/1af75d36371fb56603cccca8bfd8083f5c97d6f2/src/main/java/org/apache/commons/io/input/AbstractCharacterFilterReader.java) · [AbstractCharacterFilterReaderTest.java](https://github.com/apache/commons-io/blob/1af75d36371fb56603cccca8bfd8083f5c97d6f2/src/test/java/org/apache/commons/io/input/AbstractCharacterFilterReaderTest.java) · [pom.xml](https://github.com/apache/commons-io/blob/1af75d36371fb56603cccca8bfd8083f5c97d6f2/pom.xml).

## apache/commons-io#860 · Skipped characters, bounds, and the underlying reader position

**Change and revisions.** [Merged PR #860](https://github.com/apache/commons-io/pull/860). Positive skip requests are capped by the remaining global bound and the position advances by the count the delegate actually skipped. Before `cfe19ad9dcc9d0c7308e2dc187b2f8b57de21af0`, after `e806e6b5926993ec6348a78542b1e1377a765e88`. [Landed comparison](https://github.com/apache/commons-io/compare/cfe19ad9dcc9d0c7308e2dc187b2f8b57de21af0...e806e6b5926993ec6348a78542b1e1377a765e88).

**Public scenario.** Wrap a StringReader over "012345" in BoundedReader with a maximum of 3. Retain the delegate. For the short-skip control use a FilterReader whose skip(n) forwards at most one character, while read() behaves normally.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-io#860.1 · Intent | On a fresh wrapper, call skip(5), read() on the wrapper, then read() directly from the retained delegate. | Before, expect 5, EOF, and the character 5. After, expect 3, EOF, and the character 3. | Positions in the six distinct input characters identify exactly how many were consumed. The bound leaves the suffix starting at 3. | The wrapper reports 3 yet the delegate now starts at 5, or the wrapper reads past the limit. |
| apache/commons-io#860.2 · Control | Ask the one-character skip delegate to skip(1), then read() twice and once more. | Both revisions should return skip count 1, characters 1 and 2, then EOF. Asking it to skip(3) instead should still leave 1 and 2 on the merge. | Only one character was actually skipped. The bound admits exactly two more. | An early EOF, a repeated character, or an extra fourth character. |
| apache/commons-io#860.3 · Challenge | With a new maximum of 5, mark(2) at position zero. Compare three single-character reads against skip(4) on a separately marked identical reader. | The read path on both should yield 0, 1, EOF. The PR describes a matching read-ahead cap for skip, but landed source predicts a skip count of 4 and a delegate positioned at character 4. | The read predicate checks markedAt and readAheadLimit. The landed skip predicate uses only the global remaining count. Direct delegate read distinguishes positions 2 and 4. | A merged skip count of 2 with delegate readback 2 refutes the predicted discrepancy. A count of 4 contradicts the PR’s stated mark guarantee. |

**Evidence and limits.** The landed tests cover large requests, the hard bound and a short delegate skip. The PR description also says skip respects the mark limit. The landed method and tests leave the marked-path discrepancy visible. A wrapper EOF alone cannot reveal consuming an extra delegate character.

**Technical notes.** The Commons IO org.apache.commons.io.input wrapper uses character counts. Use StringReader, which permits marking and supports independent position readback on its retained reference. The PR links [IO-891](https://issues.apache.org/jira/browse/IO-891).

**Sources.** [BoundedReader.java](https://github.com/apache/commons-io/blob/e806e6b5926993ec6348a78542b1e1377a765e88/src/main/java/org/apache/commons/io/input/BoundedReader.java) · [BoundedReaderTest.java](https://github.com/apache/commons-io/blob/e806e6b5926993ec6348a78542b1e1377a765e88/src/test/java/org/apache/commons/io/input/BoundedReaderTest.java) · [pom.xml](https://github.com/apache/commons-io/blob/e806e6b5926993ec6348a78542b1e1377a765e88/pom.xml).

## google/jimfs#435 · A zero-length file read still returns zero after observed EOF

**Change and revisions.** [Merged PR #435](https://github.com/google/jimfs/pull/435). Honor a zero-length bulk read after a Jimfs stream has already recorded end of file. Before `f0dcab50faa6626b9275d6604a89d7debfff3677`, after `0e5725b4d44ec51d54fba15336aa23147c1bedc7`. [Landed comparison](https://github.com/google/jimfs/compare/f0dcab50faa6626b9275d6604a89d7debfff3677...0e5725b4d44ec51d54fba15336aa23147c1bedc7).

**Public scenario.** Create a Unix Jimfs file system with Jimfs.newFileSystem(Configuration.unix()). Write bytes [1,2,3] through Files.write, open Files.newInputStream, consume the three bytes and make a positive-length read that returns −1. Call read(buffer,2,0) on an open stream and examine the sentinel-filled buffer.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| google/jimfs#435.1 · Intent | After confirmed EOF call read on an eight-byte buffer at offset 2 and length 0. | The parent returns −1 after remembering EOF. The merge returns 0 with all eight cells unchanged. | The InputStream contract cited in #434 specifies zero for a zero-length request. The request covers no cells. | A nonzero return, exception or changed buffer cell on the merge. |
| google/jimfs#435.2 · Control | Before consuming the file, issue the same zero-length read and then read one byte. | Both should return 0 then 1, with all sentinel cells preserved. | Reading zero bytes cannot consume the first byte. | A changed array, a nonzero count or a different first byte. |
| google/jimfs#435.3 · Challenge | On a fresh empty file confirm EOF with read(), then alternate read(buffer,buffer.length,0), read() and another identical empty slice. | The merge should return 0, −1, 0 in order, with unchanged storage. | The endpoint is a valid empty slice. No call can create data in an empty file. | A legal endpoint is rejected, an empty slice reports EOF, or a positive request returns data. |

**Evidence and limits.** The changed JimfsInputStreamTest explicitly reaches EOF before its empty read. The file-system regression adjusts a consumer loop to terminate on a zero count. An empty read only at stream creation misses the remembered EOF branch.

**Technical notes.** The Maven jimfs module supplies the file-system provider. Keep the stream open and offsets valid since the implementation checks bounds and closure separately.

**Sources.** [JimfsInputStream.java](https://github.com/google/jimfs/blob/0e5725b4d44ec51d54fba15336aa23147c1bedc7/jimfs/src/main/java/com/google/common/jimfs/JimfsInputStream.java) · [JimfsInputStreamTest.java](https://github.com/google/jimfs/blob/0e5725b4d44ec51d54fba15336aa23147c1bedc7/jimfs/src/test/java/com/google/common/jimfs/JimfsInputStreamTest.java) · [JimfsUnixLikeFileSystemTest.java](https://github.com/google/jimfs/blob/0e5725b4d44ec51d54fba15336aa23147c1bedc7/jimfs/src/test/java/com/google/common/jimfs/JimfsUnixLikeFileSystemTest.java) · [pom.xml](https://github.com/google/jimfs/blob/0e5725b4d44ec51d54fba15336aa23147c1bedc7/jimfs/pom.xml) · [Issue #434](https://github.com/google/jimfs/issues/434).

## vigna/fastutil#384 · Bulk overwrite advances a repositioned output stream

**Change and revisions.** [Merged PR #384](https://github.com/vigna/fastutil/pull/384). The byte-array write now moves the position by the number of bytes copied even when the write fits entirely within the existing output. Before `a3d44187dca3deb185455274bb877703f2f541fe`, after `cbf3c2ec706d16c56e6896b13ef0b5361be981c8`. [Landed comparison](https://github.com/vigna/fastutil/compare/a3d44187dca3deb185455274bb877703f2f541fe...cbf3c2ec706d16c56e6896b13ef0b5361be981c8).

**Public scenario.** Create a FastByteArrayOutputStream, write bytes [1,2,3,4,5], call position(0), then write [7,8,9] with offset 0 and length 3. Observe position(), length(), and the first length() bytes of the public backing array. Continue with a single-byte write on the same stream.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| vigna/fastutil#384.1 · Intent | Observe immediately after the three-byte overwrite. | Issue #367 reports position 0 for a three-byte overwrite at zero on the parent. The merge should give position 3, length 5 and bytes [7,8,9,4,5]. | An overwrite consumes three positions and stops before the last two bytes. The high-water mark remains five. | Merged bytes look correct but the cursor is zero, or the logical length is truncated. |
| vigna/fastutil#384.2 · Control | From position 5 in a fresh five-byte stream, append two bytes [6,7]. | Both revisions should give position 7, length 7 and contents [1,2,3,4,5,6,7]. | Appending starts at the previous end and extends the stream by precisely two. | Wrong end, missing bytes or corruption of the old prefix. |
| vigna/fastutil#384.3 · Challenge | Follow the three-byte overwrite immediately with write(6). Compare against a fresh stream receiving the same three overwritten bytes via three individual write(int) calls and then write(6). | On the merge both histories should leave [7,8,9,6,5], position 4 and length 5. The parent's stale cursor predicts the last write overwrites index 0 in the bulk history. | Splitting the same bytes across calls should leave their destination and the following write position unchanged. | The two merged streams differ in any logical byte, position or length. |

**Evidence and limits.** The issue reports the position discrepancy. The PR cites a passing FastByteArrayOutputStreamTest after the fix. Inspecting just the three copied bytes would miss the cursor error until a later write overwrites them.

**Technical notes.** The fastutil source lives under src/it/unimi/dsi/fastutil/io with a corresponding JUnit test under test/. Compare only the logical prefix of the exposed array because its capacity is independent of length.

**Sources.** [FastByteArrayOutputStream.java](https://github.com/vigna/fastutil/blob/cbf3c2ec706d16c56e6896b13ef0b5361be981c8/src/it/unimi/dsi/fastutil/io/FastByteArrayOutputStream.java) · [FastByteArrayOutputStreamTest.java](https://github.com/vigna/fastutil/blob/cbf3c2ec706d16c56e6896b13ef0b5361be981c8/test/it/unimi/dsi/fastutil/io/FastByteArrayOutputStreamTest.java) · [build.xml](https://github.com/vigna/fastutil/blob/cbf3c2ec706d16c56e6896b13ef0b5361be981c8/build.xml) · [Issue #367](https://github.com/vigna/fastutil/issues/367).

## apache/commons-codec#437 · The configured Base58 alphabet determines the wire bytes

**Change and revisions.** [Merged PR #437](https://github.com/apache/commons-codec/pull/437). The builder derives its inverse alphabet from the configured 58 distinct bytes. The encoder and decoder also use that alphabet’s zero digit. Before `ac982579962c32ee28be1e80cdb514a829e3366f`, after `98986558dc1c0e2013b76bea92d75bde80568a00`. [Landed comparison](https://github.com/apache/commons-codec/compare/ac982579962c32ee28be1e80cdb514a829e3366f...98986558dc1c0e2013b76bea92d75bde80568a00).

**Public scenario.** Make a codec with Base58.builder().setEncodeTable(table).get(). Start from the ASCII Bitcoin alphabet in Base58Test and exchange its first two entries, so digit zero is "2" and digit one is "1". Encode a byte array, inspect the ASCII output, then decode known ASCII from a distinct codec configured the same way.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-codec#437.1 · Intent | Encode [0,0,1] and independently decode the literal "221". | The parent uses the default digits on the affected paths. The merge should emit "221" and decode that literal to [0,0,1]. | Each leading zero byte gets one zero symbol. The remaining magnitude 1 gets one symbol for digit one. | Either exact sequence differs, even if an encoder/decoder round trip succeeds. |
| apache/commons-codec#437.2 · Control | Use an unconfigured Base58 for [0,0,1]. | Both should encode to "112" and reconstruct [0,0,1] from those ASCII bytes. | The default alphabet begins with "12". | The default representation or recovered leading-zero count changes. |
| apache/commons-codec#437.3 · Challenge | Hold the swapped table fixed. Encode [0,58] and let a newly constructed codec decode the independently predicted text. | On the merge the ASCII must be "212", and decoding that literal must yield [0,58]. | 58 is one times 58 plus zero. The leading zero byte adds a separate zero digit before those two positional digits. | The prefix is correct but the internal zero digit is wrong, or the second codec reads a different magnitude. |

**Evidence and limits.** Base58Test covers a swapped alphabet and a replacement zero symbol. A round trip using two default tables by mistake could pass even when both custom operations ignore their settings. The value 58 checks a zero digit in a different position.

**Technical notes.** Use the byte-array API in Commons Codec’s binary package. Compare bytes as US-ASCII. The builder validates the custom alphabet’s length and uniqueness. The PR identifies the report as [CODEC-340](https://issues.apache.org/jira/browse/CODEC-340).

**Sources.** [Base58.java](https://github.com/apache/commons-codec/blob/98986558dc1c0e2013b76bea92d75bde80568a00/src/main/java/org/apache/commons/codec/binary/Base58.java) · [Base58Test.java](https://github.com/apache/commons-codec/blob/98986558dc1c0e2013b76bea92d75bde80568a00/src/test/java/org/apache/commons/codec/binary/Base58Test.java) · [pom.xml](https://github.com/apache/commons-codec/blob/98986558dc1c0e2013b76bea92d75bde80568a00/pom.xml).

## apache/commons-compress#725 · Verify a CPIO entry checksum when the caller reads into a slice

**Change and revisions.** [Merged PR #725](https://github.com/apache/commons-compress/pull/725). Accumulate unsigned entry bytes from the destination offset supplied to CpioArchiveInputStream.read. Before `a7a749f028a38a07c6b3765a4b2c3607b1ab6e71`, after `befbfe070270f61c29e032b51363dfc8c8ef51f1`. [Landed comparison](https://github.com/apache/commons-compress/compare/a7a749f028a38a07c6b3765a4b2c3607b1ab6e71...befbfe070270f61c29e032b51363dfc8c8ef51f1).

**Public scenario.** Use a new-format CRC CPIO archive with entry a containing [1,128,3], a stored checksum of 132 and a following entry b containing byte 7. Use a CpioArchiveInputStream, getNextEntry(), then read a into a caller array starting at offset 2. Continue through entry EOF and open b.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-compress#725.1 · Intent | Fill the destination with 9, reserve enough room at offset 2, and read the three bytes of a. Request another byte to finish the entry. | The parent can return the correct payload and then report a checksum error. On the merge a yields [1,128,3], entry EOF, then entry b. | The new-CRC checksum is the unsigned byte sum, 1+128+3=132. The two prefix bytes belong to the caller. | A correct payload followed by a checksum error, wrong payload, or failure to advance to b on the merge. |
| apache/commons-compress#725.2 · Control | Read a into offset zero and consume through entry EOF. | Both revisions should accept checksum 132 and let the caller read 7 from b. | The old and new checksum intervals coincide at offset zero. | Either stream rejects the archive, changes the payload, or loses the following entry. |
| apache/commons-compress#725.3 · Challenge | Hold archive bytes fixed. Read a one byte at a time at offset 1, once with prefix 0 and once with prefix 255. Reassemble the bytes and read b in each run. | Afterward both histories should finish cleanly and yield identical entries and payloads. Prefix sentinels remain unchanged. | Varying destination padding or splitting a read cannot alter the entry's bytes or checksum. | The outcome depends on the prefix, chunk size or entry order, although the archive is identical. |

**Evidence and limits.** The upstream regression reads bla.cpio into buffer offset 1 and asserts the loop completes. A check that stops after receiving the expected bytes can miss verification at entry EOF. The independently checksummed two-entry fixture also tests cursor alignment. [Issue COMPRESS-711](https://issues.apache.org/jira/browse/COMPRESS-711).

**Technical notes.** Use the Commons Compress Maven module and the CPIO new ASCII format with checksum (FORMAT_NEW_CRC). Other CPIO formats bypass this comparison.

**Sources.** [CpioArchiveInputStream.java](https://github.com/apache/commons-compress/blob/befbfe070270f61c29e032b51363dfc8c8ef51f1/src/main/java/org/apache/commons/compress/archivers/cpio/CpioArchiveInputStream.java) · [CpioArchiveInputStreamTest.java](https://github.com/apache/commons-compress/blob/befbfe070270f61c29e032b51363dfc8c8ef51f1/src/test/java/org/apache/commons/compress/archivers/cpio/CpioArchiveInputStreamTest.java) · [pom.xml](https://github.com/apache/commons-compress/blob/befbfe070270f61c29e032b51363dfc8c8ef51f1/pom.xml).

## apache/commons-compress#775 · GNU sparse TAR extraction starts at the first data record

**Change and revisions.** [Merged PR #775](https://github.com/apache/commons-compress/pull/775). An aligned GNU PAX 1.x sparse map occupies complete TAR records. The merge consumes zero padding when the last map byte already ends a 512-byte record. Before `a8cb750e5bdd0fe136d5d9cab38781f9447b2dd3`, after `948512a35a9f8ed1f8eac12f743e879aff9266d2`. [Landed comparison](https://github.com/apache/commons-compress/compare/a8cb750e5bdd0fe136d5d9cab38781f9447b2dd3...948512a35a9f8ed1f8eac12f743e879aff9266d2).

**Public scenario.** Open a valid two-member TAR through TarArchiveInputStream. The first member is GNU PAX sparse 1.0 with logical size 7, one extent at offset 3 of length 4, and stored data ABCD. Its PAX metadata must identify the sparse version and real size, and the physical entry size must include the map record and four stored bytes. In the aligned fixture pad the decimal length field with leading zeroes so the map’s final LF is byte 512. Follow the sparse member with an ordinary member named tail containing Z.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-compress#775.1 · Intent | Call getNextEntry(), then read the sparse member through end of entry. | The parent’s extra-record skip predicts lost data or a read failure. On the merge expect exactly three zero bytes followed by ABCD. | Expanding a four-byte extent at logical offset 3 produces those seven bytes. No physical padding lies after an exactly full map record. | An exception, a missing hole or payload byte, or padding appearing in the logical output on the merge. |
| apache/commons-compress#775.2 · Control | Encode the same extent with the short decimal map and zero-pad the rest of its 512-byte record. | Both revisions should extract the identical seven bytes. | The numeric extent and payload are unchanged. Both padding calculations consume the remaining bytes of a partially used record. | The ordinary short map changes the recovered data or its length on either revision. |
| apache/commons-compress#775.3 · Challenge | Keep the aligned map fixed, change only the four stored bytes to WXYZ and continue to the second member. | On the merge the first readback must become three zeros then WXYZ. The next entry must still be tail with its one byte Z and then the archive must end. | The file data and the next member have independent TAR boundaries. Successful delivery of the first file alone does not prove subsequent alignment. | The new data is ignored, or the second name, payload or end-of-archive changes. |

**Evidence and limits.** The PR regression invokes package-level TarUtils with a 512-byte map of 100 zero extents and checks the next raw byte is A rather than the B a record later. That check establishes the intended cursor position. Logical reconstruction and locating the second complete entry remain public-API predictions. [Original COMPRESS-724 report](https://issues.apache.org/jira/browse/COMPRESS-724)

**Technical notes.** Use the Commons Compress root Maven module and TAR’s 512-byte record size. The short-map and aligned-map cases need valid outer TAR headers, physical sizes, padding and GNU PAX sparse metadata in addition to the sparse text.

**Sources.** [TarUtils.java](https://github.com/apache/commons-compress/blob/948512a35a9f8ed1f8eac12f743e879aff9266d2/src/main/java/org/apache/commons/compress/archivers/tar/TarUtils.java) · [TarUtilsTest.java](https://github.com/apache/commons-compress/blob/948512a35a9f8ed1f8eac12f743e879aff9266d2/src/test/java/org/apache/commons/compress/archivers/tar/TarUtilsTest.java) · [TarArchiveInputStream.java](https://github.com/apache/commons-compress/blob/948512a35a9f8ed1f8eac12f743e879aff9266d2/src/main/java/org/apache/commons/compress/archivers/tar/TarArchiveInputStream.java) · [pom.xml](https://github.com/apache/commons-compress/blob/948512a35a9f8ed1f8eac12f743e879aff9266d2/pom.xml).

## FasterXML/jackson-core#1716 · A UTF-32 supplementary character survives a parser refill

**Change and revisions.** [Merged PR #1716](https://github.com/FasterXML/jackson-core/pull/1716). The UTF32Reader saves the computed low surrogate when only the high surrogate fits in the current character buffer. Before `2a0ea7beeb9eb0a16f04c14e07b5d0804c64433d`, after `15591d013c44ef3b2a84bb639df396149a5917f5`. [Landed comparison](https://github.com/FasterXML/jackson-core/compare/2a0ea7beeb9eb0a16f04c14e07b5d0804c64433d...15591d013c44ef3b2a84bb639df396149a5917f5).

**Public scenario.** Use a JsonFactory to create a parser on BOM-free UTF-32 bytes for an array of one string. For each prefix length 3995 through 4001, put that many cycling ASCII letters before U+1F600 and U+10000. Read START_ARRAY and VALUE_STRING, inspect the text and its code points, then read END_ARRAY.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| FasterXML/jackson-core#1716.1 · Intent | Encode these documents in UTF-32BE. Repeat in UTF-32LE. | The issue reports loss or corruption of a low surrogate when the pair is split. After, every prefix and byte order must produce exactly the two requested supplementary scalars at the tail. | U+1F600 has UTF-16 units D83D DE00 and U+10000 has D800 DC00. Endianness changes the input bytes only. | A replacement, missing or unpaired surrogate, different code point, or missing END_ARRAY on the merge. |
| FasterXML/jackson-core#1716.2 · Control | Replace the supplementary characters with two BMP letters, retaining byte order and prefix lengths. | Both revisions should return exactly those letters and the same token sequence. | Each BMP letter needs just one UTF-16 code unit. | Either parser changes the letters or terminates the array early. |
| FasterXML/jackson-core#1716.3 · Challenge | Keep the JSON value fixed, add one leading JSON whitespace character before the array, and compare the UTF-32 parse with a UTF-8 parse of the same document. | On the merge every parser must return the same string and code-point count. Spacing may move a reader refill without changing any string character. | Whitespace outside the string is insignificant. The UTF-8 path provides a second decoding route. | The byte encodings disagree, or adding only external whitespace changes the last string character. |

**Evidence and limits.** The landed test uses a public byte-array parser across seven prefix lengths and tests single-character reads in both byte orders. Checking only VALUE_STRING or string length misses an incorrect low surrogate. The external-whitespace comparison is a prediction. [Original report](https://github.com/FasterXML/jackson-core/issues/1713).

**Technical notes.** Use Jackson core’s com.fasterxml.jackson.core 2.x APIs and its normal input-encoding detection. Emit four bytes per Unicode code point when constructing the UTF-32 fixture. Encoding each Java char separately would create invalid input.

**Sources.** [UTF32Reader.java](https://github.com/FasterXML/jackson-core/blob/15591d013c44ef3b2a84bb639df396149a5917f5/src/main/java/com/fasterxml/jackson/core/io/UTF32Reader.java) · [UTF32ReaderSurrogate1713Test.java](https://github.com/FasterXML/jackson-core/blob/15591d013c44ef3b2a84bb639df396149a5917f5/src/test/java/com/fasterxml/jackson/core/io/UTF32ReaderSurrogate1713Test.java) · [pom.xml](https://github.com/FasterXML/jackson-core/blob/15591d013c44ef3b2a84bb639df396149a5917f5/pom.xml) · [Related PR #1714](https://github.com/FasterXML/jackson-core/pull/1714).

## locationtech/jts#1092 · Keep measures distinct from elevations in binary geometry

**Change and revisions.** [Merged PR #1092](https://github.com/locationtech/jts/pull/1092). Choose the WKB ordinate flags and payload from the geometry and the ordinates the writer is configured to emit. Before `a7597288e551757426015db75c22603c0baeff20`, after `034207b1de6605ad3eb8dbf8373b1ad8fab1b1b3`. [Landed comparison](https://github.com/locationtech/jts/compare/a7597288e551757426015db75c22603c0baeff20...034207b1de6605ad3eb8dbf8373b1ad8fab1b1b3).

**Public scenario.** Parse LINESTRING M(1 2 3, 5 6 7) with WKTReader. Serialize with WKBWriter(4, ByteOrderValues.LITTLE_ENDIAN, false). Inspect the header and size, decode with WKBReader and examine the coordinate sequence's measures, Z and M values.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| locationtech/jts#1092.1 · Intent | Write the XYM line with maximum output dimension four. | The parent advertises both extra dimensions by default and attempts a fourth ordinate. The merge should encode a measured line with only M set, returning measures 3 and 7 and no elevation. | The fixture has three doubles per point, a five-byte geometry header and four-byte point count, so the no-SRID output is 57 bytes. The pinned test checks the exact M-only encoding. | An exception on the merge, a Z flag, a size other than 57, or decoded M values different from 3 and 7. |
| locationtech/jts#1092.2 · Control | Write LINESTRING ZM(1 2 3 4, 5 6 7 8) with the same writer. | Both should round-trip with elevations 3 and 7 and measures 4 and 8. | The input has four distinct ordinates per position. The pinned XYZM readback examines all four. | A swapped, missing or altered Z or M, even if XY geometry equality passes. |
| locationtech/jts#1092.3 · Challenge | On the merge serialize the same XYM geometry in each supported byte order and decode each byte sequence independently. | The byte-order markers differ, but each decoded sequence has one measure per point, equal XY coordinates and M values [3,7]. | Endianness determines how numbers are encoded, independent of the meaning of the third ordinate. | Only one order decodes, or the decoded values agree in XY while the third ordinate moves into Z. |

**Evidence and limits.** Issue #733 observed an XYM line read back as XYZ with a dimension-three writer. The PR specifies four for its default-configured measured output. The M-only test compares fixed bytes, whereas the XYZM test uses WKBReader. The dual-endian M readback extends both.

**Technical notes.** Use the JTS core module and its measure-capable coordinate sequences. Disable SRID output for the stated byte count. A dimension-three constructor with default ordinates is a different configuration.

**Sources.** [WKBWriter.java](https://github.com/locationtech/jts/blob/034207b1de6605ad3eb8dbf8373b1ad8fab1b1b3/modules/core/src/main/java/org/locationtech/jts/io/WKBWriter.java) · [CheckOrdinatesFilter.java](https://github.com/locationtech/jts/blob/034207b1de6605ad3eb8dbf8373b1ad8fab1b1b3/modules/core/src/main/java/org/locationtech/jts/io/CheckOrdinatesFilter.java) · [WKBWriterTest.java](https://github.com/locationtech/jts/blob/034207b1de6605ad3eb8dbf8373b1ad8fab1b1b3/modules/core/src/test/java/org/locationtech/jts/io/WKBWriterTest.java) · [pom.xml](https://github.com/locationtech/jts/blob/034207b1de6605ad3eb8dbf8373b1ad8fab1b1b3/modules/core/pom.xml) · [Issue #733](https://github.com/locationtech/jts/issues/733).

## apache/commons-csv#412 · Round-trip MongoDB CSV records with an empty leading field

**Change and revisions.** [Merged PR #412](https://github.com/apache/commons-csv/pull/412). The MongoDB CSV preset uses the same character for quoting and escaping. The lexer now recognizes a quote at the boundary of a quoted field before interpreting it as an escape. Before `2abebaa74eb413ece7a56d86f826bc690ee26df9`, after `5770cc07e351cc124d34a6049c59e9aea8885675`. [Landed comparison](https://github.com/apache/commons-csv/compare/2abebaa74eb413ece7a56d86f826bc690ee26df9...5770cc07e351cc124d34a6049c59e9aea8885675).

**Public scenario.** Use a CSVPrinter over a StringWriter with CSVFormat.MONGODB_CSV. Print two records [a,b] and [empty,x], close the printer, then open a public CSVParser with that same preset over the saved text. Collect records through the iterator and inspect each field by index and each record’s size.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-csv#412.1 · Intent | Print and reparse [a,b] then [empty,x]. | The PR reports failure to parse the printer’s empty first column on the parent. Expect precisely two records of size two, with second record fields empty string and x after the merge. | The values passed to the independent printer are the expected reader values. Empty string still occupies a column. | Exception, early EOF, an extra record, or any merged record with the wrong field count or contents. |
| apache/commons-csv#412.2 · Control | Use only nonempty unquoted ASCII fields a,b and c,d. | Expect those two records and four corresponding values on both revisions. | These records contain no ambiguous quote/escape boundary and the comma separates two nonempty columns. | Either revision drops, merges or changes a field. |
| apache/commons-csv#412.3 · Challenge | On the merge print [empty,x] twice, changing only the second occurrence’s second field to one value containing both a comma and a literal double quote. | The first occurrence must remain [empty,x], and the second must contain precisely the empty first field and the changed second string, with its comma and quote intact. | The printer must protect delimiters and quotes within a field. The caller’s original strings give an oracle independent of the lexer. | A changed trailing field affects the leading empty column or earlier row, or escaping adds or drops a literal character. |

**Evidence and limits.** The submitted test prints the two baseline rows under every predefined format, then calls package-level nextRecord(). The public iterator and the delimiter-plus-quote field extend that evidence. Comparing printed text alone cannot show that callers can read those records back. The pinned MONGODB_CSV Javadoc still describes parsing as unsupported. These reader predictions describe particular inputs motivated by the PR and its test. A general MongoDB parsing guarantee remains undocumented.

**Technical notes.** The root Maven module supplies CSVParser, CSVPrinter, CSVFormat and the changed Lexer. This describes the named preset at the pinned revisions, with empty string distinct from null.

**Sources.** [Lexer.java](https://github.com/apache/commons-csv/blob/5770cc07e351cc124d34a6049c59e9aea8885675/src/main/java/org/apache/commons/csv/Lexer.java) · [CSVParserTest.java](https://github.com/apache/commons-csv/blob/5770cc07e351cc124d34a6049c59e9aea8885675/src/test/java/org/apache/commons/csv/CSVParserTest.java) · [CSVFormat.java](https://github.com/apache/commons-csv/blob/5770cc07e351cc124d34a6049c59e9aea8885675/src/main/java/org/apache/commons/csv/CSVFormat.java) · [pom.xml](https://github.com/apache/commons-csv/blob/5770cc07e351cc124d34a6049c59e9aea8885675/pom.xml).

## square/javapoet#994 · Reflected long annotation members compile in generated Java

**Change and revisions.** [Merged PR #994](https://github.com/square/javapoet/pull/994). JavaPoet appends a long literal suffix when serializing a reflected annotation member of type long. Before `aaebc488320bd11aab1a6248d6b8058a255c92df`, after `c9925e48577e3e74b91eb737b2c2b3c22109cde8`. [Landed comparison](https://github.com/square/javapoet/compare/aaebc488320bd11aab1a6248d6b8058a255c92df...c9925e48577e3e74b91eb737b2c2b3c22109cde8).

**Public scenario.** Define a public runtime-retained annotation with long value() and annotate a source class with 12345678910L. Obtain it with Class.getAnnotation, pass it to AnnotationSpec.get, add the returned spec to a TypeSpec, and have JavaFile emit a new class in an accessible package.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| square/javapoet#994.1 · Intent | Generate the annotation use with value 12345678910L. Compile the new class with the annotation declaration on the compiler classpath. | Issue #993 reports a compiler complaint about an oversized integer literal before. After, expect decimal text 12345678910L and successful compilation. | The decimal number exceeds Integer.MAX_VALUE and fits in long. An unsuffixed positive decimal integer literal of that magnitude is invalid here. | The literal lacks a long suffix or javac rejects the generated member value on the merge. |
| square/javapoet#994.2 · Control | Repeat with an annotation member of type int set to 7. | Both should emit an int-compatible literal and compile to a class whose reflected member equals 7. | Integer constants already fit the declared type. | The generator adds a long suffix that makes the int member uncompilable, or reflection reads another value. |
| square/javapoet#994.3 · Challenge | Use a long[] member containing 7L and −2147483649L. Compile, load the generated class, retrieve its annotation and read the array. | On the merge the recovered array must contain those two longs in order, including the negative value. | Reflecting on the compiled consumer checks the literal type, element order and sign independently of source formatting. | Generated code fails to compile or runtime reflection gives an incorrect element, length or order. |

**Evidence and limits.** The upstream test renders a reflected annotation with defaults and compares its text to a golden source string containing 12345678910L. The issue documents the compiler failure. Compilation and reflective array readback are proposed extra observations.

**Technical notes.** JavaPoet’s Maven module has the annotation builder and regression in com.squareup.javapoet. The compile/readback fixture needs a JDK compiler and a public annotation with RUNTIME retention. Include the annotation’s package on both compiler and class-loader paths.

**Sources.** [AnnotationSpec.java](https://github.com/square/javapoet/blob/c9925e48577e3e74b91eb737b2c2b3c22109cde8/src/main/java/com/squareup/javapoet/AnnotationSpec.java) · [AnnotationSpecTest.java](https://github.com/square/javapoet/blob/c9925e48577e3e74b91eb737b2c2b3c22109cde8/src/test/java/com/squareup/javapoet/AnnotationSpecTest.java) · [pom.xml](https://github.com/square/javapoet/blob/c9925e48577e3e74b91eb737b2c2b3c22109cde8/pom.xml) · [Issue #993](https://github.com/square/javapoet/issues/993).

## square/javapoet#986 · Box and unbox annotated primitive type names

**Change and revisions.** [Merged PR #986](https://github.com/square/javapoet/pull/986). Match primitives and wrappers by their unannotated type, then carry the annotation list to the converted type. Before `0d55218ae3b8c8d6fe84132b7867d8c12698ce5e`, after `d682f2013751d25725349d79b449870d0e77354c`. [Landed comparison](https://github.com/square/javapoet/compare/0d55218ae3b8c8d6fe84132b7867d8c12698ce5e...d682f2013751d25725349d79b449870d0e77354c).

**Public scenario.** Build two distinct AnnotationSpec values A and B for type-use annotations with public class names. Start from TypeName.BOOLEAN.annotated(A). Call box(), inspect the annotations and withoutAnnotations(), then unbox the result.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| square/javapoet#986.1 · Intent | Box annotated boolean, inspect isBoxedPrimitive(), then unbox it. | The PR reports that boxing an annotated primitive failed on the parent and annotated wrappers failed recognition. On the merge the wrapper is annotated java.lang.Boolean, isBoxedPrimitive() is true and unbox() equals the initial annotated boolean. | A type-use annotation changes neither the Java primitive nor its wrapper counterpart. The pinned tests assert boxing and unboxing from independently constructed inputs. | An exception, a false classification of annotated Boolean, or loss of A at either boundary. |
| square/javapoet#986.2 · Control | Box canonical TypeName.BOOLEAN and unbox that wrapper. | Both should identify java.lang.Boolean and return the canonical TypeName.BOOLEAN object on unbox, with empty annotation lists. | The unannotated control uses the pre-existing primitive constants and mappings. | A different primitive, unexpected annotations or a noncanonical unboxed result. |
| square/javapoet#986.3 · Challenge | Start from an independently built ClassName.get("java.lang","Integer") annotated with A and B in that order. Unbox and box it. Inspect the annotations after each conversion. | On the merge the intermediate type is int and the final type is Integer, with [A,B] in order at both boundaries. Stripping the annotations should recover the corresponding plain type. | The two distinct annotations reveal duplication, reversal or loss. Starting with a separately constructed wrapper exercises equality across instances. | The first annotation alone survives, their order changes, or round-trip equality fails. |

**Evidence and limits.** The PR reports the added tests fail without the change. They assert a single annotation using an AnnotationSpec fixture. Comparing only rendered unannotated names would miss dropped annotations. The two-annotation sequence remains a prediction.

**Technical notes.** Use the Maven JavaPoet module's TypeName, ClassName and AnnotationSpec APIs. This case checks the type-name model. Rendering a Java source file is unnecessary to observe the annotation list.

**Sources.** [TypeName.java](https://github.com/square/javapoet/blob/d682f2013751d25725349d79b449870d0e77354c/src/main/java/com/squareup/javapoet/TypeName.java) · [TypeNameTest.java](https://github.com/square/javapoet/blob/d682f2013751d25725349d79b449870d0e77354c/src/test/java/com/squareup/javapoet/TypeNameTest.java) · [pom.xml](https://github.com/square/javapoet/blob/d682f2013751d25725349d79b449870d0e77354c/pom.xml).

## javaparser/javaparser#5176 · Typed literal edits reach the lexical printer

**Change and revisions.** [Merged PR #5176](https://github.com/javaparser/javaparser/pull/5176). Typed literal setters now report value changes to observers. A lexical-preserving source edit should reflect the new value while retaining surrounding text. Before `a322c502cfac7d97495fc3f41c6b74a06924267f`, after `c9c78dd4c965646dd97bbf3108ff1faefa1ae198`. [Landed comparison](https://github.com/javaparser/javaparser/compare/a322c502cfac7d97495fc3f41c6b74a06924267f...c9c78dd4c965646dd97bbf3108ff1faefa1ae198).

**Public scenario.** Parse a one-field class containing the string literal a with StaticJavaParser.parse. Pass its compilation unit to LexicalPreservingPrinter.setup before finding the StringLiteralExpr and calling setString. Read the node via asString(), print the unit, and parse the printed source again to observe the value a downstream compiler would see.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| javaparser/javaparser#5176.1 · Intent | Change a to b with setString. | The PR reports old lexical text and an updated pretty-printed value on the parent. On the merge the lexical text must contain the b literal in place of a, and parsing it must yield b. | Only this node was edited. A fresh parse observes what was actually emitted, independent of the in-memory node. | The node returns b while the emitted unit still parses to a or fails to parse. |
| javaparser/javaparser#5176.2 · Control | Start with a and call setString with a again. Preserve unusual spaces around the assignment. | Expect unchanged lexical text on both revisions. The merged same-value path must leave the spelling in place. | An idempotent edit changes no token. A byte-for-byte copy of the original source supplies the comparison. | Formatting or literal spelling changes despite an unchanged value. |
| javaparser/javaparser#5176.3 · Challenge | Use a new string whose decoded characters are b, LF and double quote. Place a neighboring comment containing a in the source before setup. | On the merge the printed text must be parseable, with exactly that three-character string and the unchanged neighboring comment. The node and the newly parsed literal must agree. | A Java string literal cannot contain an unescaped physical line break. A consumer must recover the logical characters regardless of how the printer escapes them. | A double escape changes the decoded value, the print no longer parses, or the untouched comment changes. |

**Evidence and limits.** The issue-free PR gives the old lexical/pretty printer disagreement. Pinned tests exercise notifications, unchanged values and lexical output, including an escaped LF. Checking only node.getValue() or counting property callbacks misses stale or incorrectly escaped output.

**Technical notes.** The javaparser-core setters also change char, double and deprecated int/long methods. The PR documents separate null-handling changes. These claims use non-null strings and the lexical-preservation fixtures in the testing module.

**Sources.** [StringLiteralExpr.java](https://github.com/javaparser/javaparser/blob/c9c78dd4c965646dd97bbf3108ff1faefa1ae198/javaparser-core/src/main/java/com/github/javaparser/ast/expr/StringLiteralExpr.java) · [LiteralStringValueExprTest.java](https://github.com/javaparser/javaparser/blob/c9c78dd4c965646dd97bbf3108ff1faefa1ae198/javaparser-core-testing/src/test/java/com/github/javaparser/ast/expr/LiteralStringValueExprTest.java) · [LiteralValueSettersTest.java](https://github.com/javaparser/javaparser/blob/c9c78dd4c965646dd97bbf3108ff1faefa1ae198/javaparser-core-testing/src/test/java/com/github/javaparser/printer/lexicalpreservation/LiteralValueSettersTest.java) · [pom.xml](https://github.com/javaparser/javaparser/blob/c9c78dd4c965646dd97bbf3108ff1faefa1ae198/javaparser-core/pom.xml) · [Related issue #4791](https://github.com/javaparser/javaparser/issues/4791) · [Related issue #5193](https://github.com/javaparser/javaparser/issues/5193).

## javaparser/javaparser#5207 · Lexical printing preserves array brackets after a renamed identifier

**Change and revisions.** [Merged PR #5207](https://github.com/javaparser/javaparser/pull/5207). The lexical printer distinguishes brackets belonging to an element type from brackets written after a parameter or variable name. The landed range includes the separate varargs-test change. Before `7bb33415ec75aa3fe01c1b3741cbe9ee48413739`, after `ae2e9400810933b1523f3182acc69bf8998e26ca`. [Landed comparison](https://github.com/javaparser/javaparser/compare/7bb33415ec75aa3fe01c1b3741cbe9ee48413739...ae2e9400810933b1523f3182acc69bf8998e26ca). The range includes 2 consecutive landed commits.

**Public scenario.** Parse `class A { void m(String[] a[]) {} }` with StaticJavaParser.parse. Set up LexicalPreservingPrinter on the compilation unit. Find the parameter, call setName(new SimpleName("b")), then call LexicalPreservingPrinter.print(unit). Reparse that output to recover the declared name and array rank.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| javaparser/javaparser#5207.1 · Intent | Rename only a to b in the mixed declaration. | The PR reports malformed output or lost brackets for C-style edits before. After, the emitted parameter must be `String[] b[]` with the surrounding text unchanged. Reparsing must find name b and two dimensions. | Each bracket pair contributes one dimension. A name edit changes only the identifier’s token. | Printing fails, moves a bracket pair, or produces a parameter whose reparsed type has rank one. |
| javaparser/javaparser#5207.2 · Control | Rename the parameter in `void m(String[][] a)` using the same path. | Both revisions should keep the complete type before b and preserve the surrounding declaration. | Both dimensions were attached to the type and the edit touches only the name. | The emitted form changes rank or relocates brackets on either revision. |
| javaparser/javaparser#5207.3 · Challenge | Parse `class A { int a[], keep; }`. Rename a to b, print, reparse and inspect both field declarators separately. | The merge should print `class A { int b[], keep; }`. B has one array dimension and keep remains scalar int. | Comma-separated declarators share a base type while brackets after one name affect only that variable. | The text parses and b is an array, but keep also acquires a dimension, disappears, or changes name. |

**Evidence and limits.** The landed tests compare exact strings after name-node edits and type replacement, including mixed dimensions. A pretty-print or AST-only check could succeed while the token-preserving rewrite emits different Java. The sibling readback checks the printed artifact.

**Technical notes.** The printer is in javaparser-core, with regressions in javaparser-core-testing. Set up lexical preservation before editing. The first landed commit’s ArrayTypeTest concerns annotated varargs. It does not establish the sibling field result.

**Sources.** [LexicalPreservingPrinter.java](https://github.com/javaparser/javaparser/blob/ae2e9400810933b1523f3182acc69bf8998e26ca/javaparser-core/src/main/java/com/github/javaparser/printer/lexicalpreservation/LexicalPreservingPrinter.java) · [CsmArrayBrackets.java](https://github.com/javaparser/javaparser/blob/ae2e9400810933b1523f3182acc69bf8998e26ca/javaparser-core/src/main/java/com/github/javaparser/printer/concretesyntaxmodel/CsmArrayBrackets.java) · [CStyleArrayDeclarationTest.java](https://github.com/javaparser/javaparser/blob/ae2e9400810933b1523f3182acc69bf8998e26ca/javaparser-core-testing/src/test/java/com/github/javaparser/printer/lexicalpreservation/CStyleArrayDeclarationTest.java) · [ArrayTypeTest.java](https://github.com/javaparser/javaparser/blob/ae2e9400810933b1523f3182acc69bf8998e26ca/javaparser-core-testing/src/test/java/com/github/javaparser/ast/type/ArrayTypeTest.java) · [pom.xml](https://github.com/javaparser/javaparser/blob/ae2e9400810933b1523f3182acc69bf8998e26ca/javaparser-core/pom.xml) · [Related issue #2310](https://github.com/javaparser/javaparser/issues/2310) · [Related PR #5181](https://github.com/javaparser/javaparser/pull/5181).

## square/moshi#1442 · Resolve nested record component types before choosing a JSON adapter

**Change and revisions.** [Merged PR #1442](https://github.com/square/moshi/pull/1442). Resolve each record component in its enclosing parameterized type so list and map adapters receive the concrete type argument. Before `751e8219e992a9aecd286aac830fef81da790baa`, after `cdcf0da4ee260b72d7e1ea2be691a568e03720b3`. [Landed comparison](https://github.com/square/moshi/compare/751e8219e992a9aecd286aac830fef81da790baa...cdcf0da4ee260b72d7e1ea2be691a568e03720b3).

**Public scenario.** Use Moshi.Builder().build() with Java records and request an adapter for HasIndirectGenerics, a record wrapping IndirectGenerics<Long>. Give the inner record components T single, List<T> list and Map<String,T> map. Decode values 1, [2,3,4] and {"five":5}, inspect each Java value, then encode and decode again.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| square/moshi#1442.1 · Intent | Look up the outer adapter and decode the three component shapes into the Long binding. | The PR reports IllegalArgumentException for unresolved T on the parent. The merge should yield Long values 1, [2,3,4] and 5 for key five. | The declaration fixes T at Long at every position. The pinned regression checks the complete record in both directions. | An adapter lookup error on the merge, an element of another numeric type or a lost binding. |
| square/moshi#1442.2 · Control | Request an adapter for the nested GenericRecord<String> using Types.newParameterizedTypeWithOwner(RecordsTest.class, GenericRecord.class, String.class) and decode a single string component. | Both revisions should return a record whose value equals the input string. | The direct generic record test predates the nested-record change. | Adapter creation fails or the plain string changes. |
| square/moshi#1442.3 · Challenge | Use a second wrapper binding the same IndirectGenerics<T> to String. Request Long, then String, then Long adapters from one Moshi instance. Round-trip values with distinct strings and numbers. | On the merge each decoded component retains the type of its enclosing wrapper on all three lookups. No record from the String history introduces a String into the Long result. | Identical raw component declarations can represent different parameterized types. Reusing the same adapter cache exercises that distinction. | The second lookup inherits a Long adapter, the repeated lookup reads strings as numbers, or any nested list/map element has the wrong type. |

**Evidence and limits.** The PR supplies the parent lookup stack and the pinned test compares both serialized JSON and decoded record equality. A scalar-only test bypasses the List<T> lookup where the failure was reported. Alternating two concrete bindings is open.

**Technical notes.** The records adapter lies under moshi/src/main/java16. The Gradle records-tests module exercises a record-capable JVM. Use reflective record adapters and the matching Moshi artifact.

**Sources.** [RecordJsonAdapter.java](https://github.com/square/moshi/blob/cdcf0da4ee260b72d7e1ea2be691a568e03720b3/moshi/src/main/java16/com/squareup/moshi/RecordJsonAdapter.java) · [RecordsTest.java](https://github.com/square/moshi/blob/cdcf0da4ee260b72d7e1ea2be691a568e03720b3/moshi/records-tests/src/test/java/com/squareup/moshi/records/RecordsTest.java) · [build.gradle.kts](https://github.com/square/moshi/blob/cdcf0da4ee260b72d7e1ea2be691a568e03720b3/moshi/records-tests/build.gradle.kts).

## google/gson#2998 · Gson tree numbers retain the requested integral wrapper type

**Change and revisions.** [Merged PR #2998](https://github.com/google/gson/pull/2998). The byte, short and integer adapters now select a JsonWriter overload that preserves the narrowed Number class when the destination is a tree. Before `c616243d1d78c0466b53be39f893094ebb7c6918`, after `e83ef91dc7614e6f8fb5ea8dd3fd67530602f05c`. [Landed comparison](https://github.com/google/gson/compare/c616243d1d78c0466b53be39f893094ebb7c6918...e83ef91dc7614e6f8fb5ea8dd3fd67530602f05c).

**Public scenario.** With new Gson(), call toJsonTree(value, declaredType) and inspect both getAsNumber().getClass() and the actual numeric value. Compare the corresponding stream serialization with gson.toJson on the same value and declared type.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| google/gson#2998.1 · Intent | Serialize the number 1 separately as byte, short and int, then repeat with their wrapper class tokens. | The PR reports Long on the parent. The merge should expose Byte, Short and Integer respectively for both forms, all holding the value 1. | The declared type selects a specific narrowing conversion. Distinct Number classes are observable even though each writes the same JSON digit. | The merged tree stores a Long, chooses a class based on primitive versus wrapper spelling, or changes the numeric value. |
| google/gson#2998.2 · Control | Serialize 1L as long and Long. Inspect each tree and the ordinary JSON text. | Both revisions should expose Long and emit the numeric token 1. | The existing long adapter represents this value directly. Neither type nor spelling requires a conversion. | Either tree class differs from Long, or the scalar becomes a string or changes value. |
| google/gson#2998.3 · Challenge | Use an Integer-valued Number 257 with declared Byte.class. Compare the result with a Byte-valued input 1 targeted at the same class, and serialize both trees to plain JSON. | On the merge both tree values must be Byte with value 1 and both texts the numeric token 1. On the parent the width can be wrong even if the JSON agrees. | Java Number.byteValue discards higher bits for an Integer; 257 and 1 have the same low eight bits. Text alone erases wrapper width. | The merged values have different classes or values, or a correct tree value reaches the stream with different text. |

**Evidence and limits.** The pinned tests assert tree classes at value 1 and include other Number inputs for narrowing. The PR attributes the regression to primitive widening before writer overload resolution. A text-only assertion cannot distinguish Long(1) from Byte(1).

**Technical notes.** The gson Maven module contains the TypeAdapters change and PrimitiveTest. Specify the explicit declared type when testing narrowing and use the default adapters.

**Sources.** [TypeAdapters.java](https://github.com/google/gson/blob/e83ef91dc7614e6f8fb5ea8dd3fd67530602f05c/gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java) · [PrimitiveTest.java](https://github.com/google/gson/blob/e83ef91dc7614e6f8fb5ea8dd3fd67530602f05c/gson/src/test/java/com/google/gson/functional/PrimitiveTest.java) · [pom.xml](https://github.com/google/gson/blob/e83ef91dc7614e6f8fb5ea8dd3fd67530602f05c/gson/pom.xml) · [Issue #2680](https://github.com/google/gson/issues/2680) · [Related PR #2814](https://github.com/google/gson/pull/2814).

## FasterXML/jackson-core#1816 · Numeric accessors return the current token at its requested precision

**Change and revisions.** [Merged PR #1816](https://github.com/FasterXML/jackson-core/pull/1816). Jackson clears deferred numeric state across tokens and retains the text needed for later exact conversions on the same token. Before `682b4062b60d8317956ca80a28c3c92cf46d93ce`, after `b251524f3a857fd5960548ea12d4ba2dc92f8c43`. [Landed comparison](https://github.com/FasterXML/jackson-core/compare/682b4062b60d8317956ca80a28c3c92cf46d93ce...b251524f3a857fd5960548ea12d4ba2dc92f8c43).

**Public scenario.** With JsonFactory.createParser, advance through [2.5,7.5]. Read the first value with getDecimalValue(). On the second call getNumberType(), getBigIntegerValue(), getDecimalValue(), then getDoubleValue(), before advancing again.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| FasterXML/jackson-core#1816.1 · Intent | Read 2.5 as decimal, then inspect 7.5 in the stated order. | Issue #1815 reports a stale conversion of the previous number. After, getNumberType() gives DOUBLE, then the accessors give 7, decimal 7.5, and double 7.5. | BigInteger conversion truncates the current token toward zero. Both displayed halves are exactly representable as doubles. | The integer is 2, the decimal comes from the earlier token, or a later accessor loses the value. |
| FasterXML/jackson-core#1816.2 · Control | Parse [7] and read the only number first as BigInteger, then as double. | Both revisions should give 7 and 7.0 and then END_ARRAY. | The one-token input lacks a preceding numeric cache, and seven is exactly representable in both types. | Any different value, exception, or missing terminal token. |
| FasterXML/jackson-core#1816.3 · Challenge | Hold 12345678901234567890123 fixed. In independent parses, request double before BigInteger and BigInteger before double. Compare the integer with one constructed from the original decimal digits. | On the merge both integer results must be exact and both double results may have normal IEEE rounding. The PR reports that double-first could previously round away the final digits of the integer. | BigInteger on the original decimal text is an independent exact oracle, unaffected by the consumer’s earlier request for a double. | Only the double-first order changes the exact result, or exact conversion after approximate access throws. |

**Evidence and limits.** The pinned test exercises blocking parsers and both async feeder types. Its assertions check multiple accessors before advancing. A single getDoubleValue() per token cannot establish conversion independence. [Stale-value report](https://github.com/FasterXML/jackson-core/issues/1815).

**Technical notes.** This is com.fasterxml.jackson.core 2.x. Standard JSON suffices for these histories. To compare async behavior, use UTF-8 with an appropriate feeder, supply input on NOT_AVAILABLE, and signal endOfInput after the final chunk.

**Sources.** [ParserBase.java](https://github.com/FasterXML/jackson-core/blob/b251524f3a857fd5960548ea12d4ba2dc92f8c43/src/main/java/com/fasterxml/jackson/core/base/ParserBase.java) · [NonBlockingJsonParserBase.java](https://github.com/FasterXML/jackson-core/blob/b251524f3a857fd5960548ea12d4ba2dc92f8c43/src/main/java/com/fasterxml/jackson/core/json/async/NonBlockingJsonParserBase.java) · [NumberStaleValue1815Test.java](https://github.com/FasterXML/jackson-core/blob/b251524f3a857fd5960548ea12d4ba2dc92f8c43/src/test/java/com/fasterxml/jackson/core/read/NumberStaleValue1815Test.java) · [pom.xml](https://github.com/FasterXML/jackson-core/blob/b251524f3a857fd5960548ea12d4ba2dc92f8c43/pom.xml) · [Related issue #1813](https://github.com/FasterXML/jackson-core/issues/1813).

## FasterXML/jackson-databind#6407 · Carry immutable builder replacements through buffered property assignment

**Change and revisions.** [Merged PR #6407](https://github.com/FasterXML/jackson-databind/pull/6407). When a creator property arrives after regular properties, retain each new builder returned by applying the buffered values. Before `b02acce88765473e3d883c877f1e64e1c1d8910d`, after `0736200316cc75d98d38b73622aad09f28a1fc93`. [Landed comparison](https://github.com/FasterXML/jackson-databind/compare/b02acce88765473e3d883c877f1e64e1c1d8910d...0736200316cc75d98d38b73622aad09f28a1fc93).

**Public scenario.** Use the pinned Value(a,b,c,d) record and its immutable builder. The creator accepts c. Each with-method allocates a replacement. Call JsonMapper.readValue with named properties a=5, b=6, c=7 and d=8 and inspect the built record.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| FasterXML/jackson-databind#6407.1 · Intent | Deserialize the object with a and b before c, and d last. | The PR reports lost buffered values on the parent. After the change, the four accessors should return (5,6,7,8). | Each independent property was supplied exactly once. The pinned builder carries untouched fields into each replacement. | Either pre-creator value becomes zero, or the post-creator d is lost on the merge. |
| FasterXML/jackson-databind#6407.2 · Control | Use the ordinary MutableBean fixture. Read name=value before creator id=7. The setter mutates the bean and returns the String value. | Both should produce the same MutableBean with id 7 and name value. | An ordinary setter's return is immaterial to the identity of this bean. The pinned regression checks both fields. | A mapping failure, a String substituted for the target, or a bean lacking its supplied name. |
| FasterXML/jackson-databind#6407.3 · Challenge | Compare creator-first and creator-last object encodings with the array [5,6,7,8]. For the array use the pinned a,b,c,d order and ARRAY format override. | On the merge all three should yield equal Value records. Changing only b to 16 in all three encodings should change only b in each result. | Distinct properties describe the same logical value. Comparing independent orderings and shapes exposes stale intermediate builder instances. | Only one ordering or shape succeeds, or changing b affects another accessor. |

**Evidence and limits.** Issue #6397 reports silent loss for array-shaped input. The landed test exercises object, array, unwrapped and absent-creator branches and the ordinary-bean control. Successful deserialization alone misses default-valued fields.

**Technical notes.** Use tools.jackson.databind from the pinned 3.x Maven project. The array shape override is on ImmutableBuilder. The creator is c. The PR reports a JDK 21 build. Distinguish builder-returning methods from setters on an ordinary bean.

**Sources.** [BuilderBasedDeserializer.java](https://github.com/FasterXML/jackson-databind/blob/0736200316cc75d98d38b73622aad09f28a1fc93/src/main/java/tools/jackson/databind/deser/bean/BuilderBasedDeserializer.java) · [BeanAsArrayBuilderDeserializer.java](https://github.com/FasterXML/jackson-databind/blob/0736200316cc75d98d38b73622aad09f28a1fc93/src/main/java/tools/jackson/databind/deser/bean/BeanAsArrayBuilderDeserializer.java) · [PropertyBasedCreator.java](https://github.com/FasterXML/jackson-databind/blob/0736200316cc75d98d38b73622aad09f28a1fc93/src/main/java/tools/jackson/databind/deser/bean/PropertyBasedCreator.java) · [ImmutableBuilderWithCreator6397Test.java](https://github.com/FasterXML/jackson-databind/blob/0736200316cc75d98d38b73622aad09f28a1fc93/src/test/java/tools/jackson/databind/deser/builder/ImmutableBuilderWithCreator6397Test.java) · [pom.xml](https://github.com/FasterXML/jackson-databind/blob/0736200316cc75d98d38b73622aad09f28a1fc93/pom.xml) · [Issue #6397](https://github.com/FasterXML/jackson-databind/issues/6397).

## FasterXML/jackson-databind#6473 · Updating an EnumMap merges the values already owned by the caller

**Change and revisions.** [Merged PR #6473](https://github.com/FasterXML/jackson-databind/pull/6473). Updating an existing EnumMap now passes an existing value into deserialization when content merging is enabled. Fresh maps and explicitly nonmergeable values continue to use replacement semantics. Before `66ade176743438d3b8247348465aa31eb95e24f7`, after `949188f567b60b88851f4898eeb9bc82d098cfbe`. [Landed comparison](https://github.com/FasterXML/jackson-databind/compare/66ade176743438d3b8247348465aa31eb95e24f7...949188f567b60b88851f4898eeb9bc82d098cfbe).

**Public scenario.** Use the regression’s bean with an @JsonMerge EnumMap keyed by enum constants A,B,C. Its constructor fills every slot with a mutable Value carrying an initial data string and no usable JSON creator. Retain a reference to the value at A, then call mapper.readerForUpdating(bean).readValue on a document that changes only its count.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| FasterXML/jackson-databind#6473.1 · Intent | Update A.count to 3 while omitting A.data and key C. | The PR and issue report InvalidDefinitionException while constructing the value before the fix. On the merge the returned bean must be the input, its A value must still be the saved object, its count 3 and data init-A, and C must retain init-C. | Updating an existing object needs no creator. The externally saved alias shows which instance actually received the write. | The merge attempts construction, loses an omitted field, replaces A, or changes C. |
| FasterXML/jackson-databind#6473.2 · Control | Read a fresh EnumMap of creatable beans from one JSON object containing only key A with field a equal to x. | Both revisions should construct one entry A with a=x. | No old map value exists to merge. The new entry is determined entirely by this input. | Either revision fails, adds keys, or supplies a different field value. |
| FasterXML/jackson-databind#6473.3 · Challenge | Keep the same existing A and count update. Run two fresh histories differing only in the initial data string and count of the untouched C. Serialize the updated bean and inspect its tree with an independent reader. | On the merge the serialized A has count 3 and initial data in both histories, and C serializes its own original data and count each time. The retained A alias observes the same 3. | An update scoped to A cannot depend on another key’s value. Writing and reading back distinguishes a visible mutation of the bean from a change only to a temporary result. | Changing C changes serialized A, the alias stays stale, or serialization loses C’s untouched data. |

**Evidence and limits.** The regression checks saved identity, scalar replacement, content overrides and fresh-map duplicate keys. An assertion about resulting map size alone misses both omitted-field loss and replacement of an existing caller reference.

**Technical notes.** The Jackson databind 3.x module contains EnumMapDeserializer and EnumMapMerge6445Test. The update claims use default content mergeability with @JsonMerge on the map, a mutable bean value and a mapper configured as in the regression.

**Sources.** [EnumMapDeserializer.java](https://github.com/FasterXML/jackson-databind/blob/949188f567b60b88851f4898eeb9bc82d098cfbe/src/main/java/tools/jackson/databind/deser/jdk/EnumMapDeserializer.java) · [EnumMapMerge6445Test.java](https://github.com/FasterXML/jackson-databind/blob/949188f567b60b88851f4898eeb9bc82d098cfbe/src/test/java/tools/jackson/databind/deser/merge/EnumMapMerge6445Test.java) · [pom.xml](https://github.com/FasterXML/jackson-databind/blob/949188f567b60b88851f4898eeb9bc82d098cfbe/pom.xml) · [Issue #6445](https://github.com/FasterXML/jackson-databind/issues/6445).

## FasterXML/jackson-dataformat-xml#895 · Always-on Base64 XML names remain parseable across encodings

**Change and revisions.** [Merged PR #895](https://github.com/FasterXML/jackson-dataformat-xml/pull/895). The always-on name processor puts an underscore before base64url names whose initial encoded character cannot start an XML name and strips that marker during decoding. Before `f560daa9ecb75c50de084c5a57559f84134554b3`, after `c3584c7120d6a11e3d417a081d8600be47103fe9`. [Landed comparison](https://github.com/FasterXML/jackson-dataformat-xml/compare/f560daa9ecb75c50de084c5a57559f84134554b3...c3584c7120d6a11e3d417a081d8600be47103fe9).

**Public scenario.** Build an XmlFactory with XmlNameProcessors.newAlwaysOnBase64Processor() via xmlNameProcessor, then XmlMapper.builder(factory).build(). Serialize the regression DTO with its string map and read it back. Use distinct values to identify its dynamic element names.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| FasterXML/jackson-dataformat-xml#895.1 · Intent | Set the map entry "中文" to "cjk". Serialize, parse the XML, then deserialize the DTO. | The PR reports Woodstox can write an invalid digit-leading XML name before, followed by parse failure. After, the child element is named _5Lit5paH and the recovered key is exactly 中文. | The UTF-8 base64url spelling starts with 5. An XML name may start with underscore, while a digit is allowed only later. | Writing succeeds but an XML parser rejects the document, or the recovered key/value differs. |
| FasterXML/jackson-dataformat-xml#895.2 · Control | Use the key "abc" and value "ascii". | Both should use the existing wire name YWJj and recover the original pair. | YWJj is the base64 representation of those three bytes and begins with a letter. | An extra prefix changes the established wire name, or map readback changes. |
| FasterXML/jackson-dataformat-xml#895.3 · Challenge | Write both U+03FF and U+0400 as separate keys with values "below" and "at". Also parse the document with JDK XMLStreamReader and collect the two dynamic local names and text values. | On the merge these associations must be z78→below and _0IA→at in either order. A separately built mapper with the same processor must recover both distinct keys. | Adjacent Unicode scalars produce base64url initials z and 0. An independent XML consumer checks legal element names and the serialized associations. | A parser rejects either element, the marker appears on the wrong name, or the keys collide on independent readback. |

**Evidence and limits.** The regression checks complete mapper round trips for map keys and an attribute, including the exact boundary spellings. Serializing without parsing leaves the provider’s permissive write behavior unexamined. Independent StAX consumption remains a prediction.

**Technical notes.** Use tools.jackson.dataformat.xml (Jackson 3.x) with the always-on processor. The Maven module declares the Woodstox StAX implementation. The control and boundary properties refer to nonempty, namespace-free map keys.

**Sources.** [XmlNameProcessors.java](https://github.com/FasterXML/jackson-dataformat-xml/blob/c3584c7120d6a11e3d417a081d8600be47103fe9/src/main/java/tools/jackson/dataformat/xml/XmlNameProcessors.java) · [XmlNameEscapeTest.java](https://github.com/FasterXML/jackson-dataformat-xml/blob/c3584c7120d6a11e3d417a081d8600be47103fe9/src/test/java/tools/jackson/dataformat/xml/misc/XmlNameEscapeTest.java) · [pom.xml](https://github.com/FasterXML/jackson-dataformat-xml/blob/c3584c7120d6a11e3d417a081d8600be47103fe9/pom.xml).

## h2database/h2database#4034 · Keep bound integers through UNNEST and ARRAY_AGG

**Change and revisions.** [Merged PR #4034](https://github.com/h2database/h2database/pull/4034). Derive the array element type during preparation without replacing values that will arrive at execution. Before `e69ff62a4bb5fb84d4f4eee916efa1c432a200c4`, after `23bf50db54de6ef20877e3ac4e53786d8bea1998`. [Landed comparison](https://github.com/h2database/h2database/compare/e69ff62a4bb5fb84d4f4eee916efa1c432a200c4...23bf50db54de6ef20877e3ac4e53786d8bea1998).

**Public scenario.** Open an H2 JDBC connection and prepare SELECT ARRAY_AGG(V) FROM UNNEST(ARRAY[CAST(? AS INTEGER), CAST(? AS INTEGER)]) T(V). Bind 1 and 2 with setInt, execute, move to the sole result row, and inspect getObject(1,Integer[].class) and getArray(1).getArray().

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| h2database/h2database#4034.1 · Intent | Execute the two-cast aggregate query with bindings 1 and 2. | Issue #4033 reports two nulls on H2 2.2.224. On the merge both reads should yield two non-null integers with multiset {1,2}. The pinned test expects [1,2] for this execution. | UNNEST exposes the two bound values and ARRAY_AGG collects each once. The multiset avoids depending on SQL ordering without ORDER BY. | A null element, incorrect multiplicity or a noninteger value on the merge. |
| h2database/h2database#4034.2 · Control | Use literal ARRAY[1,2] in the same query with an ordinary Statement. | Both should give two non-null values 1 and 2 in either order. | The issue reports the literal control works. Neither expression depends on parameter binding time. | An empty or null-padded result, or a different element multiset. |
| h2database/h2database#4034.3 · Challenge | Reuse the same PreparedStatement, first with 7 and 7, then −4 and 9. For each execution compare JDBC array elements with values read from the separate SELECT V FROM UNNEST(...) using identical bindings. | On the merge the aggregated and unaggregated multisets should agree in each execution, including two copies of 7 and no stale 7 on the second. | The scalar-row query independently exposes the current bindings. Changing both values detects a result frozen at prepare time or cached on reuse. | A second execution repeats an old element, duplicate 7 is collapsed, or the two public queries disagree. |

**Evidence and limits.** The issue contrasts the failing aggregate with successful literal and unaggregated queries. The pinned JDBC test asserts a typed Integer[] on one execution. Successful statement preparation or a plausible SQL type does not establish the elements.

**Technical notes.** Use the H2 engine and JDBC driver from the same h2 module. The h2/pom.xml and TestPreparedStatement identify the module and regression. Keep explicit casts so parameter types are known.

**Sources.** [Parser.java](https://github.com/h2database/h2database/blob/23bf50db54de6ef20877e3ac4e53786d8bea1998/h2/src/main/org/h2/command/Parser.java) · [CastSpecification.java](https://github.com/h2database/h2database/blob/23bf50db54de6ef20877e3ac4e53786d8bea1998/h2/src/main/org/h2/expression/function/CastSpecification.java) · [TestPreparedStatement.java](https://github.com/h2database/h2database/blob/23bf50db54de6ef20877e3ac4e53786d8bea1998/h2/src/test/org/h2/test/jdbc/TestPreparedStatement.java) · [pom.xml](https://github.com/h2database/h2database/blob/23bf50db54de6ef20877e3ac4e53786d8bea1998/h2/pom.xml) · [Issue #4033](https://github.com/h2database/h2database/issues/4033).

## h2database/h2database#2614 · Nested JDBC arrays reach Java aliases with their row structure intact

**Change and revisions.** [Merged PR #2614](https://github.com/h2database/h2database/pull/2614). H2 extends conversion between SQL ARRAY values and Java arrays for aliased Java function arguments and typed JDBC result reads. Before `3d939b6a4e3d4f60ca7e378bc3af3fc0087d0249`, after `6940fc30b60af16b06376a6c2ed8c46815820730`. [Landed comparison](https://github.com/h2database/h2database/compare/3d939b6a4e3d4f60ca7e378bc3af3fc0087d0249...6940fc30b60af16b06376a6c2ed8c46815820730).

**Public scenario.** Open a JDBC connection to a fresh in-memory H2 database. Register an alias F for a public static method taking String[][] and returning Integer[][] by parsing each element of each row independently. Execute SELECT F(ARRAY[ARRAY['1','2'],ARRAY['3']]), advance the ResultSet, and read its first column with getObject(1, Integer[][].class).

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| h2database/h2database#2614.1 · Intent | Call F with those two rows of lengths two and one. | The PR targets unsupported multi-dimensional alias input before the change. The precise parent JDBC failure remains open. The merge should return an Integer[][] deeply equal to [[1,2],[3]]. | The function parses exactly the three input strings and never pads a row. Ragged shape and element classes are observable beyond outer array length. | Alias invocation or typed read fails on the merge, or a row is flattened, padded, mistyped or reordered. |
| h2database/h2database#2614.2 · Control | Use a separate one-dimensional Integer[] identity alias and bind new Integer[]{1,2} using PreparedStatement.setObject. | On both revisions the default ResultSet.getObject read should produce an Object[] with numeric contents 1 and 2 in order. | The existing one-dimensional test checks the default array class. The identity function supplies the expected contents. | Class or values differ, or a working one-dimensional binding fails. |
| h2database/h2database#2614.3 · Challenge | Call F with nested BIGINT arrays [[1,2],[3]] and call ResultSet.getObject(1, Short[][].class). Also register a second public static Java alias INSPECT(Integer[][]) that returns Arrays.deepToString of its argument. Query INSPECT(F(...)) separately and read it with ResultSet.getString(1). | On the merge the typed read should be a ragged Short[][] with rows [1,2] and [3]. The scalar read should be the text `[[1, 2], [3]]`. | All values fit both Java numeric types. The second alias independently observes the SQL result as its own argument and returns a scalar that bypasses JDBC nested-array result conversion. | The typed result and scalar read disagree about row boundaries or values, or the requested Java component type is lost. |

**Evidence and limits.** The pinned TestFunctions invokes a Java method accepting String[][] with string and BIGINT SQL arrays, checking Integer[][] and Short[][] respectively. The one-dimensional baseline originally checked only the returned class name. An independent scalar read through a second Java alias remains unexecuted.

**Technical notes.** The h2 module has its descriptor at h2/pom.xml. The alias class must be visible to the embedded database. Give it a public static method, boxed component types and numeric strings accepted by Integer.parseInt.

**Sources.** [FunctionAlias.java](https://github.com/h2database/h2database/blob/6940fc30b60af16b06376a6c2ed8c46815820730/h2/src/main/org/h2/engine/FunctionAlias.java) · [DataType.java](https://github.com/h2database/h2database/blob/6940fc30b60af16b06376a6c2ed8c46815820730/h2/src/main/org/h2/value/DataType.java) · [JdbcResultSet.java](https://github.com/h2database/h2database/blob/6940fc30b60af16b06376a6c2ed8c46815820730/h2/src/main/org/h2/jdbc/JdbcResultSet.java) · [TestFunctions.java](https://github.com/h2database/h2database/blob/6940fc30b60af16b06376a6c2ed8c46815820730/h2/src/test/org/h2/test/db/TestFunctions.java) · [pom.xml](https://github.com/h2database/h2database/blob/6940fc30b60af16b06376a6c2ed8c46815820730/h2/pom.xml).

## apache/calcite#5345 · Nested SQL casts retain intermediate precision and formatting

**Change and revisions.** [Merged PR #5345](https://github.com/apache/calcite/pull/5345). The simplifier preserves an intermediate cast when removing it would alter the final conversion, including text formatting and truncation. Before `c368970b2950903432ed61ecd7ff404a67e16fb1`, after `a2e574ec271866eb352f98d7101a386a30dc8bc8`. [Landed comparison](https://github.com/apache/calcite/compare/c368970b2950903432ed61ecd7ff404a67e16fb1...a2e574ec271866eb352f98d7101a386a30dc8bc8).

**Public scenario.** Through a Calcite JDBC connection configured for the EMP fixture in cast.iq, select four expressions for EMPNO 7369. Apply CAST(... AS VARCHAR) to DEPTNO cast to DOUBLE, DEPTNO cast to DECIMAL(5,2), SAL cast to DECIMAL(10,4), and DEPTNO cast to INTEGER. Read the single row using ResultSet.getString.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/calcite#5345.1 · Intent | Compare the four columns for DEPTNO 20 and SAL 800. | The issue reports collapsing an integer→double→text conversion to integer text. On the merge the pinned Calcite output is "20.0", "20.00", "800.0000", "20", in order. | Different intermediate SQL types preserve observable scale. The SQL transcript records exactly these results for this backend. | Any merged string loses the expected fractional digits or acquires extra digits. |
| apache/calcite#5345.2 · Control | Select CAST(DEPTNO AS VARCHAR) alongside the column with the intermediate INTEGER. | Both revisions should return "20" for both expressions. | The source column is already integral. The repeated integral conversion leaves its value and display type unchanged. | The two strings differ on the same row. |
| apache/calcite#5345.3 · Challenge | Use the fixture’s DOUBLE division DEPTNO/3e0, applying CAST to VARCHAR(3), then DOUBLE. Separately fetch the three-character intermediate string and feed it as a VARCHAR parameter to a second JDBC query that casts it to DOUBLE. | On the merge the nested and two-query results should agree at 6.6. The intermediate string should be "6.6". The issue reports length-changing casts could be discarded before. | Fetching and rebinding the intermediate prevents the optimizer from eliding it across the two statements. 20/3 has additional fractional digits before truncation. | The intermediate is "6.6" but the nested query returns a longer, untruncated numeric value. |

**Evidence and limits.** The pinned SQL transcript records row values in the Calcite execution environment. RexLosslessCastTest also checks expression simplification. A structurally plausible plan alone cannot show the displayed values. The split JDBC comparison remains a prediction. [CALCITE-7870](https://issues.apache.org/jira/browse/CALCITE-7870).

**Technical notes.** Use the core Gradle module and its cast.iq EMP fixture. Formatting here is pinned to that execution environment. When comparing a different adapter, use its own two-stage conversion as the reference and record the adapter.

**Sources.** [RexSimplify.java](https://github.com/apache/calcite/blob/a2e574ec271866eb352f98d7101a386a30dc8bc8/core/src/main/java/org/apache/calcite/rex/RexSimplify.java) · [RexUtil.java](https://github.com/apache/calcite/blob/a2e574ec271866eb352f98d7101a386a30dc8bc8/core/src/main/java/org/apache/calcite/rex/RexUtil.java) · [RexLosslessCastTest.java](https://github.com/apache/calcite/blob/a2e574ec271866eb352f98d7101a386a30dc8bc8/core/src/test/java/org/apache/calcite/rex/RexLosslessCastTest.java) · [cast.iq](https://github.com/apache/calcite/blob/a2e574ec271866eb352f98d7101a386a30dc8bc8/core/src/test/resources/sql/cast.iq) · [build.gradle.kts](https://github.com/apache/calcite/blob/a2e574ec271866eb352f98d7101a386a30dc8bc8/core/build.gradle.kts).

## apache/calcite#4942 · Preserve sub-millisecond digits when reducing temporal literals

**Change and revisions.** [Merged PR #4942](https://github.com/apache/calcite/pull/4942). Keep representable high-precision temporal literals intact through planner constant reduction and conversion to character data. Before `3fc5f464ee087f69cd7b1f8dd54ee612050a917d`, after `b25114f7c616b6e3fb4007071406f79e765ff66f`. [Landed comparison](https://github.com/apache/calcite/compare/3fc5f464ee087f69cd7b1f8dd54ee612050a917d...b25114f7c616b6e3fb4007071406f79e765ff66f).

**Public scenario.** Construct a RexBuilder with JavaTypeFactoryImpl and a RelDataTypeSystemImpl permitting precision 9 for TIME and TIMESTAMP. Use RexExecutorImpl.reduce with the fixture's GMT and US locale context. Cast the string 12:34:56.123456 to TIME(6), reduce, and inspect the returned RexLiteral as TimeString at precision six.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/calcite#4942.1 · Intent | Reduce the six-digit TIME cast and the analogous TIMESTAMP(6) cast for 2020-01-01 12:34:56.123456. | The PR reports loss of digits past milliseconds on the parent. On the merge the returned time and timestamp strings should each end in .123456 with their whole-second and date components preserved. | All six digits fit the declared precision exactly. The pinned reducer tests exercise precisions 1 through 9. | A nonliteral result for the fixture, a .123000 suffix, a changed date, or any other loss of representable digits. |
| apache/calcite#4942.2 · Control | Reduce TIME(3) and TIMESTAMP(3) casts of the same whole-second values with exactly .123 in the inputs. | Both revisions should return .123 when read as TimeString or TimestampString at precision three. | These values are exactly representable at millisecond precision. | Either reduced literal loses or changes one of the three significant digits. |
| apache/calcite#4942.3 · Challenge | Reduce a pair of timestamps differing only in the sixth fractional digit, .123456 and .123457. Cast each to VARCHAR(30), then reduce and read the result strings. | On the merge the strings should respectively end .123456 and .123457. They must remain distinguishable after the temporal-to-character conversion. | The inputs differ by one representable microsecond. String readback tests the next consumer rather than only a temporal type's declared precision. | Equal strings, a wrong last digit or a changed date on either path. |

**Evidence and limits.** CALCITE-7529 and the PR describe loss during generated constant reduction with a custom precision ceiling. The upstream tests also check a mixed list of already-reduced literals and arithmetic. Seeing TIME(6) in type metadata alone cannot establish the returned value. [Issue CALCITE-7529](https://issues.apache.org/jira/browse/CALCITE-7529).

**Technical notes.** Use Calcite core and its Rex API. The Gradle core and testkit modules exercise planner and SQL-facing cases. The pinned type factory override matters because the default temporal precision cap differs.

**Sources.** [RexBuilder.java](https://github.com/apache/calcite/blob/b25114f7c616b6e3fb4007071406f79e765ff66f/core/src/main/java/org/apache/calcite/rex/RexBuilder.java) · [RexExecutorImpl.java](https://github.com/apache/calcite/blob/b25114f7c616b6e3fb4007071406f79e765ff66f/core/src/main/java/org/apache/calcite/rex/RexExecutorImpl.java) · [RexExecutorTest.java](https://github.com/apache/calcite/blob/b25114f7c616b6e3fb4007071406f79e765ff66f/core/src/test/java/org/apache/calcite/rex/RexExecutorTest.java) · [SqlOperatorTest.java](https://github.com/apache/calcite/blob/b25114f7c616b6e3fb4007071406f79e765ff66f/testkit/src/main/java/org/apache/calcite/test/SqlOperatorTest.java) · [build.gradle.kts](https://github.com/apache/calcite/blob/b25114f7c616b6e3fb4007071406f79e765ff66f/core/build.gradle.kts).

## apache/arrow-java#1518 · Decimal holders read the signed value at the selected buffer position

**Change and revisions.** [Merged PR #1518](https://github.com/apache/arrow-java/pull/1518). The generated decimal holder readers now decode using native byte order and take the holder’s start as a byte offset. The vector utility also keeps its existing index-based entry. Before `a99297ce3ca5c6cd8dc2c5ea3f5541b0788fdd62`, after `1718ad7aeef4209d3a620541672e1af7fc5cbb1e`. [Landed comparison](https://github.com/apache/arrow-java/compare/a99297ce3ca5c6cd8dc2c5ea3f5541b0788fdd62...1718ad7aeef4209d3a620541672e1af7fc5cbb1e).

**Public scenario.** Allocate a DecimalVector with precision 38 and scale 2 in a RootAllocator. Allocate capacity for three values, store 1.23, 1234567.89 and −1234567.89, and obtain a NullableDecimalHolder with vector.get(2, holder). Compare new NullableDecimalHolderReaderImpl(holder).readBigDecimal() with vector.getObject(2) and with the value originally written before closing the vector.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/arrow-java#1518.1 · Intent | Read slots 1 and 2 via the generated nullable holder readers. | On little-endian machines the old big-endian interpretation predicts incorrect values. On the merge require the exact positive then negative BigDecimal, both with scale 2. On big-endian hardware the parent may already agree. | The caller supplied the decimal objects before encoding. Vector.getObject is a second public path. A signed unscaled value of −123456789 denotes −1234567.89 at scale 2. | The merge loses sign or scale, returns the neighboring slot, or disagrees with the original value. |
| apache/arrow-java#1518.2 · Control | Read numeric 0.00 at slot 0 with the holder and vector APIs. | Both revisions should return BigDecimal with unscaled value 0 and scale 2. | Zero uses an all-zero fixed-width representation, independent of byte order, at byte offset zero. | A nonzero number, null, or a scale different from 2 on either revision. |
| apache/arrow-java#1518.3 · Challenge | Store the same negative value in the last slot of DecimalVector and Decimal256Vector, changing only adjacent valid values between two runs. Populate a nullable holder through vector.get, copy its buffer, byte start, precision and scale to the matching non-null holder, and compare nullable and non-null reader outputs. | On the merge both widths and both kinds of reader should return exactly −1234567.89 in every run regardless of preceding values. | Sign extension changes physical width while preserving the mathematical integer. Slot 2 begins at byte offset 32 or 64 depending on the vector width. | Changing an adjacent value changes the target, or one width or holder class yields a different result. |

**Evidence and limits.** The upstream test reads two nonzero offsets and both signs in 128- and 256-bit vectors using nullable and non-null holder readers. An index-zero positive-only read can miss a displacement or sign error. The neighbor-variation comparison is a prediction.

**Technical notes.** The Arrow vector Maven module generates the reader classes from HolderReaderImpl.java. Use the module’s ArrowBuf allocator and matching generated classes. Native byte order conditions the historical prediction. Close the allocator after the vectors.

**Sources.** [HolderReaderImpl.java](https://github.com/apache/arrow-java/blob/1718ad7aeef4209d3a620541672e1af7fc5cbb1e/vector/src/main/codegen/templates/HolderReaderImpl.java) · [DecimalUtility.java](https://github.com/apache/arrow-java/blob/1718ad7aeef4209d3a620541672e1af7fc5cbb1e/vector/src/main/java/org/apache/arrow/vector/util/DecimalUtility.java) · [DecimalVector.java](https://github.com/apache/arrow-java/blob/1718ad7aeef4209d3a620541672e1af7fc5cbb1e/vector/src/main/java/org/apache/arrow/vector/DecimalVector.java) · [Decimal256Vector.java](https://github.com/apache/arrow-java/blob/1718ad7aeef4209d3a620541672e1af7fc5cbb1e/vector/src/main/java/org/apache/arrow/vector/Decimal256Vector.java) · [TestDecimalHolderDecoding.java](https://github.com/apache/arrow-java/blob/1718ad7aeef4209d3a620541672e1af7fc5cbb1e/vector/src/test/java/org/apache/arrow/vector/TestDecimalHolderDecoding.java) · [pom.xml](https://github.com/apache/arrow-java/blob/1718ad7aeef4209d3a620541672e1af7fc5cbb1e/vector/pom.xml) · [Related issue #1228](https://github.com/apache/arrow-java/issues/1228).

## apache/arrow-java#1342 · Decimal values are valid at exactly the declared precision

**Change and revisions.** [Merged PR #1342](https://github.com/apache/arrow-java/pull/1342). Scalar validation accepts a value whose precision equals the vector precision when the scales match. Before `f745a59d4c944ce47c109b89be021915b3484cce`, after `2f35627084d27e06fcaca800bc05c772e3fc1113`. [Landed comparison](https://github.com/apache/arrow-java/compare/f745a59d4c944ce47c109b89be021915b3484cce...2f35627084d27e06fcaca800bc05c772e3fc1113).

**Public scenario.** Use a RootAllocator and allocate two entries in a DecimalVector or Decimal256Vector declared with precision 5 and scale 2. Set both values, mark their validity and set the value count to two. Call validateScalars(), then inspect the entries using getObject(index). Close the vector and allocator.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/arrow-java#1342.1 · Intent | Store 999.99 and −999.99 as defined values, using either width. | Parent validation is predicted to throw ValidateException. The merge should accept both and return BigDecimal values with those digits, signs and scale 2. | Both unscaled magnitudes have five digits. The decimal precision counts magnitude digits without the sign. The upstream test validates this pair at 128 and 256 bits. | Validation rejects equality, changes scale, or getObject returns a different value. |
| apache/arrow-java#1342.2 · Control | Store 99.99 with the same declaration. In a separate vector use the raw-buffer helper in the regression to store 1000.00 as a defined value. | Both should validate the four-digit value and reject the six-digit one with ValidateException. | The valid magnitude has four digits. The invalid one has six but still fits physically in either buffer width. | A smaller value is rejected, or a physically encodable but out-of-precision value passes. |
| apache/arrow-java#1342.3 · Challenge | Populate the boundary pair via public setSafe calls, reversing the signs’ order. Transfer the two values by getObject and setSafe into a separately allocated vector of the other decimal width, with the same declared precision and scale. | On the merge both vectors should validate and return the same signed pair in the new order. | Logical decimal precision and scale are unchanged by backing width. Crossing two public setters and readers checks both sign and logical scale. | One width accepts the values but the other rejects them, or the transferred pair changes order, sign or scale. |

**Evidence and limits.** The upstream fixture writes raw decimal buffer bytes, sets validity bits and checks validateScalars for both widths. This isolates validation. It does not establish behavior through public setters and independent typed readback.

**Technical notes.** The Arrow Java vector Maven module supplies DecimalVector, Decimal256Vector and DecimalUtility. A working Arrow memory allocator implementation is needed for the off-heap buffers. Use the same compatible memory provider on both revisions.

**Sources.** [DecimalUtility.java](https://github.com/apache/arrow-java/blob/2f35627084d27e06fcaca800bc05c772e3fc1113/vector/src/main/java/org/apache/arrow/vector/util/DecimalUtility.java) · [TestDecimalPrecisionBoundary.java](https://github.com/apache/arrow-java/blob/2f35627084d27e06fcaca800bc05c772e3fc1113/vector/src/test/java/org/apache/arrow/vector/TestDecimalPrecisionBoundary.java) · [pom.xml](https://github.com/apache/arrow-java/blob/2f35627084d27e06fcaca800bc05c772e3fc1113/vector/pom.xml).

## apache/avro#2282 · Preserve a decimal’s individual scale in an Avro bytes field

**Change and revisions.** [Merged PR #2282](https://github.com/apache/avro/pull/2282). The new Java logical type `big-decimal` carries each value’s unscaled integer and scale in its encoded bytes. A schema can now describe both 12.3 and 12.30 without choosing a shared scale. Before `4ec81bd0cdc8615e833582f257684cb61c892578`, after `3ea027ac26b41edc0f08fd8c042ee918c523bdac`. [Landed comparison](https://github.com/apache/avro/compare/4ec81bd0cdc8615e833582f257684cb61c892578...3ea027ac26b41edc0f08fd8c042ee918c523bdac).

**Public scenario.** Using the merged `Conversions.BigDecimalConversion`, obtain its recommended bytes schema and `LogicalTypes.bigDecimal()`. Encode two values constructed from the strings `12.3` and `12.30`. Decode each with a fresh converter and compare both the unscaled integer and the scale.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/avro#2282.1 · Intent | Encode and recover the two differently scaled inputs under one schema. | The parent has no BigDecimalConversion API for this logical type. On the merge the pairs should be (123, 1) and (1230, 2), respectively. | BigDecimal equality includes scale. The pinned specification puts the scale in the value. | Either decoded scale changes, even if compareTo returns zero. |
| apache/avro#2282.2 · Control | Use the separate existing DecimalConversion with a bytes schema annotated decimal(6,2) and input −12.30. | Both revisions should return unscaled −1230 and scale 2. | The existing fixed-scale decimal interprets the signed big-endian integer at the schema’s scale. | The sign, integer or scale changes, or a valid value is rejected. |
| apache/avro#2282.3 · Challenge | On the merge concatenate the converter’s encoded 7 (scale 0) and 12.30. Present only the latter as a heap ByteBuffer slice, and compare with a standalone copy of those same remaining bytes. | Both views should decode to 12.30 if fromBytes honors the active view. The landed use of value.array() predicts the slice may instead decode the preceding 7. | The two views expose the same byte sequence, and the prefix is itself one complete encoding. The comparison needs no assumption about interoperability with another language. | The standalone value is 12.30 while the sliced value is 7, differs in scale, or throws. |

**Evidence and limits.** AVRO-3779 requests per-value precision and scale. The landed parameterized test compares BigDecimal values after round trips on the exact buffers produced by the converter. The specific-record test also adds a big-decimal field. Neither establishes sliced-buffer behavior. Numeric equality alone would miss lost trailing zeros.

**Technical notes.** The conversion is in lang/java/avro. The pinned specification restricts this logical type to bytes and identifies Java support. The specific-record fixture also changes its .avsc and the IDL grammar. A caller using a public conversion directly can supply the identical schema to both independent converter instances.

**Sources.** [Conversions.java](https://github.com/apache/avro/blob/3ea027ac26b41edc0f08fd8c042ee918c523bdac/lang/java/avro/src/main/java/org/apache/avro/Conversions.java) · [LogicalTypes.java](https://github.com/apache/avro/blob/3ea027ac26b41edc0f08fd8c042ee918c523bdac/lang/java/avro/src/main/java/org/apache/avro/LogicalTypes.java) · [TestBigDecimalConversion.java](https://github.com/apache/avro/blob/3ea027ac26b41edc0f08fd8c042ee918c523bdac/lang/java/avro/src/test/java/org/apache/avro/TestBigDecimalConversion.java) · [TestRecordWithLogicalTypes.avsc](https://github.com/apache/avro/blob/3ea027ac26b41edc0f08fd8c042ee918c523bdac/lang/java/avro/src/test/resources/TestRecordWithLogicalTypes.avsc) · [_index.md](https://github.com/apache/avro/blob/3ea027ac26b41edc0f08fd8c042ee918c523bdac/doc/content/en/docs/%2B%2Bversion%2B%2B/Specification/_index.md) · [pom.xml](https://github.com/apache/avro/blob/3ea027ac26b41edc0f08fd8c042ee918c523bdac/lang/java/avro/pom.xml) · [AVRO-3779](https://issues.apache.org/jira/browse/AVRO-3779).

## apache/avro#2520 · Avro duration converts three unsigned fixed-width fields without losing their units

**Change and revisions.** [Merged PR #2520](https://github.com/apache/avro/pull/2520). Java adds LogicalTypes.duration(), TimePeriod and DurationConversion for Avro’s 12-byte fixed duration logical type. Register the conversion on a GenericData instance when requesting logical values. Before `119c3fc99203cf6fb63dda7c3bb307c8841f179a`, after `abe6d421e82fa1d7e2ff4ae19b8a73f2e75ca396`. [Landed comparison](https://github.com/apache/avro/compare/119c3fc99203cf6fb63dda7c3bb307c8841f179a...abe6d421e82fa1d7e2ff4ae19b8a73f2e75ca396).

**Public scenario.** Give a fixed(12) schema the duration annotation. In an independent plain-fixed writer, use the little-endian 4-byte encodings for months 1, days 2 and milliseconds 3 in that order. Read with a GenericDatumReader created by GenericData configured with new Conversions.DurationConversion(). Also read with an unannotated fixed(12) reader of the same name or the mutual aliases from the regression.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/avro#2520.1 · Intent | Read the manually supplied bytes under the logical reader schema. | The parent lacks the new Java DurationConversion and TimePeriod API. On the merge read a TimePeriod with getters 1 month, 2 days and 3 milliseconds. | Each independently encoded four-byte word has its own unit. Treating days as months or milliseconds cannot preserve these three getter values. | A GenericFixed escapes the configured reader, a getter changes, or decoding fails on the merge. |
| apache/avro#2520.2 · Control | Read the same fixture with a plain fixed(12) writer and reader schema and an ordinary GenericData instance. | Both revisions should return GenericFixed containing the twelve original bytes unchanged. | The unannotated physical representation is a named Avro fixed value of known size. No unit conversion participates. | An altered byte, length or unexpected logical Java type on either revision. |
| apache/avro#2520.3 · Challenge | On the merge write TimePeriod.of(1, 2, 4294967295L) with the registered conversion. Read back with both plain-fixed and duration reader schemas. | The first eight bytes must stay identical to the baseline, the last four must all be FF, and the logical getter must return 4294967295L. Replacing the final component with zero may change only the last four bytes. | The maximum unsigned 32-bit word is all ones, distinct from signed −1. A second reader without conversion exposes the physical field boundary. | The sign is lost, months or days change, or the raw schema and logical getters disagree. |

**Evidence and limits.** The pinned generic regression writes and reads both ways with shared aliases and randomly chosen component values below 1000. A round trip using only one conversion implementation could conceal reciprocal byte-order errors. The all-ones field and raw-reader comparison test the unsigned boundary. The pinned specification defines the three components as unsigned little-endian words. [Original AVRO-2123 report](https://issues.apache.org/jira/browse/AVRO-2123)

**Technical notes.** The lang/java/avro module contains TimePeriod, DurationConversion and LogicalTypes. Use the GenericData instance with the registered conversion on the logical side. Duration needs a fixed schema of exactly 12 bytes. Months, days and milliseconds remain separate units. TimePeriod.of’s Javadoc prints 4294967296 as an endpoint. Both the format specification and the range guard admit at most 4294967295.

**Sources.** [Conversions.java](https://github.com/apache/avro/blob/abe6d421e82fa1d7e2ff4ae19b8a73f2e75ca396/lang/java/avro/src/main/java/org/apache/avro/Conversions.java) · [LogicalTypes.java](https://github.com/apache/avro/blob/abe6d421e82fa1d7e2ff4ae19b8a73f2e75ca396/lang/java/avro/src/main/java/org/apache/avro/LogicalTypes.java) · [TimePeriod.java](https://github.com/apache/avro/blob/abe6d421e82fa1d7e2ff4ae19b8a73f2e75ca396/lang/java/avro/src/main/java/org/apache/avro/util/TimePeriod.java) · [TestGenericLogicalTypes.java](https://github.com/apache/avro/blob/abe6d421e82fa1d7e2ff4ae19b8a73f2e75ca396/lang/java/avro/src/test/java/org/apache/avro/generic/TestGenericLogicalTypes.java) · [_index.md](https://github.com/apache/avro/blob/abe6d421e82fa1d7e2ff4ae19b8a73f2e75ca396/doc/content/en/docs/%2B%2Bversion%2B%2B/Specification/_index.md) · [pom.xml](https://github.com/apache/avro/blob/abe6d421e82fa1d7e2ff4ae19b8a73f2e75ca396/lang/java/avro/pom.xml) · [Related PR #1263](https://github.com/apache/avro/pull/1263) · [Related PR #3416](https://github.com/apache/avro/pull/3416).

## apache/parquet-java#3830 · Dictionary pages belong to a sequence of column names

**Change and revisions.** [Merged PR #3830](https://github.com/apache/parquet-java/pull/3830). The Parquet reader keys column metadata and dictionary pages by individual path components. A literal dot inside a field name retains its identity. Before `6ae2a8f173dcd2a121e41e3dc05d3dfc284d84a5`, after `bca2eaeac0afc88197c622f0f27c8a55739a5be9`. [Landed comparison](https://github.com/apache/parquet-java/compare/6ae2a8f173dcd2a121e41e3dc05d3dfc284d84a5...bca2eaeac0afc88197c622f0f27c8a55739a5be9).

**Public scenario.** Use SimpleGroupFactory with two required string columns, a top-level field named "a.b" and field "b" under group "a". Write 100 alternating rows with ExampleParquetWriter and dictionary encoding enabled, then close it. Open ParquetFileReader and call getNextDictionaryReader() before loading the row group. Obtain ColumnDescriptors from the two component arrays and read their dictionaries.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/parquet-java#3830.1 · Intent | Write top-level "one"/"two" and nested "nested-one"/"nested-two". Decode all IDs from both dictionary pages. | The issue reports a collision before. The merge must return sets {"one","two"} and {"nested-one","nested-two"} for the respective descriptors. Dictionary ID order may vary. | Each set can be computed independently from the producer’s values at that component path. | Both pages exist but a decoded value belongs to the other column. |
| apache/parquet-java#3830.2 · Control | Use otherwise identical rows and a top-level column named "plain" instead of "a.b". | Both revisions should yield the same two distinct value sets as before for the corresponding columns. | The two flattened metadata names are distinct under either representation. | Either dictionary omits one of its two values or contains a sibling value. |
| apache/parquet-java#3830.3 · Challenge | Hold all top-level values fixed, replace only the nested values with "new-one"/"new-two", and open a fresh reader. Request nested, top-level, then nested a second time. | On the merge the top-level set stays {"one","two"}. Both nested requests return the new set. | Varying only a sibling must not affect a column dictionary, even if the sibling’s page is already cached. | Changing nested values changes the top-level set, or either set depends on request order. |

**Evidence and limits.** The regression writes a real Hadoop-backed file and decodes both dictionaries. Checking that two pages are non-null, or testing the related Bloom-filter fix, misses dictionary identity. The swapped request order with modified nested data probes cache reuse.

**Technical notes.** Use parquet-hadoop and its TestParquetWriter fixture. Keep low-cardinality values together in one row group so dictionary pages exist. Loading the row group first routes dictionary reads to another page store.

**Sources.** [DictionaryPageReader.java](https://github.com/apache/parquet-java/blob/bca2eaeac0afc88197c622f0f27c8a55739a5be9/parquet-hadoop/src/main/java/org/apache/parquet/hadoop/DictionaryPageReader.java) · [TestParquetWriter.java](https://github.com/apache/parquet-java/blob/bca2eaeac0afc88197c622f0f27c8a55739a5be9/parquet-hadoop/src/test/java/org/apache/parquet/hadoop/TestParquetWriter.java) · [pom.xml](https://github.com/apache/parquet-java/blob/bca2eaeac0afc88197c622f0f27c8a55739a5be9/parquet-hadoop/pom.xml) · [Issue #3828](https://github.com/apache/parquet-java/issues/3828) · [Related PR #3827](https://github.com/apache/parquet-java/pull/3827).

## ThreeTen/threeten-extra#433 · Count complete units between offset dates in either direction

**Change and revisions.** [Merged PR #433](https://github.com/ThreeTen/threeten-extra/pull/433). OffsetDate.until adjusts an end date to the start offset and counts whole date units. The change corrects negative partial days and extends date arithmetic across the extreme supported offsets and years. Before `9b5e316f5fad89ef80a05d8cdec522315c2e26ba`, after `cad4ef4bdf209d8d76016e9d8322c18eab7c8cb0`. [Landed comparison](https://github.com/ThreeTen/threeten-extra/compare/9b5e316f5fad89ef80a05d8cdec522315c2e26ba...cad4ef4bdf209d8d76016e9d8322c18eab7c8cb0).

**Public scenario.** Construct dates with `OffsetDate.of` and call `start.until(end, ChronoUnit.DAYS)` in both directions. Treat each local date as midnight at its stated fixed offset. For ordinary dates compare the returned count with `Duration.between(start.atTime(MIDNIGHT), end.atTime(MIDNIGHT)).getSeconds() / 86400` using integer division toward zero.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| ThreeTen/threeten-extra#433.1 · Intent | Start at 2000-01-01 UTC and end on the same local date at +05:00. | The parent calculation predicts −1 day forward and 0 in reverse. The merge should return 0 in both directions. | Subtracting the midnight instants gives −5 and +5 hours. Neither interval contains a whole day. | Either merged count is nonzero, or the parent already returns zero in the forward direction. |
| ThreeTen/threeten-extra#433.2 · Control | Use UTC on 2000-01-01 and 2000-01-03. | Both revisions should give 2 forward and −2 in reverse. | Exactly 48 hours separate the instants and the offset does not change. | A sign error or any magnitude other than 2. |
| ThreeTen/threeten-extra#433.3 · Challenge | Compare OffsetDate.MIN and MAX in both directions, using DAYS and WEEKS. | The parent is expected to throw on offset normalization beyond LocalDate’s bounds. On the merge let D = LocalDate.MAX.toEpochDay() − LocalDate.MIN.toEpochDay() + 1. Expect D and −D days, and D/7 and −(D/7) whole weeks. | MIN’s +18:00 and MAX’s −18:00 add 36 hours to the epoch-day interval. A whole week contains seven days. | An exception on the merge, loss of the extra complete day, or disagreement between days and weeks. |

**Evidence and limits.** The PR attributes the negative result to rounding away from zero. The pinned test compares ordinary cases with offsets at midnight and gives independent arithmetic for the extreme day count. Opposite offsets can affect a result even when the printed local dates match. Equal-offset tests leave that branch untouched.

**Technical notes.** Use org.threeten.extra.OffsetDate from ThreeTen-Extra and java.time fixed ZoneOffset values. The epoch-day oracle stays in long arithmetic and requires no zone database or platform default zone. The prediction is limited to the stated DAYS and WEEKS cases.

**Sources.** [OffsetDate.java](https://github.com/ThreeTen/threeten-extra/blob/cad4ef4bdf209d8d76016e9d8322c18eab7c8cb0/src/main/java/org/threeten/extra/OffsetDate.java) · [TestOffsetDate.java](https://github.com/ThreeTen/threeten-extra/blob/cad4ef4bdf209d8d76016e9d8322c18eab7c8cb0/src/test/java/org/threeten/extra/TestOffsetDate.java) · [pom.xml](https://github.com/ThreeTen/threeten-extra/blob/cad4ef4bdf209d8d76016e9d8322c18eab7c8cb0/pom.xml).

## ReactiveX/RxJava#5101 · Cancelling Maybe concatenation prevents later subscription side effects

**Change and revisions.** [Merged PR #5101](https://github.com/ReactiveX/RxJava/pull/5101). RxJava 2 rechecks cancellation before moving from an emitted Maybe value to the next source. A downstream that has already accepted its first element can thereby prevent later subscriptions. Before `5a8be22b6501feefe10fb00731c00ce1ad215b89`, after `6daf59ebc19f5ef8914086fe466823f51ca628a9`. [Landed comparison](https://github.com/ReactiveX/RxJava/compare/5a8be22b6501feefe10fb00731c00ce1ad215b89...6daf59ebc19f5ef8914086fe466823f51ca628a9).

**Public scenario.** Create two synchronous cold Maybe sources with separate subscription counters. Each increments its own counter before calling onSuccess, with values 1 and 2 respectively. Subscribe using Maybe.concatArray(first, second).firstElement().test(), then inspect both counters and the observer’s terminal result.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| ReactiveX/RxJava#5101.1 · Intent | First and second sources would both succeed immediately, while firstElement consumes only the first. | The PR reports the parent still enters the next source's subscription before cancelling it. The merge should return only 1 successfully, with first counter 1 and second counter 0. | firstElement cancels the concatenated Flowable during the first item. An entry-side counter observes external work even if its downstream signals are dropped. | On the merge a second subscription occurs, or the subscriber loses its first success. |
| ReactiveX/RxJava#5101.2 · Control | Consume the full concatArray sequence with ordinary positive demand. | Both revisions should subscribe to both sources once, in first/second order, emit [1,2] and complete. | A normal concat without early cancellation must consume the second source after the first finishes. | An omitted or duplicate subscription, a reordered item, or a missing completion. |
| ReactiveX/RxJava#5101.3 · Challenge | Prepend Maybe.empty() and use the iterable overload Maybe.concat on all three. Compare with the array form with the same empty prefix and firstElement. | On the merge the empty source must be entered, then the first value source must supply 1, and the second value source must remain unentered in both representations. | An empty source cannot satisfy firstElement. The cancellation point depends on the first actual value and is independent of array versus iterable representation. | An empty prefix suppresses the first value, or the unused source executes only in one representation. |

**Evidence and limits.** Issue #5100 describes the visible extra subscription. Upstream tests use the same counted source twice and assert the count alongside the result, including delay-error variants. A result-only test can pass on a parent that starts cancelled work.

**Technical notes.** This is the RxJava 2 io.reactivex API. Keep the sources synchronous, with the subscription counter incremented before any disposed check. The claim concerns entering a source, including sources that immediately drop their signal.

**Sources.** [MaybeConcatArray.java](https://github.com/ReactiveX/RxJava/blob/6daf59ebc19f5ef8914086fe466823f51ca628a9/src/main/java/io/reactivex/internal/operators/maybe/MaybeConcatArray.java) · [MaybeConcatIterable.java](https://github.com/ReactiveX/RxJava/blob/6daf59ebc19f5ef8914086fe466823f51ca628a9/src/main/java/io/reactivex/internal/operators/maybe/MaybeConcatIterable.java) · [MaybeConcatArrayTest.java](https://github.com/ReactiveX/RxJava/blob/6daf59ebc19f5ef8914086fe466823f51ca628a9/src/test/java/io/reactivex/internal/operators/maybe/MaybeConcatArrayTest.java) · [MaybeConcatIterableTest.java](https://github.com/ReactiveX/RxJava/blob/6daf59ebc19f5ef8914086fe466823f51ca628a9/src/test/java/io/reactivex/internal/operators/maybe/MaybeConcatIterableTest.java) · [build.gradle](https://github.com/ReactiveX/RxJava/blob/6daf59ebc19f5ef8914086fe466823f51ca628a9/build.gradle) · [Related issue #5100](https://github.com/ReactiveX/RxJava/issues/5100).

## reactor/reactor-core#937 · Concatenation delivers later values before a delayed inner error

**Change and revisions.** [Merged PR #937](https://github.com/reactor/reactor-core/pull/937). In delay-until-end mode, errors from a callable inner source are accumulated while concatenation proceeds to the remaining sources. Before `0ad7976bf1c02bccc28bb478758591bc8108b11a`, after `af0cb628ece3c0a543512ea9913c4ff72ba18566`. [Landed comparison](https://github.com/reactor/reactor-core/compare/0ad7976bf1c02bccc28bb478758591bc8108b11a...af0cb628ece3c0a543512ea9913c4ff72ba18566).

**Public scenario.** Create one exception e. Pass Flux.just(Flux.just(1,2), Mono.error(e), Flux.just(3,4)) as the single publisher-of-publishers argument to Flux.concatDelayError. Subscribe and record all onNext values followed by the sole onError or onComplete signal.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| reactor/reactor-core#937.1 · Intent | Use the callable error source between two nonempty sources. | The issue reports early onError after 2 for the publisher-of-publishers form. On the merge expect 1,2,3,4 followed by the single error e. | Sequential concatenation fixes source order, and delaying a single error until the end allows the third source to emit. | The merge terminates before 4, changes order, completes normally, or delivers multiple errors. |
| reactor/reactor-core#937.2 · Control | Replace Mono.error(e) with Mono.empty(). | Both revisions should deliver 1,2,3,4 followed by one completion. | An empty inner source contributes neither elements nor errors. | The trailing values disappear, an error appears, or the subscriber never completes. |
| reactor/reactor-core#937.3 · Challenge | Keep the same sources and e, expose or hide the error publisher with Mono.error(e).hide(), and subscribe separately using concatMapDelayError(identity,true,32). Request one item at a time until the stream terminates. | On the merge both subscriptions should deliver the same ordered four values then e, with no value in excess of demand. | Hiding the publisher changes access to the callable optimization while preserving its signals. Prefetch may affect upstream requests but not downstream demand. | Only one representation delivers 3 and 4, the terminal cause differs, or any value arrives without demand. |

**Evidence and limits.** The landed tests exercise multiple public concat and merge operators, including Mono.error and Flux.error, and compare message text. The issue reports that the varargs form already succeeded in its example. Simply observing a terminal error cannot distinguish early termination. [Issue #936](https://github.com/reactor/reactor-core/issues/936).

**Technical notes.** Use the reactor-core Gradle project. Issue #936 reports Reactor Core 3.1.0.RELEASE on Java 8. Choose the single outer publisher overload for the main case. The explicit true argument on concatMapDelayError requests delay until the end.

**Sources.** [Flux.java](https://github.com/reactor/reactor-core/blob/af0cb628ece3c0a543512ea9913c4ff72ba18566/reactor-core/src/main/java/reactor/core/publisher/Flux.java) · [FluxConcatMap.java](https://github.com/reactor/reactor-core/blob/af0cb628ece3c0a543512ea9913c4ff72ba18566/reactor-core/src/main/java/reactor/core/publisher/FluxConcatMap.java) · [FluxConcatMapTest.java](https://github.com/reactor/reactor-core/blob/af0cb628ece3c0a543512ea9913c4ff72ba18566/reactor-core/src/test/java/reactor/core/publisher/FluxConcatMapTest.java) · [build.gradle](https://github.com/reactor/reactor-core/blob/af0cb628ece3c0a543512ea9913c4ff72ba18566/build.gradle).

## reactor/reactor-core#3783 · Discard every concatenated source value before thenMany emits its tail

**Change and revisions.** [Merged PR #3783](https://github.com/reactor/reactor-core/pull/3783). The merged Flux.thenMany discards the complete receiver’s values before subscribing to the supplied publisher. The old concatenation shortcut discarded values from only the last constituent. Before `92c8ea05eaa4e009fe5459bd4a1fe51b244bcc52`, after `2a664dd587e74793fb473d81e8b26a199ff07d1e`. [Landed comparison](https://github.com/reactor/reactor-core/compare/92c8ea05eaa4e009fe5459bd4a1fe51b244bcc52...2a664dd587e74793fb473d81e8b26a199ff07d1e).

**Public scenario.** Subscribe to `Flux.concat(Flux.just("a"), Flux.just("b")).thenMany(Flux.just("c"))`. Request enough demand for every signal and record each onNext value and the terminal signal. For an error use a named exception and a deferred tail whose subscription increments a counter.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| reactor/reactor-core#3783.1 · Intent | Use the two successful sources and the one-element tail. | Issue #3777 reports the parent-like first observation a. The parent source predicts [a,c], complete. The merge should emit [c], complete. | thenMany’s public documentation discards upstream elements. Both a and b belong to the receiver. | An upstream value gets through on the merge, c is missing or duplicated, or the completion signal is absent. |
| reactor/reactor-core#3783.2 · Control | Hide the identity of the same concatenation with .hide() immediately before thenMany. | Both revisions should emit only c and complete once. | The issue reports this variation passes. Hiding identity preserves the sequence of source signals. | The hidden form emits a or b, or changes the terminal result. |
| reactor/reactor-core#3783.3 · Challenge | Keep the first source and tail fixed, replace the second source with Flux.error(e), and use a tail subscription counter. | On the merge observe no values, the identical e once and zero tail subscriptions. The parent shortcut predicts a preceding a but likewise no subscription to the tail. | The receiver’s completion is the condition for starting the tail. An error terminates that receiver even after earlier values. | The tail is subscribed, a value escapes on the merge, or a different terminal signal replaces e. |

**Evidence and limits.** The original report recorded an unexpected a and the effect of hiding the sequence. The new StepVerifier test requires exactly c and completion. Existing chain tests also assert the internal concat-array size, which cannot establish what an ordinary downstream subscriber saw. The error and subscription-counter relation remains open.

**Technical notes.** Use reactor-core for Flux and reactor-test for StepVerifier if used. Keep sources synchronous and deterministic, with no global operator debugging. The original issue reports that enabling operator debugging hid the failure.

**Sources.** [Flux.java](https://github.com/reactor/reactor-core/blob/2a664dd587e74793fb473d81e8b26a199ff07d1e/reactor-core/src/main/java/reactor/core/publisher/Flux.java) · [FluxConcatArray.java](https://github.com/reactor/reactor-core/blob/2a664dd587e74793fb473d81e8b26a199ff07d1e/reactor-core/src/main/java/reactor/core/publisher/FluxConcatArray.java) · [FluxThenManyTest.java](https://github.com/reactor/reactor-core/blob/2a664dd587e74793fb473d81e8b26a199ff07d1e/reactor-core/src/test/java/reactor/core/publisher/FluxThenManyTest.java) · [build.gradle](https://github.com/reactor/reactor-core/blob/2a664dd587e74793fb473d81e8b26a199ff07d1e/reactor-core/build.gradle) · [Related issue #3777](https://github.com/reactor/reactor-core/issues/3777).

## ReactiveX/RxJava#6664 · New reactive groups expose their first value or its selector error

**Change and revisions.** [Merged PR #6664](https://github.com/ReactiveX/RxJava/pull/6664). Observable.groupBy now queues a first item before an unclaimed group can finish. The Flowable change also exposes a newly created group when selection of that item’s value fails. Before `c2dc134221ad6bd623f6160ec5338ad4496c5112`, after `cb7ff83a2444731dd7eca4760e9410a6c2980b6d`. [Landed comparison](https://github.com/ReactiveX/RxJava/compare/c2dc134221ad6bd623f6160ec5338ad4496c5112...cb7ff83a2444731dd7eca4760e9410a6c2980b6d).

**Public scenario.** On RxJava 3 run Observable.just(7).groupBy with a constant key K and identity value. Save the single GroupedObservable in an outer observer without subscribing to it in onNext. Once the outer observer completes, subscribe to the saved group and record its values and terminal event.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| ReactiveX/RxJava#6664.1 · Intent | Subscribe to the saved Observable group only after the one-item outer sequence ends. | The PR describes first-item loss from premature abandonment. On the merge the single K group must deliver 7 exactly once and complete. | Only one source item exists. Delaying the subscription to this abandoned group cannot give it a second source item. The value already assigned to it is the one observable distinction. | The merge yields an empty completed group, a duplicated 7, or a different key. |
| ReactiveX/RxJava#6664.2 · Control | For Observable.just(7,8) with the same constant key and no failing selector, subscribe to the group synchronously inside outer onNext. | Both revisions should yield one group with [7,8] and normal completion. | The synchronous inner observer claims the group before abandonment. Each source item maps unchanged to the same key. | A missing or duplicate item, extra group, or error on either revision. |
| ReactiveX/RxJava#6664.3 · Challenge | For a single item 7, retain key K but make the value selector throw a particular exception instance. Subscribe immediately to each emitted group. Run the same fixture as a Flowable with unbounded demand and as an Observable. | On the merge both outer observers should emit one K group and terminate with the thrown error. Each inner observer should receive that same exception with zero values. The parent Flowable can suppress the group on this path. | The key is known before the value conversion. Independent inner and outer subscribers check where the selector’s failure becomes observable. | The outer error is correct but no group arrives, any inner succeeds, or either subscriber gets a replacement exception. |

**Evidence and limits.** The PR identifies both paths and relates them to intermittent issue #6663, while leaving the explanation of its second failure open. The new tests check failure on new and existing groups in both types. Observing only the outer terminal state cannot show whether a group lost its sole item or error.

**Technical notes.** The RxJava 3 Gradle project places these operators under io.reactivex.rxjava3. The delayed-group claim is scoped to a one-item synchronous Observable. The Flowable comparison explicitly supplies demand.

**Sources.** [ObservableGroupBy.java](https://github.com/ReactiveX/RxJava/blob/cb7ff83a2444731dd7eca4760e9410a6c2980b6d/src/main/java/io/reactivex/rxjava3/internal/operators/observable/ObservableGroupBy.java) · [FlowableGroupBy.java](https://github.com/ReactiveX/RxJava/blob/cb7ff83a2444731dd7eca4760e9410a6c2980b6d/src/main/java/io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupBy.java) · [ObservableGroupByTest.java](https://github.com/ReactiveX/RxJava/blob/cb7ff83a2444731dd7eca4760e9410a6c2980b6d/src/test/java/io/reactivex/rxjava3/internal/operators/observable/ObservableGroupByTest.java) · [FlowableGroupByTest.java](https://github.com/ReactiveX/RxJava/blob/cb7ff83a2444731dd7eca4760e9410a6c2980b6d/src/test/java/io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupByTest.java) · [build.gradle](https://github.com/ReactiveX/RxJava/blob/cb7ff83a2444731dd7eca4760e9410a6c2980b6d/build.gradle) · [Related issue #6663](https://github.com/ReactiveX/RxJava/issues/6663).

## resilience4j/resilience4j#2067 · A retry interval of zero and a negative stopping interval have different outcomes

**Change and revisions.** [Merged PR #2067](https://github.com/resilience4j/resilience4j/pull/2067). Asynchronous retry schedules another call for a zero delay. For exceptional outcomes, the retry context reports a negative delay as a terminal error event. Before `12f66a31d7b4619ed0ffd1fddee9da683c41b9b7`, after `a1a4acb85c83dbd1b1a67cd97dac994fb8bb034c`. [Landed comparison](https://github.com/resilience4j/resilience4j/compare/12f66a31d7b4619ed0ffd1fddee9da683c41b9b7...a1a4acb85c83dbd1b1a67cd97dac994fb8bb034c).

**Public scenario.** Register retry and error listeners on Retry.of with maxAttempts(3). Decorate a CompletionStage supplier using Retry.decorateCompletionStage and a live ScheduledExecutorService. Count supplier invocations and record events through completion. Use fresh Retry instances for each history.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| resilience4j/resilience4j#2067.1 · Intent | Every call fails with the same exception. Have intervalFunction return 0 on its first call and −1 on its second. | The parent stops the asynchronous call at zero. On the merge expect two supplier invocations, one retry event, one error event and an exceptionally completed stage carrying the failure. | Zero admits one immediately scheduled attempt. The next interval is a stop decision. The landed async test counts calls and events. | The merge stops after one invocation, schedules a third, or announces a retry for the stopping interval. |
| resilience4j/resilience4j#2067.2 · Control | The first call fails, the second succeeds with "ok", and the interval function always returns a positive one millisecond. | Both revisions should return "ok" after two invocations and one retry event. | A positive delay is eligible for scheduling on either revision. The eventual success ends the history. | A final error, a third invocation, or a missing retry event. |
| resilience4j/resilience4j#2067.3 · Challenge | Keep maxAttempts(3) but configure retryOnResult for the value "again". Return a completed stage containing "again" and an immediate interval of −1, with failAfterMaxAttempts disabled. | The merged code predicts one supplier call and a final value "again", while the result path publishes a retry event with delay −1 despite scheduling no second attempt. | The exceptional path branches on the sign before event publication. AsyncContext.onResult publishes RetryOnRetryEvent before returning its interval, and the async decorator stops at a negative value. | A second supplier call or absence of the predicted negative-delay retry event refutes the corresponding part of the reading. |

**Evidence and limits.** The new synchronous and asynchronous tests use exceptional outcomes and record retry/error events. They do not establish event consistency for retryable returned values. Issue #1565 discusses rate-limiting and the earlier interpretation of zero. Count calls alongside events to detect a notification for unscheduled work.

**Technical notes.** The resilience4j-retry Gradle module contains Retry’s asynchronous decorator and RetryImpl’s contexts. Keep the executor alive until the returned future finishes. Compare events after completion, without requiring a particular scheduling latency.

**Sources.** [Retry.java](https://github.com/resilience4j/resilience4j/blob/a1a4acb85c83dbd1b1a67cd97dac994fb8bb034c/resilience4j-retry/src/main/java/io/github/resilience4j/retry/Retry.java) · [RetryImpl.java](https://github.com/resilience4j/resilience4j/blob/a1a4acb85c83dbd1b1a67cd97dac994fb8bb034c/resilience4j-retry/src/main/java/io/github/resilience4j/retry/internal/RetryImpl.java) · [CallableTest.java](https://github.com/resilience4j/resilience4j/blob/a1a4acb85c83dbd1b1a67cd97dac994fb8bb034c/resilience4j-retry/src/test/java/io/github/resilience4j/retry/internal/CallableTest.java) · [CompletionStageRetryTest.java](https://github.com/resilience4j/resilience4j/blob/a1a4acb85c83dbd1b1a67cd97dac994fb8bb034c/resilience4j-retry/src/test/java/io/github/resilience4j/retry/internal/CompletionStageRetryTest.java) · [build.gradle](https://github.com/resilience4j/resilience4j/blob/a1a4acb85c83dbd1b1a67cd97dac994fb8bb034c/resilience4j-retry/build.gradle) · [Issue #1565](https://github.com/resilience4j/resilience4j/issues/1565).
