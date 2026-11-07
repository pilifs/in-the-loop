package net.terminalvalue.crosscut.retry;

/**
 * A channel's retry throttle: the tokens it holds, in thousandths, under its limits. It is mutable, and shared: the
 * channel keeps one, every call on the channel records its outcome in it, and a retry is made only while it holds
 * more than half its tokens, so that a failing backend is not sent a storm of retries (gRPC's retry throttling).
 *
 * <p>A throttle starts full, as gRPC's does: {@code maxTokens} tokens.
 */
public final class Throttle {

    final ThrottleLimits limits;
    int milliTokens;

    public Throttle(ThrottleLimits limits) {
        this.limits = limits;
        this.milliTokens = limits.maxTokens() * 1000;
    }

    /** The tokens held, in thousandths. */
    public int milliTokens() {
        return milliTokens;
    }

    public ThrottleLimits limits() {
        return limits;
    }
}
