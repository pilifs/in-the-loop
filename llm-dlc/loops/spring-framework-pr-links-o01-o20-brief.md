# Spring Framework — caller-visible behavior across 20 merged changes

## Objective

Determine what changes for applications using these Spring APIs and which existing behavior must survive. Compare the specified landed revisions at the public entry, then follow the result to the observation a caller relies on. Each row gives an outcome that would overturn its prediction.

## spring-projects/spring-framework#37434 · Spring Framework #37434 — An explicit plus sign on hexadecimal integers

**Change and revisions.** [Merged PR #37434](https://github.com/spring-projects/spring-framework/pull/37434). Before `2c5c6b580f90ce77973d16d24bce4c5dce00b558`, after `3e05e8872f529c5f843e68fb6a82250349b9f019`. The change accepts a leading plus in hexadecimal detection and in the separate BigInteger decoder. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/2c5c6b580f90ce77973d16d24bce4c5dce00b558...3e05e8872f529c5f843e68fb6a82250349b9f019)

**Public scenario.** Pass the same string to the two-argument NumberUtils.parseNumber overload with explicit target classes. Record the returned Java type and exact value, or the exception.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37434.1 · Intent | Parse `+0x7f` as Integer and BigInteger. | The parent is expected to throw NumberFormatException for each. The landing should return Integer 127 and BigInteger 127 respectively. | The PR reports the Integer exception. Seven sixteens plus fifteen is 127, and unary plus preserves it. | Either merged call rejects the text, changes the value or returns another type. |
| spring-projects/spring-framework#37434.2 · Control | Parse `-0x7f` as Integer and `+127` as BigInteger. | Both revisions should yield −127 and 127 in the requested types. | Existing signed hex and decimal inputs denote the same magnitudes with opposite and positive signs. | Either control throws or changes sign, value or type. |
| spring-projects/spring-framework#37434.3 · Challenge | At the landing, try both `+0x80` and `+#80` with Short and Byte. | Each spelling should yield Short 128. Both Byte calls should throw NumberFormatException. | The JDK integral decoders recognize both prefixes. Signed byte ends at 127 while short includes 128. | A prefix changes the outcome, or a Byte wraps to −128. |

**Evidence and limits.** The PR gives an original failing Integer call. The regression and the BigInteger-specific path support the other predictions. A single successful Integer parse misses BigInteger decoding and overflow.

**Technical notes.** Use spring-core and its NumberUtilsTests. The maintainer identifies a subsequent revision, cb98dd335255f9f6bb7773fd718249faec27101e. The comparison here ends at the PR landing.

**Sources.** [NumberUtils.java](https://github.com/spring-projects/spring-framework/blob/3e05e8872f529c5f843e68fb6a82250349b9f019/spring-core/src/main/java/org/springframework/util/NumberUtils.java) · [NumberUtilsTests.java](https://github.com/spring-projects/spring-framework/blob/3e05e8872f529c5f843e68fb6a82250349b9f019/spring-core/src/test/java/org/springframework/util/NumberUtilsTests.java) · [spring-core build](https://github.com/spring-projects/spring-framework/blob/3e05e8872f529c5f843e68fb6a82250349b9f019/spring-core/spring-core.gradle)

## spring-projects/spring-framework#37576 · Spring Framework #37576 — A Sunday-to-Sunday cron range fires once a week

**Change and revisions.** [Merged PR #37576](https://github.com/spring-projects/spring-framework/pull/37576). Before `7ff9e3d0314766984efb20b6cbf2cfe6e19e378d`, after `1f083db2da6fe35908f1365f177c2091f5c0a26a`. The range parser previously expanded the singleton Sunday range to the whole week. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/7ff9e3d0314766984efb20b6cbf2cfe6e19e378d...1f083db2da6fe35908f1365f177c2091f5c0a26a)

**Public scenario.** Parse `0 0 0 * * SUN-SUN` with CronExpression.parse. Call next on LocalDateTime.of(2021,2,25,15,0), then feed the returned midnight back to next. LocalDateTime removes time-zone transitions from the fixture.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37576.1 · Intent | Advance once from Thursday 25 February at 15:00. | The PR reports Friday 26 February at 00:00 on the parent. Expect Sunday 28 February at 00:00 on the landing. | Both endpoints name Sunday. The first Sunday after Thursday the 25th is the 28th. | The landing returns Friday, skips the first Sunday or changes the time of day. |
| spring-projects/spring-framework#37576.2 · Control | Use the singleton day field SUN and then 0-0 with the same start. | Both should produce 28 February at midnight on both revisions. | The PR reports both spellings already denote a single Sunday. | Either spelling gives another date or disagrees with the other. |
| spring-projects/spring-framework#37576.3 · Challenge | Start exactly at 28 February 00:00 and compare SUN-SUN, 7-7 and SUN on the landing. | All three next calls should return 7 March 00:00. | next advances strictly past its seed. There is no intervening Sunday, even though the month changes. | Any expression repeats its seed, returns 1 March or misses 7 March. |

**Evidence and limits.** The author reports the Friday result and reports the field and public regression tests failing before and passing after, with the spring-context checks passing on JDK 25. Inspecting only the internal Sunday bit misses what next does at an exact match.

**Technical notes.** Use spring-context, CronExpressionTests and a six-field Spring expression with seconds first.

**Sources.** [BitsCronField.java](https://github.com/spring-projects/spring-framework/blob/1f083db2da6fe35908f1365f177c2091f5c0a26a/spring-context/src/main/java/org/springframework/scheduling/support/BitsCronField.java) · [CronExpressionTests.java](https://github.com/spring-projects/spring-framework/blob/1f083db2da6fe35908f1365f177c2091f5c0a26a/spring-context/src/test/java/org/springframework/scheduling/support/CronExpressionTests.java) · [BitsCronFieldTests.java](https://github.com/spring-projects/spring-framework/blob/1f083db2da6fe35908f1365f177c2091f5c0a26a/spring-context/src/test/java/org/springframework/scheduling/support/BitsCronFieldTests.java) · [spring-context build](https://github.com/spring-projects/spring-framework/blob/1f083db2da6fe35908f1365f177c2091f5c0a26a/spring-context/spring-context.gradle)

## spring-projects/spring-framework#30238 · Spring Framework #30238 — A single Hamcrest matcher sees the first HTTP request value

**Change and revisions.** [Merged PR #30238](https://github.com/spring-projects/spring-framework/pull/30238). Before `f0eb43a6af37df784cd2f0367022c5dba4273bf0`, after `95883b9eb7228dfeafc227de9d2ccfbd22e90ce8`. Two submitted commits landed together. The list-valued factories became headerList and queryParamList so the existing scalar matcher calls resolve as intended. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/f0eb43a6af37df784cd2f0367022c5dba4273bf0...95883b9eb7228dfeafc227de9d2ccfbd22e90ce8)

**Public scenario.** Compile the same Java source separately with each spring-test revision and the same Hamcrest factory. Create a MockClientHttpRequest with X-Choice values a,b and a URI ending in ?q=a&q=b. Call match(request) on each factory result and record normal return or AssertionError.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#30238.1 · Intent | Call header("X-Choice", equalTo("a")) and queryParam("q", equalTo("a")) with unqualified generic inference. | Expect two assertion failures before and two successful matches after. | The issue documents inference selecting a single list parameter. A String equals the first value a, while a list containing a and b does not equal that String. | Either recompiled landed matcher rejects the request, or both parent calls already select the scalar overload under the same compiler. |
| spring-projects/spring-framework#30238.2 · Control | Give the factory an explicit type witness, CoreMatchers.<String>equalTo("a"). | The header and query matchers should succeed on both revisions. | The explicit String matcher targets the element overload. The reporter used this workaround. | Either typed matcher receives the entire list or fails on a. |
| spring-projects/spring-framework#30238.3 · Challenge | On the landing change only the second value b to c. Compare the two scalar calls with headerList and queryParamList using Hamcrest contains("a","b"). | Scalar calls still pass. Both list calls pass on [a,b] and fail on [a,c]. | The second item lies outside a one-element scalar expectation and inside the ordered list expectation. | A scalar result depends on the tail, or a list matcher accepts the changed tail. |

**Evidence and limits.** Issue #30220 reports the header symptom with spring-test 5.3.26. The landed suite exercises both families. An explicitly typed matcher alone hides the overload regression.

**Technical notes.** Use spring-test's web.client.match package and Hamcrest. This comparison requires source recompilation on each classpath because javac chooses the method descriptor at the call site.

**Sources.** [MockRestRequestMatchers.java](https://github.com/spring-projects/spring-framework/blob/95883b9eb7228dfeafc227de9d2ccfbd22e90ce8/spring-test/src/main/java/org/springframework/test/web/client/match/MockRestRequestMatchers.java) · [MockRestRequestMatchersTests.java](https://github.com/spring-projects/spring-framework/blob/95883b9eb7228dfeafc227de9d2ccfbd22e90ce8/spring-test/src/test/java/org/springframework/test/web/client/match/MockRestRequestMatchersTests.java) · [Issue #30220](https://github.com/spring-projects/spring-framework/issues/30220) · [spring-test build](https://github.com/spring-projects/spring-framework/blob/95883b9eb7228dfeafc227de9d2ccfbd22e90ce8/spring-test/spring-test.gradle)

## spring-projects/spring-framework#36913 · Spring Framework #36913 — Optional conversion eligibility reflects its known element type

**Change and revisions.** [Merged PR #36913](https://github.com/spring-projects/spring-framework/pull/36913). Before `bcfa6c3c4fc9133229bcf252827989555ec009a7`, after `af466ccf63bc55f82961b6627fe0c97c43a54632`. DefaultConversionService now consults the Optional's declared generic argument when selecting the unwrapping converter. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/bcfa6c3c4fc9133229bcf252827989555ec009a7...af466ccf63bc55f82961b6627fe0c97c43a54632)

**Public scenario.** Use a new DefaultConversionService. Construct a TypeDescriptor with ResolvableType.forClassWithGenerics(Optional.class,Integer.class) and a target descriptor for LocalDate. Ask canConvert before calling convert with Optional.of(42) and those same descriptors.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#36913.1 · Intent | Ask about Optional<Integer> to LocalDate with default converters. | The PR reports true followed by conversion failure before. Expect false and a ConverterNotFoundException on a direct attempt after. | An Integer has no default LocalDate conversion. The merged regression checks predicate and exception together. | The merged predicate offers the conversion, or the direct attempt produces a date. |
| spring-projects/spring-framework#36913.2 · Control | Change target to String with the same Optional.of(42). Also ask about raw Optional to LocalDate. | Both revisions should say true and yield `42` as a String for the typed conversion. The raw predicate should remain true. | Default number-to-string conversion supplies the value. Raw Optional has no declared element that would rule a converter out. | A typed value is lost, or an unknown element type is rejected up front. |
| spring-projects/spring-framework#36913.3 · Challenge | On the landing use a fresh service with an explicit Integer→LocalDate converter defined by LocalDate.ofEpochDay. Repeat the original query and convert Optional.of(42). | The predicate should now be true and the result 1970-02-12. | The supplied conversion defines the expected result. An implementation that simply rejects all Optional-to-date pairs cannot satisfy it. | The newly registered path stays unavailable or unwraps to the wrong date. |

**Evidence and limits.** The PR describes the false positive. The tests distinguish raw types, unbounded and bounded wildcards, and assert the typed failure. An exception alone cannot establish whether eligibility changed.

**Technical notes.** Use spring-core with TypeDescriptor-aware overloads. A runtime Optional.class alone loses the parameter that distinguishes the primary case.

**Sources.** [OptionalToObjectConverter.java](https://github.com/spring-projects/spring-framework/blob/af466ccf63bc55f82961b6627fe0c97c43a54632/spring-core/src/main/java/org/springframework/core/convert/support/OptionalToObjectConverter.java) · [DefaultConversionServiceTests.java](https://github.com/spring-projects/spring-framework/blob/af466ccf63bc55f82961b6627fe0c97c43a54632/spring-core/src/test/java/org/springframework/core/convert/converter/DefaultConversionServiceTests.java) · [spring-core build](https://github.com/spring-projects/spring-framework/blob/af466ccf63bc55f82961b6627fe0c97c43a54632/spring-core/spring-core.gradle)
