package net.terminalvalue.crosscut.ratelimit;

/**
 * How long a request the bucket refuses must wait for a token: Bucket4j's {@code nanosToWaitForRefill}, and the
 * {@code Retry-After} a gateway answers a refused request with. It is a function of the bucket's refill arithmetic in
 * {@link TokenBucket}: nothing when the refill at {@code nowNanos} leaves a token, else until the period under way
 * ends, which is the credited time plus a period, less now.
 */
public final class RetryAfter {

    private RetryAfter() {}

    /** The nanoseconds until a request refused at {@code nowNanos} finds a token, 0 when the refill leaves one. */
    public static long nanosUntilToken(long tokens, long lastNanos, long nowNanos, long periodNanos, long capacity) {
        if (TokenBucket.tokensAfter(tokens, lastNanos, nowNanos, periodNanos, capacity) > 0) {
            return 0;
        }
        return TokenBucket.lastAfter(tokens, lastNanos, nowNanos, periodNanos, capacity) + periodNanos - nowNanos;
    }
}
