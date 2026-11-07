package net.terminalvalue.crosscut.retry;

import static net.terminalvalue.crosscut.Tests.check;

public final class RetryThrottlingTest {

    private RetryThrottlingTest() {}

    public static void startsFullAndRetriesWhileMoreThanHalfIsLeft() {
        Throttle throttle = new Throttle(new ThrottleLimits(4, 100));
        check(throttle.milliTokens() == 4000, "a throttle starts with its tokens");
        check(RetryThrottling.recorded(throttle, true), "3 of 4 tokens left: retry");
        check(!RetryThrottling.recorded(throttle, true), "2 of 4 is not more than half: no retry");
        check(throttle.milliTokens() == 2000, "a token taken per failure");
    }

    public static void aSuccessGivesBackTheRatioUpToTheLimit() {
        Throttle throttle = new Throttle(new ThrottleLimits(4, 600));
        RetryThrottling.recorded(throttle, true);
        RetryThrottling.recorded(throttle, false);
        check(throttle.milliTokens() == 3600, "0.6 of a token back");
        RetryThrottling.recorded(throttle, false);
        check(throttle.milliTokens() == 4000, "never above the limit");
    }

    public static void theSameLimitsKeepTheThrottleAndNewOnesStartAFullOne() {
        Throttle throttle = new Throttle(new ThrottleLimits(4, 100));
        RetryThrottling.recorded(throttle, true);
        Throttle kept = RetryThrottling.reconfigured(throttle, new ThrottleLimits(4, 100));
        check(kept.milliTokens() == 3000, "the spent token stays spent");
        Throttle fresh = RetryThrottling.reconfigured(throttle, new ThrottleLimits(10, 100));
        check(fresh.milliTokens() == 10_000, "new limits, a full throttle");
    }

    public static void rejectsLimitsOutsideTheServiceConfigsRange() {
        boolean rejected = false;
        try {
            new ThrottleLimits(0, 100);
        } catch (IllegalArgumentException e) {
            rejected = true;
        }
        check(rejected, "no tokens");
        rejected = false;
        try {
            new ThrottleLimits(4, 0);
        } catch (IllegalArgumentException e) {
            rejected = true;
        }
        check(rejected, "a zero ratio");
    }
}
