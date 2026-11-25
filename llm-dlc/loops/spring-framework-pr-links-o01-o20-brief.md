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
| spring-projects/spring-framework#30238.2 · Control | Give the factory an explicit type witness, `CoreMatchers.<String>equalTo("a")`. | The header and query matchers should succeed on both revisions. | The explicit String matcher targets the element overload. The reporter used this workaround. | Either typed matcher receives the entire list or fails on a. |
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
| spring-projects/spring-framework#36913.1 · Intent | Ask about `Optional<Integer>` to LocalDate with default converters. | The PR reports true followed by conversion failure before. Expect false and a ConverterNotFoundException on a direct attempt after. | An Integer has no default LocalDate conversion. The merged regression checks predicate and exception together. | The merged predicate offers the conversion, or the direct attempt produces a date. |
| spring-projects/spring-framework#36913.2 · Control | Change target to String with the same Optional.of(42). Also ask about raw Optional to LocalDate. | Both revisions should say true and yield `42` as a String for the typed conversion. The raw predicate should remain true. | Default number-to-string conversion supplies the value. Raw Optional has no declared element that would rule a converter out. | A typed value is lost, or an unknown element type is rejected up front. |
| spring-projects/spring-framework#36913.3 · Challenge | On the landing use a fresh service with an explicit Integer→LocalDate converter defined by LocalDate.ofEpochDay. Repeat the original query and convert Optional.of(42). | The predicate should now be true and the result 1970-02-12. | The supplied conversion defines the expected result. An implementation that simply rejects all Optional-to-date pairs cannot satisfy it. | The newly registered path stays unavailable or unwraps to the wrong date. |

**Evidence and limits.** The PR describes the false positive. The tests distinguish raw types, unbounded and bounded wildcards, and assert the typed failure. An exception alone cannot establish whether eligibility changed.

**Technical notes.** Use spring-core with TypeDescriptor-aware overloads. A runtime Optional.class alone loses the parameter that distinguishes the primary case.

**Sources.** [OptionalToObjectConverter.java](https://github.com/spring-projects/spring-framework/blob/af466ccf63bc55f82961b6627fe0c97c43a54632/spring-core/src/main/java/org/springframework/core/convert/support/OptionalToObjectConverter.java) · [DefaultConversionServiceTests.java](https://github.com/spring-projects/spring-framework/blob/af466ccf63bc55f82961b6627fe0c97c43a54632/spring-core/src/test/java/org/springframework/core/convert/converter/DefaultConversionServiceTests.java) · [spring-core build](https://github.com/spring-projects/spring-framework/blob/af466ccf63bc55f82961b6627fe0c97c43a54632/spring-core/spring-core.gradle)

## spring-projects/spring-framework#30045 · Spring Framework #30045 — SpEL calls a function bound to a Java receiver

**Change and revisions.** [Merged PR #30045](https://github.com/spring-projects/spring-framework/pull/30045). Before `d3c3088c6ba27a5a6d7f458a76f5d91320aaf828`, after `906c54faffc75721b98f9b9cf63d35edd81f7b4f`. SpEL can invoke MethodHandle values under its existing function syntax. StandardEvaluationContext gains a registerFunction overload for handles. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/d3c3088c6ba27a5a6d7f458a76f5d91320aaf828...906c54faffc75721b98f9b9cf63d35edd81f7b4f)

**Public scenario.** Use an interpreted SpelExpressionParser and a new StandardEvaluationContext. Look up the public virtual method String.concat(String) using MethodHandles.publicLookup(), bind it to the String `red-`, and use context.setVariable("tag", handle), available on both revisions. Parse and evaluate `#tag('fox')`.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#30045.1 · Intent | Evaluate the one-argument expression with red- bound as the receiver. | Expect a SpelEvaluationException on the parent and the String red-fox after. | The old function evaluator requires a reflective Method. Direct Java concatenation on the captured receiver gives red-fox. | The parent already invokes this handle, or the landing rejects the call or loses the prefix. |
| spring-projects/spring-framework#30045.2 · Control | Register the reflective public static Integer.toString(int) under num and evaluate #num(7). | Both revisions should return the String 7. | SpEL already supported static reflective functions. Direct invocation gives the same typed result. | Either evaluation rejects the Method or returns an Integer instead. |
| spring-projects/spring-framework#30045.3 · Challenge | On the landing reuse the same parsed #tag expression. Replace its binding with the same virtual handle bound to blue-, now using the new registerFunction overload. | Successive evaluations should give red-fox then blue-fox with the argument unchanged. | The function variable belongs to the evaluation context. Direct invocation on each receiver supplies an independent expected value. | The second evaluation keeps the first receiver, drops the receiver or changes the argument. |

**Evidence and limits.** The issue requests receiver capture. The pinned scenarios cover static, virtual and partially or fully bound handles. Testing only the new overload could show an API addition without establishing parent evaluation behavior.

**Technical notes.** Use spring-expression with the interpreter and the JDK public lookup. These fixed-arity calls avoid the separate array and varargs adaptation rules described in the new function documentation.

**Sources.** [FunctionReference.java](https://github.com/spring-projects/spring-framework/blob/906c54faffc75721b98f9b9cf63d35edd81f7b4f/spring-expression/src/main/java/org/springframework/expression/spel/ast/FunctionReference.java) · [StandardEvaluationContext.java](https://github.com/spring-projects/spring-framework/blob/906c54faffc75721b98f9b9cf63d35edd81f7b4f/spring-expression/src/main/java/org/springframework/expression/spel/support/StandardEvaluationContext.java) · [ExpressionLanguageScenarioTests.java](https://github.com/spring-projects/spring-framework/blob/906c54faffc75721b98f9b9cf63d35edd81f7b4f/spring-expression/src/test/java/org/springframework/expression/spel/ExpressionLanguageScenarioTests.java) · [functions.adoc](https://github.com/spring-projects/spring-framework/blob/906c54faffc75721b98f9b9cf63d35edd81f7b4f/framework-docs/modules/ROOT/pages/core/expressions/language-ref/functions.adoc) · [spring-expression build](https://github.com/spring-projects/spring-framework/blob/906c54faffc75721b98f9b9cf63d35edd81f7b4f/spring-expression/spring-expression.gradle) · [Issue #27099](https://github.com/spring-projects/spring-framework/issues/27099)

## spring-projects/spring-framework#37325 · Spring Framework #37325 — Derived HTTP clients keep independent default header and cookie lists

**Change and revisions.** [Merged PR #37325](https://github.com/spring-projects/spring-framework/pull/37325). Before `0c575d443dbdff69349a2369f40491c002dc2c96`, after `4cf6335372556d4f6ccc3a0166318c5f19037e8f`. The client builders copy individual value lists when deriving builders. WebTestClient also takes a snapshot when it builds a client. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/0c575d443dbdff69349a2369f40491c002dc2c96...4cf6335372556d4f6ccc3a0166318c5f19037e8f)

**Public scenario.** Set default header X-Mode and cookie id to one. Build a base client. On base.mutate(), append two to both existing names with defaultHeaders(h -> h.add(...)) and defaultCookie, then build. Send a GET through the derivative and through a fresh base.mutate().build(). Read complete header and cookie value lists at the receiving exchange.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37325.1 · Intent | Run this history with RestClient, WebClient and WebTestClient, keeping URI, handler and request defaults fixed. | Expect the new derivative to send [one,two] on both revisions. A fresh derivative of the base is expected to leak two before and send only [one] after for each name. | The PR demonstrates the original RestClient cookie list acquiring two. Each derived configuration starts from the same original defaults. | The landed base derivative sends two, or the edited derivative loses either value. |
| spring-projects/spring-framework#37325.2 · Control | Using fresh fixtures, add a previously absent header X-Extra and cookie extra only to the derived builder. | On both revisions the original should omit both names and still send its initial values. | The previous copy already allocated distinct maps. Adding a new key distinguishes map sharing from value-list sharing. | The new name reaches the original or its previous value disappears. |
| spring-projects/spring-framework#37325.3 · Challenge | Build WebTestClient A from a retained builder. Append two to the builder’s existing header list and cookie, build B, then GET from A after B. | On the landing A should send just one for both names while B sends one and two. The PR describes parent leakage into clients already built. | A's public build boundary precedes the change. Capturing actual requests independently tests the snapshot clients consume. | A sends B's later values, or B sends only A's original values. |

**Evidence and limits.** The PR prints the leaked default from a second RestClient mutation. The WebClient and WebTestClient regressions inspect requests. An implementation that merely copies the top-level maps passes a new-key-only check.

**Technical notes.** The relevant modules are spring-web, spring-webflux and spring-test. Use an in-process request recorder, and decode Cookie header values as name/value pairs. RestClient.Builder and WebClient.Builder also support clone(). WebTestClient exposes mutate() on the built client.

**Sources.** [DefaultRestClientBuilder.java](https://github.com/spring-projects/spring-framework/blob/4cf6335372556d4f6ccc3a0166318c5f19037e8f/spring-web/src/main/java/org/springframework/web/client/DefaultRestClientBuilder.java) · [DefaultWebClientTests.java](https://github.com/spring-projects/spring-framework/blob/4cf6335372556d4f6ccc3a0166318c5f19037e8f/spring-webflux/src/test/java/org/springframework/web/reactive/function/client/DefaultWebClientTests.java) · [MockServerTests.java](https://github.com/spring-projects/spring-framework/blob/4cf6335372556d4f6ccc3a0166318c5f19037e8f/spring-test/src/test/java/org/springframework/test/web/reactive/server/MockServerTests.java) · [spring-test build](https://github.com/spring-projects/spring-framework/blob/4cf6335372556d4f6ccc3a0166318c5f19037e8f/spring-test/spring-test.gradle) · [spring-web build](https://github.com/spring-projects/spring-framework/blob/4cf6335372556d4f6ccc3a0166318c5f19037e8f/spring-web/spring-web.gradle) · [spring-webflux build](https://github.com/spring-projects/spring-framework/blob/4cf6335372556d4f6ccc3a0166318c5f19037e8f/spring-webflux/spring-webflux.gradle)

## spring-projects/spring-framework#37378 · Spring Framework #37378 — Copying a rendering response preserves cookies in both web stacks

**Change and revisions.** [Merged PR #37378](https://github.com/spring-projects/spring-framework/pull/37378). Before `d5a7fc9a9ce32a94176620be4d9d6b070a260b9c`, after `f03b76a53dfd87e53db0c4c72f37e2a87c94f7c2`. RenderingResponse.from copies cookies when rebuilding a functional MVC or WebFlux response. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/d5a7fc9a9ce32a94176620be4d9d6b070a260b9c...f03b76a53dfd87e53db0c4c72f37e2a87c94f7c2)

**Public scenario.** Build a RenderingResponse named checkout with status CREATED, header X-View=summary, model item=book and a currency=EUR cookie with path /shop. Rebuild via RenderingResponse.from(original).modelAttribute("path","/cart").build(). MVC returns a response directly, WebFlux emits it in a Mono. Inspect the model and cookie list, and write the response using the stack’s test response or a simple resolving view.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37378.1 · Intent | Rebuild the populated response in each stack and inspect the copied cookies. | Expect currency to be absent on the parent and present once with value EUR and path /shop after. | The PR reports a response filter losing the handler's cookie. The supplied cookie defines its expected attributes. | Either merged copy loses the cookie, changes its value or widens its path. |
| spring-projects/spring-framework#37378.2 · Control | Repeat without any cookie and add the same path model attribute. | Both revisions should retain view checkout, CREATED, X-View=summary and item=book, add path=/cart and emit no cookie. | These are existing independent rendering fields inherited by from(). | The copy changes status or view, loses either model value, or invents a cookie. |
| spring-projects/spring-framework#37378.3 · Challenge | With two original currency cookies, use EUR at /shop and USD at /account, then add a fresh visit=1 cookie to the copy. Inspect cookies written to the HTTP response. | On the landing both currency value/path pairs and visit=1 should reach the client once. The original should still contain only its two currency entries. | Cookies with one name and different paths can coexist. Comparing value/path pairs tests multiplicity across the serialization boundary. | One path overwrites the other, the copy adds visit to the original, or the wire response drops an entry. |

**Evidence and limits.** The MVC regression checks a written servlet response and the resolved model and view. The WebFlux regression inspects the built response. One getFirst lookup cannot establish cookie multiplicity or wire behavior.

**Technical notes.** Use jakarta.servlet.http.Cookie in spring-webmvc and ResponseCookie in spring-webflux. Supply an in-process view resolver for a reactive write. Compare cookie attributes without requiring a global order or object identity.

**Sources.** [MVC builder](https://github.com/spring-projects/spring-framework/blob/f03b76a53dfd87e53db0c4c72f37e2a87c94f7c2/spring-webmvc/src/main/java/org/springframework/web/servlet/function/DefaultRenderingResponseBuilder.java) · [WebFlux builder](https://github.com/spring-projects/spring-framework/blob/f03b76a53dfd87e53db0c4c72f37e2a87c94f7c2/spring-webflux/src/main/java/org/springframework/web/reactive/function/server/DefaultRenderingResponseBuilder.java) · [MVC regression](https://github.com/spring-projects/spring-framework/blob/f03b76a53dfd87e53db0c4c72f37e2a87c94f7c2/spring-webmvc/src/test/java/org/springframework/web/servlet/function/DefaultRenderingResponseTests.java) · [WebFlux regression](https://github.com/spring-projects/spring-framework/blob/f03b76a53dfd87e53db0c4c72f37e2a87c94f7c2/spring-webflux/src/test/java/org/springframework/web/reactive/function/server/DefaultRenderingResponseTests.java) · [spring-webflux build](https://github.com/spring-projects/spring-framework/blob/f03b76a53dfd87e53db0c4c72f37e2a87c94f7c2/spring-webflux/spring-webflux.gradle) · [spring-webmvc build](https://github.com/spring-projects/spring-framework/blob/f03b76a53dfd87e53db0c4c72f37e2a87c94f7c2/spring-webmvc/spring-webmvc.gradle)

## spring-projects/spring-framework#37218 · Spring Framework #37218 — A stale range validator returns the current resource in full

**Change and revisions.** [Merged PR #37218](https://github.com/spring-projects/spring-framework/pull/37218). Before `749aa1f6a9bd70b637f01b0e2dceb1103cd1c5f1`, after `05619fe624cd410736848b3bf4f83d632cfe54f5`. The range covers both submitted commits, including the final polishing commit. The resource-serving paths consult If-Range before interpreting Range. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/749aa1f6a9bd70b637f01b0e2dceb1103cd1c5f1...05619fe624cd410736848b3bf4f83d632cfe54f5)

**Public scenario.** Serve a repeatable six-byte resource with ASCII bytes abcdef and the strong ETag "v2". Use GET through an MVC static resource handler, a `ResponseEntity<Resource>` controller, a functional MVC resource route and a WebFlux resource response. Configure the same validators for each route; observe status, Content-Range and raw body.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37218.1 · Intent | Send Range: bytes=1-3 and If-Range: "v1". | The parent is expected to send 206 with bcd. The landing should return 200, abcdef and no Content-Range on each route. | The client's validator is stale. RFC 9110 requires ignoring the range so the client can replace its old representation. | Any landed route emits a slice, a partial status or a Content-Range. |
| spring-projects/spring-framework#37218.2 · Control | Use the same Range with no If-Range, then with the matching strong "v2". | Both revisions should return 206, Content-Range bytes 1-3/6 and the exact bytes bcd. | An inclusive range from offsets 1 through 3 selects three known bytes. Both requests authorize serving that range. | Status or endpoints are wrong, or the body cannot be spliced back at offset 1. |
| spring-projects/spring-framework#37218.3 · Challenge | Keep the stale validator and replace the requested range with bytes=broken. Also try a syntactically valid range with W/"v2". | At the landing both should return the entire abcdef and 200. In the first call ignoring the range also suppresses any range-parse failure. | The validator is evaluated before Range. Weak tags cannot authorize combining portions of representations. | The malformed value yields 416 or the weak tag yields a partial body. |
| spring-projects/spring-framework#37218.4 · Date validator | Use a resource known to change at most once per second and an emitted Last-Modified value. Send that exact HTTP-date, then the valid date one second later, with bytes=1-3. | The landing should return 206/bcd for the exact strong date and 200/abcdef for the later date. Before, expect 206/bcd for both. | If-Range date comparison is exact. A later date does not identify the representation used for a previous download. | The exact date loses the range, or the later date is treated as fresh enough. |

**Evidence and limits.** The linked issue reports missing If-Range handling. The landed suites include helper and route-level checks. A helper returning an empty range list cannot establish the final status or bytes. The cross-route matrix is an unexecuted prediction.

**Technical notes.** The relevant modules are spring-web, spring-webmvc and spring-webflux. Supply ETag or Last-Modified on the response before range handling and use an identity-encoded resource of known length. Header dates here use the server’s own HTTP-date format.

**Sources.** [HttpRange.java](https://github.com/spring-projects/spring-framework/blob/05619fe624cd410736848b3bf4f83d632cfe54f5/spring-web/src/main/java/org/springframework/http/HttpRange.java) · [HttpRangeTests.java](https://github.com/spring-projects/spring-framework/blob/05619fe624cd410736848b3bf4f83d632cfe54f5/spring-web/src/test/java/org/springframework/http/HttpRangeTests.java) · [ResourceHttpRequestHandlerTests.java](https://github.com/spring-projects/spring-framework/blob/05619fe624cd410736848b3bf4f83d632cfe54f5/spring-webmvc/src/test/java/org/springframework/web/servlet/resource/ResourceHttpRequestHandlerTests.java) · [HttpEntityMethodProcessorMockTests.java](https://github.com/spring-projects/spring-framework/blob/05619fe624cd410736848b3bf4f83d632cfe54f5/spring-webmvc/src/test/java/org/springframework/web/servlet/mvc/method/annotation/HttpEntityMethodProcessorMockTests.java) · [ResourceHandlerFunctionTests.java](https://github.com/spring-projects/spring-framework/blob/05619fe624cd410736848b3bf4f83d632cfe54f5/spring-webmvc/src/test/java/org/springframework/web/servlet/function/ResourceHandlerFunctionTests.java) · [ResourceWebHandlerTests.java](https://github.com/spring-projects/spring-framework/blob/05619fe624cd410736848b3bf4f83d632cfe54f5/spring-webflux/src/test/java/org/springframework/web/reactive/resource/ResourceWebHandlerTests.java) · [spring-web build](https://github.com/spring-projects/spring-framework/blob/05619fe624cd410736848b3bf4f83d632cfe54f5/spring-web/spring-web.gradle) · [spring-webflux build](https://github.com/spring-projects/spring-framework/blob/05619fe624cd410736848b3bf4f83d632cfe54f5/spring-webflux/spring-webflux.gradle) · [spring-webmvc build](https://github.com/spring-projects/spring-framework/blob/05619fe624cd410736848b3bf4f83d632cfe54f5/spring-webmvc/spring-webmvc.gradle) · [Issue #27952](https://github.com/spring-projects/spring-framework/issues/27952) · [RFC 9110 §13.1.5](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.5)

## spring-projects/spring-framework#37193 · Spring Framework #37193 — Malformed SSE retry hints preserve event delivery

**Change and revisions.** [Merged PR #37193](https://github.com/spring-projects/spring-framework/pull/37193). Before `60b9f4cd3a491a84e1dfe294005729cf49ed36e5`, after `adbc8ceeab6e004ad8664c2ff5639449c18f2396`. The event-stream reader checks for ASCII digits and treats unrepresentable millisecond values as unusable hints. [Landed comparison](https://github.com/spring-projects/spring-framework/compare/60b9f4cd3a491a84e1dfe294005729cf49ed36e5...adbc8ceeab6e004ad8664c2ff5639449c18f2396)

**Public scenario.** Feed a WebFlux WebClient a text/event-stream response and consume bodyToFlux with a `ParameterizedTypeReference<ServerSentEvent<String>>`. Separate events by a blank line. Read each data() and retry(), the event order and the terminal signal. Using the envelope type exposes the retry duration.

### Claims

| ID and role | Input or history | Expected before → after, or relation on both | Independent basis | What would refute it |
|---|---|---|---|---|
| spring-projects/spring-framework#37193.1 · Intent | Send retry:none then data:foo in the first event, and data:bar in the next. | The PR reports NumberFormatException interrupting the stream before the fix. Expect data foo and bar in order, both retry values null, then completion after. | The field is optional. The event parser should ignore an invalid retry field and continue processing data. | The merged stream errors, loses either payload or invents a delay. |
| spring-projects/spring-framework#37193.2 · Control | First event has retry: 25 and data:foo; second has data:bar. | The first Spring event should carry Duration.ofMillis(25), the second no retry field, and both payloads should arrive on both revisions. | The field contains decimal ASCII digits after the single optional space. The Spring envelope represents the fields on each event. | Either revision loses a payload or reports a different duration on the first event. |
| spring-projects/spring-framework#37193.3 · Challenge | Compare two one-event streams: retry: 25 versus retry:25 followed by one trailing ASCII space. In each append a newline, data:foo, and a blank line. | The SSE rule predicts 25 ms for the first and no retry value for the second, with identical foo payloads. The merged source instead appears to accept the trailing space as well. | The field parser drops one optional leading space. A trailing space remains part of the value and is outside the ASCII digits. | A merged duration of 25 ms for the trailing-space event refutes standards compliance even if both payloads arrive. |

**Evidence and limits.** The author reports the malformed nonnumeric failure and describes signs and Arabic-Indic digits being accepted by the old parser. The regression includes overflow, which Spring ignores because a long cannot represent it. Source inspection found trim() before digit validation. The trailing-space result has not been observed at runtime.

**Technical notes.** The reader and its tests are in spring-web. For the WebClient boundary use spring-webflux with the standard SSE reader and a finite stream. Probe event metadata directly; a String-only subscription conceals this field.

**Sources.** [ServerSentEventHttpMessageReader.java](https://github.com/spring-projects/spring-framework/blob/adbc8ceeab6e004ad8664c2ff5639449c18f2396/spring-web/src/main/java/org/springframework/http/codec/ServerSentEventHttpMessageReader.java) · [ServerSentEventHttpMessageReaderTests.java](https://github.com/spring-projects/spring-framework/blob/adbc8ceeab6e004ad8664c2ff5639449c18f2396/spring-web/src/test/java/org/springframework/http/codec/ServerSentEventHttpMessageReaderTests.java) · [spring-web build](https://github.com/spring-projects/spring-framework/blob/adbc8ceeab6e004ad8664c2ff5639449c18f2396/spring-web/spring-web.gradle) · [EventSource Recommendation §5, field interpretation](https://www.w3.org/TR/2015/REC-eventsource-20150203/#event-stream-interpretation)
