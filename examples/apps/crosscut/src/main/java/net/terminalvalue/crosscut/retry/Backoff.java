package net.terminalvalue.crosscut.retry;

/**
 * How long a retry waits: an exponential backoff from {@code baseMillis}, doubled on each attempt, never longer
 * than {@code capMillis}. The policy is a value, held by the retry filter (Spring Retry's
 * {@code ExponentialBackOffPolicy}, Resilience4j's {@code IntervalFunction.ofExponentialBackoff}), and the delay
 * is a pure function of it and the attempt count; the scheduler does the waiting.
 *
 * <p>The base is positive, the cap at least the base and at most a day: a wait longer than that is a configuration
 * error, and within these bounds the doubling never leaves the range of a {@code long}.
 */
public record Backoff(long baseMillis, long capMillis) {

    public static final long MAX_CAP_MILLIS = 86_400_000L;

    public Backoff {
        if (baseMillis <= 0 || capMillis < baseMillis || capMillis > MAX_CAP_MILLIS) {
            throw new IllegalArgumentException("base must be positive and the cap between the base and a day");
        }
    }

    /**
     * The delay before the given attempt: the base doubled {@code attempt} times, stopping at the cap. The first
     * attempt (zero) waits the base, and so does any earlier one.
     */
    public long delayMillis(int attempt) {
        long delay = baseMillis;
        for (int i = 0; i < attempt && delay < capMillis; i++) {
            delay = Math.min(capMillis, delay * 2);
        }
        return delay;
    }
}
