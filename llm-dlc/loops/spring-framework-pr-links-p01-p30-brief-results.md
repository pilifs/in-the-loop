# Spring Framework P01–P30

All 31 intended changes across 30 pull requests appeared at the specified public APIs. All 30 controls matched on both revisions with identical outcomes. The campaign registered 94 merged predictions and tested each on both revisions in a fresh JVM. Of the 94 merged predictions, 91 matched and three were refuted. [Registered questions](spring-framework-pr-links-p01-p30-brief.md) · [Machine-readable audit](../../verification/merged-pr-links/p01-p30/audit.json)

## Results by pull request

| Example | What an application observed |
|---|---|
| [P01 · #37435](../../examples/478-spring-utf16-prefix/README.md) | A cut inside an emoji now drops the whole split pair. The strict UTF-8 encoder accepted the retained earlier emoji and the exact truncation suffix. |
| [P02 · #37349](../../examples/479-spring-annotation-arrays/README.md) | A scalar 7 now reads as primitive int[] through both the public annotation reader and a synthesized annotation. |
| [P03 · #36480](../../examples/480-spring-nested-return-type/README.md) | Resolving the interface type now recovers Collection<Optional<String>>. Sibling subclasses preserve distinct Long and String leaves without overrides. |
| [P04 · #36207](../../examples/481-spring-yaml-empty-values/README.md) | The new YAML hook retained a caller-selected marker for an empty mapping and both null scalars. An empty sequence still became an empty string. |
| [P05 · #21855](../../examples/482-spring-bracketed-map-key/README.md) | A balanced bracket inside a literal map key now selects the intended child. A quoted write left the similarly named decoy untouched. |
| [P06 · #37351](../../examples/483-spring-case-map-retry/README.md) | A failed computation now leaves size, iteration and case-insensitive membership in agreement. A successful retry keeps its own KEY spelling. |
| [P07 · #36626](../../examples/484-spring-mail-date-copy/README.md) | Ordinary message copies now retain the original 1234 ms through mutations of the input, getter and target. Both copy paths skipped a subclass's getter-provided date. |
| [P08 · #37596](../../examples/485-spring-retry-policy-snapshot/README.md) | A built retry policy now keeps its original exception rules. Its executor retried the file exception and returned 7 while the newer policy stopped after one call. |
| [P09 · #1912](../../examples/486-spring-session-binding/README.md) | Replacing a session attribute now unbinds the displaced listener before binding its replacement. Rebinding the same object was silent. |
| [P10 · #37531](../../examples/487-spring-multipart-file-cursors/README.md) | Two reads and a filesystem copy now returned all six in-memory upload bytes. Interleaved readers preserved independent positions at both storage thresholds. |
| [P11 · #1532](../../examples/488-spring-protobuf-http-flush/README.md) | The Google protobuf JSON response now round-trips both messages. The parent returned an empty short body and an incomplete 8192-byte prefix for the larger message. |
| [P12 · #37559](../../examples/489-spring-protobuf-json-lines/README.md) | The compact encoder now selects JSONL and produces two parseable records. The default printer produced 12 physical lines for those two messages, none independently parseable. |
| [P13 · #37202](../../examples/490-spring-multipart-empty-fields/README.md) | The servlet multipart converter now returns both an empty first field and an empty last field. Three fields under one name retained order and cardinality. |
| [P14 · #37059](../../examples/491-spring-jackson-pool/README.md) | After encoding one JSON object the recycler's acquisitions and returns now balance. Two successive NDJSON streams preserved an embedded quote and newline. |
| [P15 · #37159](../../examples/492-spring-interrupted-stream/README.md) | An interrupted empty read now throws with the interrupt flag set and cancels the source. A bulk read preserved three bytes at offset one before the next read threw. |
| [P16 · #22392](../../examples/493-spring-sql-comment-lines/README.md) | The merged SQL populator committed both original rows and ignored the sentinel in a line comment. The parent committed the first row and then failed. Its old three-argument direct client lost binary linkage on the merge. |
| [P17 · #37014](../../examples/494-spring-insert-key-columns/README.md) | Overlapping generated and supplied columns now fail during compilation. Correcting that same insert after failure returned a key identifying the only Sven row. |
| [P18 · #25305](../../examples/495-spring-database-startup/README.md) | Startup now uses JDBC isValid(1) when no SQL is configured. An invalid first loan and a throwing first loan each closed before the second was validated. |
| [P19 · #23562](../../examples/496-spring-mono-commit/README.md) | The transactional Mono now waited for the gated commit. A separate H2 connection saw zero matching rows at parent completion and one at merged completion. |
| [P20 · #29703](../../examples/497-spring-r2dbc-returned-loan/README.md) | A failed auto-commit restore now still releases the R2DBC loan. A rollback failure retained its translated cause and another checkout obtained the freed slot. |
| [P21 · #33533](../../examples/498-spring-fallback-selection/README.md) | A programmatically registered fallback now loses single-bean selection to the regular bean. The provider stream retained both singleton identities in either registration order. |
| [P22 · #35627](../../examples/499-spring-scoped-services/README.md) | The unqualified consumer now invokes D(L,C) through scoped proxies. An added archive delegate remains reachable by qualifier without changing that route. |
| [P23 · #22260](../../examples/500-spring-hibernate-named-beans/README.md) | The named Hibernate prototype now receives its originating Spring context. Named fallback creation retains X, and an absent name no longer resolves to a differently named Spring prototype. |
| [P24 · #34723](../../examples/501-spring-context-level-override/README.md) | A child-only override now preserves the parent greeting and field identity. Two different mocked children reused the identical parent with neither mock registered there. |
| [P25 · #32469](../../examples/502-spring-proxy-checked-error/README.md) | CGLIB advice now sees the original undeclared checked exception. The caller still receives its wrapper, and type-specific advice can recover normally. |
| [P26 · #28322](../../examples/503-spring-self-injected-listener/README.md) | The self-injected proxied listener now receives one callback per event. Its advice and the independent listener observed identical event objects on both publications. |
| [P27 · #30020](../../examples/504-spring-child-thread-events/README.md) | New child threads now share the recording test's events. In Jupiter the PER_CLASS and CONCURRENT combination was rejected with global parallelism both enabled and disabled. |
| [P28 · #33470](../../examples/505-spring-listener-propagation/README.md) | Event listener creation now rejects class-level REQUIRED. The method-level NOT_SUPPORTED override refreshed and received exactly one fallback event outside a transaction. |
| [P29 · #36556](../../examples/506-spring-cron-registration/README.md) | The new London cron overload and the explicit trigger fired at 08:00Z in July and 09:00Z in January, including with a Tokyo context clock. |
| [P30 · #36865](../../examples/507-spring-cron-hour-gap/README.md) | The merged cron returned Cairo's next two even hours on April 25 and New York's next legal midnight and 02:00 on March 9. Both parent schedules skipped a day. |

## Evidence and limits

Twenty-three comparisons use complete builds of the changed Spring modules and the corresponding project dependencies from each pin. Seven Spring 5.x comparisons use each pin's compiled production classes ahead of the identical released companions on both sides. The audit checks every class in those seven slices against the independent setup's class-by-class SHA-256 table and checks the loaded origins. The 7.1 snapshot dependencies are the bytes cached on November 26, 2026. P20 uses the available February 2023 Reactor and Micrometer snapshots identified by setup. [Build record and dependency dates](spring-framework-pr-links-p01-p30-brief-setup.md)

P04 compiled a small subclass separately against the two protected YAML signatures. The application caller compiled to identical bytes. P16 compiled the direct three-argument SQL client on the parent and executed that binary on both sides. Every other comparison used the same caller binary on both sides. The protobuf types, SQL script, multipart resources, Hibernate integration context and eager event listener fixtures are read by digest from the upstream Git revision. For P19 a JDBC-backed reactive transaction manager gates H2's physical commit. The public Spring operator is the original historical implementation.

The SQL script also refuted one parent prediction. With the original fixture and H2 auto-commit, the first row was already committed when the parent threw ScriptStatementFailedException. The original report described a missing terminator. The merged populator committed both intended rows. [SQL fixture, client linkage and independent readback](../../examples/493-spring-sql-comment-lines/README.md)

Run `python3 verification/merged-pr-links/audit.py --campaign p01-p30` to check the recorded evidence. Add `--replay` to recompile the callers and repeat all 188 original histories using the prepared cache.
