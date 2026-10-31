package net.terminalvalue.crosscut.resilience;

/** The states of a circuit breaker. */
public enum BreakerState {
    /** Calls go through; outcomes are recorded in the sliding window. */
    CLOSED,
    /** Calls are rejected until the wait duration has passed. */
    OPEN,
    /** A limited number of probe calls go through; their outcomes decide between CLOSED and OPEN. */
    HALF_OPEN
}
