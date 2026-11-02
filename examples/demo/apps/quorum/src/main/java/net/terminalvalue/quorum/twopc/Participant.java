package net.terminalvalue.quorum.twopc;

import static net.terminalvalue.quorum.Decision.rejected;
import static net.terminalvalue.quorum.Decision.transition;
import static net.terminalvalue.quorum.Decision.unchanged;
import static net.terminalvalue.quorum.twopc.ParticipantEffect.VOTE_NO;
import static net.terminalvalue.quorum.twopc.ParticipantEffect.VOTE_YES;
import static net.terminalvalue.quorum.twopc.ParticipantState.ABORTED;
import static net.terminalvalue.quorum.twopc.ParticipantState.COMMITTED;
import static net.terminalvalue.quorum.twopc.ParticipantState.PREPARED;

import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.twopc.ParticipantEvent.GiveUp;
import net.terminalvalue.quorum.twopc.ParticipantEvent.Learned;
import net.terminalvalue.quorum.twopc.ParticipantEvent.Prepare;
import net.terminalvalue.quorum.twopc.ParticipantEvent.Restarted;

/**
 * The rule of a two-phase-commit participant (Gray, 1978; Bernstein, Hadzilacos and Goodman, 1987): asked to
 * prepare, it votes yes and holds its locks, or votes no and aborts; while it has not voted it may give up on its
 * own; it applies the coordinator's decision once that is out; and on restarting after a crash it acts on the state
 * it logged. A participant that voted yes cannot decide alone: it holds its locks until the decision, through a
 * crash and a restart, which is the blocking property of two-phase commit. One that had not voted when it crashed
 * aborts, which is what the coordinator will presume once its timer fires: no vote went out, since a participant
 * logs its state before it sends its vote.
 */
public final class Participant {

    private Participant() {}

    public static Decision<ParticipantState, ParticipantEffect> decide(ParticipantState state, ParticipantEvent event) {
        return switch (event) {
            case Prepare prepare -> switch (state) {
                case WORKING -> prepare.able() ? transition(PREPARED, VOTE_YES) : transition(ABORTED, VOTE_NO);
                case PREPARED, COMMITTED, ABORTED -> rejected("already voted");
            };
            case GiveUp _ -> switch (state) {
                case WORKING -> transition(ABORTED);
                case PREPARED -> rejected("voted yes: holds its locks until the decision");
                case COMMITTED, ABORTED -> rejected("already decided");
            };
            case Learned learned -> switch (state) {
                case WORKING, PREPARED -> switch (learned.outcome()) {
                    case NONE -> unchanged("no decision yet");
                    case COMMIT -> transition(COMMITTED);
                    case ABORT -> transition(ABORTED);
                };
                case COMMITTED, ABORTED -> unchanged("already decided");
            };
            case Restarted _ -> switch (state) {
                case WORKING -> transition(ABORTED); // no vote went out: the coordinator will presume abort
                case PREPARED -> unchanged("holds its locks until the decision");
                case COMMITTED, ABORTED -> unchanged("already decided");
            };
        };
    }
}
