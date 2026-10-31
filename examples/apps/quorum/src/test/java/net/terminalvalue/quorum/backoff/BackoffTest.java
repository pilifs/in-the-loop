package net.terminalvalue.quorum.backoff;

import static net.terminalvalue.quorum.Tests.equal;
import static net.terminalvalue.quorum.Tests.throwsIllegalArgument;

public final class BackoffTest {

    private BackoffTest() {}

    public static void doublesPerAttempt() {
        equal(100L, Backoff.delayMillis(0, 100, 30_000));
        equal(200L, Backoff.delayMillis(1, 100, 30_000));
        equal(800L, Backoff.delayMillis(3, 100, 30_000));
    }

    public static void stopsAtTheCap() {
        equal(30_000L, Backoff.delayMillis(9, 100, 30_000));
        equal(30_000L, Backoff.delayMillis(20, 100, 30_000));
    }

    public static void refusesBadArguments() {
        throwsIllegalArgument(() -> Backoff.delayMillis(-1, 100, 30_000));
        throwsIllegalArgument(() -> Backoff.delayMillis(0, 0, 30_000));
        throwsIllegalArgument(() -> Backoff.delayMillis(0, 100, 50));
    }
}
