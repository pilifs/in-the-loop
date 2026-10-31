package net.terminalvalue.crosscut.resilience;

/**
 * What a circuit breaker reacts to. The metrics (the sliding window of outcomes, the count of probe calls, the
 * wait timer) live in the component that owns the breaker; the kernel sees them as the booleans it decides on.
 */
public sealed interface BreakerEvent {

    /** A caller asks to make a call. {@code waitElapsed} says whether the open state's wait duration has passed. */
    record CallRequested(boolean waitElapsed) implements BreakerEvent {}

    /**
     * A permitted call finished. {@code failed} says whether it counts as a failure, {@code windowComplete} whether
     * enough calls have been recorded to judge (the minimum number of calls in CLOSED, the permitted number of
     * probes in HALF_OPEN), and {@code thresholdExceeded} whether the failure rate of the window is at or above
     * the threshold.
     */
    record CallCompleted(boolean failed, boolean windowComplete, boolean thresholdExceeded) implements BreakerEvent {}
}
