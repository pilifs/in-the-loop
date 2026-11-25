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
