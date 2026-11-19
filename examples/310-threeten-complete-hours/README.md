# ThreeTenBP complete hours across midnight

The adapter maps each quarter-hour tick from 0 through 191 to a local time on June 15 or 16, 2012. It invokes LocalDateTime.until once with ChronoUnit.HOURS. The JVM driver constructs its direct-call timestamps independently by adding minutes to midnight. It compares those calls with the adapter on all 36,864 ordered pairs, including backward intervals and midnight crossings. [Upstream repair](https://github.com/ThreeTen/threetenbp/commit/f0b2eaf1856b7fb5fdf78de3cedc9781b6619b88)

On the original classes the signed-minute oracle disagrees on 6,912 pairs before the repair and zero after it. Both revisions satisfy the same-day and sign-reversal checks. At ticks 94 and 97, the parent returns 1 hour forward and −1 backward. The fix returns zero in both directions.

The adapter matched the separately constructed direct call on all 36,864 pairs for each revision. Recompiling its one delegation with MINUTES produced 36,672 correspondence failures on each revision. [Artifact identities and counts](records/adapter-correspondence.json)
