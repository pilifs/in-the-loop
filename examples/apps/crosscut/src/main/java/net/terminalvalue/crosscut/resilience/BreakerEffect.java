package net.terminalvalue.crosscut.resilience;

/** What the component owning a circuit breaker does on the kernel's decision. */
public enum BreakerEffect {
    /** Let the call through. */
    PERMIT,
    /** Start the open state's wait timer. */
    START_WAIT,
    /** Clear the sliding window and the probe count. */
    RESET_METRICS
}
