# ThreeTenBP complete hours across midnight

The adapter maps each quarter-hour tick from 0 through 191 to a local time on June 15 or 16, 2012. It invokes LocalDateTime.until once with ChronoUnit.HOURS. The JVM driver constructs its direct-call timestamps independently by adding minutes to midnight. It compares those calls with the adapter on all 36,864 ordered pairs, including backward intervals and midnight crossings. [Upstream repair](https://github.com/ThreeTen/threetenbp/commit/f0b2eaf1856b7fb5fdf78de3cedc9781b6619b88)

On the original classes the signed-minute oracle disagrees on 6,912 pairs before the repair and zero after it. Both revisions satisfy the same-day and sign-reversal checks. At ticks 94 and 97, the parent returns 1 hour forward and −1 backward. The fix returns zero in both directions.

The adapter matched the separately constructed direct call on all 36,864 pairs for each revision. Recompiling its one delegation with MINUTES produced 36,672 correspondence failures on each revision. [Artifact identities and counts](records/adapter-correspondence.json)

The original strict checker stopped while constructing the nanoseconds constant in `Duration`. Running the selected JDK’s `BigInteger.valueOf(long)` bytecode reached the duration parser. Checking its case-insensitive bracket ranges then reached service discovery in `Chronology`. A separate experiment used JVM-observed initializer state. When it observed both classes, the checker stopped on the chronology registry’s `ConcurrentHashMap` field. [Four diagnostics and their qualifications](records/initialization-probes.json)

All five strict retries on the original byte bindings stop at `ServiceLoader.load` in `Chronology.<clinit>` at line 148. On ticks 94 and 97, the public JVM witness review records one hour on the parent and zero on the fix. The same-day precondition rejects the input. [Pinned retry job](../../verification/results/20261119-231539-retry-threetenbp-hours-after-exact-jdk-a/result.json) · [Parent replay](receipts/clock-parent/executions/20261119T232013Z-9d88632d/replay.json) · [Fixed replay](receipts/clock-fix/executions/20261119T232018Z-043aab4b/replay.json) · [Domain rejection](receipts/same-day/executions/20261119T232022Z-d0a985eb/replay.json)

Each refusal packet records its claim key, revision, invocation, class digests and the checker’s diagnostic. [Per-claim refusal records](records/refusals)
