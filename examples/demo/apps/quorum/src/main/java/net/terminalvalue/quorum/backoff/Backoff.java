package net.terminalvalue.quorum.backoff;

/**
 * Exponential backoff with a cap, for retrying RPCs to a peer that did not answer. Pure: the attempt number comes
 * in, the delay comes out, and a scheduler the caller owns does the waiting.
 */
public final class Backoff {

    private Backoff() {}

    /**
     * The delay before attempt number {@code attempt} (the first retry is attempt 0): the base delay doubled per
     * attempt, never above the cap.
     */
    public static long delayMillis(int attempt, long baseMillis, long capMillis) {
        if (attempt < 0 || baseMillis <= 0 || capMillis < baseMillis) {
            throw new IllegalArgumentException("attempt >= 0, base > 0 and cap >= base are required");
        }
        // Doubling base 2^attempt times exceeds the cap exactly when base exceeds cap / 2^attempt, and that test
        // cannot overflow. From attempt 62 on, any base does.
        if (attempt >= 62 || baseMillis > (capMillis >> attempt)) {
            return capMillis;
        }
        return baseMillis << attempt;
    }
}
