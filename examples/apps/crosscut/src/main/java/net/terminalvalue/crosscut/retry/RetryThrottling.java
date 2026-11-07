package net.terminalvalue.crosscut.retry;

/**
 * What a call's outcome does to its channel's retry throttle, and which throttle the channel keeps when its service
 * config changes (gRPC's retry throttling, proposal A6). The throttle is the state; these functions change it in
 * place, as every call on the channel shares it.
 */
public final class RetryThrottling {

    private RetryThrottling() {}

    /**
     * Records a call's outcome: a failure takes a token, never below none, and a success gives back the token ratio,
     * never above the limit. Returns whether a retry may be made now: only while the throttle holds more than half
     * its tokens.
     */
    public static boolean recorded(Throttle throttle, boolean failed) {
        int ceiling = throttle.limits.maxTokens() * 1000;
        if (failed) {
            throttle.milliTokens = throttle.milliTokens >= 1000 ? throttle.milliTokens - 1000 : 0;
        } else {
            int raised = throttle.milliTokens + throttle.limits.tokenRatioMilli();
            throttle.milliTokens = raised < ceiling ? raised : ceiling;
        }
        return throttle.milliTokens > ceiling / 2;
    }

    /**
     * The throttle the channel keeps after a service config update: the same one when the limits are unchanged, so
     * that the tokens its calls in flight have spent stay spent, and a full one under new limits.
     */
    public static Throttle reconfigured(Throttle throttle, ThrottleLimits limits) {
        if (limits.maxTokens() == throttle.limits.maxTokens() && limits.tokenRatioMilli() == throttle.limits.tokenRatioMilli()) {
            return throttle;
        }
        return new Throttle(limits);
    }
}
