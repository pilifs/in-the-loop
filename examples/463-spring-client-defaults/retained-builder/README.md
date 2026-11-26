# Appending to a header initialized with defaultHeader

Calling `builder.defaultHeader("X-Mode", "one")`, building a WebTestClient, and then calling `builder.defaultHeaders(h -> h.add("X-Mode", "two"))` on that **same builder** raised UnsupportedOperationException on both PR revisions and on Spring 7.0.10. The first client still sent its original header and cookie. Spring documents the consumer's headers as live and makes the HttpHeaders methods available to it. The convenience setter creates a fixed-size list. [Original builder API](https://github.com/spring-projects/spring-framework/blob/4cf6335372556d4f6ccc3a0166318c5f19037e8f/spring-test/src/main/java/org/springframework/test/web/reactive/server/WebTestClient.java) · [Builder implementation](https://github.com/spring-projects/spring-framework/blob/4cf6335372556d4f6ccc3a0166318c5f19037e8f/spring-test/src/main/java/org/springframework/test/web/reactive/server/DefaultWebTestClientBuilder.java)

| Initialization and edit | Parent | Merge | 7.0.10 |
|---|---|---|---|
| Seed with defaultHeader, retain the builder | Append threw | Append threw | Append threw |
| Seed with defaultHeaders/add, retain the builder | A and B both sent one and two | B sent both, A sent only one | A and B both sent one and two |
| Seed with defaultHeader, edit through A.mutate() | Append threw | B sent both, a fresh derivative of A sent only one | Append threw |

The initial investigation exposed the exception. These follow-up inputs record it explicitly and change one builder choice at a time. They run separately from the campaign's 63 original predictions. The HTTP handler records both header and cookie lists from the actual request. [Caller](caller/PublicCaller.java) · [Follow-up questions](comparison.json) · [Paired observations](observations.json) · [Release observations](release-observations.json)

To repeat the two pinned revisions, run `python3 examples/463-spring-client-defaults/retained-builder/check_builder.py`. For Spring 7.0.10 run `python3 verification/merged-pr-links/m01-m10/releases.py --inputs examples/463-spring-client-defaults/retained-builder/release-inputs.json --fetch`.
