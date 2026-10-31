package net.terminalvalue.crosscut.ratelimit;

/**
 * The refill arithmetic of a token bucket rate limiter (the model behind Spring Cloud Gateway's
 * {@code RequestRateLimiter} and Bucket4j): one token every {@code periodNanos}, up to {@code capacity}. The bucket's
 * state is two numbers, the tokens it holds and the time up to which refills have been credited, and a refill is a
 * pure function of them and the clock reading the caller passes in.
 */
public final class TokenBucket {

    private TokenBucket() {}

    /** The tokens in the bucket after crediting the refills earned between {@code lastNanos} and {@code nowNanos}. */
    public static long tokensAfter(long tokens, long lastNanos, long nowNanos, long periodNanos, long capacity) {
        long earned = (nowNanos - lastNanos) / periodNanos;
        return Math.min(capacity, tokens + earned);
    }

    /**
     * The time up to which refills have been credited after the refill: {@code lastNanos} advanced by the whole
     * periods that earned a token, which is {@code nowNanos} less the part of a period that has not earned one yet.
     * That part is kept, so that a bucket polled more often than it refills still refills.
     */
    public static long lastAfter(long tokens, long lastNanos, long nowNanos, long periodNanos, long capacity) {
        return nowNanos - (nowNanos - lastNanos) % periodNanos;
    }
}
