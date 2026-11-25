# Merged Java pull requests L01–L20 — caller-visible behavior

## Objective

For each landed change, compare what a caller can observe immediately before and after the merge. Each case gives a concrete history, a control and a second way to catch a wrong result. Historical reports and source inspections are identified separately from predictions about running the two revisions.

## google/gson#3059 · Gson — finding a numeric key after a JSON round trip

**Change and revisions.** Gson makes equal numeric primitives backed by different Java number types hash consistently. A map keyed by a programmatically constructed JSON number should recognize that number after parsing its JSON representation. [Merged PR #3059](https://github.com/google/gson/pull/3059) · [Landed comparison](https://github.com/google/gson/compare/961517decce0aa907c285c19d8b93d5c746ecdcb...5e277e42786ab6441b7dd6b1a8c34d545d132307)

Before `961517decce0aa907c285c19d8b93d5c746ecdcb` → after `5e277e42786ab6441b7dd6b1a8c34d545d132307`.

**Public scenario.** Create `k = new JsonPrimitive(42)`, put it into a fresh `HashMap<JsonPrimitive,String>` with value `"saved"`, then obtain `q = JsonParser.parseString(k.toString()).getAsJsonPrimitive()`. Observe equality in both directions, both hash codes, and `map.get(q)`. Use a fresh map per history.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| google/gson#3059.1 · Intent | Insert integer 42 and look up parsed JSON number 42. | Both compare equal. The parent hashes the two representations differently and lookup is predicted to miss. The merge must give equal hashes and return `"saved"`. | Issue #992 and the landed round-trip assertion establish the pair. Java’s equal-key hash contract gives the lookup oracle. | On the merge either equality direction fails, the hashes differ, or the parsed lookup misses. |
| google/gson#3059.2 · Control | Insert numeric 42 and seek `new JsonPrimitive("42")`, then seek another integer 42. | Both revisions must miss the JSON string and return the saved value for the integer. No constraint on collisions between unequal keys. | JSON strings and numbers have distinct types. The equal integer denotes the inserted key. | The string retrieves the value or the equal integer misses on either revision. |
| google/gson#3059.3 · Challenge | On the merge insert `new JsonPrimitive(-0.0)`, replace its value using parsed JSON `0`, and remove via `new JsonPrimitive(0L)`. | Replacement must return the original value with size one. Removal must return the replacement and leave the map empty. | The regression asserts equality and equal hashes for signed zero and integer zero. Replacement and removal exercise that equivalence across three producers and two map operations. | A second entry appears, either operation returns the wrong prior value, or a zero key survives removal. |

**Evidence and limits.** The PR reports failed map lookups and issue #992 supplies the historical contract violation. The landed test checks equality and hashes, including signed zero and a large integer rounded by binary64. It does not perform the replacement/removal history. Comparing just JSON text cannot establish map behavior.

**Technical notes.** The `gson` Maven module supplies both the public parser and tree type. Parsing the text constructs the numeric key through Gson itself. A caller need not instantiate its internal lazy-number class.

**Sources.** [Regression](https://github.com/google/gson/blob/5e277e42786ab6441b7dd6b1a8c34d545d132307/gson/src/test/java/com/google/gson/JsonPrimitiveTest.java) · [Equality and hash](https://github.com/google/gson/blob/5e277e42786ab6441b7dd6b1a8c34d545d132307/gson/src/main/java/com/google/gson/JsonPrimitive.java) · [Parser](https://github.com/google/gson/blob/5e277e42786ab6441b7dd6b1a8c34d545d132307/gson/src/main/java/com/google/gson/JsonParser.java) · [Module](https://github.com/google/gson/blob/5e277e42786ab6441b7dd6b1a8c34d545d132307/gson/pom.xml) · [Original report](https://github.com/google/gson/issues/992)

## apache/commons-collections#701 · Commons Collections — the cardinality of a multiset after removing a view entry

**Change and revisions.** Removing through either distinct-element view now subtracts every occurrence of the removed key from the backing multiset's total size. [Merged PR #701](https://github.com/apache/commons-collections/pull/701) · [Landed comparison](https://github.com/apache/commons-collections/compare/a70ffd614602fa07d2429d76f77abcd1816d0be9...e218502f9f82237404bbce8e8ba5f81ffb467198)

Before `a70ffd614602fa07d2429d76f77abcd1816d0be9` → after `e218502f9f82237404bbce8e8ba5f81ffb467198`.

**Public scenario.** Populate a fresh `HashMultiSet<String>` with three A and two B. Take an iterator from `uniqueSet()` or `entrySet()`. Read the first element or entry, record its key and count, then call that iterator's `remove()`. Inspect the original multiset through `size()`, `getCount`, `toArray()` and the other view. Derive expectations from the returned key because hash iteration order is unspecified.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-collections#701.1 · Intent | Independently remove the first key through each view on a fresh fixture. | The PR reports that the parent drops the key but leaves a stale size. On the merge the key count is zero, total size is five minus its old count, and the array contains precisely the surviving copies. | Sum the multiplicities in the input after deleting the observed key. The landed test exercises both views. | The key disappears but size stays five, an extra null is exported, or a surviving occurrence is lost. |
| apache/commons-collections#701.2 · Control | Use the ordinary occurrence iterator on the fresh multiset, call next and remove once. | Both revisions should have total size four and exactly one fewer copy of that key. The other key retains its original count. | The occurrence iterator visits single elements, while the view iterators visit distinct entries. | The whole key disappears, the count stays fixed, or total size differs from four. |
| apache/commons-collections#701.3 · Challenge | On the merge remove all three A through one view (advance until A), re-add A once, then remove B through a fresh iterator of the other view. Swap the view roles and repeat. | In both histories the array must contain just A, both views have one member, and the sole entry has count one. | A fresh frequency count after delete, reinsert and delete has exactly one A. This crosses both live views and tests whether future additions inherit a stale size. | Final counts appear correct through a view but array length, element, entry count or total size differs. |

**Evidence and limits.** The PR gives a parent example with three copies of a single key, size three and three null array slots after view removal. The landed test removes one key via each view in succession. The re-insertion history is an extension. Looking only at `contains(removed)` would accept the parent.

**Technical notes.** The root Maven project contains `MultiSet`, its concrete `HashMultiSet` and the shared map-backed view implementation. The fixture uses non-null strings, so any null in the resulting array is independently detectable.

**Sources.** [Multiset contract](https://github.com/apache/commons-collections/blob/e218502f9f82237404bbce8e8ba5f81ffb467198/src/main/java/org/apache/commons/collections4/MultiSet.java) · [Map-backed views](https://github.com/apache/commons-collections/blob/e218502f9f82237404bbce8e8ba5f81ffb467198/src/main/java/org/apache/commons/collections4/multiset/AbstractMapMultiSet.java) · [Concrete receiver](https://github.com/apache/commons-collections/blob/e218502f9f82237404bbce8e8ba5f81ffb467198/src/main/java/org/apache/commons/collections4/multiset/HashMultiSet.java) · [Regression](https://github.com/apache/commons-collections/blob/e218502f9f82237404bbce8e8ba5f81ffb467198/src/test/java/org/apache/commons/collections4/multiset/AbstractMultiSetTest.java) · [Build](https://github.com/apache/commons-collections/blob/e218502f9f82237404bbce8e8ba5f81ffb467198/pom.xml)

## remkop/picocli#1529 · picocli — dispatch after changing aliases of a registered subcommand

**Change and revisions.** Updating an attached child’s aliases now updates the parent’s dispatch table. The landed range includes the implementation, variable rename and final regression. Comparing only the final commit would show just the test. [Merged PR #1529](https://github.com/remkop/picocli/pull/1529) · [Landed comparison](https://github.com/remkop/picocli/compare/4090e3dd30f9a046a72a1450972848d55e656160...edd902c0348d3548afac12096b0b16ab69f52a79)

Before `4090e3dd30f9a046a72a1450972848d55e656160` → after `edd902c0348d3548afac12096b0b16ab69f52a79`.

**Public scenario.** Construct `new CommandLine(new Main())` for an annotated root with one callable subcommand named `sub`. Let that child record each invocation and return zero. Obtain its spec from `root.getSubcommands().get("sub").getCommandSpec()`. Use `root.execute(token)` and the invocation count to distinguish dispatch from a parse error. Use the default parser and no positional parameters.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| remkop/picocli#1529.1 · Intent | After registration set `aliases("first")`, execute first, replace it with `aliases("second")`, then execute first and second. | The parent is reported to leave registered aliases unchanged. On the merge first should execute once before replacement, then fail with a nonzero exit and no invocation. Second should then execute successfully. | Issue #1528 describes the stale parent. The landed test exercises successive additions and removals via execute. | The spec lists second yet the parent still executes first or rejects second. |
| remkop/picocli#1529.2 · Control | With no aliases, execute sub and then an unknown token. Repeat after attaching an ordinary distinct alias. | Both revisions should dispatch the primary name exactly once per successful call and reject the unknown token without invoking the child. | The primary name was supplied at registration and remains unchanged throughout. | Changing only aliases breaks sub or invokes the child on the unknown token. |
| remkop/picocli#1529.3 · Challenge | On the merge add the primary name itself as an alias with `aliases("sub")`, then clear aliases using an empty string array. Compare to a fresh root that never had aliases. | If the redundant alias is accepted, both roots should still dispatch sub. The landed source predicts the edited root instead loses its primary mapping when the alias is removed. | A registered primary name is independently sufficient for dispatch. Adding an alias for the same receiver passes the implementation’s duplicate check. | After the accepted edits, sub is absent from the parent lookup or returns a nonzero exit only on the edited root. |

**Evidence and limits.** Issue #1528 reports parent and child disagreeing. The regression verifies exit codes and alias arrays for ordinary distinct aliases. The primary-name collision is an unexecuted source prediction: both names share a map key and removal erases that key. Reading only the child’s alias array would miss it.

**Technical notes.** The root Gradle build contains `picocli.CommandLine`, including the public model and parser. The pinned file preview contains the full changed methods, and the complete `Issue1528` test is available. The submitted branch also contains a synchronization merge. The three corresponding changes appear consecutively on the target.

**Sources.** [Dispatch and model](https://github.com/remkop/picocli/blob/edd902c0348d3548afac12096b0b16ab69f52a79/src/main/java/picocli/CommandLine.java) · [Regression](https://github.com/remkop/picocli/blob/edd902c0348d3548afac12096b0b16ab69f52a79/src/test/java/picocli/Issue1528.java) · [Build](https://github.com/remkop/picocli/blob/edd902c0348d3548afac12096b0b16ab69f52a79/build.gradle) · [Issue](https://github.com/remkop/picocli/issues/1528)

## java-diff-utils/java-diff-utils#233 · java-diff-utils — equal lines in a patch rendered for a side-by-side viewer

**Change and revisions.** A renderer receiving explicit equal deltas should identify unchanged lines and apply the same equality formatting used for unchanged text between edits. [Merged PR #233](https://github.com/java-diff-utils/java-diff-utils/pull/233) · [Landed comparison](https://github.com/java-diff-utils/java-diff-utils/compare/eb188a96eacff8e80877714d42fa9e2fd4fec32a...6e0ec1e22d31013eedda0ca8a72d3d77d1abf98b)

Before `eb188a96eacff8e80877714d42fa9e2fd4fec32a` → after `6e0ec1e22d31013eedda0ca8a72d3d77d1abf98b`.

**Public scenario.** Create original lines [same, before] and revised lines [same, after]. Build a patch with `DiffUtils.diff(original, revised, true)`. Call `DiffRowGenerator.create().showInlineDiffs(false).build().generateDiffRows(original, patch)`. Read each row’s tag and its old and new cells in display order.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| java-diff-utils/java-diff-utils#233.1 · Intent | Render the two-line fixture with explicit equal parts and inline markup disabled. | The PR reports CHANGE for the first row on the parent. On the merge expect (EQUAL,same,same), (CHANGE,before,after), in order. | Compare the input strings at the same positions. The pinned test asserts the two tags and the first old cell. | A tag, cell, row count or order differs on the merge. |
| java-diff-utils/java-diff-utils#233.2 · Control | Generate the patch with equal parts omitted, leaving the visible documents and renderer fixed. | Both revisions should produce those same two rows. | The renderer copies the unmodified prefix before the first edit. Omitting redundant patch content leaves the original and revised documents identical to the intent fixture. | Either revision loses the first row, tags it CHANGE, or changes the displayed cells. |
| java-diff-utils/java-diff-utils#233.3 · Challenge | Put an unchanged tail after the changed pair. Set the public builder’s equality processor to prefix each unchanged line with `EQ-`. Render both explicit and implicit equal parts on the merge. | The entire ordered sequence must agree across representations. In both columns the first cell is EQ-same and the last is EQ-tail, each decorated once. The middle remains (CHANGE,before,after). | A caller-selected pure formatter and literal input give the exact expected text. Equal lines at opposite ends exercise both sides of the change. | Tags agree but either equal cell is raw, decorated twice or missing, or representation changes the middle row. |

**Evidence and limits.** The PR reports its Maven run passed 149 tests. The landed tests check explicit equal parts in both inline modes and inspect one equal cell in each. The customized two-boundary history is a prediction. Counting two rows alone would pass with the old classification.

**Technical notes.** The Maven module is `java-diff-utils`. Use the patch overload of the row generator and default case-sensitive equality. Simple ASCII strings make the default line normalizer immaterial.

**Sources.** [Patch factory](https://github.com/java-diff-utils/java-diff-utils/blob/6e0ec1e22d31013eedda0ca8a72d3d77d1abf98b/java-diff-utils/src/main/java/com/github/difflib/DiffUtils.java) · [Renderer and builder](https://github.com/java-diff-utils/java-diff-utils/blob/6e0ec1e22d31013eedda0ca8a72d3d77d1abf98b/java-diff-utils/src/main/java/com/github/difflib/text/DiffRowGenerator.java) · [Regression](https://github.com/java-diff-utils/java-diff-utils/blob/6e0ec1e22d31013eedda0ca8a72d3d77d1abf98b/java-diff-utils/src/test/java/com/github/difflib/text/DiffRowGeneratorEqualitiesTest.java) · [Module](https://github.com/java-diff-utils/java-diff-utils/blob/6e0ec1e22d31013eedda0ca8a72d3d77d1abf98b/java-diff-utils/pom.xml)

## junit-team/junit-framework#6104 · JUnit Jupiter — discovering and reselecting inherited nested tests with the same name

**Change and revisions.** Jupiter distinguishes a nested test declared in a superclass from one with the same simple name declared in the selected subclass. Both sets of tests can run and can be addressed separately on the merge. [Merged PR #6104](https://github.com/junit-team/junit-framework/pull/6104) · [Landed comparison](https://github.com/junit-team/junit-framework/compare/bbeb7900fa76b6fc00e36e0bea05747066b4a2ec...2b484caa962ad9b0d9a6af5d2c25100b6a8f4ef6)

Before `bbeb7900fa76b6fc00e36e0bea05747066b4a2ec` → after `2b484caa962ad9b0d9a6af5d2c25100b6a8f4ef6`.

**Public scenario.** Define a package-visible Base with a non-static `@Nested class A` containing one `@Test check()` that records “base”. Define Sub extending Base with its own non-static `@Nested class A` and same-named test recording “sub”. Use the public Platform Launcher with only Jupiter enabled, select Sub as a class, discover the TestPlan, and save each leaf’s unique ID paired with the declaring class from its `TestIdentifier.getSource()` (`MethodSource`). This identifies the expected marker for each ID. Execute and count each marker separately. No parallel execution or incidental test methods are needed.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| junit-team/junit-framework#6104.1 · Intent | Class-select Sub with both nested classes present. | The PR reports that the parent runs only Sub.A. The merge should discover two distinct test leaves and finish both successfully, recording base and sub once each, in either order. | The two declarations are in different Java classes. Both are annotated. The release note expressly includes same-name inherited classes. | Only one marker appears, a marker appears twice, the IDs coincide, or discovery and execution disagree. |
| junit-team/junit-framework#6104.2 · Control | Select Base itself without changing the class files. | Both revisions should discover and execute just its one A.check, recording base once. | Selecting Base does not traverse its subclasses. Its nested test is directly declared and has no name collision. | A missing base marker or an extra sub marker on either revision. |
| junit-team/junit-framework#6104.3 · Challenge | On the merge save both leaf IDs from Sub’s TestPlan. For each ID create a fresh launcher request using `selectUniqueId(id)`, reset the markers, then execute only that request. | Each selection should record the marker for its saved declaring class and no other marker. The two separate runs should partition the class run into one base and one sub. | A test runner uses unique IDs to rerun a previously discovered test. Identical simple class and method names make the marker an independent check of identity. | Both IDs rerun the same declaration, either ID runs both or neither, or success counts conceal a swapped marker. |

**Evidence and limits.** The PR attributes the historical omission to identical descriptor IDs. The landed engine regression checks class-selected execution and separately rediscovers IDs; its fixture also includes a class named with a dollar sign. The proposed Launcher replay executes each saved leaf and observes its method body. Display names alone can coincide legitimately.

**Technical notes.** Use the matching `junit-platform-launcher`, Jupiter API and Jupiter engine from each tree. The resolver and descriptor changes belong to `junit-jupiter-engine`. Compare the meaning of IDs within one tree. Inherited nested ID text may change across revisions.

**Sources.** [Launcher](https://github.com/junit-team/junit-framework/blob/2b484caa962ad9b0d9a6af5d2c25100b6a8f4ef6/junit-platform-launcher/src/main/java/org/junit/platform/launcher/Launcher.java) · [Discovery](https://github.com/junit-team/junit-framework/blob/2b484caa962ad9b0d9a6af5d2c25100b6a8f4ef6/junit-jupiter-engine/src/main/java/org/junit/jupiter/engine/discovery/ClassSelectorResolver.java) · [Regression](https://github.com/junit-team/junit-framework/blob/2b484caa962ad9b0d9a6af5d2c25100b6a8f4ef6/jupiter-tests/src/test/java/org/junit/jupiter/engine/NestedTestClassesTests.java) · [Release note](https://github.com/junit-team/junit-framework/blob/2b484caa962ad9b0d9a6af5d2c25100b6a8f4ef6/documentation/modules/ROOT/partials/release-notes/release-notes-6.2.0-M1.adoc) · [Engine build](https://github.com/junit-team/junit-framework/blob/2b484caa962ad9b0d9a6af5d2c25100b6a8f4ef6/junit-jupiter-engine/junit-jupiter-engine.gradle.kts)

## apache/arrow-java#1019 · Apache Arrow — end offsets and element hashes of list views

**Change and revisions.** Arrow’s list-view end index becomes the exclusive child index. Hashing a list view now visits that same half-open interval even when the view begins at a nonzero offset. [Merged PR #1019](https://github.com/apache/arrow-java/pull/1019) · [Landed comparison](https://github.com/apache/arrow-java/compare/46211fccf642d6dcfcebc31081817da1529d6a35...9fd4973d12abbd9e9d14098c2acd41d97a6c4407)

Before `46211fccf642d6dcfcebc31081817da1529d6a35` → after `9fd4973d12abbd9e9d14098c2acd41d97a6c4407`.

**Public scenario.** From a buffer allocator create `ListViewVector.empty("v", allocator)`, allocate it and initialize its child field as signed 16-bit integers. Call `allocateNew(5)` on the new child `SmallIntVector`, then populate it with [10,20,30,40,50] and set its count to five. Mark both list slots valid, set offsets [0,3] and sizes [3,2] with the vector setters, then set its value count to two. For each slot read `getElementStartIndex`, `getElementEndIndex` and `getObject`. Keep the vector and allocator open for the observations.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/arrow-java#1019.1 · Intent | Inspect slot 1 and read the child values at all indices in its reported half-open interval. | The parent returns end 2 for start 3 even though the object contains [40,50]. The merge should return [3,5) and child readback [40,50], equal to the object. | A view of length two beginning at index three ends at five. Issue #470 and the regression identify the old size-as-end behavior. | End precedes start, end minus start differs from two, or the child slice disagrees with the object. |
| apache/arrow-java#1019.2 · Control | Inspect slot 0 at offset zero, length three. | Both revisions should report [0,3) and expose [10,20,30] through both read paths. | At zero offset, size and exclusive end coincide. | The reported interval, object or child readback differs on either revision. |
| apache/arrow-java#1019.3 · Challenge | On the merge compare slot 1 with a slot in a separate vector whose child is [40,50] and whose valid view starts at zero with size two. Compare their objects and `hashCode(slot)` values using the default hasher. | Equal ordered element values should yield equal slot hashes regardless of their physical position. On the parent the nonzero-offset loop can visit no elements. No particular numeric hash is required. | Both slots denote the same typed sequence. Relocating the physical slice while preserving its contents tests the consumer that hashes the view. | The objects compare equal but the hashes differ depending on the child offset. |

**Evidence and limits.** The landed tests assert end indices for ordered, out-of-order and overlapping views. In the two-slot test the element-by-element readback is performed for slot zero. The PR describes the refactoring and notes the byte widths are both four; the landed hash loop also changes its upper bound. Hash equivalence on the relocated slot is a source-based prediction.

**Technical notes.** Use the `vector` Maven module, one Arrow allocator implementation, signed `SmallIntVector` children and identical default hash configuration for both vectors. These tiny valid views exercise the interval independently of large-buffer address arithmetic.

**Sources.** [List-view implementation](https://github.com/apache/arrow-java/blob/9fd4973d12abbd9e9d14098c2acd41d97a6c4407/vector/src/main/java/org/apache/arrow/vector/complex/ListViewVector.java) · [Base vector](https://github.com/apache/arrow-java/blob/9fd4973d12abbd9e9d14098c2acd41d97a6c4407/vector/src/main/java/org/apache/arrow/vector/complex/BaseListVector.java) · [Regression and fixture](https://github.com/apache/arrow-java/blob/9fd4973d12abbd9e9d14098c2acd41d97a6c4407/vector/src/test/java/org/apache/arrow/vector/TestListViewVector.java) · [Module](https://github.com/apache/arrow-java/blob/9fd4973d12abbd9e9d14098c2acd41d97a6c4407/vector/pom.xml) · [Issue](https://github.com/apache/arrow-java/issues/470)

## jgrapht/jgrapht#792 · JGraphT #792 — Recover three edge-disjoint routes from the original graph

**Change and revisions.** Both disjoint-path algorithms share the corrected reconstruction of routes after successive shortest-path searches. Before `e7ae7a506ca4c2943878247a6e02bf71abc9b2d4` → after `26630083eda568be7099c408638ce31c4d94b4a4`. [Merged PR #792](https://github.com/jgrapht/jgrapht/pull/792) · [Landed comparison](https://github.com/jgrapht/jgrapht/compare/e7ae7a506ca4c2943878247a6e02bf71abc9b2d4...26630083eda568be7099c408638ce31c4d94b4a4)

**Public scenario.** Build a SimpleDirectedWeightedGraph<Integer, DefaultWeightedEdge> with unit-weight arcs from 1 to each of 3, 4 and 5, and from each of 6, 7 and 8 to 2. Add the middle arcs (source, destination, weight) (3,6,2), (3,7,1), (4,7,6), (4,6,5), (5,7,3), (5,8,6). On fresh instances of SuurballeKDisjointShortestPaths and BhandariKDisjointShortestPaths call getPaths(1,2,k). Read each GraphPath’s vertex list, edge list and weight against the original graph.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| jgrapht/jgrapht#792.1 · Intent | Original graph, k=3. | The PR attributes a NullPointerException to both parent algorithms. On the merge expect vertex sequences [1,3,7,2], [1,4,6,2], [1,5,8,2], in increasing weights 3, 7, 8. | Three disjoint paths must use 5→8. The two assignments of 3 and 4 to 6 and 7 cost 6 or 8 on their middle edges. The lower assignment gives total weight 18. | Either algorithm throws, returns fewer than three, shares an edge, or returns a sequence or weight outside that solution. |
| jgrapht/jgrapht#792.2 · Control | Same original graph, k=1. | Both revisions return just [1,3,7,2] with weight 3. | All routes use two unit boundary arcs, and 3→7 is the unique cheapest middle arc. | An exception, another sequence, or a weight unequal to the sum of its edges. |
| jgrapht/jgrapht#792.3 · Challenge | On the merge lower only 5→7 from 3 to 1 and request k=3 again. | The same three paths with weights [3,7,8] remain optimal, even though the first shortest-path search now has a tie. Each path traverses original forward edges with no shared edge. | To reach 8 one must still enter from 5. Using 5→7 in any final solution leaves at most two disjoint exits to 2. | The extra tie changes the final solution, exposes a reversed edge, or makes a path’s weight disagree with its original edges. |

**Evidence and limits.** Issue #790 reports the exception on JGraphT 1.3.0, 1.3.1 and trunk. The landed shared test checks the number of returned paths and the presence of each expected vertex sequence. It does not assert the reported weights or the effect of lowering an excluded edge. Counting three paths alone could miss a shared or reversed edge.

**Technical notes.** Use the jgrapht-core Maven module and a simple directed graph with nonnegative weights. Its public contract orders results by weight. The scores in the three-path solution are distinct.

**Sources.** [Shared algorithm](https://github.com/jgrapht/jgrapht/blob/26630083eda568be7099c408638ce31c4d94b4a4/jgrapht-core/src/main/java/org/jgrapht/alg/shortestpath/BaseKDisjointShortestPathsAlgorithm.java) · [Suurballe implementation](https://github.com/jgrapht/jgrapht/blob/26630083eda568be7099c408638ce31c4d94b4a4/jgrapht-core/src/main/java/org/jgrapht/alg/shortestpath/SuurballeKDisjointShortestPaths.java) · [Bhandari implementation](https://github.com/jgrapht/jgrapht/blob/26630083eda568be7099c408638ce31c4d94b4a4/jgrapht-core/src/main/java/org/jgrapht/alg/shortestpath/BhandariKDisjointShortestPaths.java) · [Regression graph](https://github.com/jgrapht/jgrapht/blob/26630083eda568be7099c408638ce31c4d94b4a4/jgrapht-core/src/test/java/org/jgrapht/alg/shortestpath/KDisjointShortestPathsTestCase.java) · [Core build](https://github.com/jgrapht/jgrapht/blob/26630083eda568be7099c408638ce31c4d94b4a4/jgrapht-core/pom.xml) · [Issue #790](https://github.com/jgrapht/jgrapht/issues/790)

## apache/commons-statistics#140 · Apache Commons Statistics #140 — Keep Cauchy tail quantiles responsive to small probabilities

**Change and revisions.** The distribution now evaluates the two inverse tails without subtracting one half from a tiny probability. Both inverse APIs use the same standardized quantile. Before `bfcc6e62e2960512ff699809434d5d7774bf16dd` → after `2535c20ad85ce756c0d396151d83e7fc4e2c904c`. [Merged PR #140](https://github.com/apache/commons-statistics/pull/140) · [Landed comparison](https://github.com/apache/commons-statistics/compare/bfcc6e62e2960512ff699809434d5d7774bf16dd...2535c20ad85ce756c0d396151d83e7fc4e2c904c)

**Public scenario.** Obtain a CauchyDistribution from of(0.5, 2). For each supplied binary64 probability call inverseCumulativeProbability(p) and inverseSurvivalProbability(p) separately. Use p directly for the survival tail because computing 1−p first can round to 1.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| apache/commons-statistics#140.1 · Intent | Use p=1e-20 and p=1e-300 on the same distribution. | The PR reports the same lower quantile near −3.26625×10¹⁶ for both on the parent. The merge should give approximately −6.366197723675814×10¹⁹ and −6.366197723675814×10²⁹⁹ respectively, with the corresponding positive upper quantiles (relative tolerance 1e−15). | The pinned test attributes its numerical references to SciPy. Independently, for these p, the tail displacement is asymptotic to 2/(πp) with relative correction of order p². | A nonfinite value, a shared plateau, a wrong sign or a value outside tolerance on the merge. |
| apache/commons-statistics#140.2 · Control | Use p=0, 0.5, 1 in increasing order. | Both revisions should yield [−∞,0.5,+∞] for the lower inverse and [+∞,0.5,−∞] for the survival inverse. | The support is the whole real line and the distribution is symmetric about 0.5. The parent median expression in source evaluates tan(0). | A wrong infinity, NaN or a median different from 0.5 on either revision. |
| apache/commons-statistics#140.3 · Challenge | On the merge use of(0, 2⁻¹⁰⁰) with the exactly representable positive p=2⁻¹⁰⁵⁰. Observe both public inverse methods. | Both real quantiles are inside binary64 range. Expect finite outputs within 1% of −2⁹⁵⁰/π and +2⁹⁵⁰/π. Source inspection predicts this property may fail on the merge. | Scale divided by p is exactly 2⁹⁵⁰. The relative correction from tan(πp)/(πp) is negligible. Computing the unscaled cotangent first can overflow before the small scale is applied. | An infinity or NaN despite the representable scaled answers, or either magnitude outside the stated band. |

**Evidence and limits.** The PR gives concrete old outputs and reports pre-fix failures and a passing distribution suite. The landed test uses moderate scale with its extreme probabilities. Its probability grid cannot expose overflow of an intermediate standardized quantile when the final scaled quantile is finite. The PR also alleges median drift, but the pinned parent formula uses p−0.5, exactly zero for the median. The control follows that source.

**Technical notes.** Use commons-statistics-distribution and the public factory. Express the challenge’s powers of two with Math.scalb(1.0, exponent). A forward CDF round trip deep in the tail can itself cancel and would not distinguish quantile errors.

**Sources.** [Cauchy formula and APIs](https://github.com/apache/commons-statistics/blob/2535c20ad85ce756c0d396151d83e7fc4e2c904c/commons-statistics-distribution/src/main/java/org/apache/commons/statistics/distribution/CauchyDistribution.java) · [Distribution contract](https://github.com/apache/commons-statistics/blob/2535c20ad85ce756c0d396151d83e7fc4e2c904c/commons-statistics-distribution/src/main/java/org/apache/commons/statistics/distribution/ContinuousDistribution.java) · [Tail regressions](https://github.com/apache/commons-statistics/blob/2535c20ad85ce756c0d396151d83e7fc4e2c904c/commons-statistics-distribution/src/test/java/org/apache/commons/statistics/distribution/CauchyDistributionTest.java) · [Module build](https://github.com/apache/commons-statistics/blob/2535c20ad85ce756c0d396151d83e7fc4e2c904c/commons-statistics-distribution/pom.xml)
