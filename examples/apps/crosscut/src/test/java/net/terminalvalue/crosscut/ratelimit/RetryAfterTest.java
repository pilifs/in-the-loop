package net.terminalvalue.crosscut.ratelimit;

import static net.terminalvalue.crosscut.Tests.equal;
import static net.terminalvalue.crosscut.ratelimit.RetryAfter.nanosUntilToken;

public final class RetryAfterTest {

    private RetryAfterTest() {}

    private static final long PERIOD = 100_000_000L; // ten tokens per second

    public static void waitsNothingWhileATokenIsThere() {
        equal(0L, nanosUntilToken(1, 0, 0, PERIOD, 10));
        equal(0L, nanosUntilToken(0, 0, PERIOD, PERIOD, 10));
    }

    public static void waitsForTheRestOfThePeriodUnderWay() {
        long half = PERIOD / 2;
        equal(half, nanosUntilToken(0, 0, half, PERIOD, 10));
        equal(PERIOD - 1, nanosUntilToken(0, 0, 1, PERIOD, 10));
    }

    public static void waitsAWholePeriodRightAfterACredit() {
        equal(PERIOD, nanosUntilToken(0, 0, 0, PERIOD, 10));
    }
}
