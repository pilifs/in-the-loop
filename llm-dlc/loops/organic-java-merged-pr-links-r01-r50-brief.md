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

**Evidence and limits.** The pinned tests check exception identity, membership, contents and size. PR discussion points to the existing MutableMapIterable Javadoc. Merely catching the exception misses a key published with no value. The colliding-key retry is a prediction.

**Technical notes.** Use the Maven eclipse-collections implementation with the matching eclipse-collections-api. The standard and strategy maps have distinct insertion code. Keep callbacks free of other map mutations.

**Sources.** [UnifiedMap.java](https://github.com/eclipse-collections/eclipse-collections/blob/4af700cda608e6817d7d17ab340b91442278cf14/eclipse-collections/src/main/java/org/eclipse/collections/impl/map/mutable/UnifiedMap.java) · [UnifiedMapWithHashingStrategy.java](https://github.com/eclipse-collections/eclipse-collections/blob/4af700cda608e6817d7d17ab340b91442278cf14/eclipse-collections/src/main/java/org/eclipse/collections/impl/map/strategy/mutable/UnifiedMapWithHashingStrategy.java) · [MutableMapIterableTestCase.java](https://github.com/eclipse-collections/eclipse-collections/blob/4af700cda608e6817d7d17ab340b91442278cf14/unit-tests-java8/src/test/java/org/eclipse/collections/test/map/mutable/MutableMapIterableTestCase.java).

## apache/commons-collections#688 · a rejected unique key leaves both collection views intact

**Change and revisions.** [Merged PR #688](https://github.com/apache/commons-collections/pull/688). Adding a value with an occupied transformed key used to mutate the caller’s collection before rejecting it. A unique index now checks the key first. Before `dad2ff61e516a601da8179708959263e38af8d68`, after `ca83f8699e10403be6987b92fb1a877743df8262`. [Landed comparison](https://github.com/apache/commons-collections/compare/dad2ff61e516a601da8179708959263e38af8d68...ca83f8699e10403be6987b92fb1a877743df8262).

**Public scenario.** Wrap an empty mutable list of strings with `IndexedCollection.uniqueIndexedCollection(list, Integer::valueOf)`. Add `"01"`, attempt to add `"1"`, catch the rejection, then read the original list, the decorator’s iterator and its integer-key lookup. Keep the list reference so the two reads are independent.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-collections#688.1 · Intent | Add the two distinct strings in that order under unique indexing. | Both should throw IllegalArgumentException on the second add. The PR reports that the parent nevertheless appends the second string. On the merge the list and iteration must contain only `"01"`, and `get(1)` must return `"01"`. | Both spellings denote integer key 1. The caller-owned list reveals a write even if the old index still returns its original value. | Merged code accepts the second string, changes either view, or loses the original mapping. |
| apache/commons-collections#688.2 · Control | Use distinct keys by adding `"01"` and `"2"` to a fresh unique wrapper. | Both adds succeed on each revision. The list is precisely those two strings, and lookups at 1 and 2 return the corresponding original spellings. | The two transformed keys are mathematically distinct, and the backing list preserves insertion order. | A valid add is rejected, or iteration and lookup disagree. |
| apache/commons-collections#688.3 · Challenge | After the rejected add, call `reindex()` on the same wrapper and then add `"2"`. | On the merge reindex should finish, add should succeed and both lookups should match the two values in the list. A leftover duplicate on the parent predicts another rejection during reindex. | Rebuilding solely from the caller-owned collection independently checks whether the earlier exception left a valid unique index. | On the merge reindex throws, a spurious entry reappears, or either surviving value is unreachable. |

**Evidence and limits.** The PR reports the exception after mutation and names the regression for `"01"` and `"1"`. Catching the exception or looking only at the first indexed value misses the corrupted backing list. Rebuilding and performing a later valid add are predictions.

**Technical notes.** Apache Commons Collections uses its root Maven project. Supply an initially empty, ordered ArrayList and a deterministic transformer. An external write to the list would invalidate the premise.

**Sources.** [IndexedCollection.java](https://github.com/apache/commons-collections/blob/ca83f8699e10403be6987b92fb1a877743df8262/src/main/java/org/apache/commons/collections4/collection/IndexedCollection.java) · [IndexedCollectionTest.java](https://github.com/apache/commons-collections/blob/ca83f8699e10403be6987b92fb1a877743df8262/src/test/java/org/apache/commons/collections4/collection/IndexedCollectionTest.java).

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

**Sources.** [ImmutableList.drv](https://github.com/vigna/fastutil/blob/a1840bcc81f0fe2fb495856dded719125d869242/drv/ImmutableList.drv) · [IntArrayListTest.java](https://github.com/vigna/fastutil/blob/a1840bcc81f0fe2fb495856dded719125d869242/test/it/unimi/dsi/fastutil/ints/IntArrayListTest.java) · [IntImmutableListTest.java](https://github.com/vigna/fastutil/blob/a1840bcc81f0fe2fb495856dded719125d869242/test/it/unimi/dsi/fastutil/ints/IntImmutableListTest.java).

## google/guava#8811 · rotating a primitive subarray by the smallest integer distance

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

**Sources.** [Ints.java](https://github.com/google/guava/blob/c0a8a1edc69393e8141424037571d9825f5fc0f4/guava/src/com/google/common/primitives/Ints.java) · [IntsTest.java](https://github.com/google/guava/blob/c0a8a1edc69393e8141424037571d9825f5fc0f4/guava-tests/test/com/google/common/primitives/IntsTest.java) · [Ints.java](https://github.com/google/guava/blob/c0a8a1edc69393e8141424037571d9825f5fc0f4/android/guava/src/com/google/common/primitives/Ints.java).
