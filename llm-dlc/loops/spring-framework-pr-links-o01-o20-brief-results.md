# Spring Framework changes at twenty public APIs

All 20 intended changes appeared on the specified parent and merge comparisons. All 20 controls returned identical observations on both sides. Of 63 registered merged predictions, 60 matched and three were refuted. Each of the 126 histories ran in a fresh JVM. [Registered questions](spring-framework-pr-links-o01-o20-brief.md) · [Build provenance](spring-framework-pr-links-o01-o20-brief-setup.md) · [Machine-readable audit](../../verification/merged-pr-links/o01-o20/audit.json)

## Results by pull request

| Example | What changed for the caller |
|---|---|
| [O01 · #37434](../../examples/458-spring-positive-hex/README.md) | Both hexadecimal prefixes now accept unary plus. The result still respects the requested numeric type and its bounds. |
| [O02 · #37576](../../examples/459-spring-sunday-cron/README.md) | A singleton Sunday range advanced from Thursday to Friday on the parent and to Sunday on the merge. |
| [O03 · #30238](../../examples/460-spring-inferred-matchers/README.md) | Recompiling the same unqualified Hamcrest call changed the method selected by javac for both headers and query parameters. |
| [O04 · #36913](../../examples/461-spring-optional-conversion/README.md) | Spring stopped offering an Optional<Integer> to LocalDate conversion when its default converters could not supply it. |
| [O05 · #30045](../../examples/462-spring-bound-functions/README.md) | A parsed SpEL function now invokes its bound Java receiver and sees a replacement binding on the next evaluation. |
| [O06 · #37325](../../examples/463-spring-client-defaults/README.md) | All three HTTP clients isolated an edited default header and cookie list from a second derivative of the base client. |
| [O07 · #37378](../../examples/464-spring-rendering-cookies/README.md) | Rebuilding a rendering response retained cookies, including two currencies with different paths, at both HTTP boundaries. |
| [O08 · #37218](../../examples/465-spring-resource-ranges/README.md) | Four resource routes agreed on the status, Content-Range and body for stale, matching, weak and date validators. |
| [O09 · #37193](../../examples/466-spring-sse-retry/README.md) | The merge delivered both events after an invalid retry hint. It still accepted a trailing space as part of a 25 ms retry. |
| [O10 · #36714](../../examples/467-spring-joined-buffers/README.md) | The merged synchronous writer traversed every component, including when the destination accepted one byte at a time. |
| [O11 · #1366](../../examples/468-spring-json-operators/README.md) | The pinned named-parameter parser preserved both PostgreSQL JSON operators and bound only the application parameter. |
| [O12 · #37308](../../examples/469-spring-batch-keys/README.md) | The merge eliminated redundant first-row bindings, and two actual generated keys identified the two inserted H2 rows. |
| [O13 · #30530](../../examples/470-spring-r2dbc-mappers/README.md) | Both new R2DBC mappers read the row. Strict constructor mapping nevertheless rejected a complete one-property result. |
| [O14 · #25256](../../examples/471-spring-cancel-transaction/README.md) | The pinned reactive operator rolled back cancellation at the merge. Moving take(1) inside its transaction preserved the row. |
| [O15 · #31133](../../examples/472-spring-nested-savepoints/README.md) | Both nested R2DBC scopes preserved the enclosing transaction on the merge. Its outer rollback removed even the successful inner write. |
| [O16 · #31699](../../examples/473-spring-resource-collections/README.md) | An XML context populated both a resource list and a resource set from a single file on the merge. |
| [O17 · #37047](../../examples/474-spring-generic-dao/README.md) | Typed bean lookup retained the advised User proxy while continuing to reject an Order token for that same bean name. |
| [O18 · #29116](../../examples/475-spring-jms-replacement/README.md) | After reset the merged JMS factory recovered on C. Direct reinitialization followed by the same failure left the retry on closed A. |
| [O19 · #37403](../../examples/476-spring-retry-cache/README.md) | The merged cache advice resubscribed after failure, delivered the successful attempt, and kept failed-attempt data out of the cache. |
| [O20 · #37600](../../examples/477-spring-flux-context/README.md) | On a cache miss, the merged Flux saw the subscriber's context. After explicit eviction a new subscription saw the replacement value. |

## Evidence and scope

Examples 458–477 use 18 complete pairs of Spring module builds. Two older builds have missing Gradle plugins or Kotlin prereleases. O11 and O14 compile the changed Java class directly from each registered Git commit on a common released classpath. The replay checks the Git blob and SHA-256 before compilation, hashes the resulting classes, and verifies their origins in each running JVM. O11 uses Spring JDBC 5.0.0.M5, pgJDBC 42.7.15 and PostgreSQL 17.12. O14 uses Spring 5.3.0-M1 and R2DBC H2, with an independent read after transaction cleanup. The 7.1 snapshot dependencies are the bytes preserved by setup on 25 November 2026. [Preparation and historical build limits](spring-framework-pr-links-o01-o20-brief-setup.md)

O03 compiles identical Java source independently on each classpath. The recorded invocation descriptors show that the inferred header and query calls selected a single Matcher on the parent and a Matcher array on the merge. The explicitly typed controls selected the array on both. Each other pair runs identical compiled caller bytecode across its two revisions. [Compiled call sites](../../examples/460-spring-inferred-matchers/observations.json)

## Findings for upstream review

- **SSE retry hints.** A trailing ASCII space after 25 still produced a 25 ms retry. Both events delivered their data. On the parent the nonnumeric hint surfaced publicly as WebClientResponseException with NumberFormatException as its cause, accounting for the one parent prediction refutation. [Event envelopes and terminal signals](../../examples/466-spring-sse-retry/README.md)
- **Strict R2DBC mapping.** A real driver row supplying the sole writable property succeeded through the constructor with default settings and threw InvalidDataAccessApiUsageException under strict checking. [Constructor and setter observations](../../examples/470-spring-r2dbc-mappers/README.md)
- **JMS recovery.** After direct reinitialization closed A and preparing B failed, the first merged retry reached closed A. After an explicit reset the same provider recovered on C. [Physical connection and session observations](../../examples/475-spring-jms-replacement/README.md)

Run `python3 verification/merged-pr-links/audit.py --campaign o01-o20` for the offline audit. Add `--replay` to recompile the callers, start the PostgreSQL fixture and repeat the comparisons with the prepared cache.

The same historical caller binaries also ran nine histories on released Spring 7.0.10. The trailing-space SSE delay and the closed JMS connection reproduced. Spring removed the strict R2DBC setter in August 2023, and the original strict call reaches NoSuchMethodError on the release. [Reproduction and upstream status](../../verification/merged-pr-links/o01-o20/upstream.md)

A separate WebTestClient follow-up ran six histories against the PR pins and three on 7.0.10. Seeding a header with defaultHeader left the same retained builder unable to append to it on all three deployments. Initializing through the consumer allowed the append. On the merge a fresh derivative also accepted the convenience-initialized header. [Initializer and builder comparison](../../examples/463-spring-client-defaults/retained-builder/README.md)

## Independent verification

The full comparison job repeated all 126 original histories and returned a byte-identical campaign audit. The debugger job ran each intent, control and challenge twice per revision at the original SSE event builder and JMS connection initializer. All 24 trials matched their public observations. Both collected reports passed a separate check of the invocation sites, caller bytecode, ordered classpaths and results. [Full replay](../../verification/jobs/2026/11/26/20261126-014520-replay-63-spring-predictions-across-20-p.json) · [Original-method traces](../../verification/jobs/2026/11/26/20261126-014529-trace-the-spring-sse-and-jms-public-coun.json)

The first independent 7.0.10 job reproduced all nine release observations and all class hashes. Its byte comparison failed because filesystem enumeration gave the class-name keys a different order. Sorting only those keys made the saved result byte-identical. The release runner now writes class hashes in sorted order. [First release comparison](../../verification/jobs/2026/11/26/20261126-015446-recheck-three-spring-counterexamples-on.json) · [Repeat including the builder follow-up](../../verification/jobs/2026/11/26/20261126-015908-recheck-three-spring-counterexamples-on.json)

A second check replaced direct controller return-value processing with a GET through DispatcherServlet and an annotated handler. Each request reached the mapped method exactly once. All eight parent and merge histories returned the same status, Content-Range and body as the first full replay. The runtime now checks the origins of DispatcherServlet, its response processor and all three other resource-serving implementations. [Mapped controller and route observations](../../examples/465-spring-resource-ranges/README.md)
