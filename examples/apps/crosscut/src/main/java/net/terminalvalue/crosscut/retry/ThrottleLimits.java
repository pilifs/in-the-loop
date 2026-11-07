package net.terminalvalue.crosscut.retry;

/**
 * The limits of a channel's retry throttle, as a service config gives them (gRPC's {@code retryThrottling}): the
 * most tokens the throttle holds, and the tokens a successful call gives back, in thousandths of a token (a ratio of
 * 0.1 is 100), since the config gives the ratio to three decimal places.
 */
public record ThrottleLimits(int maxTokens, int tokenRatioMilli) {

    public ThrottleLimits {
        if (maxTokens <= 0 || maxTokens > 1000 || tokenRatioMilli <= 0 || tokenRatioMilli > 1_000_000) {
            throw new IllegalArgumentException("at most 1000 tokens, and a positive ratio of at most 1000");
        }
    }
}
