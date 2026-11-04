package net.terminalvalue.crosscut.ratelimit;

/**
 * A fixed-window request counter, the simplest rate limit: how many requests a client has made in the window its
 * last request fell in, with windows of one length aligned to the epoch (Spring Cloud Gateway's rate limiter keeps
 * such a count per key and window; Resilience4j's {@code RateLimiter} calls the window a cycle). The counter is a
 * value: the filter keeps one per client, replaces it on each request with what {@link #counted} returns, and
 * refuses the request when the count passes the limit. The clock reading and the window length are arguments, so
 * that the counter is a pure function.
 *
 * <p>A counter starts as {@code new Window(0, 0)}: no request yet, in the window at the epoch.
 */
public record Window(long startNanos, long count) {

    public Window {
        if (startNanos < 0 || count < 0) {
            throw new IllegalArgumentException("the start and the count must not be negative");
        }
    }

    /**
     * The counter after a request at {@code nowNanos}, with windows of {@code windowNanos}: one more in the same
     * window, or the first request of the window the reading falls in.
     */
    public Window counted(long nowNanos, long windowNanos) {
        if (windowNanos <= 0 || nowNanos < startNanos) {
            throw new IllegalArgumentException("the window must be positive and time must not go back");
        }
        long start = nowNanos - nowNanos % windowNanos;
        return start == startNanos ? new Window(startNanos, count + 1) : new Window(start, 1);
    }
}
