package net.terminalvalue.quorum.twopc;

import static net.terminalvalue.quorum.Tests.equal;

import java.util.List;
import net.terminalvalue.quorum.Decision.Transition;
import net.terminalvalue.quorum.twopc.RecoveryEvent.Restarted;

public final class RecoveryTest {

    private RecoveryTest() {}

    public static void sendsALoggedCommitAgain() {
        equal(new Transition<>(Phase.COMMITTED, List.of(CoordinatorEffect.SEND_COMMIT)),
                Recovery.decide(Phase.COMMITTED, new Restarted()));
    }

    public static void sendsALoggedAbortAgain() {
        equal(new Transition<>(Phase.ABORTED, List.of(CoordinatorEffect.SEND_ABORT)),
                Recovery.decide(Phase.ABORTED, new Restarted()));
    }

    public static void presumesAbortWithoutALoggedDecision() {
        equal(new Transition<>(Phase.ABORTED, List.of(CoordinatorEffect.SEND_ABORT)),
                Recovery.decide(Phase.COLLECTING, new Restarted()));
    }
}
