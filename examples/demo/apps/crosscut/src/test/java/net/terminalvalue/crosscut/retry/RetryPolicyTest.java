package net.terminalvalue.crosscut.retry;

import static net.terminalvalue.crosscut.Tests.check;

public final class RetryPolicyTest {

    private RetryPolicyTest() {}

    public static void retriesWhatTheServerDidNotProcess() {
        check(RetryPolicy.shouldRetry(503, false, 0, 3), "503 for a POST");
        check(RetryPolicy.shouldRetry(429, false, 0, 3), "429 for a POST");
    }

    public static void doesNotRetryANonIdempotentRequestThatMayHaveRun() {
        check(!RetryPolicy.shouldRetry(500, false, 0, 3), "500 for a POST");
        check(!RetryPolicy.shouldRetry(504, false, 0, 3), "504 for a POST");
    }

    public static void retriesIdempotentRequestsOnServerErrors() {
        check(RetryPolicy.shouldRetry(500, true, 0, 3), "500 for a GET");
        check(RetryPolicy.shouldRetry(502, true, 0, 3), "502 for a GET");
        check(RetryPolicy.shouldRetry(504, true, 0, 3), "504 for a GET");
        check(RetryPolicy.shouldRetry(408, true, 0, 3), "408 for a GET");
    }

    public static void neverRetriesWhatNoRetryCanFix() {
        check(!RetryPolicy.shouldRetry(501, true, 0, 3), "501");
        check(!RetryPolicy.shouldRetry(400, true, 0, 3), "400");
        check(!RetryPolicy.shouldRetry(404, true, 0, 3), "404");
    }

    public static void stopsAtTheLastAttempt() {
        check(RetryPolicy.shouldRetry(503, true, 2, 3), "one attempt left");
        check(!RetryPolicy.shouldRetry(503, true, 3, 3), "no attempt left");
    }
}
