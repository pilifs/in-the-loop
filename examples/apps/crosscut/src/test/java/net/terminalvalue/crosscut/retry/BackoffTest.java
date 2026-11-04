package net.terminalvalue.crosscut.retry;

import static net.terminalvalue.crosscut.Tests.check;

public final class BackoffTest {

    private BackoffTest() {}

    public static void doublesFromTheBase() {
        Backoff backoff = new Backoff(100, 10_000);
        check(backoff.delayMillis(0) == 100, "first attempt waits the base");
        check(backoff.delayMillis(1) == 200, "second attempt waits twice the base");
        check(backoff.delayMillis(3) == 800, "fourth attempt waits eight times the base");
    }

    public static void stopsAtTheCap() {
        Backoff backoff = new Backoff(100, 1_000);
        check(backoff.delayMillis(4) == 1_000, "the cap, not 1600");
        check(backoff.delayMillis(40) == 1_000, "the cap, however many attempts");
    }

    public static void rejectsAnEmptyOrEndlessPolicy() {
        boolean rejected = false;
        try {
            new Backoff(0, 1_000);
        } catch (IllegalArgumentException e) {
            rejected = true;
        }
        check(rejected, "a zero base");
        rejected = false;
        try {
            new Backoff(100, Backoff.MAX_CAP_MILLIS + 1);
        } catch (IllegalArgumentException e) {
            rejected = true;
        }
        check(rejected, "a cap beyond a day");
    }
}
