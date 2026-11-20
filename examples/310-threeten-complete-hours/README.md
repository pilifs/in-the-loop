# ThreeTenBP complete hours across midnight

The adapter maps each quarter-hour tick from 0 through 191 to a local time on June 15 or 16, 2012. It invokes LocalDateTime.until once with ChronoUnit.HOURS. The JVM driver constructs its direct-call timestamps independently by adding minutes to midnight. It compares those calls with the adapter on all 36,864 ordered pairs, including backward intervals and midnight crossings. [Upstream repair](https://github.com/ThreeTen/threetenbp/commit/f0b2eaf1856b7fb5fdf78de3cedc9781b6619b88)

On the original classes the signed-minute oracle disagrees on 6,912 pairs before the repair and zero after it. Both revisions satisfy the same-day and sign-reversal checks. At ticks 94 and 97, the parent returns 1 hour forward and −1 backward. The fix returns zero in both directions.

The adapter matched the separately constructed direct call on all 36,864 pairs for each revision. Recompiling its one delegation with MINUTES produced 36,672 correspondence failures on each revision. [Artifact identities and counts](records/adapter-correspondence.json)

The original strict checker stopped while constructing the nanoseconds constant in `Duration`. Running the selected JDK’s `BigInteger.valueOf(long)` bytecode reached the duration parser. Checking its case-insensitive bracket ranges then reached service discovery in `Chronology`. A separate experiment used JVM-observed initializer state. When it observed both classes, the checker stopped on the chronology registry’s `ConcurrentHashMap` field. [Four diagnostics and their qualifications](records/initialization-probes.json)

All five strict retries on the original byte bindings stop at `ServiceLoader.load` in `Chronology.<clinit>` at line 148. On ticks 94 and 97, the public JVM witness review records one hour on the parent and zero on the fix. The same-day precondition rejects the input. [Pinned retry job](../../verification/results/20261119-231539-retry-threetenbp-hours-after-exact-jdk-a/result.json) · [Parent replay](receipts/clock-parent/executions/20261119T232013Z-9d88632d/replay.json) · [Fixed replay](receipts/clock-fix/executions/20261119T232018Z-043aab4b/replay.json) · [Domain rejection](receipts/same-day/executions/20261119T232022Z-d0a985eb/replay.json)

Each refusal packet records its claim key, revision, invocation, class digests and the checker’s diagnostic. [Per-claim refusal records](records/refusals)

## Native checks with observed chronology

Four fresh JVMs compared service discovery on the same prepared adapter and upstream JARs. With an empty context resource directory, 23:30 to 00:15 returned one hour on the parent and zero on the fix. A constructed context descriptor naming an unavailable provider caused both calls to throw `java.util.ServiceConfigurationError`. The application class loader saw zero provider descriptors throughout. Reproduce the control with `python3 -I examples/310-threeten-complete-hours/controls/check_correspondence.py --context-only`. [Service context evidence](records/service-context.json)

The prepared adapter and upstream source-slice JARs contain no service descriptor for Chronology. On that classpath, Temurin 21.0.13+9 initialized two distinct empty registries. The qualified claims bind their contents and identities, the initializer class bytes on each revision, and the single-threaded String-key ConcurrentHashMap model. They use unwind 32 to cover the 24 cached hours in LocalTime. At unwind 16 the checker stopped at that table. [JVM state, checker digests and capped probes](records/registry-probes.json)

| Obligation | Native result |
|---|---|
| Parent agreement with elapsed minutes, all 36,864 pairs | Refuted. From 18:30 to 07:15 the next day, ticks 74 and 125, the JVM reproduced 13 hours for 12 hours and 45 minutes elapsed. [Witness](receipts/clock-parent-observed/executions/20261120T000707Z-4cb75a77/replay.json) |
| Fix agreement with elapsed minutes, all 36,864 pairs | Open after the 600-second checker budget. [Attempt and resources](records/refusals/clock-fix-observed.json) |
| Same-day preservation, all 18,432 admitted pairs | Established non-vacuously across both original revisions. [Receipt](receipts/same-day-observed/20261120T000707Z-4ca562e1/result.json) |
| Reversing endpoints, all 36,864 pairs on each revision | Both open after 600 seconds apiece. [Parent attempt](records/refusals/reversal-parent-observed.json) · [Fixed attempt](records/refusals/reversal-fix-observed.json) |
| Every sub-hour midnight crossing, 12 pairs in both directions combined | The parent claim was refuted and the fix was established. At 23:45 to 00:30, the parent returned one hour. [Parent witness](receipts/clock-parent-short-crossings/executions/20261120T001840Z-d3b45559/replay.json) · [Fixed receipt](receipts/clock-fix-short-crossings/20261120T001851Z-e0f10b94/result.json) |

An independent direct JVM enumeration returned +1 or −1 hour on all twelve sub-hour crossings on the parent, and zero on all twelve on the fix. The first verification job for this subset stopped during batch argument parsing. Its linked replacement ran both frozen tasks with the requested 120-second budget. [Direct results](records/short-crossings.json) · [First job](../../verification/results/20261120-000646-prove-the-twelve-sub-hour-crossings-at-t/result.json) · [Completed batch](../../verification/results/20261120-001338-prove-the-twelve-sub-hour-crossings-at-t/result.json)
