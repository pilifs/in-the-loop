# Two Java verification briefs · Spring application behavior and data processing

**22 November 2026 · Execution baseline [`pilifs/in-the-loop/develop@209ecb6e`][develop]**

These briefs can run independently alongside the five-PR Java campaign. **Start Spring with the binding history and data processing with the boxed row mapper.** Both have reproducible JVM outcomes, and each tests a capability the old examples leave open. The remaining examples put the technique under different demands.

| Brief | First public caller | Harder consumer | What would count as progress |
|---|---|---|---|
| A · Spring authorization and binding | Three successive `DataBinder.bind` calls on a bean with shared or distinct children | A real role decision controls whether the same binder receives an edit. A historical formatter change tests the error and value observers again. | The checker predicts the decision, which writes took effect, which references stayed shared, and what error history the caller sees. |
| B · Java data processing | A stream maps ragged rows of text through `NumberUtils::toInt` into fresh boxed arrays | A matrix transpose, NaN-aware search and exact decimal parsing | The checker follows the compiled callbacks, preserves shape and identity, and distinguishes numeric outputs that a value-only comparison conflates. |

## Where the work starts

At the inspected head, **362 is the highest example ID**. The active brief already reserves Parquet #3333, Avro #1381 and #3730, Jackson Core #1415 and Commons CSV #218. Leave those cases with that run. Allocate new IDs from the current checkout when scaffolding. Recheck shared checker changes as the active work lands. [Active brief][active] · [Example 362][e362]

The receiver work verified two complete public callers natively on both historical versions. Across the 23 earlier receiver blockers, 16 reached the target on both JVMs for every registered input. All 34 unrestricted paired overloads remained unresolved. A proof about a receiver built by a specific public caller is consequently valuable and needs that construction history in its statement. [Latest receiver results][state]

On the data side, example 308 already proved the released Commons Text LCS score on 225 pairs, with 44 pairs distinguishing a shared-row control. Example 317 covers rectangular allocation and row identity. Examples 323 and 324 cover an erased bridge and a callback with observable effects. Examples 313 and 328 already distinguish raw floating-point outcomes. The proposed boxed parser existed in the earlier plan. At this head its SAM result conversion remains a concrete gap in `lambda_call`. [LCS evidence][lcs] · [Existing example results][examples] · [Lambda execution][lambda-engine] · [Earlier domain plan][old]

# Brief A · Prove what the Spring caller sees after an edit

**Deliverable.** Four examples and one cross-example transfer check. Use a small local Java application, real public Spring APIs, ordinary role assignments and in-memory beans. Record the observable decision and bean state at each step. The agent owns the whole route, including any small reflection, String, constructor or heap capability the public call needs.

### A1 · Stateful binding with shared JavaBean children

**Constructed application on released Spring Framework 6.2.3.** A `Draft` has JavaBean getters for `primary` and `backup`. They either return the same mutable `Child` or two equal-initialized, distinct children. Each child has a writable String `name` initially `"initial"` and an `int count` initially 1. Give one fresh `DataBinder` a fresh root per history, and reuse both within that history. [Public binder API][binder]

```java
DataBinder binder = new DataBinder(draft);
binder.bind(new MutablePropertyValues().add("primary.name", "Kim"));
binder.bind(new MutablePropertyValues().add("backup.count", "oops"));
binder.bind(new MutablePropertyValues().add("primary.count", "7"));
```

These are measured public outcomes on the released artifacts. Read the two children through their getters and record `draft.getPrimary() == draft.getBackup()` after **every** call.

| Prefix | Distinct children, primary / backup | Shared child, primary / backup | Binding result in both cases |
|---|---|---|---|
| After the name edit | Kim/1 · initial/1 | Kim/1 · Kim/1 | Zero errors |
| After the invalid count | Kim/1 · initial/1 | Kim/1 · Kim/1 | One field error, `backup.count`, rejected value `"oops"` |
| After the valid count | Kim/7 · initial/1 | Kim/7 · Kim/7 | The same error details remain |

**Freeze two claims.** First, prefix-by-prefix values and receiver aliasing match a two-object reference model. Second, error field, rejected value, error count and later valid writes match an ordered ledger. Run the six permutations of the three calls across both heap shapes, with observations after every prefix. Include one fresh-binder repeat as a separate control for error lifetime. A caller that skips the last edit after seeing an error can return the expected error count and still fail the bean-state claim. Use that as the deliberately wrong implementation.

### A2 · Spring Security #14196, from a role hierarchy to a public decision

This historical feature added a fluent hierarchy builder. Configure the intended graph `A → B`, `B → C`, `B → D`. Enumerate all 16 subsets of starting authorities under each of two prefixes, `ROLE_` and `CUSTOM_PREFIX_`. Compare the unordered **set of exact authority names** returned by `getReachableGrantedAuthorities` with a small graph traversal. Then pass the hierarchy to the real manager and observe its public decision. [Upstream PR][hier-pr] · [Named tests][hier-test] · [Decision API at the landed revision][auth-manager]

```java
AuthorityAuthorizationManager<Object> manager =
    AuthorityAuthorizationManager.hasAuthority(prefix + "D");
manager.setRoleHierarchy(hierarchy);
boolean granted = manager.check(() -> authentication, request).isGranted();
```

Use a test authentication containing exactly the selected authorities. Membership of A, B or D implies the decision is granted. The empty subset and C alone yield the other two outcomes. Use `hasAuthority` with the complete name so both prefix configurations exercise the intended API.

**Score the history correctly.** Run legacy text configuration on the pre-feature and landed artifacts for preservation. On the landed artifact compare text and fluent construction for both reachable names and the decision. The feature spans two commits. The immediate parent of the final polish commit already has the builder. The historical source-slice check used the pinned hierarchy and manager implementations with Spring Framework 6.1.1 and supporting Spring Security 6.2.0 classes. All 32 configurations passed for the legacy path on both sides and for the landed builder. Stock Spring Security 6.3.0 with Framework 6.1.7 also passed 32/32 per construction path. Each prefix granted 14 of 16. An omitted `B → D` edge is a discriminating control even when many direct-D inputs still pass.

**Transfer A1 → A2.** Keep authentication and the bean separate. In a small application caller, a granted decision submits the next edit to the existing binder and an ungranted decision leaves its state untouched. Cross the two heap shapes with decision histories such as grant → decline → grant and grant → grant → grant. Observe the sequence of decisions, edit count, object identities, field values and error ledger. A measured starting grid used Security 6.3.0 with Framework 6.1.7. It always submitted the first two edits and gated the third. All **64 histories** matched the independent decision and bean-state expectations (two heap shapes × two prefixes × 16 authority subsets). The third write occurred 56 times and was skipped eight times. The earlier field error remained visible in all 64. Freeze this as the primary combined caller. The varying three-decision histories above are a further experiment. Requalify the A1 result on the combined dependency graph.

### A3 · Spring Framework #36911, property names from real method metadata

Call `new Property(type, type.getMethod(methodName), null).getName()` on actual record components and ordinary getter methods. Compile the fixture so that the declaring class, method and backing field are present on both revisions. The patch examines whether there is a matching non-static field for a plain accessor. The same method spelling can resolve differently depending on the declaring class. [Upstream change][property-pr] · [Historical tests][property-test]

| Fixture method | Parent | Landed |
|---|---|---|
| Record component `budget()` | empty string | `budget` |
| Record component `issue()` | `sue` | `issue` |
| Record component `getWidget()` | `widget` | `getWidget` |
| Plain component `name()` / ordinary getter `getName()` | `name` / `name` | `name` / `name` |

These ten public calls were replayed with each revision’s unmodified `Property.java` ahead of common Spring Core 7.0.4 and JSpecify 1.0.0 dependencies. Bind the historical artifacts on the VM for the scored comparison. Add a record with an *additional getter* named `getWidget()` and no matching field. Its expected property is `widget`. This pairs the same method spelling with different metadata and makes a useful test of a reusable reflection guarantee. Run `PropertyTests#resolveNameForRecordAccessorEmbeddingGetPrefix` with the ordinary getter and record-component controls.

### A4 · Spring Framework #23893, formatter precedence during binding

Configure a `DateFormatterRegistrar` with a global ISO date-time formatter. Bind `"10/31/09 1:05"` to a bean property annotated with its local `M/d/yy h:mm` pattern. Use the real `DataBinder`, formatting conversion service and public property accessor. Freeze US locale, an explicit UTC timezone, and the year interpretation on the chosen historical JVM. The upstream regression is `DateFormattingTests#testBindDateAnnotatedPatternWithGlobalFormat`. [Landed change][format-pr] · [Historical setup and test][format-test]

The preflight used each original registrar against Spring 5.2.0.RELEASE. Both revisions displayed **the identical string**. On the parent, the bean date was null and the binder returned one field error carrying the rejected text. The fix stored **2009-10-31T01:05:00Z**, with zero errors. Freeze the stored date, error count and displayed value as one changed-behavior claim. The displayed text alone would have given the parent a false pass. Preserve a valid global-format input on an unannotated field and a malformed local-format input with its field error. Repeat a valid edit after the malformed one and reuse A1’s prefix observer. Check the historical named test separately from the UTC application caller.

**Spring exit criteria.** Return a paired historical result for each existing API, a landed-only feature result for the builder, and a release-pinned history result for A1. Aim for strict native closure of one complete binder history and one public role decision including its hierarchy. For the combined caller, publish exactly which construction or state guarantee was reused, which is still conditional, and which ordinary input exposes any remaining gap.

# Brief B · Prove a transformation from input shape to numeric result

**Deliverable.** Four examples spanning a constructed caller, a deliberate collection-contract change, an IEEE-754 search repair and a precision-sensitive parser repair. Start with a small actual mapping pipeline. Use the scalar or inner-row result as a stepping stone to the complete public operation.

### B1 · Ragged token rows, boxed method references and array factories

Use Apache Commons Lang at the landed revision of #1635 for the feature run, allowing B4 to reuse the same historical artifact. This is a constructed client of the one-argument `NumberUtils.toInt(String)` API, which uses zero when parsing fails. The earlier plan’s single-row caller was also replayed against unmodified Commons Lang 3.17.0 source. Keep the simple row method as a diagnostic if the two-dimensional caller stops first at array intake. [Pinned parser][numbers] · [Java lambda adaptation][metafactory]

```java
static Integer[][] parseRows(String[][] rows) {
    return Arrays.stream(rows)
        .map(row -> Arrays.stream(row)
            .map(NumberUtils::toInt)
            .toArray(Integer[]::new))
        .toArray(Integer[][]::new);
}
```

For `a = ["-2","bad",null,"2147483648","+7"]`, the observed row is `[-2,0,0,0,7]`. Seed the full fixture with `[a, a, a.clone(), e, e, new String[0], ["+7"], ["bad","-2"]]`, where `e` is an empty row. On the JVM all **28 pairs of output rows were distinct**. Changing the first result cell left its siblings, the input and a second invocation’s result untouched. Also cover an empty outer array, a null token and unequal row lengths. Freeze non-null row references in the primary claim.

**Two claims.** Check row lengths, order and values against a small independent signed-decimal grammar with 32-bit range checks and default zero. Check fresh output rows, preserved input aliases and mutation isolation separately. For the bounded proof, start with 0–3 rows, widths 0–2, and the five tokens above. Construct repeated non-null rows and equal-but-separate copies explicitly in the caller. Keep the larger measured fixture as a named regression and record the generated case count. A memoizer keyed on input row identity returns correct values but fails on the repeated row. Check boxed elements by value. Disassembly on the historical caller showed four lambda bootstrap sites. The mapper’s actual target returns primitive `int`, its instantiated SAM returns `Integer`, and the two `IntFunction` factories allocate `Integer[]` and `Integer[][]`. Capture those descriptors and execute the real callback. Implement the adaptation needed by this caller, then try a second consumer before extending it further.

### B2 · Vavr/Javaslang #1829, transpose a rectangular matrix and reject ragged input

Use historical package `javaslang.collection` and public `List.transpose(List<List<T>>)`. This is an intentional change to the ragged-input contract. The landed implementation allocates an `Object[][]`, checks row sizes and applies two collection factories. That couples reference-array writes with erased callbacks on a real library path. A ragged case exits before those factories run, so include a non-square rectangular case. [Upstream PR][vavr] · [Landed implementation][transpose-src] · [Inherited upstream tests][transpose-test]

| Input | Historical parent | Landed revision |
|---|---|---|
| `[[1,2,3],[4,5,6]]` | `[[1,4],[2,5],[3,6]]` | Same |
| `[[1,2],[3]]` | `[[1,3],[2]]` | `IllegalArgumentException` |
| `[[],[1]]` | `[[1]]` | `IllegalArgumentException` |
| `[[],[]]` | `[]` | `[]` |

On the JVM we also enumerated 400 matrices per revision: outer height 0–3, each row independently any sequence of width 0–2 over {0,1}. The parent matched the landed contract on **102/400** and the landed version on **400/400**. All 298 differences were ragged shapes. The production bytecode exercised multidimensional reference-array allocation, a captured predicate, reference stores and a `Function.apply` call. Freeze that finite grid. Check dimensions and `out[c][r] == in[r][c]` on positive-width rectangles, including repeated values and distinguishable cells. Check the typed exceptional outcome on ragged inputs. Run the inherited `AbstractSeqTest#shouldNotTransposeForMissingOrEmptyValues` and `#shouldTransposeIfMultiValuedWithMoreColumnsThanRows` through the concrete list tests. The named empty, one-empty-row and singleton fast paths return the same outer object. Keep those identity checks separate from value equality. Double-transpose equality applies to positive-width rectangles. A two-row zero-column input loses its shape. Observe rectangular and ragged control flow at the actual public entry. A copy of the coordinate oracle inside the adapter cannot qualify as the production transpose.

### B3 · Commons Lang #1589, search for NaN with a tolerance

Call the public four-argument `ArrayUtils.indexOf(double[], double, int, double)`. With tolerance zero, searching `[-∞, qNaN, +∞, -0.0, +0.0]` for NaN from index zero returned **−1 on the parent and 1 on the fix**. Searches for the two infinities and for zero retained their first-match indices. Upstream selectors include `ArrayUtilsTest#testIndexOfDoubleNaN` and `#testContainsDoubleNaN`. [PR][nan-pr] · [Test source][nan-test]

Construct a bounded family of arrays of length 0–3 from two distinct quiet-NaN bit patterns, signed zeros and a finite sentinel. Include null/empty arrays and starts from −1 through length+1. Retain the five-element witness as a named case. An integer-bit oracle recognizes a NaN by its exponent and nonzero significand and scans from the clamped start. Compare first-match index and input preservation. Repeated NaNs distinguish first from last. Signed-zero controls distinguish this equality rule from raw-bit equality. Freeze tolerance zero for the primary claim. As a stretch, use a small finite threshold with exact binary fractions and check both boundary inclusions.

### B4 · Commons Lang #1635, preserve precision and result type in decimal parsing

Call `NumberUtils.createNumber(String)`. For `"0.100000001490116121"`, the public parent returned `Float 0.1`. The fix returned a `BigDecimal` with coefficient `100000001490116121` and scale 18. An adjacent final digit of 2 and the negative of the first literal also distinguished the revisions. The controls `"0.1"`, `"0.5"` and `"17"` retained their classes and values. These are direct JVM replays on both pinned production sources. [PR][prec-pr] · [Historical regression in NumberUtilsTest][prec-test]

Observe runtime class and value together. For exact decimals derive sign, coefficient and scale from the lexical input with integer operations. For Float or Double controls compare the expected width and bits. Add an unchanged exception control for a malformed token and keep typed exception behavior separate from B1’s default-zero API. Preserve the upstream `NumberUtilsTest#testCreateNumber` regression. Freeze a small explicit set of strings after calibration. Adjacent decimals can legitimately choose different result classes. A native proof limited to the final `BigDecimal` constructor leaves the public parser claim open.

**Data exit criteria.** Aim for strict native closure of B1’s value and alias claims and one historical public change. For B3/B4, distinguish a complete finite input family, a bounded symbolic bit-pattern family, and general arithmetic. The current engine has symbolic floating-point comparisons and bit operations, and implements selected arithmetic over a certified finite set of reachable operands. Keep each operation’s actual bound in its result. Use ordinary input replay plus an independent oracle for any discovered counterexample. [Floating implementation][fp] · [Java Double representation][double]

## Historical source pins

All historical rows except the role builder use the landed commit’s first parent. Use the project POM or Gradle dependencies for each checkout. Preserve the difference between full historical builds, source-slice checks and release controls.

| Example | Before | Landed / release |
|---|---|---|
| A1 · Spring binder fixture | Single-version public contract | Framework `6.2.3` |
| A2 · Spring Security #14196 | `10d88cdf28449cbc4789edfe7111f2cdec9902d6` | `ee8bc78cbcd4a0a42c7e7dc2a05b5aeb29c336ae`, via feature commit `7d366242ce4ec377880fdb29b7e5ba068cf52deb` |
| A3 · Spring Framework #36911 | `fd95ab16baa2353416e96bddbd979169a9618260` | `f067d40f0a646a98d0e2735a34b6e31f0e3f2c97` |
| A4 · Spring Framework #23893 | `43a86565cac09de05e50678721cbc83a61a43a6e` | `4beb25b318486baef65fbc3c1118b43aab9f3dc5` |
| B1 · Boxed row mapper | Single-version client contract | Commons Lang at the B4 landed commit |
| B2 · Vavr #1829 | `a8cace88bfb12a9a7e1977a5765753798962e942` | `84a4c690a009c55098ec8f7106c4867e0af747c0` |
| B3 · Commons Lang #1589 | `9bca5d09c6d16a5524a3cd1d38305687ad7fdca4` | `52c06bea2f2b6c277c517dc9f5bb0d62d17e073c` |
| B4 · Commons Lang #1635 | `1dd7cb14c233140a8e76ba5441b6360a239a98dc` | `5904c573ffacaa5d8836ffc2b346f400c8901ed1` |

## Execution and reporting for either brief

1. Freeze each public entry, input family, caller construction, observation and expected outcome before changing the verifier. For an intentional feature, record whether the API exists on each side. For a single release, retain the reference implementation or independent oracle and one deliberately wrong control. Keep each brief’s own denominator by subject and claim.
2. Rebuild both original artifacts for historical changes. Run the named upstream test on the VM, transplanting test code only where needed. For application fixtures, run the supplied witness and preservation histories on the pinned release instead. Record actual loaded classes and JARs, ordered classpaths, build and subject JDKs, locale or clock settings where relevant, and verifier digest. The JVM preflights in this document used OpenJDK 21.0.13. They motivate the claims. Native results are work for these briefs.
3. Use the normal managed pipeline and standing timebox. Inspect `python3 examples/tools/build.py --plan ID` and submit the normal task entry for each example. Run ordinary strict native and the independent finite JVM route first. Keep a smaller producer, supplied startup state or narrowed domain as a separately named result. When a technique stalls, record the first unsupported call or unproved proposition and advance another example. [Project rules][loop]
4. Leave runnable examples, a per-brief scorecard and a short report describing one transfer attempt. A useful row names the public claim, original witness or proof, input coverage, first unresolved dependency, and which earlier fact was consumed. Measure the complete workflow with and without reuse on equal scope when both routes succeed. Report new reachability separately from speed. Let demonstrated reuse determine which research code becomes shared infrastructure.

[develop]: https://github.com/pilifs/in-the-loop/tree/209ecb6e4eb61fec5b72ad03113b066a9e204ce5
[active]: https://github.com/pilifs/in-the-loop/blob/209ecb6e4eb61fec5b72ad03113b066a9e204ce5/llm-dlc/loops/java-domain-proof-campaign.md
[e362]: https://github.com/pilifs/in-the-loop/tree/209ecb6e4eb61fec5b72ad03113b066a9e204ce5/examples/362-avro-buffered-encoder-cursor
[state]: https://github.com/pilifs/in-the-loop/blob/209ecb6e4eb61fec5b72ad03113b066a9e204ce5/llm-dlc/loops/domain-foundations-strategy-results.md
[lcs]: https://github.com/pilifs/in-the-loop/blob/209ecb6e4eb61fec5b72ad03113b066a9e204ce5/examples/308-commons-text-longest-common-subsequence/README.md
[examples]: https://github.com/pilifs/in-the-loop/blob/209ecb6e4eb61fec5b72ad03113b066a9e204ce5/llm-dlc/loops/twenty-example-fast-follow-results.md
[lambda-engine]: https://github.com/pilifs/in-the-loop/blob/209ecb6e4eb61fec5b72ad03113b066a9e204ce5/lib/src/bmc/mod.rs#L5281
[old]: https://github.com/pilifs/in-the-loop/blob/209ecb6e4eb61fec5b72ad03113b066a9e204ce5/llm-dlc/loops/foundation-domain-streams.md
[binder]: https://docs.spring.io/spring-framework/docs/6.2.3/javadoc-api/org/springframework/validation/DataBinder.html
[hier-pr]: https://github.com/spring-projects/spring-security/pull/14196
[hier-test]: https://github.com/spring-projects/spring-security/blob/ee8bc78cbcd4a0a42c7e7dc2a05b5aeb29c336ae/core/src/test/java/org/springframework/security/access/hierarchicalroles/RoleHierarchyImplTests.java
[auth-manager]: https://github.com/spring-projects/spring-security/blob/ee8bc78cbcd4a0a42c7e7dc2a05b5aeb29c336ae/core/src/main/java/org/springframework/security/authorization/AuthorityAuthorizationManager.java
[property-pr]: https://github.com/spring-projects/spring-framework/pull/36911
[property-test]: https://github.com/spring-projects/spring-framework/blob/f067d40f0a646a98d0e2735a34b6e31f0e3f2c97/spring-core/src/test/java/org/springframework/core/convert/PropertyTests.java
[format-pr]: https://github.com/spring-projects/spring-framework/pull/23893
[format-test]: https://github.com/spring-projects/spring-framework/blob/4beb25b318486baef65fbc3c1118b43aab9f3dc5/spring-context/src/test/java/org/springframework/format/datetime/DateFormattingTests.java
[numbers]: https://github.com/apache/commons-lang/blob/5904c573ffacaa5d8836ffc2b346f400c8901ed1/src/main/java/org/apache/commons/lang3/math/NumberUtils.java
[metafactory]: https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/invoke/LambdaMetafactory.html
[vavr]: https://github.com/vavr-io/vavr/pull/1829
[transpose-src]: https://github.com/vavr-io/vavr/blob/84a4c690a009c55098ec8f7106c4867e0af747c0/javaslang/src/main/java/javaslang/collection/Collections.java
[transpose-test]: https://github.com/vavr-io/vavr/blob/84a4c690a009c55098ec8f7106c4867e0af747c0/javaslang/src/test/java/javaslang/collection/AbstractSeqTest.java
[nan-pr]: https://github.com/apache/commons-lang/pull/1589
[nan-test]: https://github.com/apache/commons-lang/blob/52c06bea2f2b6c277c517dc9f5bb0d62d17e073c/src/test/java/org/apache/commons/lang3/ArrayUtilsTest.java
[prec-pr]: https://github.com/apache/commons-lang/pull/1635
[prec-test]: https://github.com/apache/commons-lang/blob/5904c573ffacaa5d8836ffc2b346f400c8901ed1/src/test/java/org/apache/commons/lang3/math/NumberUtilsTest.java
[fp]: https://github.com/pilifs/in-the-loop/blob/209ecb6e4eb61fec5b72ad03113b066a9e204ce5/lib/src/bmc/floating.rs
[double]: https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/Double.html
[loop]: https://github.com/pilifs/in-the-loop/blob/209ecb6e4eb61fec5b72ad03113b066a9e204ce5/llm-dlc/loops/brief-template.md#standing-rules

## Setup Agent Notes

*Added 2026-11-22 by the watcher, after a setup pass by Claude Opus 5.5 (run `spring-setup`, session `b30353b6`) that did only mechanical setup before the domain work. The full record, with every path, digest and command, is [`llm-dlc/loops/spring-and-java-data-setup.md`](spring-and-java-data-setup.md) in the repository: read its Summary table first.*

**What is ready, under `~/.cache/in-the-loop/`** (3.2 GB, outside the checkout):

- **Sources.** One bare mirror per upstream (`git-mirrors/{spring-framework,spring-security,commons-lang,vavr}.git`), holding only the 13 pinned commits, and a detached worktree per pinned revision in `spring-java-data/src/`. Every landed commit's first parent is this brief's "before" commit, and Spring Security's `10d88cdf → 7d366242 → ee8bc78c` chain is confirmed. The six signed commits verify, in a keyring kept apart from the user's.
- **Toolchains.** JDKs 8, 11, 17, 21.0.13 (the brief's preflight JVM) and 25 were already installed under SDKMAN, and Maven 3.10.0. Gradle 5.6.3, 8.5 and 9.7.0 and all seven wrapper jars match gradle.org's checksums.
- **Dependencies.** A Maven repository (`spring-java-data/m2`, use `mvn -s spring-java-data/maven-settings.xml`) and a `GRADLE_USER_HOME` (`spring-java-data/gradle-home`). They cache B1–B4 and the A2 and A3 historical builds, and offline reruns were checked. Released sets, each checked against Central with a classpath file, are in `spring-java-data/releases`: Framework 6.2.3 (A1), Security 6.3.0 with Framework 6.1.7, Security 6.2.0 with Framework 6.1.1, spring-core 7.0.4 with JSpecify 1.0.0, Framework 5.2.0.RELEASE and Commons Lang 3.17.0.
- **Built originals.** Jars for each pinned revision are in `spring-java-data/artifacts`, with digests and runtime classpaths in the record: Commons Lang (4), Vavr (2), Spring Security core before, feature and landed (3), and spring-core at both #36911 revisions (2).

**What was verified on a JVM:**

- **B1–B4.** Each side's named upstream tests pass, and the landed tests, copied onto the parent code, fail as expected. Every headline witness in this brief reproduces on JDK 21.0.13: B1's row, distinct pairs and four lambda sites; B2's four table rows; B3's −1 against 1; B4's `Float 0.1` against `BigDecimal` with scale 18, controls unchanged.
- **A1.** The whole prefix table on the released 6.2.3.
- **A2** (verification job passed). Each side's tests pass at all three revisions. On the three built jars and on 6.3.0 with 6.1.7, the legacy text configuration and the builder agree: 14 of 16 subsets granted per prefix, with identical reachable sets. This compares the two routes with each other only. No independent graph oracle exists yet.
- **A3** (job passed). The landed `PropertyTests` pass 18/18, and transplanted onto the parent they fail 9/18. The table reproduces exactly on the built jars and on each revision's `Property.java` compiled ahead of spring-core 7.0.4.
- **A4.** Reproduced through this brief's slice route only: each revision's registrar ahead of 5.2.0.RELEASE, on JDK 21 and on JDK 8. The parent gives date `null` with 1 field error, the fix `2009-10-31T01:05:00Z` with 0 errors.

**What to know before starting:**

- **A4 has no historical build.** The Framework 5.2 build needs two build plugins, `io.spring.asciidoctor:spring-asciidoctor-extensions:0.1.3.RELEASE` and `org.jfrog.buildinfo:build-info-extractor:2.13.10`, only from `repo.spring.io/plugins-release`, which has refused anonymous access since 2023 (401). The slice route above is the brief's own and needs no build. If the full build or `DateFormattingTests` is wanted, the watcher's suggestion is a Gradle init script under `~/.cache/in-the-loop/spring-java-data/`. It would point the `repo.spring.io/*` repositories at Maven Central and the Gradle Plugin Portal (most of that repository's plugins are on one or the other under the same coordinates) and leave the upstream build files unchanged. Verify the checksums of what resolves, and record any coordinate that cannot be found.
- **A3's build pulls Reactor and Micrometer snapshots,** and also uses `repo.spring.io/milestone` and `/snapshot`. The cached copies are recorded with digests, but an online rebuild may fetch different bytes, so rebuild A3 with `--offline` to keep the recorded inputs.
- **The Spring 5.2.0.RELEASE signature is unchecked:** its 2019 key isn't published with a user ID. Its checksums match Central's.
- **Left for the domain work, on purpose:** all claims, examples and example ids (this brief's note on reserved ids still applies), sidecars, adapters, recipes and verifier runs. Also the grids still to freeze: B2's 400 matrices, A2's omitted-edge control and 64 combined histories, A1's six permutations and fresh-binder control, A4's preservation inputs, and B3's and B4's bounded families.
- **Network access is unchanged.** These caches let the work start at once and keep builds reproducible. Nothing here requires working offline.
