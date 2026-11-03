package net.terminalvalue.quorum.twopc;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.Tests.equal;

import java.util.List;
import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.Decision.Transition;
import net.terminalvalue.quorum.twopc.CoordinatorEvent.Tally;
import net.terminalvalue.quorum.twopc.CoordinatorEvent.Timeout;

public final class CoordinatorTest {

    private CoordinatorTest() {}

    public static void commitsWhenEveryoneVotedYes() {
        equal(new Transition<>(Phase.COMMITTED, List.of(CoordinatorEffect.SEND_COMMIT)),
                Coordinator.decide(Phase.COLLECTING, new Tally(true, true)));
    }

    public static void abortsWhenAnyoneVotedNo() {
        equal(new Transition<>(Phase.ABORTED, List.of(CoordinatorEffect.SEND_ABORT)),
                Coordinator.decide(Phase.COLLECTING, new Tally(true, false)));
    }

    public static void waitsWhileVotesAreMissing() {
        check(Coordinator.decide(Phase.COLLECTING, new Tally(false, true)) instanceof Decision.Unchanged, "wait");
    }

    public static void abortsOnTimeout() {
        equal(new Transition<>(Phase.ABORTED, List.of(CoordinatorEffect.SEND_ABORT)),
                Coordinator.decide(Phase.COLLECTING, new Timeout(false)));
    }

    public static void aDecisionIsFinal() {
        check(Coordinator.decide(Phase.COMMITTED, new Timeout(true)) instanceof Decision.Unchanged, "committed stays");
        check(Coordinator.decide(Phase.ABORTED, new Tally(true, true)) instanceof Decision.Unchanged, "aborted stays");
    }
}
