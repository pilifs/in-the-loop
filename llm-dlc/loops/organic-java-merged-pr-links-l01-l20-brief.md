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
