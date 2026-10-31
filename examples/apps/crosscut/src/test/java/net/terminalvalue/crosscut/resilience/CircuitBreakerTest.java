package net.terminalvalue.crosscut.resilience;

import static net.terminalvalue.crosscut.Tests.check;
import static net.terminalvalue.crosscut.Tests.equal;
import static net.terminalvalue.crosscut.resilience.BreakerState.CLOSED;
import static net.terminalvalue.crosscut.resilience.BreakerState.HALF_OPEN;
import static net.terminalvalue.crosscut.resilience.BreakerState.OPEN;

import java.util.List;
import net.terminalvalue.crosscut.Decision;
import net.terminalvalue.crosscut.Decision.Transition;
import net.terminalvalue.crosscut.resilience.BreakerEvent.CallCompleted;
import net.terminalvalue.crosscut.resilience.BreakerEvent.CallRequested;

public final class CircuitBreakerTest {

    private CircuitBreakerTest() {}

    public static void closedPermitsCalls() {
        equal(new Transition<>(CLOSED, List.of(BreakerEffect.PERMIT)), CircuitBreaker.decide(CLOSED, new CallRequested(false)));
    }

    public static void closedOpensWhenACompleteWindowFailsTooOften() {
        equal(new Transition<>(OPEN, List.of(BreakerEffect.START_WAIT)), CircuitBreaker.decide(CLOSED, new CallCompleted(true, true, true)));
        check(CircuitBreaker.decide(CLOSED, new CallCompleted(true, false, true)) instanceof Decision.Unchanged, "too few calls to judge");
    }

    public static void openRejectsUntilTheWaitHasPassed() {
        check(CircuitBreaker.decide(OPEN, new CallRequested(false)) instanceof Decision.Rejected, "rejected");
        equal(new Transition<>(HALF_OPEN, List.of(BreakerEffect.RESET_METRICS, BreakerEffect.PERMIT)),
                CircuitBreaker.decide(OPEN, new CallRequested(true)));
    }

    public static void aFailedProbeReopens() {
        equal(new Transition<>(OPEN, List.of(BreakerEffect.START_WAIT)), CircuitBreaker.decide(HALF_OPEN, new CallCompleted(true, false, false)));
    }

    public static void halfOpenClosesWhenEveryProbeSucceeded() {
        equal(new Transition<>(CLOSED, List.of(BreakerEffect.RESET_METRICS)), CircuitBreaker.decide(HALF_OPEN, new CallCompleted(false, true, false)));
    }
}
