package net.terminalvalue.quorum.twopc;

import static net.terminalvalue.quorum.Tests.equal;

import java.util.List;
import net.terminalvalue.quorum.Decision.Rejected;
import net.terminalvalue.quorum.Decision.Transition;
import net.terminalvalue.quorum.Decision.Unchanged;
import net.terminalvalue.quorum.twopc.ParticipantEvent.GiveUp;
import net.terminalvalue.quorum.twopc.ParticipantEvent.Learned;
import net.terminalvalue.quorum.twopc.ParticipantEvent.Prepare;
import net.terminalvalue.quorum.twopc.ParticipantEvent.Restarted;

public final class ParticipantTest {

    private ParticipantTest() {}

    public static void votesYesAndHoldsItsLocks() {
        equal(new Transition<>(ParticipantState.PREPARED, List.of(ParticipantEffect.VOTE_YES)),
                Participant.decide(ParticipantState.WORKING, new Prepare(true)));
    }

    public static void votesNoAndAborts() {
        equal(new Transition<>(ParticipantState.ABORTED, List.of(ParticipantEffect.VOTE_NO)),
                Participant.decide(ParticipantState.WORKING, new Prepare(false)));
    }

    public static void givesUpOnlyWhileItHasNotVoted() {
        equal(new Transition<ParticipantState, ParticipantEffect>(ParticipantState.ABORTED, List.of()),
                Participant.decide(ParticipantState.WORKING, new GiveUp()));
        equal(new Rejected<>("voted yes: holds its locks until the decision"),
                Participant.decide(ParticipantState.PREPARED, new GiveUp()));
    }

    public static void appliesTheDecisionOnce() {
        equal(new Transition<ParticipantState, ParticipantEffect>(ParticipantState.COMMITTED, List.of()),
                Participant.decide(ParticipantState.PREPARED, new Learned(Outcome.COMMIT)));
        equal(new Unchanged<>("no decision yet"),
                Participant.decide(ParticipantState.PREPARED, new Learned(Outcome.NONE)));
        equal(new Unchanged<>("already decided"),
                Participant.decide(ParticipantState.COMMITTED, new Learned(Outcome.COMMIT)));
    }

    public static void aRestartHoldsALoggedYesAndAbortsWithoutOne() {
        equal(new Unchanged<>("holds its locks until the decision"),
                Participant.decide(ParticipantState.PREPARED, new Restarted()));
        equal(new Transition<ParticipantState, ParticipantEffect>(ParticipantState.ABORTED, List.of()),
                Participant.decide(ParticipantState.WORKING, new Restarted()));
    }
}
