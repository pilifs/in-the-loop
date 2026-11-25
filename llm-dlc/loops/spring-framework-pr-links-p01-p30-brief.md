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

**Public scenario.** Define `Source<T>` with a default `T get()` returning null, `Middle<P> implements Source<Collection<P>>` and `Text extends Middle<Optional<String>>`. Give Text a concrete `Collection<Optional<String>> get()` declaration. Obtain T from `Source.class.getMethod("get").getGenericReturnType()` and call `GenericTypeResolver.resolveType(T, Text.class)`. Inspect the returned `Type` recursively.

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
| spring-projects/spring-framework#36207.3 · Challenge | On the landing add e: [] to the fixture and select the unique marker again. Compare its mapping with c: {}. | The general empty-entry description suggests the same marker for both. The empty-collection branch instead predicts that c holds the marker while e holds an empty string. | Changing only the empty container type distinguishes the documented generalization from the implementation’s older sequence policy. | e carrying the marker refutes the predicted asymmetry. A blank e refutes uniform caller selection across these empty containers. |

**Evidence and limits.** YamlProcessorTests covers null, tilde and an empty mapping with null and blank sentinels. Issue #19986 reports the original null-to-blank outcome in Boot. Comparing only string properties cannot reveal whether the new hook preserves a marker object or treats an empty sequence differently.

**Technical notes.** spring-beans declares optional org.yaml:snakeyaml. Use the callback’s original map for the custom hook and the factory’s Properties for the control. The protected API signatures differ between revisions.

**Sources.** [YamlProcessor.java](https://github.com/spring-projects/spring-framework/blob/ab314aadd95e05318629943754a8e4c1dd0400be/spring-beans/src/main/java/org/springframework/beans/factory/config/YamlProcessor.java) · [YamlProcessorTests.java](https://github.com/spring-projects/spring-framework/blob/ab314aadd95e05318629943754a8e4c1dd0400be/spring-beans/src/test/java/org/springframework/beans/factory/config/YamlProcessorTests.java) · [YamlPropertiesFactoryBean.java](https://github.com/spring-projects/spring-framework/blob/ab314aadd95e05318629943754a8e4c1dd0400be/spring-beans/src/main/java/org/springframework/beans/factory/config/YamlPropertiesFactoryBean.java) · [spring-beans build](https://github.com/spring-projects/spring-framework/blob/ab314aadd95e05318629943754a8e4c1dd0400be/spring-beans/spring-beans.gradle) · [Issue #36197](https://github.com/spring-projects/spring-framework/issues/36197) · [Issue #19986](https://github.com/spring-projects/spring-framework/issues/19986)

## spring-projects/spring-framework#21855 · Spring Framework #21855 — Map keys can contain balanced brackets in a bean property path

**Change and revisions.** [Merged PR #21855](https://github.com/spring-projects/spring-framework/pull/21855). Before `7b11c3b599c82782d3e48328715926c1296d921f`, after `6899624155e9c450d5166577d8b40e9783d718f4`. Property access now finds the bracket that closes the whole map key, accounting for balanced brackets inside that key. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/7b11c3b599c82782d3e48328715926c1296d921f...6899624155e9c450d5166577d8b40e9783d718f4)

**Public scenario.** Create a JavaBean with readable property map containing mutable child beans under the literal keys `key5[foo]`, `key5[foo` and `plain`. Give them names full, prefix and control. Obtain PropertyAccessorFactory.forBeanPropertyAccess(bean). Read and write a child’s name through the property path, then read the children directly from the backing map.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#21855.1 · Intent | Read map[key5[foo]].name with the two similarly named keys present. | The PR reports truncation of the inner closing bracket. With this fixture the parent is expected to read prefix, and the landing must read full. | The original Java map explicitly assigns full to the balanced literal key. The landed regression resolves the same key unquoted and with either quote style. | The landing reads prefix, returns null or throws. |
| spring-projects/spring-framework#21855.2 · Control | Read map[plain].name and write control2 there. | Both should return control initially and leave control2 in the child stored at plain. | This property path has a single bracket pair, and the ordinary map getter supplies an independent observation. | The ordinary read or write targets a different child. |
| spring-projects/spring-framework#21855.3 · Challenge | At the landing write changed through map['key5[foo]'].name. Read the map directly and read the same property with double quotes. | Only the child under key5[foo] should change. The alternate quoted read should agree, the prefix child should still say prefix, and the map should still have three keys. | Quoting changes the path spelling while preserving the selected literal. A direct map read can detect a self-consistent read/write to the wrong child. | A decoy changes, a key is created, or the alternate read fails. |

**Evidence and limits.** The PR identifies the truncated key. The shared accessor regression reads three spellings and updates the unquoted path. Its later read through the accessor alone could agree with a misplaced write. The decoy and direct post-write observations are predictions.

**Technical notes.** Use spring-beans and the ordinary JavaBean accessor from PropertyAccessorFactory. Each child exposes getName and setName. The cases concern balanced nested brackets.

**Sources.** [AbstractNestablePropertyAccessor.java](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/src/main/java/org/springframework/beans/AbstractNestablePropertyAccessor.java) · [AbstractPropertyAccessorTests.java](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/src/test/java/org/springframework/beans/AbstractPropertyAccessorTests.java) · [IndexedTestBean.java](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/src/test/java/org/springframework/tests/sample/beans/IndexedTestBean.java) · [PropertyAccessorFactory.java](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/src/main/java/org/springframework/beans/PropertyAccessorFactory.java) · [spring-beans build](https://github.com/spring-projects/spring-framework/blob/6899624155e9c450d5166577d8b40e9783d718f4/spring-beans/spring-beans.gradle)

## spring-projects/spring-framework#37351 · Spring Framework #37351 — A failed computation leaves no case-insensitive key behind

**Change and revisions.** [Merged PR #37351](https://github.com/spring-projects/spring-framework/pull/37351). Before `06c597ed6fa8bdde6b8155a9587a9250936dd402`, after `1b4955e49f06a791a1b5f3f7333ab631cab5a293`. LinkedCaseInsensitiveMap defers key registration until a mapping function produces a non-null value. Membership, iteration and stored spelling should then agree. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/06c597ed6fa8bdde6b8155a9587a9250936dd402...1b4955e49f06a791a1b5f3f7333ab631cab5a293)

**Public scenario.** Use a fresh LinkedCaseInsensitiveMap<String> with ASCII keys. Run computeIfAbsent, inspect size, containsKey, keySet and get, then insert or remove under another spelling.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37351.1 · Intent | Compute Key with a function returning null. On another empty map use a function throwing a particular IllegalStateException. | Both revisions should return null or propagate the exception respectively. The PR reports containsKey(key) true on the parent despite size zero. The landing must report false, size zero, get(key) null and an empty key set after each call. | Map.computeIfAbsent records no mapping when the function returns null or throws. Iteration and lookup describe the same mappings. | A merged map reports membership, contains an entry, or swallows the exception. |
| spring-projects/spring-framework#37351.2 · Control | Start with put(Key, null), then computeIfAbsent(KEY, k -> null). | Both should return null and retain exactly the pre-existing Key mapping, including its original spelling and case-insensitive membership. | A null-valued mapping already existed and no replacement was supplied. The landed regression distinguishes this history from an empty map. | The mapping disappears, changes spelling, or acquires a value. |
| spring-projects/spring-framework#37351.3 · Challenge | After the failed absent-key computation, compute KEY successfully with a function recording its argument and returning v. Remove through kEy. | The landing should pass KEY to the second function, expose exactly KEY in iteration, return v from removal and finish empty with containsKey(Key) false. The PR reports the parent can reuse the first unsuccessful spelling. | The first call added no mapping. The second spelling is therefore the first successful insertion, and removal addresses that same entry irrespective of case. | The function sees Key, iteration exposes Key, or removal leaves stale membership. |

**Evidence and limits.** The PR reports the empty map with a positive membership test. Its regressions cover exceptions, retry spelling, an existing null and immediate eviction. Inspecting get alone gives null for both an absent key and a recorded null.

**Technical notes.** spring-core supplies both the implementation and LinkedCaseInsensitiveMapTests. Keep mapping functions free of mutations to the same map.

**Sources.** [LinkedCaseInsensitiveMap.java](https://github.com/spring-projects/spring-framework/blob/1b4955e49f06a791a1b5f3f7333ab631cab5a293/spring-core/src/main/java/org/springframework/util/LinkedCaseInsensitiveMap.java) · [LinkedCaseInsensitiveMapTests.java](https://github.com/spring-projects/spring-framework/blob/1b4955e49f06a791a1b5f3f7333ab631cab5a293/spring-core/src/test/java/org/springframework/util/LinkedCaseInsensitiveMapTests.java) · [spring-core build](https://github.com/spring-projects/spring-framework/blob/1b4955e49f06a791a1b5f3f7333ab631cab5a293/spring-core/spring-core.gradle)

## spring-projects/spring-framework#36626 · Spring Framework #36626 — A mail message owns its sent date across setters, getters and copies

**Change and revisions.** [Merged PR #36626](https://github.com/spring-projects/spring-framework/pull/36626). Before `e940a38014cfad78aaef39a77db128e778f2f9ae`, after `4b0101a9dcdf7dbe1841dfc33992fa8eb27eaf2f`. `SimpleMailMessage` clones a non-null `Date` on input, output, construction from another message, and transfer to a `MailMessage`. The copy paths also change how they read the original date. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/e940a38014cfad78aaef39a77db128e778f2f9ae...4b0101a9dcdf7dbe1841dfc33992fa8eb27eaf2f)

**Public scenario.** Set `new Date(1234L)` on a new message. Construct a second message from it and call `copyTo` on a recording `MailMessage` whose setter retains its argument. Read absolute milliseconds from fresh getters after mutating each reference in turn.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#36626.1 · Intent | Change the input date to 0. Next mutate the Date returned by the first message to 1 and the recording target’s Date to 2. | The parent is expected to expose these successive mutations through the shared reference. On the landing, fresh getters on the first message and its copy should still read 1234 after every step. | A plain Date has mutable millisecond state. All four landed regressions require the original timestamp to survive mutation outside the message. | Either source or copy reports 0, 1 or 2 after the respective mutation. |
| spring-projects/spring-framework#36626.2 · Control | Set a message’s date to null and copy its contents to a target already carrying 77 milliseconds. | Both should return null from the source getter and leave the target at 77. Constructing a fresh copy should give it a null date. | `copyTo` transfers populated fields only. The copy constructor starts with an empty destination. | The target’s date is cleared or a fresh copy acquires a timestamp. |
| spring-projects/spring-framework#36626.3 · Challenge | Subclass SimpleMailMessage and override only `getSentDate()` to return a fresh Date(1234) each time. Leave the inherited field unset. Compare its public getter with a constructed copy and with a target initially at 77 after `copyTo`. | The parent should copy 1234 by both routes. The broad promise to copy message contents suggests the same at the landing, but the pinned field reads predict a null constructed date and the target still at 77. | The overridden getter supplies a stable observable value with no mutable alias. Changing representation alone tests what copying a subclass promises. | A null or skipped copy falsifies preservation of the exposed date. Two copies of 1234 would refute the predicted discrepancy. |

**Evidence and limits.** The landed tests mutate Date instances on plain messages and on a recording target. They do not override the getter. Initial equality of two dates alone says nothing about whether later mutation leaks back.

**Technical notes.** `spring-context-support` supplies `SimpleMailMessage` and `MailMessage`. Use ordinary `java.util.Date`, without a custom clone implementation. The PR discussion identifies a later polish outside these pins.

**Sources.** [SimpleMailMessage.java](https://github.com/spring-projects/spring-framework/blob/4b0101a9dcdf7dbe1841dfc33992fa8eb27eaf2f/spring-context-support/src/main/java/org/springframework/mail/SimpleMailMessage.java) · [SimpleMailMessageTests.java](https://github.com/spring-projects/spring-framework/blob/4b0101a9dcdf7dbe1841dfc33992fa8eb27eaf2f/spring-context-support/src/test/java/org/springframework/mail/SimpleMailMessageTests.java) · [spring-context-support build](https://github.com/spring-projects/spring-framework/blob/4b0101a9dcdf7dbe1841dfc33992fa8eb27eaf2f/spring-context-support/spring-context-support.gradle)

## spring-projects/spring-framework#37596 · Spring Framework #37596 — A built retry policy keeps its exception rules

**Change and revisions.** [Merged PR #37596](https://github.com/spring-projects/spring-framework/pull/37596). Before `dfbe36b4da5546752cd5914940a70671e5302f22`, after `b98ad3cbe3943fbcb1d7300b3349bb0bcdafb9ba`. Building a policy snapshots the sets of included and excluded exception classes. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/dfbe36b4da5546752cd5914940a70671e5302f22...b98ad3cbe3943fbcb1d7300b3349bb0bcdafb9ba)

**Public scenario.** Build policy A from RetryPolicy.builder().maxRetries(1).delay(Duration.ZERO).includes(IOException.class). Extend the same builder with includes(IllegalArgumentException.class) and excludes(FileNotFoundException.class), then build B. Query each policy and pass it to a separate RetryTemplate.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37596.1 · Intent | After the edits, call A.shouldRetry on IllegalArgumentException and FileNotFoundException, in that order. | Expect true and false on the parent, false and true at the landing. | A initially admits IOException and its subclasses. FileNotFoundException is such a subclass. The PR demonstrates a built policy changing when its builder's includes set changes. | The merged A adopts either later rule. |
| spring-projects/spring-framework#37596.2 · Control | Query B for ordinary IOException, IllegalArgumentException and FileNotFoundException. | On both revisions expect true, true and false. | B was built after both edits. Its explicit subclass exclusion is more specific than the IOException inclusion. | B loses the added rule, or retries the explicitly excluded file exception. |
| spring-projects/spring-framework#37596.3 · Challenge | On the landing execute a fresh operation through each template. Each operation throws FileNotFoundException on its first call and would return 7 on its second. | With A expect two calls and result 7. With B expect one call and RetryException. Record the operation's own invocation count. | The same failure and retry budget pass through the public executor. Only A's snapshot permits a second attempt. | A stops after one call, or B makes a second call despite the exclusion. |

**Evidence and limits.** The PR reports its original shouldRetry result changing after a builder edit. The landed test examines the old and new policies directly. Inspecting toString or testing B alone misses what happens to work already configured with A.

**Technical notes.** Use spring-core, its RetryPolicyTests and the checked-exception-capable RetryTemplate.execute overload. Use a new attempt counter for each execution. The maintainer identifies a subsequent revision outside the comparison.

**Sources.** [Policy and builder](https://github.com/spring-projects/spring-framework/blob/b98ad3cbe3943fbcb1d7300b3349bb0bcdafb9ba/spring-core/src/main/java/org/springframework/core/retry/RetryPolicy.java) · [Builder regression](https://github.com/spring-projects/spring-framework/blob/b98ad3cbe3943fbcb1d7300b3349bb0bcdafb9ba/spring-core/src/test/java/org/springframework/core/retry/RetryPolicyTests.java) · [Public executor](https://github.com/spring-projects/spring-framework/blob/b98ad3cbe3943fbcb1d7300b3349bb0bcdafb9ba/spring-core/src/main/java/org/springframework/core/retry/RetryTemplate.java) · [spring-core build](https://github.com/spring-projects/spring-framework/blob/b98ad3cbe3943fbcb1d7300b3349bb0bcdafb9ba/spring-core/spring-core.gradle)

## spring-projects/spring-framework#1912 · Spring Framework #1912 — Replacing a session attribute notifies the displaced listener

**Change and revisions.** [Merged PR #1912](https://github.com/spring-projects/spring-framework/pull/1912). Before `0001f87d59c9a247838ce0090771f351607263ce`, after `70dbaf9751961fc9105241830fd206b873fb738c`. MockHttpSession now sends an unbind event to a displaced attribute and suppresses a redundant bind when the identical instance is stored again. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/0001f87d59c9a247838ce0090771f351607263ce...70dbaf9751961fc9105241830fd206b873fb738c)

**Public scenario.** Use the public org.springframework.mock.web.MockHttpSession from spring-test. Give distinct javax.servlet.http.HttpSessionBindingListener instances A and B a shared ordered event log. For each callback record the receiver, phase, event.getSession(), getName() and getValue(). Read the stored attribute independently.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#1912.1 · Intent | Call setAttribute(`k`, A), then setAttribute(`k`, B). | The parent should bind A then B, omitting A's unbind. The landing should bind A, unbind A, then bind B. After both writes getAttribute(`k`) should be B by identity. | There is one binding under k at a time. The landed overwrite test checks occupancy counters for both listeners. | The old listener remains bound, the wrong receiver is notified, or the stored object differs from B. |
| spring-projects/spring-framework#1912.2 · Control | Starting empty, bind A once and call removeAttribute(`k`). | Both revisions should log bind A and unbind A exactly once each. Both events should carry k, the session and A. getAttribute(`k`) should then be null. | The removal path sends the former object to its own listener. The original bind/remove regression observes a zero final counter. | The lookup stays occupied or either event identifies the wrong name, session or object. |
| spring-projects/spring-framework#1912.3 · Challenge | On the landing use two distinct listeners that compare equal. Bind A, set A again, then set B. Compare both object identities in the log. | Only the second call should be silent. Expect bind A, unbind A, bind B and final lookup B. | The same object remains bound on the second write. Equal application values can be distinct lifecycle participants on the third write. | There is an extra bind for A, or equality suppresses the transition to B. |

**Evidence and limits.** Migrated issue SPR-17109 reports that the mock notified listeners on set and remove but omitted the unbind on replacement. The regression reads net counts and covers storing the same listener twice. Net counts alone can hide redundant or misdirected callbacks. The equal-but-distinct challenge and the ordered event payloads are predictions. The original report describes binding A and B without unbinding A on replacement.

**Technical notes.** Use the javax.servlet-era spring-test class and MockHttpSessionTests. The similarly named copy under spring-web/src/test is a different class. Its landed overwrite branch calls valueUnbound on the incoming value while passing the old value in the event. The public spring-test class calls the old listener.

**Sources.** [Public session mock](https://github.com/spring-projects/spring-framework/blob/70dbaf9751961fc9105241830fd206b873fb738c/spring-test/src/main/java/org/springframework/mock/web/MockHttpSession.java) · [Binding tests](https://github.com/spring-projects/spring-framework/blob/70dbaf9751961fc9105241830fd206b873fb738c/spring-test/src/test/java/org/springframework/mock/web/MockHttpSessionTests.java) · [Internal web-test copy](https://github.com/spring-projects/spring-framework/blob/70dbaf9751961fc9105241830fd206b873fb738c/spring-web/src/test/java/org/springframework/mock/web/test/MockHttpSession.java) · [spring-test build](https://github.com/spring-projects/spring-framework/blob/70dbaf9751961fc9105241830fd206b873fb738c/spring-test/spring-test.gradle) · [spring-web build](https://github.com/spring-projects/spring-framework/blob/70dbaf9751961fc9105241830fd206b873fb738c/spring-web/spring-web.gradle) · [Migrated report #21646](https://github.com/spring-projects/spring-framework/issues/21646)

## spring-projects/spring-framework#37531 · Spring Framework #37531 — Repeated reads and copies of a small multipart file

**Change and revisions.** [Merged PR #37531](https://github.com/spring-projects/spring-framework/pull/37531). Before `a38ebf4b7cffe5946e07d0fb8ef2d7dc0ec9bbe3`, after `18860f5732ac4bccdd26bb4254f23ec57f4bd99c`. Servlet multipart file parts retained in memory now create a fresh input stream for every read or transfer. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/a38ebf4b7cffe5946e07d0fb8ef2d7dc0ec9bbe3...18860f5732ac4bccdd26bb4254f23ec57f4bd99c)

**Public scenario.** Read a multipart/form-data HTTP input through MultipartHttpMessageConverter.read using ResolvableType.forClassWithGenerics(MultiValueMap.class, String.class, Part.class). The file field has a filename and exactly the UTF-8 bytes abcdef. Take the converter.multipart.FilePart from the returned map. Repeat the parse with the in-memory limit set to 1 and to 262144 bytes.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37531.1 · Intent | With the large limit, read all bytes via content() twice using separately opened streams. Then transferTo a path and read that path with Files.readAllBytes. | The PR reports the first read succeeds and subsequent reads/copies can be empty on the parent. All three merged observations should equal abcdef. | A fresh reader of a retained upload and a copy of the same file should each start at byte zero. The regression exercises both operations. | Any merged read or the independently opened file loses bytes. |
| spring-projects/spring-framework#37531.2 · Control | Use the one-byte limit and repeat both reads and the copy. | Both revisions should yield abcdef three times. | The six-byte file exceeds this threshold. The disk implementation opens its backing file anew for each read or copy. | Any output is empty, truncated or reordered. |
| spring-projects/spring-framework#37531.3 · Challenge | At the landing open stream A, consume just a, then open B. Read B completely, overwrite an existing longer destination using transferTo and finish A. | B and the destination should each equal abcdef. A should still yield bcdef. Repeat at both thresholds. | Independent cursors permit interleaving. Replacing the destination must discard its old tail without resetting or advancing A. | B starts at b, the old tail survives, or finishing A yields anything other than bcdef. |

**Evidence and limits.** The PR gives the empty second-read and empty-file history. Its test uses files.multipart and reads file2 twice at both thresholds. A single successful read misses the shared cursor. Interleaving and overwriting a longer file are proposed extensions.

**Technical notes.** Use the synchronous org.springframework.http.converter.multipart Part and FilePart from spring-web. Keep the part live and its temporary storage available throughout the reads.

**Sources.** [MultipartHttpMessageConverter.java](https://github.com/spring-projects/spring-framework/blob/18860f5732ac4bccdd26bb4254f23ec57f4bd99c/spring-web/src/main/java/org/springframework/http/converter/multipart/MultipartHttpMessageConverter.java) · [DefaultParts.java](https://github.com/spring-projects/spring-framework/blob/18860f5732ac4bccdd26bb4254f23ec57f4bd99c/spring-web/src/main/java/org/springframework/http/converter/multipart/DefaultParts.java) · [PartGenerator.java](https://github.com/spring-projects/spring-framework/blob/18860f5732ac4bccdd26bb4254f23ec57f4bd99c/spring-web/src/main/java/org/springframework/http/converter/multipart/PartGenerator.java) · [MultipartHttpMessageConverterTests.java](https://github.com/spring-projects/spring-framework/blob/18860f5732ac4bccdd26bb4254f23ec57f4bd99c/spring-web/src/test/java/org/springframework/http/converter/multipart/MultipartHttpMessageConverterTests.java) · [Synchronous Part](https://github.com/spring-projects/spring-framework/blob/18860f5732ac4bccdd26bb4254f23ec57f4bd99c/spring-web/src/main/java/org/springframework/http/converter/multipart/Part.java) · [FilePart contract](https://github.com/spring-projects/spring-framework/blob/18860f5732ac4bccdd26bb4254f23ec57f4bd99c/spring-web/src/main/java/org/springframework/http/converter/multipart/FilePart.java) · [Multipart fixture](https://github.com/spring-projects/spring-framework/blob/18860f5732ac4bccdd26bb4254f23ec57f4bd99c/spring-web/src/test/resources/org/springframework/http/multipart/files.multipart) · [spring-web build](https://github.com/spring-projects/spring-framework/blob/18860f5732ac4bccdd26bb4254f23ec57f4bd99c/spring-web/spring-web.gradle)
