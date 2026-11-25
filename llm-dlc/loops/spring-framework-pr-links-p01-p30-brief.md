# Spring Framework — caller-visible behavior across 30 merged changes

## Objective

Determine which changes an application can observe at a public Spring API. Compare the listed revisions with the same fixture, including an unaffected use and a second observation that could expose an incomplete fix. Separate evidence from upstream reports and tests from predictions that still need execution.

## spring-projects/spring-framework#37435 · Spring Framework #37435 — Keep a supplementary character intact at the truncation boundary

**Change and revisions.** [Merged PR #37435](https://github.com/spring-projects/spring-framework/pull/37435). Before `bcb4fbf31ca15f88697da1281894281ba4d6324d`, after `35584e498e249986fbdc50bf16e3bfa88d2f97e2`. When a positive UTF-16 length limit falls inside a surrogate pair, the retained prefix ends before the pair. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/bcb4fbf31ca15f88697da1281894281ba4d6324d...35584e498e249986fbdc50bf16e3bfa88d2f97e2)

**Public scenario.** Call `StringUtils.truncate(text, limit)` on `a😀b`. Inspect the UTF-16 units preceding the exact suffix ` (truncated)...`. For the encoding check, pass the whole returned string to a fresh UTF-8 `CharsetEncoder` configured to report malformed input.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37435.1 · Intent | Use limit 2 on `a😀b`. | Parent predicts `a` plus a lone high surrogate before the suffix. Landing should return exactly `a (truncated)...`. | The pair occupies indices 1 and 2. A two-unit cut crosses it. The landed regression asserts the complete string. | The landing includes either half or all of the emoji, or changes the suffix. |
| spring-projects/spring-framework#37435.2 · Control | Use limit 3 on the same input, then limit 4. | Both should retain `a😀` with the suffix at 3 and return exactly `a😀b` at 4. | The first cut follows the complete pair. At 4 the input already fits. | Either complete pair is dropped, or a suffix appears at 4. |
| spring-projects/spring-framework#37435.3 · Challenge | Use `StringBuilder` with two consecutive emoji after `a` and a final `b`. Set limit 4 and encode the result strictly as UTF-8. | The merged string and its decoded UTF-8 bytes should equal `a😀 (truncated)...`. The parent is expected to give the encoder malformed input. | Only the second pair straddles the cut. A strict encoder exposes a dangling surrogate that a rendering or replacement encoder can hide. | Strict encoding rejects the merged string, or decoding loses the first emoji. |

**Evidence and limits.** The PR gives the split-pair example. The landed test also covers pre-existing unpaired units and a non-String input. Its promise is about the truncation boundary on the supplied sequence. Visual inspection alone can conceal a lone surrogate.

**Technical notes.** `spring-core` uses Java `char` units for the threshold. The maintainer identifies a later polishing commit in the PR discussion. The comparison ends at the original landing.

**Sources.** [StringUtils.java](https://github.com/spring-projects/spring-framework/blob/35584e498e249986fbdc50bf16e3bfa88d2f97e2/spring-core/src/main/java/org/springframework/util/StringUtils.java) · [StringUtilsTests.java](https://github.com/spring-projects/spring-framework/blob/35584e498e249986fbdc50bf16e3bfa88d2f97e2/spring-core/src/test/java/org/springframework/util/StringUtilsTests.java) · [spring-core build](https://github.com/spring-projects/spring-framework/blob/35584e498e249986fbdc50bf16e3bfa88d2f97e2/spring-core/spring-core.gradle)

## spring-projects/spring-framework#37349 · Spring Framework #37349 — Read a scalar map value through a primitive-array annotation member

**Change and revisions.** [Merged PR #37349](https://github.com/spring-projects/spring-framework/pull/37349). Before `4d3beb5c3bbdfd781a18f73693f97f8abac67154`, after `6afb65b225df5211365647f68090fb10a02afbba`. Spring allocates a singleton array with the declared component type when the supplied scalar can be assigned to it. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/4d3beb5c3bbdfd781a18f73693f97f8abac67154...6afb65b225df5211365647f68090fb10a02afbba)

**Public scenario.** Declare a runtime annotation `Options` with `int[] codes()` and `String[] names()`. Obtain `MergedAnnotation.of(Options.class, Map.of("codes", 7, "names", "east"))`. Read `getIntArray("codes")` and `getStringArray("names")` independently, then call `synthesize().codes()`.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37349.1 · Intent | Read the scalar Integer 7 as the `codes` member. | The PR describes an IllegalStateException on adaptation in the parent. The landing should return primitive `int[] {7}`. | The member return type is `int[]`. A one-element array of boxed Integer has a different runtime class. | The merged read throws, returns a boxed array through generic access, or changes 7. |
| spring-projects/spring-framework#37349.2 · Control | Read scalar `east` as `names`, then supply `new int[] {7,9}` for `codes`. | Both should return respectively `String[] {"east"}` and the two primitive integers in order. | The existing reference-array and already-correct-array paths have no boxing mismatch. | A scalar string stops adapting or a supplied array loses its second element. |
| spring-projects/spring-framework#37349.3 · Challenge | Compare the synthesized annotation with one obtained via reflection from a class annotated `@Options(codes={7}, names={"east"})`. | On the landing, `Arrays.equals` between their `codes()` results and between their `names()` results should hold. | The Java compiler determines the reflected member types and values independently of Spring’s map adapter. | The typed map accessor passes but a synthesized member throws, is empty, or differs from its compiled counterpart. |

**Evidence and limits.** The change covers all eight primitive wrappers in the landed test, which calls the package-level factory. The public factory delegates to it. Reading only the reference-array member misses the original mismatch.

**Technical notes.** Use `spring-core` and the `MergedAnnotation` API present in both revisions. The maintainer’s later `@AliasFor` test belongs to a separate revision.

**Sources.** [MergedAnnotation.java](https://github.com/spring-projects/spring-framework/blob/6afb65b225df5211365647f68090fb10a02afbba/spring-core/src/main/java/org/springframework/core/annotation/MergedAnnotation.java) · [TypeMappedAnnotation.java](https://github.com/spring-projects/spring-framework/blob/6afb65b225df5211365647f68090fb10a02afbba/spring-core/src/main/java/org/springframework/core/annotation/TypeMappedAnnotation.java) · [TypeMappedAnnotationTests.java](https://github.com/spring-projects/spring-framework/blob/6afb65b225df5211365647f68090fb10a02afbba/spring-core/src/test/java/org/springframework/core/annotation/TypeMappedAnnotationTests.java) · [spring-core build](https://github.com/spring-projects/spring-framework/blob/6afb65b225df5211365647f68090fb10a02afbba/spring-core/spring-core.gradle)

## spring-projects/spring-framework#36480 · Spring Framework #36480 — Recover the nested return type inherited through a generic interface

**Change and revisions.** [Merged PR #36480](https://github.com/spring-projects/spring-framework/pull/36480). Before `a0dba60fa657088015be64e9987f68c179c76e08`, after `c1e90d51ca6a8379a0366f30cd77e5c1be019447`. Resolving a method’s type variable against a concrete class now preserves the arguments of a parameterized binding. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/a0dba60fa657088015be64e9987f68c179c76e08...c1e90d51ca6a8379a0366f30cd77e5c1be019447)

**Public scenario.** Define `Source<T>` with `T get()`, `Middle<P> implements Source<Collection<P>>` and `Text extends Middle<Optional<String>>`. Give Text a concrete `Collection<Optional<String>> get()` declaration. Obtain T from `Source.class.getMethod("get").getGenericReturnType()` and call `GenericTypeResolver.resolveType(T, Text.class)`. Inspect the returned `Type` recursively.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#36480.1 · Intent | Resolve the interface return type in the Text context. | Parent source predicts raw `Collection.class`. Landing should expose `Collection<Optional<String>>`, equal to the generic return type of the concrete non-bridge override. | The two substitutions are `T = Collection<P>` and `P = Optional<String>`. Java reflection on the explicit override gives an independent expected Type. | The landing exposes only Collection, only Optional, an unresolved variable, or a different leaf. |
| spring-projects/spring-framework#36480.2 · Control | Use a class implementing `Source<String>` directly. | Both revisions should resolve T to `String.class`. | The interface directly fixes the variable to a class without nested arguments. | The result stays a TypeVariable or differs from String. |
| spring-projects/spring-framework#36480.3 · Challenge | Resolve T for a second sibling `Middle<Optional<Long>>`, then for Text again. Neither needs an explicit override in this variation. | On the landing the two leaf arguments should be Long and String respectively, with identical outer Collection and Optional raw types. | A sibling’s binding is determined by its declared superclass. An override is unnecessary to recover that signature. | The contexts collapse to one cached result, the leaf disappears, or resolution depends on declaring an override. |

**Evidence and limits.** The landed regression compares reflection on concrete overrides for `Collection<String>` and `Collection<Optional<String>>`. A check using erased `Method.getReturnType()` would accept the parent’s raw result.

**Technical notes.** Use `spring-core`, `java.lang.reflect.ParameterizedType`, and `getActualTypeArguments()` at each level. Select the non-bridge method when enumerating the concrete override. No instance or collection element is needed.

**Sources.** [GenericTypeResolver.java](https://github.com/spring-projects/spring-framework/blob/c1e90d51ca6a8379a0366f30cd77e5c1be019447/spring-core/src/main/java/org/springframework/core/GenericTypeResolver.java) · [GenericTypeResolverTests.java](https://github.com/spring-projects/spring-framework/blob/c1e90d51ca6a8379a0366f30cd77e5c1be019447/spring-core/src/test/java/org/springframework/core/GenericTypeResolverTests.java) · [spring-core build](https://github.com/spring-projects/spring-framework/blob/c1e90d51ca6a8379a0366f30cd77e5c1be019447/spring-core/spring-core.gradle)

## spring-projects/spring-framework#36207 · Spring Framework #36207 — Choosing a value for empty YAML entries

**Change and revisions.** [Merged PR #36207](https://github.com/spring-projects/spring-framework/pull/36207). Before `611811d8fc8b96d7983cf2d3d261727c3c12f66b`, after `ab314aadd95e05318629943754a8e4c1dd0400be`. The YAML processor changes its protected two-argument flattening hook into a three-argument hook accepting a caller-selected empty value. The public properties factory retains its default policy. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/611811d8fc8b96d7983cf2d3d261727c3c12f66b...ab314aadd95e05318629943754a8e4c1dd0400be)

**Public scenario.** Give a YamlProcessor subclass a ByteArrayResource containing the single YAML document `{a: null, b: ~, c: {}, d: '', s: value}`. Its public load method calls process and flattens the map supplied to its callback. Compile this small adapter against each revision. Use containsKey as well as get to distinguish a mapped null from an absent entry.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#36207.1 · Intent | On the parent call getFlattenedMap(map, true). At the landing call getFlattenedMap(map, true, null), then repeat with a unique marker object. | Parent a/b are empty strings and c is present with null. At the landing a/b/c should all be present with the requested value, including the identical marker object. d stays an empty string and s stays value. | YAML null and ~ denote the same null scalar. The quoted empty scalar denotes a string. The new hook documents the caller’s choice for empty entries. | One spelling gives a different answer, a present entry disappears, or d becomes the marker. |
| spring-projects/spring-framework#36207.2 · Control | Set the same resource on YamlPropertiesFactoryBean, call afterPropertiesSet(), then getObject(). | Both should expose empty strings for a, b and d, value for s, and omit c. | The factory consumes MatchCallback properties using the single-argument default flattening policy. The landed test records the default map. | c appears or a null scalar becomes an absent property. |
| spring-projects/spring-framework#36207.3 · Challenge | On the landing add e: [] to the fixture and select the unique marker again. Compare its mapping with c: {}. | The general empty-entry description suggests the same marker for both. The empty-collection branch predicts an exception to that reading: c should hold the marker while e holds an empty string. | Changing only the empty container type distinguishes the documented generalization from the implementation’s older sequence policy. | e carrying the marker refutes the predicted asymmetry. A blank e refutes uniform caller selection across these empty containers. |

**Evidence and limits.** YamlProcessorTests covers null, tilde and an empty mapping with null and blank sentinels. Issue #19986 reports the original null-to-blank outcome in Boot. Comparing only string properties cannot reveal whether the new hook preserves a marker object or treats an empty sequence differently.

**Technical notes.** spring-beans declares optional org.yaml:snakeyaml. Use the callback’s original map for the custom hook and the factory’s Properties for the control. The protected API signatures differ between revisions.

**Sources.** [YamlProcessor.java](https://github.com/spring-projects/spring-framework/blob/ab314aadd95e05318629943754a8e4c1dd0400be/spring-beans/src/main/java/org/springframework/beans/factory/config/YamlProcessor.java) · [YamlProcessorTests.java](https://github.com/spring-projects/spring-framework/blob/ab314aadd95e05318629943754a8e4c1dd0400be/spring-beans/src/test/java/org/springframework/beans/factory/config/YamlProcessorTests.java) · [YamlPropertiesFactoryBean.java](https://github.com/spring-projects/spring-framework/blob/ab314aadd95e05318629943754a8e4c1dd0400be/spring-beans/src/main/java/org/springframework/beans/factory/config/YamlPropertiesFactoryBean.java) · [spring-beans build](https://github.com/spring-projects/spring-framework/blob/ab314aadd95e05318629943754a8e4c1dd0400be/spring-beans/spring-beans.gradle) · [Issue #36197](https://github.com/spring-projects/spring-framework/issues/36197) · [Issue #19986](https://github.com/spring-projects/spring-framework/issues/19986)

## spring-projects/spring-framework#21855 · Spring Framework #21855 — Map keys can contain balanced brackets in a bean property path

**Change and revisions.** [Merged PR #21855](https://github.com/spring-projects/spring-framework/pull/21855). Before `7b11c3b599c82782d3e48328715926c1296d921f`, after `6899624155e9c450d5166577d8b40e9783d718f4`. Property access now finds the bracket that closes the whole map key, accounting for balanced brackets inside that key. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/7b11c3b599c82782d3e48328715926c1296d921f...6899624155e9c450d5166577d8b40e9783d718f4)

**Public scenario.** Create a JavaBean with readable property map containing mutable child beans under three distinct literal strings: key5[foo], key5[foo and plain. Give them names full, prefix and control. Obtain PropertyAccessorFactory.forBeanPropertyAccess(bean). Read and write a child’s name through the property path, then read the children directly from the backing map.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#21855.1 · Intent | Read map[key5[foo]].name with the two similarly named keys present. | The PR reports truncation of the inner closing bracket. With this fixture the parent is expected to read prefix, and the landing must read full. | The original Java map explicitly assigns full to the balanced literal key. The landed regression resolves the same key unquoted and with either quote style. | The landing reads prefix, returns null or throws. |
| spring-projects/spring-framework#21855.2 · Control | Read map[plain].name and write control2 there. | Both should return control initially and leave control2 in the child stored at plain. | This property path has a single bracket pair, and the ordinary map getter supplies an independent observation. | The ordinary read or write targets a different child. |
| spring-projects/spring-framework#21855.3 · Challenge | At the landing write changed through map['key5[foo]'].name. Read the map directly and read the same property with double quotes. | Only the child under key5[foo] should change. The alternate quoted read should agree, the prefix child should still say prefix, and the map should still have three keys. | Quoting changes the path spelling while preserving the selected literal. A direct map read can detect a self-consistent read/write to the wrong child. | A decoy changes, a key is created, or the alternate read fails. |

**Evidence and limits.** The PR identifies the truncated key. The shared accessor regression reads three spellings and updates the unquoted path. Its later read through the accessor alone could agree with a misplaced write. The decoy and direct post-write observations are predictions.

**Technical notes.** Use spring-beans and the ordinary JavaBean accessor from PropertyAccessorFactory. Each child exposes getName and setName. The cases concern balanced nested brackets.

**Sources.** [AbstractNestablePropertyAccessor.java](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/src/main/java/org/springframework/beans/AbstractNestablePropertyAccessor.java) · [AbstractPropertyAccessorTests.java](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/src/test/java/org/springframework/beans/AbstractPropertyAccessorTests.java) · [IndexedTestBean.java](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/src/test/java/org/springframework/tests/sample/beans/IndexedTestBean.java) · [PropertyAccessorFactory.java](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/src/main/java/org/springframework/beans/PropertyAccessorFactory.java) · [spring-beans build](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/spring-beans.gradle)
