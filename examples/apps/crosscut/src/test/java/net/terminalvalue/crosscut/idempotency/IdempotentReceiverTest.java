package net.terminalvalue.crosscut.idempotency;

import static net.terminalvalue.crosscut.Tests.check;
import static net.terminalvalue.crosscut.Tests.equal;
import static net.terminalvalue.crosscut.idempotency.KeyState.ABSENT;
import static net.terminalvalue.crosscut.idempotency.KeyState.COMPLETED;
import static net.terminalvalue.crosscut.idempotency.KeyState.IN_PROGRESS;

import java.util.List;
import net.terminalvalue.crosscut.Decision;
import net.terminalvalue.crosscut.Decision.Transition;
import net.terminalvalue.crosscut.idempotency.ReceiverEvent.Completed;
import net.terminalvalue.crosscut.idempotency.ReceiverEvent.Expired;
import net.terminalvalue.crosscut.idempotency.ReceiverEvent.Failed;
import net.terminalvalue.crosscut.idempotency.ReceiverEvent.Request;

public final class IdempotentReceiverTest {

    private IdempotentReceiverTest() {}

    public static void aNewKeyExecutes() {
        equal(new Transition<>(IN_PROGRESS, List.of(ReceiverEffect.EXECUTE)), IdempotentReceiver.decide(ABSENT, new Request(true)));
    }

    public static void aCompletedKeyReplaysTheResponse() {
        equal(new Transition<>(COMPLETED, List.of(ReceiverEffect.STORE_RESPONSE)), IdempotentReceiver.decide(IN_PROGRESS, new Completed()));
        equal(new Transition<>(COMPLETED, List.of(ReceiverEffect.REPLAY_RESPONSE)), IdempotentReceiver.decide(COMPLETED, new Request(true)));
    }

    public static void aKeyReusedForAnotherRequestIsRefused() {
        check(IdempotentReceiver.decide(COMPLETED, new Request(false)) instanceof Decision.Rejected, "422");
    }

    public static void aFailedAttemptReleasesTheKey() {
        equal(new Transition<>(ABSENT, List.of(ReceiverEffect.RELEASE_KEY)), IdempotentReceiver.decide(IN_PROGRESS, new Failed()));
    }

    public static void anExpiredKeyIsReleased() {
        equal(new Transition<>(ABSENT, List.of(ReceiverEffect.RELEASE_KEY)), IdempotentReceiver.decide(COMPLETED, new Expired()));
    }
}
