package net.terminalvalue.crosscut.resilience;

import static net.terminalvalue.crosscut.Decision.rejected;
import static net.terminalvalue.crosscut.Decision.transition;
import static net.terminalvalue.crosscut.Decision.unchanged;
import static net.terminalvalue.crosscut.resilience.BreakerEffect.PERMIT;
import static net.terminalvalue.crosscut.resilience.BreakerEffect.RESET_METRICS;
import static net.terminalvalue.crosscut.resilience.BreakerEffect.START_WAIT;
import static net.terminalvalue.crosscut.resilience.BreakerState.CLOSED;
import static net.terminalvalue.crosscut.resilience.BreakerState.HALF_OPEN;
import static net.terminalvalue.crosscut.resilience.BreakerState.OPEN;

import net.terminalvalue.crosscut.Decision;
import net.terminalvalue.crosscut.resilience.BreakerEvent.CallCompleted;
import net.terminalvalue.crosscut.resilience.BreakerEvent.CallRequested;

/**
 * The state machine of a circuit breaker (the CLOSED, OPEN and HALF_OPEN of Resilience4j's
 * {@code CircuitBreakerStateMachine}), as a total function from (state, event) to a decision.
 *
 * <p>CLOSED lets every call through and opens when a complete window's failure rate reaches the threshold. OPEN
 * rejects every call until the wait duration has passed, then lets a limited number of probe calls through as
 * HALF_OPEN. HALF_OPEN closes only once every permitted probe has completed with the failure rate below the
 * threshold; a probe that fails reopens the breaker at once.
 */
public final class CircuitBreaker {

    private CircuitBreaker() {}

    public static Decision<BreakerState, BreakerEffect> decide(BreakerState state, BreakerEvent event) {
        return switch (event) {
            case CallRequested request -> switch (state) {
                case CLOSED, HALF_OPEN -> transition(state, PERMIT);
                case OPEN -> request.waitElapsed()
                        ? transition(HALF_OPEN, RESET_METRICS, PERMIT)
                        : rejected("the circuit breaker is open");
            };
            case CallCompleted call -> switch (state) {
                case CLOSED -> call.windowComplete() && call.thresholdExceeded()
                        ? transition(OPEN, START_WAIT)
                        : unchanged("recorded in the sliding window");
                case OPEN -> unchanged("a call permitted before the breaker opened; its outcome is not recorded");
                case HALF_OPEN -> {
                    if (call.failed()) {
                        yield transition(OPEN, START_WAIT);
                    }
                    if (!call.windowComplete()) {
                        yield unchanged("more probes to go");
                    }
                    yield call.thresholdExceeded() ? transition(OPEN, START_WAIT) : transition(CLOSED, RESET_METRICS);
                }
            };
        };
    }
}
