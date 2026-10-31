package net.terminalvalue.crosscut.cache;

/**
 * The expire-after-write test of a cache entry, with {@code Long.MAX_VALUE} as the time to live meaning "never", as
 * Caffeine and Spring's cache abstraction treat it. The clock reading is passed in, so that the cache can be
 * driven by a {@code Clock} in tests and by {@code System.nanoTime()} in production.
 */
public final class Expiry {

    private Expiry() {}

    public static final long FOREVER = Long.MAX_VALUE;

    /** Whether an entry written at {@code writtenAtNanos} with the given time to live has expired at {@code nowNanos}. */
    public static boolean isExpired(long writtenAtNanos, long ttlNanos, long nowNanos) {
        if (ttlNanos == FOREVER) {
            return false;
        }
        return nowNanos - writtenAtNanos >= ttlNanos;
    }
}
