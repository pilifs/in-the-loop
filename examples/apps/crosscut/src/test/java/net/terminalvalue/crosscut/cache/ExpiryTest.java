package net.terminalvalue.crosscut.cache;

import static net.terminalvalue.crosscut.Tests.check;
import static net.terminalvalue.crosscut.cache.Expiry.isExpired;

public final class ExpiryTest {

    private ExpiryTest() {}

    private static final long SECOND = 1_000_000_000L;

    public static void expiresWhenTheTimeToLiveHasPassed() {
        check(!isExpired(10 * SECOND, 5 * SECOND, 14 * SECOND), "one second to go");
        check(isExpired(10 * SECOND, 5 * SECOND, 15 * SECOND), "exactly expired");
        check(isExpired(10 * SECOND, 5 * SECOND, 60 * SECOND), "long expired");
    }

    public static void foreverNeverExpires() {
        check(!isExpired(10 * SECOND, Expiry.FOREVER, Long.MAX_VALUE), "forever");
    }
}
