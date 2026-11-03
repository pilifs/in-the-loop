package net.terminalvalue.crosscut.ratelimit;

import static net.terminalvalue.crosscut.Tests.equal;
import static net.terminalvalue.crosscut.ratelimit.TokenBucket.lastAfter;
import static net.terminalvalue.crosscut.ratelimit.TokenBucket.tokensAfter;

public final class TokenBucketTest {

    private TokenBucketTest() {}

    private static final long PERIOD = 100_000_000L; // ten tokens per second

    public static void earnsOneTokenPerPeriod() {
        equal(3L, tokensAfter(0, 0, 3 * PERIOD, PERIOD, 10));
        equal(3 * PERIOD, lastAfter(0, 0, 3 * PERIOD, PERIOD, 10));
    }

    public static void stopsAtTheCapacity() {
        equal(10L, tokensAfter(8, 0, 5 * PERIOD, PERIOD, 10));
    }

    public static void keepsThePartOfAPeriodNotYetEarned() {
        // Polled every half period: the first poll earns nothing and must not forget the half period that passed.
        long half = PERIOD / 2;
        equal(0L, tokensAfter(0, 0, half, PERIOD, 10));
        long last = lastAfter(0, 0, half, PERIOD, 10);
        equal(1L, tokensAfter(0, last, 2 * half, PERIOD, 10));
    }
}
