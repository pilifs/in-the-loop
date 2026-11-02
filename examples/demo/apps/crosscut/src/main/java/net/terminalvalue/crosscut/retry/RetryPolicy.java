package net.terminalvalue.crosscut.retry;

/**
 * Whether a failed HTTP call may be retried. Pure: the status, whether the request is idempotent (a GET, PUT or
 * DELETE, or a POST with an idempotency key) and the attempt count come in, the answer comes out, and the client's
 * scheduler does the waiting.
 */
public final class RetryPolicy {

    private RetryPolicy() {}

    /**
     * Retry when attempts remain and the status says the server did not process the request (429, 503), or, for an
     * idempotent request only, that it may not have (408, and the 5xx range except 501, which no retry will fix).
     */
    public static boolean shouldRetry(int status, boolean idempotent, int attempt, int maxAttempts) {
        if (attempt >= maxAttempts) {
            return false;
        }
        if (status == 429 || status == 503) {
            return true;
        }
        if (!idempotent) {
            return false;
        }
        return status == 408 || (status >= 500 && status <= 599 && status != 501);
    }
}
