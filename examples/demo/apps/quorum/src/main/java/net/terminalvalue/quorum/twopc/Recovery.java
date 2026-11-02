package net.terminalvalue.quorum.twopc;

import static net.terminalvalue.quorum.Decision.transition;
import static net.terminalvalue.quorum.twopc.CoordinatorEffect.SEND_ABORT;
import static net.terminalvalue.quorum.twopc.CoordinatorEffect.SEND_COMMIT;
import static net.terminalvalue.quorum.twopc.Phase.ABORTED;
import static net.terminalvalue.quorum.twopc.Phase.COMMITTED;

import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.twopc.RecoveryEvent.Restarted;

/**
 * What a two-phase-commit coordinator does when it restarts after a crash (Gray, 1978; Mohan, Lindsay and
 * Obermarck, 1986). The coordinator logs each phase change before it acts on it, so what a crash can cost is the
 * step it was in: a decision logged but not yet sent. A logged decision is sent again, since the coordinator cannot
 * tell whether the first copy went out, and a participant that heard it ignores the second. No logged decision
 * means the transaction aborts, presumed abort: the votes the coordinator was collecting may have been lost with
 * it, and a participant that voted yes holds its locks until it hears something.
 */
public final class Recovery {

    private Recovery() {}

    public static Decision<Phase, CoordinatorEffect> decide(Phase logged, RecoveryEvent event) {
        return switch (event) {
            case Restarted _ -> switch (logged) {
                case COLLECTING -> transition(ABORTED, SEND_ABORT); // presumed abort
                case COMMITTED -> transition(COMMITTED, SEND_COMMIT);
                case ABORTED -> transition(ABORTED, SEND_ABORT);
            };
        };
    }
}
