package net.terminalvalue.quorum.twopc;

import static net.terminalvalue.quorum.Decision.transition;
import static net.terminalvalue.quorum.Decision.unchanged;
import static net.terminalvalue.quorum.twopc.CoordinatorEffect.SEND_ABORT;
import static net.terminalvalue.quorum.twopc.CoordinatorEffect.SEND_COMMIT;
import static net.terminalvalue.quorum.twopc.Phase.ABORTED;
import static net.terminalvalue.quorum.twopc.Phase.COMMITTED;

import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.twopc.CoordinatorEvent.Tally;
import net.terminalvalue.quorum.twopc.CoordinatorEvent.Timeout;

/**
 * The decision rule of a two-phase-commit coordinator (Gray, 1978): commit when every participant voted yes, abort
 * when any voted no, and abort when the votes do not all arrive in time, because a participant that has not
 * answered may have aborted on its own.
 */
public final class Coordinator {

    private Coordinator() {}

    public static Decision<Phase, CoordinatorEffect> decide(Phase phase, CoordinatorEvent event) {
        return switch (event) {
            case Tally tally -> switch (phase) {
                case COLLECTING -> !tally.complete()
                        ? unchanged("waiting for the remaining votes")
                        : tally.unanimous() ? transition(COMMITTED, SEND_COMMIT) : transition(ABORTED, SEND_ABORT);
                case COMMITTED, ABORTED -> unchanged("already decided");
            };
            case Timeout _ -> switch (phase) {
                case COLLECTING -> transition(ABORTED, SEND_ABORT); // presumed abort
                case COMMITTED, ABORTED -> unchanged("already decided");
            };
        };
    }
}
